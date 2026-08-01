import json
import os

from resources.lib import control, log_utils


PLAYER_FILENAME = 'xvault.json'
TARGET_PLAYER_FILENAME = 'xvault_stable.json'
LEGACY_PLAYER_FILENAME = 'xvault.json'
TMDBHELPER_ADDON = 'plugin.video.themoviedb.helper'
PLAYER_PROFILE_DIR = 'special://profile/addon_data/%s/players' % TMDBHELPER_ADDON


def _read_text(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return handle.read()


def _write_text(path, text):
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def _sha256_text(text):
    try:
        import hashlib
        return hashlib.sha256((text or '').encode('utf-8')).hexdigest()
    except Exception:
        return ''


def _jsonrpc(method, params=None):
    try:
        request = {'jsonrpc': '2.0', 'id': 1, 'method': method}
        if params is not None:
            request['params'] = params
        response = json.loads(control.jsonrpc(json.dumps(request)))
        if response.get('error'):
            return {}
        return response.get('result') or {}
    except Exception:
        return {}


def _addon_details():
    result = {
        'id': TMDBHELPER_ADDON,
        'installed': False,
        'enabled': None,
        'version': '',
    }
    try:
        result['installed'] = bool(control.condVisibility('System.HasAddon(%s)' % TMDBHELPER_ADDON))
    except Exception:
        pass

    details = _jsonrpc(
        'Addons.GetAddonDetails',
        {'addonid': TMDBHELPER_ADDON, 'properties': ['enabled', 'version', 'name']},
    ).get('addon') or {}
    if details:
        result.update({
            'installed': True,
            'enabled': details.get('enabled'),
            'version': details.get('version') or '',
            'name': details.get('name') or TMDBHELPER_ADDON,
        })
    return result


def _source_path():
    return os.path.join(control.addonPath, 'resources', 'tmdbhelper', PLAYER_FILENAME)


def _target_path(filename=TARGET_PLAYER_FILENAME):
    return control.translatePath('%s/%s' % (PLAYER_PROFILE_DIR, filename))


def _tmdbhelper_installed():
    details = _addon_details()
    if details.get('installed'):
        return True
    return os.path.exists(control.translatePath('special://home/addons/%s/addon.xml' % TMDBHELPER_ADDON))


def diagnostics():
    """Return a support-safe status snapshot for the TMDbHelper player bridge."""
    source = _source_path()
    target = _target_path()
    legacy_target = _target_path(LEGACY_PLAYER_FILENAME)
    source_text = _read_text(source) if os.path.exists(source) else ''
    target_text = _read_text(target) if os.path.exists(target) else ''
    legacy_text = _read_text(legacy_target) if os.path.exists(legacy_target) else ''
    details = _addon_details()
    addon_xml = control.translatePath('special://home/addons/%s/addon.xml' % TMDBHELPER_ADDON)
    details.update({
        'addon_xml_exists': os.path.exists(addon_xml),
        'source_exists': os.path.exists(source),
        'target_exists': os.path.exists(target),
        'target_matches_source': bool(source_text and target_text and source_text == target_text),
        'target_filename': TARGET_PLAYER_FILENAME,
        'legacy_target_exists': os.path.exists(legacy_target),
        'legacy_target_matches_source': bool(source_text and legacy_text and source_text == legacy_text),
        'legacy_target_conflicts': bool(source_text and legacy_text and source_text != legacy_text),
        'legacy_target_path': legacy_target,
        'source_sha256': _sha256_text(source_text),
        'target_sha256': _sha256_text(target_text),
        'target_path': target,
    })
    if not details.get('installed') and details.get('addon_xml_exists'):
        details['installed'] = True
    if not details.get('source_exists'):
        details['state'] = 'source_missing'
    elif not details.get('installed'):
        details['state'] = 'tmdbhelper_not_installed'
    elif not details.get('target_exists'):
        details['state'] = 'player_missing'
    elif not details.get('target_matches_source'):
        details['state'] = 'player_outdated'
    elif details.get('enabled') is False:
        details['state'] = 'tmdbhelper_disabled'
    else:
        details['state'] = 'ready'
    return details


def _cleanup_legacy_player(source_text):
    legacy_target = _target_path(LEGACY_PLAYER_FILENAME)
    if legacy_target == _target_path():
        return
    try:
        if not os.path.exists(legacy_target):
            return
        legacy_text = _read_text(legacy_target)
        if legacy_text == source_text:
            os.remove(legacy_target)
            log_utils.log('TMDbHelper legacy player removed: %s' % legacy_target, log_utils.LOGINFO)
        else:
            log_utils.log('TMDbHelper legacy player belongs to another add-on, leaving it untouched: %s' % legacy_target, log_utils.LOGINFO)
    except Exception as exc:
        log_utils.log('TMDbHelper legacy player cleanup failed: %s' % str(exc), log_utils.LOGWARNING)


def _install_once(log_unchanged=False):
    info = diagnostics()
    if not info.get('source_exists'):
        log_utils.log('TMDbHelper player source missing: %s' % _source_path(), log_utils.LOGWARNING)
        return False
    if not info.get('installed'):
        if log_unchanged:
            log_utils.log('TMDbHelper player not installed because TMDbHelper is not present', log_utils.LOGINFO)
        return False

    try:
        source = _source_path()
        target = _target_path()
        new_text = _read_text(source)
        old_text = _read_text(target) if os.path.exists(target) else ''
        if old_text != new_text:
            _write_text(target, new_text)
            log_utils.log('TMDbHelper player repaired: %s' % target, log_utils.LOGINFO)
        elif log_unchanged:
            log_utils.log('TMDbHelper player ready: %s' % target, log_utils.LOGINFO)
        _cleanup_legacy_player(new_text)
        return True
    except Exception as exc:
        log_utils.log('TMDbHelper player install failed: %s' % str(exc), log_utils.LOGWARNING)
        return False


def ensure_player(retries=1, delay=0, log_unchanged=False):
    """Install or repair xVAULT's TMDbHelper player file without blocking Kodi long."""
    try:
        retries = max(1, int(retries))
    except Exception:
        retries = 1
    try:
        delay = max(0, int(delay))
    except Exception:
        delay = 0

    last_state = ''
    for attempt in range(retries):
        if _install_once(log_unchanged=log_unchanged and attempt == 0):
            return True
        info = diagnostics()
        last_state = info.get('state') or ''
        if last_state in ('source_missing', 'tmdbhelper_not_installed'):
            break
        if attempt < retries - 1 and delay:
            control.sleep(delay)

    if last_state and last_state not in ('tmdbhelper_not_installed',):
        log_utils.log('TMDbHelper player not ready after repair attempt: %s' % last_state, log_utils.LOGWARNING)
    return False
