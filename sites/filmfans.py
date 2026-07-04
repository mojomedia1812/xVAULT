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

SITE_IDENTIFIER = 'filmfans'
SITE_DOMAIN = 'filmfans.org'
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
        if int(season or 0) > 0:
            return self.sources
        try:
            for movie_url in self._find_movie_pages(titles, year):
                self._read_movie_page(movie_url)
                if len(self.sources) >= 20:
                    break
        except:
            pass
        return self.sources

    def resolve(self, url):
        return url

    def _find_movie_pages(self, titles, year):
        clean_titles = set([cleantitle.get(title) for title in titles if title])
        urls = []
        for title in titles:
            letter = self._index_letter(title)
            html = self._request(self.base_link + '/index/%s' % letter, self.base_link)
            for href, label in self._index_entries(html):
                item_title, item_year = self._split_title_year(label)
                if not self._title_matches(item_title, clean_titles):
                    continue
                if year and item_year and str(year) != str(item_year):
                    continue
                urls.append(urljoin(self.base_link, href))
        return self._unique(urls)

    def _read_movie_page(self, movie_url):
        html = self._request(movie_url, self.base_link)
        slug = '/' + movie_url.rstrip('/').split('/')[-1] + '/'
        release_links = []
        for href, label in re.findall(r'<a\b[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', html or '', re.I):
            href = html_unescape(href)
            label = self._clean(label)
            if slug in href and label and not href.rstrip('/').endswith(slug.rstrip('/')):
                release_links.append((urljoin(self.base_link, href), label))
        for release_url, release_name in self._unique_pairs(release_links)[:6]:
            self._read_release(release_url, release_name)

    def _read_release(self, release_url, release_name):
        html = self._request(release_url, self.base_link)
        token = self._extract_movie_token(html)
        if not token:
            return
        data = self._request_json(self.base_link + '/api/v1/%s?rls=%s' % (token, quote_plus(release_name)), release_url)
        fragment = data.get('html', '') if isinstance(data, dict) else ''
        for href, label in re.findall(r'<a\b[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', fragment or '', re.I):
            self._add_external(urljoin(self.base_link, html_unescape(href)), self._clean(label), release_name)

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
    def _extract_movie_token(html):
        match = re.search(r"initMovie\('([^']+)'", html or '')
        return match.group(1) if match else ''

    @staticmethod
    def _index_entries(html):
        entries = []
        for href, label in re.findall(r'<a\b[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', html or '', re.I):
            label = re.sub(r'\s+', ' ', html_unescape(re.sub(r'<[^>]+>', ' ', label or ''))).strip()
            if href.startswith('/') and label and not href.startswith(('/genre', '/index', '/updates', '/faq', '/request', '/top10', '/notifications')):
                entries.append((href, label))
        return entries

    @staticmethod
    def _split_title_year(label):
        match = re.match(r'(.+?)\s*\((\d{4})\)\s*$', label or '')
        if match:
            return match.group(1).strip(), match.group(2)
        return label or '', ''

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

    @staticmethod
    def _unique_pairs(values):
        seen = set()
        result = []
        for url, label in values:
            key = (url, label)
            if key not in seen:
                seen.add(key)
                result.append((url, label))
        return result
