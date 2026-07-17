

#2021-07-20
#edit 2024-12-04

import os, sys
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
## from six
## iteritems = lambda d: ((hasattr(d, 'iteritems') and d.iteritems) or d.items)()

# xbmcaddon
Addon = xbmcaddon.Addon()
addonInfo = xbmcaddon.Addon().getAddonInfo
addonId = addonInfo('id')	   # 'plugin.video.xvault'
addonName = addonInfo('name')   # 'xVAULT'
addonVersion = addonInfo('version')
addonPath = translatePath(addonInfo('path'))   # 'C:\\Program Files\\Kodi21\\portable_data\\addons\\plugin.video.xvault\\'
addonProfilePath = translatePath(addonInfo('profile')) # 'C:\\Program Files\\Kodi21\\portable_data\\userdata\\addon_data\\plugin.video.xvault\\'

# dataPath = py2_decode(translatePath(addonInfo('profile')))

#cachePath = os.path.join(addonProfilePath, "cache")
#if not exists(cachePath): os.makedirs(cachePath)

setSetting = xbmcaddon.Addon().setSetting
_getSetting = xbmcaddon.Addon().getSetting

def getSetting(Name, default=''):
	result = _getSetting(Name)
	if result:
		return result
	else:
		return default

# xbmc
skin = xbmc.getSkinDir()
infoLabel = xbmc.getInfoLabel
condVisibility = xbmc.getCondVisibility
playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
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
player = xbmc.Player()
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
window = xbmcgui.Window(10000)
currentWindowId = xbmcgui.Window(xbmcgui.getCurrentWindowId())
item = xbmcgui.ListItem
dialog = xbmcgui.Dialog()
progressDialog = xbmcgui.DialogProgress()
progressDialogBG = xbmcgui.DialogProgressBG()

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
		login = getSetting('serienstream.user')
		password = getSetting('serienstream.pass')
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
		SettingFile = os.path.join(xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile')), "settings.xml")
		if xbmcvfs.exists(SettingFile): xbmcvfs.delete(SettingFile)
		# PROFIL_RELOAD = os.path.join(xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile')).decode('utf-8'), "profil_reload")
		# open(PROFIL_RELOAD, "w+").write('Profil reload')
		setSetting(id='serienstream.user', value=login)
		setSetting(id='serienstream.pass', value=password)
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
