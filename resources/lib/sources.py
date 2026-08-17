# edit 2025-06-12
import sys
import base64
import hashlib
import inspect
import os
import re, json, random, time
import threading
from concurrent.futures import ThreadPoolExecutor
from html import unescape as html_unescape
from urllib.parse import urlencode, urljoin, urlparse
from resources.lib import log_utils, utils, control, playback_settings
from resources.lib.control import py2_decode, py2_encode, quote_plus, parse_qsl
import resolveurl as resolver
# from functools import reduce
from resources.lib.control import getKodiVersion

if int(getKodiVersion()) >= 20: from infotagger.listitem import ListItemInfoTag

SOURCE_CACHE_TTL = 30 * 60
SOURCE_CACHE_STALE_TTL = 6 * 60 * 60
SOURCE_CACHE_LIMIT = 60
SOURCE_CONTEXT_TTL = 6 * 60 * 60
SOURCE_CONTEXT_LIMIT = 80
SERIES_CACHE_LIMIT = 200
PROVIDER_ERROR_TTL = 5 * 60
PROVIDER_TIMEOUT_TTL = 10 * 60
SOURCE_RESOLVE_TIMEOUT = 30
AUTOPLAY_PREFETCH_LIMIT = 5

# für self.sysmeta - zur späteren verwendung als meta
_params = dict(parse_qsl(sys.argv[2].replace('?',''))) if len(sys.argv) > 1 else dict()

class _XvaultThreadPoolExecutor(ThreadPoolExecutor):
    def _adjust_thread_count(self):
        try:
            if self._idle_semaphore.acquire(timeout=0):
                return

            import weakref
            from concurrent.futures import thread as _thread

            def weakref_cb(_, q=self._work_queue):
                q.put(None)

            num_threads = len(self._threads)
            if num_threads >= self._max_workers:
                return

            thread_name = '%s_%d' % (self._thread_name_prefix or 'xvault-worker', num_threads)
            worker_params = len(inspect.signature(_thread._worker).parameters)
            if worker_params == 3 and hasattr(self, '_create_worker_context'):
                worker_args = (weakref.ref(self, weakref_cb), self._create_worker_context(), self._work_queue)
            else:
                worker_args = (weakref.ref(self, weakref_cb), self._work_queue, self._initializer, self._initargs)
            worker = threading.Thread(
                name=thread_name,
                target=_thread._worker,
                args=worker_args
            )
            worker.daemon = True
            worker.start()
            self._threads.add(worker)
        except:
            return super(_XvaultThreadPoolExecutor, self)._adjust_thread_count()

class sources:
    def __init__(self):
        self.getConstants()
        self.sources = []
        self.hostDict = []
        self.current = int(time.time())
        if 'sysmeta' in _params: self.sysmeta = _params['sysmeta'] # string zur späteren verwendung als meta
        self.watcher = False
        self.max_workers = self._adaptiveWorkerCount()
        self.executor = self._newExecutor()
        self.executor_shutdown = False
        self.url = None
        self.last_source_error = 'no_sources'

    def _newExecutor(self):
        return _XvaultThreadPoolExecutor(max_workers=getattr(self, 'max_workers', self._adaptiveWorkerCount()))

    def _ensureExecutor(self):
        if getattr(self, 'executor_shutdown', False):
            self.executor = self._newExecutor()
            self.executor_shutdown = False

    def _cancelFutures(self, futures):
        try:
            for future in list(futures or []):
                try:
                    future.cancel()
                except:
                    pass
        except:
            pass

    def _adaptiveWorkerCount(self):
        try:
            if control.condVisibility('System.Platform.Android'):
                return 8
            if control.condVisibility('System.Platform.Linux'):
                return 10
            if control.condVisibility('System.Platform.Windows'):
                return 18
        except:
            pass
        return 12

    def _shutdownExecutor(self):
        try:
            if getattr(self, 'executor_shutdown', False):
                return
            try:
                self.executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                self.executor.shutdown(False)
            self.executor_shutdown = True
        except:
            pass

    def get(self, params):
        data = json.loads(params['sysmeta'])
        self.mediatype = data.get('mediatype')
        self.aliases = data.get('aliases') if 'aliases' in data else []

        title = py2_encode(data.get('title'))
        originaltitle = py2_encode(data.get('originaltitle')) if 'originaltitle' in data else title
        year = data.get('year') if 'year' in data else None
        imdb = data.get('imdb_id') if 'imdb_id' in data else data.get('imdbnumber') if 'imdbnumber' in data else None
        if not imdb and 'imdb' in data: imdb = data.get('imdb')
        tmdb = data.get('tmdb_id') if 'tmdb_id' in data else None
        #if tmdb and not imdb: print 'hallo' #TODO
        season = data.get('season') if 'season' in data else 0
        episode = data.get('episode') if 'episode' in data else 0
        premiered = data.get('premiered') if 'premiered' in data else None
        episode_title = data.get('episode_title') if 'episode_title' in data else None
        episode_premiered = data.get('episode_premiered') if 'episode_premiered' in data else None
        meta = params['sysmeta']
        # Stored metadata can outlive setting changes, especially in favorites or
        # external links. Only an explicit route parameter may override the
        # current global Standard-Aktion setting.
        select = playback_settings.normalize_mode(params.get('select'), None)
        return title, year, imdb, season, episode, originaltitle, premiered, meta, select, episode_title, episode_premiered

    def play(self, params):
        title, year, imdb, season, episode, originaltitle, premiered, meta, select, episode_title, episode_premiered = self.get(params)
        try:
            try:
                meta_data = json.loads(meta)
                list_position = int(params.get('_xvault_list_position') or control.infoLabel('Container().CurrentItem') or 0)
                if list_position >= 0:
                    meta_data['_xvault_list_position'] = list_position
                    list_content = params.get('_xvault_list_content') or control.infoLabel('Container.Content')
                    container_path = params.get('_xvault_container_path') or control.infoLabel('Container.FolderPath')
                    if list_content:
                        meta_data['_xvault_list_content'] = list_content
                    if container_path:
                        meta_data['_xvault_container_path'] = container_path
                    meta = json.dumps(meta_data)
                    params['sysmeta'] = meta
            except:
                pass

            url = None
            select = playback_settings.get_mode() if select == None else playback_settings.normalize_mode(select)
            select = self._enforceStreamLanguageSelectionMode(select)
            if select == None: return

            #Liste der gefundenen Streams
            self.last_source_error = 'no_sources'
            self._telemetryEvent('source_collection_started', 'sources', self._sourceTelemetryPayload())
            items = self.getSources(title, year, imdb, season, episode, originaltitle, premiered, episode_title=episode_title, episode_premiered=episode_premiered)
            self._telemetryEvent('source_collection_finished', 'sources', self._sourceTelemetryPayload(len(items)))
            ## unnötig
            #select = '1' if control.getSetting('downloads') == 'true' and not (control.getSetting('download.movie.path') == '' or control.getSetting('download.tv.path') == '') else select

            # # TODO überprüfen wofür mal gedacht
            # if control.window.getProperty('PseudoTVRunning') == 'True':
            #     return control.resolveUrl(int(sys.argv[1]), True, control.item(path=str(self.sourcesDirect(items))))

            if len(items) > 0:
                # Auswahl Verzeichnis
                if select == '1':
                    control.window.clearProperty(self.itemsProperty)
                    control.window.setProperty(self.itemsProperty, json.dumps(items))
                    
                    control.window.clearProperty(self.metaProperty)
                    control.window.setProperty(self.metaProperty, meta)
                    if 'plugin' in control.infoLabel('Container.PluginName'):
                        control.sleep(2)
                        return control.execute('Container.Update(%s?action=addItem&title=%s)' % (sys.argv[0], quote_plus(title)))
                    return self.addItem(title)
                # Auswahl Dialog
                elif select == '0':
                    url = self.sourcesDialog(items)
                    if  url == 'close://': return
                # Autoplay
                else:
                    try: autoplay_meta = json.loads(meta)
                    except: autoplay_meta = meta
                    if self.sourcesAutoplay(items, title, autoplay_meta):
                        return
                    self.last_source_error = 'autoplay_failed'
                    url = None

            if url == None: return self.errorForSources(getattr(self, 'last_source_error', 'no_sources'))

            try: meta = json.loads(meta)
            except: pass
            meta = self._mergeSelectedStreamMeta(meta, getattr(self, 'selectedSourceItem', None))

            self._shutdownExecutor()
            from resources.lib.player import player
            if not player().run(title, url, meta):
                self.errorForSources('playback_start_failed')
        except Exception as e:
            log_utils.log('Error %s' % str(e), log_utils.LOGERROR)
        finally:
            self._shutdownExecutor()

    def _enforceStreamLanguageSelectionMode(self, select):
        if getattr(self, 'mediatype', None) not in ['movie', 'tvshow']:
            return select
        if control.getSetting('hosts.language') != '0':
            return select
        if select == '':
            select = '2'
        if str(select) != '2':
            return select

        current_mode = playback_settings.get_mode()
        if current_mode in ['0', '1']:
            return current_mode

        choice = control.selectDialog(
            ['Dialog', 'Verzeichnis'],
            'Stream-Sprache: Alle'
        )
        if choice < 0:
            control.infoDialog('Autoplay ist bei Sprache Alle nicht moeglich.', icon='WARNING')
            return None

        select = str(choice)
        playback_settings.set_mode(select)
        control.infoDialog('Standard-Aktion wurde auf %s gesetzt.' % (['Dialog', 'Verzeichnis'][choice]), icon='INFO')
        return select


    def _sourceTelemetryPayload(self, source_count=None, error_group=None):
        payload = {
            'media_type': getattr(self, 'mediatype', 'unknown'),
            'playback_mode': playback_settings.get_mode(),
        }
        if source_count is not None:
            payload['source_count'] = int(source_count)
        if error_group:
            payload['error_group'] = error_group
        return payload


    def _telemetryEvent(self, event_name, event_group='sources', payload=None):
        try:
            from resources.lib import telemetry
            telemetry.event(event_name, event_group, payload or {})
        except:
            pass


# Liste gefundene Streams Indexseite|Hoster
    def addItem(self, title):
        control.playlist.clear()

        items = control.window.getProperty(self.itemsProperty)
        items = json.loads(items)
        if items == None or len(items) == 0: control.idle() ; sys.exit()

        sysaddon = sys.argv[0]
        syshandle = int(sys.argv[1])
        systitle = sysname = quote_plus(title)

        meta = control.window.getProperty(self.metaProperty)
        meta = json.loads(meta)
        source_context = self._writeSourceContext(meta)
#TODO
        if meta['mediatype'] == 'movie':
            # downloads = True if control.getSetting('downloads') == 'true' and control.exists(control.translatePath(control.getSetting('download.movie.path'))) else False
            downloads = True if control.getSetting('downloads') == 'true' and control.getSetting('download.movie.path') else False
        else:
            # downloads = True if control.getSetting('downloads') == 'true' and control.exists(control.translatePath(control.getSetting('download.tv.path'))) else False
            downloads = True if control.getSetting('downloads') == 'true' and control.getSetting('download.tv.path') else False

        addonPoster, addonBanner = control.addonPoster(), control.addonBanner()
        addonFanart, settingFanart = control.addonFanart(), control.getSetting('fanart')

        if 'backdrop_url' in meta and 'http' in meta['backdrop_url']: fanart = meta['backdrop_url']
        elif 'fanart' in meta and 'http' in meta['fanart']: fanart = meta['fanart']
        else: fanart = addonFanart

        if 'cover_url' in meta and 'http' in meta['cover_url']: poster = meta['cover_url']
        elif 'poster' in meta and 'http' in meta['poster']: poster = meta['poster']
        else:  poster = addonPoster
        sysimage = poster

        if 'season' in meta and 'episode' in meta:
            sysname += quote_plus(' S%02dE%02d' % (int(meta['season']), int(meta['episode'])))
        elif 'year' in meta:
            sysname += quote_plus(' (%s)' % meta['year'])

        for i in range(len(items)):
            try:
                label = items[i]['label']
                syssource = quote_plus(json.dumps([items[i]]))

                item = control.item(label=label, offscreen=True)
                item.setProperty('IsPlayable', 'true')
                item.setArt({'poster': poster, 'banner': addonBanner})
                if settingFanart == 'true': item.setProperty('Fanart_Image', fanart)

                cm = []
                if downloads:
                    cm.append(("Download", 'RunPlugin(%s?action=download&name=%s&image=%s&source=%s)' % (sysaddon, sysname, sysimage, syssource)))
                if control.getSetting('jd_enabled') == 'true':
                    cm.append(("Sende zum JDownloader", 'RunPlugin(%s?action=sendToJD&name=%s&source=%s)' % (sysaddon, sysname, syssource)))
                if control.getSetting('jd2_enabled') == 'true':
                    cm.append(("Sende zum JDownloader2", 'RunPlugin(%s?action=sendToJD2&name=%s&source=%s)' % (sysaddon, sysname, syssource)))
                if control.getSetting('myjd_enabled') == 'true':
                    cm.append(("Sende zu My.JDownloader", 'RunPlugin(%s?action=sendToMyJD&name=%s&source=%s)' % (sysaddon, sysname, syssource)))
                if control.getSetting('pyload_enabled') == 'true':
                    cm.append(("Sende zu PyLoad", 'RunPlugin(%s?action=sendToPyLoad&name=%s&source=%s)' % (sysaddon, sysname, syssource)))
                cm.append(("Medien-Info", 'RunPlugin(%s?action=mediaInfo&source=%s)' % (sysaddon, syssource)))
                cm.append(('Einstellungen', 'RunPlugin(%s?action=addonSettings)' % sysaddon))
                item.addContextMenuItems(cm)

                url = "%s?action=playItem&title=%s&source=%s" % (sysaddon, systitle, syssource)
                if source_context:
                    url = "%s&context=%s" % (url, quote_plus(source_context))

                # ## Notwendig für Library Exporte ##
                # ## Amazon Scraper Details ##
                # if "amazon" in label.lower():
                #     aid = re.search(r'asin%3D(.*?)%22%2C', url)
                #     url = "plugin://plugin.video.amazon-test/?mode=PlayVideo&asin=" + aid.group(1)

                ##https: // codedocs.xyz / AlwinEsch / kodi / group__python__xbmcgui__listitem.html  # ga0b71166869bda87ad744942888fb5f14

                name = '%s%sStaffel: %s   Episode: %s' % (title, "\n", meta['season'], meta['episode']) if 'season' in meta else title
                plot = meta['plot'] if 'plot' in meta and len(meta['plot'].strip()) >= 1 else ''
                plot = '[COLOR blue]%s[/COLOR]%s%s' % (name, "\n\n", py2_encode(plot))

                if 'duration' in meta:
                    infolable = {'plot': plot,'duration': meta['duration']}
                else:
                    infolable = {'plot': plot}

                # TODO
                # if 'cast' in meta and meta['cast']: item.setCast(meta['cast'])
                # # # remove unsupported InfoLabels
                meta.pop('cast', None)  # ersetzt durch item.setCast(i['cast'])
                meta.pop('number_of_seasons', None)
                meta.pop('imdb_id', None)
                meta.pop('tvdb_id', None)
                meta.pop('tmdb_id', None)

                ## Quality Video Stream from source.append quality - items[i]['quality']
                video_streaminfo ={}
                if "4k" in items[i]['quality'].lower():
                    video_streaminfo.update({'width': 3840, 'height': 2160})
                elif "1080p" in items[i]['quality'].lower():
                    video_streaminfo.update({'width': 1920, 'height': 1080})
                elif "hd" in items[i]['quality'].lower() or "720p" in items[i]['quality'].lower():
                    video_streaminfo.update({'width': 1280,'height': 720})
                else:
                    # video_streaminfo.update({"width": 720, "height": 576})
                    video_streaminfo.update({})

                ## Codec for Video Stream from extra info - items[i]['info']
                if 'hevc' in items[i]['label'].lower():
                    video_streaminfo.update({'codec': 'hevc'})
                elif '265' in items[i]['label'].lower():
                    video_streaminfo.update({'codec': 'h265'})
                elif 'mkv' in items[i]['label'].lower():
                    video_streaminfo.update({'codec': 'mkv'})
                elif 'mp4' in items[i]['label'].lower():
                    video_streaminfo.update({'codec': 'mp4'})
                else:
                    # video_streaminfo.update({'codec': 'h264'})
                    video_streaminfo.update({'codec': ''})

                ## Quality & Channels Audio Stream from extra info - items[i]['info']
                audio_streaminfo = {}
                if 'dts' in items[i]['label'].lower():
                    audio_streaminfo.update({'codec': 'dts'})
                elif 'plus' in items[i]['label'].lower() or 'e-ac3' in items[i]['label'].lower():
                    audio_streaminfo.update({'codec': 'eac3'})
                elif 'dolby' in items[i]['label'].lower() or 'ac3' in items[i]['label'].lower():
                    audio_streaminfo.update({'codec': 'ac3'})
                else:
                    # audio_streaminfo.update({'codec': 'aac'})
                    audio_streaminfo.update({'codec': ''})

                ## Channel update ##
                if '7.1' in items[i].get('info','').lower():
                    audio_streaminfo.update({'channels': 8})
                elif '5.1' in items[i].get('info','').lower():
                    audio_streaminfo.update({'channels': 6})
                else:
                    # audio_streaminfo.update({'channels': 2})
                    audio_streaminfo.update({'channels': ''})

                if int(getKodiVersion()) <= 19:
                    item.setInfo(type='Video', infoLabels=infolable)
                    item.addStreamInfo('video', video_streaminfo)
                    item.addStreamInfo('audio', audio_streaminfo)
                else:
                    info_tag = ListItemInfoTag(item, 'video')
                    info_tag.set_info(infolable)
                    stream_details = {
                        'video': [video_streaminfo],
                        'audio': [audio_streaminfo]}
                    info_tag.set_stream_details(stream_details)
                    # info_tag.set_cast(aActors)

                control.addItem(handle=syshandle, url=url, listitem=item, isFolder=False)
            except:
                pass

        control.content(syshandle, 'videos')
        control.plugincategory(syshandle, control.addonVersion)
        control.endofdirectory(syshandle, cacheToDisc=True)


    def playItem(self, title, source, params=None):
        isDebug = False
        if isDebug: log_utils.log('start playItem', log_utils.LOGWARNING)
        try:
            meta = self._playbackMetaForSourceItem(params or {})
            if not isinstance(meta, dict):
                raise Exception('Wiedergabe-Kontext fehlt')

            header = control.addonInfo('name')
            # control.idle() #ok
            progressDialog = control.progressDialog if control.getSetting('progress.dialog') == '0' else control.progressDialogBG
            progressDialog.create(header, '')
            progressDialog.update(0)

            item = json.loads(source)[0]
            #if isDebug: log_utils.log('playItem 237', log_utils.LOGWARNING)
            if item['source'] == None: raise Exception()
            
            self._ensureExecutor()
            future = self.executor.submit(self.sourcesResolve, item)
            
            waiting_time = 30
            while waiting_time > 0:
                try:
                    if control.abortRequested: return sys.exit()
                    if progressDialog.iscanceled(): return progressDialog.close()
                except:
                    pass
                if future.done(): break
                control.sleep(1)
                waiting_time = waiting_time - 1
                progressDialog.update(int(100 - 100. / 30 * waiting_time), str(item['label']))
                #if isDebug: log_utils.log('playItem 252', log_utils.LOGWARNING)
                if control.condVisibility('Window.IsActive(virtualkeyboard)') or \
                        control.condVisibility('Window.IsActive(yesnoDialog)'):
                        # or control.condVisibility('Window.IsActive(PopupRecapInfoWindow)'):
                    waiting_time = waiting_time + 1  # dont count down while dialog is presented
                if future.done(): break

            try: progressDialog.close()
            except: pass
            if isDebug: log_utils.log('playItem 261', log_utils.LOGWARNING)
            control.execute('Dialog.Close(virtualkeyboard)')
            control.execute('Dialog.Close(yesnoDialog)')

            if isDebug: log_utils.log('playItem url: %s' % self.url, log_utils.LOGWARNING)
            if self.url == None:
                #self.errorForSources()
                return

            meta = self._mergeSelectedStreamMeta(meta, item)
            self._shutdownExecutor()
            from resources.lib.player import player
            if not player().run(title, self.url, meta):
                self.errorForSources('playback_start_failed')
            return self.url
        except Exception as e:
            log_utils.log('Error %s' % str(e), log_utils.LOGERROR)
        finally:
            self._shutdownExecutor()

    def _playbackMetaForSourceItem(self, params):
        context = params.get('context') if isinstance(params, dict) else ''
        meta = self._readSourceContext(context)
        if isinstance(meta, dict):
            return meta

        candidates = []
        if isinstance(params, dict):
            candidates.append(params.get('sysmeta'))
        candidates.append(getattr(self, 'sysmeta', None))
        try:
            candidates.append(control.window.getProperty(self.metaProperty))
        except:
            pass
        for raw in candidates:
            if not raw:
                continue
            try:
                meta = json.loads(raw)
                if isinstance(meta, dict):
                    return meta
            except:
                pass
        return {}

    def _sourceContextFile(self):
        return os.path.join(control.dataPath, 'source_context_v1.json')

    def _compactPlaybackMeta(self, meta):
        if not isinstance(meta, dict):
            return {}
        keep = [
            'title', 'originaltitle', 'year', 'mediatype', 'imdb_id', 'imdbnumber',
            'imdb', 'tmdb_id', 'tvdb_id', 'season', 'episode', 'number_of_seasons',
            'number_of_episodes', 'episode_title', 'episode_premiered', 'premiered',
            'poster', 'fanart', 'backdrop_url', 'plot', 'playcount', 'overlay',
            '_xvault_list_position', '_xvault_list_content', '_xvault_container_path',
            '_xvault_queue_playback', '_xvault_queue_last'
        ]
        return dict((key, meta.get(key)) for key in keep if key in meta and meta.get(key) not in [None, ''])

    def _writeSourceContext(self, meta):
        try:
            compact = self._compactPlaybackMeta(meta)
            if not compact:
                return ''
            raw = json.dumps(compact, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            token = hashlib.sha256(('%s:%s' % (raw, time.time())).encode('utf-8')).hexdigest()[:24]
            payload = self._readSourceContextPayload()
            entries = payload.get('entries') if isinstance(payload.get('entries'), dict) else {}
            now = int(time.time())
            entries[token] = {'timestamp': now, 'meta': compact}
            while len(entries) > SOURCE_CONTEXT_LIMIT:
                oldest = sorted(entries.items(), key=lambda item: int(item[1].get('timestamp', 0)))[0][0]
                entries.pop(oldest, None)
            payload = {'version': 1, 'entries': entries}
            self._writeSourceContextPayload(payload)
            try:
                control.window.setProperty('%s.context.%s' % (self.metaProperty, token), json.dumps(compact))
            except:
                pass
            return token
        except Exception as e:
            log_utils.log('Quellen-Kontext konnte nicht gespeichert werden: %s' % str(e), log_utils.LOGWARNING)
            return ''

    def _readSourceContext(self, token):
        if not token:
            return {}
        try:
            raw = control.window.getProperty('%s.context.%s' % (self.metaProperty, token))
            if raw:
                meta = json.loads(raw)
                if isinstance(meta, dict):
                    return meta
        except:
            pass
        try:
            payload = self._readSourceContextPayload()
            entry = (payload.get('entries') or {}).get(token)
            if not isinstance(entry, dict):
                return {}
            meta = entry.get('meta')
            return meta if isinstance(meta, dict) else {}
        except:
            return {}

    def _readSourceContextPayload(self):
        try:
            path = self._sourceContextFile()
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as handle:
                    payload = json.load(handle)
            else:
                payload = {}
        except:
            payload = {}
        entries = payload.get('entries') if isinstance(payload.get('entries'), dict) else {}
        now = int(time.time())
        for key, entry in list(entries.items()):
            try:
                if now - int(entry.get('timestamp', 0)) > SOURCE_CONTEXT_TTL:
                    entries.pop(key, None)
            except:
                entries.pop(key, None)
        return {'version': 1, 'entries': entries}

    def _writeSourceContextPayload(self, payload):
        try:
            if not os.path.exists(control.dataPath):
                os.makedirs(control.dataPath)
            path = self._sourceContextFile()
            tmp_path = path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False)
            try:
                os.replace(tmp_path, path)
            except:
                if os.path.exists(path):
                    os.remove(path)
                os.rename(tmp_path, path)
        except Exception as e:
            log_utils.log('Quellen-Kontext konnte nicht geschrieben werden: %s' % str(e), log_utils.LOGWARNING)


    def getSources(self, title, year, imdb, season, episode, originaltitle, premiered, quality='HD', timeout=30, episode_title=None, episode_premiered=None, force_refresh=False, quiet=False):
#TODO
        self.sources = []
        self.hostDict = self._getHostDict()
        sourceDict = self.sourceDict
        sourceDict = [(i[0], i[1], i[1].priority) for i in sourceDict]
        random.shuffle(sourceDict)
        sourceDict = sorted(sourceDict, key=lambda i: i[2])

        cache_key = self._sourceCacheKey(title, year, imdb, season, episode, originaltitle, premiered, episode_title, episode_premiered, sourceDict)
        series_key = self._seriesCacheKey(title, year, imdb, originaltitle, premiered)
        cached, stale = self._readSourceCache(cache_key, allow_stale=True)
        if cached and not force_refresh:
            self.sources = cached
            if stale:
                log_utils.log('Quellen-Cache verwendet (stale): %s Treffer' % len(self.sources), log_utils.LOGINFO)
                self._scheduleSourceCacheRefresh(cache_key, title, year, imdb, season, episode, originaltitle, premiered, episode_title, episode_premiered)
            else:
                log_utils.log('Quellen-Cache verwendet: %s Treffer' % len(self.sources), log_utils.LOGINFO)
            return self.sources

        if not quiet:
            control.idle() #ok
            progressDialog = control.progressDialog if control.getSetting('progress.dialog') == '0' else control.progressDialogBG
            progressDialog.create(control.addonInfo('name'), '')
            progressDialog.update(0)
            progressDialog.update(0, "Quellen werden vorbereitet")
        else:
            progressDialog = None

        content = 'shows' if getattr(self, 'mediatype', None) == 'tvshow' else 'movies' if season == 0 or season == '' or season == None else 'shows'
        aliases, localtitle = utils.getAliases(imdb, content)
        if localtitle and title != localtitle and originaltitle != localtitle:
            if not title in aliases: aliases.append(title)
            title = localtitle
        for i in self.aliases:
            if not i in aliases:
                aliases.append(i)
        titles = utils.get_titles_for_search(title, originaltitle, aliases)

        sourceDict = self._filterTemporarilyBlockedProviders(sourceDict)
        sourceDict = self._promoteSeriesProviders(sourceDict, series_key)

        self._ensureExecutor()
        futures = {self.executor.submit(self._getSource, titles, year, season, episode, imdb, provider[0], provider[1], episode_title, episode_premiered): provider[0] for provider in sourceDict}

        string4 = "Total"

        try: timeout = int(control.getSetting('scrapers.timeout'))
        except: pass
        
        quality = control.getSetting('hosts.quality')
        if quality == '': quality = '0'

        source_4k = 0
        source_1080 = 0
        source_720 = 0
        source_sd = 0
        total = d_total = 0
        total_format = '[COLOR %s][B]%s[/B][/COLOR]'
        pdiag_format = ' 4K: %s | 1080p: %s | 720p: %s | SD: %s | %s: %s                                         '.split('|')

        for i in range(0, 4 * timeout):
            try:
                if control.abortRequested: return sys.exit()
                try:
                    if progressDialog.iscanceled(): break
                except:
                    pass

                if len(self.sources) > 0:
                    if quality in ['0']:
                        source_4k = len([e for e in self.sources if e['quality'] == '4K'])
                        source_1080 = len([e for e in self.sources if e['quality'] in ['1440p','1080p']])
                        source_720 = len([e for e in self.sources if e['quality'] in ['720p','HD']])
                        source_sd = len([e for e in self.sources if e['quality'] not in ['4K','1440p','1080p','720p','HD']])
                    elif quality in ['1']:
                        source_1080 = len([e for e in self.sources if e['quality'] in ['1440p','1080p']])
                        source_720 = len([e for e in self.sources if e['quality'] in ['720p','HD']])
                        source_sd = len([e for e in self.sources if e['quality'] not in ['4K','1440p','1080p','720p','HD']])
                    elif quality in ['2']:
                        source_1080 = len([e for e in self.sources if e['quality'] in ['1080p']])
                        source_720 = len([e for e in self.sources if e['quality'] in ['720p','HD']])
                        source_sd = len([e for e in self.sources if e['quality'] not in ['4K','1440p','1080p','720p','HD']])
                    elif quality in ['3']:
                        source_720 = len([e for e in self.sources if e['quality'] in ['720p','HD']])
                        source_sd = len([e for e in self.sources if e['quality'] not in ['4K','1440p','1080p','720p','HD']])
                    else:
                        source_sd = len([e for e in self.sources if e['quality'] not in ['4K','1440p','1080p','720p','HD']])

                    total = source_4k + source_1080 + source_720 + source_sd

                source_4k_label = total_format % ('red', source_4k) if source_4k == 0 else total_format % ('lime', source_4k)
                source_1080_label = total_format % ('red', source_1080) if source_1080 == 0 else total_format % ('lime', source_1080)
                source_720_label = total_format % ('red', source_720) if source_720 == 0 else total_format % ('lime', source_720)
                source_sd_label = total_format % ('red', source_sd) if source_sd == 0 else total_format % ('lime', source_sd)
                source_total_label = total_format % ('red', total) if total == 0 else total_format % ('lime', total)

                try:
                    info = [name.upper() for future, name in futures.items() if not future.done()]

                    percent = int(100 * float(i) / (2 * timeout) + 1)

                    if quality in ['0']:
                        line1 = '|'.join(pdiag_format) % (source_4k_label, source_1080_label, source_720_label, source_sd_label, str(string4), source_total_label)
                    elif quality in ['1']:
                        line1 = '|'.join(pdiag_format[1:]) % (source_1080_label, source_720_label, source_sd_label, str(string4), source_total_label)
                    elif quality in ['2']:
                        line1 = '|'.join(pdiag_format[1:]) % (source_1080_label, source_720_label, source_sd_label, str(string4), source_total_label)
                    elif quality in ['3']:
                        line1 = '|'.join(pdiag_format[2:]) % (source_720_label, source_sd_label, str(string4), source_total_label)
                    else:
                        line1 = '|'.join(pdiag_format[3:]) % (source_sd_label, str(string4), source_total_label)

                    if (i / 2) < timeout:
                        string = "Verbleibende Indexseiten: %s"
                    else:
                        string = 'Waiting for: %s'

                    if len(info) > 6: line = line1 + string % (str(len(info)))
                    elif len(info) > 1: line = line1 + string % (', '.join(info))
                    elif len(info) == 1: line = line1 + string % (''.join(info))
                    else: line = line1 + 'Suche beendet!'

                    if progressDialog:
                        progressDialog.update(max(1, percent), line)
                    if len(info) == 0: break

                except Exception as e:
                    log_utils.log('Exception Raised: %s' % str(e), log_utils.LOGERROR)

                control.sleep(1)
            except:
                pass

        time.sleep(1)

        for future, provider_name in futures.items():
            try:
                if not future.done():
                    self._markProviderTemporarilyBlocked(provider_name, 'timeout', PROVIDER_TIMEOUT_TTL)
            except:
                pass
        self._cancelFutures(futures.keys())

        try:
            if progressDialog:
                progressDialog.close()
        except: pass
        self.sourcesFilter()
        self._writeSourceCache(cache_key, self.sources)
        self._updateSeriesCache(series_key, season, episode, self.sources, cache_key)
        self._shutdownExecutor()
        return self.sources

    def _sourceCacheKey(self, title, year, imdb, season, episode, originaltitle, premiered, episode_title, episode_premiered, sourceDict):
        provider_state = []
        for name, call, priority in sorted(sourceDict, key=lambda item: item[0]):
            provider_state.append({
                'name': name,
                'domain': getattr(call, 'domain', ''),
                'priority': priority
            })

        settings = {}
        for setting in [
            'hosts.quality',
            'hosts.language',
            'hosts.language.mode',
            'hosts.language.unknown',
            'hosts.language.multi',
            'hosts.sort.provider',
            'hosts.sort.priority',
            'hosts.limit',
            'hosts.limit.num'
        ]:
            settings[setting] = control.getSetting(setting)

        key = {
            'version': 5,
            'addon': control.addonVersion,
            'mediatype': getattr(self, 'mediatype', None),
            'title': py2_decode(title),
            'originaltitle': py2_decode(originaltitle),
            'year': str(year or ''),
            'imdb': str(imdb or ''),
            'season': str(season or ''),
            'episode': str(episode or ''),
            'premiered': str(premiered or ''),
            'episode_title': str(episode_title or ''),
            'episode_premiered': str(episode_premiered or ''),
            'aliases': sorted([str(i) for i in getattr(self, 'aliases', [])]),
            'providers': provider_state,
            'settings': settings
        }
        raw_key = json.dumps(key, sort_keys=True)
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    def _sourceCacheFile(self):
        return os.path.join(control.dataPath, 'source_cache_v2.json')

    def _seriesCacheKey(self, title, year, imdb, originaltitle, premiered):
        if getattr(self, 'mediatype', None) != 'tvshow':
            return None
        key = {
            'version': 1,
            'addon': control.addonVersion,
            'title': py2_decode(title),
            'originaltitle': py2_decode(originaltitle),
            'year': str(year or ''),
            'imdb': str(imdb or ''),
            'premiered': str(premiered or '')
        }
        raw_key = json.dumps(key, sort_keys=True)
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    def _readSourceCache(self, cache_key, allow_stale=False):
        try:
            cache = self._readSourceCachePayload()
            entry = (cache.get('entries') or {}).get(cache_key)
            if not entry:
                return None, False
            age = int(time.time()) - int(entry.get('timestamp', 0))
            if age > SOURCE_CACHE_TTL:
                if not allow_stale or age > SOURCE_CACHE_STALE_TTL:
                    return None, False
                stale = True
            else:
                stale = False
            items = entry.get('items')
            if not isinstance(items, list) or len(items) == 0:
                return None, False
            return items, stale
        except Exception as e:
            log_utils.log('Quellen-Cache konnte nicht gelesen werden: %s' % str(e), log_utils.LOGWARNING)
            return None, False

    def _writeSourceCache(self, cache_key, items):
        try:
            if not isinstance(items, list) or len(items) == 0:
                return
            payload = self._readSourceCachePayload()
            entries = payload.get('entries')
            if not isinstance(entries, dict):
                entries = {}
            now = int(time.time())
            entries[cache_key] = {
                'timestamp': now,
                'items': items
            }
            for key, entry in list(entries.items()):
                if now - int(entry.get('timestamp', 0)) > SOURCE_CACHE_STALE_TTL:
                    entries.pop(key, None)
            while len(entries) > SOURCE_CACHE_LIMIT:
                oldest = sorted(entries.items(), key=lambda item: int(item[1].get('timestamp', 0)))[0][0]
                entries.pop(oldest, None)
            payload['version'] = 2
            payload['entries'] = entries
            self._writeSourceCachePayload(payload)
            log_utils.log('Quellen-Cache gespeichert: %s Treffer' % len(items), log_utils.LOGINFO)
        except Exception as e:
            log_utils.log('Quellen-Cache konnte nicht gespeichert werden: %s' % str(e), log_utils.LOGWARNING)

    def _readSourceCachePayload(self):
        try:
            raw = control.window.getProperty(self.sourceCacheProperty)
            if raw:
                payload = json.loads(raw)
                if isinstance(payload.get('entries'), dict):
                    return self._normalizeSourceCachePayload(payload)
        except:
            pass
        try:
            cache_file = self._sourceCacheFile()
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as handle:
                    payload = json.load(handle)
                payload = self._normalizeSourceCachePayload(payload)
                control.window.setProperty(self.sourceCacheProperty, json.dumps(payload))
                return payload
        except Exception as e:
            log_utils.log('Persistenter Quellen-Cache konnte nicht gelesen werden: %s' % str(e), log_utils.LOGWARNING)
        return self._normalizeSourceCachePayload({})

    def _writeSourceCachePayload(self, payload):
        payload = self._normalizeSourceCachePayload(payload)
        try:
            control.window.setProperty(self.sourceCacheProperty, json.dumps(payload))
        except:
            pass
        try:
            if not os.path.exists(control.dataPath):
                os.makedirs(control.dataPath)
            cache_file = self._sourceCacheFile()
            tmp_file = cache_file + '.tmp'
            with open(tmp_file, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False)
            try:
                os.replace(tmp_file, cache_file)
            except:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                os.rename(tmp_file, cache_file)
        except Exception as e:
            log_utils.log('Persistenter Quellen-Cache konnte nicht geschrieben werden: %s' % str(e), log_utils.LOGWARNING)

    def _normalizeSourceCachePayload(self, payload):
        if not isinstance(payload, dict):
            payload = {}
        entries = payload.get('entries') if isinstance(payload.get('entries'), dict) else {}
        if payload.get('key') and payload.get('items'):
            entries[payload.get('key')] = {
                'timestamp': payload.get('timestamp', 0),
                'items': payload.get('items')
            }
        series = payload.get('series') if isinstance(payload.get('series'), dict) else {}
        provider_health = payload.get('provider_health') if isinstance(payload.get('provider_health'), dict) else {}
        now = int(time.time())
        for key, entry in list(entries.items()):
            try:
                if now - int(entry.get('timestamp', 0)) > SOURCE_CACHE_STALE_TTL:
                    entries.pop(key, None)
            except:
                entries.pop(key, None)
        for key, entry in list(provider_health.items()):
            try:
                if int(entry.get('blocked_until', 0)) <= now:
                    provider_health.pop(key, None)
            except:
                provider_health.pop(key, None)
        while len(series) > SERIES_CACHE_LIMIT:
            oldest = sorted(series.items(), key=lambda item: int(item[1].get('timestamp', 0)))[0][0]
            series.pop(oldest, None)
        return {
            'version': 2,
            'entries': entries,
            'series': series,
            'provider_health': provider_health
        }

    def _filterTemporarilyBlockedProviders(self, sourceDict):
        payload = self._readSourceCachePayload()
        provider_health = payload.get('provider_health') or {}
        now = int(time.time())
        filtered = []
        skipped = []
        for provider in sourceDict:
            state = provider_health.get(provider[0])
            if state and int(state.get('blocked_until', 0)) > now:
                skipped.append(provider[0])
                continue
            filtered.append(provider)
        if skipped:
            log_utils.log('Temporär gesperrte Indexseiten übersprungen: %s' % ', '.join(skipped), log_utils.LOGINFO)
        return filtered

    def _markProviderTemporarilyBlocked(self, provider, reason, ttl):
        try:
            if not provider:
                return
            payload = self._readSourceCachePayload()
            provider_health = payload.get('provider_health')
            if not isinstance(provider_health, dict):
                provider_health = {}
            provider_health[provider] = {
                'reason': str(reason or 'error'),
                'blocked_until': int(time.time()) + int(ttl),
                'timestamp': int(time.time())
            }
            payload['provider_health'] = provider_health
            self._writeSourceCachePayload(payload)
            log_utils.log('Indexseite temporär gesperrt: %s (%s)' % (provider, reason), log_utils.LOGWARNING)
        except:
            pass

    def _promoteSeriesProviders(self, sourceDict, series_key):
        if not series_key:
            return sourceDict
        try:
            payload = self._readSourceCachePayload()
            series = (payload.get('series') or {}).get(series_key) or {}
            providers = series.get('providers') or {}
            if not providers:
                return sourceDict
            order = {}
            for provider, state in providers.items():
                order[provider] = int(state.get('hits', 0)) * 1000000 + int(state.get('timestamp', 0))
            return sorted(sourceDict, key=lambda item: (-order.get(item[0], 0), item[2], item[0]))
        except:
            return sourceDict

    def _updateSeriesCache(self, series_key, season, episode, items, cache_key):
        if not series_key or not items:
            return
        try:
            payload = self._readSourceCachePayload()
            series = payload.get('series')
            if not isinstance(series, dict):
                series = {}
            entry = series.get(series_key)
            if not isinstance(entry, dict):
                entry = {'providers': {}, 'episodes': {}}
            providers = entry.get('providers') if isinstance(entry.get('providers'), dict) else {}
            now = int(time.time())
            for provider in sorted(set([item.get('provider') for item in items if item.get('provider')])):
                state = providers.get(provider) if isinstance(providers.get(provider), dict) else {}
                providers[provider] = {
                    'hits': int(state.get('hits', 0)) + 1,
                    'timestamp': now
                }
            episodes = entry.get('episodes') if isinstance(entry.get('episodes'), dict) else {}
            episode_key = 'S%02dE%02d' % (int(season or 0), int(episode or 0))
            episodes[episode_key] = {
                'timestamp': now,
                'cache_key': cache_key,
                'providers': sorted(set([item.get('provider') for item in items if item.get('provider')]))
            }
            entry.update({
                'timestamp': now,
                'providers': providers,
                'episodes': episodes
            })
            series[series_key] = entry
            payload['series'] = series
            self._writeSourceCachePayload(payload)
        except Exception as e:
            log_utils.log('Serien-Cache konnte nicht aktualisiert werden: %s' % str(e), log_utils.LOGWARNING)

    def _scheduleSourceCacheRefresh(self, cache_key, title, year, imdb, season, episode, originaltitle, premiered, episode_title, episode_premiered):
        try:
            refresh_property = '%s.refresh.%s' % (self.sourceCacheProperty, cache_key)
            if control.window.getProperty(refresh_property):
                return
            control.window.setProperty(refresh_property, 'true')

            def refresh():
                try:
                    worker = sources()
                    worker.mediatype = getattr(self, 'mediatype', None)
                    worker.aliases = list(getattr(self, 'aliases', []))
                    worker.getSources(
                        title, year, imdb, season, episode, originaltitle, premiered,
                        episode_title=episode_title,
                        episode_premiered=episode_premiered,
                        force_refresh=True,
                        quiet=True
                    )
                except Exception as e:
                    log_utils.log('Quellen-Cache Hintergrundaktualisierung fehlgeschlagen: %s' % str(e), log_utils.LOGWARNING)
                finally:
                    try:
                        control.window.clearProperty(refresh_property)
                    except:
                        pass

            thread = threading.Thread(target=refresh)
            thread.daemon = True
            thread.start()
        except:
            pass


    def _getSource(self, titles, year, season, episode, imdb, source, call, episode_title=None, episode_premiered=None):
        try:
            try:
                call.mediatype = getattr(self, 'mediatype', None)
                call.episode_title = episode_title
                call.episode_premiered = episode_premiered
            except:
                pass
            if self._acceptsHostDict(call):
                sources = call.run(titles, year, season, episode, imdb, hostDict=self.hostDict)
            else:
                sources = call.run(titles, year, season, episode, imdb)
            if sources == None or sources == []:
                return {'provider': source, 'count': 0, 'status': 'empty'}
            sources = [json.loads(t) for t in set(json.dumps(d, sort_keys=True) for d in sources)]
            for i in sources:
                i.update({'provider': source})
                i.update({'provider_display': self._providerDisplayName(source, call)})
                if not 'priority' in i: i.update({'priority': 100})
                if not 'prioHoster' in i: i.update({'prioHoster': 100})
            self.sources.extend(sources)
            return {'provider': source, 'count': len(sources), 'status': 'ok'}
        except Exception as e:
            self._markProviderTemporarilyBlocked(source, 'error', PROVIDER_ERROR_TTL)
            log_utils.log('Indexseite Fehler: %s / %s' % (source, str(e)), log_utils.LOGWARNING)
            return {'provider': source, 'count': 0, 'status': 'error'}

    def _acceptsHostDict(self, call):
        try:
            return 'hostDict' in inspect.signature(call.run).parameters
        except:
            return False

    def _getHostDict(self):
        try:
            domains = []
            relevant = resolver.relevant_resolvers(
                include_disabled=True,
                include_universal=False,
                include_popups=True
            )
            for item in relevant:
                for domain in getattr(item, 'domains', []) or []:
                    domain = str(domain).strip().lower()
                    if domain and domain != '*':
                        domains.append(domain)
            domains = sorted(set(domains))
            log_utils.log('ResolveURL-Hosterliste geladen: %s Domains' % len(domains), log_utils.LOGINFO)
            return domains
        except Exception as e:
            log_utils.log('ResolveURL-Hosterliste konnte nicht geladen werden: %s' % str(e), log_utils.LOGWARNING)
            return []

    def _providerDisplayName(self, provider, call=None):
        try:
            site_name = getattr(getattr(call.__class__, '__init__', None), '__globals__', {}).get('SITE_NAME', '') if call else ''
            if site_name:
                return self._streamDisplayText(site_name)
            module = sys.modules.get(call.__class__.__module__) if call else None
            site_name = getattr(module, 'SITE_NAME', '') if module else ''
            if site_name:
                return self._streamDisplayText(site_name)
        except:
            pass
        return self._streamDisplayText(provider)

    def _streamDisplayText(self, value):
        value = '' if value == None else str(value)
        value = re.sub(r'\[[^\]]+\]', '', value)
        value = re.sub(r'\s+', ' ', value).strip()
        known = {
            'voe': 'VOE',
            'voe.sx': 'VOE',
            'vivo': 'VIVO',
            'vidoza': 'Vidoza',
            'doodstream': 'DoodStream',
            'serienstream': 'SerienStream',
            'filmpalast': 'Filmpalast',
            'filmo': 'Filmo'
        }
        return known.get(value.lower(), value)

    def _mergeSelectedStreamMeta(self, meta, item):
        try:
            if not isinstance(meta, dict):
                meta = json.loads(meta)
            else:
                meta = dict(meta)
        except:
            return meta
        if not item:
            return meta

        hoster = self._streamDisplayText(item.get('source'))
        provider = self._streamDisplayText(item.get('provider_display') or item.get('provider'))
        if hoster:
            meta['_xvault_stream_hoster'] = hoster
        if provider:
            meta['_xvault_stream_provider'] = provider
        if item.get('quality'):
            meta['_xvault_stream_quality'] = item.get('quality')
        if item.get('label'):
            meta['_xvault_stream_label'] = item.get('label')
        return meta

    def _normalizeStreamLanguage(self, item):
        language_codes = self._languageCodesFromText(item.get('language', ''))
        if language_codes:
            return self._languageFromCodes(language_codes)

        values = [item.get('info', '')]
        codes = set()
        for value in values:
            codes.update(self._languageCodesFromText(value))
        return self._languageFromCodes(codes)

    def _languageFromCodes(self, codes):
        if 'multi' in codes or ('de' in codes and 'en' in codes):
            return 'multi'
        if 'de' in codes:
            return 'de'
        if 'en' in codes:
            return 'en'
        return 'unknown'

    def _languageCodesFromText(self, value):
        if value == None:
            return set()
        if isinstance(value, (list, tuple, set)):
            value = ' '.join([str(i) for i in value])
        text = str(value).lower()
        text = re.sub(r'[^a-z0-9]+', ' ', text)
        tokens = set([token for token in text.split() if token])
        codes = set()

        if tokens.intersection(set(['multi', 'multilang', 'multilanguage', 'multilingual', 'dual', 'dl'])):
            codes.add('multi')
        if re.search(r'\bdual\s+audio\b', text):
            codes.add('multi')
        if re.search(r'\b(?:ger|deu|german|deutsch|de)\s+(?:eng|english|englisch|en)\b', text):
            codes.add('multi')
        if re.search(r'\b(?:eng|english|englisch|en)\s+(?:ger|deu|german|deutsch|de)\b', text):
            codes.add('multi')

        if tokens.intersection(set(['de', 'deu', 'ger', 'german', 'deutsch'])):
            codes.add('de')
        if tokens.intersection(set(['en', 'eng', 'english', 'englisch'])):
            codes.add('en')
        return codes

    def _applyLanguagePreference(self):
        if getattr(self, 'mediatype', None) not in ['movie', 'tvshow']:
            return
        if len(self.sources) == 0:
            return

        language_setting = control.getSetting('hosts.language')
        if language_setting == '':
            language_setting = '0'

        for item in self.sources:
            item['_xvault_language'] = self._normalizeStreamLanguage(item)

        if language_setting == '0':
            return

        target = {'1': 'de', '2': 'en', '3': 'multi'}.get(language_setting)
        if target == None:
            return

        strict = control.getSetting('hosts.language.mode') == '1'
        keep_unknown = control.getSetting('hosts.language.unknown') == 'true'
        allow_multi = control.getSetting('hosts.language.multi') == 'true'

        def matches(item):
            language = item.get('_xvault_language', 'unknown')
            if language == target:
                return True
            if target in ['de', 'en'] and language == 'multi' and allow_multi:
                return True
            if language == 'unknown' and keep_unknown:
                return True
            return False

        if strict:
            self.sources = [item for item in self.sources if matches(item)]
            return

        def language_rank(item):
            language = item.get('_xvault_language', 'unknown')
            if language == target:
                return 0
            if target in ['de', 'en'] and language == 'multi' and allow_multi:
                return 1
            if language == 'unknown' and keep_unknown:
                return 2
            return 3

        self.sources = sorted(self.sources, key=language_rank)

    def _languageLabel(self, item):
        language = item.get('_xvault_language')
        if language == None:
            language = self._normalizeStreamLanguage(item)
            item['_xvault_language'] = language
        return {
            'de': 'DE',
            'en': 'EN',
            'multi': 'MULTI',
            'unknown': '?'
        }.get(language, '?')


    def sourcesFilter(self):
        # hostblockDict = utils.getHostDict()
        # self.sources = [i for i in self.sources if i['source'].split('.')[0] not in str(hostblockDict)] # Hoster ausschließen (Liste)

        quality = control.getSetting('hosts.quality')
        if quality == '': quality = '0'

        random.shuffle(self.sources)

        self.sources = sorted(self.sources, key=lambda k: k['prioHoster'], reverse=False)

        for i in range(len(self.sources)):
            q = self.sources[i]['quality']            
            if q.lower() == 'hd': self.sources[i].update({'quality': '720p'})

        filter = []
        if quality in ['0']: filter += [i for i in self.sources if i['quality'] == '4K']
        if quality in ['0', '1']: filter += [i for i in self.sources if i['quality'] == '1440p']
        if quality in ['0', '1', '2']: filter += [i for i in self.sources if i['quality'] == '1080p']
        if quality in ['0', '1', '2', '3']: filter += [i for i in self.sources if i['quality'] == '720p']
        #filter += [i for i in self.sources if i['quality'] in ['SD', 'SCR', 'CAM']]
        filter += [i for i in self.sources if i['quality'] not in ['4k', '1440p', '1080p', '720p']]
        self.sources = filter

        if control.getSetting('hosts.sort.provider') == 'true':
            self.sources = sorted(self.sources, key=lambda k: (k.get('prioHoster', 0) >= 999, k['provider']))

        if control.getSetting('hosts.sort.priority') == 'true' and self.mediatype == 'tvshow': self.sources = sorted(self.sources, key=lambda k: (k.get('prioHoster', 0) >= 999, k['priority']), reverse=False)

        self._applyLanguagePreference()

        if str(control.getSetting('hosts.limit')) == 'true':
            self.sources = self.sources[:int(control.getSetting('hosts.limit.num'))]
        else:
            self.sources = self.sources[:100]

        for i in range(len(self.sources)):
            p = self.sources[i]['provider']
            q = self.sources[i]['quality']
            s = self.sources[i]['source']
            ## s = s.rsplit('.', 1)[0]
            l = self._languageLabel(self.sources[i])

            try: f = (' | '.join(['[I]%s [/I]' % info.strip() for info in self.sources[i]['info'].split('|')]))
            except: f = ''
            if l:
                f = ('[B]%s[/B] | %s' % (l, f)) if f else '[B]%s[/B]' % l

            label = '%02d | [B]%s[/B] | ' % (int(i + 1), p)
            if q in ['4K', '1440p', '1080p', '720p']: label += '%s | [B][I]%s [/I][/B] | %s' % (s, q, f)
            elif q == 'SD': label += '%s | %s' % (s, f)
            else: label += '%s | %s | [I]%s [/I]' % (s, f, q)
            label = label.replace('| 0 |', '|').replace(' | [I]0 [/I]', '')
            label = re.sub(r'\[I\]\s+\[/I\]', ' ', label)
            label = re.sub(r'\|\s+\|', '|', label)
            label = re.sub(r'\|(?:\s+|)$', '', label)

            if self.sources[i].get('prioHoster', 0) >= 999:
                label += ' | [COLOR red]CAPTCHA[/COLOR]'
            self.sources[i]['label'] = label.upper()

            # ## EMBY shown as premium link ##
            # if self.sources[i]['provider']=="emby" or self.sources[i]['provider']=="amazon" or self.sources[i]['provider']=="netflix" or self.sources[i]['provider']=="maxdome":
            #     prem_identify = 'blue'
            #     self.sources[i]['label'] = ('[COLOR %s]' % (prem_identify)) + label.upper() + '[/COLOR]'

        self.sources = [i for i in self.sources if 'label' in i]
        return self.sources


    def sourcesResolve(self, item, info=False, check_stream=False, set_url=True):
        try:
            if set_url:
                self.url = None
            url = item['url']
            direct = item['direct']
            local = item.get('local', False)
            provider = item['provider']
            call = [i[1] for i in self.sourceDict if i[0] == provider][0]
            url = call.resolve(url)

            if not direct == True:
                resolved = False
                voe_url = self._resolveVoeDirect(url, item)
                if voe_url:
                    url = voe_url
                    resolved = True
                else:
                    try:
                        include_popups = item.get('prioHoster', 0) >= 999
                        hmf = resolver.HostedMediaFile(url=url, include_disabled=True, include_universal=False, include_popups=include_popups)
                        if not hmf.valid_url() and not include_popups:
                            hmf = resolver.HostedMediaFile(url=url, include_disabled=True, include_universal=False, include_popups=True)
                        if hmf.valid_url():
                            url = hmf.resolve()
                            resolved = True
                            if url == False or url == None or url == '': url = None # raise Exception()
                    except:
                        url = None
                if url and not resolved and not self._looksLikeDirectMediaUrl(url):
                    log_utils.log('Resolver lieferte keinen Direktstream: Provider %s / %s' % (item['provider'], item['source']), log_utils.LOGWARNING)
                    url = None
            elif item.get('prioHoster', 0) >= 999:
                try:
                    hmf = resolver.HostedMediaFile(url=url, include_disabled=True, include_universal=False, include_popups=True)
                    if hmf.valid_url():
                        url = hmf.resolve()
                        if url == False or url == None or url == '': url = None
                except:
                    url = None

            if not self._isUsableResolvedUrl(url, local):
                log_utils.log('Ungueltige Stream-URL verworfen: Provider %s / %s / %s' % (item['provider'], item['source'], str(url)), log_utils.LOGWARNING)
                url = None

            if url == None or (not '://' in str(url) and not local):
                log_utils.log('Kein Video Link gefunden: Provider %s / %s / %s ' % (item['provider'], item['source'] , str(item['source'])), log_utils.LOGERROR)
                raise Exception()

            if check_stream and not local and not utils.test_stream(url):
                log_utils.log('URL Test Error: Provider %s / %s / %s' % (item['provider'], item['source'], url), log_utils.LOGERROR)
                raise Exception()

            if url:
                if set_url:
                    self.url = url
                return url
            else:
                raise Exception()
        except:
            if info: self.errorForSources()
            return

    def _isUsableResolvedUrl(self, url, local=False):
        try:
            if local:
                return True
            raw_url = str(url or '').split('|', 1)[0].strip()
            if not raw_url:
                return False
            parsed = urlparse(raw_url)
            if parsed.scheme in ['http', 'https']:
                host = (parsed.hostname or '').lower()
                if not host or host in ['redirect']:
                    return False
                return True
            if parsed.scheme in ['plugin', 'rtmp', 'rtsp', 'udp', 'pvr', 'file']:
                return True
            return '://' in raw_url
        except:
            return False

    def _looksLikeDirectMediaUrl(self, url):
        try:
            clean_url = str(url).split('|', 1)[0].split('?', 1)[0].lower()
            if re.search(r'/playlist/\d+(?:/|$)', urlparse(clean_url).path):
                return True
            return re.search(r'\.(?:m3u8?|mpd|mp4|mkv|avi|mov|flv|wmv|webm|ts)$', clean_url) != None
        except:
            return False

    def _resolveVoeDirect(self, url, item):
        try:
            if 'voe' not in str(item.get('source', '')).lower() and 'voe' not in urlparse(str(url).split('|', 1)[0]).netloc.lower():
                return None

            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            page_url = str(url).split('|', 1)[0]
            response = requests.get(page_url, headers=headers, timeout=12, allow_redirects=True)
            html = response.text or ''
            real_url = response.url

            for _ in range(3):
                redirect = re.search(r"window\.location\.href\s*=\s*'([^']+)'", html)
                if not redirect:
                    break
                page_url = urljoin(real_url, html_unescape(redirect.group(1)))
                response = requests.get(page_url, headers=headers, timeout=12, allow_redirects=True)
                html = response.text or ''
                real_url = response.url

            packed = re.search(r'json">\["([^"]+)"\]</script>\s*<script\s+src="([^"]+)', html)
            if not packed:
                return None

            script_url = urljoin(real_url, html_unescape(packed.group(2)))
            script = requests.get(script_url, headers=headers, timeout=12).text or ''
            repl = re.search(r"(\[(?:'\W{2}'[,\]]){1,9})", script)
            if not repl:
                return None

            data = self._decodeVoePayload(packed.group(1), repl.group(1))
            media_url = data.get('direct_access_url') or data.get('source') or data.get('file')
            if not media_url:
                return None

            stream_headers = urlencode({
                'User-Agent': headers['User-Agent'],
                'Referer': real_url,
            })
            log_utils.log('VOE direkt aufgeloest: Provider %s / %s' % (item.get('provider'), item.get('source')), log_utils.LOGINFO)
            return '%s|%s' % (media_url, stream_headers)
        except Exception as e:
            log_utils.log('VOE Direktaufloesung fehlgeschlagen: %s' % str(e), log_utils.LOGWARNING)
            return None

    def _decodeVoePayload(self, encoded, replacements):
        tokens = [re.escape(token) for token in replacements[2:-2].split("','")]
        text = ''
        for char in encoded:
            value = ord(char)
            if 64 < value < 91:
                value = (value - 52) % 26 + 65
            elif 96 < value < 123:
                value = (value - 84) % 26 + 97
            text += chr(value)
        for token in tokens:
            text = re.sub(token, '', text)
        step = base64.b64decode(text).decode('utf-8', errors='replace')
        step = ''.join(chr(ord(char) - 3) for char in step)
        return json.loads(base64.b64decode(step[::-1]).decode('utf-8', errors='replace'))


    def sourcesDialog(self, items):
        self._ensureExecutor()
        labels = [i['label'] for i in items]

        select = control.selectDialog(labels)
        if select == -1: return 'close://'

        next = [y for x,y in enumerate(items) if x >= select]
        prev = [y for x,y in enumerate(items) if x < select][::-1]

        items = [items[select]]
        items = [i for i in items+next+prev][:40]

        header = control.addonInfo('name')
        header2 = header.upper()

        progressDialog = control.progressDialog if control.getSetting('progress.dialog') == '0' else control.progressDialogBG
        progressDialog.create(header, '')
        progressDialog.update(0)

        block = None

        try:
            for i in range(len(items)):
                try:
                    if items[i]['source'] == block: raise Exception()

                    future = self.executor.submit(self.sourcesResolve, items[i], False, True)

                    try:
                        if progressDialog.iscanceled(): break
                        progressDialog.update(int((100 / float(len(items))) * i), str(items[i]['label']))
                    except:
                        progressDialog.update(int((100 / float(len(items))) * i), str(header2) + str(items[i]['label']))

                    waiting_time = 30
                    while waiting_time > 0:
                        try:
                            if control.abortRequested: return sys.exit() #xbmc.Monitor().abortRequested()
                            if progressDialog.iscanceled(): return progressDialog.close()
                        except:
                            pass

                        if future.done(): break
                        control.sleep(1)

                        waiting_time = waiting_time - 1

                        if control.condVisibility('Window.IsActive(virtualkeyboard)') or \
                                control.condVisibility('Window.IsActive(yesnoDialog)'):
                            waiting_time = waiting_time + 1 #dont count down while dialog is presented ## control.condVisibility('Window.IsActive(PopupRecapInfoWindow)') or \

                    if not future.done():
                        future.cancel()
                        block = items[i]['source']

                    if self.url == None: raise Exception()

                    self.selectedSource = items[i]['label']
                    self.selectedSourceItem = items[i]

                    try: progressDialog.close()
                    except: pass

                    control.execute('Dialog.Close(virtualkeyboard)')
                    control.execute('Dialog.Close(yesnoDialog)')
                    return self.url
                except:
                    pass

            try: progressDialog.close()
            except: pass

        except Exception as e:
            try: progressDialog.close()
            except: pass
            log_utils.log('Error %s' % str(e), log_utils.LOGINFO)


    def _resolveSourceWithTimeout(self, item, progressDialog=None, timeout=SOURCE_RESOLVE_TIMEOUT, set_url=True):
        self._ensureExecutor()
        future = self.executor.submit(self.sourcesResolve, item, False, True, set_url)
        waiting_time = timeout
        while waiting_time > 0:
            try:
                if control.abortRequested:
                    return sys.exit()
                if progressDialog and progressDialog.iscanceled():
                    return 'close://'
            except:
                pass

            if future.done():
                break
            control.sleep(1)
            waiting_time = waiting_time - 1

            if control.condVisibility('Window.IsActive(virtualkeyboard)') or \
                    control.condVisibility('Window.IsActive(yesnoDialog)'):
                waiting_time = waiting_time + 1

        if not future.done():
            future.cancel()
            log_utils.log(
                'Resolve Timeout: Provider %s / Hoster %s nach %s Sekunden' %
                (item.get('provider'), item.get('source'), timeout),
                log_utils.LOGWARNING
            )
            return None

        try:
            return future.result()
        except Exception as e:
            log_utils.log(
                'Resolve Fehler: Provider %s / Hoster %s / %s' %
                (item.get('provider'), item.get('source'), str(e)),
                log_utils.LOGWARNING
            )
            return None


    def _autoplayPrefetchWindow(self, items):
        try:
            return max(2, min(AUTOPLAY_PREFETCH_LIMIT, len(items), max(2, int(getattr(self, 'max_workers', 12) / 2))))
        except:
            return min(3, len(items))

    def _resolveAutoplayCandidates(self, items, progressDialog=None, header2=''):
        self._ensureExecutor()
        max_items = min(len(items), 40)
        prefetch_window = self._autoplayPrefetchWindow(items[:max_items])
        pending = {}
        submitted = 0

        def submit_next():
            nonlocal submitted
            while submitted < max_items and len(pending) < prefetch_window:
                item = items[submitted]
                future = self.executor.submit(self.sourcesResolve, item, False, True, False)
                pending[submitted] = {
                    'future': future,
                    'item': item,
                    'started': time.time()
                }
                submitted += 1

        submit_next()

        for index in range(max_items):
            submit_next()
            state = pending.get(index)
            if not state:
                continue
            future = state['future']
            item = state['item']
            deadline = time.time() + SOURCE_RESOLVE_TIMEOUT

            while not future.done():
                try:
                    if control.abortRequested:
                        self._cancelFutures([state['future'] for state in pending.values()])
                        return None, 'abort://'
                    if progressDialog and progressDialog.iscanceled():
                        self._cancelFutures([state['future'] for state in pending.values()])
                        return None, 'close://'
                except:
                    pass

                if time.time() >= deadline:
                    log_utils.log(
                        'Autoplay Resolve Timeout: Provider %s / Hoster %s nach %s Sekunden' %
                        (item.get('provider'), item.get('source'), SOURCE_RESOLVE_TIMEOUT),
                        log_utils.LOGWARNING
                    )
                    break

                try:
                    if progressDialog:
                        label = str(item.get('label') or '')
                        percent = int((100 / float(max_items)) * index)
                        progressDialog.update(percent, label)
                except:
                    try:
                        if progressDialog:
                            progressDialog.update(int((100 / float(max_items)) * index), str(header2) + str(item.get('label') or ''))
                    except:
                        pass

                control.sleep(0.25)
                if control.condVisibility('Window.IsActive(virtualkeyboard)') or \
                        control.condVisibility('Window.IsActive(yesnoDialog)'):
                    deadline += 0.25

            pending.pop(index, None)
            submit_next()

            if not future.done():
                continue

            try:
                url = future.result()
            except Exception as e:
                log_utils.log(
                    'Autoplay Resolve Fehler: Provider %s / Hoster %s / %s' %
                    (item.get('provider'), item.get('source'), str(e)),
                    log_utils.LOGWARNING
                )
                url = None

            if url:
                self.url = url
                self._cancelFutures([state['future'] for state in pending.values()])
                return item, url

        self._cancelFutures([state['future'] for state in pending.values()])
        return None, None


    def sourcesAutoplay(self, items, title, meta):
        if not items:
            return False

        header = control.addonInfo('name')
        header2 = header.upper()
        progressDialog = None

        try:
            control.sleep(1)
            progressDialog = control.progressDialog if control.getSetting('progress.dialog') == '0' else control.progressDialogBG
            progressDialog.create(header, '')
            progressDialog.update(0)
        except:
            progressDialog = None

        try:
            from resources.lib.player import player

            remaining = list(items)
            while remaining:
                item, url = self._resolveAutoplayCandidates(remaining, progressDialog, header2)
                if url == 'close://':
                    return False
                if url == 'abort://':
                    return sys.exit()
                if not item or not url:
                    break

                self.selectedSourceItem = item
                playback_meta = self._mergeSelectedStreamMeta(dict(meta) if isinstance(meta, dict) else meta, item)

                try: progressDialog.close()
                except: pass
                progressDialog = None

                log_utils.log(
                    'Autoplay versucht Quelle: Provider %s / Hoster %s' %
                    (item.get('provider'), item.get('source')),
                    log_utils.LOGINFO
                )
                self._shutdownExecutor()
                if player().run(title, url, playback_meta):
                    return True
                self._ensureExecutor()

                log_utils.log(
                    'Autoplay Quelle startete nicht: Provider %s / Hoster %s' %
                    (item.get('provider'), item.get('source')),
                    log_utils.LOGWARNING
                )

                try:
                    index = remaining.index(item)
                    remaining = remaining[index + 1:]
                except:
                    remaining = remaining[1:]

                try:
                    progressDialog = control.progressDialog if control.getSetting('progress.dialog') == '0' else control.progressDialogBG
                    progressDialog.create(header, '')
                    progressDialog.update(0)
                except:
                    progressDialog = None
        finally:
            try: progressDialog.close()
            except: pass

        return False


    def sourcesDirect(self, items):
        # TODO - OK
        # filter = [i for i in items if i['source'].lower() in self.hostcapDict and i['debrid'] == '']
        # items = [i for i in items if not i in filter]
        # items = [i for i in items if ('autoplay' in i and i['autoplay'] == True) or not 'autoplay' in i]

        u = None

        header = control.addonInfo('name')
        header2 = header.upper()

        try:
            control.sleep(1)

            progressDialog = control.progressDialog if control.getSetting('progress.dialog') == '0' else control.progressDialogBG
            progressDialog.create(header, '')
            progressDialog.update(0)
        except:
            pass

        for i in range(len(items)):
            try:
                if progressDialog and progressDialog.iscanceled(): break
                if progressDialog: progressDialog.update(int((100 / float(len(items))) * i), str(items[i]['label']))
            except:
                try:
                    if progressDialog: progressDialog.update(int((100 / float(len(items))) * i), str(header2) + str(items[i]['label']))
                except:
                    pass

            try:
                if control.abortRequested: return sys.exit()

                url = self._resolveSourceWithTimeout(items[i], progressDialog, SOURCE_RESOLVE_TIMEOUT)
                if url == 'close://':
                    break
                if u == None: u = url
                if not url == None:
                    self.selectedSourceItem = items[i]
                    break
            except:
                pass

        try: progressDialog.close()
        except: pass

        return u

    def mediaInfo(self, source, dialog=None):
        import xbmcgui
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except: pass
        try:
            item = json.loads(source)[0]
            if item['source'] is None:
                raise Exception()

            import time as _time
            from resources.lib.mediainfo import TOTAL_TIMEOUT
            deadline = _time.time() + TOTAL_TIMEOUT

            if dialog is None:
                dialog = xbmcgui.DialogProgress()
                dialog.create('Medien-Info', 'Löse Stream-URL auf...')
                dialog.update(0)

            future = self.executor.submit(self.sourcesResolve, item)

            # Wait for resolve with responsive cancel (check every 250ms)
            # Cap at deadline so resolve + probe share the TOTAL_TIMEOUT budget
            for i in range(120):  # 120 * 250ms = 30s max
                remaining = int(deadline - _time.time())
                if remaining <= 0:
                    break
                dialog.update(int(50.0 * i / 120), 'Löse Stream-URL auf...')
                try:
                    if dialog.iscanceled():
                        try: dialog.close()
                        except: pass
                        return
                except: pass
                if future.done():
                    break
                control.sleep(0.25)  # 250ms — control.sleep() takes seconds, not ms
                # Don't count down while resolver shows interactive dialogs
                if control.condVisibility('Window.IsActive(virtualkeyboard)') or \
                        control.condVisibility('Window.IsActive(yesnoDialog)'):
                    continue

            url = self.url if future.done() else None
            control.execute('Dialog.Close(virtualkeyboard)')
            control.execute('Dialog.Close(yesnoDialog)')

            try:
                if dialog.iscanceled():
                    try: dialog.close()
                    except: pass
                    return
            except: pass

            if url is None:
                try: dialog.close()
                except: pass
                control.infoDialog("Stream-URL konnte nicht aufgelöst werden", sound=False, icon='INFO')
                return

            log_utils.log('mediaInfo: resolve done, url=%s deadline_remaining=%.1f' % (url[:80], deadline - _time.time()), log_utils.LOGWARNING)
            dialog.update(50, 'Analysiere Stream...')

            from resources.lib import mediainfo
            t_probe = _time.time()
            info = mediainfo.getMediaInfo(url, dialog, deadline)
            log_utils.log('mediaInfo: probe done in %.1fs, got_info=%s' % (_time.time() - t_probe, bool(info)), log_utils.LOGWARNING)

            try: dialog.close()
            except: pass

            if info:
                xbmcgui.Dialog().textviewer('Medien-Info', info)
            else:
                control.infoDialog("Auflösung konnte nicht ermittelt werden", sound=False, icon='INFO')

        except Exception as e:
            try:
                if dialog: dialog.close()
            except: pass
            log_utils.log('mediaInfo Error: %s' % str(e), log_utils.LOGERROR)
            control.infoDialog("Auflösung konnte nicht ermittelt werden", sound=False, icon='INFO')


    def errorForSources(self, error_group='no_sources'):
        self._telemetryEvent('source_collection_failed', 'sources', self._sourceTelemetryPayload(0, error_group))
        control.infoDialog("Keine Streams verfügbar oder ausgewählt", sound=False, icon='INFO')

    def getTitle(self, title):
        title = utils.normalize(title)
        return title

    def getConstants(self):
        self.itemsProperty = '%s.container.items' % control.Addon.getAddonInfo('id')
        self.metaProperty = '%s.container.meta'  % control.Addon.getAddonInfo('id')
        self.sourceCacheProperty = '%s.sources.last' % control.Addon.getAddonInfo('id')
        from scrapers import sources
        self.sourceDict = sources()
