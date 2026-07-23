import hashlib
import os
import time
import xml.etree.ElementTree as ET

import xbmcvfs

from resources.lib import control, log_utils
from resources.lib.sync import device, storage
from resources.lib.sync.api_client import ApiError, Client


STATE_FILE = 'sync_favorites_state.json'
REMOTE_PULL_INTERVAL = 45


def favourites_path():
    return control.translatePath('special://profile/favourites.xml')


def read_favourites():
    path = favourites_path()
    if not os.path.exists(path):
        return ''
    with open(path, 'r', encoding='utf-8-sig') as handle:
        return handle.read()


def favorites_hash(raw_xml=None):
    raw = read_favourites() if raw_xml is None else raw_xml
    normalized = raw.replace('\r\n', '\n').strip().encode('utf-8')
    return hashlib.sha256(normalized).hexdigest()


def collect(raw_xml=None, deleted_keys=None, base_keys=None):
    raw = read_favourites() if raw_xml is None else raw_xml
    items = []
    if raw.strip():
        try:
            for index, item in enumerate(_parse_entries(raw), 1):
                path_text = item['path']
                items.append({
                    'order': index,
                    'label': item['label'],
                    'thumb': item['thumb'],
                    'path': path_text,
                    'type': 'video' if _is_xvault_path(path_text) else 'unknown',
                })
        except Exception as exc:
            log_utils.log('xVAULT sync: failed to parse favourites.xml: %s' % exc, log_utils.LOGWARNING)
    digest = favorites_hash(raw)
    payload = {
        'schema_version': 1,
        'source': 'kodi_favourites',
        'addon': control.addonId,
        'device_id': device.get_device_id(),
        'updated_at': iso_now(),
        'favorites_hash': digest,
        'raw_xml': raw,
        'items': items,
    }
    if deleted_keys:
        payload['deleted_keys'] = sorted(set(deleted_keys))
    if base_keys is not None:
        payload['base_keys'] = list(base_keys)
    return payload


def _is_xvault_path(path_text):
    return 'plugin.video.xvault' in path_text or 'plugin.video.xvaultalpha' in path_text


def check_and_push_if_changed(silent=True, client=None, require_enabled=True, force=False):
    if require_enabled and (not storage.is_enabled() or not storage.is_logged_in()):
        return False
    if not require_enabled and client is None and not storage.is_logged_in():
        return False
    client = client or Client()
    local_raw = read_favourites()
    local_hash = favorites_hash(local_raw)

    server_raw = ''
    server_available = False
    try:
        data = client.pull_favorites()
        favorites = data.get('favorites') or {}
        server_raw = _payload_raw_xml(favorites)
        server_available = True
    except ApiError as exc:
        if exc.code != 'NO_BACKUP_FOUND':
            if not silent:
                control.infoDialog(str(exc), icon='WARNING')
            return False

    merged_raw, deleted_keys = merge_favorites_with_deleted(local_raw, server_raw, deletion_aware=True)
    merged_hash = favorites_hash(merged_raw)
    local_needs_update = merged_hash != local_hash

    if local_needs_update:
        write_favourites(merged_raw, backup=True)

    server_hash = favorites_hash(server_raw) if server_available else ''
    if not force and not local_needs_update and merged_hash == storage.get_setting(storage.LAST_FAVORITES_HASH) and (not server_available or merged_hash == server_hash):
        return False

    if server_available and merged_hash == server_hash:
        mark_synced(merged_raw)
        storage.update_last_sync(iso_now())
        storage.set_status('Angemeldet als %s' % storage.email())
        return local_needs_update

    try:
        client.push_favorites(collect(merged_raw, deleted_keys=deleted_keys))
        mark_synced(merged_raw)
        storage.update_last_sync(iso_now())
        storage.set_status('Angemeldet als %s' % storage.email())
        if not silent:
            control.infoDialog('Favoriten wurden gesichert.', icon='INFO')
        return True
    except ApiError as exc:
        if not silent:
            control.infoDialog(str(exc), icon='WARNING')
        return False


def restore_from_server(mode='ask', client=None, require_login=True):
    if require_login and not storage.is_logged_in():
        control.infoDialog('Bitte zuerst anmelden.', icon='WARNING')
        return False
    try:
        data = (client or Client()).pull_favorites()
    except ApiError as exc:
        control.infoDialog(str(exc), icon='WARNING')
        return False
    favorites = data.get('favorites') or {}
    if not favorites:
        control.infoDialog('Keine Serverdaten gefunden.', icon='WARNING')
        return False

    if mode == 'ask':
        choice = control.dialog.contextmenu(['Serverstand überschreibt lokalen Stand', 'Serverstand mit lokalem Stand zusammenführen'])
        if choice < 0:
            return False
        mode = 'overwrite' if choice == 0 else 'merge'

    if not control.yesnoDialog('Lokale Favoriten werden geändert.', 'Vorher wird automatisch eine Sicherung erstellt.', 'Fortfahren?', yeslabel='Ja', nolabel='Nein'):
        return False

    raw_xml = _payload_raw_xml(favorites)
    if mode == 'merge':
        raw_xml = merge_favorites(read_favourites(), raw_xml, deletion_aware=False)
    if not raw_xml.strip():
        raw_xml = '<favourites />\n'

    write_favourites(raw_xml, backup=True)
    mark_synced(raw_xml)
    storage.update_last_sync(iso_now())
    control.infoDialog('Favoriten wurden wiederhergestellt. Bitte Kodi ggf. neu starten.', icon='INFO', time=6000)
    return True


def merge_favorites(local_xml, server_xml, deletion_aware=False):
    merged_raw, _deleted_keys = merge_favorites_with_deleted(local_xml, server_xml, deletion_aware=deletion_aware)
    return merged_raw


def merge_favorites_with_deleted(local_xml, server_xml, deletion_aware=False):
    local_entries = _dedupe_entries(_parse_entries(local_xml))
    server_entries = _dedupe_entries(_parse_entries(server_xml))
    removed = set()
    if deletion_aware:
        last_keys = set(load_state().get('keys') or [])
        if last_keys:
            local_keys = set(_entry_key(item) for item in local_entries)
            server_keys = set(_entry_key(item) for item in server_entries)
            removed = (last_keys - local_keys) | (last_keys - server_keys)
    return _build_xml(_combine_entries(local_entries, server_entries, removed)), removed


def _parse_entries(raw):
    if not raw or not raw.strip():
        return []
    try:
        root = ET.fromstring(raw.encode('utf-8'))
    except Exception:
        return []
    result = []
    for node in root.findall('favourite'):
        result.append({
            'label': node.attrib.get('name', ''),
            'thumb': node.attrib.get('thumb', ''),
            'path': (node.text or '').strip(),
        })
    return result


def _payload_raw_xml(payload):
    raw = payload.get('raw_xml', '') if isinstance(payload, dict) else ''
    if raw:
        return raw
    items = payload.get('items', []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return ''
    entries = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entries.append({
            'label': item.get('label', ''),
            'thumb': item.get('thumb', ''),
            'path': item.get('path', ''),
        })
    return _build_xml(_dedupe_entries(entries))


def _entry_key(item):
    return (item.get('path') or item.get('label') or '').strip()


def _dedupe_entries(entries):
    result = []
    seen = set()
    for item in entries:
        key = _entry_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _combine_entries(local_entries, server_entries, removed=None):
    removed = removed or set()
    entries = []
    seen = set()
    for item in list(local_entries) + list(server_entries):
        key = _entry_key(item)
        if not key or key in removed or key in seen:
            continue
        seen.add(key)
        entries.append(item)
    return entries


def _build_xml(entries):
    root = ET.Element('favourites')
    for item in entries:
        node = ET.SubElement(root, 'favourite')
        if item.get('label'):
            node.set('name', item['label'])
        if item.get('thumb'):
            node.set('thumb', item['thumb'])
        node.text = item.get('path', '')
    return ET.tostring(root, encoding='unicode') + '\n'


def write_favourites(raw_xml, backup=False):
    if not raw_xml.strip():
        raw_xml = '<favourites />\n'
    if backup:
        backup_current()
    path = favourites_path()
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(raw_xml)


def load_state():
    data = storage.read_json(STATE_FILE, {})
    return data if isinstance(data, dict) else {}


def mark_synced(raw_xml):
    entries = _dedupe_entries(_parse_entries(raw_xml))
    keys = [_entry_key(item) for item in entries if _entry_key(item)]
    digest = favorites_hash(raw_xml)
    storage.write_json(STATE_FILE, {
        'favorites_hash': digest,
        'keys': keys,
        'updated_at': iso_now(),
    })
    storage.set_setting(storage.LAST_FAVORITES_HASH, digest)


def has_local_changes():
    if not storage.is_enabled() or not storage.is_logged_in():
        return False
    return favorites_hash() != storage.get_setting(storage.LAST_FAVORITES_HASH)


def monitor_changes(interval=5):
    try:
        import xbmc
        monitor = xbmc.Monitor()
        next_remote_pull = 0
        while not monitor.abortRequested():
            if monitor.waitForAbort(interval):
                break
            try:
                from resources.lib import telemetry
                telemetry.heartbeat()
            except Exception:
                pass
            now = time.time()
            if has_local_changes():
                check_and_push_if_changed(silent=True)
                next_remote_pull = now + REMOTE_PULL_INTERVAL
            elif now >= next_remote_pull:
                check_and_push_if_changed(silent=True)
                if storage.is_enabled() and storage.is_logged_in():
                    try:
                        from resources.lib.sync import binge_sync
                        binge_sync.pull_remote(apply_bookmarks=True, silent=True)
                    except Exception as exc:
                        log_utils.log('xVAULT sync: binge remote monitor failed: %s' % exc, log_utils.LOGWARNING)
                next_remote_pull = now + REMOTE_PULL_INTERVAL
    except Exception as exc:
        log_utils.log('xVAULT sync: favorites monitor stopped: %s' % exc, log_utils.LOGWARNING)


def backup_current():
    raw = read_favourites()
    if not raw:
        return
    backup = favourites_path() + '.xvault-backup-%s' % time.strftime('%Y%m%d%H%M%S')
    with open(backup, 'w', encoding='utf-8') as handle:
        handle.write(raw)


def iso_now():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')
