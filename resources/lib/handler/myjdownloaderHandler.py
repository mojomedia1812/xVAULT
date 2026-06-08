# -*- coding: utf-8 -*-
# Python 3

from resources.lib.handler import myjdapi
from resources.lib import control
from xbmc import LOGINFO as LOGNOTICE, log

class cMyJDownloaderHandler:

    def sendToMyJDownloader(self, sUrl, sMovieTitle, sSourceUrl=None):
        if self.__checkConfig() == False:
            control.infoDialog('Einstellungen nicht konfiguriert', heading='My.JDownloader', icon='ERROR')
            return False

        log('xVAULT -> [myjdownloaderHandler]: connecting to MyJD...', LOGNOTICE)
        jd = myjdapi.Myjdapi()
        try:
            jd.connect(self.__getUser(), self.__getPass())
        except Exception as e:
            log('xVAULT -> [myjdownloaderHandler]: connect failed: %s' % str(e), LOGNOTICE)
            control.infoDialog('Verbindung fehlgeschlagen', heading='My.JDownloader', icon='ERROR')
            return False

        log('xVAULT -> [myjdownloaderHandler]: connected, getting device "%s"' % self.__getDevice(), LOGNOTICE)
        try:
            device = jd.get_device(self.__getDevice())
        except Exception as e:
            log('xVAULT -> [myjdownloaderHandler]: device not found: %s' % str(e), LOGNOTICE)
            control.infoDialog('Geraet nicht gefunden: ' + self.__getDevice(), heading='My.JDownloader', icon='ERROR')
            return False

        log('xVAULT -> [myjdownloaderHandler]: sending link: %s' % sUrl, LOGNOTICE)
        if sSourceUrl:
            log('xVAULT -> [myjdownloaderHandler]: sourceUrl: %s' % sSourceUrl, LOGNOTICE)
        try:
            params = {"autostart": False, "links": sUrl, "packageName": sMovieTitle}
            if sSourceUrl:
                params["sourceUrl"] = sSourceUrl
            response = device.linkgrabber.add_links([params])
            log('xVAULT -> [myjdownloaderHandler]: add_links response: %s' % str(response), LOGNOTICE)
            control.infoDialog('Link gesendet', heading='My.JDownloader', icon='INFO')
            return True
        except Exception as e:
            log('xVAULT -> [myjdownloaderHandler]: send failed: %s' % str(e), LOGNOTICE)
            control.infoDialog('Fehler beim Senden: ' + str(e), heading='My.JDownloader', icon='ERROR')
        return False

    def __checkConfig(self):
        log('xVAULT -> [myjdownloaderHandler]: check MYJD Addon settings', LOGNOTICE)
        if control.getSetting('myjd_enabled') == 'true':
            return True
        return False

    def __getDevice(self):
        return control.getSetting('myjd_device')

    def __getUser(self):
        return control.getSetting('myjd_user')

    def __getPass(self):
        return control.getSetting('myjd_pass')
