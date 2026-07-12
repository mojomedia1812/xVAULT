# edit 2025-06-12
import sys
import base64
import hashlib
import re, json, random, time
from concurrent.futures import ThreadPoolExecutor
from html import unescape as html_unescape
from urllib.parse import urlencode, urljoin, urlparse
from resources.lib import log_utils, utils, control, playback_settings
from resources.lib.control import py2_decode, py2_encode, quote_plus, parse_qsl
import resolveurl as resolver
# from functools import reduce
from resources.lib.control import getKodiVersion

if int(getKodiVersion()) >= 20: from infotagger.listitem import ListItemInfoTag

SOURCE_CACHE_TTL = 15 * 60
SOURCE_CACHE_LIMIT = 5

# für self.sysmeta - zur späteren verwendung als meta
_params = dict(parse_qsl(sys.argv[2].replace('?',''))) if len(sys.argv) > 1 else dict()

class sources:
    def __init__(self):
        self.getConstants()
        self.sources = []
        self.current = int(time.time())
        if 'sysmeta' in _params: self.sysmeta = _params['sysmeta'] # string zur späteren verwendung als meta
        self.watcher = False
        self.executor = ThreadPoolExecutor(max_workers=20)
        self.url = None

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
                list_position = int(params.get('_xvault_list_position') or control.infoLabel('Container().CurrentItem'))
                if list_position > 0:
                    meta_data['_xvault_list_position'] = list_position
                    meta_data['_xvault_list_content'] = params.get('_xvault_list_content') or control.infoLabel('Container.Content')
                    meta_data['_xvault_container_path'] = params.get('_xvault_container_path') or control.infoLabel('Container.FolderPath')
                    meta = json.dumps(meta_data)
                    params['sysmeta'] = meta
            except:
                pass

            url = None
            select = playback_settings.get_mode() if select == None else playback_settings.normalize_mode(select)
            select = self._enforceStreamLanguageSelectionMode(select)
            if select == None: return

            #Liste der gefundenen Streams
            items = self.getSources(title, year, imdb, season, episode, originaltitle, premiered, episode_title=episode_title, episode_premiered=episode_premiered)
            ## unnötig
            #select = '1' if control.getSetting('downloads') == 'true' and not (control.getSetting('download.movie.path') == '' or control.getSetting('download.tv.path') == '') else select

            # # TODO überprüfen wofür mal gedacht
            # if control.window.getProperty('PseudoTVRunning') == 'True':
            #     return control.resolveUrl(int(sys.argv[1]), True, control.item(path=str(self.sourcesDirect(items))))

            if len(items) > 0:
                # Auswahl Verzeichnis
                if select == '1' and 'plugin' in control.infoLabel('Container.PluginName'):
                    control.window.clearProperty(self.itemsProperty)
                    control.window.setProperty(self.itemsProperty, json.dumps(items))
                    
                    control.window.clearProperty(self.metaProperty)
                    control.window.setProperty(self.metaProperty, meta)
                    control.sleep(2)
                    return control.execute('Container.Update(%s?action=addItem&title=%s)' % (sys.argv[0], quote_plus(title)))
                # Auswahl Dialog
                elif select == '0' or select == '1':
                    url = self.sourcesDialog(items)
                    if  url == 'close://': return
                # Autoplay
                else:
                    url = self.sourcesDirect(items)

            if url == None: return self.errorForSources()

            try: meta = json.loads(meta)
            except: pass
            meta = self._mergeSelectedStreamMeta(meta, getattr(self, 'selectedSourceItem', None))

            from resources.lib.player import player
            player().run(title, url, meta)
        except Exception as e:
            log_utils.log('Error %s' % str(e), log_utils.LOGERROR)

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


    def playItem(self, title, source):
        isDebug = False
        if isDebug: log_utils.log('start playItem', log_utils.LOGWARNING)
        try:
            meta = control.window.getProperty(self.metaProperty)
            meta = json.loads(meta)

            header = control.addonInfo('name')
            # control.idle() #ok
            progressDialog = control.progressDialog if control.getSetting('progress.dialog') == '0' else control.progressDialogBG
            progressDialog.create(header, '')
            progressDialog.update(0)

            item = json.loads(source)[0]
            #if isDebug: log_utils.log('playItem 237', log_utils.LOGWARNING)
            if item['source'] == None: raise Exception()
            
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
            from resources.lib.player import player
            player().run(title, self.url, meta)
            return self.url
        except Exception as e:
            log_utils.log('Error %s' % str(e), log_utils.LOGERROR)


    def getSources(self, title, year, imdb, season, episode, originaltitle, premiered, quality='HD', timeout=30, episode_title=None, episode_premiered=None):
#TODO
        # self._getHostDict()
        sourceDict = self.sourceDict
        sourceDict = [(i[0], i[1], i[1].priority) for i in sourceDict]
        random.shuffle(sourceDict)
        sourceDict = sorted(sourceDict, key=lambda i: i[2])

        cache_key = self._sourceCacheKey(title, year, imdb, season, episode, originaltitle, premiered, episode_title, episode_premiered, sourceDict)
        cached = self._readSourceCache(cache_key)
        if cached:
            self.sources = cached
            log_utils.log('Quellen-Cache verwendet: %s Treffer' % len(self.sources), log_utils.LOGINFO)
            return self.sources

        control.idle() #ok
        progressDialog = control.progressDialog if control.getSetting('progress.dialog') == '0' else control.progressDialogBG
        progressDialog.create(control.addonInfo('name'), '')
        progressDialog.update(0)
        progressDialog.update(0, "Quellen werden vorbereitet")

        content = 'shows' if getattr(self, 'mediatype', None) == 'tvshow' else 'movies' if season == 0 or season == '' or season == None else 'shows'
        aliases, localtitle = utils.getAliases(imdb, content)
        if localtitle and title != localtitle and originaltitle != localtitle:
            if not title in aliases: aliases.append(title)
            title = localtitle
        for i in self.aliases:
            if not i in aliases:
                aliases.append(i)
        titles = utils.get_titles_for_search(title, originaltitle, aliases)

        futures = {self.executor.submit(self._getSource, titles, year, season, episode, imdb, provider[0], provider[1], episode_title, episode_premiered): provider[0] for provider in sourceDict}
        provider_names = {provider[0].upper() for provider in sourceDict}

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

                    progressDialog.update(max(1, percent), line)
                    if len(info) == 0: break

                except Exception as e:
                    log_utils.log('Exception Raised: %s' % str(e), log_utils.LOGERROR)

                control.sleep(1)
            except:
                pass

        time.sleep(1)

        try: progressDialog.close()
        except: pass
        self.sourcesFilter()
        self._writeSourceCache(cache_key, self.sources)
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
            'version': 1,
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

    def _readSourceCache(self, cache_key):
        try:
            raw = control.window.getProperty(self.sourceCacheProperty)
            if not raw:
                return None
            cache = json.loads(raw)
            if cache.get('key') == cache_key:
                entry = cache
            else:
                entry = (cache.get('entries') or {}).get(cache_key)
            if not entry:
                return None
            if int(time.time()) - int(entry.get('timestamp', 0)) > SOURCE_CACHE_TTL:
                return None
            items = entry.get('items')
            if not isinstance(items, list) or len(items) == 0:
                return None
            return items
        except Exception as e:
            log_utils.log('Quellen-Cache konnte nicht gelesen werden: %s' % str(e), log_utils.LOGWARNING)
            return None

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
                'timestamp': int(time.time()),
                'items': items
            }
            for key, entry in list(entries.items()):
                if now - int(entry.get('timestamp', 0)) > SOURCE_CACHE_TTL:
                    entries.pop(key, None)
            while len(entries) > SOURCE_CACHE_LIMIT:
                oldest = sorted(entries.items(), key=lambda item: int(item[1].get('timestamp', 0)))[0][0]
                entries.pop(oldest, None)
            payload = {
                'version': 1,
                'entries': entries
            }
            control.window.setProperty(self.sourceCacheProperty, json.dumps(payload))
            log_utils.log('Quellen-Cache gespeichert: %s Treffer' % len(items), log_utils.LOGINFO)
        except Exception as e:
            log_utils.log('Quellen-Cache konnte nicht gespeichert werden: %s' % str(e), log_utils.LOGWARNING)

    def _readSourceCachePayload(self):
        try:
            raw = control.window.getProperty(self.sourceCacheProperty)
            if not raw:
                return {'version': 1, 'entries': {}}
            payload = json.loads(raw)
            if isinstance(payload.get('entries'), dict):
                return payload
            if payload.get('key') and payload.get('items'):
                return {
                    'version': 1,
                    'entries': {
                        payload.get('key'): {
                            'timestamp': payload.get('timestamp', 0),
                            'items': payload.get('items')
                        }
                    }
                }
        except:
            pass
        return {'version': 1, 'entries': {}}


    def _getSource(self, titles, year, season, episode, imdb, source, call, episode_title=None, episode_premiered=None):
        try:
            try:
                call.mediatype = getattr(self, 'mediatype', None)
                call.episode_title = episode_title
                call.episode_premiered = episode_premiered
            except:
                pass
            sources = call.run(titles, year, season, episode, imdb)  # kasi self.hostDict
            if sources == None or sources == []: raise Exception()
            sources = [json.loads(t) for t in set(json.dumps(d, sort_keys=True) for d in sources)]
            for i in sources:
                i.update({'provider': source})
                i.update({'provider_display': self._providerDisplayName(source, call)})
                if not 'priority' in i: i.update({'priority': 100})
                if not 'prioHoster' in i: i.update({'prioHoster': 100})
            self.sources.extend(sources)
        except:
            pass

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
            'vivo': 'VIVO',
            'vidoza': 'Vidoza',
            'doodstream': 'DoodStream',
            'serienstream': 'SerienStream',
            'filmpalast': 'Filmpalast'
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


    def sourcesResolve(self, item, info=False, check_stream=False):
        try:
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
                        hmf = resolver.HostedMediaFile(url=url, include_disabled=True, include_universal=False, include_popups=False)
                        if not hmf.valid_url():
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

            if url == None or (not '://' in str(url) and not local):
                log_utils.log('Kein Video Link gefunden: Provider %s / %s / %s ' % (item['provider'], item['source'] , str(item['source'])), log_utils.LOGERROR)
                raise Exception()

            if check_stream and not local and not utils.test_stream(url):
                log_utils.log('URL Test Error: Provider %s / %s / %s' % (item['provider'], item['source'], url), log_utils.LOGERROR)
                raise Exception()

            if url:
                self.url = url
                return url
            else:
                raise Exception()
        except:
            if info: self.errorForSources()
            return

    def _looksLikeDirectMediaUrl(self, url):
        try:
            clean_url = str(url).split('|', 1)[0].split('?', 1)[0].lower()
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
                                control.condVisibility('Window.IsActive(yesnoDialog)') or \
                                control.condVisibility('Window.IsActive(ProgressDialog)'):
                            waiting_time = waiting_time + 1 #dont count down while dialog is presented ## control.condVisibility('Window.IsActive(PopupRecapInfoWindow)') or \

                    if not future.done(): block = items[i]['source']

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
                if progressDialog.iscanceled(): break
                progressDialog.update(int((100 / float(len(items))) * i), str(items[i]['label']))
            except:
                progressDialog.update(int((100 / float(len(items))) * i), str(header2) + str(items[i]['label']))

            try:
                if control.abortRequested: return sys.exit()

                url = self.sourcesResolve(items[i], False, True)
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


    def errorForSources(self):
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
