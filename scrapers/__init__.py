import importlib.util
import os
import pkgutil

from resources.lib import log_utils

debug = True

_SCRAPERS_ROOT = os.path.dirname(__file__)
_ADDON_ROOT = os.path.dirname(_SCRAPERS_ROOT)
_SITES_FOLDER = os.path.join(_ADDON_ROOT, 'sites')
_LEGACY_FOLDER = os.path.join(_SCRAPERS_ROOT, 'scrapers_source', 'de')
_MODULE_CACHE = {}


def _get_setting(setting_id):
    try:
        import xbmcaddon
    except Exception:
        return ''
    addon = xbmcaddon.Addon()
    try:
        return addon.getSetting(setting_id)
    finally:
        del addon


def _set_setting(setting_id, value):
    try:
        import xbmcaddon
    except Exception:
        return None
    addon = xbmcaddon.Addon()
    try:
        return addon.setSetting(setting_id, value)
    finally:
        del addon


def _folder_has_providers(folder):
    if not os.path.isdir(folder):
        return False
    return any(filename.endswith('.py') and not filename.startswith('__') for filename in os.listdir(folder))


def getActiveProviderFolder():
    if _folder_has_providers(_SITES_FOLDER):
        return _SITES_FOLDER
    return _LEGACY_FOLDER


def getProviderModuleNames():
    folder = getActiveProviderFolder()
    if not os.path.isdir(folder):
        return []
    return sorted(
        filename[:-3] for filename in os.listdir(folder)
        if filename.endswith('.py') and not filename.startswith('__')
    )


def _module_cache_key(spec, module_name):
    origin = getattr(spec, 'origin', None)
    if origin and os.path.isfile(origin):
        try:
            return origin, os.path.getmtime(origin)
        except OSError:
            pass
    return module_name, None


def _load_module(loader, module_name):
    if hasattr(loader, 'find_spec'):
        spec = loader.find_spec(module_name, None)
        if spec is None or spec.loader is None:
            raise ImportError('Unable to load scraper module: %s' % module_name)
        cache_key = _module_cache_key(spec, module_name)
        module = _MODULE_CACHE.get(cache_key)
        if module is not None:
            return module
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE_CACHE[cache_key] = module
        return module

    if hasattr(loader, 'find_module'):
        return loader.find_module(module_name).load_module(module_name)

    raise ImportError('Unable to load scraper module: %s' % module_name)


def sources(specified_folders=None):
    try:
        sourceDict = []
        folder = getActiveProviderFolder()
        if not os.path.isdir(folder):
            return sourceDict

        for loader, module_name, is_pkg in pkgutil.walk_packages([folder]):
            if is_pkg:
                continue
            if not enabledCheck(module_name):
                continue
            try:
                module = _load_module(loader, module_name)
                sourceDict.append((module_name, module.source()))
            except Exception as e:
                _set_setting('provider.' + module_name, 'false')
                if debug:
                    log_utils.log('Error: Loading module: "%s": %s' % (module_name, e), log_utils.LOGERROR)
        return sourceDict
    except Exception:
        return []


def enabledCheck(module_name):
    if _get_setting('provider.' + module_name) == 'false' or _get_setting('provider.' + module_name + '.check') == 'false':
        return False
    return True


def providerSources():
    return ['Sites']


def providerNames():
    return [module_name.split('_')[0] for module_name in getProviderModuleNames()]


def getAllHosters():
    return list(set(providerNames()))


def getScraperFolder(scraper_source):
    return os.path.basename(getActiveProviderFolder())


def getModuleName(scraper_folders):
    return providerSources()
