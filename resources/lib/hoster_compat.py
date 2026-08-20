import ast
import json
import re

from six.moves import urllib_parse

from resources.lib import log_utils


VOE_ROTATION_DOMAINS = [
    'johnbeyondnation.com',
    'jeanprofessorcentral.com',
    'juliewomanwish.com',
    'garylargeavailable.com',
    'jennifereconomicgive.com',
    'pamelachangemission.com',
    'ellenpoliticalfollow.com',
    'caseyimpactstation.com',
    'matthewhotelscience.com',
    'jessicachoosemake.com',
    'stevenfamilyedge.com',
    'kinoger.ru',
]

STREAMIX_DOMAINS = [
    'viewdara.com',
    'thebesthosterv.com',
    'kinoger.pw',
]

PLAYMATE_DOMAINS = [
    'playmate.to',
]

FIRESTREAM_DOMAINS = [
    'firestream.to',
]

KINOGER_DOMAINS = [
    'kinoger.embed4me.vip',
    'kinoger.seekplays.pro',
]

KINOGER_FILELIONS_DOMAINS = [
    'kinoger.be',
]

VEEV_DOMAINS = [
    'veev.pro',
]

EXTRA_RESOLVER_DOMAINS = sorted(set(
    VOE_ROTATION_DOMAINS +
    STREAMIX_DOMAINS +
    PLAYMATE_DOMAINS +
    FIRESTREAM_DOMAINS +
    KINOGER_DOMAINS +
    KINOGER_FILELIONS_DOMAINS +
    VEEV_DOMAINS
))


def extra_domains():
    return list(EXTRA_RESOLVER_DOMAINS)


def is_supported_host(host):
    host = _clean_host(host)
    return host in EXTRA_RESOLVER_DOMAINS


def display_name(host):
    host = _clean_host(host)
    if host in VOE_ROTATION_DOMAINS:
        return 'VOE'
    if host in STREAMIX_DOMAINS:
        return 'Streamix'
    if host in PLAYMATE_DOMAINS:
        return 'Playmate'
    if host in FIRESTREAM_DOMAINS:
        return 'FireStream'
    if host in KINOGER_DOMAINS:
        return 'KinoGer'
    if host in KINOGER_FILELIONS_DOMAINS:
        return 'FileLions'
    if host in VEEV_DOMAINS:
        return 'Veev'
    return host


def resolve(url):
    host, media_id = _match_firestream(url)
    if host and media_id:
        return _resolve_existing_plugin('firestream', 'FireStreamResolver', host, media_id)

    host, media_id = _match_streamix(url)
    if host and media_id:
        return _resolve_existing_plugin('streamix', 'StreamixResolver', host, media_id)

    host, media_id = _match_kinoger(url)
    if host and media_id:
        return _resolve_existing_plugin('kinoger', 'KinoGerResolver', host, media_id)

    host, media_id = _match_kinoger_filelions(url)
    if host and media_id:
        return _resolve_kinoger_filelions(host, media_id)

    host, media_id = _match_voe(url)
    if host and media_id:
        return _resolve_existing_plugin('voesx', 'VoeResolver', host, media_id)

    host, media_id = _match_veev(url)
    if host and media_id:
        return _resolve_existing_plugin('veev', 'VeevResolver', host, media_id)

    host, media_id = _match_playmate(url)
    if host and media_id:
        return _resolve_playmate(host, media_id)

    return None


def _resolve_existing_plugin(module_name, class_name, host, media_id):
    try:
        module = __import__('resolveurl.plugins.%s' % module_name, fromlist=[class_name])
        resolver = getattr(module, class_name)()
        result = resolver.get_media_url(host, media_id)
        if result:
            log_utils.log(
                'Hoster-Kompatibilitaet aufgeloest: %s / %s' % (display_name(host), host),
                log_utils.LOGINFO
            )
        return result
    except Exception as exc:
        log_utils.log(
            'Hoster-Kompatibilitaet fehlgeschlagen: %s / %s / %s' % (display_name(host), host, str(exc)),
            log_utils.LOGWARNING
        )
        return None


def _resolve_playmate(host, media_id):
    try:
        import requests
        from resources.lib.requestHandler import cRequestHandler

        api_url = 'https://%s/api/s' % host
        referer = 'https://%s/' % host
        headers = {
            'User-Agent': cRequestHandler.RandomUA(),
            'Referer': referer,
        }
        response = requests.post(
            api_url,
            data={'c': media_id, 'd': 'web'},
            headers=headers,
            timeout=12
        )
        data = response.json() if hasattr(response, 'json') else json.loads(response.text or '{}')
        stream_url = data.get('sx')
        if not stream_url:
            return None
        stream_headers = urllib_parse.urlencode(headers)
        log_utils.log('Hoster-Kompatibilitaet aufgeloest: Playmate / %s' % host, log_utils.LOGINFO)
        return '%s|%s' % (stream_url, stream_headers)
    except Exception as exc:
        log_utils.log('Playmate-Kompatibilitaet fehlgeschlagen: %s' % str(exc), log_utils.LOGWARNING)
        return None


def _resolve_kinoger_filelions(host, media_id):
    try:
        import requests
        from resources.lib.requestHandler import cRequestHandler

        if '$$' in media_id:
            media_id, referer = media_id.split('$$', 1)
            referer = urllib_parse.urljoin(referer, '/')
        else:
            referer = 'https://kinoger.to/'

        web_url = 'https://%s/%s' % (host, media_id.lstrip('/'))
        headers = {
            'User-Agent': cRequestHandler.RandomUA(),
            'Referer': referer,
        }
        response = requests.get(web_url, headers=headers, timeout=12)
        html = response.text or ''
        try:
            from resolveurl.lib import helpers
            html += helpers.get_packed_data(html)
        except:
            helpers = None

        links = re.search(r'var\s*links\s*=\s*([^;]+)', html)
        if links:
            links = ast.literal_eval(links.group(1))
            source = links.get('hls2') or links.get('hls3') or links.get('hls4')
            if source:
                if source.startswith('/'):
                    source = urllib_parse.urljoin(web_url, source)
                stream_headers = {
                    'User-Agent': headers['User-Agent'],
                    'Referer': urllib_parse.urljoin(web_url, '/'),
                    'Origin': urllib_parse.urljoin(web_url, '/')[:-1],
                    'verifypeer': 'false',
                }
                log_utils.log('Hoster-Kompatibilitaet aufgeloest: FileLions / %s' % host, log_utils.LOGINFO)
                return '%s|%s' % (source, urllib_parse.urlencode(stream_headers))

        fallback_media_id = '%s$$%s' % (media_id, referer)
        return _resolve_existing_plugin('filelions', 'FileLionsResolver', host, fallback_media_id)
    except Exception as exc:
        log_utils.log('KinoGer/FileLions-Kompatibilitaet fehlgeschlagen: %s' % str(exc), log_utils.LOGWARNING)
        return None


def _match_firestream(url):
    return _match(url, r'(?://|\.)(firestream\.to)/(?:e|v)/([0-9A-Za-z_-]+)')


def _match_streamix(url):
    domains = '|'.join(re.escape(domain) for domain in STREAMIX_DOMAINS)
    return _match(url, r'(?://|\.)((?:%s))/(?:e|v)/([0-9A-Za-z]+)' % domains)


def _match_kinoger(url):
    domains = '|'.join(re.escape(domain) for domain in KINOGER_DOMAINS)
    return _match(url, r'(?://|\.)((?:%s))/(?:#|api/v1/video\?id=)([0-9A-Za-z]+)' % domains)


def _match_kinoger_filelions(url):
    host, media_id = _match(url, r'(?://|\.)(kinoger\.be)/((?:s|v|f|d|e|embed|file|download)/[0-9A-Za-z$:/.]+(?:\$\$https?://[^|]+)?)')
    if host and media_id:
        return host, media_id
    clean_url = str(url or '').split('|', 1)[0]
    parts = clean_url.split('$$', 1)
    host, media_id = _match(parts[0], r'(?://|\.)(kinoger\.be)/((?:s|v|f|d|e|embed|file|download)/[0-9A-Za-z$:/.]+)')
    if host and media_id and len(parts) > 1:
        return host, '%s$$%s' % (media_id, parts[1])
    return host, media_id


def _match_voe(url):
    domains = '|'.join(re.escape(domain) for domain in VOE_ROTATION_DOMAINS)
    return _match(url, r'(?://|\.)((?:%s))/(?:e/)?([0-9A-Za-z]+)' % domains)


def _match_veev(url):
    domains = '|'.join(re.escape(domain) for domain in VEEV_DOMAINS)
    return _match(url, r'(?://|\.)((?:%s))/(?:e|d)/([0-9A-Za-z]+)' % domains)


def _match_playmate(url):
    return _match(url, r'(?://|\.)(playmate\.to)/(?:watch|embed|e|v)/([0-9A-Za-z]+)')


def _match(url, pattern):
    try:
        clean_url = str(url or '').split('|', 1)[0]
        match = re.search(pattern, clean_url, re.I)
        if not match:
            return None, None
        return _clean_host(match.group(1)), match.group(2)
    except:
        return None, None


def _clean_host(host):
    host = str(host or '').strip().lower()
    if host.startswith('www.'):
        host = host[4:]
    return host
