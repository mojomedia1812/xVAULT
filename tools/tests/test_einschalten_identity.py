"""Identity evidence must come from the selected provider movie, never our query."""
import ast
import json
from pathlib import Path
import re
import types
import unittest
from unittest.mock import Mock
from urllib.parse import urljoin, quote_plus, urlsplit

from resources.lib import movie_identity

ROOT = Path(__file__).resolve().parents[2]
ALIEN = 'Alien - Das unheimliche Wesen aus einer fremden Welt'
PATHS = ('sites/einschalten.py', 'scrapers/scrapers_source/de/einschalten.py')


def card(title=ALIEN, year=1979, slug='alien'):
    return '<a class="group" title="%s" href="/movie/%s"><span>%s</span></a>' % (title, slug, year)


class EinschaltenTests(unittest.TestCase):
    def scraper(self, path, search=None, detail=None, api=None):
        self.calls = []
        def request(url, **kwargs):
            self.calls.append(url)
            if '/search?' in url:
                body = search if search is not None else card()
            elif url.endswith('/watch'):
                body = api if api is not None else json.dumps({'streamUrl': 'https://fixture.invalid/video', 'releaseName': 'Alien.German.1979.1080p'})
            else:
                body = detail if detail is not None else '<h1>%s</h1><meta itemprop="datePublished" content="1979-05-25">' % ALIEN
            def get():
                if isinstance(body, Exception): raise body
                return body
            return types.SimpleNamespace(request=get)
        parser = types.SimpleNamespace(parse=lambda html, pattern: (bool(re.findall(pattern, html, re.S)), re.findall(pattern, html, re.S)))
        scope = dict(json=json, movie_identity=movie_identity, cParser=parser, cRequestHandler=request,
                     cleantitle=types.SimpleNamespace(get=movie_identity.title_key),
                     getSetting=lambda key, default: default, urljoin=urljoin, quote_plus=quote_plus,
                     SITE_IDENTIFIER='einschalten', SITE_DOMAIN='einschalten.in',
                     isBlockedHoster=lambda url, **kwargs: (False, 'Fixture', url, 1),
                     log_utils=Mock(), xbmc=types.SimpleNamespace(LOGWARNING=2))
        tree=ast.parse((ROOT/path).read_text(encoding='utf8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='source')
        exec(compile(ast.Module(body=[cls],type_ignores=[]),path,'exec'),scope)
        return scope['source']()

    def test_alien_verified_with_observed_full_title_and_year(self):
        for path in PATHS:
            with self.subTest(path=path):
                scraper=self.scraper(path)
                rows=scraper.run(['Alien',ALIEN],1979,imdb='tt0078748')
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]['identity_status'],'verified')
                self.assertEqual(rows[0]['movie_identity']['title'],ALIEN)
                self.assertEqual(rows[0]['movie_identity']['year'],'1979')
                self.assertEqual(movie_identity.classify(['Alien',ALIEN],1979,'tt0078748',rows[0]['movie_identity']),'verified')

    def test_title_prefix_and_remake_year_do_not_pass(self):
        for path in PATHS:
            for search in (card('Alien - A Different Film',1979),card(ALIEN,2026)):
                scraper=self.scraper(path,search=search)
                self.assertEqual(scraper.run(['Alien',ALIEN],1979),[])
                self.assertFalse(any(url.endswith('/watch') for url in self.calls))

    def test_detail_year_or_imdb_conflict_is_rejected_before_stream_request(self):
        for path in PATHS:
            for detail in ('<h1>%s</h1><meta itemprop="datePublished" content="2026">'%ALIEN,
                           '<h1>%s</h1><script type="application/ld+json">%s</script>' % (ALIEN,json.dumps({'@type':'Movie','name':ALIEN,'datePublished':'1979','sameAs':'https://imdb.com/title/tt9999999/'}))):
                scraper=self.scraper(path,detail=detail)
                self.assertEqual(scraper.run([ALIEN],1979,imdb='tt0078748'),[])
                self.assertFalse(any(url.endswith('/watch') for url in self.calls))

    def test_detail_unavailable_uses_provider_card_not_requested_values(self):
        for path in PATHS:
            scraper=self.scraper(path,detail=TimeoutError('fixture'))
            rows=scraper.run(['Alien',ALIEN],1979)
            self.assertEqual(rows[0]['movie_identity'],{'title':ALIEN,'year':'1979','imdb':''})
            self.assertEqual(rows[0]['identity_status'],'verified')

    def test_conflicting_first_candidate_does_not_hide_second_matching_movie(self):
        for path in PATHS:
            scraper=self.scraper(path,search=card(slug='one')+card(slug='two'))
            request=scraper.run.__globals__['cRequestHandler']
            def by_url(url,**kwargs):
                if urlsplit(url).path=='/movie/one':
                    return types.SimpleNamespace(request=lambda:'<h1>Another Movie</h1>')
                return request(url,**kwargs)
            scraper.run.__globals__['cRequestHandler']=by_url
            self.assertEqual(len(scraper.run([ALIEN],1979)),1)
            self.assertFalse(any('/one/watch' in url for url in self.calls))
            self.assertTrue(any('/two/watch' in url for url in self.calls))

    def test_specials_are_not_classified_as_movies_and_runs_do_not_accumulate(self):
        for path in PATHS:
            scraper=self.scraper(path)
            self.assertEqual(len(scraper.run([ALIEN],1979)),1)
            self.assertEqual(len(scraper.run([ALIEN],1979)),1)
            scraper.mediatype='episode'
            self.calls.clear()
            self.assertEqual(scraper.run([ALIEN],1979,season=0,episode=1),[])
            self.assertFalse(any(urlsplit(url).path=='/movie/alien' for url in self.calls))

    def test_search_query_is_encoded(self):
        for path in PATHS:
            scraper=self.scraper(path,search='')
            scraper.run(['A & B + C'],1979)
            self.assertTrue(self.calls[0].endswith('query=A+%26+B+%2B+C'))


if __name__=='__main__': unittest.main()
