"""Regression cases for episode identity and unnamed hosters on SerienStream."""
import ast
import datetime
import html
from html.parser import HTMLParser
from pathlib import Path
import re
import types
import unittest
from urllib.parse import urljoin, urlparse


ROOT = Path(__file__).resolve().parents[2]


def load_scraper():
    # Load the real scraper definitions while keeping Kodi/network imports out
    # of this deterministic fixture test.
    tree = ast.parse((ROOT / 'sites/serienstream.py').read_text(encoding='utf-8-sig'))
    definitions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    clean_scope = {'re': re, 'html': HTMLParser(), 'unescape': html.unescape,
                   'py2_encode': lambda value: value}
    clean_tree = ast.parse((ROOT / 'scrapers/modules/cleantitle.py').read_text(encoding='utf-8-sig'))
    clean_definitions = [n for n in clean_tree.body if isinstance(n, ast.FunctionDef)]
    exec(compile(ast.Module(body=clean_definitions, type_ignores=[]), 'cleantitle.py', 'exec'), clean_scope)
    namespace = {'re': re, 'datetime': datetime, 'urljoin': urljoin, 'urlparse': urlparse,
                 'html_unescape': html.unescape, 'cleantitle': types.SimpleNamespace(**clean_scope),
                 'SITE_DOMAIN': 'serienstream.to', 'SITE_IDENTIFIER': 'serienstream',
                 'LEGACY_DOMAINS': set(), 'log_utils': False,
                 'getSetting': lambda name, default='': default}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), 'serienstream.py', 'exec'), namespace)
    return namespace['source']


SOURCE = load_scraper()


def page(title, language='2', published='April 21, 2026', provider='VOE', season=8, episode=18):
    return ('<h2>S%02dE%02d: %s</h2><span>Veröffentlicht am %s</span>'
            '<button data-link-id="123" data-play-url="/r?t=fixture" '
            'data-provider-name="%s" data-language-id="%s"></button>') % (
                season, episode, title, published, provider, language)


class SerienStreamEpisodeTests(unittest.TestCase):
    def scraper(self, pages):
        scraper = SOURCE()
        scraper._request_page = lambda url: pages.get(url, '')
        scraper._available_seasons = lambda *args: [8]
        return scraper

    def test_generic_provider_is_not_a_playable_hoster(self):
        for provider in ['Provider', 'PROVIDER', ' provider ']:
            with self.subTest(provider=provider):
                scraper = self.scraper({})
                scraper._request_page = lambda url: page('Test', provider=provider)
                scraper.run2('/serie/test', 2022, season=8, episode=18)
                self.assertEqual(scraper.sources, [])

    def test_real_hosters_and_their_languages_are_preserved(self):
        scraper = self.scraper({})
        scraper._request_page = lambda url: page('Test', '1') + page('Test', '2', provider='Doodstream')
        scraper.run2('/serie/test', 2022, season=8, episode=18)
        self.assertEqual([(x['source'], x['language']) for x in scraper.sources],
                         [('VOE', 'de'), ('Doodstream', 'en')])

    def test_fbi_18_keeps_english_instead_of_german_episode_5(self):
        base = 'https://serienstream.to/serie/fbi'
        direct = base + '/staffel-8/episode-18'
        wrong = base + '/staffel-8/episode-5'
        scraper = self.scraper({direct: page('(Behavior)'),
                                wrong: page('Unantastbar (Falsetto)', '1', 'April 22, 2026', episode=5),
                                base + '/staffel-8': '<a href="/serie/fbi/staffel-8/episode-5">5</a>'})
        scraper.episode_title = 'Nachahmungstäter'
        scraper.episode_premiered = '2026-04-20'
        scraper.run2('/serie/fbi', 2018, season=8, episode=18)
        self.assertEqual([x['language'] for x in scraper.sources], ['en'])
        self.assertEqual(scraper.episode_referer, direct)

    def test_upload_date_alone_never_maps_to_another_episode(self):
        base = 'https://serienstream.to/serie/fbi'
        scraper = self.scraper({base + '/staffel-8': '<a href="/serie/fbi/staffel-8/episode-5">5</a>',
                                base + '/staffel-8/episode-5': page('Unantastbar (Falsetto)', '1', 'April 22, 2026')})
        for title in [None, 'Nachahmungstäter']:
            self.assertIsNone(scraper._find_matching_episode_page('/serie/fbi', 8, 18, title, '2026-04-20'))

    def test_upload_date_is_not_a_reason_to_remap_a_direct_page(self):
        scraper = self.scraper({})
        scraper.episode_premiered = '2025-11-10'
        self.assertFalse(scraper._should_find_matching_episode(page('Unantastbar', '1', 'April 22, 2026'), 8))

    def test_overlapping_words_do_not_identify_an_episode(self):
        self.assertFalse(SOURCE()._episode_titles_match('A Very Good Man', 'A Very Good Woman'))

    def test_parenthesized_original_title_and_chapter_mapping_still_work(self):
        scraper = SOURCE()
        self.assertTrue(scraper._episode_titles_match('Behavior', 'Nachahmungstäter (Behavior)'))
        self.assertTrue(scraper._episode_titles_match('Virus', 'Virus'))
        self.assertTrue(scraper._episode_titles_match('Chapter Twelve: The Epiphany',
                                                    'Kapitel zwölf: Die Offenbarung'))

    def test_unique_title_can_still_recover_a_different_episode_number(self):
        base = 'https://serienstream.to/serie/test'
        target = base + '/staffel-8/episode-5'
        scraper = self.scraper({base + '/staffel-8': '<a href="/serie/test/staffel-8/episode-5">5</a>',
                                target: page('Nachahmungstäter (Behavior)', '1')})
        mapped = scraper._find_matching_episode_page('/serie/test', 8, 18, 'Behavior', '2026-04-20')
        self.assertEqual(mapped[0], target)

    def test_duplicate_titles_do_not_pick_the_first_episode(self):
        base = 'https://serienstream.to/serie/test'
        scraper = self.scraper({base + '/staffel-8': '<a href="/serie/test/staffel-8/episode-5">5</a>'
                                                   '<a href="/serie/test/staffel-8/episode-6">6</a>',
                                base + '/staffel-8/episode-5': page('Pilot'),
                                base + '/staffel-8/episode-6': page('Pilot')})
        self.assertIsNone(scraper._find_matching_episode_page('/serie/test', 8, 18, 'Pilot'))

    def test_wrong_numbered_direct_page_is_rejected_without_metadata(self):
        scraper = self.scraper({})
        scraper._request_page = lambda url: page('Unantastbar', '1', episode=5)
        scraper.run2('/serie/fbi', 2018, season=8, episode=18)
        self.assertEqual(scraper.sources, [])

    def test_original_language_title_does_not_hide_wrong_episode_number(self):
        scraper = self.scraper({})
        scraper.episode_title = 'Nachahmungstäter'
        self.assertTrue(scraper._should_find_matching_episode(page('(Falsetto)', episode=5), 8, 18))


if __name__ == '__main__':
    unittest.main()
