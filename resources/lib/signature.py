"""Optional local startup signature, once per visit to the add-on."""
import os
import threading
import time

import xbmc
from resources.lib import control, log_utils

SESSION = 'plugin.video.xvault.signature.session'
RUNNING = 'plugin.video.xvault.signature.running'
_watcher = None


def observe_navigation():
    """Leaving xVAULT arms the next start; navigating back inside does not."""
    if control.window.getProperty(RUNNING):
        return
    # Kodi briefly clears the container while returning from fullscreen or
    # rebuilding a directory. Those transitions are not an add-on exit.
    if any(control.condVisibility(condition) for condition in (
            'Window.IsActive(fullscreenvideo)', 'Window.IsActive(visualisation)',
            'Window.IsActive(busydialog)', 'Window.IsActive(busydialognocancel)',
            'Container.IsUpdating')):
        return
    path = control.infoLabel('Container.FolderPath').lower()
    inside = path.startswith(('plugin://plugin.video.xvault/', 'plugin://plugin.video.xvault?'))
    media_window = control.condVisibility('Window.IsActive(videos)') or control.condVisibility('Window.IsActive(music)')
    if not inside or not media_window:
        control.window.clearProperty(SESSION)


def start_monitor():
    global _watcher
    if _watcher is not None and _watcher.is_alive():
        return
    def watch():
        monitor = xbmc.Monitor()
        while not monitor.abortRequested():
            try:
                observe_navigation()
            except Exception:
                pass
            monitor.waitForAbort(.5)
    _watcher = threading.Thread(target=watch, name='xvault-signature-navigation', daemon=True)
    _watcher.start()


class SignaturePlayer(xbmc.Player):
    def __init__(self):
        super(SignaturePlayer, self).__init__()
        self.finished = False

    def onPlayBackStopped(self): self.finished = True
    def onPlayBackEnded(self): self.finished = True
    def onPlayBackError(self): self.finished = True


def play_on_start():
    if control.window.getProperty(SESSION) or control.window.getProperty(RUNNING):
        return False
    # Do not start for a background directory query or replace another video/radio.
    if not (control.condVisibility('Window.IsActive(videos)') or control.condVisibility('Window.IsActive(music)')):
        return False
    control.window.setProperty(SESSION, 'true')
    if control.getSetting('signature.enabled', 'true') == 'false' or xbmc.Player().isPlaying():
        return False
    path = os.path.join(control.addonPath, 'resources', 'media', 'signature.mp4')
    if not os.path.isfile(path):
        log_utils.log('Signature: lokales Startvideo fehlt', log_utils.LOGWARNING)
        return False
    control.window.setProperty(RUNNING, 'true')
    try:
        item = control.item(label='xVAULT Signature', path=path, offscreen=True)
        item.setInfo('video', {'title': 'xVAULT Signature', 'mediatype': 'video'})
        item.setContentLookup(False)
        item.setProperty('IsPlayable', 'true')
        player = SignaturePlayer()
        player.play(path, item)
        monitor = xbmc.Monitor()
        deadline = time.monotonic() + 25
        while not player.finished and not monitor.abortRequested() and time.monotonic() < deadline:
            if player.isPlaying() and player.getPlayingFile() != path:
                break  # User started another item; leave that playback alone.
            monitor.waitForAbort(.1)
        return True
    except Exception as exc:
        log_utils.log('Signature: Startvideo konnte nicht abgespielt werden (%s)' % type(exc).__name__, log_utils.LOGWARNING)
        return False
    finally:
        control.window.clearProperty(RUNNING)
