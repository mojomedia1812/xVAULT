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

    def _request(self, url, headers=None, caching=False, preserve_newlines=False):
        request = cRequestHandler(url, caching=caching, ignoreErrors=True)
        if preserve_newlines:
            request.removeNewLines(False)
            request.removeBreakLines(False)
        request.addHeaderEntry('User-Agent', self.ua)
        request.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
        for key, value in (headers or {}).items():
            request.addHeaderEntry(key, value)
        payload = request.request()
        return payload, str(request.getStatus()), request.getRealUrl()

    def _request_json(self, url, headers=None, caching=False):
        payload, status, real_url = self._request(url, headers=headers, caching=caching)
        if status not in ['200', '301']:
            logger.error('[%s] API-Status: %s' % (SITE_NAME, status))
            return None
        try:
            return json.loads(payload)
        except Exception as exc:
            logger.error('[%s] JSON-Fehler: %s' % (SITE_NAME, str(exc)))
            return None

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

    def _language_headers(self, stream_language, referer=''):
        headers = {
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8' if stream_language == 'de' else 'en-US,en;q=0.9,de;q=0.7',
        }
        if referer:
            headers['Referer'] = referer
        return headers

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
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            payload, status, real_url = self._request(page_url, headers=headers, caching=False)
            logger.info('[%s] Seite besucht: %s - Status: %s' % (SITE_NAME, page_url, status))
            return status in ['200', '301']
        except Exception as exc:
            logger.error('[%s] Fehler beim Seitenbesuch: %s' % (SITE_NAME, str(exc)))
            return False

    def _fresh_embed_url(self, tmdb_id, season=0, episode=0, language='de'):
        media_type, page_url, api_url = self._media_urls(tmdb_id, season, episode)
        self._visit_page_for_cookies(page_url)

        headers = {
            'Referer': page_url,
            'Accept': 'application/json, */*',
            'Origin': 'https://' + self.domain,
            'Connection': 'keep-alive'
        }
        data = self._request_json(api_url, headers=headers, caching=False)
        if not data:
            return None, None
        src = data.get('src', '')
        if not src:
            logger.warning('[%s] Kein src in API-Response gefunden' % SITE_NAME)
            return None, None

        embed_url = 'https://%s%s' % (VIXCLOUD, self._src_with_language(src, language))
        logger.info('[%s] Frischer Embed: type=%s tmdb=%s lang=%s' % (SITE_NAME, media_type, tmdb_id, language))
        return embed_url, page_url

    def _playlist_from_embed(self, embed_url, referer, stream_language):
        headers = {
            'Referer': referer,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        headers.update(self._language_headers(stream_language))

        html, status, real_url = self._request(embed_url, headers=headers, caching=False)
        if status not in ['200', '301']:
            logger.error('[%s] Embed Status: %s' % (SITE_NAME, status))
            return None, None, None

        token_match = re.search(r"['\"]token['\"]?\s*:\s*['\"]([a-f0-9]+)['\"]", html)
        expires_match = re.search(r"['\"]expires['\"]?\s*:\s*['\"]?(\d+)['\"]?", html)
        url_match = re.search(r"url\s*:\s*['\"]([^'\"]+/playlist/\d+)['\"]", html)

        if not (token_match and expires_match and url_match):
            logger.error('[%s] Playlist-Parameter unvollstaendig: token=%s expires=%s url=%s' % (
                SITE_NAME, bool(token_match), bool(expires_match), bool(url_match)
            ))
            return None, None, None

        playlist_url = '%s?token=%s&expires=%s&h=1&lang=%s' % (
            url_match.group(1), token_match.group(1), expires_match.group(1), stream_language
        )
        playlist_headers = {
            'User-Agent': self.ua,
            'Accept': '*/*',
            'Referer': embed_url,
            'Origin': 'https://' + VIXCLOUD,
        }
        playlist_headers.update(self._language_headers(stream_language))

        playlist, playlist_status, real_playlist_url = self._request(
            playlist_url,
            headers=playlist_headers,
            caching=False,
            preserve_newlines=True
        )
        if playlist_status not in ['200', '301']:
            logger.error('[%s] Playlist Status: %s' % (SITE_NAME, playlist_status))
            return playlist_url, playlist_headers, None

        return playlist_url, playlist_headers, playlist

    def _verified_stream_language(self, tmdb_id, season, episode, stream_language):
        embed_url, referer = self._fresh_embed_url(tmdb_id, season, episode, stream_language)
        if not embed_url:
            return None, None, None

        playlist_url, playlist_headers, playlist = self._playlist_from_embed(embed_url, referer, stream_language)
        if not playlist:
            logger.warning('[%s] Sprache nicht verifiziert: lang=%s tmdb=%s' % (SITE_NAME, stream_language, tmdb_id))
            return None, None, None

        audio_languages = self._audio_languages_from_playlist(playlist)
        if audio_languages and stream_language not in audio_languages:
            logger.warning('[%s] Sprache verworfen: angefordert=%s, Audio=%s, tmdb=%s' % (
                SITE_NAME, stream_language, ','.join(sorted(audio_languages)), tmdb_id
            ))
            return None, None, None

        if audio_languages:
            logger.info('[%s] Sprache verifiziert: lang=%s, Audio=%s, tmdb=%s' % (
                SITE_NAME, stream_language, ','.join(sorted(audio_languages)), tmdb_id
            ))
        return embed_url, playlist_url, audio_languages

    def _audio_languages_from_playlist(self, playlist):
        languages = set()
        audio_seen = False
        if isinstance(playlist, bytes):
            playlist = playlist.decode('utf-8', 'replace')
        media_lines = re.findall(r'#EXT-X-MEDIA:[^#\r\n]+', playlist or '', flags=re.I)
        if not media_lines:
            media_lines = (playlist or '').splitlines()
        for line in media_lines:
            if not re.search(r'#EXT-X-MEDIA', line or '', flags=re.I):
                continue
            if not re.search(r'TYPE\s*=\s*AUDIO', line or '', flags=re.I):
                continue
            audio_seen = True
            code = self._audio_language_from_values(
                self._hls_attr(line, 'LANGUAGE'),
                self._hls_attr(line, 'NAME'),
                self._hls_attr(line, 'RENDITION')
            )
            if code:
                languages.add(code)
        if audio_seen and not languages:
            languages.add('unknown')
        return languages

    @staticmethod
    def _hls_attr(line, name):
        match = re.search(r'%s=(?:"([^"]*)"|([^,]*))' % re.escape(name), line or '', flags=re.I)
        if not match:
            return ''
        return (match.group(1) if match.group(1) is not None else match.group(2) or '').strip()

    @staticmethod
    def _audio_language_from_values(*values):
        text = ' '.join([str(value or '') for value in values]).lower()
        text = re.sub(r'[^a-z0-9]+', ' ', text)
        tokens = set([token for token in text.split() if token])
        if tokens.intersection(set(['de', 'deu', 'ger', 'german', 'deutsch'])):
            return 'de'
        if tokens.intersection(set(['en', 'eng', 'english', 'englisch'])):
            return 'en'
        return ''

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            tmdb_id = self._get_tmdb_id(imdb)
            if not tmdb_id:
                logger.warning('[%s] Keine TMDB-ID gefunden fuer IMDB: %s' % (SITE_NAME, imdb))
                return self.sources

            seen_urls = set()
            for language, language_label in self._stream_languages():
                embed_url, playlist_url, audio_languages = self._verified_stream_language(tmdb_id, season, episode, language)
                if not embed_url:
                    continue

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
            playlist_url, headers_dict, playlist = self._playlist_from_embed(embed_url, referer, stream_language)
            if not playlist_url or not headers_dict or not playlist:
                return None

            audio_languages = self._audio_languages_from_playlist(playlist)
            if audio_languages and stream_language not in audio_languages:
                logger.error('[%s] Resolve abgebrochen: angefordert=%s, Audio=%s' % (
                    SITE_NAME, stream_language, ','.join(sorted(audio_languages))
                ))
                return None

            final_url = '%s|%s' % (playlist_url, urllib.parse.urlencode(headers_dict))
            logger.info('[%s] Finale URL: %s' % (SITE_NAME, final_url[:150]))
            return final_url

        except Exception as exc:
            logger.error('[%s] resolve() Fehler: %s' % (SITE_NAME, str(exc)))
            import traceback
            logger.debug('[%s] Traceback: %s' % (SITE_NAME, traceback.format_exc()))
            return None
