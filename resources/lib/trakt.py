import base64
import json
import sys
import time

try:
    import requests
except Exception:
    requests = None

from resources.lib import control, log_utils, playcountDB
from resources.lib.sync import binge_sync, storage


BASE_URL = 'https://api.trakt.tv'
CACHE_FILE = 'trakt_cache.json'
AUTH_FILE = 'trakt_auth.json'
TOKEN_SKEW = 60
MAX_LIST_PAGES = 5
TRAKT_CLIENT_ID = 'b64:MTdhNTQzNGUxNjRjMDViZDliNDU4NzEzOTBlNDg4YmE2OGNiZjViNDZlYzkzMjk0ZjJjODYzMzIwOGJhYWQ2MQ=='
TRAKT_CLIENT_SECRET = 'b64:ODZlOThkMjFjOGZmOTUxNTczYzA2YzgxNmE4MjVmMDk3N2UyNDM5NjE2NTIxNjUxNzdlMzE3NWNjZGY5NWY2Mw=='


class TraktError(Exception):
    def __init__(self, message, status=None):
        Exception.__init__(self, message)
        self.status = status


def dispatch(action, params=None):
    params = params or {}
    if action == 'traktAuthorize':
        authorize()
        return False
    elif action == 'traktLogout':
        logout()
        return False
    elif action == 'traktStatus':
        show_status()
        return False
    elif action == 'traktSyncNow':
        sync_watched(silent=False)
        return False
    elif action == 'traktImportWatched':
        import_watched(silent=False)
        return False
    elif action == 'traktExportWatched':
        export_watched(silent=False)
        return False
    elif action == 'traktList':
        return show_media_list(params)
    elif action == 'traktRate':
        rate_from_params(params)
        return False
    return False


def get_aliases(item_id, mediatype):
    if not item_id or not _bool('trakt.aliases.enabled', 'true'):
        return [], ''
    if not _client_id():
        return [], ''

    kind = _trakt_kind(mediatype)
    if kind not in ('movies', 'shows'):
        return [], ''

    cache_key = 'aliases:%s:%s' % (kind, item_id)
    cached = _cache_get(cache_key, _cache_ttl())
    if cached:
        return cached.get('aliases', []), cached.get('localtitle', '')

    try:
        data, _headers = _request('GET', '/%s/%s/aliases' % (kind, item_id), timeout=_alias_timeout())
        aliases = [entry.get('title') for entry in data or [] if entry.get('country') in ('de', 'us', 'en', 'at', '') and entry.get('title')]
        local_titles = [entry.get('title') for entry in data or [] if entry.get('country') == 'de' and entry.get('title')]
        result = {
            'aliases': _unique(aliases),
            'localtitle': local_titles[0] if local_titles else '',
        }
        _cache_set(cache_key, result)
        return result['aliases'], result['localtitle']
    except Exception as exc:
        _log('alias lookup failed for %s/%s: %s' % (kind, item_id, exc), log_utils.LOGWARNING)
        return [], ''


def get_external_ids(item_id, mediatype):
    if not item_id or not _client_id():
        return {}
    kind = _trakt_kind(mediatype)
    if kind not in ('movies', 'shows'):
        return {}
    cache_key = 'ids:%s:%s' % (kind, item_id)
    cached = _cache_get(cache_key, _cache_ttl())
    if cached:
        return cached
    try:
        data, _headers = _request('GET', '/%s/%s' % (kind, item_id), params={'extended': 'full'}, timeout=_alias_timeout())
        ids = (data or {}).get('ids') or {}
        _cache_set(cache_key, ids)
        return ids
    except Exception as exc:
        _log('id lookup failed for %s/%s: %s' % (kind, item_id, exc), log_utils.LOGWARNING)
        return {}


def authorize():
    client_id = _client_id()
    client_secret = _client_secret()
    if not client_id or not client_secret:
        control.dialog.ok(
            control.addonName,
            'Die interne Trakt OAuth-Konfiguration ist unvollstaendig.'
        )
        return False

    try:
        data, _headers = _request(
            'POST',
            '/oauth/device/code',
            payload={'client_id': client_id},
            oauth=False,
            timeout=15,
        )
    except TraktError as exc:
        control.infoDialog(str(exc), icon='WARNING', time=6000)
        return False

    user_code = data.get('user_code')
    device_code = data.get('device_code')
    verification_url = data.get('verification_url') or 'https://trakt.tv/activate'
    interval = int(data.get('interval') or 5)
    expires_in = int(data.get('expires_in') or 600)
    if not user_code or not device_code:
        control.infoDialog('Trakt hat keinen Aktivierungscode geliefert.', icon='WARNING', time=6000)
        return False

    control.dialog.ok(
        control.addonName,
        'Trakt verbinden:\n\n1. Oeffne %s\n2. Gib den Code ein: [B]%s[/B]\n\nDanach mit OK fortfahren.' % (verification_url, user_code)
    )

    progress = control.progressDialog
    progress.create(control.addonName, 'Warte auf Trakt-Freigabe...')
    started = time.time()
    try:
        while time.time() - started < expires_in:
            if progress.iscanceled():
                return False
            remaining = max(0, expires_in - int(time.time() - started))
            percent = int(100 - (float(remaining) / float(expires_in) * 100))
            progress.update(percent, 'Code: %s | Restzeit: %ss' % (user_code, remaining))
            status, token_data = _poll_device_token(device_code, client_id, client_secret)
            if status == 200:
                _save_auth(token_data)
                _refresh_user_status()
                control.infoDialog('Trakt verbunden.', icon='INFO', time=5000)
                return True
            error_code = (token_data or {}).get('error') or ''
            if status == 400 and error_code in ('', 'authorization_pending', 'pending'):
                control.sleep(interval)
                continue
            if status == 418 or error_code in ('access_denied', 'denied'):
                control.infoDialog('Trakt-Freigabe wurde abgelehnt.', icon='WARNING', time=6000)
                return False
            if status in (404, 409, 410) or error_code in ('expired_token', 'invalid_grant', 'invalid_device_code'):
                control.infoDialog('Trakt-Aktivierung ist abgelaufen oder ungueltig.', icon='WARNING', time=6000)
                return False
            if status in (401, 403):
                control.infoDialog('Trakt-OAuth-Konfiguration wurde von Trakt abgelehnt.', icon='WARNING', time=6000)
                return False
            if status == 400 and error_code in ('invalid_client', 'invalid_request'):
                control.infoDialog('Trakt-OAuth-Konfiguration wurde von Trakt abgelehnt.', icon='WARNING', time=6000)
                return False
            if status == 429 or error_code == 'slow_down':
                interval += 5
            control.sleep(interval)
    finally:
        try:
            progress.close()
        except Exception:
            pass

    control.infoDialog('Trakt-Aktivierung abgelaufen.', icon='WARNING', time=6000)
    return False


def logout():
    token = _access_token()
    if token and _client_id() and _client_secret():
        try:
            _request(
                'POST',
                '/oauth/revoke',
                payload={'token': token, 'client_id': _client_id(), 'client_secret': _client_secret()},
                oauth=False,
                timeout=10,
            )
        except Exception:
            pass
    _clear_auth()
    control.infoDialog('Trakt abgemeldet.', icon='INFO')


def show_status():
    connected = is_authorized()
    if connected:
        _refresh_user_status()
    status_text = _auth_value('status') or _setting('trakt.status')
    status = status_text or ('verbunden' if connected else 'nicht verbunden')
    username = _auth_value('username') or _setting('trakt.username') or '-'
    lines = [
        'Status: %s' % status,
        'OAuth-App: xVAULT Device-Code',
        'Alias-Suche: %s' % ('aktiv' if _bool('trakt.aliases.enabled', 'true') else 'inaktiv'),
        'Gesehen-Sync: %s' % ('aktiv' if _bool('trakt.sync.watched', 'false') else 'inaktiv'),
        'Scrobbling: %s' % ('aktiv' if _bool('trakt.scrobble.enabled', 'false') else 'inaktiv'),
        'Benutzer: %s' % username,
        'Letzter Sync: %s' % (_setting('trakt.last_sync_at') or '-'),
    ]
    _log('Trakt Status: %s' % ' | '.join(lines))
    control.infoDialog(
        'Trakt: %s | Alias %s | Sync %s | Scrobble %s' % (
            status,
            'an' if _bool('trakt.aliases.enabled', 'true') else 'aus',
            'an' if _bool('trakt.sync.watched', 'false') else 'aus',
            'an' if _bool('trakt.scrobble.enabled', 'false') else 'aus',
        ),
        icon='INFO',
        time=8000
    )


def is_authorized():
    return bool(_access_token() or _refresh_token())


def sync_watched(silent=True):
    changed = False
    if not _bool('trakt.sync.watched', 'false'):
        if not silent:
            control.infoDialog('Trakt Gesehen-Sync ist deaktiviert.', icon='WARNING')
        return False
    changed = export_watched(silent=True) or changed
    changed = import_watched(silent=True) or changed
    _set_setting('trakt.last_sync_at', _display_time())
    if not silent:
        control.infoDialog('Trakt-Synchronisation abgeschlossen.', icon='INFO')
    return changed


def import_watched(silent=True):
    if not _can_use_oauth(silent):
        return False
    try:
        items = []
        movies, _headers = _request('GET', '/sync/watched/movies', oauth=True, timeout=20)
        shows, _headers = _request('GET', '/sync/watched/shows', oauth=True, timeout=30)
        for entry in movies or []:
            item = _trakt_movie_to_binge(entry)
            if item:
                items.append(item)
        for show_entry in shows or []:
            items.extend(_trakt_show_to_binge(show_entry))
        if not items:
            return False
        binge_sync.save_items(items)
        for item in items:
            if item.get('completed'):
                binge_sync.apply_to_playcount(item)
        _set_setting('trakt.last_sync_at', _display_time())
        return True
    except Exception as exc:
        _notify_or_log('Trakt-Import fehlgeschlagen: %s' % exc, silent)
        return False


def export_watched(silent=True):
    if not _can_use_oauth(silent):
        return False
    try:
        movies = []
        shows = {}
        for item in binge_sync.combined_items():
            if not (item.get('completed') or float(item.get('watched_percent') or 0) >= 90.0):
                continue
            meta = _binge_item_to_meta(item)
            if _is_episode_meta(meta):
                show_key = _show_key(meta)
                show = shows.setdefault(show_key, _history_show_object(meta))
                season = _ensure_history_season(show, _int(meta.get('season')))
                episode = {'number': _int(meta.get('episode')), 'watched_at': item.get('updated_at') or binge_sync.iso_now()}
                if episode['number']:
                    season.setdefault('episodes', []).append(episode)
            elif _is_movie_meta(meta):
                movie = _movie_object(meta)
                if movie:
                    movie['watched_at'] = item.get('updated_at') or binge_sync.iso_now()
                    movies.append(movie)
        payload = {}
        if movies:
            payload['movies'] = movies
        if shows:
            payload['shows'] = list(shows.values())
        if not payload:
            return False
        _request('POST', '/sync/history', payload=payload, oauth=True, timeout=25)
        _set_setting('trakt.last_sync_at', _display_time())
        return True
    except Exception as exc:
        _notify_or_log('Trakt-Export fehlgeschlagen: %s' % exc, silent)
        return False


def update_watch_status(meta, watched=True, silent=True):
    if not _bool('trakt.sync.watched', 'false') or not _can_use_oauth(True):
        return False
    try:
        payload = _history_payload(meta, remove=not watched)
        if not payload:
            return False
        endpoint = '/sync/history' if watched else '/sync/history/remove'
        _request('POST', endpoint, payload=payload, oauth=True, timeout=15)
        return True
    except Exception as exc:
        _notify_or_log('Trakt-Status konnte nicht geschrieben werden: %s' % exc, silent)
        return False


def update_watch_status_from_params(params, silent=True):
    try:
        meta = json.loads(params.get('meta') or '{}')
    except Exception:
        return False
    watched = str(params.get('playCount', '0')) == '1'
    return update_watch_status(meta, watched=watched, silent=silent)


def scrobble_start(meta, current_time=0, total_time=0):
    if not _bool('trakt.scrobble.enabled', 'false') or not _can_use_oauth(True):
        return False
    return _scrobble('start', meta, current_time, total_time)


def scrobble_pause(meta, current_time=0, total_time=0):
    if not _bool('trakt.scrobble.enabled', 'false') or not _can_use_oauth(True):
        return False
    return _scrobble('pause', meta, current_time, total_time)


def record_playback(meta, current_time, total_time, completed=False):
    if _bool('trakt.scrobble.enabled', 'false') and _can_use_oauth(True):
        return _scrobble('stop', meta, current_time, total_time)
    if completed:
        return update_watch_status(meta, watched=True, silent=True)
    return False


def show_media_list(params):
    if not _can_use_oauth(False):
        _empty_directory()
        return True
    list_type = params.get('type') or 'watchlist'
    media_type = params.get('media_type') or 'movie'
    try:
        ids = _list_tmdb_ids(list_type, media_type)
        if not ids:
            control.infoDialog('Keine Trakt-Eintraege gefunden.', icon='INFO')
            _empty_directory()
            return True
        _render_tmdb_ids(ids, media_type)
        return True
    except Exception as exc:
        control.infoDialog('Trakt-Liste konnte nicht geladen werden.', icon='WARNING', time=6000)
        _log('list load failed: %s' % exc, log_utils.LOGWARNING)
        _empty_directory()
        return True


def rate_from_params(params):
    if not _bool('trakt.ratings.enabled', 'false'):
        control.infoDialog('Trakt-Bewertungen sind deaktiviert.', icon='WARNING')
        return False
    if not _can_use_oauth(False):
        return False
    try:
        meta = json.loads(params.get('meta') or '{}')
    except Exception:
        control.infoDialog('Bewertung nicht moeglich: Metadaten fehlen.', icon='WARNING')
        return False
    options = ['%s/10' % i for i in range(1, 11)]
    index = control.selectDialog(options, 'Trakt-Bewertung')
    if index < 0:
        return False
    rating = index + 1
    payload = _rating_payload(meta, rating)
    if not payload:
        control.infoDialog('Bewertung nicht moeglich: IDs fehlen.', icon='WARNING')
        return False
    try:
        _request('POST', '/sync/ratings', payload=payload, oauth=True, timeout=15)
        control.infoDialog('Trakt-Bewertung gespeichert.', icon='INFO')
        return True
    except Exception as exc:
        control.infoDialog('Trakt-Bewertung fehlgeschlagen.', icon='WARNING', time=6000)
        _log('rating failed: %s' % exc, log_utils.LOGWARNING)
        return False


def context_rate_item(sysaddon, meta):
    if not _bool('trakt.ratings.enabled', 'false'):
        return None
    return ('Trakt: Bewerten', 'RunPlugin(%s?action=traktRate&meta=%s)' % (sysaddon, control.quote_plus(json.dumps(meta))))


def _scrobble(action, meta, current_time, total_time):
    try:
        progress = _progress(current_time, total_time)
        if action == 'stop' and progress < 1.0:
            return False
        payload = _scrobble_payload(meta, progress)
        if not payload:
            return False
        _request('POST', '/scrobble/%s' % action, payload=payload, oauth=True, timeout=10)
        return True
    except Exception as exc:
        _log('scrobble %s failed: %s' % (action, exc), log_utils.LOGWARNING)
        return False


def _request(method, path, params=None, payload=None, oauth=False, timeout=10, retry=True):
    if requests is None:
        raise TraktError('Python requests ist nicht verfuegbar.')
    client_id = _client_id()
    if not client_id:
        raise TraktError('Trakt OAuth-Konfiguration fehlt.')
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': _user_agent(),
        'trakt-api-key': client_id,
        'trakt-api-version': '2',
    }
    if oauth:
        token = _valid_access_token()
        if not token:
            raise TraktError('Bitte Trakt zuerst verbinden.')
        headers['Authorization'] = 'Bearer %s' % token
    url = path if str(path).startswith('http') else BASE_URL + path
    response = requests.request(method, url, headers=headers, params=params, json=payload, timeout=timeout)
    if response.status_code == 401 and oauth and retry and _refresh_access_token():
        return _request(method, path, params=params, payload=payload, oauth=oauth, timeout=timeout, retry=False)
    if 200 <= response.status_code < 300:
        if response.status_code == 204 or not response.content:
            return {}, response.headers
        try:
            return response.json(), response.headers
        except Exception:
            return {}, response.headers
    raise TraktError(_status_message(response), response.status_code)


def _poll_device_token(device_code, client_id, client_secret):
    if requests is None:
        return 0, {}
    url = BASE_URL + '/oauth/device/token'
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': _user_agent(),
        'trakt-api-key': client_id,
        'trakt-api-version': '2',
    }
    payload = {'code': device_code, 'client_id': client_id, 'client_secret': client_secret}
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    if response.status_code == 200:
        return 200, response.json()
    try:
        return response.status_code, response.json()
    except Exception:
        return response.status_code, {}


def _valid_access_token():
    token = _access_token()
    if token and _token_expires_at() > int(time.time()) + TOKEN_SKEW:
        return token
    if _refresh_access_token():
        return _access_token()
    return ''


def _refresh_access_token():
    refresh = _refresh_token()
    if not refresh or not _client_id() or not _client_secret():
        return False
    try:
        data, _headers = _request(
            'POST',
            '/oauth/token',
            payload={
                'refresh_token': refresh,
                'client_id': _client_id(),
                'client_secret': _client_secret(),
                'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                'grant_type': 'refresh_token',
            },
            oauth=False,
            timeout=15,
            retry=False,
        )
        _save_auth(data)
        return True
    except Exception as exc:
        _log('token refresh failed: %s' % exc, log_utils.LOGWARNING)
        return False


def _save_auth(data):
    expires_in = int(data.get('expires_in') or 0)
    token_expires_at = int(time.time()) + expires_in if expires_in else 0
    auth = _auth_data()
    auth.update({
        'access_token': data.get('access_token') or auth.get('access_token') or '',
        'refresh_token': data.get('refresh_token') or auth.get('refresh_token') or '',
        'token_expires_at': token_expires_at,
        'enabled': True,
        'status': auth.get('status') or 'Verbunden',
        'updated_at': _display_time(),
    })
    _write_auth(auth)
    _set_setting('trakt.access_token', auth.get('access_token') or '')
    _set_setting('trakt.refresh_token', auth.get('refresh_token') or '')
    _set_setting('trakt.token_expires_at', str(token_expires_at))
    _set_setting('trakt.enabled', 'true')
    _set_setting('trakt.status', 'Verbunden')


def _clear_auth():
    auth = _auth_data()
    auth.update({
        'access_token': '',
        'refresh_token': '',
        'token_expires_at': 0,
        'enabled': False,
        'status': 'Nicht verbunden',
        'updated_at': _display_time(),
    })
    _write_auth(auth)
    for key in ('trakt.access_token', 'trakt.refresh_token', 'trakt.token_expires_at', 'trakt.username'):
        _set_setting(key, '')
    _set_setting('trakt.status', 'Nicht verbunden')


def _refresh_user_status():
    try:
        data, _headers = _request('GET', '/users/settings', oauth=True, timeout=10)
        user = (data.get('user') or {}).get('username') or ''
        if user:
            auth = _auth_data()
            auth.update({'username': user, 'status': 'Verbunden als %s' % user, 'updated_at': _display_time()})
            _write_auth(auth)
            _set_setting('trakt.username', user)
            _set_setting('trakt.status', 'Verbunden als %s' % user)
    except Exception:
        pass


def _can_use_oauth(silent):
    if not _trakt_enabled():
        if not silent:
            control.infoDialog('Trakt-Konto ist deaktiviert.', icon='WARNING', time=6000)
        return False
    if not _client_id() or not _client_secret():
        if not silent:
            control.infoDialog('Trakt OAuth-Konfiguration fehlt.', icon='WARNING', time=6000)
        return False
    if not _valid_access_token():
        if not silent:
            control.infoDialog('Bitte Trakt zuerst verbinden.', icon='WARNING', time=6000)
        return False
    return True


def _history_payload(meta, remove=False):
    if _is_episode_meta(meta) or (_int(meta.get('season')) and not _is_movie_meta(meta)):
        show = _history_show_object(meta)
        if not show:
            return {}
        season_num = _int(meta.get('season'))
        episode_num = _int(meta.get('episode'))
        if season_num is not None:
            season = {'number': season_num}
            if episode_num:
                episode = {'number': episode_num}
                if not remove:
                    episode['watched_at'] = binge_sync.iso_now()
                season['episodes'] = [episode]
            show['seasons'] = [season]
        return {'shows': [show]}
    movie = _movie_object(meta)
    if movie:
        if not remove:
            movie['watched_at'] = binge_sync.iso_now()
        return {'movies': [movie]}
    return {}


def _rating_payload(meta, rating):
    rated_at = binge_sync.iso_now()
    if _is_episode_meta(meta) or (_int(meta.get('season')) and not _is_movie_meta(meta)):
        show = _history_show_object(meta)
        if not show:
            return {}
        season_num = _int(meta.get('season'))
        episode_num = _int(meta.get('episode'))
        if episode_num:
            show['seasons'] = [{'number': season_num, 'episodes': [{'number': episode_num, 'rating': rating, 'rated_at': rated_at}]}]
        elif season_num is not None:
            show['seasons'] = [{'number': season_num, 'rating': rating, 'rated_at': rated_at}]
        else:
            show['rating'] = rating
            show['rated_at'] = rated_at
        return {'shows': [show]}
    movie = _movie_object(meta)
    if movie:
        movie['rating'] = rating
        movie['rated_at'] = rated_at
        return {'movies': [movie]}
    return {}


def _scrobble_payload(meta, progress):
    if _is_episode_meta(meta):
        show = _show_object(meta)
        episode = _episode_object(meta)
        if not show or not episode:
            return {}
        return {'show': show, 'episode': episode, 'progress': progress}
    movie = _movie_object(meta)
    if movie:
        return {'movie': movie, 'progress': progress}
    return {}


def _movie_object(meta):
    ids = _ids(meta)
    title = meta.get('title') or meta.get('originaltitle') or meta.get('systitle') or meta.get('name')
    movie = {}
    if title:
        movie['title'] = title
    year = _int(meta.get('year'))
    if year:
        movie['year'] = year
    if ids:
        movie['ids'] = ids
    return movie if movie.get('ids') or movie.get('title') else {}


def _show_object(meta):
    ids = _ids(meta)
    title = meta.get('systitle') or meta.get('title') or meta.get('showtitle')
    show = {}
    if title:
        show['title'] = title
    year = _int(meta.get('year'))
    if year:
        show['year'] = year
    if ids:
        show['ids'] = ids
    return show if show.get('ids') or show.get('title') else {}


def _history_show_object(meta):
    show = _show_object(meta)
    return show


def _episode_object(meta):
    season = _int(meta.get('season'))
    episode = _int(meta.get('episode'))
    if season is None or episode is None:
        return {}
    result = {'season': season, 'number': episode}
    if meta.get('episode_title'):
        result['title'] = meta.get('episode_title')
    return result


def _ids(meta):
    ids = {}
    imdb = meta.get('imdb_id') or meta.get('imdbnumber') or meta.get('imdb')
    tmdb = meta.get('tmdb_id')
    tvdb = meta.get('tvdb_id')
    if imdb:
        ids['imdb'] = str(imdb)
    if tmdb:
        ids['tmdb'] = _int(tmdb) or tmdb
    if tvdb:
        ids['tvdb'] = _int(tvdb) or tvdb
    return ids


def _binge_item_to_meta(item):
    extra = item.get('extra') or {}
    return {
        'mediatype': extra.get('mediatype') or ('tvshow' if item.get('season') and item.get('episode') else 'movie'),
        'title': item.get('title') or item.get('name'),
        'systitle': item.get('title') or item.get('name'),
        'name': item.get('name'),
        'year': item.get('year'),
        'season': item.get('season'),
        'episode': item.get('episode'),
        'imdb_id': extra.get('imdb_id'),
        'tmdb_id': extra.get('tmdb_id'),
    }


def _trakt_movie_to_binge(entry):
    movie = entry.get('movie') or {}
    ids = movie.get('ids') or {}
    title = movie.get('title') or ''
    year = movie.get('year') or ''
    if not title:
        return None
    name = '%s (%s)' % (title, year) if year else title
    meta = {'mediatype': 'movie', 'imdb_id': ids.get('imdb'), 'tmdb_id': ids.get('tmdb')}
    return {
        'schema_version': 1,
        'item_key': binge_sync.item_key(meta, name, year),
        'title': title,
        'name': name,
        'year': str(year or '0'),
        'season': None,
        'episode': None,
        'position_seconds': 0,
        'duration_seconds': 0,
        'watched_percent': 100.0,
        'completed': True,
        'provider': 'trakt',
        'updated_at': entry.get('last_watched_at') or binge_sync.iso_now(),
        'extra': {'mediatype': 'movie', 'imdb_id': ids.get('imdb') or '', 'tmdb_id': ids.get('tmdb') or ''},
    }


def _trakt_show_to_binge(entry):
    show = entry.get('show') or {}
    ids = show.get('ids') or {}
    title = show.get('title') or ''
    result = []
    if not title:
        return result
    for season in entry.get('seasons') or []:
        season_num = _int(season.get('number'))
        if season_num is None:
            continue
        for episode in season.get('episodes') or []:
            episode_num = _int(episode.get('number'))
            if episode_num is None:
                continue
            name = '%s S%02dE%02d' % (title, season_num, episode_num)
            meta = {'mediatype': 'episode', 'imdb_id': ids.get('imdb'), 'tmdb_id': ids.get('tmdb'), 'season': season_num, 'episode': episode_num}
            result.append({
                'schema_version': 1,
                'item_key': binge_sync.item_key(meta, name, '0'),
                'title': title,
                'name': name,
                'year': str(show.get('year') or '0'),
                'season': season_num,
                'episode': episode_num,
                'position_seconds': 0,
                'duration_seconds': 0,
                'watched_percent': 100.0,
                'completed': True,
                'provider': 'trakt',
                'updated_at': episode.get('last_watched_at') or entry.get('last_watched_at') or binge_sync.iso_now(),
                'extra': {'mediatype': 'episode', 'imdb_id': ids.get('imdb') or '', 'tmdb_id': ids.get('tmdb') or ''},
            })
    return result


def _list_tmdb_ids(list_type, media_type):
    trakt_type = 'movies' if media_type == 'movie' else 'shows'
    ids = []
    if list_type == 'collection':
        path = '/sync/collection/%s' % trakt_type
        pages = [(None, None)]
    else:
        path = '/sync/watchlist/%s/rank/asc' % trakt_type
        pages = []
        for page in range(1, MAX_LIST_PAGES + 1):
            pages.append((page, 100))
    for page, limit in pages:
        params = {}
        if page:
            params = {'page': page, 'limit': limit}
        data, headers = _request('GET', path, params=params, oauth=True, timeout=25)
        for entry in data or []:
            item = entry.get('movie') if media_type == 'movie' else entry.get('show')
            ids_obj = (item or {}).get('ids') or {}
            tmdb_id = ids_obj.get('tmdb')
            if tmdb_id and tmdb_id not in ids:
                ids.append(tmdb_id)
        if not page:
            break
        try:
            page_count = int(headers.get('X-Pagination-Page-Count') or page)
            if page >= page_count:
                break
        except Exception:
            if not data:
                break
    return ids


def _render_tmdb_ids(ids, media_type):
    from resources.lib.tmdb import cTMDB
    if media_type == 'movie':
        from resources.lib.indexers import movies
        renderer = movies.movies()
        items = []
        for tmdb_id in ids:
            meta = renderer.super_meta(tmdb_id)
            if meta:
                items.append(meta)
        renderer.Directory(items)
    else:
        from resources.lib.indexers import tvshows
        renderer = tvshows.tvshows()
        items = []
        tmdb = cTMDB()
        for tmdb_id in ids:
            try:
                meta = tmdb.get_meta('tvshow', '', '', tmdb_id, advanced='true')
                if meta:
                    playcount = 0
                    try:
                        from resources.lib import watched_status
                        playcount = watched_status.tvshow_playcount(meta['title'], number_of_seasons=meta.get('number_of_seasons'))
                    except Exception:
                        pass
                    meta.update({'playcount': playcount, 'overlay': 7 if playcount else 6})
                    items.append(meta)
            except Exception:
                pass
        renderer.Directory(items)


def _empty_directory():
    try:
        handle = int(sys.argv[1])
        if handle >= 0:
            control.endofdirectory(handle, succeeded=True, cacheToDisc=False)
    except Exception:
        pass


def _ensure_history_season(show, season_num):
    for season in show.setdefault('seasons', []):
        if _int(season.get('number')) == season_num:
            return season
    season = {'number': season_num, 'episodes': []}
    show['seasons'].append(season)
    return season


def _show_key(meta):
    ids = _ids(meta)
    return 'tmdb:%s' % ids.get('tmdb') if ids.get('tmdb') else 'imdb:%s' % ids.get('imdb') if ids.get('imdb') else 'title:%s' % (meta.get('title') or meta.get('systitle') or '')


def _is_movie_meta(meta):
    mediatype = str(meta.get('mediatype') or '').lower()
    return mediatype == 'movie' or (not meta.get('season') and not meta.get('episode') and mediatype != 'tvshow')


def _is_episode_meta(meta):
    return bool(_int(meta.get('season')) is not None and _int(meta.get('episode')) is not None)


def _progress(current_time, total_time):
    try:
        total = float(total_time or 0)
        current = float(current_time or 0)
        if total > 0:
            return round(max(0.0, min(100.0, current / total * 100.0)), 2)
    except Exception:
        pass
    return 0.1


def _status_message(response):
    mapping = {
        401: 'Trakt OAuth fehlt oder ist abgelaufen.',
        403: 'Trakt API-Key ist ungueltig oder die App ist nicht freigegeben.',
        409: 'Trakt meldet einen Konflikt/Duplikat.',
        420: 'Trakt Account-Limit erreicht.',
        422: 'Trakt konnte die Daten nicht verarbeiten.',
        429: 'Trakt Rate-Limit erreicht. Bitte spaeter erneut versuchen.',
    }
    message = mapping.get(response.status_code, 'Trakt Fehler %s' % response.status_code)
    retry_after = response.headers.get('Retry-After')
    if retry_after:
        message += ' Retry-After: %ss.' % retry_after
    return message


def _notify_or_log(message, silent):
    if silent:
        _log(message, log_utils.LOGWARNING)
    else:
        control.infoDialog(message, icon='WARNING', time=6000)


def _cache_get(key, ttl):
    data = _cache_data()
    item = data.get(key)
    if not isinstance(item, dict):
        return None
    if int(time.time()) - int(item.get('timestamp') or 0) > ttl:
        return None
    return item.get('value')


def _cache_set(key, value):
    data = _cache_data()
    data[key] = {'timestamp': int(time.time()), 'value': value}
    storage.write_json(CACHE_FILE, data)


def _cache_data():
    data = storage.read_json(CACHE_FILE, {})
    return data if isinstance(data, dict) else {}


def _cache_ttl():
    try:
        hours = int(_setting('trakt.alias.cache.hours', '168'))
    except Exception:
        hours = 168
    return max(1, hours) * 3600


def _alias_timeout():
    try:
        return max(1, int(_setting('trakt.alias.timeout', '5')))
    except Exception:
        return 5


def _client_id():
    return _decode_secret(TRAKT_CLIENT_ID)


def _client_secret():
    return _decode_secret(TRAKT_CLIENT_SECRET)


def _decode_secret(value):
    if value.startswith('b64:'):
        return base64.b64decode(value[4:].encode('ascii')).decode('utf-8')
    return value


def _user_agent():
    version = getattr(control, 'addonVersion', '') or 'unknown'
    return 'xVAULT/%s Kodi' % version


def _access_token():
    return (_auth_value('access_token') or _setting('trakt.access_token') or '').strip()


def _refresh_token():
    return (_auth_value('refresh_token') or _setting('trakt.refresh_token') or '').strip()


def _token_expires_at():
    try:
        return int(_auth_value('token_expires_at') or _setting('trakt.token_expires_at') or 0)
    except Exception:
        return 0


def _trakt_enabled():
    auth = _auth_data()
    if auth.get('enabled') is True or str(auth.get('enabled')).lower() == 'true':
        return True
    return _bool('trakt.enabled', 'false')


def _auth_value(key, default=''):
    data = _auth_data()
    value = data.get(key, default) if isinstance(data, dict) else default
    return '' if value is None else str(value)


def _auth_data():
    data = storage.read_json(AUTH_FILE, {})
    return data if isinstance(data, dict) else {}


def _write_auth(data):
    return storage.write_json(AUTH_FILE, data)


def _setting(key, default=''):
    return control.getSetting(key, default)


def _set_setting(key, value):
    value = '' if value is None else str(value)
    try:
        if key in ('trakt.enabled',):
            control.Addon.setSettingBool(key, value.lower() == 'true')
            return
        control.Addon.setSettingString(key, value)
        return
    except Exception as exc:
        _log('Trakt setSettingString/setSettingBool fehlgeschlagen fuer %s: %s' % (key, exc), log_utils.LOGWARNING)
        pass
    try:
        control.setSetting(key, value)
    except Exception as exc:
        _log('Trakt setting fallback fehlgeschlagen fuer %s: %s' % (key, exc), log_utils.LOGWARNING)


def _bool(key, default='false'):
    return str(_setting(key, default)).lower() == 'true'


def _trakt_kind(mediatype):
    value = str(mediatype or '').lower()
    if value.startswith('movie'):
        return 'movies'
    if value.startswith('show') or value.startswith('tv'):
        return 'shows'
    return value


def _unique(values):
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _int(value):
    try:
        if value == '' or value is None:
            return None
        return int(value)
    except Exception:
        return None


def _display_time():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def _log(message, level=log_utils.LOGINFO):
    try:
        log_utils.log('Trakt: %s' % message, level)
    except Exception:
        pass
