import time

import xbmcgui

from resources.lib import control
from resources.lib.sync import binge_sync, favorites_sync, storage
from resources.lib.sync.api_client import ApiError, Client


PRIVACY_TEXT = (
    'Für Favoriten-Backup und Verlauf werden deine E-Mail-Adresse, ein sicherer '
    'Zugangsschlüssel sowie deine xVAULT-Favoriten und Wiedergabestände gespeichert. '
    'Dein Kennwort wird nicht im Klartext gespeichert.'
)


def dispatch(action):
    if action == 'syncRegister':
        register()
    elif action == 'syncLogin':
        login()
    elif action == 'syncNow':
        sync_now()
    elif action == 'syncRestoreFavorites':
        favorites_sync.restore_from_server()
    elif action == 'syncLogout':
        logout()
    elif action == 'syncStatus':
        show_status()
    elif action == 'syncPrivacy':
        control.dialog.ok(control.addonName, PRIVACY_TEXT)


def register():
    email = ask_email()
    if not email:
        return
    password = ask_password('Kennwort festlegen')
    if not password:
        return
    try:
        data = Client().register(email, password)
        finish_login(data.get('email', email), data.get('api_key', ''), 'Registrierung erfolgreich.')
    except ApiError as exc:
        control.infoDialog(str(exc), icon='WARNING', time=6000)


def login():
    email = ask_email(storage.email())
    if not email:
        return
    password = ask_password('Kennwort')
    if not password:
        return
    try:
        data = Client().login(email, password)
        finish_login(data.get('email', email), data.get('api_key', ''), 'Anmeldung erfolgreich.')
    except ApiError as exc:
        control.infoDialog(str(exc), icon='WARNING', time=6000)


def logout():
    storage.clear_login()
    control.infoDialog('Du bist abgemeldet.', icon='INFO')


def sync_now():
    if not storage.is_logged_in():
        control.infoDialog('Bitte zuerst anmelden.', icon='WARNING')
        return
    ok_fav = favorites_sync.check_and_push_if_changed(silent=True, require_enabled=False)
    ok_binge = binge_sync.push_local(silent=True)
    binge_sync.pull_remote(apply_bookmarks=True, silent=True)
    storage.update_last_sync(time.strftime('%Y-%m-%d %H:%M:%S'))
    control.infoDialog('Synchronisation abgeschlossen.', icon='INFO')


def show_status():
    status = 'Angemeldet als %s' % storage.email() if storage.is_logged_in() else 'Nicht angemeldet'
    lines = [
        status,
        'Synchronisation: %s' % ('aktiv' if storage.is_enabled() else 'inaktiv'),
        'Letzte Synchronisation: %s' % (storage.get_setting(storage.LAST_SYNC_AT) or '-'),
        'API-Key: %s' % storage.mask_token(storage.api_key()),
    ]
    control.dialog.ok(control.addonName, '\n'.join(lines))
    storage.set_status(status)


def finish_login(email, api_key, message):
    storage.save_login(email, api_key)
    client = Client(api_key=api_key)
    if initial_sync(client, email):
        control.infoDialog(message + ' Erste Synchronisation abgeschlossen.', icon='INFO', time=6000)
    else:
        control.infoDialog(message + ' Die Synchronisation ist nun aktiviert.', icon='INFO', time=6000)


def initial_sync(client, email):
    changed = False
    changed = favorites_sync.check_and_push_if_changed(
        silent=True,
        client=client,
        require_enabled=False,
        force=True,
    ) or changed
    changed = binge_sync.push_local(silent=True, client=client, require_login=False) or changed
    changed = binge_sync.pull_remote(apply_bookmarks=True, silent=True, client=client, require_login=False) or changed
    storage.update_last_sync(time.strftime('%Y-%m-%d %H:%M:%S'))
    storage.set_status('Angemeldet als %s' % email)
    return changed


def ask_email(default=''):
    value = control.dialog.input('E-Mail-Adresse', defaultt=default or '', type=xbmcgui.INPUT_ALPHANUM)
    return value.strip()


def ask_password(heading):
    return control.dialog.input(heading, type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
