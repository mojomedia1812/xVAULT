"""Collection film clicks must not start Kodi's playback resolver prematurely."""
import ast
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
from urllib.parse import quote_plus, unquote_plus

ROOT = Path(__file__).resolve().parents[2]


def load_class(path, name, scope, methods=None):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    if methods is not None:
        cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in methods]
    exec(compile(ast.Module(body=[cls], type_ignores=[]), path, 'exec'), scope)
    return scope[name]


class CollectionSourceSelectionTests(unittest.TestCase):
    def collection(self):
        self.control = Mock()
        self.control.getSetting.return_value = 'false'
        self.control.addonPoster.return_value = 'DefaultMovies.png'
        self.control.quote_plus = quote_plus
        self.control.unquote_plus = unquote_plus
        cls = load_class('resources/lib/indexers/collections.py', 'collections',
                         dict(control=self.control, json=json, sys=sys, ListItemInfoTag=None))
        return cls.__new__(cls)

    def test_collection_movie_is_an_action_not_a_playback_resolver(self):
        obj = self.collection()
        obj._end = Mock()
        obj._has_next_page = Mock(return_value=False)
        obj._set_info = Mock()
        obj._movie_plot = Mock(return_value='Plot')
        with patch.object(sys, 'argv', ['plugin://plugin.video.xvault/', '7', '']):
            obj._movies_directory([{'title': 'Alien', 'slug': 'alien', 'year': 1979}],
                                  'alien-collection', 1, '', 'Alien Collection')
        args = self.control.addItem.call_args.args
        self.assertEqual(args[0], 7)
        self.assertIn('action=collectionPlay&slug=alien&', args[1])
        self.assertFalse(args[3])  # Same action-style item as regular movie results.
        self.assertFalse(any(call.args == ('IsPlayable', 'true')
                             for call in self.control.item.return_value.setProperty.call_args_list))
        obj._end.assert_called_once_with('movies')

    def test_collection_hands_metadata_to_current_global_action(self):
        obj = self.collection()
        obj._movie_meta = Mock(return_value={'title': 'Alien', 'year': 1979})
        obj._tmdb_meta = Mock(return_value={'title': 'Alien', 'year': 1979, 'mediatype': 'movie'})
        sources = Mock()
        with patch.dict(sys.modules, {'resources.lib.sources': sources}):
            obj.play({'slug': 'alien', 'title': 'Alien'})
        params = sources.sources.return_value.play.call_args.args[0]
        self.assertNotIn('select', params)
        self.assertEqual(json.loads(params['sysmeta'])['title'], 'Alien')

    def test_directory_action_never_resolves_or_starts_a_stream(self):
        for in_plugin in (True, False):
            with self.subTest(in_plugin=in_plugin):
                obj, control, player = self.source_player('1', in_plugin)
                obj.play({'sysmeta': json.dumps({'title': 'Alien', 'mediatype': 'movie'})})
                obj.getSources.assert_called_once()
                obj.sourcesDialog.assert_not_called()
                obj.sourcesAutoplay.assert_not_called()
                player.assert_not_called()
                control.resolveUrl.assert_not_called()
                if in_plugin:
                    self.assertIn('Container.Update(', control.execute.call_args.args[0])
                else:
                    obj.addItem.assert_called_once_with('Alien')
                obj._shutdownExecutor.assert_called_once()

    def test_dialog_and_autoplay_remain_available(self):
        for mode in ('0', '2'):
            with self.subTest(mode=mode):
                obj, control, player = self.source_player(mode, True)
                obj.play({'sysmeta': json.dumps({'title': 'Alien', 'mediatype': 'movie'})})
                obj.addItem.assert_not_called()
                if mode == '0':
                    obj.sourcesDialog.assert_called_once()
                    player.return_value.run.assert_called_once()
                else:
                    obj.sourcesAutoplay.assert_called_once()
                    player.assert_not_called()

    def source_player(self, mode, in_plugin):
        control = Mock()
        control.infoLabel.side_effect = lambda label: ('plugin.video.xvault' if in_plugin else '') if label == 'Container.PluginName' else ''
        player = Mock()
        cls = load_class('resources/lib/sources.py', 'sources', dict(
            control=control, json=json, sys=types.SimpleNamespace(argv=['plugin://plugin.video.xvault/', '7', '']),
            quote_plus=quote_plus, py2_encode=lambda v: v,
            playback_settings=types.SimpleNamespace(get_mode=lambda: mode, normalize_mode=lambda v, default=None: v),
            log_utils=Mock()), methods=('get', 'play', '_recoveryResolver'))
        obj = cls()
        obj._enforceStreamLanguageSelectionMode = lambda value: value
        obj.getSources = Mock(return_value=[{'identity_status': 'verified'}])
        obj._telemetryEvent = Mock()
        obj._sourceTelemetryPayload = Mock()
        obj.itemsProperty, obj.metaProperty = 'qa.items', 'qa.meta'
        obj.addItem = Mock()
        obj.sourcesDialog = Mock(return_value='https://example.invalid/selected')
        obj.sourcesAutoplay = Mock(return_value=True)
        obj._mergeSelectedStreamMeta = lambda meta, source: meta
        obj._shutdownExecutor = Mock()
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {'resources.lib.player': types.SimpleNamespace(player=player)}).start()
        return obj, control, player


if __name__ == '__main__':
    unittest.main()
