import json
import os

from resources.lib import control, playback_settings


STATE_FILE = os.path.join(control.addonProfilePath, 'startup_info.json')
APPLIED_SETTING = 'first_install.playback_defaults.applied'

_PROFILE_STATE_FILES = (
    'startup_info.json',
    'playcount.db',
    'bookmarks.pcl',
    'tvshows.pcl',
    'channels.json',
    'linear-tv-catalog.json',
    'sync_binge_state.json',
    'sync_favorites_state.json',
)


def apply_playback_defaults_once():
    """Set playback defaults only for a genuinely fresh xVAULT profile."""
    try:
        if control.getSetting(APPLIED_SETTING) == 'true':
            return

        if playback_settings.has_profile_mode():
            control.setSetting(id=APPLIED_SETTING, value='true')
            playback_settings.migrate_mode_setting()
            return

        if _profile_has_existing_state():
            control.setSetting(id=APPLIED_SETTING, value='true')
            return

        control.setSetting(id='hosts.language', value='1')
        playback_settings.set_mode('2')
        control.setSetting(id=APPLIED_SETTING, value='true')
    except Exception:
        pass


def _profile_has_existing_state():
    state = _load_state()
    if state and (
        state.get('last_started_version')
        or state.get('intro_seen')
        or state.get('intro_screen_seen')
    ):
        return True

    for filename in _PROFILE_STATE_FILES:
        path = os.path.join(control.addonProfilePath, filename)
        try:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return True
        except Exception:
            pass

    return False


def _load_state():
    try:
        with open(STATE_FILE, 'r') as handle:
            return json.load(handle)
    except Exception:
        return {}
