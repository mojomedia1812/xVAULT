# -*- coding: UTF-8 -*-
import resolveurl as resolver
import re
import urllib.parse
from resources.lib.requestHandler import cRequestHandler
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
        h = cRequestHandler(url, bypass_dns=True)
        h.addHeaderEntry('User-Agent', UA)
        if referer:
            h.addHeaderEntry('Referer', referer)
        return h.request()

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

                content_match = re.search(
                    r'id="content"[^>]*>(.+?)<[^>]*id="paging"',
                    data, re.S | re.I
                )
                if not content_match:
                    continue

                content = content_match.group(1)

                matches = re.findall(
                    r'<a[^>]*href="//filmpalast\.to([^"]+)"[^>]*title="([^"]+)"',
                    content, re.S | re.I
                )

                clean_search = cleantitle.get(title)

                for m_url, m_title in matches:
                    clean_match = cleantitle.get(m_title)
                    if clean_search not in clean_match and clean_match not in clean_search:
                        continue

                    page_url = self.base_link + m_url
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

            streams = re.findall(
                r'<p class="hostName">([^<]+)</p>.*?<li[^>]*class="streamPlayBtn[^"]*".*?<a[^>]*(?:href|data-player-url)="([^"]+)"',
                moviecontent, re.S | re.I
            )

            for hoster, s_url in streams:
                if not s_url or s_url.startswith('javascript'):
                    continue

                is_blocked, res_host, res_url, prio = isBlockedHoster(s_url)
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


