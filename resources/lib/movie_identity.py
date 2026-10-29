"""Evidence from provider detail pages, never from the requested list-item label."""
import json
import hashlib
import os
import re
import unicodedata
import time
from html import unescape
from html.parser import HTMLParser


def text(value):
    value = unescape(re.sub(r'<[^>]*>', ' ', str(value or '')))
    return re.sub(r'\s+', ' ', value).strip()


def title_key(value):
    value = re.sub(r'\s*\((?:19|20)\d{2}\)\s*$', '', text(value))
    value = unicodedata.normalize('NFKD', value.casefold())
    return ''.join(c for c in value if c.isalnum() and not unicodedata.combining(c))


def year_value(value):
    match = re.match(r'^(19\d{2}|20\d{2})(?:\D|$)', str(value or '').strip())
    return match.group(1) if match else ''


def imdb_value(value):
    match = re.search(r'\btt\d{5,12}\b', str(value or ''), re.I)
    return match.group().lower() if match else ''


def classify(titles, year, imdb, found):
    """Return verified, unknown or conflict; IDs beat regional year differences."""
    found = found if isinstance(found, dict) else {}
    expected_id, actual_id = imdb_value(imdb), imdb_value(found.get('imdb'))
    if expected_id and actual_id:
        return 'verified' if expected_id == actual_id else 'conflict'
    wanted, actual = year_value(year), year_value(found.get('year'))
    if wanted and actual and wanted != actual:
        return 'conflict'
    names = {title_key(t) for t in titles if t}
    name = title_key(found.get('title'))
    if name and names and name not in names:
        return 'conflict'
    return 'verified' if name and name in names and wanted and wanted == actual else 'unknown'


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.heading, self.scripts = {}, [], []
        self.h1_depth = 0
        self.script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            self.meta[(attrs.get('property') or attrs.get('name') or attrs.get('itemprop') or '').lower()] = attrs.get('content', '')
        if tag == 'h1':
            self.h1_depth += 1
        if tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json':
            self.script = []

    def handle_endtag(self, tag):
        if tag == 'h1':
            self.h1_depth = max(0, self.h1_depth - 1)
        if tag == 'script' and self.script is not None:
            self.scripts.append(''.join(self.script))
            self.script = None

    def handle_data(self, data):
        if self.h1_depth:
            self.heading.append(data)
        if self.script is not None:
            self.script.append(data)


def from_html(html, fallback_title='', fallback_year=''):
    page = _Page()
    page.feed(html or '')
    found = {'title': text(' '.join(page.heading)) or text(page.meta.get('og:title')) or text(fallback_title),
             'year': year_value(fallback_year), 'imdb': ''}
    title_year = re.search(r'\((19\d{2}|20\d{2})\)\s*$', found['title'])
    if not found['year'] and title_year:
        found['year'] = title_year.group(1)
    for key in ('datepublished', 'og:video:release_date', 'video:release_date'):
        found['year'] = year_value(page.meta.get(key)) or found['year']
    # Only a single primary Movie object is evidence, not recommendations/item lists.
    movies = []
    for script in page.scripts:
        try:
            value = json.loads(script)
        except (ValueError, TypeError):
            continue
        nodes = value if isinstance(value, list) else [value]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            candidates = [node] + (node.get('@graph') if isinstance(node.get('@graph'), list) else [])
            if isinstance(node.get('mainEntity'), dict):
                candidates.append(node['mainEntity'])
            for candidate in candidates:
                if isinstance(candidate, dict) and candidate.get('@type') == 'Movie':
                    movies.append(candidate)
    if len(movies) == 1 and (not found['title'] or title_key(movies[0].get('name')) == title_key(found['title'])):
        movie = movies[0]
        found['title'] = text(movie.get('name')) or found['title']
        found['year'] = year_value(movie.get('datePublished')) or found['year']
        refs = [movie.get('sameAs'), movie.get('url')]
        ids = {imdb_value(v) for ref in refs for v in (ref if isinstance(ref, list) else [ref])} - {''}
        if len(ids) == 1:
            found['imdb'] = ids.pop()
    if not found['year']:
        pattern = r'(?:Erscheinungsjahr|Erscheinungsdatum|Veröffentlicht|Jahr|Release|datePublished)[\s:<="\'/\w-]{0,100}?(19\d{2}|20\d{2})\b'
        match = re.search(pattern, unescape(html or ''), re.I)
        if match:
            found['year'] = match.group(1)
    return found


def annotate(items, titles, year, imdb, found):
    status = classify(titles, year, imdb, found)
    if status == 'conflict':
        return []
    for item in items:
        item['movie_identity'] = dict(found)
        item['identity_status'] = status
        item['identity_target'] = imdb_value(imdb) or (title_key(titles[0] if titles else '') + ':' + year_value(year))
    return items


def rejection_key(item):
    return hashlib.sha256(json.dumps([item.get('identity_target'), item.get('provider'),
                                     item.get('url')], sort_keys=True).encode('utf-8')).hexdigest()


def rejections(path):
    try:
        if os.path.getsize(path) > 200000:
            return {}
        with open(path, encoding='utf-8') as handle:
            values = json.load(handle)
        return {k: float(v) for k, v in values.items() if re.fullmatch(r'[a-f0-9]{64}', k)
                and time.time() < float(v) <= time.time() + 86401}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def reject(path, item):
    values = rejections(path)
    values[rejection_key(item)] = time.time() + 86400
    values = dict(sorted(values.items(), key=lambda kv: kv[1], reverse=True)[:1000])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + '.%s.tmp' % os.getpid()
    with open(temporary, 'w', encoding='utf-8') as handle:
        json.dump(values, handle)
    os.replace(temporary, path)


def without_rejected(path, items):
    values = rejections(path)
    return [i for i in items if rejection_key(i) not in values]
