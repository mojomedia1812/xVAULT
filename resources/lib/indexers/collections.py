import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from resources.lib import control, log_utils

try:
	from infotagger.listitem import ListItemInfoTag
except Exception:
	ListItemInfoTag = None


BASE_URL = 'https://filmo.to'
CACHE_TTL = 24 * 60 * 60

CURATED_SERIES_RULES = {
	'alien': {
		'allow_tmdb_collection_ids': (8091, 115762, 135416, 1434946),
	},
	'batman': {
		'tmdb_collection_queries': (
			'Batman',
			'The Dark Knight',
			'Batman Beyond',
			'Batman: The Dark Knight Returns',
			'Batman: The Long Halloween',
			'LEGO DC Comics Super Heroes',
			'Batman Unlimited',
		),
		'allow_tmdb_collection_ids': (
			120794, 263, 948485, 379475, 248534, 785583, 386162, 334996,
			1313822, 1737864, 209131,
		),
		'allow_tmdb_ids': (
			2661, 242643, 471474, 581997, 870358,
		),
		'allow_title_tokens': ('batman',),
		'allow_tmdb_collection_name_tokens': (
			'batman', 'dark knight', 'batman beyond', 'lego dc', 'red hood',
			'son of batman', 'man of steel', 'ニンジャバットマン',
		),
	},
}

THEME_COLLECTION_SLUGS = (
	'top-kinofilme',
	'movies-filmed-in-Europe',
	'neu-bei-filmo-disney-co',
	'action-spannung-grusel',
	'summer-2026',
	'explore-new-release-movies',
)


class collections:
	def __init__(self):
		self.cache_dir = os.path.join(control.addonProfilePath, 'cache', 'filmo_collections')
		self.art_path = control.artPath()

	def root(self, params=None):
		page = self._safe_int((params or {}).get('page'), 1)
		html = self._load_html('/collections', 'collections_%s' % page, page=page)
		items = self._parse_collections(html)
		self._collections_directory(items, page, html)

	def movies(self, params):
		slug = params.get('slug') or ''
		if not slug:
			return self._empty('Sammlung konnte nicht geöffnet werden.')
		page = self._safe_int(params.get('page'), 1)
		html = self._load_html('/collections/%s' % slug, 'collection_%s_%s' % (slug, page), page=page)
		items = self._parse_movies(html)
		title = self._page_title(html) or params.get('name') or 'Collection'
		items = self._enrich_and_sort_movies(items, slug, title)
		self._movies_directory(items, slug, page, html, title)

	def play(self, params):
		slug = params.get('slug') or ''
		title = control.unquote_plus(params.get('title') or '')
		poster = control.unquote_plus(params.get('poster') or '')
		if slug:
			meta = self._movie_meta(slug)
			if meta.get('title'):
				title = meta.get('title')
		else:
			meta = {}

		if not title:
			return control.infoDialog('Filmtitel konnte nicht gelesen werden.', icon='WARNING', time=3000)

		year = meta.get('year')
		play_meta = self._tmdb_meta(title, year)
		if not play_meta:
			play_meta = {
				'mediatype': 'movie',
				'title': title,
				'originaltitle': title,
				'systitle': title,
				'year': year,
				'premiered': meta.get('premiered'),
				'plot': meta.get('plot') or '',
				'poster': poster or meta.get('poster') or control.addonPoster(),
				'cover_url': poster or meta.get('poster') or control.addonPoster(),
				'fanart': meta.get('fanart') or control.addonFanart(),
				'backdrop_url': meta.get('fanart') or control.addonFanart(),
			}

		try:
			from resources.lib import sources
			sources.sources().play({'sysmeta': json.dumps(play_meta)})
		except Exception:
			log_utils.error('Filmo Collection Wiedergabe fehlgeschlagen')
			control.infoDialog('Quellensuche konnte nicht gestartet werden.', icon='ERROR', time=3000)

	def _collections_directory(self, items, page, html):
		if not items:
			return self._empty('Collections konnten nicht geladen werden.')
		sysaddon = sys.argv[0]
		syshandle = int(sys.argv[1])
		for item_data in items:
			label = item_data['title']
			item = control.item(label=label, offscreen=True)
			poster = item_data.get('poster') or self._media('04_filme.png')
			item.setArt({'poster': poster, 'thumb': poster, 'icon': poster})
			if control.getSetting('fanart') == 'true':
				item.setProperty('Fanart_Image', control.addonFanart())
			item.setInfo('video', {'plot': 'Filme aus der Collection: %s' % item_data['title'], 'overlay': 4})
			item.setIsFolder(True)
			url = '%s?action=collectionMovies&slug=%s&name=%s' % (
				sysaddon,
				control.quote_plus(item_data['slug']),
				control.quote_plus(item_data['title']),
			)
			control.addItem(syshandle, url, item, True)

		if self._has_next_page(html, '/collections', page):
			self._add_next('%s?action=collectionsNavigator&page=%s' % (sysaddon, page + 1))
		self._end('movies')

	def _movies_directory(self, items, slug, page, html, title):
		if not items:
			return self._empty('In dieser Collection wurden keine Filme gefunden.')
		sysaddon = sys.argv[0]
		syshandle = int(sys.argv[1])
		for item_data in items:
			label = item_data['title']
			item = control.item(label=label, offscreen=True)
			poster = item_data.get('poster') or control.addonPoster()
			item.setArt({'poster': poster, 'thumb': poster, 'icon': poster, 'banner': control.addonBanner()})
			if control.getSetting('fanart') == 'true':
				item.setProperty('Fanart_Image', control.addonFanart())
			self._set_info(item, {
				'title': label,
				'mediatype': 'movie',
				'year': item_data.get('year') or 0,
				'premiered': item_data.get('premiered') or '',
				'plot': self._movie_plot(title, item_data),
				'overlay': 6,
			})
			item.setProperty('IsPlayable', 'true')
			item.addContextMenuItems([('Einstellungen', 'RunPlugin(%s?action=addonSettings)' % sysaddon)])
			url = '%s?action=collectionPlay&slug=%s&title=%s&poster=%s' % (
				sysaddon,
				control.quote_plus(item_data['slug']),
				control.quote_plus(label),
				control.quote_plus(poster),
			)
			control.addItem(syshandle, url, item, False)

		if self._has_next_page(html, '/collections/%s' % slug, page):
			self._add_next('%s?action=collectionMovies&slug=%s&name=%s&page=%s' % (
				sysaddon,
				control.quote_plus(slug),
				control.quote_plus(title),
				page + 1,
			))
		self._end('movies')

	def _enrich_and_sort_movies(self, items, collection_slug='', collection_title=''):
		if not items:
			return items
		enriched = []
		try:
			workers = min(8, max(1, len(items)))
			with ThreadPoolExecutor(max_workers=workers) as executor:
				for item_data in executor.map(self._enrich_movie_item, items):
					enriched.append(item_data)
		except Exception:
			log_utils.error('Filmo Collection Metadaten konnten nicht parallel geladen werden')
			enriched = [self._enrich_movie_item(item_data) for item_data in items]
		enriched = self._filter_collection_items(collection_slug, collection_title, enriched)
		return sorted(enriched, key=self._movie_sort_key)

	def _enrich_movie_item(self, item_data):
		item_data = dict(item_data)
		meta = self._movie_meta(item_data.get('slug') or '')
		for key in ('premiered', 'year', 'plot', 'fanart'):
			if meta.get(key):
				item_data[key] = meta.get(key)
		if meta.get('poster'):
			item_data['poster'] = item_data.get('poster') or meta.get('poster')
		if meta.get('title'):
			item_data['title'] = meta.get('title')
		tmdb = self._tmdb_collection_meta(item_data)
		if tmdb:
			item_data.update(tmdb)
		return item_data

	def _filter_collection_items(self, collection_slug, collection_title, items):
		if not items or collection_slug in THEME_COLLECTION_SLUGS:
			return items

		rule = CURATED_SERIES_RULES.get(collection_slug)
		targets = self._tmdb_collection_targets(collection_slug, collection_title, rule)
		if rule:
			filtered = [item for item in items if self._item_matches_rule(item, rule, collection_title, targets)]
			return filtered if filtered else items

		target_ids = targets.get('collection_ids') or self._detect_tmdb_collection_ids(collection_title, items)
		target_movie_ids = targets.get('movie_ids') or set()
		if not target_ids and not target_movie_ids:
			return items

		filtered = [
			item for item in items
			if self._item_matches_tmdb_targets(item, collection_title, target_ids, target_movie_ids)
		]
		return filtered if len(filtered) >= 2 else items

	def _item_matches_rule(self, item_data, rule, collection_title='', targets=None):
		targets = targets or {}
		allowed_collection_ids = self._int_set(rule.get('allow_tmdb_collection_ids', ()))
		allowed_collection_ids.update(targets.get('collection_ids') or set())
		allowed_movie_ids = self._int_set(rule.get('allow_tmdb_ids', ()))
		allowed_movie_ids.update(targets.get('movie_ids') or set())
		tmdb_id = self._as_int(item_data.get('tmdb_id'))
		collection_id = self._as_int(item_data.get('tmdb_collection_id'))
		if tmdb_id and tmdb_id in allowed_movie_ids:
			return True
		if collection_id and collection_id in allowed_collection_ids:
			return True
		if self._item_collection_name_allowed(item_data, rule):
			return True
		if self._item_title_allowed(item_data, rule):
			return True
		if rule.get('allow_unassigned_title_match') and collection_title and self._unassigned_title_matches_collection(collection_title, item_data):
			return True
		return False

	def _item_matches_tmdb_targets(self, item_data, collection_title, target_collection_ids, target_movie_ids):
		tmdb_id = self._as_int(item_data.get('tmdb_id'))
		collection_id = self._as_int(item_data.get('tmdb_collection_id'))
		if tmdb_id and tmdb_id in target_movie_ids:
			return True
		if collection_id and collection_id in target_collection_ids:
			return True
		if self._tmdb_collection_name_matches(collection_title, item_data.get('tmdb_collection_name') or ''):
			return True
		return self._unassigned_title_matches_collection(collection_title, item_data)

	def _tmdb_collection_targets(self, collection_slug, collection_title, rule=None):
		rule = rule or {}
		targets = {'collection_ids': set(), 'movie_ids': set()}
		queries = []
		if collection_title:
			queries.append(collection_title)
		queries.extend(rule.get('tmdb_collection_queries', ()))

		seen_queries = set()
		for query in queries:
			query_key = self._clean(query).lower()
			if not query_key or query_key in seen_queries:
				continue
			seen_queries.add(query_key)
			for result in self._tmdb_search_collections(query):
				collection_id = self._as_int(result.get('id'))
				name = result.get('name') or ''
				if not collection_id or not self._tmdb_search_result_matches(collection_title, name, rule):
					continue
				targets['collection_ids'].add(collection_id)
				self._add_tmdb_collection_parts(collection_id, targets)

		for collection_id in self._int_set(rule.get('allow_tmdb_collection_ids', ())):
			targets['collection_ids'].add(collection_id)
			self._add_tmdb_collection_parts(collection_id, targets)

		return targets

	def _add_tmdb_collection_parts(self, collection_id, targets):
		details = self._tmdb_collection_details(collection_id)
		for part in details.get('parts') or []:
			tmdb_id = self._as_int(part.get('id'))
			if tmdb_id:
				targets['movie_ids'].add(tmdb_id)

	def _tmdb_search_result_matches(self, collection_title, tmdb_name, rule):
		if self._tmdb_collection_name_matches(collection_title, tmdb_name):
			return True
		name = self._clean(tmdb_name).lower()
		for token in rule.get('allow_tmdb_collection_name_tokens', ()):
			if self._clean(token).lower() in name:
				return True
		return False

	def _item_collection_name_allowed(self, item_data, rule):
		name = self._clean(item_data.get('tmdb_collection_name') or '').lower()
		if not name:
			return False
		for token in rule.get('allow_tmdb_collection_name_tokens', ()):
			if self._clean(token).lower() in name:
				return True
		return False

	def _item_title_allowed(self, item_data, rule):
		title = self._clean('%s %s' % (item_data.get('title') or '', item_data.get('tmdb_title') or '')).lower()
		if not title:
			return False
		for token in rule.get('allow_title_tokens', ()):
			if self._clean(token).lower() in title:
				return True
		return False

	def _detect_tmdb_collection_ids(self, collection_title, items):
		if not collection_title:
			return set()
		matches = {}
		for item_data in items:
			collection_id = item_data.get('tmdb_collection_id')
			collection_name = item_data.get('tmdb_collection_name') or ''
			if not collection_id or not self._tmdb_collection_name_matches(collection_title, collection_name):
				continue
			matches.setdefault(collection_id, 0)
			matches[collection_id] += 1

		if not matches:
			return set()
		threshold = max(2, int(round(len(items) * 0.5)))
		ids = set([collection_id for collection_id, count in matches.items() if count >= threshold])
		return ids

	def _tmdb_collection_name_matches(self, collection_title, tmdb_name):
		title_tokens = self._significant_tokens(collection_title)
		name_tokens = self._significant_tokens(tmdb_name)
		if not title_tokens or not name_tokens:
			return False
		return all(token in name_tokens for token in title_tokens)

	def _unassigned_title_matches_collection(self, collection_title, item_data):
		if item_data.get('tmdb_collection_id'):
			return False
		return self._tmdb_collection_name_matches(collection_title, item_data.get('title') or '')

	def _significant_tokens(self, value):
		value = self._clean(value).lower()
		value = re.sub(r'[^0-9a-zäöüß]+', ' ', value)
		stopwords = set(('a', 'an', 'the', 'der', 'die', 'das', 'und', 'von', 'filmreihe', 'collection'))
		return [token for token in value.split() if token and token not in stopwords]

	def _movie_sort_key(self, item_data):
		premiered = item_data.get('premiered') or ''
		if re.match(r'^\d{4}-\d{2}-\d{2}$', premiered):
			return (0, premiered, item_data.get('title') or '')
		year = item_data.get('year')
		if year:
			return (1, '%04d-99-99' % int(year), item_data.get('title') or '')
		return (2, '9999-99-99', item_data.get('title') or '')

	def _movie_plot(self, collection_title, item_data):
		parts = []
		if item_data.get('year'):
			parts.append('Erscheinungsjahr: %s' % item_data.get('year'))
		if item_data.get('premiered'):
			parts.append('Veröffentlichung: %s' % item_data.get('premiered'))
		parts.append('Film aus der Collection: %s' % collection_title)
		if item_data.get('plot'):
			parts.append(item_data.get('plot'))
		return '\n\n'.join(parts)

	def _parse_collections(self, html):
		items = []
		seen = set()
		for match in re.finditer(r'<a\b(?=[^>]*collection-index-card\b)[^>]*href="([^"]+/collections/([^"?/]+))"[^>]*>(.*?)</a>', html, re.S):
			slug = control.unquote(match.group(2)).strip()
			body = match.group(3)
			title = self._class_text(body, 'collection-index-card__title')
			count = self._class_text(body, 'collection-index-card__meta')
			if not title or slug in seen:
				continue
			seen.add(slug)
			items.append({
				'title': title,
				'slug': slug,
				'count': count,
				'poster': self._first_poster(body),
			})
		return items

	def _parse_movies(self, html):
		items = []
		seen = set()
		for match in re.finditer(r'<a\b(?=[^>]*movie-poster-grid-card\b)[^>]*href="([^"]+/movies/([^"?/]+))"[^>]*>(.*?)</a>', html, re.S):
			slug = control.unquote(match.group(2)).strip()
			body = match.group(3)
			title = self._class_text(body, 'movie-poster-grid-card__title') or self._attr_text(body, 'alt')
			if not title or slug in seen:
				continue
			seen.add(slug)
			items.append({
				'title': title,
				'slug': slug,
				'poster': self._first_poster(body),
			})
		return items

	def _movie_meta(self, slug):
		html = self._load_html('/movies/%s' % slug, 'movie_%s' % slug)
		title = self._page_title(html)
		plot = self._meta_content(html, 'description') or self._meta_property(html, 'og:description')
		poster = self._meta_property(html, 'og:image') or self._first_poster(html)
		premiered = self._release_date(html)
		year = premiered[:4] if premiered else self._year_from_text(html)
		return {
			'title': title,
			'plot': plot,
			'poster': poster,
			'fanart': poster,
			'premiered': premiered,
			'year': int(year) if str(year).isdigit() else None,
		}

	def _tmdb_meta(self, title, year):
		try:
			from resources.lib.tmdb import cTMDB
			meta = cTMDB().get_meta('movie', title, year=year or '', advanced='true')
			if meta:
				return meta
		except Exception:
			log_utils.error('TMDb-Metadaten fuer Filmo Collection nicht gefunden')
		return {}

	def _tmdb_collection_meta(self, item_data):
		slug = item_data.get('slug') or ''
		if not slug:
			return {}
		cache_key = 'tmdb_movie_%s' % slug
		cached = self._read_cache(cache_key)
		if cached:
			try:
				return json.loads(cached)
			except Exception:
				pass

		title = item_data.get('title') or ''
		if not title:
			return {}
		try:
			from resources.lib.tmdb import cTMDB
			meta = cTMDB().search_movie_name(title, item_data.get('year') or '', advanced='true')
		except Exception:
			log_utils.error('TMDb-Collection fuer Filmo Film nicht gefunden')
			meta = {}

		result = {}
		try:
			tmdb_id = meta.get('id') or meta.get('tmdb_id')
			if tmdb_id:
				result['tmdb_id'] = int(tmdb_id)
			if meta.get('title'):
				result['tmdb_title'] = meta.get('title')
			if meta.get('release_date'):
				result['tmdb_release_date'] = meta.get('release_date')
			collection = meta.get('belongs_to_collection') or {}
			if collection.get('id'):
				result['tmdb_collection_id'] = int(collection.get('id'))
			if collection.get('name'):
				result['tmdb_collection_name'] = collection.get('name')
		except Exception:
			result = {}

		self._write_cache(cache_key, json.dumps(result, ensure_ascii=False))
		return result

	def _tmdb_search_collections(self, query):
		query = self._clean(query)
		if not query:
			return []
		cache_key = 'tmdb_collection_search_%s' % query
		cached = self._read_cache(cache_key)
		if cached:
			try:
				return json.loads(cached)
			except Exception:
				pass
		try:
			from resources.lib.tmdb import cTMDB
			tmdb = cTMDB()
			if not tmdb.api_key:
				return []
			data = tmdb._call('search/collection', 'query=%s&page=1' % control.quote_plus(query))
			results = data.get('results') or []
		except Exception:
			log_utils.error('TMDb-Collection-Suche fuer Filmo Collection fehlgeschlagen')
			results = []
		self._write_cache(cache_key, json.dumps(results, ensure_ascii=False))
		return results

	def _tmdb_collection_details(self, collection_id):
		collection_id = self._as_int(collection_id)
		if not collection_id:
			return {}
		cache_key = 'tmdb_collection_details_%s' % collection_id
		cached = self._read_cache(cache_key)
		if cached:
			try:
				return json.loads(cached)
			except Exception:
				pass
		try:
			from resources.lib.tmdb import cTMDB
			tmdb = cTMDB()
			if not tmdb.api_key:
				return {}
			data = tmdb._call('collection/%s' % collection_id)
		except Exception:
			log_utils.error('TMDb-Collection-Details fuer Filmo Collection fehlgeschlagen')
			data = {}
		self._write_cache(cache_key, json.dumps(data, ensure_ascii=False))
		return data

	def _int_set(self, values):
		result = set()
		for value in values or ():
			number = self._as_int(value)
			if number:
				result.add(number)
		return result

	def _as_int(self, value):
		try:
			return int(value)
		except Exception:
			return None

	def _load_html(self, path, key, page=1):
		if page and page > 1:
			url = '%s%s?page=%s' % (BASE_URL, path, page)
			cache_key = '%s_page_%s' % (key, page)
		else:
			url = '%s%s' % (BASE_URL, path)
			cache_key = key
		cached = self._read_cache(cache_key)
		if cached:
			return cached
		html = self._fetch(url)
		if html:
			self._write_cache(cache_key, html)
		return html

	def _fetch(self, url):
		try:
			if control.is_python2:
				request = control.Request(url, headers={
					'User-Agent': 'Mozilla/5.0 (Kodi; xVAULT)',
					'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
				})
				response = control.urlopen(request, timeout=20)
				data = response.read()
				return data.decode('utf-8', 'replace')
			request = control.Request(url, headers={
				'User-Agent': 'Mozilla/5.0 (Kodi; xVAULT)',
				'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
			})
			with control.urlopen(request, timeout=20) as response:
				return response.read().decode('utf-8', 'replace')
		except Exception as exc:
			log_utils.log('Filmo Collections nicht erreichbar: %s' % exc, log_utils.LOGWARNING)
			return ''

	def _read_cache(self, key):
		path = self._cache_file(key)
		try:
			if not os.path.exists(path):
				return ''
			with open(path, 'r', encoding='utf-8') as handle:
				payload = json.load(handle)
			if int(time.time()) - int(payload.get('time', 0)) > CACHE_TTL:
				return ''
			return payload.get('html') or ''
		except Exception:
			return ''

	def _write_cache(self, key, html):
		try:
			if not os.path.exists(self.cache_dir):
				os.makedirs(self.cache_dir)
			with open(self._cache_file(key), 'w', encoding='utf-8') as handle:
				json.dump({'time': int(time.time()), 'html': html}, handle)
		except Exception as exc:
			log_utils.log('Filmo Cache konnte nicht geschrieben werden: %s' % exc, log_utils.LOGWARNING)

	def _cache_file(self, key):
		safe = re.sub(r'[^a-zA-Z0-9_.-]+', '_', key)
		return os.path.join(self.cache_dir, safe + '.json')

	def _class_text(self, html, class_name):
		match = re.search(r'<[^>]+class="[^"]*%s[^"]*"[^>]*>(.*?)</[^>]+>' % re.escape(class_name), html, re.S)
		return self._clean(match.group(1)) if match else ''

	def _attr_text(self, html, attr):
		match = re.search(r'\b%s="([^"]+)"' % re.escape(attr), html, re.S)
		return self._clean(match.group(1)) if match else ''

	def _first_poster(self, html):
		match = re.search(r'<img[^>]+src="(https://filmo\.to/img/poster/[^"]+)"', html, re.S)
		if match:
			return control.unescape(match.group(1))
		match = re.search(r'srcset="(https://filmo\.to/img/poster/[^" ]+)', html, re.S)
		return control.unescape(match.group(1)) if match else ''

	def _meta_content(self, html, name):
		match = re.search(r'<meta[^>]+name="%s"[^>]+content="([^"]*)"' % re.escape(name), html, re.S)
		return self._clean(match.group(1)) if match else ''

	def _meta_property(self, html, name):
		match = re.search(r'<meta[^>]+property="%s"[^>]+content="([^"]*)"' % re.escape(name), html, re.S)
		return control.unescape(match.group(1)) if match else ''

	def _page_title(self, html):
		match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
		if match:
			return self._clean(match.group(1))
		match = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
		title = self._clean(match.group(1)) if match else ''
		return re.sub(r'\s+jetzt kostenlos streamen\s+.*$', '', title, flags=re.I)

	def _release_date(self, html):
		match = re.search(r'(\d{4}-\d{2}-\d{2})', html)
		return match.group(1) if match else ''

	def _year_from_text(self, html):
		match = re.search(r'\b(19[0-9]{2}|20[0-9]{2})\b', self._clean(html))
		return match.group(1) if match else ''

	def _has_next_page(self, html, path, page):
		next_page = page + 1
		return bool(re.search(r'href="%s%s\?page=%s"' % (re.escape(BASE_URL), re.escape(path), next_page), html))

	def _clean(self, value):
		value = re.sub(r'<[^>]+>', ' ', value or '')
		value = control.unescape(value)
		return re.sub(r'\s+', ' ', value).strip()

	def _safe_int(self, value, default):
		try:
			return int(value)
		except Exception:
			return default

	def _media(self, name):
		path = os.path.join(self.art_path, name)
		return path if os.path.exists(path) else control.addonPoster()

	def _add_next(self, url):
		item = control.item(label='Nächste Seite', offscreen=True)
		icon = control.addonNext()
		item.setArt({'icon': icon, 'thumb': icon, 'poster': icon})
		item.setInfo('video', {'plot': 'Weitere Collections anzeigen', 'overlay': 4})
		item.setIsFolder(True)
		control.addItem(int(sys.argv[1]), url, item, True)

	def _set_info(self, item, meta):
		if ListItemInfoTag is not None and int(control.getKodiVersion()) >= 20:
			info_tag = ListItemInfoTag(item, 'video')
			info_tag.set_info(meta)
		else:
			item.setInfo('video', meta)

	def _end(self, content):
		handle = int(sys.argv[1])
		control.content(handle, content)
		control.plugincategory(handle, control.addonName + ' / ' + control.addonVersion)
		control.endofdirectory(handle, succeeded=True, cacheToDisc=True)

	def _empty(self, message):
		try:
			control.infoDialog(message, icon='WARNING', time=3000)
		except Exception:
			pass
		try:
			self._end('movies')
		except Exception:
			pass
		return []
