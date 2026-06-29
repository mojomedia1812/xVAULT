import sys
from os import path

import xbmcvfs

from resources.lib import control
from resources.lib.tools import cParser

sysaddon = sys.argv[0]
syshandle = int(sys.argv[1]) if len(sys.argv) > 1 else ''
artPath = control.artPath()
addonFanart = control.addonFanart()

class navigator:
	def root(self):
		self.addDirectoryItem("Suche Filme", 'moviesSearch', '01_suche_filme.png', 'DefaultAddonsSearch.png')
		self.addDirectoryItem("Suche TV-Serien", 'tvshowsSearch', '02_suche_tv_serien.png', 'DefaultAddonsSearch.png')
		self.addDirectoryItem("Suche nach Person / Darsteller", 'personSearch', '03_darsteller_suche_nach_person.png', 'DefaultAddonsSearch.png')
		self.addDirectoryItem("Filme", 'movieNavigator', '04_filme.png', 'DefaultMovies.png')
		self.addDirectoryItem("TV-Serien", 'tvNavigator', '05_tv_serien.png', 'DefaultTVShows.png')
		self.addDirectoryItem("LiveTV", 'liveTVNavigator', 'DefaultTVShows.png', 'DefaultTVShows.png')
		self.addDirectoryItem("Stream-URL abspielen", 'playURL', '07_stream_url_abspielen.png', 'DefaultAddonWebSkin.png', isFolder=False)
		self.addDirectoryItem("Werkzeuge", 'toolNavigator', '06_werkzeuge.png', 'DefaultAddonProgram.png')
		self._endDirectory(content='', cache=False)

	def movies(self):
		self.addDirectoryItem("[B]Filme[/B] - Neu", 'listings&media_type=movie&url=kino', '04_01_filme_neu.png', 'DefaultRecentlyAddedMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Jahr", 'movieYears', '04_02_filme_jahr.png', 'DefaultMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Genres", 'movieGenres', '04_03_filme_genres.png', 'DefaultMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Am populärsten", 'listings&media_type=movie&url=production_status=released%26sort_by=popularity.desc', '04_04_filme_am_populaersten.png', 'DefaultMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Am besten bewertet", 'listings&media_type=movie&url=production_status=released%26sort_by=vote_average.desc', '04_05_filme_am_besten_bewertet.png', 'DefaultMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Meist bewertet", 'listings&media_type=movie&url=production_status=released%26sort_by=vote_count.desc', '04_06_filme_meist_bewertet.png', 'DefaultMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Bestes Einspielergebnis", 'listings&media_type=movie&url=production_status=released%26sort_by=revenue.desc', '04_07_filme_bestes_einspielergebnis.png', 'DefaultMovies.png')
		self._endDirectory()

	def tvshows(self):
		self.addDirectoryItem("[B]Serien[/B] - Genres", 'tvGenres', '05_01_serien_genres.png', 'DefaultTVShows.png')
		self.addDirectoryItem("[B]Serien[/B] - Am populärsten", 'listings&media_type=tv&url=sort_by=popularity.desc', '05_02_serien_am_populaersten.png', 'DefaultTVShows.png')
		self.addDirectoryItem("[B]Serien[/B] - Am besten bewertet", 'listings&media_type=tv&url=sort_by=vote_average.desc', '05_03_serien_am_besten_bewertet.png', 'DefaultTVShows.png')
		self.addDirectoryItem("[B]Serien[/B] - Meist bewertet", 'listings&media_type=tv&url=sort_by=vote_count.desc', '05_04_serien_meist_bewertet.png', 'DefaultTVShows.png')
		self._endDirectory()

	def tools(self):
		self.addDirectoryItem("[B]Support[/B]: Information anzeigen", 'pluginInfo', '06_01_support_informationen_anzeigen.png', 'DefaultAddonProgram.png', isFolder=False)
		self.addDirectoryItem(control.addonName +": EINSTELLUNGEN", 'addonSettings', '06_02_xvault_einstellungen.png', 'DefaultAddonProgram.png', isFolder=False)
		self.addDirectoryItem("[B]Resolver[/B]: EINSTELLUNGEN", 'resolverSettings', '06_03_resolver_einstellungen.png', 'DefaultAddonProgram.png', isFolder=False)
		self._endDirectory()

	def downloads(self):
		movie_downloads = control.getSetting('download.movie.path')
		tv_downloads = control.getSetting('download.tv.path')
		if len(control.listDir(movie_downloads)[0]) > 0:
			self.addDirectoryItem("Filme", movie_downloads, 'movies.png', 'DefaultMovies.png', isAction=False)
		if len(control.listDir(tv_downloads)[0]) > 0:
			self.addDirectoryItem("TV-Serien", tv_downloads, 'tvshows.png', 'DefaultTVShows.png', isAction=False)
		self._endDirectory()

	def addDirectoryItem(self, name, query, thumb, icon, context=None, queue=False, isAction=True, isFolder=True):
		url = '%s?action=%s' % (sysaddon, query) if isAction else query
		thumb = self.getMedia(thumb, icon)
		listitem = control.item(name, offscreen=True)
		listitem.setArt({'poster': thumb, 'icon': icon})
		if context is not None:
			cm = []
			cm.append((context[0], 'RunPlugin(%s?action=%s)' % (sysaddon, context[1])))
			listitem.addContextMenuItems(cm)

		isMatch, sPlot = cParser.parseSingleResult(query, "plot'.*?'([^']+)")
		if not isMatch: sPlot = '[COLOR blue]{0}[/COLOR]'.format(name)
		if isFolder:
			listitem.setInfo('video', {'overlay': 4, 'plot': control.unquote_plus(sPlot)})
			listitem.setIsFolder(True)
		else:
			listitem.setProperty('IsPlayable', 'false')
		self.addFanart(listitem, query)
		control.addItem(syshandle, url, listitem, isFolder)

	def _endDirectory(self, content='', cache=True):
		control.content(syshandle, content)
		control.plugincategory(syshandle, control.addonName + ' / '+ control.addonVersion)
		control.endofdirectory(syshandle, succeeded=True, cacheToDisc=cache)

	def addFanart(self, listitem, query):
		if control.getSetting('fanart')=='true':
			isMatch, sFanart = cParser.parseSingleResult(query, "fanart'.*?'([^']+)")
			if isMatch:
				sFanart = self.getMedia(sFanart)
				listitem.setProperty('fanart_image', sFanart)
			else:
				listitem.setProperty('fanart_image', addonFanart)

	def getMedia(self,mediaFile=None, icon=None):
		if xbmcvfs.exists(path.join(artPath, mediaFile)): mediaFile = path.join(artPath, mediaFile)
		elif xbmcvfs.exists(path.join(artPath, 'sites', mediaFile)): mediaFile = path.join(artPath, 'sites', mediaFile)
		elif mediaFile.startswith('http'): return mediaFile
		else: mediaFile = icon
		return mediaFile
	

