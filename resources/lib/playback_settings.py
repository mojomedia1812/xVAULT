import os
import xml.etree.ElementTree as ET

from resources.lib import control


MODE_DIALOG = '0'
MODE_DIRECTORY = '1'
MODE_AUTOPLAY = '2'

_MODE_ALIASES = {
    '0': MODE_DIALOG,
    'dialog': MODE_DIALOG,
    'Dialog': MODE_DIALOG,
    '1': MODE_DIRECTORY,
    'directory': MODE_DIRECTORY,
    'folder': MODE_DIRECTORY,
    'verzeichnis': MODE_DIRECTORY,
    'Verzeichnis': MODE_DIRECTORY,
    '2': MODE_AUTOPLAY,
    'autoplay': MODE_AUTOPLAY,
    'Autoplay': MODE_AUTOPLAY,
}

_MODE_SETTING_VALUES = {
    MODE_DIALOG: MODE_DIALOG,
    MODE_DIRECTORY: MODE_DIRECTORY,
    MODE_AUTOPLAY: MODE_AUTOPLAY,
}


def normalize_mode(value, default=MODE_AUTOPLAY):
    if value is None:
        return default
    key = str(value).strip()
    if not key:
        return default
    return _MODE_ALIASES.get(key) or _MODE_ALIASES.get(key.lower(), default)


def get_mode(default=MODE_AUTOPLAY):
    raw = _read_addon_setting('hosts.mode') or _read_profile_setting('hosts.mode')
    return normalize_mode(raw, default)


def set_mode(value):
    mode = normalize_mode(value, MODE_AUTOPLAY)
    control.setSetting(id='hosts.mode', value=_MODE_SETTING_VALUES[mode])
    return mode


def migrate_mode_setting():
    raw = _read_profile_setting('hosts.mode') or _read_addon_setting('hosts.mode')
    mode = normalize_mode(raw, None)
    if mode is None:
        return set_mode(MODE_AUTOPLAY)

    desired = _MODE_SETTING_VALUES[mode]
    if str(raw).strip() != desired:
        control.setSetting(id='hosts.mode', value=desired)
    return mode


def _read_profile_setting(setting_id):
    try:
        path = os.path.join(control.addonProfilePath, 'settings.xml')
        if not os.path.exists(path):
            return ''
        root = ET.parse(path).getroot()
        for node in root.findall('setting'):
            if node.get('id') == setting_id:
                return (node.text or node.get('value') or '').strip()
    except Exception:
        pass
    return ''


def _read_addon_setting(setting_id):
    try:
        import xbmcaddon
        return xbmcaddon.Addon().getSetting(setting_id)
    except Exception:
        pass
    try:
        return control.getSetting(setting_id)
    except Exception:
        return ''
