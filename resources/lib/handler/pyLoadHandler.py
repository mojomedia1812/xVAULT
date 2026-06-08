# -*- coding: utf-8 -*-
# Python 3

import sys

from resources.lib import control
from xbmc import LOGINFO as LOGNOTICE, log
from urllib.request import Request, urlopen, build_opener
from urllib.error import HTTPError
from urllib.parse import urlencode, quote_plus

class cPyLoadHandler:

    def sendToPyLoad(self, sPackage, sUrl):
        log('xVAULT -> [pyLoadHandler]: PyLoad package: ' + str(sPackage) + ', ' + str(sUrl), LOGNOTICE)
        if self.__sendLinkToCore(sPackage, sUrl):
            control.infoDialog('Link gesendet', heading='PyLoad', icon='INFO')
        else:
            control.infoDialog('Senden fehlgeschlagen', heading='PyLoad', icon='ERROR')

    def __sendLinkToCore(self, sPackage, sUrl):
        log('xVAULT -> [pyLoadHandler]: Sending link...', LOGNOTICE)
        try:
            py_host = control.getSetting('pyload_host')
            py_port = control.getSetting('pyload_port')
            py_user = control.getSetting('pyload_user')
            py_passwd = control.getSetting('pyload_passwd')
            mydata = [('username', py_user), ('password', py_passwd)]
            mydata = urlencode(mydata)
            # check if host has a leading http://
            if py_host.find('http://') != 0:
                py_host = 'http://' + py_host
            log('xVAULT -> [pyLoadHandler]: Attempting to connect to PyLoad at: ' + py_host + ':' + py_port, LOGNOTICE)
            req = Request(py_host + ':' + py_port + '/api/login', mydata)
            req.add_header("Content-type", "application/x-www-form-urlencoded")
            page = urlopen(req).read()
            page = page[1:]
            session = page[:-1]
            opener = build_opener()
            opener.addheaders.append(('Cookie', 'beaker.session.id=' + session))
            sPackage = sPackage.translate(str.maketrans('\\/:*?"<>|', '_________'))
            py_url = py_host + ':' + py_port + '/api/addPackage?name="' + quote_plus(sPackage) + '"&links=["' + quote_plus(sUrl) + '"]'
            log('xVAULT -> [pyLoadHandler]: PyLoad API call: ' + py_url, LOGNOTICE)
            sock = opener.open(py_url).read()
            sock.close()
            return True
        except HTTPError as e:
            log('xVAULT -> [pyLoadHandler]: unable to send link: Error= ' + str(sys.exc_info()[0]), LOGNOTICE)
            log(str(e.code), LOGNOTICE)
            try:
                sock.close()
            except Exception:
                log('xVAULT -> [pyLoadHandler]: unable to close socket...', LOGNOTICE)
            return False
