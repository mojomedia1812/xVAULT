"""Local origin/support diagnostics. Detection is advisory, never remote attestation."""
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

from resources.lib import release_security as security

KNOWN_KODIBOX_NAVIGATOR = '8f2ae97b153f1e4deda014cbe2374a1a07e9c3ab94cc204379141a5a589586f8'
_last_result = None


def detect_kodibox(root, profile='', wizard=False, host_executable=None):
    version = ''
    try:
        version = ET.parse(os.path.join(root, 'addon.xml')).getroot().get('version', '')
    except (OSError, ET.ParseError):
        pass
    signals = []
    if 'ger.kodi.box2' in (str(root) + '/' + str(profile)).lower():
        signals.append('Android-Paket ger.kodi.box2')
    executable = str(host_executable or sys.executable).replace('\\', '/')
    windows_host = (wizard or any('kodibox' in p.lower() for p in executable.split('/'))) and any(
        'kodibox' in p.lower() for p in str(root).replace('\\', '/').split('/'))
    if windows_host:
        signals.append('KodiBox-Installationspfad und Host/Wizard (Windows/portable)')
    if wizard:
        signals.append('KodiBox-Wizard installiert (Umgebungshinweis)')
    known_copy = False
    try:
        path = os.path.join(root, 'resources', 'lib', 'indexers', 'navigator.py')
        # Normalize newline conversion only, keeping the known source fingerprint exact.
        import hashlib
        with open(path, 'rb') as f:
            digest = hashlib.sha256(f.read().replace(b'\r\n', b'\n')).hexdigest()
        known_copy = version == '2028.10.11.1' and digest == KNOWN_KODIBOX_NAVIGATOR
    except OSError:
        pass
    if known_copy:
        signals.append('Bekannte KodiBox-Dateifassung / Versionsnummer 2028.10.11.1')
    return {'detected': known_copy or windows_host or any('ger.kodi.box2' in s for s in signals),
            'known_copy': known_copy,
            'environment_hint': bool(wizard), 'signals': signals,
            'based_on': '2026.10.11.1' if known_copy else None, 'claimed_version': version}


def inspect(root=None, profile=None, force=True):
    global _last_result
    from resources.lib import control
    root = root or control.addonPath
    profile = profile or control.dataPath
    if not force and _last_result is not None:
        return _last_result
    wizard = os.path.isdir(os.path.join(os.path.dirname(root), 'plugin.program.kodibox'))
    result = {'checked_at': int(time.time()), 'kodibox': detect_kodibox(root, profile, wizard),
              'integrity': security.inspect_tree(root), 'updates_enabled': control.getSetting('updates.auto', 'true') != 'false'}
    try:
        response = json.loads(control.jsonrpc(json.dumps({'jsonrpc': '2.0', 'id': 92,
                              'method': 'Settings.GetSettingValue', 'params': {'setting': 'general.addonupdates'}})))
        result['kodi_update_mode'] = response.get('result', {}).get('value')
    except Exception:
        result['kodi_update_mode'] = None
    result['version_warning'] = security.version_warning(result['kodibox']['claimed_version'])
    if result['kodibox']['detected']:
        basis = result['kodibox']['based_on']
        if result['integrity']['state'] == 'original':
            result['summary'] = 'KodiBox-Umgebung erkannt – xVAULT-Originalpaket unveraendert'
        else:
            result['summary'] = 'KodiBox-Kopie erkannt' + (' – basiert auf ' + basis if basis else '')
        result['summary'] += ' – eigene Updates ' + ('aktiviert' if result['updates_enabled'] else 'deaktiviert')
    elif result['integrity']['state'] == 'original':
        result['summary'] = result['integrity']['message']
    else:
        result['summary'] = result['integrity']['message']
    _last_result = result
    try:
        os.makedirs(profile, exist_ok=True)
        path = os.path.join(profile, 'distribution-status.json')
        temp = path + '.%s.tmp' % os.getpid()
        with open(temp, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    except OSError:
        pass
    return result


def cached_status():
    from resources.lib import control
    try:
        with open(os.path.join(control.dataPath, 'distribution-status.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def checkpoint(source, rehash=False, notify=False):
    """Called independently from entry point, service, playback, updater and support."""
    from resources.lib import control, log_utils
    if rehash:
        result = inspect(force=True)
    else:
        result = cached_status()
        detected = detect_kodibox(control.addonPath, control.dataPath,
                                  os.path.isdir(os.path.join(os.path.dirname(control.addonPath), 'plugin.program.kodibox')))
        if detected['detected']:
            result = inspect(force=True)
        if not result:
            result = inspect(force=True)
    suspicious = (result.get('kodibox', {}).get('detected') or result.get('version_warning') or
                  result.get('integrity', {}).get('state') in ('modified', 'invalid_reference'))
    if suspicious:
        log_utils.log('xVAULT Herkunft [%s]: %s; %s' %
                      (source, result.get('summary'), result.get('version_warning', '')), log_utils.LOGWARNING)
        if notify:
            # Throttle repeated playback notifications, but keep a visible status menu entry.
            key = 'plugin.video.xvault.origin.notification'
            now = time.time()
            try:
                previous = float(control.window.getProperty(key) or '0')
            except ValueError:
                previous = 0
            if now - previous > 300:
                control.infoDialog(result.get('summary', 'Originalstatus nicht bestaetigt'), time=8000)
                control.window.setProperty(key, str(now))
    return result


def show_status():
    from resources.lib import control
    import xbmcgui
    result = checkpoint('support-dialog', rehash=True)
    from resources.lib import updater
    state = updater.read_state()
    lines = [result['summary'], result.get('version_warning', ''), '',
             'Installiert: ' + result['kodibox']['claimed_version'],
             'Kanal: ' + updater.selected_channel(),
             'Integritaet: ' + result['integrity']['state'],
             'Berechneter SHA-256: ' + result['integrity'].get('installed_sha256', 'nicht verfuegbar'),
             'Referenz-SHA-256: ' + result['integrity'].get('expected_sha256', 'nicht verfuegbar'),
             'Updatepruefung: ' + state.get('message', 'Noch nicht ausgefuehrt'),
             'Repository-Referenz abgeglichen: ' + str(state.get('repository_match', 'noch nicht erreichbar')),
             '', 'Die lokale Pruefung erkennt Veraenderungen gegen eine signierte Referenz.',
             'Sie ist keine nicht umgehbare Attestierung des Kodi-Hosts.']
    if state.get('release'):
        lines.append('Zielversion: ' + state['release']['version'])
    for kind in ('changed', 'missing', 'extra'):
        values = result['integrity'].get(kind, [])
        if values:
            lines.append('%s: %s' % (kind, ', '.join(values[:15])))
    xbmcgui.Dialog().textviewer('xVAULT – Herkunft, Updates und Supportstatus', '\n'.join(lines))
