"""Station presets and a Kodi-owned sleep alarm restricted to radio audio."""
import json
import time
import uuid
import xbmc
import xbmcgui

PRESETS = ('Pastelllinien', 'Resonance', 'Liquid Emblem', 'Klangarchiv', 'Lichtgewebe', 'Eclipse', 'Gravity')
ALARM = 'xvault_radio_sleep'
PROPERTY = 'xvault.radio.sleep'


def preset(identifier):
    from resources.lib import radio
    return radio.stored('radio.presets').get(identifier)


def choose_preset(identifier):
    from resources.lib import radio
    values = radio.stored('radio.presets')
    current = values.get(identifier)
    selected = xbmcgui.Dialog().select('Visualisierung für diesen Sender', ['Globale Vorgabe'] + list(PRESETS),
        preselect=current + 1 if isinstance(current, int) and 0 <= current < 7 else 0)
    if selected < 0:
        return
    if selected == 0:
        values.pop(identifier, None)
    else:
        values[identifier] = selected - 1
    radio.addon().setSetting('radio.presets', json.dumps(values))
    radio.notify('Sender-Vorgabe gespeichert; gilt beim nächsten Start.')


def sleep_status():
    try:
        state = json.loads(xbmcgui.Window(10000).getProperty(PROPERTY) or '{}')
        return state if state.get('until', 0) > time.time() else {}
    except (ValueError, TypeError):
        return {}


def set_sleep():
    from resources.lib import radio
    options = [0, 15, 30, 45, 60, 90, 120]
    selected = xbmcgui.Dialog().select('Radio-Einschlaftimer', ['Ausschalten'] + ['%d Minuten' % n for n in options[1:]])
    if selected < 0:
        return
    xbmc.executebuiltin('CancelAlarm(%s,true)' % ALARM)
    win = xbmcgui.Window(10000)
    win.clearProperty(PROPERTY)
    minutes = options[selected]
    if not minutes:
        radio.notify('Einschlaftimer ausgeschaltet')
        return
    player = xbmc.Player()
    current = json.loads(win.getProperty('xvault.radio.current') or '{}')
    if not player.isPlayingAudio() or player.getPlayingFile().split('|', 1)[0] != current.get('target'):
        radio.notify('Bitte zuerst einen xVAULT-Radiosender starten.')
        return
    token = uuid.uuid4().hex
    win.setProperty(PROPERTY, json.dumps(dict(token=token, target=current['target'], until=time.time() + minutes * 60)))
    xbmc.executebuiltin('AlarmClock(%s,RunPlugin(%s),%d,true,false)' % (ALARM, radio.url('radioSleepExpire', token=token), minutes))
    radio.notify('Radio stoppt in %d Minuten; bei einem Senderwechsel endet der Timer.' % minutes)


def expire(token):
    win = xbmcgui.Window(10000)
    try:
        state = json.loads(win.getProperty(PROPERTY) or '{}')
        if not token or state.get('token') != token:
            return
        win.clearProperty(PROPERTY)
        player = xbmc.Player()
        if player.isPlayingAudio() and player.getPlayingFile().split('|', 1)[0] == state.get('target'):
            player.stop()
    except (ValueError, RuntimeError):
        pass
