# -*- coding: utf-8 -*-
import json
import urllib.parse
from urllib.parse import urlparse
from resources.lib.requestHandler import cRequestHandler

try:
    import xbmc
    KODI_AVAILABLE = True
except ImportError:
    KODI_AVAILABLE = False
    xbmc = None

from scrapers.modules import source_utils
SITE_IDENTIFIER = 'huhu'
DOMAIN = 'oha.to'
SITE_DOMAIN = DOMAIN
SITE_NAME = 'OHA'
URL_MAIN = f'https://{DOMAIN}/'
URL_VOD = URL_MAIN + 'vod'
URL_SOURCE = URL_VOD + '/source/%s/%s.json'
URL_RESOLVE = URL_VOD + '/resolve?url=%s'


def _request_json(url, headers=None):
    try:
        request = cRequestHandler(url, caching=True)
        for key, value in (headers or {}).items():
            request.addHeaderEntry(key, value)
        payload = request.request()
        if not payload:
            return None
        return json.loads(payload)
    except:
        return None


def _request_real_url(url, headers=None):
    try:
        request = cRequestHandler(url, caching=False, ignoreErrors=True)
        for key, value in (headers or {}).items():
            request.addHeaderEntry(key, value)
        request.request()
        return request.getRealUrl() or url
    except:
        return None

def get_media_data(imdb='', season=0, episode=0):
    imdb = (imdb or '').strip()
    if not imdb:
        return None, None
    if season and episode:
        return 'series', 'imdb:%s:%s:%s' % (imdb, int(season), int(episode))
    return 'video', 'imdb:%s' % imdb

def make_request(url):
    headers = {
        'Referer': URL_MAIN,
        'Origin': f'https://{DOMAIN}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        return _request_json(url, headers)
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
    name = (name or '').split('(')[0].strip()
    upper = name.upper()

    if 'SERVER P2' in upper:
        return 'Streamtape'
    elif 'SERVER W2' in upper:
        return 'Doodstream'
    elif 'SERVER O' in upper:
        return 'Vidoza'
    elif 'SERVER E' in upper:
        return 'Mixdrop'
    elif 'SERVER M2' in upper:
        return 'Supervideo'
    elif 'SERVER G2' in upper:
        return 'Luluvideo'
    elif 'SERVER C' in upper:
        return 'VOE'
    elif 'SERVER Z' in upper:
        return 'Filemoon'
    elif 'SERVER A' in upper or 'SERVER B' in upper:
        return 'Doodstream'
    elif 'SERVER R' in upper:
        return 'Vidsonic'
    else:
        return name

def parse_hoster_from_url(url):
    try:
        host = (urlparse(url).hostname or '').lower().replace('www.', '')
        if not host:
            return ''
        if 'voe.' in host:
            return 'VOE'
        if 'dood' in host or 'playmogo' in host or 'myvidplay' in host:
            return 'Doodstream'
        if 'filemoon' in host:
            return 'Filemoon'
        if 'mixdrop' in host:
            return 'Mixdrop'
        if 'supervideo' in host:
            return 'Supervideo'
        if 'veev' in host:
            return 'Veev'
        if 'poophq' in host:
            return 'PoopHD'
        if 'vidsonic' in host:
            return 'Vidsonic'
        return host.split('.')[0].title()
    except:
        return ''

def parse_language(link):
    languages = link.get('languages')
    if isinstance(languages, list) and languages:
        return str(languages[0]).split('(')[0].strip() or 'de'
    return str(link.get('language') or 'de').split('(')[0].strip() or 'de'

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de', 'en']
        self.domains = ['oha.to', 'oha.cx', 'oha.online']
    
    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        sources = []
        
        if not imdb:
            return sources
        
        try:
            media_type, media_id = get_media_data(imdb, season, episode)
            if not media_id:
                return sources
            
            links_url = URL_SOURCE % (media_type, urllib.parse.quote(media_id, safe=':'))
            links_data = make_request(links_url)
            
            if not links_data:
                return sources
            
            if isinstance(links_data, dict):
                links_data = links_data.get('sources') or []
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
                    quality = link.get('quality') or parse_quality(link_name)
                    hoster = parse_hoster(link_name) or parse_hoster_from_url(hoster_url)
                    language = parse_language(link)
                    
                    source_entry = {
                        'source': hoster,
                        'quality': quality,
                        'language': language,
                        'url': hoster_url,
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            resolved = _request_json(URL_RESOLVE % urllib.parse.quote(url, safe=''), headers)
            if isinstance(resolved, dict) and resolved.get('url'):
                return resolved.get('url')
            return url
        
        except:
            return None
