import hashlib
import time

from resources.lib import bookmarkDB, control, playcountDB
from resources.lib.sync import device, storage
from resources.lib.sync.api_client import ApiError, Client


FILENAME = 'sync_binge_state.json'


def record_playback(meta, name, year, current_time, total_time, completed=None, push=True):
    try:
        duration = int(total_time or 0)
        position = int(current_time or 0)
    except Exception:
        return False
    if duration <= 0 or position <= 0:
        return False
    watched_percent = round((float(position) / float(duration)) * 100.0, 2)
    if completed is None:
        completed = watched_percent >= 92.0
    item = {
        'schema_version': 1,
        'item_key': item_key(meta, name, year),
        'title': meta.get('title') or name,
        'name': name,
        'year': str(year or meta.get('year') or '0'),
        'season': _maybe_int(meta.get('season')),
        'episode': _maybe_int(meta.get('episode')),
        'position_seconds': position,
        'duration_seconds': duration,
        'watched_percent': watched_percent,
        'completed': bool(completed),
        'provider': 'xvault',
        'updated_at': iso_now(),
        'extra': {
            'mediatype': meta.get('mediatype'),
            'imdb_id': meta.get('imdb_id') or meta.get('imdb'),
            'tmdb_id': meta.get('tmdb_id'),
        },
    }
    save_items([item])
    if push and storage.is_enabled() and storage.is_logged_in():
        push_local(silent=True)
    return True


def item_key(meta, name, year):
    if meta.get('tmdb_id'):
        base = 'tmdb:%s:%s:%s' % (meta.get('tmdb_id'), meta.get('season', ''), meta.get('episode', ''))
    elif meta.get('imdb_id') or meta.get('imdb'):
        base = 'imdb:%s:%s:%s' % (meta.get('imdb_id') or meta.get('imdb'), meta.get('season', ''), meta.get('episode', ''))
    else:
        base = 'name:%s:%s:%s:%s' % (name, year, meta.get('season', ''), meta.get('episode', ''))
    return hashlib.sha256(base.encode('utf-8')).hexdigest()


def load_items():
    data = storage.read_json(FILENAME, {'items': []})
    return data.get('items', [])


def save_items(items):
    merged = _merge_items(load_items(), items)
    storage.write_json(FILENAME, {'schema_version': 1, 'items': list(merged.values())})


def _merge_items(existing_items, incoming_items):
    merged = {}
    aliases = {}
    for item in list(existing_items or []) + list(incoming_items or []):
        if not isinstance(item, dict):
            continue
        keys = _candidate_keys(item)
        if not keys:
            continue
        key = next((aliases.get(candidate) for candidate in keys if aliases.get(candidate)), keys[0])
        current = merged.get(key)
        if current is None or is_newer(item, current):
            merged[key] = item
        for candidate in keys:
            aliases[candidate] = key
    return merged


def _merge_key(item):
    keys = _candidate_keys(item)
    return keys[0] if keys else item.get('item_key')


def _candidate_keys(item):
    extra = item.get('extra') or {}
    mediatype = _item_mediatype(item)
    keys = []
    if mediatype == 'movie':
        imdb_id = str(extra.get('imdb_id') or '')
        if imdb_id:
            keys.append('movie:imdb:%s' % imdb_id)
        tmdb_id = str(extra.get('tmdb_id') or '')
        if tmdb_id:
            keys.append('movie:tmdb:%s' % tmdb_id)
        keys.append('movie:name:%s:%s' % (_norm_title(item.get('title') or item.get('name')), str(item.get('year') or '')))
    if mediatype == 'episode':
        tmdb_id = str(extra.get('tmdb_id') or '')
        season = _maybe_int(item.get('season'))
        episode = _maybe_int(item.get('episode'))
        if tmdb_id and season and episode:
            keys.append('episode:tmdb:%s:%s:%s' % (tmdb_id, season, episode))
        keys.append('episode:name:%s:%s:%s' % (_norm_title(item.get('title')), season or '', episode or ''))
    if item.get('item_key'):
        keys.append('item:%s' % item.get('item_key'))
    return [key for key in keys if key and '::' not in key]


def sync_local_playcounts():
    local_items = collect_local_playcount_items()
    if not local_items:
        return False
    before = _state_signature(load_items())
    save_items(local_items)
    return _state_signature(load_items()) != before


def collect_local_playcount_items():
    try:
        watched = playcountDB.getWatchedItems()
    except Exception as exc:
        log_sync_warning('failed to collect local playcounts: %s' % exc)
        return []
    items = []
    for row in watched.get('movies', []):
        items.append(_movie_row_to_item(row))
    for row in watched.get('episodes', []):
        items.append(_episode_row_to_item(row))
    return [item for item in items if item]


def _movie_row_to_item(row):
    title = row.get('title') or row.get('name') or ''
    name = row.get('name') or title
    if not title or not name:
        return None
    imdb_id = row.get('imdb_id') or ''
    year = _year_from_name(name)
    meta = {'mediatype': 'movie', 'imdb_id': imdb_id}
    return {
        'schema_version': 1,
        'item_key': item_key(meta, name, year),
        'title': title,
        'name': name,
        'year': str(year or '0'),
        'season': None,
        'episode': None,
        'position_seconds': 0,
        'duration_seconds': 0,
        'watched_percent': 100.0,
        'completed': True,
        'provider': 'xvault-playcount',
        'updated_at': iso_now(),
        'extra': {
            'mediatype': 'movie',
            'imdb_id': imdb_id,
            'tmdb_id': '',
        },
    }


def _episode_row_to_item(row):
    title = row.get('title') or ''
    name = row.get('name') or title
    season = _maybe_int(row.get('season'))
    episode = _maybe_int(row.get('episode'))
    if not title or not name or not season or not episode:
        return None
    meta = {'mediatype': 'episode', 'season': season, 'episode': episode}
    return {
        'schema_version': 1,
        'item_key': item_key(meta, name, '0'),
        'title': title,
        'name': name,
        'year': '0',
        'season': season,
        'episode': episode,
        'position_seconds': 0,
        'duration_seconds': 0,
        'watched_percent': 100.0,
        'completed': True,
        'provider': 'xvault-playcount',
        'updated_at': iso_now(),
        'extra': {
            'mediatype': 'episode',
            'imdb_id': '',
            'tmdb_id': '',
        },
    }


def _year_from_name(name):
    text = str(name or '').strip()
    if len(text) >= 6 and text[-1:] == ')' and text[-6:-5] == '(':
        year = text[-5:-1]
        if year.isdigit():
            return year
    return '0'


def _state_signature(items):
    return sorted('%s:%s:%s:%s' % (
        _merge_key(item),
        item.get('completed'),
        item.get('watched_percent'),
        item.get('position_seconds'),
    ) for item in items if isinstance(item, dict))


def combined_items():
    sync_local_playcounts()
    merged = _merge_items([], load_items())
    return list(merged.values())


def push_local(silent=False, client=None, require_login=True):
    if require_login and not storage.is_logged_in():
        if not silent:
            control.infoDialog('Bitte zuerst anmelden.', icon='WARNING')
        return False
    try:
        client = client or Client()
        items = combined_items()
        if not items:
            return False
        client.push_binge_state(items, device.get_device_id())
        storage.update_last_sync(iso_now())
        return True
    except ApiError as exc:
        if not silent:
            control.infoDialog(str(exc), icon='WARNING')
        return False


def pull_remote(apply_bookmarks=True, silent=False, client=None, require_login=True):
    if require_login and not storage.is_logged_in():
        if not silent:
            control.infoDialog('Bitte zuerst anmelden.', icon='WARNING')
        return False
    try:
        client = client or Client()
        data = client.pull_binge_state()
        sync_local_playcounts()
        items = data.get('items', [])
        save_items(items)
        merged_items = combined_items()
        if apply_bookmarks:
            apply_to_bookmarks(merged_items)
        if _state_signature(merged_items) != _state_signature(items):
            client.push_binge_state(merged_items, device.get_device_id())
        storage.update_last_sync(iso_now())
        return True
    except ApiError as exc:
        if not silent:
            control.infoDialog(str(exc), icon='WARNING')
        return False


def apply_to_bookmarks(items):
    for item in items:
        if item.get('completed'):
            apply_to_playcount(item)
            continue
        name = item.get('name') or item.get('title')
        year = str(item.get('year') or '0')
        position = item.get('position_seconds')
        if not name or not position:
            continue
        try:
            bookmarkDB.save_query(_bookmark_id(name, year), str(position), 'bookmarks')
        except Exception as exc:
            log_sync_warning('failed to apply bookmark state: %s' % exc)


def apply_to_playcount(item):
    title = item.get('title') or item.get('name') or ''
    name = item.get('name') or title
    if not title or not name:
        return False
    extra = item.get('extra') or {}
    mediatype = extra.get('mediatype') or ('episode' if item.get('season') and item.get('episode') else 'movie')
    imdb_id = extra.get('imdb_id') or ''
    season = _maybe_int(item.get('season'))
    episode = _maybe_int(item.get('episode'))
    try:
        if mediatype == 'movie' and imdb_id:
            playcountDB.createEntry('movie', title, name, imdb_id, None, None, None, None)
            playcountDB.updatePlaycount('movie', title, name, imdb_id, None, None, None, None, 1)
            return True
        if season and episode:
            playcountDB.createEntry('episode', title, name, imdb_id, None, season, None, episode)
            playcountDB.updatePlaycount('episode', title, name, imdb_id, None, season, None, episode, 1)
            return True
    except Exception as exc:
        log_sync_warning('failed to apply watched state: %s' % exc)
    return False


def is_movie_watched(meta):
    for item in completed_items():
        if _item_mediatype(item) != 'movie':
            continue
        if _same_id(meta, item):
            return True
        if _same_title_year(meta.get('title') or meta.get('originaltitle'), meta.get('year'), item):
            return True
    return False


def is_episode_watched(title, season, episode, meta=None):
    season = _maybe_int(season)
    episode = _maybe_int(episode)
    if not season or not episode:
        return False
    for item in completed_items():
        if _item_mediatype(item) != 'episode':
            continue
        if _maybe_int(item.get('season')) != season or _maybe_int(item.get('episode')) != episode:
            continue
        if meta and _same_id(meta, item):
            return True
        if _norm_title(item.get('title')) == _norm_title(title):
            return True
        if _norm_title(item.get('name')).startswith(_norm_title(title) + ' s%02d' % season):
            return True
    return False


def is_season_watched(title, season, number_of_episodes=None):
    season = _maybe_int(season)
    total = _maybe_int(number_of_episodes)
    if not season or not total:
        return False
    watched = set()
    for item in completed_items():
        if _item_mediatype(item) != 'episode':
            continue
        if _maybe_int(item.get('season')) != season:
            continue
        if _norm_title(item.get('title')) != _norm_title(title):
            continue
        episode = _maybe_int(item.get('episode'))
        if episode:
            watched.add(episode)
    return len(watched) >= total


def completed_items():
    result = []
    for item in load_items():
        if item.get('completed') or float(item.get('watched_percent') or 0) >= 92.0:
            result.append(item)
    return result


def _item_mediatype(item):
    extra = item.get('extra') or {}
    mediatype = extra.get('mediatype')
    if mediatype == 'movie':
        return 'movie'
    if item.get('season') and item.get('episode'):
        return 'episode'
    return mediatype or 'movie'


def _same_id(meta, item):
    extra = item.get('extra') or {}
    meta_tmdb = str(meta.get('tmdb_id') or '')
    item_tmdb = str(extra.get('tmdb_id') or '')
    if meta_tmdb and item_tmdb and meta_tmdb == item_tmdb:
        return True
    meta_imdb = str(meta.get('imdb_id') or meta.get('imdbnumber') or meta.get('imdb') or '')
    item_imdb = str(extra.get('imdb_id') or '')
    return bool(meta_imdb and item_imdb and meta_imdb == item_imdb)


def _same_title_year(title, year, item):
    if _norm_title(title) != _norm_title(item.get('title')):
        return False
    item_year = str(item.get('year') or '')
    return not year or not item_year or str(year) == item_year


def _norm_title(value):
    return str(value or '').strip().lower()


def log_sync_warning(message):
    try:
        from resources.lib import log_utils
        log_utils.log('xVAULT sync: %s' % message, log_utils.LOGWARNING)
    except Exception:
        pass


def _bookmark_id(name, year):
    digest = hashlib.md5()
    for value in (name, year):
        for char in str(value):
            digest.update(char.encode('utf-8'))
    return digest.hexdigest()


def is_newer(candidate, current):
    if current.get('completed') and not candidate.get('completed'):
        return False
    if candidate.get('completed') and not current.get('completed'):
        return True
    if candidate.get('completed') and current.get('completed'):
        if _is_playcount_import(candidate) and not _is_playcount_import(current):
            return False
        if _is_playcount_import(current) and not _is_playcount_import(candidate):
            return True
    c_time = candidate.get('updated_at') or ''
    old_time = current.get('updated_at') or ''
    if c_time != old_time:
        return c_time > old_time
    return int(candidate.get('position_seconds') or 0) >= int(current.get('position_seconds') or 0)


def _is_playcount_import(item):
    return item.get('provider') == 'xvault-playcount'


def _maybe_int(value):
    try:
        return int(value)
    except Exception:
        return None


def iso_now():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')
