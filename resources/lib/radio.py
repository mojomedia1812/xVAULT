"""Native Kodi radio directories, music playback and Kodi favourites."""
import json
import os
import sys
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import requests
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


def read_cache():
    try:
        text = xbmcgui.Window(10011).getProperty(CACHE_PROPERTY)
        if not text:
            with xbmcvfs.File(cache_path()) as stream:
                text = stream.read()
        data = json.loads(text)
        age = time.time() - float(data['timestamp'])
        if data.get('schema') != 2 or not 0 <= age <= rb.STALE_TTL or not isinstance(data['rows'], list):
            return None
        # Re-apply the strict filter to every cached entry as well.
        data['rows'] = [r for r in data['rows'] if rb.clean_station(r)]
        return data
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return None


def write_cache(rows):
    data = dict(schema=2, timestamp=time.time(), rows=rows)
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    xbmcgui.Window(10011).setProperty(CACHE_PROPERTY, text)
    with xbmcvfs.File(cache_path(), 'w') as stream:
        stream.write(text)
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


def group_catalog(rows):
    xbmcgui.Window(10000).setProperty(IDENTITY_REQUEST, '1')
    return rb.group_stations(rows, read_identities())


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
            if not rb.identity_candidates(cached['rows'], updated):
                win.clearProperty(IDENTITY_REQUEST)
        except Exception as exc:
            xbmc.log('xVAULT Radio identity scan: %s' % type(exc).__name__, xbmc.LOGWARNING)
        # Network probes stay outside directory construction, with idle time per batch.
        if monitor.waitForAbort(15):
            break


def start_background():
    global _identity_thread
    if _identity_thread and _identity_thread.is_alive():
        return
    _identity_thread = threading.Thread(target=identity_worker, name='xvault-radio-identities', daemon=True)
    _identity_thread.start()


def catalog(force=False):
    cached = read_cache()
    if cached and not force and time.time() - cached['timestamp'] < rb.CATALOG_TTL:
        return group_catalog(cached['rows'])
    progress = xbmcgui.DialogProgress()
    progress.create('xVAULT Radio', 'Deutsche Radiosender werden geladen …')
    monitor = xbmc.Monitor()
    try:
        rows = client().catalog(cancelled=lambda: progress.iscanceled() or monitor.abortRequested(),
                                progress=lambda n: progress.update(50, '%d Sendervarianten geladen' % n))
        write_cache(rows)
        return group_catalog(rows)
    except rb.Cancelled:
        raise
    except rb.RadioError:
        if cached:
            notify('Radio Browser nicht erreichbar. Senderliste vom %s.' %
                   time.strftime('%d.%m. %H:%M', time.localtime(cached['timestamp'])))
            return group_catalog(cached['rows'])
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
    item = xbmcgui.ListItem(label=label or station['name'], path=path or '')
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
    item = xbmcgui.ListItem(label=label)
    item.setArt({'icon': 'DefaultMusicSources.png', 'thumb': 'DefaultMusicSources.png'})
    xbmcplugin.addDirectoryItem(handle(), url(action, **params), item, True)


def command(label, action, **params):
    item = xbmcgui.ListItem(label=label)
    item.setProperty('IsPlayable', 'false')
    xbmcplugin.addDirectoryItem(handle(), url(action, **params), item, False)


def finish(title):
    xbmcplugin.setPluginCategory(handle(), 'Radio · ' + title)
    xbmcplugin.setContent(handle(), 'songs')
    # Preserve the chosen radio order instead of inheriting a video sort method.
    xbmcplugin.addSortMethod(handle(), xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(handle(), cacheToDisc=False)


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
    stations = rb.filter_stations(catalog(), sender_family=params.get('family', ''))
    names = sorted({g for s in stations for g in s['genres']}, key=rb.normalized)
    for genre in names:
        count = sum(genre in s['genres'] for s in stations)
        folder('%s (%d)' % (genre, count), 'radioList', genre=genre, family=params.get('family', ''))
    finish('Genres')


def show_families(params):
    stations = rb.filter_stations(catalog(), genre=params.get('genre', ''))
    for name in sorted({s['family'] for s in stations if s['family']}, key=rb.normalized):
        count = sum(s['family'] == name for s in stations)
        folder('%s (%d)' % (name, count), 'radioList', family=name, genre=params.get('genre', ''))
    if any(not s['family'] for s in stations):
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
    if params.get('genre') and not params.get('family') and mode == 'all':
        folder('Dieses Genre nach Senderfamilie', 'radioFamilies', genre=params['genre'])
    if params.get('family') and not params.get('genre') and mode == 'all':
        folder('Diese Senderfamilie nach Genre', 'radioGenres', family=params['family'])
    items = []
    for station in stations:
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
    if not stations:
        notify('Keine passenden deutschen Radiosender vorhanden.')
    finish('%s%s · %d Sender' % (params.get('family', ''), params.get('genre', ''), len(stations)))


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
    return rb.probe_stream_url(station['url'])


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
                except (rb.RadioError, requests.RequestException):
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
