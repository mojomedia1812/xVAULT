# -*- coding: UTF-8 -*-
import re, random, base64, ast, binascii, json, requests, string
from resources.lib.control import quote_plus, unquote_plus, infoDialog, urlparse, getSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib import pyaes
from binascii import unhexlify
from scrapers.modules import dom_parser, source_utils, cleantitle
from scrapers.modules.tools import cParser, cUtil
from resources.lib import log_utils
import re
import resolveurl as resolver
from resources.lib.control import urljoin
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser, source_utils
from resources.lib.control import getSetting
import xbmcgui
SITE_IDENTIFIER = 'kinoger'
SITE_DOMAIN = 'kinoger.com'
SITE_NAME = SITE_IDENTIFIER.upper()
from resolveurl.plugins import voesx

DOOD_DOMAINS = ('dood.sbs', 'dood.re', 'dood.cx', 'dood.la', 'dood.so', 'dood.pm', 'dood.to', 'dood.watch')

def _rewrite_dood(url):
    for d in DOOD_DOMAINS:
        if d in url.lower():
            url = url.replace(d, 'veev.to')
    return url

def extract_media_id_from_kinoger(kinoger_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36",
        "Referer": "https://kinoger.ru/"
    }
    try:
        response = requests.get(kinoger_url, headers=headers, timeout=15)
        html = response.text
        patterns = [
            r'https?://[^/]+/e/([a-zA-Z0-9]{8,12})',
            r'voe\.sx/e/([a-zA-Z0-9]{8,12})',
            r'/([a-zA-Z0-9]{8,12})["\']'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for media_id in matches:
                if len(media_id) >= 8 and media_id.isalnum():
                    return media_id
        return None
    except Exception:
        return None

def get_voe_stream_from_kinoger(kinoger_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://kinoger.ru/"
    }
    try:
        media_id = extract_media_id_from_kinoger(kinoger_url)
        if media_id:
            resolver = voesx.VoeResolver()
            stream_url = resolver.get_media_url('voe.sx', media_id)
            return stream_url
        return None
    except Exception as e:
        xbmc.log(f"Fehler: {str(e)}", xbmc.LOGERROR)
        return None

class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search = self.base_link + '/index.php?do=search&subaction=search&search_start=1&full_search=0&result_from=1&titleonly=3&story=%s'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        sources = []
        items = []
        url = ''
        try:
            t = [cleantitle.get(i) for i in titles if i]
            years = [str(year), str(year + 1)] if season == 0 else ['']
            for title in titles:
                try:
                    sUrl = self.search % title
                    oRequest = cRequestHandler(sUrl)
                    oRequest.removeBreakLines(False)
                    oRequest.removeNewLines(False)
                    oRequest.cacheTime = 60 * 60 * 12
                    sHtmlContent = oRequest.request()

                    search_results = dom_parser.parse_dom(sHtmlContent, 'div', attrs={'class': 'title'})
                    search_results = dom_parser.parse_dom(search_results, 'a')
                    search_results = [(i.attrs['href'], i.content) for i in search_results]
                    search_results = [(i[0], re.findall(r'(.*?)\((\d+)', i[1])[0]) for i in search_results]

                    if season > 0:
                        for x in range(0, len(search_results)):
                            title = cleantitle.get(search_results[x][1][0])
                            if 'staffel' in title and any(k in title for k in t):
                                url = search_results[x][0]
                    else:
                        for x in range(0, len(search_results)):
                            title = cleantitle.get(search_results[x][1][0])
                            if any(k in title for k in t) and search_results[x][1][1] in years:
                                url = search_results[x][0]
                                break
                    if url != '': break
                except:
                    pass

            if url == '': return sources

            oRequest = cRequestHandler(url)
            oRequest.cacheTime = 60 * 60 * 12
            sHtmlContent = oRequest.request()
            quali = re.findall('title="Stream.(.+?)"', sHtmlContent)
            links = re.findall(r'.show.+?,(\[\[.+?\]\])', sHtmlContent)
            if len(links) == 0: return sources

            if season > 0 and episode > 0:
                season = season - 1
                episode = episode - 1

            for i in range(0, len(links)):
                direct = True
                pw = ast.literal_eval(links[i])
                url = (pw[season][episode]).strip()
                valid, host = source_utils.is_host_valid(url, hostDict)
                if valid: direct = False
                quality = quali[i]
                if quality == '':
                    quality = 'SD'
                elif quality == 'HD':
                    quality = '720p'
                elif quality == 'HD+':
                    quality = '1080p'
                elif '2160' in quality or '4K' in quality:
                    quality = '4K'
                elif '1440' in quality or '2K' in quality:
                    quality = '1440p'
                elif '480' in quality:
                    quality = '480p'
                elif '360' in quality:
                    quality = '360p'
                items.append({'source': host, 'quality': quality, 'url': url, 'direct': direct})

            headers = '&Accept-Language=de%2Cen-US%3Bq%3D0.7%2Cen%3Bq%3D0.3&Accept=%2A%2F%2A&User-Agent=Mozilla%2F5.0+%28Windows+NT+10.0%3B+Win64%3B+x64%3B+rv%3A99.0%29+Gecko%2F20100101+Firefox%2F99.0'
            for item in items:
                try:
                    if 'kinoger.re' in item['source']: continue
                    elif 'p2p' in item['source'] or 'P2P' in item['source']: continue
                    elif 'kinoger.ru' in item['source']:
                        sUrl = item['url']
                        stream_url = get_voe_stream_from_kinoger(sUrl)
                        if stream_url:
                            sources.append({'source': item['source'], 'quality': item['quality'], 'language': 'de', 'url': stream_url, 'direct': False})
                    elif 'kinoger.be' in item['source']:
                        sUrl = item['url']
                        oRequest = cRequestHandler(sUrl, caching=False, ignoreErrors=True)
                        oRequest.addHeaderEntry('Referer', 'https://kinoger.com/')
                        sHtmlContent = oRequest.request()
                        isMatch, packed = cParser.parseSingleResult(sHtmlContent, r'(eval\s*\(function.*?)</script>')
                        if isMatch:
                            from resources.lib import jsunpacker
                            sHtmlContent = jsunpacker.unpack(packed)
                        isMatch, hUrl = cParser.parseSingleResult(sHtmlContent, 'sources.*?file.*?(http[^"]+)')
                        if isMatch:
                            hUrl = hUrl.replace('\\', '')
                            oRequest = cRequestHandler(hUrl, caching=False, ignoreErrors=True)
                            oRequest.addHeaderEntry('Referer', 'https://kinoger.be/')
                            oRequest.addHeaderEntry('Origin', 'https://kinoger.be')
                            oRequest.removeNewLines(False)
                            sHtmlContent = oRequest.request()
                            if 'CF-DDOS-GUARD aktiv' in sHtmlContent:
                                continue
                            else:
                                pattern = r'RESOLUTION=.*?x(\d+).*?\n(index[^\n]+)'
                                isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                        if isMatch:
                            for sQuality, sUrl in aResult:
                                sUrl = (hUrl.split('video')[0].strip() + sUrl.strip())
                                sUrl = sUrl + '|Origin=https%3A%2F%2Fkinoger.be&Referer=https%3A%2F%2Fkinoger.be%2F' + headers
                                sources.append({'source': item['source'], 'quality': sQuality, 'language': 'de', 'url': sUrl, 'direct': True})
                    else:
                        url = _rewrite_dood(item['url'])
                        sources.append({'source': item['source'], 'quality': item['quality'], 'language': 'de', 'url': url, 'direct': False})

                except:
                    continue

            if len(sources) == 0:
                log_utils.log('Kinoger: kein Provider - %s ' % titles[0], log_utils.LOGINFO)
            else:
                for source in sources:
                    if source not in self.sources: self.sources.append(source)
                return self.sources
        except:
            return sources

    def resolve(self, url):
        try:
            return url
        except:
            return

    def _quali(self, q):
        if '720-' in q: return '720p'
        elif '1080-' in q: return '1080p'
        else: return 'SD'

    def _quality(self, q):
        hl = q.split('x')
        h = int(hl[0])
        l = int(hl[1])
        if h >= 1920: return '1080p'
        elif l >= 720 or h >= 1080: return '720p'
        else: return 'SD'

    def decodeStr(self, text):
        ergebnis = ''
        k = text[-1]
        t0, t1 = self.keys(k)
        text = text[:-1]
        for i in range(len(text)):
            for ii in range(len(t0)):
                if text[i] in t0[ii]:
                    ergebnis = ergebnis + t1[ii]
                elif text[i] in t1[ii]:
                    ergebnis = ergebnis + t0[ii]
        return unquote_plus(base64.b64decode(ergebnis[::-1] + '==').decode())

    def encodeUrl(self, e):
        r = 0,
        n = ''
        t = 1
        a = (random.randint(2, 9))
        t0, t1 = self.keys(str(a))
        t = a + 5
        for r in range(len(e)):
            n += self.toString(ord(e[r]), t)
            n += '!'
        n = base64.b64encode(n[:-1].encode()).decode().replace('=', '')
        e = ''
        for i in range(len(n)):
            for ii in range(len(t0)):
                if n[i] in t0[ii]:
                    e = e + t1[ii]
                elif n[i] in t1[ii]:
                    e = e + t0[ii]
        return self.encodeStr(e + str(a))

    def encodeStr(self, text):
        ergebnis = ''
        k = str(random.randint(2, 7))
        t0, t1 = self.keys(k)
        text = quote_plus(text)
        text = base64.b64encode(text.encode())
        text = text.decode().replace('=', '')[::-1]
        for i in range(len(text)):
            for ii in range(len(t0)):
                if text[i] in t0[ii]:
                    ergebnis = ergebnis + t1[ii]
                elif text[i] in t1[ii]:
                    ergebnis = ergebnis + t0[ii]
        return ergebnis + k

    def toString(self, number, base):
        string = "0123456789abcdefghijklmnopqrstuvwxyz"
        if number < base:
            return string[number]
        else:
            return self.toString(number // base, base) + string[number % base]

    def keys(self, s):
        if s == '1':
            return ('54A80Ibc3VBdefWGTSFg1X7hEYNijZU', 'kQl2mCnDoMpOq9rHsPt6uLvawRxJyKz')
        if s == '2':
            return ('4YMHUe5OFZ7L2PEJ8fgKAh1RGiIj0kV', 'aTlNmCn3oBpDqSr9sbtWu6vcwdxXyQz')
        elif s == '3':
            return ('AN4YZVHTJEOeLS2fGaFghiKWjQMbIkl', 'Xmc1d3nCo7p5qBrUsDt9u8vRw6x0yPz')
        elif s == '4':
            return ('V6YD2ZNWaTefXgObhS3UcRAP4dIiJjK', 'k7l5mLnCoEpMqGrBsFtQuHv1w0x9y8z')
        elif s == '5':
            return ('OGAFaN985MDHTbYW7ceQfdIgZhJiXj3', 'kSl6mRn2oCpKqErPsUt1u0v4wLxByVz')
        elif s == '6':
            return ('cZXK8O3BS5NRedFPfLAg2U6hIiDj7VT', 'k9lQmJnWoGp1q0rCsatHuYvbw4xMyEz')
        elif s == '7':
            return ('UZQXTPHcVS7deEfWDgRMLh9iIa1Y0j2', 'klb3m8nOoBpNqKr5s6tJuAvCwGxFy4z')
        elif s == '8':
            return ('AZI4WCcKOdNJGF3YEa2eHfgb8hMiLjD', 'kUlPmBnSoVp5q7r6s9t1uTv0wQxRyXz')
        elif s == '9':
            return ('OWZYcP3adUNSbeCfJVghTQDRIiKjBkG', 'X5lMmFnAoLp1q7r6s0tHu2vEw9x4y8z')
        else:
            return ('', '')

    def aes(self, txt):
        import base64
        from resources.lib import pyaes
        from binascii import unhexlify
        key = unhexlify('0123456789abcdef0123456789abcdef')
        iv = unhexlify('abcdef9876543210abcdef9876543210')
        aes = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(key, iv))
        return base64.b64encode(aes.feed(txt) + aes.feed()).decode()

    def check_302(self, url, headers):
        try:
            user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0'
            host = urlparse(url).netloc
            headers.update({'User-Agent': user_agent, 'Host': host, 'Range': 'bytes=0-',
                            'Connection': 'keep-alive',
                            'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5'})
            r = requests.get(url, allow_redirects=False, headers=headers, timeout=7)
            if 300 <= r.status_code < 400: return r.headers['Location']
            if 400 <= r.status_code: return
            return url
        except:
            return

    def get_embedurl(self, host, media_id):
        def makeid(length):
            t = string.ascii_letters + string.digits
            return ''.join([random.choice(t) for _ in range(length)])

        x = '{0}||{1}||{2}||streamsb'.format(makeid(12), media_id, makeid(12))
        c1 = binascii.hexlify(x.encode('utf8')).decode('utf8')
        x = '7Vd5jIEF2lKy||nuewwgxb1qs'
        c2 = binascii.hexlify(x.encode('utf8')).decode('utf8')
        return 'https://{0}/{1}7/{2}'.format(host, c2, c1)
