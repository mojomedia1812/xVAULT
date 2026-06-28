import json
import ssl
import urllib.error
import urllib.request

from resources.lib import log_utils
from resources.lib.sync import storage


HTTPS_BASE = 'https://xvault.xo.je/index.php?action='
HTTP_BASE = 'http://xvault.xo.je/index.php?action='
TIMEOUT = 15


class ApiError(Exception):
    def __init__(self, message, code='SYNC_FAILED', status=None):
        Exception.__init__(self, message)
        self.code = code
        self.status = status


class Client(object):
    def __init__(self, api_key=None):
        self.api_key = api_key if api_key is not None else storage.api_key()

    def register(self, email, password):
        return self._post('register', {'email': email, 'password': password}, auth=False)

    def login(self, email, password):
        return self._post('login', {'email': email, 'password': password}, auth=False)

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
        headers = {'Accept': 'application/json'}
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json; charset=utf-8'
        if auth and self.api_key:
            headers['Authorization'] = 'Bearer %s' % self.api_key
            headers['X-API-Key'] = self.api_key

        last_error = None
        for base in (HTTPS_BASE, HTTP_BASE):
            try:
                request = urllib.request.Request(base + action, data=body, headers=headers, method=method)
                context = ssl.create_default_context()
                with urllib.request.urlopen(request, timeout=TIMEOUT, context=context) as response:
                    raw = response.read().decode('utf-8')
                data = json.loads(raw)
                if not data.get('success'):
                    raise ApiError(data.get('message', 'Synchronisation fehlgeschlagen'), data.get('error_code', 'SYNC_FAILED'))
                return data.get('data', {})
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode('utf-8', 'ignore')
                try:
                    data = json.loads(raw)
                    raise ApiError(data.get('message', 'Synchronisation fehlgeschlagen'), data.get('error_code', 'SYNC_FAILED'), exc.code)
                except ValueError:
                    raise ApiError('Synchronisation fehlgeschlagen', 'SYNC_FAILED', exc.code)
            except ApiError:
                raise
            except Exception as exc:
                last_error = exc
                log_utils.log('xVAULT sync: API call %s via %s failed: %s' % (action, base.split(':', 1)[0], _safe_error(exc)), log_utils.LOGWARNING)
                continue
        raise ApiError('Synchronisation fehlgeschlagen. Bitte später erneut versuchen.', 'SYNC_FAILED')


def _safe_error(exc):
    text = str(exc)
    token = storage.api_key()
    if token:
        text = text.replace(token, storage.mask_token(token))
    return text
