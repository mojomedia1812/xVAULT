"""Playback management against real temporary SQLite/PHP five-device sync."""
import importlib
import json
import unittest
from unittest.mock import Mock, patch

from tools.tests import test_sync_client as client_tests


class PlaybackStateTests(unittest.TestCase):
    setUp = client_tests.DeviceClientTests.setUp
    activate = client_tests.DeviceClientTests.activate
    progress = client_tests.DeviceClientTests.progress
    add_favorite = client_tests.DeviceClientTests.add_favorite

    def state(self):
        self.settings[self.name]['playback.library'] = 'false'
        module = importlib.import_module('resources.lib.playback_state')
        self.engine.request_background = Mock()
        return module

    def meta(self):
        return {'title': 'Sync Test', 'year': '2026', 'mediatype': 'movie', 'imdb_id': 'tt1234567', 'tmdb_id': '7654321'}

    def test_hiding_keeps_position_is_device_local_and_restart_restores(self):
        state = self.state()
        self.progress(1200)
        state.hide(self.meta())
        self.assertTrue(state.hidden(self.meta()))
        self.assertEqual(self.binge.load_items()[0]['position_seconds'], 1200)
        self.activate('B')
        self.assertFalse(state.hidden(self.meta()))
        self.activate('A')
        state.started(self.meta())
        self.assertFalse(state.hidden(self.meta()))
        foreign = dict(self.meta(), tmdb_id='999')
        state.hide(self.meta())
        self.assertFalse(state.hidden(foreign))

    def test_offline_reset_reaches_five_devices_and_stale_checkpoint_loses(self):
        state = self.state()
        self.progress(1200, session='old-a')
        key = self.binge.load_items()[0]['item_key']
        old_base = self.engine.playback_base(key)
        for name in 'BCDE':
            self.activate(name)
            self.engine.synchronize()
        self.activate('B')
        reset = state.reset_progress(self.meta())
        self.assertTrue(reset['progress_reset'])
        self.assertEqual(self.binge.load_items()[0]['position_seconds'], 0)
        self.assertGreater(self.engine.inspect()['pending'], 0, 'Offline reset must be durable')
        self.assertTrue(self.engine.synchronize())
        self.activate('A')
        self.progress(1300, session='old-a', base=old_base, sequence=99)
        self.assertEqual(self.binge.load_items()[0]['position_seconds'], 0)
        self.assertTrue(self.engine.inspect()['conflicts'])
        bookmark = self.binge._bookmark_id('Sync Test (2026)', '2026')
        for name in 'ABCDE':
            self.activate(name)
            self.assertTrue(self.engine.synchronize())
            self.assertEqual(self.binge.load_items()[0]['position_seconds'], 0)
            self.assertFalse(self.bookmarks.get_query(bookmark, 'bookmarks'))
        # A deliberately started new session may legitimately resume tracking.
        base = self.engine.playback_base(key)
        self.progress(400, session='new-e', base=base)
        self.assertEqual(self.binge.load_items()[0]['position_seconds'], 400)

    def test_watch_unwatch_and_reset_keep_favorites_and_authentication(self):
        state = self.state()
        self.add_favorite('Do not delete')
        token = self.storage.api_key()
        state.set_watched(self.meta(), True)
        self.assertTrue(self.binge.is_movie_watched(self.meta()))
        state.reset_progress(self.meta())
        self.assertTrue(self.binge.is_movie_watched(self.meta()))
        state.set_watched(self.meta(), False)
        self.assertFalse(self.binge.is_movie_watched(self.meta()))
        self.assertEqual(self.playcounts.getPlaycount('movie', 'imdb_id', 'tt1234567'), 0)
        self.assertIn('Do not delete', self.favorites.read_favourites())
        self.assertEqual(self.storage.api_key(), token)

    def test_tracking_and_resume_work_after_manual_unwatch(self):
        state = self.state()
        self.settings[self.name]['bookmarks'] = 'true'
        state.set_watched(self.meta(), False)
        self.engine.synchronize()
        key = self.binge.load_items()[0]['item_key']
        self.progress(400, session='new', base=self.engine.playback_base(key))
        self.progress(500, session='new', base=self.engine.playback_base(key), sequence=2)
        self.assertEqual(self.binge.load_items()[0]['position_seconds'], 500)
        self.binge.prepare_resume(self.meta(), 'Sync Test (2026)', '2026')
        bookmark = self.binge._bookmark_id('Sync Test (2026)', '2026')
        self.assertEqual(self.bookmarks.get_query(bookmark, 'bookmarks')[1], '500')

    def test_actions_are_encoded_and_legacy_watch_actions_are_replaced(self):
        state = self.state()
        actions = state.merge_context([('old', 'RunPlugin(x?action=UpdatePlayCount)'), ('Info', 'Action(Info)')], self.meta())
        self.assertEqual(len(actions), 5)
        self.assertFalse(any('UpdatePlayCount' in command for _, command in actions))
        self.assertTrue(all('sysmeta=' in command for _, command in actions[1:]))


class LibraryIdentityTests(unittest.TestCase):
    def setUp(self):
        # Isolated import, independent of whichever Kodi stubs other tests use.
        import importlib.util
        import sys
        import types
        from pathlib import Path
        spec = importlib.util.spec_from_file_location('library_identity_test', Path(__file__).resolve().parents[2] / 'resources/lib/library_state.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'resources.lib.control': types.SimpleNamespace()}):
            spec.loader.exec_module(self.module)

    def test_identity_requires_ids_and_rejects_conflicting_ids(self):
        same = self.module.same_ids
        self.assertFalse(same({'title': 'Alien'}, {'title': 'Alien'}))
        self.assertTrue(same({'imdb_id': 'tt0078748'}, {'uniqueid': {'imdb': 'tt0078748'}}))
        self.assertFalse(same({'imdb_id': 'tt0078748', 'tmdb_id': '1'}, {'uniqueid': {'imdb': 'tt0078748', 'tmdb': '2'}}))

    def test_foreign_library_types_are_ignored(self):
        self.module.notify('VideoLibrary.OnUpdate', json.dumps({'item': {'type': 'musicvideo', 'id': 1}}))
        self.assertFalse(self.module._pending)
        self.module.notify('VideoLibrary.OnUpdate', json.dumps({'item': {'type': 'episode', 'id': 1}}))
        self.assertEqual(list(self.module._pending), [('episode', 1)])

    def test_unwatch_writes_only_matched_id_and_clears_lastplayed(self):
        import sys
        import types
        properties = {}
        self.module.control = types.SimpleNamespace(getSetting=lambda *args: 'true')
        self.module.targets = Mock(return_value=[('episode', 7)])
        self.module.details = Mock(return_value={'playcount': 1})
        self.module.rpc = Mock(return_value={})
        window = types.SimpleNamespace(setProperty=properties.__setitem__)
        with patch.dict(sys.modules, {'xbmcgui': types.SimpleNamespace(Window=lambda _: window)}):
            self.module.write({'tmdb_id': '123', 'season': 2, 'episode': 6}, completed=False)
        self.module.rpc.assert_called_once_with('VideoLibrary.SetEpisodeDetails', {
            'episodeid': 7, 'resume': {'position': 0.0, 'total': 0.0}, 'playcount': 0, 'lastplayed': ''})
        self.assertIn('xvault.library.episode.7', properties)


if __name__ == '__main__':
    unittest.main()
