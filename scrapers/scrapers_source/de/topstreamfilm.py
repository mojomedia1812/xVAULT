# -*- coding: UTF-8 -*-
import re
from scrapers.modules.tools import cParser  # re - alternative
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser, source_utils
from resources.lib.control import getSetting
import xbmcgui
SITE_IDENTIFIER = 'topstreamfilm'
SITE_DOMAIN = 'www.topstreamfilm.live'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def parse_quality(self, url):
        url_lower = url.lower()
        if '2160' in url_lower or '4k' in url_lower:
            return '4K'
        elif '1440' in url_lower or '2k' in url_lower:
            return '1440p'
        elif '1080' in url_lower:
            return '1080p'
        elif '720' in url_lower:
            return '720p'
        elif '480' in url_lower:
            return '480p'
        elif '360' in url_lower:
            return '360p'
        return 'HD'
    def __init__(self):
        
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain

        self.search_link = self.base_link + '/?story=%s&do=search&subaction=search'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            if season == 0:
                oRequest = cRequestHandler('https://meinecloud.click/movie/%s' % imdb, caching=True)
                sHtmlContent = oRequest.request()
                isMatch, aResult = cParser.parse(sHtmlContent, 'data-link="([^"]+)')
                for sUrl in aResult:
                    if sUrl.startswith('/'): sUrl = 'https:' + sUrl
                    valid, hoster = source_utils.is_host_valid(sUrl, hostDict)
                    if not valid: continue
                    quality = self.parse_quality(sUrl)
                    self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': sUrl, 'direct': False})

            else:
                oRequest = cRequestHandler(self.search_link % imdb, caching=True)
                sHtmlContent = oRequest.request()
                pattern = 'class="thumb".*?title="([^"]+).*?href="([^"]+).*?_year">([^<]+)'
                isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                if not isMatch: return self.sources

                sName, sUrl, sYear = aResult[0]
                oRequest = cRequestHandler(sUrl, caching=True)
                sHtmlContent = oRequest.request()
                pattern = r'%sx%s\s.*?/>' % (str(season), str(episode))
                isMatch, sLinkContainer = cParser.parseSingleResult(sHtmlContent, pattern)
                pattern = 'href="([^"]+)'
                isMatch, aResult = cParser.parse(sLinkContainer, pattern)
                if not isMatch: return self.sources
                for sUrl in aResult:
                    if sUrl.startswith('/'): sUrl = 'https:' + sUrl
                    valid, hoster = source_utils.is_host_valid(sUrl, hostDict)
                    if not valid: continue
                    quality = self.parse_quality(sUrl)
                    self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': sUrl, 'direct': False})
            return self.sources
        except:
            return self.sources

    def resolve(self, url):
        return url
