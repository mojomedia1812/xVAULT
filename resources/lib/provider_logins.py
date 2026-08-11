from resources.lib import control


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


def configure(provider_id):
    provider = PROVIDERS.get(provider_id or '')
    if not provider:
        control.infoDialog('Unbekannter Anbieter.', icon='WARNING')
        return False

    username = _ask_text(
        '%s: %s' % (provider['name'], provider['user_label']),
        control.getSetting(provider['user_setting']),
        hidden=False,
    )
    if username is None:
        return False

    password = _ask_text(
        '%s: Passwort' % provider['name'],
        control.getSetting(provider['pass_setting']),
        hidden=True,
    )
    if password is None:
        return False

    control.setSetting(provider['user_setting'], username.strip())
    control.setSetting(provider['pass_setting'], password)
    control.infoDialog('%s-Zugangsdaten gespeichert.' % provider['name'], icon='INFO')
    return True


def clear(provider_id):
    provider = PROVIDERS.get(provider_id or '')
    if not provider:
        control.infoDialog('Unbekannter Anbieter.', icon='WARNING')
        return False
    if not control.yesnoDialog(
        '%s-Zugangsdaten löschen?' % provider['name'],
        'Benutzername und Passwort werden aus den xVAULT-Einstellungen entfernt.',
        'Fortfahren?',
        yeslabel='Löschen',
        nolabel='Abbrechen',
    ):
        return False
    control.setSetting(provider['user_setting'], '')
    control.setSetting(provider['pass_setting'], '')
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
