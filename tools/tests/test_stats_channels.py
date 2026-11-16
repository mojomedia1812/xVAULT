import json
from pathlib import Path
import shutil
import subprocess
import unittest

from tools.upgrade_stats_dashboard import upgrade

ROOT = Path(__file__).resolve().parents[2]


class StatsChannelsTests(unittest.TestCase):
    def php(self, body):
        php = shutil.which('php')
        if not php:
            self.skipTest('PHP unavailable')
        command = [php]
        extension = Path(php).parent / 'ext/php_pdo_sqlite.dll'
        if extension.exists():
            command += ['-d', 'extension=' + str(extension)]
        code = "<?php require " + json.dumps(str(ROOT / 'api/stats/version_stats.php')) + ';' + body
        p = subprocess.run(command, input=code, text=True, capture_output=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_channels_include_old_clients_alpha_and_invalid_versions(self):
        rows = [
            ['2026.11.01.1', 'stable', 'plugin.video.xvault'],
            ['2026.11.16.3', 'stable', 'plugin.video.xvault'],
            ['2026.11.16.3', 'alpha', 'plugin.video.xvault'],
            ['2026.11.16.1', 'stable', 'plugin.video.xvaultalpha'],
            ['Alpha 2026.11.16.2', '', ''],
            ['2026.07.23.3', 'stable', 'plugin.video.xvault'],
            ['2026.11.31.2', '', ''], ['', '', ''],
        ]
        result = self.php('$rows=json_decode(' + json.dumps(json.dumps(rows)) + ',true);'
                          'echo json_encode(array_map(fn($r)=>xvault_stats_channel(...$r),$rows));')
        self.assertEqual(result, ['Release', 'Nightly', 'Alpha', 'Alpha', 'Alpha', 'Release', 'Unbekannt', 'Unbekannt'])

    def test_all_versions_aggregate_variants_sort_numerically_and_escape_html(self):
        data = self.php('''
            $pdo=new PDO('sqlite::memory:');
            $pdo->exec('CREATE TABLE telemetry_installations(current_addon_version TEXT, addon_variant TEXT, current_addon_id TEXT,last_seen_at TEXT)');
            $q=$pdo->prepare('INSERT INTO telemetry_installations VALUES (?,?,?,?)');
            for($i=1;$i<=30;$i++) $q->execute(['2026.11.16.'.$i,'stable','plugin.video.xvault','2026-11-16 12:00:00']);
            $q->execute(['2026.11.16.3','','plugin.video.xvault','2026-11-16 13:00:00']);
            $q->execute(['2026.11.16.3','alpha','plugin.video.xvaultalpha','2026-11-16 14:00:00']);
            $q->execute(['<script>alert(1)</script>','','','2026-11-16 14:00:00']);
            $data=xvault_stats_versions($pdo);
            echo json_encode(['data'=>$data,'html'=>xvault_stats_versions_html($data['versions'])]);
        ''')
        versions = data['data']['versions']
        self.assertEqual(len(versions), 32)
        numeric = [r['version'] for r in versions if r['channel'] == 'Nightly']
        self.assertEqual(numeric[0], '2026.11.16.30')
        row = next(r for r in versions if r['version'] == '2026.11.16.3' and r['channel'] == 'Nightly')
        self.assertEqual(row['installations'], 2)
        self.assertEqual(row['last_seen'], '2026-11-16 13:00:00')
        channels = {r['label']: r['value'] for r in data['data']['channels']}
        self.assertEqual(channels, dict(Release=1, Nightly=30, Alpha=1, Unbekannt=1))
        self.assertNotIn('<script>', data['html'])
        self.assertIn('&lt;script&gt;', data['html'])

    def test_dashboard_upgrade_preserves_auth_and_is_idempotent(self):
        auth = "<?php const DASHBOARD_PASSWORD_HASH = 'test-placeholder';\nif (!$authorized) exit;\n"
        original = auth + '''$versionRows = query_rows($pdo, "SELECT version LIMIT 20");
$variantRows = query_rows($pdo, "SELECT variant");
<?= table_block('Varianten', $variantRows) ?>
<?= table_block('xVAULT-Versionen', $versionRows) ?>'''
        updated = upgrade(original)
        self.assertTrue(updated.startswith(auth))
        self.assertNotIn('LIMIT 20', updated)
        self.assertIn('Release / Nightly / Alpha', updated)
        self.assertEqual(updated, upgrade(updated))
        with self.assertRaises(ValueError):
            upgrade('<?php unexpected_layout();')


if __name__ == '__main__':
    unittest.main()
