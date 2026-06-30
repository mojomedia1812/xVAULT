# -*- coding: utf-8 -*-
import json
import re
import unicodedata

from resources.lib.control import getSetting, urljoin
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger
from scrapers.modules import cleantitle


SITE_IDENTIFIER = 'bsto'
SITE_DOMAIN = 'bs.to'
SITE_NAME = 'BS.to'
log_utils = True


try:
    from html import unescape as html_unescape
except ImportError:
    try:
        from HTMLParser import HTMLParser as _HTMLParser
        html_unescape = _HTMLParser().unescape
    except Exception:
        def html_unescape(value):
            return value.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")

try:
    from urllib.parse import unquote
except ImportError:
    from urllib import unquote

try:
    import requests
except Exception:
    requests = None


def _clean_text(value):
    value = html_unescape(value or '')
    value = re.sub(r'<[^>]+>', ' ', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def _all_variants(title):
    if not title:
        return []

    title = _clean_text(title)
    parts = [title]
    parts.extend([part.strip() for part in re.split(r'\s*\|\s*', title) if part.strip()])

    results = []
    variant_functions = []
    for name in ('get', 'geturl', 'getsearch', 'movie', 'tv'):
        func = getattr(cleantitle, name, None)
        if func:
            variant_functions.append(func)

    for part in parts:
        for func in variant_functions:
            try:
                value = func(part)
                if value:
                    results.append(value)
            except Exception:
                pass

        try:
            ascii_title = unicodedata.normalize('NFKD', part)
            ascii_title = ascii_title.encode('ascii', 'ignore').decode('ascii')
            ascii_title = re.sub(r'[^a-z0-9]', '', ascii_title.lower())
            if ascii_title:
                results.append(ascii_title)
        except Exception:
            pass

    return list(set([result for result in results if result]))


def _titles_match(search_variants, scraped_title):
    scraped_variants = _all_variants(scraped_title)

    for query in search_variants:
        for scraped in scraped_variants:
            if not query or not scraped:
                continue
            if query == scraped:
                return True
            if len(query) > 4 and query in scraped:
                return True
            if len(scraped) > 4 and scraped in query:
                return True
    return False


class source:
    def __init__(self):
        self.priority = 5
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.sources = []
        self.login_checked = False
        self.logged_in = False
        self.session = requests.Session() if requests else None

        if log_utils:
            logger.info('%s - Init: %s' % (SITE_NAME, self.base_link))

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        if season == 0:
            return self.sources

        try:
            self._login_if_configured()

            search_variants = []
            for title in titles:
                search_variants.extend(_all_variants(title))
            search_variants = list(set([variant for variant in search_variants if variant]))

            if log_utils:
                logger.info('%s - Search: S%02dE%02d | variants=%s' % (SITE_NAME, int(season), int(episode), search_variants))

            matches = self._find_series(titles, search_variants)
            if not matches:
                return self.sources

            for series_url, series_title in matches[:2]:
                if log_utils:
                    logger.info('%s - Match: %s | %s' % (SITE_NAME, series_url, series_title))
                self.run2(series_url, season, episode)

        except Exception as exc:
            if log_utils:
                logger.info('%s - Error: %s' % (SITE_NAME, str(exc)))

        return self.sources

    def run2(self, series_url, season, episode):
        series_url = series_url.strip('/')
        languages = self._requested_language_codes()
        seen = set()

        for language in languages:
            page_url = '%s/%s/%s' % (series_url, int(season), language)
            full_url = urljoin(self.base_link, page_url)

            if log_utils:
                logger.info('%s - Episode page: %s' % (SITE_NAME, full_url))

            html = self._request(full_url, caching=True)
            if not html:
                continue

            hosters = self._parse_hoster_links(html, series_url, season, episode)
            if not hosters:
                continue

            if self._requires_recaptcha(html):
                if log_utils:
                    logger.info('%s - Skipped %d sources on %s: reCAPTCHA required' % (SITE_NAME, len(hosters), page_url))
                continue

            for href, hoster, link_language in hosters:
                key = (href, hoster, link_language)
                if key in seen:
                    continue
                seen.add(key)

                source_language, language_info = self._language_from_code(link_language)
                source_url = urljoin(self.base_link, href)
                if self._source_requires_recaptcha(source_url, full_url):
                    if log_utils:
                        logger.info('%s - Skipped: %s | %s | reCAPTCHA required' % (SITE_NAME, hoster, link_language))
                    continue

                info = language_info

                self.sources.append({
                    'source': hoster,
                    'quality': 'SD',
                    'language': source_language,
                    'url': source_url,
                    'info': info,
                    'direct': False,
                    'debridonly': False,
                    'priority': self.priority,
                    'prioHoster': 100
                })

                if log_utils:
                    logger.info('%s - Added: %s | %s | %s' % (SITE_NAME, hoster, link_language, href))

        if log_utils:
            logger.info('%s - Total: %d sources' % (SITE_NAME, len(self.sources)))

        return self.sources

    def _source_requires_recaptcha(self, url, referer):
        html = self._request(url, referer=referer, caching=False)
        if not html:
            return True
        return self._requires_recaptcha(html)

    def resolve(self, url):
        try:
            if log_utils:
                logger.info('%s - Resolving: %s' % (SITE_NAME, url[:120]))

            html = self._request(url, referer=self.base_link, caching=False)
            if not html:
                return None

            lid = self._extract_attr_by_class(html, 'hoster-player', 'data-lid')
            token = self._extract_meta(html, 'security_token')

            if not lid:
                if log_utils:
                    logger.info('%s - No hoster-player LID found' % SITE_NAME)
                return None

            data = {
                'LID': lid,
                'ticket': '',
                'token': token or ''
            }
            response = self._request(
                urljoin(self.base_link, 'ajax/embed.php'),
                referer=url,
                post=data,
                caching=False,
                accept='application/json, text/javascript, */*; q=0.01'
            )

            if not response:
                return None

            try:
                payload = json.loads(response)
            except Exception:
                if log_utils:
                    logger.info('%s - Embed response is not JSON: %s' % (SITE_NAME, response[:120]))
                return None

            if payload.get('success') and payload.get('link'):
                final_url = html_unescape(payload.get('link'))
                if log_utils:
                    logger.info('%s - Resolved to: %s' % (SITE_NAME, final_url[:120]))
                return final_url

            if self._requires_recaptcha(html):
                logger.info('%s - Hoster link requires reCAPTCHA; no automated bypass is used' % SITE_NAME)
            else:
                logger.info('%s - Embed failed: %s' % (SITE_NAME, response[:160]))
            return None

        except Exception as exc:
            if log_utils:
                logger.info('%s - Resolve error: %s' % (SITE_NAME, str(exc)))
            return None

    def _find_series(self, titles, search_variants):
        html = self._request(urljoin(self.base_link, 'andere-serien'), caching=True)
        if not html:
            return []

        results = []
        seen = set()
        for href, title in self._parse_series_index(html):
            if href in seen:
                continue
            seen.add(href)
            if _titles_match(search_variants, title):
                results.append((href, title))

        return results

    def _parse_series_index(self, html):
        results = []
        for match in re.finditer(r'<a\b([^>]*)>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
            href = self._attr(match.group(1), 'href')
            if not href or not href.startswith('serie/'):
                continue
            if len(href.strip('/').split('/')) != 2:
                continue

            title = _clean_text(match.group(2))
            if not title:
                slug = href.rsplit('/', 1)[-1]
                title = slug.replace('-', ' ')
            results.append((href.strip('/'), title))
        return results

    def _parse_hoster_links(self, html, series_url, season, episode):
        try:
            slug = re.escape(series_url.strip('/').split('/', 1)[1])
        except Exception:
            return []

        pattern = re.compile(
            r'^serie/%s/%s/%s-[^"\']+/(de|en|des)/([^/"\']+)$' % (slug, int(season), int(episode)),
            re.IGNORECASE
        )

        hosters = []
        for match in re.finditer(r'<a\b([^>]*)>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
            attrs = match.group(1)
            href = self._attr(attrs, 'href')
            if not href:
                continue

            link_match = pattern.match(href.strip('/'))
            if not link_match:
                continue

            language = link_match.group(1).lower()
            hoster = self._attr(attrs, 'title') or _clean_text(match.group(2)) or link_match.group(2)
            hoster = _clean_text(unquote(hoster))
            if not hoster:
                continue

            hosters.append((href.strip('/'), hoster, language))

        return hosters

    def _requested_language_codes(self):
        setting = getSetting('hosts.language')
        if setting == '1':
            return ['de']
        if setting == '2':
            return ['en', 'des']
        return ['de', 'en', 'des']

    @staticmethod
    def _language_from_code(code):
        code = (code or '').lower()
        if code == 'de':
            return 'de', 'Deutsch'
        if code == 'des':
            return 'en', 'Deutsch Sub'
        if code == 'en':
            return 'en', 'Englisch'
        return '', ''

    def _login_if_configured(self):
        if self.login_checked:
            return
        self.login_checked = True

        login = getSetting(SITE_IDENTIFIER + '.user')
        password = getSetting(SITE_IDENTIFIER + '.pass')
        if not login or not password:
            return

        try:
            page = self._request(self.base_link, caching=False)
            token = self._extract_input(page, 'security_token')
            data = {
                'login[user]': login,
                'login[pass]': password,
                'login[remember]': 'true',
                'security_token': token or ''
            }
            response = self._request(self.base_link, post=data, referer=self.base_link, caching=False, ajax=False)
            self.logged_in = bool(response and (
                'logout' in response.lower()
                or 'abmelden' in response.lower()
                or not re.search(r'<form[^>]+id=["\']login["\']', response, re.IGNORECASE)
            ))
            if log_utils:
                logger.info('%s - Login configured, success=%s' % (SITE_NAME, self.logged_in))
        except Exception as exc:
            if log_utils:
                logger.info('%s - Login error: %s' % (SITE_NAME, str(exc)))

    def _request(self, url, referer=None, post=None, caching=True, accept=None, ajax=True):
        if self.session is not None:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
                    'Accept': accept or 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
                if referer:
                    headers['Referer'] = referer
                if post is not None:
                    if ajax:
                        headers['X-Requested-With'] = 'XMLHttpRequest'
                    headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'

                try:
                    timeout = int(getSetting('requestTimeout', 10))
                except Exception:
                    timeout = 10

                if post is None:
                    response = self.session.get(url, headers=headers, timeout=timeout)
                else:
                    response = self.session.post(url, data=post, headers=headers, timeout=timeout)

                if response.status_code >= 400 and log_utils:
                    logger.info('%s - HTTP %s for %s' % (SITE_NAME, response.status_code, url[:120]))
                return response.text
            except Exception as exc:
                if log_utils:
                    logger.info('%s - requests fallback: %s' % (SITE_NAME, str(exc)))

        request = cRequestHandler(url, caching=caching if post is None else False, ignoreErrors=True)
        request.addHeaderEntry('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        request.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
        if accept:
            request.addHeaderEntry('Accept', accept)
        if referer:
            request.addHeaderEntry('Referer', referer)
        if post is not None:
            if ajax:
                request.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
            request.addHeaderEntry('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
            for key, value in post.items():
                request.addParameters(key, value)
        return request.request()

    @staticmethod
    def _attr(attrs, name):
        match = re.search(r'%s\s*=\s*(["\'])(.*?)\1' % re.escape(name), attrs, re.IGNORECASE | re.DOTALL)
        return _clean_text(match.group(2)) if match else ''

    @staticmethod
    def _extract_meta(html, name):
        match = re.search(r'<meta[^>]+name=["\']%s["\'][^>]+content=["\']([^"\']+)' % re.escape(name), html, re.IGNORECASE)
        return _clean_text(match.group(1)) if match else ''

    @staticmethod
    def _extract_input(html, name):
        pattern = r'<input[^>]+name=["\']%s["\'][^>]*value=["\']([^"\']*)' % re.escape(name)
        match = re.search(pattern, html, re.IGNORECASE)
        return _clean_text(match.group(1)) if match else ''

    @staticmethod
    def _extract_attr_by_class(html, class_name, attr_name):
        pattern = r'<[^>]+class=["\'][^"\']*%s[^"\']*["\'][^>]*>' % re.escape(class_name)
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            return ''
        return source._attr(match.group(0), attr_name)

    @staticmethod
    def _requires_recaptcha(html):
        match = re.search(r'series\.init\s*\([^,]+,\s*[^,]+,\s*["\']([^"\']*)["\']\)', html, re.IGNORECASE)
        return bool(match and match.group(1).strip())
