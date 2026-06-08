# -*- coding: UTF-8 -*-
import re
import xbmc
from resources.lib.utils import isBlockedHoster
from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from scrapers.modules import cleantitle

try:
    from urllib import parse as urllib_parse
except ImportError:
    import urllib as urllib_parse

SITE_IDENTIFIER = 'movie2k2'
SITE_DOMAIN = 'movie2k.cx'
SITE_NAME = 'Movie2k2'

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/search?q=%s'
        self.ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    def run(self, titles, year, season=0, episode=0, imdb=''):
        sources = []
        logger.info('Load %s - Start run for: %s' % (SITE_NAME, titles[0]))
        
        links = self.search(titles, year, season, episode)
        if not links:
            logger.info('Load %s - No movie links found' % SITE_NAME)
            return []

        for url in links:
            try:
                logger.info('Load %s - Requesting movie page: %s' % (SITE_NAME, url))
                oRequest = cRequestHandler(url)
                oRequest.addHeaderEntry('User-Agent', self.ua)
                oRequest.addHeaderEntry('Referer', self.base_link)
                html = oRequest.request()
                
                if not html:
                    continue

                pattern = r"loadMirror\s*\(\s*'([^']+)'\s*\).*?>\s*(?:&nbsp;)*\s*([^<|\s|&]+)"
                isMatch, aResult = cParser().parse(html, pattern)

                if isMatch:
                    logger.info('Load %s - Found %s potential mirrors' % (SITE_NAME, len(aResult)))
                    for sStreamUrl, sHosterName in aResult:
                        if sStreamUrl.startswith('//'): sStreamUrl = 'https:' + sStreamUrl
                        elif sStreamUrl.startswith('/'): sStreamUrl = self.base_link + sStreamUrl
                        
                        isBlocked, hoster, sFinalUrl, prioHoster = isBlockedHoster(sStreamUrl)
                        if isBlocked: continue

                        sources.append({
                            'source': hoster or sHosterName.replace('.com','').replace('.to','').strip(),
                            'quality': 'HD' if 'hd.gif' in html.lower() else 'SD',
                            'language': 'de',
                            'url': sFinalUrl,
                            'direct': False,
                            'prioHoster': prioHoster
                        })
            except Exception as e:
                logger.info('Load %s - Error in hoster parsing: %s' % (SITE_NAME, str(e)))
        
        return sources

    def search(self, titles, year, season, episode):
        results = []
        search_term = titles[0]
        try:
            query_url = self.search_link % urllib_parse.quote(search_term)
            logger.info('Load %s - Sending search request: %s' % (SITE_NAME, query_url))
            
            oRequest = cRequestHandler(query_url)
            oRequest.addHeaderEntry('User-Agent', self.ua)
            html = oRequest.request()

            if not html:
                return []

            if 'loadMirror' in html:
                logger.info('Load %s - Direct hit (redirected to movie page)' % SITE_NAME)
                return [oRequest.getRealUrl()]

            pattern = r'href\s*=\s*["\']([^"\']*?/stream/[^"\']+)["\'][^>]*>.*?<strong>([^<]+)</strong>'
            isMatch, aResult = cParser().parse(html, pattern)
            
            if isMatch:
                target_clean = cleantitle.get(search_term)
                for sPath, sName in aResult:
                    if target_clean in cleantitle.get(sName) or cleantitle.get(sName) in target_clean:
                        if sPath.startswith('http'):
                            full_url = sPath
                        else:
                            full_url = self.base_link + ('' if sPath.startswith('/') else '/') + sPath
                        
                        logger.info('Load %s - Match found in list: %s' % (SITE_NAME, sName))
                        results.append(full_url)
                        break

            if not results:
                short_term = search_term.split(' ')[0]
                if short_term != search_term:
                    logger.info('Load %s - No result for full title, trying fallback: %s' % (SITE_NAME, short_term))
                    query_url = self.search_link % urllib_parse.quote(short_term)
                    oRequest = cRequestHandler(query_url)
                    html = oRequest.request()
                    
                    if 'loadMirror' in html: 
                        return [oRequest.getRealUrl()]
                    
                    isMatch, aResult = cParser().parse(html, pattern)
                    if isMatch:
                        for sPath, sName in aResult:
                            if cleantitle.get(short_term) in cleantitle.get(sName):
                                if sPath.startswith('http'):
                                    full_url = sPath
                                else:
                                    full_url = self.base_link + ('' if sPath.startswith('/') else '/') + sPath
                                results.append(full_url)
                                break
            
        except Exception as e:
            logger.info('Load %s - Search error: %s' % (SITE_NAME, str(e)))
            
        return results

    def resolve(self, url):
        return url
