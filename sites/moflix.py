# -*- coding: UTF-8 -*-

import json
import re
import unicodedata
from html import unescape as html_unescape
from urllib.parse import quote, quote_plus, urlencode, urljoin, urlparse

from resources.lib.control import getSetting, setSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger
from resources.lib.utils import isBlockedHoster
from scrapers.modules import cleantitle


SITE_IDENTIFIER = 'moflix'
SITE_DOMAIN = 'moflix-stream.xyz'
SITE_NAME = 'MoFlix'

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'


class MoflixTemporarilyUnavailable(Exception):
    xvault_provider_reason = 'cloudflare'
    xvault_provider_ttl = 30 * 60


class source:
    def __init__(self):
        self.priority = 4
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain.strip('/')
        self.search_link = self.base_link + '/api/v1/search/%s?query=%s&limit=8'
        self.detail_link = self.base_link + '/api/v1/titles/%s?load=images,genres,productionCountries,keywords,videos,primaryVideo,seasons,compactCredits'
        self.episode_link = self.base_link + '/api/v1/titles/%s/seasons/%s/episodes/%s?load=videos,compactCredits,primaryVideo'
        self.episodes_link = self.base_link + '/api/v1/titles/%s/seasons/%s/episodes?perPage=100&query=&page=1'
        self.html_search_link = self.base_link + '/search/%s'
        self.html_title_link = self.base_link + '/titles/%s/%s'
        self.html_episode_link = self.base_link + '/titles/%s/%s/season/%s/episode/%s'
        self.sources = []
        self._seen = set()

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            item = self._best_match(titles, year, season, imdb)
            if not item:
                return self.sources

            if int(season or 0) > 0 and int(episode or 0) > 0:
                videos = self._episode_videos_with_fallback(item, season, episode)
            else:
                videos = self._title_videos(item)

            self._add_videos(videos)
            if self.sources:
                self._mark_available()
        except MoflixTemporarilyUnavailable as exc:
            logger.warning('[%s] Temporaer nicht verfuegbar: %s' % (SITE_NAME, exc))
            raise
        except Exception as exc:
            logger.error('[%s] Fehler: %s' % (SITE_NAME, exc))
        return self.sources

    def resolve(self, url):
        return url

    def _best_match(self, titles, year, season, imdb):
        candidates = []
        seen = set()
        last_block = None
        html_fallback_ok = False
        for title in self._search_titles(titles):
            results = []
            try:
                data = self._json(self.search_link % (quote(title), quote_plus(title)), self.base_link + '/')
                results = data.get('results') if isinstance(data, dict) else []
            except MoflixTemporarilyUnavailable as exc:
                last_block = exc
                logger.info('[%s] API-Suche blockiert, nutze HTML-Fallback fuer "%s": %s' % (SITE_NAME, title, exc))

            if not results:
                try:
                    html_results = self._html_search(title)
                    html_fallback_ok = True
                    if html_results:
                        results = html_results
                except MoflixTemporarilyUnavailable as exc:
                    last_block = exc

            for item in results or []:
                if not isinstance(item, dict):
                    continue
                if str(item.get('model_type') or '').lower() == 'person':
                    continue
                item_id = item.get('id')
                if item_id in seen:
                    continue
                seen.add(item_id)
                score = self._match_score(item, titles, year, season, imdb)
                if score > 0:
                    candidates.append((score, item))
        candidates.sort(key=lambda value: value[0], reverse=True)
        if candidates:
            return candidates[0][1]
        if last_block and not html_fallback_ok:
            raise last_block
        return None

    def _match_score(self, item, titles, year, season, imdb):
        want_series = int(season or 0) > 0
        is_series = bool(item.get('is_series'))
        if want_series != is_series:
            return 0

        score = 0
        if imdb and str(item.get('imdb_id') or '').strip().lower() == str(imdb).strip().lower():
            score += 100

        clean_titles = set([cleantitle.get(title) for title in titles if title])
        item_titles = set()
        for key in ['name', 'title', 'original_title']:
            value = item.get(key)
            if value:
                item_titles.add(cleantitle.get(value))
        for value in list(item_titles):
            value = re.sub(r'(unrated|extended|directorscut|germansub|uncut)$', '', value or '')
            if value:
                item_titles.add(value)

        if clean_titles.intersection(item_titles):
            score += 60
        elif self._loose_title_match(clean_titles, item_titles):
            score += 25
        else:
            return 0 if not score else score

        item_year = self._year(item)
        try:
            if year and item_year:
                delta = abs(int(year) - int(item_year))
                if delta == 0:
                    score += 20
                elif delta == 1:
                    score += 8
                else:
                    score -= 35
        except Exception:
            pass

        return score

    def _episode_videos(self, title_id, season, episode):
        if not title_id:
            return []
        detail = self._json(self.episode_link % (title_id, int(season or 0), int(episode or 0)), self.base_link + '/')
        episode_data = detail.get('episode') if isinstance(detail.get('episode'), dict) else {}
        videos = episode_data.get('videos') or []
        if videos:
            return videos

        listing = self._json(self.episodes_link % (title_id, int(season or 0)), self.base_link + '/')
        pagination = listing.get('pagination') if isinstance(listing.get('pagination'), dict) else {}
        for candidate in pagination.get('data') or []:
            try:
                if int(candidate.get('episode_number') or 0) == int(episode or 0):
                    candidate_id = candidate.get('episode_number') or episode
                    detail = self._json(self.episode_link % (title_id, int(season or 0), int(candidate_id)), self.base_link + '/')
                    episode_data = detail.get('episode') if isinstance(detail.get('episode'), dict) else {}
                    return episode_data.get('videos') or []
            except Exception:
                pass
        return []

    def _title_videos(self, item):
        videos = []
        try:
            detail = self._json(self.detail_link % item.get('id'), self.base_link + '/')
            title = detail.get('title') if isinstance(detail.get('title'), dict) else {}
            videos = title.get('videos') or []
        except MoflixTemporarilyUnavailable as exc:
            logger.info('[%s] API-Details blockiert, nutze HTML-Fallback: %s' % (SITE_NAME, exc))

        if videos:
            return videos
        return self._html_title_videos(item)

    def _episode_videos_with_fallback(self, item, season, episode):
        videos = []
        try:
            videos = self._episode_videos(item.get('id'), season, episode)
        except MoflixTemporarilyUnavailable as exc:
            logger.info('[%s] API-Episode blockiert, nutze HTML-Fallback: %s' % (SITE_NAME, exc))

        if videos:
            return videos
        return self._html_episode_videos(item, season, episode)

    def _add_videos(self, videos):
        for video in videos or []:
            if not isinstance(video, dict):
                continue
            url = html_unescape(str(video.get('src') or '').strip())
            if not url or url in self._seen or 'youtube.' in url.lower() or 'youtu.be/' in url.lower():
                continue
            self._seen.add(url)

            quality = self._quality('%s %s' % (video.get('quality') or '', url))
            language = self._language(video.get('language'), video.get('quality'), video.get('name'), url)
            info = self._info(video)
            direct = self._is_direct(url, video)
            clean_url = self._with_headers(url) if direct else url

            if direct:
                if self._is_moflix_hls(url) and not self._direct_hls_usable(url):
                    logger.info('[%s] Direkter HLS-Link verworfen: Unter-Playlist nicht erreichbar' % SITE_NAME)
                    continue
                hoster = self._host_name(url) or SITE_NAME
                prio_hoster = 20
            else:
                is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(clean_url, isResolve=False)
                if is_blocked or not clean_url:
                    continue
                prio_hoster = min(prio_hoster, self._mirror_priority(clean_url))

            self.sources.append({
                'source': hoster or SITE_NAME,
                'quality': quality,
                'language': language,
                'url': clean_url,
                'direct': direct,
                'debridonly': False,
                'prioHoster': prio_hoster,
                'info': info
            })

    def _json(self, url, referer):
        try:
            request = cRequestHandler(url, caching=True, preserve_url=True)
            request.addHeaderEntry('User-Agent', UA)
            request.addHeaderEntry('Accept', 'application/json, text/plain, */*')
            request.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
            request.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
            request.addHeaderEntry('Referer', referer or self.base_link + '/')
            payload = request.request()
            status = str(request.getStatus() or '')
            if self._is_cloudflare_challenge(payload, status):
                raise MoflixTemporarilyUnavailable('Cloudflare-Schutz aktiv (%s)' % (status or 'unbekannter Status'))
            if status == '403':
                raise MoflixTemporarilyUnavailable('HTTP 403 von %s' % self.domain)
            if not payload or status not in ['', '200', '301', '302']:
                return {}
            return json.loads(payload)
        except MoflixTemporarilyUnavailable:
            raise
        except Exception as exc:
            logger.error('[%s] Request fehlgeschlagen: %s (%s)' % (SITE_NAME, url, exc))
            return {}

    def _html_search(self, title):
        data = self._html_bootstrap(self.html_search_link % quote(title, safe=''), self.base_link + '/')
        loaders = data.get('loaders') if isinstance(data.get('loaders'), dict) else {}
        search_page = loaders.get('searchPage') if isinstance(loaders.get('searchPage'), dict) else {}
        results = search_page.get('results') or []
        return results if isinstance(results, list) else []

    def _html_title_videos(self, item):
        data = self._html_bootstrap(self._html_title_url(item), self.base_link + '/')
        return self._videos_from_bootstrap(data)

    def _html_episode_videos(self, item, season, episode):
        title_id = item.get('id')
        slug = self._title_slug(item)
        url = self.html_episode_link % (
            quote(str(title_id), safe=''),
            quote(slug, safe=''),
            int(season or 0),
            int(episode or 0)
        )
        data = self._html_bootstrap(url, self._html_title_url(item))
        return self._videos_from_bootstrap(data)

    def _html_title_url(self, item):
        title_id = item.get('id')
        return self.html_title_link % (quote(str(title_id), safe=''), quote(self._title_slug(item), safe=''))

    def _html_bootstrap(self, url, referer=None):
        payload, status = self._request_html(url, referer)
        if self._is_cloudflare_challenge(payload, status):
            raise MoflixTemporarilyUnavailable('Cloudflare-Schutz auf HTML-Seite aktiv (%s)' % (status or 'unbekannter Status'))
        if not payload or status not in ['', '200', '301', '302']:
            logger.warning('[%s] HTML-Fallback ohne Antwort: %s (%s)' % (SITE_NAME, url, status or 'kein Status'))
            return {}
        data = self._extract_bootstrap_data(payload)
        if not data:
            logger.warning('[%s] HTML-Fallback ohne bootstrapData: %s' % (SITE_NAME, url))
        return data

    def _request_html(self, url, referer=None):
        try:
            request = cRequestHandler(url, caching=True, preserve_url=True)
            request.removeNewLines(False)
            request.removeBreakLines(False)
            request.addHeaderEntry('User-Agent', UA)
            request.addHeaderEntry('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8')
            request.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
            request.addHeaderEntry('Referer', referer or self.base_link + '/')
            request.addHeaderEntry('Upgrade-Insecure-Requests', '1')
            request.addHeaderEntry('Sec-Fetch-Dest', 'document')
            request.addHeaderEntry('Sec-Fetch-Mode', 'navigate')
            request.addHeaderEntry('Sec-Fetch-Site', 'same-origin')
            payload = request.request()
            status = str(request.getStatus() or '')
            return payload or '', status
        except Exception:
            return '', ''

    def _mark_available(self):
        try:
            setSetting('provider.' + SITE_IDENTIFIER + '.check', 'true')
            if self.domain:
                setSetting('provider.' + SITE_IDENTIFIER + '.domain', self.domain)
        except Exception:
            pass

    @staticmethod
    def _extract_bootstrap_data(payload):
        marker = 'window.bootstrapData'
        start = (payload or '').find(marker)
        if start < 0:
            return {}
        start = (payload or '').find('{', start)
        if start < 0:
            return {}

        depth = 0
        in_string = False
        escape = False
        end = -1
        for index in range(start, len(payload or '')):
            char = payload[index]
            if in_string:
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        if end < 0:
            return {}

        try:
            data = json.loads(payload[start:end])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _videos_from_bootstrap(data):
        loaders = data.get('loaders') if isinstance(data, dict) else {}
        if not isinstance(loaders, dict):
            return []
        for page_key, data_keys in [
            ('episodePage', ['episode', 'video', 'title']),
            ('titlePage', ['title', 'video']),
            ('watchPage', ['video', 'title', 'episode'])
        ]:
            page = loaders.get(page_key)
            if not isinstance(page, dict):
                continue
            for data_key in data_keys:
                node = page.get(data_key)
                if isinstance(node, dict) and isinstance(node.get('videos'), list) and node.get('videos'):
                    return node.get('videos') or []
        return source._find_videos(loaders)

    @staticmethod
    def _find_videos(value):
        if isinstance(value, dict):
            videos = value.get('videos')
            if isinstance(videos, list) and videos:
                return videos
            for child in value.values():
                found = source._find_videos(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = source._find_videos(child)
                if found:
                    return found
        return []

    def _title_slug(self, item):
        for key in ['name', 'title', 'original_title']:
            value = item.get(key)
            if value:
                return self._slug(value)
        return self._slug(item.get('id'))

    @staticmethod
    def _slug(value):
        text = html_unescape(str(value or '')).strip().lower()
        for old, new in [('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')]:
            text = text.replace(old, new)
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
        return text or 'title'

    def _request_text(self, url, referer=None, caching=False):
        try:
            request = cRequestHandler(url, caching=caching, preserve_url=True)
            request.removeNewLines(False)
            request.removeBreakLines(False)
            request.addHeaderEntry('User-Agent', UA)
            request.addHeaderEntry('Accept', '*/*')
            request.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
            request.addHeaderEntry('Referer', referer or self.base_link + '/')
            request.addHeaderEntry('Origin', self.base_link)
            payload = request.request()
            status = str(request.getStatus() or '')
            return payload or '', status
        except Exception:
            return '', ''

    def _direct_hls_usable(self, url):
        try:
            master, status = self._request_text(url, self.base_link + '/', caching=False)
            if status not in ['200', '301', '302'] or '#EXTM3U' not in master:
                return False
            child = self._first_child_playlist(master)
            if not child:
                return True
            child_url = urljoin(url, child)
            _payload, child_status = self._request_text(child_url, url, caching=False)
            return child_status in ['200', '301', '302']
        except Exception:
            return False

    @staticmethod
    def _first_child_playlist(master):
        for line in (master or '').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '.m3u' in line.lower():
                return line
        return ''

    @staticmethod
    def _is_cloudflare_challenge(payload, status):
        text = str(payload or '').lower()
        if payload == 'CLOUDFLARE-SCHUTZ AKTIV':
            return True
        if (
            'cf-mitigated' in text or
            'just a moment' in text or
            'enable javascript and cookies' in text
        ):
            return True
        if status == '403' and (
            'cloudflare' in text
        ):
            return True
        return False

    def _search_titles(self, titles):
        seen = set()
        result = []
        for title in titles or []:
            title = html_unescape(str(title or '').strip())
            if not title:
                continue
            variants = [title]
            if ' - ' in title:
                variants.append(title.split(' - ', 1)[0].strip())
            if ':' in title:
                variants.append(title.split(':', 1)[0].strip())
            for variant in variants:
                key = variant.lower()
                if variant and key not in seen:
                    seen.add(key)
                    result.append(variant)
        return result[:8]

    @staticmethod
    def _loose_title_match(clean_titles, item_titles):
        for wanted in clean_titles:
            for current in item_titles:
                if not wanted or not current or min(len(wanted), len(current)) < 5:
                    continue
                if wanted in current or current in wanted:
                    return True
        return False

    @staticmethod
    def _year(item):
        for key in ['year', 'release_date', 'first_air_date']:
            value = item.get(key)
            match = re.search(r'\b(19\d{2}|20\d{2})\b', str(value or ''))
            if match:
                return match.group(1)
        return ''

    @staticmethod
    def _quality(value):
        text = str(value or '').lower()
        if '2160' in text or '4k' in text:
            return '4K'
        if '1440' in text:
            return '1440p'
        if '1080' in text:
            return '1080p'
        if '720' in text:
            return '720p'
        if '480' in text or '360' in text or 'sd' in text:
            return 'SD'
        return 'HD'

    @staticmethod
    def _language(explicit, *values):
        explicit = str(explicit or '').strip().lower()
        if explicit in ['de', 'deu', 'ger', 'german', 'deutsch']:
            return 'de'
        if explicit in ['en', 'eng', 'english', 'englisch']:
            return 'en'
        if explicit in ['multi', 'multilang', 'dual', 'dl']:
            return 'multi'

        text = ' '.join([str(value or '').lower() for value in values])
        tokens = set(re.findall(r'[a-z]+', text))
        if 'multi' in tokens or 'dual' in tokens or 'dl' in tokens or ('de' in tokens and 'en' in tokens):
            return 'multi'
        if any(token in tokens for token in ['de', 'deu', 'ger', 'german', 'deutsch']):
            return 'de'
        if any(token in tokens for token in ['en', 'eng', 'english', 'englisch']):
            return 'en'
        return 'unknown'

    def _info(self, video):
        values = []
        for key in ['name', 'quality', 'type', 'origin']:
            value = str(video.get(key) or '').strip()
            if value and value.lower() not in ['none', 'null']:
                values.append(value)
        return ' | '.join(values)

    @staticmethod
    def _is_direct(url, video):
        url_path = str(url or '').split('|', 1)[0].split('?', 1)[0].lower()
        video_type = str(video.get('type') or '').lower()
        return video_type == 'stream' or url_path.endswith(('.m3u8', '.m3u', '.mpd', '.mp4'))

    @staticmethod
    def _is_moflix_hls(url):
        try:
            clean_url = str(url or '').split('|', 1)[0].split('?', 1)[0].lower()
            host = (urlparse(clean_url).hostname or '').lower()
            return clean_url.endswith(('.m3u8', '.m3u')) and (
                host.endswith('.moflix-stream.day') or host.endswith('.moflix-stream.xyz')
            )
        except Exception:
            return False

    def _with_headers(self, url):
        if '|' in url:
            return url
        headers = urlencode({
            'User-Agent': UA,
            'Referer': self.base_link + '/',
            'Origin': self.base_link,
        })
        return '%s|%s' % (url, headers)

    @staticmethod
    def _host_name(url):
        try:
            host = (urlparse(str(url).split('|', 1)[0]).hostname or '').lower()
            if host.startswith('www.'):
                host = host[4:]
            for prefix in ['moflix-stream.', 'moflix.']:
                if host.startswith(prefix):
                    return 'MoFlix'
            if host.endswith('.moflix-stream.day') or host.endswith('.moflix-stream.xyz'):
                return 'MoFlix'
            return host
        except Exception:
            return ''

    @staticmethod
    def _mirror_priority(url):
        host = (urlparse(str(url or '').split('|', 1)[0]).hostname or '').lower()
        if host == 'veev.to':
            return 25
        if host == 'moflix-stream.click':
            return 35
        if host in ['moflix.rpmplay.xyz', 'moflix.upns.xyz']:
            return 45
        if host == 'moflix-stream.link':
            return 55
        if host == 'gupload.xyz':
            return 70
        return 100
