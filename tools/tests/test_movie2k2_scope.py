"""Movie2k2 must never query or resolve episodes, including specials and old caches."""
import ast
import os
from pathlib import Path
import random
import time
import types
import unittest
from unittest.mock import Mock

from resources.lib import provider_scope

ROOT = Path(__file__).resolve().parents[2]


def source_method(name):
    tree = ast.parse((ROOT / 'resources/lib/sources.py').read_text(encoding='utf8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'sources')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = dict(provider_scope=provider_scope, random=random, time=time, os=os,
                 control=types.SimpleNamespace(dataPath='unused'),
                 movie_identity=types.SimpleNamespace(without_rejected=lambda path, rows: rows),
                 log_utils=types.SimpleNamespace(log=Mock(), LOGINFO=1))
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'sources.py', 'exec'), scope)
    return scope[name]


class MovieOnlyTests(unittest.TestCase):
    def test_both_scrapers_return_before_any_network_for_all_series_shapes(self):
        for path in ('sites/movie2k2.py', 'scrapers/scrapers_source/de/movie2k2.py'):
            tree = ast.parse((ROOT / path).read_text(encoding='utf8'))
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'source')
            network = Mock(side_effect=AssertionError('Episode requested a film provider'))
            scope = dict(provider_scope=provider_scope, SITE_IDENTIFIER='movie2k2', SITE_DOMAIN='fixture.test',
                         getSetting=lambda key, default='': default, cRequestHandler=network)
            exec(compile(ast.Module(body=[cls], type_ignores=[]), path, 'exec'), scope)
            for kind, season, episode in [('tvshow', 0, 0), ('episode', 0, 1), ('episode', '0', '1'),
                                           (None, 1, 2), (None, '1', '2'), ('tv', 0, 0), ('season', 0, 0)]:
                with self.subTest(path=path, kind=kind, season=season, episode=episode):
                    scraper = scope['source']()
                    scraper.mediatype = kind
                    self.assertEqual(scraper.run(['Series'], 1963, season, episode), [])
                    self.assertEqual(scraper.search(['Series'], 1963, season, episode), [])
            network.assert_not_called()

    def test_collector_filters_provider_before_cache_lookup_and_removes_cached_series_sources(self):
        method = source_method('getSources')
        for kind, season, episode in [('episode', 0, 1), ('tvshow', 1, 1), ('movie', 0, 0)]:
            cache_key = Mock(return_value='key')
            rows = [dict(provider='movie2k2'), dict(provider='serienstream')]
            obj = types.SimpleNamespace(mediatype=kind, sourceDict=[('movie2k2', types.SimpleNamespace(priority=1)),
                ('serienstream', types.SimpleNamespace(priority=1))], _getHostDict=lambda: [], _sourceCacheKey=cache_key,
                _seriesCacheKey=lambda *a: 'series', _readSourceCache=lambda *a, **kw: (rows, False),
                _filterTemporarilyBlockedHosters=lambda rows: rows)
            found = method(obj, 'Title', 2026, 'tt1', season, episode, '', '')
            expected = ['movie2k2', 'serienstream'] if kind == 'movie' else ['serienstream']
            self.assertEqual([r['provider'] for r in found], expected)
            self.assertEqual(sorted(p[0] for p in cache_key.call_args.args[-1]), sorted(expected))

    def test_background_collection_and_old_episode_context_cannot_bypass_restriction(self):
        provider = Mock()
        obj = types.SimpleNamespace(mediatype='episode')
        result = source_method('_getSource')(obj, ['Series'], 2026, 0, 1, '', 'movie2k2', provider)
        self.assertEqual(result['status'], 'unsupported')
        provider.run.assert_not_called()
        obj = types.SimpleNamespace(_playbackMetaForSourceItem=Mock(return_value=dict(mediatype='tvshow', season=1, episode=1)))
        self.assertIsNone(source_method('sourcesResolve')(obj, dict(provider='movie2k2')))
        obj._playbackMetaForSourceItem.assert_called_once()

    def test_films_with_numeric_or_string_zero_remain_allowed_and_other_providers_unchanged(self):
        for zero in (None, '', 0, '0'):
            self.assertTrue(provider_scope.allowed('movie2k2', 'movie', zero, zero))
        self.assertTrue(provider_scope.allowed('serienstream', 'episode', 1, 2))


if __name__ == '__main__':
    unittest.main()
