"""Kodi library bridge: JSON-RPC only and stable IDs, never title guesses or SQL."""
import collections
import json
import time
import uuid

from resources.lib import control

_pending = collections.deque(maxlen=200)
_catalog = {}


def rpc(method, params):
    import xbmc
    reply = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    if 'error' in reply:
        raise RuntimeError('Kodi library RPC: ' + method)
    return reply.get('result') or {}


def same_ids(meta, row):
    ids = row.get('uniqueid') or {}
    wanted = {'imdb': str(meta.get('imdb_id') or meta.get('imdbnumber') or ''), 'tmdb': str(meta.get('tmdb_id') or '')}
    shared = [key for key in wanted if wanted[key] and ids.get(key)]
    return bool(shared) and all(wanted[key] == str(ids[key]) for key in shared)


def catalog(kind):
    now = time.monotonic()
    old = _catalog.get(kind)
    if old and now - old[0] < 30:
        return old[1]
    plural = 'Movies' if kind == 'movie' else 'TVShows'
    rows = rpc('VideoLibrary.Get' + plural, {'properties': ['uniqueid']}).get(plural.lower(), [])
    _catalog[kind] = (now, rows)
    return rows


def targets(meta):
    from resources.lib.playback_state import normalize
    meta = normalize(meta)
    kind = meta['mediatype']
    base = 'movie' if kind == 'movie' else 'tvshow'
    found = [row for row in catalog(base) if same_ids(meta, row)]
    if len(found) != 1:
        return []
    if base == 'movie':
        return [('movie', found[0]['movieid'])]
    rows = rpc('VideoLibrary.GetEpisodes', {'tvshowid': found[0]['tvshowid'], 'properties': ['season', 'episode']}).get('episodes', [])
    return [('episode', row['episodeid']) for row in rows
            if (kind == 'tvshow' or int(row['season']) == int(meta.get('season') or 0))
            and (kind != 'episode' or int(row['episode']) == int(meta['episode']))]


def details(kind, identifier):
    return rpc('VideoLibrary.Get%sDetails' % kind.title(), {kind + 'id': identifier, 'properties': ['playcount', 'resume']}).get(kind + 'details', {})


def signature(row):
    resume = row.get('resume') or {}
    return [int(row.get('playcount') or 0), round(float(resume.get('position') or 0), 1), round(float(resume.get('total') or 0), 1)]


def write(meta, completed=None, position=0, total=0):
    if control.getSetting('playback.library', 'true') == 'false':
        return
    try:
        import xbmcgui
        for kind, identifier in targets(meta):
            old = details(kind, identifier)
            params = {kind + 'id': identifier, 'resume': {'position': float(position), 'total': float(total)}}
            if completed is not None:
                params['playcount'] = 1 if completed else 0
                if not completed:
                    params['lastplayed'] = ''
            expected = {'playcount': params.get('playcount', old.get('playcount', 0)), 'resume': params['resume']}
            # Shared across plugin interpreters and the service; avoids echo loops.
            xbmcgui.Window(10000).setProperty('xvault.library.%s.%s' % (kind, identifier), json.dumps(signature(expected)))
            rpc('VideoLibrary.Set%sDetails' % kind.title(), params)
    except Exception as exc:
        from resources.lib import log_utils
        log_utils.log('xVAULT library bridge: ' + type(exc).__name__, log_utils.LOGWARNING)


def notify(method, data):
    if method == 'VideoLibrary.OnUpdate':
        try:
            value = json.loads(data).get('item') or {}
            if value.get('type') in ('movie', 'episode') and value.get('id') is not None:
                _pending.append((value['type'], int(value['id'])))
        except (ValueError, TypeError):
            pass
    elif method in ('VideoLibrary.OnScanFinished', 'VideoLibrary.OnRemove'):
        _catalog.clear()


def poll():
    import xbmc
    import xbmcgui
    if not _pending or xbmc.Player().isPlayingVideo() or control.getSetting('playback.library', 'true') == 'false':
        return
    kind, identifier = _pending.popleft()
    try:
        row = details(kind, identifier)
        marker = 'xvault.library.%s.%s' % (kind, identifier)
        win = xbmcgui.Window(10000)
        if win.getProperty(marker) == json.dumps(signature(row)):
            return
        from resources.lib import personal, playback_state
        from resources.lib.sync import binge_sync, engine
        for item in list(binge_sync.load_items()):
            meta = personal.item_meta(item)
            if playback_state.normalize(meta)['mediatype'] != kind:
                continue
            if (kind, identifier) not in targets(meta):
                continue
            updated = dict(item)
            resume = row.get('resume') or {}
            completed = bool(row.get('playcount'))
            updated.update(completed=completed, watch_state='watched' if completed else 'unwatched',
                           position_seconds=float(resume.get('position') or 0), duration_seconds=float(resume.get('total') or 0),
                           watched_percent=100 if completed else 0, progress_reset=not resume.get('position'),
                           session_id='kodi:' + str(uuid.uuid4()), sequence=0, updated_at=binge_sync.iso_now())
            playback_state._replace(updated)
            binge_sync.apply_local_states({updated['item_key']: updated}, apply_library=False)
            engine.record(updated, kind='progress', session_id=updated['session_id'])
            if bool(item.get('completed')) != completed:
                engine.record(updated, kind='watch')
            engine.request_background(active=True)
        win.setProperty(marker, json.dumps(signature(row)))
    except Exception as exc:
        from resources.lib import log_utils
        log_utils.log('xVAULT library import: ' + type(exc).__name__, log_utils.LOGWARNING)
