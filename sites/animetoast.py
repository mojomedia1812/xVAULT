# -*- coding: UTF-8 -*-

import json
import re

from html import unescape as html_unescape
from urllib.parse import quote_plus, urljoin, urlparse

from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger
from resources.lib.utils import isBlockedHoster
from scrapers.modules import cleantitle, source_utils


SITE_IDENTIFIER = 'animetoast'
SITE_DOMAIN = 'www.animetoast.cc'
SITE_NAME = 'AnimeToast'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0'


class source:
    def __init__(self):
        self.priority = 9
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.sources = []
        self._seen = set()

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        if int(season or 0) <= 0 or int(episode or 0) <= 0:
            return self.sources

        try:
            for page_url, page_title, score in self._find_series_pages(titles, season):
                if score <= 0:
                    continue
                html = self._request(page_url, self.base_link)
                if not html:
                    continue
                language, language_info = self._language_from_title(page_title + ' ' + page_url)
                self._add_ajax_sources(html, page_url, season, episode, language, language_info)
                self._add_multilink_sources(html, page_url, season, episode, language, language_info)
                if len(self.sources) >= 12:
                    break
        except Exception as exc:
            logger.error('[%s] Fehler: %s' % (SITE_NAME, exc))
        return self.sources

    def resolve(self, url):
        if not self._is_animetoast_url(url):
            return url

        html = self._request(url, self.base_link, caching=False)
        target = self._player_embed_url(html)
        return target or url

    def _find_series_pages(self, titles, season):
        candidates = []
        seen = set()
        for title in titles:
            if not title:
                continue
            search_url = self.base_link + '/?s=' + quote_plus(title)
            html = self._request(search_url, self.base_link)
            for href, label in self._search_results(html):
                key = href.rstrip('/')
                if key in seen:
                    continue
                seen.add(key)
                score = self._match_score(title, label, href, season)
                if score > 0:
                    candidates.append((href, label, score))
        candidates.sort(key=lambda item: item[2], reverse=True)
        return candidates[:4]

    def _search_results(self, html):
        results = []
        seen = set()
        pattern = r'<h3[^>]*>\s*<a\s+href=(["\'])(.*?)\1[^>]*>(.*?)</a>'
        for match in re.finditer(pattern, html or '', re.I | re.S):
            href = self._absolute(match.group(2))
            label = self._clean(match.group(3))
            if not href or not label or href in seen:
                continue
            seen.add(href)
            results.append((href, label))
        return results

    def _add_ajax_sources(self, html, referer, season, episode, language, language_info):
        nonce = self._nonce(html)
        if not nonce:
            return
        for player_title, player_html in self._simple_iframe_players(html):
            if not self._player_matches_season(player_title, season):
                continue
            for server in self._server_values(player_html):
                payload = self._ajax_episode(player_title, server, episode, nonce, referer)
                if not isinstance(payload, dict) or not payload.get('success'):
                    continue
                data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
                stream_url = (data.get('url') or '').replace('\\/', '/')
                self._add_source(stream_url, '', language, language_info, 'Episode %s' % episode)

    def _add_multilink_sources(self, html, referer, season, episode, language, language_info):
        tabs = self._tab_labels(html)
        for tab_id, tab_html in self._tab_blocks(html):
            hoster_label = tabs.get(tab_id, SITE_NAME)
            for link, label in self._episode_links(tab_html):
                if not self._episode_label_matches(label, season, episode):
                    continue
                target = self._player_embed_url(self._request(link, referer, caching=False))
                self._add_source(target or link, hoster_label, language, language_info, label)

    def _add_source(self, url, hoster_label, language, language_info, info=''):
        url = self._absolute(html_unescape((url or '').strip()))
        if not url or url in self._seen or url.startswith('javascript:') or url == '#':
            return
        self._seen.add(url)

        if self._is_animetoast_url(url):
            self.sources.append({
                'source': hoster_label or SITE_NAME,
                'quality': 'HD',
                'language': language,
                'url': url,
                'direct': False,
                'debridonly': False,
                'prioHoster': 95,
                'info': self._info(language_info, info)
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
            'source': hoster or self._host(url) or hoster_label or SITE_NAME,
            'quality': 'HD',
            'language': language,
            'url': clean_url,
            'direct': False,
            'debridonly': False,
            'prioHoster': prio_hoster,
            'info': self._info(language_info, info)
        })

    def _ajax_episode(self, player_title, server, episode, nonce, referer):
        request = cRequestHandler(self.base_link + '/wp-admin/admin-ajax.php', caching=False)
        request.addHeaderEntry('User-Agent', UA)
        request.addHeaderEntry('Accept', 'application/json, text/javascript, */*; q=0.01')
        request.addHeaderEntry('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
        request.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
        request.addHeaderEntry('Origin', self.base_link)
        request.addHeaderEntry('Referer', referer)
        request.addParameters('action', 'get_episode_data')
        request.addParameters('title', player_title)
        request.addParameters('server', server)
        request.addParameters('episode', str(int(episode or 0)))
        request.addParameters('nonce', nonce)
        payload = request.request()
        if not payload:
            return {}
        try:
            return json.loads(payload)
        except:
            return {}

    def _request(self, url, referer=None, caching=True):
        try:
            request = cRequestHandler(url, caching=caching, preserve_url=True)
            request.addHeaderEntry('User-Agent', UA)
            request.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
            if referer:
                request.addHeaderEntry('Referer', referer)
            return request.request() or ''
        except Exception as exc:
            logger.error('[%s] Request fehlgeschlagen: %s (%s)' % (SITE_NAME, url, exc))
            return ''

    def _simple_iframe_players(self, html):
        players = []
        pattern = r'(<div\b[^>]*class=(["\'])[^"\']*simple-iframe-player[^"\']*\2[^>]*>[\s\S]*?)(?=<div\b[^>]*class=(["\'])[^"\']*simple-iframe-player|\Z)'
        for match in re.finditer(pattern, html or '', re.I):
            block = match.group(1)
            title = self._attr(block, 'data-title')
            if title:
                players.append((html_unescape(title), block))
        return players

    def _server_values(self, html):
        servers = []
        for match in re.finditer(r'<option\b[^>]*\bvalue=(["\'])(.*?)\1[^>]*>', html or '', re.I | re.S):
            value = html_unescape(match.group(2)).strip()
            if value and value not in servers:
                servers.append(value)
        return servers

    def _tab_labels(self, html):
        labels = {}
        pattern = r'<a\b[^>]*href=(["\'])#(multi_link_tab\d+)\1[^>]*>(.*?)</a>'
        for match in re.finditer(pattern, html or '', re.I | re.S):
            labels[match.group(2)] = self._clean(match.group(3))
        return labels

    def _tab_blocks(self, html):
        pattern = r'<div\b[^>]*\bid=(["\'])(multi_link_tab\d+)\1[^>]*>([\s\S]*?)(?=<div\b[^>]*\bid=(["\'])multi_link_tab\d+\4|</div>\s*</div>\s*</div>)'
        for match in re.finditer(pattern, html or '', re.I):
            yield match.group(2), match.group(3)

    def _episode_links(self, html):
        links = []
        pattern = r'<a\b[^>]*\bhref=(["\'])([^"\']*\?link=\d+)\1[^>]*>([\s\S]*?)</a>'
        for match in re.finditer(pattern, html or '', re.I):
            links.append((self._absolute(match.group(2)), self._clean(match.group(3))))
        return links

    def _episode_label_matches(self, label, season, episode):
        text = self._clean(label)
        if not text:
            return False
        season = int(season or 0)
        episode = int(episode or 0)

        range_match = re.search(r'\bS0*(\d+)\s*:\s*E0*(\d+)\s*-\s*(\d*)\b', text, re.I)
        if range_match:
            range_season = int(range_match.group(1))
            start = int(range_match.group(2))
            end = int(range_match.group(3)) if range_match.group(3) else start
            return range_season == season and start <= episode <= end and start == end

        exact_match = re.search(r'\bS0*(\d+)\s*[:\s-]*E0*(\d+)\b', text, re.I)
        if exact_match:
            return int(exact_match.group(1)) == season and int(exact_match.group(2)) == episode

        ep_match = re.search(r'\b(?:E|Episode|Folge)\s*0*(\d+)\b', text, re.I)
        if ep_match:
            return int(ep_match.group(1)) == episode

        plain_match = re.fullmatch(r'0*(\d+)', text)
        return bool(plain_match and int(plain_match.group(1)) == episode)

    def _player_embed_url(self, html):
        block_match = re.search(r'<div\b[^>]*\bid=(["\'])player-embed\1[^>]*>([\s\S]*?)</div>', html or '', re.I)
        block = block_match.group(2) if block_match else html or ''
        for match in re.finditer(r'<a\b[^>]*\bhref=(["\'])(https?://[^"\']+)\1', block, re.I):
            url = html_unescape(match.group(2)).strip()
            if url and not self._is_animetoast_url(url):
                return url
        return ''

    def _nonce(self, html):
        match = re.search(r'var\s+iframe_loader\s*=\s*\{[^}]*"nonce"\s*:\s*"([^"]+)"', html or '', re.I)
        return match.group(1) if match else ''

    def _match_score(self, requested_title, page_title, href, season):
        requested = self._normal_title(requested_title)
        found = self._normal_title(page_title)
        if not requested or not found:
            return 0
        if requested != found and requested not in found and found not in requested:
            return 0

        score = 100 if requested == found else 70
        page_season = self._season_from_text(page_title + ' ' + href)
        season = int(season or 1)
        if page_season:
            if page_season != season:
                return 0
            score += 20
        elif season == 1:
            score += 10

        language, info = self._language_from_title(page_title + ' ' + href)
        if language == 'de':
            score += 4
        if info and 'Sub' in info:
            score -= 8
        return score

    def _player_matches_season(self, title, season):
        player_season = self._season_from_text(title)
        return not player_season or player_season == int(season or 1)

    @staticmethod
    def _season_from_text(text):
        match = re.search(r'\b(?:S|Season)\s*0*(\d+)\b', text or '', re.I)
        return int(match.group(1)) if match else None

    @staticmethod
    def _language_from_title(text):
        text_l = (text or '').lower()
        if 'ger-dub' in text_l or 'ger dub' in text_l or 'deutsch' in text_l:
            return 'de', 'Ger-Dub'
        if 'eng-dub' in text_l or 'eng dub' in text_l:
            return 'en', 'Eng-Dub'
        if 'ger-sub' in text_l or 'ger sub' in text_l:
            return 'unknown', 'Ger-Sub'
        if 'eng-sub' in text_l or 'eng sub' in text_l:
            return 'unknown', 'Eng-Sub'
        return 'unknown', ''

    @staticmethod
    def _normal_title(title):
        title = html_unescape(title or '')
        title = re.sub(r'\b(?:ger|eng)\s*[- ]\s*(?:dub|sub)\b', ' ', title, flags=re.I)
        title = re.sub(r'\b(?:german|english|deutsch|englisch)\b', ' ', title, flags=re.I)
        title = re.sub(r'\b(?:season|staffel)\s*\d+\b', ' ', title, flags=re.I)
        return cleantitle.get(title)

    def _absolute(self, url):
        url = html_unescape((url or '').strip())
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        return urljoin(self.base_link, url)

    @staticmethod
    def _clean(value):
        return re.sub(r'\s+', ' ', html_unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()

    @staticmethod
    def _attr(html, attr):
        match = re.search(r'\b%s=(["\'])(.*?)\1' % re.escape(attr), html or '', re.I | re.S)
        return match.group(2) if match else ''

    @staticmethod
    def _host(url):
        try:
            return (urlparse(url).hostname or '').lower().replace('www.', '')
        except:
            return ''

    @staticmethod
    def _info(*values):
        return ' | '.join([str(value) for value in values if value])

    def _is_animetoast_url(self, url):
        try:
            host = (urlparse(url).hostname or '').lower()
            return host == self.domain or host.endswith('.' + self.domain.replace('www.', ''))
        except:
            return False
