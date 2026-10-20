"""Exercise provider health decisions without starting the Kodi background service."""
import ast
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import patch


def service_functions(settings, doh_result=(False, 'example.test', None)):
    source = Path(__file__).resolve().parents[2] / 'service.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('_doh_enabled', '_checkdomain')]
    writes = {}
    calls = []

    def doh(domain):
        calls.append(domain)
        return doh_result

    scope = {'getSetting': lambda name, default='': settings.get(name, default),
             'setSetting': writes.__setitem__, 'PROVIDER_DOMAIN_REPLACEMENTS': {},
             '_settingsLock': threading.Lock(), 'isLogger': False,
             'RandomUA': lambda: 'test', '_checkdomain_with_doh': doh}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), scope)
    return scope, writes, calls


class ProviderHealthTests(unittest.TestCase):
    def test_current_setting_controls_doh_including_disabled_value(self):
        for value, expected in [('true', True), ('false', False), ('', True)]:
            with self.subTest(value=value):
                scope, _, _ = service_functions({'bypassDNSlock.enabled': value,
                                                  'bypassDNSlock': 'true'})
                self.assertEqual(scope['_doh_enabled'](), expected)

    def request_failure(self, enabled, doh_result):
        scope, writes, calls = service_functions({'bypassDNSlock.enabled': enabled}, doh_result)
        requests = types.ModuleType('requests')
        requests.packages = types.SimpleNamespace(urllib3=types.SimpleNamespace(disable_warnings=lambda: None))

        def head(*args, **kwargs):
            raise TimeoutError('temporary network outage')

        requests.head = head
        with patch.dict(sys.modules, {'requests': requests}):
            scope['_checkdomain']('example.test', 'example')
        return writes, calls

    def test_temporary_failure_keeps_provider_eligible_when_doh_disabled(self):
        writes, calls = self.request_failure('false', (False, 'example.test', None))
        self.assertEqual(writes['provider.example.check'], '')
        self.assertEqual(writes['provider.example.domain'], 'example.test')
        self.assertEqual(calls, [])

    def test_enabled_doh_recovers_a_failed_direct_check(self):
        writes, calls = self.request_failure('true', (True, 'mirror.test', '200'))
        self.assertEqual(writes['provider.example.check'], 'true')
        self.assertEqual(writes['provider.example.domain'], 'mirror.test')
        self.assertEqual(calls, ['example.test'])


if __name__ == '__main__':
    unittest.main()
