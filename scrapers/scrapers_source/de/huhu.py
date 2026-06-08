# -*- coding: utf-8 -*-
import json
import requests
from resources.lib.control import getSetting
import urllib.parse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import xbmc
    KODI_AVAILABLE = True
except ImportError:
    KODI_AVAILABLE = False
    xbmc = None

from scrapers.modules import source_utils
SITE_IDENTIFIER = 'huhu'
DOMAIN = 'www.huhu.to'
URL_MAIN = f'https://{DOMAIN}/web-vod/'
URL_LINKS = URL_MAIN + 'api/links?id=%s'
URL_GET = URL_MAIN + 'api/get?link='

def get_media_data(imdb='', season=0, episode=0):
    try:
        if season == 0:
            result = requests.get(
                f'https://api.themoviedb.org/3/find/{imdb}?api_key={getSetting("api.tmdb")}&external_source=imdb_id',
                timeout=10,
                verify=False
            ).json()["movie_results"][0]
            media_id = f'movie.{result["id"]}'
        else:
            result = requests.get(
                f'https://api.themoviedb.org/3/find/{imdb}?api_key={getSetting("api.tmdb")}&external_source=imdb_id',
                timeout=10,
                verify=False
            ).json()["tv_results"][0]
            media_id = f'series.{result["id"]}.{season}.{episode}'
        
        return media_id
    except:
        return None

def make_request(url):
    headers = {
        'Referer': URL_MAIN,
        'Origin': f'https://{DOMAIN}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        resp = requests.get(
            url,
            headers=headers,
            timeout=15,
            verify=False
        )
        
        if resp.status_code != 200:
            return None
        
        return resp.json()
    except:
        return None

def parse_quality(name):
    if not name:
        return 'SD'
    if '(' in name and 'p)' in name:
        try:
            quality_str = name.split('(')[1].split('p)')[0].strip()
            return quality_str + 'p'
        except:
            pass
    name_lower = name.lower()
    if '2160' in name_lower or '4k' in name_lower:
        return '4K'
    elif '1440' in name_lower or '2k' in name_lower:
        return '1440p'
    elif '1080' in name_lower:
        return '1080p'
    elif '720' in name_lower:
        return '720p'
    elif '480' in name_lower:
        return '480p'
    elif '360' in name_lower:
        return '360p'
    return 'SD'

def parse_hoster(name):
    name = name.split('(')[0].strip()
    
    if 'Server P2' in name:
        return 'Streamtape'
    elif 'Server W2' in name:
        return 'Doodstream'
    elif 'Server O' in name:
        return 'Vidoza'
    elif 'Server E' in name:
        return 'Mixdrop'
    elif 'Server M2' in name:
        return 'Supervideo'
    elif 'Server G2' in name:
        return 'Luluvideo'
    else:
        return name

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domains = ['huhu.to']
    
    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        sources = []
        
        if not imdb:
            return sources
        
        try:
            media_id = get_media_data(imdb, season, episode)
            if not media_id:
                return sources
            
            links_url = URL_LINKS % media_id
            links_data = make_request(links_url)
            
            if not links_data:
                return sources
            
            if not isinstance(links_data, list):
                return sources
            
            for link in links_data:
                try:
                    if not isinstance(link, dict):
                        continue
                    
                    hoster_url = link.get('url', '').strip()
                    if not hoster_url:
                        continue
                    
                    link_name = link.get('name', '')
                    quality = parse_quality(link_name)
                    hoster = parse_hoster(link_name)
                    language = link.get('language', 'de').split('(')[0].strip()
                    
                    final_url = URL_GET + hoster_url
                    
                    source_entry = {
                        'source': hoster,
                        'quality': quality,
                        'language': language,
                        'url': final_url,
                        'direct': False,
                        'debridonly': False,
                        'info': link_name
                    }
                    
                    sources.append(source_entry)
                
                except:
                    continue
            
            return sources
        
        except:
            return sources
    
    def resolve(self, url):
        try:
            headers = {
                'Referer': URL_MAIN,
                'Origin': f'https://{DOMAIN}',
                'User-Agent': 'Mozilla/5.0'
            }
            
            resp = requests.get(
                url,
                headers=headers,
                timeout=10,
                verify=False,
                allow_redirects=True
            )
            
            return resp.url
        
        except:
            return None
