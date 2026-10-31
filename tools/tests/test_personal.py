"""Start page edge cases, real SQLite persistence and scoped radio timers."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, path, modules):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class PersonalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.props = {}
        self.control = types.ModuleType('resources.lib.control')
        self.control.dataPath = self.temp.name
        self.control.infoDialog = Mock()
        self.control.execute = Mock()
        self.win = types.SimpleNamespace(setProperty=self.props.__setitem__, getProperty=lambda k: self.props.get(k, ''), clearProperty=lambda k: self.props.pop(k, None))
        self.modules = {'resources.lib.control': self.control,
                        'resources.lib.bookmarkDB': types.ModuleType('resources.lib.bookmarkDB'),
                        'xbmcgui': types.SimpleNamespace(Window=lambda _: self.win)}
        self.module = load('personal_tested', 'resources/lib/personal.py', self.modules)

    def test_subscription_toggle_and_removed_cache_not_resurrected(self):
        with patch.dict(sys.modules, self.modules):
            self.module.toggle({'tmdb_id': '123', 'title': 'Serie', 'mediatype': 'tvshow'})
            self.assertEqual(len(self.module.subscriptions()), 1)
            self.module.save_cache('123', {'episode': None})
            self.assertIn('123', self.module.cached())
            self.module.toggle({'tmdb_id': '123', 'title': 'Serie'})
            self.module.save_cache('123', {'episode': 'late worker'})
            self.assertEqual(self.module.cached(), {})

    def test_finale_selects_next_season_but_never_future_or_special(self):
        episodes = [{'season_number': s, 'episode_number': e, 'air_date': date}
                    for s, e, date in [(0, 1, '2020-01-01'), (1, 9, '2020-01-01'), (2, 1, '2021-01-01'), (2, 2, '2099-01-01')]]
        self.assertEqual(self.module.next_episode(episodes, {'season': 1, 'episode': 9, 'completed': True})['season_number'], 2)
        self.assertEqual(self.module.next_episode(episodes, {'season': 1, 'episode': 9, 'completed': False})['season_number'], 1)
        self.assertEqual(self.module.next_episode(episodes, None)['season_number'], 2)
        self.assertIsNone(self.module.next_episode(episodes, {'season': 2, 'episode': 1, 'completed': True}))

    def test_imported_progress_can_be_played_without_embedded_metadata(self):
        meta = self.module.item_meta({'title': 'Serie', 'year': '1963', 'season': 1, 'episode': 2,
                                      'extra': {'tmdb_id': '123', 'imdb_id': 'tt123', 'mediatype': 'episode'}})
        self.assertEqual((meta['tmdb_id'], meta['season'], meta['episode']), ('123', 1, 2))


class SleepTests(unittest.TestCase):
    def setUp(self):
        self.props, self.audio, self.target = {}, True, 'https://radio.example/live'
        self.stop = Mock()
        owner = self
        player = types.SimpleNamespace(isPlayingAudio=lambda: owner.audio, getPlayingFile=lambda: owner.target, stop=self.stop)
        win = types.SimpleNamespace(setProperty=self.props.__setitem__, getProperty=lambda k: self.props.get(k, ''), clearProperty=lambda k: self.props.pop(k, None))
        self.module = load('radio_tools_tested', 'resources/lib/radio_tools.py',
                           {'xbmc': types.SimpleNamespace(Player=lambda: player), 'xbmcgui': types.SimpleNamespace(Window=lambda _: win)})

    def arm(self):
        self.props[self.module.PROPERTY] = json.dumps(dict(token='test', target='https://radio.example/live', until=9999999999))

    def test_stale_alarm_cannot_cancel_a_new_timer(self):
        self.arm()
        self.module.expire('old')
        self.stop.assert_not_called()
        self.assertIn(self.module.PROPERTY, self.props)

    def test_sleep_alarm_never_stops_video_or_other_audio(self):
        for audio, target in [(False, 'https://radio.example/live'), (True, 'https://other.example/live')]:
            self.audio, self.target = audio, target
            self.arm()
            self.module.expire('test')
            self.stop.assert_not_called()

    def test_sleep_alarm_stops_its_radio(self):
        self.arm()
        self.module.expire('test')
        self.stop.assert_called_once()
        self.assertNotIn(self.module.PROPERTY, self.props)


if __name__ == '__main__':
    unittest.main()
