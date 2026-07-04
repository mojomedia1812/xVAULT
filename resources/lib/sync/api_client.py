import json
import re
import ssl
import urllib.error
import urllib.request

from resources.lib import log_utils
from resources.lib.sync import storage


HTTPS_BASE = 'https://xvault.xo.je/index.php?action='
HTTP_BASE = 'http://xvault.xo.je/index.php?action='
TIMEOUT = 15
USER_AGENT = 'Mozilla/5.0 (Kodi; xVAULT Sync)'
CHALLENGE_RE = re.compile(r'toNumbers\("([0-9a-f]+)"\)')


class ApiError(Exception):
    def __init__(self, message, code='SYNC_FAILED', status=None):
        Exception.__init__(self, message)
        self.code = code
        self.status = status


class Client(object):
    def __init__(self, api_key=None):
        if api_key is not None:
            self.api_keys = [api_key] if api_key else []
        else:
            self.api_keys = storage.api_keys()
        self.api_key = self.api_keys[0] if self.api_keys else ''
        self._challenge_cookies = {}

    def register(self, email, password):
        return self._post('register', {'email': email, 'password': password}, auth=False)

    def login(self, email, password):
        return self._post('login', {'email': email, 'password': password}, auth=False)

    def reset_password(self, email):
        return self._post('password_reset', {'email': email}, auth=False)

    def status(self):
        return self._get('status', auth=False)

    def push_favorites(self, data):
        return self._post('favorites_push', {'device_id': data.get('device_id'), 'favorites': data})

    def pull_favorites(self):
        return self._get('favorites_pull')

    def push_binge_state(self, items, device_id):
        return self._post('binge_push', {'device_id': device_id, 'items': items})

    def pull_binge_state(self):
        return self._get('binge_pull')

    def sync_all(self, favorites=None, binge_items=None, device_id=None):
        payload = {'device_id': device_id}
        if favorites is not None:
            payload['favorites'] = favorites
        if binge_items is not None:
            payload['binge_items'] = binge_items
        return self._post('sync_push', payload)

    def pull_all(self):
        return self._get('sync_pull')

    def _get(self, action, auth=True):
        return self._request(action, 'GET', None, auth)

    def _post(self, action, payload, auth=True):
        return self._request(action, 'POST', payload, auth)

    def _request(self, action, method, payload=None, auth=True):
        body = None
        base_headers = {'Accept': 'application/json', 'User-Agent': USER_AGENT}
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            base_headers['Content-Type'] = 'application/json; charset=utf-8'

        last_error = None
        auth_keys = self.api_keys if auth else [None]
        if auth and not auth_keys:
            auth_keys = ['']
        for index, key in enumerate(auth_keys):
            headers = dict(base_headers)
            if auth and key:
                headers['Authorization'] = 'Bearer %s' % key
                headers['X-API-Key'] = key
            for base in (HTTPS_BASE, HTTP_BASE):
                try:
                    raw = self._open(base, action, method, body, headers)
                    data = json.loads(raw)
                    if not data.get('success'):
                        raise ApiError(data.get('message', 'Synchronisation fehlgeschlagen'), data.get('error_code', 'SYNC_FAILED'))
                    self.api_key = key or ''
                    return data.get('data', {})
                except urllib.error.HTTPError as exc:
                    raw = exc.read().decode('utf-8', 'ignore')
                    try:
                        data = json.loads(raw)
                        api_exc = ApiError(data.get('message', 'Synchronisation fehlgeschlagen'), data.get('error_code', 'SYNC_FAILED'), exc.code)
                    except ValueError:
                        api_exc = ApiError('Synchronisation fehlgeschlagen', 'SYNC_FAILED', exc.code)
                    if auth and api_exc.code == 'UNAUTHORIZED' and index < len(auth_keys) - 1:
                        log_utils.log('xVAULT sync: API key rejected for %s, retrying stored fallback key' % action, log_utils.LOGWARNING)
                        break
                    raise api_exc
                except ApiError as exc:
                    if auth and exc.code == 'UNAUTHORIZED' and index < len(auth_keys) - 1:
                        log_utils.log('xVAULT sync: API key rejected for %s, retrying stored fallback key' % action, log_utils.LOGWARNING)
                        break
                    raise
                except Exception as exc:
                    last_error = exc
                    log_utils.log('xVAULT sync: API call %s via %s failed: %s' % (action, base.split(':', 1)[0], _safe_error(exc)), log_utils.LOGWARNING)
                    continue
        raise ApiError('Synchronisation fehlgeschlagen. Bitte später erneut versuchen.', 'SYNC_FAILED')

    def _open(self, base, action, method, body, headers):
        url = base + action
        context = ssl.create_default_context()
        request_headers = dict(headers)
        cookie = self._challenge_cookies.get(base)
        if cookie:
            request_headers['Cookie'] = '__test=%s' % cookie

        for _attempt in range(3):
            request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
            with urllib.request.urlopen(request, timeout=TIMEOUT, context=context) as response:
                raw = response.read().decode('utf-8', 'ignore')
            if not _is_hosting_challenge(raw):
                return raw
            cookie = _solve_hosting_challenge(raw)
            self._challenge_cookies[base] = cookie
            request_headers['Cookie'] = '__test=%s' % cookie
        return raw


def _is_hosting_challenge(raw):
    return 'slowAES.decrypt' in raw and '__test=' in raw


def _solve_hosting_challenge(raw):
    values = CHALLENGE_RE.findall(raw)
    if len(values) < 3:
        raise ApiError('Synchronisation fehlgeschlagen: Hosting-Challenge konnte nicht gelesen werden.', 'SYNC_HOST_CHALLENGE')
    try:
        import pyaes
        key = bytes(bytearray.fromhex(values[0]))
        iv = bytes(bytearray.fromhex(values[1]))
        encrypted = bytes(bytearray.fromhex(values[2]))
        aes = pyaes.AESModeOfOperationCBC(key, iv=iv)
        decrypted = b''.join(aes.decrypt(encrypted[index:index + 16]) for index in range(0, len(encrypted), 16))
        return decrypted.hex()
    except ApiError:
        raise
    except Exception as exc:
        log_utils.log('xVAULT sync: hosting challenge failed: %s' % _safe_error(exc), log_utils.LOGWARNING)
        raise ApiError('Synchronisation fehlgeschlagen: Hosting-Challenge konnte nicht geloest werden.', 'SYNC_HOST_CHALLENGE')


def _safe_error(exc):
    text = str(exc)
    for token in storage.api_keys():
        text = text.replace(token, storage.mask_token(token))
    return text
