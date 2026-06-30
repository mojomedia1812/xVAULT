# -*- coding: UTF-8 -*-
import re
import json
import urllib.request
from resources.lib.tools import logger
from resources.lib.control import getSetting, urlparse, quote_plus

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
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.imdb_link = self.base_link + '/data/browse/?lang=%s&order_by=new&page=1&imdb=%s'
        self.search_link = self.base_link + '/data/browse/?lang=%s&keyword=%s&year=%s&type=%s&page=1'
        self.watch_links = [
            self.base_link + '/data/watch/?_id=%s',
            self.base_link + '/data/watch?_id=%s'
        ]
        self.sources = []

    def _request(self, url, cache=0, log_errors=True):
        try:
            headers = {
                'User-Agent': UA,
                'Referer': self.base_link + '/',
                'Origin': self.base_link,
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/plain, */*'
            }
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=15) as response:
                sResponse = response.read().decode('utf-8', 'replace')
            if not sResponse:
                if log_errors:
                    logger.error('[%s] Leere Antwort von %s' % (SITE_NAME, url))
                return None
            return json.loads(sResponse)
        except Exception as e:
            if log_errors:
                logger.error('[%s] Request-Fehler: %s' % (SITE_NAME, str(e)))
            return None

    def _watchRequest(self, media_id):
        for watch_link in self.watch_links:
            data = self._request(watch_link % media_id, cache=60 * 10, log_errors=False)
            if data and isinstance(data.get('streams'), list):
                return data
        return None

    def _languageQueries(self):
        setting = getSetting('hosts.language') or '0'
        if setting == '2':
            return ['3']
        return ['4']

    def _languageFromWatch(self, data, title=''):
        value = str(data.get('lang', '')).strip()
        if value == '2':
            return 'de', 'Deutsch'
        if value == '3':
            return 'en', 'Englisch'
        if value == '4':
            return 'multi', 'Mehrsprachig'

        title = str(title)
        if re.search(r'\bStaffel\b', title, re.IGNORECASE):
            return 'de', 'Deutsch'
        if re.search(r'\bSeason\b', title, re.IGNORECASE):
            return 'en', 'Englisch'
        return 'de', 'Deutsch'

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

        movies = []
        seen_ids = set()

        for lang in self._languageQueries():
            if imdb:
                aJson = self._request(self.imdb_link % (lang, imdb), cache=60 * 60 * 24, log_errors=False)
                if aJson and isinstance(aJson.get('movies'), list) and len(aJson['movies']) > 0:
                    logger.info('[%s] IMDB-Treffer lang=%s: %d Eintraege' % (SITE_NAME, lang, len(aJson['movies'])))
                    for movie in aJson['movies']:
                        media_id = str(movie.get('_id', ''))
                        if media_id and media_id not in seen_ids:
                            seen_ids.add(media_id)
                            movies.append(movie)

            if len(movies) == 0:
                mediaType = 'tvseries' if season else 'movies'
                for title in titles:
                    aJson = self._request(self.search_link % (lang, quote_plus(title), '' if season else year, mediaType), cache=60 * 60 * 6)
                    if not aJson or not isinstance(aJson.get('movies'), list):
                        continue
                    logger.info('[%s] Suchtreffer lang=%s: %d Eintraege' % (SITE_NAME, lang, len(aJson['movies'])))
                    for movie in aJson['movies']:
                        media_id = str(movie.get('_id', ''))
                        if media_id and media_id not in seen_ids:
                            seen_ids.add(media_id)
                            movies.append(movie)

        if len(movies) == 0:
            logger.error('[%s] Keine oder ungueltige API-Antwort' % SITE_NAME)
            return self.sources

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
                    try:
                        if sYear and len(sYear) == 4 and abs(int(sYear) - int(year)) > 1:
                            continue
                    except:
                        pass
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
        aJson = self._watchRequest(data[0])
        if not aJson or not isinstance(aJson.get('streams'), list):
            logger.error('[%s] Keine Streams fuer ID %s' % (SITE_NAME, data[0]))
            return

        sQuality = _parseQuality(data[1])
        isTvshow = len(data) > 2
        language, language_label = self._languageFromWatch(aJson, aJson.get('title', ''))
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
                'language': language,
                'url': sUrl,
                'direct': bDirect,
                'prioHoster': 0,
                'info': language_label
            })

        logger.info('[%s] %d Quellen' % (SITE_NAME, len(self.sources)))

    def resolve(self, url):
        try:
            return url
        except:
            return
