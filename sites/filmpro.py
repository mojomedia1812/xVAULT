# -*- coding: UTF-8 -*-
from resources.lib.utils import isBlockedHoster
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser
from scrapers.modules.tools import cParser
from resources.lib.control import getSetting, quote_plus

SITE_IDENTIFIER = 'filmpro'
SITE_DOMAIN = 'www.filmpalast.pro'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/?story=%s&do=search&subaction=search&titleonly=3'

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        sources = []
        if season == 0:
            query = 'https://meinecloud.click/ddl/%s' % imdb
            oRequest = cRequestHandler(query)
            oRequest.cacheTime = 60 * 60 * 24 * 2
            sHtmlContent = oRequest.request()
            pattern = "window.open.*?'([^']+).*?mark>([^<]+)"
            isMatch, aResults = cParser.parse(sHtmlContent, pattern)
            if isMatch:
                for link, quality in aResults:
                    isBlocked, hoster, sUrl, prioHoster = isBlockedHoster(link, isResolve=False)
                    if isBlocked: continue
                    if sUrl: sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': sUrl, 'direct': False, 'prioHoster': prioHoster})
            return sources
        else:
            try:
                url = ''
                t = [cleantitle.get(i) for i in titles if i]
                for title in titles:
                    try:
                        query = self.search_link % quote_plus(title)
                        oRequest  = cRequestHandler(query)
                        oRequest.cacheTime = 60 * 60 * 24 * 2
                        sHtmlContent = oRequest.request()
                        r = dom_parser.parse_dom(sHtmlContent, 'ul', attrs={'id': 'dle-content'})
                        if r:
                            r = dom_parser.parse_dom(r, 'li')
                            if len(r) == 0: continue
                            for i in r:
                                pattern = r'href="([^"]+).*?Title">([^<]+).*?Year">(\d+).*?Qlty">([^<]+)'
                                sUrl, sTitle, sYear, sQuality = cParser.parse(i.content, pattern)[1][0]
                                sTitle = sTitle.split(' - Der')[0]
                                if sYear == str(year) and cleantitle.get(sTitle) in t:
                                    url = sUrl
                                if url: break
                        if url:
                            break
                    except:
                        pass

                if url == '': return sources

                oRequest = cRequestHandler(url)
                oRequest.cacheTime = 60 * 60 * 24
                sHtmlContent = oRequest.request()
                pattern='data-num="%sx%s".*?"mirrors">(.*?)</div' % (season, episode)
                isMatch, dataLinks= cParser.parse(sHtmlContent, pattern)
                pattern='(http[^"]+)'
                aResults=cParser.parse(dataLinks[0], pattern)[1]

                for link in aResults:
                    isBlocked, sDomain, sUrl, prioHoster = isBlockedHoster(link, isResolve=False)
                    if isBlocked: continue
                    if url: sources.append({'source': sDomain, 'quality': 'HD', 'language': 'de', 'url': sUrl, 'direct': False, 'prioHoster': prioHoster})
                return sources
            except:
                return sources
    def resolve(self, url):
        try:
            return url
        except:
            return
