"""Actual HTTP probes and central resolver regressions without Kodi imports."""
import ast
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import types
import unittest
from urllib.parse import urlparse, urlencode

from resources.lib import stream_probe

ROOT = Path(__file__).resolve().parents[2]
MP4 = b'\x00\x00\x00\x18ftypisom' + bytes(4096)
HLS = b'#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\nsegment.ts\n'


class StreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_HEAD(self):
                cls.calls.append(('HEAD', self.path, dict(self.headers)))
                self.send_error(403)

            def do_GET(self):
                cls.calls.append(('GET', self.path, dict(self.headers)))
                if self.path == '/no-range' and self.headers.get('Range'):
                    self.send_error(416)
                    return
                if self.path == '/missing':
                    self.send_error(404)
                    return
                if self.path in ('/opaque', '/no-range'):
                    body, content_type = MP4, 'application/octet-stream'
                elif self.path in ('/master.m3u8', '/master.txt'):
                    body, content_type = HLS, 'text/plain'
                else:
                    body, content_type = b'<!doctype html><script>window.location="https://ads.invalid";</script>', 'text/html'
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.base = 'http://127.0.0.1:%s' % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def setUp(self):
        self.calls.clear()

    def test_opaque_media_works_when_head_is_forbidden(self):
        self.assertTrue(stream_probe.is_media_stream(self.base + '/opaque'))
        self.assertEqual([c[0] for c in self.calls], ['GET'])

    def test_hls_is_verified_by_body_including_txt_urls(self):
        for path in ('/master.m3u8', '/master.txt'):
            self.assertTrue(stream_probe.is_media_stream(self.base + path))
        self.assertFalse(stream_probe.is_media_stream(self.base + '/fake.m3u8'))

    def test_range_rejection_retries_without_range_and_preserves_headers(self):
        url = self.base + '/no-range|' + urlencode({'Referer': 'https://host.invalid/embed', 'User-Agent': 'Kodi fixture', 'verifypeer': 'false'})
        self.assertTrue(stream_probe.is_media_stream(url))
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn('Range', self.calls[-1][2])
        self.assertEqual(self.calls[-1][2]['Referer'], 'https://host.invalid/embed')
        self.assertNotIn('Verifypeer', self.calls[-1][2])

    def test_deleted_media_and_http_200_html_are_not_playable(self):
        for path in ('/missing', '/error.mp4', '/browser-check'):
            self.assertFalse(stream_probe.is_media_stream(self.base + path))

    def resolver(self, provider_url, known_hoster=False):
        tree = ast.parse((ROOT / 'resources/lib/sources.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'sources')
        names = ('sourcesResolve', '_isUsableResolvedUrl', '_looksLikeDirectMediaUrl')
        cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
        compat = types.SimpleNamespace(is_supported_host=lambda host: False, resolve=lambda url: None)
        scope = dict(urlparse=urlparse, re=re,
                     utils=types.SimpleNamespace(test_stream=stream_probe.is_media_stream),
                     hoster_compat=compat, log_utils=types.SimpleNamespace(log=lambda *a: None, LOGWARNING=1, LOGERROR=2))
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'sources.py', 'exec'), scope)
        resolver = scope['sources']()
        resolver.sourceDict = [('fixture', types.SimpleNamespace(resolve=lambda url: provider_url))]
        resolver._normalizeResolverUrl = lambda url, item: url
        resolver._isKnownHosterUrl = lambda url: known_hoster
        resolver._resolveVoeDirect = lambda *a: None
        resolver._resolveWithResolveUrl = lambda *a, **k: None
        return resolver

    def item(self, direct=False):
        return dict(url='https://host.invalid/e/fixture', source='Fixture', provider='fixture', direct=direct)

    def test_provider_resolved_stream_is_not_resolved_twice(self):
        resolver = self.resolver(self.base + '/opaque')
        def forbidden(*a, **k):
            raise AssertionError('Already resolved media was resolved twice')
        resolver._resolveWithResolveUrl = forbidden
        self.assertEqual(resolver.sourcesResolve(self.item(), check_stream=True), self.base + '/opaque')
        self.assertEqual(len(self.calls), 1, 'The verified provider result must not be probed twice')

    def test_provider_redirect_to_hoster_is_not_consumed_by_probe(self):
        resolver = self.resolver(self.base + '/one-use-hoster', known_hoster=True)
        resolver._resolveWithResolveUrl = lambda *a, **k: self.base + '/master.m3u8'
        self.assertEqual(resolver.sourcesResolve(self.item(), check_stream=True), self.base + '/master.m3u8')
        self.assertEqual([c[1] for c in self.calls], ['/master.m3u8'])

    def test_provider_html_and_resolver_html_do_not_reach_player(self):
        resolver = self.resolver(self.base + '/error.mp4')
        self.assertIsNone(resolver.sourcesResolve(self.item(), check_stream=True))
        resolver = self.resolver(self.base + '/one-use-hoster', known_hoster=True)
        resolver._resolveWithResolveUrl = lambda *a, **k: self.base + '/fake.m3u8'
        self.assertIsNone(resolver.sourcesResolve(self.item(), check_stream=True))

    def test_explicit_direct_source_still_requires_media_content(self):
        resolver = self.resolver(self.base + '/opaque')
        self.assertEqual(resolver.sourcesResolve(self.item(True), check_stream=True), self.base + '/opaque')
        resolver = self.resolver(self.base + '/fake.m3u8')
        self.assertIsNone(resolver.sourcesResolve(self.item(True), check_stream=True))


if __name__ == '__main__':
    unittest.main()
