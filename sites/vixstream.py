# -*- coding: UTF-8 -*-
import base64
import json
import re
import urllib.parse

from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger

SITE_IDENTIFIER = 'vixstream'
SITE_DOMAIN = 'vixsrc.to'
SITE_NAME = SITE_IDENTIFIER.upper()
VIXCLOUD = 'vixcloud.co'
_K = base64.b64decode('ZWRkZTZiNWU0MTI0NmFiNzlhMjY5N2NkMTI1ZTE3ODE=').decode()


class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.tak = getSetting('api.tmdb') or _K
        self.ua = (
            'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
            '(KHTML, like Gecko) SamsungBrowser/29.0 Chrome/136.0.0.0 Mobile Safari/537.36'
        )
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
                logger.error('[%s] requests module nicht verfuegbar!' % SITE_NAME)
        return self._session

    def _get_tmdb_id(self, imdb_id):
        try:
            url = 'https://api.themoviedb.org/3/find/%s?api_key=%s&external_source=imdb_id' % (imdb_id, self.tak)
            oRequest = cRequestHandler(url, caching=True)
            data = json.loads(oRequest.request())
            if data.get('movie_results'):
                return str(data['movie_results'][0]['id'])
            if data.get('tv_results'):
                return str(data['tv_results'][0]['id'])
        except Exception as exc:
            logger.error('[%s] TMDB Fehler: %s' % (SITE_NAME, str(exc)))
        return None

    def _stream_languages(self):
        setting = getSetting('hosts.language') or '0'
        if setting == '1':
            return [('de', 'Deutsch')]
        if setting == '2':
            return [('en', 'Englisch')]
        return [('de', 'Deutsch'), ('en', 'Englisch')]

    def _src_with_language(self, src, language):
        if re.search(r'([?&])lang=[a-z]+', src):
            return re.sub(r'([?&])lang=[a-z]+', r'\1lang=%s' % language, src)
        separator = '&' if '?' in src else '?'
        return '%s%slang=%s' % (src, separator, language)

    def _media_urls(self, tmdb_id, season=0, episode=0):
        is_tvshow = getattr(self, 'mediatype', None) == 'tvshow'
        if int(season) == 0 and not is_tvshow:
            page_url = 'https://%s/movie/%s' % (self.domain, tmdb_id)
            api_url = 'https://%s/api/movie/%s' % (self.domain, tmdb_id)
            media_type = 'movie'
        else:
            page_url = 'https://%s/tv/%s' % (self.domain, tmdb_id)
            api_url = 'https://%s/api/tv/%s/%s/%s' % (self.domain, tmdb_id, str(season), str(episode))
            media_type = 'tv'
        return media_type, page_url, api_url

    def _stable_url(self, tmdb_id, season=0, episode=0, language='de'):
        if int(season) == 0 and getattr(self, 'mediatype', None) != 'tvshow':
            return 'vixsrc://movie/%s?lang=%s' % (tmdb_id, language)
        return 'vixsrc://tv/%s/%s/%s?lang=%s' % (tmdb_id, int(season), int(episode), language)

    def _visit_page_for_cookies(self, page_url):
        try:
            session = self._get_session()
            if not session:
                logger.error('[%s] Keine Session verfuegbar' % SITE_NAME)
                return False

            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            response = session.get(page_url, headers=headers, timeout=10)
            logger.info('[%s] Seite besucht: %s - Status: %s' % (SITE_NAME, page_url, response.status_code))
            return response.status_code == 200
        except Exception as exc:
            logger.error('[%s] Fehler beim Seitenbesuch: %s' % (SITE_NAME, str(exc)))
            return False

    def _fresh_embed_url(self, tmdb_id, season=0, episode=0, language='de'):
        media_type, page_url, api_url = self._media_urls(tmdb_id, season, episode)
        self._visit_page_for_cookies(page_url)

        session = self._get_session()
        if not session:
            logger.error('[%s] Keine Session fuer API-Aufruf verfuegbar' % SITE_NAME)
            return None, None

        headers = {
            'Referer': page_url,
            'Accept': 'application/json, */*',
            'Origin': 'https://' + self.domain,
            'Connection': 'keep-alive'
        }
        response = session.get(api_url, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error('[%s] API-Status: %s' % (SITE_NAME, response.status_code))
            return None, None

        data = response.json()
        src = data.get('src', '')
        if not src:
            logger.warning('[%s] Kein src in API-Response gefunden' % SITE_NAME)
            return None, None

        embed_url = 'https://%s%s' % (VIXCLOUD, self._src_with_language(src, language))
        logger.info('[%s] Frischer Embed: type=%s tmdb=%s lang=%s' % (SITE_NAME, media_type, tmdb_id, language))
        return embed_url, page_url

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            tmdb_id = self._get_tmdb_id(imdb)
            if not tmdb_id:
                logger.warning('[%s] Keine TMDB-ID gefunden fuer IMDB: %s' % (SITE_NAME, imdb))
                return self.sources

            embed_url, page_url = self._fresh_embed_url(tmdb_id, season, episode, 'de')
            if not embed_url:
                return self.sources

            seen_urls = set()
            for language, language_label in self._stream_languages():
                stable_url = self._stable_url(tmdb_id, season, episode, language)
                if stable_url in seen_urls:
                    continue
                seen_urls.add(stable_url)

                self.sources.append({
                    'source': 'VixCloud',
                    'quality': '1080p',
                    'language': language,
                    'url': stable_url,
                    'direct': False,
                    'info': language_label
                })
                logger.info('[%s] Quelle gefunden: tmdb=%s, lang=%s' % (SITE_NAME, tmdb_id, language))

        except Exception as exc:
            logger.error('[%s] run() Fehler: %s' % (SITE_NAME, str(exc)))
            import traceback
            logger.debug('[%s] Traceback: %s' % (SITE_NAME, traceback.format_exc()))

        return self.sources

    def _resolve_stable_url(self, url_data):
        parsed = urllib.parse.urlparse(url_data)
        query = urllib.parse.parse_qs(parsed.query)
        stream_language = query.get('lang', ['de'])[0]
        if stream_language not in ['de', 'en']:
            stream_language = 'de'

        parts = [part for part in parsed.path.strip('/').split('/') if part]
        if parsed.netloc == 'movie' and len(parts) >= 1:
            embed_url, referer = self._fresh_embed_url(parts[0], 0, 0, stream_language)
            return embed_url, referer, stream_language

        if parsed.netloc == 'tv' and len(parts) >= 3:
            tmdb_id, season, episode = parts[:3]
            embed_url, referer = self._fresh_embed_url(tmdb_id, season, episode, stream_language)
            return embed_url, referer, stream_language

        logger.error('[%s] Ungueltige stabile URL: %s' % (SITE_NAME, url_data))
        return None, None, stream_language

    def resolve(self, url_data):
        try:
            if url_data.startswith('vixsrc://'):
                embed_url, referer, stream_language = self._resolve_stable_url(url_data)
                if not embed_url:
                    return None
            else:
                embed_url, referer = url_data.split('|', 1)
                parsed_embed = urllib.parse.urlparse(embed_url)
                stream_language = urllib.parse.parse_qs(parsed_embed.query).get('lang', ['de'])[0]
                if stream_language not in ['de', 'en']:
                    stream_language = 'de'

            logger.info('[%s] resolve() - embed_url: %s' % (SITE_NAME, embed_url))

            session = self._get_session()
            if not session:
                logger.error('[%s] Keine Session fuer resolve verfuegbar' % SITE_NAME)
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
                'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8' if stream_language == 'de' else 'en-US,en;q=0.9,de;q=0.7',
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

                playlist_url = '%s?token=%s&expires=%s&h=1&lang=%s' % (base_url, token, expires, stream_language)
                logger.info('[%s] Playlist aus masterPlaylist: %s' % (SITE_NAME, playlist_url))

                headers_dict = {
                    'User-Agent': self.ua,
                    'Referer': embed_url,
                    'Origin': 'https://' + VIXCLOUD,
                }
                final_url = '%s|%s' % (playlist_url, urllib.parse.urlencode(headers_dict))
                logger.info('[%s] Finale URL: %s' % (SITE_NAME, final_url[:150]))
                return final_url

            logger.error('[%s] Nicht alle Parameter gefunden' % SITE_NAME)
            return None

        except Exception as exc:
            logger.error('[%s] resolve() Fehler: %s' % (SITE_NAME, str(exc)))
            import traceback
            logger.debug('[%s] Traceback: %s' % (SITE_NAME, traceback.format_exc()))
            return None
