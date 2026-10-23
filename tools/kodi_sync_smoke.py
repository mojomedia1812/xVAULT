"""Run inside installed Kodi using RunScript(path, private-config.json, phase).

The config must reference a loopback-only LocalAPI test fixture. Settings,
favorites, auth, playcount databases and bookmarks live in a separate sandbox.
No production account, settings or favorites are changed by this script.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import time
import traceback
from urllib.parse import urlparse

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
if urlparse(config['base']).hostname not in ('127.0.0.1', 'localhost'):
    raise RuntimeError('Kodi sync smoke tests require a loopback test API')
sys.path.insert(0, config['addon_path'])
sandbox = Path(config['sandbox'])
sandbox.mkdir(parents=True, exist_ok=True)
phase = sys.argv[2] if len(sys.argv) > 2 else 'test'
results = []

from resources.lib import control
settings = {}
active = 'A'
control.dataPath = control.addonProfilePath = str(sandbox / active)
Path(control.dataPath).mkdir(exist_ok=True)
control.getSetting = lambda key, default='': settings.setdefault(active, {}).get(key, default)
control.setSetting = lambda key, value: settings.setdefault(active, {}).__setitem__(key, value)

from resources.lib.sync import engine, storage, device, api_client, favorites_sync, binge_sync, account
from resources.lib import playcountDB, bookmarkDB
api_client.API_BASES = (config['base'],)
engine._request_property = lambda: 'xvault.sync.smoke.request'


def activate(name):
    global active
    active = name
    folder = sandbox / name
    folder.mkdir(exist_ok=True)
    settings.setdefault(name, {'sync.device_id': name, 'sync.device_name': 'Kodi Test ' + name})
    control.dataPath = control.addonProfilePath = str(folder)
    storage.reconcile_auth_settings()
    favorites_sync.favourites_path = lambda: str(folder / 'favourites.xml')
    playcountDB.playcountDB = str(folder / 'playcount.db')
    with closing(sqlite3.connect(playcountDB.playcountDB)) as db:
        for table in ('movie', 'episode', 'season', 'tvshow'):
            db.execute(playcountDB._createSql(table))
        db.commit()


def check(name, callback):
    callback()
    results.append({'name': name, 'status': 'PASS'})
    (sandbox / ('results-%s.json' % phase)).write_text(json.dumps(results, indent=2), encoding='utf-8')


def expect(condition, reason):
    if not condition:
        raise AssertionError(reason)


def add_favorite(label):
    entries = favorites_sync._delta_entries()
    entries.append({'label': label, 'path': 'plugin://plugin.video.xvault/?sync-test=' + label})
    favorites_sync.write_favourites(favorites_sync._build_xml(entries))


def main():
    if phase == 'large-snapshot':
        activate('H')
        data = api_client.Client().login(config['email'], config['password'])
        storage.save_login(config['email'], data['api_key'])
        entities = [dict(kind='progress', key='%064x' % index, revision=index + 1, deleted=False,
                         data={'value': dict(item_key='%064x' % index, title='Volume %s' % index,
                                             name='Volume %s (2026)' % index, year='2026', completed=True,
                                             position_seconds=7200, extra={'mediatype': 'movie', 'imdb_id': 'tt9%06d' % index})})
                    for index in range(1000)]
        class Snapshot:
            def exchange(self, payload):
                return dict(protocol=2, revision=1000, entities=entities, devices=[], activity=[], conflicts=[], results=[])
        original = binge_sync.apply_local_states
        batches = []
        def counted(items, cleared):
            batches.append(len(items))
            return original(items, cleared)
        binge_sync.apply_local_states = counted
        started = time.monotonic()
        engine.synchronize(client=Snapshot())
        initial = time.monotonic() - started
        started = time.monotonic()
        engine.synchronize(client=Snapshot())
        repeated = time.monotonic() - started
        expect(batches == [1000], 'Unchanged history was applied again')
        expect(len(playcountDB.getWatchedItems()['movies']) == 1000, 'Large history lost entries')
        results.append({'name': 'thousand-items-and-unchanged-poll', 'status': 'PASS',
                        'initial_seconds': round(initial, 3), 'unchanged_seconds': round(repeated, 3), 'batches': batches})
        return
    if phase == 'no-echo':
        activate('C')
        add_favorite('Kodi-independent-C')
        engine.synchronize()
        activate('D')
        add_favorite('Kodi-independent-D')
        engine.synchronize()
        before = engine.inspect()['revision']
        engine.synchronize()
        expect(engine.inspect()['revision'] == before, 'Remote changes were echoed as local edits')
        expect('Kodi-independent-C' in favorites_sync.read_favourites(), 'Independent addition lost')
        results.append({'name': 'concurrent-favorites-do-not-trigger-sync-echo', 'status': 'PASS'})
        return
    if phase == 'bootstrap':
        activate('F')
        data = api_client.Client().login(config['email'], config['password'])
        storage.save_login(config['email'], data['api_key'])
        add_favorite('Kodi-legacy-import')
        storage.write_json(binge_sync.FILENAME, {'items': [dict(
            item_key='old-local-key', title='Kodi Legacy', name='Kodi Legacy (2026)', year='2026',
            position_seconds=900, duration_seconds=7200, completed=False, provider='xvault',
            extra={'mediatype': 'movie', 'tmdb_id': '99887766'})]})
        engine.synchronize()
        expect(engine.inspect()['pending'] == 0, 'Initial import was not acknowledged')
        activate('G')
        data = api_client.Client().login(config['email'], config['password'])
        storage.save_login(config['email'], data['api_key'])
        engine.synchronize()
        expect('Kodi-legacy-import' in favorites_sync.read_favourites(), 'Initial favorite missing')
        key = binge_sync._bookmark_id('Kodi Legacy (2026)', '2026')
        expect(bookmarkDB.get_query(key, 'bookmarks')[1] == '900', 'Initial local history missing')
        results.append({'name': 'first-login-imports-existing-local-favorites-and-history', 'status': 'PASS'})
        return
    if phase == 'checkpoint':
        activate('A')
        from resources.lib.player import player
        instance = player()
        instance.meta = {'mediatype': 'movie', 'title': 'Kodi Callback Test', 'year': 2026, 'tmdb_id': '76541234'}
        instance.name, instance.year = 'Kodi Callback Test (2026)', '2026'
        instance.currentTime, instance.totalTime = 900, 7200
        instance._sync_session = 'kodi-callback-test'
        instance._sync_sequence = 0
        key = binge_sync.item_key(instance.meta, instance.name, instance.year)
        instance._sync_base = engine.playback_base(key)
        instance._sync_watch_base = engine.playback_base(key, 'watch')
        instance._sync_watch_recorded = False
        instance._syncCheckpoint(completed=False)
        instance.currentTime = 600  # An intentional rewind must be retained.
        instance.onPlayBackPaused()
        activate('C')
        engine.synchronize()
        bookmark = binge_sync._bookmark_id(instance.name, instance.year)
        expect(bookmarkDB.get_query(bookmark, 'bookmarks')[1] == '600', 'Real player checkpoint/pause callback failed')
        results.append({'name': 'real-kodi-player-checkpoint-and-pause-callbacks', 'status': 'PASS'})
        return
    if phase == 'seed-conflict':
        activate('B')
        meta = {'mediatype': 'movie', 'title': 'Kodi Sync Test', 'tmdb_id': '87654321', 'year': 2026}
        binge_sync.record_playback(meta, 'Kodi Sync Test (2026)', '2026', 300, 7200, completed=False, session_id='kodi-ui-conflict', base_revision=-1, sequence=1)
        expect(bool(engine.inspect()['conflicts']), 'UI conflict missing')
        results.append({'name': 'resume-conflict-seeded', 'status': 'PASS'})
        return
    if phase in ('ui', 'resume-ui'):
        activate('B')
        if phase == 'ui':
            account.manage_devices()
        else:
            item = next(e for e in engine.inspect()['entities'] if e['kind'] == 'progress' and e['data']['value'].get('title') == 'Kodi Sync Test')
            account.choose_resume(item['key'])
        return
    if phase == 'restart':
        for name in 'ABCDE':
            activate(name)
            expect(storage.is_logged_in(), 'Login did not survive interpreter restart')
            engine.synchronize(active=True)
            expect('Kodi-A' in favorites_sync.read_favourites(), 'Favorite lost across restart')
        results.append({'name': 'five-profiles-login-and-state-survive-kodi-interpreter-restart', 'status': 'PASS'})
        return
    def logins():
        for name in 'ABCDE':
            activate(name)
            data = api_client.Client().login(config['email'], config['password'])
            storage.save_login(config['email'], data['api_key'])
            engine.synchronize(active=True)
        expect(len(engine.inspect()['devices']) == 5, 'Expected five registered devices')
    check('five-simultaneous-device-logins', logins)
    def handoff():
        activate('A')
        add_favorite('Kodi-A')
        engine.synchronize()
        activate('B')
        engine.on_wake()
        request = engine.background_request()
        expect(request.get('active') and request.get('account') == config['email'], 'Wake did not queue background sync')
        engine.synchronize(active=request['active'])  # Isolated service consumer.
        expect('Kodi-A' in favorites_sync.read_favourites(), 'A -> B missing')
        add_favorite('Kodi-B')
        engine.synchronize()
        activate('A')
        engine.synchronize()
        expect('Kodi-B' in favorites_sync.read_favourites(), 'B -> A missing')
    check('a-b-a-handoff-including-wake', handoff)
    def offline():
        add_favorite('Kodi-offline')
        class Offline:
            def exchange(self, payload):
                raise TimeoutError('Test offline')
        try:
            engine.synchronize(client=Offline())
        except TimeoutError:
            pass
        expect(engine.inspect()['pending'] == 1, 'Offline change was not persisted')
        engine.synchronize()
        expect(engine.inspect()['pending'] == 0, 'Outbox did not drain')
        activate('E')
        engine.synchronize()
        expect('Kodi-offline' in favorites_sync.read_favourites(), 'Offline change missing on E')
    check('offline-outbox-and-reconnect', offline)
    def playback():
        meta = {'mediatype': 'movie', 'title': 'Kodi Sync Test', 'imdb_id': 'tt7654321', 'tmdb_id': '87654321', 'year': 2026}
        activate('A')
        key = binge_sync.item_key(meta, 'Kodi Sync Test (2026)', '2026')
        binge_sync.record_playback(meta, 'Kodi Sync Test (2026)', '2026', 1200, 7200, completed=False, session_id='kodi-a', base_revision=-1, sequence=1)
        activate('B')
        engine.synchronize()
        bookmark = binge_sync._bookmark_id('Kodi Sync Test (2026)', '2026')
        expect(bookmarkDB.get_query(bookmark, 'bookmarks')[1] == '1200', 'Remote resume was not written to Kodi bookmark store')
        # Simulate B having started before seeing A's playback session.
        binge_sync.record_playback(meta, 'Kodi Sync Test (2026)', '2026', 600, 7200, completed=False, session_id='kodi-b', base_revision=-1, sequence=1)
        state = engine.inspect()
        expect(len(state['conflicts']) == 1, 'Concurrent playback must retain an alternative')
        engine.resolve(state['conflicts'][0], use_local=True)
        engine.synchronize()
        activate('A')
        engine.synchronize()
        expect(bookmarkDB.get_query(bookmark, 'bookmarks')[1] == '600', 'Chosen playback alternative was not transferred')
        # Manual watched/unwatched goes through the real playcount database.
        manual = dict(meta, sysname='Kodi Sync Test (2026)')
        binge_sync.update_watch_status(manual, watched=True)
        activate('B')
        engine.synchronize()
        expect(binge_sync.is_movie_watched(meta), 'Manual watched status not reflected')
        binge_sync.update_watch_status(manual, watched=False)
        activate('A')
        engine.synchronize()
        expect(not binge_sync.is_movie_watched(meta), 'Manual unwatched status not reflected')
        expect(not bookmarkDB.get_query(bookmark, 'bookmarks'), 'Manual reset retained an obsolete resume bookmark')
    check('resume-conflict-resolution-and-watch-status-in-real-kodi-stores', playback)
    def journal():
        state = engine.inspect()
        actors = {e['device_id'] for e in state['activity']}
        expect({'A', 'B'} <= actors, 'Change authors missing')
        expect(all('event_sequence' in e for e in state['activity']), 'Server journal order missing')
        expect(all('last_used_at' in d for d in state['devices']), 'Last-used information missing')
    check('device-authorship-and-last-used-journal', journal)


try:
    main()
except Exception:
    results.append({'name': 'exception', 'status': 'FAIL', 'traceback': traceback.format_exc()})
finally:
    import xbmcgui
    xbmcgui.Window(10000).clearProperty(engine._request_property())
    (sandbox / ('results-%s.json' % phase)).write_text(json.dumps(results, indent=2), encoding='utf-8')
