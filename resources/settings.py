import sys
from xbmcgui import NOTIFICATION_INFO, Dialog

from resources.lib import control
from scrapers import getProviderModuleNames

dialog = Dialog()
name = control.addonInfo('name')


def window(title='', content='', filename=''):
    import xbmc, xbmcgui, time, os
    if content == '' and filename == '': return
    if content == '' and filename != '':
        file = os.path.join(control.py2_decode(control.translatePath(control.addonInfo('path'))), 'resources', filename)
        if sys.version_info[0] == 2:
            with open(file, 'r') as f:
                content = f.read()
        else:
            with open(file, 'rb') as f:
                content = f.read().decode('utf8')

        window_id = 10147
        control_label = 1
        control_textbox = 5
        timeout = 1
        xbmc.executebuiltin("ActivateWindow({})".format(window_id))
        w = xbmcgui.Window(window_id)
        start_time = time.time()
        while (not xbmc.getCondVisibility("Window.IsVisible({})".format(window_id)) and
               time.time() - start_time < timeout):
            xbmc.sleep(100)
        w.getControl(control_label).setLabel(title)
        w.getControl(control_textbox).setText(content)


def run(params):
    action = params.get('subaction')

    if action == "Defaults":
        dialog.notification(name , 'Einstellungen wurden übernommen', NOTIFICATION_INFO, 500, sound=False)
        sourceList = getProviderModuleNames()
        for i in sourceList:
            source_setting = 'provider.' + i
            value = control.getSettingDefault(source_setting)
            control.setSetting(source_setting, value)

    elif action == "toggleAll":
        dialog.notification(name , 'Einstellungen wurden übernommen', NOTIFICATION_INFO, 500, sound=False)
        sourceList = getProviderModuleNames()
        for i in sourceList:
            source_setting = 'provider.' + i
            control.setSetting(source_setting, params['setting'])

    elif action == "defaultsGerman":
        sourceList = getProviderModuleNames()
        for i in sourceList:
            source_setting = 'provider.' + i
            value = control.getSettingDefault(source_setting)
            control.setSetting(source_setting, value)

    elif action == "toggleGerman":
        sourceList = getProviderModuleNames()
        for i in sourceList:
            source_setting = 'provider.' + i
            control.setSetting(source_setting, params['setting'])

    elif action == "downloadInfo":
        window('Hilfe zum Syntax für den Ordnerpfad', '', 'downloadinfo.txt')
