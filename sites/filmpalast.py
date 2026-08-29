# -*- coding: UTF-8 -*-
import re
from html import unescape
from urllib.parse import quote, urljoin, urlparse
from resources.lib.utils import isBlockedHoster
from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'filmpalast'
SITE_DOMAIN = 'filmpalast.to'

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = '/search/title/%s'
        self.max_search_pages = 5

    def _request(self, url, referer=None):
        headers = {
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'close',
        }
        if referer:
            headers['Referer'] = referer

        try:
            request = cRequestHandler(url, caching=True, preserve_url=True)
            for key, value in headers.items():
                request.addHeaderEntry(key, value)
            return request.request()
        except Exception as e:
            logger.error('[Filmpalast] Request fehlgeschlagen: %s (%s)' % (url, e))
            return ''

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        sources = []
        url = ''
        moviecontent = ''

        try:
            titles = [t for t in titles if t and str(t).lower() != 'none']
            logger.info('[Filmpalast] Suche: %s' % titles)

            for title in titles:
                candidates = []
                for m_url, m_title in self._search_candidates(title):
                    if season and episode and not self._episode_matches(m_title, m_url, season, episode):
                        continue

                    score = self._match_score(title, m_title, m_url, year)
                    if score <= 0:
                        continue

                    page_url = self._absolute_url(m_url)
                    page_data = self._request(page_url, self.base_link)
                    if not page_data:
                        continue
                    if year and not self._year_matches(page_data, year):
                        continue

                    candidates.append((score, page_url, page_data))

                if candidates:
                    candidates.sort(key=lambda item: item[0], reverse=True)
                    _score, url, moviecontent = candidates[0]
                    logger.info('[Filmpalast] Treffer: %s' % url)
                    break

            if not url:
                return sources

            if not moviecontent:
                moviecontent = self._request(url, self.base_link)

            quality = 'HD'
            q = re.search(r'<span id="release_text"[^>]*>([^<&]+)', moviecontent, re.I)
            if q:
                t = q.group(1)
                if '2160' in t or '4K' in t:
                    quality = '4K'
                elif '1080' in t:
                    quality = '1080p'
                elif '720' in t:
                    quality = '720p'

            streams = self._parse_streams(moviecontent)

            for hoster, s_url in streams:
                if not s_url or s_url.startswith('javascript'):
                    continue

                is_blocked, res_host, res_url, prio = isBlockedHoster(s_url, isResolve=False)
                if is_blocked and prio >= 100:
                    continue

                sources.append({
                    'source': res_host if res_host else hoster.strip(),
                    'quality': quality,
                    'language': 'de',
                    'url': res_url if res_url else s_url,
                    'direct': False,
                    'debridonly': False,
                    'prioHoster': prio
                })

            logger.info('[Filmpalast] %d Quellen gefunden' % len(sources))
            return sources

        except Exception as e:
            logger.error('[Filmpalast] Fehler: %s' % e)
            return sources

    def resolve(self, url):
        return url

    def _content_area(self, data):
        content_match = re.search(
            r'id=["\']content["\'][^>]*>(.+?)(?:<[^>]*id=["\']paging["\']|<footer\b|</body>)',
            data or '',
            re.S | re.I
        )
        return content_match.group(1) if content_match else data or ''

    def _search_candidates(self, title):
        search_url = self.base_link + (self.search_link % quote(title))
        queue = [search_url]
        visited = set()
        results = []
        seen = set()

        while queue and len(visited) < self.max_search_pages:
            page_url = queue.pop(0)
            if page_url in visited:
                continue
            visited.add(page_url)

            data = self._request(page_url, self.base_link)
            if not data:
                continue

            for href, result_title in self._parse_search_results(self._content_area(data)):
                key = (self._absolute_url(href), self._clean_title(result_title))
                if key in seen:
                    continue
                seen.add(key)
                results.append((href, result_title))

            for next_url in self._next_page_urls(data, search_url):
                if next_url not in visited and next_url not in queue:
                    queue.append(next_url)

        return results

    def _parse_search_results(self, html):
        results = []
        seen = set()

        for match in re.finditer(r'(?is)<a\b[^>]*\bhref=(["\'])(.*?)\1[^>]*>.*?</a>', html or ''):
            anchor = match.group(0)
            href = unescape(match.group(2)).strip()
            if '/stream/' not in href:
                continue
            title = (
                self._attr(anchor, 'title')
                or self._attr(anchor, 'data-title')
                or self._attr(anchor, 'aria-label')
                or self._image_alt(anchor)
                or self._clean_text(re.sub(r'(?is)^<a\b[^>]*>|</a>$', ' ', anchor))
                or self._title_from_href(href)
            )
            if not href or not title:
                continue
            key = (href, title)
            if key in seen:
                continue
            seen.add(key)
            results.append((href, title))
        return results

    def _parse_streams(self, html):
        clean_html = re.sub(r'<!--.*?-->', ' ', html or '', flags=re.S)
        streams = []
        seen = set()
        blocks = re.findall(r'<ul[^>]*class=["\'][^"\']*currentStreamLinks[^"\']*["\'][^>]*>(.*?)</ul>', clean_html, re.S | re.I)
        if not blocks:
            blocks = [clean_html]

        for block in blocks:
            host_match = re.search(r'<p[^>]*class=["\'][^"\']*hostName[^"\']*["\'][^>]*>(.*?)</p>', block, re.S | re.I)
            hoster = self._clean_text(host_match.group(1)) if host_match else 'Filmpalast'
            for url_match in re.finditer(r'\b(?:href|data-player-url|data-url|data-href)=["\']([^"\']+)["\']', block, re.S | re.I):
                stream_url = unescape(url_match.group(1)).strip()
                if not stream_url or stream_url == '#' or stream_url.lower().startswith('javascript'):
                    continue
                stream_url = self._absolute_url(stream_url)
                if self.domain in urlparse(stream_url).netloc and '/stream/' in stream_url:
                    continue
                key = (hoster.lower(), stream_url)
                if key in seen:
                    continue
                seen.add(key)
                streams.append((hoster, stream_url))
        return streams

    def _next_page_urls(self, html, first_search_url):
        urls = []
        seen = set()
        first_path = urlparse(first_search_url).path.rstrip('/')
        for match in re.finditer(r'(?is)<a\b[^>]*\bhref=(["\'])(.*?)\1[^>]*>(.*?)</a>', html or ''):
            href = unescape(match.group(2)).strip()
            label = self._clean_text(match.group(3)).lower()
            if not href:
                continue
            absolute = self._absolute_url(href)
            path = urlparse(absolute).path.rstrip('/')
            if not path.startswith(first_path):
                continue
            if not re.search(r'(?:^|\D)(?:[2-9]|\d{2,})(?:\D|$)', label) and 'vorw' not in label and 'next' not in label and '+' not in label:
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            urls.append(absolute)
        return urls[:self.max_search_pages - 1]

    def _absolute_url(self, url):
        url = unescape(url or '').strip()
        if url.startswith('//'):
            return 'https:' + url
        return urljoin(self.base_link, url)

    @staticmethod
    def _attr(html, attr):
        match = re.search(r'\b%s=(["\'])(.*?)\1' % re.escape(attr), html or '', re.S | re.I)
        return source._clean_text(match.group(2)) if match else ''

    def _image_alt(self, html):
        match = re.search(r'(?is)<img\b[^>]*\balt=(["\'])(.*?)\1', html or '')
        return self._clean_text(match.group(2)) if match else ''

    def _title_from_href(self, href):
        try:
            slug = unescape(str(href).split('/stream/', 1)[1]).split('?', 1)[0].strip('/')
            return self._clean_text(slug.replace('-', ' '))
        except:
            return ''

    @staticmethod
    def _clean_text(value):
        value = unescape(value or '')
        value = re.sub(r'<[^>]+>', ' ', value)
        value = re.sub(r'\s+', ' ', value)
        return value.strip()

    def _clean_title(self, title, year=None):
        title = self._clean_text(title)
        if year:
            title = re.sub(r'\(?\b%s\b\)?' % re.escape(str(year)), ' ', title)
        return cleantitle.get(title)

    def _title_variants(self, title, year=None):
        values = []
        base = self._clean_text(title)
        if year:
            base = re.sub(r'\(?\b%s\b\)?' % re.escape(str(year)), ' ', base)
        candidates = [base]
        candidates.append(re.sub(r'\s*&\s*', ' ', base))
        candidates.append(re.sub(r'\band\b', ' ', base, flags=re.I))
        for candidate in candidates:
            cleaned = cleantitle.get(candidate)
            if cleaned:
                values.append(cleaned)
            ascii_candidate = candidate.lower()
            replacements = [
                (u'\xe4', 'ae'), (u'\xf6', 'oe'), (u'\xfc', 'ue'),
                (u'\xdf', 'ss'), (u'\xe9', 'e'), (u'\xe8', 'e'),
            ]
            for source_text, target_text in replacements:
                ascii_candidate = ascii_candidate.replace(source_text, target_text)
            ascii_candidate = re.sub(r'[^a-z0-9]+', '', ascii_candidate)
            if ascii_candidate:
                values.append(ascii_candidate)
        return list(set([value for value in values if value]))

    def _match_score(self, requested_title, result_title, href, year=None):
        requested = self._title_variants(requested_title, year)
        result = self._title_variants(result_title, year)
        slug_title = self._title_from_href(href)
        if slug_title:
            result.extend(self._title_variants(slug_title, year))

        for left in requested:
            for right in result:
                if not left or not right:
                    continue
                if left == right:
                    return 100
                if len(left) >= 6 and len(right) >= 6 and (left in right or right in left):
                    return 60
        return 0

    def _year_matches(self, html, expected_year):
        page_year = self._extract_year(html)
        if not page_year:
            return True
        try:
            return abs(int(page_year) - int(expected_year)) <= 1
        except:
            return True

    def _extract_year(self, html):
        patterns = [
            r'>\s*Ver(?:&ouml;|\xf6)ffentlicht:\s*([^<]+)',
            r'>\s*(?:Erscheinungsjahr|Release|Jahr):\s*([^<]+)',
            r'<time[^>]+datetime=(["\'])(.*?)\1',
            r'<meta[^>]+property=(["\'])(?:og:video:release_date|video:release_date)\1[^>]+content=(["\'])(.*?)\2',
        ]
        for pattern in patterns:
            match = re.search(pattern, html or '', re.I | re.S)
            if not match:
                continue
            text = ' '.join([group for group in match.groups() if group])
            year = re.search(r'\b(19\d{2}|20\d{2})\b', unescape(text))
            if year:
                return year.group(1)
        return ''

    def _episode_matches(self, title, url, season, episode):
        haystack = '%s %s' % (title or '', url or '')
        if re.search(r'\bs0*%de0*%d\b' % (int(season), int(episode)), haystack, re.I):
            return True

        pattern = r'\b(?:staffel|season)\s*0*%d\b.*\b(?:episode|folge)\s*0*%d\b' % (int(season), int(episode))
        return bool(re.search(pattern, haystack, re.I))


