# -*- coding: utf-8 -*-
# Python 3

import re

from resources.lib import control
from xbmc import LOGINFO as LOGNOTICE, log
from urllib.request import Request, urlopen
from urllib.parse import urlencode

class cJDownloader2Handler:
    def sendToJDownloader2(self, sUrl):
        if self.__checkConfig() is False:
            control.infoDialog('Einstellungen nicht konfiguriert', heading='JDownloader 2', icon='ERROR')
            return False

        if self.__checkConnection() is False:
            control.infoDialog('Verbindung fehlgeschlagen', heading='JDownloader 2', icon='ERROR')
            return False

        if self.__download(sUrl) is True:
            control.infoDialog('Link gesendet', heading='JDownloader 2', icon='INFO')
            return True
        return False

    def __client(self, path, params):
        sHost = self.__getHost()
        sPort = self.__getPort()
        ENCODING = 'utf-8'
        url = 'http://{}:{}/{}'.format(sHost, sPort, path)
        if params is not None:
            headers = {'Content-Type': 'application/x-www-form-urlencoded;charset={}'.format(ENCODING)}
            request = Request(url, urlencode(params).encode(ENCODING), headers)
        else:
            request = Request(url)
        return urlopen(request).read().decode(ENCODING).strip()

    def __download(self, sFileUrl):
        log('xVAULT -> [jdownloader2Handler]: JD2 Link: ' + str(sFileUrl), LOGNOTICE)
        params = {'passwords': 'myPassword', 'source': 'http://jdownloader.org/spielwiese', 'urls': sFileUrl, 'submit': 'Add Link to JDownloader'}
        if self.__client('flash/add', params).lower() == 'success':
            return True
        else:
            return False

    def __checkConfig(self):
        log('xVAULT -> [jdownloader2Handler]: check JD2 Addon settings', LOGNOTICE)
        bEnabled = control.getSetting('jd2_enabled')
        if bEnabled == 'true':
            return True
        return False

    def __getHost(self):
        return control.getSetting('jd2_host')

    def __getPort(self):
        return control.getSetting('jd2_port')

    def __checkConnection(self):
        log('xVAULT -> [jdownloader2Handler]: check JD2 Connection', LOGNOTICE)
        try:
            output = self.__client('jdcheck.js', None)
            pattern = re.compile(r'jdownloader\s*=\s*true', re.IGNORECASE)
            if pattern.search(output) != None:
                return True
        except Exception:
            return False
        return False
