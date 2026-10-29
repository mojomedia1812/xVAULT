"""Exercise live Kodi settings ownership and a stalled provider search."""
import ast
from pathlib import Path
import random
import types
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]


class SettingsAndSearchTests(unittest.TestCase):
    def test_setting_updates_kodi_even_when_xml_already_has_new_value(self):
        tree = ast.parse((ROOT / 'resources/lib/control.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'setSetting')
        live = {'sync.status': 'Nicht angemeldet'}
        addon = types.SimpleNamespace(getSetting=lambda k: live.get(k, ''),
                                      setSetting=Mock(side_effect=live.__setitem__))
        fallback = Mock()
        scope = dict(xbmcaddon=types.SimpleNamespace(Addon=lambda _: addon), addonId='plugin.video.xvault',
                     getSetting=lambda _: 'Angemeldet', _writeSettingValue=fallback,
                     _invalidateSettingsCache=Mock())
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'control.py', 'exec'), scope)
        self.assertTrue(scope['setSetting']('sync.status', 'Angemeldet'))
        self.assertEqual(live['sync.status'], 'Angemeldet')
        fallback.assert_not_called()
        scope['setSetting']('sync.status', 'Angemeldet')
        self.assertEqual(addon.setSetting.call_count, 1)

    def test_stalled_provider_stops_at_configured_seconds(self):
        tree = ast.parse((ROOT / 'resources/lib/sources.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'sources')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'getSources')
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        control = types.SimpleNamespace(getSetting=lambda k: {'scrapers.timeout': '35', 'hosts.quality': '0'}.get(k, ''),
                                        abortRequested=False, sleep=sleep)
        scope = dict(time=types.SimpleNamespace(monotonic=lambda: clock[0]), control=control, random=random,
                     utils=types.SimpleNamespace(getAliases=lambda *a: ([], ''), get_titles_for_search=lambda *a: []),
                     log_utils=types.SimpleNamespace(log=Mock(), LOGERROR=1), PROVIDER_TIMEOUT_TTL=60)
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'sources.py', 'exec'), scope)
        future = Mock(); future.done.return_value = False
        obj = Mock(sourceDict=[('slow', types.SimpleNamespace(priority=0))], aliases=[])
        obj._readSourceCache.return_value = (None, False)
        obj._filterTemporarilyBlockedProviders.side_effect = lambda x: x
        obj._promoteSeriesProviders.side_effect = lambda x, _: x
        obj.executor.submit.return_value = future
        self.assertEqual(scope['getSources'](obj, 'Test', 2026, 'tt-test', 0, 0, '', '', quiet=True), [])
        self.assertEqual(clock[0], 35)
        obj._cancelFutures.assert_called_once()
        obj._shutdownExecutor.assert_called_once()


if __name__ == '__main__':
    unittest.main()
