# edit 2026-06-13

import os
import re
import shutil
import zipfile
import json
import time
from xml.etree import ElementTree

try:
    import requests
except:
    requests = None

from resources.lib import control, log_utils


STABLE_ADDON_ID = 'plugin.video.xvault'
ALPHA_ADDON_ID = 'plugin.video.xvaultalpha'
STABLE_MANIFEST_URL = 'https://raw.githubusercontent.com/mojomedia1812/xVAULT/main/addon.xml'
STABLE_DOWNLOAD_URL = 'http://xvault.ddnss.de/downloads/plugin.video.xvault-%s.zip'
ALPHA_MANIFEST_URL = 'https://raw.githubusercontent.com/mojomedia1812/xvaultalpha/main/addon.xml'
ALPHA_DOWNLOAD_URL = 'https://raw.githubusercontent.com/mojomedia1812/xvaultalpha/main/docs/downloads/plugin.video.xvaultalpha-%s.zip'
MANIFEST_URL = STABLE_MANIFEST_URL
DOWNLOAD_URL = STABLE_DOWNLOAD_URL
REQUEST_TIMEOUT = 10
CHANNEL_STABLE = 'stable'
CHANNEL_EXTERNAL = 'external'
SETTING_CHANNEL = 'updates.channel'
SETTING_MANIFEST_URL = 'updates.manifest_url'
SETTING_DOWNLOAD_URL = 'updates.download_url'


class UpdateCancelled(Exception):
    pass


class UpdateError(Exception):
    pass


def check_for_update(prompt=True, ignore_disabled=False):
    """Return False when an update was installed and the current plugin run should stop."""
    if not ignore_disabled and not automatic_updates_enabled():
        return True

    try:
        release = get_latest_release()
        if not release:
            return True

        latest_version = release['version']
        if compare_versions(latest_version, control.addonVersion) <= 0:
            return True

        yes = True
        if prompt:
            yes = control.yesnoDialog(
                'Eine neue xVAULT-Version ist verfügbar.',
                'Installiert: %s   Neu: %s' % (control.addonVersion, latest_version),
                'Jetzt installieren?',
                heading=control.addonName,
                nolabel='Nein',
                yeslabel='Installieren'
            )
        if not yes:
            return True

        if install_update(latest_version, release['download_url']):
            return False
    except Exception as e:
        log_utils.log('Update check failed: %s' % str(e), log_utils.LOGWARNING)

    return True


def automatic_updates_enabled():
    return control.getSetting('updates.auto', 'true').lower() != 'false'


def configure_external_source(manifest_url, download_url):
    manifest_url = str(manifest_url or '').strip()
    download_url = str(download_url or '').strip()
    if not manifest_url or not download_url or '%s' not in download_url:
        raise UpdateError('Invalid update source')
    control.setSetting(SETTING_CHANNEL, CHANNEL_EXTERNAL)
    control.setSetting(SETTING_MANIFEST_URL, manifest_url)
    control.setSetting(SETTING_DOWNLOAD_URL, download_url)


def reset_update_source():
    control.setSetting(SETTING_CHANNEL, CHANNEL_STABLE)
    control.setSetting(SETTING_MANIFEST_URL, '')
    control.setSetting(SETTING_DOWNLOAD_URL, '')


def get_latest_release():
    try:
        return _release_from_urls(*_source_urls())
    except UpdateError:
        if control.getSetting(SETTING_CHANNEL, CHANNEL_STABLE) == CHANNEL_EXTERNAL:
            reset_update_source()
            return _release_from_urls(*_source_urls())
        raise


def get_stable_release():
    return _release_from_urls(STABLE_MANIFEST_URL, STABLE_DOWNLOAD_URL, STABLE_ADDON_ID)


def get_alpha_release(manifest_url=None, download_url=None):
    return _release_from_urls(manifest_url or ALPHA_MANIFEST_URL, download_url or ALPHA_DOWNLOAD_URL, ALPHA_ADDON_ID)


def get_release_from_source(manifest_url, download_url, expected_addon_id=None):
    return _release_from_urls(manifest_url, download_url, expected_addon_id)


def _release_from_urls(manifest_url, download_url, expected_addon_id=None):
    if requests is None:
        raise UpdateError('requests module is not available')
    expected_addon_id = expected_addon_id or control.addonId

    response = requests.get(
        manifest_url,
        headers={'User-Agent': '%s/%s' % (control.addonId, control.addonVersion)},
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    addon_id, version = _addon_xml_info(response.text)
    if addon_id != expected_addon_id:
        raise UpdateError('Unexpected addon id in update manifest: %s' % addon_id)
    if not version:
        raise UpdateError('No version found in update manifest')

    return {
        'version': version,
        'download_url': download_url % version,
    }


def _source_urls():
    if control.getSetting(SETTING_CHANNEL, CHANNEL_STABLE) == CHANNEL_EXTERNAL:
        manifest_url = control.getSetting(SETTING_MANIFEST_URL, '')
        download_url = control.getSetting(SETTING_DOWNLOAD_URL, '')
        if manifest_url and download_url and '%s' in download_url:
            return manifest_url, download_url
        reset_update_source()
    if control.addonId == ALPHA_ADDON_ID:
        return ALPHA_MANIFEST_URL, ALPHA_DOWNLOAD_URL
    return STABLE_MANIFEST_URL, STABLE_DOWNLOAD_URL


def install_update(version, url, addon_id=None, run_after=False):
    target_addon_id = addon_id or control.addonId
    temp_zip = os.path.join(control.translatePath('special://temp/'), '%s-%s.zip' % (target_addon_id, version))
    try:
        _download(url, temp_zip, version)
        root = _validate_zip(temp_zip, version, target_addon_id)
        if target_addon_id == control.addonId:
            _record_pending_update(version)
        _extract_zip_root(temp_zip, root, _addon_install_path(target_addon_id))
        control.execute('UpdateLocalAddons')
        if target_addon_id != control.addonId:
            _wait_for_addon(target_addon_id)
            _set_addon_enabled(target_addon_id, True)
        if run_after:
            _wait_for_addon(target_addon_id, enabled=True)
            control.execute('RunAddon("%s")' % target_addon_id)
        control.infoDialog(
            'Version %s wurde installiert. xVAULT bitte erneut öffnen.' % version,
            icon='INFO',
            time=6000
        )
        return True
    except UpdateCancelled:
        control.infoDialog('Aktualisierung abgebrochen', icon='INFO')
    except Exception as e:
        log_utils.log('Update install failed: %s' % str(e), log_utils.LOGERROR)
        control.infoDialog('Aktualisierung fehlgeschlagen', icon='ERROR')
    finally:
        try:
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
        except:
            pass
    return False


def _addon_install_path(addon_id):
    if addon_id == control.addonId:
        return control.addonPath
    return os.path.join(control.translatePath('special://home/addons/'), addon_id)


def _set_addon_enabled(addon_id, enabled):
    try:
        command = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'Addons.SetAddonEnabled',
            'params': {
                'addonid': addon_id,
                'enabled': bool(enabled),
            },
        }
        response = json.loads(control.jsonrpc(json.dumps(command)))
        if response.get('error'):
            raise UpdateError(response.get('error'))
    except Exception as exc:
        log_utils.log('Could not enable addon %s: %s' % (addon_id, str(exc)), log_utils.LOGWARNING)


def _wait_for_addon(addon_id, enabled=None, timeout=12):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            command = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'Addons.GetAddonDetails',
                'params': {
                    'addonid': addon_id,
                    'properties': ['enabled', 'version'],
                },
            }
            response = json.loads(control.jsonrpc(json.dumps(command)))
            addon = response.get('result', {}).get('addon')
            if addon and (enabled is None or bool(addon.get('enabled')) == bool(enabled)):
                return addon
            if response.get('error'):
                last_error = response.get('error')
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    if last_error:
        log_utils.log('Timed out waiting for addon %s: %s' % (addon_id, last_error), log_utils.LOGWARNING)
    return None


def _record_pending_update(target_version):
    try:
        from resources.lib import startup_info
        startup_info.record_pending_update(control.addonVersion, target_version)
    except Exception as e:
        log_utils.log('Could not store update startup info: %s' % str(e), log_utils.LOGWARNING)


def _download(url, destination, version):
    if requests is None:
        raise UpdateError('requests module is not available')

    progress = control.progressDialog
    progress.create(control.addonName, 'Aktualisierung wird heruntergeladen')
    try:
        response = requests.get(url, stream=True, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        total = int(response.headers.get('content-length') or 0)
        downloaded = 0
        directory = os.path.dirname(destination)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(destination, 'wb') as output:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if progress.iscanceled():
                    raise UpdateCancelled()
                if not chunk:
                    continue
                output.write(chunk)
                downloaded += len(chunk)
                percent = int(downloaded * 100 / total) if total else 0
                progress.update(percent, 'Version %s' % version)
    finally:
        try:
            progress.close()
        except:
            pass


def _validate_zip(path, expected_version, expected_addon_id=None):
    expected_addon_id = expected_addon_id or control.addonId
    with zipfile.ZipFile(path) as archive:
        addon_xml = _find_addon_xml(archive)
        addon_id, version = _addon_xml_info(archive.read(addon_xml).decode('utf-8'))
        if addon_id != expected_addon_id:
            raise UpdateError('Unexpected addon id in zip: %s' % addon_id)
        if version != expected_version:
            raise UpdateError('Unexpected version in zip: %s' % version)
        root = addon_xml.rsplit('/', 1)[0] if '/' in addon_xml else ''
        if root and root != expected_addon_id:
            raise UpdateError('Unexpected addon root in zip: %s' % root)
        return root


def _find_addon_xml(archive):
    for name in archive.namelist():
        normalized = _normalize_zip_name(name)
        if normalized.endswith('/addon.xml') or normalized == 'addon.xml':
            return normalized
    raise UpdateError('addon.xml not found in update zip')


def _extract_zip_root(path, root, destination):
    destination = os.path.abspath(destination)
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = _normalize_zip_name(info.filename)
            relative = _relative_name(name, root)
            if not relative or relative.endswith('/'):
                continue

            target = _safe_join(destination, relative)
            directory = os.path.dirname(target)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            with archive.open(info) as source, open(target, 'wb') as output:
                shutil.copyfileobj(source, output)


def _relative_name(name, root):
    if not root:
        return name
    prefix = root.rstrip('/') + '/'
    if name.startswith(prefix):
        return name[len(prefix):]
    return ''


def _safe_join(base, relative):
    parts = [part for part in relative.replace('\\', '/').split('/') if part]
    if any(part == '..' for part in parts):
        raise UpdateError('Unsafe path in update zip: %s' % relative)

    target = os.path.abspath(os.path.join(base, *parts))
    if target != base and not target.startswith(base + os.sep):
        raise UpdateError('Unsafe path in update zip: %s' % relative)
    return target


def _normalize_zip_name(name):
    return name.replace('\\', '/').lstrip('/')


def _addon_xml_info(content):
    try:
        root = ElementTree.fromstring(content)
        return root.attrib.get('id'), root.attrib.get('version')
    except:
        addon_id = _find_attr(content, 'id')
        version = _find_attr(content, 'version')
        return addon_id, version


def _find_attr(content, attr):
    match = re.search(r'\b%s=[\'"]([^\'"]+)[\'"]' % attr, content)
    return match.group(1) if match else None


def compare_versions(left, right):
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    length = max(len(left_parts), len(right_parts))

    for i in range(length):
        left_part = left_parts[i] if i < len(left_parts) else (1, 0)
        right_part = right_parts[i] if i < len(right_parts) else (1, 0)
        if left_part == right_part:
            continue
        return 1 if left_part > right_part else -1
    return 0


def _version_parts(version):
    parts = []
    for part in re.findall(r'\d+|[A-Za-z]+', str(version)):
        if part.isdigit():
            parts.append((1, int(part)))
        else:
            parts.append((0, part.lower()))
    return parts
