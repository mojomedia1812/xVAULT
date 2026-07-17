import json
import os
import platform
import re
import subprocess
import time
import uuid
import urllib.request

from resources.lib import control, log_utils


HTTP_BASE = 'http://xvault-sql.ddnss.de/index.php?action='
HTTPS_BASE = 'https://xvault-sql.ddnss.de/index.php?action='
TIMEOUT = 5
HEARTBEAT_INTERVAL = 300
CONSENT_VERSION = '1'

SETTING_ENABLED = 'telemetry.enabled'
SETTING_INSTALL_ID = 'telemetry.install_id'
SETTING_SESSION_ID = 'telemetry.session_id'
SETTING_LAST_HEARTBEAT = 'telemetry.last_heartbeat'
SETTING_CONSENT_VERSION = 'telemetry.consent_version'

SAFE_PAYLOAD_KEYS = set([
    'menu',
    'media_type',
    'playback_mode',
    'error_group',
    'source_count',
    'working_count',
    'blocked_count',
    'sync_area',
    'setting_group',
    'feature',
])


def enabled():
    return control.getSetting(SETTING_ENABLED, 'false') == 'true'


def status_lines():
    install_id = control.getSetting(SETTING_INSTALL_ID, '')
    session_id = control.getSetting(SETTING_SESSION_ID, '')
    context = device_context()
    return [
        'Nutzungsstatistik: %s' % ('aktiv' if enabled() else 'inaktiv'),
        'Installations-ID: %s' % (_mask(install_id) if install_id else 'nicht erstellt'),
        'Sitzung: %s' % (_mask(session_id) if session_id else 'nicht gestartet'),
        'System: %s / %s' % (context.get('os_family', 'unknown'), context.get('device_class', 'unknown')),
        'Hardware: %s / %s' % (context.get('hardware_family', 'unknown'), context.get('cpu_arch', 'unknown')),
        'Letzter Heartbeat: %s' % (control.getSetting(SETTING_LAST_HEARTBEAT, '') or 'nie'),
    ]


def show_status():
    try:
        import xbmcgui
        xbmcgui.Dialog().textviewer('xVAULT Nutzungsstatistik', '\n'.join(status_lines()))
    except Exception:
        control.infoDialog('Nutzungsstatistik: %s' % ('aktiv' if enabled() else 'inaktiv'), icon='INFO')


def app_start():
    if not enabled():
        return
    _ensure_install_id()
    session_id = str(uuid.uuid4())
    control.setSetting(SETTING_SESSION_ID, session_id)
    event('app_start', 'lifecycle', {'feature': 'service'}, force=True)
    heartbeat(force=True)


def app_stop(reason='shutdown'):
    if not enabled():
        return
    event('app_stop', 'lifecycle', {'feature': 'service'}, end_reason=reason, force=True)


def heartbeat(force=False):
    if not enabled():
        return
    now = int(time.time())
    try:
        last = int(control.getSetting(SETTING_LAST_HEARTBEAT, '0') or 0)
    except Exception:
        last = 0
    if not force and now - last < HEARTBEAT_INTERVAL:
        return
    if event('heartbeat', 'lifecycle', {'feature': 'service'}, force=True):
        control.setSetting(SETTING_LAST_HEARTBEAT, str(now))


def menu_opened(menu):
    event('menu_opened', 'navigation', {'menu': _slug(menu)})


def event(name, group='general', payload=None, end_reason=None, force=False):
    if not enabled() and not force:
        return False
    if not enabled():
        return False
    install_id = _ensure_install_id()
    session_id = control.getSetting(SETTING_SESSION_ID, '')
    if not session_id:
        session_id = str(uuid.uuid4())
        control.setSetting(SETTING_SESSION_ID, session_id)
    body = {
        'install_id': install_id,
        'session_id': session_id,
        'event': _slug(name),
        'event_group': _slug(group),
        'context': device_context(),
        'payload': _clean_payload(payload or {}),
    }
    if end_reason:
        body['end_reason'] = _slug(end_reason)
    return _post('telemetry', body)


def device_context():
    props = _android_props()
    os_family = _os_family(props)
    device_class, hardware_family = _device_class(props, os_family)
    return {
        'addon_version': _text(control.addonVersion, 32),
        'kodi_version': _text(control.infoLabel('System.BuildVersion') or '', 64),
        'os_family': _text(os_family, 64),
        'os_version': _text(_os_version(props, os_family), 128),
        'device_class': _text(device_class, 64),
        'hardware_family': _text(hardware_family, 128),
        'cpu_arch': _text(platform.machine() or '', 64),
        'telemetry_consent_version': CONSENT_VERSION,
    }


def _post(action, body):
    data = json.dumps(body).encode('utf-8')
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'Mozilla/5.0 (Kodi; xVAULT Telemetry)',
    }
    last_error = None
    for base in (HTTP_BASE, HTTPS_BASE):
        try:
            request = urllib.request.Request(base + action, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                raw = response.read().decode('utf-8', 'ignore')
            parsed = json.loads(raw)
            if parsed.get('success'):
                return True
            last_error = parsed.get('message', 'telemetry rejected')
        except Exception as exc:
            last_error = exc
            continue
    try:
        log_utils.log('xVAULT telemetry: event %s failed: %s' % (body.get('event'), str(last_error)), log_utils.LOGWARNING)
    except Exception:
        pass
    return False


def _ensure_install_id():
    install_id = control.getSetting(SETTING_INSTALL_ID, '')
    if not install_id:
        install_id = str(uuid.uuid4())
        control.setSetting(SETTING_INSTALL_ID, install_id)
        control.setSetting(SETTING_CONSENT_VERSION, CONSENT_VERSION)
    return install_id


def _android_props():
    if not control.condVisibility('System.Platform.Android'):
        return {}
    wanted = [
        'ro.product.manufacturer',
        'ro.product.brand',
        'ro.product.model',
        'ro.product.device',
        'ro.build.version.release',
        'ro.build.version.incremental',
        'ro.build.characteristics',
        'ro.build.display.id',
    ]
    result = {}
    try:
        for key in wanted:
            value = subprocess.check_output(['getprop', key], stderr=subprocess.STDOUT, timeout=2)
            result[key] = value.decode('utf-8', 'ignore').strip()
    except Exception:
        pass
    return result


def _os_family(props):
    if control.condVisibility('System.Platform.Windows'):
        return 'Windows'
    if control.condVisibility('System.Platform.Android'):
        maker = (props.get('ro.product.manufacturer') or props.get('ro.product.brand') or '').lower()
        model = (props.get('ro.product.model') or props.get('ro.product.device') or '').lower()
        display = (props.get('ro.build.display.id') or '').lower()
        if maker == 'amazon' or model.startswith('aft') or 'fire os' in display:
            return 'FireOS'
        return 'Android'
    if control.condVisibility('System.Platform.OSX'):
        return 'macOS'
    if control.condVisibility('System.Platform.Linux'):
        return 'Linux'
    return platform.system() or 'Unknown'


def _os_version(props, os_family):
    if os_family in ('Android', 'FireOS'):
        version = props.get('ro.build.version.release') or ''
        display = props.get('ro.build.display.id') or ''
        if os_family == 'FireOS' and display:
            return 'FireOS %s (%s)' % (version, display)
        return 'Android %s' % version if version else os_family
    try:
        return platform.platform()
    except Exception:
        return os_family


def _device_class(props, os_family):
    if os_family == 'FireOS':
        return 'fire_tv', 'amazon_fire_tv'
    if os_family == 'Android':
        characteristics = (props.get('ro.build.characteristics') or '').lower()
        model = (props.get('ro.product.model') or '').lower()
        if 'tv' in characteristics:
            return 'android_tv', 'generic_android'
        if 'tablet' in characteristics or 'tab' in model:
            return 'tablet', 'generic_android'
        return 'mobile', 'generic_android'
    if os_family == 'Linux':
        model = _read_text('/proc/device-tree/model').lower()
        if 'raspberry pi' in model:
            return 'raspberry_pi', 'raspberry_pi'
        return 'linux_pc', 'generic_linux'
    if os_family == 'Windows':
        return 'windows_pc', 'generic_windows'
    if os_family == 'macOS':
        return 'computer', 'generic_macos'
    return 'unknown', 'unknown'


def _read_text(path):
    try:
        if os.path.exists(path):
            with open(path, 'rb') as handle:
                return handle.read(256).decode('utf-8', 'ignore').replace('\x00', '').strip()
    except Exception:
        pass
    return ''


def _clean_payload(payload):
    result = {}
    for key, value in (payload or {}).items():
        if key not in SAFE_PAYLOAD_KEYS:
            continue
        if isinstance(value, (int, float)):
            result[key] = value
        else:
            result[key] = _text(value, 128)
    return result


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
