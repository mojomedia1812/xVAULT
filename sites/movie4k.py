# -*- coding: UTF-8 -*-

import json
import re

from resources.lib.control import getSetting, quote_plus, setSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHoster
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'movie4k'
SITE_DOMAIN = 'movie4k.sx'
SITE_NAME = SITE_IDENTIFIER.upper()
LEGACY_DOMAINS = ('movie4k-to.cfd', 'www.movie4k-to.cfd', 'movie4k.to', 'www.movie4k.to')


class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        if self.domain in LEGACY_DOMAINS:
            self.domain = SITE_DOMAIN
            setSetting('provider.' + SITE_IDENTIFIER + '.domain', self.domain)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/data/search/?lang=%s&keyword=%s'
        self.watch_link = self.base_link + '/data/watch/?_id=%s'
        self.checkHoster = False if getSetting('provider.movie4k.checkHoster') == 'false' else True
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb=''):
        try:
            streams = self.search(titles, year, season, episode)
            if not streams:
                return self.sources

            total = 0
            for item in streams:
                stream_url = self._clean_stream_url(item.get('stream', ''))
                if not stream_url:
                    continue

                is_blocked, hoster, url, prio_hoster = isBlockedHoster(stream_url, isResolve=self.checkHoster)
                if is_blocked or not url:
                    continue

                self.sources.append({
                    'source': hoster,
                    'quality': self._quality(item),
                    'language': item.get('_xvault_language', 'de'),
                    'url': url,
                    'direct': True if self.checkHoster else False,
                    'prioHoster': prio_hoster,
                    'info': item.get('_xvault_language_label', '')
                })
                total += 1
                if total >= 10:
                    break
        except:
            pass
        return self.sources

    def resolve(self, url):
        return url

    def _request_json(self, url, referer=None):
        request = cRequestHandler(url, caching=True)
        request.addHeaderEntry('Accept', 'application/json, text/plain, */*')
        request.addHeaderEntry('Referer', referer or (self.base_link + '/'))
        request.addHeaderEntry('Origin', self.base_link)
        request.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
        payload = request.request()
        if not payload or payload in ('SEITE NICHT ERREICHBAR', 'URL FEHLER', 'TIMEOUT', 'CLOUDFLARE-SCHUTZ AKTIV'):
            return None
        if '"success":false' in payload and 'request options must be set' in payload:
            return None
        return json.loads(payload)

    def _language_queries(self):
        setting = getSetting('hosts.language') or '0'
        if setting == '1':
            return [('2', 'de', 'Deutsch')]
        if setting == '2':
            return [('3', 'en', 'Englisch')]
        return [('2', 'de', 'Deutsch'), ('3', 'en', 'Englisch')]

    def _language_from_item(self, item, fallback_code, fallback_label):
        value = str(item.get('lang', '')).strip()
        if value == '2':
            return 'de', 'Deutsch'
        if value == '3':
            return 'en', 'Englisch'
        return fallback_code, fallback_label

    def _matches_result(self, item, clean_titles, year, season):
        title = self._title_without_season(str(item.get('title', '')))
        if not title:
            return False

        is_tv = str(item.get('tv', '0')) == '1'
        if season:
            if not is_tv:
                return False
            try:
                if int(item.get('s', 0)) != int(season):
                    return False
            except:
                return False
            return self._title_matches(title, clean_titles)

        if is_tv:
            return False
        if not self._title_matches(title, clean_titles):
            return False
        try:
            api_year = int(item.get('year', 0))
            req_year = int(year or 0)
            if api_year and req_year and abs(api_year - req_year) > 1:
                return False
        except:
            pass
        return True

    def _title_matches(self, title, clean_titles):
        api_title = cleantitle.get(title)
        if api_title in clean_titles:
            return True
        for clean_title in clean_titles:
            if not clean_title:
                continue
            if api_title.startswith(clean_title) or clean_title.startswith(api_title):
                return True
        return False

    @staticmethod
    def _title_without_season(title):
        title = re.sub(r'\s*[-:]\s*(Staffel|Season)\s*\d+.*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()
        return title

    @staticmethod
    def _is_deleted(item):
        value = item.get('deleted')
        return value is True or str(value).strip() == '1'

    @staticmethod
    def _clean_stream_url(url):
        if not url:
            return ''
        url = str(url).strip()
        if url.startswith('https:///'):
            return 'https://' + url[9:]
        if url.startswith('http:///'):
            return 'http://' + url[8:]
        if url.startswith('//'):
            return 'https:' + url
        return url

    @staticmethod
    def _quality(item):
        values = [
            item.get('release', ''),
            item.get('quality', ''),
            item.get('res', ''),
            item.get('stream', '')
        ]
        text = ' '.join([str(value or '') for value in values]).lower()
        if '2160' in text or '4k' in text:
            return '4K'
        if '1440' in text or '2k' in text:
            return '1440p'
        if '1080' in text:
            return '1080p'
        if '720' in text:
            return '720p'
        if '480' in text:
            return '480p'
        if '360' in text:
            return '360p'
        return 'HD'

    def search(self, titles, year, season, episode):
        streams = []
        clean_titles = set([cleantitle.get(item) for item in set(titles) if item])
        seen_ids = set()
        seen_streams = set()

        for lang, language_code, language_label in self._language_queries():
            for title in titles:
                try:
                    search_url = self.search_link % (lang, quote_plus(title))
                    data = self._request_json(search_url, self.base_link + '/browse?keyword=%s' % quote_plus(title))
                    if not isinstance(data, list):
                        continue

                    matches = [item for item in data if self._matches_result(item, clean_titles, year, season)]
                    for match in matches:
                        media_id = match.get('_id')
                        if not media_id or media_id in seen_ids:
                            continue
                        seen_ids.add(media_id)

                        watch = self._request_json(self.watch_link % media_id, self.base_link + '/watch/%s/%s' % (match.get('slug', 'movie'), media_id))
                        if not isinstance(watch, dict):
                            continue

                        stream_language, stream_language_label = self._language_from_item(watch, language_code, language_label)
                        for stream in watch.get('streams', []) or []:
                            if self._is_deleted(stream):
                                continue
                            if season and str(stream.get('e', '')) != str(episode):
                                continue
                            stream_url = self._clean_stream_url(stream.get('stream', ''))
                            if not stream_url or stream_url in seen_streams:
                                continue
                            seen_streams.add(stream_url)
                            stream['_xvault_language'] = stream_language
                            stream['_xvault_language_label'] = stream_language_label
                            streams.append(stream)
                            if len(streams) >= 60:
                                return streams
                except:
                    continue
        return streams
