# edit 2026-06-14

import json
import os
import shutil
import sys

import xbmc

try:
    import xbmcvfs
except Exception:
    xbmcvfs = None

from resources.lib import control


REPOSITORY_ID = 'repository.xvault'
TEMPLATE_FILE = os.path.join(control.addonPath, 'resources', 'repository', 'addon.xml')
SOURCE_ICON = os.path.join(control.addonPath, 'resources', 'icon.png')


def ensure_xvault_repository():
    """Create and enable the xVAULT Kodi repository after zip installs."""
    try:
        repo_dir = os.path.join(_translate_path('special://home/addons/'), REPOSITORY_ID)
        addon_xml = os.path.join(repo_dir, 'addon.xml')
        icon = os.path.join(repo_dir, 'icon.png')

        changed = False
        _mkdir(repo_dir)

        template = _read_text(TEMPLATE_FILE)
        if _read_text(addon_xml) != template:
            _write_text(addon_xml, template)
            changed = True

        if _copy_if_needed(SOURCE_ICON, icon):
            changed = True

        if changed or not _has_repository():
            _refresh_addons()
            _enable_repository()
            _refresh_repositories()
        return True
    except Exception as e:
        _log('Repository bootstrap failed: %s' % str(e), xbmc.LOGWARNING)
        return False


def _has_repository():
    try:
        return bool(xbmc.getCondVisibility('System.HasAddon(%s)' % REPOSITORY_ID))
    except Exception:
        return False


def _enable_repository():
    try:
        request = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'Addons.SetAddonEnabled',
            'params': {
                'addonid': REPOSITORY_ID,
                'enabled': True,
            },
        }
        xbmc.executeJSONRPC(json.dumps(request))
    except Exception:
        pass


def _refresh_addons():
    try:
        xbmc.executebuiltin('UpdateLocalAddons')
        xbmc.Monitor().waitForAbort(1)
    except Exception:
        pass


def _refresh_repositories():
    try:
        xbmc.executebuiltin('UpdateAddonRepos')
        xbmc.Monitor().waitForAbort(1)
    except Exception:
        pass


def _copy_if_needed(source, destination):
    try:
        if os.path.exists(destination) and os.path.getsize(destination) == os.path.getsize(source):
            return False
        shutil.copyfile(source, destination)
        return True
    except Exception:
        return False


def _read_text(path):
    try:
        with open(path, 'rb') as handle:
            return handle.read().decode('utf-8')
    except Exception:
        return ''


def _write_text(path, content):
    with open(path, 'wb') as handle:
        handle.write(content.encode('utf-8'))


def _mkdir(path):
    if not path or os.path.exists(path):
        return
    os.makedirs(path)


def _translate_path(path):
    if xbmcvfs and hasattr(xbmcvfs, 'translatePath'):
        return xbmcvfs.translatePath(path)
    if sys.version_info.major == 2:
        return xbmc.translatePath(path).decode('utf-8')
    return xbmc.translatePath(path)


def _log(message, level):
    try:
        xbmc.log('[xVAULT.repository] %s' % message, level)
    except Exception:
        pass
