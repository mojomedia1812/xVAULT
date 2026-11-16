"""Exercise the complete run entry point, including its runtime imports."""
import ast
import os
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[2]


class PlayerStartTests(unittest.TestCase):
    def test_complete_start_reaches_open_with_and_without_sync(self):
        tree=ast.parse((ROOT/'resources/lib/player.py').read_text(encoding='utf8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='player')
        cls.bases=[];cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='run']
        for logged_in in (False,True):
            with self.subTest(sync=logged_in):
                control=Mock(is_python2=False)
                control.sanitizeMetaArtwork.side_effect=lambda meta:meta
                control.translatePath.return_value=str(ROOT)
                log=Mock()
                scope=dict(control=control,uuid=uuid,time=time,os=Mock(path=os.path),
                           bookmarks=Mock(return_value=Mock(get=Mock(return_value='0'))),
                           log_utils=log,PLAYBACK_INTENT='test.intent')
                exec(compile(ast.Module(body=[cls],type_ignores=[]),'player.py','exec'),scope)
                p=scope['player']()
                p._playbackLabel=Mock(return_value='QA title')
                p.getVideoDB=Mock(return_value=0)
                p._openStream=Mock(return_value=None)
                p.keepPlaybackAlive=Mock(return_value=True)
                sync=types.ModuleType('resources.lib.sync')
                sync.engine=Mock();sync.binge_sync=Mock();sync.storage=Mock()
                sync.account=Mock()
                sync.storage.is_enabled.return_value=logged_in
                sync.storage.is_logged_in.return_value=logged_in
                # A preceding test may have imported the real distribution
                # module and cached it on the parent package. Isolate the
                # package as well as sys.modules entries for runtime imports.
                lib=types.ModuleType('resources.lib');lib.__path__=[]
                lib.distribution=Mock();lib.sync=sync
                lib.playback_recovery=types.SimpleNamespace(RecoveryState=Mock())
                imports={'xbmc':Mock(), 'glob':types.SimpleNamespace(glob=lambda pattern:['MyVideos131.db']),
                         'resources.lib':lib, 'resources.lib.distribution':lib.distribution,
                         'resources.lib.sync':sync, 'resources.lib.playback_recovery':lib.playback_recovery}
                with patch.dict(sys.modules,imports):
                    ok=p.run('QA title','https://fixture.invalid/video.mp4',dict(title='QA title',year=2026,mediatype='movie'))
                self.assertTrue(ok)
                self.assertEqual(len(p._intent_token),32)
                p._openStream.assert_called_once_with('https://fixture.invalid/video.mp4',initial=True)
                p.keepPlaybackAlive.assert_called_once()
                log.log.assert_not_called()


if __name__=='__main__':unittest.main()
