# -*- coding: UTF-8 -*-

import json
import re
from html import unescape as html_unescape
from urllib.parse import quote, quote_plus, urlencode, urljoin, urlparse

from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger
from resources.lib.utils import isBlockedHoster
from scrapers.modules import cleantitle


SITE_IDENTIFIER = 'moflix'
SITE_DOMAIN = 'moflix-stream.xyz'
SITE_NAME = 'MoFlix'

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'


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
        self.sources = []
        self._seen = set()

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            item = self._best_match(titles, year, season, imdb)
            if not item:
                return self.sources

            if int(season or 0) > 0 and int(episode or 0) > 0:
                videos = self._episode_videos(item.get('id'), season, episode)
            else:
                detail = self._json(self.detail_link % item.get('id'), self.base_link + '/')
                title = detail.get('title') if isinstance(detail.get('title'), dict) else {}
                videos = title.get('videos') or []

            self._add_videos(videos)
        except Exception as exc:
            logger.error('[%s] Fehler: %s' % (SITE_NAME, exc))
        return self.sources

    def resolve(self, url):
        return url

    def _best_match(self, titles, year, season, imdb):
        candidates = []
        seen = set()
        for title in self._search_titles(titles):
            data = self._json(self.search_link % (quote(title), quote_plus(title)), self.base_link + '/')
            results = data.get('results') if isinstance(data, dict) else []
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
        return candidates[0][1] if candidates else None

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
            if not payload or str(request.getStatus()) not in ['', '200', '301', '302']:
                return {}
            return json.loads(payload)
        except Exception as exc:
            logger.error('[%s] Request fehlgeschlagen: %s (%s)' % (SITE_NAME, url, exc))
            return {}

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
