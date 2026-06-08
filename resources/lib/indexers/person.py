

#2021-06-09
# edit 2025-06-12

import sys
import json
from resources.lib.tmdb import cTMDB
from resources.lib.indexers import navigator
from resources.lib import searchDB, control, utils, playcountDB
from resources.lib.control import iteritems

_params = dict(control.parse_qsl(sys.argv[2].replace('?', ''))) if len(sys.argv) > 1 else dict()


class person:
	def __init__(self):
		self.list = []
		self.total_pages = 0
		self.next_pages = 0
		self.query = ''
		self.activeSearchDB = ''
		#self.setSearchDB() # TODO different search providers
		self.playcount = 0

	def get(self, params):
		try:
			self.next_pages = int(params.get('page')) + 1
			self.query = params.get('query')
			# Suche nach 'willis'
			# https://api.themoviedb.org/3/search/person?language=de&api_key=be7e192d9ff45609c57344a5c561be1d&query=willis&page=1
			self.list, self.total_pages = cTMDB().search_term('person', params.get('query'), params.get('page'))
			if self.list == None or len(self.list) == 0:  # nichts gefunden
				 return control.infoDialog("Nichts gefunden", time=2000)
			#self.list = sorted(self.list, key=lambda k: k['popularity'])
			self.personDirectory(self.list)
			searchDB.save_query(params.get('query'), params.get('action'))
			return self.list
		except:
			pass

	def search(self):
		navigator.navigator().addDirectoryItem("[B]Darsteller - neue Suche[/B]", 'searchNew&table=person', '03_01_darsteller_neue_suche.png', 'DefaultAddonsSearch.png',
											   isFolder=False, context=('Einstellungen', 'addonSettings'))
		match = searchDB.getSearchTerms('person')
		lst = []
		delete_option = False
		for index, i in enumerate(match):
			term = control.py2_encode(i['query'])
			if term not in lst:
				delete_option = True
				navigator.navigator().addDirectoryItem(term, 'person&page=1&query=%s' % control.quote_plus(term), self.activeSearchDB + '_people-search.png',
													   'DefaultAddonsSearch.png', isFolder=True,
													   context=("Suchanfrage löschen", 'searchDelTerm&table=person&name=%s' % index))
				lst += [(term)]

		if delete_option:
			navigator.navigator().addDirectoryItem("[B]Suchverlauf löschen[/B]", 'searchClear&table=person', '03_02_suchverlauf_loeschen.png', 'DefaultAddonProgram.png', isFolder=False)
		navigator.navigator()._endDirectory('', False)  # addons  videos  files


	def personDirectory(self, items):
		if items == None or len(items) == 0:
			control.idle()
			sys.exit()
		sysaddon = sys.argv[0]
		syshandle = int(sys.argv[1])

		addonBanner = control.addonBanner()
		addonFanart, settingFanart = control.addonFanart(), control.getSetting('fanart')
		addonNoPicture = control.addonNoPicture()
		for i in items:
			try:
				label = i['name'] # show in list

				meta = dict((k, v) for k, v in iteritems(i))

				poster = i['poster'] if 'poster' in i and i['poster'] != None else addonNoPicture
				fanart = i['fanart'] if 'fanart' in i and 'http' in i['fanart'] else addonFanart
				meta.update({'poster': poster})
				meta.update({'fanart': fanart})

				sysmeta = control.quote_plus(json.dumps(meta))

				url = '%s?action=personCredits&sysmeta=%s&number=0' % (sysaddon, sysmeta) #TODO

				item = control.item(label=label, offscreen=True)

				if 'plot' in i:
					plot = i['plot']
				else:
					plot = label

				meta.update({'plot': plot})

				item.setArt({'poster': poster, 'banner': addonBanner})
				if settingFanart == 'true': item.setProperty('Fanart_Image', fanart)

				## supported infolabels: https://codedocs.xyz/AlwinEsch/kodi/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
				# remove unsupported infolabels
				meta.pop('fanart', None)
				meta.pop('poster', None)
				meta.pop('id', None)
				meta.pop('name', None)
				meta.pop('popularity', None)

				item.setInfo(type='Video', infoLabels=meta)

				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
			except:
				pass

		# nächste Seite
		try:
			if self.next_pages <= self.total_pages:
				url = '%s?action=person&url=&page=%s&query=%s' % (sys.argv[0], self.next_pages, control.quote_plus(self.query))
				item = control.item(label="Nächste Seite")
				icon = control.addonNext()
				item.setArt({'icon': icon, 'thumb': icon, 'poster': icon, 'banner': icon})
				if not addonFanart == None: item.setProperty('Fanart_Image', addonFanart)
				#  -> gesehen/ungesehen im cm und "Keine Informationen verfügbar" ausblenden (abhängig von control.content() )
				item.setInfo('video', {'overlay': 4, 'plot': ' '})  # alt255
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
		except:
			pass

		control.content(syshandle, 'videos')
		control.plugincategory(syshandle, control.addonVersion)
		control.endofdirectory(syshandle, cacheToDisc=True)


	def getCredits(self, params):
		try:
			if 'person_id' in params:
				person_id = params['person_id']
				number = int(params.get('number', 0))
				self.list = cTMDB().search_credits('movie_credits', person_id)
				self.list = utils.multikeysort(self.list, ['-vote_average', '-popularity'])
				self.creditsDirectory(self.list, number, person_id)
			else:
				meta = json.loads(params.get('sysmeta'))
				# Suche nach Filme mit "Bruce Willis" -> 62
				# https://api.themoviedb.org/3/person/62/movie_credits?api_key=86dd18b04874d9c94afadde7993d94e3&language=de
				self.list = cTMDB().search_credits('movie_credits', meta['id']) # "combined_credits", "tv_credits", "movie_credits"

				if self.list == None or len(self.list) == 0:  # nichts gefunden
					 control.infoDialog("Nichts gefunden", time=8000)
				#self.list = sorted(self.list, key=lambda k: k['vote_average'], reverse=True)
				self.list = utils.multikeysort(self.list, ['-vote_average', '-popularity'])
				self.creditsDirectory(self.list, person_id=meta['id'])
				return self.list
		except:
			pass


	def creditsDirectory(self, items, number=0, person_id=None):
		if items == None or len(items) == 0:
			control.idle()
			sys.exit()
		sysaddon = sys.argv[0]
		syshandle = int(sys.argv[1])

		addonPoster, addonBanner = control.addonPoster(), control.addonBanner()
		addonFanart, settingFanart = control.addonFanart(), control.getSetting('fanart')
		hasTrailerPlayer = control.hasTrailerPlayer()
		trailerLabel = control.trailerLabel()
		for i in range(number, number + 20):
			if i >= len(items): break
			try:
				#label = i['name'] # show in list
				meta = cTMDB()._formatSuper(items[i], '')
				if meta['genre'] == '': continue
				poster = meta['poster'] if 'poster' in meta and meta['poster'] != None else addonPoster
				fanart = meta['fanart'] if 'fanart' in meta and 'http' in meta['fanart'] else addonFanart
				meta.update({'poster': poster})
				meta.update({'fanart': fanart})

				sysmeta = control.quote_plus(json.dumps(meta))

				url = '%s?action=playfromPerson&sysmeta=%s' % (sysaddon, sysmeta) #playPerson

				year = str(meta['year']) if 'year' in meta else '1900'
				label = meta['title'] + ' (' + year + ')' #+ meta['mediatype']
				try:
					playcount = playcountDB.getPlaycount('movie', 'name', label)  # mediatype, column_names, column_value, season=0, episode=0
					meta.update({'playcount': playcount})
				except:
					pass

				item = control.item(label=label, offscreen=True)

				if 'plot' in meta:
					plot = meta['plot']
				else:
					plot = label

				meta.update({'plot': plot})

				item.setArt({'poster': poster, 'banner': addonBanner})
				if settingFanart == 'true': item.setProperty('Fanart_Image', fanart)

				## supported infolabels: https://codedocs.xyz/AlwinEsch/kodi/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
				# remove unsupported infolabels
				movie_title = meta.get('title', '')
				tmdb_id = meta.get('tmdb_id', '')
				meta.pop('fanart', None)
				meta.pop('poster', None)
				meta.pop('id', None)
				meta.pop('name', None)
				meta.pop('popularity', None)
				meta.pop('tmdb_id', None)
				meta.pop('genre_ids', None)
				meta.pop('originallanguage', None)
				meta.pop('cover_url', None)
				meta.pop('backdrop_url', None)
				item.setInfo(type='Video', infoLabels=meta)

				cm = []
				if hasTrailerPlayer and tmdb_id:
					cm.append((trailerLabel, 'RunPlugin(%s?action=playTrailer&tmdb_id=%s&mediatype=movie&title=%s&year=%s&poster=%s)' % (
						sysaddon, tmdb_id,
						control.quote_plus(str(movie_title)),
						year,
						control.quote_plus(str(poster)),
					)))
				if cm:
					item.addContextMenuItems(cm)
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=False)
			except Exception as e:
				print(e)
				pass

		# nächste Seite
		try:
			next_number = number + 20
			if person_id is not None and next_number < len(items):
				url = '%s?action=personCredits&person_id=%s&number=%s' % (sys.argv[0], person_id, next_number)
				item = control.item(label="Nächste Seite")
				icon = control.addonNext()
				item.setArt({'icon': icon, 'thumb': icon, 'poster': icon, 'banner': icon})
				if not addonFanart == None: item.setProperty('Fanart_Image', addonFanart)
				#  -> gesehen/ungesehen im cm und "Keine Informationen verfügbar" ausblenden (abhängig von control.content() )
				item.setInfo('video', {'overlay': 4, 'plot': ' '})  # alt255
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
		except:
			pass

		control.content(syshandle, 'movies')
		control.plugincategory(syshandle, control.addonVersion)
		control.endofdirectory(syshandle, cacheToDisc=True)

