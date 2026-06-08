# -*- coding: utf-8 -*-
from resources.lib.utils import isBlockedHoster
from scrapers.modules.tools import cParser
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle
from resources.lib.control import getSetting, setSetting, urljoin
try:
    from json import loads
except:
    from simplejson import loads

SITE_IDENTIFIER = 'kkiste'
SITE_DOMAIN = 'kkiste.eu'
SITE_NAME = 'KKiste'

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.browse_link = self.base_link + '/data/browse/?lang=%s&type=%s&order_by=new&page=1&limit=0'
        self.watch_link = self.base_link + '/data/watch/?_id=%s'
        
        
        self.hoster_priority = {
            'streamtape': 5,
            'voe': 10,
            'doodstream': 5,
            'mixdrop': 9,
            'streamwish': 8,
            'filemoon': 5,
            'vidoza': 7,
            'upstream': 5,
            'streamruby': 10,
            'vidguard': 6
        }
        self.min_priority = 6  
        self.max_per_hoster = 5  

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            from resources.lib.requestHandler import cRequestHandler
            from scrapers.modules import cleantitle
            from scrapers.modules.tools import cParser
            import re
        except:
            return []

        sources = []
        
        try:
            t = set([cleantitle.get(i) for i in set(titles) if i])
            years = (year, year+1, year-1, 0)
            
            lang = '2'
            mediaType = 'tvseries' if season > 0 else 'movies'
            searchUrl = self.browse_link % (lang, mediaType)
            
            oRequest = cRequestHandler(searchUrl)
            oRequest.addHeaderEntry('Referer', self.base_link + '/')
            oRequest.addHeaderEntry('Origin', self.base_link)
            sJson = oRequest.request()
            aJson = loads(sJson)
            
            if 'movies' not in aJson:
                return []
            
            movie_id = None
            
            for movie in aJson['movies']:
                if '_id' not in movie:
                    continue
                
                sTitle = str(movie.get('title', ''))
                sYear = movie.get('year', 0)
                
                if season == 0:
                    if 'Staffel' in sTitle or 'Season' in sTitle:
                        continue
                    if cleantitle.get(sTitle) in t and int(sYear) in years:
                        movie_id = str(movie['_id'])
                        break
                else:
                    if ' - ' not in sTitle:
                        continue
                    sSeriesTitle = sTitle.split(' - ')[0].strip()
                    if cleantitle.get(sSeriesTitle) in t:
                        seasonMatch = re.search(r'Staffel\s+(\d+)|Season\s+(\d+)', sTitle, re.IGNORECASE)
                        if seasonMatch:
                            foundSeason = int(seasonMatch.group(1) or seasonMatch.group(2))
                            if foundSeason == season:
                                movie_id = str(movie['_id'])
                                break
            
            if not movie_id:
                return []
            
            watchUrl = self.watch_link % movie_id
            oRequest = cRequestHandler(watchUrl)
            oRequest.addHeaderEntry('Referer', self.base_link + '/')
            oRequest.addHeaderEntry('Origin', self.base_link)
            sJson = oRequest.request()
            aJson = loads(sJson)
            
            if 'streams' not in aJson:
                return []
            
            
            hoster_count = {}
            
            for stream in aJson['streams']:
                if season > 0:
                    if 'e' not in stream or int(stream['e']) != episode:
                        continue
                
                if 'stream' not in stream:
                    continue
                
                sUrl = stream['stream']
                
                if 'youtube' in sUrl.lower() or 'vod' in sUrl.lower():
                    continue
                
                if sUrl.startswith('//'):
                    sUrl = 'https:' + sUrl
                elif sUrl.startswith('/'):
                    sUrl = 'https:/' + sUrl
                
                isMatch, aName = cParser.parse(sUrl, '//([^/]+)/')
                if not isMatch:
                    continue
                
                sName = aName[0]
                if '.' in sName:
                    sName = sName[:sName.rindex('.')]
                
                # Priorität prüfen
                priority = 0
                for hoster, prio in self.hoster_priority.items():
                    if hoster in sName.lower():
                        priority = prio
                        break
                
                if priority < self.min_priority:
                    continue
                
                
                hoster_key = sName.lower()
                if hoster_key not in hoster_count:
                    hoster_count[hoster_key] = 0
                
                if hoster_count[hoster_key] >= self.max_per_hoster:
                    continue  
                
                
                hoster_count[hoster_key] += 1
                
                quality = 'HD'
                if 'release' in stream and stream['release']:
                    release = str(stream['release']).upper()
                    if 'CAM' in release or 'TS' in release:
                        quality = 'CAM'
                    elif 'SD' in release:
                        quality = 'SD'
                
                sources.append({
                    'source': sName,
                    'quality': quality,
                    'language': 'de',
                    'url': sUrl,
                    'direct': False,
                    'debridonly': False,
                    'priority': priority
                })
            
            
            sources = sorted(sources, key=lambda x: x.get('priority', 0), reverse=True)
            return sources
            
        except:
            return []

    def resolve(self, url):
        return url
