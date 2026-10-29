import ast
from http.cookiejar import LWPCookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import types
import unittest
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import Request, build_opener

ROOT = Path(__file__).resolve().parents[2]


class BoundedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == '/error':
                    self.send_error(403)
                    return
                body = b'{"ok":true}' if self.path != '/big' else b'x' * 1000
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                try:
                    for b in body:
                        self.wfile.write(bytes([b]))
                        self.wfile.flush()
                        if self.path == '/slow':
                            time.sleep(0.1)
                except (OSError, ConnectionError):
                    pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.daemon_threads = True
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.url = 'http://127.0.0.1:%s' % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def request(self, path, **options):
        tree = ast.parse((ROOT / 'resources/lib/requestHandler.py').read_text(encoding='utf8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'cRequestHandler')
        cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'request_bounded']
        scope = dict(time=time, LWPCookieJar=LWPCookieJar, Request=Request, urlparse=urlparse, HTTPError=HTTPError)
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'requestHandler.py', 'exec'), scope)
        req = scope['cRequestHandler']()
        with tempfile.TemporaryDirectory() as folder:
            req._cookiePath = str(Path(folder) / 'cookies')
            req._sUrl = self.url + path
            req._headerEntries = {}
            req._cRequestHandler__getDnsOverride = lambda: None
            req._cRequestHandler__getOpener = lambda *args: build_opener()
            return req.request_bounded(**options)

    def test_real_http_reply_and_http_error(self):
        self.assertEqual(json.loads(self.request('/ok')), {'ok': True})
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError):
            self.request('/error')

    def test_slow_trickle_has_total_budget_not_just_idle_timeout(self):
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            self.request('/slow', budget=0.2, timeout=0.5)
        self.assertLess(time.monotonic() - start, 1.5)

    def test_cancellation_and_response_size_are_bounded(self):
        with self.assertRaises(TimeoutError):
            self.request('/ok', cancelled=lambda: True)
        with self.assertRaises(ValueError):
            self.request('/big', limit=30)

    def test_oha_uses_uncached_verified_bounded_api_requests(self):
        tree = ast.parse((ROOT / 'sites/huhu.py').read_text(encoding='utf8'))
        nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Import))]
        from urllib.error import HTTPError, URLError
        import ssl
        calls = []
        def request(url, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(addHeaderEntry=lambda *a: None,
                request_bounded=lambda **kw: (calls.append(kw) or '{"sources":[]}'))
        scope = dict(cRequestHandler=request, getSetting=lambda key: '', KODI_AVAILABLE=False,
                     HTTPError=HTTPError, URLError=URLError, logger=types.SimpleNamespace(warning=lambda *a: None))
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'huhu.py', 'exec'), scope)
        scope['_request_json']('https://fixture.test/api')
        self.assertFalse(calls[0]['caching'])
        self.assertTrue(calls[0]['ssl_verify'])
        self.assertFalse(calls[0]['follow_redirects'])
        self.assertEqual(calls[1]['budget'], 12)
        scope['getSetting'] = lambda key: 'false'
        self.assertIsNone(scope['_request_json']('https://fixture.test/api'))
        self.assertEqual(len(calls), 2)

    def test_disabled_oha_cannot_be_resolved_from_an_old_source_context(self):
        tree = ast.parse((ROOT / 'resources/lib/sources.py').read_text(encoding='utf8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'sources')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'sourcesResolve')
        scope = {'control': types.SimpleNamespace(getSetting=lambda key: 'false')}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'sources.py', 'exec'), scope)
        instance = types.SimpleNamespace()
        item = dict(url='https://fixture.test/old', provider='huhu', direct=False)
        self.assertIsNone(scope['sourcesResolve'](instance, item))


if __name__ == '__main__':
    unittest.main()
