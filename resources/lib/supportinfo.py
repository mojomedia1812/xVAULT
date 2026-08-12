# edit 2026-07-17

import hashlib
import io
import json
import os
import platform as py_platform
import re
import shutil
import sys
import time
import uuid
import zipfile
from datetime import datetime
from glob import glob

import xbmc
import xbmcaddon
import xbmcgui

try:
    import requests
except Exception:
    requests = None

from resources.lib import control
from resources.lib.control import translatePath


SUPPORT_TITLE = 'xVAULT Support'
SUPPORT_USER_AGENT = '%s/%s support-uploader' % (control.addonId, control.addonVersion)
MAX_LOG_BYTES = 512 * 1024
MAX_LOG_LINES = 1200
MAX_UPLOAD_WARNING_BYTES = 100 * 1024 * 1024
SUPPORT_PROVIDER_FILEIO = 'file.io'
SUPPORT_PROVIDER_FILEBIN = 'filebin.net'
SUPPORT_PROVIDER_0X0 = '0x0.st'
SHORTENER_SERVICES = (
    {'name': 'da.gd', 'kind': 'plain_get', 'url': 'https://da.gd/s'},
    {'name': 'tinyurl.com', 'kind': 'plain_get', 'url': 'https://tinyurl.com/api-create.php'},
    {'name': 'is.gd', 'kind': 'isgd', 'url': 'https://is.gd/create.php'},
    {'name': 'v.gd', 'kind': 'isgd', 'url': 'https://v.gd/create.php'},
)

SENSITIVE_SETTING_PARTS = (
    'pass', 'passwd', 'password', 'token', 'api', 'key', 'secret', 'cookie',
    'auth', 'email', 'user', 'login', 'account', 'device_id', 'install_id',
    'session_id', 'hash', 'link',
)
PATH_SETTING_PARTS = ('path', 'folder', 'dir')

LOG_TOKENS = (
    'xvault',
    'plugin.video.xvault',
    'plugin.video.xvaultalpha',
    'plugin.video.themoviedb.helper',
    'tmdbhelper',
    'the movie db helper',
    'x-directory/normal',
    'plugin.video.xstream',
    '[ xvault debug ]',
    'resources.lib',
    'scrapers.scrapers_source',
    'resolveurl',
    'inputstream.adaptive',
    'inputstream.ffmpegdirect',
    'inputstream.rtmp',
    'pvr.iptvsimple',
)


def getRepofromAddonsDB(addonID):
    try:
        from sqlite3 import dbapi2 as database

        database_path = translatePath('special://database/')
        matches = sorted(glob(os.path.join(database_path, 'Addons*.db')), reverse=True)
        if not matches:
            return ''
        dbcon = database.connect(matches[0])
        try:
            dbcur = dbcon.cursor()
            dbcur.execute("SELECT origin FROM installed WHERE addonID = ?", (addonID,))
            match = dbcur.fetchone()
            return match[0] if match and len(match) > 0 else ''
        finally:
            dbcon.close()
    except Exception:
        return ''


def platform():
    if xbmc.getCondVisibility('system.platform.android'):
        return 'Android'
    if xbmc.getCondVisibility('system.platform.linux.Raspberrypi'):
        return 'Linux/RPi'
    if xbmc.getCondVisibility('system.platform.linux'):
        return 'Linux'
    if xbmc.getCondVisibility('system.platform.windows'):
        return 'Windows'
    if xbmc.getCondVisibility('system.platform.uwp'):
        return 'Windows UWP'
    if xbmc.getCondVisibility('system.platform.osx'):
        return 'OSX'
    if xbmc.getCondVisibility('system.platform.atv2'):
        return 'ATV2'
    if xbmc.getCondVisibility('system.platform.ios'):
        return 'iOS'
    if xbmc.getCondVisibility('system.platform.darwin'):
        return 'iOS'
    if xbmc.getCondVisibility('system.platform.xbox'):
        return 'XBOX'
    if xbmc.getCondVisibility('System.HasAddon(service.coreelec.settings)'):
        return 'CoreElec'
    if xbmc.getCondVisibility('System.HasAddon(service.libreelec.settings)'):
        return 'LibreElec'
    if xbmc.getCondVisibility('System.HasAddon(service.osmc.settings)'):
        return 'OSMC'
    return py_platform.system() or 'Unknown'


def getDNS(dns):
    status = 'Beschaeftigt'
    loop = 1
    while status == 'Beschaeftigt':
        if loop == 20:
            break
        status = xbmc.getInfoLabel(dns)
        xbmc.sleep(10)
        loop += 1
    return status


def pluginInfo():
    lines = [
        'Kodi Version:  %s (Code Version: %s)' % (
            xbmc.getInfoLabel('System.BuildVersion')[:4],
            xbmc.getInfoLabel('System.BuildVersionCode'),
        ),
        'System Plattform:   %s' % platform(),
        'FreeMem: %sMB' % str(xbmc.getFreeMem()),
        'aktiver Skin: %s' % xbmc.getSkinDir(),
        '',
        'Plugin Informationen zu %s:' % xbmcaddon.Addon().getAddonInfo('name'),
        'Version:  %s - %s' % (
            xbmcaddon.Addon().getAddonInfo('id'),
            xbmcaddon.Addon().getAddonInfo('version'),
        ),
        'installiert aus Repository:  %s' % getRepofromAddonsDB(xbmcaddon.Addon().getAddonInfo('id')),
        '',
    ]

    lines.extend(_addon_info_lines('script.module.resolveurl', 'ResolveURL'))
    lines.extend([''])
    lines.extend(_addon_info_lines('plugin.video.themoviedb.helper', 'TMDbHelper'))
    lines.extend(_tmdbhelper_status_lines())
    lines.extend([
        '',
        'aktiver DNS Nameserver1: %s' % getDNS('Network.DNS1Address'),
        'aktiver DNS Nameserver2: %s' % getDNS('Network.DNS2Address'),
    ])

    xbmcgui.Dialog().textviewer('xVAULT Support Informationen', '\n'.join(lines))


def createSupportPackageAndUpload():
    support_uuid = str(uuid.uuid4())
    created_at = _utc_timestamp()
    date_part = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_name = '%s_%s.zip' % (support_uuid, date_part)
    temp_root = _support_temp_root()
    workspace = os.path.join(temp_root, support_uuid)
    zip_path = os.path.join(temp_root, zip_name)
    progress = xbmcgui.DialogProgress()

    try:
        _mkdir(temp_root)
        _remove_tree(workspace)
        _mkdir(workspace)

        progress.create(SUPPORT_TITLE, 'Sammle Diagnosedaten...')
        manifest = _build_support_workspace(workspace, support_uuid, zip_name, created_at)
        progress.update(65, 'Erstelle ZIP-Datei...')
        _zip_workspace(workspace, zip_path)
        zip_size = os.path.getsize(zip_path)
        progress.close()

        _show_package_manifest(manifest, zip_size)
        if not _confirm_upload(manifest, zip_size):
            _delete_file(zip_path)
            control.infoDialog('Supportpaket verworfen. UUID: %s' % support_uuid, icon='INFO', time=6000)
            return

        progress.create(SUPPORT_TITLE, 'Lade Supportpaket hoch...')
        progress.update(20, 'Upload wird gestartet...')
        upload_result = _upload_support_zip(zip_path, zip_name, manifest.get('provider', {}))
        progress.update(90, 'Loesche lokales ZIP...')
        upload_result = _add_short_url(upload_result)
        _store_last_upload(support_uuid, zip_name, zip_size, upload_result)
        _delete_file(zip_path)
        progress.close()

        control.setSetting(id='support.last_uuid', value=support_uuid)
        control.setSetting(id='support.last_link', value=upload_result.get('short_link') or upload_result.get('link', ''))
        xbmcgui.Dialog().ok(
            SUPPORT_TITLE,
            'Upload erfolgreich.[CR]Service-ID: %s' % (
                upload_result.get('short_id') or _short_url_service_id(upload_result.get('short_link', '')) or 'nicht verfuegbar'
            ),
        )
    except Exception as exc:
        try:
            progress.close()
        except Exception:
            pass
        _delete_file(zip_path)
        _log('Support upload failed for %s: %s' % (support_uuid, str(exc)), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(
            SUPPORT_TITLE,
            'Supportpaket konnte nicht hochgeladen werden.[CR]UUID: %s[CR]Fehler: %s[CR]Lokales ZIP wurde geloescht.' % (
                support_uuid,
                _short_error(exc),
            ),
        )
    finally:
        _remove_tree(workspace)


def _addon_info_lines(addon_id, label):
    try:
        addon = xbmcaddon.Addon(addon_id)
        return [
            'Plugin Informationen zu %s:' % addon.getAddonInfo('name'),
            'Version:  %s - %s' % (addon.getAddonInfo('id'), addon.getAddonInfo('version')),
            'installiert aus Repository:  %s' % getRepofromAddonsDB(addon_id),
        ]
    except Exception:
        return ['Plugin Informationen zu %s: nicht installiert' % label]


def _build_support_workspace(workspace, support_uuid, zip_name, created_at):
    manifest = {
        'support_uuid': support_uuid,
        'zip_filename': zip_name,
        'created_at_utc': created_at,
        'provider': _provider_config(),
        'contains': [
            'Addon-/Kodi-/Python-Versionen',
            'relevante Abhaengigkeiten',
            'TMDbHelper-Integrationsstatus inklusive xVAULT-Player-Datei',
            'redigierte Plugin-Einstellungen',
            'xVAULT-bezogene Kodi-Logzeilen',
            'TMDbHelper- und alte xStream-bezogene Kodi-Logzeilen',
            'Dateiliste mit Groessen und SHA256 fuer Addon-Quelldateien',
            'Profil-Dateiliste ohne Datenbankinhalte',
            'Dateistatus verwandter Addon-Profile ohne Inhalte',
        ],
        'excluded': [
            'Passwoerter, Tokens, API-Keys, Cookies',
            'Kunden-/Dokumentinhalte',
            'Suchverlauf und Favoriteninhalte',
            'lokale Datenbanken selbst',
            'Screenshots, Caches, Downloads',
            'vollstaendige Kodi-Systemlogs',
            'vollstaendige TMDbHelper-/xStream-Profile',
        ],
    }

    _write_json(os.path.join(workspace, 'environment.json'), {
        'addon': _addon_context(),
        'system': _system_context(),
        'dependencies': _dependency_context(),
        'integrations': _integration_context(),
    })
    _write_json(os.path.join(workspace, 'settings_redacted.json'), _settings_context())
    _write_json(os.path.join(workspace, 'addon_files.json'), _addon_files_context())
    _write_json(os.path.join(workspace, 'profile_files.json'), _profile_files_context())
    _write_json(os.path.join(workspace, 'related_profile_files.json'), _related_profile_files_context())
    _write_text(os.path.join(workspace, 'recent_xvault_log.txt'), _recent_xvault_log())

    manifest['package_files'] = _workspace_file_summary(workspace)
    _write_json(os.path.join(workspace, 'manifest.json'), manifest)
    return manifest


def _addon_context():
    return {
        'id': control.addonId,
        'name': control.addonName,
        'version': control.addonVersion,
        'path': _redact_path(control.addonPath),
        'profile_path': _redact_path(control.addonProfilePath),
        'repository': getRepofromAddonsDB(control.addonId),
    }


def _system_context():
    return {
        'created_local': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'created_utc': _utc_timestamp(),
        'timezone': time.tzname[0] if time.tzname else '',
        'kodi_build': xbmc.getInfoLabel('System.BuildVersion'),
        'kodi_build_code': xbmc.getInfoLabel('System.BuildVersionCode'),
        'platform': platform(),
        'skin': xbmc.getSkinDir(),
        'language': xbmc.getLanguage() if hasattr(xbmc, 'getLanguage') else '',
        'free_memory_mb': xbmc.getFreeMem(),
        'python_version': sys.version.split()[0],
        'python_executable': _redact_path(sys.executable),
        'os': _redact_text(py_platform.platform()),
        'machine': py_platform.machine(),
        'dns1': _redact_text(getDNS('Network.DNS1Address')),
        'dns2': _redact_text(getDNS('Network.DNS2Address')),
    }


def _dependency_context():
    addon_ids = [
        'script.module.requests',
        'script.module.six',
        'script.module.resolveurl',
        'inputstream.adaptive',
        'inputstream.ffmpegdirect',
        'inputstream.rtmp',
        'pvr.iptvsimple',
        'plugin.video.youtube',
        'plugin.video.themoviedb.helper',
        'plugin.video.xstream',
        'repository.xvault',
    ]
    result = []
    for addon_id in addon_ids:
        item = {'id': addon_id, 'installed': bool(xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id))}
        if item['installed']:
            try:
                addon = xbmcaddon.Addon(addon_id)
                item.update({
                    'name': addon.getAddonInfo('name'),
                    'version': addon.getAddonInfo('version'),
                    'repository': getRepofromAddonsDB(addon_id),
                })
            except Exception:
                pass
        result.append(item)
    return result


def _integration_context():
    return {
        'tmdbhelper': _tmdbhelper_diagnostics(),
    }


def _tmdbhelper_diagnostics():
    try:
        from resources.lib import tmdbhelper_integration
        data = tmdbhelper_integration.diagnostics()
        if data.get('target_path'):
            data['target_path'] = _redact_path(data.get('target_path'))
        if data.get('legacy_target_path'):
            data['legacy_target_path'] = _redact_path(data.get('legacy_target_path'))
        return data
    except Exception as exc:
        return {'error': str(exc)}


def _tmdbhelper_status_lines():
    data = _tmdbhelper_diagnostics()
    if data.get('error'):
        return ['TMDbHelper Status: Fehler: %s' % data.get('error')]
    return [
        'TMDbHelper Status: %s' % data.get('state', 'unknown'),
        'TMDbHelper aktiviert: %s' % data.get('enabled'),
        'TMDbHelper Version: %s' % (data.get('version') or 'unbekannt'),
        'xVAULT-Player vorhanden: %s' % data.get('target_exists'),
        'xVAULT-Player aktuell: %s' % data.get('target_matches_source'),
    ]


def _settings_context():
    settings_file = os.path.join(control.addonPath, 'resources', 'settings.xml')
    entries = []
    provider_fallback = {}
    try:
        import xml.etree.ElementTree as ET

        root = ET.parse(settings_file).getroot()
        for setting in root.findall('.//setting'):
            setting_id = setting.attrib.get('id')
            if not setting_id:
                continue
            default = setting.attrib.get('default', '')
            value = control.getSetting(setting_id, default)
            redacted_value, redacted = _redact_setting(setting_id, value)
            entries.append({
                'id': setting_id,
                'type': setting.attrib.get('type', ''),
                'default_present': default != '',
                'value': redacted_value,
                'redacted': redacted,
            })
        provider_fallback = _provider_login_fallback_context()
    except Exception as exc:
        return {'error': str(exc)}
    return {'provider_login_fallback': provider_fallback, 'settings': entries}


def _provider_login_fallback_context():
    result = {
        'exists': False,
        'path': _redact_path(os.path.join(control.addonProfilePath, 'provider_logins.json')),
        'providers': {},
    }
    try:
        from resources.lib import provider_logins
        store = provider_logins._load_store()
        result['exists'] = os.path.exists(os.path.join(control.addonProfilePath, 'provider_logins.json'))
        for provider_id in provider_logins.PROVIDERS:
            entry = store.get(provider_id) or {}
            result['providers'][provider_id] = {
                'username_present': bool(entry.get('username')),
                'password_present': bool(entry.get('password')),
            }
    except Exception as exc:
        result['error'] = _short_error(exc)
    return result


def _addon_files_context():
    result = []
    allowed_extensions = ('.py', '.xml', '.json', '.txt')
    skip_dirs = set(['.git', '__pycache__', 'cookies', 'htmlcache', 'backups', 'docs', 'stream-link-auditor'])
    base = os.path.abspath(control.addonPath)
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for filename in files:
            full_path = os.path.join(root, filename)
            if not filename.lower().endswith(allowed_extensions):
                continue
            try:
                rel = os.path.relpath(full_path, base).replace('\\', '/')
                stat = os.stat(full_path)
                result.append({
                    'path': rel,
                    'size': stat.st_size,
                    'modified': int(stat.st_mtime),
                    'sha256': _sha256_file(full_path),
                })
            except Exception:
                pass
    return {'files': sorted(result, key=lambda item: item['path'])}


def _profile_files_context():
    result = []
    base = os.path.abspath(control.addonProfilePath)
    if not os.path.isdir(base):
        return {'files': []}
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d.lower() not in ('cache', 'htmlcache', '__pycache__')]
        for filename in files:
            full_path = os.path.join(root, filename)
            try:
                rel = os.path.relpath(full_path, base).replace('\\', '/')
                stat = os.stat(full_path)
                result.append({
                    'path': rel,
                    'extension': os.path.splitext(filename)[1].lower(),
                    'size': stat.st_size,
                    'modified': int(stat.st_mtime),
                    'content_included': False,
                })
            except Exception:
                pass
    return {'files': sorted(result, key=lambda item: item['path'])}


def _related_profile_files_context():
    return {
        'addons': [
            _addon_profile_context('plugin.video.themoviedb.helper', include_dirs=('players', 'log_library', 'timer_report')),
            _addon_profile_context('plugin.video.xstream', include_dirs=()),
        ]
    }


def _addon_profile_context(addon_id, include_dirs=()):
    base = os.path.abspath(translatePath('special://profile/addon_data/%s/' % addon_id))
    item = {
        'id': addon_id,
        'profile_exists': os.path.isdir(base),
        'profile_path': _redact_path(base),
        'files': [],
        'directories': {},
    }
    for directory in include_dirs:
        item['directories'][directory] = os.path.isdir(os.path.join(base, directory))
    if not os.path.isdir(base):
        return item

    result = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d.lower() not in ('cache', 'htmlcache', '__pycache__')]
        rel_root = os.path.relpath(root, base).replace('\\', '/')
        if include_dirs and rel_root != '.' and not any(
            rel_root == directory or rel_root.startswith(directory.rstrip('/') + '/')
            for directory in include_dirs
        ):
            dirs[:] = []
            continue
        for filename in files:
            full_path = os.path.join(root, filename)
            try:
                rel = os.path.relpath(full_path, base).replace('\\', '/')
                stat = os.stat(full_path)
                result.append({
                    'path': rel,
                    'extension': os.path.splitext(filename)[1].lower(),
                    'size': stat.st_size,
                    'modified': int(stat.st_mtime),
                    'content_included': False,
                })
            except Exception:
                pass
    item['files'] = sorted(result, key=lambda value: value['path'])[:300]
    item['truncated'] = len(result) > 300
    return item


def _recent_xvault_log():
    log_paths = _candidate_log_paths()
    sections = []
    for log_path in log_paths:
        if not os.path.exists(log_path):
            continue
        try:
            content = _read_tail(log_path, MAX_LOG_BYTES)
            filtered = _filter_log_lines(content)
            if filtered:
                sections.append('### %s\n%s' % (_redact_path(log_path), filtered))
        except Exception as exc:
            sections.append('### %s\nLog konnte nicht gelesen werden: %s' % (_redact_path(log_path), str(exc)))
    if not sections:
        return 'Keine xVAULT-bezogenen Logzeilen gefunden.\n'
    return '\n\n'.join(sections) + '\n'


def _candidate_log_paths():
    candidates = []
    for base in ('special://logpath/', 'special://temp/'):
        try:
            translated = translatePath(base)
            candidates.extend([
                os.path.join(translated, 'kodi.log'),
                os.path.join(translated, 'kodi.old.log'),
            ])
        except Exception:
            pass
    unique = []
    seen = set()
    for candidate in candidates:
        norm = os.path.abspath(candidate)
        if norm not in seen:
            seen.add(norm)
            unique.append(norm)
    return unique


def _read_tail(filename, max_bytes):
    with open(filename, 'rb') as handle:
        try:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes), os.SEEK_SET)
        except Exception:
            pass
        return handle.read(max_bytes).decode('utf-8', 'replace')


def _filter_log_lines(content):
    result = []
    include_next = 0
    for line in content.splitlines():
        lower = line.lower()
        include = any(token in lower for token in LOG_TOKENS)
        if include or include_next > 0:
            result.append(_redact_text(line))
            include_next = 8 if ('traceback' in lower or 'exception' in lower or 'error' in lower) else max(include_next - 1, 0)
        elif 'traceback (most recent call last)' in lower:
            result.append(_redact_text(line))
            include_next = 12
    return '\n'.join(result[-MAX_LOG_LINES:])


def _workspace_file_summary(workspace):
    result = []
    for root, dirs, files in os.walk(workspace):
        for filename in files:
            full_path = os.path.join(root, filename)
            rel = os.path.relpath(full_path, workspace).replace('\\', '/')
            try:
                result.append({'path': rel, 'size': os.path.getsize(full_path)})
            except Exception:
                pass
    return sorted(result, key=lambda item: item['path'])


def _show_package_manifest(manifest, zip_size):
    text = [
        'UUID: %s' % manifest.get('support_uuid'),
        'ZIP: %s' % manifest.get('zip_filename'),
        'Groesse: %s' % _format_bytes(zip_size),
        'Upload-Dienst: %s' % manifest.get('provider', {}).get('name', ''),
        'Ablauf: %s' % manifest.get('provider', {}).get('expiry_label', ''),
        '',
        'Enthalten:',
    ]
    text.extend(['- %s' % item for item in manifest.get('contains', [])])
    text.append('')
    text.append('Nicht enthalten:')
    text.extend(['- %s' % item for item in manifest.get('excluded', [])])
    xbmcgui.Dialog().textviewer('xVAULT Supportpaket', '\n'.join(text))


def _confirm_upload(manifest, zip_size):
    provider = manifest.get('provider', {})
    warning = ''
    if zip_size > MAX_UPLOAD_WARNING_BYTES:
        warning = 'Grosses Paket: %s. ' % _format_bytes(zip_size)
    message = '%sSupportpaket zu %s hochladen?[CR]Danach wird eine Kurz-URL erstellt.' % (warning, provider.get('name', ''))
    default_no = getattr(xbmcgui, 'DLG_YESNO_NO_BTN', 0)
    try:
        return xbmcgui.Dialog().yesno(
            SUPPORT_TITLE,
            message,
            nolabel='Abbrechen',
            yeslabel='Hochladen',
            defaultbutton=default_no,
        )
    except TypeError:
        return xbmcgui.Dialog().yesno(
            SUPPORT_TITLE,
            message,
            nolabel='Abbrechen',
            yeslabel='Hochladen',
        )


def _provider_config():
    provider_setting = control.getSetting('support.upload.provider', '0')
    expiry_index = control.getSetting('support.upload.expiry', '1')
    expiry = _expiry_config(expiry_index)
    if str(provider_setting) == '1':
        return {
            'name': SUPPORT_PROVIDER_FILEIO,
            'endpoint': 'https://file.io',
            'expiry_value': expiry['fileio'],
            'expiry_label': expiry['label'],
        }
    if str(provider_setting) == '2':
        return {
            'name': SUPPORT_PROVIDER_0X0,
            'endpoint': 'https://0x0.st',
            'expiry_value': expiry['hours'],
            'expiry_label': expiry['label'],
        }
    return {
        'name': SUPPORT_PROVIDER_FILEBIN,
        'endpoint': 'https://filebin.net/',
        'expiry_label': expiry['label'],
    }


def _expiry_config(index):
    values = {
        '0': {'label': '1 Tag', 'fileio': '1d', 'hours': '24'},
        '1': {'label': '7 Tage', 'fileio': '7d', 'hours': '168'},
        '2': {'label': '14 Tage', 'fileio': '14d', 'hours': '336'},
    }
    return values.get(str(index), values['1'])


def _upload_support_zip(zip_path, zip_name, provider):
    provider = provider or _provider_config()
    if provider['name'] == SUPPORT_PROVIDER_0X0:
        return _upload_0x0(zip_path, zip_name, provider)
    if provider['name'] == SUPPORT_PROVIDER_FILEBIN:
        return _upload_filebin(zip_path, zip_name, provider)
    return _upload_fileio(zip_path, zip_name, provider)


def _upload_fileio(zip_path, zip_name, provider):
    data = {
        'expires': provider.get('expiry_value', '7d'),
        'maxDownloads': '1',
        'autoDelete': 'true',
    }
    response_json = _post_multipart_json(
        provider['endpoint'],
        data,
        zip_path,
        zip_name,
        params={'expires': provider.get('expiry_value', '7d')},
    )
    if not response_json.get('success'):
        raise SupportUploadError(response_json.get('message') or response_json.get('error') or 'Upload abgelehnt')
    link = response_json.get('link')
    if not link:
        raise SupportUploadError('Upload-Antwort enthaelt keinen Link')
    return {
        'provider': provider['name'],
        'link': link,
        'key': response_json.get('key', ''),
        'expires': response_json.get('expires') or response_json.get('expiry') or provider.get('expiry_label', ''),
        'raw': response_json,
    }


def _upload_filebin(zip_path, zip_name, provider):
    support_uuid = zip_name.split('_', 1)[0]
    headers = {
        'User-Agent': SUPPORT_USER_AGENT,
        'Accept': 'application/json',
        'Content-Type': 'application/zip',
        'filename': zip_name,
        'bin': support_uuid,
    }
    if requests:
        with open(zip_path, 'rb') as handle:
            response = requests.post(
                provider['endpoint'],
                data=handle,
                headers=headers,
                timeout=(10, 180),
            )
        if response.status_code < 200 or response.status_code >= 300:
            raise SupportUploadError('HTTP %s: %s' % (response.status_code, response.text[:200]))
    else:
        _urllib_post_raw(provider['endpoint'], headers, zip_path)
    link = 'https://filebin.net/%s/%s' % (support_uuid, zip_name)
    return {
        'provider': provider['name'],
        'link': link,
        'bin': support_uuid,
        'expires': provider.get('expiry_label', ''),
    }


def _add_short_url(upload_result):
    link = upload_result.get('link', '')
    if not link:
        return upload_result
    short_link = _shorten_url(link)
    if short_link:
        upload_result['short_link'] = short_link
        upload_result['short_id'] = _short_url_service_id(short_link)
    else:
        upload_result['short_link'] = ''
        upload_result['short_id'] = ''
        upload_result['shortener_error'] = 'Kurz-URL konnte nicht erstellt werden'
    return upload_result


def _short_url_service_id(short_link):
    value = str(short_link or '').strip().rstrip('/')
    if not value:
        return ''
    try:
        from urllib.parse import urlparse
    except ImportError:
        from urlparse import urlparse
    parsed = urlparse(value)
    path = parsed.path.rstrip('/') if parsed.path else ''
    if path:
        return path.rsplit('/', 1)[-1]
    return value.rsplit('/', 1)[-1]


def _shorten_url(link):
    for service in SHORTENER_SERVICES:
        try:
            short_link = _call_shortener(service, link)
            if _is_http_url(short_link):
                return short_link
            _log('URL shortener failed at %s: invalid response' % service.get('name', ''), xbmc.LOGWARNING)
        except Exception as exc:
            _log('URL shortener failed at %s: %s' % (service.get('name', ''), str(exc)), xbmc.LOGWARNING)
    return ''


def _call_shortener(service, link):
    kind = service.get('kind', '')
    if kind == 'plain_get':
        return _get_text(service['url'], {'url': link}).strip()

    response_json = _get_json(service['url'], {'format': 'json', 'url': link})
    short_link = response_json.get('shorturl', '')
    if short_link:
        return short_link
    error = response_json.get('errormessage') or response_json.get('error') or 'unknown shortener error'
    raise SupportUploadError(error)


def _is_http_url(value):
    try:
        string_types = (basestring,)
    except NameError:
        string_types = (str,)
    return isinstance(value, string_types) and (value.startswith('http://') or value.startswith('https://'))


def _get_json(url, params):
    if requests:
        response = requests.get(
            url,
            params=params,
            headers={'User-Agent': SUPPORT_USER_AGENT, 'Accept': 'application/json'},
            timeout=15,
        )
        text = response.text
        if response.status_code >= 400:
            raise SupportUploadError('HTTP %s: %s' % (response.status_code, text[:200]))
        return response.json()
    return _urllib_get_json(url, params)


def _get_text(url, params):
    if requests:
        response = requests.get(
            url,
            params=params,
            headers={'User-Agent': SUPPORT_USER_AGENT, 'Accept': 'text/plain, */*'},
            timeout=15,
        )
        text = response.text
        if response.status_code >= 400:
            raise SupportUploadError('HTTP %s: %s' % (response.status_code, text[:200]))
        return text
    return _urllib_get_text(url, params)


def _upload_0x0(zip_path, zip_name, provider):
    if requests:
        with open(zip_path, 'rb') as handle:
            response = requests.post(
                provider['endpoint'],
                files={'file': (zip_name, handle, 'application/zip')},
                data={'secret': '', 'expires': provider.get('expiry_value', '168')},
                headers={'User-Agent': SUPPORT_USER_AGENT},
                timeout=(10, 180),
            )
        if response.status_code >= 400:
            raise SupportUploadError('HTTP %s: %s' % (response.status_code, response.text[:200]))
        link = response.text.strip()
        if not link.startswith('http'):
            raise SupportUploadError('Upload-Antwort enthaelt keinen Link')
        return {
            'provider': provider['name'],
            'link': link,
            'management_token': response.headers.get('X-Token', ''),
            'expires': provider.get('expiry_label', ''),
        }
    raise SupportUploadError('requests-Modul fehlt fuer 0x0.st Upload')


def _post_multipart_json(url, fields, file_path, filename, params=None):
    if requests:
        with open(file_path, 'rb') as handle:
            response = requests.post(
                url,
                params=params or {},
                data=fields,
                files={'file': (filename, handle, 'application/zip')},
                headers={'User-Agent': SUPPORT_USER_AGENT},
                timeout=(10, 180),
            )
        text = response.text
        if response.status_code >= 400:
            raise SupportUploadError('HTTP %s: %s' % (response.status_code, text[:200]))
        try:
            return response.json()
        except Exception:
            raise SupportUploadError('Ungueltige Upload-Antwort: %s' % text[:200])
    return _urllib_post_multipart_json(url, fields, file_path, filename, params=params)


def _urllib_post_raw(url, headers, file_path):
    try:
        from urllib.request import Request, urlopen
    except ImportError:
        from urllib2 import Request, urlopen

    with open(file_path, 'rb') as handle:
        request = Request(url, data=handle.read(), headers=headers)
    response = urlopen(request, timeout=180)
    try:
        status = response.getcode()
        if status < 200 or status >= 300:
            raw = response.read().decode('utf-8', 'replace')
            raise SupportUploadError('HTTP %s: %s' % (status, raw[:200]))
    finally:
        try:
            response.close()
        except Exception:
            pass


def _urllib_get_json(url, params):
    try:
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen
    except ImportError:
        from urllib import urlencode
        from urllib2 import Request, urlopen

    separator = '&' if '?' in url else '?'
    request = Request(url + separator + urlencode(params), headers={
        'User-Agent': SUPPORT_USER_AGENT,
        'Accept': 'application/json',
    })
    response = urlopen(request, timeout=15)
    raw = response.read().decode('utf-8', 'replace')
    try:
        return json.loads(raw)
    except Exception:
        raise SupportUploadError('Ungueltige Kurz-URL-Antwort: %s' % raw[:200])


def _urllib_get_text(url, params):
    try:
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen
    except ImportError:
        from urllib import urlencode
        from urllib2 import Request, urlopen

    separator = '&' if '?' in url else '?'
    request = Request(url + separator + urlencode(params), headers={
        'User-Agent': SUPPORT_USER_AGENT,
        'Accept': 'text/plain, */*',
    })
    response = urlopen(request, timeout=15)
    return response.read().decode('utf-8', 'replace')


def _urllib_post_multipart_json(url, fields, file_path, filename, params=None):
    try:
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen
    except ImportError:
        from urllib import urlencode
        from urllib2 import Request, urlopen

    if params:
        separator = '&' if '?' in url else '?'
        url = url + separator + urlencode(params)

    boundary = '----xvault-support-%s' % uuid.uuid4().hex
    body = io.BytesIO()
    for key, value in fields.items():
        body.write(('--%s\r\n' % boundary).encode('utf-8'))
        body.write(('Content-Disposition: form-data; name="%s"\r\n\r\n' % key).encode('utf-8'))
        body.write(str(value).encode('utf-8'))
        body.write(b'\r\n')
    body.write(('--%s\r\n' % boundary).encode('utf-8'))
    body.write(('Content-Disposition: form-data; name="file"; filename="%s"\r\n' % filename).encode('utf-8'))
    body.write(b'Content-Type: application/zip\r\n\r\n')
    with open(file_path, 'rb') as handle:
        body.write(handle.read())
    body.write(b'\r\n')
    body.write(('--%s--\r\n' % boundary).encode('utf-8'))

    request = Request(url, data=body.getvalue(), headers={
        'User-Agent': SUPPORT_USER_AGENT,
        'Content-Type': 'multipart/form-data; boundary=%s' % boundary,
        'Accept': 'application/json',
    })
    response = urlopen(request, timeout=180)
    raw = response.read().decode('utf-8', 'replace')
    try:
        return json.loads(raw)
    except Exception:
        raise SupportUploadError('Ungueltige Upload-Antwort: %s' % raw[:200])


def _store_last_upload(support_uuid, zip_name, zip_size, upload_result):
    payload = {
        'support_uuid': support_uuid,
        'zip_filename': zip_name,
        'zip_size': zip_size,
        'uploaded_at_utc': _utc_timestamp(),
        'local_zip_deleted': True,
        'upload': upload_result,
    }
    path = os.path.join(control.addonProfilePath, 'support_last_upload.json')
    _mkdir(os.path.dirname(path))
    _write_json(path, payload)


def _zip_workspace(workspace, zip_path):
    _delete_file(zip_path)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for root, dirs, files in os.walk(workspace):
            for filename in files:
                full_path = os.path.join(root, filename)
                arcname = os.path.relpath(full_path, workspace).replace('\\', '/')
                archive.write(full_path, arcname)


def _write_json(filename, payload):
    _mkdir(os.path.dirname(filename))
    with io.open(filename, 'w', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
        handle.write('\n')


def _write_text(filename, content):
    _mkdir(os.path.dirname(filename))
    with io.open(filename, 'w', encoding='utf-8') as handle:
        handle.write(content)


def _sha256_file(filename):
    digest = hashlib.sha256()
    with open(filename, 'rb') as handle:
        while True:
            chunk = handle.read(1024 * 128)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _redact_setting(setting_id, value):
    lower_id = setting_id.lower()
    if any(part in lower_id for part in SENSITIVE_SETTING_PARTS):
        return ('<redacted>', True) if value else ('', False)
    if any(part in lower_id for part in PATH_SETTING_PARTS):
        return (_redact_path(value), bool(value))
    return (_redact_text(value), False)


def _redact_text(value):
    text = str(value or '')
    text = re.sub(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', '<redacted-email>', text)
    text = re.sub(r'(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret|cookie)=([^&\s]+)', r'\1=<redacted>', text)
    text = re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._\-]+', r'\1<redacted>', text)
    text = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '<redacted-ip>', text)
    text = _redact_path(text)
    return text


def _redact_path(value):
    text = str(value or '')
    text = re.sub(r'(?i)C:\\Users\\[^\\\/]+', r'C:\\Users\\<user>', text)
    text = re.sub(r'(?i)/home/[^/\s]+', '/home/<user>', text)
    text = re.sub(r'(?i)/Users/[^/\s]+', '/Users/<user>', text)
    return text


def _support_temp_root():
    return os.path.join(translatePath('special://temp/'), 'xvault-support')


def _mkdir(directory):
    if directory and not os.path.exists(directory):
        os.makedirs(directory)


def _remove_tree(directory):
    if directory and os.path.isdir(directory):
        shutil.rmtree(directory, ignore_errors=True)


def _delete_file(filename):
    try:
        if filename and os.path.exists(filename):
            os.remove(filename)
    except Exception:
        pass


def _format_bytes(size):
    value = float(size or 0)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return '%.1f %s' % (value, unit) if unit != 'B' else '%d B' % int(value)
        value /= 1024.0
    return '%d B' % int(size or 0)


def _utc_timestamp():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def _short_error(exc):
    text = str(exc)
    if len(text) > 180:
        return text[:177] + '...'
    return text


def _log(message, level=xbmc.LOGINFO):
    try:
        xbmc.log('[xVAULT.support] %s' % message, level)
    except Exception:
        pass


class SupportUploadError(Exception):
    pass
