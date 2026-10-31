"""Local-first start page and bounded series radar, using existing playback/sync."""
import contextlib
import datetime
import json
import os
import sqlite3
import sys
import threading
import time
from urllib.parse import urlencode

from resources.lib import control, watch_progress

CACHE_TTL = 6 * 3600
WORK_BUDGET = 25
_worker = None


@contextlib.contextmanager
def database():
    os.makedirs(control.dataPath, exist_ok=True)
    conn = sqlite3.connect(os.path.join(control.dataPath, 'personal.sqlite'), timeout=3)
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS shows (id TEXT PRIMARY KEY, meta TEXT NOT NULL, added REAL NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS cache (id TEXT PRIMARY KEY, value TEXT NOT NULL, checked REAL NOT NULL)')
        yield conn
        conn.commit()
    finally:
        conn.close()


def subscriptions():
    with database() as conn:
        return [json.loads(row[0]) for row in conn.execute('SELECT meta FROM shows ORDER BY added DESC')]


def cached():
    with database() as conn:
        return {row[0]: dict(json.loads(row[1]), checked=row[2]) for row in conn.execute('SELECT id,value,checked FROM cache')}


def save_cache(identifier, value):
    with database() as conn:
        # A removed subscription must not be resurrected by a running check.
        if conn.execute('SELECT 1 FROM shows WHERE id=?', (str(identifier),)).fetchone():
            conn.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)', (str(identifier), json.dumps(value), time.time()))


def toggle(meta):
    identifier = str(meta.get('tmdb_id') or '')
    if not identifier.isdigit():
        control.infoDialog('Für diese Serie fehlt die TMDb-ID.')
        return
    with database() as conn:
        exists = conn.execute('SELECT 1 FROM shows WHERE id=?', (identifier,)).fetchone()
        if exists:
            conn.execute('DELETE FROM shows WHERE id=?', (identifier,))
            conn.execute('DELETE FROM cache WHERE id=?', (identifier,))
        else:
            value = dict(meta, mediatype='tvshow')
            value.pop('episodes', None)
            conn.execute('INSERT INTO shows VALUES (?,?,?)', (identifier, json.dumps(value), time.time()))
    request_refresh()
    control.infoDialog('Aus Serien-Radar entfernt' if exists else 'Im Serien-Radar vorgemerkt')
    control.execute('Container.Refresh')


def context(meta):
    return ('Serien-Radar: vormerken / entfernen', 'RunPlugin(%s)' % url('radarToggle', sysmeta=json.dumps(meta)))


def url(action, **params):
    return 'plugin://plugin.video.xvault/?' + urlencode(dict(action=action, **params))


def item_meta(item):
    extra = item.get('extra') or {}
    meta = dict(extra.get('meta') or {})
    for field in ('mediatype', 'tmdb_id', 'imdb_id'):
        if extra.get(field) and not meta.get(field):
            meta[field] = extra[field]
    meta.update(title=meta.get('title') or item.get('title') or item.get('name'), year=item.get('year') or meta.get('year') or '0')
    if item.get('season') is not None and item.get('episode') is not None:
        meta.update(mediatype='episode', season=item['season'], episode=item['episode'])
    else:
        meta.setdefault('mediatype', 'movie')
    return meta


def progress_items():
    from resources.lib.sync import binge_sync
    return sorted(binge_sync.load_items(), key=lambda i: i.get('updated_at') or '', reverse=True)


def continuing(items=None):
    return [i for i in (progress_items() if items is None else items)
            if not i.get('completed') and watch_progress.should_store_resume(i.get('position_seconds'), i.get('duration_seconds'))][:30]


def last_episodes(items):
    result = {}
    for item in items:
        meta = item_meta(item)
        identifier = str(meta.get('tmdb_id') or '')
        if meta.get('mediatype') == 'episode' and identifier and identifier not in result:
            result[identifier] = item
    return result


def next_episode(episodes, last):
    """Use aired, unwatched regular episodes; handle season boundaries explicitly."""
    today = datetime.date.today().isoformat()
    episodes = sorted((e for e in episodes if e.get('season_number', 0) > 0 and e.get('air_date') and e['air_date'] <= today),
                      key=lambda e: (e['season_number'], e['episode_number']))
    if not last:
        return episodes[-1] if episodes else None
    current = (int(last.get('season') or 0), int(last.get('episode') or 0)) if last else (0, 0)
    for episode in episodes:
        number = (episode['season_number'], episode['episode_number'])
        if number > current or (number == current and not last.get('completed')):
            return episode
    return None


def fetch(path, deadline):
    from resources.lib.requestHandler import cRequestHandler
    from resources.lib.tmdb import cTMDB
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Radar budget exhausted')
    api = cTMDB()
    query = urlencode({'api_key': api.api_key, 'language': 'de-DE'})
    return json.loads(cRequestHandler(api.URL + path + '?' + query, caching=False).request_bounded(
        timeout=min(4, remaining), budget=remaining, limit=2 * 1024 * 1024))


def refresh_one(meta, last=None):
    deadline = time.monotonic() + WORK_BUDGET
    identifier = str(meta['tmdb_id'])
    detail = fetch('tv/' + identifier, deadline)
    meta = dict(meta, number_of_seasons=detail.get('number_of_seasons', 0))
    if not meta.get('poster') and detail.get('poster_path'):
        meta['poster'] = 'https://image.tmdb.org/t/p/w342' + detail['poster_path']
    if not meta.get('fanart') and detail.get('backdrop_path'):
        meta['fanart'] = 'https://image.tmdb.org/t/p/w1280' + detail['backdrop_path']
    seasons = [s for s in detail.get('seasons', []) if s.get('season_number', 0) > 0 and s.get('air_date') and s['air_date'] <= datetime.date.today().isoformat()]
    start = int(last.get('season') or 1) if last else (seasons[-1]['season_number'] if seasons else 1)
    episodes = []
    # At most two seasons per check, including the next season after a finale.
    for season in [s for s in seasons if s['season_number'] >= start][:2]:
        episodes.extend(fetch('tv/%s/season/%s' % (identifier, season['season_number']), deadline).get('episodes', []))
    episode = next_episode(episodes, last)
    value = {'meta': meta, 'episode': episode, 'source_status': 'nicht geprüft'}
    if episode:
        value['meta'] = dict(meta, mediatype='episode', season=episode['season_number'], episode=episode['episode_number'],
                             episode_title=episode.get('name', ''), episode_premiered=episode.get('air_date', ''))
    save_cache(identifier, value)
    return value


def request_refresh(force=False):
    import xbmcgui
    if force:
        with database() as conn:
            conn.execute('UPDATE cache SET checked=0')
    xbmcgui.Window(10000).setProperty('xvault.personal.refresh', 'force' if force else 'pending')


def worker():
    import xbmc
    import xbmcgui
    from resources.lib import update_maintenance
    monitor = xbmc.Monitor()
    win = xbmcgui.Window(10000)
    next_check = time.monotonic() + 15
    while not monitor.waitForAbort(1) and not update_maintenance.requested():
        request = win.getProperty('xvault.personal.refresh')
        if time.monotonic() < next_check and not request:
            continue
        win.clearProperty('xvault.personal.refresh')
        next_check = time.monotonic() + 30
        if xbmc.Player().isPlayingVideo():
            continue
        try:
            cache = cached()
            history = last_episodes(progress_items())
            shows = {str(m['tmdb_id']): m for m in subscriptions()}
            # Completed episodes also populate the next-episode section without subscription.
            shows.update({key: item_meta(item) for key, item in history.items() if key not in shows})
            for identifier, meta in shows.items():
                if monitor.abortRequested() or update_maintenance.requested():
                    return
                last = history.get(identifier)
                marker = [last.get('season'), last.get('episode'), last.get('completed')] if last else None
                old = cache.get(identifier, {})
                if request != 'force' and time.time() - old.get('checked', 0) < CACHE_TTL and old.get('last') == marker:
                    continue
                try:
                    value = refresh_one(meta, last)
                    if value.get('episode') and identifier in {str(s['tmdb_id']) for s in subscriptions()}:
                        from resources.lib.radar_probe import probe
                        value['source_status'] = probe(value['meta'], budget=12)
                        value['source_checked'] = time.time()
                    value['last'] = marker
                    # cache also supports recently watched, non-subscribed shows
                    with database() as conn:
                        conn.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)', (identifier, json.dumps(value), time.time()))
                except Exception as exc:
                    xbmc.log('xVAULT radar: ' + type(exc).__name__, xbmc.LOGWARNING)
                    failed = dict(old, meta=old.get('meta') or meta, last=marker, error=type(exc).__name__)
                    with database() as conn:
                        conn.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)', (identifier, json.dumps(failed), time.time() - CACHE_TTL + 300))
                # One bounded show per tick prevents long startup/network bursts.
                break
        except Exception as exc:
            xbmc.log('xVAULT personal worker: ' + type(exc).__name__, xbmc.LOGWARNING)


def start_background():
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=worker, name='xvault-personal', daemon=True)
        _worker.start()


def add(label, action, meta=None, folder=False, description='', context_items=None):
    import xbmcgui
    import xbmcplugin
    target = url(action, **({'sysmeta': json.dumps(meta)} if meta else {}))
    item = xbmcgui.ListItem(label=label, offscreen=True)
    item.setArt({'thumb': (meta or {}).get('poster') or 'DefaultTVShows.png', 'fanart': (meta or {}).get('fanart') or control.addonFanart()})
    item.setInfo('video', {'title': label, 'plot': description or (meta or {}).get('plot', '')})
    item.setProperty('IsPlayable', 'true' if action in ('personalPlay', 'play') else 'false')
    if context_items:
        item.addContextMenuItems(context_items)
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), target, item, folder)


def render_preview():
    for item in continuing()[:3]:
        add('Weiterschauen · %s · %s' % (item.get('name') or item['title'], watch_progress.format_time(item['position_seconds'])), 'personalPlay', item_meta(item))
    for entry in list(cached().values())[:3]:
        if entry.get('episode') and entry.get('last') and entry['last'][2]:
            meta = entry['meta']
            add('Nächste Folge · %s · S%02dE%02d' % (meta['title'], int(meta['season']), int(meta['episode'])), 'personalPlay', meta)
    subscribed = {str(m['tmdb_id']) for m in subscriptions()}
    for key, entry in list(cached().items()):
        if key in subscribed and entry.get('episode'):
            meta = entry['meta']
            add('Serien-Radar · %s · S%02dE%02d · %s' % (meta['title'], int(meta['season']), int(meta['episode']), entry.get('source_status', 'nicht geprüft')), 'personalPlay', meta)
            break
    if control.getSetting('radio.enabled', 'true') != 'false':
        from resources.lib import radio
        index = radio.recent_programs()
        if index:
            programs = index
            recent = radio.stored('radio.history')
            for identifier in sorted(recent, key=recent.get, reverse=True)[:2]:
                station = radio.find(identifier, programs)
                if station:
                    import xbmcplugin
                    xbmcplugin.addDirectoryItem(int(sys.argv[1]), radio.url('radioPlay', id=station['id']), radio.music_item(station, 'Zuletzt gehört · ' + station['name']), False)


def home():
    import xbmcplugin
    add('Weiterschauen', 'personalContinue', folder=True)
    add('Nächste Serienfolgen', 'personalNext', folder=True)
    add('Serien-Radar · vorgemerkte Serien', 'seriesRadar', folder=True)
    if control.getSetting('radio.enabled', 'true') != 'false':
        add('Meine Radiofavoriten', 'radioFavorites', folder=True)
        add('Zuletzt gehörte Sender', 'radioRecent', folder=True)
        from resources.lib import radio
        radio.quick_favorites()
    add('Systemcheck', 'systemCheck', folder=True)
    render_preview()
    xbmcplugin.setPluginCategory(int(sys.argv[1]), 'Mein xVAULT')
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc=False)


def show(action):
    import xbmcplugin
    if action == 'personalContinue':
        rows = continuing()
        for item in rows:
            add('%s · ab %s' % (item.get('name') or item['title'], watch_progress.format_time(item['position_seconds'])), 'personalPlay', item_meta(item))
        if not rows:
            add('Noch keine begonnenen Filme oder Folgen', 'personalInfo')
    else:
        cache = cached()
        metas = subscriptions() if action == 'seriesRadar' else [item_meta(i) for i in last_episodes(progress_items()).values()]
        for meta in metas:
            value = cache.get(str(meta.get('tmdb_id')), {})
            ep = value.get('episode')
            stale = time.time() - value.get('checked', 0) >= CACHE_TTL
            label = meta.get('title', 'Serie')
            if ep:
                label += ' · S%02dE%02d · %s' % (ep['season_number'], ep['episode_number'], ep.get('name') or '')
                status = value.get('source_status', 'nicht geprüft')
                if value.get('source_checked') and time.time() - value['source_checked'] > CACHE_TTL:
                    status = 'Quellenprüfung veraltet'
                label += ' · ' + status
            else:
                label += ' · ' + ('Prüfung vorübergehend nicht möglich' if value.get('error') else 'keine weitere ausgestrahlte Folge gefunden' if value else 'Prüfung ausstehend')
            if ep and value.get('error'):
                label += ' · letzte Prüfung fehlgeschlagen'
            if stale and value:
                label += ' · Stand veraltet'
            contexts = [context(meta)]
            if ep:
                contexts.append(('Deutsche Quellen jetzt prüfen', 'RunPlugin(%s)' % url('radarSources', id=str(meta['tmdb_id']))))
            target_meta = value.get('meta') or meta
            target_action = 'personalPlay' if ep else 'seasons' if target_meta.get('number_of_seasons') else 'personalInfo'
            add(label, target_action, target_meta, folder=target_action == 'seasons', context_items=contexts,
                description='Quellenangaben sind Anbieterangaben, keine bestätigte Tonspur. Stand: %s' %
                (time.strftime('%d.%m.%Y %H:%M', time.localtime(value['checked'])) if value else 'noch nicht geprüft'))
        if not metas:
            add('Serien über ihr Kontextmenü vormerken' if action == 'seriesRadar' else 'Noch kein Serienverlauf vorhanden', 'personalInfo')
        add('Serienprüfung im Hintergrund anfordern', 'radarRefresh')
    xbmcplugin.setPluginCategory(int(sys.argv[1]), 'Mein xVAULT / ' + {'seriesRadar': 'Serien-Radar', 'personalNext': 'Nächste Folgen', 'personalContinue': 'Weiterschauen'}[action])
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc=False)
    request_refresh()


def play(meta):
    # Fetch the latest account position before the existing source/player path.
    from resources.lib.sync import storage, engine
    if storage.is_enabled() and storage.is_logged_in():
        if not engine.synchronize(active=True):
            control.infoDialog('Abgleich derzeit nicht erreichbar; lokaler Wiedergabestand wird verwendet.', time=5000)
    from resources.lib.sources import sources
    return sources().play({'sysmeta': json.dumps(meta)})


def source_check(identifier):
    """Use the normal source collector in an isolated Kodi script, never the menu."""
    import xbmc
    import xbmcgui
    win = xbmcgui.Window(10000)
    if win.getProperty('xvault.radar.sources'):
        control.infoDialog('Eine Quellenprüfung läuft bereits.')
        return
    value = cached().get(str(identifier))
    if not value or not value.get('episode'):
        return
    if time.time() - value.get('source_checked', 0) < CACHE_TTL:
        control.infoDialog(value.get('source_status', 'Nicht geprüft'))
        return
    win.setProperty('xvault.radar.sources', str(identifier))
    xbmc.executebuiltin('RunScript(%s,%s)' % (os.path.join(control.addonPath, 'resources', 'lib', 'radar_probe.py'), identifier))
    control.infoDialog('Deutsche Quellen werden im Hintergrund geprüft (max. 20 Sekunden).')
