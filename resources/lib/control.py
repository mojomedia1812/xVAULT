

#2021-07-20
#edit 2024-12-04

import os, sys, atexit
import xml.etree.ElementTree as ET
import xbmc, xbmcplugin, xbmcaddon, xbmcgui, xbmcvfs
from six import iteritems

is_python2 = sys.version_info.major == 2

if is_python2:
	#from xbmc import translatePath
	from HTMLParser import HTMLParser
	unescape = HTMLParser().unescape
	from urlparse import urlparse, parse_qsl, urljoin, parse_qs, urlsplit
	from urllib import quote_plus, unquote_plus, quote, unquote, urlencode, urlretrieve
	from urllib2 import Request, urlopen
else:
	#from xbmcvfs import translatePath
	from html import unescape
	from html.parser import HTMLParser
	from urllib.parse import urlparse, quote_plus, parse_qsl, unquote_plus, urljoin, quote, unquote, urlencode, parse_qs, urlsplit
	from urllib.request import Request, urlopen, urlretrieve

def translatePath(*args):
	if is_python2: return xbmc.translatePath(*args).decode("utf-8")
	else: return xbmcvfs.translatePath(*args)

def exists(*args):
	return os.path.exists(translatePath(*args))

def py2_decode(value):
	if is_python2:
		try: return value.decode('utf-8')
		except: return value
	return value

def py2_encode(value):
	if is_python2:
		try: return value.encode('utf-8')
		except: return value
	return value

def _addonRootPath():
	return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

def _addonAssetPath(base, value):
	value = str(value or '').strip()
	if not value:
		return ''
	if value.startswith('special://') or value.startswith('http://') or value.startswith('https://') or os.path.isabs(value):
		return value
	return os.path.join(base, value)

def _readAddonInfo():
	base = _addonRootPath()
	info = {'id': 'plugin.video.xvault', 'name': 'xVAULT', 'version': '', 'path': base}
	try:
		root = ET.parse(os.path.join(base, 'addon.xml')).getroot()
		for key in ('id', 'name', 'version'):
			value = root.attrib.get(key)
			if value:
				info[key] = value
		assets = root.find("./extension[@point='xbmc.addon.metadata']/assets")
		if assets is None:
			assets = root.find('.//assets')
		if assets is not None:
			for key in ('icon', 'fanart', 'banner'):
				node = assets.find(key)
				if node is not None and node.text:
					info[key] = _addonAssetPath(base, node.text)
	except:
		pass
	info['profile'] = translatePath('special://profile/addon_data/%s/' % info.get('id', 'plugin.video.xvault'))
	return info
## from six
## iteritems = lambda d: ((hasattr(d, 'iteritems') and d.iteritems) or d.items)()

class _KodiLazyObject(object):
	def __init__(self, factory, cleanup=None):
		self._factory = factory
		self._cleanup = cleanup
		self._obj = None

	def _get(self):
		if self._obj is None:
			self._obj = self._factory()
		return self._obj

	def __getattr__(self, name):
		if self._cleanup and name == self._cleanup:
			return self._release_call
		return getattr(self._get(), name)

	def __bool__(self):
		return True

	__nonzero__ = __bool__

	def _release_call(self, *args, **kwargs):
		obj = self._obj
		self._obj = None
		if obj is None:
			return None
		try:
			return getattr(obj, self._cleanup)(*args, **kwargs)
		except:
			return None

	def release(self):
		if self._cleanup:
			self._release_call()
			return
		self._obj = None


class _KodiDynamicObject(object):
	def __init__(self, factory):
		self._factory = factory

	def __getattr__(self, name):
		return getattr(self._factory(), name)

	def __bool__(self):
		return True

	__nonzero__ = __bool__


_kodi_lazy_objects = []


def _lazy(factory, cleanup=None):
	obj = _KodiLazyObject(factory, cleanup)
	_kodi_lazy_objects.append(obj)
	return obj


def _dynamic(factory):
	return _KodiDynamicObject(factory)


# xbmcaddon
_ADDON_INFO = _readAddonInfo()
addonId = _ADDON_INFO.get('id', 'plugin.video.xvault')


def addonInfo(key):
	value = _ADDON_INFO.get(key)
	if value:
		return value
	return ''


addonName = addonInfo('name')   # 'xVAULT'
addonVersion = addonInfo('version')
addonPath = translatePath(addonInfo('path'))   # 'C:\\Program Files\\Kodi21\\portable_data\\addons\\plugin.video.xvault\\'
addonProfilePath = translatePath(addonInfo('profile')) # 'C:\\Program Files\\Kodi21\\portable_data\\userdata\\addon_data\\plugin.video.xvault\\'

# dataPath = py2_decode(translatePath(addonInfo('profile')))

#cachePath = os.path.join(addonProfilePath, "cache")
#if not exists(cachePath): os.makedirs(cachePath)

_settings_cache = {}

def _readSettingsXml(path, defaults=False):
	values = {}
	if not path or not os.path.exists(path):
		return values
	try:
		root = ET.parse(path).getroot()
		for node in root.findall('.//setting'):
			setting_id = node.attrib.get('id')
			if not setting_id:
				continue
			if defaults:
				value = node.attrib.get('default')
				if value is None:
					value = node.attrib.get('value')
				if value is None and node.text is not None:
					value = node.text
			else:
				value = node.attrib.get('value')
				if value is None and node.text is not None:
					value = node.text
			if value is not None:
				values[setting_id] = str(value).strip()
	except:
		pass
	return values

def _settingsValues(path, defaults=False):
	try:
		mtime = os.path.getmtime(path)
	except:
		mtime = None
	cache_key = (path, bool(defaults))
	cached = _settings_cache.get(cache_key)
	if cached and cached.get('mtime') == mtime:
		return cached.get('values', {})
	values = _readSettingsXml(path, defaults)
	_settings_cache[cache_key] = {'mtime': mtime, 'values': values}
	return values

def _invalidateSettingsCache():
	try:
		_settings_cache.clear()
	except:
		pass

def _settingsXmlPath():
	return os.path.join(addonProfilePath, 'settings.xml')

def _settingsRoot(path):
	try:
		if path and os.path.exists(path):
			root = ET.parse(path).getroot()
			if root.tag == 'settings':
				return root
	except:
		pass
	return ET.Element('settings', {'version': '2'})

def _writeSettingsRoot(root, path):
	tmp_path = ''
	try:
		directory = os.path.dirname(path)
		if directory and not os.path.exists(directory):
			os.makedirs(directory)
		try:
			if hasattr(ET, 'indent'):
				ET.indent(root, space='    ')
		except:
			pass
		tmp_path = path + '.tmp'
		ET.ElementTree(root).write(tmp_path, encoding='utf-8', xml_declaration=False)
		os.replace(tmp_path, path)
		return True
	except:
		try:
			if tmp_path and os.path.exists(tmp_path):
				os.remove(tmp_path)
		except:
			pass
		return False

def _writeSettingValue(setting_id, value):
	if not setting_id:
		return False
	path = _settingsXmlPath()
	root = _settingsRoot(path)
	root.attrib.setdefault('version', '2')
	target = None
	for node in list(root.findall('setting')):
		if node.attrib.get('id') != setting_id:
			continue
		if target is None:
			target = node
		else:
			root.remove(node)
	if target is None:
		target = ET.SubElement(root, 'setting', {'id': setting_id})
	else:
		target.attrib.clear()
		target.attrib['id'] = setting_id
	for attr in ('default', 'value'):
		if attr in target.attrib:
			del target.attrib[attr]
	if value == '':
		target.text = None
	else:
		target.text = value
	return _writeSettingsRoot(root, path)

def setSetting(id=None, value=None):
	value = '' if value is None else str(value)
	try:
		if getSetting(id) == value:
			return True
	except Exception:
		pass
	result = _writeSettingValue(id, value)
	if result:
		_invalidateSettingsCache()
	return result

def getSetting(Name, default=''):
	result = _settingsValues(_settingsXmlPath()).get(Name)
	if result:
		return result
	result = _settingsValues(os.path.join(addonPath, 'resources', 'settings.xml'), defaults=True).get(Name)
	if result:
		return result
	return default

class _AddonSettingsProxy(object):
	def getAddonInfo(self, key):
		return addonInfo(key)

	def getSetting(self, key):
		return getSetting(key)

	def setSetting(self, key, value=''):
		return setSetting(key, value)

	def setSettingString(self, key, value=''):
		return setSetting(key, value)

	def setSettingBool(self, key, value=False):
		return setSetting(key, 'true' if value else 'false')


Addon = _AddonSettingsProxy()

# xbmc
skin = xbmc.getSkinDir()
infoLabel = xbmc.getInfoLabel
condVisibility = xbmc.getCondVisibility
playlist = _lazy(lambda: xbmc.PlayList(xbmc.PLAYLIST_VIDEO))
keyboard = xbmc.Keyboard


# kb = xbmc.Keyboard('default', 'heading', True)
# kb.setDefault('password') # optional
# kb.setHeading('Enter password') # optional
# kb.setHiddenInput(True) # optional
# kb.doModal()
# if (kb.isConfirmed()):
#   text = kb.getText()


execute = xbmc.executebuiltin
executebuiltin  = xbmc.executebuiltin
player = _dynamic(lambda: xbmc.Player())
abortRequested = xbmc.Monitor().abortRequested()
jsonrpc = xbmc.executeJSONRPC
getInfoLabel = xbmc.getInfoLabel


# xbmcvfs
listDir = xbmcvfs.listdir
openFile = xbmcvfs.File
makeFile = xbmcvfs.mkdir
mkDir = xbmcvfs.mkdir
delete = xbmcvfs.delete
# exists = xbmcvfs.exists

# xbmcplugin
resolveUrl = xbmcplugin.setResolvedUrl
addItem = xbmcplugin.addDirectoryItem
endofdirectory = xbmcplugin.endOfDirectory
content = xbmcplugin.setContent
plugincategory = xbmcplugin.setPluginCategory

def sortLabel(syshandle):
	xbmcplugin.addSortMethod(syshandle, xbmcplugin.SORT_METHOD_LABEL)

def trailerLabel():
	"""Return localised context menu label for the trailer action."""
	try:
		lang = xbmc.getLanguage(xbmc.ISO_639_1).lower()[:2]
	except Exception:
		lang = 'en'
	return 'Trailer ansehen' if lang == 'de' else 'Watch Trailer'

def hasTrailerPlayer():
	"""Always True — IMDB provides direct MP4 playback without any YouTube player.
	Context menu 'Trailer ansehen' is shown for every item."""
	return True

# xbmcgui
window = _dynamic(lambda: xbmcgui.Window(10000))
currentWindowId = _dynamic(lambda: xbmcgui.Window(xbmcgui.getCurrentWindowId()))
item = xbmcgui.ListItem
dialog = _dynamic(lambda: xbmcgui.Dialog())
progressDialog = _lazy(lambda: xbmcgui.DialogProgress(), 'close')
progressDialogBG = _lazy(lambda: xbmcgui.DialogProgressBG(), 'close')

dataPath = py2_decode(translatePath(addonInfo('profile')))

bookmarksFile = os.path.join(addonProfilePath, 'bookmarks.db')
settingsFile = os.path.join(addonPath, 'resources', 'settings.xml')

def addonIcon():
	return addonInfo('icon')

def addonFanart():
	return addonInfo('fanart')

def artPath():
	return os.path.join(translatePath(addonInfo('path')), 'resources', 'media')

def addonThumb():
	return os.path.join(artPath(), 'poster.png')

def addonPoster():
	return os.path.join(artPath(), 'poster.png')

def addonBanner():
	return os.path.join(artPath(), 'banner.png')

def playlistObject():
	try:
		return playlist._get()
	except:
		return xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

#def addonFanart():
#	addonXml = os.path.join(py2_decode(translatePath(addonInfo('path'))), 'addon.xml')
#	import xml.dom.minidom as minidom
#	doc = minidom.parse(addonXml)
#	# with open(addonXml, 'r') as f: content = f.read()
#	# fanart = re.search('fanart>([^<]+)', content).group(1)
#	fanart = doc.getElementsByTagName('fanart')[0].firstChild.nodeValue
#	fanart = os.path.join(addonInfo('path'), os.path.normpath(fanart))
#	if os.path.exists(fanart):
#		return fanart
#	return

def addonNext():
	return os.path.join(artPath(), 'next.png')

def addonNoPicture():
	return os.path.join(artPath(), 'no-picture.png')

def isBlockedProviderArt(url):
	try:
		parsed = urlparse(str(url).split('|', 1)[0])
		host = (parsed.netloc or '').split('@')[-1].split(':', 1)[0].lower()
		path = (parsed.path or '').lower()
		if host in ('s.to', 'www.s.to'):
			return True
		if host in ('serienstream.to', 'www.serienstream.to') or host.endswith('.serienstream.to'):
			return path.startswith('/media/images/')
	except:
		pass
	return False

def _isLocalArt(value):
	try:
		if str(value).startswith('special://'):
			return exists(value)
		return os.path.exists(value)
	except:
		return False

def selectArtwork(candidates, fallback=''):
	for candidate in candidates:
		try:
			value = py2_decode(candidate)
		except:
			value = candidate
		value = str(value or '').strip()
		if not value:
			continue
		if isBlockedProviderArt(value):
			continue
		if value.startswith('http://') or value.startswith('https://') or _isLocalArt(value):
			return value
	return fallback

def posterArtwork(*candidates):
	return selectArtwork(candidates, addonPoster())

def fanartArtwork(*candidates):
	return selectArtwork(candidates, addonFanart())

def sanitizeMetaArtwork(meta):
	if not isinstance(meta, dict):
		return meta
	poster = posterArtwork(meta.get('cover_url'), meta.get('poster'))
	fanart = fanartArtwork(meta.get('backdrop_url'), meta.get('fanart'))
	meta.update({'poster': poster, 'cover_url': poster, 'fanart': fanart, 'backdrop_url': fanart})
	return meta

def infoDialog(message, heading=addonInfo('name'), icon='', time=3000, sound=False):
	if icon == '': icon = addonIcon()
	elif icon == 'INFO': icon = xbmcgui.NOTIFICATION_INFO
	elif icon == 'WARNING': icon = xbmcgui.NOTIFICATION_WARNING
	elif icon == 'ERROR': icon = xbmcgui.NOTIFICATION_ERROR
	dialog.notification(heading, message, icon, time, sound=sound)

def yesnoDialog(line1, line2, line3, heading=addonInfo('name'), nolabel='', yeslabel=''):
	if is_python2:
		return dialog.yesno(heading, line1, line2, line3, nolabel, yeslabel)
	else:
		return dialog.yesno(heading, line1+'\n'+line2+'\n'+line3, nolabel, yeslabel)

def selectDialog(list, heading=addonInfo('name')):
	return dialog.select(heading, list)

def showparentdiritems():
	if not 'false' in xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"Settings.GetSettingValue", "params":{"setting":"filelists.showparentdiritems"}}'):
		return True
	else:
		return False

# Modified `sleep` command that honors a user exit request
def sleep(time):
	monitor = xbmc.Monitor()
	while time > 0 and not monitor.abortRequested():
		monitor.waitForAbort(min(1, time))
		time = time - 1

def getKodiVersion():
	return xbmc.getInfoLabel("System.BuildVersion").split(".")[0]

def busy():
	if int(getKodiVersion()) >= 18:
		return execute('ActivateWindow(busydialognocancel)')
	else:
		return execute('ActivateWindow(busydialog)')

def idle():
	if int(getKodiVersion()) >= 18:
		return execute('Dialog.Close(busydialognocancel)')
	else:
		return execute('Dialog.Close(busydialog)')

def visible():
	if int(getKodiVersion()) >= 18 and xbmc.getCondVisibility('Window.IsActive(busydialognocancel)') == 1:
		return True
	return xbmc.getCondVisibility('Window.IsActive(busydialog)') == 1

def reload_profile():
	profil = xbmc.getInfoLabel('System.ProfileName')
	sleep(500)
	#if profil:
	xbmc.executebuiltin('LoadProfile(' + profil + ',prompt)')

def openSettings(query=None, id=addonInfo('id')):
	try:
		idle()
		execute('Addon.OpenSettings(%s)' % id)
		if query is None:
			raise Exception()
		if len(str(query).split('.')) == 1:
			c = query
			f = 0
		else:  c, f = str(query).split('.')
		if int(getKodiVersion()) >= 21:
			execute('SetFocus(%i)' % (int(c)-200))
			if int(f):execute('SetFocus(%i)' % (int(f)-180))
		elif int(getKodiVersion()) >= 18:
			execute('SetFocus(%i)' % (int(c)-100))			  #   k19: -100
			if int(f):execute('SetFocus(%i)' % (int(f)-80))	 #   k19: -80
		else:
			execute('SetFocus(%i)' % (int(c) + 100))
			if int(f):execute('SetFocus(%i)' % (int(f) + 200))
	except:
		return

def resetSettings():
	yes = yesnoDialog("Zurücksetzen der Settings (außer Konten)", 'und einem abschließenden Reload vom Profil', 'Sind Sie sicher?')
	if not yes: return
	try:
		flimmerstube_login = getSetting('flimmerstube.user')
		flimmerstube_password = getSetting('flimmerstube.pass')
		aniworld_login = getSetting('aniworld.user')
		aniworld_password = getSetting('aniworld.pass')
		os_user = getSetting('subtitles.os_user')
		os_pass = getSetting('subtitles.os_pass')
		tmdb = getSetting('api.tmdb')
		trakt_enabled = getSetting('trakt.enabled')
		trakt_sync_watched = getSetting('trakt.sync.watched')
		trakt_scrobble = getSetting('trakt.scrobble.enabled')
		trakt_status = getSetting('trakt.status')
		trakt_last_sync = getSetting('trakt.last_sync_at')
		trakt_username = getSetting('trakt.username')
		trakt_access_token = getSetting('trakt.access_token')
		trakt_refresh_token = getSetting('trakt.refresh_token')
		trakt_token_expires_at = getSetting('trakt.token_expires_at')
		fanart = getSetting('api.fanart.tv')
		debug = getSetting('status.debug')
		SettingFile = os.path.join(addonProfilePath, "settings.xml")
		if xbmcvfs.exists(SettingFile): xbmcvfs.delete(SettingFile)
		setSetting(id='flimmerstube.user', value=flimmerstube_login)
		setSetting(id='flimmerstube.pass', value=flimmerstube_password)
		setSetting(id='aniworld.user', value=aniworld_login)
		setSetting(id='aniworld.pass', value=aniworld_password)
		setSetting(id='subtitles.os_user', value=os_user)
		setSetting(id='subtitles.os_pass', value=os_pass)
		setSetting(id='api.tmdb', value=tmdb)
		setSetting(id='trakt.enabled', value=trakt_enabled)
		setSetting(id='trakt.sync.watched', value=trakt_sync_watched)
		setSetting(id='trakt.scrobble.enabled', value=trakt_scrobble)
		setSetting(id='trakt.status', value=trakt_status)
		setSetting(id='trakt.last_sync_at', value=trakt_last_sync)
		setSetting(id='trakt.username', value=trakt_username)
		setSetting(id='trakt.access_token', value=trakt_access_token)
		setSetting(id='trakt.refresh_token', value=trakt_refresh_token)
		setSetting(id='trakt.token_expires_at', value=trakt_token_expires_at)
		setSetting(id='api.fanart.tv', value=fanart)
		setSetting(id='status.debug', value=debug)
		return True
	except:
		return

def getSettingDefault(id):
	import re
	try:
		settings = open(settingsFile, 'r')
		value = ' '.join(settings.readlines())
		value.strip('\n')
		settings.close()
		value = re.findall(r'id=\"%s\".*?default=\"(.*?)\"' % (id), value)[0]
		return value
	except:
		return None

def inAdvancedsettings(word=''):
	advancedsettings = py2_decode(os.path.join(translatePath('special://userdata/'), "advancedsettings.xml"))
	if exists(advancedsettings):
		with open(advancedsettings, 'r') as file:
			content = file.read()
			if word in content: return True
	return False


def cleanupKodiObjects():
	try:
		idle()
	except:
		pass
	try:
		sources_module = sys.modules.get('resources.lib.sources')
		if sources_module is not None and hasattr(sources_module, '_RESOLVEURL_MODULE'):
			setattr(sources_module, '_RESOLVEURL_MODULE', None)
	except:
		pass
	try:
		for module_name in list(sys.modules.keys()):
			if module_name == 'resolveurl' or module_name.startswith('resolveurl.'):
				sys.modules.pop(module_name, None)
	except:
		pass
	for obj in reversed(_kodi_lazy_objects):
		try:
			obj.release()
		except:
			pass
	try:
		import gc
		gc.collect()
	except:
		pass


try:
	atexit.register(cleanupKodiObjects)
except:
	pass
