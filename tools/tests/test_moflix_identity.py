"""Prevent same-name MoFlix films from replacing a different IMDb/year."""
import ast
import html
from html.parser import HTMLParser
from pathlib import Path
import re
import types
import unittest
from urllib.parse import quote, quote_plus, urlencode, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[2]
clean_scope = {'re': re, 'html': HTMLParser(), 'unescape': html.unescape, 'py2_encode': lambda s: s}
clean_tree = ast.parse((ROOT / 'scrapers/modules/cleantitle.py').read_text(encoding='utf-8-sig'))
exec(compile(ast.Module(body=[n for n in clean_tree.body if isinstance(n, ast.FunctionDef)], type_ignores=[]), 'cleantitle.py', 'exec'), clean_scope)
tree = ast.parse((ROOT / 'sites/moflix.py').read_text(encoding='utf-8'))
scope = dict(getSetting=lambda key, default='': default, setSetting=lambda *a: None,
             html_unescape=html.unescape, cleantitle=types.SimpleNamespace(**clean_scope),
             quote=quote, quote_plus=quote_plus, urlencode=urlencode, urljoin=urljoin, urlparse=urlparse,
             logger=types.SimpleNamespace(**{k: lambda *a: None for k in ('info', 'error', 'warning')}))
definitions = [n for n in tree.body if isinstance(n, (ast.Import, ast.Assign, ast.ClassDef))]
exec(compile(ast.Module(body=definitions, type_ignores=[]), 'moflix.py', 'exec'), scope)
SOURCE = scope['source']


class MoflixIdentityTests(unittest.TestCase):
    def item(self, year=2026, imdb='tt34385135', **kw):
        return dict(name='Colony', original_title='The Colony', year=year, imdb_id=imdb, **kw)

    def test_different_known_imdb_is_rejected_even_with_same_title_and_year(self):
        self.assertEqual(SOURCE()._match_score(self.item(imdb='tt1160996'), ['Colony'], 2026, 0, 'tt34385135'), 0)

    def test_old_remake_without_imdb_is_rejected_by_year(self):
        for year in (2013, 2021):
            self.assertEqual(SOURCE()._match_score(self.item(year=year, imdb=''), ['Colony', 'The Colony'], 2026, 0, 'tt34385135'), 0)

    def test_exact_imdb_is_authoritative_over_catalog_year_or_translated_title(self):
        self.assertGreater(SOURCE()._match_score(self.item(year=2024), ['Gunche'], 2026, 0, 'tt34385135'), 0)

    def test_correct_title_year_without_imdb_still_matches(self):
        self.assertGreater(SOURCE()._match_score(self.item(imdb=''), ['Colony'], 2026, 0, 'tt34385135'), 0)

    def test_one_year_release_difference_without_imdb_remains_supported(self):
        self.assertGreater(SOURCE()._match_score(self.item(year=2025, imdb=''), ['Colony'], 2026, 0, 'tt34385135'), 0)

    def test_best_match_never_falls_back_to_2013_when_2026_is_missing(self):
        scraper = SOURCE()
        scraper._json = lambda *a: {'results': [self.item(year=2013, imdb='tt1160996', id=1)]}
        self.assertIsNone(scraper._best_match(['Colony', 'The Colony'], 2026, 0, 'tt34385135'))

    def test_same_name_candidates_choose_correct_film_independent_of_order(self):
        for reverse in (False, True):
            candidates = [self.item(year=2013, imdb='tt1160996', id=1), self.item(id=2)]
            if reverse:
                candidates.reverse()
            scraper = SOURCE()
            scraper._json = lambda *a: {'results': candidates}
            self.assertEqual(scraper._best_match(['Colony'], 2026, 0, 'tt34385135')['id'], 2)

    def test_movie_and_series_are_not_interchangeable(self):
        self.assertEqual(SOURCE()._match_score(self.item(is_series=True), ['Colony'], 2026, 0, 'tt34385135'), 0)


if __name__ == '__main__':
    unittest.main()
