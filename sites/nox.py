# -*- coding: UTF-8 -*-

import json
import re

from resources.lib.control import getSetting, quote_plus
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHoster
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'nox'
SITE_DOMAIN = 'nox.to'
SITE_NAME = SITE_IDENTIFIER.upper()


class source:
    def __init__(self):
        self.priority = 6
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/api/frontend/search/%s'
        self.media_link = self.base_link + '/api/frontend/media/%s'
        self.sources = []
        self._seen = set()

    def run(self, titles, year, season=0, episode=0, imdb=''):
        try:
            clean_titles = set([cleantitle.get(title) for title in titles if title])
            for title in titles:
                data = self._request_json(self.search_link % quote_plus(title), self.base_link)
                media_items = data.get('result', {}).get('media', []) if isinstance(data, dict) else []
                for media in media_items:
                    if not self._matches_media(media, clean_titles, year, season, imdb):
                        continue
                    detail = self._request_json(self.media_link % media.get('slug'), self.base_link + '/download/Filme/%s' % media.get('slug'))
                    self._add_ready_links(detail.get('result', detail), season, episode)
                    if len(self.sources) >= 20:
                        return self.sources
        except:
            pass
        return self.sources

    def resolve(self, url):
        return url

    def _add_ready_links(self, media, season, episode):
        for release in media.get('releases', []) or []:
            if int(season or 0) > 0 and not self._matches_episode_release(release, season, episode):
                continue
            if release.get('linkState') != 'ready' or not release.get('link'):
                continue
            for link in release.get('link') or []:
                url = link.get('url') if isinstance(link, dict) else link
                self._add_source(url, release)

    def _add_source(self, url, release):
        if not url or url in self._seen:
            return
        self._seen.add(url)
        is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(url, isResolve=False)
        if is_blocked or not clean_url:
            return
        self.sources.append({
            'source': hoster,
            'quality': self._quality(release),
            'language': self._language(release),
            'url': clean_url,
            'direct': False,
            'prioHoster': prio_hoster,
            'info': release.get('name', '')
        })

    def _matches_media(self, media, clean_titles, year, season, imdb):
        if imdb and media.get('imdbid') == imdb:
            return True
        title = cleantitle.get(media.get('title', ''))
        if title not in clean_titles:
            return False
        media_type = media.get('type')
        if int(season or 0) > 0 and media_type not in ['series', 'episode', None]:
            return False
        if not season and media_type in ['series', 'episode']:
            return False
        try:
            if year and media.get('productionyear') and abs(int(media.get('productionyear')) - int(year)) > 1:
                return False
        except:
            pass
        return True

    @staticmethod
    def _matches_episode_release(release, season, episode):
        name = '%s %s' % (release.get('name', ''), release.get('title', ''))
        match = re.search(r'\bS0*(\d+)\s*E0*(\d+)\b', name, re.I)
        return bool(match and int(match.group(1)) == int(season or 0) and int(match.group(2)) == int(episode or 0))

    def _request_json(self, url, referer):
        request = cRequestHandler(url, caching=True)
        request.addHeaderEntry('Accept', 'application/json, text/plain, */*')
        request.addHeaderEntry('Referer', referer)
        payload = request.request()
        if not payload:
            return {}
        return json.loads(payload)

    @staticmethod
    def _quality(release):
        text = ' '.join([str(release.get(key, '')) for key in ['video', 'name', 'title', 'notes']]).lower()
        if '2160' in text or '4k' in text:
            return '4K'
        if '1440' in text:
            return '1440p'
        if '1080' in text:
            return '1080p'
        if '720' in text:
            return '720p'
        if '480' in text or 'dvd' in text:
            return 'SD'
        return 'HD'

    @staticmethod
    def _language(release):
        text = ' '.join([str(release.get(key, '')) for key in ['audio', 'name', 'title']]).lower()
        if 'dl' in text or ('german' in text and 'english' in text):
            return 'multi'
        if any(token in text for token in ['german', 'deutsch', '.ger.', ' ger ']):
            return 'de'
        if any(token in text for token in ['english', '.eng.', ' eng ']):
            return 'en'
        return 'unknown'
