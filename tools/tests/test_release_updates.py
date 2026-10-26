"""Signed hashes, channels, real local HTTP polling and transactional rollback."""
import ast
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from zipfile import ZipFile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from resources.lib import release_security as security
from resources.lib import distribution
from resources.lib.update_install_helper import replace_tree, cleanup_artifacts
from tools import release_packaging as packaging

ROOT = Path(__file__).resolve().parents[2]


class ReleaseUpdateTests(unittest.TestCase):
    def test_maintenance_acknowledges_only_after_workers_exit(self):
        from resources.lib import update_maintenance as maintenance
        props = {}
        win = types.SimpleNamespace(getProperty=lambda k: props.get(k, ''),
            setProperty=props.__setitem__, clearProperty=lambda k: props.pop(k, None))
        worker = types.SimpleNamespace(name='xvault-network', is_alive=lambda: True)
        joined = []
        worker.join = lambda timeout: joined.append(timeout)
        with patch.object(maintenance, 'window', return_value=win):
            maintenance.started()
            self.assertFalse(maintenance.requested())
            props[maintenance.REQUEST] = 'test-install'
            foreign = types.SimpleNamespace(name='other-addon', is_alive=lambda: True)
            with patch.object(maintenance.threading, 'enumerate', side_effect=[[worker, foreign], [foreign]]):
                maintenance.finished()
            self.assertEqual(props[maintenance.STOPPED], 'test-install')
            self.assertNotIn(maintenance.RUNNING, props)
            self.assertEqual(joined, [.1])

    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        key = self.folder / 'private.pem'
        key.write_bytes(self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        public = self.key.public_key().public_numbers()
        for target, value in [('PUBLIC_N', public.n), ('PUBLIC_E', public.e)]:
            p = patch.object(security, target, value);p.start();self.addCleanup(p.stop)
        p = patch.dict('os.environ', {'XVAULT_SIGNING_KEY': str(key)});p.start();self.addCleanup(p.stop)
        self.settings = {'updates.channel': 'release'}
        self.properties = {}
        self.control = types.SimpleNamespace(dataPath=str(self.folder / 'profile'), addonPath=str(self.folder / 'addon'),
            addonVersion='2026.10.24.1', getSetting=lambda k, default='': self.settings.get(k, default),
            window=types.SimpleNamespace(setProperty=self.properties.__setitem__))
        self.log = types.SimpleNamespace(log=lambda *a: None, LOGWARNING=2)
        namespace = dict(control=self.control, log_utils=self.log, security=security, urlsplit=urlsplit)
        tree = ast.parse((ROOT / 'resources/lib/updater.py').read_text(encoding='utf-8'))
        definitions = [n for n in tree.body if not isinstance(n, ast.ImportFrom)]
        exec(compile(ast.Module(body=definitions, type_ignores=[]), 'updater.py', 'exec'), namespace)
        self.updater = types.SimpleNamespace(**namespace)
        self.files = {'addon.xml': b'<addon id="plugin.video.xvault" version="2026.10.24.1"/>',
                      'default.py': b'print("fixture")\n', 'resources/settings.xml': b'<settings/>'}
        self.envelope = packaging.make_integrity(self.files, '2026.10.24.1')
        self.payload = security.verify_envelope(self.envelope)
        self.release = {k: self.payload[k] for k in ('version', 'channel', 'addon_id', 'build_id', 'tree_sha256')}
        self.zip = self.folder / 'fixture.zip'
        self.write_zip()
        self.release.update(sha256=security.sha256_file(self.zip), size=self.zip.stat().st_size,
                            download_url='https://fixture.invalid/download.zip', integrity_url='https://fixture.invalid/integrity.json')

    def write_zip(self, changed=None):
        files = dict(self.files)
        files[security.INTEGRITY_FILE] = security.canonical(self.envelope)
        files.update(changed or {})
        with ZipFile(self.zip, 'w') as z:
            for name, data in files.items():z.writestr(security.ADDON_ID + '/' + name, data)

    def extracted(self):
        root = self.folder / 'tree'
        with ZipFile(self.zip) as z:z.extractall(root)
        return root / security.ADDON_ID

    def test_signature_authenticates_payload_not_just_hash_string(self):
        bad = copy.deepcopy(self.envelope);bad['payload']['version'] = '2028.10.11.1'
        with self.assertRaises(security.VerificationError):security.verify_envelope(bad)

    def test_clean_install_recalculates_same_tree_hash(self):
        r = security.inspect_tree(str(self.extracted()))
        self.assertEqual(r['state'], 'original')
        self.assertEqual(r['expected_sha256'], r['installed_sha256'])

    def test_changed_missing_and_added_files_are_detected_on_recheck(self):
        root = self.extracted();self.assertEqual(security.inspect_tree(root)['state'], 'original')
        (root / 'default.py').write_text('changed')
        (root / 'resources/settings.xml').unlink()
        (root / 'injected.py').write_text('print("extra")')
        r = security.inspect_tree(root)
        self.assertEqual(r['state'], 'modified')
        self.assertEqual((r['changed'], r['missing'], r['extra']), (['default.py'], ['resources/settings.xml'], ['injected.py']))

    def test_python_bytecode_does_not_make_original_modified(self):
        root = self.extracted();(root / '__pycache__').mkdir();(root / '__pycache__/default.pyc').write_bytes(b'cache')
        self.assertEqual(security.inspect_tree(root)['state'], 'original')

    def test_missing_reference_is_unknown_not_forgery(self):
        root = self.extracted();(root / security.INTEGRITY_FILE).unlink()
        self.assertEqual(security.inspect_tree(root)['state'], 'unverified')

    def test_modified_signed_reference_is_rejected(self):
        root = self.extracted();bad = copy.deepcopy(self.envelope);bad['payload']['files']['default.py'] = '0'*64
        (root / security.INTEGRITY_FILE).write_text(json.dumps(bad))
        self.assertEqual(security.inspect_tree(root)['state'], 'invalid_reference')

    def test_original_package_stages_and_passes_verification(self):
        target = self.folder / 'stage'
        self.updater.stage_package(str(self.zip), self.release, str(target))
        self.assertEqual(security.inspect_tree(target)['state'], 'original')

    def test_repacked_payload_cannot_be_authorized_with_new_zip_hash_alone(self):
        self.write_zip({'default.py': b'modified'})
        self.release['sha256'] = security.sha256_file(self.zip)
        with self.assertRaisesRegex(Exception, 'Datei-Hash'):
            self.updater.stage_package(str(self.zip), self.release, str(self.folder/'stage'))

    def test_wrong_zip_hash_is_rejected_before_extraction(self):
        self.release['sha256'] = '0'*64
        with self.assertRaisesRegex(Exception, 'ZIP-SHA'):
            self.updater.stage_package(str(self.zip), self.release, str(self.folder/'stage'))

    def test_traversal_and_unlisted_files_are_rejected(self):
        for name in ('../escape.py', 'extra.py'):
            with self.subTest(name=name):
                self.write_zip({name: b'extra'});self.release['sha256'] = security.sha256_file(self.zip)
                with self.assertRaises(Exception):self.updater.stage_package(str(self.zip), self.release, str(self.folder/'stage'))
        self.assertFalse((self.folder/'escape.py').exists())

    def test_release_nightly_schema_and_future_version_warning(self):
        self.assertEqual(security.version_info('2026.10.24.1')['channel'], 'release')
        self.assertEqual(security.version_info('2026.10.24.9')['channel'], 'nightly')
        self.assertIsNone(security.version_info('2026.02.30.1'))
        self.assertTrue(security.version_warning('2028.10.11.1', '2026.10.24.1'))

    def test_switch_from_higher_nightly_to_release_is_explicit_action(self):
        self.assertEqual(self.updater.update_plan('2026.10.24.9', self.release)['action'], 'switch')
        self.assertEqual(self.updater.update_plan('2028.10.11.1', self.release)['action'], 'repair')

    def test_higher_version_in_selected_channel_is_forward_update(self):
        nightly = dict(self.release, version='2026.10.26.2', channel='nightly')
        self.assertEqual(self.updater.update_plan('2026.10.24.1', nightly, channel='nightly')['action'], 'update')
        release = dict(self.release, version='2026.10.26.1')
        self.assertEqual(self.updater.update_plan('2026.10.24.9', release, channel='release')['action'], 'update')

    def test_lower_version_still_requires_confirmation_in_same_channel(self):
        nightly = dict(self.release, version='2026.10.24.2', channel='nightly')
        self.assertEqual(self.updater.update_plan('2026.10.26.2', nightly, channel='nightly')['action'], 'switch')

    def test_auto_monitor_installs_forward_channel_update_without_explicit_override(self):
        import sys
        from resources.lib import update_maintenance
        self.settings.update({'updates.channel': 'nightly', 'updates.mode': '1', 'updates.auto': 'true'})
        self.control.window.getProperty = lambda key: ''
        nightly = dict(self.release, version='2026.10.26.2', channel='nightly')
        state = dict(release=nightly, plan=self.updater.update_plan('2026.10.24.1', nightly, channel='nightly'))
        monitor = types.SimpleNamespace(waitForAbort=lambda timeout: False)
        installs = []
        namespace = self.updater.start_background.__globals__
        with patch.dict(sys.modules, {'xbmc': types.SimpleNamespace(Monitor=lambda: monitor)}), \
                patch.object(update_maintenance, 'requested', return_value=False), \
                patch.dict(namespace, {'poll': lambda **kw: state, 'idle_for_install': lambda: True,
                                      'install_release': lambda release, **kw: installs.append((release, kw))}):
            self.updater.start_background()
            namespace['_thread'].join(2)
            self.assertFalse(namespace['_thread'].is_alive())
        self.assertEqual(installs, [(nightly, {'explicit': False})])

    def test_channel_mismatch_and_replayed_feed_are_rejected(self):
        feed = packaging.sign(dict(schema=1, channel='release', sequence=5, release=self.release))
        with self.assertRaises(Exception):self.updater.validate_catalog(feed, 'nightly')
        with self.assertRaises(Exception):self.updater.validate_catalog(feed, 'release', 6)

    def test_legacy_external_setting_cannot_change_trusted_feed(self):
        self.settings['updates.channel'] = 'external'
        self.assertEqual(self.updater.selected_channel(), 'release')

    def test_known_android_and_windows_hosts_are_detected_without_claiming_baseline(self):
        a = distribution.detect_kodibox('/storage/ger.kodi.box2/addons/plugin.video.xvault')
        b = distribution.detect_kodibox('C:/Programs/KodiBox/portable_data/addons/plugin.video.xvault', wizard=True)
        c = distribution.detect_kodibox('C:/Programs/Kodi/addons/plugin.video.xvault', wizard=True)
        self.assertTrue(a['detected'] and b['detected']);self.assertFalse(c['detected'])
        self.assertIsNone(a['based_on'])

    def test_failed_directory_switch_restores_old_addon(self):
        target, stage, backup = [self.folder/name for name in ('plugin.video.xvault', '.xvault-stage-test', '.xvault-backup-test')]
        target.mkdir();stage.mkdir();(target/'old.py').write_text('old');(stage/'new.py').write_text('new')
        import os
        real = os.replace;calls = []
        def replace(a, b):
            calls.append((a,b))
            if len(calls)==2:raise OSError('simulated filesystem failure')
            return real(a,b)
        with patch('os.replace', replace):
            with self.assertRaises(OSError):replace_tree(str(stage), str(target), str(backup))
        self.assertEqual((target/'old.py').read_text(), 'old');self.assertFalse(backup.exists())

    def test_cleanup_removes_failed_stage_and_only_our_old_marked_backups(self):
        target = self.folder/'plugin.video.xvault';target.mkdir()
        stage = self.folder/'.xvault-stage-test';stage.mkdir();(stage/'bad.py').write_text('bad')
        backup = self.folder/'.xvault-backup-new';backup.mkdir()
        unowned = self.folder/'.xvault-backup-unowned';unowned.mkdir();(unowned/'user.txt').write_text('keep')
        job = dict(target=str(target),stage=str(stage),backup=str(backup))
        cleanup_artifacts(job,False);self.assertFalse(stage.exists())
        for i in range(3):
            path = self.folder/('.xvault-backup-old'+str(i));path.mkdir()
            (path/'.xvault-update-backup.json').write_text(json.dumps({'addon_id':'plugin.video.xvault'}))
        cleanup_artifacts(job,True)
        marked = list(self.folder.glob('.xvault-backup-*/.xvault-update-backup.json'))
        self.assertEqual(len(marked),2);self.assertTrue((unowned/'user.txt').exists())

    def test_real_http_poll_is_independent_of_kodi_and_honors_check_frequency(self):
        case = self
        class Handler(BaseHTTPRequestHandler):
            calls = 0
            def log_message(self, *args):pass
            def do_GET(self):
                Handler.calls += 1
                body = security.canonical(case.feed if self.path.endswith('release.json') else case.envelope)
                self.send_response(200);self.send_header('Content-Length', str(len(body)));self.end_headers();self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base = 'http://127.0.0.1:%s/' % server.server_port
        self.release.update(download_url=base+'fixture.zip', integrity_url=base+'integrity.json')
        self.feed = packaging.sign(dict(schema=1, channel='release', sequence=10, release=self.release))
        origin = {'state':'original', 'build_id':self.release['build_id'], 'installed_sha256':self.release['tree_sha256']}
        lib = importlib.import_module('resources.lib')
        with patch.object(lib, 'distribution', types.SimpleNamespace(checkpoint=lambda *a,**kw: {'integrity':origin}), create=True):
            state = self.updater.poll(force=True, base_url=base, allow_loopback=True)
            self.assertFalse(state['network_error']);self.assertTrue(state['repository_match'])
            self.assertEqual(state['plan']['action'], 'none')
            calls = Handler.calls
            self.updater.poll(base_url=base, allow_loopback=True)
            self.assertEqual(Handler.calls, calls)
            self.control.addonVersion = '2026.10.23.1'
            state = self.updater.poll(force=True, base_url=base, allow_loopback=True)
            self.assertEqual(state['plan']['action'], 'update')
            calls = Handler.calls
            self.control.addonVersion = '2026.10.24.1'
            state = self.updater.poll(base_url=base, allow_loopback=True)
            self.assertGreater(Handler.calls, calls)
            self.assertEqual(state['plan']['action'], 'none')
            self.assertTrue(state['repository_match'])
            with patch.dict(self.updater.poll.__globals__, {'fetch_json': lambda *a: (_ for _ in ()).throw(OSError('offline'))}):
                state = self.updater.poll(force=True, base_url=base, allow_loopback=True)
            self.assertTrue(state['network_error']);self.assertEqual(state['release']['version'], '2026.10.24.1')

    def test_kodi_repository_urls_follow_selected_channel(self):
        tree = ast.parse((ROOT/'resources/lib/repository.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='channel_template')
        namespace = {'BASE_URL': security.BASE_URL}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'repository.py', 'exec'), namespace)
        template = (ROOT/'resources/repository/addon.xml').read_text(encoding='utf-8')
        import xml.etree.ElementTree as ET
        for channel, prefix in [('release',''),('nightly','updates/nightly/')]:
            root = ET.fromstring(namespace['channel_template'](template, channel))
            self.assertEqual(root.find('.//info').text, security.BASE_URL+prefix+'addons.xml')
            self.assertEqual(root.find('.//checksum').text, security.BASE_URL+prefix+'addons.xml.md5')

    def test_nightly_catalog_does_not_replace_release_feed_or_repository(self):
        docs = self.folder/'docs'
        packaging.write_catalog(self.zip, self.envelope, docs)
        release_feed = (docs/'updates/release.json').read_bytes()
        release_repo = (docs/'updates/release/addons.xml').read_bytes()
        self.files['addon.xml'] = self.files['addon.xml'].replace(b'2026.10.24.1', b'2026.10.24.9')
        self.envelope = packaging.make_integrity(self.files, '2026.10.24.9')
        self.write_zip()
        packaging.write_catalog(self.zip, self.envelope, docs)
        self.assertEqual((docs/'updates/release.json').read_bytes(), release_feed)
        self.assertEqual((docs/'updates/release/addons.xml').read_bytes(), release_repo)
        self.assertIn(b'2026.10.24.9', (docs/'updates/nightly/addons.xml').read_bytes())


if __name__ == '__main__':
    unittest.main()
