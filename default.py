
# 2023-05-10
# edit 2025-06-12

import sys, json
from urllib.parse import parse_qs, urlsplit
from resources.lib import dependencies

if not dependencies.ensure_all_dependencies():
    sys.exit()

from resources.lib import control

params = dict(control.parse_qsl(control.urlsplit(sys.argv[2]).query))

action = params.get('action')
name = params.get('name')
table = params.get('table')
title = params.get('title')
source = params.get('source')

# ------ navigator --------------
if action == None or action == 'root':
    from resources.lib import repository
    repository.ensure_xvault_repository()
    from resources.lib import updater
    if not updater.check_for_update():
        sys.exit()
    from resources.lib import startup_info
    startup_info.show_pending_startup_info()
    from resources.lib.indexers import navigator
    navigator.navigator().root()

elif action == 'pluginInfo':
    from resources.lib import supportinfo
    supportinfo.pluginInfo()

elif action == 'movieNavigator':
    from resources.lib.indexers import navigator
    navigator.navigator().movies()

elif action == 'tvNavigator':
    from resources.lib.indexers import navigator
    navigator.navigator().tvshows()

elif action == 'toolNavigator':
    from resources.lib.indexers import navigator
    navigator.navigator().tools()

elif action == 'downloadNavigator':
    from resources.lib.indexers import navigator
    navigator.navigator().downloads()

elif action == 'liveTVNavigator':
    from resources.lib.indexers import navigator
    navigator.navigator().live_tv()

elif action == 'm3uLiveNavigator':
    from resources.lib import m3u_live
    m3u_live.list_playlists()

elif action == 'm3uLiveList':
    from resources.lib import m3u_live
    m3u_live.list_channels(params.get('playlist'))

elif action == 'm3uLiveExportAll':
    from resources.lib import m3u_live
    m3u_live.export_all()

elif action == 'm3uLiveExport':
    from resources.lib import m3u_live
    m3u_live.export_playlist(params.get('playlist'))

elif action and action.startswith('vavoo_'):
    from resources.lib import vavooto
    vavooto.dispatch(params)

# -------------------------------------------
elif action == 'download':
    image = params.get('image')
    from resources.lib import downloader
    from resources.lib import sources
    try: downloader.download(name, image, sources.sources().sourcesResolve(json.loads(source)[0], True))
    except: pass

elif action in ('sendToJD', 'sendToJD2', 'sendToMyJD', 'sendToPyLoad'):
    item = json.loads(source)[0]
    raw_url = item.get('url', '')
    jd_url = item.get('jd_url', '')
    if raw_url:
        # Prefer JD-friendly URL (e.g. kinoger.ru -> VOE) over pre-resolved
        # CDN/m3u8 URLs with time-limited tokens and header requirements.
        if jd_url:
            url = jd_url
            source_url = None
        else:
            url = raw_url
            source_url = None

            # Strip resolveurl's $$referer suffix (e.g. "https://vidhide.com/e/abc$$https://filmpalast.to/")
            if '$$' in url:
                url = url.split('$$')[0]

            # Handle Kodi-style |headers (e.g. "https://cdn.com/v.mp4|Referer=...&Origin=...")
            if '|' in url:
                base_url, header_str = url.split('|', 1)
                headers = dict(parse_qs(header_str, keep_blank_values=True))
                referer = headers.get('Referer', [''])[0]
                if referer and urlsplit(referer).path not in ('', '/'):
                    # Referer has a real path — likely a hoster page JD can resolve
                    url = referer
                else:
                    url = base_url
                    if referer:
                        source_url = referer

        if action == 'sendToJD':
            from resources.lib.handler.jdownloaderHandler import cJDownloaderHandler
            cJDownloaderHandler().sendToJDownloader(url)
        elif action == 'sendToJD2':
            from resources.lib.handler.jdownloader2Handler import cJDownloader2Handler
            cJDownloader2Handler().sendToJDownloader2(url)
        elif action == 'sendToMyJD':
            from resources.lib.handler.myjdownloaderHandler import cMyJDownloaderHandler
            cMyJDownloaderHandler().sendToMyJDownloader(url, name, source_url)
        elif action == 'sendToPyLoad':
            from resources.lib.handler.pyLoadHandler import cPyLoadHandler
            cPyLoadHandler().sendToPyLoad(name, url)

elif action == 'mediaInfo':
    import xbmcgui
    dialog = xbmcgui.DialogProgress()
    dialog.create('Medien-Info', 'Löse Stream-URL auf...')
    dialog.update(0)
    from resources.lib import sources
    sources.sources().mediaInfo(source, dialog)

elif action == 'playExtern':
    import json
    if not control.visible(): control.busy()
    try:
        sysmeta = {}
        for key, value in params.items():
            if key == 'action': continue
            elif key == 'year' or key == 'season' or key == 'episode': value = int(value)
            if value == 0: continue
            sysmeta.update({key : value})
        if int(params.get('season')) == 0:
            mediatype = 'movie'
        else:
            mediatype = 'tvshow'
        sysmeta.update({'mediatype': mediatype})
        # if control.getSetting('hosts.mode') == '2':
        #     sysmeta.update({'select': '2'})
        # else:
        #     sysmeta.update({'select': '1'})
        sysmeta.update({'select': control.getSetting('hosts.mode')})
        sysmeta = json.dumps(sysmeta)
        params.update({'sysmeta': sysmeta})
        from resources.lib import sources
        sources.sources().play(params)
    except:
        pass

elif action == 'playURL':
    try:
        import resolveurl
        import xbmcgui, xbmc
        #url = 'https://streamvid.net/embed-uhgo683xes41'
        #url = 'https://moflix-stream.click/v/gcd0aueegeia'
        url = xbmcgui.Dialog().input("URL Input")
        hmf = resolveurl.HostedMediaFile(url=url, include_disabled=True, include_universal=False)
        try:
            if hmf.valid_url(): url = hmf.resolve()
        except:
            pass
        item = xbmcgui.ListItem('URL-direkt')
        kodiver = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
        if ".m3u8" in url or '.mpd' in url:
            item.setProperty("inputstream", "inputstream.adaptive")
            if '.mpd' in url:
                if kodiver < 21: item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
                item.setMimeType('application/dash+xml')
            else:
                if kodiver < 21: item.setProperty('inputstream.adaptive.manifest_type', 'hls')
                item.setMimeType("application/vnd.apple.mpegurl")
            item.setContentLookup(False)
            if '|' in url:
                stream_url, strhdr = url.split('|')
                item.setProperty('inputstream.adaptive.stream_headers', strhdr)
                if kodiver > 19: item.setProperty('inputstream.adaptive.manifest_headers', strhdr)
                # item.setPath(stream_url)
                url = stream_url
        item.setPath(url)
        xbmc.Player().play(url, item)
    except:
        #print('Kein Video Link gefunden')
        control.infoDialog("Keinen Video Link gefunden", sound=True, icon='WARNING', time=1000)

elif action == 'liveTV':
    control.execute('ActivateWindow(TVChannels)')

elif action == 'vavooTV':
    from resources.lib import vavooto
    vavooto.open_root()

elif action == 'vavooFavorites':
    from resources.lib import vavooto
    vavooto.open_favorites()

elif action == 'vavooSettings':
    from resources.lib import vavooto
    vavooto.open_settings()

elif action == 'vavooMakeM3U':
    from resources.lib import vavooto
    vavooto.make_m3u()

elif action == 'playTrailer':
    try:
        from resources.lib.trailer import playTrailer
        playTrailer(
            tmdb_id   = params.get('tmdb_id', ''),
            mediatype = params.get('mediatype', 'movie'),
            title     = params.get('title', ''),
            year      = params.get('year', ''),
            poster    = params.get('poster', ''),
        )
    except Exception:
        control.infoDialog('Trailer-Suche fehlgeschlagen', sound=True, icon='WARNING')

elif action == 'UpdatePlayCount':
    from resources.lib import playcountDB
    playcountDB.UpdatePlaycount(params)
    control.execute('Container.Refresh')

# listings -------------------------------
elif action == 'listings':
    from resources.lib.indexers import listings
    listings.listings().get(params)

elif action == 'movieYears':
    from resources.lib.indexers import listings
    listings.listings().movieYears()

elif action == 'movieGenres':
    from resources.lib.indexers import listings
    listings.listings().movieGenres()

elif action == 'tvGenres':
    from resources.lib.indexers import listings
    listings.listings().tvGenres()

# search ----------------------
elif action == 'searchNew':
    from resources.lib import searchDB
    searchDB.search_new(table)

elif action == 'searchClear':
    from resources.lib import searchDB
    searchDB.remove_all_query(table)
    # if len(searchDB.getSearchTerms()) == 0:
    #     control.execute('Action(ParentDir)')

elif action == 'searchDelTerm':
    from resources.lib import searchDB
    searchDB.remove_query(name, table)
    # if len(searchDB.getSearchTerms()) == 0:
    #     control.execute('Action(ParentDir)')

# person ----------------------
elif action == 'person':
    from resources.lib.indexers import person
    person.person().get(params)

elif action == 'personSearch':
    from resources.lib.indexers import person
    person.person().search()

elif action == 'personCredits':
    from resources.lib.indexers import person
    person.person().getCredits(params)

elif action == 'playfromPerson':
    if not control.visible(): control.busy()
    sysmeta = json.loads(params['sysmeta'])
    if sysmeta['mediatype'] == 'movie':
        from resources.lib.indexers import movies
        sysmeta = movies.movies().super_meta(sysmeta['tmdb_id'])
        sysmeta = json.dumps(sysmeta)
    else:
        from resources.lib.indexers import tvshows
        sysmeta = tvshows.tvshows().super_meta(sysmeta['tmdb_id'])
        sysmeta = control.quote_plus(json.dumps(sysmeta))

    params.update({'sysmeta': sysmeta})
    from resources.lib import sources
    sources.sources().play(params)

# movies ----------------------
elif action == 'movies':
    from resources.lib.indexers import movies
    movies.movies().get(params)

elif action == 'moviesSearch':
    from resources.lib.indexers import movies
    movies.movies().search()

# tvshows ---------------------------------
elif action == 'tvshows': # 'tvshowPage'
    from resources.lib.indexers import tvshows
    tvshows.tvshows().get(params)

elif action == 'tvshowsSearch':
    from resources.lib.indexers import tvshows
    tvshows.tvshows().search()

# seasons ---------------------------------
elif action == 'seasons':
    from resources.lib.indexers import seasons
    seasons.seasons().get(params)  # params

# episodes ---------------------------------
elif action == 'episodes':
    from resources.lib.indexers import episodes
    episodes.episodes().get(params)

elif action == 'playFromHere':
    from resources.lib import seriesqueue
    seriesqueue.start(params)

# sources ---------------------------------
elif action == 'play':
    try:
        params['_xvault_list_position'] = control.infoLabel('Container().CurrentItem')
        params['_xvault_list_content'] = control.infoLabel('Container.Content')
    except:
        pass
    if not control.visible(): control.busy()
    from resources.lib import sources
    sources.sources().play(params)

elif action == 'addItem':
    from resources.lib import sources
    sources.sources().addItem(title)

elif action == 'playItem':
    if not control.visible(): control.busy()
    from resources.lib import sources
    sources.sources().playItem(title, source)

# Settings ------------------------------
elif action == "settings":  # alle Quellen aktivieren / deaktivieren
    from resources import settings
    settings.run(params)

elif action == 'addonSettings':
    # query = None
    query = params.get('query')
    control.openSettings(query)

elif action == 'resetSettings':
    status = control.resetSettings()
    if status:
        control.reload_profile()
        control.sleep(500)
        control.execute('RunAddon("%s")' % control.addonId)
        
elif action == 'resolverSettings':
    import resolveurl as resolver
    resolver.display_settings()

# try:
#     import pydevd
#     if pydevd.connected: pydevd.kill_all_pydev_threads()
# except:
#     pass
# finally:
#     exit()
