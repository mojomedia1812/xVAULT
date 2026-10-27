"""Radio Browser catalog and classification. No Kodi or playback dependencies."""
import json
import random
import re
import time
import unicodedata
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

SERVERS = ('de1.api.radio-browser.info', 'nl1.api.radio-browser.info', 'fi1.api.radio-browser.info')
PAGE_SIZE = 500
MAX_PAGES = 32
MAX_RESPONSE = 4 * 1024 * 1024
CATALOG_TTL = 6 * 3600
STALE_TTL = 48 * 3600
IDENTITY_TTL = 24 * 3600
IDENTITY_RETRY = 6 * 3600


class RadioError(Exception):
    pass


class Cancelled(RadioError):
    pass


def station_id(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise RadioError('Ungueltige Senderkennung')


def web_url(value):
    try:
        p = urlsplit(str(value or ''))
        return str(value) if p.scheme in ('http', 'https') and p.hostname and not p.username and not p.password else ''
    except ValueError:
        return ''


def eligible(row):
    return (isinstance(row, dict) and str(row.get('countrycode', '')).upper() == 'DE'
            and row.get('lastcheckok') == 1
            and bool(web_url(row.get('url_resolved') or row.get('url'))))


def number(value):
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        return 0


def normalized(value):
    value = unicodedata.normalize('NFKD', str(value or '').casefold())
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in value if not unicodedata.combining(c))).strip()


GENRES = (
    ('Dance & EDM', ('dance', 'edm', 'electro', 'electronic', 'electronica', 'dance classics', 'hands up')),
    ('House', ('house', 'deep house', 'tech house', 'progressive house')),
    ('Techno', ('techno', 'hardtechno', 'hardstyle', 'hardcore')),
    ('Trance', ('trance', 'psytrance', 'progressive trance', 'vocal trance')),
    ('Pop & Charts', ('pop', 'charts', 'top 40', 'top40', 'hits', 'hit radio', 'hot ac')),
    ('Rock & Alternative', ('rock', 'classic rock', 'alternative', 'indie', 'punk')),
    ('Metal', ('metal', 'heavy metal', 'hard rock')),
    ('Schlager & Volksmusik', ('schlager', 'volksmusik', 'deutscher schlager', 'partyschlager')),
    ('Oldies', ('oldies', '60s', '60er', '70s', '70er', 'goldies')),
    ('80er', ('80s', '80er', '1980s', 'eighties')),
    ('90er', ('90s', '90er', '1990s', 'eurodance', 'nineties')),
    ('2000er', ('00s', '00er', '2000s', '2000er', '2000')),
    ("Hip-Hop & R'n'B", ('hip hop', 'hiphop', 'rap', 'deutschrap', 'deutsch rap', 'rnb', 'r b', 'urban')),
    ('Jazz', ('jazz', 'smooth jazz', 'smoothjazz', 'swing')),
    ('Klassik', ('classical', 'klassik', 'classic', 'opera')),
    ('Chillout & Lounge', ('chillout', 'chill out', 'lounge', 'ambient', 'relax', 'easy listening', 'downtempo')),
    ('Disco, Funk & Soul', ('disco', 'funk', 'soul', 'motown')),
    ('Country', ('country', 'bluegrass', 'americana')),
    ('Reggae & Weltmusik', ('reggae', 'ska', 'world', 'world music', 'latin', 'salsa')),
    ('Nachrichten & Talk', ('news', 'nachrichten', 'talk', 'information', 'culture', 'kultur', 'politics')),
    ('Weihnachten', ('christmas', 'weihnachten', 'xmas')),
)


def genres(row):
    tags = {normalized(t) for t in str(row.get('tags', '')).split(',') if t.strip()}
    found = [label for label, words in GENRES if tags.intersection(words)]
    return found or ['Weitere Musikrichtungen']


# Only known brands are grouped; unknown stations are never assigned by fuzzy matching.
FAMILIES = (
    ('0N Radio', r'^0\s*n\b', ('0nradio.com',)),
    ('1A Radio', r'^1\s*a\b', ('1aradio.com',)),
    ('SUNSHINE LIVE', r'^sunshine\s*live\b', ('sunshine-live.de',)),
    ('ANTENNE BAYERN', r'^antenne bayern\b', ('antenne.de',)),
    ('ROCK ANTENNE', r'^rock antenne\b', ('rockantenne.de',)),
    ('RADIO BOB!', r'^(radio )?bob\b', ('radiobob.de',)),
    ('bigFM', r'^big\s*fm\b', ('bigfm.de',)),
    ('90s90s', r'^90s90s\b', ('90s90s.de',)),
    ('80s80s', r'^80s80s\b', ('80s80s.de',)),
    ('1LIVE', r'^1live\b', ()),
    ('NDR', r'^ndr\b', ()), ('WDR', r'^wdr\b', ()), ('SWR', r'^swr\b', ()),
    ('MDR', r'^mdr\b', ()), ('BAYERN / BR', r'^(bayern [1-5]|br klassik|br24|br puls)\b', ()),
    ('hr', r'^hr [1-4]\b', ()), ('rbb', r'^rbb\b', ()),
    ('RauteMusik', r'^raute\s*musik\b', ('rautemusik.fm',)),
    ('radio UNiCC', r'^radio unicc\b', ('radio-unicc.de',)),
    ('Euer Radio', r'^euer radio\b', ('euer-radio.de',)),
    ('Radio R', r'^radio r\b', ('radio-r.net',)),
    ('Nachklang FM', r'^nachklang\b', ('nachklang.fm',)),
    ('ENERGY', r'^energy\b', ('energy.de',)),
    ('RADIO REGENBOGEN', r'^radio regenbogen\b', ('regenbogen.de',)),
    ('HIT RADIO FFH', r'^(hit radio )?ffh\b', ('ffh.de',)),
)


def family(row):
    name = normalized(row.get('name'))
    # Keep compatibility with Kodi's older Python 3 releases.
    host = (urlsplit(web_url(row.get('homepage'))).hostname or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    for label, pattern, hosts in FAMILIES:
        if host in hosts or re.search(pattern, name):
            return label
    return ''


def clean_station(row):
    if not eligible(row):
        return None
    try:
        identifier = station_id(row.get('stationuuid'))
    except RadioError:
        return None
    return dict(id=identifier, name=str(row.get('name') or 'Unbenannter Sender').strip(),
                url=web_url(row.get('url_resolved') or row.get('url')),
                homepage=web_url(row.get('homepage')), icon=web_url(row.get('favicon')),
                tags=str(row.get('tags') or ''), genres=genres(row), family=family(row),
                votes=number(row.get('votes')), codec=str(row.get('codec') or '').upper(),
                bitrate=number(row.get('bitrate')), hls=row.get('hls') == 1,
                state=str(row.get('state') or ''), countrycode='DE',
                checked=str(row.get('lastcheckoktime_iso8601') or row.get('lastcheckoktime') or ''),
                country=str(row.get('country') or 'Deutschland'))


def program_key(row):
    name = re.sub(r'\b(?:mp3|aac\+?|ogg|opus|flac|\d+\s*(?:kbps|kbit/?s))\b', ' ', row['name'], flags=re.I)
    name = re.sub(r'\b(?:(?:low|high)\s+(?:quality|bitrate)|hq|lq)\b', ' ', name, flags=re.I)
    host = (urlsplit(row.get('homepage') or '').hostname or '').lower()
    return normalized(name), host[4:] if host.startswith('www.') else host


def stream_key(value):
    """Conservative URL identity: keep path case, slashes and all query parameters."""
    value = web_url(value)
    if not value:
        return ''
    try:
        parts = urlsplit(value)
        host = parts.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        if parts.port and (parts.scheme, parts.port) not in (('http', 80), ('https', 443)):
            host += ':' + str(parts.port)
        return urlunsplit((parts.scheme.lower(), host, parts.path or '/', parts.query, ''))
    except ValueError:
        return ''


def endpoint_key(value):
    """Regiocast adds per-listener analytics to a program-specific stream path.

    Ignore only these known analytics fields for identity, never for playback.
    Other providers, routing arguments and authorization parameters stay intact.
    """
    value = stream_key(value)
    if not value:
        return ''
    parts = urlsplit(value)
    if (parts.hostname.endswith('.streamabc.net')
            and re.fullmatch(r'/regc-[a-zA-Z0-9_-]+', parts.path)):
        tracking = {'sABC', 'aw_0_1st.playerid', 'amsparams'}
        query = parse_qsl(parts.query, keep_blank_values=True)
        if any(key in tracking for key, val in query):
            value = urlunsplit((parts.scheme, parts.netloc, parts.path,
                                urlencode([(key, val) for key, val in query if key not in tracking]), ''))
    return value


def family_program(station):
    """Protect named subchannels, including when API records have a wrong shared URL."""
    brand = normalized(station.get('family'))
    if not brand:
        return None
    name = program_key(station)[0]
    if name.startswith('radio '):
        name = name[6:]
    if name == brand or name.startswith(brand + ' '):
        name = name[len(brand):].strip()
    if name == 'radio':
        name = ''
    return brand, name


def cached_target(source, identities=None, now=None):
    record = (identities or {}).get(source, {})
    try:
        if record.get('ok') is True and 0 <= (now or time.time()) - float(record['checked']) < IDENTITY_TTL:
            return stream_key(record.get('target'))
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    return ''


def group_stations(rows, identities=None, now=None):
    stations, seen = [], set()
    for raw in rows:
        station = clean_station(raw)
        if not station or station['id'] in seen:
            continue
        seen.add(station['id'])
        station['stream_key'] = endpoint_key(cached_target(stream_key(station['url']), identities, now) or station['url'])
        stations.append(station)
    parents = list(range(len(stations)))
    hints = [{family_program(s)} - {None} for s in stations]

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def merge(left, right):
        left, right = root(left), root(right)
        if left == right:
            return
        # Check whole components: an unnamed alias must not bridge Rock and Dance.
        if hints[left] and hints[right] and hints[left] != hints[right]:
            return
        parents[right] = left
        hints[left] |= hints[right]

    names, streams = {}, {}
    for index, station in enumerate(stations):
        name_key = program_key(station)
        if name_key[1]:  # A missing operator/homepage is not proof of identity.
            if name_key in names:
                merge(names[name_key], index)
            else:
                names[name_key] = index
        key = station['stream_key']
        if key:
            # Keep conflicting components separate even if they share an API URL.
            for previous in streams.get(key, []):
                merge(previous, index)
            streams.setdefault(key, []).append(index)
    buckets = {}
    for index, station in enumerate(stations):
        buckets.setdefault(root(index), []).append(station)
    programs = []
    for variants in buckets.values():
        variants.sort(key=lambda s: (-s['votes'], -s['bitrate'], s['id']))
        program = dict(variants[0])
        program['variants'] = variants
        program['aliases'] = sorted({s['name'] for s in variants})
        program['genres'] = sorted({g for s in variants for g in s['genres']})
        program['tags'] = ','.join(sorted({t.strip() for s in variants for t in s['tags'].split(',') if t.strip()}))
        program['family'] = program['family'] or next((s['family'] for s in variants if s['family']), '')
        programs.append(program)
    return programs


def filter_stations(stations, genre='', sender_family='', query='', sort='votes'):
    query = normalized(query)
    result = [s for s in stations if (not genre or genre in s.get('genres', []))
              and (not sender_family or s.get('family') == sender_family)
              and (not query or query in normalized(' '.join(s.get('aliases') or [s['name']]) + ' ' + s.get('family', '') + ' ' + s.get('tags', '')))]
    if sort == 'name':
        return sorted(result, key=lambda s: (normalized(s['name']), -s['votes']))
    if sort == 'bitrate':
        return sorted(result, key=lambda s: (-max(v['bitrate'] for v in s['variants']), -s['votes'], normalized(s['name'])))
    return sorted(result, key=lambda s: (-s['votes'], normalized(s['name'])))


def stream_variants(station, preferred='auto'):
    variants = station.get('variants') or [station]
    def rank(s):
        match = s['codec'].startswith(preferred.upper()) if preferred in ('mp3', 'aac') else s['codec'] == 'MP3'
        return (not match, s.get('hls', False), -s['bitrate'], -s['votes'])
    result, targets = [], {}
    for variant in sorted(variants, key=rank):
        key = variant.get('stream_key') or stream_key(variant['url'])
        if key not in targets:
            candidate = dict(variant, api_aliases=[variant['id']])
            result.append(candidate)
            targets[key] = candidate
        elif variant['id'] not in targets[key]['api_aliases']:
            targets[key]['api_aliases'].append(variant['id'])
    return result


def identity_candidates(rows, identities=None, now=None):
    """Only probe plausible name aliases; never crawl all station streams."""
    now = now or time.time()
    groups = {}
    for raw in rows:
        station = clean_station(raw)
        if not station:
            continue
        name, operator = program_key(station)
        name = re.sub(r'^radio\s+|\s+radio$', '', name).strip()
        if not operator or not name:
            continue
        groups.setdefault((name, operator), []).append(station)
    pending = {}
    for variants in groups.values():
        # Exact names already group quality variants without doing any network I/O.
        if len({program_key(s) for s in variants}) < 2:
            continue
        if len({endpoint_key(cached_target(stream_key(s['url']), identities, now) or s['url']) for s in variants}) < 2:
            continue
        for station in variants:
            source = stream_key(station['url'])
            record = (identities or {}).get(source, {})
            try:
                ttl = IDENTITY_TTL if record.get('ok') is True else IDENTITY_RETRY
                if 0 <= now - float(record['checked']) < ttl:
                    continue
            except (KeyError, TypeError, ValueError, AttributeError):
                pass
            if source:
                pending[source] = max(station['votes'], pending.get(source, 0))
    return sorted(pending, key=lambda source: (-pending[source], source))


def probe_stream_url(source):
    """Bounded GET; Kodi still performs the actual audio decoding and playback."""
    if not web_url(source):
        raise RadioError('Ungültige Streamadresse')
    with requests.Session() as session:
        session.max_redirects = 5
        return _probe_response(session, source)


def _probe_response(session, source):
    with session.get(source, headers={'User-Agent': 'Kodi xVAULT Radio'}, timeout=(2, 4),
                     stream=True, allow_redirects=True) as response:
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').lower().split(';')[0]
        if content_type.startswith(('text/html', 'application/json')):
            raise RadioError('Streamserver liefert keine Audiodaten')
        block = next(response.iter_content(1024), b'')
        if not block or block.lstrip().lower().startswith((b'<!doctype html', b'<html')):
            raise RadioError('Stream ist leer oder liefert eine HTML-Seite')
        target = web_url(response.url)
        if not target:
            raise RadioError('Ungültige Streamadresse')
        return target


def refresh_identities(rows, identities, resolve=probe_stream_url, stopped=lambda: False, limit=6):
    updated = dict(identities)
    changed = False
    for source in identity_candidates(rows, updated)[:limit]:
        if stopped():
            break
        try:
            target = stream_key(resolve(source))
            if not target:
                raise RadioError('Ungültiges Streamziel')
            record = dict(target=target, checked=time.time(), ok=True)
        except (RadioError, requests.RequestException, ValueError):
            # A failed or expired observation must never be identity evidence.
            record = dict(checked=time.time(), ok=False)
        updated[source] = record
        changed = True
    return updated, changed


class Client:
    def __init__(self, version='local', transport=None):
        self.session = transport or requests.Session()
        self.headers = {'User-Agent': 'xVAULT/%s RadioBrowser' % version, 'Accept': 'application/json'}
        self.servers = list(SERVERS)
        random.shuffle(self.servers)
        self.discovered = False

    def _json(self, host, path, params=None, method='GET'):
        if not re.fullmatch(r'[a-z0-9-]+\.api\.radio-browser\.info', host):
            raise RadioError('Ungueltiger Radio-Browser-Server')
        with self.session.request(method, 'https://' + host + path, params=params,
                                  headers=self.headers, timeout=(3, 8), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise RadioError('Unerwartete Serverantwort')
            payload = bytearray()
            deadline = time.monotonic() + 15
            for block in response.iter_content(65536):
                payload.extend(block)
                if len(payload) > MAX_RESPONSE or time.monotonic() > deadline:
                    raise RadioError('Senderantwort ist zu gross')
            return json.loads(payload.decode('utf-8'))

    def discover(self):
        if self.discovered:
            return
        self.discovered = True
        try:
            servers = self._json(self.servers[0], '/json/servers')
            names = list(dict.fromkeys(s['name'] for s in servers if isinstance(s, dict)
                                      and re.fullmatch(r'[a-z0-9-]+\.api\.radio-browser\.info', str(s.get('name', '')))))
            random.shuffle(names)
            self.servers = names + [s for s in self.servers if s not in names]
        except (requests.RequestException, ValueError, TypeError, RadioError):
            pass

    def get(self, path, params=None):
        self.discover()
        for host in self.servers[:3]:
            try:
                return self._json(host, path, params)
            except (requests.RequestException, ValueError, TypeError, RadioError):
                continue
        raise RadioError('Radio Browser ist derzeit nicht erreichbar. Bitte spaeter erneut versuchen.')

    def catalog(self, cancelled=lambda: False, progress=lambda count: None):
        rows, identifiers = [], set()
        for page in range(MAX_PAGES):
            if cancelled():
                raise Cancelled('Laden abgebrochen')
            batch = self.get('/json/stations/search', dict(countrycode='DE',
                             hidebroken='true', order='name', reverse='false', limit=PAGE_SIZE, offset=page * PAGE_SIZE))
            if not isinstance(batch, list):
                raise RadioError('Ungueltige Senderliste')
            for row in batch:
                if isinstance(row, dict) and row.get('stationuuid') not in identifiers:
                    identifiers.add(row.get('stationuuid'))
                    rows.append(row)
            progress(len(rows))
            if len(batch) < PAGE_SIZE:
                return [row for row in rows if clean_station(row)]
        raise RadioError('Senderliste unvollstaendig; keine Teilliste gespeichert')

    def station(self, identifier):
        identifier = station_id(identifier)
        rows = self.get('/json/stations/byuuid/' + identifier)
        if not isinstance(rows, list):
            raise RadioError('Ungueltige Senderantwort')
        for raw in rows:
            station = clean_station(raw)
            if station and station['id'] == identifier:
                return station
        raise RadioError('Sender ist nicht mehr als deutscher und erreichbarer Sender gelistet.')

    def vote(self, identifier):
        identifier = station_id(identifier)
        self.discover()
        # A write is sent once only: a lost reply must not cause duplicate votes.
        try:
            result = self._json(self.servers[0], '/json/vote/' + identifier, method='POST')
        except (requests.RequestException, ValueError, TypeError, RadioError):
            raise RadioError('Abstimmung nicht bestaetigt. Es wurde nicht automatisch erneut abgestimmt.')
        if not isinstance(result, dict) or not isinstance(result.get('ok'), bool):
            raise RadioError('Ungueltige Antwort auf die Abstimmung')
        return result

    def register_play(self, identifier):
        identifier = station_id(identifier)
        # Click counting is separate from voting, and never controls playback.
        try:
            self._json(self.servers[0], '/json/url/' + identifier)
        except (requests.RequestException, ValueError, TypeError, RadioError):
            pass
