# edit 2026-06-13

import json
import os
import sys
import time
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


ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = ADDON.getAddonInfo('path')
ADDON_VERSION = ADDON.getAddonInfo('version')

INSTALL_TIMEOUT = 90
INSTALL_OPTIONAL = True

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

        required = [addon_id for addon_id, optional in dependencies if not optional]
        installable = [
            (addon_id, optional)
            for addon_id, optional in dependencies
            if _should_install(addon_id, optional)
        ]

        missing = [(addon_id, optional) for addon_id, optional in installable if not _has_addon(addon_id)]
        if not missing:
            _enable_addons([addon_id for addon_id, optional in installable])
            _mark_checked()
            return True

        _notify('Installiere Abhaengigkeiten...', 'INFO', 3000)
        for addon_id, optional in missing:
            _install_addon(addon_id)

        _enable_addons([addon_id for addon_id, optional in installable])

        still_missing = [addon_id for addon_id, optional in installable if not _has_addon(addon_id)]
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


def _dependencies_from_manifest():
    addon_xml = os.path.join(_translate_path(ADDON_PATH), 'addon.xml')
    root = ET.parse(addon_xml).getroot()

    dependencies = []
    for node in root.findall('./requires/import'):
        addon_id = node.attrib.get('addon')
        if not addon_id or addon_id == 'xbmc.python' or addon_id == ADDON_ID:
            continue
        optional = node.attrib.get('optional', '').lower() == 'true'
        dependencies.append((addon_id, optional))

    return _unique_dependencies(dependencies)


def _unique_dependencies(dependencies):
    seen = set()
    result = []
    for addon_id, optional in dependencies:
        if addon_id in seen:
            continue
        seen.add(addon_id)
        result.append((addon_id, optional))
    return result


def _should_install(addon_id, optional):
    if optional and addon_id in SKIP_OPTIONAL_INSTALL:
        return False
    if optional and not INSTALL_OPTIONAL:
        return False
    return True


def _has_addon(addon_id):
    try:
        return bool(xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id))
    except:
        return False


def _install_addon(addon_id):
    if _has_addon(addon_id):
        return True

    _log('Installing dependency: %s' % addon_id, xbmc.LOGINFO)
    try:
        xbmc.executebuiltin('InstallAddon(%s)' % addon_id, True)
    except TypeError:
        xbmc.executebuiltin('InstallAddon(%s)' % addon_id)

    _accept_install_dialog()
    if _wait_for_addon(addon_id):
        return True

    # Some skins show the confirmation dialog after InstallAddon returns.
    _accept_install_dialog()
    return _wait_for_addon(addon_id, timeout=15)


def _wait_for_addon(addon_id, timeout=INSTALL_TIMEOUT):
    deadline = time.time() + timeout
    monitor = xbmc.Monitor()
    while time.time() < deadline and not monitor.abortRequested():
        if _has_addon(addon_id):
            return True
        monitor.waitForAbort(1)
    return _has_addon(addon_id)


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
