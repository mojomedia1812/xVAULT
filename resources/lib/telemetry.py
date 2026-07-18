import json
import os
import re
import subprocess
import time
import uuid
import urllib.error
import urllib.request

from resources.lib import control, log_utils


SUPABASE_RPC_URL = 'https://edluzxyhbmrtardcjqwy.supabase.co/rest/v1/rpc/xvault_ingest'
SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_Vzsxq3UGeHXoOoN5d3ehng_mcOB_pWj'
TIMEOUT = 5
HEARTBEAT_INTERVAL = 600
CONSENT_VERSION = '2'

SETTING_ENABLED = 'telemetry.enabled'
SETTING_INSTALL_ID = 'telemetry.install_id'
SETTING_SESSION_ID = 'telemetry.session_id'
SETTING_LAST_HEARTBEAT = 'telemetry.last_heartbeat'
SETTING_CONSENT_VERSION = 'telemetry.consent_version'
SETTING_ADDON_VERSION = 'telemetry.addon_version'

ALLOWED_EVENTS = set([
    'installation_created',
    'addon_updated',
    'app_start',
    'app_stop',
    'heartbeat',
])

_RUNTIME_INSTALL_ID = None
_RUNTIME_SESSION_ID = None
_RUNTIME_LAST_HEARTBEAT = 0


def enabled():
    return control.getSetting(SETTING_ENABLED, 'false') == 'true'


def status_lines():
    install_id = control.getSetting(SETTING_INSTALL_ID, '')
    session_id = control.getSetting(SETTING_SESSION_ID, '')
    context = device_context()
    return [
        'Nutzungsstatistik: %s' % ('aktiv' if enabled() else 'inaktiv'),
        'Backend: Supabase',
        'Installations-ID: %s' % (_mask(install_id) if install_id else 'nicht erstellt'),
        'Sitzung: %s' % (_mask(session_id) if session_id else 'nicht gestartet'),
        'xVAULT-Version: %s' % context.get('addon_version', ''),
        'Kodi-Version: %s' % (context.get('kodi_version', '') or 'unbekannt'),
        'OS-Klasse: %s' % context.get('os_class', 'unknown'),
        'Geräteklasse: %s' % context.get('device_class', 'unknown'),
        'Heartbeat: alle 10 Minuten',
        'Letzter Heartbeat: %s' % (control.getSetting(SETTING_LAST_HEARTBEAT, '') or 'nie'),
    ]


def show_status():
    try:
        import xbmcgui
        xbmcgui.Dialog().textviewer('xVAULT Nutzungsstatistik', '\n'.join(status_lines()))
    except Exception:
        control.infoDialog('Nutzungsstatistik: %s' % ('aktiv' if enabled() else 'inaktiv'), icon='INFO')


def app_start():
    global _RUNTIME_INSTALL_ID, _RUNTIME_SESSION_ID
    if not enabled():
        return
    install_id, created, should_emit_installation = _ensure_install_id()
    _RUNTIME_INSTALL_ID = install_id
    _RUNTIME_SESSION_ID = str(uuid.uuid4())
    control.setSetting(SETTING_SESSION_ID, _RUNTIME_SESSION_ID)
    if should_emit_installation:
        if event('installation_created', 'lifecycle', {'feature': 'service'}, force=True):
            control.setSetting(SETTING_CONSENT_VERSION, CONSENT_VERSION)
    _emit_update_if_needed(created)
    if event('app_start', 'lifecycle', {'feature': 'service'}, force=True):
        _set_last_heartbeat(int(time.time()))


def app_stop(reason='shutdown'):
    if not enabled():
        return
    event('app_stop', 'lifecycle', {'feature': 'service'}, end_reason=reason, force=True)


def heartbeat(force=False):
    if not enabled():
        return
    now = int(time.time())
    last = _last_heartbeat()
    if not force and now - last < HEARTBEAT_INTERVAL:
        return
    if event('heartbeat', 'lifecycle', {'feature': 'service'}, force=True):
        _set_last_heartbeat(now)


def menu_opened(menu):
    event('menu_opened', 'navigation', {'menu': _slug(menu)})


def event(name, group='general', payload=None, end_reason=None, force=False):
    event_name = _slug(name)
    if event_name not in ALLOWED_EVENTS:
        return False
    if not enabled() and not force:
        return False
    if not enabled():
        return False
    install_id = _current_install_id()
    session_id = _current_session_id()
    body = {
        'install_id': install_id,
        'session_id': session_id,
        'event': event_name,
        'event_group': 'lifecycle',
        'context': device_context(),
    }
    if end_reason:
        body['end_reason'] = _slug(end_reason)
    return _post(body)


def device_context():
    props = _android_props()
    os_class = _os_class(props)
    return {
        'addon_version': _text(control.addonVersion, 32),
        'kodi_version': _text(control.infoLabel('System.BuildVersion') or '', 64),
        'os_class': _text(os_class, 16),
        'device_class': _text(_device_class(props, os_class), 32),
    }


def _post(payload):
    body = json.dumps({'payload': payload}).encode('utf-8')
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer %s' % SUPABASE_PUBLISHABLE_KEY,
        'apikey': SUPABASE_PUBLISHABLE_KEY,
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'Mozilla/5.0 (Kodi; xVAULT Telemetry)',
    }
    last_error = None
    try:
        request = urllib.request.Request(SUPABASE_RPC_URL, data=body, headers=headers, method='POST')
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read().decode('utf-8', 'ignore')
        parsed = json.loads(raw or '{}')
        if parsed.get('success') is True:
            return True
        last_error = parsed.get('message', 'telemetry rejected')
    except urllib.error.HTTPError as exc:
        try:
            last_error = exc.read().decode('utf-8', 'ignore')
        except Exception:
            last_error = exc
    except Exception as exc:
        last_error = exc
    try:
        log_utils.log('xVAULT telemetry: event %s failed: %s' % (payload.get('event'), str(last_error)), log_utils.LOGWARNING)
    except Exception:
        pass
    return False


def _ensure_install_id():
    global _RUNTIME_INSTALL_ID
    install_id = control.getSetting(SETTING_INSTALL_ID, '')
    created = False
    if not install_id:
        install_id = str(uuid.uuid4())
        control.setSetting(SETTING_INSTALL_ID, install_id)
        created = True
    _RUNTIME_INSTALL_ID = install_id
    consent_version = control.getSetting(SETTING_CONSENT_VERSION, '')
    return install_id, created, created or consent_version != CONSENT_VERSION


def _emit_update_if_needed(created):
    current_version = _text(control.addonVersion, 32)
    if not current_version:
        return
    stored_version = control.getSetting(SETTING_ADDON_VERSION, '')
    if created or not stored_version:
        control.setSetting(SETTING_ADDON_VERSION, current_version)
        return
    if stored_version == current_version:
        return
    if event('addon_updated', 'lifecycle', {'feature': 'service'}, force=True):
        control.setSetting(SETTING_ADDON_VERSION, current_version)


def _current_install_id():
    global _RUNTIME_INSTALL_ID
    if _RUNTIME_INSTALL_ID:
        return _RUNTIME_INSTALL_ID
    install_id, _created, _should_emit_installation = _ensure_install_id()
    return install_id


def _current_session_id():
    global _RUNTIME_SESSION_ID
    if _RUNTIME_SESSION_ID:
        return _RUNTIME_SESSION_ID
    session_id = control.getSetting(SETTING_SESSION_ID, '')
    if not session_id:
        session_id = str(uuid.uuid4())
        control.setSetting(SETTING_SESSION_ID, session_id)
    _RUNTIME_SESSION_ID = session_id
    return session_id


def _last_heartbeat():
    if _RUNTIME_LAST_HEARTBEAT:
        return _RUNTIME_LAST_HEARTBEAT
    try:
        return int(control.getSetting(SETTING_LAST_HEARTBEAT, '0') or 0)
    except Exception:
        return 0


def _set_last_heartbeat(timestamp):
    global _RUNTIME_LAST_HEARTBEAT
    _RUNTIME_LAST_HEARTBEAT = int(timestamp or 0)
    control.setSetting(SETTING_LAST_HEARTBEAT, str(_RUNTIME_LAST_HEARTBEAT))


def _android_props():
    if not control.condVisibility('System.Platform.Android'):
        return {}
    wanted = [
        'ro.product.manufacturer',
        'ro.product.brand',
        'ro.product.model',
        'ro.product.device',
        'ro.build.version.release',
        'ro.build.characteristics',
        'ro.build.display.id',
    ]
    result = {}
    for key in wanted:
        try:
            value = subprocess.check_output(['getprop', key], stderr=subprocess.STDOUT, timeout=2)
            result[key] = value.decode('utf-8', 'ignore').strip()
        except Exception:
            continue
    return result


def _os_class(props):
    if control.condVisibility('System.Platform.Windows'):
        return 'Windows'
    if control.condVisibility('System.Platform.Android'):
        maker = (props.get('ro.product.manufacturer') or props.get('ro.product.brand') or '').lower()
        model = (props.get('ro.product.model') or props.get('ro.product.device') or '').lower()
        display = (props.get('ro.build.display.id') or '').lower()
        if maker == 'amazon' or model.startswith('aft') or 'fire os' in display:
            return 'FireOS'
        return 'Android'
    if control.condVisibility('System.Platform.Linux'):
        return 'Linux'
    return 'unknown'


def _device_class(props, os_class):
    if os_class == 'FireOS':
        return 'Fire TV'
    if os_class == 'Linux':
        model = _read_text('/proc/device-tree/model').lower()
        if 'raspberry pi' in model:
            return 'Raspberry Pi'
        return 'PC'
    if os_class == 'Windows':
        return 'PC'
    if os_class == 'Android':
        manufacturer = (props.get('ro.product.manufacturer') or props.get('ro.product.brand') or '').lower()
        model = (props.get('ro.product.model') or props.get('ro.product.device') or '').lower()
        characteristics = (props.get('ro.build.characteristics') or '').lower()
        if manufacturer == 'amazon' or model.startswith('aft'):
            return 'Fire TV'
        if 'tablet' in characteristics or 'tab' in model:
            return 'Tablet'
        if 'phone' in characteristics or 'mobile' in characteristics:
            return 'Mobile'
        return 'unknown'
    return 'unknown'


def _read_text(path):
    try:
        if os.path.exists(path):
            with open(path, 'rb') as handle:
                return handle.read(256).decode('utf-8', 'ignore').replace('\x00', '').strip()
    except Exception:
        pass
    return ''


def _slug(value):
    text = str(value or '').lower()
    text = re.sub(r'[^a-z0-9_:-]+', '_', text).strip('_')
    return text[:64] or 'unknown'


def _text(value, limit):
    text = str(value or '')
    text = re.sub(r'[\r\n\t]+', ' ', text)
    return text[:limit]


def _mask(value):
    value = str(value or '')
    if len(value) <= 12:
        return value
    return value[:8] + '...' + value[-4:]
