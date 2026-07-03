

#2021-11-22
#edit 2025-03-02

import sys, re
import hashlib,os,codecs
from sqlite3 import dbapi2 as database
import xbmc, xbmcplugin
from resources.lib.control import py2_encode, translatePath, executebuiltin
from resources.lib import log_utils, control, playcountDB

try:
    import xmlrpclib as _xmlrpclib
    from StringIO import StringIO as _io
except:
    import xmlrpc.client as _xmlrpclib
    from io import BytesIO as _io

# eventuell zur spÃ¤teren verwendung als meta
#_params = dict(parse_qsl(sys.argv[2].replace('?',''))) if len(sys.argv) > 1 else dict()

class player(xbmc.Player):
    def __init__(self, *args, **kwargs):
        xbmc.Player.__init__(self, *args, **kwargs)
        self.streamFinished = False
        self.totalTime = 0
        self.currentTime = 0
        self.playcount = 0
        self.watcher_control = False
        self.list_position = 0
        self.list_content = ''
        self.queue_playback = False
        self.queue_last = False
        self.isdebug = True if control.getSetting('status.debug') == 'true' else False


    def run(self, title, url, meta):
        import xbmc
        try:
            self.meta = meta
            self.mediatype = meta['mediatype']
            self.title = meta['title']
            self.year = str(meta['year']) if 'year' in meta else ''
            if meta['mediatype'] == 'movie':
                self.name = title + ' (%s)' % meta['year'] if meta.get('year', False) else title
            else:
                self.name = title + ' S%02dE%02d' % (int(meta['season']), int(meta['episode']))

            if control.is_python2 and type(self.name) != unicode:
                self.name = self.name.decode('utf-8')
            self.imdb = meta['imdb_id'] if 'imdb_id' in meta else None
            self.number_of_seasons = meta['number_of_seasons'] if 'number_of_seasons' in meta else None
            self.season = meta['season'] if 'season' in meta else None
            self.number_of_episodes = meta['number_of_episodes'] if 'number_of_episodes' in meta else None
            self.episode = meta['episode'] if 'episode' in meta else None

            self.playcount = meta['playcount'] if 'playcount' in meta else 0
            self.list_position = int(meta.get('_xvault_list_position', 0) or 0)
            self.list_content = meta.get('_xvault_list_content', '')
            self.container_path = meta.get('_xvault_container_path', '')
            self.queue_playback = bool(meta.get('_xvault_queue_playback', False))
            self.queue_last = bool(meta.get('_xvault_queue_last', False))
            self.offset = bookmarks().get(self.name, self.year)

            from glob import glob
            os.chdir(os.path.join(control.translatePath('special://database/')))
            self.videoDB = os.path.join(control.translatePath('special://database/'), sorted(glob("MyVideos*.db"), reverse=True)[0])

            self.fileID = self.getVideoDB()

            plot = control.unquote(meta['plot']) if 'plot' in meta else ''

            Info = {'plot': plot}
            Info.setdefault('IMDBNumber', meta['imdbnumber'])
            if meta['mediatype'] == 'movie':
                Info.setdefault('OriginalTitle', meta['title'])
                Info.setdefault('year', meta['year'])
            else:
                Info.setdefault('TVshowtitle', meta['title'])
                Info.setdefault('Season', self.season)
                Info.setdefault('Episode', self.episode)

            item = control.item(label=self.name)

            # TS: video/mp2t
            # HLS: application/x-mpegURL or application/vnd.apple.mpegurl
            # Dash: application/dash+xml
            kodiver = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
            if ".m3u" in url or '.mpd' in url:
                item.setProperty("inputstream", "inputstream.adaptive")
                if '.mpd' in url:
                    if kodiver < 21: item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
                    item.setMimeType('application/dash+xml')
                else:
                    if kodiver < 21: item.setProperty('inputstream.adaptive.manifest_type', 'hls')
                    # item.setMimeType("application/vnd.apple.mpegurl")
                    item.setMimeType('application/x-mpegURL')
                item.setContentLookup(False)
                if '|' in url:
                    stream_url, strhdr = url.split('|')
                    item.setProperty('inputstream.adaptive.stream_headers', strhdr)
                    if kodiver > 19: item.setProperty('inputstream.adaptive.manifest_headers', strhdr)
                    #item.setPath(stream_url)
                    url = stream_url

            item.setPath(url)
            try:
                item.setArt({'poster': meta['poster']})
                item.setInfo(type='Video', infoLabels=Info)
            except:
                pass
            item.setProperty('IsPlayable', 'true')

            if int(sys.argv[1]) > 0:
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
            else:
                xbmc.Player().play(url, item)
            self.keepPlaybackAlive()
            return
        except:
            return


    def keepPlaybackAlive(self):
        if self.isdebug: log_utils.log('Start - keepPlaybackAlive', log_utils.LOGINFO)
        for i in range(0, 240):
            if self.isPlayingVideo(): break
            control.sleep(1)

        if self.isPlayingVideo():
            try:
                playcountDB.createEntry(self.mediatype, self.title, self.name, self.imdb, self.number_of_seasons, self.season, self.number_of_episodes, self.episode)
            except:
                pass

        monitor = xbmc.Monitor()
        self.watcher_control = False
        while (not monitor.abortRequested()) & (not self.streamFinished):
            if self.isPlayingVideo():
                self.totalTime = self.getTotalTime()
                self.currentTime = self.getTime()
                watcher = (self.currentTime / self.totalTime >= .9)
                if watcher and not self.watcher_control:
                    playcountDB.updatePlaycount(self.mediatype, self.title, self.name, self.imdb, self.number_of_seasons, self.season, self.number_of_episodes, self.episode, 1)
                    #control.setSetting(id='watcher.control', value='true')
                    self.watcher_control = True
            monitor.waitForAbort(3)

        if self.isdebug: log_utils.log('Ende - keepPlaybackAlive', log_utils.LOGINFO)


    def idleForPlayback(self):
        for i in range(0, 200):
            if control.condVisibility('Window.IsActive(busydialog)') == 1: control.idle()
            else: break
            control.sleep(1)


    def onAVStarted(self):
        if self.isdebug: log_utils.log('Start - onAVStarted', log_utils.LOGINFO)
        control.execute('Dialog.Close(all,true)')
        if not self.offset == '0': self.seekTime(float(self.offset))
        self.idleForPlayback()
        if control.getSetting('subtitles') == 'true':
            subtitles().get(self.name, self.imdb, self.season, self.episode)
            # Subtitles in Player MenÃ¼ ausschalten - wird dann bei Bedarf per "Hand" eingeschaltet
            # xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Player.SetSubtitle", "params": {"playerid": 1, "subtitle" : "on"}, "id": "1"}')
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Player.SetSubtitle", "params": {"playerid": 1, "subtitle" : "off"}, "id": "1"}')
        if self.isdebug: log_utils.log('Ende - onAVStarted', log_utils.LOGINFO)


    def onPlayBackStopped(self):
        self._finishPlayback(True, playback_ended=False)

    def onPlayBackEnded(self):
        self._finishPlayback(not self.queue_playback or self.queue_last, playback_ended=True)
        if self.isdebug: log_utils.log('Ende - onPlayBackEnded', log_utils.LOGINFO)

    def _finishPlayback(self, restore_navigation, playback_ended=False):
        if self.streamFinished:
            return
        if self.isdebug: log_utils.log('Start - onPlayBackStopped', log_utils.LOGINFO)
        self.runVideoDB()
        self.streamFinished = True
        completed = self._completed(playback_ended)
        if completed:
            self.currentTime = self.totalTime if self.totalTime else self.currentTime
            if not self.watcher_control:
                self._markWatched()
            self.watcher_control = True
        bookmarks().reset(self.currentTime, self.totalTime, self.name, self.year)
        try:
            from resources.lib.sync import binge_sync
            binge_sync.record_playback(self.meta, self.name, self.year, self.currentTime, self.totalTime, completed=completed, push=True)
        except:
            pass
        if restore_navigation:
            if self.isdebug: log_utils.log('vor parentDir - onPlayBackStopped', log_utils.LOGINFO)
            restore_position = self._shouldRestoreListPosition()
            try:
                self.parentDir()
            finally:
                if restore_position:
                    from resources.lib.utils import restoreListPosition
                    restoreListPosition(self.list_position, self.list_content, __name__)
        self.watcher_control = False
        if self.isdebug: log_utils.log('Ende - onPlayBackStopped', log_utils.LOGINFO)

    def _shouldRestoreListPosition(self):
        if self.list_position <= 0:
            return False
        if self.mediatype != 'movie' and control.getSetting('status.position') == 'true':
            return False
        return True


    def _completed(self, playback_ended=False):
        if playback_ended:
            return True
        if self.watcher_control:
            return True
        try:
            return bool(self.totalTime and self.currentTime and (float(self.currentTime) / float(self.totalTime) >= .9))
        except:
            return False


    def _markWatched(self):
        try:
            playcountDB.createEntry(self.mediatype, self.title, self.name, self.imdb, self.number_of_seasons, self.season, self.number_of_episodes, self.episode)
            playcountDB.updatePlaycount(self.mediatype, self.title, self.name, self.imdb, self.number_of_seasons, self.season, self.number_of_episodes, self.episode, 1)
        except:
            pass


    def parentDir(self):
        refreshtime = 2
        control.sleep(refreshtime)
        ccont = ''
        if control.getSetting('hosts.mode') == '1': # Liste der Streams (Hosterliste) als Verzeichnis
            count = 0
            # prÃ¼fen ob Hosterliste aktiv ist - content ist da 'videos'
            for count in range(1, 25+1):
                control.sleep(2)
                ccont = control.getInfoLabel("Container.Content")
                if ccont == 'videos': break

            if self.isdebug: log_utils.log(__name__ + ' - count: %s - Container.Content (1):  %s' % (count, control.getInfoLabel("Container.Content")), log_utils.LOGINFO)
            if count == 25: return

            # zur Film- bzw. Episodenliste wechseln  - von content 'videos' dann zu content 'videos'
            if control.getInfoLabel("Container.Content") != 'movies' and ccont == 'videos':
                control.execute('Action(ParentDir)')
                for count in range(1, 15 + 1):
                    control.sleep(2)
                    ccont = control.getInfoLabel("Container.Content")
                    if ccont == 'movies': break

                if self.isdebug: log_utils.log(__name__ + ' - count: %s - Container.Content (2):  %s' % (count, control.getInfoLabel("Container.Content")), log_utils.LOGINFO)
                if count == 15:
                    return
                else:
                    refreshtime = 0

        if self.playcount == 0:
            ## auch abhÃ¤ngig von control.content()
            refresh = False
            if control.getSetting('status.refresh.movies') == 'true' and self.mediatype == 'movie': # immer!
                refresh = True
            elif control.getSetting('status.refresh.episodes') == 'true' and self.mediatype != 'movie':
                refresh = True

            if refresh:
                if refreshtime != 0: control.sleep(refreshtime)
                self.refreshContainer()


    def refreshContainer(self):
        if self.mediatype != 'movie' and self.container_path:
            control.execute('Container.Update(%s,replace)' % self.container_path)
            return
        control.execute('Container.Refresh')

# keine EintrÃ¤ge fÃ¼r bookmarks und files in die Kodi DB 'MyVideos116.db' anlegen bzw. sofort lÃ¶schen
    def runVideoDB(self):
        idFile = self.getVideoDB()
        if idFile != self.fileID:
            self.removeVideoDB(idFile)

    def getVideoDB(self):
        dbcon = database.connect(self.videoDB)
        dbcur = dbcon.cursor()
        dbcur.execute("SELECT * FROM files")
        match = dbcur.fetchall()
        dbcon.close()
        if match and len(match) > 0: idFile = len(match)
        else: idFile = 0
        return idFile

    def removeVideoDB(self, idFile):
        dbcon = database.connect(self.videoDB)
        dbcur = dbcon.cursor()
        dbcur.execute("DELETE FROM files WHERE idFile = '%s'" % idFile) # in DB vorhandener Trigger lÃ¶scht auch den bookmark
        dbcon.commit()
        dbcon.close()


class subtitles:
    def __init__(self, *args, **kwargs):
        from xbmcaddon import Addon
        __scriptname__ = "XBMC Subtitles Login"
        __version__ = Addon().getAddonInfo('version')  # Module version
        BASE_URL_XMLRPC = u"http://api.opensubtitles.org/xml-rpc"

        self.server = _xmlrpclib.ServerProxy(BASE_URL_XMLRPC, verbose=0)
        login = self.server.LogIn(Addon().getSetting('subtitles.os_user'), Addon().getSetting('subtitles.os_pass'), "en", "%s_v%s" % (__scriptname__.replace(" ", "_"), __version__))
        if login["status"] == "200 OK":
            self.osdb_token = login["token"]

    def get(self, name, imdb, season, episode):
        season = str(season)
        episode = str(episode)
        try:
            langDict = {'Afrikaans': 'afr', 'Albanian': 'alb', 'Arabic': 'ara', 'Armenian': 'arm', 'Basque': 'baq', 'Bengali': 'ben', 'Bosnian': 'bos', 'Breton': 'bre', 'Bulgarian': 'bul', 'Burmese': 'bur', 'Catalan': 'cat', 'Chinese': 'chi', 'Croatian': 'hrv', 'Czech': 'cze', 'Danish': 'dan', 'Dutch': 'dut', 'English': 'eng', 'Esperanto': 'epo', 'Estonian': 'est', 'Finnish': 'fin', 'French': 'fre', 'Galician': 'glg', 'Georgian': 'geo', 'German': 'ger', 'Greek': 'ell', 'Hebrew': 'heb', 'Hindi': 'hin', 'Hungarian': 'hun', 'Icelandic': 'ice', 'Indonesian': 'ind', 'Italian': 'ita', 'Japanese': 'jpn', 'Kazakh': 'kaz', 'Khmer': 'khm', 'Korean': 'kor', 'Latvian': 'lav', 'Lithuanian': 'lit', 'Luxembourgish': 'ltz', 'Macedonian': 'mac', 'Malay': 'may', 'Malayalam': 'mal', 'Manipuri': 'mni', 'Mongolian': 'mon', 'Montenegrin': 'mne', 'Norwegian': 'nor', 'Occitan': 'oci', 'Persian': 'per', 'Polish': 'pol', 'Portuguese': 'por,pob', 'Portuguese(Brazil)': 'pob,por', 'Romanian': 'rum', 'Russian': 'rus', 'Serbian': 'scc', 'Sinhalese': 'sin', 'Slovak': 'slo', 'Slovenian': 'slv', 'Spanish': 'spa', 'Swahili': 'swa', 'Swedish': 'swe', 'Syriac': 'syr', 'Tagalog': 'tgl', 'Tamil': 'tam', 'Telugu': 'tel', 'Thai': 'tha', 'Turkish': 'tur', 'Ukrainian': 'ukr', 'Urdu': 'urd'}
            codePageDict = {'ara': 'cp1256', 'ar': 'cp1256', 'ell': 'cp1253', 'el': 'cp1253', 'heb': 'cp1255', 'he': 'cp1255', 'tur': 'cp1254', 'tr': 'cp1254', 'rus': 'cp1251', 'ru': 'cp1251'}

            # opensubtitles.org
            os_user = control.getSetting('subtitles.os_user')
            os_pass = control.getSetting('subtitles.os_pass')
            os_useragent = 'TemporaryUserAgent'

            langs = []
            try:
                try: langs = langDict[control.getSetting('subtitles.lang.1')].split(',')
                except: langs.append(langDict[control.getSetting('subtitles.lang.1')])
            except: pass

            try:
                try: langs = langs + langDict[control.getSetting('subtitles.lang.2')].split(',')
                except: langs.append(langDict[control.getSetting('subtitles.lang.2')])
            except: pass

            try: subLang = xbmc.Player().getSubtitles()
            except: subLang = ''
            if subLang == langs[0]: raise Exception()

            imdbid = re.sub(r'[^0-9]', '', imdb)
            if season == 'None' or episode == 'None':
                result = self.server.SearchSubtitles(self.osdb_token, [{'sublanguageid': langs[0], 'imdbid': imdbid}])['data']
                if result == []: result = self.server.SearchSubtitles(self.osdb_token, [{'sublanguageid': langs[1], 'imdbid': imdbid}])['data']
            else:
                result = self.server.SearchSubtitles(self.osdb_token, [{'sublanguageid': langs[0], 'imdbid': imdbid, 'season': season, 'episode': episode}])['data']
                if result == []: result = self.server.SearchSubtitles(self.osdb_token, [{'sublanguageid': langs[1], 'imdbid': imdbid, 'season': season, 'episode': episode}])['data']
                # fmt = ['hdtv']

            filter = []
            result = [i for i in result if i['SubSumCD'] == '1']

            for userrank in ['OS Legend','Administrator','Translator','Platinum member','Gold member','Silver member', 'Bronze member','trusted','']:
                for i in result:
                    if i['UserRank'] == userrank.lower():
                        filter.append(i)

            try: lang = xbmc.convertLanguage(filter[0]['SubLanguageID'], xbmc.ISO_639_1)
            except: lang = filter[0]['SubLanguageID']

            subtitle = control.translatePath('special://temp/')
            subtitle = os.path.join(subtitle, 'TemporarySubs.%s.srt' % lang)

            ZipDownloadID = filter[0]['ZipDownloadLink'].split('/')[-1]
            ZipDownloadLink = 'https://dl.opensubtitles.org/en/download/sub/%s' % ZipDownloadID

            import requests, zipfile

            r = requests.get(ZipDownloadLink)
            zf = zipfile.ZipFile(_io(r.content))
            content = ''
            for name in zf.namelist():
                if not name.endswith('.srt'): continue
                content = zf.read(name)

            codepage = codePageDict.get(lang, '')
            if codepage and control.getSetting('subtitles.utf') == 'true':
                try:
                    content_encoded = codecs.decode(content, codepage)
                    content = codecs.encode(content_encoded, 'utf-8')
                except:
                    pass

            output = open(subtitle, 'wb')
            output.write(content)
            output.close()

            control.sleep(1)
            xbmc.Player().setSubtitles(subtitle)
        except:
            pass


class bookmarks:
    def get(self, name, year='0'):
        from resources.lib import bookmarkDB
        offset = '0'
        try:
            if not control.getSetting('bookmarks') == 'true': raise Exception()

            idFile = hashlib.md5()
            for i in name:
                try:
                    idFile.update(str(i).encode('utf-8'))
                except:
                    idFile.update(str(i))
            for i in year:
                try:
                    idFile.update(str(i).encode('utf-8'))
                except:
                    idFile.update(str(i))
            idFile = str(idFile.hexdigest())

            match = bookmarkDB.get_query(idFile, 'bookmarks.pcl')

            # dbcon = database.connect(control.bookmarksFile)
            # dbcur = dbcon.cursor()
            # dbcur.execute("CREATE TABLE IF NOT EXISTS bookmark (""idFile TEXT, ""timeInSeconds TEXT, ""UNIQUE(idFile)"");")
            # dbcur.execute("SELECT * FROM bookmark WHERE idFile = '%s'" % idFile)
            # match = dbcur.fetchone()
            # dbcon.commit()
            # dbcon.close()

            if match: self.offset = str(match[1])
            if self.offset == '0': raise Exception()
            minutes, seconds = divmod(float(self.offset), 60)
            hours, minutes = divmod(minutes, 60)
            label = '%02d:%02d:%02d' % (hours, minutes, seconds)
            label = py2_encode("Fortsetzen ab : %s" % label)

            if control.getSetting('bookmarks.auto') == 'false':
                try:
                    yes = control.dialog.contextmenu([label, "Vom Anfang abspielen", ])
                except:
                    yes = control.yesnoDialog(label, '', '', str(name), "Fortsetzen",
                                              "Vom Anfang abspielen")
                if yes:
                    bookmarkDB.remove_query(idFile, 'bookmarks')
                    self.offset = '0'

            return self.offset
        except:
            return offset


    def reset(self, currentTime, totalTime, name, year='0'):
        from resources.lib import bookmarkDB
        try:
            #if not control.getSetting('bookmarks') == 'true': raise Exception()
            if control.getSetting('bookmarks') == 'true' and int(currentTime) > 180:
                timeInSeconds = str(currentTime)
                idFile = hashlib.md5()
                for i in name:
                    try:
                        idFile.update(str(i).encode('utf-8'))
                    except:
                        idFile.update(str(i))
                for i in year:
                    try:
                        idFile.update(str(i).encode('utf-8'))
                    except:
                        idFile.update(str(i))
                idFile = str(idFile.hexdigest())

                if (currentTime / totalTime) >= .92:
                    bookmarkDB.remove_query(idFile, 'bookmarks')
                else:
                    bookmarkDB.save_query(idFile, timeInSeconds, 'bookmarks')

                # dbcon = database.connect(control.bookmarksFile)
                # dbcur = dbcon.cursor()
                # dbcur.execute("CREATE TABLE IF NOT EXISTS bookmark (""idFile TEXT, ""timeInSeconds TEXT, ""UNIQUE(idFile)"");")
                # if (currentTime / totalTime) <= .92:
                #     dbcur.execute("DELETE FROM bookmark WHERE idFile = '%s'" % idFile)
                #     dbcur.execute("INSERT INTO bookmark Values (?, ?)", (idFile, timeInSeconds))
                # else:
                #     dbcur.execute("DELETE FROM bookmark WHERE idFile = '%s'" % idFile)
                # dbcon.commit()
                # dbcon.close()

        except:
            pass

