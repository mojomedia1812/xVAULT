"""Signature starts once per add-on visit, never over existing playback."""
import ast
import os
from pathlib import Path
import threading
import time
import types
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


class SignatureTests(unittest.TestCase):
    def setUp(self):
        self.properties = {}
        self.path = 'plugin://plugin.video.xvault/'
        self.window = 'videos'
        self.enabled = 'true'
        self.active = False
        self.plays = []
        owner = self
        class Player:
            def isPlaying(self): return owner.active
            def play(self, path, item):
                owner.plays.append(path)
                self.onPlayBackEnded()
        control = types.SimpleNamespace(
            window=types.SimpleNamespace(getProperty=lambda k: self.properties.get(k, ''),
                                         setProperty=self.properties.__setitem__,
                                         clearProperty=lambda k: self.properties.pop(k, None)),
            infoLabel=lambda _: self.path,
            condVisibility=lambda query: query == 'Window.IsActive(%s)' % self.window,
            getSetting=lambda *a: self.enabled, addonPath=str(ROOT), item=Mock())
        tree = ast.parse((ROOT / 'resources/lib/signature.py').read_text(encoding='utf8'))
        tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
        scope = dict(os=os, threading=threading, time=time, control=control, log_utils=Mock(),
                     xbmc=types.SimpleNamespace(Player=Player, Monitor=lambda: Mock()))
        exec(compile(tree, 'signature.py', 'exec'), scope)
        self.module = types.SimpleNamespace(**scope)

    def test_setting_is_in_quickstart_enabled_by_default_and_video_is_bundled(self):
        root = ET.parse(ROOT / 'resources/settings.xml').getroot()
        setting = root.find("category[@label='Schnellstart']/setting[@id='signature.enabled']")
        self.assertEqual(setting.get('label'), 'Signature')
        self.assertEqual(setting.get('default'), 'true')
        self.assertTrue((ROOT / 'resources/media/signature.mp4').is_file())

    def test_repeated_root_and_back_navigation_do_not_replay(self):
        self.assertTrue(self.module.play_on_start())
        self.path += '?action=movieNavigator'
        self.module.observe_navigation()
        self.assertFalse(self.module.play_on_start())
        self.assertEqual(len(self.plays), 1)

    def test_leaving_and_reentering_addon_rearms_intro(self):
        self.module.play_on_start()
        self.path, self.window = '', 'home'
        self.module.observe_navigation()
        self.window = 'videos'
        self.assertTrue(self.module.play_on_start())
        self.assertEqual(len(self.plays), 2)

    def test_disabled_or_existing_player_is_never_replaced(self):
        self.enabled = 'false'
        self.assertFalse(self.module.play_on_start())
        self.properties.clear()
        self.enabled, self.active = 'true', True
        self.assertFalse(self.module.play_on_start())
        self.assertEqual(self.plays, [])

    def test_background_directory_request_does_not_play_or_mark_session(self):
        self.window = 'home'
        self.assertFalse(self.module.play_on_start())
        self.assertEqual(self.properties, {})

    def test_fullscreen_and_running_intro_do_not_rearm(self):
        self.properties[self.module.SESSION] = 'true'
        self.window = 'fullscreenvideo'
        self.module.observe_navigation()
        self.assertIn(self.module.SESSION, self.properties)

    def test_directory_rebuild_after_intro_does_not_count_as_exit(self):
        self.properties[self.module.SESSION] = 'true'
        self.path, self.window = '', 'busydialognocancel'
        self.module.observe_navigation()
        self.assertIn(self.module.SESSION, self.properties)
        self.properties[self.module.RUNNING] = 'true'
        self.path, self.window = '', 'home'
        self.module.observe_navigation()
        self.assertIn(self.module.SESSION, self.properties)

    def test_stop_callback_and_failure_are_local_to_intro(self):
        player = self.module.SignaturePlayer()
        player.onPlayBackStopped()
        self.assertTrue(player.finished)
        self.module.control.item.side_effect = OSError('fixture')
        self.assertFalse(self.module.play_on_start())
        self.assertNotIn(self.module.RUNNING, self.properties)


if __name__ == '__main__':
    unittest.main()
