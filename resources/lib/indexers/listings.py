

#2021-07-15
# edit 2025-08-02 switch from treads to concurrent.futures 

import sys, os, datetime
import json
from resources.lib.requestHandler import cRequestHandler
from resources.lib import control, log_utils

_params = dict(control.parse_qsl(sys.argv[2].replace('?', ''))) if len(sys.argv) > 1 else dict()

#TV-Film
# {"genres":[{"id":10759,"name":"Action & Adventure"},{"id":16,"name":"Animation"},{"id":35,"name":"Komödie"},{"id":80,"name":"Krimi"},{"id":99,"name":"Dokumentarfilm"},{"id":18,"name":"Drama"},{"id":10751,"name":"Familie"},{"id":10762,"name":"Kids"},{"id":9648,"name":"Mystery"},{"id":10763,"name":"News"},{"id":10764,"name":"Reality"},{"id":10765,"name":"Sci-Fi & Fantasy"},{"id":10766,"name":"Soap"},{"id":10767,"name":"Talk"},{"id":10768,"name":"War & Politics"},{"id":37,"name":"Western"}]}

_genresTv = [{"id":10759,"name":"Action & Abenteuer"},{"id":16,"name":"Animation"},{"id":35,"name":"Komödie"},{"id":80,"name":"Krimi"},{"id":18,"name":"Drama"},{"id":10751,"name":"Familie"},
			 {"id":10762,"name":"Kids"},{"id":9648,"name":"Mystery"},{"id":10764,"name":"Reality"},{"id":10765,"name":"Sci-Fi & Fantasy"},{"id":10768,"name":"War & Politics"},
			 {"id":37,"name":"Western"}]

_genresMovie = [{"id":28,"name":"Action"},{"id":12,"name":"Abenteuer"},{"id":16,"name":"Animation"},{"id":35,"name":"Komödie"},{"id":80,"name":"Krimi"},{"id":18,"name":"Drama"},
				{"id":10751,"name":"Familie"},{"id":14,"name":"Fantasy"},{"id":36,"name":"Historie"},{"id":27,"name":"Horror"},{"id":10402,"name":"Musik"},{"id":9648,"name":"Mystery"},
				{"id":10749,"name":"Liebesfilm"},{"id":878,"name":"Science Fiction"},{"id":10770,"name":"TV-Film"},{"id":53,"name":"Thriller"},{"id":10752,"name":"Kriegsfilm"},{"id":37,"name":"Western"}]

class listings:
	def __init__(self):
		self.URL = 'https://api.themoviedb.org/3/discover'
		self.api_key = control.getSetting('api.tmdb').strip()
		self.lang = 'de'
		self.list = []
		self.total_pages = 0
		self.query = ''
		self.media_type = ''
		#self.year_params = 'release_date.gte=%s-01-01&release_date.lte=%s-12-31&with_release_type=2|3&without_genres=%s&sort_by=popularity.desc'
		#self.year_params = 'primary_release_year=%s&with_release_type=2|3&without_genres=%s&sort_by=vote_count.desc' #&sort_by= vote_average.desc / popularity.desc / vote_count
		self.genres_params = ''
		self.popular_link = ''
		self.datetime = datetime.datetime.utcnow()
		self.provider_logo = 'https://image.tmdb.org/t/p/w185'

	def get(self, params):
		try:
			if params.get('next_pages'):
				next_pages = int(params.get('next_pages'))
			else:
				next_pages = 1

			append_to_response = 'page=%s' % next_pages
			self.media_type = params.get('media_type')
			url = params.get('url')
			if url == 'kino':
				today = datetime.datetime.today() - datetime.timedelta(days=21)
				fromday = datetime.datetime.today() - datetime.timedelta(days=90)
				_today = today.strftime('%Y-%m-%d')
				_fromday = fromday.strftime('%Y-%m-%d')
				url = 'primary_release_date.gte=%s&primary_release_date.lte=%s' % (_fromday, _today)
			elif url == 'new_tv_de':
				today = self._germany_today()
				fromday = today - datetime.timedelta(days=30)
				url = 'first_air_date.gte=%s&first_air_date.lte=%s&sort_by=first_air_date.desc&timezone=Europe/Berlin&include_null_first_air_dates=false' % (fromday.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))

			list, total_pages = self._call(url, append_to_response=append_to_response)
			if not list:
				label = 'Neue Serien konnten nicht geladen werden.' if params.get('url') == 'new_tv_de' else 'Nichts gefunden.'
				return self._emptyDirectory(label, media_type=self.media_type)
			params.update({'list': list})
			params.update({'next_pages': next_pages})
			params.update({'total_pages': total_pages})
			params.update({'media_type': self.media_type})
			if self.media_type == 'movie':
				from resources.lib.indexers import movies
				movies.movies().getDirectory(params)
			else:
				from resources.lib.indexers import tvshows
				tvshows.tvshows().getDirectory(params)
			return self.list
		except Exception as exc:
			log_utils.log('Listing fehlgeschlagen (%s): %s' % (params.get('url'), exc), log_utils.LOGWARNING)
			return self._emptyDirectory('Liste konnte nicht geladen werden.', media_type=params.get('media_type'))

	def movieYears(self):
		year = (self.datetime.strftime('%Y'))
		without = '99,10762,10767,10766,16' # doku, kids, Talk, Soap, Animation
		for i in range(int(year), 1960, -1):
			self.list.append({'name': str(i), 'url': 'primary_release_year=%s&with_release_type=2|3&without_genres=%s&sort_by=vote_count.desc' % (str(i), without), 'image': 'years.png', 'action': 'listings'})
		self.media_type = 'movie'
		self.addDirectory(self.list)
		return self.list

	def movieGenres(self):
		without = '99,16'
		self.media_type = 'movie'
		for i in _genresMovie:
			if i['id'] == 16: without = '99'
			self.list.append({'name': i['name'], 'url': 'with_genres=%s&without_genres=%s&sort_by=vote_count.desc' % (str(i['id']), without), 'image': 'genres.png', 'action': 'listings'})
		self.addDirectory(self.list)
		return self.list

	def tvGenres(self):
		without = '99,10762,10767,10766,16' # doku, kids, Talk, Soap, Animation
		self.media_type = 'tv'
		for i in _genresTv:
			if i['id'] == 16 or i['id'] == 10762: without = '99,10767,10766'
			self.list.append({'name': i['name'], 'url': 'with_genres=%s&without_genres=%s&sort_by=vote_count.desc' % (str(i['id']), without), 'image': 'genres.png', 'action': 'listings'})
		self.addDirectory(self.list)
		return self.list

	def movieWatchProviders(self):
		self.media_type = 'movie'
		self._watchProviders()
		return self.list

	def tvWatchProviders(self):
		self.media_type = 'tv'
		self._watchProviders()
		return self.list

	def _watchProviders(self):
		providers = self._providerList(self.media_type)
		for provider in providers:
			provider_id = provider.get('provider_id')
			name = provider.get('provider_name')
			if not provider_id or not name:
				continue
			logo = provider.get('logo_path')
			image = self.provider_logo + logo if logo else 'tmdb_search.png'
			media_label = 'Filme' if self.media_type == 'movie' else 'Serien'
			url = 'watch_region=DE&with_watch_providers=%s&sort_by=popularity.desc' % provider_id
			self.list.append({
				'name': name,
				'url': url,
				'image': image,
				'action': 'listings',
				'plot': '%s mit TMDb-Verfügbarkeit bei %s im deutschen Markt.' % (media_label, name)
			})
		if not self.list:
			return self._emptyDirectory('Streaming-Anbieter konnten nicht geladen werden.', media_type=self.media_type)
		self.addDirectory(self.list)
		return self.list

	def _providerList(self, media_type):
		if media_type not in ['movie', 'tv']:
			return []
		url = 'https://api.themoviedb.org/3/watch/providers/%s?api_key=%s&language=de-DE&watch_region=DE' % (media_type, self.api_key)
		try:
			request = cRequestHandler(url, caching=True, ignoreErrors=True)
			request.cacheTime = 60 * 60 * 24
			payload = request.request()
			if not payload:
				return []
			data = json.loads(payload)
			providers = data.get('results') or []
			providers = [provider for provider in providers if isinstance(provider, dict)]
			providers.sort(key=lambda item: (int(item.get('display_priority') or 9999), item.get('provider_name') or ''))
			return providers
		except Exception as exc:
			log_utils.log('TMDb-Streaming-Anbieter konnten nicht geladen werden (%s): %s' % (media_type, exc), log_utils.LOGWARNING)
			return []

	def _germany_today(self):
		try:
			from zoneinfo import ZoneInfo
			return datetime.datetime.now(ZoneInfo('Europe/Berlin')).date()
		except:
			return datetime.datetime.now().date()

	def _emptyDirectory(self, message, media_type=''):
		try:
			control.infoDialog(message, icon='WARNING', time=4000)
		except:
			pass
		try:
			syshandle = int(sys.argv[1])
			control.content(syshandle, 'tvshows' if media_type == 'tv' else 'movies')
			control.plugincategory(syshandle, control.addonVersion)
			control.endofdirectory(syshandle, cacheToDisc=False)
		except Exception as exc:
			log_utils.log('Leeres Listing konnte nicht beendet werden: %s' % exc, log_utils.LOGWARNING)
		return []


	def _call(self, url, append_to_response=''):
		url = '%s/%s?api_key=%s&language=de-DE&region=DE&vote_count.gte=20&include_adult=false&include_video=false&%s' % (self.URL, self.media_type, self.api_key, url)
		if not 'without_genres' in url: url += '&without_genres=99' # doku
		if append_to_response:
			url += '&%s' % append_to_response
		oRequestHandler = cRequestHandler(url, ignoreErrors=True)
		name = oRequestHandler.request()
		if not name:
			return [], 0
		try:
			data = json.loads(name)
		except (TypeError, ValueError):
			return [], 0
		if 'errors' in data or ('status_code' in data and data['status_code'] != 1):
			return [], 0
		if 'status_code' in data and data['status_code'] == 34:
			return [], 0
		list = []
		for i in data['results']:
			if self._validResult(i):
				list.append(i['id'])

		return list, data['total_pages']

	def _validResult(self, item):
		if not isinstance(item, dict):
			return False
		if self.media_type == 'movie':
			return bool(item.get('id') and (item.get('title') or item.get('original_title')))
		return bool(item.get('id') and (item.get('name') or item.get('original_name')))


	def addDirectory(self, items):
		if items is None or len(items) == 0:
			control.idle()
			sys.exit()
		sysaddon = sys.argv[0]
		syshandle = int(sys.argv[1])
		addonPoster, addonFanart, addonThumb, artPath = control.addonFanart(), control.addonFanart(), control.addonThumb(), control.artPath()

		for i in items:
			try:
				name = i['name']
				if 'plot' in i:
					plot = i['plot']
				elif self.media_type == 'movie':
					if 'primary_release_year' in i['url']:
						plot = 'Filme aus dem Jahr:  %s' % name
					else:
						plot = 'Filme aus der Kategorie:  %s' % name
				else:
					plot = 'Serien aus der Kategorie:  %s' % name

				try:
					image = i.get('image') or ''
					if image.startswith('http://') or image.startswith('https://'):
						poster = image
						thumb = image
					else:
						poster = os.path.join(artPath, image)
						thumb = os.path.join(artPath, image)
				except:
					thumb = addonThumb
					poster = addonPoster

				url = '%s?action=%s' % (sysaddon, i['action'])
				url += '&media_type=%s' % self.media_type
				try:
					url += '&url=%s' % control.quote_plus(i['url'])
				except:
					pass

				item = control.item(label=name, offscreen=True)
				# item.setArt({'icon': thumb, 'thumb': thumb})
				item.setArt({'thumb': thumb, 'poster': poster})
				if not addonFanart is None: item.setProperty('Fanart_Image', addonFanart)

				#  -> gesehen/ungesehen im cm und "Keine Informationen verfügbar" ausblenden (abhängig vom Skin)
				item.setInfo('video', {'overlay': 4, 'plot': plot})
				item.setIsFolder(True)

				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
			except:
				pass

		control.content(syshandle, 'videos')
		control.plugincategory(syshandle, control.addonVersion)
		control.endofdirectory(syshandle, cacheToDisc=True)

