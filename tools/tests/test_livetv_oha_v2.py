"""Regression tests for OHA's October 2026 switch to the manifest v2 API."""
import ast
import json
import os
from pathlib import Path
import re
import tempfile
import time
import types
import unittest
from urllib.parse import urlparse, urlunparse


SOURCE = Path(__file__).resolve().parents[2] / 'resources/lib/linear_tv.py'


class HTTPError(Exception):
    def __init__(self, response):
        self.response = response


class Reply:
    def __init__(self, data=None, status=200):
        self.data, self.status_code, self.closed = data, status, False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPError(self)

    def json(self):
        return self.data

    def close(self):
        self.closed = True


class OhaProtocolTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='xvault-oha-')
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        self.calls, self.replies = [], []
        def get(url, **kwargs):
            self.calls.append((url, kwargs))
            return self.replies.pop(0)
        progress = types.SimpleNamespace(create=lambda *a: None, update=lambda *a: None, close=lambda: None, iscanceled=lambda: False)
        scope = dict(re=re, os=os, json=json, time=time, urlparse=urlparse, urlunparse=urlunparse,
                     control=types.SimpleNamespace(addonProfilePath=folder.name, getSetting=lambda key, default='': default,
                                                  infoDialog=lambda *a, **k: None, progressDialog=progress, addonName='xVAULT'),
                     log_utils=types.SimpleNamespace(log=lambda *a: None, LOGWARNING=2), requests=types.SimpleNamespace(get=get))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        scope[target.id] = value
        defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
        exec(compile(ast.Module(body=defs, type_ignores=[]), str(SOURCE), 'exec'), scope)
        scope['CATALOG_FILE'] = str(self.folder / 'catalog.json')
        scope['_visible_channels'] = lambda channels: channels
        self.scope = scope

    def test_catalog_uses_get_country_filter_and_cursor(self):
        self.replies.append(Reply({'items': [], 'nextCursor': None}))
        self.scope['_catalog_page']('Germany', '300')
        url, options = self.calls[0]
        self.assertEqual(url, 'https://oha.to/live/catalog/live/channels.json')
        self.assertEqual(options['params'], {'filter[group]': 'Germany', 'cursor': '300'})

    def test_live_items_preserve_new_id_group_and_epg_identity(self):
        items = [{'type': 'live', 'id': '12345', 'name': 'ARD HD (1)', 'url': 'https://oha.to/live/play/12345', 'tags': ['Germany'], 'ids': {'tvg': 'DasErste.de'}},
                 {'type': 'iptv', 'id': 'old', 'url': 'https://oha.to/oha-iptv/play/old'}]
        channels = self.scope['_parse_catalog_items'](items)
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0]['id'], '12345')
        self.assertEqual(channels[0]['group'], 'Germany')
        self.assertEqual(channels[0]['epg_id'], 'DasErste.de')

    def test_resolve_uses_new_endpoint_without_signature_ping(self):
        self.replies.append(Reply({'url': 'https://stream.example/live.m3u8', 'format': 'hls'}))
        self.assertEqual(self.scope['_resolve']('https://oha.to/live/play/12345'), 'https://stream.example/live.m3u8')
        self.assertEqual(self.calls[0][0], 'https://oha.to/live/resolve')
        self.assertEqual(self.calls[0][1]['params'], {'url': 'https://oha.to/live/play/12345'})
        self.assertEqual(len(self.calls), 1)

    def test_obsolete_play_urls_are_not_sent_to_new_resolver(self):
        self.assertEqual(self.scope['_resolve']('https://oha.to/oha-iptv/play/old'), '')
        self.assertFalse(self.calls)

    def test_404_switches_to_alternate_domain_and_closes_responses(self):
        first, second = Reply(status=404), Reply({'items': []})
        self.replies.extend([first, second])
        self.scope['_catalog_page']('Germany', None)
        self.assertTrue(self.calls[1][0].startswith('https://www.oha.to/'))
        self.assertTrue(first.closed and second.closed)

    def test_authentication_error_does_not_loop_over_domains(self):
        response = Reply(status=401)
        self.replies.append(response)
        with self.assertRaises(HTTPError):
            self.scope['_catalog_page']('Germany', None)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(response.closed)

    def test_old_cache_is_invalid_even_when_recent(self):
        cache = {'source': 'oha.to', 'updated_at': time.time(), 'channels': [{'id': '123', 'url': 'https://oha.to/live/play/123'}]}
        self.assertFalse(self.scope['_cache_valid'](cache))
        cache['schema_version'] = 2
        self.assertTrue(self.scope['_cache_valid'](cache))
        cache['channels'][0]['url'] = 'https://oha.to/oha-iptv/play/123'
        self.assertFalse(self.scope['_cache_valid'](cache))

    def test_refresh_backs_up_legacy_cache_and_stores_protocol_version(self):
        path = Path(self.scope['CATALOG_FILE'])
        old = {'source': 'oha.to', 'channels': [{'id': 'old', 'name': 'ARD HD', 'url': 'https://oha.to/oha-iptv/play/old'}]}
        path.write_text(json.dumps(old), encoding='utf-8')
        self.scope['_download_catalog'] = lambda: [{'id': 'new', 'name': 'ARD HD', 'url': 'https://oha.to/live/play/new'}]
        channels = self.scope['_catalog'](force=True)
        self.assertEqual(json.loads(Path(str(path) + '.legacy-backup').read_text()), old)
        self.assertEqual(json.loads(path.read_text())['schema_version'], 2)
        self.assertEqual(self.scope['_channel_by_id'](channels, 'old')['id'], 'new')

    def test_download_failure_does_not_reuse_incompatible_legacy_cache(self):
        path = Path(self.scope['CATALOG_FILE'])
        path.write_text(json.dumps({'source': 'oha.to', 'channels': [{'id': 'old'}]}))
        self.scope['_download_catalog'] = lambda: []
        self.assertEqual(self.scope['_catalog'](force=True), [])

    def test_compatible_expired_cache_remains_available_when_offline(self):
        path = Path(self.scope['CATALOG_FILE'])
        channels = [{'id': '1', 'name': 'ARD', 'url': 'https://oha.to/live/play/1'}]
        path.write_text(json.dumps({'source': 'oha.to', 'schema_version': 2, 'updated_at': 0, 'channels': channels}))
        self.scope['_download_catalog'] = lambda: []
        result = self.scope['_catalog'](force=True)
        self.assertEqual(result[0]['id'], '1')

    def test_repeated_pagination_cursor_rejects_partial_catalog(self):
        self.scope['_catalog_page'] = lambda *a: {'items': [], 'nextCursor': '300'}
        self.assertEqual(self.scope['_download_catalog'](), [])

    def test_ambiguous_names_do_not_remap_old_channel_ids(self):
        channels = [{'id': '1', 'name': 'ARD'}, {'id': '2', 'name': 'ARD'}]
        self.scope['_retain_channel_aliases'](channels, [{'id': 'old', 'name': 'ARD'}])
        self.assertIsNone(self.scope['_channel_by_id'](channels, 'old'))


if __name__ == '__main__':
    unittest.main()
