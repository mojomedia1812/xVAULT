

#2021-07-21
# edit 2025-08-02 switch from treads to concurrent.futures 

import sys
import datetime, time, json
from resources.lib.tmdb import cTMDB
from concurrent.futures import ThreadPoolExecutor
from resources.lib import control, playcountDB, watched_status
from resources.lib.control import getKodiVersion
if int(getKodiVersion()) >= 20: from infotagger.listitem import ListItemInfoTag

_params = dict(control.parse_qsl(sys.argv[2].replace('?',''))) if len(sys.argv) > 1 else dict()
MAX_SEASON_WORKERS = 4

class seasons:
	def __init__(self):
		self.list = []
		self.lang = "de"
		self.sysmeta = _params['sysmeta']
		#self.datetime = (datetime.datetime.utcnow() - datetime.timedelta(hours=5))
		#self.systime = (self.datetime).strftime('%Y%m%d%H%M%S%f')


	def get(self, params):
		try:
			data = json.loads(params['sysmeta'])
			self.title = data['title']
			number_of_seasons = data.get('number_of_seasons') or 0
			try:
				number_of_seasons = int(number_of_seasons)
			except:
				number_of_seasons = 0

			tmdb_id = data['tmdb_id']
			tvdb_id = data['tvdb_id'] if 'tvdb_id' in data else None
			imdb_id = data['imdb_id'] if 'imdb_id' in data else None
			title = data['title']

			self.imdb_id = imdb_id
			self.number_of_seasons = number_of_seasons
			self.tvshow_status = playcountDB.getTvshowStatus(title)
			data['playcount'] = watched_status.tvshow_playcount(title, number_of_seasons=number_of_seasons, tvshow_status=self.tvshow_status)
			self.sysmeta = json.dumps(data)

			self.list.append({'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': 0, 'is_special': True})
			for i in range(1, number_of_seasons+1):
				self.list.append({'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': i})
			self.worker()
			show_playcount = watched_status.tvshow_playcount(title, self.list, number_of_seasons, self.tvshow_status)
			watched_status.store_tvshow_status(title, title, imdb_id, number_of_seasons, show_playcount)
			data['playcount'] = show_playcount
			self.sysmeta = json.dumps(data)
			if self.list == None or len(self.list) == 0:	# nichts gefunden
				control.infoDialog("Nichts gefunden", time=8000)
			else:
				self.Directory(self.list)
				return self.list
			return
		except:
			pass # return ???


	def worker(self):
		self.meta = []
		workers = min(MAX_SEASON_WORKERS, max(1, len(self.list)))
		with ThreadPoolExecutor(max_workers=workers) as executor:
			executor.map(self.super_meta, self.list)

		self.meta = sorted(self.meta, key=lambda k: k['season'])
		self.list = [i for i in self.meta] # falls noch eine Filterfunktion kommt


	def super_meta(self, i):
		try:
			meta = cTMDB().get_meta_seasons(i['tmdb_id'] , i['season'], advanced='true')
			if not meta or not meta.get('number_of_episodes'):
				return
			if i.get('is_special'):
				meta.update({'is_special': True})
			playcount = watched_status.season_playcount(
				self.title,
				meta['season'],
				meta.get('episodes'),
				meta.get('number_of_episodes'),
				tvshow_status=getattr(self, 'tvshow_status', None),
			)
			watched_status.store_season_status(
				self.title,
				self.title + ' S%02d' % int(meta['season']),
				meta['season'],
				meta.get('number_of_episodes'),
				playcount,
			)
			overlay = 7 if playcount > 0 else 6
			meta.update({'playcount': playcount, 'overlay': overlay})
			meta.pop('episodes', None)
			self.meta.append(meta)
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
		normal_season_count = len([item for item in items if int(item.get('season') or 0) > 0])
		pos = 0
		for i in items:
			try:
				meta = json.loads(self.sysmeta)
				sysmeta = json.loads(self.sysmeta)
				season = i['season']

				systitle = sysmeta['systitle']
				sysname = systitle + ' S%02d' % season
				sysmeta.update({'sysname': sysname})
				sysmeta.update({'season': season})
				sysmeta.update({'number_of_episodes': i['number_of_episodes']})

				_sysmeta = {k: v for k, v in sysmeta.items()}
				_sysmeta.pop('cast', None)
				_sysmeta = control.quote_plus(json.dumps(_sysmeta))

				if i.get('is_special') or int(season) == 0:
					base_label = 'Specials / Pilotfilme - %s' % sysmeta['title']
				else:
					base_label = 'Staffel %s - %s' % (season, sysmeta['title'])
				label = base_label
				if i.get('premiered') and datetime.datetime(*(time.strptime(i['premiered'], "%Y-%m-%d")[0:6])) > datetime.datetime.now():
					label = '[COLOR=red][I]{}[/I][/COLOR]'.format(label) # ffcc0000

				poster = i['poster'] if 'poster' in i and 'http' in i['poster'] else sysmeta['poster']
				fanart = sysmeta['fanart'] if 'fanart' in sysmeta else addonFanart
				plot = i['plot'] if 'plot' in i and len(i['plot']) > 50 else sysmeta['plot']

				meta.update({'poster': poster})
				meta.update({'fanart': fanart})
				meta.update({'plot': plot})
				#if 'air_date' in i and i['air_date']: meta.update({'air_date': i['air_date']})
				if 'premiered' in i and i['premiered']: meta.update({'premiered': i['premiered']})

				item = control.item(label=label, offscreen=True)
				item.setArt({'poster': poster, 'banner': addonBanner})
				if settingFanart == 'true': item.setProperty('Fanart_Image', fanart)

				if sysmeta['playcount'] == 0: playcount = i['playcount']
				else: playcount = 1

				cm = []
				try:
					if playcount == 1:
						cm.append((unwatchedMenu, 'RunPlugin(%s?action=UpdatePlayCount&meta=%s&playCount=0)' % (sysaddon, _sysmeta)))
						meta.update({'playcount': 1, 'overlay': 7})
						sysmeta.update({'playcount': 1, 'overlay': 7})
						pos = season + 1
						if season == 0:
							pos = 1
						elif normal_season_count == season:
							pos = season
					else:
						cm.append((watchedMenu, 'RunPlugin(%s?action=UpdatePlayCount&meta=%s&playCount=1)' % (sysaddon, _sysmeta)))
						meta.update({'playcount': 0, 'overlay': 6})
						sysmeta.update({'playcount': 0, 'overlay': 6})
				except:
					pass
				info_meta = self._season_info_meta(meta, sysmeta, i, base_label, plot)
				try:
					from resources.lib import trakt
					rate_item = trakt.context_rate_item(sysaddon, sysmeta)
					if rate_item:
						cm.append(rate_item)
				except:
					pass
				item.addContextMenuItems(cm)

				sysmeta = control.quote_plus(json.dumps(sysmeta))
				url = '%s?action=episodes&sysmeta=%s' % (sysaddon, sysmeta)

				aActors = []

				## supported infolabels: https://codedocs.xyz/AlwinEsch/kodi/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
				# # # remove unsupported InfoLabels
				meta = info_meta

				if int(getKodiVersion()) <= 19:
					if aActors: item.setCast(aActors)
					item.setInfo(type='Video', infoLabels=meta)
				else:
					info_tag = ListItemInfoTag(item, 'video')
					info_tag.set_info(meta)
					info_tag.set_cast(aActors)


				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
			except Exception as e:
				#print(e) #TODO LOG
				pass

		control.content(syshandle, 'videos')
		control.plugincategory(syshandle, control.addonVersion)
		control.endofdirectory(syshandle, cacheToDisc=False)

		# setzt Auswahl nach letzte als gesehen markierte Staffel
		if control.getSetting('status.position') == 'true':
			from resources.lib.utils import setPosition
			setPosition(pos, __name__, 'videos')

	def _season_info_meta(self, meta, sysmeta, season_item, label, plot):
		info = {
			'title': label,
			'tvshowtitle': sysmeta.get('title', ''),
			'season': season_item.get('season'),
			'plot': plot or '',
			'mediatype': 'season',
			'playcount': meta.get('playcount', season_item.get('playcount', 0)),
			'overlay': meta.get('overlay', season_item.get('overlay', 6)),
		}
		if season_item.get('premiered'):
			info['premiered'] = season_item.get('premiered')
			try:
				info['year'] = int(str(season_item.get('premiered'))[:4])
			except:
				pass
		if sysmeta.get('genre'):
			info['genre'] = sysmeta.get('genre')
		if sysmeta.get('studio'):
			info['studio'] = sysmeta.get('studio')
		return info
