import hashlib
import os
import time
import xml.etree.ElementTree as ET

import xbmcvfs

from resources.lib import control, log_utils
from resources.lib.sync import device, storage
from resources.lib.sync.api_client import ApiError, Client


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


def collect():
    raw = read_favourites()
    items = []
    if raw.strip():
        try:
            root = ET.fromstring(raw.encode('utf-8'))
            for index, node in enumerate(root.findall('favourite'), 1):
                path_text = (node.text or '').strip()
                items.append({
                    'order': index,
                    'label': node.attrib.get('name', ''),
                    'thumb': node.attrib.get('thumb', ''),
                    'path': path_text,
                    'type': 'video' if 'plugin.video.xvault' in path_text else 'unknown',
                })
        except Exception as exc:
            log_utils.log('xVAULT sync: failed to parse favourites.xml: %s' % exc, log_utils.LOGWARNING)
    digest = favorites_hash(raw)
    return {
        'schema_version': 1,
        'source': 'kodi_favourites',
        'addon': control.addonId,
        'device_id': device.get_device_id(),
        'updated_at': iso_now(),
        'favorites_hash': digest,
        'raw_xml': raw,
        'items': items,
    }


def check_and_push_if_changed(silent=True):
    if not storage.is_enabled() or not storage.is_logged_in():
        return False
    data = collect()
    if data['favorites_hash'] == storage.get_setting(storage.LAST_FAVORITES_HASH):
        return False
    try:
        Client().push_favorites(data)
        storage.set_setting(storage.LAST_FAVORITES_HASH, data['favorites_hash'])
        storage.update_last_sync(iso_now())
        storage.set_status('Angemeldet als %s' % storage.email())
        if not silent:
            control.infoDialog('Favoriten wurden gesichert.', icon='INFO')
        return True
    except ApiError as exc:
        if not silent:
            control.infoDialog(str(exc), icon='WARNING')
        return False


def restore_from_server(mode='ask'):
    if not storage.is_logged_in():
        control.infoDialog('Bitte zuerst anmelden.', icon='WARNING')
        return False
    try:
        data = Client().pull_favorites()
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

    raw_xml = favorites.get('raw_xml', '')
    if mode == 'merge':
        raw_xml = merge_favorites(read_favourites(), raw_xml)
    if not raw_xml.strip():
        raw_xml = '<favourites />\n'

    backup_current()
    path = favourites_path()
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(raw_xml)
    storage.set_setting(storage.LAST_FAVORITES_HASH, favorites_hash(raw_xml))
    storage.update_last_sync(iso_now())
    control.infoDialog('Favoriten wurden wiederhergestellt. Bitte Kodi ggf. neu starten.', icon='INFO', time=6000)
    return True


def merge_favorites(local_xml, server_xml):
    entries = []
    seen = set()
    for raw in (server_xml, local_xml):
        for item in _parse_entries(raw):
            key = item['path'] or item['label']
            if key in seen:
                continue
            seen.add(key)
            entries.append(item)
    root = ET.Element('favourites')
    for item in entries:
        node = ET.SubElement(root, 'favourite')
        if item['label']:
            node.set('name', item['label'])
        if item['thumb']:
            node.set('thumb', item['thumb'])
        node.text = item['path']
    return ET.tostring(root, encoding='unicode') + '\n'


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


def backup_current():
    raw = read_favourites()
    if not raw:
        return
    backup = favourites_path() + '.xvault-backup-%s' % time.strftime('%Y%m%d%H%M%S')
    with open(backup, 'w', encoding='utf-8') as handle:
        handle.write(raw)


def iso_now():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')
