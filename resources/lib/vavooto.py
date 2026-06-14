# edit 2026-06-14

import xbmc

from resources.lib import control
from resources.lib import dependencies


ADDON_ID = 'plugin.video.vavooto'
MIN_VERSION = '2026.05.03'


def open_root():
    if _ensure_installed():
        _open_plugin('plugin://%s/' % ADDON_ID)


def open_favorites():
    if _ensure_installed():
        _open_plugin('plugin://%s/?action=favchannels' % ADDON_ID)


def open_settings():
    if _ensure_installed():
        control.openSettings(id=ADDON_ID)


def make_m3u():
    if _ensure_installed():
        control.execute('RunPlugin(plugin://%s/?action=makem3u)' % ADDON_ID)


def _ensure_installed():
    if _has_addon():
        return True

    install = control.yesnoDialog(
        'VAVOO.TO ist nicht installiert.',
        'Jetzt aus dem Michaz Repository installieren?',
        ''
    )
    if not install:
        return False

    control.infoDialog('Installiere VAVOO.TO...', icon='INFO', time=3000)
    if dependencies.install_addon(ADDON_ID, MIN_VERSION):
        control.infoDialog('VAVOO.TO ist installiert.', icon='INFO', time=3000)
        return True

    control.infoDialog('VAVOO.TO konnte nicht installiert werden.', icon='ERROR', time=7000)
    return False


def _open_plugin(plugin_url):
    control.execute('ActivateWindow(Videos,%s,return)' % plugin_url)


def _has_addon():
    try:
        return bool(xbmc.getCondVisibility('System.HasAddon(%s)' % ADDON_ID))
    except Exception:
        return False
