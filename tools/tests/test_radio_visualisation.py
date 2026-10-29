"""Kodi-native visualisation callbacks, settings ownership and repository bootstrap."""
import json
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
IDS = ('visualization.xvault',)
TARGET = 'https://stream.example/radio.mp3'


class VisualisationTests(unittest.TestCase):
    def setUp(self):
        self.props, self.settings, self.commands = {}, {'musicplayer.visualisation': ''}, []
        self.choice = '0'
        self.available = set(IDS)
        self.audio, self.target = True, TARGET
        owner = self

        class Player:
            def isPlayingAudio(self):
                return owner.audio

            def getPlayingFile(self):
                return owner.target

        def rpc(raw):
            request = json.loads(raw)
            method, params = request['method'], request['params']
            if method == 'Addons.GetAddonDetails':
                result = {'addon': {'enabled': params['addonid'] in owner.available}}
            elif method == 'Settings.GetSettingValue':
                result = {'value': owner.settings[params['setting']]}
            elif method == 'Settings.SetSettingValue':
                owner.settings[params['setting']] = params['value']
                result = True
            else:
                raise AssertionError(method)
            return json.dumps({'result': result})

        self.win = types.SimpleNamespace(getProperty=lambda k: self.props.get(k, ''),
            setProperty=self.props.__setitem__, clearProperty=lambda k: self.props.pop(k, None))
        self.gui = types.SimpleNamespace(Window=lambda _: self.win, Dialog=Mock(), NOTIFICATION_INFO='info')
        self.xbmc = types.SimpleNamespace(Player=Player, executeJSONRPC=rpc,
            executebuiltin=self.commands.append, log=Mock(), LOGWARNING=2)
        addon = types.SimpleNamespace(getSetting=lambda _: self.choice)
        natives = {'xbmc': self.xbmc, 'xbmcgui': self.gui,
                   'xbmcaddon': types.SimpleNamespace(Addon=lambda ident: addon)}
        self.module = types.ModuleType('radio_visualisation_under_test')
        self.module.__file__ = str(ROOT / 'resources/lib/radio_visualisation.py')
        with patch.dict(sys.modules, natives):
            exec(compile(Path(self.module.__file__).read_text(encoding='utf8'), self.module.__file__, 'exec'), self.module.__dict__)

    def test_default_is_xvault_visuals_and_arming_does_not_change_global_settings(self):
        self.module.arm(TARGET)
        self.assertEqual(self.module.pending()['visualizer'], IDS[0])
        self.assertEqual(self.settings['musicplayer.visualisation'], '')
        self.assertEqual(self.commands, [])

    def test_real_audio_start_activates_native_window_once_and_restores_on_stop(self):
        self.module.arm(TARGET)
        player = self.module.RadioPlayer()
        player.onAVStarted()
        self.assertEqual(self.settings['musicplayer.visualisation'], IDS[0])
        self.assertEqual(self.commands, ['ActivateWindow(visualisation)'])
        player.onAVStarted()  # Audio metadata change must not reopen after user goes back.
        self.assertEqual(len(self.commands), 1)
        player.onPlayBackStopped()
        self.assertEqual(self.settings['musicplayer.visualisation'], '')

    def test_unrelated_audio_video_and_expired_requests_do_not_open_visualisation(self):
        for case in ('different_source', 'video', 'expired'):
            self.audio, self.target = True, TARGET
            self.module.arm(TARGET)
            if case == 'different_source':
                self.target = 'https://other.example/music.mp3'
            elif case == 'video':
                self.audio = False
            else:
                data = self.module.pending()
                data['created'] = time.time() - 121
                self.props[self.module.PENDING] = json.dumps(data)
            self.module.RadioPlayer().onAVStarted()
        self.assertEqual(self.commands, [])

    def test_choices_and_disabled_mode(self):
        for value, visualizer in enumerate(IDS):
            self.choice = str(value)
            self.module.arm(TARGET)
            self.assertEqual(self.module.pending()['visualizer'], visualizer)
        self.choice = '1'
        self.module.arm(TARGET)
        self.assertIsNone(self.module.pending())

    def test_missing_visualizer_does_not_break_radio_or_install_on_playback(self):
        self.available.clear()
        self.module.arm(TARGET)
        self.assertIsNone(self.module.pending())
        self.assertEqual(self.commands, [])
        self.gui.Dialog.return_value.notification.assert_called_once()

    def test_manual_kodi_visualizer_change_is_preserved(self):
        self.module.arm(TARGET)
        player = self.module.RadioPlayer()
        player.onAVStarted()
        self.settings['musicplayer.visualisation'] = 'visualization.user-choice'
        player.onPlayBackEnded()
        self.assertEqual(self.settings['musicplayer.visualisation'], 'visualization.user-choice')

    def test_station_switch_restores_original_setting_after_last_station(self):
        self.settings['musicplayer.visualisation'] = 'visualization.previous'
        player = self.module.RadioPlayer()
        self.module.arm(TARGET)
        player.onAVStarted()
        self.target = 'https://stream.example/second.mp3'
        self.module.arm(self.target)
        player.onPlayBackStopped()  # Stop of old stream must not clear the new request.
        self.assertIsNotNone(self.module.pending())
        player.onAVStarted()
        self.assertEqual(self.settings['musicplayer.visualisation'], IDS[0])
        player.onPlayBackEnded()
        self.assertEqual(self.settings['musicplayer.visualisation'], 'visualization.previous')

    def test_service_start_and_shutdown_preserve_settings_and_no_extra_input_handlers(self):
        self.module.arm(TARGET)
        self.module.start_monitor()
        self.module.start_monitor()
        self.assertEqual(len(self.commands), 1)
        self.module.stop_monitor()
        self.assertEqual(self.settings['musicplayer.visualisation'], '')
        self.assertNotIn('onAction', self.module.RadioPlayer.__dict__)


class VisualisationDependenciesTests(unittest.TestCase):
    def setUp(self):
        self.native = Mock()
        self.gui = Mock()
        self.module = types.ModuleType('dependencies_under_test')
        self.addon_settings = {}
        native_addon = types.SimpleNamespace(Addon=lambda ident: types.SimpleNamespace(
            getSetting=lambda name: self.addon_settings.get(name, '')))
        module_patch = patch.dict(sys.modules, {'xbmcaddon': native_addon})
        module_patch.start()
        self.addCleanup(module_patch.stop)
        self.module.__file__ = str(ROOT / 'resources/lib/dependencies.py')
        with patch.dict(sys.modules, {'xbmc': self.native, 'xbmcgui': self.gui, 'xbmcvfs': Mock()}):
            exec(compile(Path(self.module.__file__).read_text(encoding='utf8'), self.module.__file__, 'exec'), self.module.__dict__)

    def test_all_visualizers_are_declared_and_selected_for_kodi_bootstrap(self):
        self.native.getInfoLabel.return_value = '22.0-RC1'
        import xml.etree.ElementTree as ET
        imports = {n.get('addon') for n in ET.parse(ROOT / 'addon.xml').findall('./requires/import')}
        for addon in IDS:
            self.assertIn(addon, imports)
            self.assertTrue(self.module._should_install(addon, optional=True))
            self.assertNotIn(addon, self.module.EXTERNAL_ADDON_SOURCES)
        self.assertFalse(self.module._should_install('inputstream.adaptive', optional=True))
        for addon in ('visualization.shadertoy', 'visualization.spectrum', 'visualization.waveform'):
            self.assertNotIn(addon, imports)
            self.assertFalse(self.module._should_install(addon, optional=True))

    def test_disabled_radio_never_auto_installs_its_native_visualizer(self):
        self.native.getInfoLabel.return_value = '22.0-RC1'
        self.addon_settings['radio.enabled'] = 'false'
        self.assertFalse(self.module._should_install(IDS[0], optional=True))

    def test_install_uses_native_kodi_repository_command_without_external_download(self):
        with patch.object(self.module, '_has_addon', return_value=False), \
                patch.object(self.module, '_refresh_addons') as refresh, \
                patch.object(self.module, '_accept_install_dialog'), \
                patch.object(self.module, '_wait_for_addon', return_value=True), \
                patch.object(self.module, '_install_external_addon', side_effect=AssertionError('external source')):
            for addon in IDS:
                self.assertTrue(self.module._install_addon(addon))
        commands = [c.args[0] for c in self.native.executebuiltin.call_args_list]
        self.assertEqual(commands, ['InstallAddon(%s)' % addon for addon in IDS])
        refresh.assert_called_once()
        for call in self.native.executebuiltin.call_args_list:
            self.assertEqual(len(call.args), 1)  # Never synchronously wait on a modal installer.

    def test_existing_visualizers_are_not_downloaded_again(self):
        with patch.object(self.module, '_has_addon', return_value=True):
            for addon in IDS:
                self.assertTrue(self.module._install_addon(addon))
        self.native.executebuiltin.assert_not_called()

    def test_native_visuals_do_not_attempt_incompatible_binary_installation(self):
        with patch.object(self.module.sys, 'platform', 'win32'), patch.object(self.module.struct, 'calcsize', return_value=8):
            self.native.getInfoLabel.return_value = '22.0-RC1'
            self.assertTrue(self.module._should_install(IDS[0], True))
            self.native.getInfoLabel.return_value = '21.3'
            self.assertFalse(self.module._should_install(IDS[0], True))
        with patch.object(self.module.sys, 'platform', 'linux'):
            self.assertFalse(self.module._should_install(IDS[0], True))
        with patch.object(self.module.struct, 'calcsize', return_value=4):
            self.assertFalse(self.module.native_visuals_supported())


if __name__ == '__main__':
    unittest.main()
