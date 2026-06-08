# -*- coding: utf-8 -*-
# Python 3

from xbmc import LOGINFO as LOGNOTICE, log
from resources.lib import control
from urllib.request import Request, urlopen

class cJDownloaderHandler:
    def sendToJDownloader(self, sUrl):
        if self.__checkConfig() == False:
            control.infoDialog('Einstellungen nicht konfiguriert', heading='JDownloader', icon='ERROR')
            return False

        if self.__checkConnection() == False:
            control.infoDialog('Verbindung fehlgeschlagen', heading='JDownloader', icon='ERROR')
            return False

        bDownload = self.__download(sUrl)
        if bDownload == True:
            control.infoDialog('Link gesendet', heading='JDownloader', icon='INFO')

    def __checkConfig(self):
        log('xVAULT -> [jdownloaderHandler]: check JD Addon settings', LOGNOTICE)
        bEnabled = control.getSetting('jd_enabled')
        if bEnabled == 'true':
            return True
        return False

    def __getHost(self):
        return control.getSetting('jd_host')

    def __getPort(self):
        return control.getSetting('jd_port')

    def __getAutomaticStart(self):
        bAutomaticStart = control.getSetting('jd_automatic_start')
        if bAutomaticStart == 'true':
            return True
        return False

    def __getLinkGrabber(self):
        bGrabber = control.getSetting('jd_grabber')
        if bGrabber == 'true':
            return True
        return False

    def __download(self, sFileUrl):
        sHost = self.__getHost()
        sPort = self.__getPort()
        bAutomaticDownload = self.__getAutomaticStart()
        bLinkGrabber = self.__getLinkGrabber()
        sLinkForJd = self.__createJDUrl(sFileUrl, sHost, sPort, bAutomaticDownload, bLinkGrabber)
        log('xVAULT -> [jdownloaderHandler]: JD Link: ' + str(sLinkForJd), LOGNOTICE)
        request = Request(sLinkForJd)
        urlopen(request).read()
        return True

    def __createJDUrl(self, sFileUrl, sHost, sPort, bAutomaticDownload, bLinkGrabber):
        sGrabber = '1' if bLinkGrabber else '0'
        sAutomaticStart = '1' if bAutomaticDownload else '0'
        sUrl = 'http://' + str(sHost) + ':' + str(sPort) + '/action/add/links/grabber' + sGrabber + '/start' + sAutomaticStart + '/' + sFileUrl
        return sUrl

    def __checkConnection(self):
        log('xVAULT -> [jdownloaderHandler]: check JD Connection', LOGNOTICE)
        sHost = self.__getHost()
        sPort = self.__getPort()
        sLinkForJd = 'http://' + str(sHost) + ':' + str(sPort)
        try:
            request = Request(sLinkForJd)
            urlopen(request).read()
            return True
        except Exception:
            return False
