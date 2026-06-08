

#2021-07-14
# edit 2025-06-12

import sys
from os import path
import xbmcvfs, xbmc
from resources.lib import control
from resources.lib.tools import cParser

sysaddon = sys.argv[0]
syshandle = int(sys.argv[1]) if len(sys.argv) > 1 else ''
artPath = control.artPath()
addonFanart = control.addonFanart()
addonPath = control.addonPath

# TODO https://kodi.wiki/view/Default_Icons
class navigator:
	def root(self):
		self.addDirectoryItem("Suche Filme", 'moviesSearch', '01_suche_filme.png', 'DefaultAddonsSearch.png')
		self.addDirectoryItem("Suche TV-Serien", 'tvshowsSearch', '02_suche_tv_serien.png', 'DefaultAddonsSearch.png')
		self.addDirectoryItem("Darsteller - Suche nach Person", 'personSearch', '03_darsteller_suche_nach_person.png', 'DefaultAddonsSearch.png')
		self.addDirectoryItem("Filme", 'movieNavigator', '04_filme.png', 'DefaultMovies.png')
		self.addDirectoryItem("TV-Serien", 'tvNavigator', '05_tv_serien.png', 'DefaultTVShows.png')
		if control.getSetting('downloads') == 'true':
			import threading
			_has_files = [False]
			def _chk():
				try:
					_has_files[0] = (
						len(control.listDir(control.getSetting('download.movie.path'))[0]) > 0 or
						len(control.listDir(control.getSetting('download.tv.path'))[0]) > 0
					)
				except Exception:
					pass
			_t = threading.Thread(target=_chk, daemon=True)
			_t.start()
			_t.join(timeout=2.0)
			if _t.is_alive():
				control.infoDialog('Download-Pfad nicht erreichbar', time=5000)
			elif _has_files[0]:
				self.addDirectoryItem("Downloads", 'downloadNavigator', 'downloads.png', 'DefaultFolder.png')
		self.addDirectoryItem("Werkzeuge", 'toolNavigator', '06_werkzeuge.png', 'DefaultAddonProgram.png')
		if xbmc.getCondVisibility('system.platform.windows'): self.addDirectoryItem("Stream-URL abspielen", 'playURL', '07_stream_url_abspielen.png', 'DefaultAddonWebSkin.png', isFolder=False)
		self._endDirectory(content='',cache=False)  # addons  videos  files

# TODO vote_count vote_average popularity revenue
	def movies(self):
		self.addDirectoryItem("[B]Filme[/B] - Neu", 'listings&media_type=movie&url=kino', '04_01_filme_neu.png', 'DefaultRecentlyAddedMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Jahr", 'movieYears', '04_02_filme_jahr.png', 'DefaultMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Genres", 'movieGenres', '04_03_filme_genres.png', 'DefaultMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Am populärsten", 'listings&media_type=movie&url=production_status=released%26sort_by=popularity.desc', '04_04_filme_am_populaersten.png', 'DefaultMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Am besten bewertet", 'listings&media_type=movie&url=production_status=released%26sort_by=vote_average.desc', '04_05_filme_am_besten_bewertet.png', 'DefaultMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Meist bewertet", 'listings&media_type=movie&url=production_status=released%26sort_by=vote_count.desc', '04_06_filme_meist_bewertet.png', 'DefaultMovies.png')
		self.addDirectoryItem("[B]Filme[/B] - Bestes Einspielergebnis", 'listings&media_type=movie&url=production_status=released%26sort_by=revenue.desc', '04_07_filme_bestes_einspielergebnis.png', 'DefaultMovies.png')
		# self.addDirectoryItem("[B]Filme[/B] - Oskar-Gewinner", 'movies&url=oscars', 'oscar-winners.png', 'DefaultMovies.png')
		self._endDirectory()

	def tvshows(self):
		self.addDirectoryItem("[B]Serien[/B] - Genres", 'tvGenres', '05_01_serien_genres.png', 'DefaultTVShows.png')
		self.addDirectoryItem("[B]Serien[/B] - Am populärsten", 'listings&media_type=tv&url=sort_by=popularity.desc', '05_02_serien_am_populaersten.png', 'DefaultTVShows.png')
		self.addDirectoryItem("[B]Serien[/B] - Am besten bewertet", 'listings&media_type=tv&url=sort_by=vote_average.desc', '05_03_serien_am_besten_bewertet.png', 'DefaultTVShows.png')
		self.addDirectoryItem("[B]Serien[/B] - Meist bewertet", 'listings&media_type=tv&url=sort_by=vote_count.desc', '05_04_serien_meist_bewertet.png', 'DefaultTVShows.png')
		# self.addDirectoryItem("[B]Serien[/B] - Suche nach Darstellern/Crew", 'tvPerson', 'people-search.png', 'DefaultTVShows.png', isFolder=False)
		self._endDirectory()

	def tools(self):
		self.addDirectoryItem("[B]Support[/B]: Information anzeigen", 'pluginInfo', '06_01_support_informationen_anzeigen.png', 'DefaultAddonProgram.png', isFolder=False)
		self.addDirectoryItem(control.addonName +": EINSTELLUNGEN", 'addonSettings', '06_02_xvault_einstellungen.png', 'DefaultAddonProgram.png', isFolder=False)
		# self.addDirectoryItem("[B]"+control.addonName.upper()+"[/B]: Reset Settings (außer Konten)", 'resetSettings', 'nightly_update.png', 'DefaultAddonProgram.png', isFolder=False)
		self.addDirectoryItem("[B]Resolver[/B]: EINSTELLUNGEN", 'resolverSettings', '06_03_resolver_einstellungen.png', 'DefaultAddonProgram.png', isFolder=False)
		self._endDirectory()	# addons  videos  files

	def downloads(self):
		movie_downloads = control.getSetting('download.movie.path')
		tv_downloads = control.getSetting('download.tv.path')
		if len(control.listDir(movie_downloads)[0]) > 0:
			self.addDirectoryItem("Filme", movie_downloads, 'movies.png', 'DefaultMovies.png', isAction=False)
		if len(control.listDir(tv_downloads)[0]) > 0:
			self.addDirectoryItem("TV-Serien", tv_downloads, 'tvshows.png', 'DefaultTVShows.png', isAction=False)
		self._endDirectory()

#TODO
	def addDirectoryItem(self, name, query, thumb, icon, context=None, queue=False, isAction=True, isFolder=True):
		url = '%s?action=%s' % (sysaddon, query) if isAction == True else query
		thumb = self.getMedia(thumb, icon)
		#laut kodi doku - ListItem([label, label2, path, offscreen])
		listitem = control.item(name, offscreen=True) # Removed iconImage and thumbnailImage
		listitem.setArt({'poster': thumb, 'icon': icon})
		if not context == None:
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

	def _endDirectory(self, content='', cache=True ): # addons  videos  files
		# https://romanvm.github.io/Kodistubs/_autosummary/xbmcplugin.html#xbmcplugin.setContent
		control.content(syshandle, content)
		control.plugincategory(syshandle, control.addonName + ' / '+ control.addonVersion)
		control.endofdirectory(syshandle, succeeded=True, cacheToDisc=cache)

# ------- ergänzt für xStream V2 -----------
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
	

