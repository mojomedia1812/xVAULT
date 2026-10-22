import re
import time

import xbmcgui

from resources.lib import control, log_utils
from resources.lib.sync import binge_sync, favorites_sync, storage, engine, device
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
    elif action == 'syncDevices':
        manage_devices()


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
    if storage.is_logged_in():
        try:
            Client().exchange({'device_id': device.get_device_id(), 'device_name': device.get_device_name(), 'revoke_device': device.get_device_id()})
        except Exception:
            # Local logout must also work offline. Remote revocation remains
            # available from another signed-in device.
            pass
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
        if not engine.synchronize(client=client, active=True):
            control.infoDialog('Abgleich läuft bereits oder Synchronisation ist deaktiviert.', icon='INFO')
            return
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
    storage.reconcile_auth_settings()
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
    try:
        return engine.synchronize(client=client, active=True)
    except Exception as exc:
        log_utils.log('xVAULT sync: initial device sync pending: %s' % exc, log_utils.LOGWARNING)
        return False


def choose_resume(key):
    import json
    state = engine.inspect()
    conflicts = [c for c in state.get('conflicts', [])
                 if (lambda op: op['kind'] == 'progress' and op['key'] == key)(json.loads(c['operation_json']))]
    if not conflicts:
        return True
    names = {d['device_id']: d['name'] for d in state.get('devices', [])}
    current = next((e for e in state['entities'] if e['kind'] == 'progress' and e['key'] == key), None)
    def label(value, device_id):
        seconds = int(value.get('position_seconds') or 0)
        return '%s: %02d:%02d' % (names.get(device_id, device_id or 'Kontostand'), seconds // 60, seconds % 60)
    labels = [label((current or {}).get('data', {}).get('value', {}), (current or {}).get('device_id'))]
    labels += [label(json.loads(c['operation_json'])['patch']['value'], c['device_id']) for c in conflicts]
    selected = control.dialog.select('Unterschiedliche Wiedergabestände – welchen fortsetzen?', labels)
    if selected < 0:
        return False
    try:
        chosen = conflicts[selected - 1] if selected else None
        if chosen:
            engine.resolve(chosen, use_local=True)
            if not engine.synchronize(active=True):
                return False
            if any(c['operation_id'] == chosen['operation_id'] for c in engine.inspect().get('conflicts', [])):
                return False
        for conflict in conflicts:
            if conflict is not chosen:
                engine.resolve(conflict, use_local=False)
        return engine.synchronize(active=True)
    except Exception:
        control.infoDialog('Auswahl konnte noch nicht abgeglichen werden. Bitte erneut versuchen.', icon='WARNING')
        return False


def manage_devices():
    if not storage.is_logged_in():
        control.infoDialog('Bitte zuerst anmelden.', icon='WARNING')
        return
    try:
        engine.synchronize(active=True)
    except Exception:
        control.infoDialog('Server nicht erreichbar. Zeige zuletzt gespeicherten Stand.', icon='WARNING')
    state = engine.inspect()
    choice = control.dialog.select('Geräte & Sync-Verlauf', [
        'Geräte anzeigen / abmelden', 'Änderungsverlauf',
        'Konflikte lösen (%s)' % len(state.get('conflicts', [])),
        'Ausstehende Änderungen: %s' % state['pending'],
    ])
    names = {d['device_id']: d['name'] for d in state.get('devices', [])}
    if choice == 0:
        devices = state.get('devices', [])
        labels = ['%s%s | benutzt: %s%s' % (
            d['name'], ' (dieses Gerät)' if d['device_id'] == device.get_device_id() else '',
            d.get('last_used_at') or '-',
            '' if d.get('authenticated') else ' (abgemeldet)') for d in devices]
        selected = control.dialog.select('Geräte – Auswahl für Details', labels)
        if selected < 0:
            return
        selected_device = devices[selected]
        action = control.dialog.contextmenu(['Geräteinformationen', 'Gerät abmelden'])
        if action == 0:
            control.dialog.textviewer(selected_device['name'], '\n'.join([
                'Zuletzt benutzt: %s' % (selected_device.get('last_used_at') or '–'),
                'Zuletzt erreichbar: %s' % selected_device['last_seen_at'],
                'Letzte Änderung: %s' % (selected_device.get('last_changed_at') or '–'),
                'Anmeldung: %s' % ('aktiv' if selected_device.get('authenticated') else 'abgemeldet'),
                'Zeitangaben: Serverzeit',
            ]))
        elif action == 1 and control.yesnoDialog('Gerät abmelden?', selected_device['name'], 'Erneute Anmeldung ist anschließend erforderlich.'):
            try:
                Client().exchange({'device_id': device.get_device_id(), 'device_name': device.get_device_name(), 'revoke_device': devices[selected]['device_id']})
                if devices[selected]['device_id'] == device.get_device_id():
                    storage.clear_login()
                control.infoDialog('Gerät abgemeldet.', icon='INFO')
            except ApiError as exc:
                control.infoDialog(str(exc), icon='WARNING')
    elif choice == 1:
        lines = []
        for event in state.get('activity', []):
            import json
            op = json.loads(event['operation_json'])
            result = json.loads(event['result_json'])
            value = op.get('patch', {}).get('value', {})
            label = op.get('patch', {}).get('label') or value.get('title') or op['key'][:12]
            action = 'gelöscht' if op.get('deleted') else 'geändert'
            if result.get('unchanged'):
                action = 'unverändert / Zwischenstand ignoriert'
            detail = ''
            if op['kind'] == 'progress':
                seconds = int(value.get('position_seconds') or 0)
                detail = ' bei %02d:%02d' % (seconds // 60, seconds % 60)
            elif op['kind'] == 'watch':
                detail = ': gesehen' if value.get('completed') else ': ungesehen'
            elif not op.get('deleted'):
                before = (result.get('before') or {}).get('data', {})
                fields = {'order': 'Reihenfolge', 'label': 'Bezeichnung', 'thumb': 'Vorschaubild', 'path': 'Ziel'}
                detail = '\n  ' + '\n  '.join('%s: %s → %s' % (fields.get(field, field), before.get(field, '–'), new) for field, new in op['patch'].items())
            status = {'accepted': 'übernommen', 'conflict': 'Konflikt'}.get(result['status'], result['status'])
            lines.append('%s · %s · %s %s%s · %s%s' % (event['created_at'], names.get(event['device_id'], event['device_id']), label, action, detail, status, ' (gelöst)' if event['resolved'] else ''))
        control.dialog.textviewer('Sync-Verlauf (letzte 100 Änderungen)', '\n'.join(lines) or 'Noch keine Änderungen.')
    elif choice == 2:
        conflicts = state.get('conflicts', [])
        labels = []
        import json
        for conflict in conflicts:
            op = json.loads(conflict['operation_json'])
            value = op.get('patch', {}).get('value', {})
            kind = {'favorite': 'Favorit', 'progress': 'Wiedergabestand', 'watch': 'Gesehen-Status'}.get(op['kind'], op['kind'])
            labels.append('%s · %s · %s' % (names.get(conflict['device_id'], conflict['device_id']), kind, op.get('patch', {}).get('label') or value.get('title') or op['key'][:12]))
        selected = control.dialog.select('Offene Sync-Konflikte', labels)
        if selected >= 0:
            conflict = conflicts[selected]
            op = json.loads(conflict['operation_json'])
            current = next((e for e in state['entities'] if e['kind'] == op['kind'] and e['key'] == op['key']), {})
            def describe(data, deleted=False):
                if deleted:
                    return 'gelöscht'
                value = data.get('value', {})
                if op['kind'] == 'progress':
                    seconds = int(value.get('position_seconds') or 0)
                    return '%s – %02d:%02d' % (value.get('title', ''), seconds // 60, seconds % 60)
                if op['kind'] == 'watch':
                    return 'gesehen' if value.get('completed') else 'ungesehen'
                return ', '.join('%s: %s' % (k, v) for k, v in data.items())
            decision = control.dialog.select('Welche Änderung übernehmen?', [
                'Kontostand: ' + describe(current.get('data', {}), current.get('deleted')),
                names.get(conflict['device_id'], conflict['device_id']) + ': ' + describe(op['patch'], op.get('deleted')),
            ])
            if decision >= 0:
                engine.resolve(conflict, use_local=decision == 1)
                sync_now()


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
