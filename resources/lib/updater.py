"""Signed release/nightly updates independent of Kodi's global update setting."""
import json
import os
import re
import shutil
import threading
import time
import uuid
import zipfile
from urllib.parse import urlsplit
from resources.lib import control, log_utils, release_security as security

STABLE_ADDON_ID = security.ADDON_ID
ALPHA_ADDON_ID = 'plugin.video.xvaultalpha'
STABLE_MANIFEST_URL = security.BASE_URL + 'updates/release.json'
STABLE_DOWNLOAD_URL = security.BASE_URL + 'downloads/plugin.video.xvault-%s.zip'
ALPHA_MANIFEST_URL = ALPHA_DOWNLOAD_URL = ''
INTERVALS = {'release': 21600, 'nightly': 3600}
REQUEST_PROPERTY = 'plugin.video.xvault.update.request'
_thread = None
_lock = threading.Lock()


class UpdateError(Exception):
    pass


class UpdateCancelled(UpdateError):
    pass


def selected_channel():
    return 'nightly' if control.getSetting('updates.channel', 'release').lower() in ('nightly', '1') else 'release'


def automatic_updates_enabled():
    return control.getSetting('updates.auto', 'true').lower() != 'false'


def _state_path():
    return os.path.join(control.dataPath, 'update-state.json')


def read_state():
    try:
        with open(_state_path(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(state):
    os.makedirs(control.dataPath, exist_ok=True)
    temp = _state_path() + '.' + uuid.uuid4().hex + '.tmp'
    with open(temp, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(temp, _state_path())


def _secure_url(url, allow_loopback=False):
    p = urlsplit(url)
    if p.scheme == 'https' and p.hostname and not p.username and not p.password:
        return
    if allow_loopback and p.scheme == 'http' and p.hostname in ('127.0.0.1', 'localhost', '::1'):
        return
    raise UpdateError('Updateadresse muss HTTPS verwenden')


def fetch_json(url, allow_loopback=False):
    import requests
    _secure_url(url, allow_loopback)
    with requests.get(url, timeout=4, stream=True) as response:
        response.raise_for_status()
        _secure_url(response.url, allow_loopback)
        body = bytearray()
        deadline = time.monotonic() + 15
        for block in response.iter_content(65536):
            body.extend(block)
            if len(body) > 2097152 or time.monotonic() > deadline:
                raise UpdateError('Update-Referenz zu gross oder Zeitlimit erreicht')
        return json.loads(body.decode('utf-8'))


def validate_catalog(envelope, channel, minimum_sequence=0):
    payload = security.verify_envelope(envelope)
    if payload.get('schema') != 1 or payload.get('channel') != channel:
        raise UpdateError('Falscher Updatekanal')
    sequence = payload.get('sequence')
    if not isinstance(sequence, int) or sequence < minimum_sequence:
        raise UpdateError('Veraltete Update-Referenz abgewiesen')
    release = payload.get('release')
    if release is None:
        return payload
    info = security.version_info(release.get('version'))
    if not info or info['channel'] != channel or release.get('channel') != channel or release.get('addon_id') != STABLE_ADDON_ID:
        raise UpdateError('Version, Kanal oder Add-on-ID stimmen nicht')
    for key in ('sha256', 'tree_sha256'):
        if not re.fullmatch('[0-9a-f]{64}', str(release.get(key, ''))):
            raise UpdateError('Fehlender SHA-256-Wert')
    if not isinstance(release.get('size'), int) or not 0 < release['size'] < 134217728:
        raise UpdateError('Ungueltige Paketgroesse')
    if release.get('build_id') != release['version'] + '-' + release['tree_sha256'][:16]:
        raise UpdateError('Build-ID stimmt nicht')
    return payload


def update_plan(installed_version, release, installed_integrity=None, channel=None):
    if not release:
        return {'action': 'none', 'message': 'In diesem Kanal ist noch kein Paket freigegeben.'}
    integrity = installed_integrity or {}
    warning = security.version_warning(installed_version, release['version'])
    same = installed_version == release['version']
    info = security.version_info(installed_version)
    switch = info and info['channel'] != (channel or release['channel'])
    if same and integrity.get('state') == 'original' and integrity.get('build_id') == release['build_id']:
        return {'action': 'none', 'message': 'Installierter Stand ist aktuell und unveraendert.', 'warning': warning}
    if warning or same:
        return {'action': 'repair', 'message': warning or 'Abweichender Dateistand; explizite Reparatur erforderlich.', 'warning': warning}
    if switch or compare_versions(release['version'], installed_version) < 0:
        return {'action': 'switch', 'message': 'Kanal-Rueckwechsel auf %s' % release['version'], 'warning': warning}
    return {'action': 'update', 'message': 'Version %s ist verfuegbar.' % release['version'], 'warning': warning}


def poll(force=False, base_url=None, allow_loopback=False):
    from resources.lib import distribution
    channel, state, now = selected_channel(), read_state(), time.time()
    retry = 300 if state.get('network_error') else INTERVALS[channel]
    if not force and state.get('channel') == channel and now - state.get('last_attempt', 0) < retry:
        return state
    sequences = dict(state.get('sequences') or {})
    try:
        envelope = fetch_json((base_url or security.BASE_URL) + 'updates/' + channel + '.json', allow_loopback)
        payload = validate_catalog(envelope, channel, sequences.get(channel, 0))
        release = payload.get('release')
        if release:
            for key in ('download_url', 'integrity_url'):
                _secure_url(release[key], allow_loopback)
            reference = security.verify_envelope(fetch_json(release['integrity_url'], allow_loopback))
            security.validate_integrity_payload(reference)
            if any(reference.get(k) != release.get(k) for k in ('addon_id', 'version', 'channel', 'build_id', 'tree_sha256')):
                raise UpdateError('Kanal und Repository-Dateireferenz widersprechen sich')
        result = distribution.checkpoint('update-check', rehash=True)
        plan = update_plan(control.addonVersion, release, result['integrity'], channel)
        sequences[channel] = payload['sequence']
        state = dict(channel=channel, last_attempt=now, last_success=now, sequences=sequences,
                     release=release, plan=plan, message=plan['message'], network_error=False)
        if release and control.addonVersion == release['version']:
            state['repository_reference_sha256'] = release['tree_sha256']
            state['repository_match'] = result['integrity'].get('installed_sha256') == release['tree_sha256']
    except Exception as exc:
        if state.get('channel') != channel:
            state = {'sequences': sequences}
        state.update(channel=channel, last_attempt=now, network_error=True,
                     message='Updatepruefung derzeit nicht moeglich: ' + type(exc).__name__)
        log_utils.log('xVAULT update: ' + state['message'], log_utils.LOGWARNING)
    _save_state(state)
    return state


def request_check(force=False):
    control.window.setProperty(REQUEST_PROPERTY, json.dumps({'id': uuid.uuid4().hex, 'force': bool(force)}))


def idle_for_install():
    import xbmc
    try:
        if xbmc.Player().isPlaying() or xbmc.getGlobalIdleTime() < 30:
            return False
        if control.condVisibility('Window.IsActive(busydialog)') or control.condVisibility('Window.IsActive(progressdialog)'):
            return False
        from resources.lib.sync import engine
        return not engine.inspect().get('pending')
    except Exception:
        return False


def start_background():
    global _thread
    if _thread and _thread.is_alive():
        return
    def run():
        import xbmc
        monitor, handled, next_tick = xbmc.Monitor(), '', 0
        from resources.lib import update_maintenance
        while not monitor.waitForAbort(1) and not update_maintenance.requested():
            try:
                raw = control.window.getProperty(REQUEST_PROPERTY)
                request = json.loads(raw) if raw else {}
                requested = request.get('id') and request['id'] != handled
                if not requested and time.time() < next_tick:
                    continue
                state = poll(force=bool(requested and request.get('force')))
                handled, next_tick = request.get('id', handled), time.time() + 60
                if (automatic_updates_enabled() and control.getSetting('updates.mode', '0') in ('auto', '1')
                        and not state.get('network_error') and state.get('plan', {}).get('action') == 'update'
                        and idle_for_install()):
                    install_release(state['release'], explicit=False)
                    return
            except Exception as exc:
                log_utils.log('xVAULT update monitor: ' + type(exc).__name__, log_utils.LOGWARNING)
                next_tick = time.time() + 300
    _thread = threading.Thread(target=run, name='xvault-updates', daemon=True)
    _thread.start()


def download_verified(release, destination, allow_loopback=False):
    import requests
    import hashlib
    _secure_url(release['download_url'], allow_loopback)
    digest, total, deadline = hashlib.sha256(), 0, time.monotonic() + 120
    with requests.get(release['download_url'], stream=True, timeout=4) as response:
        response.raise_for_status()
        _secure_url(response.url, allow_loopback)
        with open(destination, 'wb') as f:
            for block in response.iter_content(65536):
                total += len(block)
                if total > release['size'] or time.monotonic() > deadline:
                    raise UpdateError('Paketgroesse oder Download-Zeitlimit ueberschritten')
                digest.update(block)
                f.write(block)
    if total != release['size'] or digest.hexdigest() != release['sha256']:
        raise UpdateError('Download stimmt nicht mit dem Repository-SHA-256 ueberein')


def stage_package(path, release, stage):
    if security.sha256_file(path) != release['sha256']:
        raise UpdateError('ZIP-SHA-256 stimmt nicht')
    with zipfile.ZipFile(path) as archive:
        entries = [i for i in archive.infolist() if not i.is_dir()]
        if len(entries) > 10000 or sum(i.file_size for i in entries) > 268435456:
            raise UpdateError('Paket ist zu gross')
        seen = set()
        for info in entries:
            security.safe_relative(info.filename)
            if not info.filename.startswith(STABLE_ADDON_ID + '/'):
                raise UpdateError('Falsches Add-on-Wurzelverzeichnis')
            if info.filename.casefold() in seen or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise UpdateError('Doppelter Dateiname oder symbolischer Link')
            seen.add(info.filename.casefold())
        envelope = json.loads(archive.read(STABLE_ADDON_ID + '/' + security.INTEGRITY_FILE).decode('utf-8'))
        payload = security.verify_envelope(envelope)
        files = security.validate_integrity_payload(payload)
        if any(payload.get(k) != release.get(k) for k in ('addon_id', 'version', 'channel', 'tree_sha256', 'build_id')):
            raise UpdateError('Paket passt nicht zur signierten Freigabe')
        expected = {STABLE_ADDON_ID + '/' + n for n in files} | {STABLE_ADDON_ID + '/' + security.INTEGRITY_FILE}
        if {i.filename for i in entries} != expected:
            raise UpdateError('ZIP-Dateiliste weicht von der signierten Referenz ab')
        import hashlib
        for name, digest in files.items():
            if hashlib.sha256(archive.read(STABLE_ADDON_ID + '/' + name)).hexdigest() != digest:
                raise UpdateError('Datei-Hash stimmt nicht: ' + name)
        os.makedirs(stage, exist_ok=False)
        try:
            for info in entries:
                target = os.path.join(stage, *info.filename[len(STABLE_ADDON_ID) + 1:].split('/'))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with archive.open(info) as src, open(target, 'wb') as dest:
                    shutil.copyfileobj(src, dest)
        except Exception:
            shutil.rmtree(stage)
            raise
    if security.inspect_tree(stage)['state'] != 'original':
        raise UpdateError('Vorbereitetes Paket hat die Originalpruefung nicht bestanden')


def install_release(release, explicit=False, allow_loopback=False):
    from resources.lib import distribution
    import xbmc
    origin = distribution.checkpoint('update-install', rehash=True)
    if xbmc.Player().isPlaying():
        raise UpdateError('Bitte die Wiedergabe vor der Installation beenden')
    if not explicit and update_plan(control.addonVersion, release, origin['integrity'], selected_channel())['action'] != 'update':
        raise UpdateError('Reparatur oder Kanal-Rueckwechsel muss bestaetigt werden')
    if not _lock.acquire(blocking=False):
        raise UpdateError('Eine Installation laeuft bereits')
    folder = os.path.join(control.dataPath, 'updates')
    os.makedirs(folder, exist_ok=True)
    lockfile = os.path.join(folder, 'install.lock')
    acquired = False
    try:
        try:
            fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise UpdateError('Eine Installation ist bereits vorbereitet')
        os.close(fd)
        acquired = True
        token, parent = uuid.uuid4().hex, os.path.dirname(control.addonPath)
        stage, backup = os.path.join(parent, '.xvault-stage-' + token), os.path.join(parent, '.xvault-backup-' + token)
        path = os.path.join(folder, 'download-' + token + '.zip')
        download_verified(release, path, allow_loopback)
        stage_package(path, release, stage)
        helper = os.path.join(folder, 'installer-' + token + '.py')
        shutil.copy2(os.path.join(control.addonPath, 'resources/lib/update_install_helper.py'), helper)
        jobfile = os.path.join(folder, 'job-' + token + '.json')
        job = dict(stage=stage, target=control.addonPath, backup=backup, result=os.path.join(folder, 'last-install.json'),
                   version=release['version'], build_id=release['build_id'], lockfile=lockfile)
        with open(jobfile, 'w', encoding='utf-8') as f:
            json.dump(job, f)
        control.execute('RunScript("%s","%s")' % (helper.replace('"', ''), jobfile.replace('"', '')))
        return True
    except Exception:
        if acquired and os.path.exists(lockfile):
            os.remove(lockfile)
        if 'stage' in locals() and os.path.isdir(stage) and not os.path.islink(stage):
            shutil.rmtree(stage)
        raise
    finally:
        if 'path' in locals() and os.path.isfile(path):
            os.remove(path)
        _lock.release()


def check_for_update(prompt=True, ignore_disabled=False):
    request_check(force=ignore_disabled)
    return True


def choose_channel():
    import xbmcgui
    choice = xbmcgui.Dialog().select('xVAULT Updatekanal', ['Release – freigegebene Versionen', 'Nightly – Testversionen'])
    if choice < 0:
        return
    channel = ('release', 'nightly')[choice]
    if channel != selected_channel() and not control.yesnoDialog('Updatekanal auf %s wechseln?' % channel,
            'Ein Rueckwechsel kann eine niedrigere Version installieren. Das Profil bleibt erhalten.', '', heading=control.addonName):
        return
    control.setSetting('updates.channel', channel)
    from resources.lib import repository
    repository.ensure_xvault_repository()
    request_check(force=True)
    control.infoDialog('Kanal %s gewaehlt. Verfuegbarkeit wird geprueft.' % channel)


def manual_check():
    state = poll(force=True)
    control.infoDialog(state.get('message', 'Pruefung beendet'), time=7000)
    return state


def install_offer():
    state = poll(force=True)
    if state.get('network_error') or not state.get('release'):
        control.infoDialog(state.get('message', 'Kein Paket verfuegbar'), time=7000)
        return
    if control.yesnoDialog('Version %s aus Kanal %s installieren?' % (state['release']['version'], selected_channel()),
                          'Bei einem Rueckwechsel wird die aktuelle Installation gesichert.', '', heading=control.addonName):
        try:
            install_release(state['release'], explicit=True)
        except Exception as exc:
            control.infoDialog('Installation nicht gestartet: %s' % exc, time=8000)


def get_stable_release():
    return validate_catalog(fetch_json(STABLE_MANIFEST_URL), 'release')['release']


def reset_update_source():
    control.setSetting('updates.channel', 'release')


def install_update(version, url, addon_id=None, run_after=False):
    release = get_stable_release()
    if not release or version != release['version'] or url != release['download_url'] or (addon_id and addon_id != STABLE_ADDON_ID):
        raise UpdateError('Nur signierte freigegebene Originalpakete koennen installiert werden')
    return install_release(release, explicit=True)


def configure_external_source(*args, **kwargs):
    raise UpdateError('Unsignierte externe Updatequellen werden nicht unterstuetzt')


def get_alpha_release(*args, **kwargs):
    raise UpdateError('Alpha benoetigt eine eigene signierte Freigabe; bitte Nightly verwenden')


def get_release_from_source(*args, **kwargs):
    raise UpdateError('Externe Updatequellen sind nicht freigegeben')


def get_latest_release():
    return validate_catalog(fetch_json(security.BASE_URL + 'updates/' + selected_channel() + '.json'), selected_channel())['release']


def compare_versions(left, right):
    def parts(value):
        return [(1, int(p)) if p.isdigit() else (0, p.lower()) for p in re.findall(r'\d+|[A-Za-z]+', str(value))]
    a, b = parts(left), parts(right)
    size = max(len(a), len(b))
    a += [(1, 0)] * (size - len(a))
    b += [(1, 0)] * (size - len(b))
    return (a > b) - (a < b)
