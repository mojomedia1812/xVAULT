"""Modules installed during a running Kodi service become importable immediately."""
import ast
import importlib
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


class DynamicModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.paths = {}
        source = Path(__file__).resolve().parents[2] / 'resources/lib/dependencies.py'
        method = next(n for n in ast.parse(source.read_text()).body
                      if isinstance(n, ast.FunctionDef) and n.name == '_refresh_python_module_paths')
        scope = dict(os=os, sys=sys, ET=ET, _translate_path=lambda p: p)
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), scope)
        self.refresh = scope['_refresh_python_module_paths']

    def addon(self, name, library='lib', dependencies=()):
        root = self.base / name
        root.mkdir()
        self.paths[name] = root
        (root / 'addon.xml').write_text(
            '<addon id="%s"><requires>%s</requires><extension point="xbmc.python.module" library="%s"/></addon>'
            % (name, ''.join('<import addon="%s"/>' % d for d in dependencies), library))
        return root

    def api(self, name):
        if name not in self.paths:
            raise RuntimeError('Not installed')
        return types.SimpleNamespace(getAddonInfo=lambda _: str(self.paths[name]))

    def test_late_install_and_transitive_library_import_without_restart(self):
        a = self.addon('script.module.fixture.a', 'python', ['script.module.fixture.b', 'xbmc.python'])
        b = self.addon('script.module.fixture.b', 'lib', ['script.module.fixture.a'])
        (a / 'python').mkdir(); (b / 'lib').mkdir()
        (a / 'python/_xvault_late_a.py').write_text('from _xvault_late_b import VALUE')
        (b / 'lib/_xvault_late_b.py').write_text('VALUE = 42')
        for name in ('_xvault_late_a', '_xvault_late_b'):
            self.addCleanup(sys.modules.pop, name, None)
        with patch.object(sys, 'path', list(sys.path)), patch.dict(sys.modules, {
                'xbmcaddon': types.SimpleNamespace(Addon=self.api)}):
            with self.assertRaises(ModuleNotFoundError):
                importlib.import_module('_xvault_late_a')
            self.refresh(['script.module.fixture.a'])
            self.assertEqual(importlib.import_module('_xvault_late_a').VALUE, 42)
            self.refresh(['script.module.fixture.a'])
            self.assertEqual(sys.path.count(str(a / 'python')), 1)

    def test_missing_modules_and_library_outside_addon_are_ignored(self):
        self.addon('script.module.fixture.bad', '../outside')
        outside = self.base / 'outside'; outside.mkdir()
        with patch.object(sys, 'path', list(sys.path)), patch.dict(sys.modules, {
                'xbmcaddon': types.SimpleNamespace(Addon=self.api)}):
            before = list(sys.path)
            self.refresh(['script.module.absent', 'script.module.fixture.bad', 'visualization.xvault'])
            self.assertEqual(sys.path, before)


if __name__ == '__main__':
    unittest.main()
