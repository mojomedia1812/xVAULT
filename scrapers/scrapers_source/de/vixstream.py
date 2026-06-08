# -*- coding: UTF-8 -*-
import re
import json
import base64
import urllib.parse
from resources.lib.requestHandler import cRequestHandler
from resources.lib.control import getSetting
from resources.lib.tools import logger

SITE_IDENTIFIER = 'vixstream'
SITE_DOMAIN = 'vixsrc.to'
SITE_NAME = SITE_IDENTIFIER.upper()
VIXCLOUD = 'vixcloud.co'
_K = base64.b64decode('ZWRkZTZiNWU0MTI0NmFiNzlhMjY5N2NkMTI1ZTE3ODE=').decode()

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.tak = getSetting('api.tmdb') or _K
        self.ua = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/29.0 Chrome/136.0.0.0 Mobile Safari/537.36"
        self.sources = []
        self._session = None

    def _get_session(self):
    
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
                self._session.headers.update({
                    'User-Agent': self.ua,
                    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8'
                })
            except ImportError:
                logger.error('[%s] requests module nicht verfügbar!' % SITE_NAME)
        return self._session

    def _get_tmdb_id(self, imdb_id):
        try:
            url = 'https://api.themoviedb.org/3/find/%s?api_key=%s&external_source=imdb_id' % (imdb_id, self.tak)
            oRequest = cRequestHandler(url, caching=True)
            data = json.loads(oRequest.request())
            if data.get('movie_results'):
                return str(data['movie_results'][0]['id'])
            elif data.get('tv_results'):
                return str(data['tv_results'][0]['id'])
        except Exception as e:
            logger.error('[%s] TMDB Fehler: %s' % (SITE_NAME, str(e)))
        return None

    def _visit_page_for_cookies(self, page_url):
        
        try:
            session = self._get_session()
            if not session:
                logger.error('[%s] Keine Session verfügbar' % SITE_NAME)
                return False
            
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            response = session.get(page_url, headers=headers, timeout=10)
            logger.info('[%s] Seite besucht: %s - Status: %s' % (SITE_NAME, page_url, response.status_code))
            return response.status_code == 200
        except Exception as e:
            logger.error('[%s] Fehler beim Seitenbesuch: %s' % (SITE_NAME, str(e)))
            return False

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            tmdb_id = self._get_tmdb_id(imdb)
            if not tmdb_id:
                logger.warning('[%s] Keine TMDB-ID gefunden für IMDB: %s' % (SITE_NAME, imdb))
                return self.sources

            
            if int(season) == 0:
                page_url = 'https://%s/movie/%s' % (self.domain, tmdb_id)
                api_url = 'https://%s/api/movie/%s' % (self.domain, tmdb_id)
            else:
                page_url = 'https://%s/tv/%s' % (self.domain, tmdb_id)
                api_url = 'https://%s/api/tv/%s/%s/%s' % (self.domain, tmdb_id, str(season), str(episode))

        
            self._visit_page_for_cookies(page_url)

            session = self._get_session()
            if not session:
                logger.error('[%s] Keine Session für API-Aufruf verfügbar' % SITE_NAME)
                return self.sources

            headers = {
                'Referer': page_url,
                'Accept': 'application/json, */*',
                'Origin': 'https://' + self.domain,
                'Connection': 'keep-alive'
            }
            response = session.get(api_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error('[%s] API-Status: %s' % (SITE_NAME, response.status_code))
                return self.sources
            
            data = response.json()
            src = data.get('src', '')
            
            if not src:
                logger.warning('[%s] Kein src in API-Response gefunden' % SITE_NAME)
                return self.sources

            
            src = re.sub(r'lang=[a-z]+', 'lang=de', src)
            embed_url = 'https://%s%s' % (VIXCLOUD, src)

            self.sources.append({
                'source': 'VixCloud',
                'quality': '1080p',
                'language': 'de',
                'url': embed_url + '|' + page_url,
                'direct': False
            })
            logger.info('[%s] Quelle gefunden: tmdb=%s, url=%s' % (SITE_NAME, tmdb_id, embed_url))

        except Exception as e:
            logger.error('[%s] run() Fehler: %s' % (SITE_NAME, str(e)))
            import traceback
            logger.debug('[%s] Traceback: %s' % (SITE_NAME, traceback.format_exc()))

        return self.sources

    def resolve(self, url_data):
      try:
        embed_url, referer = url_data.split('|', 1)
        logger.info('[%s] resolve() - embed_url: %s' % (SITE_NAME, embed_url))

        session = self._get_session()
        if not session:
            logger.error('[%s] Keine Session für resolve verfügbar' % SITE_NAME)
            return None

        video_id_match = re.search(r'/embed/(\d+)', embed_url)
        if not video_id_match:
            logger.error('[%s] Konnte Video-ID nicht aus embed URL extrahieren' % SITE_NAME)
            return None
        
        video_id = video_id_match.group(1)
        logger.info('[%s] Video-ID: %s' % (SITE_NAME, video_id))

        headers = {
            'Referer': referer,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
        }
        
        logger.info('[%s] Lade embed-Seite: %s' % (SITE_NAME, embed_url))
        response = session.get(embed_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logger.error('[%s] Embed Status: %s' % (SITE_NAME, response.status_code))
            return None
        
        html = response.text
        
        token_match = re.search(r"['\"]token['\"]?\s*:\s*['\"]([a-f0-9]+)['\"]", html)
        expires_match = re.search(r"['\"]expires['\"]?\s*:\s*['\"]?(\d+)['\"]?", html)
        url_match = re.search(r"url\s*:\s*['\"]([^'\"]+/playlist/\d+)['\"]", html)
        
        if not token_match:
            logger.error('[%s] Token nicht gefunden' % SITE_NAME)
            snippet = html[:2000] if len(html) > 2000 else html
            logger.info('[%s] HTML snippet: %s...' % (SITE_NAME, snippet))
        if not expires_match:
            logger.error('[%s] Expires nicht gefunden' % SITE_NAME)
        if not url_match:
            logger.error('[%s] URL nicht gefunden' % SITE_NAME)
        
        if token_match and expires_match and url_match:
            token = token_match.group(1)
            expires = expires_match.group(1)
            base_url = url_match.group(1)
            
            logger.info('[%s] Extrahiert - Token: %s..., Expires: %s' % (SITE_NAME, token[:16], expires))
            
            playlist_url = '%s?token=%s&expires=%s&h=1&lang=de' % (base_url, token, expires)
            logger.info('[%s] Playlist aus masterPlaylist: %s' % (SITE_NAME, playlist_url))
            
            headers_dict = {
                'User-Agent': self.ua,
                'Referer': embed_url,
                'Origin': 'https://' + self.domain,
            }
            
            final_url = '%s|%s' % (playlist_url, urllib.parse.urlencode(headers_dict))
            logger.info('[%s] Finale URL: %s' % (SITE_NAME, final_url[:150]))
            return final_url
        
        logger.error('[%s] Nicht alle Parameter gefunden' % SITE_NAME)
        return None

      except Exception as e:
        logger.error('[%s] resolve() Fehler: %s' % (SITE_NAME, str(e)))
        import traceback
        logger.debug('[%s] Traceback: %s' % (SITE_NAME, traceback.format_exc()))
        return None
