"""VIXSTREAM manifests must prove their language, quality and nested validity."""
import ast
import hashlib
import json
from pathlib import Path
import re
import types
import unittest


ROOT = Path(__file__).resolve().parents[2]
tree = ast.parse((ROOT / 'sites/vixstream.py').read_text(encoding='utf-8'))
definitions = [n for n in tree.body if isinstance(n, (ast.Import, ast.Assign, ast.ClassDef))]
settings = {}
namespace = {
    'getSetting': lambda key, default='': settings.get(key, default),
    'logger': types.SimpleNamespace(**{level: lambda *a: None for level in ('info', 'warning', 'error', 'debug')}),
}
exec(compile(ast.Module(body=definitions, type_ignores=[]), 'vixstream.py', 'exec'), namespace)
SOURCE = namespace['source']
MASTER = '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1080000,RESOLUTION=854x480\nchild.m3u8\n'
MEDIA = '#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\nsegment.ts\n#EXT-X-ENDLIST\n'


class VixstreamTests(unittest.TestCase):
    def setUp(self):
        settings.clear()

    def scraper(self, master=MASTER, child=MEDIA, status='200'):
        scraper = SOURCE()
        scraper.mediatype = 'tvshow'
        scraper._get_tmdb_id = lambda imdb: '7626'
        scraper._fresh_embed_url = lambda *a: ('https://fixture.invalid/embed', 'https://fixture.invalid/tv')
        scraper._playlist_from_embed = lambda *a: ('https://fixture.invalid/playlist/1', {'Referer': 'fixture'}, master)
        scraper._request = lambda url, **kw: (child, status, url)
        return scraper

    def test_requested_german_does_not_prove_muxed_audio_language(self):
        settings['hosts.language'] = '1'
        items = self.scraper().run(['The Monkees'], 1966, 1, 1, 'tt0060010')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['language'], 'unknown')
        self.assertEqual(items[0]['info'], 'Sprache unbekannt')
        self.assertEqual(items[0]['quality'], 'SD')

    def test_unknown_language_is_not_duplicated_for_de_and_en_requests(self):
        self.assertEqual(len(self.scraper().run(['Monkees'], 1966, 1, 1, 'fixture')), 1)

    def test_english_audio_in_child_is_never_reported_as_german(self):
        settings['hosts.language'] = '1'
        child = MEDIA.replace('#EXTM3U', '#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,LANGUAGE="en",NAME="English"')
        self.assertEqual(self.scraper(child=child).run(['Monkees'], 1966, 1, 1, 'fixture'), [])

    def test_verified_german_audio_and_manifest_quality_are_retained(self):
        settings['hosts.language'] = '1'
        master = MASTER.replace('854x480', '1280x720').replace('#EXTM3U', '#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,LANGUAGE="de",NAME="Deutsch"')
        items = self.scraper(master=master).run(['Fixture'], 2020, 1, 1, 'fixture')
        self.assertEqual((items[0]['language'], items[0]['quality']), ('de', '720p'))

    def test_german_subtitles_do_not_prove_german_audio(self):
        master = MASTER.replace('#EXTM3U', '#EXTM3U\n#EXT-X-MEDIA:TYPE=SUBTITLES,LANGUAGE="de",NAME="Deutsch"')
        items = self.scraper(master=master).run(['Fixture'], 2020, 1, 1, 'fixture')
        self.assertEqual(items[0]['language'], 'unknown')

    def test_unknown_audio_tag_remains_available_as_unknown(self):
        master = MASTER.replace('#EXTM3U', '#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,LANGUAGE="und",NAME="Audio"')
        self.assertEqual(self.scraper(master=master).run(['Fixture'], 2020, 1, 1, 'fixture')[0]['language'], 'unknown')

    def test_error_child_and_fake_master_are_rejected(self):
        for scraper in (self.scraper(child='<html>error</html>'), self.scraper(status='403'),
                        self.scraper(master='<html>error</html>'), self.scraper(master='#EXTM3U\n')):
            with self.subTest(scraper=scraper):
                self.assertEqual(scraper.run(['Fixture'], 2020, 1, 1, 'fixture'), [])
                self.assertIsNone(scraper.resolve('vixsrc://tv/7626/1/1?lang=de'))

    def test_playlist_cycles_are_bounded(self):
        scraper = self.scraper(child=MASTER)
        calls = []
        def request(url, **kw):
            calls.append(url)
            return MASTER, '200', url
        scraper._request = request
        self.assertFalse(scraper._inspect_playlist('https://fixture.invalid/playlist/1', {}, MASTER)[0])
        self.assertEqual(len(calls), 1)

    def test_unknown_stream_resolves_without_inventing_language(self):
        url = self.scraper().resolve('vixsrc://tv/7626/1/1?lang=de')
        self.assertTrue(url.startswith('https://fixture.invalid/playlist/1|'))

    def test_initial_kodi_manifest_access_keeps_headers_on_replacement_domains(self):
        player_tree = ast.parse((ROOT / 'resources/lib/player.py').read_text(encoding='utf-8'))
        cls = next(n for n in player_tree.body if isinstance(n, ast.ClassDef) and n.name == 'player')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_needsManifestHeadersInPath')
        scope = {'re': re}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'player.py', 'exec'), scope)
        needs = lambda url: scope['_needsManifestHeadersInPath'](None, url)
        for host in ('vixcloud.co', 'vixsrc.to', 'replacement.invalid'):
            self.assertTrue(needs('https://' + host + '/playlist/123?token=fixture'))
        self.assertFalse(needs('https://fixture.invalid/movie.mp4'))

    def test_provider_revision_invalidates_old_mislabeled_source_cache(self):
        tree = ast.parse((ROOT / 'resources/lib/sources.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'sources')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_sourceCacheKey')
        scope = dict(json=json, hashlib=hashlib, py2_decode=lambda x: x,
                     control=types.SimpleNamespace(addonVersion='fixture', getSetting=lambda key: ''))
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'sources.py', 'exec'), scope)
        provider = self.scraper()
        args = ['Monkees', 1966, 'tt0060010', 1, 1, 'The Monkees', '', '', '', [('vixstream', provider, 1)]]
        key = lambda: scope['_sourceCacheKey'](types.SimpleNamespace(mediatype='tvshow'), *args)
        current = key()
        del provider.cache_version
        self.assertNotEqual(current, key())


if __name__ == '__main__':
    unittest.main()
