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
        storage.save_login(data.get('email', email), data.get('api_key', ''))
        control.infoDialog('Registrierung erfolgreich. Die Synchronisation ist nun aktiviert.', icon='INFO', time=6000)
        after_login_restore_hint()
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
        storage.save_login(data.get('email', email), data.get('api_key', ''))
        control.infoDialog('Anmeldung erfolgreich.', icon='INFO')
        after_login_restore_hint()
    except ApiError as exc:
        control.infoDialog(str(exc), icon='WARNING', time=6000)


def logout():
    storage.clear_login()
    control.infoDialog('Du bist abgemeldet.', icon='INFO')


def sync_now():
    if not storage.is_logged_in():
        control.infoDialog('Bitte zuerst anmelden.', icon='WARNING')
        return
    ok_fav = favorites_sync.check_and_push_if_changed(silent=True)
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


def after_login_restore_hint():
    try:
        data = Client().pull_favorites()
        if data.get('favorites') and control.yesnoDialog('Ein Favoriten-Backup wurde gefunden.', 'Möchtest du es jetzt wiederherstellen?', '', yeslabel='Ja', nolabel='Nein'):
            favorites_sync.restore_from_server()
    except ApiError:
        pass
    binge_sync.pull_remote(apply_bookmarks=True, silent=True)


def ask_email(default=''):
    value = control.dialog.input('E-Mail-Adresse', defaultt=default or '', type=xbmcgui.INPUT_ALPHANUM)
    return value.strip()


def ask_password(heading):
    return control.dialog.input(heading, type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
