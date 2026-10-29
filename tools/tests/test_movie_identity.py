import ast
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from resources.lib import movie_identity as identity

ROOT = Path(__file__).resolve().parents[2]


class IdentityTests(unittest.TestCase):
    def provider(self, name):
        import re
        tree = ast.parse((ROOT / ('sites/' + name + '.py')).read_text(encoding='utf8'))
        nodes = [n for n in tree.body if isinstance(n, (ast.Import, ast.ClassDef, ast.FunctionDef, ast.Assign))]
        nodes = [n for n in tree.body if n in nodes or (isinstance(n, ast.ImportFrom) and n.module in ('html', 'urllib.parse'))]
        parser = types.SimpleNamespace(parse=lambda html, pattern: (bool(re.findall(pattern, html, re.S)), re.findall(pattern, html, re.S)))
        parser_factory = type('Parser', (), {'parse': staticmethod(parser.parse)})
        scope = dict(movie_identity=identity, getSetting=lambda key, default='': default,
            cleantitle=types.SimpleNamespace(get=identity.title_key), cParser=parser_factory,
            logger=types.SimpleNamespace(**{k: lambda *a: None for k in ('info', 'warning', 'error')}),
            isBlockedHoster=lambda url, **kw: (False, 'Fixture', url, 1),
            cRequestHandler=lambda *a, **kw: types.SimpleNamespace(request=lambda: '{"url":"fixture.test"}'))
        # xbmc is only imported for the host environment, not used in matching.
        nodes = [n for n in nodes if not (isinstance(n, ast.Import) and any(a.name == 'xbmc' for a in n.names))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), name + '.py', 'exec'), scope)
        return scope['source'](), scope

    def test_remakes_never_match_by_name_alone(self):
        for title, old, new in [('Buddy', 2013, 2026), ("Don't Move", 2024, 2026)]:
            self.assertEqual(identity.classify([title], new, '', {'title': title, 'year': old}), 'conflict')
            self.assertEqual(identity.classify([title], new, '', {'title': title, 'year': new}), 'verified')
            self.assertEqual(identity.classify([title], new, '', {'title': title}), 'unknown')

    def test_ids_override_regional_years_but_conflicting_ids_always_fail(self):
        self.assertEqual(identity.classify(['Alias'], 2026, 'tt1000001',
                         {'title': 'Original', 'year': 2025, 'imdb': 'tt1000001'}), 'verified')
        self.assertEqual(identity.classify(['Buddy'], 2026, 'tt1000001',
                         {'title': 'Buddy', 'year': 2026, 'imdb': 'tt1000002'}), 'conflict')
        self.assertEqual(identity.classify(['Buddy'], 2026, '', {'title': 'Buddy', 'year': 2025}), 'conflict')

    def test_html_only_uses_movie_metadata_not_copyright_or_recommendations(self):
        html = '<h1>Buddy</h1><div>Jahr: 2013</div><footer>Copyright 2026</footer>'
        self.assertEqual(identity.from_html(html)['year'], '2013')
        self.assertEqual(identity.classify(['Buddy'], 2026, '', identity.from_html(html)), 'conflict')
        page = '<h1>Buddy</h1><a href="https://imdb.com/title/tt1000002">Empfehlung</a>'
        self.assertEqual(identity.from_html(page)['imdb'], '')
        schema = {'@type': 'Movie', 'name': 'Other', 'sameAs': 'https://imdb.com/title/tt1000001'}
        page += '<script type="application/ld+json">' + json.dumps(schema) + '</script>'
        self.assertEqual(identity.from_html(page)['imdb'], '')

    def test_primary_schema_and_aliases(self):
        schema = {'@type': 'Movie', 'name': 'Buddy', 'datePublished': '2026-09-01',
                  'sameAs': ['https://imdb.com/title/tt1000001']}
        page = '<h1>Buddy</h1><script type="application/ld+json">' + json.dumps(schema) + '</script>'
        found = identity.from_html(page)
        self.assertEqual(found, {'title': 'Buddy', 'year': '2026', 'imdb': 'tt1000001'})
        self.assertEqual(identity.classify(['Local title', 'Buddy'], 2026, '', found), 'verified')

    def test_wrong_content_exclusion_is_local_bounded_and_expires(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / 'wrong-content.json')
            items = [dict(identity_target='tt1000001', provider='test', url='https://fixture.test/a?token=private'),
                     dict(identity_target='tt1000001', provider='test', url='https://fixture.test/b'),
                     dict(identity_target='tt1000002', provider='test', url='https://fixture.test/a?token=private')]
            identity.reject(path, items[0])
            self.assertEqual(identity.without_rejected(path, items), items[1:])
            self.assertNotIn('private', Path(path).read_text())
            with patch.object(identity.time, 'time', return_value=identity.time.time() + 86402):
                self.assertEqual(identity.without_rejected(path, items), items)

    def test_central_gate_applies_to_all_movie_providers_but_not_series(self):
        tree = ast.parse((ROOT / 'resources/lib/sources.py').read_text(encoding='utf8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'sources')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_getSource')
        scope = {'movie_identity': identity,
                 'log_utils': types.SimpleNamespace(log=lambda *a: None, LOGINFO=1)}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'sources.py', 'exec'), scope)
        for media, expected in [('movie', 0), ('tvshow', 1)]:
            instance = types.SimpleNamespace(mediatype=media, sources=[],
                        _acceptsHostDict=lambda call: False, _stableUniqueSources=lambda items: items,
                        _providerDisplayName=lambda *args: 'Fixture')
            scraper = types.SimpleNamespace(run=lambda *args: [dict(url='fixture', movie_identity={'title': 'Buddy', 'year': 2013})])
            scope['_getSource'](instance, ['Buddy'], 2026, 0, 0, '', 'fixture', scraper)
            self.assertEqual(len(instance.sources), expected)

    def test_movie2k2_checks_all_same_name_candidates(self):
        tree = ast.parse((ROOT / 'sites/movie2k2.py').read_text(encoding='utf8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        search = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'search')
        import re
        from urllib import parse
        parser = types.SimpleNamespace(parse=lambda html, pattern: (True, [('/stream/old', 'Buddy'), ('/stream/new', 'Buddy')]))
        req = lambda url: types.SimpleNamespace(addHeaderEntry=lambda *a: None, request=lambda: 'list')
        scope = dict(re=re, urllib_parse=parse, cRequestHandler=req, cParser=lambda: parser,
                     cleantitle=types.SimpleNamespace(get=identity.title_key), SITE_NAME='Fixture',
                     logger=types.SimpleNamespace(info=lambda *a: None))
        exec(compile(ast.Module(body=[search], type_ignores=[]), 'movie2k2.py', 'exec'), scope)
        scraper = types.SimpleNamespace(search_link='https://fixture.test/search?q=%s', ua='test', base_link='https://fixture.test')
        self.assertEqual(len(scope['search'](scraper, ['Buddy'], 2026, 0, 0)), 2)

    def test_autoplay_does_not_submit_unverified_movie_sources(self):
        tree = ast.parse((ROOT / 'resources/lib/sources.py').read_text(encoding='utf8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'sources')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_resolveAutoplayCandidates')
        scope = {'time': __import__('time'), 'SOURCE_RESOLVE_TIMEOUT': 30}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'sources.py', 'exec'), scope)
        calls = []
        future = types.SimpleNamespace(done=lambda: True, result=lambda: 'https://fixture.test/media')
        instance = types.SimpleNamespace(mediatype='movie', _ensureExecutor=lambda: None,
                    _autoplayPrefetchWindow=lambda items: 2, sourcesResolve=lambda *a: None,
                    executor=types.SimpleNamespace(submit=lambda *args: (calls.append(args[1]) or future)),
                    _cancelFutures=lambda *args: None)
        unknown = {'identity_status': 'unknown'}
        self.assertEqual(scope['_resolveAutoplayCandidates'](instance, [unknown]), (None, None))
        self.assertEqual(calls, [])
        verified = {'identity_status': 'verified'}
        item, url = scope['_resolveAutoplayCandidates'](instance, [unknown, verified])
        self.assertIs(item, verified)
        self.assertEqual(calls, [verified])

    def test_movie2k2_run_skips_old_year_and_keeps_correct_later_candidate(self):
        scraper, scope = self.provider('movie2k2')
        scraper.mediatype = 'movie'
        scraper.search = lambda *a: ['old', 'new']
        pages = {key: '<h1>Buddy</h1>Jahr: %s<a onclick="loadMirror(\'https://fixture.test/%s\')">VOE</a>' % (year, key)
                 for key, year in [('old', 2013), ('new', 2026)]}
        scope['cRequestHandler'] = lambda url: types.SimpleNamespace(addHeaderEntry=lambda *a: None, request=lambda: pages[url])
        found = scraper.run(['Buddy'], 2026)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['url'], 'https://fixture.test/new')
        self.assertEqual(found[0]['identity_status'], 'verified')

    def test_filmpalast_run_selects_correct_year(self):
        scraper, scope = self.provider('filmpalast')
        scraper.mediatype = 'movie'
        scraper._search_candidates = lambda *a: [('https://fixture.test/old', "Don't Move"), ('https://fixture.test/new', "Don't Move")]
        scraper._request = lambda url, *a: '<h1>Don\'t Move</h1>Jahr: ' + ('2024' if url.endswith('old') else '2026')
        scraper._parse_streams = lambda html: [('Fixture', 'https://fixture.test/media')]
        found = scraper.run(["Don't Move"], 2026)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['movie_identity']['year'], '2026')

    def test_megakino_continues_after_wrong_year(self):
        scraper, scope = self.provider('megakino')
        pages = {'search': '<a class="poster grid-item" href="/old"><img alt="Buddy"></a><a class="poster grid-item" href="/new"><img alt="Buddy"></a>',
                 'old': '<h1>Buddy</h1>Jahr: 2013', 'new': '<h1>Buddy</h1>Jahr: 2026'}
        scraper.get_html = lambda url: pages['search' if 'do=search' in url else url.rsplit('/', 1)[-1]]
        found = scraper._search_and_match('Buddy', ['buddy'], ['Buddy'], 2026, '', True)
        self.assertTrue(found.endswith('/new'))
        self.assertEqual(scraper._found_identity['year'], '2026')


if __name__ == '__main__':
    unittest.main()
