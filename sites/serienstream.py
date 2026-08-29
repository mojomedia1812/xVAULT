# -*- coding: utf-8 -*-
import re
import sys
import datetime
from urllib.parse import urlparse
from resources.lib.control import getSetting, urljoin, setSetting
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser
from resources.lib.utils import isBlockedHoster
from resources.lib.tools import logger, cParser


SITE_IDENTIFIER = 'serienstream'
SITE_DOMAIN = 'serienstream.to'
SITE_NAME = 'SerienStream'
log_utils = True
LEGACY_DOMAINS = set(['.'.join(('s', 'to')), 'www.' + '.'.join(('s', 'to'))])

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
        if (self.domain or '').lower() in LEGACY_DOMAINS:
            self.domain = SITE_DOMAIN
            try:
                setSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
            except:
                pass

        self.base_link = 'https://' + self.domain
        self.search_link = '/suche?term='

        self.sources = []

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

            if log_utils:
                logger.info('SerienStream - Searching without credentials')

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

            if self._should_find_matching_episode(sHtmlContent, season):
                mapped_episode = self._find_matching_episode_page(
                    url,
                    season,
                    episode,
                    getattr(self, 'episode_title', None),
                    getattr(self, 'episode_premiered', None),
                    full_url
                )
                if mapped_episode:
                    full_url, sHtmlContent = mapped_episode
                    if log_utils:
                        logger.info('SerienStream - Episode title/date fallback: %s' % full_url)

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

                    protected_hoster = provider_name.lower() in ('doodstream', 'dood')
                    self.sources.append({
                        'source': provider_name,
                        'quality': quality,
                        'language': language,
                        'url': redirect_url,
                        'info': language_info,
                        'direct': False,
                        'debridonly': False,
                        'priority': self.priority,
                        'prioHoster': 999 if protected_hoster else 0
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
                    logger.info('SerienStream - Direct episode title mismatch: request=%s | page=%s' % (episode_title, page_title))
                return True
            return False

        page_date = self._extract_publish_date(html)
        if episode_premiered and page_date and not self._dates_match(episode_premiered, page_date):
            if log_utils:
                logger.info('SerienStream - Direct episode date mismatch: request=%s | page=%s' % (episode_premiered, page_date))
            return True

        return False

    def _find_matching_episode_page(self, series_url, season=0, episode=0, episode_title=None, episode_premiered=None, direct_url=''):
        if not episode_title and not episode_premiered:
            return None

        season_numbers = self._available_seasons(series_url, season)

        if log_utils:
            logger.info('SerienStream - Episode fallback check: seasons=%s | S%02dE%02d | title=%s | premiered=%s' % (
                season_numbers,
                int(season or 0),
                int(episode or 0),
                episode_title,
                episode_premiered
            ))

        direct_path = self._normalise_episode_path(direct_url)
        date_matches = []
        for season_number in season_numbers:
            season_url = '%s/staffel-%d' % (series_url.rstrip('/'), int(season_number))
            season_full_url = urljoin(self.base_link, season_url)

            season_html = self._request_page(season_full_url)
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
            if log_utils:
                logger.info('SerienStream - Unique episode date fallback: %s' % date_matches[0][0])
            return date_matches[0]
        if episode_title and len(date_matches) > 1 and log_utils:
            logger.info('SerienStream - Episode date fallback ignored because %d candidates share %s' % (
                len(date_matches),
                episode_premiered
            ))

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

        return sorted([season for season in seasons if 0 <= season <= 15])

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
            value = value.replace('/stream/', '/')
            return value.rstrip('/')
        except:
            return ''

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
            logger.info('SerienStream - Episode title match: request=%s | candidate=%s' % (
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

    def _is_serienstream_url(self, url):
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
            return self._is_serienstream_url(url) and parsed.path.rstrip('/') == '/r'
        except:
            return False

    @staticmethod
    def _is_frame_bridge(html):
        if not html:
            return False
        text = str(html)
        return 'frameBridge' in text and 'window.parent.postMessage' in text

    def _external_redirect_target(self, base_url, location):
        if not location:
            return None
        try:
            target = urljoin(base_url, html_unescape(location).replace('\\/', '/'))
            if target and not self._is_serienstream_url(target):
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
                        logger.info('SerienStream - Resolved redirect location: %s' % target[:80])
                    return target
        except:
            pass
        return None

    def resolve(self, url):
        try:
            if log_utils:
                logger.info('SerienStream - Resolving: %s' % url[:80])

            referer = getattr(self, 'episode_referer', self.base_link)
            internal_redirect = self._is_internal_redirect_url(url)
            bridge_seen = False

            redirect_url = self._resolve_http_redirect(url, referer)
            if redirect_url:
                return redirect_url

            try:
                oRequest = cRequestHandler(url, caching=False, ignoreErrors=True)
                oRequest.addHeaderEntry('User-Agent', 'Mozilla/5.0')
                oRequest.addHeaderEntry('Referer', referer)
                response_html = oRequest.request()
                final_url = oRequest.getRealUrl()

                if final_url and final_url != url:
                    if log_utils:
                        logger.info('SerienStream - Resolved via cRequestHandler: %s' % final_url[:80])
                    return final_url
                if self._is_frame_bridge(response_html):
                    bridge_seen = True
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

                    if log_utils:
                        logger.info('SerienStream - Resolved to: %s' % final_url[:80])

                    if final_url and final_url != url and len(final_url) > 20:
                        return final_url
                    if self._is_frame_bridge(response.text):
                        bridge_seen = True

                except:
                    pass

            if bridge_seen:
                if log_utils:
                    logger.info('SerienStream - Frame bridge detected, no playable redirect available')
                return None
            if internal_redirect:
                if log_utils:
                    logger.info('SerienStream - Internal redirect unresolved, skipping source')
                return None

            if log_utils:
                logger.info('SerienStream - Could not resolve, returning original URL')
            return url

        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Resolve error: %s' % str(e))
            return None if self._is_internal_redirect_url(url) else url
