# edit 2026-06-13

import os
import re
import shutil
import zipfile
from xml.etree import ElementTree

try:
    import requests
except:
    requests = None

from resources.lib import control, log_utils


MANIFEST_URL = 'https://raw.githubusercontent.com/mojomedia1812/xVAULT/main/addon.xml'
DOWNLOAD_URL = 'https://mojomedia1812.github.io/xVAULT/downloads/plugin.video.xvault-%s.zip'
REQUEST_TIMEOUT = 10


class UpdateCancelled(Exception):
    pass


class UpdateError(Exception):
    pass


def check_for_update():
    """Return False when an update was installed and the current plugin run should stop."""
    try:
        release = get_latest_release()
        if not release:
            return True

        latest_version = release['version']
        if compare_versions(latest_version, control.addonVersion) <= 0:
            return True

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


def get_latest_release():
    if requests is None:
        raise UpdateError('requests module is not available')

    response = requests.get(
        MANIFEST_URL,
        headers={'User-Agent': '%s/%s' % (control.addonId, control.addonVersion)},
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    addon_id, version = _addon_xml_info(response.text)
    if addon_id != control.addonId:
        raise UpdateError('Unexpected addon id in update manifest: %s' % addon_id)
    if not version:
        raise UpdateError('No version found in update manifest')

    return {
        'version': version,
        'download_url': DOWNLOAD_URL % version,
    }


def install_update(version, url):
    temp_zip = os.path.join(control.translatePath('special://temp/'), 'plugin.video.xvault-%s.zip' % version)
    try:
        _download(url, temp_zip, version)
        root = _validate_zip(temp_zip, version)
        _record_pending_update(version)
        _extract_zip_root(temp_zip, root, control.addonPath)
        control.execute('UpdateLocalAddons')
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


def _validate_zip(path, expected_version):
    with zipfile.ZipFile(path) as archive:
        addon_xml = _find_addon_xml(archive)
        addon_id, version = _addon_xml_info(archive.read(addon_xml).decode('utf-8'))
        if addon_id != control.addonId:
            raise UpdateError('Unexpected addon id in zip: %s' % addon_id)
        if version != expected_version:
            raise UpdateError('Unexpected version in zip: %s' % version)
        return addon_xml.rsplit('/', 1)[0] if '/' in addon_xml else ''


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
