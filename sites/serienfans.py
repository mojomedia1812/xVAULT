# -*- coding: UTF-8 -*-

import json
import re

from resources.lib.control import getSetting, quote_plus, urljoin
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHoster
from scrapers.modules import cleantitle, source_utils

try:
    from html import unescape as html_unescape
except ImportError:
    from HTMLParser import HTMLParser
    html_unescape = HTMLParser().unescape

SITE_IDENTIFIER = 'serienfans'
SITE_DOMAIN = 'serienfans.org'
SITE_NAME = SITE_IDENTIFIER.upper()


class source:
    def __init__(self):
        self.priority = 8
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.sources = []
        self._seen = set()

    def run(self, titles, year, season=0, episode=0, imdb=''):
        if int(season or 0) <= 0:
            return self.sources
        try:
            for series_url in self._find_series_pages(titles):
                self._read_season(series_url, season, episode)
                if len(self.sources) >= 20:
                    break
        except:
            pass
        return self.sources

    def resolve(self, url):
        return url

    def _find_series_pages(self, titles):
        clean_titles = set([cleantitle.get(title) for title in titles if title])
        urls = []
        for title in titles:
            letter = self._index_letter(title)
            html = self._request(self.base_link + '/index/%s' % letter, self.base_link)
            for href, label in self._index_entries(html):
                item_title = re.sub(r'\s*\(\d{4}\)\s*$', '', label).strip()
                if self._title_matches(item_title, clean_titles):
                    urls.append(urljoin(self.base_link, href))
        return self._unique(urls)

    def _read_season(self, series_url, season, episode):
        html = self._request(series_url, self.base_link)
        token = self._extract_season_token(html)
        if not token:
            return
        data = self._request_json(self.base_link + '/api/v1/%s/season/%s?lang=ALL' % (token, season), series_url)
        fragment = data.get('html', '') if isinstance(data, dict) else ''
        blocks = self._episode_blocks(fragment, season, episode)
        for block in blocks:
            release_name = self._clean(block)
            for href, label in re.findall(r'<a\b[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', block, re.I):
                self._add_external(urljoin(self.base_link, html_unescape(href)), self._clean(label), release_name)

    def _episode_blocks(self, html, season, episode):
        wanted = r'\bS0*%d\s*E0*%d\b' % (int(season or 0), int(episode or 0))
        blocks = []
        for match in re.finditer(wanted, html or '', re.I):
            start = max(0, html.rfind('<div', 0, match.start()))
            end = html.find('</div>', match.end())
            if start >= 0 and end > start:
                blocks.append(html[start:end + 6])
        return blocks

    def _add_external(self, url, hoster_label, release_name):
        final_url = self._final_url(url)
        if not final_url or final_url in self._seen:
            return
        self._seen.add(final_url)
        is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(final_url, isResolve=False)
        if is_blocked or not clean_url:
            return
        self.sources.append({
            'source': hoster or hoster_label or SITE_NAME,
            'quality': source_utils.check_url(release_name.lower()),
            'language': self._language(release_name),
            'url': clean_url,
            'direct': False,
            'prioHoster': prio_hoster,
            'info': release_name
        })

    def _final_url(self, url):
        request = cRequestHandler(url, caching=False)
        request.addHeaderEntry('Referer', self.base_link + '/')
        request.request()
        return request.getRealUrl() or url

    def _request(self, url, referer=None):
        request = cRequestHandler(url, caching=True)
        if referer:
            request.addHeaderEntry('Referer', referer)
        return request.request() or ''

    def _request_json(self, url, referer):
        request = cRequestHandler(url, caching=False)
        request.addHeaderEntry('Accept', 'application/json, text/javascript, */*; q=0.01')
        request.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
        request.addHeaderEntry('Referer', referer)
        payload = request.request()
        if not payload:
            return {}
        return json.loads(payload)

    @staticmethod
    def _extract_season_token(html):
        match = re.search(r"initSeason\('([^']+)'", html or '')
        return match.group(1) if match else ''

    @staticmethod
    def _index_entries(html):
        entries = []
        for href, label in re.findall(r'<a\b[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', html or '', re.I):
            label = re.sub(r'\s+', ' ', html_unescape(re.sub(r'<[^>]+>', ' ', label or ''))).strip()
            if href.startswith('/') and label and not href.startswith(('/genre', '/index', '/updates', '/faq', '/request', '/top10', '/notifications')):
                if re.match(r'^/[^/]+$', href):
                    entries.append((href, label))
        return entries

    @staticmethod
    def _title_matches(title, clean_titles):
        current = cleantitle.get(title)
        return current in clean_titles

    @staticmethod
    def _language(text):
        text = (text or '').lower()
        if '.dl.' in text or 'german.dl' in text or 'multi' in text:
            return 'multi'
        if 'german' in text or 'deutsch' in text:
            return 'de'
        if 'english' in text or '.eng.' in text:
            return 'en'
        return 'unknown'

    @staticmethod
    def _index_letter(title):
        match = re.search(r'[a-z0-9]', (title or '').lower())
        return match.group(0) if match else '_'

    @staticmethod
    def _clean(value):
        return re.sub(r'\s+', ' ', html_unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()

    @staticmethod
    def _unique(values):
        seen = set()
        result = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result
