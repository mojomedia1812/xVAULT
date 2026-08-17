import json
import os
import platform as py_platform
import re
import subprocess
import time
import uuid
import urllib.error
import urllib.request

from resources.lib import control, log_utils


API_ENDPOINTS = (
    'https://all-stats.de/index.php?action=telemetry',
)
TIMEOUT = 5
HEARTBEAT_INTERVAL = 1800
CONSENT_VERSION = '2'

SETTING_ENABLED = 'telemetry.enabled'
SETTING_INSTALL_ID = 'telemetry.install_id'
SETTING_SESSION_ID = 'telemetry.session_id'
SETTING_LAST_HEARTBEAT = 'telemetry.last_heartbeat'
SETTING_CONSENT_VERSION = 'telemetry.consent_version'
SETTING_ADDON_VERSION = 'telemetry.addon_version'
STABLE_ADDON_ID = 'plugin.video.xvault'
ALPHA_ADDON_ID = 'plugin.video.xvaultalpha'

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
_RUNTIME_FAILURE_COUNT = 0
_RUNTIME_RETRY_AFTER = 0

CONTEXT_EVENTS = set([
    'installation_created',
    'addon_updated',
    'app_start',
])


def enabled():
    return control.getSetting(SETTING_ENABLED, 'true').lower() != 'false'


def status_lines():
    install_id = control.getSetting(SETTING_INSTALL_ID, '')
    session_id = control.getSetting(SETTING_SESSION_ID, '')
    context = device_context()
    return [
        'Nutzungsstatistik: %s' % ('aktiv' if enabled() else 'inaktiv'),
        'Backend: xVAULT API',
        'Installations-ID: %s' % (_mask(install_id) if install_id else 'nicht erstellt'),
        'Sitzung: %s' % (_mask(session_id) if session_id else 'nicht gestartet'),
        'xVAULT-Version: %s' % context.get('addon_version', ''),
        'xVAULT-Kanal: %s' % context.get('addon_variant', 'stable'),
        'Kodi-Version: %s' % (context.get('kodi_version', '') or 'unbekannt'),
        'OS-Klasse: %s' % context.get('os_class', 'unknown'),
        'OS-Version: %s' % context.get('os_version', 'unbekannt'),
        'Geräteklasse: %s' % context.get('device_class', 'unknown'),
        'Heartbeat: alle 30 Minuten',
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
    install_id = _valid_install_id(_current_install_id())
    if not install_id:
        install_id, _created, _should_emit_installation = _ensure_install_id()
        install_id = _valid_install_id(install_id)
    if not install_id:
        return False
    session_id = _valid_session_id(_current_session_id())
    body = {
        'install_id': install_id,
        'session_id': session_id,
        'event': event_name,
        'event_group': 'lifecycle',
    }
    if event_name in CONTEXT_EVENTS:
        body['context'] = device_context()
    if payload and event_name != 'heartbeat':
        body['payload'] = _safe_payload(payload)
    if end_reason:
        body['end_reason'] = _slug(end_reason)
    return _post(body)


def device_context():
    props = _android_props()
    os_class = _os_class(props)
    addon_id = _addon_id()
    addon_variant = _addon_variant(addon_id)
    return {
        'addon_version': _addon_version(),
        'addon_id': addon_id,
        'addon_variant': addon_variant,
        'kodi_version': _text(control.infoLabel('System.BuildVersion') or '', 64),
        'os_class': _text(os_class, 16),
        'os_version': _text(_os_version(props, os_class), 64),
        'device_class': _text(_device_class(props, os_class), 32),
        'telemetry_consent_version': CONSENT_VERSION,
    }


def _post(payload):
    global _RUNTIME_FAILURE_COUNT, _RUNTIME_RETRY_AFTER
    now = int(time.time())
    if _RUNTIME_RETRY_AFTER and now < _RUNTIME_RETRY_AFTER:
        return False

    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'Mozilla/5.0 (Kodi; xVAULT Telemetry)',
    }
    last_error = None
    for endpoint in API_ENDPOINTS:
        try:
            request = urllib.request.Request(endpoint, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                raw = response.read().decode('utf-8', 'ignore')
            parsed = json.loads(raw or '{}')
            if parsed.get('success') is True:
                _RUNTIME_FAILURE_COUNT = 0
                _RUNTIME_RETRY_AFTER = 0
                return True
            last_error = parsed.get('message', 'telemetry rejected')
        except urllib.error.HTTPError as exc:
            try:
                last_error = exc.read().decode('utf-8', 'ignore')
            except Exception:
                last_error = exc
        except Exception as exc:
            last_error = exc
        continue

    _RUNTIME_FAILURE_COUNT += 1
    _RUNTIME_RETRY_AFTER = now + min(6 * 60 * 60, 10 * 60 * (2 ** min(_RUNTIME_FAILURE_COUNT - 1, 5)))
    try:
        log_utils.log('xVAULT telemetry: event %s failed: %s' % (payload.get('event'), str(last_error)), log_utils.LOGWARNING)
    except Exception:
        pass
    return False


def _ensure_install_id():
    global _RUNTIME_INSTALL_ID
    install_id = control.getSetting(SETTING_INSTALL_ID, '')
    created = False
    if not _valid_install_id(install_id):
        install_id = str(uuid.uuid4())
        control.setSetting(SETTING_INSTALL_ID, install_id)
        created = True
    _RUNTIME_INSTALL_ID = install_id
    consent_version = control.getSetting(SETTING_CONSENT_VERSION, '')
    return install_id, created, created or consent_version != CONSENT_VERSION


def _emit_update_if_needed(created):
    current_version = _addon_version()
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
    if _valid_install_id(_RUNTIME_INSTALL_ID):
        return _RUNTIME_INSTALL_ID
    install_id, _created, _should_emit_installation = _ensure_install_id()
    return install_id


def _current_session_id():
    global _RUNTIME_SESSION_ID
    if _valid_session_id(_RUNTIME_SESSION_ID):
        return _RUNTIME_SESSION_ID
    session_id = control.getSetting(SETTING_SESSION_ID, '')
    if not _valid_session_id(session_id):
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
    if not _is_platform('Android'):
        return {}
    wanted = [
        'ro.product.manufacturer',
        'ro.product.brand',
        'ro.product.model',
        'ro.product.device',
        'ro.product.name',
        'ro.product.board',
        'ro.product.vendor.model',
        'ro.product.system.model',
        'ro.build.product',
        'ro.hardware',
        'ro.build.version.release',
        'ro.build.version.release_or_codename',
        'ro.build.version.sdk',
        'ro.build.version.incremental',
        'ro.build.characteristics',
        'ro.build.display.id',
        'ro.build.fingerprint',
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
    if _is_platform('Android'):
        maker = (props.get('ro.product.manufacturer') or props.get('ro.product.brand') or '').lower()
        model = (props.get('ro.product.model') or props.get('ro.product.device') or '').lower()
        display = (props.get('ro.build.display.id') or '').lower()
        fingerprint = (props.get('ro.build.fingerprint') or '').lower()
        if maker == 'amazon' or model.startswith('aft') or 'fire os' in display or 'amazon' in fingerprint:
            return 'FireOS'
        return 'Android'
    if _is_platform('Windows') or _visible('system.platform.uwp'):
        return 'Windows'
    if _is_platform('Linux') or _visible('System.HasAddon(service.coreelec.settings)') or _visible('System.HasAddon(service.libreelec.settings)') or _visible('System.HasAddon(service.osmc.settings)'):
        return 'Linux'
    if _is_platform('OSX') or _visible('system.platform.darwin'):
        return 'macOS'
    if _visible('system.platform.ios'):
        return 'iOS'
    if _visible('system.platform.atv2'):
        return 'tvOS'
    if _visible('system.platform.xbox'):
        return 'Xbox'
    fallback = py_platform.system().lower()
    if fallback == 'windows':
        return 'Windows'
    if fallback == 'linux':
        return 'Linux'
    if fallback == 'darwin':
        return 'macOS'
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
    if os_class == 'macOS':
        return 'PC'
    if os_class == 'tvOS':
        return 'TV Box'
    if os_class == 'Xbox':
        return 'Console'
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
        if _is_android_tv(props):
            return 'Android TV'
        return 'Android TV'
    if os_class == 'iOS':
        machine = py_platform.machine().lower()
        if 'ipad' in machine:
            return 'Tablet'
        if 'iphone' in machine or 'ipod' in machine:
            return 'Mobile'
        return 'Mobile'
    return 'unknown'


def _os_version(props, os_class):
    if os_class == 'FireOS':
        return _fire_os_version(props)
    if os_class == 'Android':
        return _android_os_version(props)
    if os_class == 'Windows':
        release = py_platform.release()
        version = py_platform.version()
        return _join_version('Windows', release, version)
    if os_class == 'Linux':
        special = _linux_appliance_version()
        if special:
            return special
        return _linux_os_release()
    if os_class == 'macOS':
        version = py_platform.mac_ver()[0] or py_platform.release()
        return _join_version('macOS', version)
    if os_class == 'iOS':
        return _join_version('iOS', _info_label_first(['System.OSVersion', 'System.BuildVersionCode']))
    if os_class == 'tvOS':
        return _join_version('tvOS', _info_label_first(['System.OSVersion', 'System.BuildVersionCode']))
    if os_class == 'Xbox':
        return _join_version('Xbox', _info_label_first(['System.OSVersion', 'System.BuildVersionCode']))
    fallback = py_platform.system()
    release = py_platform.release()
    return _join_version(fallback or 'unknown', release) if fallback else 'unbekannt'


def _fire_os_version(props):
    values = [
        props.get('ro.build.display.id'),
        props.get('ro.build.fingerprint'),
        props.get('ro.product.name'),
        props.get('ro.product.device'),
        props.get('ro.product.model'),
        props.get('ro.build.version.release_or_codename'),
        props.get('ro.build.version.release'),
        props.get('ro.build.version.sdk'),
    ]
    text = ' '.join(str(value or '').lower() for value in values)
    if 'vega' in text:
        return 'Vega OS'
    match = re.search(r'fire\s*os\s*(\d+)', text)
    if match:
        return 'Fire OS %s' % match.group(1)

    release = _major_number(props.get('ro.build.version.release_or_codename') or props.get('ro.build.version.release'))
    sdk = _major_number(props.get('ro.build.version.sdk'))
    mapped = {
        5: 'Fire OS 5',
        7: 'Fire OS 6',
        9: 'Fire OS 7',
        11: 'Fire OS 8',
        14: 'Fire OS 14',
    }.get(release)
    if mapped:
        return mapped

    mapped_sdk = {
        22: 'Fire OS 5',
        25: 'Fire OS 6',
        28: 'Fire OS 7',
        30: 'Fire OS 8',
        34: 'Fire OS 14',
    }.get(sdk)
    if mapped_sdk:
        return mapped_sdk

    if release:
        return 'Fire OS (Android %s)' % release
    return 'Fire OS unbekannt'


def _android_os_version(props):
    release = props.get('ro.build.version.release_or_codename') or props.get('ro.build.version.release')
    if release:
        return 'Android %s' % _text(release, 24)
    sdk = props.get('ro.build.version.sdk')
    if sdk:
        return 'Android SDK %s' % _text(sdk, 12)
    return 'Android unbekannt'


def _linux_appliance_version():
    if _visible('System.HasAddon(service.coreelec.settings)'):
        return _join_version('CoreELEC', _linux_version_id())
    if _visible('System.HasAddon(service.libreelec.settings)'):
        return _join_version('LibreELEC', _linux_version_id())
    if _visible('System.HasAddon(service.osmc.settings)'):
        return _join_version('OSMC', _linux_version_id())
    return ''


def _linux_os_release():
    values = _read_os_release()
    pretty = values.get('PRETTY_NAME')
    if pretty:
        return _text(pretty, 64)
    name = values.get('NAME') or 'Linux'
    version = values.get('VERSION_ID') or values.get('VERSION') or py_platform.release()
    return _join_version(name, version)


def _linux_version_id():
    values = _read_os_release()
    return values.get('VERSION_ID') or values.get('VERSION') or ''


def _read_os_release():
    result = {}
    for path in ('/etc/os-release', '/usr/lib/os-release'):
        try:
            if not os.path.exists(path):
                continue
            with open(path, 'r', encoding='utf-8', errors='ignore') as handle:
                for line in handle:
                    if '=' not in line:
                        continue
                    key, value = line.rstrip('\n').split('=', 1)
                    result[key] = value.strip().strip('"')
            if result:
                return result
        except Exception:
            pass
    return result


def _join_version(name, *parts):
    values = [str(part or '').strip() for part in parts if str(part or '').strip()]
    if values:
        return _text('%s %s' % (name, ' '.join(values)), 64)
    return _text('%s unbekannt' % name, 64)


def _major_number(value):
    match = re.search(r'\d+', str(value or ''))
    if not match:
        return None
    try:
        return int(match.group(0))
    except Exception:
        return None


def _visible(expression):
    try:
        return bool(control.condVisibility(expression))
    except Exception:
        return False


def _is_platform(name):
    return _visible('System.Platform.%s' % name) or _visible('system.platform.%s' % name.lower())


def _info_label_first(labels):
    for label in labels:
        try:
            value = control.infoLabel(label)
            if value:
                return value
        except Exception:
            pass
    return ''


def _is_android_tv(props):
    values = [
        props.get('ro.product.manufacturer'),
        props.get('ro.product.brand'),
        props.get('ro.product.model'),
        props.get('ro.product.device'),
        props.get('ro.product.name'),
        props.get('ro.product.board'),
        props.get('ro.product.vendor.model'),
        props.get('ro.product.system.model'),
        props.get('ro.build.product'),
        props.get('ro.hardware'),
        props.get('ro.build.characteristics'),
        props.get('ro.build.display.id'),
    ]
    text = ' '.join(str(value or '').lower() for value in values)
    characteristics = str(props.get('ro.build.characteristics') or '').lower()
    model = ' '.join([
        str(props.get('ro.product.model') or ''),
        str(props.get('ro.product.device') or ''),
        str(props.get('ro.product.name') or ''),
    ]).lower()

    if re.search(r'(^|[,;\s])(?:tv|box|stb|leanback)([,;\s]|$)', characteristics):
        return True
    if re.search(r'\b(?:android\s*tv|google\s*tv|smart\s*tv|set[-\s]?top|stb|tvbox|tv\s*box)\b', text):
        return True
    if re.search(r'\b(?:mibox|mi\s*box|mi\s*tv|mdz-|shield|chromecast|bravia|homatics|mecool|formuler|strong|onn\.?|amlogic|s905|s912|s922)\b', text):
        return True
    if re.search(r'\b(?:box|tv|atv)\b', model):
        return True
    return False


def _read_text(path):
    try:
        if os.path.exists(path):
            with open(path, 'rb') as handle:
                return handle.read(256).decode('utf-8', 'ignore').replace('\x00', '').strip()
    except Exception:
        pass
    return ''


def _safe_payload(payload):
    if not isinstance(payload, dict):
        return {}
    allowed = set([
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
    result = {}
    for key, value in payload.items():
        safe_key = _slug(key)
        if safe_key not in allowed:
            continue
        if isinstance(value, bool):
            result[safe_key] = bool(value)
        elif isinstance(value, (int, float)):
            result[safe_key] = value
        else:
            result[safe_key] = _slug(value)
    return result


def _valid_install_id(value):
    text = str(value or '').strip()
    if re.match(r'^[A-Za-z0-9._:-]{16,128}$', text):
        return text
    return ''


def _valid_session_id(value):
    text = str(value or '').strip()
    if re.match(r'^[A-Za-z0-9._:-]{8,128}$', text):
        return text
    return ''


def _slug(value):
    text = str(value or '').lower()
    text = re.sub(r'[^a-z0-9_:-]+', '_', text).strip('_')
    return text[:64] or 'unknown'


def _text(value, limit):
    text = str(value or '')
    text = re.sub(r'[\r\n\t]+', ' ', text)
    return text[:limit]


def _addon_version():
    return _text(control.addonVersion, 32)


def _addon_id():
    return _text(getattr(control, 'addonId', '') or STABLE_ADDON_ID, 64)


def _addon_variant(addon_id=None):
    addon_id = _text(addon_id or _addon_id(), 64).lower()
    if addon_id == ALPHA_ADDON_ID or addon_id.endswith('xvaultalpha'):
        return 'alpha'
    return 'stable'


def _mask(value):
    value = str(value or '')
    if len(value) <= 12:
        return value
    return value[:8] + '...' + value[-4:]
