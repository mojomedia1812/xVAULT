"""Runs as a copied standalone Kodi script so the addon service can be stopped."""
import json
import os
import shutil
import sys
import time


def replace_tree(stage, target, backup):
    """Same-filesystem switch with rollback. Never touches addon_data."""
    parent = os.path.realpath(os.path.dirname(target))
    for path in (stage, target, backup):
        if os.path.dirname(os.path.realpath(path)) != parent or os.path.islink(path):
            raise ValueError('Unsafe installation path')
    if os.path.basename(target) != 'plugin.video.xvault' or not os.path.basename(stage).startswith('.xvault-stage-') or not os.path.basename(backup).startswith('.xvault-backup-'):
        raise ValueError('Unexpected installation directory')
    moved_old = False
    try:
        if os.path.exists(target):
            os.replace(target, backup)
            moved_old = True
        os.replace(stage, target)
    except Exception:
        if moved_old:
            os.replace(backup, target)
        raise


def cleanup_artifacts(job, installed):
    parent = os.path.realpath(os.path.dirname(job['target']))
    stage = job['stage']
    if not installed and os.path.isdir(stage) and not os.path.islink(stage):
        if os.path.dirname(os.path.realpath(stage)) == parent and os.path.basename(stage).startswith('.xvault-stage-'):
            shutil.rmtree(stage)
    if not installed:
        return
    marker = '.xvault-update-backup.json'
    with open(os.path.join(job['backup'], marker), 'w', encoding='utf-8') as f:
        json.dump({'addon_id': 'plugin.video.xvault'}, f)
    backups = []
    for name in os.listdir(parent):
        path = os.path.join(parent, name)
        if not name.startswith('.xvault-backup-') or os.path.islink(path):
            continue
        try:
            with open(os.path.join(path, marker), encoding='utf-8') as f:
                if json.load(f).get('addon_id') == 'plugin.video.xvault':
                    backups.append(path)
        except (OSError, ValueError):
            pass
    for path in sorted(backups, key=os.path.getmtime, reverse=True)[2:]:
        if os.path.dirname(os.path.realpath(path)) == parent:
            shutil.rmtree(path)


def main(job_file):
    import xbmc
    import xbmcvfs
    with open(job_file, encoding='utf-8') as f:
        job = json.load(f)
    addons = os.path.realpath(xbmcvfs.translatePath('special://home/addons/'))
    target = os.path.join(addons, 'plugin.video.xvault')
    if os.path.realpath(job['target']) != target:
        raise ValueError('Unexpected addon target')
    sys.path.insert(0, target)
    from resources.lib import release_security as security
    from resources.lib import update_maintenance as maintenance
    def rpc(method, params):
        result = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 82, 'method': method, 'params': params})))
        if result.get('error'):
            raise RuntimeError(str(result['error']))
        return result.get('result')
    result = {'state': 'failed', 'version': job['version']}
    disabled = False
    installed = False
    maintenance_token = ''
    try:
        check = security.inspect_tree(job['stage'])
        if check['state'] != 'original' or check['build_id'] != job['build_id']:
            raise ValueError('Staged package failed final integrity check')
        if rpc('Player.GetActivePlayers', {}):
            raise RuntimeError('Wiedergabe aktiv; Installation wurde verschoben')
        win = maintenance.window()
        maintenance_token = os.path.basename(job['stage'])
        if win.getProperty(maintenance.RUNNING):
            win.setProperty(maintenance.REQUEST, maintenance_token)
            for _ in range(900):
                if win.getProperty(maintenance.STOPPED) == maintenance_token:
                    break
                xbmc.sleep(100)
            else:
                raise RuntimeError('Hintergrunddienst noch aktiv; Installation wurde verschoben')
        rpc('Addons.SetAddonEnabled', {'addonid': 'plugin.video.xvault', 'enabled': False})
        disabled = True
        # Wait for the service threads to observe Kodi's abort signal.
        xbmc.sleep(2000)
        replace_tree(job['stage'], target, job['backup'])
        installed = True
        # Backups must not look like a second installed addon to Kodi's scanner.
        backup_xml = os.path.join(job['backup'], 'addon.xml')
        if os.path.exists(backup_xml):
            os.replace(backup_xml, backup_xml + '.restore')
        xbmc.executebuiltin('UpdateLocalAddons')
        for _ in range(30):
            data = rpc('Addons.GetAddonDetails', {'addonid': 'plugin.video.xvault', 'properties': ['version']})
            if data['addon']['version'] == job['version']:
                break
            xbmc.sleep(500)
        else:
            raise RuntimeError('Kodi meldet nicht die installierte Zielversion')
        rpc('Addons.SetAddonEnabled', {'addonid': 'plugin.video.xvault', 'enabled': True})
        disabled = False
        result.update(state='installed', build_id=job['build_id'], backup=job['backup'])
    except Exception as exc:
        result['message'] = str(exc)
        if installed:
            failed = job['stage']
            os.replace(target, failed)
            backup_xml = os.path.join(job['backup'], 'addon.xml')
            if os.path.exists(backup_xml + '.restore'):
                os.replace(backup_xml + '.restore', backup_xml)
            os.replace(job['backup'], target)
            xbmc.executebuiltin('UpdateLocalAddons')
        if disabled:
            rpc('Addons.SetAddonEnabled', {'addonid': 'plugin.video.xvault', 'enabled': True})
    finally:
        if maintenance_token:
            maintenance.window().clearProperty(maintenance.REQUEST)
            maintenance.window().clearProperty(maintenance.STOPPED)
        result['finished_at'] = int(time.time())
        with open(job['result'], 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        if os.path.exists(job['lockfile']):
            os.remove(job['lockfile'])
        try:
            cleanup_artifacts(job, result['state'] == 'installed')
        except OSError:
            xbmc.log('xVAULT: Update-Sicherung konnte nicht bereinigt werden', xbmc.LOGWARNING)
        import xbmcgui
        xbmcgui.Dialog().notification('xVAULT Update',
            'Version %s installiert. xVAULT bitte neu oeffnen.' % job['version'] if result['state'] == 'installed' else
            'Update nicht installiert; bisherige Version bleibt erhalten.', time=7000)


if __name__ == '__main__':
    main(sys.argv[1])
