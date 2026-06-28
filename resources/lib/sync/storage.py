import json
import os

from resources.lib import control, log_utils


ACCOUNT_EMAIL = 'sync.email'
API_KEY = 'sync.api_key'
SYNC_ENABLED = 'sync.enabled'
LOGGED_IN = 'sync.logged_in'
LAST_SYNC_AT = 'sync.last_sync_at'
LAST_FAVORITES_HASH = 'sync.last_favorites_hash'
STATUS_TEXT = 'sync.status'
DEVICE_ID = 'sync.device_id'


def get_setting(key, default=''):
    return control.getSetting(key, default)


def set_setting(key, value):
    control.setSetting(key, '' if value is None else str(value))


def is_enabled():
    return get_setting(SYNC_ENABLED) == 'true'


def is_logged_in():
    return bool(get_setting(API_KEY)) and get_setting(LOGGED_IN) == 'true'


def email():
    return get_setting(ACCOUNT_EMAIL)


def api_key():
    return get_setting(API_KEY)


def profile_path(*parts):
    base = control.addonProfilePath
    if not os.path.exists(base):
        try:
            os.makedirs(base)
        except Exception:
            pass
    return os.path.join(base, *parts)


def read_json(filename, default=None):
    path = profile_path(filename)
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except Exception:
        return {} if default is None else default


def write_json(filename, data):
    path = profile_path(filename)
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, path)
        return True
    except Exception as exc:
        log_utils.log('xVAULT sync: failed to write %s: %s' % (filename, exc), log_utils.LOGWARNING)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


def save_login(user_email, token):
    set_setting(ACCOUNT_EMAIL, user_email)
    set_setting(API_KEY, token)
    set_setting(LOGGED_IN, 'true')
    set_setting(SYNC_ENABLED, 'true')
    set_status('Angemeldet als %s' % user_email)


def clear_login():
    set_setting(API_KEY, '')
    set_setting(LOGGED_IN, 'false')
    set_status('Nicht angemeldet')


def set_status(text):
    set_setting(STATUS_TEXT, text)


def update_last_sync(timestamp):
    set_setting(LAST_SYNC_AT, timestamp)


def mask_token(token):
    if not token:
        return ''
    if len(token) <= 8:
        return '****'
    return token[:4] + '****' + token[-4:]
