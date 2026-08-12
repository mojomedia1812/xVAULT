# -*- coding: utf-8 -*-
import datetime
import json
import re
from urllib.parse import urlparse

from resources.lib.control import getSetting, urljoin
from resources.lib import provider_logins
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger
from scrapers.modules import cleantitle, dom_parser


SITE_IDENTIFIER = 'aniworld'
SITE_DOMAIN = 'aniworld.to'
SITE_NAME = 'AniWorld'
log_utils = True

try:
    from html import unescape as html_unescape
except ImportError:
    try:
        from HTMLParser import HTMLParser as _HTMLParser
        html_unescape = _HTMLParser().unescape
    except:
        def html_unescape(s):
            return s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")


def _all_variants(title):
    if not title:
        return []

    results = []
    title_clean = html_unescape(title)

    for name in ('get', 'geturl', 'getsearch', 'movie', 'tv'):
        try:
            func = getattr(cleantitle, name)
            value = func(title_clean)
            if value:
                results.append(value)
        except:
            pass

    try:
        value = cleantitle.get(re.sub(r'\s*&\s*', ' ', title_clean))
        if value:
            results.append(value)
    except:
        pass

    return list(set([item for item in results if item]))


def _titles_match(search_variants, scraped_title):
    scraped_variants = _all_variants(scraped_title)
    if log_utils:
        logger.info('AniWorld - Match check: search=%s | scraped=%s' % (search_variants, scraped_variants))

    for query_variant in search_variants:
        for scraped_variant in scraped_variants:
            if query_variant and scraped_variant and (query_variant in scraped_variant or scraped_variant in query_variant):
                return True
    return False


class source:
    def __init__(self):
        self.priority = 4
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = '/ajax/seriesSearch?keyword='
        self.sources = []
        self.logged_in = False

        if log_utils:
            logger.info('AniWorld - Init: %s' % self.base_link)

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        if int(season or 0) == 0 and getattr(self, 'mediatype', None) != 'tvshow':
            return self.sources

        try:
            search_variants = []
            for title in titles:
                if title:
                    search_variants.extend(_all_variants(title))
            search_variants = list(set([item for item in search_variants if item]))

            if log_utils:
                logger.info('AniWorld - Search: S%02dE%02d | variants: %s' % (int(season or 0), int(episode or 0), search_variants))

            login, password = self._getLogin()
            if login and password:
                self._do_login(login, password)

            matches = []
            for title in titles:
                if not title:
                    continue
                links = self._search_title(title)
                for href, series_title in links:
                    if _titles_match(search_variants, series_title):
                        matches.append({'source': href})
                        if log_utils:
                            logger.info('AniWorld - Match: %s | title: %s' % (href, series_title))
                        break
                if matches:
                    break

            if not matches:
                return self.sources

            for item in matches:
                self.run2(item['source'], year, season=season, episode=episode, hostDict=hostDict, imdb=imdb)

        except Exception as e:
            if log_utils:
                logger.info('AniWorld - Error: %s' % str(e))
            return self.sources

        return self.sources

    def _search_title(self, title):
        try:
            try:
                from urllib import quote
            except:
                from urllib.parse import quote

            try:
                search_term = quote(title)
            except:
                search_term = quote(title.encode('utf-8'))

            search_url = urljoin(self.base_link, self.search_link + search_term)
            if log_utils:
                logger.info('AniWorld - Search URL: %s' % search_url)

            request = cRequestHandler(search_url)
            request.addHeaderEntry('User-Agent', 'Mozilla/5.0')
            request.addHeaderEntry('Accept', 'application/json, text/javascript, */*; q=0.01')
            request.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
            payload = request.request()
            return self._parse_search_results(payload)
        except Exception as e:
            if log_utils:
                logger.info('AniWorld - Search error: %s' % str(e))
            return []

    def _parse_search_results(self, payload):
        links = []
        if not payload:
            return links

        try:
            data = json.loads(payload)
            if not isinstance(data, list):
                return links

            for item in data:
                try:
                    if not isinstance(item, dict):
                        continue
                    slug = html_unescape(item.get('link') or '').strip().strip('/')
                    title = html_unescape(item.get('name') or '').strip()
                    if not slug or not title:
                        continue
                    href = '/anime/stream/' + slug
                    links.append((href, title))
                    if log_utils:
                        logger.info('AniWorld - Result: href="%s" title="%s"' % (href, title))
                except Exception as e:
                    if log_utils:
                        logger.info('AniWorld - Parse entry error: %s' % str(e))
        except Exception as e:
            if log_utils:
                logger.info('AniWorld - Parse error: %s' % str(e))

        return links

    def run2(self, url, year, season=0, episode=0, hostDict=None, imdb=None):
        try:
            url = url[:-1] if url.endswith('/') else url
            if 'staffel' in url:
                url = re.findall('(.*?)staffel', url)[0].rstrip('/')

            episode_url = '%s/staffel-%d/episode-%d' % (url, int(season), int(episode))
            full_url = urljoin(self.base_link, episode_url)

            if log_utils:
                logger.info('AniWorld - Episode: %s' % full_url)

            html = self._request_page(full_url)

            if self._should_find_matching_episode(html, season):
                mapped_episode = self._find_matching_episode_page(
                    url,
                    season,
                    episode,
                    getattr(self, 'episode_title', None),
                    getattr(self, 'episode_premiered', None),
                    full_url
                )
                if mapped_episode:
                    full_url, html = mapped_episode
                    if log_utils:
                        logger.info('AniWorld - Episode title/date fallback: %s' % full_url)

            if not html:
                return self.sources

            if imdb:
                imdb_links = dom_parser.parse_dom(html, 'a', attrs={'class': 'imdb-link'}, req='href')
                if imdb_links:
                    found_imdb = imdb_links[0].attrs.get('data-imdb', '')
                    if found_imdb and found_imdb != imdb:
                        return self.sources

            matches = self._parse_stream_link_buttons(html)
            if not matches:
                return self.sources

            if log_utils:
                logger.info('AniWorld - Found %d links' % len(matches))

            self.episode_referer = full_url

            for link_html in matches:
                try:
                    link_id = self._attr(link_html, 'data-link-id')
                    play_url = self._attr(link_html, 'data-link-target')
                    language_id = self._attr(link_html, 'data-lang-key')
                    provider_name = self._hoster_from_link(link_html)
                    language, language_info = self._language_from_id(language_id)

                    if not link_id or not play_url or not provider_name or not language:
                        continue

                    redirect_url = urljoin(self.base_link, play_url)
                    protected_hoster = provider_name.lower() in ('doodstream', 'dood')

                    self.sources.append({
                        'source': provider_name,
                        'quality': 'SD',
                        'language': language,
                        'url': redirect_url,
                        'info': language_info,
                        'direct': False,
                        'debridonly': False,
                        'priority': self.priority,
                        'prioHoster': 999 if protected_hoster else 0
                    })

                    if log_utils:
                        logger.info('AniWorld - Added: %s | %s' % (provider_name, language_info))

                except Exception as e:
                    if log_utils:
                        logger.info('AniWorld - Link error: %s' % str(e))

            if log_utils:
                logger.info('AniWorld - Total: %d sources' % len(self.sources))

            return self.sources

        except Exception as e:
            if log_utils:
                logger.info('AniWorld - Fatal: %s' % str(e))
            return self.sources

    def _request_page(self, full_url):
        try:
            request = cRequestHandler(full_url)
            request.addHeaderEntry('User-Agent', 'Mozilla/5.0')
            return request.request() or ''
        except Exception as e:
            if log_utils:
                logger.info('AniWorld - Request error: %s' % str(e))
            return ''

    @staticmethod
    def _parse_stream_link_buttons(html):
        pattern = r'<li\b(?=[^>]*data-link-id=)[^>]*>.*?</li>'
        return re.findall(pattern, html or '', re.DOTALL | re.IGNORECASE)

    def _has_stream_links(self, html):
        return bool(self._parse_stream_link_buttons(html))

    def _should_find_matching_episode(self, html, season):
        if int(season or 0) == 0:
            return False

        episode_title = getattr(self, 'episode_title', None)
        episode_premiered = getattr(self, 'episode_premiered', None)
        if not episode_title and not episode_premiered:
            return False

        if not self._has_stream_links(html):
            return True

        page_title = self._extract_episode_title(html)
        if episode_title and page_title:
            if not self._episode_titles_match(episode_title, page_title):
                if log_utils:
                    logger.info('AniWorld - Direct episode title mismatch: request=%s | page=%s' % (episode_title, page_title))
                return True
            return False

        return False

    def _find_matching_episode_page(self, series_url, season=0, episode=0, episode_title=None, episode_premiered=None, direct_url=''):
        if not episode_title and not episode_premiered:
            return None

        season_numbers = self._available_seasons(series_url, season)
        direct_path = self._normalise_episode_path(direct_url)
        date_matches = []

        if log_utils:
            logger.info('AniWorld - Episode fallback check: seasons=%s | S%02dE%02d | title=%s | premiered=%s' % (
                season_numbers,
                int(season or 0),
                int(episode or 0),
                episode_title,
                episode_premiered
            ))

        for season_number in season_numbers:
            season_url = '%s/staffel-%d' % (series_url.rstrip('/'), int(season_number))
            season_html = self._request_page(urljoin(self.base_link, season_url))
            if not season_html:
                continue

            episode_links = self._parse_episode_links(season_html, series_url, season_number)
            if not episode_links:
                continue

            for episode_url in episode_links:
                if self._normalise_episode_path(episode_url) == direct_path:
                    continue

                full_url = urljoin(self.base_link, episode_url)
                html = self._request_page(full_url)
                if not html or not self._has_stream_links(html):
                    continue

                page_title = self._extract_episode_title(html)
                if episode_title and self._episode_titles_match(episode_title, page_title):
                    return full_url, html

                page_date = self._extract_publish_date(html)
                if episode_premiered and self._dates_match(episode_premiered, page_date):
                    if episode_title:
                        date_matches.append((full_url, html))
                    else:
                        return full_url, html

        if episode_title and len(date_matches) == 1:
            return date_matches[0]

        return None

    def _available_seasons(self, series_url, requested_season=0):
        seasons = set()
        base_html = self._request_page(urljoin(self.base_link, series_url.rstrip('/')))
        for value in re.findall(r'/staffel-(\d+)(?:/|["\'])', base_html or '', re.IGNORECASE):
            try:
                seasons.add(int(value))
            except:
                pass

        requested = int(requested_season or 0)
        if requested:
            seasons.add(requested)
            for value in range(max(0, requested - 1), requested + 5):
                seasons.add(value)
        seasons.add(0)

        if not seasons:
            seasons = set(range(0, 9))

        return sorted([season for season in seasons if 0 <= season <= 30])

    def _parse_episode_links(self, html, series_url, season_number):
        links = []
        seen = set()
        series_slug = self._series_slug(series_url)
        patterns = [
            r'href="([^"]*/staffel-%d/episode-\d+)"' % int(season_number),
            r"href='([^']*/staffel-%d/episode-\d+)'" % int(season_number),
        ]

        for pattern in patterns:
            for href in re.findall(pattern, html or '', re.IGNORECASE):
                href = html_unescape(href).strip()
                if href.startswith('http'):
                    href = re.sub(r'^https?://[^/]+', '', href)
                if not href.startswith('/'):
                    href = '/' + href
                if series_slug and series_slug not in href:
                    continue
                if href in seen:
                    continue
                seen.add(href)
                links.append(href)

        def episode_number(value):
            match = re.search(r'/episode-(\d+)', value)
            return int(match.group(1)) if match else 0

        return sorted(links, key=episode_number)

    @staticmethod
    def _series_slug(series_url):
        try:
            value = series_url.rstrip('/')
            if '/staffel-' in value:
                value = value.split('/staffel-', 1)[0]
            return value.rstrip('/').split('/')[-1]
        except:
            return ''

    @staticmethod
    def _normalise_episode_path(url):
        if not url:
            return ''
        try:
            value = html_unescape(str(url))
            value = re.sub(r'^https?://[^/]+', '', value)
            if not value.startswith('/'):
                value = '/' + value
            return value.rstrip('/')
        except:
            return ''

    def _extract_episode_title(self, html):
        patterns = [
            r'<h2[^>]*>\s*S\d+E\d+\s*:\s*(.*?)</h2>',
            r'<title>[^<]*S\d+E\d+\s*:\s*(.*?)\s*\|',
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'][^"\']*S\d+E\d+\s*:\s*([^"\']+)',
            r'<h2[^>]*>\s*(.*?)\s*(?:\[\s*Episode\s+\d+\s*\])?\s*</h2>',
        ]
        for pattern in patterns:
            match = re.search(pattern, html or '', re.IGNORECASE | re.DOTALL)
            if match:
                title = re.sub(r'<[^>]+>', ' ', match.group(1))
                title = re.sub(r'\[\s*Episode\s+\d+\s*\]', ' ', title, flags=re.IGNORECASE)
                title = html_unescape(title)
                title = re.sub(r'\s+', ' ', title).strip()
                if title:
                    return title
        return ''

    def _episode_titles_match(self, requested, candidate):
        requested_variants = self._episode_title_variants(requested)
        candidate_variants = self._episode_title_variants(candidate)

        if log_utils:
            logger.info('AniWorld - Episode title match: request=%s | candidate=%s' % (
                requested_variants,
                candidate_variants
            ))

        for req in requested_variants:
            for cand in candidate_variants:
                if len(req) >= 6 and len(cand) >= 6 and (req in cand or cand in req):
                    return True
        return False

    @staticmethod
    def _episode_title_variants(title):
        if not title:
            return []

        value = html_unescape(title)
        value = value.replace(u'\u2018', "'").replace(u'\u2019', "'").replace(u'\u201c', '"').replace(u'\u201d', '"')
        parts = [value]
        parts.extend(re.findall(r'\(([^)]+)\)', value))
        parts.append(re.sub(r'\([^)]*\)', ' ', value))

        variants = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            try:
                clean = cleantitle.get(part)
                if clean:
                    variants.append(clean)
            except:
                pass

            ascii_part = part.lower()
            replacements = [
                (u'\xe4', 'ae'), (u'\xf6', 'oe'), (u'\xfc', 'ue'),
                (u'\xdf', 'ss'), (u'\xe9', 'e'), (u'\xe8', 'e'),
            ]
            for source, target in replacements:
                ascii_part = ascii_part.replace(source, target)
            ascii_part = re.sub(r'[^a-z0-9]+', '', ascii_part)
            if ascii_part:
                variants.append(ascii_part)

        return list(set([variant for variant in variants if variant]))

    @staticmethod
    def _extract_publish_date(html):
        month_chars = r'A-Za-z\xc4\xd6\xdc\xe4\xf6\xfc\xdf'
        match = re.search(
            r'Ver(?:&ouml;|\xf6)ffentlicht(?:\s+bei\s+uns)?:\s*(?:[A-Za-z\xc4\xd6\xdc\xe4\xf6\xfc\xdf]+,\s*)?(\d{1,2}\.\d{1,2}\.\d{4})',
            html or '',
            re.IGNORECASE
        )
        if not match:
            return None

        value = html_unescape(match.group(1)).strip()
        try:
            parsed = datetime.datetime.strptime(value, '%d.%m.%Y').date()
            if parsed.year <= 1970:
                return None
            return parsed
        except:
            pass
        return None

    @staticmethod
    def _dates_match(requested, candidate):
        if not requested or not candidate:
            return False
        try:
            requested_date = datetime.datetime.strptime(str(requested)[:10], '%Y-%m-%d').date()
        except:
            return False
        try:
            return abs((requested_date - candidate).days) <= 2
        except:
            return False

    @staticmethod
    def _attr(html, name):
        match = re.search(r'%s=["\']([^"\']*)["\']' % re.escape(name), html, re.IGNORECASE)
        return html_unescape(match.group(1)).strip() if match else ''

    @staticmethod
    def _hoster_from_link(html):
        patterns = [
            r'<h4[^>]*>\s*([^<]+)\s*</h4>',
            r'title=["\']Hoster\s+([^"\']+)["\']',
            r'class=["\'][^"\']*\bicon\s+([A-Za-z0-9._ -]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html or '', re.IGNORECASE | re.DOTALL)
            if match:
                value = re.sub(r'<[^>]+>', ' ', match.group(1))
                value = html_unescape(value)
                value = re.sub(r'\s+', ' ', value).strip()
                if value:
                    return value
        return ''

    @staticmethod
    def _language_from_id(language_id):
        language_id = str(language_id or '').strip()
        if language_id == '1':
            return 'de', 'Deutsch'
        if language_id == '2':
            return 'en', 'Englisch'
        if language_id == '3':
            return 'en', 'Ger-Sub'
        return '', ''

    def _is_aniworld_url(self, url):
        try:
            parsed = urlparse(str(url).split('|', 1)[0])
            host = (parsed.netloc or '').split(':', 1)[0].lower()
            domains = set([SITE_DOMAIN, (self.domain or SITE_DOMAIN).lower()])
            return host in domains or any(host.endswith('.' + domain) for domain in domains)
        except:
            return False

    def _is_internal_redirect_url(self, url):
        try:
            parsed = urlparse(str(url).split('|', 1)[0])
            return self._is_aniworld_url(url) and parsed.path.startswith('/redirect/')
        except:
            return False

    def _external_redirect_target(self, base_url, location):
        if not location:
            return None
        try:
            target = urljoin(base_url, html_unescape(location).replace('\\/', '/'))
            if target and not self._is_aniworld_url(target):
                return target
        except:
            pass
        return None

    def _resolve_http_redirect(self, url, referer):
        try:
            import requests
            requests.packages.urllib3.disable_warnings()

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': referer,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            response = requests.get(url, headers=headers, allow_redirects=False, verify=False, timeout=10)
            if response.status_code in (301, 302, 303, 307, 308):
                target = self._external_redirect_target(response.url, response.headers.get('Location'))
                if target:
                    if log_utils:
                        logger.info('AniWorld - Resolved redirect location: %s' % target[:80])
                    return target
        except:
            pass
        return None

    def resolve(self, url):
        try:
            if log_utils:
                logger.info('AniWorld - Resolving: %s' % url[:80])

            referer = getattr(self, 'episode_referer', self.base_link)
            internal_redirect = self._is_internal_redirect_url(url)

            redirect_url = self._resolve_http_redirect(url, referer)
            if redirect_url:
                return redirect_url

            try:
                request = cRequestHandler(url, caching=False, ignoreErrors=True)
                request.addHeaderEntry('User-Agent', 'Mozilla/5.0')
                request.addHeaderEntry('Referer', referer)
                request.request()
                final_url = request.getRealUrl()
                if final_url and final_url != url:
                    if log_utils:
                        logger.info('AniWorld - Resolved via cRequestHandler: %s' % final_url[:80])
                    return final_url
            except:
                pass

            if getSetting('bypassDNSlock', 'false') != 'true':
                try:
                    import requests
                    requests.packages.urllib3.disable_warnings()
                    session = requests.Session()
                    session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': referer,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                    })
                    response = session.get(url, allow_redirects=True, verify=False, timeout=10)
                    final_url = response.url
                    if final_url and final_url != url and len(final_url) > 20:
                        if log_utils:
                            logger.info('AniWorld - Resolved to: %s' % final_url[:80])
                        return final_url
                except:
                    pass

            if internal_redirect:
                if log_utils:
                    logger.info('AniWorld - Internal redirect unresolved, skipping source')
                return None

            return url

        except Exception as e:
            if log_utils:
                logger.info('AniWorld - Resolve error: %s' % str(e))
            return None if self._is_internal_redirect_url(url) else url

    @staticmethod
    def _getLogin():
        login, password = provider_logins.get_credentials(SITE_IDENTIFIER)
        if not login or not password:
            return '', ''
        return login, password

    def _do_login(self, login, password):
        try:
            if log_utils:
                logger.info('AniWorld - Optional login configured')

            login_url = self.base_link + '/login'
            request = cRequestHandler(login_url)
            request.addHeaderEntry('User-Agent', 'Mozilla/5.0')
            login_page = request.request()

            form_fields = {}
            input_pattern = r'<input[^>]*name=["\']([^"\']+)["\'][^>]*(?:value=["\']([^"\']*)["\'])?[^>]*>'
            for match in re.finditer(input_pattern, login_page or '', re.IGNORECASE):
                name = match.group(1)
                value = match.group(2) if match.group(2) else ''
                if name.lower() not in ['email', 'password']:
                    form_fields[name] = value

            request = cRequestHandler(login_url)
            request.addHeaderEntry('User-Agent', 'Mozilla/5.0')
            request.addHeaderEntry('Content-Type', 'application/x-www-form-urlencoded')
            request.addHeaderEntry('Referer', login_url)
            request.addHeaderEntry('Origin', self.base_link)

            for field_name, field_value in form_fields.items():
                request.addParameters(field_name, field_value)

            request.addParameters('email', login)
            request.addParameters('password', password)

            response = request.request()
            self.logged_in = bool(response and ('logout' in response.lower() or 'abmelden' in response.lower()))
            return self.logged_in
        except Exception as e:
            if log_utils:
                logger.info('AniWorld - Login error: %s' % str(e))
            self.logged_in = False
            return False
