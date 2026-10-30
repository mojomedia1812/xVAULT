"""Guard native add-on selection against wrong OS, architecture and Kodi ABI."""
import importlib
import ast
import hashlib
import json
import os
import shutil
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from resources.lib import native_visuals
from tools.build_visuals import publish_native_profile


class NativeProfileTests(unittest.TestCase):
    def test_native_update_rolls_back_a_failed_directory_switch(self):
        source = Path(__file__).resolve().parents[2] / 'resources/lib/dependencies.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        method = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_update_native_visuals')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            addons = root / 'addons'; addons.mkdir()
            target = addons / 'visualization.xvault'; target.mkdir()
            (target / 'old.bin').write_bytes(b'original')
            userdata = root / 'userdata'; userdata.mkdir()
            (userdata / 'settings.xml').write_text('personal settings')
            package = root / 'source.zip'
            with ZipFile(package, 'w') as archive:
                archive.writestr('visualization.xvault/addon.xml',
                    '<addon id="visualization.xvault" version="22.0.2"><requires>'
                    '<import addon="kodi.binary.instance.visualization" version="5.0.0"/>'
                    '</requires><extension point="xbmc.addon.metadata"><platform>windows-x86_64</platform>'
                    '</extension></addon>')
                archive.writestr('visualization.xvault/new.bin', b'new')
            reference = dict(addon_id='visualization.xvault', version='22.0.2', size=package.stat().st_size,
                             sha256=hashlib.sha256(package.read_bytes()).hexdigest())
            api = types.SimpleNamespace(getCondVisibility=lambda _: False, executeJSONRPC=lambda _: '{}', LOGWARNING=1)
            scope = dict(xbmc=api, _log=lambda *a: None,
                         _native_descriptor=lambda _: (reference, 'https://fixture.test/native.zip'),
                         _dependency_temp_path=lambda _: str(root / 'download.zip'),
                         _download_file=lambda url, dest: shutil.copyfile(package, dest),
                         _translate_path=lambda _: str(addons), _mkdir=lambda p: Path(p).mkdir(parents=True, exist_ok=True),
                         _safe_join=lambda base, part: str(Path(base) / part),
                         _normalize_zip_name=lambda name: name, zipfile=importlib.import_module('zipfile'),
                         os=os, ET=ET, json=json, DependencyError=RuntimeError,
                         _refresh_addons=lambda: None, _enable_addons=lambda _: None,
                         _wait_for_addon=lambda *a, **k: True)
            exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), scope)
            real_replace = os.replace
            calls = []
            def fail_second(a, b):
                calls.append((a, b))
                if len(calls) == 2:
                    raise OSError('simulated locked native library')
                return real_replace(a, b)
            with patch.object(native_visuals, 'profile', return_value='windows-x86_64/kodi22'), \
                    patch('os.replace', side_effect=fail_second):
                self.assertFalse(scope['_update_native_visuals']('22.0.2'))
            self.assertEqual((target / 'old.bin').read_bytes(), b'original')
            self.assertFalse((target / 'new.bin').exists())
            self.assertEqual((userdata / 'settings.xml').read_text(), 'personal settings')

    def test_only_built_and_compatible_profiles_are_selected(self):
        cases = [
            ('win32', 8, 'AMD64', '22.0-RC1', False, 'windows-x86_64/kodi22'),
            ('linux', 4, 'armv7l', '21.3', True, 'android-armv7/kodi21'),
            ('linux', 4, 'armv7l', '21.2', True, 'android-armv7/kodi21'),
            ('linux', 8, 'aarch64', '21.3', True, 'android-aarch64/kodi21'),
            ('linux', 8, 'arm64', '21.2', True, 'android-aarch64/kodi21'),
            ('linux', 4, 'aarch64', '21.3', True, 'android-armv7/kodi21'),
            ('linux', 4, 'arm64', '21.3', True, 'android-armv7/kodi21'),
            ('linux', 8, 'armv7l', '21.3', True, ''),
            ('linux', 8, 'x86_64', '21.3', True, ''),
            ('linux', 8, 'aarch64', '22.0', True, ''),
            ('linux', 8, 'aarch64', '21.3', False, ''),
            ('linux', 4, 'armv7l', '22.0', True, ''),
            ('linux', 4, 'armv7l', '21.3', False, ''),
            ('linux', 4, 'i686', '21.3', True, ''),
            ('win32', 4, 'AMD64', '22.0', False, ''),
            ('win32', 8, 'AMD64', '21.3', False, ''),
            ('darwin', 8, 'arm64', '22.0', False, ''),
        ]
        for host, size, machine, kodi, android, expected in cases:
            with self.subTest(host=host, machine=machine, kodi=kodi), \
                    patch.object(native_visuals.sys, 'platform', host), \
                    patch.object(native_visuals.struct, 'calcsize', return_value=size), \
                    patch.object(native_visuals.platform, 'machine', return_value=machine):
                api = types.SimpleNamespace(getInfoLabel=lambda _: kodi, getCondVisibility=lambda _: android)
                self.assertEqual(native_visuals.profile(api), expected)
                self.assertEqual(bool(native_visuals.required_version(api)), bool(expected))

    def test_native_feed_keeps_android_separate_and_checks_api(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root / 'native.zip'
            xml = ('<addon id="visualization.xvault" version="21.0.2">'
                   '<requires><import addon="kodi.binary.instance.visualization" version="4.0.0"/></requires>'
                   '<extension point="xbmc.addon.metadata"><platform>android-armv7</platform></extension></addon>')
            with ZipFile(package, 'w') as archive:
                archive.writestr('visualization.xvault/addon.xml', xml)
            with patch('tools.release_packaging.sign', side_effect=lambda payload: {'payload': payload}):
                target = publish_native_profile(package, root / 'docs', 'android-armv7/kodi21')
            feed = target.parent.parent / 'addons.xml'
            self.assertEqual(ET.parse(feed).find('addon').get('version'), '21.0.2')
            self.assertFalse((root / 'docs/addons.xml').exists())
            with self.assertRaises(ValueError):
                publish_native_profile(package, root / 'docs', 'windows-x86_64/kodi22')

    def test_arm64_feed_cannot_deliver_an_arm32_library(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root / 'native.zip'
            xml = ('<addon id="visualization.xvault" version="21.0.2">'
                   '<requires><import addon="kodi.binary.instance.visualization" version="4.0.0"/></requires>'
                   '<extension point="xbmc.addon.metadata"><platform>android-aarch64</platform></extension></addon>')
            with ZipFile(package, 'w') as archive:
                archive.writestr('visualization.xvault/addon.xml', xml)
            with patch('tools.release_packaging.sign', side_effect=lambda payload: {'payload': payload}):
                target = publish_native_profile(package, root / 'docs', 'android-aarch64/kodi21')
            reference = json.loads((target.parent.parent / 'native.json').read_text())['payload']
            self.assertEqual(reference['profile'], 'android-aarch64/kodi21')
            self.assertEqual(reference['sha256'], hashlib.sha256(package.read_bytes()).hexdigest())
            with self.assertRaises(ValueError):
                publish_native_profile(package, root / 'docs', 'android-armv7/kodi21')


if __name__ == '__main__':
    unittest.main()
