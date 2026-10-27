"""Native Kodi radio directories, music playback and Kodi favourites."""
import json
import hashlib
import os
import sys
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib import radio_browser as rb

BASE = 'plugin://plugin.video.xvault/'
CACHE_PROPERTY = 'xvault.radio.catalog.v2'
IDENTITY_REQUEST = 'xvault.radio.identities.requested'
_identity_thread = None
INDEX_PROPERTY = 'xvault.radio.index.v1'
RAW_STAMP_PROPERTY = 'xvault.radio.raw.stamp'
INDEX_SCHEMA = 1
RETRY_INTERVAL = 300
LIST_PAGE_SIZE = 250
SORTS = ('votes', 'name', 'bitrate')
SORT_LABELS = ('Meiste Votes', 'Name A–Z', 'Höchste Bitrate')


def addon():
    return xbmcaddon.Addon('plugin.video.xvault')


def handle():
    return int(sys.argv[1])


def url(action, **params):
    return BASE + '?' + urlencode(dict(params, action=action))


def notify(message):
    xbmcgui.Dialog().notification('xVAULT Radio', message, xbmcgui.NOTIFICATION_INFO, 5000)


def rpc(method, params):
    result = json.loads(xbmc.executeJSONRPC(json.dumps(dict(jsonrpc='2.0', id=1, method=method, params=params))))
    if result.get('error'):
        raise rb.RadioError('Kodi konnte die Favoriten nicht bearbeiten.')
    return result.get('result', {})


def client():
    return rb.Client(addon().getAddonInfo('version'))


def cache_path():
    folder = xbmcvfs.translatePath(addon().getAddonInfo('profile'))
    xbmcvfs.mkdirs(folder)
    return folder + '/radio-catalog.json'


def file_stamp(path):
    try:
        stat = os.stat(path)
        return [stat.st_mtime_ns, stat.st_size]
    except OSError:
        return None


def atomic_json(path, text):
    temporary = path + '.%s.%s.tmp' % (os.getpid(), time.time_ns())
    try:
        with xbmcvfs.File(temporary, 'w') as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.isfile(temporary):
            os.remove(temporary)


def index_path(meta=False):
    return os.path.join(os.path.dirname(cache_path()), 'radio-index-meta.json' if meta else 'radio-index-programs.json')


def source_token():
    return [INDEX_SCHEMA, addon().getAddonInfo('version'), file_stamp(cache_path()), file_stamp(identity_path())]


def summaries(programs):
    families, genres, family_genres, genre_families, singles_by_genre = {}, {}, {}, {}, {}
    singles = 0
    for station in programs:
        family = station['family']
        if family:
            families[family] = families.get(family, 0) + 1
        else:
            singles += 1
        for genre in station['genres']:
            genres[genre] = genres.get(genre, 0) + 1
            if family:
                fg = family_genres.setdefault(family, {})
                fg[genre] = fg.get(genre, 0) + 1
                gf = genre_families.setdefault(genre, {})
                gf[family] = gf.get(family, 0) + 1
            else:
                singles_by_genre[genre] = singles_by_genre.get(genre, 0) + 1
    return dict(families=families, genres=genres, family_genres=family_genres,
                genre_families=genre_families, singles=singles, singles_by_genre=singles_by_genre)


def read_index(summary_only=False):
    try:
        text = xbmcgui.Window(10011).getProperty(INDEX_PROPERTY)
        if not text:
            with xbmcvfs.File(index_path(meta=True)) as stream:
                text = stream.read()
        meta = json.loads(text)
        now = time.time()
        if (meta['token'] != source_token() or not 0 <= now - meta['timestamp'] < rb.STALE_TTL
                or not meta['created'] <= now < meta['valid_until']
                or meta['program_stamp'] != file_stamp(index_path())):
            return None
        if not isinstance(meta['summary'], dict) or not all(isinstance(meta['summary'][key], dict)
                for key in ('families', 'genres', 'family_genres', 'genre_families', 'singles_by_genre')):
            return None
        if summary_only:
            return meta
        with xbmcvfs.File(index_path()) as stream:
            data = stream.read()
        if hashlib.sha256(data.encode('utf-8')).hexdigest() != meta['digest']:
            return None
        programs = json.loads(data)
        return programs if isinstance(programs, list) else None
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return None


def prepare_index(cached, offline=False, records=None):
    token = source_token()
    records = read_identities() if records is None else records
    programs = rb.group_stations(cached['rows'], records)
    now = time.time()
    valid_until = min(cached['timestamp'] + rb.STALE_TTL,
                      now + RETRY_INTERVAL if offline else cached['timestamp'] + rb.CATALOG_TTL)
    for record in records.values():
        if record.get('ok') is True:
            valid_until = min(valid_until, float(record['checked']) + rb.IDENTITY_TTL)
    if token == source_token() and valid_until > now:
        data = json.dumps(programs, ensure_ascii=False, separators=(',', ':'))
        try:
            atomic_json(index_path(), data)
            meta = dict(token=token, timestamp=cached['timestamp'], created=now, valid_until=valid_until,
                        digest=hashlib.sha256(data.encode('utf-8')).hexdigest(),
                        program_stamp=file_stamp(index_path()), summary=summaries(programs))
            text = json.dumps(meta, ensure_ascii=False, separators=(',', ':'))
            atomic_json(index_path(meta=True), text)
            xbmcgui.Window(10011).setProperty(INDEX_PROPERTY, text)
        except OSError:
            xbmc.log('xVAULT Radio: prepared index could not be stored', xbmc.LOGWARNING)
    return programs


def menu_summary():
    meta = read_index(summary_only=True)
    if meta:
        return meta['summary']
    programs = catalog()
    meta = read_index(summary_only=True)
    return meta['summary'] if meta else summaries(programs)


def read_cache():
    try:
        win = xbmcgui.Window(10011)
        text = win.getProperty(CACHE_PROPERTY)
        stamp = json.dumps(file_stamp(cache_path()))
        if win.getProperty(RAW_STAMP_PROPERTY) != stamp:
            text = ''
        if not text:
            with xbmcvfs.File(cache_path()) as stream:
                text = stream.read()
        data = json.loads(text)
        age = time.time() - float(data['timestamp'])
        if data.get('schema') != 2 or not 0 <= age <= rb.STALE_TTL or not isinstance(data['rows'], list):
            return None
        # Re-apply the strict filter to every cached entry as well.
        data['rows'] = [r for r in data['rows'] if rb.eligible(r)]
        return data
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return None


def write_cache(rows):
    data = dict(schema=2, timestamp=time.time(), rows=rows)
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    atomic_json(cache_path(), text)
    win = xbmcgui.Window(10011)
    win.setProperty(CACHE_PROPERTY, text)
    win.setProperty(RAW_STAMP_PROPERTY, json.dumps(file_stamp(cache_path())))
    win.setProperty(INDEX_PROPERTY, '')
    return data


def identity_path():
    return os.path.join(os.path.dirname(cache_path()), 'radio-stream-identities.json')


def read_identities():
    try:
        with xbmcvfs.File(identity_path()) as stream:
            data = json.loads(stream.read())
        if data.get('schema') != 1 or not isinstance(data.get('records'), dict):
            return {}
        records, now = {}, time.time()
        for source, record in list(data['records'].items())[:10000]:
            if not isinstance(record, dict) or not rb.stream_key(source):
                continue
            ttl = rb.IDENTITY_TTL if record.get('ok') is True else rb.IDENTITY_RETRY
            if 0 <= now - float(record.get('checked', 0)) < ttl:
                records[source] = record
        return records
    except (OSError, ValueError, TypeError, RuntimeError):
        return {}


def write_identities(records):
    # The service is the single writer. Atomic replacement prevents partial reads.
    target = identity_path()
    with xbmcvfs.File(target + '.tmp', 'w') as stream:
        stream.write(json.dumps(dict(schema=1, records=records), ensure_ascii=False, separators=(',', ':')))
    os.replace(target + '.tmp', target)


def identity_worker():
    from resources.lib import update_maintenance
    monitor, win = xbmc.Monitor(), xbmcgui.Window(10000)
    def stopped():
        return monitor.abortRequested() or update_maintenance.requested()
    while not stopped():
        if monitor.waitForAbort(2):
            break
        if not win.getProperty(IDENTITY_REQUEST) or xbmc.Player().isPlaying():
            continue
        try:
            cached = read_cache()
            if not cached:
                win.clearProperty(IDENTITY_REQUEST)
                continue
            records = read_identities()
            updated, changed = rb.refresh_identities(cached['rows'], records, stopped=stopped, limit=6)
            if changed:
                write_identities(updated)
                if time.time() - cached['timestamp'] < rb.CATALOG_TTL and not stopped():
                    prepare_index(cached, records=updated)
            else:
                win.clearProperty(IDENTITY_REQUEST)
        except Exception as exc:
            xbmc.log('xVAULT Radio identity scan: %s' % type(exc).__name__, xbmc.LOGWARNING)
        # Network probes stay outside directory construction, with idle time per batch.
        for _ in range(15):
            if stopped() or monitor.waitForAbort(1):
                return


def start_background():
    global _identity_thread
    from resources.lib import radio_visualisation
    radio_visualisation.start_monitor()
    if _identity_thread and _identity_thread.is_alive():
        return
    _identity_thread = threading.Thread(target=identity_worker, name='xvault-radio-identities', daemon=True)
    _identity_thread.start()


def catalog(force=False):
    if not force:
        prepared = read_index()
        if prepared is not None:
            return prepared
    cached = read_cache()
    if cached and not force and time.time() - cached['timestamp'] < rb.CATALOG_TTL:
        xbmcgui.Window(10000).setProperty(IDENTITY_REQUEST, '1')
        return prepare_index(cached)
    progress = xbmcgui.DialogProgress()
    progress.create('xVAULT Radio', 'Deutsche Radiosender werden geladen …')
    monitor = xbmc.Monitor()
    try:
        rows = client().catalog(cancelled=lambda: progress.iscanceled() or monitor.abortRequested(),
                                progress=lambda n: progress.update(50, '%d Sendervarianten geladen' % n))
        cached = write_cache(rows)
        xbmcgui.Window(10000).setProperty(IDENTITY_REQUEST, '1')
        return prepare_index(cached)
    except rb.Cancelled:
        raise
    except rb.RadioError:
        if cached:
            notify('Radio Browser nicht erreichbar. Senderliste vom %s.' %
                   time.strftime('%d.%m. %H:%M', time.localtime(cached['timestamp'])))
            return prepare_index(cached, offline=True)
        raise
    finally:
        progress.close()


def setting_index(key, size):
    try:
        return max(0, min(size - 1, int(addon().getSetting(key) or '0')))
    except ValueError:
        return 0


def sort_order():
    return SORTS[setting_index('radio.sort', len(SORTS))]


def stored(key):
    try:
        value = json.loads(addon().getSetting(key) or '{}')
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def remember(key, identifier):
    values = stored(key)
    values[identifier] = time.time()
    values = dict(sorted(values.items(), key=lambda pair: rb.number(pair[1]), reverse=True)[:30])
    addon().setSetting(key, json.dumps(values, separators=(',', ':')))


def favorite_id(favorite):
    try:
        target = urlsplit(favorite.get('path', ''))
        params = parse_qs(target.query)
        if (favorite.get('type') == 'media' and target.scheme == 'plugin'
                and target.netloc == 'plugin.video.xvault' and params.get('action') == ['radioPlay']):
            return rb.station_id(params.get('id', [''])[0])
    except (ValueError, rb.RadioError):
        pass
    return ''


def favorites():
    return {favorite_id(f): f for f in rpc('Favourites.GetFavourites',
            {'properties': ['path', 'thumbnail']}).get('favourites', []) if favorite_id(f)}


def find(identifier, stations):
    identifier = rb.station_id(identifier)
    return next((s for s in stations if any(v['id'] == identifier for v in s['variants'])), None)


def detail(station):
    formats = ', '.join(sorted(set('%s %s kbit/s' % (v['codec'] or 'Audio', v['bitrate'])
                                  for v in station.get('variants', [station]))))
    return ('Deutschland · letzter Streamcheck positiv\n%s\n%s\n%s Votes · %s\n'
            'Letzter erfolgreicher API-Check: %s\nQuelle: Radio Browser' %
            (station.get('family') or 'Einzelsender', ', '.join(station['genres']),
             station['votes'], formats, station.get('checked') or 'unbekannt'))


def music_item(station, label=None, path=None):
    item = xbmcgui.ListItem(label=label or station['name'], path=path or '', offscreen=True)
    info = item.getMusicInfoTag()
    # Kodi's song label mask can use the music title instead of ListItem.label.
    # Keep list votes/favourite markers visible; playback passes no decorated label.
    info.setTitle(label or station['name'])
    info.setArtist(station.get('family') or station['name'])
    info.setGenres(station['genres'])
    info.setComment(detail(station))
    item.setArt({'thumb': station.get('icon') or 'DefaultMusicSources.png',
                 'poster': station.get('icon') or 'DefaultMusicSources.png',
                 'icon': station.get('icon') or 'DefaultMusicSources.png'})
    item.setProperty('IsPlayable', 'true')
    return item


def folder(label, action, **params):
    meta = read_index(summary_only=True)
    revision = [source_token(), meta['created'] if meta else int(time.time() // RETRY_INTERVAL)]
    params['rev'] = hashlib.sha256(json.dumps(revision).encode()).hexdigest()[:16]
    item = xbmcgui.ListItem(label=label, offscreen=True)
    item.setArt({'icon': 'DefaultMusicSources.png', 'thumb': 'DefaultMusicSources.png'})
    xbmcplugin.addDirectoryItem(handle(), url(action, **params), item, True)


def command(label, action, **params):
    item = xbmcgui.ListItem(label=label, offscreen=True)
    item.setProperty('IsPlayable', 'false')
    xbmcplugin.addDirectoryItem(handle(), url(action, **params), item, False)


def finish(title, cache=True):
    xbmcplugin.setPluginCategory(handle(), 'Radio · ' + title)
    xbmcplugin.setContent(handle(), 'songs')
    # Preserve the chosen radio order instead of inheriting a video sort method.
    xbmcplugin.addSortMethod(handle(), xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(handle(), cacheToDisc=cache)


def home():
    folder('Nach Genre', 'radioGenres')
    folder('Nach Senderfamilie', 'radioFamilies')
    folder('Meiste Votes', 'radioList', sort='votes')
    folder('Alle Sender', 'radioList')
    folder('Sender suchen', 'radioSearch')
    folder('Meine Radiofavoriten', 'radioFavorites')
    folder('Zuletzt gehört', 'radioRecent')
    command('Sortierung: ' + SORT_LABELS[setting_index('radio.sort', 3)], 'radioSort')
    command('Senderliste aktualisieren', 'radioRefresh')
    command('Über Radio · Deutschland', 'radioAbout')
    finish('Deutschland')


def show_genres(params):
    summary = menu_summary()
    counts = summary['family_genres'].get(params['family'], {}) if params.get('family') else summary['genres']
    for genre in sorted(counts, key=rb.normalized):
        count = counts[genre]
        folder('%s (%d)' % (genre, count), 'radioList', genre=genre, family=params.get('family', ''))
    finish('Genres')


def show_families(params):
    summary = menu_summary()
    counts = summary['genre_families'].get(params['genre'], {}) if params.get('genre') else summary['families']
    for name in sorted(counts, key=rb.normalized):
        count = counts[name]
        folder('%s (%d)' % (name, count), 'radioList', family=name, genre=params.get('genre', ''))
    singles = summary['singles_by_genre'].get(params['genre'], 0) if params.get('genre') else summary['singles']
    if singles:
        folder('Einzelsender / weitere Sender', 'radioList', single='true', genre=params.get('genre', ''))
    finish('Senderfamilien')


def show_list(params, mode='all'):
    stations = rb.filter_stations(catalog(), genre=params.get('genre', ''),
               sender_family=params.get('family', ''), query=params.get('q', ''),
               sort=params.get('sort') or sort_order())
    favs = favorites()
    if params.get('single') == 'true':
        stations = [s for s in stations if not s['family']]
    if mode in ('favorites', 'recent'):
        ids = favs if mode == 'favorites' else stored('radio.history')
        stations = [s for s in stations if any(v['id'] in ids for v in s['variants'])]
        if mode == 'recent':
            stations.sort(key=lambda s: max(rb.number(ids.get(v['id'])) for v in s['variants']), reverse=True)
    total = len(stations)
    page = min(rb.number(params.get('page')), max(0, (total - 1) // LIST_PAGE_SIZE))
    start = page * LIST_PAGE_SIZE
    visible = stations[start:start + LIST_PAGE_SIZE]
    if params.get('genre') and not params.get('family') and mode == 'all':
        folder('Dieses Genre nach Senderfamilie', 'radioFamilies', genre=params['genre'])
    if params.get('family') and not params.get('genre') and mode == 'all':
        folder('Diese Senderfamilie nach Genre', 'radioGenres', family=params['family'])
    items = []
    for station in visible:
        marked = any(v['id'] in favs for v in station['variants'])
        label = '%s%s · %d Votes' % ('★ ' if marked else '', station['name'], station['votes'])
        item = music_item(station, label)
        identifier = station['id']
        context = [('Aus Radiofavoriten entfernen' if marked else 'Zu Radiofavoriten hinzufügen',
                    'RunPlugin(%s)' % url('radioFavoriteToggle', id=identifier)),
                   ('Für diesen Sender abstimmen', 'RunPlugin(%s)' % url('radioVote', id=identifier)),
                   ('Senderinformationen', 'RunPlugin(%s)' % url('radioInfo', id=identifier))]
        item.addContextMenuItems(context)
        items.append((url('radioPlay', id=identifier), item, False))
    if items:
        xbmcplugin.addDirectoryItems(handle(), items, totalItems=len(items))
    if start + LIST_PAGE_SIZE < total:
        next_params = {key: params[key] for key in ('genre', 'family', 'q', 'single', 'sort') if params.get(key)}
        next_params['page'] = page + 1
        next_action = {'favorites': 'radioFavorites', 'recent': 'radioRecent'}.get(mode, 'radioList')
        folder('Weitere Sender (%d–%d von %d)' % (start + LIST_PAGE_SIZE + 1,
               min(start + 2 * LIST_PAGE_SIZE, total), total), next_action, **next_params)
    if not stations:
        notify('Keine passenden deutschen Radiosender vorhanden.')
    title = '%s%s · %d Sender' % (params.get('family', ''), params.get('genre', ''), total)
    if total > LIST_PAGE_SIZE:
        title += ' · Seite %d' % (page + 1)
    finish(title, cache=False)


def toggle_favorite(identifier):
    station = find(identifier, catalog())
    if not station:
        # A removed station can still be removed from favourites.
        matches = [f for key, f in favorites().items() if key == rb.station_id(identifier)]
        if not matches:
            raise rb.RadioError('Dieser Sender erfüllt den Radiofilter nicht mehr.')
    else:
        ids = {v['id'] for v in station['variants']}
        matches = [f for key, f in favorites().items() if key in ids]
    if matches:
        for favorite in matches:
            rpc('Favourites.AddFavourite', {k: favorite[k] for k in ('title', 'type', 'path', 'thumbnail') if k in favorite})
        notify('Radiofavorit entfernt')
    else:
        rpc('Favourites.AddFavourite', dict(title=station['name'], type='media',
            path=url('radioPlay', id=station['id']), thumbnail=station.get('icon') or 'DefaultMusicSources.png'))
        notify('In Kodi-Favoriten gespeichert')
    xbmc.executebuiltin('Container.Refresh')


def vote(identifier):
    identifier = rb.station_id(identifier)
    stamp = rb.number(stored('radio.votes').get(identifier))
    if 0 <= time.time() - stamp < 600:
        notify('Für diesen Sender wurde gerade abgestimmt. Bitte 10 Minuten warten.')
        return
    api = client()
    station = api.station(identifier)  # Also validates favourites and stale list links.
    if not xbmcgui.Dialog().yesno('Radio Browser', 'Öffentliche Stimme für „%s“ abgeben?\n'
                                 'Radio Browser erlaubt eine Stimme je Sender und IP in 10 Minuten.' % station['name']):
        return
    result = api.vote(identifier)
    if not result['ok']:
        notify('Stimme abgelehnt: ' + str(result.get('message') or 'Bitte später erneut versuchen.'))
        return
    remember('radio.votes', identifier)
    # Invalidate only our own cache; do not invent a new public vote total.
    cached = read_cache()
    if cached:
        cached['timestamp'] = time.time() - rb.CATALOG_TTL - 1
        text = json.dumps(cached, ensure_ascii=False)
        xbmcgui.Window(10011).setProperty(CACHE_PROPERTY, text)
        with xbmcvfs.File(cache_path(), 'w') as stream:
            stream.write(text)
    notify('Deine Stimme wurde bestätigt. Vielen Dank!')
    xbmc.executebuiltin('Container.Refresh')


def probe_stream(station):
    import requests
    try:
        return rb.probe_stream_url(station['url'])
    except requests.RequestException as exc:
        raise rb.RadioError('Stream derzeit nicht erreichbar: ' + type(exc).__name__)


def play(identifier):
    resolved = False
    try:
        identifier = rb.station_id(identifier)
        station = find(identifier, catalog())
        if not station:
            raise rb.RadioError('Sender erfüllt den Deutschland-/Erreichbarkeitsfilter nicht mehr.')
        preferred = ('auto', 'mp3', 'aac')[setting_index('radio.codec', 3)]
        api = client()
        progress = xbmcgui.DialogProgress()
        progress.create('xVAULT Radio', station['name'])
        try:
            for index, candidate in enumerate(rb.stream_variants(station, preferred)[:4]):
                if progress.iscanceled() or xbmc.Monitor().abortRequested():
                    raise rb.Cancelled('Wiedergabe abgebrochen')
                progress.update(index * 25, '%s · %s kbit/s' % (candidate['codec'], candidate['bitrate']))
                fresh = None
                for alias_id in candidate.get('api_aliases', [candidate['id']])[:4]:
                    try:
                        fresh = api.station(alias_id)
                        break
                    except rb.RadioError:
                        continue
                if not fresh:
                    continue
                try:
                    target = probe_stream(fresh)
                except rb.RadioError:
                    continue
                item = music_item(fresh, path=target)
                item.setContentLookup(False)
                mime = {'MP3': 'audio/mpeg', 'AAC': 'audio/aac', 'AAC+': 'audio/aac',
                        'OGG': 'audio/ogg', 'OPUS': 'audio/ogg', 'FLAC': 'audio/flac'}.get(fresh['codec'])
                if fresh.get('hls'):
                    mime = 'application/vnd.apple.mpegurl'
                if mime:
                    item.setMimeType(mime)
                progress.close()
                try:
                    from resources.lib import radio_visualisation
                    radio_visualisation.arm(target)
                except Exception as exc:
                    xbmc.log('xVAULT Radio visualisation unavailable: ' + type(exc).__name__, xbmc.LOGWARNING)
                xbmcplugin.setResolvedUrl(handle(), True, item)
                resolved = True
                remember('radio.history', station['id'])
                threading.Thread(target=api.register_play, args=(fresh['id'],), name='xvault-radio-click', daemon=True).start()
                return
            raise rb.RadioError('Keine erreichbare Streamvariante gefunden. Bitte später erneut versuchen.')
        finally:
            progress.close()
    finally:
        if not resolved:
            xbmcplugin.setResolvedUrl(handle(), False, xbmcgui.ListItem())


def dispatch(action, params):
    folders = {'radioNavigator', 'radioGenres', 'radioFamilies', 'radioList', 'radioSearch',
               'radioFavorites', 'radioRecent'}
    try:
        if action == 'radioNavigator':
            home()
        elif action == 'radioGenres':
            show_genres(params)
        elif action == 'radioFamilies':
            show_families(params)
        elif action == 'radioList':
            show_list(params)
        elif action == 'radioSearch':
            query = params.get('q')
            if query is None:
                query = xbmcgui.Dialog().input('Deutsche Radiosender suchen')
            if query:
                show_list(dict(params, q=query))
            else:
                finish('Suche')
        elif action in ('radioFavorites', 'radioRecent'):
            show_list(params, 'favorites' if action == 'radioFavorites' else 'recent')
        elif action == 'radioPlay':
            play(params.get('id'))
        elif action == 'radioFavoriteToggle':
            toggle_favorite(params.get('id'))
        elif action == 'radioVote':
            vote(params.get('id'))
        elif action == 'radioInfo':
            station = find(params.get('id'), catalog())
            if not station:
                raise rb.RadioError('Sender nicht mehr gelistet')
            xbmcgui.Dialog().textviewer(station['name'], detail(station) + '\n\n' + station['homepage'])
        elif action == 'radioSort':
            choice = xbmcgui.Dialog().select('Radiosender sortieren', list(SORT_LABELS),
                                              preselect=setting_index('radio.sort', 3))
            if choice >= 0:
                addon().setSetting('radio.sort', str(choice))
                xbmc.executebuiltin('Container.Refresh')
        elif action == 'radioRefresh':
            stations = catalog(force=True)
            notify('%d deutsche Radiosender verfügbar' % len(stations))
            xbmc.executebuiltin('Container.Refresh')
        elif action == 'radioAbout':
            xbmcgui.Dialog().textviewer('xVAULT Radio · Radio Browser',
                'Nur Deutschland (DE) und letzter Streamcheck positiv. '
                'Das ist keine Garantie für aktuelle Erreichbarkeit. Deshalb prüfen wir Sender und Stream vor dem Start erneut.\n\n'
                'Genres stammen aus Sender-Tags. Senderfamilien werden anhand bekannter Namen und Domains zugeordnet. '
                'Gleiche Streamziele werden zusammengefasst. Bekannte Spartensender bleiben getrennt. '
                'Weiterleitungen ähnlicher Einträge werden im Leerlauf begrenzt geprüft; Ergebnisse gelten 24 Stunden '
                'und erscheinen beim nächsten Öffnen einer Senderliste. Mehrere Formate bleiben als Alternativen erhalten. '
                'Angezeigte Votes gehören zum führenden API-Eintrag; '
                'sie werden nicht über Varianten addiert.\n\nFavoriten liegen in Kodis Favoritenverwaltung und können vom '
                'vorhandenen xVAULT-Favoritenabgleich übernommen werden. Zuletzt gehört bleibt gerätelokal.\n\n'
                'Radio Browser erhält bei Wiedergabe einen Aufrufzähler; Stimmen werden ausschließlich nach deiner Bestätigung gesendet. '
                'Der Dienst und die Streamserver erhalten deine IP-Adresse. Auch die begrenzten Hintergrundprüfungen '
                'rufen Streamserver auf.\n\nQuelle: https://www.radio-browser.info/')
        else:
            raise rb.RadioError('Unbekannte Radioaktion')
    except rb.Cancelled:
        if action in folders:
            xbmcplugin.endOfDirectory(handle(), succeeded=False, cacheToDisc=False)
    except rb.RadioError as exc:
        notify(str(exc))
        if action in folders:
            xbmcplugin.endOfDirectory(handle(), succeeded=False, cacheToDisc=False)
    except Exception as exc:
        xbmc.log('xVAULT Radio: %s' % type(exc).__name__, xbmc.LOGERROR)
        notify('Radio konnte nicht geladen werden. Details stehen im Kodi-Protokoll.')
        if action in folders:
            xbmcplugin.endOfDirectory(handle(), succeeded=False, cacheToDisc=False)
