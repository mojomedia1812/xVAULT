# -*- coding: UTF-8 -*-
from resources.lib.utils import isBlockedHoster
import json
import re
import time
from resources.lib.requestHandler import cRequestHandler
from resources.lib.control import urlparse, quote_plus, urljoin, parse_qs, getSetting, setSetting
from scrapers.modules import cleantitle, dom_parser, source_utils
SITE_IDENTIFIER = 'kinox'
SITE_DOMAIN = 'www12.kinoz.to'
SITE_NAME = SITE_IDENTIFIER.upper()
LANGUAGE_MAP = {
    '1': ('de', 'Deutsch'),
    '2': ('en', 'Englisch'),
    '15': ('multi', 'Deutsch/Englisch')
}

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de', 'en']
        self.domains, self.base_link = self.getdomain()
        self.search_link = self.base_link +'/Search.html?q=%s'
        self.get_links_epi = '/aGET/MirrorByEpisode/?Addr=%s&SeriesID=%s&Season=%s&Episode=%s'
        self.mirror_link = '/aGET/Mirror/%s&Hoster=%s&Mirror=%s'
        self.checkHoster = False if getSetting('provider.kinox.checkHoster') == 'false' else True
        self.sources = []

    def getdomain(self, check=False):
        if getSetting('kinox.base_link') and check == False: return [getSetting('provider.kinox.domain')], getSetting('kinox.base_link')
        domains = ['kinox.PUB', 'kinox.fan','kinox.FUN', 'kinox.CLICK', 'kinox.AM', 'kinoS.TO', 'kinox.DIGITAL', 'KinoX.to', 'kinos.to', 'kinox.EXPRESS',
                   'kinox.SG', 'kinox.sh', 'kinox.GRATIS', 'kinox.WTF', 'kinox.tv', 'kinox.BZ', 'kinox.MOBI', 'kinox.TV', 'kinox.to', 'www12.kinos.to',
                   'kinox.LOL', 'kinox.FYI', 'kinox.CLOUD', 'kinox.DIRECT', 'kinox.SH', 'kinox.CLUB', 'kinoz.TO', 'ww8.kinox.to']
        for i in range(18, 22):
            domain = 'www%s.kinoz.to' % i
            domains.insert(0, domain)
        for domain in domains:
            try:
                url = 'http://%s' % domain
                request = cRequestHandler(url, caching=False, ignoreErrors=True)
                html = request.request()
                url = request.getRealUrl() or url
                if str(request.getStatus()) in ['200', '301']:
                    r = dom_parser.parse_dom(html, 'meta', attrs={'name': 'keywords'}, req='content')
                    if r and 'kinox.to' in r[0].attrs.get('content').lower():
                        setSetting('provider.kinox.domain', urlparse(url).netloc)
                        setSetting('kinox.base_link', url[:-1])
                        if check:
                            self.domains = [urlparse(url).netloc]
                            self.base_link = url[:-1]
                            return self.domains, self.base_link
                        return  [urlparse(url).netloc], url[:-1]
            except:
                pass

    def _languageId(self, value):
        value = source_utils.replaceHTMLCodes(str(value or ''))
        match = re.search(r'/lng/(\d+)\.', value)
        if not match:
            match = re.search(r'(?:^|/)(\d+)\.(?:png|gif|jpg|jpeg)', value, re.IGNORECASE)
        return match.group(1) if match else '0'

    def _languageFromId(self, language_id):
        return LANGUAGE_MAP.get(str(language_id), ('unknown', ''))

    def _wantedLanguage(self, language_id):
        setting = getSetting('hosts.language') or '0'
        language_id = str(language_id)
        if setting == '1':
            return language_id in ['1', '15']
        if setting == '2':
            return language_id in ['2', '15']
        if setting == '3':
            return language_id == '15'
        return language_id in ['1', '2', '15']

    def _languageImgFromBlock(self, block):
        for img in re.findall(r'<img[^>]+>', block, flags=re.I):
            if re.search(r'alt=["\']language["\']', img, flags=re.I):
                return self._languageId(img)
        return '0'

    def _parseSearchResults(self, html, season, year):
        results = []

        try:
            tables = dom_parser.parse_dom(html, 'table', attrs={'id': 'RsltTableStatic'})
            rows = dom_parser.parse_dom(tables, 'tr')
            rows = [(dom_parser.parse_dom(i, 'a', req='href'), dom_parser.parse_dom(i, 'img', attrs={'alt': 'language'}, req='src'), dom_parser.parse_dom(i, 'span')) for i in rows]
            rows = [(i[0][0].attrs['href'], i[0][0].content, self._languageId(i[1][0].attrs['src']), i[2][0].content if i[2] else '') for i in rows if i[0] and i[1]]
            for href, title, language_id, result_year in rows:
                if season or str(result_year) == str(year):
                    results.append((href, title, language_id, result_year))
        except:
            pass

        try:
            blocks = re.findall(r'(<div[^>]+onclick=["\']location\.href=["\'][^"\']*/Stream/[^"\']+["\'];?["\'][^>]*>.*?)(?=<div[^>]+onclick=["\']location\.href=["\'][^"\']*/Stream/|</ul>\s*</div>)', html, flags=re.S | re.I)
            for block in blocks:
                href = re.search(r'href=["\']([^"\']*/Stream/[^"\']+)["\']', block, flags=re.I)
                if not href:
                    href = re.search(r'location\.href=["\']([^"\']*/Stream/[^"\']+)["\']', block, flags=re.I)
                title = re.search(r'<h1[^>]*>(.*?)</h1>', block, flags=re.S | re.I)
                if not title:
                    title = re.search(r'<a[^>]+title=["\']([^"\']+)["\']', block, flags=re.I)
                result_title = source_utils.replaceHTMLCodes(re.sub(r'<[^>]+>', ' ', title.group(1))).strip() if title else ''
                result_title = re.sub(r'\s+', ' ', result_title)
                text = re.sub(r'<[^>]+>', ' ', block)
                text = re.sub(r'\s+', ' ', source_utils.replaceHTMLCodes(text)).strip()
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', text)
                result_year = year_match.group(1) if year_match else ''
                language_id = self._languageImgFromBlock(block)
                if href and result_title:
                    if season or not result_year or str(result_year) == str(year):
                        results.append((href.group(1), result_title, language_id, result_year))
        except:
            pass

        unique = []
        seen = set()
        for href, title, language_id, result_year in results:
            key = (href, language_id)
            if key in seen:
                continue
            seen.add(key)
            unique.append((href, title, language_id, result_year))
        return unique

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        matches = []
        t = [cleantitle.get(i) for i in set(titles) if i]
        for title in titles:
            try:
                query = self.search_link % (quote_plus(title))
                oRequest = cRequestHandler(query)
                sHtmlContent = oRequest.request()
                if not sHtmlContent:
                    self.getdomain(True)
                    query = self.search_link % (quote_plus(title))
                    sHtmlContent = cRequestHandler(query).request()
                results = self._parseSearchResults(sHtmlContent, season, year)
                results = [i for i in results if cleantitle.get(i[1]) in t and self._wantedLanguage(i[2])]
                if len(results) == 0:
                    continue
                matches.extend(results)
                break
            except:
                pass

        unique_matches = []
        seen_urls = set()
        for item in matches:
            key = (item[0], item[2])
            if key in seen_urls:
                continue
            seen_urls.add(key)
            unique_matches.append(item)
        matches = unique_matches

        try:
            if not matches:
                return self.sources

            for href, result_title, language_id, result_year in matches:
                language, language_label = self._languageFromId(language_id)
                url = urljoin(self.base_link, href)
                oRequest = cRequestHandler(url)
                sHtmlContent = oRequest.request()
                if season and episode:
                    r = dom_parser.parse_dom(sHtmlContent, 'select', attrs={'id': 'SeasonSelection'}, req='rel')[0]
                    r = source_utils.replaceHTMLCodes(r.attrs['rel'])[1:]
                    r = parse_qs(r)
                    r = dict([(i, r[i][0]) if r[i] else (i, '') for i in r])
                    r = urljoin(self.base_link, self.get_links_epi % (r['Addr'], r['SeriesID'], season, episode))
                    oRequest = cRequestHandler(r)
                    sHtmlContent = oRequest.request()
                r = dom_parser.parse_dom(sHtmlContent, 'ul', attrs={'id': 'HosterList'})[0]
                r = dom_parser.parse_dom(r, 'li', attrs={'id': re.compile(r'Hoster_\d+')}, req='rel')
                r = [(source_utils.replaceHTMLCodes(i.attrs['rel']), i.content) for i in r if i[0] and i[1]]
                r = [(i[0], re.findall(r'class="Named"[^>]*>([^<]+).*?(\d+)/(\d+)', i[1])) for i in r]
                r = [(i[0], i[1][0][0].lower().rsplit('.', 1)[0], i[1][0][2]) for i in r if len(i[1]) > 0]
                for link, hoster, mirrors in r:
                    try:
                        u = parse_qs('&id=%s' % link)
                        u = dict([(x, u[x][0]) if u[x] else (x, '') for x in u])
                        for x in range(0, int(mirrors)):
                            tempLink = self.mirror_link % (u['id'], u['Hoster'], x + 1)
                            if season and episode: tempLink += "&Season=%s&Episode=%s" % (season, episode)
                            url = urljoin(self.base_link, tempLink)
                            oRequest = cRequestHandler(url)
                            sHtmlContent = oRequest.request()
                            if len(sHtmlContent) < 20:
                                time.sleep(1)  
                                oRequest = cRequestHandler(url)
                                sHtmlContent = oRequest.request()
                            r = json.loads(sHtmlContent)['Stream']
                            r = [(dom_parser.parse_dom(r, 'a', req='href'), dom_parser.parse_dom(r, 'iframe', req='src'))]
                            r = [i[0][0].attrs['href'] if i[0] else i[1][0].attrs['src'] for i in r if i[0] or i[1]][0]
                            if not r.startswith('http'): r = urljoin('https:', r)
                            isBlocked, hoster, url, prioHoster = isBlockedHoster(r)
                            if isBlocked: continue
                            info = 'Mirror ' + str(x+1)
                            if language_label:
                                info += ' | ' + language_label
                            if url: self.sources.append({'source': hoster, 'quality': 'SD', 'language': language, 'url': url, 'direct': True, 'prioHoster': prioHoster, 'info': info})
                    except:
                        pass
            return self.sources
        except:
            return self.sources
    def resolve(self, url):
        return url

