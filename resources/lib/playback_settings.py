import os
import xml.etree.ElementTree as ET

from resources.lib import control


MODE_DIALOG = '0'
MODE_DIRECTORY = '1'
MODE_AUTOPLAY = '2'

SETTING_ID = 'xvault.playback.mode'
MIGRATION_SETTING_ID = 'xvault.playback.mode.migrated'
MODE_FILE = 'playback_mode.txt'
LEGACY_SETTING_IDS = ('hosts.mode.v3', 'hosts.mode.v2', 'hosts.mode', 'default.action')
LEGACY_MARKER_IDS = ('hosts.mode.v3.migrated', 'hosts.mode.v2.migrated')
MODE_ORDER = (MODE_DIALOG, MODE_DIRECTORY, MODE_AUTOPLAY)

_MODE_LABELS = {
    MODE_DIALOG: 'Dialog',
    MODE_DIRECTORY: 'Verzeichnis',
    MODE_AUTOPLAY: 'Autoplay',
}

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
    MODE_DIALOG: _MODE_LABELS[MODE_DIALOG],
    MODE_DIRECTORY: _MODE_LABELS[MODE_DIRECTORY],
    MODE_AUTOPLAY: _MODE_LABELS[MODE_AUTOPLAY],
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


def select_mode(value=None):
    if value is None:
        labels = [_MODE_LABELS[mode] for mode in MODE_ORDER]
        choice = control.selectDialog(labels, 'Standard-Aktion')
        if choice < 0:
            return None
        mode = MODE_ORDER[choice]
    else:
        mode = normalize_mode(value, None)
        if mode is None:
            control.infoDialog('Ungueltige Standard-Aktion.', icon='WARNING')
            return None

    set_mode(mode)
    control.infoDialog('Standard-Aktion: %s' % _MODE_LABELS[mode], icon='INFO')
    return mode


def migrate_mode_setting():
    mode, _raw, source = _resolve_mode(None)
    if mode is None:
        return MODE_AUTOPLAY
    if source != 'file' or _legacy_profile_settings_present():
        _write_mode(mode)
    return mode


def has_profile_mode():
    mode, _raw, source = _resolve_mode(None)
    return mode is not None and source != 'default'


def _resolve_mode(default=MODE_AUTOPLAY):
    file_raw = _read_mode_file()
    file_mode = normalize_mode(file_raw, None)
    if file_mode is not None:
        return file_mode, file_raw, 'file'

    explicit_profile_candidates = []
    default_profile_candidates = []
    for setting_id in LEGACY_SETTING_IDS:
        raw, is_default = _read_profile_setting(setting_id)
        if _profile_value_is_explicit(raw, is_default):
            explicit_profile_candidates.append((raw, 'profile:%s' % setting_id))
        elif _profile_value_is_default(raw, is_default):
            default_profile_candidates.append((raw, 'profile-default:%s' % setting_id))

    for raw, source in explicit_profile_candidates:
        mode = normalize_mode(raw, None)
        if mode is not None:
            return mode, raw, source

    for setting_id in LEGACY_SETTING_IDS:
        raw, available = _read_live_addon_setting(setting_id)
        mode = normalize_mode(raw, None)
        if available and mode is not None:
            return mode, raw, 'live:%s' % setting_id

    for raw, source in default_profile_candidates:
        mode = normalize_mode(raw, None)
        if mode is not None:
            return mode, raw, source

    return default, '', 'default'


def _write_mode(mode):
    _write_mode_file(_MODE_SETTING_VALUES[mode])
    _remove_profile_settings(LEGACY_SETTING_IDS + LEGACY_MARKER_IDS)


def _mode_file_path():
    return os.path.join(control.addonProfilePath, MODE_FILE)


def _read_mode_file():
    try:
        with open(_mode_file_path(), 'r', encoding='utf-8') as handle:
            return handle.read().strip()
    except Exception:
        return ''


def _write_mode_file(value):
    try:
        path = _mode_file_path()
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        tmp_path = path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as handle:
            handle.write(value + '\n')
        os.replace(tmp_path, path)
    except Exception:
        pass


def _legacy_profile_settings_present():
    for setting_id in LEGACY_SETTING_IDS + LEGACY_MARKER_IDS:
        raw, _is_default = _read_profile_setting(setting_id)
        if raw:
            return True
    return False


def _profile_value_is_explicit(raw, is_default):
    mode = normalize_mode(raw, None)
    return mode is not None and (not is_default or mode in (MODE_DIALOG, MODE_DIRECTORY))


def _profile_value_is_default(raw, is_default):
    mode = normalize_mode(raw, None)
    return mode is not None and is_default and not _profile_value_is_explicit(raw, is_default)


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


def _remove_profile_settings(setting_ids):
    try:
        path = os.path.join(control.addonProfilePath, 'settings.xml')
        if not os.path.exists(path):
            return
        root = ET.parse(path).getroot()
        changed = False
        for node in list(root.findall('setting')):
            if node.get('id') in setting_ids:
                root.remove(node)
                changed = True
        if changed:
            ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=False)
    except Exception:
        pass


def _read_live_addon_setting(setting_id):
    try:
        return control.getSetting(setting_id), True
    except Exception:
        return '', False
