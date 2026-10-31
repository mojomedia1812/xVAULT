"""Open Kodi's native music visualisation once the requested radio is audible."""
import json
import time
import uuid

import xbmc
import xbmcaddon
import xbmcgui

PENDING = 'xvault.radio.visualisation.pending'
VISUALIZERS = ('visualization.xvault',)
SETTING = 'musicplayer.visualisation'
_player = None


def choice():
    try:
        return int(xbmcaddon.Addon('plugin.video.xvault').getSetting('radio.visualisation') or '0')
    except ValueError:
        return 0


def window():
    return xbmcgui.Window(10000)


def rpc(method, params):
    data = json.loads(xbmc.executeJSONRPC(json.dumps(dict(jsonrpc='2.0', id=91, method=method, params=params))))
    if data.get('error'):
        raise RuntimeError('Kodi visualisation command failed')
    return data.get('result', {})


def selected():
    if xbmcaddon.Addon('plugin.video.xvault').getSetting('radio.enabled') == 'false':
        return ''
    return VISUALIZERS[0] if choice() == 0 else ''


def arm(target, station_id=None):
    """No network or add-on installation on the playback-critical path."""
    win = window()
    win.setProperty('xvault.radio.next', json.dumps(dict(target=target, station_id=station_id, created=time.time())))
    win.clearProperty(PENDING)
    visualizer = selected()
    if not visualizer:
        return
    try:
        addon = rpc('Addons.GetAddonDetails', {'addonid': visualizer, 'properties': ['enabled']}).get('addon', {})
    except RuntimeError:
        addon = {}
    if not addon.get('enabled'):
        xbmcgui.Dialog().notification('xVAULT Radio', 'Visualisierung nicht verfügbar: ' + visualizer.split('.')[-1],
                                      xbmcgui.NOTIFICATION_INFO, 5000)
        return
    preset = None
    if station_id:
        from resources.lib.radio_tools import preset as station_preset
        preset = station_preset(station_id)
    win.setProperty(PENDING, json.dumps(dict(token=uuid.uuid4().hex, target=target, preset=preset,
                                           visualizer=visualizer,
                                           created=time.time())))


def pending():
    try:
        data = json.loads(window().getProperty(PENDING))
        if (not isinstance(data, dict) or data.get('visualizer') not in VISUALIZERS
                or not isinstance(data.get('target'), str)
                or not 0 <= time.time() - float(data['created']) < 120):
            return None
        return data
    except (ValueError, TypeError, KeyError):
        return None


class RadioPlayer(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.active = None

    def restore(self):
        active, self.active = self.active, None
        if not active:
            return
        try:
            current = rpc('Settings.GetSettingValue', {'setting': SETTING}).get('value', '')
            # Preserve a deliberate visualizer change through Kodi's own controls.
            if current == active['visualizer']:
                rpc('Settings.SetSettingValue', {'setting': SETTING, 'value': active['previous']})
            if 'previous_preset' in active:
                addon = xbmcaddon.Addon(active['visualizer'])
                if addon.getSetting('preset') == str(active.get('preset')):
                    addon.setSetting('preset', active['previous_preset'])
        except Exception as exc:
            xbmc.log('xVAULT radio visualisation restore: ' + type(exc).__name__, xbmc.LOGWARNING)

    def onAVStarted(self):
        try:
            target = self.getPlayingFile().split('|', 1)[0]
            try:
                radio = json.loads(window().getProperty('xvault.radio.next') or '{}')
                if self.isPlayingAudio() and radio.get('target') == target and 0 <= time.time() - radio.get('created', 0) < 120:
                    window().setProperty('xvault.radio.current', json.dumps(radio))
                    window().clearProperty('xvault.radio.next')
                    sleep = json.loads(window().getProperty('xvault.radio.sleep') or '{}')
                    if sleep and sleep.get('target') != target:
                        window().clearProperty('xvault.radio.sleep')
                        xbmc.executebuiltin('CancelAlarm(xvault_radio_sleep,true)')
                else:
                    current = json.loads(window().getProperty('xvault.radio.current') or '{}')
                    if current.get('target') != target:
                        window().clearProperty('xvault.radio.current')
            except (ValueError, TypeError):
                pass
            if not selected():
                window().clearProperty(PENDING)
                self.restore()
                return
            request = pending()
            if not self.isPlayingAudio() or not request or target != request['target']:
                if self.active and target != self.active['target']:
                    self.restore()
                return
            window().clearProperty(PENDING)
            self.restore()
            previous = rpc('Settings.GetSettingValue', {'setting': SETTING}).get('value', '')
            self.active = dict(request, previous=previous)
            preset = request.get('preset')
            if isinstance(preset, int) and 0 <= preset < 7:
                addon = xbmcaddon.Addon(request['visualizer'])
                self.active['previous_preset'] = addon.getSetting('preset')
                addon.setSetting('preset', str(preset))
            result = rpc('Settings.SetSettingValue', {'setting': SETTING, 'value': request['visualizer']})
            if result is not True:
                self.restore()
                return
            xbmc.executebuiltin('ActivateWindow(visualisation)')
        except Exception as exc:
            self.restore()
            xbmc.log('xVAULT radio visualisation start: ' + type(exc).__name__, xbmc.LOGWARNING)

    def onPlayBackStopped(self):
        self.restore()
        window().clearProperty('xvault.radio.current')
        window().clearProperty('xvault.radio.sleep')
        xbmc.executebuiltin('CancelAlarm(xvault_radio_sleep,true)')

    def onPlayBackEnded(self):
        self.onPlayBackStopped()

    def onPlayBackError(self):
        self.onPlayBackStopped()


def start_monitor():
    global _player
    if _player is None:
        _player = RadioPlayer()
        if _player.isPlayingAudio() and pending():
            _player.onAVStarted()


def stop_monitor():
    global _player
    if _player is not None:
        _player.restore()
        _player = None
    window().clearProperty(PENDING)
