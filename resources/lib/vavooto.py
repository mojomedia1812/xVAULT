# edit 2026-06-14

from resources.lib import control


ACTION_PREFIX = 'vavoo_'
LIVE_TV_ACTIONS = set([
    'live',
    'livePlay',
    'channels',
    'favchannels',
    'group_tv',
    'a_z_tv',
    'addTvFavorit',
    'delTvFavorit',
    'delallTvFavorit',
    'makem3u',
])


def open_root():
    dispatch({'action': 'root'})


def open_favorites():
    dispatch({'action': 'favchannels'})


def open_settings():
    control.openSettings()


def make_m3u():
    from resources.lib import m3u_live

    m3u_live.export_all()


def dispatch(params):
    """Route embedded VAVOO.TO actions through xVAULT."""
    params = dict(params or {})
    action = _internal_action(params.pop('action', None))
    tv = params.get('name')

    if _is_live_tv_action(action, tv):
        return _show_live_tv_disabled()

    from resources.lib.vavoo import stalker, vavoo_tv, vjackson, vjlive
    from resources.lib.vavoo.utils import clear, execute, log, setSetting

    if tv and (action in (None, '', 'livePlay')):
        return vjlive.livePlay(tv, params.get('type'), params.get('group'))

    if action in (None, '', 'root'):
        return vjackson.menu(params)

    if action == 'addTvFavorit' and tv:
        return vjlive.change_favorit(tv)

    if action == 'delTvFavorit' and tv:
        return vjlive.change_favorit(tv, True)

    if action == 'delallTvFavorit':
        setSetting('favs', '[]')
        execute('Container.Refresh')
        return

    actions = {
        'choose': lambda: vavoo_tv.choose(),
        'get_genres': lambda: stalker.get_genres(),
        'choose_portal': lambda: stalker.choose_portal(),
        'new_mac': lambda: stalker.new_mac(),
        'clear': lambda: clear(),
        'delete_search': lambda: clear_search(params),
        'channels': lambda: vjlive.channels(params.get('items'), params.get('type'), params.get('group')),
        'settings': lambda: open_settings(),
        'favchannels': lambda: vjlive.favchannels(),
        'makem3u': lambda: make_m3u(),
    }

    if action in actions:
        return actions[action]()

    handler = getattr(vjackson, action, None)
    if callable(handler) and not action.startswith('_'):
        return handler(params)

    log('Unbekannte action: %s' % action)
    return vjackson.menu(params)


def clear_search(params):
    from resources.lib.vavoo.utils import delete_search

    return delete_search(params)


def _internal_action(action):
    if action and action.startswith(ACTION_PREFIX):
        return action[len(ACTION_PREFIX):]
    return action


def _is_live_tv_action(action, tv=None):
    if action in LIVE_TV_ACTIONS:
        return True
    return bool(tv and action in (None, '', 'livePlay'))


def _show_live_tv_disabled():
    control.infoDialog("LiveTV ist in dieser Version deaktiviert.", icon='WARNING', time=5000)
