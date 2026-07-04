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

SITE_IDENTIFIER = 'streamcloudforum'
SITE_DOMAIN = 'streamcloud.forum'
SITE_NAME = 'STREAMCLOUD.FORUM'


class source:
    def __init__(self):
        self.priority = 2
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/index.php?do=search&subaction=search&story=%s'
        self.sources = []
        self._seen = set()

    def run(self, titles, year, season=0, episode=0, imdb=''):
        try:
            if int(season or 0) > 0:
                self._run_episode(titles, season, episode, imdb)
            else:
                self._run_movie(titles, year, imdb)
        except:
            pass
        return self.sources

    def resolve(self, url):
        return url

    def _run_movie(self, titles, year, imdb):
        detail_urls = self._find_detail_urls(titles, year, expect_series=False)
        player_urls = []

        for detail_url in detail_urls[:3]:
            html = self._request(detail_url, self.base_link)
            player_urls.extend(self._movie_player_urls(html))

        if imdb:
            player_urls.append('https://meinecloud.click/movie/%s' % imdb)

        for player_url in self._unique(player_urls):
            html = self._request(player_url, self.base_link)
            self._add_data_links(html, player_url)

    def _run_episode(self, titles, season, episode, imdb):
        player_urls = []
        for detail_url in self._find_detail_urls(titles, '', expect_series=True)[:3]:
            html = self._request(detail_url, self.base_link)
            player_urls.extend(self._serial_player_urls(html, imdb))

        if imdb:
            player_url = self._serial_player_from_imdb(imdb)
            if player_url:
                player_urls.append(player_url)
            else:
                player_urls.append('https://meinecloud.click/serial/%s' % imdb)

        for player_url in self._unique(player_urls):
            html = self._request(player_url, self.base_link)
            self._add_episode_links(html, season, episode, player_url)

    def _find_detail_urls(self, titles, year='', expect_series=False):
        clean_titles = set([cleantitle.get(t) for t in titles if t])
        results = []
        for title in titles:
            if not title:
                continue
            html = self._request(self.search_link % quote_plus(title), self.base_link)
            for item in self._parse_search_results(html):
                item_title = item.get('title', '')
                item_year = item.get('year', '')
                url = item.get('url', '')
                if not url:
                    continue
                if expect_series and 'serie' not in url.lower() and '-stream-deutsch' in url.lower():
                    # StreamCloud Forum uses the same suffix for movies and series. Keep
                    # title matches even when the URL is not conclusive.
                    pass
                if not self._title_matches(item_title, clean_titles):
                    continue
                if year and item_year and str(year) != str(item_year):
                    continue
                results.append(url)
        return self._unique(results)

    def _parse_search_results(self, html):
        pattern = (
            r'<div class="item\b[^>]*>[\s\S]*?'
            r'<div class="thumb" title="([^"]*)"[\s\S]*?'
            r'<a href="([^"]+)"[\s\S]*?'
            r'<div class="f_title">\s*<a[^>]*>([\s\S]*?)</a>\s*</div>\s*'
            r'<div class="f_year">([^<]*)'
        )
        results = []
        for match in re.finditer(pattern, html or '', re.IGNORECASE):
            thumb_title, url, title, year = match.groups()
            results.append({
                'title': self._clean(title or thumb_title),
                'url': urljoin(self.base_link, html_unescape(url)),
                'year': self._clean(year)
            })
        return results

    def _movie_player_urls(self, html):
        urls = re.findall(r'<iframe[^>]+src="([^"]*meinecloud\.click/movie/[^"]+)"', html or '', re.I)
        urls += re.findall(r'https?://meinecloud\.click/movie/tt\d+', html or '', re.I)
        return [urljoin(self.base_link, html_unescape(url)) for url in urls]

    def _serial_player_urls(self, html, imdb=''):
        urls = []
        for imdb_id in re.findall(r'https?://meinecloud\.click/(?:ddl|serial)/((?:tt)?\d+)', html or '', re.I):
            if not imdb_id.startswith('tt'):
                imdb_id = 'tt' + imdb_id
            player = self._serial_player_from_imdb(imdb_id)
            if player:
                urls.append(player)
        if imdb:
            player = self._serial_player_from_imdb(imdb)
            if player:
                urls.append(player)
        return urls

    def _serial_player_from_imdb(self, imdb):
        try:
            data = self._request_json('https://meinecloud.click/serials.php?task=check&id_imdb=%s' % quote_plus(imdb), self.base_link)
            if isinstance(data, dict) and data.get('exists') and data.get('player_url'):
                return data.get('player_url').replace('\\/', '/')
        except:
            pass
        return ''

    def _add_data_links(self, html, referer):
        for url in re.findall(r'data-link="([^"]+)"', html or '', re.I):
            self._add_source(url, referer=referer)

    def _add_episode_links(self, html, season, episode, referer):
        for tag in re.findall(r'<div class="_ep[^"]*"[^>]*>', html or '', re.I):
            attrs = dict(re.findall(r'data-([a-z_-]+)="([^"]*)"', tag, re.I))
            label = html_unescape(attrs.get('label', ''))
            link = attrs.get('link', '')
            match = re.search(r'\bS0*(\d+)\s*E0*(\d+)\b', label, re.I)
            if not match:
                continue
            if int(match.group(1)) == int(season or 0) and int(match.group(2)) == int(episode or 0):
                self._add_source(link, referer=referer, info=label)

    def _add_source(self, url, referer='', info=''):
        url = html_unescape((url or '').strip())
        if not url or url.startswith('javascript:') or url == '#':
            return
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = urljoin(referer or self.base_link, url)

        host = self._host(url)
        if host in ['meinecloud.click', 'dl.tmdb.club'] and not re.search(r'\.(?:mp4|m3u8)(?:\?|$)', url, re.I):
            return

        if url in self._seen:
            return
        self._seen.add(url)

        quality = self._quality(url + ' ' + info)

        if re.search(r'\.(?:mp4|m3u8)(?:\?|$)', url, re.I):
            self.sources.append({
                'source': host or SITE_NAME,
                'quality': quality,
                'language': 'de',
                'url': url,
                'direct': True,
                'prioHoster': 90,
                'info': info
            })
            return

        is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(url, isResolve=False)
        if is_blocked or not clean_url:
            valid, hoster = source_utils.is_host_valid(url, [])
            if not valid:
                return
            clean_url = url
            prio_hoster = 100

        self.sources.append({
            'source': hoster or host or SITE_NAME,
            'quality': quality,
            'language': 'de',
            'url': clean_url,
            'direct': False,
            'prioHoster': prio_hoster,
            'info': info
        })

    def _request(self, url, referer=None, caching=True):
        request = cRequestHandler(url, caching=caching)
        request.addHeaderEntry('User-Agent', cRequestHandler.RandomUA())
        request.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
        if referer:
            request.addHeaderEntry('Referer', referer)
        return request.request() or ''

    def _request_json(self, url, referer=None):
        payload = self._request(url, referer=referer, caching=False)
        return json.loads(payload)

    @staticmethod
    def _title_matches(title, clean_titles):
        current = cleantitle.get(title)
        if current in clean_titles:
            return True
        return any(current and clean and (current.startswith(clean) or clean.startswith(current)) for clean in clean_titles)

    @staticmethod
    def _quality(text):
        text = (text or '').lower()
        if '2160' in text or '4k' in text:
            return '4K'
        if '1440' in text:
            return '1440p'
        if '1080' in text:
            return '1080p'
        if '720' in text:
            return '720p'
        if '480' in text or 'dvd' in text:
            return 'SD'
        return 'HD'

    @staticmethod
    def _host(url):
        try:
            from resources.lib.control import urlparse
            return (urlparse(url).hostname or '').replace('www.', '')
        except:
            return ''

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
