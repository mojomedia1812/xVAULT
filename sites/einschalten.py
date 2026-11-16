# -*- coding: UTF-8 -*-
import re
import json
from scrapers.modules.tools import cParser
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser, source_utils
from resources.lib.control import getSetting, setSetting, urljoin, quote_plus
from resources.lib.utils import isBlockedHoster
import xbmc
import xbmcgui
from resources.lib import movie_identity

SITE_IDENTIFIER = 'einschalten'
import sys, os; sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..")); from resources.lib import log_utils
SITE_DOMAIN = 'einschalten.in'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = urljoin(self.base_link, 'search?query=%s')
        self.checkHoster = False
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        self.sources = []
        queries = list(dict.fromkeys(i for i in titles if i))
        t = [cleantitle.get(i) for i in queries]
        links = []
        seen = set()
        is_movie = (getattr(self, 'mediatype', 'movie') not in ('tvshow', 'episode', 'season', 'tv')
                    and str(season) in ('0', '', 'None') and str(episode) in ('0', '', 'None'))

        try:
            for sSearchText in queries:
                URL_SEARCH = self.search_link % quote_plus(sSearchText)
                oRequest = cRequestHandler(URL_SEARCH, caching=True)
                sHtmlContent = oRequest.request()
                pattern = r'class="group.*?title="([^"]+).*?href="([^"]+).*?span>(\d+)'
                isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                if not isMatch: continue
                for sName, sUrl, sYear in aResult:
                    sYear = int(sYear) if sYear.isdigit() else 0

                    observed = {'title': movie_identity.text(sName), 'year': movie_identity.year_value(sYear)}
                    if is_movie:
                        if movie_identity.classify(titles, year, imdb, observed) != 'verified':
                            continue
                    elif not (cleantitle.get(sName.split('-')[0].strip()) in t and f'staffel {str(season)}' in sName.lower()):
                        continue
                    if sUrl not in seen:
                        seen.add(sUrl)
                        links.append((sUrl, observed))
                if len(links) > 0: break
            if len(links) == 0:
                return self.sources
            for link, observed in links:
                try:
                    found = observed
                    if is_movie:
                        try:
                            detail = cRequestHandler(urljoin(self.base_link, link), caching=True).request()
                        except Exception:
                            detail = ''
                        # Fallbacks are observed provider-card values, never the
                        # requested label/year. Detail conflicts always win.
                        found = movie_identity.from_html(detail, observed['title'], observed['year'])
                        if movie_identity.classify(titles, year, imdb, found) == 'conflict':
                            continue
                    sUrl = self.base_link + '/api' + link + '/watch'
                    sHtmlContent = cRequestHandler(sUrl).request()
                    if 'streamUrl' not in sHtmlContent:
                        log_utils.log('[EINSCHALTEN] API-Antwort enthält keinen Stream', xbmc.LOGWARNING)
                        continue
                    jResult = json.loads(sHtmlContent)
                    releaseName = jResult.get('releaseName', '')
                    streamUrl = jResult.get('streamUrl')
                    if not streamUrl:
                        continue
                    if '2160' in releaseName or '4K' in releaseName:
                        quality = '4K'
                    elif '1440' in releaseName or '2K' in releaseName:
                        quality = '1440p'
                    elif '1080' in releaseName:
                        quality = '1080p'
                    elif '720' in releaseName:
                        quality = '720p'
                    elif '480' in releaseName:
                        quality = '480p'
                    elif '360' in releaseName:
                        quality = '360p'
                    else:
                        quality = 'SD'
                    isBlocked, hoster, url, prioHoster = isBlockedHoster(streamUrl, isResolve=False)
                    if isBlocked:
                        continue
                    row = {'source': hoster, 'quality': quality, 'language': 'de', 'url': streamUrl, 'direct': False, 'prioHoster': prioHoster}
                    if is_movie:
                        self.sources.extend(movie_identity.annotate([row], titles, year, imdb, found))
                    else:
                        self.sources.append(row)
                    if self.sources:
                        break
                except Exception as e:
                    continue
            return self.sources
        except Exception as e:
            return self.sources
    def resolve(self, url):
        try:
            import resolveurl as resolver
            resolved_url = resolver.resolve(url)
            return resolved_url
        except Exception as e:
            return
