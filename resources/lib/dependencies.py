# edit 2026-06-13

import json
import os
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon

try:
    import xbmcvfs
except:
    xbmcvfs = None

try:
    import xbmcgui
except:
    xbmcgui = None

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen


ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = ADDON.getAddonInfo('path')
ADDON_VERSION = ADDON.getAddonInfo('version')

INSTALL_TIMEOUT = 90
INSTALL_OPTIONAL = False
DOWNLOAD_TIMEOUT = 20

# Kodi cannot resolve these dependencies from its official repository during a
# direct "install from zip" flow, so xVAULT bootstraps them from their upstream
# Kodi repositories after xVAULT itself has been installed.
REQUIRED_EXTERNAL_ADDONS = set(['script.module.resolveurl'])
AUTO_INSTALL_OPTIONAL_EXTERNALS = set([
    'script.module.download-m3u8',
    'inputstream.adaptive',
    'plugin.video.joyn',
    'plugin.video.joyn-at',
])
EXTERNAL_ADDON_SOURCES = {
    'script.module.resolveurl': {
        'repository_id': 'repository.resolveurl',
        'repository_zip_urls': [
            'https://gujal00.github.io/repository.resolveurl-1.0.0.zip',
            'https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/repository.resolveurl/repository.resolveurl-1.0.0.zip',
        ],
        'metadata_url': 'https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml',
        'datadir': 'https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/',
    },
    'script.module.download-m3u8': {
        'metadata_url': 'https://raw.githubusercontent.com/chrisklietsch/repository.kc-kodi/main/repo/addons.xml',
        'datadir': 'https://raw.githubusercontent.com/chrisklietsch/repository.kc-kodi/main/repo/',
    },
}

# Debug-only helper, not needed for normal playback/download features.
SKIP_OPTIONAL_INSTALL = set(['script.module.pydevd'])


def ensure_all_dependencies():
    """Install and enable missing Kodi dependencies before xVAULT imports them."""
    try:
        if _was_checked():
            return True

        dependencies = _dependencies_from_manifest()
        if not dependencies:
            _mark_checked()
            return True

        required = [
            addon_id
            for addon_id, optional, version in dependencies
            if _is_required(addon_id, optional)
        ]
        installable = [
            (addon_id, optional, version)
            for addon_id, optional, version in dependencies
            if _should_install(addon_id, optional)
        ]

        missing = [
            (addon_id, optional, version)
            for addon_id, optional, version in installable
            if not _has_addon(addon_id, version)
        ]
        if not missing:
            _enable_addons([addon_id for addon_id, optional, version in installable])
            _mark_checked()
            return True

        _notify('Installiere Abhaengigkeiten...', 'INFO', 3000)
        for addon_id, optional, version in missing:
            _install_addon(addon_id, version)

        _enable_addons([addon_id for addon_id, optional, version in installable])

        still_missing = [
            addon_id
            for addon_id, optional, version in installable
            if not _has_addon(addon_id, version)
        ]
        missing_required = [addon_id for addon_id in still_missing if addon_id in required]

        if still_missing:
            _log('Missing dependencies after install: %s' % ', '.join(still_missing), xbmc.LOGWARNING)
            _notify('Abhaengigkeiten fehlen: %s' % ', '.join(still_missing[:3]), 'WARNING', 7000)

        success = len(missing_required) == 0
        if success:
            _mark_checked()
        return success
    except Exception as e:
        _log('Dependency check failed: %s' % str(e), xbmc.LOGERROR)
        return True


def install_addon(addon_id, min_version=None):
    """Install an add-on on demand using Kodi first and known external sources as fallback."""
    try:
        if _has_addon(addon_id, min_version):
            _enable_addons([addon_id])
            return True

        if not _install_addon(addon_id, min_version):
            return False

        _enable_addons([addon_id])
        _refresh_addons()
        return _has_addon(addon_id, min_version)
    except Exception as e:
        _log('On-demand install failed for %s: %s' % (addon_id, str(e)), xbmc.LOGERROR)
        return False


def _dependencies_from_manifest():
    addon_xml = os.path.join(_translate_path(ADDON_PATH), 'addon.xml')
    root = ET.parse(addon_xml).getroot()

    dependencies = []
    for node in root.findall('./requires/import'):
        addon_id = node.attrib.get('addon')
        if not addon_id or addon_id == 'xbmc.python' or addon_id == ADDON_ID:
            continue
        optional = node.attrib.get('optional', '').lower() == 'true'
        version = node.attrib.get('version')
        dependencies.append((addon_id, optional, version))

    return _unique_dependencies(dependencies)


def _unique_dependencies(dependencies):
    seen = set()
    result = []
    for addon_id, optional, version in dependencies:
        if addon_id in seen:
            continue
        seen.add(addon_id)
        result.append((addon_id, optional, version))
    return result


def _is_required(addon_id, optional):
    return not optional or addon_id in REQUIRED_EXTERNAL_ADDONS


def _should_install(addon_id, optional):
    if optional and addon_id in SKIP_OPTIONAL_INSTALL:
        return False
    if addon_id in REQUIRED_EXTERNAL_ADDONS or addon_id in AUTO_INSTALL_OPTIONAL_EXTERNALS:
        return True
    if optional and not INSTALL_OPTIONAL:
        return False
    return True


def _has_addon(addon_id, min_version=None):
    try:
        if not bool(xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id)):
            return False
        if min_version:
            installed = xbmcaddon.Addon(addon_id).getAddonInfo('version')
            return _compare_versions(installed, min_version) >= 0
        return True
    except:
        return False


def _install_addon(addon_id, min_version=None):
    if _has_addon(addon_id, min_version):
        return True

    if addon_id in EXTERNAL_ADDON_SOURCES:
        if _install_external_addon(addon_id, min_version):
            return True
        _log('External dependency source failed, falling back to Kodi repo: %s' % addon_id, xbmc.LOGWARNING)

    return _install_addon_from_kodi(addon_id, min_version)


def _install_addon_from_kodi(addon_id, min_version=None, timeout=INSTALL_TIMEOUT):
    _log('Installing dependency: %s' % addon_id, xbmc.LOGINFO)
    try:
        xbmc.executebuiltin('InstallAddon(%s)' % addon_id, True)
    except TypeError:
        xbmc.executebuiltin('InstallAddon(%s)' % addon_id)

    _accept_install_dialog()
    if _wait_for_addon(addon_id, min_version, timeout):
        return True

    # Some skins show the confirmation dialog after InstallAddon returns.
    _accept_install_dialog()
    return _wait_for_addon(addon_id, min_version, timeout=15)


def _install_external_addon(addon_id, min_version=None):
    source = EXTERNAL_ADDON_SOURCES.get(addon_id)
    if not source:
        return False

    repository_id = source.get('repository_id')
    if repository_id and not _has_addon(repository_id):
        _install_external_repository(repository_id, source)

    if repository_id and _has_addon(repository_id):
        _enable_addons([repository_id])
        _refresh_addons()
        if _install_addon_from_kodi(addon_id, min_version, timeout=45):
            return True

    return _install_latest_addon_zip(addon_id, source, min_version)


def _install_external_repository(repository_id, source):
    for url in source.get('repository_zip_urls', []):
        if _install_zip_from_url(url, repository_id):
            _log('Installed external repository: %s' % repository_id, xbmc.LOGINFO)
            return True
    return False


def _install_latest_addon_zip(addon_id, source, min_version=None):
    try:
        node = _addon_node_from_metadata(addon_id, source['metadata_url'])
        version = node.attrib.get('version')
        if min_version and version and _compare_versions(version, min_version) < 0:
            _log('External source has old %s version: %s' % (addon_id, version), xbmc.LOGWARNING)
            return False

        if not _install_required_addons(_requirements_from_node(node), parent_id=addon_id):
            return False
        zip_url = _addon_zip_url(source['datadir'], addon_id, version)
        return _install_zip_from_url(zip_url, addon_id, min_version)
    except Exception as e:
        _log('External install failed for %s: %s' % (addon_id, str(e)), xbmc.LOGWARNING)
    return False


def _install_required_addons(dependencies, parent_id=None):
    success = True
    for addon_id, optional, version in dependencies:
        if optional or addon_id in ('xbmc.python', ADDON_ID, parent_id):
            continue
        if not _has_addon(addon_id, version):
            if not _install_addon(addon_id, version):
                success = False
    return success


def _install_zip_from_url(url, expected_id, min_version=None):
    temp_zip = _dependency_temp_path(url)
    try:
        _download_file(url, temp_zip)
        installed_id = _extract_addon_zip(temp_zip, expected_id)
        _refresh_addons()
        _enable_addons([installed_id])
        return _wait_for_addon(installed_id, min_version, timeout=20)
    except Exception as e:
        _log('Failed to install %s from %s: %s' % (expected_id, url, str(e)), xbmc.LOGWARNING)
    finally:
        try:
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
        except:
            pass
    return False


def _wait_for_addon(addon_id, min_version=None, timeout=INSTALL_TIMEOUT):
    deadline = time.time() + timeout
    monitor = xbmc.Monitor()
    while time.time() < deadline and not monitor.abortRequested():
        if _has_addon(addon_id, min_version):
            return True
        monitor.waitForAbort(1)
    return _has_addon(addon_id, min_version)


def _accept_install_dialog():
    try:
        for i in range(8):
            if xbmc.getCondVisibility('Window.IsActive(yesnoDialog)') or xbmc.getCondVisibility('Window.IsActive(DialogConfirm.xml)'):
                xbmc.executebuiltin('SendClick(11)')
                return
            xbmc.Monitor().waitForAbort(0.25)
    except:
        pass


def _enable_addons(addon_ids):
    for addon_id in addon_ids:
        if _has_addon(addon_id):
            _set_addon_enabled(addon_id)


def _set_addon_enabled(addon_id):
    try:
        request = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'Addons.SetAddonEnabled',
            'params': {
                'addonid': addon_id,
                'enabled': True,
            },
        }
        xbmc.executeJSONRPC(json.dumps(request))
    except:
        pass


def _refresh_addons():
    try:
        xbmc.executebuiltin('UpdateLocalAddons')
        xbmc.Monitor().waitForAbort(1)
        xbmc.executebuiltin('UpdateAddonRepos')
        xbmc.Monitor().waitForAbort(2)
    except:
        pass


def _addon_node_from_metadata(addon_id, metadata_url):
    content = _download_text(metadata_url)
    root = ET.fromstring(content)
    for node in root.findall('addon'):
        if node.attrib.get('id') == addon_id:
            return node
    raise DependencyError('Addon not found in metadata: %s' % addon_id)


def _requirements_from_node(node):
    dependencies = []
    for child in node.findall('./requires/import'):
        addon_id = child.attrib.get('addon')
        if not addon_id:
            continue
        optional = child.attrib.get('optional', '').lower() == 'true'
        dependencies.append((addon_id, optional, child.attrib.get('version')))
    return dependencies


def _addon_zip_url(datadir, addon_id, version):
    if not version:
        raise DependencyError('No version found for %s' % addon_id)
    base = datadir.rstrip('/') + '/'
    return '%s%s/%s-%s.zip' % (base, addon_id, addon_id, version)


def _download_text(url):
    response = _open_url(url)
    try:
        return response.read().decode('utf-8', 'replace')
    finally:
        _close_response(response)


def _download_file(url, destination):
    _mkdir(os.path.dirname(destination))
    response = _open_url(url)
    try:
        with open(destination, 'wb') as output:
            while True:
                chunk = response.read(1024 * 64)
                if not chunk:
                    break
                output.write(chunk)
    finally:
        _close_response(response)


def _open_url(url):
    request = Request(
        url,
        headers={
            'User-Agent': '%s/%s' % (ADDON_ID, ADDON_VERSION),
        },
    )
    return urlopen(request, timeout=DOWNLOAD_TIMEOUT)


def _close_response(response):
    try:
        response.close()
    except:
        pass


def _dependency_temp_path(url):
    filename = os.path.basename(url.split('?', 1)[0]) or 'dependency.zip'
    directory = os.path.join(_translate_path('special://temp/'), 'xvault-dependencies')
    _mkdir(directory)
    return os.path.join(directory, filename)


def _extract_addon_zip(path, expected_id):
    addons_dir = _translate_path('special://home/addons/')
    with zipfile.ZipFile(path) as archive:
        addon_xml = _find_addon_xml(archive)
        content = archive.read(addon_xml).decode('utf-8', 'replace')
        addon_id, version = _addon_xml_info(content)
        if addon_id != expected_id:
            raise DependencyError('Unexpected addon id in zip: %s' % addon_id)

        root = addon_xml.rsplit('/', 1)[0] if '/' in addon_xml else ''
        destination = os.path.join(addons_dir, addon_id)
        _mkdir(destination)

        for info in archive.infolist():
            name = _normalize_zip_name(info.filename)
            relative = _relative_name(name, root)
            if not relative or relative.endswith('/'):
                continue

            target = _safe_join(destination, relative)
            _mkdir(os.path.dirname(target))
            with archive.open(info) as source, open(target, 'wb') as output:
                while True:
                    chunk = source.read(1024 * 64)
                    if not chunk:
                        break
                    output.write(chunk)

    return addon_id


def _find_addon_xml(archive):
    for name in archive.namelist():
        normalized = _normalize_zip_name(name)
        if normalized.endswith('/addon.xml') or normalized == 'addon.xml':
            return normalized
    raise DependencyError('addon.xml not found in dependency zip')


def _relative_name(name, root):
    if not root:
        return name
    prefix = root.rstrip('/') + '/'
    if name.startswith(prefix):
        return name[len(prefix):]
    return ''


def _safe_join(base, relative):
    parts = [part for part in relative.replace('\\', '/').split('/') if part]
    if any(part == '..' for part in parts):
        raise DependencyError('Unsafe path in dependency zip: %s' % relative)

    target = os.path.abspath(os.path.join(base, *parts))
    base = os.path.abspath(base)
    if target != base and not target.startswith(base + os.sep):
        raise DependencyError('Unsafe path in dependency zip: %s' % relative)
    return target


def _normalize_zip_name(name):
    return name.replace('\\', '/').lstrip('/')


def _addon_xml_info(content):
    try:
        root = ET.fromstring(content)
        return root.attrib.get('id'), root.attrib.get('version')
    except:
        addon_id = _find_attr(content, 'id')
        version = _find_attr(content, 'version')
        return addon_id, version


def _find_attr(content, attr):
    match = re.search(r'\b%s=[\'"]([^\'"]+)[\'"]' % attr, content)
    return match.group(1) if match else None


def _compare_versions(left, right):
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    length = max(len(left_parts), len(right_parts))

    for i in range(length):
        left_part = left_parts[i] if i < len(left_parts) else (1, 0)
        right_part = right_parts[i] if i < len(right_parts) else (1, 0)
        if left_part == right_part:
            continue
        return 1 if left_part > right_part else -1
    return 0


def _version_parts(version):
    parts = []
    for part in re.findall(r'\d+|[A-Za-z]+', str(version or '0')):
        if part.isdigit():
            parts.append((1, int(part)))
        else:
            parts.append((0, part.lower()))
    return parts


def _mkdir(path):
    if not path or os.path.exists(path):
        return
    os.makedirs(path)


class DependencyError(Exception):
    pass


def _was_checked():
    try:
        if not xbmcgui:
            return False
        value = xbmcgui.Window(10000).getProperty(_checked_property())
        return value == ADDON_VERSION
    except:
        return False


def _mark_checked():
    try:
        if xbmcgui:
            xbmcgui.Window(10000).setProperty(_checked_property(), ADDON_VERSION)
    except:
        pass


def _checked_property():
    return '%s.dependencies.checked' % ADDON_ID


def _translate_path(path):
    if xbmcvfs and hasattr(xbmcvfs, 'translatePath'):
        return xbmcvfs.translatePath(path)
    if sys.version_info.major == 2:
        return xbmc.translatePath(path).decode('utf-8')
    return xbmc.translatePath(path)


def _notify(message, icon='INFO', time_ms=5000):
    try:
        if not xbmcgui:
            return
        icon_value = getattr(xbmcgui, 'NOTIFICATION_%s' % icon, xbmcgui.NOTIFICATION_INFO)
        xbmcgui.Dialog().notification(ADDON_NAME, message, icon_value, time_ms, sound=False)
    except:
        pass


def _log(message, level):
    try:
        xbmc.log('[xVAULT.dependencies] %s' % message, level)
    except:
        pass
