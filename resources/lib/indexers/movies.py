

#2021-07-15
# edit 2025-08-02 switch from treads to concurrent.futures 

import sys
import datetime, time, json
from concurrent.futures import ThreadPoolExecutor
from resources.lib.tmdb import cTMDB
from resources.lib.indexers import navigator
from resources.lib import searchDB, playcountDB, art, control, log_utils
from resources.lib.control import getKodiVersion, iteritems

if int(getKodiVersion()) >= 20: from infotagger.listitem import ListItemInfoTag

_params = dict(control.parse_qsl(sys.argv[2].replace('?',''))) if len(sys.argv) > 1 else dict()

class movies:
	def __init__(self):
		self.list = []
		self.meta = []
		self.total_pages = 0
		self.next_pages = 0
		self.query = ''
		self.activeSearchDB = 'TMDB'
		#self.setSearchDB() # TODO different search providers
		self.playcount = 0
		self.search_direct = False

		self.datetime = (datetime.datetime.utcnow() - datetime.timedelta(hours=5))
		self.systime = (self.datetime).strftime('%Y%m%d%H%M%S%f')

	def get(self, params):
		try:
			self.next_pages = int(params.get('page'))
			self.query = params.get('query')
			self.list, self.total_pages = cTMDB().search_term('movie', params.get('query'), params.get('page'))
			if self.list == None or len(self.list) == 0:  # nichts gefunden
				return control.infoDialog("Nichts gefunden1", time=2000)
			self.search_direct = True
			self.getDirectory(params)
			searchDB.save_query(params.get('query'), params.get('action'))
		except:
			return

	def getDirectory(self, params):
		try:
			if params.get('next_pages'): self.next_pages = params.get('next_pages')
			if params.get('total_pages'): self.total_pages = params.get('total_pages')
			if params.get('list'): self.list = params.get('list')
			self.worker()
			if self.list == None or len(self.list) == 0:	#nichts gefunden
				return control.infoDialog("Nichts gefunden", time=2000)
			self.Directory(self.list)
			return self.list
		except:
			return


	def search(self):
		# TODO different search providers
		#navigator.navigator().addDirectoryItem("DB für Suche auswählen", 'movieChangeSearchDB', self.activeSearchDB + '.png', 'DefaultMovies.png', isFolder=False)
		navigator.navigator().addDirectoryItem("[B]Filme - neue Suche %s[/B]" % self.activeSearchDB , 'searchNew&table=movies', '01_01_filme_neue_suche_tmdb.png', 'DefaultAddonsSearch.png',
											   isFolder=False, context=('Einstellungen', 'addonSettings'))
		match = searchDB.getSearchTerms('movies')
		lst = []
		delete_option = False
		#for i in match:
		for index, i in enumerate(match):
			term = control.py2_encode(i['query'])
			if term not in lst:
				delete_option = True
				navigator.navigator().addDirectoryItem(term, 'movies&page=1&query=%s' % control.quote_plus(term), '_search.png',
													   'DefaultAddonsSearch.png', isFolder=True,
													   context=("Suchanfrage löschen", 'searchDelTerm&table=movies&name=%s' % index))
				lst += [(term)]

		if delete_option:
			navigator.navigator().addDirectoryItem("[B]Suchverlauf löschen[/B]", 'searchClear&table=movies', '01_02_suchverlauf_loeschen.png', 'DefaultAddonProgram.png', isFolder=False)
		navigator.navigator()._endDirectory('', False) # addons  videos  files


#TODO https://forum.kodi.tv/showthread.php?tid=199579
	# def setSearchDB(self, new=''):
	#	 if control.getSetting('active.SearchDB.movie'):
	#		 _searchDB = control.getSetting('active.SearchDB.movie')
	#		 if new != '':
	#			 control.setSetting('active.SearchDB.movie', new)
	#			 _searchDB = new
	#		 self.activeSearchDB  = _searchDB
	#	 else:
	#		 control.setSetting('active.SearchDB.movie', 'tmdb')
	#		 self.activeSearchDB = 'tmdb'
	#
	# def changeSearchDB(self):
	#	 active = control.getSetting('active.SearchDB.movie')
	#	 data = []
	#	 for i in ['tmdb', 'trakt']:
	#		 if i == active: continue
	#		 data.append('wechseln zu ' + i.upper())
	#	 index = control.dialog.contextmenu(data)
	#	 if index == -1:
	#		 return
	#	 term = data[index].lower().split()[-1]
	#	 self.setSearchDB(term)
	#	 url = '%s?action=movieSearch' % sys.argv[0]
	#	 control.execute('Container.Update(%s)' % url)


	def worker(self):
		try:
			self.meta = []
			with ThreadPoolExecutor() as executor:
				executor.map(self.super_meta, self.list)
			self.meta = sorted(self.meta, key=lambda k: k['title'])
			#self.list = [i for i in self.meta if i['votes'] > 10 and i['rating'] > 4]
			self.list = []
			for i in self.meta:
				if self.search_direct:
					self.list.append(i)
				else:
					if 'votes' in i and i['votes'] > 10 and 'rating' in i and i['rating'] > 4: self.list.append(i)
					if not 'votes' in i: self.list.append(i)
		except:
			log_utils.error()

	def super_meta(self, id):
		try:
			# TODO different search providers
			meta = cTMDB().get_meta('movie', '', '', id, advanced='true')
			try:
				playcount = playcountDB.getPlaycount('movie', 'imdb_id', meta['imdb_id']) # mediatype, column_names, column_value, season=0, episode=0
				playcount = playcount if playcount else 0
				meta.update({'playcount': playcount})
			except:
				pass
			if not 'poster' in meta or meta['poster'] == '':
				poster = art.getMovie_art(meta['tmdb_id'], meta['imdbnumber'])
				meta.update({'poster': poster})
			#meta.update({'mediatype': 'movie'})
			self.meta.append(meta)
			return meta
		except:
			pass


	def Directory(self, items):
		if items == None or len(items) == 0:
			control.idle()
			sys.exit()
		sysaddon = sys.argv[0]
		syshandle = int(sys.argv[1])

		addonPoster, addonBanner = control.addonPoster(), control.addonBanner()
		addonFanart, settingFanart = control.addonFanart(), control.getSetting('fanart')

		watchedMenu = "In %s [I]Gesehen[/I]" % control.addonName
		unwatchedMenu = "In %s [I]Ungesehen[/I]" % control.addonName
		hasTrailerPlayer = control.hasTrailerPlayer()
		trailerLabel = control.trailerLabel()
		for i in items:
			try:
				title = i['title'] if 'title' in i else i['originaltitle']
				try:
					label = '%s (%s)' % (title, i['year'])  # show in list
				except:
					label = title

				sysname = label

				if 'premiered' in i:
					if datetime.datetime(*(time.strptime(i['premiered'], "%Y-%m-%d")[0:6])) > datetime.datetime.now():
						label = '[COLOR=red][I]{}[/I][/COLOR]'.format(label) # ffcc0000
				else:
					label = '[COLOR=red][I]{}[/I][/COLOR]'.format(label)

				meta = dict((k, v) for k, v in iteritems(i))
				if not 'duration' in i or i['duration'] == 0: meta.update({'duration': str(120 * 60)})

				poster = i['poster'] if 'poster' in i and 'http' in i['poster'] else addonPoster
				fanart = i['fanart'] if 'fanart' in i and 'http' in i['fanart'] else addonFanart
				meta.update({'poster': poster})
				meta.update({'fanart': fanart})
				meta.update({'systitle': title})
				meta.update({'sysname': sysname})

				_sysmeta = control.quote_plus(json.dumps(meta))

				item = control.item(label=label, offscreen=True)
				item.setArt({'poster': poster, 'banner': addonBanner})
				if settingFanart == 'true': item.setProperty('Fanart_Image', fanart)

				cm = []
				try:
					playcount = i['playcount'] if 'playcount' in i else 0
					if playcount == 1:
						cm.append((unwatchedMenu, 'RunPlugin(%s?action=UpdatePlayCount&meta=%s&playCount=0)' % (sysaddon, _sysmeta)))
						meta.update({'playcount': 1, 'overlay': 7})
					else:
						cm.append((watchedMenu, 'RunPlugin(%s?action=UpdatePlayCount&meta=%s&playCount=1)' % (sysaddon, _sysmeta)))
						meta.update({'playcount': 0, 'overlay': 6})
				except:
					pass

				if hasTrailerPlayer:
					cm.append((trailerLabel, 'RunPlugin(%s?action=playTrailer&tmdb_id=%s&mediatype=movie&title=%s&year=%s&poster=%s)' % (
						sysaddon, meta['tmdb_id'],
						control.quote_plus(str(title)),
						str(i.get('year', '')),
						control.quote_plus(str(poster)),
					)))
				cm.append(('Einstellungen', 'RunPlugin(%s?action=addonSettings)' % sysaddon))
				item.addContextMenuItems(cm)

				if 'plot' in i:
					plot = i['plot']
				else:
					plot = ''

				votes = ''
				if 'rating' in i and i['rating'] != '':
					if 'votes' in i: votes = '(%s)' % str(i['votes']).replace(',', '')
					plot = '[COLOR blue]Bewertung :  %.1f  %s[/COLOR]%s%s' % (float(i['rating']), votes, "\n\n", plot)
				meta.update({'plot': plot})
				aActors = []
				if 'cast' in i and i['cast']: aActors = i['cast']

				 ## supported infolabels: https://codedocs.xyz/AlwinEsch/kodi/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
				# remove unsupported infolabels
				meta.pop('cast', None)  # ersetzt durch item.setCast(i['cast'])
				meta.pop('fanart', None)
				meta.pop('tmdb_id', None)
				meta.pop('originallanguage', None)
				meta.pop('budget', None)
				meta.pop('revenue', None)
				meta.pop('sysname', None)
				meta.pop('systitle', None)

				sysmeta = control.quote_plus(json.dumps(meta))
				url = '%s?action=play&sysmeta=%s' % (sysaddon, sysmeta)

				meta.pop('poster', None)
				meta.pop('imdb_id', None)
				meta.pop('aliases', None)
				meta.pop('backdrop_url', None)
				meta.pop('cover_url', None)
# TODO
				# gefakte Video/Audio Infos
				# video_streaminfo = {'codec': 'h264', "width": 1920, "height": 1080}
				# audio_streaminfo = {'codec': 'dts', 'channels': 6, 'language': 'de'}
				video_streaminfo = {}
				audio_streaminfo = {}

				if int(getKodiVersion()) <= 19:
					if aActors: item.setCast(aActors)
					item.setInfo(type='Video', infoLabels=meta)
					item.addStreamInfo('video', video_streaminfo)
					item.addStreamInfo('audio', audio_streaminfo)
				else:
					info_tag = ListItemInfoTag(item, 'video')
					info_tag.set_info(meta)
					"""
					stream_details = {
							'video': [{videostream_1_values}, {videostream_2_values} ...],
							'audio': [{audiostream_1_values}, {audiostream_2_values} ...],
							'subtitle': [{subtitlestream_1_values}, {subtitlestream_2_values} ...]}
					"""
					stream_details = {
						'video': [video_streaminfo],
						'audio': [audio_streaminfo]}

					info_tag.set_stream_details(stream_details)
					info_tag.set_cast(aActors)

				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=False)
			except Exception as e:
				print(e)
				pass

		# nächste Seite
		try:
			self.next_pages = self.next_pages + 1
			if self.next_pages <= self.total_pages:
				if self.query:
					url = '%s?action=movies&url=&page=%s&query=%s' % (sys.argv[0], self.next_pages, control.quote_plus(self.query))
				else:
					url = '%s?action=listings' % sys.argv[0]
					url += '&media_type=%s' % _params.get('media_type')
					url += '&next_pages=%s' % self.next_pages
					url += '&url=%s' % control.quote_plus(_params.get('url'))
				item = control.item(label="Nächste Seite")
				icon = control.addonNext()
				item.setArt({'icon': icon, 'thumb': icon, 'poster': icon, 'banner': icon})
				if not addonFanart == None: item.setProperty('Fanart_Image', addonFanart)
				
				#  -> gesehen/ungesehen im cm und "Keine Informationen verfügbar" ausblenden (abhängig von control.content() )
				video_streaminfo = {'overlay': 4, 'plot': 'Â '}  # alt255

				if int(getKodiVersion()) <= 19:
					item.setInfo('video', video_streaminfo)
				else:
					stream_details = {'video': [video_streaminfo]}
					info_tag = ListItemInfoTag(item, 'video')
					info_tag.set_stream_details(stream_details)
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
		except:
			pass

		control.content(syshandle, 'movies')
		control.plugincategory(syshandle, control.addonVersion)
		control.endofdirectory(syshandle, cacheToDisc=True)
