import os
import xml.etree.ElementTree as ET

from resources.lib import control


MODE_DIALOG = '0'
MODE_DIRECTORY = '1'
MODE_AUTOPLAY = '2'

SETTING_ID = 'hosts.mode.v2'
MIGRATION_SETTING_ID = 'hosts.mode.v2.migrated'
LEGACY_SETTING_IDS = ('hosts.mode', 'default.action')

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
    mode, _raw, _source = _resolve_mode(default, prefer_live=True)
    return mode


def set_mode(value):
    mode = normalize_mode(value, MODE_AUTOPLAY)
    _write_mode(mode)
    return mode


def migrate_mode_setting():
    mode, raw, source = _resolve_mode(None, prefer_live=True)
    if mode is None:
        return MODE_AUTOPLAY

    desired = _MODE_SETTING_VALUES[mode]
    if (
        str(raw).strip() != desired
        or _profile_setting_differs_from_mode(mode)
        or _profile_source_differs_from_live(source, mode)
    ):
        _write_mode(mode)
    return mode


def has_profile_mode():
    for setting_id in (SETTING_ID,) + LEGACY_SETTING_IDS:
        raw, is_default = _read_profile_setting(setting_id)
        if _profile_value_is_explicit(raw, is_default):
            return True
    return False


def _resolve_mode(default=MODE_AUTOPLAY, prefer_live=True):
    current_raw, current_is_default = _read_profile_setting(SETTING_ID)
    live_raw, live_available = _read_live_addon_setting(SETTING_ID)
    explicit_profile_candidates = [
        (current_raw, 'profile:%s' % SETTING_ID, _profile_value_is_explicit(current_raw, current_is_default))
    ]
    default_profile_candidates = [
        (current_raw, 'profile-default:%s' % SETTING_ID, _profile_value_is_default(current_raw, current_is_default))
    ]
    live_candidates = [(live_raw, 'live:%s' % SETTING_ID, live_available)]

    for setting_id in LEGACY_SETTING_IDS:
        legacy_raw, legacy_is_default = _read_profile_setting(setting_id)
        explicit_profile_candidates.append(
            (legacy_raw, 'profile:%s' % setting_id, _profile_value_is_explicit(legacy_raw, legacy_is_default))
        )
        default_profile_candidates.append(
            (legacy_raw, 'profile-default:%s' % setting_id, _profile_value_is_default(legacy_raw, legacy_is_default))
        )
        legacy_live_raw, legacy_live_available = _read_live_addon_setting(setting_id)
        live_candidates.append((legacy_live_raw, 'live:%s' % setting_id, legacy_live_available))

    if _stored_legacy_should_precede_live(live_raw, current_raw, current_is_default, explicit_profile_candidates):
        ordered_candidates = explicit_profile_candidates + live_candidates + default_profile_candidates
    elif prefer_live:
        ordered_candidates = live_candidates + explicit_profile_candidates + default_profile_candidates
    else:
        ordered_candidates = explicit_profile_candidates + live_candidates + default_profile_candidates

    for raw, source, enabled in ordered_candidates:
        if not enabled:
            continue
        mode = normalize_mode(raw, None)
        if mode is not None:
            return mode, raw, source

    return default, '', 'default'


def _write_mode(mode):
    value = _MODE_SETTING_VALUES[mode]
    if mode == MODE_AUTOPLAY:
        try:
            control.setSetting(id=SETTING_ID, value=_MODE_LABELS[MODE_DIALOG])
        except Exception:
            pass
    control.setSetting(id=SETTING_ID, value=value)
    control.setSetting(id=MIGRATION_SETTING_ID, value='true')
    _write_profile_setting(SETTING_ID, value, clear_legacy=True)
    _write_profile_setting(MIGRATION_SETTING_ID, 'true')


def _profile_source_differs_from_live(source, mode):
    if not str(source).startswith('profile:'):
        return False
    raw, available = _read_live_addon_setting(SETTING_ID)
    return available and normalize_mode(raw, None) != mode


def _profile_setting_differs_from_mode(mode):
    raw, _is_default = _read_profile_setting(SETTING_ID)
    return bool(raw) and str(raw).strip() != _MODE_SETTING_VALUES[mode]


def _stored_legacy_should_precede_live(live_raw, current_raw, current_is_default, explicit_profile_candidates):
    if _migration_marker_applied():
        return False
    if normalize_mode(live_raw, None) != MODE_AUTOPLAY:
        return False
    if normalize_mode(current_raw, None) is not None and not current_is_default:
        return False
    for raw, source, enabled in explicit_profile_candidates:
        if (
            enabled
            and source in ('profile:%s' % setting_id for setting_id in LEGACY_SETTING_IDS)
            and normalize_mode(raw, None) in (MODE_DIALOG, MODE_DIRECTORY)
        ):
            return True
    return False


def _profile_value_is_explicit(raw, is_default):
    mode = normalize_mode(raw, None)
    return mode is not None and (not is_default or mode in (MODE_DIALOG, MODE_DIRECTORY))


def _profile_value_is_default(raw, is_default):
    mode = normalize_mode(raw, None)
    return mode is not None and is_default and not _profile_value_is_explicit(raw, is_default)


def _migration_marker_applied():
    raw, _is_default = _read_profile_setting(MIGRATION_SETTING_ID)
    return str(raw).strip().lower() == 'true'


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


def _write_profile_setting(setting_id, value, clear_legacy=False):
    try:
        path = os.path.join(control.addonProfilePath, 'settings.xml')
        if os.path.exists(path):
            root = ET.parse(path).getroot()
        else:
            root = ET.Element('settings', {'version': '2'})

        if clear_legacy:
            for node in list(root.findall('setting')):
                if node.get('id') in LEGACY_SETTING_IDS:
                    root.remove(node)

        target = None
        for node in root.findall('setting'):
            if node.get('id') == setting_id:
                target = node
                break
        if target is None:
            target = ET.SubElement(root, 'setting', {'id': setting_id})
        target.attrib.pop('default', None)
        target.text = value

        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=False)
    except Exception:
        pass


def _read_live_addon_setting(setting_id):
    try:
        import xbmcaddon
        return xbmcaddon.Addon().getSetting(setting_id), True
    except Exception:
        pass
    try:
        return control.getSetting(setting_id), False
    except Exception:
        return '', False
