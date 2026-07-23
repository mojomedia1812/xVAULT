import json
import uuid

try:
    import requests
except Exception:
    requests = None

from resources.lib import control, log_utils


RPC_URL = 'https://edluzxyhbmrtardcjqwy.supabase.co/rest/v1/rpc/xvault_plus_unlock'
PUBLISHABLE_KEY = 'sb_publishable_Vzsxq3UGeHXoOoN5d3ehng_mcOB_pWj'
REQUEST_TIMEOUT = 12
SETTING_CLIENT_ID = 'plus.client_id'
SETTING_ENABLED = 'plus.enabled'


def activate():
    code = _password_input()
    if not code:
        return
    try:
        data = _unlock(code)
        if not data.get('success'):
            control.infoDialog('Aktivierung nicht moeglich.', icon='WARNING', time=5000)
            return

        from resources.lib import updater
        updater.configure_external_source(data.get('manifest_url'), data.get('download_url'))
        control.setSetting(SETTING_ENABLED, 'true')
        control.infoDialog('Aktivierung erfolgreich. Aktualisierung wird vorbereitet.', icon='INFO', time=5000)
        updater.check_for_update(prompt=False, ignore_disabled=True)
    except Exception as exc:
        log_utils.log('Plus activation failed: %s' % str(exc), log_utils.LOGWARNING)
        control.infoDialog('Aktivierung fehlgeschlagen.', icon='ERROR', time=5000)


def _password_input():
    keyboard = control.keyboard('', 'Plus', True)
    try:
        keyboard.setHiddenInput(True)
    except Exception:
        pass
    keyboard.doModal()
    if not keyboard.isConfirmed():
        return ''
    return (keyboard.getText() or '').strip()


def _unlock(code):
    if requests is None:
        raise RuntimeError('requests module is not available')
    payload = {
        'code': str(code or ''),
        'client_id': _client_id(),
        'context': {
            'addon_id': control.addonId,
            'addon_version': control.addonVersion,
        },
    }
    response = requests.post(
        RPC_URL,
        data=json.dumps({'payload': payload}),
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'apikey': PUBLISHABLE_KEY,
            'Authorization': 'Bearer ' + PUBLISHABLE_KEY,
            'User-Agent': '%s/%s' % (control.addonId, control.addonVersion),
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError('invalid unlock response')
    return data


def _client_id():
    value = control.getSetting(SETTING_CLIENT_ID, '')
    try:
        uuid.UUID(value)
        return value
    except Exception:
        value = str(uuid.uuid4())
        control.setSetting(SETTING_CLIENT_ID, value)
        return value
