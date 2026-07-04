# -*- coding: utf-8 -*-
from scrapers.modules.tools import cParser
from scrapers.modules import cleantitle
from resources.lib.control import getSetting, quote_plus
from resources.lib.requestHandler import cRequestHandler
import re
try:
    from json import loads
except:
    from simplejson import loads

SITE_IDENTIFIER = 'kkiste'
SITE_DOMAIN = 'kkiste.eu'
SITE_NAME = 'KKiste'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.browse_link = self.base_link + '/data/browse/?lang=%s&keyword=%s&year=%s&type=%s&page=1'
        self.watch_links = [
            self.base_link + '/data/watch/?_id=%s',
            self.base_link + '/data/watch?_id=%s'
        ]
        
        
        self.hoster_priority = {
            'streamtape': 5,
            'voe': 10,
            'doodstream': 5,
            'mixdrop': 9,
            'streamwish': 8,
            'filemoon': 5,
            'vidoza': 7,
            'upstream': 5,
            'streamruby': 10,
            'vidguard': 6
        }
        self.min_priority = 6  
        self.max_per_hoster = 5  

    def _ajax_headers(self, referer=None):
        return {
            'User-Agent': UA,
            'Accept': 'application/json, text/plain, */*',
            'Referer': referer or (self.base_link + '/'),
            'Origin': self.base_link,
            'X-Requested-With': 'XMLHttpRequest'
        }

    def _request_json(self, url, referer=None):
        request = cRequestHandler(url, caching=True)
        for key, value in self._ajax_headers(referer).items():
            request.addHeaderEntry(key, value)
        sJson = request.request()
        if not sJson:
            return None
        return loads(sJson)

    def _watch_json(self, media_id, referer=None):
        for watch_link in self.watch_links:
            try:
                data = self._request_json(watch_link % media_id, referer)
                if data and isinstance(data.get('streams'), list):
                    return data
            except:
                pass
        return None

    def _language_queries(self):
        setting = getSetting('hosts.language') or '0'
        if setting == '1':
            return ['2']
        if setting == '2':
            return ['3']
        return ['2', '3']

    def _language_from_watch(self, data, title=''):
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

    def _match_search_result(self, movie, clean_titles, year, season):
        sTitle = str(movie.get('title', ''))
        if not sTitle:
            return False

        if season == 0:
            if re.search(r'\b(Staffel|Season)\s+\d+', sTitle, re.IGNORECASE):
                return False
            if cleantitle.get(re.sub(r'\s*\(\d{4}\)\s*$', '', sTitle).strip()) not in clean_titles:
                return False
            try:
                sYear = int(movie.get('year', 0))
                reqYear = int(year)
                if sYear and reqYear and abs(sYear - reqYear) > 1:
                    return False
            except:
                pass
            return True

        seasonMatch = re.search(r'Staffel\s+(\d+)|Season\s+(\d+)', sTitle, re.IGNORECASE)
        if not seasonMatch:
            return False
        foundSeason = int(seasonMatch.group(1) or seasonMatch.group(2))
        if foundSeason != int(season):
            return False
        sSeriesTitle = re.sub(r'\s*[-:]\s*(Staffel|Season)\s*\d+.*', '', sTitle, flags=re.IGNORECASE).strip()
        return cleantitle.get(sSeriesTitle) in clean_titles

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        sources = []
        
        try:
            clean_titles = set([cleantitle.get(i) for i in set(titles) if i])
            mediaType = 'tvseries' if season > 0 else 'movies'
            found_ids = set()
            hoster_count = {}
            
            for lang in self._language_queries():
                for title in titles:
                    searchUrl = self.browse_link % (lang, quote_plus(title), '' if season > 0 else year, mediaType)
                    aJson = self._request_json(searchUrl, self.base_link + '/browse?keyword=%s' % quote_plus(title))
                    if not aJson or 'movies' not in aJson:
                        continue

                    for movie in aJson['movies']:
                        if '_id' not in movie or not self._match_search_result(movie, clean_titles, year, season):
                            continue

                        movie_id = str(movie['_id'])
                        if movie_id in found_ids:
                            continue
                        found_ids.add(movie_id)

                        watch_data = self._watch_json(movie_id, self.base_link + '/browse?keyword=%s' % quote_plus(title))
                        if not watch_data:
                            continue
                        language, language_label = self._language_from_watch(watch_data, movie.get('title', ''))

                        for stream in watch_data['streams']:
                            if season > 0:
                                if 'e' not in stream or int(stream['e']) != int(episode):
                                    continue
                            
                            if 'stream' not in stream:
                                continue
                            
                            sUrl = stream['stream']
                            
                            if 'youtube' in sUrl.lower() or 'vod' in sUrl.lower():
                                continue
                            
                            if sUrl.startswith('//'):
                                sUrl = 'https:' + sUrl
                            elif sUrl.startswith('/'):
                                sUrl = 'https:/' + sUrl
                            
                            isMatch, aName = cParser.parse(sUrl, '//([^/]+)/')
                            if not isMatch:
                                continue
                            
                            sName = aName[0]
                            if '.' in sName:
                                sName = sName[:sName.rindex('.')]
                            
                            priority = 0
                            for hoster, prio in self.hoster_priority.items():
                                if hoster in sName.lower():
                                    priority = prio
                                    break
                            
                            if priority < self.min_priority:
                                continue
                            
                            hoster_key = '%s:%s' % (language, sName.lower())
                            if hoster_key not in hoster_count:
                                hoster_count[hoster_key] = 0
                            
                            if hoster_count[hoster_key] >= self.max_per_hoster:
                                continue
                            
                            hoster_count[hoster_key] += 1
                            
                            quality = 'HD'
                            if 'release' in stream and stream['release']:
                                release = str(stream['release']).upper()
                                if 'CAM' in release or 'TS' in release:
                                    quality = 'CAM'
                                elif 'SD' in release:
                                    quality = 'SD'
                            
                            sources.append({
                                'source': sName,
                                'quality': quality,
                                'language': language,
                                'url': sUrl,
                                'direct': False,
                                'debridonly': False,
                                'priority': priority,
                                'info': language_label
                            })
            
            
            sources = sorted(sources, key=lambda x: x.get('priority', 0), reverse=True)
            return sources
            
        except:
            return []

    def resolve(self, url):
        return url
