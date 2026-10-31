"""Real Python sync engine + real PHP API; Kodi interfaces use temporary files."""
import importlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.parse import parse_qsl

from tools.tests.test_sync_protocol import LocalAPI
from tools.tests.test_sync_protocol import ROOT


class DeviceClientTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='xvault-clients-')
        self.addCleanup(self.folder.cleanup)
        self.api = LocalAPI()
        self.addCleanup(self.api.close)
        self.name = 'A'
        self.settings = {}
        self.playing = False
        self.control = types.ModuleType('resources.lib.control')
        self.control.getSetting = lambda key, default='': self.settings[self.name].get(key, default)
        self.control.setSetting = lambda key, value: self.settings[self.name].__setitem__(key, value)
        self.control.translatePath = lambda path: str(Path(self.control.dataPath) / 'favourites.xml')
        self.control.parse_qsl = parse_qsl
        self.control.addonId = 'plugin.video.xvault'
        self.control.infoDialog = lambda *a, **k: None
        log = types.SimpleNamespace(log=lambda *a, **k: None, LOGWARNING=2, LOGERROR=3)
        xbmc = types.SimpleNamespace(Player=lambda: types.SimpleNamespace(isPlayingVideo=lambda: self.playing), getInfoLabel=lambda _: 'Test Kodi')
        vfs = types.SimpleNamespace(exists=lambda p: Path(p).exists(), mkdir=lambda p: Path(p).mkdir(exist_ok=True))
        self.activate('A', init=False)
        modules = {'resources.lib.control': self.control, 'resources.lib.log_utils': log, 'xbmc': xbmc, 'xbmcvfs': vfs}
        # Another test may already have imported resources.lib. A fresh module
        # dictionary alone leaves stale attributes on that surviving package,
        # pointing at a previous test's deleted profile and database.
        library = types.ModuleType('resources.lib')
        library.__path__ = [str(ROOT / 'resources/lib')]
        library.control, library.log_utils = self.control, log
        sync_package = types.ModuleType('resources.lib.sync')
        sync_package.__path__ = [str(ROOT / 'resources/lib/sync')]
        library.sync = sync_package
        modules.update({'resources.lib': library, 'resources.lib.sync': sync_package})
        module_patch = patch.dict(sys.modules, modules)
        module_patch.start()
        self.addCleanup(module_patch.stop)
        for key in list(sys.modules):
            if key.startswith('resources.lib.') and key not in modules:
                del sys.modules[key]
        self.storage = importlib.import_module('resources.lib.sync.storage')
        self.engine = importlib.import_module('resources.lib.sync.engine')
        self.favorites = importlib.import_module('resources.lib.sync.favorites_sync')
        self.binge = importlib.import_module('resources.lib.sync.binge_sync')
        self.bookmarks = importlib.import_module('resources.lib.bookmarkDB')
        self.playcounts = importlib.import_module('resources.lib.playcountDB')
        self.client_module = importlib.import_module('resources.lib.sync.api_client')
        self.client_module.API_BASES = (self.api.base,)
        self.tokens = {}
        for name in 'ABCDE':
            self.activate(name)
            self.tokens[name] = self.api.login(name)
            self.storage.save_login(self.api.email, self.tokens[name])
            self.engine.synchronize()
        self.activate('A')

    def activate(self, name, init=True):
        self.name = name
        folder = Path(self.folder.name) / name
        folder.mkdir(exist_ok=True)
        self.settings.setdefault(name, {'sync.device_id': name, 'sync.device_name': name})
        self.control.dataPath = self.control.addonProfilePath = str(folder)
        if init:
            self.playcounts.playcountDB = str(folder / 'playcount.db')
            with closing(sqlite3.connect(self.playcounts.playcountDB)) as db:
                for table in ('movie', 'episode', 'season', 'tvshow'):
                    db.execute(self.playcounts._createSql(table))
                db.commit()

    def add_favorite(self, label):
        entries = self.favorites._delta_entries()
        entries.append({'label': label, 'path': 'plugin://plugin.video.xvault/?test=' + label})
        self.favorites.write_favourites(self.favorites._build_xml(entries))

    def test_five_clients_handoff_and_deleted_favorite_does_not_return(self):
        self.add_favorite('Added on A')
        self.engine.synchronize()
        for name in 'BCDE':
            self.activate(name)
            self.engine.synchronize()
            self.assertIn('Added on A', self.favorites.read_favourites())
        self.activate('B')
        self.favorites.write_favourites('<favourites />')
        self.engine.synchronize()
        self.activate('A')
        self.engine.synchronize()
        self.assertNotIn('Added on A', self.favorites.read_favourites())

    def test_empty_php_deletion_patch_keeps_sync_and_conflict_resolution_working(self):
        self.add_favorite('Original')
        self.engine.synchronize()
        self.activate('B')
        self.engine.synchronize()
        self.activate('A')
        self.favorites.write_favourites(self.favorites.read_favourites().replace('name="Original"', 'name="Renamed on A"'))
        self.engine.synchronize()
        self.activate('B')
        self.favorites.write_favourites('<favourites />')
        self.assertTrue(self.engine.synchronize())
        conflict = self.engine.inspect()['conflicts'][0]
        self.assertEqual(json.loads(conflict['operation_json'])['patch'], [])
        self.assertTrue(self.engine.synchronize(), 'An open deletion conflict must not block later polls')
        self.engine.resolve(conflict, use_local=True)
        self.assertTrue(self.engine.synchronize())
        self.assertFalse(self.engine.inspect()['conflicts'])
        self.assertFalse(self.favorites._delta_entries())
        self.activate('A')
        self.assertTrue(self.engine.synchronize())
        self.assertFalse(self.favorites._delta_entries())

    def test_outbox_survives_lost_response_and_module_restart(self):
        self.add_favorite('Offline')
        real = self.client_module.Client()
        class LostResponse:
            def exchange(inner, payload):
                real.exchange(payload)
                raise TimeoutError('Simulated lost reply')
        with self.assertRaises(TimeoutError):
            self.engine.synchronize(client=LostResponse())
        self.assertEqual(self.engine.inspect()['pending'], 1)
        self.engine = importlib.reload(self.engine)
        self.engine.synchronize()
        self.assertEqual(self.engine.inspect()['pending'], 0)
        self.assertEqual(len(self.engine.inspect()['activity']), 1)

    def test_local_edit_during_exchange_is_preserved(self):
        real = self.client_module.Client()
        class EditDuringRequest:
            def exchange(inner, payload):
                reply = real.exchange(payload)
                self.add_favorite('During request')
                return reply
        self.engine.synchronize(client=EditDuringRequest())
        self.assertIn('During request', self.favorites.read_favourites())
        self.assertEqual(self.engine.inspect()['pending'], 1)
        self.engine.synchronize()
        self.activate('B')
        self.engine.synchronize()
        self.assertIn('During request', self.favorites.read_favourites())

    def progress(self, seconds, session='a', base=-1, sequence=1):
        return self.binge.record_playback(
            {'mediatype': 'movie', 'title': 'Sync Test', 'imdb_id': 'tt1234567', 'tmdb_id': '7654321'},
            'Sync Test (2026)', '2026', seconds, 7200, completed=False,
            session_id=session, base_revision=base, sequence=sequence)

    def test_resume_manual_watch_state_and_playing_video_protection(self):
        self.progress(1200)
        key = self.binge._bookmark_id('Sync Test (2026)', '2026')
        self.activate('B')
        self.playing = True
        self.engine.synchronize()
        self.assertFalse(self.bookmarks.get_query(key, 'bookmarks'))
        self.playing = False
        self.engine.synchronize()
        self.assertEqual(self.bookmarks.get_query(key, 'bookmarks')[1], '1200')
        item = self.binge.load_items()[0]
        item.update(completed=False, watch_state='unwatched')
        self.engine.record(item, kind='watch')
        self.engine.synchronize()
        self.activate('A')
        self.engine.synchronize()
        self.assertFalse(self.bookmarks.get_query(key, 'bookmarks'))
        self.assertFalse(self.binge.completed_items())
        self.assertFalse(self.binge.load_items()[0]['completed'])

    def test_resume_on_other_device_with_localized_title_uses_stable_identity(self):
        self.progress(1200)
        self.activate('B')
        self.assertTrue(self.engine.synchronize())
        self.settings['B']['bookmarks'] = 'true'
        original = self.binge.load_items()[0]
        meta = dict(original['extra'], title='Anderer lokaler Titel', mediatype='movie')
        self.binge.prepare_resume(meta, 'Anderer lokaler Titel (2026)', '2026')
        key = self.binge._bookmark_id('Anderer lokaler Titel (2026)', '2026')
        self.assertEqual(self.bookmarks.get_query(key, 'bookmarks')[1], '1200')
        # Identical names must not transfer a bookmark to a different TMDb item.
        other = dict(meta, tmdb_id='definitely-another-id')
        self.binge.prepare_resume(other, 'Wrong item (2026)', '2026')
        self.assertFalse(self.bookmarks.get_query(self.binge._bookmark_id('Wrong item (2026)', '2026'), 'bookmarks'))

    def test_episode_metadata_from_series_lists_keeps_episodes_separate(self):
        for episode in (1, 2):
            meta = dict(title='Series', tmdb_id='123', mediatype='tvshow', season=1, episode=episode, year=2026)
            self.binge.record_playback(meta, 'Series S01E%02d' % episode, '2026', 500, 3600, completed=False, push=False)
        items = self.binge.load_items()
        self.assertEqual(len(items), 2)
        self.assertEqual({self.binge._item_mediatype(item) for item in items}, {'episode'})

    def test_parallel_playback_conflict_keeps_both_positions(self):
        self.progress(1200, session='a')
        self.activate('B')
        self.progress(600, session='b')
        state = self.engine.inspect()
        self.assertEqual(len(state['conflicts']), 1)
        self.assertEqual(json.loads(state['conflicts'][0]['operation_json'])['patch']['value']['position_seconds'], 600)
        self.assertEqual(state['entities'][0]['data']['value']['position_seconds'], 1200)
        self.engine.resolve(state['conflicts'][0], use_local=True)
        self.engine.synchronize()
        self.assertFalse(self.engine.inspect()['conflicts'])
        self.activate('A')
        self.engine.synchronize()
        self.assertEqual(self.binge.load_items()[0]['position_seconds'], 600)

    def test_manual_and_playback_identity_and_php_migration_match(self):
        for mediatype, season, episode in [('movie', None, None), ('movie', 0, 0), ('tvshow', 8, 18), ('season', 8, None), ('tvshow', None, None)]:
            for ids in ({'tmdb_id': '1234'}, {'imdb_id': 'tt1234'}, {}):
                meta = dict(mediatype=mediatype, title='Identity Test', year=2026, season=season, episode=episode, **ids)
                manual = self.binge._manual_watch_item(meta, True)
                key = self.binge.item_key(meta, manual['name'], '2026')
                self.assertEqual(manual['item_key'], key)
                code = "require $argv[1]; echo sync2_item_key(json_decode(file_get_contents('php://stdin'), true));"
                result = subprocess.run(['php', '-r', code, str(ROOT / 'api/sync_v2.php')], input=json.dumps(manual), text=True, capture_output=True, check=True)
                self.assertEqual(result.stdout, key)

    def test_manual_watched_then_unwatched_uses_same_resume_identity(self):
        self.progress(1200)
        meta = {'mediatype': 'movie', 'title': 'Sync Test', 'year': 2026, 'imdb_id': 'tt1234567', 'tmdb_id': '7654321', 'sysname': 'Sync Test (2026)'}
        self.binge.update_watch_status(meta, watched=True)
        self.activate('B')
        self.engine.synchronize()
        self.assertTrue(self.binge.is_movie_watched(meta))
        self.binge.update_watch_status(meta, watched=False)
        self.activate('A')
        self.engine.synchronize()
        self.assertFalse(self.binge.is_movie_watched(meta))
        key = self.binge._bookmark_id('Sync Test (2026)', '2026')
        self.assertFalse(self.bookmarks.get_query(key, 'bookmarks'))

    def test_first_login_bootstraps_missing_local_history_and_favorites(self):
        self.activate('F')
        self.storage.save_login(self.api.email, self.api.login('F'))
        self.add_favorite('Imported local favorite')
        old_item = dict(item_key='old-identity', title='Local history', name='Local history (2026)', year='2026',
                        position_seconds=900, duration_seconds=7200, completed=False, provider='xvault',
                        extra={'mediatype': 'movie', 'tmdb_id': '5555'})
        self.storage.write_json(self.binge.FILENAME, {'items': [old_item]})
        self.engine.synchronize()
        self.assertEqual(self.engine.inspect()['pending'], 0)
        self.assertEqual(self.engine.inspect()['legacy_items'][0]['item_key'], 'old-identity')
        self.activate('B')
        self.engine.synchronize()
        self.assertIn('Imported local favorite', self.favorites.read_favourites())
        key = self.binge._bookmark_id('Local history (2026)', '2026')
        self.assertEqual(self.bookmarks.get_query(key, 'bookmarks')[1], '900')

    def test_independent_additions_do_not_echo_remote_sort_order_as_local_edits(self):
        self.add_favorite('A')
        self.engine.synchronize()
        self.activate('B')  # B still has its original empty baseline.
        self.add_favorite('B')
        self.engine.synchronize()
        before = self.engine.inspect()['revision']
        self.engine.synchronize()
        self.assertEqual(self.engine.inspect()['revision'], before)
        self.assertEqual(len(self.favorites._delta_entries()), 2)

    def test_large_unchanged_snapshot_skips_local_writes_and_batches_initial_apply(self):
        entities = []
        for index in range(1000):
            item = dict(item_key=str(index), title='Volume %s' % index, name='Volume %s (2026)' % index,
                        year='2026', completed=True, position_seconds=7200, duration_seconds=7200,
                        extra={'mediatype': 'movie', 'imdb_id': 'tt9%06d' % index})
            entities.append(dict(kind='progress', key=str(index), revision=index + 1, deleted=False, data={'value': item}))
        class Snapshot:
            def exchange(inner, payload):
                return dict(protocol=2, revision=1000, entities=entities, devices=[], activity=[], conflicts=[], results=[])
        connect = self.playcounts.db.connect
        with patch.object(self.playcounts.db, 'connect', wraps=connect) as connections:
            self.engine.synchronize(client=Snapshot())
            self.assertEqual(connections.call_count, 1, 'Initial history must use one playcount connection')
        self.assertEqual(len(self.playcounts.getWatchedItems()['movies']), 1000)
        with patch.object(self.binge, 'apply_local_states', wraps=self.binge.apply_local_states) as apply, \
             patch.object(self.storage, 'write_json', wraps=self.storage.write_json) as write:
            self.engine.synchronize(client=Snapshot())
            apply.assert_not_called()
            self.assertTrue(all(call.args[0] == 'sync_status.json' for call in write.call_args_list))
            # A single changed entity must not rewrite the other 999 entries.
            entities[25]['data']['value']['completed'] = False
            entities[25]['data']['value']['watch_state'] = 'unwatched'
            self.engine.synchronize(client=Snapshot())
            self.assertEqual(set(apply.call_args.args[0]), {'25'})
        self.assertEqual(self.playcounts.getPlaycount('movie', 'imdb_id', 'tt9000025'), 0)

    def test_login_write_failure_does_not_claim_a_new_login(self):
        with patch.object(self.storage, 'write_json', return_value=False):
            self.assertFalse(self.storage.save_login('unsaved@example.com', 'unsaved-key'))
        self.assertEqual(self.storage.email(), self.api.email)

    def test_last_sync_recovers_after_stale_settings_are_restored(self):
        for filename in ('sync_favorites_state.json', 'sync_binge_state.json'):
            self.storage.write_json(filename, {'updated_at': '2020-01-01 00:00:00'})
        self.storage.update_last_sync('2026-10-28 12:34:56')
        self.settings[self.name]['sync.last_sync_at'] = '2020-01-01 00:00:00'
        self.settings[self.name]['sync.status'] = 'Nicht angemeldet'
        self.settings[self.name]['sync.logged_in'] = 'false'
        self.storage.reconcile_auth_settings()
        self.assertTrue(self.storage.is_logged_in())
        self.assertEqual(self.settings[self.name]['sync.last_sync_at'], '2026-10-28 12:34:56')
        self.assertTrue(self.settings[self.name]['sync.status'].startswith('Angemeldet als'))

    def test_background_request_is_nonblocking_and_scoped_to_account(self):
        properties = {}
        window = types.SimpleNamespace(setProperty=properties.__setitem__, getProperty=lambda key: properties.get(key, ''))
        gui = types.SimpleNamespace(Window=lambda _: window)
        with patch.dict(sys.modules, {'xbmcgui': gui}), \
             patch.object(self.engine, 'synchronize', side_effect=AssertionError('UI must not run sync')):
            self.engine.on_wake()
            request = self.engine.background_request()
            self.assertTrue(request['active'])
            self.assertEqual(request['account'], self.api.email)
            self.assertTrue(request['id'])
            self.storage.save_login('different@example.com', 'test-only-key')
            self.assertEqual(self.engine.background_request(), {})

    def test_read_only_status_does_not_wait_for_sync_writer_or_rewrite_state(self):
        with closing(sqlite3.connect(self.engine._path())) as writer:
            writer.execute('BEGIN IMMEDIATE')
            with self.engine.database(readonly=True) as (reader, state):
                self.assertEqual(reader.execute('PRAGMA query_only').fetchone()[0], 1)
                self.assertIn('revision', state)
            self.assertIn('pending', self.engine.inspect())
            self.assertEqual(self.engine.playback_base('unknown'), -1)
            writer.rollback()

    def test_batch_failure_rolls_back_playcounts_and_retries_unapplied_state(self):
        item = dict(item_key='9' * 64, title='Rollback', name='Rollback (2026)', year='2026',
                    completed=True, extra={'mediatype': 'movie', 'imdb_id': 'tt99112233'})
        self.engine.record(item)
        with patch.object(self.bookmarks, 'update_queries', side_effect=OSError('Storage unavailable')):
            with self.assertRaises(OSError):
                self.engine.synchronize()
        self.assertIsNone(self.playcounts.getPlaycount('movie', 'imdb_id', 'tt99112233'))
        self.engine.synchronize()
        self.assertEqual(self.playcounts.getPlaycount('movie', 'imdb_id', 'tt99112233'), 1)

    def test_local_conflict_reapplies_unchanged_authoritative_bookmark(self):
        self.progress(1200)
        self.activate('B')
        self.engine.synchronize()
        key = self.binge._bookmark_id('Sync Test (2026)', '2026')
        self.bookmarks.save_query(key, '600', 'bookmarks')
        self.progress(600, session='stale-b', base=-1)
        self.assertTrue(self.engine.inspect()['conflicts'])
        self.assertEqual(self.bookmarks.get_query(key, 'bookmarks')[1], '1200')


if __name__ == '__main__':
    unittest.main()
