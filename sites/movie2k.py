# -*- coding: UTF-8 -*-
from resources.lib.utils import isBlockedHoster
import re, json
import urllib.request
from resources.lib.control import getSetting, quote_plus
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'movie2k'
SITE_DOMAIN = 'movie2k.ch' 
SITE_NAME = SITE_IDENTIFIER.upper()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/data/browse/?lang=%s&keyword=%s&year=%s&type=%s&page=1'
        self.watch_link = self.base_link + '/data/watch/?_id=%s'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb=''):
        jSearch = self.search(titles, year, season, episode)
        if jSearch == [] or jSearch == 0: return
        jSearch = sorted(jSearch, key=lambda k: k.get('added', ''), reverse=True)
        total = 0
        loop = 0
        for i in range(len(jSearch)):
            sUrl = jSearch[i]['stream']
            #if 'streamtape' in sUrl: continue
            loop += 1
            if loop == 50:
                break

            release = jSearch[i].get('release', '')
            if '2160' in release or '4K' in release:
                quality = '4K'
            elif '1440' in release or '2K' in release:
                quality = '1440p'
            elif '1080' in release:
                quality = '1080p'
            elif '720' in release:
                quality = '720p'
            elif '480' in release:
                quality = '480p'
            elif '360' in release:
                quality = '360p'
            else:
                quality = 'HD'

            isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
            if isBlocked: continue
            if url:
                language = jSearch[i].get('_xvault_language', 'de')
                language_label = jSearch[i].get('_xvault_language_label', '')
                self.sources.append({'source': hoster, 'quality': quality, 'language': language, 'url': url, 'direct': True, 'prioHoster': prioHoster, 'info': language_label})
                total += 1
                if total == 10: break
        return self.sources

    def resolve(self, url):
        return  url

    def _ajax_headers(self, referer=None):
        return {
            'User-Agent': UA,
            'Accept': 'application/json, text/plain, */*',
            'Referer': referer or (self.base_link + '/'),
            'Origin': self.base_link,
            'X-Requested-With': 'XMLHttpRequest'
        }

    def _request_json(self, url, referer=None):
        request = urllib.request.Request(url, headers=self._ajax_headers(referer))
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read().decode('utf-8', 'replace')
        if not payload or '"success":false' in payload:
            return None
        payload = re.sub(r'\\\s+\\', '\\\\', payload)
        return json.loads(payload)

    def _language_queries(self):
        setting = getSetting('hosts.language') or '0'
        if setting == '2':
            return ['3']
        return ['4']

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

    def _match_search_result(self, item, clean_titles, year, season):
        title = str(item.get('title', ''))
        if not title:
            return False

        if season > 0:
            season_match = re.search(r'Staffel\s+(\d+)|Season\s+(\d+)', title, re.IGNORECASE)
            if not season_match:
                return False
            found_season = season_match.group(1) or season_match.group(2)
            if str(found_season) != str(season):
                return False
            series_title = re.sub(r'\s*[-:]\s*(Staffel|Season)\s*\d+.*', '', title, flags=re.IGNORECASE).strip()
            return cleantitle.get(series_title) in clean_titles

        if re.search(r'\b(Staffel|Season)\s+\d+', title, re.IGNORECASE):
            return False

        api_title = re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()
        if cleantitle.get(api_title) not in clean_titles:
            return False
        try:
            api_year = int(item.get('year', 0))
            req_year = int(year)
            if api_year and req_year and abs(api_year - req_year) > 1:
                return False
        except:
            pass
        return True

    def search(self, titles, year, season, episode):
        jSearch = []
        mtype = 'movies'
        if season > 0:
            year = ''
            mtype = 'tvseries'

        clean_titles = set([cleantitle.get(i) for i in set(titles) if i])
        seen_ids = set()

        for lang in self._language_queries():
            for title in titles:
                try:
                    query = self.search_link % (lang, quote_plus(title), year, mtype)
                    data = self._request_json(query, self.base_link + '/browse?keyword=%s' % quote_plus(title))
                    movies = data.get('movies', []) if data else []
                    if not movies:
                        continue

                    matches = [i for i in movies if self._match_search_result(i, clean_titles, year, season)]
                    for match in matches:
                        media_id = match.get('_id', False)
                        if not media_id or media_id in seen_ids:
                            continue
                        seen_ids.add(media_id)

                        watch = self._request_json(self.watch_link % media_id, self.base_link + '/browse?keyword=%s' % quote_plus(title))
                        if not watch:
                            continue

                        language, language_label = self._language_from_watch(watch, match.get('title', ''))
                        streams = watch.get('streams', [])

                        if season > 0:
                            streams = [i for i in streams if i.get('e', False) and str(i.get('e')) == str(episode)]

                        for stream in streams:
                            stream['_xvault_language'] = language
                            stream['_xvault_language_label'] = language_label
                            jSearch.append(stream)

                        if len(jSearch) >= 60:
                            return jSearch
                except:
                    continue

        return jSearch
