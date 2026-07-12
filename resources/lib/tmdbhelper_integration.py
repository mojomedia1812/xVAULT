import os

from resources.lib import control, log_utils


PLAYER_FILENAME = 'xvault.json'
TMDBHELPER_ADDON = 'plugin.video.themoviedb.helper'


def _read_text(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return handle.read()


def _write_text(path, text):
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def _tmdbhelper_installed():
    return os.path.exists(control.translatePath('special://home/addons/%s/addon.xml' % TMDBHELPER_ADDON))


def ensure_player():
    if not _tmdbhelper_installed():
        return False

    source = os.path.join(control.addonPath, 'resources', 'tmdbhelper', PLAYER_FILENAME)
    target = control.translatePath(
        'special://profile/addon_data/%s/players/%s' % (TMDBHELPER_ADDON, PLAYER_FILENAME)
    )
    if not os.path.exists(source):
        return False

    try:
        new_text = _read_text(source)
        old_text = _read_text(target) if os.path.exists(target) else ''
        if old_text != new_text:
            _write_text(target, new_text)
            log_utils.log('TMDbHelper player installed: %s' % target, log_utils.LOGINFO)
        return True
    except Exception as exc:
        log_utils.log('TMDbHelper player install failed: %s' % str(exc), log_utils.LOGWARNING)
        return False
