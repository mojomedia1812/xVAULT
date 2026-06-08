
import os, re
import xbmcaddon
from xbmcvfs import translatePath
from resources.lib.utils import kill, remove_dir

addonInfo = xbmcaddon.Addon().getAddonInfo
addonId = addonInfo('id')
addonVersion = addonInfo('version')
root_path = translatePath(os.path.join('special://home/addons/', '%s'))
addon_data_path = translatePath(os.path.join('special://home/userdata/addon_data/', '%s'))
userdata_path = translatePath(os.path.join('special://home/userdata/', '%s'))

def starter2():
    pass