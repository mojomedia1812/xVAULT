# -*- coding: utf-8 -*-
# Python 3

import re

from resources.lib import control
from xbmc import LOGINFO as LOGNOTICE, log
from urllib.request import Request, urlopen
from urllib.parse import urlencode


def package_name(metadata=None, source=None, fallback=''):
    """Name the JD2 package, leaving original filenames to JD2/Packagizer."""
    metadata = metadata if isinstance(metadata, dict) else {}
    source = source if isinstance(source, dict) else {}

    def text(value):
        return re.sub(r'[\x00-\x1f\x7f]', '', str(value if value is not None else '')).strip()

    def number(value, minimum):
        value = text(value)
        return int(value) if value.isdigit() and int(value) >= minimum else None

    season = number(metadata.get('season'), 0)
    episode = number(metadata.get('episode'), 1)
    series = metadata.get('mediatype') in ('episode', 'tvshow', 'season', 'tv') or episode is not None
    title = text(metadata.get('tvshowtitle') if series else '') or text(metadata.get('title')) or text(metadata.get('originaltitle'))
    if title:
        name = title
        if series:
            if season is not None and episode is not None:
                name += ' S%02dE%02d' % (season, episode)
        else:
            year = text(metadata.get('year'))
            if re.fullmatch(r'[1-9][0-9]{3}', year):
                name += ' (%s)' % year
    else:
        # Older context menus already carry a formatted title/year or SxxExx.
        name = text(fallback)
    quality = text(source.get('quality'))
    if name and quality.casefold() not in ('', '0', 'none', 'unknown', 'unbekannt', 'n/a', 'na', '?', '-'):
        name += ' [%s]' % quality
    return name


class cJDownloader2Handler:
    def sendToJDownloader2(self, sUrl, metadata=None, source=None, name=''):
        if self.__checkConfig() is False:
            control.infoDialog('Einstellungen nicht konfiguriert', heading='JDownloader 2', icon='ERROR')
            return False

        if self.__checkConnection() is False:
            control.infoDialog('Verbindung fehlgeschlagen', heading='JDownloader 2', icon='ERROR')
            return False

        if self.__download(sUrl, package_name(metadata, source, name)) is True:
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

    def __download(self, sFileUrl, package=''):
        log('xVAULT -> [jdownloader2Handler]: JD2 Link: ' + str(sFileUrl), LOGNOTICE)
        params = {'passwords': 'myPassword', 'source': 'http://jdownloader.org/spielwiese', 'urls': sFileUrl, 'submit': 'Add Link to JDownloader'}
        if package:
            params['package'] = package
        directory = control.getSetting('jd2_directory').strip()
        if directory:
            params['dir'] = directory
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
