# -*- coding: UTF-8 -*-
import re
import urllib.parse
import urllib.request
import ssl
import zlib
from html import unescape
from resources.lib.utils import isBlockedHoster
from resources.lib.control import getSetting
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
            timeout = int(getSetting('requestTimeout', 10) or 10)
        except Exception:
            timeout = 10

        try:
            request = urllib.request.Request(url, headers=headers)
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                raw = response.read()
                encoding = response.headers.get('Content-Encoding', '').lower()
                if encoding == 'gzip':
                    raw = zlib.decompress(raw, zlib.MAX_WBITS | 16)
                elif encoding == 'deflate':
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                charset = response.headers.get_content_charset() or 'utf-8'
                return raw.decode(charset, 'replace')
        except Exception as e:
            logger.error('[Filmpalast] Request fehlgeschlagen: %s (%s)' % (url, e))
            return ''

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        sources = []
        url = ''

        try:
            titles = [t for t in titles if t and str(t).lower() != 'none']
            logger.info('[Filmpalast] Suche: %s' % titles)

            for title in titles:
                search_url = self.base_link + (self.search_link % urllib.parse.quote(title))
                data = self._request(search_url, self.base_link)
                if not data:
                    continue

                content = self._content_area(data)
                matches = self._parse_search_results(content)

                clean_search = self._clean_title(title, year)

                for m_url, m_title in matches:
                    if season and episode and not self._episode_matches(m_title, m_url, season, episode):
                        continue

                    clean_match = self._clean_title(m_title, year)
                    if clean_search not in clean_match and clean_match not in clean_search:
                        continue

                    page_url = self._absolute_url(m_url)
                    page_data = self._request(page_url, self.base_link)

                    if year:
                        y = re.search(r'>Ver&ouml;ffentlicht:\s*([^<]+)', page_data, re.I)
                        if y and str(year) not in y.group(1):
                            continue

                    url = page_url
                    logger.info('[Filmpalast] Treffer: %s' % url)
                    break

                if url:
                    break

            if not url:
                return sources

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
                    'debridonly': False
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

    def _parse_search_results(self, html):
        results = []
        seen = set()
        pattern = re.compile(
            r'<a\b(?=[^>]*\btitle=(["\'])(?P<title>.*?)\1)[^>]*\bhref=(["\'])(?P<href>(?:(?:https?:)?//[^"\']+)?/stream/[^"\']+)\3',
            re.S | re.I
        )
        for match in pattern.finditer(html or ''):
            href = unescape(match.group('href')).strip()
            title = self._clean_text(match.group('title'))
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
            for url_match in re.finditer(r'\b(?:href|data-player-url)=["\']([^"\']+)["\']', block, re.S | re.I):
                stream_url = unescape(url_match.group(1)).strip()
                if not stream_url or stream_url == '#' or stream_url.lower().startswith('javascript'):
                    continue
                stream_url = self._absolute_url(stream_url)
                if self.domain in urllib.parse.urlparse(stream_url).netloc and '/stream/' in stream_url:
                    continue
                key = (hoster.lower(), stream_url)
                if key in seen:
                    continue
                seen.add(key)
                streams.append((hoster, stream_url))
        return streams

    def _absolute_url(self, url):
        url = unescape(url or '').strip()
        if url.startswith('//'):
            return 'https:' + url
        return urllib.parse.urljoin(self.base_link, url)

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

    def _episode_matches(self, title, url, season, episode):
        haystack = '%s %s' % (title or '', url or '')
        if re.search(r'\bs0*%de0*%d\b' % (int(season), int(episode)), haystack, re.I):
            return True

        pattern = r'\b(?:staffel|season)\s*0*%d\b.*\b(?:episode|folge)\s*0*%d\b' % (int(season), int(episode))
        return bool(re.search(pattern, haystack, re.I))


