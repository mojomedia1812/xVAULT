import json
import sys
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

try:
    from resources.lib import playback_settings
    playback_settings.migrate_mode_setting()
except Exception:
    pass


def _track_menu(menu):
    try:
        from resources.lib import telemetry
        telemetry.menu_opened(menu)
    except Exception:
        pass


def _finish_action():
    try:
        handle = int(sys.argv[1])
        if handle >= 0:
            control.endofdirectory(handle, succeeded=True, cacheToDisc=False)
    except Exception:
        pass


if action is None or action == 'root':
    from resources.lib import updater
    if updater.automatic_updates_enabled():
        from resources.lib import repository
        repository.ensure_xvault_repository()
        if not updater.check_for_update():
            sys.exit()
    try:
        from resources.lib import first_install
        first_install.apply_playback_defaults_once()
    except Exception:
        pass
    try:
        from resources.lib import tmdbhelper_integration
        tmdbhelper_integration.ensure_player()
    except Exception:
        pass
    from resources.lib import startup_info
    startup_info.show_pending_startup_info()
    try:
        from resources.lib.sync import favorites_sync
        favorites_sync.check_and_push_if_changed(silent=True)
    except Exception:
        pass
    try:
        from resources.lib import linear_tv
        linear_tv.clear_session_health()
    except Exception:
        pass
    _track_menu('root')
    from resources.lib.indexers import navigator
    navigator.navigator().root()

elif action == 'pluginInfo':
    from resources.lib import supportinfo
    supportinfo.pluginInfo()
    _finish_action()

elif action == 'supportUpload':
    from resources.lib import supportinfo
    supportinfo.createSupportPackageAndUpload()
    _finish_action()

elif action == 'movieNavigator':
    _track_menu('movies')
    from resources.lib.indexers import navigator
    navigator.navigator().movies()

elif action == 'tvNavigator':
    _track_menu('tvshows')
    from resources.lib.indexers import navigator
    navigator.navigator().tvshows()

elif action == 'liveTVNavigator':
    _track_menu('livetv')
    from resources.lib import linear_tv
    linear_tv.show_home()

elif action == 'liveTVRefresh':
    from resources.lib import linear_tv
    linear_tv.refresh()

elif action == 'liveTVHealthCheck':
    from resources.lib import linear_tv
    linear_tv.check_channel_health()

elif action == 'liveTVCategory':
    from resources.lib import linear_tv
    linear_tv.show_category(params.get('category'))

elif action == 'liveTVSearch':
    from resources.lib import linear_tv
    linear_tv.show_search(params.get('query'))

elif action == 'liveTVFavorites':
    from resources.lib import linear_tv
    linear_tv.show_favorites()

elif action == 'liveTVFavoriteAdd':
    from resources.lib import linear_tv
    linear_tv.add_favorite(params.get('id'))

elif action == 'liveTVFavoriteRemove':
    from resources.lib import linear_tv
    linear_tv.remove_favorite(params.get('id'))

elif action == 'liveTVPlay':
    from resources.lib import linear_tv
    linear_tv.play(params.get('id'))

elif action == 'liveTVLiteNavigator':
    _track_menu('livetv_lite')
    from resources.lib import linear_tv_lite
    linear_tv_lite.show_home()

elif action == 'liveTVLiteRefresh':
    from resources.lib import linear_tv_lite
    linear_tv_lite.refresh()

elif action == 'liveTVLiteCategory':
    from resources.lib import linear_tv_lite
    linear_tv_lite.show_category(params.get('category'))

elif action == 'liveTVLitePlay':
    from resources.lib import linear_tv_lite
    linear_tv_lite.play(params.get('id'))

elif action == 'toolNavigator':
    _track_menu('tools')
    from resources.lib.indexers import navigator
    navigator.navigator().tools()

elif action == 'downloadNavigator':
    _track_menu('downloads')
    from resources.lib.indexers import navigator
    navigator.navigator().downloads()

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
        # Prefer JD-friendly URLs over pre-resolved CDN/m3u8 URLs.
        if jd_url:
            url = jd_url
            source_url = None
        else:
            url = raw_url
            source_url = None

            if '$$' in url:
                url = url.split('$$')[0]

            if '|' in url:
                base_url, header_str = url.split('|', 1)
                headers = dict(parse_qs(header_str, keep_blank_values=True))
                referer = headers.get('Referer', [''])[0]
                if referer and urlsplit(referer).path not in ('', '/'):
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
    dialog = control.progressDialog
    dialog.create('Medien-Info', 'Löse Stream-URL auf...')
    dialog.update(0)
    from resources.lib import sources
    sources.sources().mediaInfo(source, dialog)

elif action == 'playTMDbHelper':
    from resources.lib import tmdbhelper_player
    tmdbhelper_player.play(params)

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
                url = stream_url
        item.setPath(url)
        xbmc.Player().play(url, item)
    except:
        control.infoDialog("Keinen Video Link gefunden", sound=True, icon='WARNING', time=1000)

elif action == 'telemetryStatus':
    from resources.lib import telemetry
    telemetry.show_status()
    try:
        handle = int(sys.argv[1])
        if handle >= 0:
            control.endofdirectory(handle, succeeded=True, cacheToDisc=False)
    except Exception:
        pass

elif action and action.startswith('sync'):
    from resources.lib.sync import account
    account.dispatch(action)

elif action and action.startswith('trakt'):
    from resources.lib import trakt
    trakt_directory = trakt.dispatch(action, params)
    if not trakt_directory:
        try:
            handle = int(sys.argv[1])
            if handle >= 0:
                control.endofdirectory(handle, succeeded=True, cacheToDisc=False)
        except Exception:
            pass

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
    try:
        from resources.lib import trakt
        trakt.update_watch_status_from_params(params, silent=True)
    except Exception:
        pass
    try:
        from resources.lib.sync import binge_sync
        binge_sync.update_watch_status_from_params(params, push=False)
        binge_sync.push_local(silent=True)
    except Exception:
        pass
    control.execute('Container.Refresh')

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

elif action == 'searchNew':
    from resources.lib import searchDB
    searchDB.search_new(table)

elif action == 'searchClear':
    from resources.lib import searchDB
    searchDB.remove_all_query(table)

elif action == 'searchDelTerm':
    from resources.lib import searchDB
    searchDB.remove_query(name, table)

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

elif action == 'movies':
    from resources.lib.indexers import movies
    movies.movies().get(params)

elif action == 'moviesSearch':
    from resources.lib.indexers import movies
    movies.movies().search()

elif action == 'tvshows': # 'tvshowPage'
    from resources.lib.indexers import tvshows
    tvshows.tvshows().get(params)

elif action == 'tvshowsSearch':
    from resources.lib.indexers import tvshows
    tvshows.tvshows().search()

elif action == 'seasons':
    from resources.lib.indexers import seasons
    seasons.seasons().get(params)  # params

elif action == 'episodes':
    from resources.lib.indexers import episodes
    episodes.episodes().get(params)

elif action == 'playFromHere':
    from resources.lib import seriesqueue
    seriesqueue.start(params)

elif action == 'play':
    try:
        params['_xvault_list_position'] = control.infoLabel('Container().CurrentItem')
        params['_xvault_list_content'] = control.infoLabel('Container.Content')
        params['_xvault_container_path'] = control.infoLabel('Container.FolderPath')
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

elif action == "settings":  # alle Quellen aktivieren / deaktivieren
    from resources import settings
    settings.run(params)

elif action == 'addonSettings':
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
