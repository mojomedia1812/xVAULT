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

        from resources.lib import updater as updater_module
        manifest_url, download_url = _alpha_source(data, updater_module)
        control.setSetting(SETTING_ENABLED, 'true')

        release = updater_module.get_alpha_release(manifest_url, download_url)
        latest_version = release.get('version')
        if not latest_version:
            raise RuntimeError('missing update version')

        log_utils.log(
            'Update release check: target=%s latest=%s' % (updater_module.ALPHA_ADDON_ID, latest_version),
            log_utils.LOGINFO
        )
        log_utils.log('Update install start: addon=%s target=%s' % (updater_module.ALPHA_ADDON_ID, latest_version), log_utils.LOGINFO)
        control.infoDialog('Aktivierung erfolgreich. Version %s wird installiert.' % latest_version, icon='INFO', time=5000)
        if not updater_module.install_update(
            latest_version,
            release.get('download_url'),
            addon_id=updater_module.ALPHA_ADDON_ID,
            run_after=True
        ):
            control.setSetting(SETTING_ENABLED, 'false')
    except Exception as exc:
        log_utils.log('Plus activation failed: %s' % str(exc), log_utils.LOGWARNING)
        control.setSetting(SETTING_ENABLED, 'false')
        control.infoDialog('Aktivierung fehlgeschlagen.', icon='ERROR', time=5000)


def deactivate():
    if not _confirm_deactivation():
        return

    try:
        from resources.lib import updater as updater_module
        updater = updater_module

        release = updater.get_stable_release()
        control.setSetting(SETTING_ENABLED, 'false')
        updater.reset_update_source()

        if not updater.install_update(
            release['version'],
            release['download_url'],
            addon_id=updater.STABLE_ADDON_ID,
            run_after=True
        ):
            control.setSetting(SETTING_ENABLED, 'true')
    except Exception as exc:
        log_utils.log('Plus deactivation failed: %s' % str(exc), log_utils.LOGWARNING)
        control.setSetting(SETTING_ENABLED, 'true')
        control.infoDialog('Plus-Deaktivierung fehlgeschlagen.', icon='ERROR', time=5000)


def _confirm_deactivation():
    return control.yesnoDialog(
        'Plus deaktivieren und zu xVAULT wechseln?',
        'Die aktuelle Standard-Version wird heruntergeladen.',
        'xVAULT danach bitte erneut oeffnen.',
        heading=control.addonName,
        nolabel='Abbrechen',
        yeslabel='Deaktivieren'
    )


def _alpha_source(data, updater):
    return updater.ALPHA_MANIFEST_URL, updater.ALPHA_DOWNLOAD_URL


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
