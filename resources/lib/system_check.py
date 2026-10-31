"""Human-readable diagnostics. No credentials, playback URLs or automatic repair."""
import json
import time
from resources.lib import control


def home():
    import xbmcplugin
    from resources.lib import personal, distribution, updater, dependencies
    from resources.lib.sync import storage, engine
    origin = distribution.cached_status() or {}
    state = updater.read_state()
    personal.add('Updates · %s · %s' % (updater.selected_channel(), state.get('message', 'noch nicht geprüft')), 'updateCheck',
                 description='Prüft das aktuelle Angebot des gewählten Kanals; installiert nichts.')
    integrity = origin.get('integrity', {}).get('state', 'noch nicht geprüft')
    personal.add('Originalpaket · ' + integrity, 'distributionStatus', description=origin.get('summary', 'Originalprüfung öffnen'))
    personal.add('Originalpaket aktualisieren oder reparieren …', 'updateInstall', description='Erst nach Bestätigung; ersetzt Add-on-Dateien durch das signierte Originalpaket.')
    logged = storage.is_logged_in()
    sync = engine.inspect() if logged else {}
    label = 'angemeldet' if logged else 'nicht angemeldet'
    if not storage.is_enabled():
        label += ', Abgleich deaktiviert'
    personal.add('Geräte-Sync · ' + label, 'syncStatus' if logged else 'syncLogin', description='Letzter Abgleich: %s · %d ausstehend · %d Konflikte' %
                 (storage.get_setting(storage.LAST_SYNC_AT) or 'noch keiner', sync.get('pending', 0), len(sync.get('conflicts', []))))
    personal.add('Geräte-Sync jetzt abgleichen', 'syncNow', description='Übernimmt Kontostände und sendet ausstehende lokale Änderungen über das bestehende Konfliktprotokoll.')
    if logged:
        personal.add('Geräte, Verlauf und Konflikte verwalten', 'syncDevices')
    missing = []
    for addon_id in sorted(dependencies.REQUIRED_EXTERNAL_ADDONS):
        if not dependencies._has_addon(addon_id):
            missing.append(addon_id)
    personal.add('Abhängigkeiten · ' + ('vollständig' if not missing else '%d fehlen' % len(missing)), 'systemRepairDependencies',
                 description='Erneut prüfen und fehlende erforderliche Module installieren. ' + ', '.join(missing))
    supported = dependencies.native_visuals_supported()
    personal.add('xVAULT-Visuals · ' + ('verfügbar' if dependencies._has_addon('visualization.xvault') else 'noch nicht installiert' if supported else 'für diese Plattform/Kodi-Version nicht verfügbar'),
                 'addonSettings', description='Optionale native Visualisierung; Radio funktioniert auch ohne dieses Paket.')
    network = storage.read_json('system-check.json', {})
    for name, result in network.get('services', {}).items():
        personal.add('%s · %s' % (name, result), 'systemNetwork', description='Letzte Prüfung: ' + time.strftime('%d.%m.%Y %H:%M', time.localtime(network.get('checked', 0))))
    personal.add('Dienste-Erreichbarkeit jetzt prüfen', 'systemNetwork', description='Prüft Update-Feed, Sync-API, TMDb und Radio Browser im Hintergrund mit kurzen Zeitlimits; benötigt keine Anmeldung.')
    personal.add('Einstellungen auf Fehler prüfen …', 'repairSettings')
    personal.add('System- und Supportinformationen', 'pluginInfo')
    xbmcplugin.setPluginCategory(int(__import__('sys').argv[1]), 'Systemcheck')
    xbmcplugin.addSortMethod(int(__import__('sys').argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(int(__import__('sys').argv[1]), cacheToDisc=False)


def network():
    import xbmcgui
    import xbmc
    import os
    if xbmcgui.Window(10000).getProperty('xvault.systemcheck.running'):
        control.infoDialog('Diensteprüfung läuft bereits.')
        return
    xbmcgui.Window(10000).setProperty('xvault.systemcheck.running', 'true')
    xbmc.executebuiltin('RunScript(%s)' % os.path.join(control.addonPath, 'resources', 'lib', 'system_probe.py'))
    control.infoDialog('Dienste werden im Hintergrund geprüft; Ergebnis anschließend im Systemcheck öffnen.')


def run_probe():
    import xbmcgui
    from resources.lib.requestHandler import cRequestHandler
    from resources.lib import release_security
    from resources.lib.sync import storage
    from resources.lib.tmdb import cTMDB
    from urllib.parse import urlencode
    urls = [('Update-Server', release_security.BASE_URL + 'updates/release.json'),
            ('Sync-API', 'https://all-stats.de/index.php?action=status'),
            ('TMDb', cTMDB.URL + 'configuration?' + urlencode({'api_key': cTMDB().api_key}))]
    results = {}
    try:
        for name, url in urls:
            try:
                raw = cRequestHandler(url, caching=False).request_bounded(timeout=3, budget=5)
                data = json.loads(raw)
                if name == 'Sync-API' and data.get('success') is not True:
                    raise ValueError('API status rejected')
                results[name] = 'erreichbar'
            except Exception as exc:
                results[name] = 'nicht bestätigt (%s)' % type(exc).__name__
        from resources.lib.radio_browser import SERVERS
        results['Radio Browser'] = 'nicht bestätigt (alle geprüften Server)'
        for host in SERVERS:
            try:
                data = json.loads(cRequestHandler('https://' + host + '/json/stats', caching=False).request_bounded(timeout=3, budget=5))
                if not isinstance(data, dict) or 'stations' not in data:
                    raise ValueError('Invalid radio API reply')
                results['Radio Browser'] = 'erreichbar'
                break
            except Exception:
                continue
        storage.write_json('system-check.json', dict(checked=time.time(), services=results))
    finally:
        xbmcgui.Window(10000).clearProperty('xvault.systemcheck.running')


def repair_dependencies():
    from resources.lib import dependencies
    import xbmcgui
    if xbmcgui.Dialog().yesno('Abhängigkeiten reparieren', 'Fehlende erforderliche Module über die vorhandenen Installationswege nachladen?'):
        # Explicitly bypass only the session check, not the package/platform guards.
        for addon_id in sorted(dependencies.REQUIRED_EXTERNAL_ADDONS):
            if not dependencies._has_addon(addon_id):
                dependencies.install_addon(addon_id)
        dependencies._refresh_python_module_paths(list(dependencies.REQUIRED_EXTERNAL_ADDONS))
        control.infoDialog('Abhängigkeiten geprüft. Systemcheck erneut öffnen.')
