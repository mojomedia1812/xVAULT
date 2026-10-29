# edit 2026-06-13

import json
import os
import re
import sys
import struct
import time
import zipfile
import xml.etree.ElementTree as ET

import xbmc

try:
    import xbmcvfs
except:
    xbmcvfs = None

try:
    import xbmcgui
except:
    xbmcgui = None

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen


ADDON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _addon_manifest_info():
    info = {
        'id': 'plugin.video.xvault',
        'name': 'xVAULT',
        'path': ADDON_PATH,
        'version': '',
    }
    try:
        root = ET.parse(os.path.join(ADDON_PATH, 'addon.xml')).getroot()
        for key in ('id', 'name', 'version'):
            value = root.attrib.get(key)
            if value:
                info[key] = value
    except:
        pass
    return info


_ADDON_INFO = _addon_manifest_info()
ADDON_ID = _ADDON_INFO.get('id', 'plugin.video.xvault')
ADDON_NAME = _ADDON_INFO.get('name', 'xVAULT')
ADDON_VERSION = _ADDON_INFO.get('version', '')

INSTALL_TIMEOUT = 90
INSTALL_OPTIONAL = False
DOWNLOAD_TIMEOUT = 20

# Some Kodi installations abort direct ZIP installs when a dependency is not
# already indexed locally. xVAULT declares runtime modules as optional in
# addon.xml, then enforces and installs the real runtime requirements here.
REQUIRED_EXTERNAL_ADDONS = set([
    'script.module.requests',
    'script.module.six',
    'script.module.pyaes',
    'script.module.pyqrcode',
    'script.module.infotagger',
    'script.module.resolveurl',
])
AUTO_INSTALL_OPTIONAL_EXTERNALS = set([
    'script.module.download-m3u8',
])
# Native xVAULT renderer. Kodi chooses its platform/ABI package;
# unlike Python dependencies, it must never use an external ZIP fallback.
AUTO_INSTALL_VISUALIZATIONS = set([
    'visualization.xvault',
])
# Binary inputstream add-ons are platform packages. Some Kodi builds, for
# example webOS ports, cannot provide every package. They remain optional and
# are never installed during the general startup bootstrap.
OPTIONAL_BINARY_ADDONS = set([
    'inputstream.adaptive',
    'inputstream.ffmpegdirect',
    'inputstream.rtmp',
])
# PVR clients are user-controlled Kodi components. xVAULT must not install or
# enable them during the general startup/update dependency pass.
EXTERNAL_ADDON_SOURCES = {
    'script.module.resolveurl': {
        'repository_id': 'repository.resolveurl',
        'repository_zip_urls': [
            'https://gujal00.github.io/repository.resolveurl-1.0.0.zip',
            'https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/repository.resolveurl/repository.resolveurl-1.0.0.zip',
        ],
        'metadata_url': 'https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml',
        'datadir': 'https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/',
    },
    'script.module.pyqrcode': {
        'repository_id': 'repository.resolveurl',
        'repository_zip_urls': [
            'https://gujal00.github.io/repository.resolveurl-1.0.0.zip',
            'https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/repository.resolveurl/repository.resolveurl-1.0.0.zip',
        ],
        'metadata_url': 'https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml',
        'datadir': 'https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/',
    },
    'script.module.download-m3u8': {
        'metadata_url': 'https://raw.githubusercontent.com/chrisklietsch/repository.kc-kodi/main/repo/addons.xml',
        'datadir': 'https://raw.githubusercontent.com/chrisklietsch/repository.kc-kodi/main/repo/',
    },
}

# Debug-only helper, not needed for normal playback/download features.
SKIP_OPTIONAL_INSTALL = set(['script.module.pydevd'])


def ensure_all_dependencies():
    """Install and enable missing Kodi dependencies before xVAULT imports them."""
    try:
        if _was_checked():
            return True

        dependencies = _dependencies_from_manifest()
        if not dependencies:
            _mark_checked()
            return True

        required = [
            addon_id
            for addon_id, optional, version in dependencies
            if _is_required(addon_id, optional)
        ]
        installable = [
            (addon_id, optional, version)
            for addon_id, optional, version in dependencies
            if _should_install(addon_id, optional)
        ]

        missing = [
            (addon_id, optional, version)
            for addon_id, optional, version in installable
            if not _has_addon(addon_id, version)
        ]
        if not missing:
            _enable_addons([addon_id for addon_id, optional, version in installable])
            _mark_checked()
            return True

        _notify('Installiere Abhängigkeiten...', 'INFO', 3000)
        for addon_id, optional, version in missing:
            _install_addon(addon_id, version)

        _enable_addons([addon_id for addon_id, optional, version in installable])

        still_missing = [
            addon_id
            for addon_id, optional, version in installable
            if not _has_addon(addon_id, version)
        ]
        missing_required = [addon_id for addon_id in still_missing if addon_id in required]

        if still_missing:
            _log('Missing dependencies after install: %s' % ', '.join(still_missing), xbmc.LOGWARNING)
            visible_missing = [a for a in still_missing if a not in AUTO_INSTALL_VISUALIZATIONS]
            if visible_missing:
                _notify('Abhängigkeiten fehlen: %s' % ', '.join(visible_missing[:3]), 'WARNING', 7000)

        success = len(missing_required) == 0
        if success:
            _mark_checked()
        return success
    except Exception as e:
        _log('Dependency check failed: %s' % str(e), xbmc.LOGERROR)
        return True


def install_addon(addon_id, min_version=None):
    """Install an add-on on demand using Kodi first and known external sources as fallback."""
    try:
        if _has_addon(addon_id, min_version):
            _enable_addons([addon_id])
            return True

        if not _install_addon(addon_id, min_version):
            return False

        _enable_addons([addon_id])
        _refresh_addons()
        return _has_addon(addon_id, min_version)
    except Exception as e:
        _log('On-demand install failed for %s: %s' % (addon_id, str(e)), xbmc.LOGERROR)
        return False


def _dependencies_from_manifest():
    addon_xml = os.path.join(_translate_path(ADDON_PATH), 'addon.xml')
    root = ET.parse(addon_xml).getroot()

    dependencies = []
    for node in root.findall('./requires/import'):
        addon_id = node.attrib.get('addon')
        if not addon_id or addon_id == 'xbmc.python' or addon_id == ADDON_ID:
            continue
        optional = node.attrib.get('optional', '').lower() == 'true'
        version = node.attrib.get('version')
        dependencies.append((addon_id, optional, version))

    return _unique_dependencies(dependencies)


def _unique_dependencies(dependencies):
    seen = set()
    result = []
    for addon_id, optional, version in dependencies:
        if addon_id in seen:
            continue
        seen.add(addon_id)
        if addon_id in AUTO_INSTALL_VISUALIZATIONS:
            from resources.lib.native_visuals import required_version
            version = required_version(xbmc) or version
        result.append((addon_id, optional, version))
    return result


def _is_required(addon_id, optional):
    return not optional or addon_id in REQUIRED_EXTERNAL_ADDONS


def _should_install(addon_id, optional):
    if addon_id in AUTO_INSTALL_VISUALIZATIONS:
        import xbmcaddon
        if xbmcaddon.Addon('plugin.video.xvault').getSetting('radio.enabled') == 'false':
            return False
    if addon_id in AUTO_INSTALL_VISUALIZATIONS and not native_visuals_supported():
        return False
    if optional and addon_id in SKIP_OPTIONAL_INSTALL:
        return False
    if optional and addon_id in OPTIONAL_BINARY_ADDONS:
        return False
    if addon_id in REQUIRED_EXTERNAL_ADDONS or addon_id in AUTO_INSTALL_OPTIONAL_EXTERNALS or addon_id in AUTO_INSTALL_VISUALIZATIONS:
        return True
    if optional and not INSTALL_OPTIONAL:
        return False
    return True


def native_visuals_supported():
    from resources.lib.native_visuals import profile
    return bool(profile(xbmc))


def _addon_version(addon_id):
    try:
        payload = json.dumps({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'Addons.GetAddonDetails',
            'params': {
                'addonid': addon_id,
                'properties': ['version'],
            },
        })
        response = json.loads(xbmc.executeJSONRPC(payload) or '{}')
        addon = response.get('result', {}).get('addon', {})
        return str(addon.get('version') or '').strip()
    except:
        return ''


def _has_addon(addon_id, min_version=None):
    try:
        if not bool(xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id)):
            return False
        if min_version:
            installed = _addon_version(addon_id)
            if not installed:
                return False
            return _compare_versions(installed, min_version) >= 0
        return True
    except:
        return False


def _install_addon(addon_id, min_version=None):
    if _has_addon(addon_id, min_version):
        return True

    if addon_id in AUTO_INSTALL_VISUALIZATIONS:
        if not _native_package_available(min_version):
            _log('No compatible native visualizer currently reachable; optional install skipped', xbmc.LOGINFO)
            return False
        if _addon_version(addon_id):
            return _update_native_visuals(min_version)
        _ensure_native_repository()
        _refresh_addons()  # Pick up the companion package before its first installation.

    if addon_id in EXTERNAL_ADDON_SOURCES:
        if _install_external_addon(addon_id, min_version):
            return True
        _log('External dependency source failed, falling back to Kodi repo: %s' % addon_id, xbmc.LOGWARNING)

    return _install_addon_from_kodi(addon_id, min_version)


def _ensure_native_repository():
    from resources.lib import repository
    repository.ensure_xvault_repository()


def _native_package_available(min_version=None):
    from resources.lib.native_visuals import profile
    from resources.lib.release_security import BASE_URL
    selected = profile(xbmc)
    if not selected:
        return False
    try:
        with urlopen(BASE_URL + 'updates/native/' + selected + '/addons.xml', timeout=5) as response:
            root = ET.fromstring(response.read(256 * 1024))
        node = root.find("addon[@id='visualization.xvault']")
        if node is None or node.find("./extension[@point='xbmc.addon.metadata']/platform").text != selected.split('/')[0]:
            return False
        dependency = node.find("./requires/import[@addon='kodi.binary.instance.visualization']")
        expected_api = '4.0.0' if selected.endswith('/kodi21') else '5.0.0'
        if dependency is None or dependency.get('version') != expected_api:
            return False
        return not min_version or _compare_versions(node.get('version', ''), min_version) >= 0
    except Exception:
        return False


def _native_descriptor(min_version=None):
    from resources.lib import release_security as security
    from resources.lib.native_visuals import profile
    selected = profile(xbmc)
    if not selected:
        raise DependencyError('Unsupported native profile')
    base = security.BASE_URL + 'updates/native/' + selected + '/'
    with urlopen(base + 'native.json', timeout=5) as response:
        data = security.verify_envelope(json.loads(response.read(256 * 1024)))
    if (data.get('schema') != 1 or data.get('kind') != 'native-addon' or
            data.get('addon_id') != 'visualization.xvault' or data.get('profile') != selected or
            not re.fullmatch(r'visualization\.xvault/visualization\.xvault-[0-9.]+\.zip', str(data.get('package', ''))) or
            not re.fullmatch(r'[0-9a-f]{64}', str(data.get('sha256', ''))) or
            not 0 < int(data.get('size', 0)) < 32 * 1024 * 1024 or
            (min_version and _compare_versions(data.get('version', ''), min_version) < 0)):
        raise DependencyError('Invalid native package reference')
    return data, base + data['package']


def _update_native_visuals(min_version=None):
    # Kodi's InstallAddon builtin returns early when an add-on is installed.
    # Replace a verified native package only while its player is not in use.
    if xbmc.getCondVisibility('Player.HasMedia'):
        _log('Native visualizer update deferred until a later idle startup', xbmc.LOGINFO)
        return False
    import uuid
    import shutil
    from resources.lib import release_security as security
    from resources.lib.native_visuals import profile
    stage = backup = target = temp_zip = ''
    moved_old = moved_new = False
    try:
        reference, url = _native_descriptor(min_version)
        temp_zip = _dependency_temp_path(url)
        _download_file(url, temp_zip)
        if os.path.getsize(temp_zip) != reference['size'] or security.sha256_file(temp_zip) != reference['sha256']:
            raise DependencyError('Native package checksum mismatch')
        parent = os.path.realpath(_translate_path('special://home/addons/'))
        target = os.path.join(parent, 'visualization.xvault')
        stage = os.path.join(parent, '.xvault-native-stage-' + uuid.uuid4().hex)
        backup = os.path.join(parent, '.xvault-native-backup-' + uuid.uuid4().hex)
        with zipfile.ZipFile(temp_zip) as archive:
            node = ET.fromstring(archive.read('visualization.xvault/addon.xml'))
            selected = profile(xbmc)
            api = node.find("./requires/import[@addon='kodi.binary.instance.visualization']")
            platform_node = node.find("./extension[@point='xbmc.addon.metadata']/platform")
            if (node.get('id') != reference['addon_id'] or node.get('version') != reference['version'] or
                    platform_node is None or platform_node.text != selected.split('/')[0] or api is None or
                    api.get('version') != ('4.0.0' if selected.endswith('/kodi21') else '5.0.0')):
                raise DependencyError('Native package ABI mismatch')
            _mkdir(stage)
            for entry in archive.infolist():
                name = _normalize_zip_name(entry.filename)
                if not name.startswith('visualization.xvault/') or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise DependencyError('Unsafe native package entry')
                relative = name[len('visualization.xvault/'):]
                if not relative or name.endswith('/'):
                    continue
                destination = _safe_join(stage, relative)
                _mkdir(os.path.dirname(destination))
                with archive.open(entry) as source, open(destination, 'wb') as output:
                    shutil.copyfileobj(source, output)
        if xbmc.getCondVisibility('Player.HasMedia'):
            return False
        xbmc.executeJSONRPC(json.dumps(dict(jsonrpc='2.0', id=1, method='Addons.SetAddonEnabled', params={'addonid':'visualization.xvault','enabled':False})))
        os.replace(target, backup); moved_old = True
        os.replace(stage, target); moved_new = True
        os.replace(os.path.join(backup, 'addon.xml'), os.path.join(backup, 'addon.xml.restore'))
        _refresh_addons(); _enable_addons(['visualization.xvault'])
        if not _wait_for_addon('visualization.xvault', reference['version'], timeout=10):
            raise DependencyError('Updated native package not registered')
        return True
    except Exception as exc:
        _log('Native visualizer update failed: ' + type(exc).__name__, xbmc.LOGWARNING)
        if moved_new:
            os.replace(target, stage)
        if moved_old:
            retired = os.path.join(backup, 'addon.xml.restore')
            if os.path.exists(retired):
                os.replace(retired, os.path.join(backup, 'addon.xml'))
            os.replace(backup, target)
            _refresh_addons(); _enable_addons(['visualization.xvault'])
        return False
    finally:
        if stage and os.path.isdir(stage) and os.path.dirname(os.path.realpath(stage)) == os.path.realpath(os.path.dirname(target)) and os.path.basename(stage).startswith('.xvault-native-stage-'):
            shutil.rmtree(stage)
        if temp_zip and os.path.isfile(temp_zip):
            os.remove(temp_zip)


def _install_addon_from_kodi(addon_id, min_version=None, timeout=INSTALL_TIMEOUT):
    _log('Installing dependency: %s' % addon_id, xbmc.LOGINFO)
    # InstallAddon may open a modal confirmation. Waiting for the builtin here
    # blocks its calling script before that confirmation can be handled.
    xbmc.executebuiltin('InstallAddon(%s)' % addon_id)

    _accept_install_dialog()
    if _wait_for_addon(addon_id, min_version, timeout):
        return True

    # Some skins show the confirmation dialog after InstallAddon returns.
    _accept_install_dialog()
    return _wait_for_addon(addon_id, min_version, timeout=15)


def _install_external_addon(addon_id, min_version=None):
    source = EXTERNAL_ADDON_SOURCES.get(addon_id)
    if not source:
        return False

    repository_id = source.get('repository_id')
    if repository_id and not _has_addon(repository_id):
        _install_external_repository(repository_id, source)

    if repository_id and _has_addon(repository_id):
        _enable_addons([repository_id])
        _refresh_addons()
        if _install_addon_from_kodi(addon_id, min_version, timeout=45):
            return True

    return _install_latest_addon_zip(addon_id, source, min_version)


def _install_external_repository(repository_id, source):
    for url in source.get('repository_zip_urls', []):
        if _install_zip_from_url(url, repository_id):
            _log('Installed external repository: %s' % repository_id, xbmc.LOGINFO)
            return True
    return False


def _install_latest_addon_zip(addon_id, source, min_version=None):
    try:
        node = _addon_node_from_metadata(addon_id, source['metadata_url'])
        version = node.attrib.get('version')
        if min_version and version and _compare_versions(version, min_version) < 0:
            _log('External source has old %s version: %s' % (addon_id, version), xbmc.LOGWARNING)
            return False

        if not _install_required_addons(_requirements_from_node(node), parent_id=addon_id):
            return False
        zip_url = _addon_zip_url(source['datadir'], addon_id, version)
        return _install_zip_from_url(zip_url, addon_id, min_version)
    except Exception as e:
        _log('External install failed for %s: %s' % (addon_id, str(e)), xbmc.LOGWARNING)
    return False


def _install_required_addons(dependencies, parent_id=None):
    success = True
    for addon_id, optional, version in dependencies:
        if optional or addon_id in ('xbmc.python', ADDON_ID, parent_id):
            continue
        if not _has_addon(addon_id, version):
            if not _install_addon(addon_id, version):
                success = False
    return success


def _install_zip_from_url(url, expected_id, min_version=None):
    temp_zip = _dependency_temp_path(url)
    try:
        _download_file(url, temp_zip)
        installed_id = _extract_addon_zip(temp_zip, expected_id)
        _refresh_addons()
        _enable_addons([installed_id])
        return _wait_for_addon(installed_id, min_version, timeout=20)
    except Exception as e:
        _log('Failed to install %s from %s: %s' % (expected_id, url, str(e)), xbmc.LOGWARNING)
    finally:
        try:
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
        except:
            pass
    return False


def _wait_for_addon(addon_id, min_version=None, timeout=INSTALL_TIMEOUT):
    deadline = time.time() + timeout
    monitor = xbmc.Monitor()
    while time.time() < deadline and not monitor.abortRequested():
        if _has_addon(addon_id, min_version):
            return True
        monitor.waitForAbort(1)
    return _has_addon(addon_id, min_version)


def _accept_install_dialog():
    try:
        for i in range(8):
            if xbmc.getCondVisibility('Window.IsActive(yesnoDialog)') or xbmc.getCondVisibility('Window.IsActive(DialogConfirm.xml)'):
                xbmc.executebuiltin('SendClick(11)')
                return
            xbmc.Monitor().waitForAbort(0.25)
    except:
        pass


def _enable_addons(addon_ids):
    for addon_id in addon_ids:
        if _has_addon(addon_id):
            _set_addon_enabled(addon_id)


def _set_addon_enabled(addon_id):
    try:
        request = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'Addons.SetAddonEnabled',
            'params': {
                'addonid': addon_id,
                'enabled': True,
            },
        }
        xbmc.executeJSONRPC(json.dumps(request))
    except:
        pass


def _refresh_addons():
    try:
        xbmc.executebuiltin('UpdateLocalAddons')
        xbmc.Monitor().waitForAbort(1)
        xbmc.executebuiltin('UpdateAddonRepos')
        xbmc.Monitor().waitForAbort(2)
    except:
        pass


def _addon_node_from_metadata(addon_id, metadata_url):
    content = _download_text(metadata_url)
    root = ET.fromstring(content)
    for node in root.findall('addon'):
        if node.attrib.get('id') == addon_id:
            return node
    raise DependencyError('Addon not found in metadata: %s' % addon_id)


def _requirements_from_node(node):
    dependencies = []
    for child in node.findall('./requires/import'):
        addon_id = child.attrib.get('addon')
        if not addon_id:
            continue
        optional = child.attrib.get('optional', '').lower() == 'true'
        dependencies.append((addon_id, optional, child.attrib.get('version')))
    return dependencies


def _addon_zip_url(datadir, addon_id, version):
    if not version:
        raise DependencyError('No version found for %s' % addon_id)
    base = datadir.rstrip('/') + '/'
    return '%s%s/%s-%s.zip' % (base, addon_id, addon_id, version)


def _download_text(url):
    response = _open_url(url)
    try:
        return response.read().decode('utf-8', 'replace')
    finally:
        _close_response(response)


def _download_file(url, destination):
    _mkdir(os.path.dirname(destination))
    response = _open_url(url)
    try:
        with open(destination, 'wb') as output:
            while True:
                chunk = response.read(1024 * 64)
                if not chunk:
                    break
                output.write(chunk)
    finally:
        _close_response(response)


def _open_url(url):
    request = Request(
        url,
        headers={
            'User-Agent': '%s/%s' % (ADDON_ID, ADDON_VERSION),
        },
    )
    return urlopen(request, timeout=DOWNLOAD_TIMEOUT)


def _close_response(response):
    try:
        response.close()
    except:
        pass


def _dependency_temp_path(url):
    filename = os.path.basename(url.split('?', 1)[0]) or 'dependency.zip'
    directory = os.path.join(_translate_path('special://temp/'), 'xvault-dependencies')
    _mkdir(directory)
    return os.path.join(directory, filename)


def _extract_addon_zip(path, expected_id):
    addons_dir = _translate_path('special://home/addons/')
    with zipfile.ZipFile(path) as archive:
        addon_xml = _find_addon_xml(archive)
        content = archive.read(addon_xml).decode('utf-8', 'replace')
        addon_id, version = _addon_xml_info(content)
        if addon_id != expected_id:
            raise DependencyError('Unexpected addon id in zip: %s' % addon_id)

        root = addon_xml.rsplit('/', 1)[0] if '/' in addon_xml else ''
        destination = os.path.join(addons_dir, addon_id)
        _mkdir(destination)

        for info in archive.infolist():
            name = _normalize_zip_name(info.filename)
            relative = _relative_name(name, root)
            if not relative or relative.endswith('/'):
                continue

            target = _safe_join(destination, relative)
            _mkdir(os.path.dirname(target))
            with archive.open(info) as source, open(target, 'wb') as output:
                while True:
                    chunk = source.read(1024 * 64)
                    if not chunk:
                        break
                    output.write(chunk)

    return addon_id


def _find_addon_xml(archive):
    for name in archive.namelist():
        normalized = _normalize_zip_name(name)
        if normalized.endswith('/addon.xml') or normalized == 'addon.xml':
            return normalized
    raise DependencyError('addon.xml not found in dependency zip')


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
        raise DependencyError('Unsafe path in dependency zip: %s' % relative)

    target = os.path.abspath(os.path.join(base, *parts))
    base = os.path.abspath(base)
    if target != base and not target.startswith(base + os.sep):
        raise DependencyError('Unsafe path in dependency zip: %s' % relative)
    return target


def _normalize_zip_name(name):
    return name.replace('\\', '/').lstrip('/')


def _addon_xml_info(content):
    try:
        root = ET.fromstring(content)
        return root.attrib.get('id'), root.attrib.get('version')
    except:
        addon_id = _find_attr(content, 'id')
        version = _find_attr(content, 'version')
        return addon_id, version


def _find_attr(content, attr):
    match = re.search(r'\b%s=[\'"]([^\'"]+)[\'"]' % attr, content)
    return match.group(1) if match else None


def _compare_versions(left, right):
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
    for part in re.findall(r'\d+|[A-Za-z]+', str(version or '0')):
        if part.isdigit():
            parts.append((1, int(part)))
        else:
            parts.append((0, part.lower()))
    return parts


def _mkdir(path):
    if not path or os.path.exists(path):
        return
    os.makedirs(path)


class DependencyError(Exception):
    pass


def _was_checked():
    try:
        if not xbmcgui:
            return False
        value = xbmcgui.Window(10000).getProperty(_checked_property())
        return value == _checked_value()
    except:
        return False


def _mark_checked():
    try:
        if xbmcgui:
            xbmcgui.Window(10000).setProperty(_checked_property(), _checked_value())
    except:
        pass


def _checked_property():
    return '%s.dependencies.checked' % ADDON_ID


def _checked_value():
    try:
        dependencies = [
            '%s:%s:%s' % (addon_id, '1' if optional else '0', version or '')
            for addon_id, optional, version in _dependencies_from_manifest()
            if _should_install(addon_id, optional)
        ]
        return '%s|%s' % (ADDON_VERSION, ','.join(dependencies))
    except:
        return ADDON_VERSION


def _translate_path(path):
    if xbmcvfs and hasattr(xbmcvfs, 'translatePath'):
        return xbmcvfs.translatePath(path)
    if sys.version_info.major == 2:
        return xbmc.translatePath(path).decode('utf-8')
    return xbmc.translatePath(path)


def _notify(message, icon='INFO', time_ms=5000):
    try:
        if not xbmcgui:
            return
        icon_value = getattr(xbmcgui, 'NOTIFICATION_%s' % icon, xbmcgui.NOTIFICATION_INFO)
        xbmcgui.Dialog().notification(ADDON_NAME, message, icon_value, time_ms, sound=False)
    except:
        pass


def _log(message, level):
    try:
        xbmc.log('[xVAULT.dependencies] %s' % message, level)
    except:
        pass
