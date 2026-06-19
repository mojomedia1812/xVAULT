# edit 2026-06-19

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import control

try:
    from urllib.parse import parse_qsl, urlencode, urlsplit
    from urllib.request import Request, urlopen
except ImportError:
    from urlparse import parse_qsl, urlsplit
    from urllib import urlencode
    from urllib2 import Request, urlopen


VAVOO_CHANNELS_URL = 'https://vavoo.to/channels'
HUHU_CHANNELS_URL = 'https://huhu.to/channels'
DATA_DIR = os.path.join(control.addonPath, 'resources', 'data')
AUDITOR_FILE = os.path.join(DATA_DIR, 'stream-link-auditor.json')
CATEGORIES_FILE = os.path.join(DATA_DIR, 'vavoo_channels_categorized.json')
V_CHANNELS_FILE = os.path.join(control.addonProfilePath, 'v-channels.json')
H_CHANNELS_FILE = os.path.join(control.addonProfilePath, 'h-channels.json')
CHANNELS_FILE = os.path.join(control.addonProfilePath, 'channels.json')
STATE_FILE = os.path.join(control.addonProfilePath, 'channels-state.json')
CACHE_SECONDS = 30 * 60
COUNTRY = 'Germany'


def list_categories(force_refresh=False):
    catalog = load_catalog(force_refresh=force_refresh)
    channels = catalog.get('channels', [])
    grouped = _group_by_category(channels)
    handle = _handle()

    refresh = _item('Senderlisten aktualisieren', {
        'plot': 'VAVOO- und HUHU-Senderlisten neu laden und channels.json aktualisieren.',
        'title': 'Senderlisten aktualisieren',
    })
    refresh.setProperty('IsPlayable', 'false')
    control.addItem(handle, _addon_url({'action': 'liveTVRefresh'}), refresh, False)

    for category in sorted(grouped, key=lambda value: _sort_label(value)):
        entries = grouped[category]
        item = _item(category, {
            'plot': '%s Sender' % len(entries),
            'title': category,
        })
        item.setIsFolder(True)
        control.addItem(handle, _addon_url({'action': 'liveTVCategory', 'category': category}), item, True)

    _end(handle, 'LiveTV')


def refresh_catalog():
    catalog = load_catalog(force_refresh=True)
    count = len(catalog.get('channels', []))
    control.infoDialog('LiveTV-Senderliste aktualisiert: %s Sender' % count, icon='INFO', time=4000)
    xbmc.executebuiltin('Container.Refresh')


def list_channels(category):
    catalog = load_catalog()
    channels = [
        channel for channel in catalog.get('channels', [])
        if channel.get('category') == category
    ]
    handle = _handle()

    for channel in sorted(channels, key=lambda value: _sort_label(value.get('name'))):
        item = _item(channel.get('name') or 'LiveTV', {
            'plot': _channel_plot(channel),
            'title': channel.get('name') or 'LiveTV',
        })
        item.setProperty('IsPlayable', 'true')
        url = _addon_url({'action': 'liveTVPlay', 'id': str(channel.get('id'))})
        try:
            item.setPath(url)
        except Exception:
            pass
        control.addItem(handle, url, item, False)

    control.sortLabel(handle)
    _end(handle, category or 'LiveTV')


def play_channel(channel_id):
    catalog = load_catalog()
    channel = _channel_by_id(catalog.get('channels', []), channel_id)
    if not channel:
        control.infoDialog('LiveTV-Sender nicht gefunden', icon='WARNING', time=4000)
        return

    url = channel.get('stream_url')
    if not url:
        control.infoDialog('Kein Stream-Link fuer diesen Sender gefunden', icon='WARNING', time=4000)
        return
    url, headers = _resolve_stream_url(channel)
    if not url:
        control.infoDialog('LiveTV-Stream konnte nicht aufgeloest werden', icon='WARNING', time=4000)
        return

    item = control.item(channel.get('name') or 'LiveTV', offscreen=True)
    item.setProperty('IsPlayable', 'true')
    item.setInfo('video', {
        'title': channel.get('name') or 'LiveTV',
        'plot': _channel_plot(channel),
    })
    if _is_hls(url):
        _configure_hls(item)
    if headers:
        if _is_hls(url):
            item.setProperty('inputstream.adaptive.common_headers', headers)
            item.setProperty('inputstream.adaptive.stream_headers', headers)
        else:
            url += '|%s' % headers
    item.setPath(url)
    control.resolveUrl(_handle(), True, item)


def load_catalog(force_refresh=False):
    _ensure_profile_dir()
    if not force_refresh and _fresh_catalog_exists():
        merged = _read_json(CHANNELS_FILE, [])
        if merged:
            return {'channels': build_playable_channels(merged), 'state': _read_json(STATE_FILE, {})}

    v_channels, h_channels = _fetch_sources()
    if v_channels is None or h_channels is None:
        cached_merged = _read_json(CHANNELS_FILE, [])
        if cached_merged:
            control.infoDialog('LiveTV nutzt die gespeicherte Senderliste.', icon='WARNING', time=4000)
            return {'channels': build_playable_channels(cached_merged), 'state': _read_json(STATE_FILE, {})}
        control.infoDialog('LiveTV-Senderlisten konnten nicht geladen werden.', icon='ERROR', time=5000)
        return {'channels': [], 'state': {}}

    merged = merge_channel_lists(v_channels, h_channels)
    channels = build_playable_channels(merged)
    _write_json(CHANNELS_FILE, merged)
    state = {
        'updated_at': int(time.time()),
        'vavoo_count': len(v_channels),
        'huhu_count': len(h_channels),
        'merged_count': len(merged),
        'playable_count': len(channels),
    }
    _write_json(STATE_FILE, state)
    return {'channels': channels, 'state': state}


def merge_channel_lists(v_channels, h_channels):
    merged = []
    seen_ids = set()

    for channel in _german_channels(v_channels):
        channel_id = _channel_id(channel)
        if channel_id in seen_ids:
            continue
        item = dict(channel)
        item['source'] = 'vavoo'
        merged.append(item)
        seen_ids.add(channel_id)

    for channel in _german_channels(h_channels):
        channel_id = _channel_id(channel)
        if channel_id in seen_ids:
            continue
        item = dict(channel)
        item['source'] = 'huhu'
        merged.append(item)
        seen_ids.add(channel_id)

    return merged


def build_playable_channels(merged_channels):
    auditor = _auditor_index()
    categories = _category_index()
    result = []

    for channel in merged_channels:
        channel_id = _channel_id(channel)
        audit = auditor['by_id'].get(channel_id)
        if not audit:
            audit = auditor['by_name'].get(_normalize_name(channel.get('name')))
        if not audit:
            continue
        if audit.get('channel_country') != COUNTRY:
            continue

        categorized = categories.get(channel_id, {})
        category = categorized.get('category') or 'Sonstige'
        name = _display_name(channel.get('name') or audit.get('channel_name'))
        result.append({
            'id': channel_id,
            'name': name,
            'country': COUNTRY,
            'category': category,
            'source': channel.get('source') or 'vavoo',
            'stream_url': audit.get('url'),
            'catalog_name': channel.get('name') or '',
            'auditor_name': audit.get('channel_name') or '',
            'position': channel.get('p'),
        })

    result.sort(key=lambda value: (_sort_label(value.get('category')), _sort_label(value.get('name'))))
    return result


def _fetch_sources():
    tasks = {
        'v': (VAVOO_CHANNELS_URL, V_CHANNELS_FILE),
        'h': (HUHU_CHANNELS_URL, H_CHANNELS_FILE),
    }
    result = {'v': None, 'h': None}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = dict(
            (executor.submit(_download_json, url, path), key)
            for key, (url, path) in tasks.items()
        )
        for future in as_completed(futures):
            key = futures[future]
            try:
                result[key] = future.result()
            except Exception:
                result[key] = None
    return result['v'], result['h']


def _download_json(url, output_path):
    request = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 Kodi xVAULT/%s' % control.addonVersion,
        'Accept': 'application/json,text/plain,*/*',
    })
    response = urlopen(request, timeout=20)
    raw = response.read()
    try:
        response.close()
    except Exception:
        pass
    text = raw.decode('utf-8-sig')
    data = json.loads(text)
    _write_json(output_path, data)
    return data


def _auditor_index():
    data = _read_json(AUDITOR_FILE, {})
    entries = data.get('results', []) if isinstance(data, dict) else data
    by_id = {}
    by_name = {}
    for entry in entries:
        if entry.get('channel_country') != COUNTRY:
            continue
        url = entry.get('url') or ''
        channel_id = _id_from_url(url)
        if not channel_id:
            continue
        by_id.setdefault(channel_id, entry)
        normalized = _normalize_name(entry.get('channel_name'))
        if normalized:
            by_name.setdefault(normalized, entry)
    return {'by_id': by_id, 'by_name': by_name}


def _category_index():
    data = _read_json(CATEGORIES_FILE, [])
    result = {}
    for item in data:
        if str(item.get('country', '')).lower() != COUNTRY.lower():
            continue
        channel_id = _channel_id(item)
        if not channel_id:
            continue
        result[channel_id] = item
    return result


def _german_channels(channels):
    return [
        channel for channel in channels
        if str(channel.get('country', '')).lower() == COUNTRY.lower()
    ]


def _channel_by_id(channels, channel_id):
    try:
        wanted = int(channel_id)
    except Exception:
        wanted = channel_id
    for channel in channels:
        if channel.get('id') == wanted:
            return channel
    return None


def _channel_id(channel):
    try:
        return int(channel.get('id'))
    except Exception:
        return None


def _id_from_url(url):
    match = re.search(r'/play/(\d+)/', url or '')
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _display_name(name):
    value = str(name or '').strip()
    value = re.sub(r'\s*\|\w+\s*$', '', value).strip()
    return value or 'LiveTV'


def _normalize_name(name):
    value = _display_name(name).upper()
    value = re.sub(r'\s*\(\d+\)\s*$', '', value).strip()
    value = re.sub(r'\s*\[[^\]]*\]\s*', ' ', value)
    value = re.sub(r'[^A-Z0-9]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def _sort_label(value):
    return _normalize_name(value)


def _group_by_category(channels):
    grouped = {}
    for channel in channels:
        category = channel.get('category') or 'Sonstige'
        grouped.setdefault(category, []).append(channel)
    return grouped


def _channel_plot(channel):
    parts = [
        'Kategorie: %s' % (channel.get('category') or 'Sonstige'),
        'Quelle: %s' % (channel.get('source') or 'unbekannt'),
        'ID: %s' % channel.get('id'),
    ]
    if channel.get('auditor_name') and channel.get('auditor_name') != channel.get('name'):
        parts.append('Stream: %s' % channel.get('auditor_name'))
    return '\n'.join(parts)


def _resolve_stream_url(channel):
    url = channel.get('stream_url')
    if 'vavoo.to/play/' not in (url or ''):
        return url, None
    resolve_url = _vavoo_catalog_url(channel) or _vavoo_resolve_url(url)
    try:
        _suppress_insecure_request_warning()
        from resources.lib.vavoo import vjlive

        resolved, headers = vjlive.resolve_link(resolve_url)
        if resolved:
            return resolved, headers
    except Exception:
        pass
    return None, None


def _suppress_insecure_request_warning():
    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass


def _vavoo_catalog_url(channel):
    channel_id = str(channel.get('id') or '')
    if not channel_id:
        return None
    try:
        from resources.lib.vavoo import utils as vavoo_utils

        headers = {
            'user-agent': 'MediaHubMX/2',
            'accept': 'application/json',
            'content-type': 'application/json; charset=utf-8',
            'accept-encoding': 'gzip',
            'mediahubmx-signature': vavoo_utils.getAuthSignature(),
        }
        payload = {
            'language': 'de',
            'region': 'AT',
            'catalogId': 'iptv',
            'id': 'iptv',
            'adult': False,
            'search': _catalog_search_name(channel.get('name')),
            'sort': 'name',
            'filter': {'group': COUNTRY},
            'cursor': 0,
            'clientVersion': '3.1.0',
        }
        response = vavoo_utils.request_json(
            'POST',
            'https://vavoo.to/mediahubmx-catalog.json',
            json=payload,
            headers=headers,
            timeout=12,
            retries=1,
        )
        for item in response.get('items', []):
            item_url = item.get('url') or ''
            if '/play/%s' % channel_id in item_url:
                return item_url
    except Exception:
        pass
    return None


def _catalog_search_name(name):
    value = _display_name(name)
    value = re.sub(r'\s*\(\d+\)\s*$', '', value).strip()
    value = re.sub(r'\s*\[[^\]]*\]\s*', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def _vavoo_resolve_url(url):
    channel_id = _id_from_url(url)
    if channel_id:
        return 'https://vavoo.to/play/%s' % channel_id
    return url


def _item(label, info):
    icon = control.addonPoster()
    item = control.item(label, offscreen=True)
    item.setArt({'icon': icon, 'thumb': icon, 'poster': icon})
    item.setInfo('video', info)
    return item


def _is_hls(url):
    return '.m3u8' in (url or '').lower()


def _configure_hls(item):
    try:
        kodiver = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
    except Exception:
        kodiver = 20
    item.setProperty('inputstream', 'inputstream.adaptive')
    if kodiver < 21:
        item.setProperty('inputstream.adaptive.manifest_type', 'hls')
    item.setMimeType('application/vnd.apple.mpegurl')
    item.setContentLookup(False)


def _fresh_catalog_exists():
    if not os.path.exists(CHANNELS_FILE) or not os.path.exists(STATE_FILE):
        return False
    state = _read_json(STATE_FILE, {})
    updated_at = int(state.get('updated_at') or 0)
    return updated_at and int(time.time()) - updated_at < CACHE_SECONDS


def _read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8-sig') as handle:
            return json.load(handle)
    except TypeError:
        try:
            with open(path, 'r') as handle:
                raw = handle.read()
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8-sig')
            return json.loads(raw)
        except Exception:
            return default
    except Exception:
        return default


def _write_json(path, data):
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    temp_path = path + '.tmp'
    with open(temp_path, 'w', encoding='utf-8', newline='\n') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(temp_path, path)


def _ensure_profile_dir():
    if control.addonProfilePath and not os.path.exists(control.addonProfilePath):
        os.makedirs(control.addonProfilePath)


def _addon_url(params):
    return '%s?%s' % (sys.argv[0], urlencode(params))


def _handle():
    return int(sys.argv[1]) if len(sys.argv) > 1 else -1


def _end(handle, category):
    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.setPluginCategory(handle, control.addonName + ' / ' + category)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
