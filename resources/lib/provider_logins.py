import json
import os

import xbmc

from resources.lib import control
from resources.lib.tools import logger


STORE_FILE = 'provider_logins.json'


PROVIDERS = {
    'flimmerstube': {
        'name': 'FlimmerStube.com',
        'user_setting': 'flimmerstube.user',
        'pass_setting': 'flimmerstube.pass',
        'user_label': 'E-Mail',
    },
    'aniworld': {
        'name': 'AniWorld.to',
        'user_setting': 'aniworld.user',
        'pass_setting': 'aniworld.pass',
        'user_label': 'E-Mail',
    },
    'opensubtitles': {
        'name': 'OpenSubtitles.org',
        'user_setting': 'subtitles.os_user',
        'pass_setting': 'subtitles.os_pass',
        'user_label': 'Benutzername',
    },
}


def provider_items():
    return [
        (provider_id, provider['name'])
        for provider_id, provider in PROVIDERS.items()
    ]


def is_configured(provider_id):
    provider = PROVIDERS.get(provider_id or '')
    if not provider:
        return False
    username, password = get_credentials(provider_id)
    return bool(username and password)


def get_credentials(provider_id):
    provider = PROVIDERS.get(provider_id or '')
    if not provider:
        return '', ''
    username = control.getSetting(provider['user_setting'])
    password = control.getSetting(provider['pass_setting'])
    if username and password:
        return username, password
    fallback = _load_store().get(provider_id) or {}
    return fallback.get('username') or '', fallback.get('password') or ''


def configure(provider_id):
    provider = PROVIDERS.get(provider_id or '')
    if not provider:
        _log('configure unknown provider=%s' % (provider_id or ''))
        control.infoDialog('Unbekannter Anbieter.', icon='WARNING')
        return False

    _log('configure opened provider=%s configured_before=%s' % (provider_id, is_configured(provider_id)))
    username = _ask_text(
        '%s: %s' % (provider['name'], provider['user_label']),
        control.getSetting(provider['user_setting']),
        hidden=False,
    )
    if username is None:
        _log('configure cancelled provider=%s step=username' % provider_id)
        return False

    password = _ask_text(
        '%s: Passwort' % provider['name'],
        control.getSetting(provider['pass_setting']),
        hidden=True,
    )
    if password is None:
        _log('configure cancelled provider=%s step=password' % provider_id)
        return False

    username = username.strip()
    if not username or not password:
        _log(
            'configure rejected empty credentials provider=%s user_present=%s pass_present=%s'
            % (provider_id, bool(username), bool(password)),
            warning=True,
        )
        control.infoDialog(
            '%s-Zugangsdaten nicht gespeichert: Benutzername und Passwort muessen gefuellt sein.'
            % provider['name'],
            icon='WARNING',
            time=5000,
        )
        return False

    settings_write_ok = _set(provider['user_setting'], username) and _set(provider['pass_setting'], password)
    fallback_write_ok = _store_credentials(provider_id, username, password)

    if not settings_write_ok and not fallback_write_ok:
        _log('configure setSetting failed provider=%s' % provider_id, warning=True)
        control.infoDialog('%s-Zugangsdaten konnten nicht gespeichert werden.' % provider['name'], icon='ERROR', time=5000)
        return False

    settings_verified = _verify_settings(provider, username, password)
    fallback_verified = _verify_fallback(provider_id, username, password)
    if not settings_verified and not fallback_verified:
        user_match = control.getSetting(provider['user_setting']) == username
        pass_match = control.getSetting(provider['pass_setting']) == password
        _log(
            'configure persist verify failed provider=%s user_present=%s pass_present=%s user_match=%s pass_match=%s fallback_match=%s'
            % (
                provider_id,
                bool(control.getSetting(provider['user_setting'])),
                bool(control.getSetting(provider['pass_setting'])),
                user_match,
                pass_match,
                fallback_verified,
            ),
            warning=True,
        )
        control.infoDialog(
            '%s-Zugangsdaten konnten nicht dauerhaft gespeichert werden. Bitte Supportpaket erstellen.'
            % provider['name'],
            icon='ERROR',
            time=7000,
        )
        return False

    if not settings_verified and fallback_verified:
        _log('configure saved provider=%s storage=fallback kodi_settings=False' % provider_id, warning=True)
        control.infoDialog('%s-Zugangsdaten gespeichert. Kodi-Settings-Fallback aktiv.' % provider['name'], icon='INFO', time=5000)
        return True

    _log('configure saved provider=%s storage=kodi_settings fallback=%s' % (provider_id, fallback_verified))
    control.infoDialog('%s-Zugangsdaten gespeichert.' % provider['name'], icon='INFO')
    return True


def clear(provider_id):
    provider = PROVIDERS.get(provider_id or '')
    if not provider:
        _log('clear unknown provider=%s' % (provider_id or ''))
        control.infoDialog('Unbekannter Anbieter.', icon='WARNING')
        return False
    _log('clear opened provider=%s configured_before=%s' % (provider_id, is_configured(provider_id)))
    if not control.yesnoDialog(
        '%s-Zugangsdaten löschen?' % provider['name'],
        'Benutzername und Passwort werden aus den xVAULT-Einstellungen entfernt.',
        'Fortfahren?',
        yeslabel='Löschen',
        nolabel='Abbrechen',
    ):
        _log('clear cancelled provider=%s' % provider_id)
        return False
    _set(provider['user_setting'], '')
    _set(provider['pass_setting'], '')
    _clear_store(provider_id)
    fallback_username, fallback_password = get_credentials(provider_id)
    if control.getSetting(provider['user_setting']) or control.getSetting(provider['pass_setting']) or fallback_username or fallback_password:
        _log('clear persist verify failed provider=%s' % provider_id, warning=True)
        control.infoDialog('%s-Zugangsdaten konnten nicht vollstaendig geloescht werden.' % provider['name'], icon='WARNING')
        return False
    _log('clear saved provider=%s configured_after=False' % provider_id)
    control.infoDialog('%s-Zugangsdaten gelöscht.' % provider['name'], icon='INFO')
    return True


def _ask_text(heading, default='', hidden=False):
    keyboard = control.keyboard(default or '', heading, hidden)
    try:
        keyboard.setHiddenInput(hidden)
    except Exception:
        pass
    keyboard.doModal()
    if not keyboard.isConfirmed():
        return None
    return keyboard.getText()


def _set(setting_id, value):
    try:
        result = control.setSetting(setting_id, value)
        return result is not False
    except Exception as exc:
        _log('setSetting exception setting=%s error=%s' % (setting_id, _short_error(exc)), warning=True)
        return False


def _verify_settings(provider, username, password):
    for _attempt in range(4):
        if control.getSetting(provider['user_setting']) == username and control.getSetting(provider['pass_setting']) == password:
            return True
        try:
            xbmc.sleep(150)
        except Exception:
            pass
    return False


def _verify_fallback(provider_id, username, password):
    fallback = _load_store().get(provider_id) or {}
    return fallback.get('username') == username and fallback.get('password') == password


def _store_credentials(provider_id, username, password):
    try:
        store = _load_store()
        store[provider_id] = {'username': username, 'password': password}
        _write_store(store)
        return _verify_fallback(provider_id, username, password)
    except Exception as exc:
        _log('fallback store exception provider=%s error=%s' % (provider_id, _short_error(exc)), warning=True)
        return False


def _clear_store(provider_id):
    try:
        store = _load_store()
        if provider_id in store:
            del store[provider_id]
            _write_store(store)
        return True
    except Exception as exc:
        _log('fallback clear exception provider=%s error=%s' % (provider_id, _short_error(exc)), warning=True)
        return False


def _load_store():
    path = _store_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        _log('fallback load exception error=%s' % _short_error(exc), warning=True)
        return {}


def _write_store(store):
    directory = control.addonProfilePath
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    with open(_store_path(), 'w', encoding='utf-8') as handle:
        json.dump(store, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write('\n')


def _store_path():
    return os.path.join(control.addonProfilePath, STORE_FILE)


def _log(message, warning=False):
    try:
        if warning:
            logger.warning('Provider login: %s' % message)
        else:
            logger.info('Provider login: %s' % message)
    except Exception:
        pass


def _short_error(exc):
    text = str(exc)
    if len(text) > 160:
        return text[:157] + '...'
    return text
