import xbmc

from resources.lib import control
from resources.lib.tools import logger


PROVIDERS = {
    'bsto': {
        'name': 'BS.to',
        'user_setting': 'bsto.user',
        'pass_setting': 'bsto.pass',
        'user_label': 'Benutzername',
    },
    'serienstream': {
        'name': 'SerienStream.to',
        'user_setting': 'serienstream.user',
        'pass_setting': 'serienstream.pass',
        'user_label': 'E-Mail',
    },
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
    return bool(control.getSetting(provider['user_setting']) and control.getSetting(provider['pass_setting']))


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

    if not _set(provider['user_setting'], username) or not _set(provider['pass_setting'], password):
        _log('configure setSetting failed provider=%s' % provider_id, warning=True)
        control.infoDialog('%s-Zugangsdaten konnten nicht gespeichert werden.' % provider['name'], icon='ERROR', time=5000)
        return False

    if not _verify(provider, username, password):
        user_match = control.getSetting(provider['user_setting']) == username
        pass_match = control.getSetting(provider['pass_setting']) == password
        _log(
            'configure persist verify failed provider=%s user_present=%s pass_present=%s user_match=%s pass_match=%s'
            % (
                provider_id,
                bool(control.getSetting(provider['user_setting'])),
                bool(control.getSetting(provider['pass_setting'])),
                user_match,
                pass_match,
            ),
            warning=True,
        )
        control.infoDialog(
            '%s-Zugangsdaten wurden von Kodi nicht dauerhaft gespeichert. Bitte Supportpaket erstellen.'
            % provider['name'],
            icon='ERROR',
            time=7000,
        )
        return False

    _log('configure saved provider=%s configured_after=True' % provider_id)
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
    if control.getSetting(provider['user_setting']) or control.getSetting(provider['pass_setting']):
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


def _verify(provider, username, password):
    for _attempt in range(4):
        if control.getSetting(provider['user_setting']) == username and control.getSetting(provider['pass_setting']) == password:
            return True
        try:
            xbmc.sleep(150)
        except Exception:
            pass
    return False


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
