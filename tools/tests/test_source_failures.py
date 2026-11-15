"""A broken upload must not quarantine other videos at the same host."""
import ast
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import time
import types
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import urlparse

from resources.lib import source_failures

ROOT = Path(__file__).resolve().parents[2]


class SourceFailureTests(unittest.TestCase):
    def make_resolver(self, payload=None):
        names = ('_hosterHealthKey', '_filterTemporarilyBlockedHosters', '_markHosterTemporarilyBlocked',
                 '_normalizeSourceCachePayload', 'sourcesResolve', '_resolveWithResolveUrl',
                 '_isUsableResolvedUrl', '_looksLikeDirectMediaUrl', '_fallbackSourceItems', '_sourceItemKey')
        tree = ast.parse((ROOT / 'resources/lib/sources.py').read_text(encoding='utf8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'sources')
        cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
        hmf = Mock()
        hmf.valid_url.return_value = True
        self.hmf = hmf
        self.control = Mock()
        scope = dict(hashlib=hashlib, time=time, json=json, re=re, urlparse=urlparse,
                     control=self.control, log_utils=Mock(),
                     utils=types.SimpleNamespace(test_stream=lambda url: True),
                     hoster_compat=types.SimpleNamespace(resolve=Mock(return_value=None)),
                     _resolveurl=lambda: types.SimpleNamespace(HostedMediaFile=lambda **kw: hmf),
                     HOSTER_ERROR_TTL=300, SOURCE_CACHE_STALE_TTL=21600, SERIES_CACHE_LIMIT=200)
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'sources.py', 'exec'), scope)
        self.scope = scope
        obj = scope['sources']()
        self.payload = payload if payload is not None else {}
        obj._readSourceCachePayload = lambda: copy.deepcopy(self.payload)
        def write(data):
            self.payload.clear()
            self.payload.update(copy.deepcopy(data))
        obj._writeSourceCachePayload = write
        obj.sourceDict = [('fixture', types.SimpleNamespace(resolve=lambda url: url))]
        obj._normalizeResolverUrl = lambda url, item: url
        obj._isKnownHosterUrl = lambda url: True
        obj._resolveVoeDirect = lambda *a: None
        obj._resolveHostedMediaFileAutoPick = Mock(side_effect=Exception('Video deleted or removed.'))
        return obj

    def item(self, media='dead', query=''):
        return dict(provider='fixture', source='SameHost', url='https://host.invalid/e/' + media + query, direct=False)

    def test_deleted_link_is_resolved_once_then_skipped_including_new_instance(self):
        obj = self.make_resolver()
        self.assertIsNone(obj.sourcesResolve(self.item(), check_stream=True))
        obj._resolveHostedMediaFileAutoPick.assert_called_once()
        state = next(iter(self.payload['hoster_health'].values()))
        self.assertEqual(state['reason'], 'deleted')
        self.assertGreater(state['blocked_until'], time.time() + 86000)
        # Caller-level generic error handling cannot overwrite the useful cause/TTL.
        obj._markHosterTemporarilyBlocked(self.item(), 'resolve_failed', 300)
        self.assertEqual(next(iter(self.payload['hoster_health'].values())), state)
        self.assertIsNone(obj.sourcesResolve(self.item(), check_stream=True))
        obj._resolveHostedMediaFileAutoPick.assert_called_once()
        saved = copy.deepcopy(self.payload)
        other = self.make_resolver(saved)
        self.assertIsNone(other.sourcesResolve(self.item(), check_stream=True))
        other._resolveHostedMediaFileAutoPick.assert_not_called()

    def test_other_upload_same_hoster_remains_playable(self):
        obj = self.make_resolver()
        obj.sourcesResolve(self.item())
        obj._resolveHostedMediaFileAutoPick.side_effect = None
        obj._resolveHostedMediaFileAutoPick.return_value = 'https://cdn.invalid/video.mp4'
        self.assertEqual(obj.sourcesResolve(self.item('good'), check_stream=True), 'https://cdn.invalid/video.mp4')
        self.assertEqual(obj._filterTemporarilyBlockedHosters([self.item(), self.item('good')]), [self.item('good')])

    def test_http_404_tls_and_temporary_failures_do_not_repeat_popup_resolution(self):
        for error, reason, ttl in [(HTTPError('https://private.invalid/token', 404, 'Not Found', {}, None), 'not_found', 1800),
                                   (Exception('CERTIFICATE_VERIFY_FAILED'), 'tls', 300),
                                   (Exception('HTTP Error 522: timeout'), 'server', 300),
                                   (TimeoutError('timed out'), 'network', 300)]:
            with self.subTest(reason=reason):
                if isinstance(error, HTTPError):
                    self.addCleanup(error.close)
                obj = self.make_resolver()
                obj._resolveHostedMediaFileAutoPick.side_effect = error
                self.assertIsNone(obj.sourcesResolve(self.item()))
                obj._resolveHostedMediaFileAutoPick.assert_called_once()
                state = next(iter(self.payload['hoster_health'].values()))
                self.assertEqual(state['reason'], reason)
                self.assertAlmostEqual(state['blocked_until'] - time.time(), ttl, delta=2)

    def test_expiry_query_identity_and_private_keys(self):
        obj = self.make_resolver()
        a, b = self.item(query='?token=secret-a'), self.item(query='?token=secret-b')
        obj._markHosterTemporarilyBlocked(a, 'network', 300)
        self.assertEqual(obj._filterTemporarilyBlockedHosters([a, b]), [b])
        self.assertNotIn('secret', json.dumps(self.payload))
        with patch.object(time, 'time', return_value=time.time() + 301):
            self.assertEqual(obj._filterTemporarilyBlockedHosters([a, b]), [a, b])

    def test_legacy_hoster_wide_blocks_are_discarded_and_storage_bounded(self):
        obj = self.make_resolver()
        now = int(time.time())
        health = {'fixture|samehost': dict(blocked_until=now + 999, timestamp=now)}
        health.update({'link:' + str(i): dict(blocked_until=now + 999, timestamp=i) for i in range(510)})
        result = obj._normalizeSourceCachePayload({'hoster_health': health})
        self.assertEqual(len(result['hoster_health']), 500)
        self.assertNotIn('fixture|samehost', result['hoster_health'])

    def test_fallback_skips_dead_upload_but_keeps_other_upload_same_host(self):
        obj = self.make_resolver()
        dead, good, selected = self.item(), self.item('good'), self.item('selected')
        obj.itemsProperty = 'qa.items'
        obj._markHosterTemporarilyBlocked(dead, 'deleted', 86400)
        self.control.window.getProperty.return_value = json.dumps([selected, dead, good])
        self.assertEqual(obj._fallbackSourceItems(selected), [good])

    def test_generic_parser_error_does_not_become_a_deleted_video(self):
        self.assertIsNone(source_failures.classify(Exception('Video Link Not Found')))
        self.assertIsNone(source_failures.classify(Exception('Unexpected page markup')))

    def test_parallel_prefetch_failures_do_not_overwrite_other_uploads(self):
        obj = self.make_resolver()
        read = obj._readSourceCachePayload
        def delayed_read():
            payload = read()
            time.sleep(.005)
            return payload
        obj._readSourceCachePayload = delayed_read
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: obj._markHosterTemporarilyBlocked(self.item(str(i)), 'deleted', 86400), range(8)))
        self.assertEqual(len(self.payload['hoster_health']), 8)


if __name__ == '__main__':
    unittest.main()
