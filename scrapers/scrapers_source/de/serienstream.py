# -*- coding: utf-8 -*-
import re
import sys
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
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)

        if getSetting('bypassDNSlock') != 'true':
            self.base_link = 'https://' + self.domain
        else:
            self.base_link = 'http://186.2.175.5'
        self.search_link = '/suche?term='

        self.sources = []
        self.logged_in = False
        self.credentials_checked = False

        if log_utils:
            logger.info('SerienStream - Init: %s' % self.base_link)

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        if season == 0:
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

            oRequest = cRequestHandler(full_url)
            oRequest.addHeaderEntry('User-Agent', 'Mozilla/5.0')
            sHtmlContent = oRequest.request()

            if len(sHtmlContent) == 0:
                return self.sources

            if imdb:
                a = dom_parser.parse_dom(sHtmlContent, 'a', attrs={'class': 'imdb-link'}, req='href')
                if a:
                    foundImdb = a[0].attrs.get("data-imdb", '')
                    if foundImdb and not foundImdb == imdb:
                        return

            pattern = r'data-link-id="([^"]+)"[^>]*data-play-url="([^"]+)"[^>]*data-provider-name="([^"]+)"[^>]*data-language-id="([^"]+)"'
            matches = re.findall(pattern, sHtmlContent, re.DOTALL | re.IGNORECASE)

            if not matches:
                return self.sources

            if log_utils:
                logger.info('SerienStream - Found %d links' % len(matches))

            self.episode_referer = full_url

            for link_id, play_url, provider_name, language_id in matches:
                try:
                    if language_id != '1':
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
                        'language': 'de',
                        'url': redirect_url,
                        'info': '',
                        'direct': False,
                        'debridonly': False,
                        'priority': self.priority,
                        'prioHoster': 0
                    })

                    if log_utils:
                        logger.info('SerienStream - Added: %s' % provider_name)

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
