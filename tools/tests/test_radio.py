"""Strict Radio Browser identity, grouping, bounded API calls and native Kodi UI contracts."""
import copy
import importlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

import requests
from resources.lib import radio_browser as rb

ID = 'f3def834-4d96-11e9-a4d7-52543be04c81'
OTHER = 'f3def834-4d96-11e9-a4d7-52543be04c82'


def row(**values):
    result = dict(stationuuid=ID, name='Test Radio', countrycode='DE', has_extended_info=True,
                  lastcheckok=1, url_resolved='https://radio.example/live.mp3',
                  homepage='https://www.example.org/', favicon='', tags='dance,house,90s',
                  votes=12, codec='MP3', bitrate=128)
    result.update(values)
    return result


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError('test')

    def iter_content(self, size):
        yield json.dumps(self.payload).encode()


class CatalogTests(unittest.TestCase):
    def test_filter_requires_all_flags(self):
        self.assertTrue(rb.eligible(row()))
        for values in [dict(countrycode='AT'), dict(lastcheckok=0),
                       dict(url_resolved='file:///test'), dict(url_resolved='https://u:p@host/a')]:
            self.assertFalse(rb.eligible(row(**values)), values)

    def test_verified_metadata_is_not_required_anywhere(self):
        raw = row(has_extended_info=False)
        self.assertTrue(rb.eligible(raw))
        self.assertIsNotNone(rb.clean_station(raw))
        del raw['has_extended_info']
        self.assertEqual(len(rb.group_stations([raw])), 1)
        api, _ = self.api()
        with patch.object(api, 'get', return_value=[raw]) as get:
            self.assertEqual(len(api.catalog()), 1)
            self.assertNotIn('has_extended_info', get.call_args.args[1])
            self.assertEqual(api.station(ID)['id'], ID)

    def test_invalid_identity_rejected(self):
        self.assertIsNone(rb.clean_station(row(stationuuid='../vote')))
        with self.assertRaises(rb.RadioError):
            rb.station_id('bad')

    def test_genre_matches_whole_tags(self):
        self.assertNotIn('Rock & Alternative', rb.genres(row(tags='hardrock')))
        self.assertIn('House', rb.genres(row(tags='deep house')))

    def test_german_search_and_unknown_genre(self):
        self.assertEqual(rb.normalized('Ä Ö Ü ß'), 'a o u ss')
        self.assertEqual(rb.genres(row(tags='unknown')), ['Weitere Musikrichtungen'])

    def test_known_family_domain_and_name(self):
        self.assertEqual(rb.family(row(name='- 0 N - Dance', homepage='https://www.0nradio.com')), '0N Radio')
        self.assertEqual(rb.family(row(name='NDR 2', homepage='')), 'NDR')
        self.assertEqual(rb.family(row(name='SWRock im NDRaum', homepage='https://ndr.fake.de')), '')

    def test_grouping_variants_and_deduplication(self):
        programs = rb.group_stations([row(), row(), row(stationuuid=OTHER, codec='AAC', bitrate=64, votes=25)])
        self.assertEqual(len(programs), 1)
        self.assertEqual(len(programs[0]['variants']), 2)
        self.assertEqual(programs[0]['votes'], 25)  # Never sum unrelated vote totals.
        self.assertEqual(rb.stream_variants(programs[0])[0]['codec'], 'MP3')
        self.assertEqual(rb.stream_variants(programs[0], 'aac')[0]['codec'], 'AAC')

    def test_do_not_group_different_programs(self):
        programs = rb.group_stations([row(), row(stationuuid=OTHER, name='Other Radio', url_resolved='https://radio.example/other.mp3')])
        self.assertEqual(len(programs), 2)
        self.assertEqual(rb.program_key(rb.clean_station(row(homepage='https://www.world.org')))[1], 'world.org')

    def test_identical_stream_merges_aliases_and_keeps_all_ids(self):
        rows = [row(name='80s80s', homepage='https://80s80s.de', votes=100),
                row(stationuuid=OTHER, name='80s80s Radio', homepage='http://www.80s80s.de/streams', votes=20)]
        program, = rb.group_stations(rows)
        self.assertEqual(program['name'], '80s80s')
        self.assertEqual(program['votes'], 100)
        self.assertEqual({s['id'] for s in program['variants']}, {ID, OTHER})
        self.assertEqual(len(rb.filter_stations([program], query='80s80s Radio')), 1)
        self.assertEqual(len(rb.stream_variants(program)), 1)
        self.assertEqual(set(rb.stream_variants(program)[0]['api_aliases']), {ID, OTHER})

    def test_radio_word_alone_is_not_merge_evidence(self):
        rows = [row(name='80s80s', homepage='https://80s80s.de'),
                row(stationuuid=OTHER, name='80s80s Radio', homepage='https://80s80s.de',
                    url_resolved='https://radio.example/other.mp3')]
        self.assertEqual(len(rb.group_stations(rows)), 2)

    def test_named_subchannels_stay_separate_even_with_bad_shared_url(self):
        for names in [('80s80s Rock', '80s80s Dance'), ('80s80s NRW', '80s80s Bayern'),
                      ('80s80s', '80s80s Pop Stories'), ('NDR 1', 'NDR 2')]:
            rows = [row(name=names[0], homepage='https://example.org'), row(stationuuid=OTHER,
                    name=names[1], homepage='https://example.org')]
            self.assertEqual(len(rb.group_stations(rows)), 2, names)

    def test_unnamed_alias_cannot_bridge_conflicting_subchannels(self):
        rows = [row(name='80s80s Rock'), row(stationuuid=OTHER, name='Unknown'),
                row(stationuuid='f3def834-4d96-11e9-a4d7-52543be04c83', name='80s80s Dance')]
        programs = rb.group_stations(rows)
        self.assertEqual(len(programs), 2)
        self.assertTrue(all(not {'80s80s Rock', '80s80s Dance'}.issubset(s['aliases']) for s in programs))

    def test_quality_suffix_and_format_variants_are_preserved(self):
        rows = [row(name='Test MP3 128 kbps'), row(stationuuid=OTHER, name='Test AAC Low Quality',
                codec='AAC', bitrate=64, url_resolved='https://radio.example/low.aac')]
        program, = rb.group_stations(rows)
        self.assertEqual(len(rb.stream_variants(program)), 2)

    def test_missing_operator_does_not_merge_names_alone(self):
        rows = [row(homepage=''), row(stationuuid=OTHER, homepage='', url_resolved='https://other.example/live')]
        self.assertEqual(len(rb.group_stations(rows)), 2)

    def test_url_normalization_preserves_program_and_token_parameters(self):
        self.assertEqual(rb.stream_key('https://RADIO.example:443/live#player'), 'https://radio.example/live')
        self.assertNotEqual(rb.stream_key('https://radio.example/live?station=rock'),
                            rb.stream_key('https://radio.example/live?station=dance'))
        self.assertNotEqual(rb.stream_key('https://radio.example/Rock'), rb.stream_key('https://radio.example/rock'))

    def test_only_known_regiocast_analytics_are_ignored_for_identity(self):
        base = 'https://regiocast.streamabc.net/regc-radio-mp3-192-123'
        self.assertEqual(rb.endpoint_key(base + '?sABC=session&aw_0_1st.playerid=web&amsparams=playerid:123'), base)
        self.assertEqual(rb.endpoint_key(base + '?sABC=session&station=rock&token=secret'), base + '?station=rock&token=secret')
        other = 'https://other.example/live?sABC=one'
        self.assertEqual(rb.endpoint_key(other), other)
        gateway = 'https://regiocast.streamabc.net/?sABC=one'
        self.assertEqual(rb.endpoint_key(gateway), gateway)

    def identity_rows(self):
        return [row(name='80s80s', homepage='https://80s80s.de'),
                row(stationuuid=OTHER, name='80s80s Radio', homepage='https://80s80s.de',
                    url_resolved='https://radio.example/alias')]

    def test_cached_redirects_merge_and_expired_or_failed_results_do_not(self):
        now = time.time()
        rows = self.identity_rows()
        identities = {r['url_resolved']: dict(checked=now, ok=True, target='https://cdn.example/same.mp3') for r in rows}
        program, = rb.group_stations(rows, identities, now=now)
        self.assertEqual(len(program['variants']), 2)
        self.assertEqual(len(rb.group_stations(rows, identities, now=now + rb.IDENTITY_TTL + 1)), 2)
        for record in identities.values():
            record['ok'] = False
        self.assertEqual(len(rb.group_stations(rows, identities, now=now)), 2)

    def test_background_scan_is_limited_cached_and_never_votes(self):
        resolve = Mock(return_value='https://cdn.example/same.mp3')
        rows = self.identity_rows()
        records, changed = rb.refresh_identities(rows, {}, resolve=resolve, limit=1)
        self.assertTrue(changed)
        self.assertEqual(resolve.call_count, 1)
        records, _ = rb.refresh_identities(rows, records, resolve=resolve)
        self.assertEqual(resolve.call_count, 2)
        self.assertEqual(len(rb.group_stations(rows, records)), 1)
        self.assertEqual(rb.identity_candidates(rows, records), [])
        resolve.reset_mock()
        rb.refresh_identities(rows, records, resolve=resolve)
        resolve.assert_not_called()

    def test_background_failure_and_abort_do_not_poison_identity(self):
        resolve = Mock(side_effect=requests.Timeout())
        rows = self.identity_rows()
        records, changed = rb.refresh_identities(rows, {}, resolve=resolve, stopped=lambda: True)
        self.assertFalse(changed)
        resolve.assert_not_called()
        records, changed = rb.refresh_identities(rows, {}, resolve=resolve)
        self.assertEqual(len(rb.group_stations(rows, records)), 2)
        self.assertTrue(changed)
        self.assertEqual(rb.identity_candidates(rows, records), [])  # Six-hour failure backoff.

    def test_combined_filters_and_vote_sort(self):
        programs = rb.group_stations([row(name='- 0 N - Dance', homepage='https://0nradio.com'),
                        row(stationuuid=OTHER, name='- 1 A - Pop', homepage='https://1aradio.com', votes=30)])
        self.assertEqual(rb.filter_stations(programs)[0]['votes'], 30)
        self.assertEqual(len(rb.filter_stations(programs, genre='House', sender_family='0N Radio')), 1)
        self.assertEqual(len(rb.filter_stations(programs, query='1 a')), 1)

    def api(self):
        transport = Mock()
        api = rb.Client(transport=transport)
        api.discovered = True
        return api, transport

    def test_catalog_reapplies_filter_and_paginates(self):
        api, _ = self.api()
        with patch.object(rb, 'PAGE_SIZE', 2), patch.object(api, 'get', side_effect=[
                [row(has_extended_info=False), row(stationuuid=OTHER, lastcheckok=0)], []]) as get:
            self.assertEqual(len(api.catalog()), 1)
            self.assertEqual(get.call_args_list[1].args[1]['offset'], 2)

    def test_catalog_does_not_cache_incomplete_result(self):
        api, _ = self.api()
        with patch.object(rb, 'PAGE_SIZE', 1), patch.object(rb, 'MAX_PAGES', 1), patch.object(api, 'get', return_value=[row()]):
            with self.assertRaises(rb.RadioError):
                api.catalog()

    def test_catalog_cancellation(self):
        api, _ = self.api()
        with self.assertRaises(rb.Cancelled):
            api.catalog(cancelled=lambda: True)

    def test_station_does_not_substitute_other_uuid_or_broken(self):
        api, _ = self.api()
        for rows in ([row(stationuuid=OTHER)], [row(lastcheckok=0)]):
            with patch.object(api, 'get', return_value=rows), self.assertRaises(rb.RadioError):
                api.station(ID)

    def test_failed_read_tries_another_server(self):
        api, _ = self.api()
        with patch.object(api, '_json', side_effect=[requests.Timeout(), [row()]]) as call:
            self.assertEqual(api.station(ID)['id'], ID)
            self.assertEqual(call.call_count, 2)

    def test_vote_write_is_never_retried(self):
        api, _ = self.api()
        with patch.object(api, '_json', side_effect=requests.Timeout()) as call:
            with self.assertRaises(rb.RadioError):
                api.vote(ID)
            self.assertEqual(call.call_count, 1)
            self.assertEqual(call.call_args.kwargs['method'], 'POST')

    def test_vote_rejection_and_success_remain_distinct(self):
        api, _ = self.api()
        for ok in (True, False):
            with patch.object(api, '_json', return_value={'ok': ok}):
                self.assertIs(api.vote(ID)['ok'], ok)

    def test_invalid_vote_response(self):
        api, _ = self.api()
        with patch.object(api, '_json', return_value={'ok': 'false'}), self.assertRaises(rb.RadioError):
            api.vote(ID)

    def test_transport_is_bounded_and_does_not_follow_redirects(self):
        api, transport = self.api()
        transport.request.return_value = Response([row()])
        self.assertEqual(api._json(rb.SERVERS[0], '/json/stations/search')[0]['stationuuid'], ID)
        options = transport.request.call_args.kwargs
        self.assertFalse(options['allow_redirects'])
        self.assertEqual(options['timeout'], (3, 8))
        with self.assertRaises(rb.RadioError):
            api._json('attacker.invalid', '/json/vote/' + ID)
        with patch.object(rb, 'MAX_RESPONSE', 1), self.assertRaises(rb.RadioError):
            api._json(rb.SERVERS[0], '/json/stations/search')
        transport.request.return_value = Response({}, status=302)
        with self.assertRaises(rb.RadioError):
            api._json(rb.SERVERS[0], '/')

    def test_discovery_rejects_foreign_hosts(self):
        api, _ = self.api()
        api.discovered = False
        with patch.object(api, '_json', return_value=[{'name': 'attacker.com'}, {'name': 'de2.api.radio-browser.info'}]):
            api.discover()
        self.assertIn('de2.api.radio-browser.info', api.servers)
        self.assertNotIn('attacker.com', api.servers)


class RedirectHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ('/main', '/radio'):
                    self.send_response(302)
                    self.send_header('Location', '/audio')
                    self.end_headers()
                elif self.path == '/loop':
                    self.send_response(302)
                    self.send_header('Location', '/loop')
                    self.end_headers()
                else:
                    html = self.path == '/html'
                    body = b'<html>Not a stream</html>' if html else b'\xff\xfb' + b'0' * 1022
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream' if html else 'audio/mpeg')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:%d' % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)

    def test_real_redirects_become_one_program_after_background_scan(self):
        rows = [row(name='80s80s', homepage='https://80s80s.de', url_resolved=self.base + '/main'),
                row(stationuuid=OTHER, name='80s80s Radio', homepage='https://80s80s.de',
                    url_resolved=self.base + '/radio')]
        self.assertEqual(len(rb.group_stations(rows)), 2)
        records, changed = rb.refresh_identities(rows, {})
        self.assertTrue(changed)
        program, = rb.group_stations(rows, records)
        self.assertEqual(len(program['variants']), 2)
        self.assertEqual(len(rb.stream_variants(program)), 1)

    def test_html_and_redirect_loops_are_not_accepted_as_identity_evidence(self):
        with self.assertRaises(rb.RadioError):
            rb.probe_stream_url(self.base + '/html')
        with self.assertRaises(requests.TooManyRedirects):
            rb.probe_stream_url(self.base + '/loop')


class KodiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.props, self.settings, self.favs = {}, {}, {}
        self.native = Mock()
        self.native.getAddonInfo.side_effect = lambda key: self.tmp.name if key == 'profile' else 'test'
        self.native.getSetting.side_effect = lambda key: self.settings.get(key, '')
        self.native.setSetting.side_effect = self.settings.__setitem__
        self.window = types.SimpleNamespace(getProperty=lambda k: self.props.get(k, ''), setProperty=self.props.__setitem__)
        self.xbmc, self.gui, self.plugin = Mock(), Mock(), Mock()
        self.gui.Window.return_value = self.window
        self.gui.DialogProgress.return_value.iscanceled.return_value = False
        self.xbmc.Monitor.return_value.abortRequested.return_value = False
        self.vfs = types.SimpleNamespace(translatePath=lambda p: p, mkdirs=lambda p: None,
                                        File=lambda p, mode='r': open(p, mode, encoding='utf8'))
        self.modules = patch.dict(sys.modules, {'xbmc': self.xbmc, 'xbmcgui': self.gui,
            'xbmcplugin': self.plugin, 'xbmcvfs': self.vfs,
            'xbmcaddon': types.SimpleNamespace(Addon=lambda *a: self.native)})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        sys.modules.pop('resources.lib.radio', None)
        self.radio = importlib.import_module('resources.lib.radio')
        self.addCleanup(lambda: sys.modules.pop('resources.lib.radio', None))
        self.argv = patch.object(sys, 'argv', ['plugin://plugin.video.xvault/', '42', ''])
        self.argv.start()
        self.addCleanup(self.argv.stop)

    def test_native_favourite_identity_does_not_accept_other_plugins(self):
        f = dict(type='media', path=self.radio.url('radioPlay', id=ID))
        self.assertEqual(self.radio.favorite_id(f), ID)
        self.assertEqual(self.radio.favorite_id(dict(f, path=f['path'].replace('xvault', 'other'))), '')

    def test_old_variant_favourite_matches_program(self):
        programs = rb.group_stations([row(), row(stationuuid=OTHER, votes=50)])
        self.assertEqual(self.radio.find(ID, programs)['id'], OTHER)

    def test_native_favorite_and_recent_ids_survive_alias_merge(self):
        programs = rb.group_stations([row(), row(stationuuid=OTHER, name='Test Radio Alias', votes=50)])
        self.assertEqual(self.radio.find(ID, programs)['id'], OTHER)
        self.assertEqual(self.radio.find(OTHER, programs)['id'], OTHER)
        self.radio.remember('radio.history', ID)
        with patch.object(self.radio, 'catalog', return_value=programs), \
                patch.object(self.radio, 'favorites', return_value={ID: {}}):
            self.radio.show_list({}, mode='favorites')
            self.assertEqual(len(self.plugin.addDirectoryItems.call_args.args[1]), 1)
            self.radio.show_list({}, mode='recent')
            self.assertEqual(len(self.plugin.addDirectoryItems.call_args.args[1]), 1)

    def test_foreground_grouping_does_not_probe_any_stream(self):
        with patch.object(rb, 'probe_stream_url', side_effect=AssertionError('foreground HTTP')):
            programs = self.radio.group_catalog([row()])
        self.assertEqual(len(programs), 1)
        self.assertEqual(self.props[self.radio.IDENTITY_REQUEST], '1')

    def test_identity_file_roundtrip_expiry_and_corruption(self):
        records = {'https://radio.example/live': dict(target='https://cdn.example/live', checked=time.time(), ok=True)}
        self.radio.write_identities(records)
        self.assertEqual(self.radio.read_identities(), records)
        records['https://radio.example/live']['checked'] -= rb.IDENTITY_TTL + 1
        self.radio.write_identities(records)
        self.assertEqual(self.radio.read_identities(), {})
        Path(self.radio.identity_path()).write_text('{broken', encoding='utf8')
        self.assertEqual(self.radio.read_identities(), {})

    def test_home_has_no_network_work(self):
        with patch.object(self.radio, 'client', side_effect=AssertionError('network')):
            self.radio.home()
        self.plugin.endOfDirectory.assert_called_once()

    def test_music_metadata_keeps_votes_visible_but_playback_title_clean(self):
        station = rb.clean_station(row())
        self.radio.music_item(station, label='Test Radio · 12 Votes')
        info = self.gui.ListItem.return_value.getMusicInfoTag.return_value
        info.setTitle.assert_called_with('Test Radio · 12 Votes')
        self.radio.music_item(station, path=station['url'])
        info.setTitle.assert_called_with('Test Radio')

    def test_station_list_uses_native_bulk_directory_api(self):
        programs = rb.group_stations([row(), row(stationuuid=OTHER, name='Other Radio', url_resolved='https://radio.example/other.mp3')])
        with patch.object(self.radio, 'catalog', return_value=programs), patch.object(self.radio, 'favorites', return_value={}):
            self.radio.show_list({})
        self.plugin.addDirectoryItems.assert_called_once()
        self.assertEqual(len(self.plugin.addDirectoryItems.call_args.args[1]), 2)
        self.plugin.addDirectoryItem.assert_not_called()

    def test_cache_revalidates_filter_and_expiry(self):
        self.radio.write_cache([row(), row(stationuuid=OTHER, countrycode='AT')])
        self.assertEqual(len(self.radio.read_cache()['rows']), 1)
        data = json.loads(self.props[self.radio.CACHE_PROPERTY])
        data['timestamp'] -= rb.STALE_TTL + 1
        self.props[self.radio.CACHE_PROPERTY] = json.dumps(data)
        self.assertIsNone(self.radio.read_cache())

    def test_old_verified_only_cache_is_invalidated(self):
        self.radio.write_cache([row(has_extended_info=False)])
        self.assertEqual(len(self.radio.read_cache()['rows']), 1)
        data = json.loads(self.props[self.radio.CACHE_PROPERTY])
        data['schema'] = 1
        self.props[self.radio.CACHE_PROPERTY] = json.dumps(data)
        self.assertIsNone(self.radio.read_cache())

    def test_fresh_cache_skips_api(self):
        self.radio.write_cache([row()])
        with patch.object(self.radio, 'client', side_effect=AssertionError('network')):
            self.assertEqual(len(self.radio.catalog()), 1)

    def test_stale_cache_fallback_is_not_silent(self):
        self.radio.write_cache([row()])
        data = json.loads(self.props[self.radio.CACHE_PROPERTY])
        data['timestamp'] -= rb.CATALOG_TTL + 1
        self.props[self.radio.CACHE_PROPERTY] = json.dumps(data)
        api = Mock()
        api.catalog.side_effect = rb.RadioError('offline')
        with patch.object(self.radio, 'client', return_value=api):
            self.assertEqual(len(self.radio.catalog()), 1)
        self.gui.Dialog.return_value.notification.assert_called_once()

    def test_vote_cancelled_does_not_write(self):
        api = Mock()
        api.station.return_value = rb.clean_station(row())
        self.gui.Dialog.return_value.yesno.return_value = False
        with patch.object(self.radio, 'client', return_value=api):
            self.radio.vote(ID)
        api.vote.assert_not_called()

    def test_vote_confirmed_remembered_but_rejected_not_remembered(self):
        api = Mock()
        api.station.return_value = rb.clean_station(row())
        self.gui.Dialog.return_value.yesno.return_value = True
        for ok in (False, True):
            api.vote.return_value = {'ok': ok}
            with patch.object(self.radio, 'client', return_value=api):
                self.radio.vote(ID)
            self.assertEqual(ID in self.radio.stored('radio.votes'), ok)
        api.vote.reset_mock()
        with patch.object(self.radio, 'client', return_value=api):
            self.radio.vote(ID)
        api.vote.assert_not_called()

    def test_favorite_uses_native_rpc_and_stable_uuid(self):
        with patch.object(self.radio, 'catalog', return_value=rb.group_stations([row()])), \
                patch.object(self.radio, 'favorites', return_value={}), patch.object(self.radio, 'rpc') as rpc:
            self.radio.toggle_favorite(ID)
        self.assertEqual(rpc.call_args.args[0], 'Favourites.AddFavourite')
        self.assertEqual(rpc.call_args.args[1]['type'], 'media')
        self.assertEqual(rpc.call_args.args[1]['path'], self.radio.url('radioPlay', id=ID))

    def test_native_audio_fallback_and_failed_resolution(self):
        programs = rb.group_stations([row(), row(stationuuid=OTHER, codec='AAC', url_resolved='https://radio.example/live.aac')])
        api = Mock()
        api.station.side_effect = [rb.RadioError('first failed'), rb.clean_station(row(stationuuid=OTHER, codec='AAC', url_resolved='https://radio.example/live.aac'))]
        with patch.object(self.radio, 'catalog', return_value=programs), patch.object(self.radio, 'client', return_value=api), \
                patch.object(self.radio, 'probe_stream', return_value='https://stream.example/audio.aac'), \
                patch.object(self.radio.threading, 'Thread'):
            self.radio.play(ID)
        self.assertTrue(self.plugin.setResolvedUrl.call_args.args[1])
        self.assertIn(ID, self.radio.stored('radio.history'))
        self.plugin.reset_mock()
        with patch.object(self.radio, 'catalog', return_value=[]), self.assertRaises(rb.RadioError):
            self.radio.play(ID)
        self.assertFalse(self.plugin.setResolvedUrl.call_args.args[1])

    def test_retired_api_id_falls_back_to_alias_without_probing_same_stream_twice(self):
        programs = rb.group_stations([row(), row(stationuuid=OTHER, name='Alias')])
        api = Mock()
        api.station.side_effect = [rb.RadioError('retired id'), rb.clean_station(row(stationuuid=OTHER))]
        with patch.object(self.radio, 'catalog', return_value=programs), patch.object(self.radio, 'client', return_value=api), \
                patch.object(self.radio, 'probe_stream', return_value='https://radio.example/live.mp3') as probe, \
                patch.object(self.radio.threading, 'Thread'):
            self.radio.play(ID)
        self.assertTrue(self.plugin.setResolvedUrl.call_args.args[1])
        self.assertEqual(api.station.call_count, 2)
        probe.assert_called_once()


if __name__ == '__main__':
    unittest.main()
