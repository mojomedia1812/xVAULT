import json

from resources.lib import control


PROPERTY_PREFIX = 'plugin.video.xvault.seriesqueue.'


def make_key(meta):
    return '%s.%s' % (meta.get('tmdb_id', 'unknown'), meta.get('season', 0))


def store(key, episodes):
    control.window.setProperty(PROPERTY_PREFIX + key, json.dumps(episodes))


def start(params):
    key = params.get('queue')
    try:
        start_index = int(params.get('index', 0))
    except (TypeError, ValueError):
        start_index = 0

    try:
        episodes = json.loads(control.window.getProperty(PROPERTY_PREFIX + key))
    except (TypeError, ValueError):
        episodes = []

    if not episodes or start_index < 0 or start_index >= len(episodes):
        control.infoDialog('Die Episodenliste ist nicht mehr verfuegbar.', sound=True, icon='WARNING')
        return

    selected = episodes[start_index:]
    playlist = control.videoPlaylist()
    playlist.clear()
    plugin_url = 'plugin://%s/' % control.addonId

    for offset, episode in enumerate(selected):
        meta = dict(episode)
        meta['_xvault_queue_playback'] = True
        meta['_xvault_queue_last'] = offset == len(selected) - 1
        meta['_xvault_list_position'] = start_index + 1
        meta['_xvault_list_content'] = 'movies'

        label = meta.get('sysname') or meta.get('title') or 'Episode'
        item = control.item(label=label, offscreen=True)
        item.setProperty('IsPlayable', 'true')
        try:
            item.setArt({'poster': meta.get('poster', ''), 'fanart': meta.get('fanart', '')})
        except:
            pass

        url = '%s?action=play&select=2&sysmeta=%s' % (
            plugin_url,
            control.quote_plus(json.dumps(meta)),
        )
        playlist.add(url, item)

    player = control.kodiPlayer()
    try:
        player.play(playlist)
    finally:
        del player
        del playlist
