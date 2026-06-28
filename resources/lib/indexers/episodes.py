

#2021-07-15
# edit 2025-08-02 switch from treads to concurrent.futures 

import sys
import datetime, json, time
from resources.lib import control, watched_status
from resources.lib.tmdb import cTMDB
from concurrent.futures import ThreadPoolExecutor
from resources.lib.control import getKodiVersion
if int(getKodiVersion()) >= 20: from infotagger.listitem import ListItemInfoTag

_params = dict(control.parse_qsl(sys.argv[2].replace('?',''))) if len(sys.argv) > 1 else dict()

class episodes:
	def __init__(self):
		self.list = []
		self.lang = "de"
		self.datetime = (datetime.datetime.utcnow() - datetime.timedelta(hours=5))
		self.systime = (self.datetime).strftime('%Y%m%d%H%M%S%f')
		self.sysmeta = _params['sysmeta']

		self.ePosition = 0

	def get(self, params):
		try:
			data = json.loads(params['sysmeta'])
			self.title = data['title']
			season = data['season']
			episodes = data.get('episodes')
			if not episodes:
				season_meta = cTMDB().get_meta_seasons(data['tmdb_id'], season, advanced='true')
				episodes = season_meta.get('episodes', [])
			if not episodes:
				return
			data['number_of_episodes'] = len(episodes)
			self.sysmeta = json.dumps(data)

			self.list.extend(episodes)

			# for i in range(1, number_of_episodes+1):
			#	 self.list.append({'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season, 'episode': i})
			self.worker()
			playcount = watched_status.season_playcount(self.title, season, self.list, data.get('number_of_episodes'))
			watched_status.store_season_status(self.title, self.title + ' S%02d' % int(season), season, data.get('number_of_episodes'), playcount)
			if playcount == 0 and data.get('number_of_seasons'):
				watched_status.store_tvshow_status(self.title, self.title, data.get('imdb_id'), data.get('number_of_seasons'), 0)
			data['playcount'] = playcount
			self.sysmeta = json.dumps(data)
			self.Directory(self.list)
			return  self.list
		except:
			return


	def worker(self):
		try:
			self.meta = []
			#much faster
			with ThreadPoolExecutor() as executor:
				executor.map(self.super_meta, self.list)

			self.meta = sorted(self.meta, key=lambda k: k['episode'])
			self.list = [i for i in self.meta] # falls noch eine Filterfunktion kommt
			# self.list = [i for i in self.list if not i['plot'].strip() == '' and not i['poster'] == control.addonPoster()]  # - Filter
		except:
			return


	def super_meta(self, i):
		try:
			#meta = cTMDB().get_meta_episode('episode', '', self.list[i]['tmdb_id'] , self.list[i]['season'], self.list[i]['episode'], advanced='true')
			meta = cTMDB()._format_episodes(i, self.title)
			playcount = watched_status.episode_playcount(self.title, meta['season'], meta['episode'], meta)
			overlay = 7 if playcount > 0 else 6
			meta.update({'playcount': playcount, 'overlay': overlay})
			self.meta.append(meta)
		except:
			pass


	def Directory(self, items):
		# if xbmc.getInfoLabel("Container.Viewmode") != 55: xbmc.executebuiltin( "Container.SetViewMode(%i)" % 55 )
		if items == None or len(items) == 0:
			control.idle()
			sys.exit()

		sysaddon = sys.argv[0]
		syshandle = int(sys.argv[1])

		addonPoster, addonBanner = control.addonPoster(), control.addonBanner()
		addonFanart, settingFanart = control.addonFanart(), control.getSetting('fanart')

		watchedMenu = "In %s [I]Gesehen[/I]" % control.addonName
		unwatchedMenu = "In %s [I]Ungesehen[/I]" % control.addonName
		from resources.lib import seriesqueue
		queue_meta = json.loads(self.sysmeta)
		queue_key = seriesqueue.make_key(queue_meta)
		queue_items = []
		pos = 0
		for i in items:
			try:
				meta = json.loads(self.sysmeta)
				meta.pop('episodes', None)
				sysmeta = json.loads(self.sysmeta)
				sysmeta.pop('episodes', None)
				season = i['season']
				episode = i['episode']

				systitle = sysmeta['title']
				sysname = systitle + ' S%02dE%02d' % (season, episode)
				sysmeta.update({'episode': episode})
				sysmeta.update({'sysname': sysname})

				_sysmeta = control.quote_plus(json.dumps(sysmeta))

				if 'title' in i and i['title']: label = '%sx%02d  %s' % (season, episode, i['title'])
				else: label = '%sx%02d  Episode %s' % (season, episode,  episode)
				if datetime.datetime(*(time.strptime(i['premiered'], "%Y-%m-%d")[0:6])) > datetime.datetime.now():
					label = '[COLOR=red][I]{}[/I][/COLOR]'.format(label)  # ffcc0000

				poster = i['poster'] if 'poster' in i and 'http' in i['poster'] else sysmeta['poster']
				fanart = sysmeta['fanart'] if 'fanart' in sysmeta else addonFanart
				plot = ''
				if 'plot' in i and len(i['plot']) > 50:
					plot = i['plot']
					sysmeta.update({'plot': plot})

				#plot = i['plot'] if 'plot' in i and len(i['plot']) > 50 else ''  #sysmeta['plot']
				plot = '[COLOR blue]%s%sStaffel: %s   Episode: %s[/COLOR]%s%s' % (meta['title'], "\n",i['season'], i['episode'], "\n\n", plot)

				meta.update({'poster': poster})
				meta.update({'fanart': fanart})
				meta.update({'plot': plot})
				if 'premiered' in i and i['premiered']: meta.update({'premiered': i['premiered']})

				item = control.item(label=label, offscreen=True)
				item.setArt({'poster': poster, 'banner': addonBanner})
				if settingFanart == 'true': item.setProperty('Fanart_Image', fanart)

				cm = []
				queue_index = len(queue_items)
				queue_items.append(dict(sysmeta))
				cm.append((
					'Ab hier abspielen',
					'RunPlugin(%s?action=playFromHere&queue=%s&index=%s)' % (
						sysaddon,
						control.quote_plus(queue_key),
						queue_index,
					),
				))
				try:
					playcount = i['playcount'] if sysmeta['playcount'] == 0 else 1
					if playcount == 1:
						cm.append((unwatchedMenu, 'RunPlugin(%s?action=UpdatePlayCount&meta=%s&playCount=0)' % (sysaddon, _sysmeta)))
						meta.update({'playcount': 1, 'overlay': 7})
						sysmeta.update({'playcount': 1, 'overlay': 7})
						pos = episode + 1
						if len(items) == episode: pos = episode
					else:
						cm.append((watchedMenu, 'RunPlugin(%s?action=UpdatePlayCount&meta=%s&playCount=1)' % (sysaddon, _sysmeta)))
						meta.update({'playcount': 0, 'overlay': 6})
						sysmeta.update({'playcount': 0, 'overlay': 6})
				except:
					pass
				cm.append(('Einstellungen', 'RunPlugin(%s?action=addonSettings)' % sysaddon))
				item.addContextMenuItems(cm)

				sysmeta = control.quote_plus(json.dumps(sysmeta))
				url = '%s?action=play&sysmeta=%s' % (sysaddon, sysmeta)

				aActors = []
				if 'cast' in meta and meta['cast']: aActors = meta['cast']

				# # # remove unsupported InfoLabels
				meta.pop('cast', None)
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

				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=False)
			except:
				pass

		seriesqueue.store(queue_key, queue_items)
		control.content(syshandle, 'movies')	# 'episodes' cpu last sehr hoch / movies
		if control.skin == 'skin.estuary':
			control.execute('Container.SetViewMode(%s)' % str(55))

		control.plugincategory(syshandle, control.addonVersion)
		control.endofdirectory(syshandle, cacheToDisc=False)
		control.sleep(0.2)

		# setzt Auswahl nach letzte als gesehen markierte Episode
		if control.getSetting('status.position')== 'true':
			from resources.lib.utils import setPosition
			setPosition(pos, __name__)

