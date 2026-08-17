import re
import time

import xbmcgui

from resources.lib import control, log_utils
from resources.lib.sync import binge_sync, favorites_sync, storage
from resources.lib.sync.api_client import ApiError, Client


PRIVACY_TEXT = (
    'Für Favoriten-Backup und Verlauf werden deine E-Mail-Adresse, ein sicherer '
    'Zugangsschlüssel sowie deine xVAULT-Favoriten und Wiedergabestände gespeichert. '
    'Dein Kennwort wird nicht im Klartext gespeichert.'
)
EMAIL_RE = re.compile(r'^[^@\s]+@([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$')


def dispatch(action):
    if action == 'syncRegister':
        register()
    elif action == 'syncLogin':
        login()
    elif action == 'syncResetPassword':
        reset_password()
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


def track_sync(event_name, area='manual', error_group=None):
    payload = {'sync_area': area}
    if error_group:
        payload['error_group'] = error_group
    try:
        from resources.lib import telemetry
        telemetry.event(event_name, 'sync', payload)
    except Exception:
        pass


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
        if exc.code == 'EMAIL_EXISTS':
            control.dialog.ok(control.addonName, 'Diese E-Mail-Adresse ist bereits registriert.\nBitte melde dich an oder nutze die Passwort-Wiederherstellung.')
        elif exc.code == 'INVALID_EMAIL_DOMAIN':
            control.dialog.ok(control.addonName, 'Die Domain dieser E-Mail-Adresse ist nicht erreichbar oder besitzt keine nutzbaren DNS-/Mail-Einträge.\n\nBitte prüfe die Schreibweise oder verwende eine andere E-Mail-Adresse.')
        elif exc.code == 'INVALID_EMAIL':
            control.dialog.ok(control.addonName, 'Bitte gib eine gültige E-Mail-Adresse ein.')
        else:
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


def reset_password():
    email = ask_email(storage.email())
    if not email:
        return
    if not control.yesnoDialog('Kennwort wiederherstellen', 'Für diese E-Mail-Adresse wird ein neues Kennwort erstellt.', 'Alte Anmeldungen werden abgemeldet.', yeslabel='Erstellen', nolabel='Abbrechen'):
        return
    try:
        data = Client().reset_password(email)
        new_password = data.get('password', '')
        if not new_password:
            control.infoDialog('Kennwort konnte nicht erstellt werden.', icon='WARNING', time=6000)
            return
        storage.clear_login()
        storage.set_setting(storage.ACCOUNT_EMAIL, data.get('email', email))
        control.dialog.ok(control.addonName, 'Neues Kennwort:\n[B]%s[/B]\n\nBitte notiere es dir und melde dich damit an.' % new_password)
    except ApiError as exc:
        if exc.code == 'EMAIL_NOT_FOUND':
            control.dialog.ok(control.addonName, 'Diese E-Mail-Adresse ist nicht registriert.')
        else:
            control.infoDialog(str(exc), icon='WARNING', time=6000)


def logout():
    storage.clear_login()
    control.infoDialog('Du bist abgemeldet.', icon='INFO')


def sync_now():
    storage.reconcile_auth_settings()
    if not storage.is_logged_in():
        control.infoDialog('Bitte zuerst anmelden.', icon='WARNING')
        return
    track_sync('sync_started', 'manual')
    try:
        client = Client()
        favorites_sync.check_and_push_if_changed(silent=True, client=client, require_enabled=False)
        binge_sync.push_local(silent=True, client=client, require_login=False)
        binge_sync.pull_remote(apply_bookmarks=True, silent=True, client=client, require_login=False)
        storage.update_last_sync(time.strftime('%Y-%m-%d %H:%M:%S'))
        storage.set_status('Angemeldet als %s' % storage.email())
        track_sync('sync_finished', 'manual')
        control.infoDialog('Synchronisation abgeschlossen.', icon='INFO')
    except ApiError as exc:
        track_sync('sync_failed', 'manual', 'api_error')
        control.infoDialog(str(exc), icon='WARNING', time=6000)
    except Exception as exc:
        log_utils.log('xVAULT sync: manual sync failed: %s' % str(exc), log_utils.LOGERROR)
        track_sync('sync_failed', 'manual', 'plugin_error')
        control.infoDialog('Synchronisation fehlgeschlagen.', icon='WARNING', time=6000)


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
    value = value.strip().lower()
    if value and not is_valid_email_format(value):
        control.dialog.ok(control.addonName, 'Bitte gib eine gültige E-Mail-Adresse ein.\n\nBeispiel: name@example.de')
        return ''
    return value


def is_valid_email_format(value):
    if not value or len(value) > 254:
        return False
    if '..' in value:
        return False
    return EMAIL_RE.match(value) is not None


def ask_password(heading):
    return control.dialog.input(heading, type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
