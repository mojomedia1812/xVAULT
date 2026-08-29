# -*- coding: UTF-8 -*-

import json
import re
from html import unescape
from urllib.parse import quote_plus, urljoin, urlparse

from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger
from resources.lib.utils import isBlockedHoster
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'filmo'
SITE_DOMAIN = 'filmo.to'
SITE_NAME = 'Filmo'

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/search?q=%s'
        self.suggest_link = self.base_link + '/search/suggest?q=%s'
        self.sources = []
        self._seen = set()
        self._last_response_header = None

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        if int(season or 0) > 0:
            return self.sources
        try:
            clean_titles = set([cleantitle.get(title) for title in titles if title])
            for candidate in self._candidates(titles):
                page = self._get(candidate.get('url'), referer=self.base_link + '/')
                if not page:
                    continue
                title = self._page_title(page) or candidate.get('title')
                if not self._matches(title, clean_titles, year, page):
                    continue
                self._add_chips(candidate.get('url'), page)
                if len(self.sources) >= 20:
                    break
        except Exception as exc:
            logger.error('[Filmo] Fehler: %s' % exc)
        return self.sources

    def resolve(self, url):
        return url

    def _candidates(self, titles):
        result = []
        seen = set()
        for title in titles:
            if not title:
                continue
            for item in self._suggest(title) + self._search(title):
                url = item.get('url') or ''
                if not url:
                    continue
                url = urljoin(self.base_link, url)
                if '/movies/' not in url or url in seen:
                    continue
                seen.add(url)
                result.append({'title': item.get('title') or '', 'url': url})
                if len(result) >= 30:
                    return result
        return result

    def _suggest(self, title):
        try:
            headers = {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
            payload, status, _real_url = self._request(
                self.suggest_link % quote_plus(title),
                referer=self.base_link + '/',
                headers=headers,
                caching=True
            )
            if status not in ('200', '301'):
                return []
            data = json.loads(payload or '{}')
            items = []
            for movie in data.get('movies') or []:
                if isinstance(movie, dict):
                    items.append({'title': movie.get('title') or '', 'url': movie.get('url') or ''})
            return items
        except Exception:
            return []

    def _search(self, title):
        html = self._get(self.search_link % quote_plus(title), referer=self.base_link + '/')
        if not html:
            return []
        items = []
        seen = set()
        for match in re.finditer(r'(?is)<a\b[^>]+href=["\']([^"\']*/movies/[^"\']+)["\'][^>]*>(.*?)</a>', html):
            url = unescape(match.group(1)).strip()
            if url in seen:
                continue
            seen.add(url)
            body = match.group(2)
            title = (
                self._attr_text(match.group(0), 'title')
                or self._attr_text(match.group(0), 'aria-label')
                or self._class_text(body, 'popular-spotlight-card__title')
                or self._class_text(body, 'movie-poster-grid-card__title')
                or self._attr_text(body, 'alt')
            )
            items.append({'title': title, 'url': url})
        return items

    def _add_chips(self, page_url, html):
        csrf = self._csrf_token(html)
        open_mint = self._open_mint_url(html) or (self.base_link + '/n')
        for row in self._provider_rows(html):
            language = self._language(row.get('language'))
            if language not in ('de', 'en'):
                continue
            for chip in row.get('chips') or []:
                final_url = self._mint(open_mint, chip.get('p'), csrf, page_url)
                if not final_url or final_url in self._seen:
                    continue
                self._seen.add(final_url)

                is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(final_url, isResolve=False)
                if is_blocked or not clean_url:
                    continue

                quality = self._quality(chip.get('metadata') or [])
                info = ' | '.join([value for value in chip.get('metadata') or [] if value and value != quality])
                if row.get('language'):
                    info = ('%s | %s' % (row.get('language'), info)).strip(' |')

                self.sources.append({
                    'source': hoster or chip.get('hoster') or SITE_NAME,
                    'quality': quality,
                    'language': language,
                    'url': clean_url,
                    'direct': False,
                    'debridonly': False,
                    'prioHoster': prio_hoster,
                    'info': info
                })

    def _provider_rows(self, html):
        rows = []
        pattern = re.compile(
            r'(?is)<div class=["\']provider-row["\'][^>]*>.*?'
            r'<span class=["\']provider-row__lang["\']>(.*?)</span>.*?'
            r'<div class=["\']provider-row__chips["\']>(.*?)(?=<div class=["\']provider-row["\']|</section>|<div class=["\']mt-2|\Z)'
        )
        for match in pattern.finditer(html or ''):
            row_html = match.group(2)
            chips = []
            for chip_match in re.finditer(r'(?is)<div\b[^>]*data-provider-chip\b[^>]*>.*?</div>', row_html):
                chip_html = chip_match.group(0)
                p_value = self._attr_text_raw(chip_html, 'data-p')
                if not p_value:
                    continue
                chips.append({
                    'p': p_value,
                    'hoster': self._attr_text(chip_html, 'aria-label') or self._class_text(chip_html, 'provider-chip__name'),
                    'metadata': self._metadata(chip_html),
                })
            if chips:
                rows.append({'language': self._clean(match.group(1)), 'chips': chips})
        return rows

    def _mint(self, open_mint, p_value, csrf, referer):
        if not p_value:
            return ''
        try:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.base_link,
                'Referer': referer or self.base_link + '/',
            }
            if csrf:
                headers['X-CSRF-TOKEN'] = csrf
            payload, status, _real_url = self._request(
                open_mint,
                referer=referer or self.base_link + '/',
                headers=headers,
                post={'p': p_value},
                jspost=True,
                caching=False
            )
            if status not in ('200', '301'):
                return ''
            response = json.loads(payload or '{}') or {}
            direct_url = self._external_url(
                response.get('url') or response.get('href') or response.get('location') or response.get('redirect')
            )
            if direct_url:
                return direct_url

            token = response.get('x') or response.get('token')
            if not token:
                return ''
            mint_url = open_mint.rstrip('/') + '/' + quote_plus(token)
            redirect_html, status, real_url = self._request(
                mint_url,
                referer=referer or self.base_link + '/',
                caching=False,
                follow_redirects=False
            )
            redirect_url = self._redirect_target_from_response(mint_url, status, real_url, redirect_html)
            if redirect_url:
                return redirect_url

            redirect_html, status, real_url = self._request(
                mint_url,
                referer=referer or self.base_link + '/',
                caching=False,
                follow_redirects=True
            )
            redirect_url = self._redirect_target_from_response(mint_url, status, real_url, redirect_html)
            return redirect_url or ''
        except Exception:
            return ''

    def _get(self, url, referer=None):
        if not url:
            return ''
        try:
            payload, status, _real_url = self._request(
                url,
                referer=referer or self.base_link + '/',
                headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'},
                caching=False
            )
            if status not in ('200', '301'):
                return ''
            return payload
        except Exception:
            return ''

    def _request(self, url, referer=None, headers=None, post=None, jspost=False, caching=False, follow_redirects=True):
        request = cRequestHandler(url, caching=caching, ignoreErrors=True, jspost=jspost, preserve_url=True, follow_redirects=follow_redirects)
        request.addHeaderEntry('User-Agent', UA)
        request.addHeaderEntry('Accept-Language', 'de,en-US;q=0.7,en;q=0.3')
        request.addHeaderEntry('Connection', 'close')
        if referer:
            request.addHeaderEntry('Referer', referer)
        for key, value in (headers or {}).items():
            request.addHeaderEntry(key, value)
        for key, value in (post or {}).items():
            request.addParameters(key, value)
        payload = request.request()
        self._last_response_header = request.getResponseHeader()
        return payload or '', str(request.getStatus()), request.getRealUrl()

    def _matches(self, title, clean_titles, year, html):
        clean_title = cleantitle.get(title or '')
        if clean_title not in clean_titles and not any(
            clean_title and value and len(clean_title) >= 5 and len(value) >= 5 and (clean_title in value or value in clean_title)
            for value in clean_titles
        ):
            return False
        page_year = self._year(html)
        try:
            if year and page_year and abs(int(page_year) - int(year)) > 1:
                return False
        except Exception:
            pass
        return True

    def _year(self, html):
        release = self._detail_value(html, 'Erscheinungsdatum')
        match = re.search(r'\b(19\d{2}|20\d{2})\b', release or '')
        if match:
            return match.group(1)
        match = re.search(r'<span[^>]*class=["\'][^"\']*ft-meta-label[^"\']*["\'][^>]*>\s*(19\d{2}|20\d{2})\s*</span>', html or '', re.I)
        return match.group(1) if match else ''

    def _detail_value(self, html, label):
        match = re.search(
            r'(?is)<h3[^>]*class=["\'][^"\']*section-headline[^"\']*["\'][^>]*>\s*%s\s*</h3>.*?'
            r'<dd[^>]*class=["\'][^"\']*entry-description[^"\']*["\'][^>]*>(.*?)</dd>' % re.escape(label),
            html or ''
        )
        return self._clean(match.group(1)) if match else ''

    def _page_title(self, html):
        match = re.search(r'<h1[^>]*>(.*?)</h1>', html or '', re.S | re.I)
        if match:
            return self._clean(match.group(1))
        match = re.search(r'<title[^>]*>(.*?)</title>', html or '', re.S | re.I)
        title = self._clean(match.group(1)) if match else ''
        return re.sub(r'\s+jetzt kostenlos streamen\s+.*$', '', title, flags=re.I)

    def _csrf_token(self, html):
        return self._meta_content(html, 'csrf-token')

    def _open_mint_url(self, html):
        match = re.search(r'"openMint"\s*:\s*"([^"]+)"', html or '')
        return self._json_url(match.group(1)) if match else ''

    def _metadata(self, chip_html):
        values = []
        for match in re.finditer(r'(?is)<span class=["\']provider-chip__metadata-tag["\']>(.*?)</span>', chip_html or ''):
            value = self._clean(match.group(1))
            if value:
                values.append(value)
        return values

    @staticmethod
    def _quality(values):
        text = ' '.join([str(value or '') for value in values]).lower()
        if '2160' in text or '4k' in text:
            return '4K'
        if '1440' in text:
            return '1440p'
        if '1080' in text:
            return '1080p'
        if '720' in text:
            return '720p'
        if '480' in text or 'sd' in text:
            return 'SD'
        return 'HD'

    @staticmethod
    def _language(value):
        text = str(value or '').strip().lower()
        if text in ('deutsch', 'german', 'de', 'ger') or 'deutsch' in text or 'german' in text:
            return 'de'
        if text in ('english', 'englisch', 'en', 'eng') or 'english' in text or 'englisch' in text:
            return 'en'
        return 'unknown'

    def _class_text(self, html, class_name):
        match = re.search(r'(?is)<[^>]+class=["\'][^"\']*%s[^"\']*["\'][^>]*>(.*?)</[^>]+>' % re.escape(class_name), html or '')
        return self._clean(match.group(1)) if match else ''

    def _attr_text(self, html, attr):
        return self._clean(self._attr_text_raw(html, attr))

    @staticmethod
    def _attr_text_raw(html, attr):
        match = re.search(r'\b%s=["\']([^"\']+)["\']' % re.escape(attr), html or '', re.S | re.I)
        return unescape(match.group(1)).strip() if match else ''

    def _meta_content(self, html, name):
        match = re.search(r'<meta[^>]+name=["\']%s["\'][^>]+content=["\']([^"\']*)["\']' % re.escape(name), html or '', re.S | re.I)
        return self._clean(match.group(1)) if match else ''

    @staticmethod
    def _json_url(value):
        return value.replace('\\/', '/').replace('\\u0026', '&').replace('\\u003d', '=')

    def _redirect_target_from_response(self, request_url, status, real_url, html):
        header = getattr(self, '_last_response_header', None)
        location = ''
        try:
            if header:
                location = header.get('Location') or header.get('location') or ''
        except Exception:
            location = ''

        for candidate in [location, real_url, self._extract_redirect_url(html)]:
            target = self._external_url(candidate, request_url)
            if target:
                return target
        return ''

    def _extract_redirect_url(self, html):
        patterns = [
            r'(?is)<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^"\']*url=([^"\']+)',
            r'(?is)window\.location(?:\.href)?\s*=\s*["\']([^"\']+)',
            r'(?is)location\.replace\(\s*["\']([^"\']+)',
            r'(?is)<a\b[^>]*\bhref=["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html or '')
            if match:
                return unescape(match.group(1)).strip()
        return ''

    def _external_url(self, value, base_url=None):
        if not value:
            return ''
        try:
            target = urljoin(base_url or self.base_link, self._json_url(unescape(str(value)).strip()))
            if not target or self._is_filmo_url(target):
                return ''
            return target
        except Exception:
            return ''

    def _is_filmo_url(self, value):
        try:
            host = (urlparse(str(value).split('|', 1)[0]).hostname or '').lower()
            domain = (self.domain or SITE_DOMAIN).lower()
            return host == domain or host.endswith('.' + domain)
        except Exception:
            return False

    @staticmethod
    def _clean(value):
        value = unescape(value or '')
        value = re.sub(r'<[^>]+>', ' ', value)
        value = re.sub(r'\s+', ' ', value)
        return value.strip()
