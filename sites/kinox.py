# -*- coding: UTF-8 -*-
from resources.lib.utils import isBlockedHoster
import json
import re
import time
import requests
from scrapers.modules.tools import cParser
from resources.lib.requestHandler import cRequestHandler
from resources.lib.control import urlparse, quote_plus, urljoin, parse_qs, getSetting, setSetting
from scrapers.modules import cleantitle, dom_parser, source_utils
SITE_IDENTIFIER = 'kinox'
SITE_DOMAIN = 'www12.kinoz.to'
SITE_NAME = SITE_IDENTIFIER.upper()
class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
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
                resp = requests.get(url)
                url = resp.url
                if resp.status_code == 200:
                    r = dom_parser.parse_dom(resp.text, 'meta', attrs={'name': 'keywords'}, req='content')
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
    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        url = ''
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
                r = dom_parser.parse_dom(sHtmlContent, 'table', attrs={'id': 'RsltTableStatic'})
                r = dom_parser.parse_dom(r, 'tr')
                r = [(dom_parser.parse_dom(i, 'a', req='href'), dom_parser.parse_dom(i, 'img', attrs={'alt': 'language'}, req='src'), dom_parser.parse_dom(i, 'span')) for i in r]
                r = [(i[0][0].attrs['href'], i[0][0].content, i[1][0].attrs['src'], i[2][0].content) for i in r if i[0] and i[1]]
                if season:
                    r = [(i[0], i[1], re.findall(r'.+?(\d+)\.', i[2]), i[3]) for i in r]
                    if r == []: continue
                else:
                    r = [(i[0], i[1], re.findall(r'.+?(\d+)\.', i[2]), i[3]) for i in r if i[3] == str(year)]
                    if r == []: continue
                r = [(i[0], i[1], i[2][0] if len(i[2]) > 0 else '0', i[3]) for i in r]
                r = sorted(r, key=lambda i: int(i[2]))
                r = [i[0] for i in r if i[2] in ['1', '15'] and cleantitle.get(i[1]) in t]
                if len(r) == 0:
                    continue
                else:
                    url = urljoin(self.base_link,r[0])
                    break
            except:
                pass

        try:
            if not url:
                return sources
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
                        if url: self.sources.append({'source': hoster, 'quality': 'SD', 'language': 'de', 'url': url, 'direct': True, 'prioHoster': prioHoster, 'info': 'Mirror ' + str(x+1)})
                except:
                    pass
            return self.sources
        except:
            return self.sources
    def resolve(self, url):
        return url

