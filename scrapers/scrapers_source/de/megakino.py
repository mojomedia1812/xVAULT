# -*- coding: UTF-8 -*-
import re, requests, time, resolveurl as resolver
from scrapers.modules.tools import cParser
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser, source_utils
from resources.lib.control import getSetting

def get_url():
    url = "https://raw.githubusercontent.com/mr-evil1/megakino/main/megakino-url.json"
    try:
        current_domain = requests.get(url, timeout=5).json().get("url")
        return current_domain
    except:
        return 'megakino.live'

SITE_IDENTIFIER = 'megakino'
SITE_DOMAIN = get_url()
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/index.php?do=search&subaction=search&story=%s'
        self.checkHoster = False if getSetting('provider.megakino.checkHoster') == 'false' else True
        self.sources = []
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Referer': self.base_link}

    def get_html(self, url):
        try:
            session = requests.Session()
            r = session.get(url, headers=self.headers, timeout=10)
            html = r.text
            if html and 'yg=token' in html:
                token_url = self.base_link + '/index.php?yg=token'
                token_headers = self.headers.copy()
                token_headers.update({'X-Requested-With': 'XMLHttpRequest', 'Referer': url})
                session.get(token_url, headers=token_headers, timeout=10)
                time.sleep(0.5)
                r = session.get(url, headers=self.headers, timeout=10)
                html = r.text
            return html if html and len(html) > 500 else ""
        except:
            return ""

    def _search_and_match(self, search_term, t, titles):
        try:
            search_url = self.search_link % search_term
            sHtmlContent = self.get_html(search_url)
            if not sHtmlContent:
                return None
            pattern = r'<a class="poster grid-item[^>]*href="([^"]+)"[^>]*>.*?alt="([^"]+)"'
            isMatch, aResult = cParser.parse(sHtmlContent, pattern)
            if not isMatch:
                return None
            for sUrl, sName in aResult:
                if not sUrl.startswith('http'):
                    sUrl = self.base_link + sUrl
                if cleantitle.get(sName) in t or any(cleantitle.get(x) in cleantitle.get(sName) for x in titles):
                    return sUrl
        except:
            pass
        return None

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        self.sources = []
        try:
            t = [cleantitle.get(i) for i in set(titles) if i]

            found_url = None

            if imdb:
                found_url = self._search_and_match(imdb, t, titles)

            if not found_url:
                for sSearchText in titles:
                    found_url = self._search_and_match(sSearchText, t, titles)
                    if found_url:
                        break

            if found_url:
                self.get_sources(found_url, year, season, episode, hostDict)

        except:
            pass
        return self.sources

    def get_sources(self, url, year, season, episode, hostDict):
        html = self.get_html(url)
        if not html: return
        quality = '720p'
        if '1080' in html: quality = '1080p'
        if season > 0:
            pattern = r'<select[^>]*id="ep%s"[^>]*>(.*?)</select>' % str(episode)
            isMatch, sContainer = cParser.parseSingleResult(html, pattern)
            if isMatch:
                isMatch, links = cParser.parse(sContainer, 'value="([^"]+)"')
            else: return
        else:
            pattern = r'<iframe[^>]*src="([^"]+)"'
            isMatch, links = cParser.parse(html, pattern)
        if isMatch:
            for sUrl in links:
                if 'youtube' in sUrl: continue
                if sUrl.startswith('//'): sUrl = 'https:' + sUrl
                valid, hoster = source_utils.is_host_valid(sUrl, hostDict)
                if valid:
                    self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': sUrl, 'direct': False})

    def resolve(self, url):
        return url
