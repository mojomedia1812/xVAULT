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
    merged = {item.get('item_key'): item for item in load_items() if item.get('item_key')}
    for item in items:
        key = item.get('item_key')
        if not key:
            continue
        current = merged.get(key)
        if current is None or is_newer(item, current):
            merged[key] = item
    storage.write_json(FILENAME, {'schema_version': 1, 'items': list(merged.values())})


def push_local(silent=False, client=None, require_login=True):
    if require_login and not storage.is_logged_in():
        if not silent:
            control.infoDialog('Bitte zuerst anmelden.', icon='WARNING')
        return False
    try:
        items = load_items()
        if not items:
            return False
        (client or Client()).push_binge_state(items, device.get_device_id())
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
        data = (client or Client()).pull_binge_state()
        items = data.get('items', [])
        save_items(items)
        if apply_bookmarks:
            apply_to_bookmarks(items)
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
        bookmarkDB.save_query(_bookmark_id(name, year), str(position), 'bookmarks')


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
    c_time = candidate.get('updated_at') or ''
    old_time = current.get('updated_at') or ''
    if c_time != old_time:
        return c_time > old_time
    if current.get('completed') and not candidate.get('completed'):
        return False
    return int(candidate.get('position_seconds') or 0) >= int(current.get('position_seconds') or 0)


def _maybe_int(value):
    try:
        return int(value)
    except Exception:
        return None


def iso_now():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')
