"""HTTP integration tests of the real PHP handlers, isolated from production.

Requires PHP with pdo_sqlite (or XVAULT_TEST_MYSQL_DSN pointing to an EMPTY test
database, plus XVAULT_TEST_MYSQL_USER/PASSWORD). Never use a production database.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).resolve().parents[2]


class LocalAPI:
    def __init__(self, folder=None):
        self.temp = tempfile.TemporaryDirectory(prefix='xvault-sync-') if folder is None else None
        self.folder = Path(folder or self.temp.name)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.password = uuid.uuid4().hex
        self.email = 'sync-%s@example.com' % uuid.uuid4().hex[:12]
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        source = (ROOT / 'api/index.php').read_text(encoding='utf-8')
        (self.folder / 'functions.php').write_text('<?php\n' + source[source.index('function db('):], encoding='utf-8')
        shutil.copyfile(ROOT / 'api/sync_v2.php', self.folder / 'sync_v2.php')
        # Test-only adapter. All authentication, exchange, CAS and journal logic
        # comes verbatim from the production PHP source.
        router = '''<?php
require __DIR__ . '/sync_v2.php';
require __DIR__ . '/functions.php';
$pdo = new PDO(getenv('XVAULT_TEST_MYSQL_DSN') ?: 'sqlite:' . __DIR__ . '/test.sqlite', getenv('XVAULT_TEST_MYSQL_USER') ?: null, getenv('XVAULT_TEST_MYSQL_PASSWORD') ?: null, [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
if ($pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'mysql') {
    ensure_schema($pdo);
} else {
    $pdo->exec('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password_hash TEXT, api_key_hash TEXT, created_at TEXT, updated_at TEXT, last_login_at TEXT, is_active INT DEFAULT 1)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS favorites_items (user_id INT, key_hash TEXT, label TEXT, thumb TEXT, path TEXT, sort_order INT, is_deleted INT, revision INT, created_at TEXT, updated_at TEXT)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS favorites_backups (user_id INT, data_json TEXT, updated_at TEXT, id INT)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS binge_state (user_id INT, item_key TEXT, data_json TEXT, created_at TEXT, updated_at TEXT)');
    sync2_schema($pdo);
}
if (!sync2_query($pdo, 'SELECT id FROM users WHERE email = ?', [TEST_EMAIL])->fetch()) {
    sync2_query($pdo, 'INSERT INTO users (email, password_hash, api_key_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)', [TEST_EMAIL, password_hash(TEST_PASSWORD, PASSWORD_DEFAULT), hash('sha256', 'legacy-test-key'), now(), now()]);
}
try { dispatch($pdo, []); } catch (Throwable $e) { http_response_code(500); echo json_encode(['exception'=>get_class($e), 'message'=>$e->getMessage()]); }
'''
        router = router.replace("require __DIR__ . '/sync_v2.php';", "define('TEST_EMAIL', %s); define('TEST_PASSWORD', %s);\nrequire __DIR__ . '/sync_v2.php';" % (json.dumps(self.email), json.dumps(self.password)))
        (self.folder / 'router.php').write_text(router, encoding='utf-8')
        php = shutil.which('php')
        command = [php]
        ext = Path(php).parent / 'ext/php_pdo_sqlite.dll'
        if ext.exists():
            command += ['-d', 'extension=' + str(ext)]
        mysql = Path(php).parent / 'ext/php_pdo_mysql.dll'
        if os.getenv('XVAULT_TEST_MYSQL_DSN') and mysql.exists():
            command += ['-d', 'extension=' + str(mysql)]
        command += ['-S', '127.0.0.1:%s' % self.port, str(self.folder / 'router.php')]
        self.command = command
        self.log = (self.folder / 'php.log').open('w', encoding='utf-8')
        self.process = subprocess.Popen(command, cwd=self.folder, stdout=self.log, stderr=self.log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.base = 'http://127.0.0.1:%s/index.php?action=' % self.port
        for _ in range(50):
            try:
                self.request('status')
                break
            except Exception:
                time.sleep(.1)
        else:
            self.close()
            raise RuntimeError('PHP test API failed to start')

    def request(self, action, data=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = Request(self.base + action, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            with urlopen(req, timeout=15) as response:
                result = json.load(response)
        except HTTPError as exc:
            with exc:
                result = json.load(exc)
        if not result.get('success'):
            raise RuntimeError(result.get('error_code') or result)
        return result.get('data', {})

    def login(self, device):
        return self.request('login', {'email': self.email, 'password': self.password, 'device_id': device})['api_key']

    def exchange(self, device, token, operations=None, **kwargs):
        return self.request('sync_exchange', dict(device_id=device, device_name='Kodi ' + device, operations=operations or [], **kwargs), token)

    def seed_legacy(self):
        code = '''
$p = new PDO(getenv('XVAULT_TEST_MYSQL_DSN') ?: 'sqlite:' . $argv[2], getenv('XVAULT_TEST_MYSQL_USER') ?: null, getenv('XVAULT_TEST_MYSQL_PASSWORD') ?: null, [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$q=$p->prepare('SELECT id FROM users WHERE email=?'); $q->execute([$argv[1]]); $id=(int)$q->fetchColumn();
foreach ([0,1] as $deleted) {
    $q=$p->prepare('INSERT INTO favorites_items (user_id,key_hash,label,thumb,path,sort_order,is_deleted,revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)');
    $q->execute([$id,hash('sha256','legacy-favorite-'.$deleted),'Legacy '.$deleted,'','plugin://plugin.video.xvault/?legacy='.$deleted,1,$deleted,1,'2026-01-01','2026-01-01']);
}
foreach (['xvault','xvault-manual'] as $provider) {
    $item=['item_key'=>hash('sha256',$provider),'title'=>'Legacy movie','name'=>'Legacy movie (2026)','year'=>'2026','position_seconds'=>1200,'duration_seconds'=>7200,'completed'=>false,'provider'=>$provider,'updated_at'=>'2026-01-01','extra'=>['mediatype'=>'movie','tmdb_id'=>'1234']];
    if ($provider==='xvault-manual') $item['watch_state']='unwatched';
    $q=$p->prepare('INSERT INTO binge_state (user_id,item_key,data_json,created_at,updated_at) VALUES (?,?,?,?,?)');
    $q->execute([$id,$item['item_key'],json_encode($item),'2026-01-01','2026-01-01']);
}
'''
        command = self.command[:self.command.index('-S')] + ['-r', code, self.email, str(self.folder / 'test.sqlite')]
        subprocess.run(command, capture_output=True, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def close(self):
        self.process.terminate()
        self.process.wait(timeout=10)
        self.log.close()
        if self.temp:
            self.temp.cleanup()


def operation(key='favorite', kind='favorite', base=-1, patch=None, **kwargs):
    return dict(id=str(uuid.uuid4()), kind=kind, key=hashlib.sha256(key.encode()).hexdigest(), base_revision=base,
                patch=patch if patch is not None else {'label': key, 'path': 'plugin://plugin.video.xvault/?test=' + key, 'order': 1}, **kwargs)


class DeviceProtocolTests(unittest.TestCase):
    def setUp(self):
        self.api = LocalAPI()
        self.addCleanup(self.api.close)
        self.tokens = {d: self.api.login(d) for d in 'ABCDE'}

    def exchange(self, device, ops=None, **kwargs):
        return self.api.exchange(device, self.tokens[device], ops, **kwargs)

    def test_five_logins_keep_each_other_and_legacy_login_valid(self):
        for device in 'ABCDE':
            self.assertEqual(self.exchange(device)['protocol'], 2)
        self.api.exchange('legacy', 'legacy-test-key')
        self.api.login('B')
        self.assertEqual(self.exchange('A')['protocol'], 2)

    def test_a_b_a_handoff_and_journal(self):
        first = operation()
        a = self.exchange('A', [first])
        b = self.exchange('B')
        self.assertEqual(a['entities'], b['entities'])
        changed = operation(base=b['revision'], patch={'label': 'Changed on B'})
        self.exchange('B', [changed])
        state = self.exchange('A')
        self.assertEqual(state['entities'][0]['data']['label'], 'Changed on B')
        self.assertEqual({e['device_id'] for e in state['activity']}, {'A', 'B'})

    def test_concurrent_independent_edits_and_same_field_conflict(self):
        original = self.exchange('A', [operation()])
        rev = original['revision']
        self.exchange('A', [operation(base=rev, patch={'label': 'A'})])
        b = self.exchange('B', [operation(base=rev, patch={'thumb': 'B'})])
        self.assertEqual(b['results'][0]['status'], 'accepted')
        c = self.exchange('C', [operation(base=rev, patch={'label': 'C'})])
        self.assertEqual(c['results'][0]['status'], 'conflict')
        self.assertEqual(c['entities'][0]['data']['label'], 'A')
        self.assertEqual(c['entities'][0]['data']['thumb'], 'B')
        conflict = c['conflicts'][0]
        d = self.exchange('D', [operation(base=c['revision'], patch={'label': 'C'}, resolves=conflict['operation_id'])])
        self.assertFalse(d['conflicts'])
        self.assertEqual(d['entities'][0]['data']['label'], 'C')

    def test_deletion_tombstone_and_explicit_restore(self):
        a = self.exchange('A', [operation()])
        b = self.exchange('B', [operation(base=a['revision'], patch={}, deleted=True)])
        c = self.exchange('C', [operation(base=a['revision'])])
        self.assertEqual(c['results'][0]['status'], 'conflict')
        self.assertTrue(c['entities'][0]['deleted'])
        restored = self.exchange('A', [operation(base=b['revision'])])
        self.assertFalse(restored['entities'][0]['deleted'])

    def test_lost_response_retries_are_idempotent(self):
        op = operation()
        first = self.exchange('A', [op])
        retry = self.exchange('A', [op])
        self.assertEqual(retry['revision'], first['revision'])
        self.assertEqual(len(retry['activity']), 1)

    def test_five_parallel_writers_preserve_all_entries(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda d: self.exchange(d, [operation(key=d)]), 'ABCDE'))
        final = self.exchange('A')
        self.assertEqual(len(final['entities']), 5)
        self.assertEqual(final['revision'], 5)
        self.assertEqual(len({r['revision'] for r in results}), 5)

    @unittest.skipUnless(os.getenv('XVAULT_TEST_MYSQL_DSN'), 'Real row-lock concurrency requires MariaDB/MySQL')
    def test_five_independent_php_processes_share_database_lock(self):
        bases = [self.api.base]
        for _ in range(4):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            command = list(self.api.command)
            command[command.index('-S') + 1] = '127.0.0.1:%s' % port
            proc = subprocess.Popen(command, cwd=self.api.folder, stdout=self.api.log, stderr=self.api.log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            def cleanup(proc=proc):
                proc.terminate()
                proc.wait(timeout=10)
            self.addCleanup(cleanup)
            for _ in range(50):
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=.1):
                        break
                except OSError:
                    time.sleep(.1)
            bases.append('http://127.0.0.1:%s/index.php?action=' % port)
        barrier = threading.Barrier(5)
        def send(args):
            base, device, op = args
            barrier.wait(timeout=10)
            req = Request(base + 'sync_exchange', data=json.dumps({'device_id': device, 'operations': [op]}).encode(), headers={'Authorization': 'Bearer ' + self.tokens[device], 'Content-Type': 'application/json'})
            with urlopen(req, timeout=20) as response:
                reply = json.load(response)
                self.assertTrue(reply['success'], reply)
                return reply['data']
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(send, [(base, d, operation(d)) for base, d in zip(bases, 'ABCDE')]))
        self.assertEqual(self.exchange('A')['revision'], 5)
        self.assertEqual(len({r['revision'] for r in results}), 5)
        # All writers saw revision 5; only one may change A.label.
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(send, [(base, d, operation('A', base=5, patch={'label': d + ' wins'})) for base, d in zip(bases, 'ABCDE')]))
        self.assertEqual(sum(r['results'][0]['status'] == 'accepted' for r in results), 1)
        self.assertEqual(sum(r['results'][0]['status'] == 'conflict' for r in results), 4)

    def test_playback_sessions_preserved_conflict_and_clock_independence(self):
        key = hashlib.sha256(b'film').hexdigest()
        def progress(session, sequence, position, base=-1, clock='2099-01-01'):
            return operation('film', 'progress', base, {'value': dict(item_key=key, session_id=session, sequence=sequence, position_seconds=position, updated_at=clock)})
        a = self.exchange('A', [progress('a', 1, 100)])
        b = self.exchange('B', [progress('b', 1, 200)])
        self.assertEqual(b['results'][0]['status'], 'conflict')
        a2 = self.exchange('A', [progress('a', 2, 50, clock='1999-01-01')])
        self.assertEqual(a2['entities'][0]['data']['value']['position_seconds'], 50)
        late = self.exchange('A', [progress('a', 1, 900)])
        self.assertEqual(late['entities'][0]['data']['value']['position_seconds'], 50)
        self.assertEqual(late['revision'], a2['revision'])
        self.assertEqual(len(late['conflicts']), 1)

    def test_device_binding_revocation_and_password_reset(self):
        self.exchange('A')
        with self.assertRaisesRegex(RuntimeError, 'DEVICE_MISMATCH'):
            self.api.exchange('clone', self.tokens['A'])
        self.exchange('B', revoke_device='A')
        with self.assertRaisesRegex(RuntimeError, 'UNAUTHORIZED'):
            self.exchange('A')
        self.api.request('password_reset', {'email': self.api.email})
        for device in 'BCDE':
            with self.assertRaisesRegex(RuntimeError, 'UNAUTHORIZED'):
                self.exchange(device)

    def test_legacy_writes_blocked_after_migration(self):
        self.exchange('A')
        with self.assertRaisesRegex(RuntimeError, 'CLIENT_UPDATE_REQUIRED'):
            self.api.request('binge_push', {'items': []}, self.tokens['B'])

    def test_watch_state_conflicts_ignore_client_clock_and_redundant_marks(self):
        key = hashlib.sha256(b'film').hexdigest()
        def mark(watched, base=-1, clock='2099-01-01'):
            return operation('film', 'watch', base, {'value': dict(item_key=key, completed=watched, updated_at=clock)})
        first = self.exchange('A', [mark(True)])
        redundant = self.exchange('B', [mark(True, clock='1999-01-01')])
        self.assertEqual(redundant['revision'], first['revision'])
        self.assertFalse(redundant['conflicts'])
        reset = self.exchange('B', [mark(False, first['revision'])])
        stale = self.exchange('A', [mark(True, first['revision'])])
        self.assertEqual(stale['results'][0]['status'], 'conflict')
        self.assertFalse(stale['entities'][0]['data']['value']['completed'])

    def test_migration_preserves_favorites_tombstones_progress_and_manual_state(self):
        self.api.seed_legacy()
        state = self.exchange('A')
        self.assertEqual(len(state['entities']), 4)
        favorites = [e for e in state['entities'] if e['kind'] == 'favorite']
        self.assertEqual(sum(e['deleted'] for e in favorites), 1)
        key = hashlib.sha256(b'movie:tmdb:1234::').hexdigest()
        progress = next(e for e in state['entities'] if e['kind'] == 'progress')
        watch = next(e for e in state['entities'] if e['kind'] == 'watch')
        self.assertEqual(progress['key'], key)
        self.assertEqual(watch['key'], key)
        self.assertEqual(progress['data']['value']['position_seconds'], 1200)
        self.assertEqual(watch['data']['value']['watch_state'], 'unwatched')


if __name__ == '__main__':
    unittest.main()
