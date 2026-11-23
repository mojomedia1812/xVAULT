"""Exercise the JD2 route and actual HTTP form against an isolated local endpoint."""
import ast
import importlib.util
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, quote_plus, urlencode, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HANDLER = 'resources.lib.handler.jdownloader2Handler'


class JD2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = []

        class Endpoint(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'jdownloader = true;')

            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                cls.requests.append((self.path, self.headers['Content-Type'],
                                     parse_qs(body.decode('utf8'), keep_blank_values=True)))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'success')

            def log_message(self, *args):
                pass

        cls.server = HTTPServer(('127.0.0.1', 0), Endpoint)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.settings = dict(jd2_enabled='true', jd2_host='127.0.0.1',
                             jd2_port=str(self.server.server_port), jd2_directory='')
        self.control = types.ModuleType('resources.lib.control')
        self.control.getSetting = lambda key: self.settings.get(key, '')
        self.control.infoDialog = Mock()
        xbmc = types.ModuleType('xbmc')
        xbmc.LOGINFO, xbmc.log = 1, Mock()
        spec = importlib.util.spec_from_file_location(HANDLER, ROOT / 'resources/lib/handler/jdownloader2Handler.py')
        self.handler = importlib.util.module_from_spec(spec)
        self.modules = patch.dict(sys.modules, {'resources.lib.control': self.control, 'xbmc': xbmc})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        # Avoid Kodi imports, including any parent package attributes from other tests.
        with patch('resources.lib.control', self.control, create=True):
            spec.loader.exec_module(self.handler)

    def test_package_names(self):
        cases = [
            ({'title': 'Alien', 'year': 1979}, {'quality': '1080p'}, 'Alien (1979) [1080p]'),
            ({'title': 'Alien', 'year': None}, {}, 'Alien'),
            ({'title': 'Film', 'year': 0}, {'quality': 'Unknown'}, 'Film'),
            ({'title': 'Film', 'year': '2026?'}, {}, 'Film'),
            ({'title': 'Scrubs', 'mediatype': 'tvshow', 'season': '2', 'episode': '1', 'year': 2001}, {'quality': 'HD'}, 'Scrubs S02E01 [HD]'),
            ({'title': 'Episodentitel', 'tvshowtitle': 'Serie', 'mediatype': 'episode', 'season': 0, 'episode': 3}, {}, 'Serie S00E03'),
            ({'title': 'Serie', 'mediatype': 'episode', 'season': 2}, {}, 'Serie'),
            ({'title': 'Serie', 'mediatype': 'episode', 'season': -1, 'episode': 2}, {}, 'Serie'),
            ({'originaltitle': 'Original'}, {}, 'Original'),
            ({}, {'quality': '4K'}, 'Alter Titel S02E01 [4K]'),
        ]
        for meta, source, expected in cases:
            with self.subTest(meta=meta):
                self.assertEqual(self.handler.package_name(meta, source, 'Alter Titel S02E01'), expected)
        for unknown in ('', None, 'unknown', 'Unbekannt', 'N/A', '?', '-', '0'):
            self.assertEqual(self.handler.package_name({'title': 'Film'}, {'quality': unknown}), 'Film')
        self.assertEqual(self.handler.package_name(None, {'quality': 'HD'}), '')

    def test_actual_form_encoding_and_optional_directory(self):
        for directory in ('', '   ', '/srv/Filme & Serien/ÄÖ', r'D:\Videos\München + Köln'):
            with self.subTest(directory=directory):
                self.settings['jd2_directory'] = directory
                url = 'https://host.test/watch?a=1&b=%2B#ä'
                ok = self.handler.cJDownloader2Handler().sendToJDownloader2(
                    url, metadata={'title': 'München & Köln + 東京', 'year': 2026}, source={'quality': '720p'})
                self.assertTrue(ok)
                path, content_type, form = self.requests[-1]
                self.assertEqual(path, '/flash/add')
                self.assertIn('application/x-www-form-urlencoded', content_type)
                expected = dict(passwords=['myPassword'], source=['http://jdownloader.org/spielwiese'],
                                urls=[url], submit=['Add Link to JDownloader'],
                                package=['München & Köln + 東京 (2026) [720p]'])
                if directory.strip():
                    expected['dir'] = [directory.strip()]
                self.assertEqual(form, expected)
                self.assertNotIn('filename', form)
        self.assertTrue(self.handler.cJDownloader2Handler().sendToJDownloader2('https://host.test/file'))
        self.assertNotIn('package', self.requests[-1][2])

    def route(self, action, item, meta):
        tree = ast.parse((ROOT / 'default.py').read_text(encoding='utf8'))
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and isinstance(n.test, ast.Compare)
                      and ast.unparse(n.test).startswith("action in ('sendToJD', 'sendToJD2'"))
        fake_sources = types.ModuleType('resources.lib.sources')
        reader = Mock(return_value=meta)
        fake_sources.sources = lambda: types.SimpleNamespace(_readSourceContext=reader)
        jd1 = types.ModuleType('resources.lib.handler.jdownloaderHandler')
        jd1_call = Mock()
        jd1.cJDownloaderHandler = lambda: types.SimpleNamespace(sendToJDownloader=jd1_call)
        myjd = types.ModuleType('resources.lib.handler.myjdownloaderHandler')
        myjd_call = Mock()
        myjd.cMyJDownloaderHandler = lambda: types.SimpleNamespace(sendToMyJDownloader=myjd_call)
        pyload = types.ModuleType('resources.lib.handler.pyLoadHandler')
        pyload_call = Mock()
        pyload.cPyLoadHandler = lambda: types.SimpleNamespace(sendToPyLoad=pyload_call)
        scope = dict(action=action, source=json.dumps([item]), name='Fallback (2026)',
                     params={'context': 'stable-context'}, json=json, parse_qs=parse_qs, urlsplit=urlsplit)
        with patch.dict(sys.modules, {HANDLER: self.handler, 'resources.lib.sources': fake_sources,
                                      'resources.lib.handler.jdownloaderHandler': jd1,
                                      'resources.lib.handler.myjdownloaderHandler': myjd,
                                      'resources.lib.handler.pyLoadHandler': pyload}), \
                patch('resources.lib.sources', fake_sources, create=True):
            exec(compile(ast.Module(body=branch.body, type_ignores=[]), 'default.py', 'exec'), scope)
        return reader, dict(sendToJD=jd1_call, sendToMyJD=myjd_call, sendToPyLoad=pyload_call)

    def test_route_preserves_all_url_choices_and_carries_context(self):
        cases = [
            ({'url': 'https://cdn.test/video', 'jd_url': 'https://host.test/page'}, 'https://host.test/page'),
            ({'url': 'https://host.test/file$$extra'}, 'https://host.test/file'),
            ({'url': 'https://cdn.test/video|' + urlencode({'Referer': 'https://host.test/watch/123'})}, 'https://host.test/watch/123'),
            ({'url': 'https://cdn.test/video|' + urlencode({'Referer': 'https://host.test/'})}, 'https://cdn.test/video'),
            ({'url': 'https://host.test/file'}, 'https://host.test/file'),
        ]
        for item, expected in cases:
            with self.subTest(item=item):
                item['quality'] = '1080p'
                reader, _ = self.route('sendToJD2', item, {'title': 'Serie', 'season': 2, 'episode': 1})
                reader.assert_called_once_with('stable-context')
                self.assertEqual(self.requests[-1][2]['urls'], [expected])
                self.assertEqual(self.requests[-1][2]['package'], ['Serie S02E01 [1080p]'])
        self.route('sendToJD2', {'url': 'https://host.test/file'}, {})
        self.assertEqual(self.requests[-1][2]['package'], ['Fallback (2026)'])

    def test_jd1_does_not_read_or_receive_jd2_metadata(self):
        reader, calls = self.route('sendToJD', {'url': 'https://host.test/file'}, {'title': 'Film'})
        reader.assert_not_called()
        calls['sendToJD'].assert_called_once_with('https://host.test/file')

    def test_myjd_and_pyload_keep_existing_arguments_and_referer(self):
        url = 'https://cdn.test/video|' + urlencode({'Referer': 'https://host.test/'})
        for action in ('sendToMyJD', 'sendToPyLoad'):
            reader, calls = self.route(action, {'url': url}, {'title': 'Film'})
            reader.assert_not_called()
            expected = ('https://cdn.test/video', 'Fallback (2026)', 'https://host.test/') if action == 'sendToMyJD' else ('Fallback (2026)', 'https://cdn.test/video')
            calls[action].assert_called_once_with(*expected)

    def test_disabled_or_unreachable_jd2_does_not_submit(self):
        count = len(self.requests)
        self.settings['jd2_enabled'] = 'false'
        self.assertFalse(self.handler.cJDownloader2Handler().sendToJDownloader2('https://host.test/file'))
        self.settings['jd2_enabled'] = 'true'
        with patch.object(self.handler, 'urlopen', side_effect=OSError('offline')):
            self.assertFalse(self.handler.cJDownloader2Handler().sendToJDownloader2('https://host.test/file'))
        self.assertEqual(len(self.requests), count)

    def test_context_menu_passes_token_and_setting_is_remote_text(self):
        tree = ast.parse((ROOT / 'resources/lib/sources.py').read_text(encoding='utf8'))
        menu = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                    and ast.unparse(n.test) == "control.getSetting('jd2_enabled') == 'true'")
        cm = []
        scope = dict(control=self.control, cm=cm, sysaddon='plugin://plugin.video.xvault/',
                     sysname=quote_plus('München & Köln'), syssource=quote_plus('[{}]'),
                     source_context='token-123', quote_plus=quote_plus)
        exec(compile(ast.Module(body=[menu], type_ignores=[]), 'sources.py', 'exec'), scope)
        query = parse_qs(urlsplit(cm[0][1][len('RunPlugin('):-1]).query)
        self.assertEqual(query['context'], ['token-123'])
        self.assertEqual(query['name'], ['München & Köln'])
        setting = ET.parse(ROOT / 'resources/settings.xml').find(".//setting[@id='jd2_directory']")
        self.assertEqual(setting.get('type'), 'text')
        self.assertEqual(setting.get('default'), '')
        self.assertIn('JD2-Rechner', setting.get('label'))
        compact = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_compactPlaybackMeta')
        scope = {}
        exec(compile(ast.Module(body=[compact], type_ignores=[]), 'sources.py', 'exec'), scope)
        self.assertEqual(scope['_compactPlaybackMeta'](None, {'tvshowtitle': 'Serie'}), {'tvshowtitle': 'Serie'})


if __name__ == '__main__':
    unittest.main()
