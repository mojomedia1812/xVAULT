

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
		with ThreadPoolExecutor() as executor:
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
					label = 'Specials / Pilotfilme - %s' % sysmeta['title']
				else:
					label = 'Staffel %s - %s' % (season, sysmeta['title'])
				if i.get('premiered') and datetime.datetime(*(time.strptime(i['premiered'], "%Y-%m-%d")[0:6])) > datetime.datetime.now():
					label = '[COLOR=red][I]{}[/I][/COLOR]'.format(label) # ffcc0000

				poster = control.posterArtwork(i.get('poster'), sysmeta.get('poster'))
				fanart = control.fanartArtwork(sysmeta.get('fanart'), i.get('fanart'))
				plot = i['plot'] if 'plot' in i and len(i['plot']) > 50 else sysmeta['plot']

				meta.update({'poster': poster})
				meta.update({'fanart': fanart})
				sysmeta.update({'poster': poster})
				sysmeta.update({'fanart': fanart})
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
				if 'cast' in meta and meta['cast']: aActors = meta['cast']

				## supported infolabels: https://codedocs.xyz/AlwinEsch/kodi/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
				# # # remove unsupported InfoLabels
				meta.pop('cast', None)  # ersetzt durch item.setCast(i['cast'])
				meta.pop('fanart', None)
				meta.pop('poster', None)
				meta.pop('imdb_id', None)
				meta.pop('tvdb_id', None)
				meta.pop('tmdb_id', None)
				meta.pop('number_of_seasons', None)
				meta.pop('number_of_episodes', None)
				meta.pop('originallanguage', None)
				meta.pop('sysname', None)
				meta.pop('systitle', None)
				meta.pop('year', None)
				meta.pop('aliases', None)
				meta.pop('backdrop_url', None)
				meta.pop('cover_url', None)

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
					stream_details = {
						'video': [video_streaminfo],
						'audio': [audio_streaminfo]}
					info_tag.set_stream_details(stream_details)
					info_tag.set_cast(aActors)


				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
			except Exception as e:
				#print(e) #TODO LOG
				pass

		control.content(syshandle, 'tvshows')
		control.plugincategory(syshandle, control.addonVersion)
		control.endofdirectory(syshandle, cacheToDisc=False)

		# setzt Auswahl nach letzte als gesehen markierte Staffel -> Content: 'movies'
		if control.getSetting('status.position') == 'true':
			from resources.lib.utils import setPosition
			setPosition(pos, __name__, 'movies')
