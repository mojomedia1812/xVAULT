# -*- coding: UTF-8 -*-

import json

from resources.lib.control import getSetting, quote_plus
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHoster
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'cineto'
SITE_DOMAIN = 'cine.to'
SITE_NAME = 'CINE.TO'


class source:
    def __init__(self):
        self.priority = 7
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.sources = []
        self._seen = set()

    def run(self, titles, year, season=0, episode=0, imdb=''):
        if int(season or 0) > 0:
            return self.sources
        try:
            clean_titles = set([cleantitle.get(title) for title in titles if title])
            for title in titles:
                for entry in self._search(title):
                    if not self._matches(entry, clean_titles, year, imdb):
                        continue
                    for language_id, language_code in self._language_ids(entry):
                        self._add_links(entry.get('imdb') or entry.get('id'), language_id, language_code)
                    if len(self.sources) >= 20:
                        return self.sources
        except:
            pass
        return self.sources

    def resolve(self, url):
        return url

    def _search(self, title):
        payload = self._post_json('/request/search', {
            'kind': 'all',
            'genre': '',
            'rating': '0',
            'year': '0',
            'term': title,
            'language': self._preferred_language_id(),
            'page': '1',
            'count': '12'
        })
        if not isinstance(payload, dict) or not payload.get('status'):
            return []
        return payload.get('entries', []) or []

    def _add_links(self, imdb_id, language_id, language_code):
        if not imdb_id:
            return
        imdb_id = str(imdb_id).replace('tt', '').zfill(7)
        payload = self._post_json('/request/links', {'ID': imdb_id, 'lang': language_id})
        if not isinstance(payload, dict) or not payload.get('status'):
            return
        for hoster, links in (payload.get('links') or {}).items():
            if not isinstance(links, list) or len(links) < 2:
                continue
            quality = self._quality(links[0])
            for mirror_id in links[1:]:
                self._add_source(self.base_link + '/out/%s' % mirror_id, hoster, quality, language_code)

    def _add_source(self, url, hoster, quality, language_code):
        if not url or url in self._seen:
            return
        self._seen.add(url)
        is_blocked, resolved_hoster, clean_url, prio_hoster = isBlockedHoster(url, isResolve=False)
        if is_blocked or not clean_url:
            return
        self.sources.append({
            'source': resolved_hoster or hoster or SITE_NAME,
            'quality': quality,
            'language': language_code,
            'url': clean_url,
            'direct': False,
            'prioHoster': prio_hoster,
            'info': hoster or ''
        })

    def _post_json(self, path, params):
        request = cRequestHandler(self.base_link + path, caching=False)
        request.addHeaderEntry('Accept', 'application/json, text/javascript, */*; q=0.01')
        request.addHeaderEntry('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
        request.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
        request.addHeaderEntry('Origin', self.base_link)
        request.addHeaderEntry('Referer', self.base_link + '/')
        for key, value in params.items():
            request.addParameters(key, value)
        payload = request.request()
        if not payload:
            return {}
        return json.loads(payload)

    def _matches(self, entry, clean_titles, year, imdb):
        entry_imdb = str(entry.get('imdb') or entry.get('id') or '').replace('tt', '').zfill(7)
        if imdb and entry_imdb and imdb.replace('tt', '').zfill(7) == entry_imdb:
            return True
        if cleantitle.get(entry.get('title', '')) not in clean_titles:
            return False
        try:
            if year and entry.get('year') and abs(int(entry.get('year')) - int(year)) > 1:
                return False
        except:
            pass
        return True

    def _language_ids(self, entry):
        available = str(entry.get('language', '')).split(',')
        preferred = self._preferred_language_id()
        mapping = {'1': 'en', '2': 'de'}
        if preferred != '0':
            return [(preferred, mapping.get(preferred, 'unknown'))] if preferred in available else []
        return [(lang, mapping.get(lang, 'unknown')) for lang in available if lang in mapping]

    @staticmethod
    def _preferred_language_id():
        setting = getSetting('hosts.language') or '0'
        if setting == '1':
            return '2'
        if setting == '2':
            return '1'
        return '0'

    @staticmethod
    def _quality(value):
        return {'0': 'CAM', '1': 'SD', '2': 'SD', '3': 'HD', 0: 'CAM', 1: 'SD', 2: 'SD', 3: 'HD'}.get(value, 'HD')
