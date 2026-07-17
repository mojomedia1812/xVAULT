import os
import xml.etree.ElementTree as ET

from resources.lib import control


MODE_DIALOG = '0'
MODE_DIRECTORY = '1'
MODE_AUTOPLAY = '2'

SETTING_ID = 'hosts.mode'
LEGACY_SETTING_ID = 'default.action'

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
    mode, _raw, _source = _resolve_mode(default)
    return mode


def set_mode(value):
    mode = normalize_mode(value, MODE_AUTOPLAY)
    _write_mode(mode)
    return mode


def migrate_mode_setting():
    mode, raw, source = _resolve_mode(None)
    if mode is None:
        return MODE_AUTOPLAY

    desired = _MODE_SETTING_VALUES[mode]
    canonical_sources = ('profile:%s' % SETTING_ID, 'addon:%s' % SETTING_ID)
    if source not in canonical_sources or str(raw).strip() != desired:
        _write_mode(mode)
    return mode


def has_profile_mode():
    for setting_id in (SETTING_ID, LEGACY_SETTING_ID):
        raw, is_default = _read_profile_setting(setting_id)
        if raw and not is_default and normalize_mode(raw, None) is not None:
            return True
    return False


def _resolve_mode(default=MODE_AUTOPLAY):
    current_raw, current_is_default = _read_profile_setting(SETTING_ID)
    legacy_raw, legacy_is_default = _read_profile_setting(LEGACY_SETTING_ID)

    candidates = (
        (current_raw, 'profile:%s' % SETTING_ID, not current_is_default),
        (legacy_raw, 'profile:%s' % LEGACY_SETTING_ID, not legacy_is_default),
        (current_raw, 'profile-default:%s' % SETTING_ID, current_is_default),
        (_read_addon_setting(SETTING_ID), 'addon:%s' % SETTING_ID, True),
        (_read_addon_setting(LEGACY_SETTING_ID), 'addon:%s' % LEGACY_SETTING_ID, True),
    )

    for raw, source, enabled in candidates:
        if not enabled:
            continue
        mode = normalize_mode(raw, None)
        if mode is not None:
            return mode, raw, source
    return default, '', 'default'


def _write_mode(mode):
    control.setSetting(id=SETTING_ID, value=_MODE_SETTING_VALUES[mode])


def _read_profile_setting(setting_id):
    try:
        path = os.path.join(control.addonProfilePath, 'settings.xml')
        if not os.path.exists(path):
            return '', False
        root = ET.parse(path).getroot()
        for node in root.findall('setting'):
            if node.get('id') == setting_id:
                return (node.text or node.get('value') or '').strip(), node.get('default') == 'true'
    except Exception:
        pass
    return '', False


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
