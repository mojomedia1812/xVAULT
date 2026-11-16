"""Recovery keeps one source/session, and never restarts a deliberate stop."""
import ast
from pathlib import Path
import threading
import time
import types
import sys
import unittest
from unittest.mock import Mock

from resources.lib.playback_recovery import RecoveryState

ROOT = Path(__file__).resolve().parents[2]


class RecoveryTests(unittest.TestCase):
    def player(self, refresh=None):
        tree = ast.parse((ROOT / 'resources/lib/player.py').read_text(encoding='utf8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'player')
        cls.bases = []
        names = ('_requestRecovery', '_tryRecovery', '_ownsRecoveryPlayback',
                 '_hasPlaybackOwnership', '_acceptPlaybackCallback', '_retirePlayback',
                 'onPlayBackStopped', 'onPlayBackEnded', 'onPlayBackError')
        cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
        control = Mock()
        control.progressDialog.iscanceled.return_value = False
        props = {'qa.owner': 'session-a'}
        control.window.getProperty.side_effect = lambda k: props.get(k, '')
        scope = dict(control=control, threading=threading, time=time, log_utils=Mock(), PLAYBACK_START_TIMEOUT=.05,
                     PLAYBACK_OWNER='qa.owner')
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'player.py', 'exec'), scope)
        p = scope['player']()
        p._recovery = RecoveryState()
        p._playback_token = 'session-a'
        p.streamFinished = False
        p._recovery.observe(30, 120)
        p._refresh_source = refresh or Mock(return_value='https://new.invalid/token2.mp4')
        p._recovering = False
        p._recovery_internal_stop = False
        p._recovery_open_requested = False
        p._recovery_open_failed = False
        p._user_stopped = False
        p._recovery_pending = 'error'
        p.mediatype = 'episode'
        p.playback_started = True
        p.playback_failed = False
        p.isdebug = False
        p.currentTime, p.totalTime = 30, 120
        p._active_stream_url = 'https://old.invalid/token1.mp4'
        p._owned_playing_file = p._active_stream_url
        p._finishPlayback = Mock()
        p._telemetryEvent = Mock()
        p._closePlaybackBusyDialogs = Mock()
        p._syncCheckpoint = Mock()
        p._stopFailedPlayback = Mock()
        self.playing = False
        p.isPlaying = lambda: self.playing
        p.isPlayingVideo = lambda: self.playing
        p.getPlayingFile = lambda: p._active_stream_url
        p.getTime = lambda: 30.5
        def opened(url, initial):
            p._active_stream_url = url
            p._recovery_av_started = True
            self.playing = True
        p._openStream = Mock(side_effect=opened)
        p.stop = Mock(side_effect=lambda: setattr(self, 'playing', False))
        self.control = control
        self.monitor = types.SimpleNamespace(abortRequested=lambda: False, waitForAbort=lambda _: time.sleep(.001))
        return p

    def test_policy_rejects_stop_live_unknown_duration_and_normal_end(self):
        s = RecoveryState()
        s.observe(30, 120)
        for reason in ('error', 'stall', 'eof'):
            self.assertTrue(s.interrupted(reason, 'movie'))
            self.assertFalse(s.interrupted(reason, 'movie', user_stopped=True))
            self.assertFalse(s.interrupted(reason, 'live'))
        s.observe(115, 120)
        self.assertFalse(s.interrupted('eof', 'episode'))
        s = RecoveryState()
        s.observe(30, 0)
        self.assertFalse(s.interrupted('error', 'movie'))

    def test_error_and_premature_eof_defer_finalization_and_watched_state(self):
        for callback in ('onPlayBackError', 'onPlayBackEnded'):
            p = self.player()
            getattr(p, callback)()
            p._finishPlayback.assert_not_called()
            self.assertIn(p._recovery_pending, ('error', 'eof'))

    def test_user_stop_cancels_pending_recovery(self):
        p = self.player()
        p.onPlayBackStopped()
        self.assertTrue(p._user_stopped)
        self.assertIsNone(p._recovery_pending)
        p._finishPlayback.assert_called_once_with(True, playback_ended=False)
        self.assertFalse(p._requestRecovery('error'))

    def test_setting_can_disable_recovery(self):
        p = self.player()
        self.control.getSetting.return_value = 'false'
        self.assertFalse(p._requestRecovery('error'))

    def test_source_refresh_uses_original_link_and_never_sets_shared_url(self):
        tree = ast.parse((ROOT / 'resources/lib/sources.py').read_text(encoding='utf8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'sources')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_recoveryResolver')
        scope = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'sources.py', 'exec'), scope)
        resolver = types.SimpleNamespace(sourcesResolve=Mock(return_value='fresh'))
        item = {'url': 'https://original.invalid/redirect', 'provider': 'series', 'language': 'de'}
        callback = scope['_recoveryResolver'](resolver, item)
        item['url'] = 'https://cached.invalid/old-token'
        self.assertEqual(callback(), 'fresh')
        self.assertEqual(resolver.sourcesResolve.call_args.args,
                         ({'url': 'https://original.invalid/redirect', 'provider': 'series', 'language': 'de'}, False, True, False))

    def test_replacement_uses_native_start_offset_with_positive_plugin_handle(self):
        tree = ast.parse((ROOT / 'resources/lib/player.py').read_text(encoding='utf8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'player')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_openStream')
        control, xbmc, plugin = Mock(), Mock(), Mock()
        xbmc.getInfoLabel.return_value = '21.3'
        scope = dict(control=control, xbmc=xbmc, xbmcplugin=plugin, sys=types.SimpleNamespace(argv=['plugin://qa', '12']), re=__import__('re'))
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'player.py', 'exec'), scope)
        p = types.SimpleNamespace(meta={}, _stream_info={}, playback_name='QA', offset='326.5', _recovering=True)
        p._playback_token = 'session-a'
        p._hasPlaybackOwnership = lambda: True
        scope['_openStream'](p, 'https://fresh.invalid/video.mp4', initial=False)
        control.item.return_value.setProperty.assert_any_call('StartOffset', '326.5')
        xbmc.Player.return_value.play.assert_called_once()
        plugin.setResolvedUrl.assert_not_called()

    def test_fresh_url_keeps_position_and_uses_direct_player_not_plugin_handle(self):
        p = self.player()
        self.assertTrue(p._tryRecovery(self.monitor))
        p._refresh_source.assert_called_once()
        p._openStream.assert_called_once_with('https://new.invalid/token2.mp4', initial=False)
        self.assertEqual(p.offset, '30.0')
        self.assertAlmostEqual(p.currentTime, 30.5)
        p._stopFailedPlayback.assert_not_called()

    def test_retry_budget_applies_to_whole_session(self):
        p = self.player(Mock(return_value=None))
        self.assertFalse(p._tryRecovery(self.monitor))
        self.assertEqual(p._refresh_source.call_count, 2)
        self.assertFalse(p._tryRecovery(self.monitor))
        self.assertEqual(p._refresh_source.call_count, 2)
        p._openStream.assert_not_called()

    def test_cancel_or_new_playback_during_resolution_never_opens_old_stream(self):
        for switch in (False, True):
            p = self.player()
            def refresh():
                if switch:
                    self.playing = True
                    p.getPlayingFile = lambda: 'https://other.invalid/user-selected.mp4'
                else:
                    self.control.progressDialog.iscanceled.return_value = True
                return 'https://new.invalid/token2.mp4'
            p._refresh_source = refresh
            self.assertFalse(p._tryRecovery(self.monitor))
            p._openStream.assert_not_called()
            if switch:
                p._stopFailedPlayback.assert_not_called()

    def test_timed_out_late_resolver_can_never_start_playback(self):
        p = self.player(lambda: (time.sleep(.08) or 'https://late.invalid/token.mp4'))
        p._recovery.RESOLVE_TIMEOUT = .01
        self.assertFalse(p._tryRecovery(self.monitor))
        time.sleep(.1)
        p._openStream.assert_not_called()

    def test_unseekable_replacement_is_stopped_instead_of_starting_at_zero(self):
        p = self.player()
        p.getTime = lambda: 0
        self.assertFalse(p._tryRecovery(self.monitor))
        p._stopFailedPlayback.assert_called_once()


if __name__ == '__main__':
    unittest.main()
