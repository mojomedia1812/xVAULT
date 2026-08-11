import json
import os
import threading
import time
import uuid

from resources.lib import control, log_utils


ACCOUNT_EMAIL = 'sync.email'
API_KEY = 'sync.api_key'
SYNC_ENABLED = 'sync.enabled'
LOGGED_IN = 'sync.logged_in'
LAST_SYNC_AT = 'sync.last_sync_at'
LAST_FAVORITES_HASH = 'sync.last_favorites_hash'
STATUS_TEXT = 'sync.status'
DEVICE_ID = 'sync.device_id'
AUTH_FILE = 'sync_auth.json'
_AUTH_CACHE = None


def get_setting(key, default=''):
    return control.getSetting(key, default)


def set_setting(key, value):
    control.setSetting(key, '' if value is None else str(value))


def is_enabled():
    return get_setting(SYNC_ENABLED) == 'true'


def is_logged_in():
    reconcile_auth_settings()
    data = _auth_data()
    if _has_auth_record(data):
        return _auth_logged_in(data) and bool(_auth_api_key(data))
    return bool(get_setting(API_KEY)) and get_setting(LOGGED_IN) == 'true'


def email():
    data = _auth_data()
    if _has_auth_record(data):
        return _auth_email(data) or get_setting(ACCOUNT_EMAIL)
    return get_setting(ACCOUNT_EMAIL)


def api_key():
    data = _auth_data()
    if _has_auth_record(data):
        return _auth_api_key(data)
    return get_setting(API_KEY)


def api_keys():
    keys = []
    data = _auth_data()
    if _has_auth_record(data):
        keys.append(_auth_api_key(data))
    keys.append(get_setting(API_KEY))
    result = []
    for key in keys:
        key = (key or '').strip()
        if key and key not in result:
            result.append(key)
    return result


def reconcile_auth_settings():
    data = _auth_data()
    if not _has_auth_record(data):
        return

    key = _auth_api_key(data)
    logged = _auth_logged_in(data) and bool(key)
    user_email = _auth_email(data)

    if user_email and get_setting(ACCOUNT_EMAIL) != user_email:
        set_setting(ACCOUNT_EMAIL, user_email)
    if get_setting(API_KEY) != key:
        set_setting(API_KEY, key)
    if get_setting(LOGGED_IN) != ('true' if logged else 'false'):
        set_setting(LOGGED_IN, 'true' if logged else 'false')
    if logged:
        if get_setting(SYNC_ENABLED) != 'true':
            set_setting(SYNC_ENABLED, 'true')
        set_status('Angemeldet als %s' % (user_email or get_setting(ACCOUNT_EMAIL)))
    elif get_setting(STATUS_TEXT) != 'Nicht angemeldet':
        set_status('Nicht angemeldet')


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
    tmp = '%s.%s.%s.%s.tmp' % (path, os.getpid(), threading.current_thread().ident, uuid.uuid4().hex)
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
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


def _auth_data():
    global _AUTH_CACHE
    if _AUTH_CACHE is None:
        data = read_json(AUTH_FILE, {})
        _AUTH_CACHE = data if isinstance(data, dict) else {}
    return _AUTH_CACHE


def _write_auth(data):
    global _AUTH_CACHE
    _AUTH_CACHE = data
    return write_json(AUTH_FILE, data)


def _has_auth_record(data):
    return isinstance(data, dict) and any(key in data for key in ('email', 'api_key', 'logged_in'))


def _auth_email(data):
    return str(data.get('email') or '').strip()


def _auth_api_key(data):
    return str(data.get('api_key') or '').strip()


def _auth_logged_in(data):
    value = data.get('logged_in')
    return value is True or str(value).lower() == 'true'


def save_login(user_email, token):
    set_setting(ACCOUNT_EMAIL, user_email)
    set_setting(API_KEY, token)
    set_setting(LOGGED_IN, 'true')
    set_setting(SYNC_ENABLED, 'true')
    _write_auth({
        'email': user_email,
        'api_key': token,
        'logged_in': True,
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    })
    reconcile_auth_settings()
    set_status('Angemeldet als %s' % user_email)


def clear_login():
    user_email = email()
    set_setting(API_KEY, '')
    set_setting(LOGGED_IN, 'false')
    _write_auth({
        'email': user_email,
        'api_key': '',
        'logged_in': False,
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    })
    reconcile_auth_settings()
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
