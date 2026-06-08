# -*- coding: UTF-8 -*-
from resources.lib.utils import isBlockedHoster
import re, json
from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules.tools import cParser

SITE_IDENTIFIER = 'movie2k'
import xbmc
import sys, os; sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..")); from resources.lib import log_utils
SITE_DOMAIN = 'movie2k.ch' 
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = 'https://movie2k.ch/data/browse/?lang=2&keyword=%s&year=%s&type=%s&page=1' 
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb=''):
        jSearch = self.search(titles, year, season, episode)
        if jSearch == [] or jSearch == 0: return
        jSearch = sorted(jSearch, key=lambda k: k.get('added', ''), reverse=True)
        total = 0
        loop = 0
        for i in range(len(jSearch)):
            sUrl = jSearch[i]['stream']
            #if 'streamtape' in sUrl: continue
            loop += 1
            if loop == 50:
                break

            release = jSearch[i].get('release', '')
            if '2160' in release or '4K' in release:
                quality = '4K'
            elif '1440' in release or '2K' in release:
                quality = '1440p'
            elif '1080' in release:
                quality = '1080p'
            elif '720' in release:
                quality = '720p'
            elif '480' in release:
                quality = '480p'
            elif '360' in release:
                quality = '360p'
            else:
                quality = 'HD'

            isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
            if isBlocked: continue
            if url:
                self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'prioHoster': prioHoster})
                total += 1
                if total == 10: break
        return self.sources

    def resolve(self, url):
        return  url

    def search(self, titles, year, season, episode):
        jSearch = []
        mtype = 'movies'
        if season > 0:
            year = ''
            mtype = 'tvseries'
        for title in titles:
            try:
                query = self.search_link % (title, year, mtype)
                oRequest = cRequestHandler(query)
                Search = oRequest.request()
                if '"success":false' in Search: continue
                Search = re.sub(r'\\\s+\\', '\\\\',   Search)
                jSearch = json.loads(Search)['movies']
                if jSearch == []:  continue
                if season > 0:
                    for i in jSearch:
                        isMatch, sSeason = cParser.parseSingleResult(i.get('title'), r'Staffel.*?(\d+)')
                        if sSeason == str(season):
                            id = i.get('_id', False)
                            if id: break
                else:
                    for i in jSearch:
                        if i.get('year', False) and  not i.get('year') == year: continue
                        id = i.get('_id', False)
                        if id: break
                oRequest = cRequestHandler('https://movie2k.ch/data/watch/?_id=%s'  % id)
                jSearch = json.loads(oRequest.request())
                if season > 0:
                    jSearch = jSearch['streams']
                    jSearchNew = []
                    for i in jSearch:
                        if not i.get('e', False): continue
                        elif not str(i.get('e')) == str(episode): continue
                        jSearchNew.append(i)
                    return jSearchNew
                else:
                    return jSearch['streams']
            except:
                continue
        return jSearch
