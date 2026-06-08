
# movie4k
# 2022-11-11
# edit 2024-12-14

from resources.lib.utils import isBlockedHoster
import re
from scrapers.modules.tools import cParser  # re - alternative
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser
from resources.lib.control import getSetting, setSetting

SITE_IDENTIFIER = 'movie4k'
SITE_DOMAIN = 'movie4k-to.cfd' # https://movie4k.bid/
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain

        #self.search_link = 'https://movie4k.pics/index.php?do=search&subaction=search&search_start=0&full_search=1&result_from=1&titleonly=3&story=%s'
        self.search_link = self.base_link + '/index.php?story=%s&do=search&subaction=search&titleonly=3'
        self.checkHoster = False if getSetting('provider.movie4k.checkHoster') == 'false' else True
        self.sources = []


    def run(self, titles, year, season=0, episode=0, imdb=''):
        sources = []
        try:
            t = set([cleantitle.get(i) for i in set(titles) if i])
            years = (year, year+1, year-1, 0)
            links = []

            if season == 0:
                ## https://meinecloud.click/movie/tt1477834
                #oRequest = cRequestHandler('https://meinecloud.click/movie/%s' % imdb, caching=True)
                #sHtmlContent = oRequest.request()
                sHtmlContent = requests.get('https://meinecloud.click/movie/%s' % imdb).text
                isMatch, aResult = cParser.parse(sHtmlContent, 'data-link="([^"]+)')
                for sUrl in aResult:
                    if sUrl.startswith('/'): sUrl = 'https:' + sUrl
                    isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
                    if isBlocked: continue
                    if url:
                        self.sources.append({'source': hoster, 'quality': '1080p', 'language': 'de', 'url': url, 'direct': True, 'prioHoster': prioHoster})
                return self.sources

            for sSearchText in titles:
                try:
                    #oRequest = cRequestHandler(self.search_link % sSearchText, caching=True)
                    #sHtmlContent = oRequest.request()
                    oRequest = requests.get(self.search_link % sSearchText).text
                    pattern = 'article class.*?href="([^"]+).*?<h3>([^<]+).*?white">([^<]+)'
                    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                    if not isMatch: continue

                    for sUrl, sName, sYear in aResult:
                        # if season == 0:
                        #     if cleantitle.get(sName) in t and int(sYear) in years:
                        #         # url = sUrl
                        #         # break
                        #         links.append(sUrl)
                        #
                        # else:
                        # if cleantitle.get(sName.split('-')[0].strip()) in t and str(season) in sName.split('-')[1]:
                        if cleantitle.get(sName) in t:
                            links.append(sUrl)
                            #break
                    if len(links) > 0: break
                except:
                    continue

            if len(links) == 0: return sources

            for url in links:
                #sHtmlContent = cRequestHandler(url).request()
                sHtmlContent = requests.get(url).text
                #isMatch, quality = cParser().parseSingleResult(sHtmlContent, 'QualitÃ¤t:.*?span>([^<]+)')
                quality = 'HD'
                #if season > 0:
                #pattern = '\s%s<.*?</ul>' % episode
                pattern = 'data-num="%sx%s"(.*?)</div' % (season, episode)
                isMatch, sHtmlContent = cParser.parseSingleResult(sHtmlContent, pattern)
                if not isMatch: return sources

                isMatch, aResult = cParser().parse(sHtmlContent, 'link="([^"]+)".*?">([^<]+)')    # link="([^"]+)">([^<]+)
                if not isMatch: return sources
                for sUrl, sName in aResult:
                    if 'railer' in sName or 'youtube'in sUrl or 'vod'in sUrl: continue
                    if sUrl.startswith('/'): sUrl = re.sub('//', 'https://', sUrl)
                    if sUrl.startswith('/'): sUrl = 'https:/' + sUrl
                    isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
                    if isBlocked: continue
                    if url: self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'prioHoster': prioHoster})

            return self.sources
        except:
            return self.sources

    def resolve(self, url):
        try:
            return url
        except:
            return
