# -*- coding: UTF-8 -*-

import json
import re

from html import unescape as html_unescape
from urllib.parse import quote_plus

from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger
from scrapers.modules import cleantitle


SITE_IDENTIFIER = 'internetarchive'
SITE_DOMAIN = 'archive.org'
SITE_NAME = 'Internet Archive'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0'


class source:
    def __init__(self):
        self.priority = 10
        self.language = ['de', 'en']
        self.domain = SITE_DOMAIN
        self.base_link = 'https://' + self.domain
        self.sources = []
        self._seen = set()

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        if int(season or 0) > 0:
            return self.sources

        try:
            clean_titles = set([cleantitle.get(title) for title in titles if title])
            for title in titles:
                if not title:
                    continue
                for item in self._search(title):
                    if not self._matches(item, clean_titles, year):
                        continue
                    self._add_metadata_source(item, year)
                    if len(self.sources) >= 6:
                        return self.sources
        except Exception as exc:
            logger.error('[%s] Fehler: %s' % (SITE_NAME, exc))
        return self.sources

    def resolve(self, url):
        return url

    def _search(self, title):
        query = 'title:("%s") AND mediatype:(movies)' % title.replace('"', '')
        params = [
            ('q', query),
            ('fl[]', 'identifier'),
            ('fl[]', 'title'),
            ('fl[]', 'year'),
            ('fl[]', 'language'),
            ('rows', '10'),
            ('page', '1'),
            ('output', 'json')
        ]
        url = self.base_link + '/advancedsearch.php?' + '&'.join(
            ['%s=%s' % (key, quote_plus(value)) for key, value in params]
        )
        data = self._request_json(url, self.base_link)
        if not isinstance(data, dict):
            return []
        response = data.get('response') if isinstance(data.get('response'), dict) else {}
        return response.get('docs') or []

    def _add_metadata_source(self, item, year):
        identifier = item.get('identifier')
        if not identifier:
            return
        metadata = self._request_json(self.base_link + '/metadata/' + quote_plus(identifier), self.base_link)
        if not isinstance(metadata, dict):
            return
        media_file = self._best_media_file(metadata.get('files') or [])
        if not media_file:
            return
        filename = media_file.get('name') or ''
        url = self.base_link + '/download/%s/%s' % (quote_plus(identifier), quote_plus(filename))
        if url in self._seen:
            return
        self._seen.add(url)

        self.sources.append({
            'source': SITE_NAME,
            'quality': self._quality(filename),
            'language': self._language(item.get('language') or metadata.get('metadata', {}).get('language')),
            'url': url,
            'direct': True,
            'debridonly': False,
            'prioHoster': 120,
            'info': self._info(item, media_file, year)
        })

    def _best_media_file(self, files):
        candidates = []
        for entry in files:
            name = entry.get('name') or ''
            if not re.search(r'\.(?:mp4|mkv|webm)$', name, re.I):
                continue
            lower = name.lower()
            if any(token in lower for token in ['sample', 'trailer', 'thumb', 'preview']):
                continue
            try:
                size = int(entry.get('size') or 0)
            except:
                size = 0
            if size < 50 * 1024 * 1024:
                continue
            candidates.append((self._quality_score(name), size, entry))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][2]

    def _matches(self, item, clean_titles, year):
        title = html_unescape(str(item.get('title') or ''))
        item_year = self._year(item.get('year') or title)
        clean = cleantitle.get(re.sub(r'\(?\b(?:19|20)\d{2}\b\)?', ' ', title))
        if clean not in clean_titles:
            return False
        if year:
            if not item_year:
                return False
            try:
                if abs(int(item_year) - int(year)) > 1:
                    return False
            except:
                return False
        return True

    @staticmethod
    def _request_json(url, referer=None):
        request = cRequestHandler(url, caching=True, preserve_url=True)
        request.addHeaderEntry('User-Agent', UA)
        request.addHeaderEntry('Accept', 'application/json, text/plain, */*')
        if referer:
            request.addHeaderEntry('Referer', referer)
        payload = request.request()
        if not payload:
            return {}
        try:
            return json.loads(payload)
        except:
            return {}

    @staticmethod
    def _quality(filename):
        text = (filename or '').lower()
        if '2160' in text or '4k' in text:
            return '4K'
        if '1440' in text:
            return '1440p'
        if '1080' in text:
            return '1080p'
        if '720' in text:
            return '720p'
        return 'SD'

    def _quality_score(self, filename):
        return {'4K': 5, '1440p': 4, '1080p': 3, '720p': 2, 'SD': 1}.get(self._quality(filename), 0)

    @staticmethod
    def _language(value):
        text = ' '.join(value) if isinstance(value, list) else str(value or '')
        text = re.sub(r'[^a-z0-9]+', ' ', text.lower())
        tokens = set([token for token in text.split() if token])
        if tokens.intersection(set(['de', 'deu', 'ger', 'german', 'deutsch'])):
            return 'de'
        if tokens.intersection(set(['en', 'eng', 'english', 'englisch'])):
            return 'en'
        return 'unknown'

    @staticmethod
    def _year(value):
        match = re.search(r'\b((?:19|20)\d{2})\b', str(value or ''))
        return match.group(1) if match else ''

    @staticmethod
    def _info(item, media_file, requested_year):
        values = []
        if item.get('title'):
            values.append(str(item.get('title')))
        if requested_year:
            values.append(str(requested_year))
        if media_file.get('format'):
            values.append(str(media_file.get('format')))
        return ' | '.join(values)
