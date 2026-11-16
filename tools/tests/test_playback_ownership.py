"""Two concurrent Kodi player instances may never control each other's video."""
import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock
import uuid

ROOT=Path(__file__).resolve().parents[2]


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.props={}
        self.control=Mock()
        self.control.window.getProperty.side_effect=lambda key:self.props.get(key,'')
        self.control.window.setProperty.side_effect=self.props.__setitem__
        self.control.getSetting.return_value='false'
        names=('_claimPlaybackOwnership','_hasPlaybackOwnership','_retirePlayback','_acceptPlaybackCallback',
               '_ownsRecoveryPlayback','onAVStarted','onPlayBackStopped','onPlayBackEnded','onPlayBackError',
               '_requestRecovery','_stopFailedPlayback','_safePlayerTime','_safePlayerTotal','_runDeferredNavigationRestore')
        tree=ast.parse((ROOT/'resources/lib/player.py').read_text(encoding='utf8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='player')
        cls.bases=[];cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
        scope=dict(control=self.control,log_utils=Mock(),uuid=uuid,PLAYBACK_OWNER='owner',PLAYBACK_INTENT='intent')
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'player.py','exec'),scope)
        self.cls=scope['player']

    def player(self,token,url):
        p=self.cls()
        p._intent_token=token;p._playback_token=None;p._superseded=False
        p.streamFinished=False;p.playback_started=True;p.playback_failed=False
        p._recovering=False;p._recovery_internal_stop=False;p._recovery_pending='error'
        p._user_stopped=False;p._resume_via_item=False;p.isdebug=False
        p.currentTime=600;p.totalTime=1200;p.offset='600'
        p._active_stream_url=p._owned_playing_file=url
        p.isPlaying=Mock(return_value=True);p.getPlayingFile=Mock(return_value=url)
        p.getTime=Mock(return_value=10);p.getTotalTime=Mock(return_value=1800)
        p.seekTime=Mock();p.stop=Mock();p._telemetryEvent=Mock()
        p._finishPlayback=Mock();p.parentDir=Mock();p.restore_navigation_pending=True
        p.restore_position_pending=True;p._waitForContainerNavigationIdle=Mock(return_value=True)
        self.props['intent']=token
        self.assertTrue(p._claimPlaybackOwnership())
        return p

    def test_old_av_callback_cannot_seek_or_adopt_new_video(self):
        a=self.player('A','https://fixture/A.mp4')
        self.player('B','https://fixture/B.mp4')
        a.getPlayingFile.return_value='https://fixture/B.mp4'
        a.onAVStarted()
        a.seekTime.assert_not_called()
        self.assertEqual(a._owned_playing_file,'https://fixture/A.mp4')
        self.assertTrue(a.streamFinished)
        a._finishPlayback.assert_called_once_with(False,playback_ended=False)

    def test_late_old_stop_eof_and_error_never_recover_or_restore_navigation(self):
        for callback in ('onPlayBackStopped','onPlayBackEnded','onPlayBackError'):
            a=self.player('A','https://fixture/A.mp4')
            self.player('B','https://fixture/B.mp4')
            getattr(a,callback)()
            self.assertIsNone(a._recovery_pending)
            self.assertFalse(a.restore_navigation_pending)
            self.assertFalse(a.restore_position_pending)
            a._stopFailedPlayback()
            a.stop.assert_not_called()
            a._runDeferredNavigationRestore()
            a.parentDir.assert_not_called()

    def test_identical_media_url_still_belongs_to_new_session(self):
        a=self.player('A','https://fixture/same.mp4')
        b=self.player('B','https://fixture/same.mp4')
        self.assertFalse(a._ownsRecoveryPlayback())
        self.assertTrue(b._ownsRecoveryPlayback())

    def test_old_checkpoint_reads_keep_old_position_not_new_video_time(self):
        a=self.player('A','https://fixture/A.mp4')
        self.player('B','https://fixture/B.mp4')
        self.assertEqual(a._safePlayerTime(),600)
        self.assertEqual(a._safePlayerTotal(),1200)
        a.getTime.assert_not_called();a.getTotalTime.assert_not_called()

    def test_external_addon_start_also_retires_old_player(self):
        a=self.player('A','https://fixture/A.mp4')
        a.getPlayingFile.return_value='plugin://other-addon/B'
        a.onAVStarted()
        a.seekTime.assert_not_called();self.assertTrue(a._superseded)

    def test_stale_preparation_cannot_claim_over_newer_request(self):
        a=self.player('A','https://fixture/A.mp4')
        a._intent_token='stale'
        self.props['intent']='C'
        self.assertFalse(a._claimPlaybackOwnership())
        self.assertEqual(self.props['owner'],'A')

    def test_new_player_ignores_previous_video_during_asynchronous_open(self):
        b=self.player('B','https://fixture/B.mp4')
        b.playback_started=False
        b._owned_playing_file=None
        b.getPlayingFile.return_value='https://fixture/A.mp4'
        for callback in ('onAVStarted','onPlayBackStopped','onPlayBackEnded','onPlayBackError'):
            getattr(b,callback)()
        self.assertFalse(b.streamFinished)
        self.assertFalse(b._superseded)
        b._finishPlayback.assert_not_called()
        b.seekTime.assert_not_called()

    def test_retired_player_never_touches_new_video_with_highlight_on_or_off(self):
        for setting in ('true','false'):
            a=self.player('A','https://fixture/A.mp4')
            self.player('B','https://fixture/B.mp4')
            self.control.getSetting.return_value=setting
            a._runDeferredNavigationRestore()
            a.parentDir.assert_not_called()
            self.control.execute.assert_not_called()


if __name__=='__main__': unittest.main()
