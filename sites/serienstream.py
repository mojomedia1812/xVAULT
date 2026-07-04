# -*- coding: utf-8 -*-
import re
import sys
import datetime
from resources.lib.control import getSetting, urljoin, setSetting
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser
from resources.lib.utils import isBlockedHoster
from resources.lib.tools import logger, cParser


SITE_IDENTIFIER = 'serienstream'
SITE_DOMAIN = 's.to'
SITE_NAME = 'SerienStream'
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

    try:
        v = cleantitle.get(title_clean)
        if v:
            results.append(v)
    except:
        pass

    try:
        v = cleantitle.geturl(title_clean)
        if v:
            results.append(v)
    except:
        pass

    try:
        v = cleantitle.getsearch(title_clean)
        if v:
            results.append(v)
    except:
        pass

    try:
        v = cleantitle.movie(title_clean)
        if v:
            results.append(v)
    except:
        pass

    try:
        v = cleantitle.tv(title_clean)
        if v:
            results.append(v)
    except:
        pass

    try:
        t2 = re.sub(r'\s*&\s*', ' ', title_clean)
        v = cleantitle.get(t2)
        if v:
            results.append(v)
    except:
        pass

    try:
        t3 = re.sub(r'\s*&\s*', ' ', title_clean)
        t3 = re.sub(r'\band\b', ' ', t3, flags=re.IGNORECASE)
        v = cleantitle.get(t3)
        if v:
            results.append(v)
    except:
        pass

    try:
        t4 = html_unescape(title)
        t4 = re.sub(r'\s*&\s*', ' ', t4)
        t4 = re.sub(r'\band\b', ' ', t4, flags=re.IGNORECASE)
        t4 = re.sub(r'[^a-z0-9]', '', t4.lower())
        if t4:
            results.append(t4)
    except:
        pass

    return list(set([r for r in results if r]))


def _titles_match(search_variants, scraped_title):
    scraped_variants = _all_variants(scraped_title)

    if log_utils:
        logger.info('SerienStream - Match check: search=%s | scraped=%s' % (search_variants, scraped_variants))

    for sv in scraped_variants:
        for qv in search_variants:
            if qv and sv and qv in sv:
                return True
    return False


class source:
    def __init__(self):
        self.priority = 4
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)

        self.base_link = 'https://' + self.domain
        self.search_link = '/suche?term='

        self.sources = []
        self.logged_in = False
        self.credentials_checked = False

        if log_utils:
            logger.info('SerienStream - Init: %s' % self.base_link)

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        if int(season or 0) == 0 and getattr(self, 'mediatype', None) != 'tvshow':
            return self.sources

        try:
            t = []
            for i in titles:
                if i:
                    t.extend(_all_variants(i))
            t = list(set([x for x in t if x]))

            if log_utils:
                logger.info('SerienStream - Search: S%02dE%02d | all title variants: %s' % (season, episode, t))

            login, password = self._getLogin()

            if not login or not password:
                if log_utils:
                    logger.info('SerienStream - No credentials, skipping scraper')

                if not self.credentials_checked:
                    self.credentials_checked = True
                    try:
                        import xbmcgui
                        xbmcgui.Dialog().ok(
                            'SerienStream',
                            'Keine Login-Daten in den Einstellungen eingetragen.\n\nBitte Email und Passwort fuer SerienStream eintragen.\nBis dahin wird SerienStream uebersprungen.'
                        )
                    except Exception as e:
                        if log_utils:
                            logger.info('SerienStream - Dialog error: %s' % str(e))

                return self.sources

            if log_utils:
                logger.info('SerienStream - Credentials found, attempting login')

            login_success = self._do_login(login, password)
            if not login_success:
                if log_utils:
                    logger.info('SerienStream - Login failed, but continuing anyway')

            aLinks = []

            if imdb:
                try:
                    try:
                        from urllib import quote
                    except:
                        from urllib.parse import quote

                    imdb_search_url = urljoin(self.base_link, self.search_link + quote(imdb))

                    if log_utils:
                        logger.info('SerienStream - IMDB search URL: %s' % imdb_search_url)

                    oRequest = cRequestHandler(imdb_search_url)
                    oRequest.addHeaderEntry('User-Agent', 'Mozilla/5.0')
                    sHtmlContent = oRequest.request()

                    links = self._parse_search_results(sHtmlContent)

                    if links:
                        if log_utils:
                            logger.info('SerienStream - IMDB search found %d results' % len(links))
                        href, series_title = links[0]
                        aLinks.append({'source': href})
                        if log_utils:
                            logger.info('SerienStream - IMDB match: %s | title: %s' % (href, series_title))

                except Exception as e:
                    if log_utils:
                        logger.info('SerienStream - IMDB search error: %s' % str(e))

            if not aLinks:
                if log_utils:
                    logger.info('SerienStream - No IMDB result, falling back to title search')

                for title in titles:
                    if not title:
                        continue

                    try:
                        try:
                            from urllib import quote
                        except:
                            from urllib.parse import quote

                        if isinstance(title, str):
                            try:
                                search_term = quote(title)
                            except:
                                search_term = quote(title.encode('utf-8'))
                        else:
                            search_term = quote(title)

                        search_url = urljoin(self.base_link, self.search_link + search_term)

                        if log_utils:
                            logger.info('SerienStream - Search URL: %s' % search_url)

                        oRequest = cRequestHandler(search_url)
                        oRequest.addHeaderEntry('User-Agent', 'Mozilla/5.0')
                        sHtmlContent = oRequest.request()

                        links = self._parse_search_results(sHtmlContent)

                        if links:
                            if log_utils:
                                logger.info('SerienStream - Found %d results' % len(links))

                            for href, series_title in links:
                                matched = False
                                for clean_title in t:
                                    try:
                                        if clean_title in cleantitle.get(series_title):
                                            matched = True
                                            break
                                    except:
                                        pass

                                if not matched:
                                    matched = _titles_match(t, series_title)

                                if matched:
                                    aLinks.append({'source': href})
                                    if log_utils:
                                        logger.info('SerienStream - Match: %s | title: %s' % (href, series_title))
                                    break

                        if aLinks:
                            break

                    except Exception as e:
                        if log_utils:
                            logger.info('SerienStream - Search error: %s' % str(e))
                        continue

            if len(aLinks) == 0:
                return self.sources

            for i in aLinks:
                url = i['source']
                self.run2(url, year, season=season, episode=episode, hostDict=hostDict, imdb=imdb)

        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Error: %s' % str(e))
            return self.sources

        return self.sources

    def _do_login(self, login, password):
        try:
            if log_utils:
                logger.info('SerienStream - Performing login...')

            URL_LOGIN = self.base_link + '/login'

            oRequest = cRequestHandler(URL_LOGIN)
            oRequest.addHeaderEntry('User-Agent', 'Mozilla/5.0')
            login_page = oRequest.request()

            form_fields = {}
            input_pattern = r'<input[^>]*name=["\']([^"\']+)["\'][^>]*(?:value=["\']([^"\']*)["\'])?[^>]*>'
            for match in re.finditer(input_pattern, login_page, re.IGNORECASE):
                name = match.group(1)
                value = match.group(2) if match.group(2) else ''
                if name.lower() not in ['email', 'password']:
                    form_fields[name] = value

            oRequest = cRequestHandler(URL_LOGIN)
            oRequest.addHeaderEntry('User-Agent', 'Mozilla/5.0')
            oRequest.addHeaderEntry('Content-Type', 'application/x-www-form-urlencoded')
            oRequest.addHeaderEntry('Referer', URL_LOGIN)
            oRequest.addHeaderEntry('Origin', self.base_link)

            for field_name, field_value in form_fields.items():
                oRequest.addParameters(field_name, field_value)

            oRequest.addParameters('email', login)
            oRequest.addParameters('password', password)

            login_response = oRequest.request()
            if not login_response or login_response in ['SEITE NICHT ERREICHBAR', 'CLOUDFLARE-SCHUTZ AKTIV', 'URL FEHLER', 'TIMEOUT', 'DDOS GUARD SCHUTZ']:
                self.logged_in = False
                return False

            if len(login_response) != len(login_page):
                if log_utils:
                    logger.info('SerienStream - Login successful')
                self.logged_in = True
                return True
            elif 'logout' in login_response.lower() or 'abmelden' in login_response.lower():
                if log_utils:
                    logger.info('SerienStream - Login successful')
                self.logged_in = True
                return True
            else:
                self.logged_in = False
                return False

        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Login error: %s' % str(e))
            self.logged_in = False
            return False

    def _parse_search_results(self, html):
        links = []

        try:
            patterns = [
                r'href="https?://[^/]+(/serie/[^"]+)"',
                r'href="(/serie/[^"]+)"',
            ]

            all_serie_hrefs = []
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                all_serie_hrefs.extend(matches)

            all_serie_hrefs = list(set(all_serie_hrefs))

            for href in all_serie_hrefs:
                try:
                    title = None

                    title_pattern = r'href="[^"]*' + re.escape(href) + r'"[^>]*title="([^"]+)"'
                    title_match = re.search(title_pattern, html, re.IGNORECASE)
                    if title_match:
                        title = title_match.group(1)

                    if not title:
                        context_pattern = r'href="[^"]*' + re.escape(href) + r'"[^>]*>(.{0,300}?)</a>'
                        context_match = re.search(context_pattern, html, re.IGNORECASE | re.DOTALL)
                        if context_match:
                            inner = re.sub(r'<[^>]+>', '', context_match.group(1)).strip()
                            if inner:
                                title = inner

                    if not title:
                        slug = href.rstrip('/').split('/')[-1]
                        title = slug.replace('-', ' ').title()

                    if title:
                        title = html_unescape(title)
                        title = re.sub(r'<[^>]+>', '', title).strip()

                        if log_utils:
                            logger.info('SerienStream - Result: href="%s" title="%s"' % (href, title))

                        links.append((href, title))

                except Exception as e:
                    if log_utils:
                        logger.info('SerienStream - Parse entry error: %s' % str(e))
                    pass

        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Parse error: %s' % str(e))

        return links

    def run2(self, url, year, season=0, episode=0, hostDict=None, imdb=None):
        try:
            url = url[:-1] if url.endswith('/') else url
            if "staffel" in url:
                url = re.findall("(.*?)staffel", url)[0]

            episode_url = '%s/staffel-%d/episode-%d' % (url, int(season), int(episode))
            full_url = urljoin(self.base_link, episode_url)

            if log_utils:
                logger.info('SerienStream - Episode: %s' % full_url)

            sHtmlContent = self._request_page(full_url)

            if not self._has_stream_links(sHtmlContent) and int(season) != 0:
                special = self._find_special_episode_page(
                    url,
                    getattr(self, 'episode_title', None),
                    getattr(self, 'episode_premiered', None)
                )
                if special:
                    full_url, sHtmlContent = special
                    if log_utils:
                        logger.info('SerienStream - Special fallback: %s' % full_url)

            if len(sHtmlContent) == 0:
                return self.sources

            if imdb:
                a = dom_parser.parse_dom(sHtmlContent, 'a', attrs={'class': 'imdb-link'}, req='href')
                if a:
                    foundImdb = a[0].attrs.get("data-imdb", '')
                    if foundImdb and not foundImdb == imdb:
                        return

            matches = self._parse_stream_link_buttons(sHtmlContent)

            if not matches:
                return self.sources

            if log_utils:
                logger.info('SerienStream - Found %d links' % len(matches))

            self.episode_referer = full_url

            for link_html in matches:
                try:
                    link_id = self._attr(link_html, 'data-link-id')
                    play_url = self._attr(link_html, 'data-play-url')
                    provider_name = self._attr(link_html, 'data-provider-name')
                    language_id = self._attr(link_html, 'data-language-id')
                    language_label = self._attr(link_html, 'data-language-label')
                    language, language_info = self._language_from_id(language_id, language_label)

                    if not link_id or not play_url or not provider_name or not language:
                        continue

                    redirect_url = urljoin(self.base_link, play_url)

                    quality = 'SD'
                    try:
                        quality_pattern = r'data-provider-name="' + re.escape(provider_name) + r'"[^>]*>(.*?)</button>'
                        quality_match = re.search(quality_pattern, sHtmlContent, re.DOTALL | re.IGNORECASE)
                        if quality_match and 'hd' in quality_match.group(1).lower():
                            quality = 'HD'
                    except:
                        pass

                    self.sources.append({
                        'source': provider_name,
                        'quality': quality,
                        'language': language,
                        'url': redirect_url,
                        'info': language_info,
                        'direct': False,
                        'debridonly': False,
                        'priority': self.priority,
                        'prioHoster': 0
                    })

                    if log_utils:
                        logger.info('SerienStream - Added: %s | %s' % (provider_name, language_info))

                except Exception as e:
                    if log_utils:
                        logger.info('SerienStream - Error: %s' % str(e))
                    continue

            if log_utils:
                logger.info('SerienStream - Total: %d sources' % len(self.sources))

            return self.sources

        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Fatal: %s' % str(e))
            return self.sources

    def _request_page(self, full_url):
        try:
            oRequest = cRequestHandler(full_url)
            oRequest.addHeaderEntry('User-Agent', 'Mozilla/5.0')
            return oRequest.request() or ''
        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Request error: %s' % str(e))
            return ''

    @staticmethod
    def _parse_stream_link_buttons(html):
        pattern = r'<[^>]+data-link-id="[^"]+"[^>]*>'
        return re.findall(pattern, html or '', re.DOTALL | re.IGNORECASE)

    def _has_stream_links(self, html):
        return bool(self._parse_stream_link_buttons(html))

    def _find_special_episode_page(self, series_url, episode_title=None, episode_premiered=None):
        if not episode_title and not episode_premiered:
            return None

        season_url = '%s/staffel-0' % series_url.rstrip('/')
        season_full_url = urljoin(self.base_link, season_url)

        if log_utils:
            logger.info('SerienStream - Special fallback check: %s | title=%s | premiered=%s' % (
                season_full_url,
                episode_title,
                episode_premiered
            ))

        season_html = self._request_page(season_full_url)
        if not season_html:
            return None

        episode_links = self._parse_episode_links(season_html, season_url)
        if not episode_links:
            return None

        for episode_url in episode_links:
            full_url = urljoin(self.base_link, episode_url)
            html = self._request_page(full_url)
            if not html or not self._has_stream_links(html):
                continue

            page_title = self._extract_episode_title(html)
            if episode_title and self._episode_titles_match(episode_title, page_title):
                return full_url, html

            page_date = self._extract_publish_date(html)
            if episode_premiered and self._dates_match(episode_premiered, page_date):
                return full_url, html

        return None

    def _parse_episode_links(self, html, season_url):
        links = []
        seen = set()
        season_prefix = season_url.rstrip('/')

        patterns = [
            r'href="([^"]*/staffel-0/episode-\d+)"',
            r"href='([^']*/staffel-0/episode-\d+)'",
        ]
        for pattern in patterns:
            for href in re.findall(pattern, html or '', re.IGNORECASE):
                href = html_unescape(href).strip()
                if href.startswith('http'):
                    href = re.sub(r'^https?://[^/]+', '', href)
                if not href.startswith('/'):
                    href = '/' + href
                if season_prefix not in href:
                    continue
                if href in seen:
                    continue
                seen.add(href)
                links.append(href)

        def episode_number(value):
            match = re.search(r'/episode-(\d+)', value)
            return int(match.group(1)) if match else 0

        return sorted(links, key=episode_number)

    def _extract_episode_title(self, html):
        patterns = [
            r'<h2[^>]*>\s*S\d+E\d+\s*:\s*(.*?)</h2>',
            r'<title>[^<]*S\d+E\d+\s*:\s*(.*?)\s*\|',
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'][^"\']*S\d+E\d+\s*:\s*([^"\']+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html or '', re.IGNORECASE | re.DOTALL)
            if match:
                title = re.sub(r'<[^>]+>', ' ', match.group(1))
                title = html_unescape(title)
                title = re.sub(r'\s+', ' ', title).strip()
                if title:
                    return title
        return ''

    def _episode_titles_match(self, requested, candidate):
        requested_variants = self._episode_title_variants(requested)
        candidate_variants = self._episode_title_variants(candidate)

        if log_utils:
            logger.info('SerienStream - Special title match: request=%s | candidate=%s' % (
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
            r'Ver(?:&ouml;|\xf6)ffentlicht\s+am\s+([' + month_chars + r']+\s+\d{1,2},\s+\d{4}|\d{1,2}\.\s*[' + month_chars + r']+\.?\s+\d{4}|\d{4}-\d{2}-\d{2})',
            html or '',
            re.IGNORECASE
        )
        if not match:
            return None

        value = html_unescape(match.group(1)).strip()
        months = {
            'january': 1, 'jan': 1, 'januar': 1,
            'february': 2, 'feb': 2, 'februar': 2,
            'march': 3, 'mar': 3, 'maerz': 3, u'm\xe4rz': 3,
            'april': 4, 'apr': 4,
            'may': 5, 'mai': 5,
            'june': 6, 'jun': 6, 'juni': 6,
            'july': 7, 'jul': 7, 'juli': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9,
            'october': 10, 'oct': 10, 'oktober': 10, 'okt': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12, 'dezember': 12, 'dez': 12,
        }

        iso_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', value)
        if iso_match:
            return datetime.date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))

        english_match = re.match(r'([' + month_chars + r']+)\s+(\d{1,2}),\s+(\d{4})', value)
        if english_match:
            month = months.get(english_match.group(1).lower().rstrip('.'))
            if month:
                return datetime.date(int(english_match.group(3)), month, int(english_match.group(2)))

        german_match = re.match(r'(\d{1,2})\.\s*([' + month_chars + r']+)\.?\s+(\d{4})', value)
        if german_match:
            month = months.get(german_match.group(2).lower().rstrip('.'))
            if month:
                return datetime.date(int(german_match.group(3)), month, int(german_match.group(1)))

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
        match = re.search(r'%s="([^"]*)"' % re.escape(name), html, re.IGNORECASE)
        return html_unescape(match.group(1)).strip() if match else ''

    @staticmethod
    def _language_from_id(language_id, label=''):
        language_label = (label or '').strip()
        normalized_label = language_label.lower()
        if language_id == '1' or 'deutsch' in normalized_label:
            return 'de', language_label or 'Deutsch'
        if language_id == '2' or 'englisch' in normalized_label or 'english' in normalized_label:
            return 'en', language_label or 'Englisch'
        if language_id == '3' or 'ger-sub' in normalized_label or 'sub' in normalized_label:
            return 'en', language_label or 'Ger-Sub'
        return '', language_label

    def resolve(self, url):
        try:
            if log_utils:
                logger.info('SerienStream - Resolving: %s' % url[:80])

            try:
                import requests
                requests.packages.urllib3.disable_warnings()

                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': getattr(self, 'episode_referer', self.base_link),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                })

                response = session.get(url, allow_redirects=True, verify=False, timeout=10)
                final_url = response.url

                if log_utils:
                    logger.info('SerienStream - Resolved to: %s' % final_url[:80])

                if final_url and final_url != url and len(final_url) > 20:
                    return final_url

            except:
                pass

            try:
                oRequest = cRequestHandler(url, ignoreErrors=True)
                oRequest.addHeaderEntry('User-Agent', 'Mozilla/5.0')
                oRequest.addHeaderEntry('Referer', getattr(self, 'episode_referer', self.base_link))
                oRequest.request()
                final_url = oRequest.getRealUrl()

                if final_url and final_url != url:
                    if log_utils:
                        logger.info('SerienStream - Resolved via cRequestHandler: %s' % final_url[:80])
                    return final_url
            except:
                pass

            if log_utils:
                logger.info('SerienStream - Could not resolve, returning original URL')
            return url

        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Resolve error: %s' % str(e))
            return url

    @staticmethod
    def _getLogin():
        login = ''
        password = ''

        try:
            from scrapers.modules.jsnprotect import cHelper
            login = cHelper.UserName
            password = cHelper.PassWord
            setSetting('serienstream.user', login)
            setSetting('serienstream.pass', password)
        except:
            login = getSetting(SITE_IDENTIFIER + '.user')
            password = getSetting(SITE_IDENTIFIER + '.pass')

        if not login or not password:
            return '', ''

        return login, password
