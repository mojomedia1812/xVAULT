"""Provider identity, circuit recovery and incomplete-cache regressions."""
import ast
import json
import os
from pathlib import Path
import re
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]


def definitions(path, cls=None, names=None, **scope):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef if cls else ast.FunctionDef)
             and (n.name == cls if cls else n.name in names)]
    if cls and names:
        nodes[0].body = [n for n in nodes[0].body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, 'exec'), scope)
    return scope


class IdentityTests(unittest.TestCase):
    def test_incomplete_episode_fallback_cannot_remap_to_partial_match(self):
        from tools.tests.test_serienstream_episodes import SOURCE
        p = SOURCE()
        p._available_seasons = lambda *args: [2]
        p._request_page = lambda *args: 'fixture'
        p._parse_episode_links = lambda *args: ['/serie/fixture/staffel-2/episode-%d' % n for n in range(1, 27)]
        p._has_stream_links = lambda *args: True
        p._extract_episode_title = lambda *args: 'Wanted'
        p._episode_titles_match = lambda *args: True
        self.assertIsNone(p._find_matching_episode_page('/serie/fixture', 2, 1, 'Wanted'))
        self.assertTrue(p.search_incomplete)
        self.assertIsNone(p._fallback_deadline)

    def test_movie2k_rejects_original_scrubs_and_conflicting_embedded_ids(self):
        source = definitions('sites/movie2k.py', cls='source', names={'_series_identity_matches'}, re=re)['source']
        match = source._series_identity_matches
        self.assertFalse(match({'year': 2026}, {'imdb': 'tt0285403'}, 'tt40197357', 2026))
        self.assertTrue(match({'year': 2002}, {'imdb': 'tt0285403'}, 'tt0285403', 2001))
        self.assertFalse(match({'year': 2001}, {}, 'tt40197357', 2026))
        self.assertFalse(match({}, {}, 'tt40197357', 2026))
        self.assertTrue(match({'year': 2026}, {}, 'tt40197357', 2026))
        self.assertFalse(match({}, {'imdb': 'tt40197357', 'streams': [{'stream': 'https://host/embed/tt0285403/2-1'}]}, 'tt40197357', 2026))

    def test_legacy_oha_alias_recovers_but_explicit_disable_is_honored(self):
        values = {'provider.huhu': 'true', 'provider.huhu.check': 'false', 'provider.huhu.domain': 'www.oha.to'}
        check = definitions('scrapers/__init__.py', names={'enabledCheck'},
                            control=types.SimpleNamespace(getSetting=lambda key: values.get(key, '')),
                            _HIDDEN_PROVIDERS=set(), _CHECK_OPTIONAL_PROVIDERS=set())['enabledCheck']
        self.assertTrue(check('huhu'))
        values['provider.huhu'] = 'false'
        self.assertFalse(check('huhu'))
        values['provider.huhu'] = 'true'
        values['provider.huhu.domain'] = 'oha.to'
        self.assertFalse(check('huhu'))


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        props = {}
        control = types.SimpleNamespace(dataPath=self.folder.name,
            window=types.SimpleNamespace(getProperty=lambda key: props.get(key, ''), setProperty=props.__setitem__))
        names = {'_sourceCacheFile', '_readSourceCache', '_writeSourceCache', '_hasVolatileSourceUrls',
                 '_readSourceCachePayload', '_writeSourceCachePayload', '_normalizeSourceCachePayload',
                 '_filterTemporarilyBlockedProviders', '_markProviderTemporarilyBlocked'}
        cls = definitions('resources/lib/sources.py', cls='sources', names=names, control=control,
            log_utils=Mock(), os=os, time=time, json=json, urlparse=urlparse,
            SOURCE_CACHE_TTL=1800, SOURCE_CACHE_STALE_TTL=21600, SOURCE_CACHE_LIMIT=60, SERIES_CACHE_LIMIT=200)['sources']
        self.p = cls()
        self.p.sourceCacheProperty = 'qa'
        self.row = {'provider': 'movie2k', 'url': 'https://host/valid'}

    def test_old_serienstream_timeout_does_not_block_other_episode(self):
        self.p._writeSourceCachePayload({'provider_health': {'serienstream': {'reason': 'timeout', 'blocked_until': int(time.time()) + 600}}})
        self.assertEqual(self.p._filterTemporarilyBlockedProviders([('serienstream', None)]), [('serienstream', None)])
        self.p._writeSourceCachePayload({})
        self.p._markProviderTemporarilyBlocked('serienstream', 'timeout', 600)
        self.assertFalse(self.p._readSourceCachePayload()['provider_health'])

    def test_request_timeout_cache_is_short_but_warm_reusable(self):
        self.p._missing_providers = {'serienstream'}
        self.p._writeSourceCache('key', [self.row])
        self.assertEqual(self.p._readSourceCache('key'), ([self.row], False))
        future = time.time() + 61
        with patch.object(time, 'time', return_value=future):
            self.assertIsNone(self.p._readSourceCache('key', allow_stale=True)[0])

    def test_recovered_provider_invalidates_partial_cache_immediately(self):
        self.p._markProviderTemporarilyBlocked('moflix', 'network', 300)
        self.p._filterTemporarilyBlockedProviders([('moflix', None)])
        self.p._writeSourceCache('key', [self.row])
        self.assertEqual(self.p._readSourceCache('key'), ([self.row], False))
        payload = self.p._readSourceCachePayload()
        payload['provider_health'].clear()
        self.p._writeSourceCachePayload(payload)
        self.assertIsNone(self.p._readSourceCache('key')[0])

    def test_complete_cache_retains_normal_lifetime(self):
        self.p._writeSourceCache('key', [self.row])
        future = time.time() + 120
        with patch.object(time, 'time', return_value=future):
            self.assertEqual(self.p._readSourceCache('key'), ([self.row], False))
