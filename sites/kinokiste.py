# -*- coding: UTF-8 -*-
import re
import json
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger
from resources.lib.control import getSetting, urlparse

SITE_IDENTIFIER = 'kinokiste'
SITE_DOMAIN = 'kinokiste.eu'
SITE_NAME = SITE_IDENTIFIER.upper()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

DIRECT_EXTENSIONS = ('.m3u8', '.mp4', '.mkv', '.avi', '.ts')

BROKEN_HOSTERS = ['veev.to', 'veev.cc', 'voe.sx', 'voe.to']

QUALITY_MAP = [
    ('4K',    ['4k', 'uhd', '2160']),
    ('1080p', ['1080']),
    ('720p',  ['720']),
    ('HD',    ['hd', 'web', 'webrip', 'bluray', 'bdrip', 'brrip']),
    ('HDCAM', ['hdcam']),
    ('SD',    ['sd', 'dvd', 'dvdrip']),
    ('TS',    ['ts', 'telesync', 'tc']),
    ('CAM',   ['cam']),
]

QUALITY_ORDER = ['4K', '1080p', '720p', 'HD', 'HDCAM', 'SD', 'TS', 'CAM']

def _parseQuality(raw):
    s = raw.lower()
    for label, keys in QUALITY_MAP:
        if any(k in s for k in keys):
            return label
    return raw[:20] if raw else 'SD'

def _qualityRank(q):
    try:
        return QUALITY_ORDER.index(q)
    except:
        return 99

def _isDirect(url):
    path = urlparse(url).path.lower().split('?')[0]
    return any(path.endswith(ext) for ext in DIRECT_EXTENSIONS)

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.imdb_link = self.base_link + '/data/browse/?lang=2&order_by=new&page=1&imdb=%s'
        self.search_link = self.base_link + '/data/browse/?lang=2&order_by=new&page=1&limit=0'
        self.watch_link = self.base_link + '/data/watch/?_id=%s'
        self.sources = []

    def _request(self, url, cache=0):
        try:
            oRequest = cRequestHandler(url)
            oRequest.addHeaderEntry('User-Agent', UA)
            oRequest.addHeaderEntry('Referer', self.base_link + '/')
            oRequest.addHeaderEntry('Origin', self.base_link)
            oRequest.cacheTime = cache
            sResponse = oRequest.request()
            if not sResponse:
                logger.error('[%s] Leere Antwort von %s' % (SITE_NAME, url))
                return None
            return json.loads(sResponse)
        except Exception as e:
            logger.error('[%s] Request-Fehler: %s' % (SITE_NAME, str(e)))
            return None

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        search_terms = []
        sMainTitle = ''
        for t in titles:
            if not t:
                continue
            sBase = re.sub(r'\s*\(\d{4}\)\s*$', '', t).strip()
            if not sMainTitle:
                sMainTitle = sBase
            search_terms.append(sBase.replace(' ', '').lower())
            search_terms.append(sBase.lower())

        if not sMainTitle:
            return self.sources

        logger.info('[%s] Suche: "%s" imdb=%s year=%s season=%s episode=%s' % (SITE_NAME, sMainTitle, imdb, year, season, episode))

        movies = None

        if imdb:
            aJson = self._request(self.imdb_link % imdb, cache=60 * 60 * 24)
            if aJson and isinstance(aJson.get('movies'), list) and len(aJson['movies']) > 0:
                logger.info('[%s] IMDB-Treffer: %d Eintraege' % (SITE_NAME, len(aJson['movies'])))
                movies = aJson['movies']

        if movies is None:
            aJson = self._request(self.search_link, cache=60 * 60 * 6)
            if not aJson or not isinstance(aJson.get('movies'), list):
                logger.error('[%s] Keine oder ungueltige API-Antwort' % SITE_NAME)
                return self.sources
            movies = aJson['movies']
            logger.info('[%s] Fallback: %d Eintraege geladen' % (SITE_NAME, len(movies)))

        matches = []
        for movie in movies:
            if '_id' not in movie:
                continue
            sTitle = str(movie.get('title', ''))
            isTvshow = 'Staffel' in sTitle or 'Season' in sTitle
            if season == 0 and isTvshow:
                continue
            if season != 0 and not isTvshow:
                continue
            sYear = str(movie.get('year', ''))
            sQuality = str(movie.get('quality', ''))

            if season == 0:
                sApiBase = re.sub(r'\s*\(\d{4}\)\s*$', '', sTitle).strip()
                sApiNsp = sApiBase.replace(' ', '').lower()
                sApiLower = sApiBase.lower()
                if any(st in sApiNsp or st in sApiLower for st in search_terms):
                    if sYear and len(sYear) == 4 and abs(int(sYear) - int(year)) > 1:
                        continue
                    logger.info('[%s] Treffer: "%s"' % (SITE_NAME, sTitle))
                    matches.append((str(movie['_id']), sQuality))
            else:
                mSeason = re.search(r'Staffel\s+(\d+)|Season\s+(\d+)', sTitle, re.IGNORECASE)
                sSeason = (mSeason.group(1) or mSeason.group(2)) if mSeason else '1'
                sBase = re.sub(r'\s*[-–]\s*(Staffel|Season)\s*\d+.*', '', sTitle, flags=re.IGNORECASE).strip()
                sBase = re.sub(r'\s*\(\d{4}\)\s*$', '', sBase).strip()
                if any(st in sBase.replace(' ', '').lower() or st in sBase.lower() for st in search_terms):
                    if int(sSeason) == int(season):
                        logger.info('[%s] Serien-Treffer: "%s" S%s' % (SITE_NAME, sTitle, sSeason))
                        matches.append((str(movie['_id']), sQuality, int(sSeason)))

        logger.info('[%s] %d Match(es) gefunden' % (SITE_NAME, len(matches)))

        for match in matches:
            self._getStreams(match, episode, hostDict)

        return self.sources

    def _getStreams(self, data, episode, hostDict):
        aJson = self._request(self.watch_link % data[0], cache=60 * 10)
        if not aJson or not isinstance(aJson.get('streams'), list):
            logger.error('[%s] Keine Streams fuer ID %s' % (SITE_NAME, data[0]))
            return

        sQuality = _parseQuality(data[1])
        isTvshow = len(data) > 2
        logger.info('[%s] %d Streams fuer ID %s' % (SITE_NAME, len(aJson['streams']), data[0]))

        best_per_domain = {}

        for stream in aJson['streams']:
            if isTvshow and 'e' in stream and str(stream['e']) != str(episode):
                continue
            if 'stream' not in stream:
                continue
            sUrl = stream['stream']
            if sUrl.startswith('//'):
                sUrl = 'https:' + sUrl

            sDomain = urlparse(sUrl).hostname or ''
            if not sDomain:
                continue

            if any(b in sDomain for b in BROKEN_HOSTERS):
                logger.info('[%s] Hoster geblockt: %s' % (SITE_NAME, sDomain))
                continue

            bDirect = _isDirect(sUrl)

            if not bDirect and hostDict:
                sDomainShort = '.'.join(sDomain.split('.')[-2:])
                if not any(sDomainShort in h or sDomain in h for h in hostDict):
                    continue

            quality = _parseQuality(str(stream['release'])) if stream.get('release') else sQuality

            if sDomain not in best_per_domain or _qualityRank(quality) < _qualityRank(best_per_domain[sDomain][1]):
                best_per_domain[sDomain] = (sUrl, quality, bDirect)

        for sDomain, (sUrl, quality, bDirect) in best_per_domain.items():
            self.sources.append({
                'source': sDomain,
                'quality': quality,
                'language': 'de',
                'url': sUrl,
                'direct': bDirect,
                'prioHoster': 0
            })

        logger.info('[%s] %d Quellen' % (SITE_NAME, len(self.sources)))

    def resolve(self, url):
        try:
            return url
        except:
            return
