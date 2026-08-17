<?php
declare(strict_types=1);

$configFile = __DIR__ . '/config.php';
if (!is_file($configFile)) {
    $configFile = __DIR__ . '/config.example.php';
}
$config = require $configFile;

date_default_timezone_set($config['timezone'] ?? 'Europe/Berlin');
ini_set('display_errors', '0');

if (!empty($config['cors_origin'])) {
    header('Access-Control-Allow-Origin: ' . $config['cors_origin']);
    header('Access-Control-Allow-Headers: Authorization, Content-Type, X-API-Key');
    header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
}
header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    respond(true, 'OK');
}

try {
    $pdo = db($config);
    ensure_schema($pdo);
    dispatch($pdo, $config);
} catch (Throwable $e) {
    log_error('SERVER_ERROR: ' . $e->getMessage());
    respond(false, 'Serverfehler', null, 'SERVER_ERROR', 500);
}

function db(array $config): PDO
{
    $dsn = sprintf(
        'mysql:host=%s;dbname=%s;charset=utf8mb4',
        $config['db_host'] ?? 'localhost',
        $config['db_name'] ?? ''
    );
    return new PDO($dsn, $config['db_user'] ?? '', $config['db_pass'] ?? '', [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
}

function ensure_schema(PDO $pdo): void
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        api_key_hash CHAR(64) DEFAULT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        last_login_at DATETIME DEFAULT NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS favorites_backups (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        device_id VARCHAR(128) DEFAULT NULL,
        data_json LONGTEXT NOT NULL,
        data_hash CHAR(64) NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        INDEX idx_user_id (user_id),
        INDEX idx_data_hash (data_hash)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS favorites_sync_meta (
        user_id INT NOT NULL PRIMARY KEY,
        revision BIGINT NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS favorites_items (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        key_hash CHAR(64) NOT NULL,
        label VARCHAR(512) DEFAULT NULL,
        thumb TEXT DEFAULT NULL,
        path TEXT DEFAULT NULL,
        item_hash CHAR(64) DEFAULT NULL,
        sort_order INT NOT NULL DEFAULT 0,
        is_deleted TINYINT(1) NOT NULL DEFAULT 0,
        revision BIGINT NOT NULL,
        device_id VARCHAR(128) DEFAULT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE KEY uniq_favorites_user_key (user_id, key_hash),
        INDEX idx_favorites_user_revision (user_id, revision),
        INDEX idx_favorites_user_active (user_id, is_deleted, sort_order)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS binge_state (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        device_id VARCHAR(128) DEFAULT NULL,
        item_key VARCHAR(512) NOT NULL,
        title VARCHAR(512) DEFAULT NULL,
        season INT DEFAULT NULL,
        episode INT DEFAULT NULL,
        position_seconds INT DEFAULT NULL,
        duration_seconds INT DEFAULT NULL,
        watched_percent DECIMAL(5,2) DEFAULT NULL,
        completed TINYINT(1) NOT NULL DEFAULT 0,
        provider VARCHAR(255) DEFAULT NULL,
        data_json LONGTEXT DEFAULT NULL,
        updated_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE KEY uniq_user_item (user_id, item_key),
        INDEX idx_user_updated (user_id, updated_at)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS sync_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        device_id VARCHAR(128) DEFAULT NULL,
        sync_type VARCHAR(64) NOT NULL,
        direction VARCHAR(16) NOT NULL,
        status VARCHAR(32) NOT NULL,
        message VARCHAR(512) DEFAULT NULL,
        created_at DATETIME NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        INDEX idx_user_created (user_id, created_at)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS telemetry_installations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        install_hash CHAR(64) NOT NULL UNIQUE,
        first_seen_at DATETIME NOT NULL,
        last_seen_at DATETIME NOT NULL,
        current_addon_id VARCHAR(64) DEFAULT NULL,
        addon_variant VARCHAR(32) DEFAULT NULL,
        current_addon_version VARCHAR(32) DEFAULT NULL,
        current_kodi_version VARCHAR(64) DEFAULT NULL,
        os_family VARCHAR(64) DEFAULT NULL,
        os_version VARCHAR(128) DEFAULT NULL,
        device_class VARCHAR(64) DEFAULT NULL,
        hardware_family VARCHAR(128) DEFAULT NULL,
        cpu_arch VARCHAR(64) DEFAULT NULL,
        telemetry_consent_version VARCHAR(32) DEFAULT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        INDEX idx_telemetry_install_last_seen (last_seen_at),
        INDEX idx_telemetry_install_device (device_class),
        INDEX idx_telemetry_install_os (os_family)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS telemetry_sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        installation_id INT NOT NULL,
        session_hash CHAR(64) NOT NULL UNIQUE,
        started_at DATETIME NOT NULL,
        last_heartbeat_at DATETIME NOT NULL,
        ended_at DATETIME DEFAULT NULL,
        duration_seconds INT NOT NULL DEFAULT 0,
        addon_id VARCHAR(64) DEFAULT NULL,
        addon_variant VARCHAR(32) DEFAULT NULL,
        addon_version VARCHAR(32) DEFAULT NULL,
        kodi_version VARCHAR(64) DEFAULT NULL,
        os_family VARCHAR(64) DEFAULT NULL,
        os_version VARCHAR(128) DEFAULT NULL,
        device_class VARCHAR(64) DEFAULT NULL,
        hardware_family VARCHAR(128) DEFAULT NULL,
        cpu_arch VARCHAR(64) DEFAULT NULL,
        end_reason VARCHAR(64) DEFAULT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        FOREIGN KEY (installation_id) REFERENCES telemetry_installations(id) ON DELETE CASCADE,
        INDEX idx_telemetry_session_install (installation_id),
        INDEX idx_telemetry_session_seen (last_heartbeat_at)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS telemetry_events (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        installation_id INT NOT NULL,
        session_id INT DEFAULT NULL,
        event_name VARCHAR(64) NOT NULL,
        event_group VARCHAR(64) DEFAULT NULL,
        occurred_at DATETIME NOT NULL,
        addon_id VARCHAR(64) DEFAULT NULL,
        addon_variant VARCHAR(32) DEFAULT NULL,
        addon_version VARCHAR(32) DEFAULT NULL,
        kodi_version VARCHAR(64) DEFAULT NULL,
        os_family VARCHAR(64) DEFAULT NULL,
        os_version VARCHAR(128) DEFAULT NULL,
        device_class VARCHAR(64) DEFAULT NULL,
        source_name VARCHAR(32) DEFAULT NULL,
        source_event_id BIGINT DEFAULT NULL,
        client_event_id VARCHAR(128) DEFAULT NULL,
        payload_json TEXT DEFAULT NULL,
        created_at DATETIME NOT NULL,
        FOREIGN KEY (installation_id) REFERENCES telemetry_installations(id) ON DELETE CASCADE,
        FOREIGN KEY (session_id) REFERENCES telemetry_sessions(id) ON DELETE SET NULL,
        UNIQUE KEY uniq_telemetry_source_event (source_name, source_event_id),
        INDEX idx_telemetry_event_name (event_name),
        INDEX idx_telemetry_event_created (created_at),
        INDEX idx_telemetry_event_install (installation_id)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS telemetry_event_rollups (
        bucket_type VARCHAR(16) NOT NULL,
        bucket_start DATETIME NOT NULL,
        event_name VARCHAR(64) NOT NULL,
        event_group VARCHAR(64) NOT NULL DEFAULT '',
        addon_id VARCHAR(64) NOT NULL DEFAULT '',
        addon_variant VARCHAR(32) NOT NULL DEFAULT '',
        addon_version VARCHAR(32) NOT NULL DEFAULT '',
        kodi_version VARCHAR(64) NOT NULL DEFAULT '',
        os_family VARCHAR(64) NOT NULL DEFAULT '',
        os_version VARCHAR(128) NOT NULL DEFAULT '',
        device_class VARCHAR(64) NOT NULL DEFAULT '',
        event_count INT NOT NULL DEFAULT 0,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (bucket_type, bucket_start, event_name, event_group, addon_id, addon_variant, addon_version, kodi_version, os_family, os_version, device_class)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS telemetry_online_rollups (
        bucket_start DATETIME NOT NULL PRIMARY KEY,
        max_online INT NOT NULL DEFAULT 0,
        updated_at DATETIME NOT NULL
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS telemetry_daily_stats (
        stat_date DATE NOT NULL,
        event_name VARCHAR(64) NOT NULL,
        addon_version VARCHAR(32) NOT NULL DEFAULT '',
        os_family VARCHAR(64) NOT NULL DEFAULT '',
        device_class VARCHAR(64) NOT NULL DEFAULT '',
        unique_installations INT NOT NULL DEFAULT 0,
        session_count INT NOT NULL DEFAULT 0,
        event_count INT NOT NULL DEFAULT 0,
        total_runtime_seconds BIGINT NOT NULL DEFAULT 0,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (stat_date, event_name, addon_version, os_family, device_class)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    ensure_column($pdo, 'telemetry_installations', 'current_addon_id', "VARCHAR(64) DEFAULT NULL");
    ensure_column($pdo, 'telemetry_installations', 'addon_variant', "VARCHAR(32) DEFAULT NULL");
    ensure_column($pdo, 'telemetry_sessions', 'addon_id', "VARCHAR(64) DEFAULT NULL");
    ensure_column($pdo, 'telemetry_sessions', 'addon_variant', "VARCHAR(32) DEFAULT NULL");
    ensure_column($pdo, 'telemetry_events', 'addon_id', "VARCHAR(64) DEFAULT NULL");
    ensure_column($pdo, 'telemetry_events', 'addon_variant', "VARCHAR(32) DEFAULT NULL");
    ensure_column($pdo, 'telemetry_events', 'os_version', "VARCHAR(128) DEFAULT NULL");
    ensure_column($pdo, 'telemetry_events', 'source_name', "VARCHAR(32) DEFAULT NULL");
    ensure_column($pdo, 'telemetry_events', 'source_event_id', "BIGINT DEFAULT NULL");
    ensure_column($pdo, 'telemetry_events', 'client_event_id', "VARCHAR(128) DEFAULT NULL");
    ensure_unique_index($pdo, 'telemetry_events', 'uniq_telemetry_source_event', ['source_name', 'source_event_id']);
}

function ensure_column(PDO $pdo, string $table, string $column, string $definition): void
{
    try {
        $stmt = $pdo->prepare('SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = ? AND column_name = ?');
        $stmt->execute([$table, $column]);
        if ((int)$stmt->fetchColumn() > 0) {
            return;
        }
        $pdo->exec("ALTER TABLE `$table` ADD COLUMN `$column` $definition");
    } catch (Throwable $e) {
        log_error('SCHEMA_COLUMN_ERROR: ' . $table . '.' . $column . ': ' . $e->getMessage());
    }
}

function ensure_unique_index(PDO $pdo, string $table, string $index, array $columns): void
{
    try {
        $stmt = $pdo->prepare('SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = ? AND index_name = ?');
        $stmt->execute([$table, $index]);
        if ((int)$stmt->fetchColumn() > 0) {
            return;
        }
        $parts = array_map(fn($column) => "`$column`", $columns);
        $pdo->exec("ALTER TABLE `$table` ADD UNIQUE KEY `$index` (" . implode(',', $parts) . ")");
    } catch (Throwable $e) {
        log_error('SCHEMA_INDEX_ERROR: ' . $table . '.' . $index . ': ' . $e->getMessage());
    }
}

function dispatch(PDO $pdo, array $config): void
{
    $action = action_name();
    if ($action === 'status') {
        respond(true, 'OK', ['service' => 'xVAULT Sync API', 'time' => now()]);
    }
    if ($action === 'register') {
        require_method('POST');
        register_user($pdo, input_json());
    }
    if ($action === 'login') {
        require_method('POST');
        login_user($pdo, input_json());
    }
    if ($action === 'password_reset') {
        require_method('POST');
        reset_password($pdo, input_json());
    }
    if ($action === 'telemetry') {
        require_method('POST');
        telemetry_ingest($pdo, input_json(), $config);
    }

    $user = require_user($pdo);
    switch ($action) {
        case 'favorites_push':
            require_method('POST');
            favorites_push($pdo, $user, input_json());
            break;
        case 'favorites_pull':
            favorites_pull($pdo, $user);
            break;
        case 'favorites_delta':
            require_method('POST');
            favorites_delta($pdo, $user, input_json());
            break;
        case 'favorites_state':
            favorites_state($pdo, $user);
            break;
        case 'binge_push':
            require_method('POST');
            binge_push($pdo, $user, input_json());
            break;
        case 'binge_pull':
            binge_pull($pdo, $user);
            break;
        case 'sync_push':
            require_method('POST');
            sync_push($pdo, $user, input_json());
            break;
        case 'sync_pull':
            sync_pull($pdo, $user);
            break;
        default:
            respond(false, 'Unbekannter Endpunkt', null, 'NOT_FOUND', 404);
    }
}

function action_name(): string
{
    if (!empty($_GET['action'])) {
        return str_replace('-', '_', (string)$_GET['action']);
    }
    $path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
    $path = trim($path, '/');
    $path = preg_replace('#^api/#', '', $path);
    $map = [
        'register' => 'register',
        'login' => 'login',
        'password/reset' => 'password_reset',
        'password-reset' => 'password_reset',
        'status' => 'status',
        'favorites/push' => 'favorites_push',
        'favorites/pull' => 'favorites_pull',
        'favorites/delta' => 'favorites_delta',
        'favorites/state' => 'favorites_state',
        'binge/push' => 'binge_push',
        'binge/pull' => 'binge_pull',
        'sync/push' => 'sync_push',
        'sync/pull' => 'sync_pull',
        'telemetry' => 'telemetry',
    ];
    return $map[$path] ?? 'status';
}

function input_json(): array
{
    $raw = file_get_contents('php://input') ?: '';
    if ($raw === '') {
        return [];
    }
    $data = json_decode($raw, true);
    if (!is_array($data)) {
        respond(false, 'Ungueltige JSON-Anfrage', null, 'INVALID_JSON', 400);
    }
    return $data;
}

function register_user(PDO $pdo, array $data): void
{
    [$email, $password] = credentials($data);
    $stmt = $pdo->prepare('SELECT id FROM users WHERE email = ?');
    $stmt->execute([$email]);
    if ($stmt->fetch()) {
        respond(false, 'E-Mail-Adresse ist bereits registriert', null, 'EMAIL_EXISTS', 409);
    }

    $apiKey = bin2hex(random_bytes(32));
    $now = now();
    $stmt = $pdo->prepare('INSERT INTO users (email, password_hash, api_key_hash, created_at, updated_at, last_login_at) VALUES (?, ?, ?, ?, ?, ?)');
    $stmt->execute([
        $email,
        password_hash($password, PASSWORD_DEFAULT),
        hash('sha256', $apiKey),
        $now,
        $now,
        $now,
    ]);
    respond(true, 'Registrierung erfolgreich', ['email' => $email, 'api_key' => $apiKey]);
}

function login_user(PDO $pdo, array $data): void
{
    [$email, $password] = credentials($data);
    $stmt = $pdo->prepare('SELECT * FROM users WHERE email = ? AND is_active = 1');
    $stmt->execute([$email]);
    $user = $stmt->fetch();
    if (!$user || !password_verify($password, $user['password_hash'])) {
        respond(false, 'Ungueltige Zugangsdaten', null, 'INVALID_LOGIN', 401);
    }

    $apiKey = bin2hex(random_bytes(32));
    $now = now();
    $stmt = $pdo->prepare('UPDATE users SET api_key_hash = ?, updated_at = ?, last_login_at = ? WHERE id = ?');
    $stmt->execute([hash('sha256', $apiKey), $now, $now, $user['id']]);
    respond(true, 'Anmeldung erfolgreich', ['email' => $email, 'api_key' => $apiKey]);
}

function reset_password(PDO $pdo, array $data): void
{
    $email = strtolower(trim((string)($data['email'] ?? '')));
    if ($email === '') {
        respond(false, 'E-Mail-Adresse ist erforderlich', null, 'MISSING_FIELDS', 400);
    }
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        respond(false, 'Ungueltige E-Mail-Adresse', null, 'INVALID_EMAIL', 400);
    }
    $stmt = $pdo->prepare('SELECT * FROM users WHERE email = ? AND is_active = 1');
    $stmt->execute([$email]);
    $user = $stmt->fetch();
    if (!$user) {
        respond(false, 'Diese E-Mail-Adresse ist nicht registriert', null, 'EMAIL_NOT_FOUND', 404);
    }

    $password = generate_password(9);
    $now = now();
    $stmt = $pdo->prepare('UPDATE users SET password_hash = ?, api_key_hash = NULL, updated_at = ? WHERE id = ?');
    $stmt->execute([password_hash($password, PASSWORD_DEFAULT), $now, $user['id']]);
    respond(true, 'Neues Kennwort wurde erstellt', ['email' => $email, 'password' => $password]);
}

function generate_password(int $length): string
{
    $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';
    $password = '';
    $max = strlen($chars) - 1;
    for ($index = 0; $index < $length; $index++) {
        $password .= $chars[random_int(0, $max)];
    }
    return $password;
}

function credentials(array $data): array
{
    $email = strtolower(trim((string)($data['email'] ?? '')));
    $password = (string)($data['password'] ?? '');
    if ($email === '' || $password === '') {
        respond(false, 'E-Mail und Kennwort sind erforderlich', null, 'MISSING_FIELDS', 400);
    }
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        respond(false, 'Ungueltige E-Mail-Adresse', null, 'INVALID_EMAIL', 400);
    }
    if (strlen($password) < 8) {
        respond(false, 'Kennwort muss mindestens 8 Zeichen haben', null, 'WEAK_PASSWORD', 400);
    }
    return [$email, $password];
}

function require_user(PDO $pdo): array
{
    $key = bearer_key();
    if ($key === '') {
        $body = input_json();
        $key = (string)($body['api_key'] ?? '');
    }
    if ($key === '') {
        respond(false, 'Nicht angemeldet', null, 'UNAUTHORIZED', 401);
    }
    $stmt = $pdo->prepare('SELECT * FROM users WHERE api_key_hash = ? AND is_active = 1');
    $stmt->execute([hash('sha256', $key)]);
    $user = $stmt->fetch();
    if (!$user) {
        respond(false, 'Nicht angemeldet', null, 'UNAUTHORIZED', 401);
    }
    return $user;
}

function bearer_key(): string
{
    $headers = function_exists('getallheaders') ? getallheaders() : [];
    $auth = $headers['Authorization'] ?? $headers['authorization'] ?? ($_SERVER['HTTP_AUTHORIZATION'] ?? '');
    if (preg_match('/Bearer\s+(.+)/i', $auth, $match)) {
        return trim($match[1]);
    }
    return trim((string)($headers['X-API-Key'] ?? $headers['x-api-key'] ?? ($_SERVER['HTTP_X_API_KEY'] ?? '')));
}

function latest_favorites_payload(PDO $pdo, int $userId): ?array
{
    $stmt = $pdo->prepare('SELECT data_json FROM favorites_backups WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1');
    $stmt->execute([$userId]);
    $row = $stmt->fetch();
    if (!$row) {
        return null;
    }
    $payload = json_decode($row['data_json'], true);
    return is_array($payload) ? $payload : null;
}

function replace_favorites_payload(PDO $pdo, int $userId, ?string $deviceId, array $payload, string $now): array
{
    $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    $hash = hash('sha256', $json);

    $pdo->beginTransaction();
    try {
        $delete = $pdo->prepare('DELETE FROM favorites_backups WHERE user_id = ?');
        $delete->execute([$userId]);

        $insert = $pdo->prepare('INSERT INTO favorites_backups (user_id, device_id, data_json, data_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)');
        $insert->execute([$userId, $deviceId, $json, $hash, $now, $now]);

        $pdo->commit();
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        throw $e;
    }

    return ['data_hash' => $hash, 'updated_at' => $now];
}

function merge_favorites_payload(?array $serverPayload, array $incomingPayload, array $deletedKeys, ?string $deviceId): array
{
    $removed = array_fill_keys($deletedKeys, true);
    $entries = [];
    foreach (array_merge(favorites_payload_entries($incomingPayload), favorites_payload_entries($serverPayload)) as $entry) {
        $key = favorite_entry_key($entry);
        if ($key === '' || isset($removed[$key]) || isset($entries[$key])) {
            continue;
        }
        $entries[$key] = $entry;
    }

    $mergedEntries = array_values($entries);
    $payload = $incomingPayload;
    unset($payload['deleted_keys'], $payload['removed_keys'], $payload['base_keys']);
    $payload['schema_version'] = 1;
    $payload['source'] = $payload['source'] ?? 'kodi_favourites';
    $payload['device_id'] = $deviceId;
    $payload['updated_at'] = now();
    $payload['raw_xml'] = build_favorites_xml($mergedEntries);
    $payload['items'] = favorites_items_from_entries($mergedEntries);
    $payload['favorites_hash'] = hash('sha256', trim(str_replace("\r\n", "\n", $payload['raw_xml'])));
    return $payload;
}

function favorites_payload_entries(?array $payload): array
{
    if (!is_array($payload)) {
        return [];
    }
    $entries = [];
    $raw = (string)($payload['raw_xml'] ?? '');
    if (trim($raw) !== '' && function_exists('simplexml_load_string')) {
        $xml = @simplexml_load_string($raw);
        if ($xml !== false) {
            foreach ($xml->favourite as $node) {
                $entries[] = [
                    'label' => isset($node['name']) ? (string)$node['name'] : '',
                    'thumb' => isset($node['thumb']) ? (string)$node['thumb'] : '',
                    'path' => trim((string)$node),
                ];
            }
        }
    }
    if (!$entries && isset($payload['items']) && is_array($payload['items'])) {
        foreach ($payload['items'] as $item) {
            if (!is_array($item)) {
                continue;
            }
            $entries[] = [
                'label' => (string)($item['label'] ?? ''),
                'thumb' => (string)($item['thumb'] ?? ''),
                'path' => (string)($item['path'] ?? ''),
            ];
        }
    }
    return dedupe_favorite_entries($entries);
}

function deleted_favorite_keys(array $data, array $payload): array
{
    $keys = [];
    foreach ([$data, $payload] as $source) {
        foreach (['deleted_keys', 'removed_keys'] as $field) {
            if (!isset($source[$field]) || !is_array($source[$field])) {
                continue;
            }
            foreach ($source[$field] as $key) {
                $key = trim((string)$key);
                if ($key !== '') {
                    $keys[$key] = true;
                }
            }
        }
    }
    return array_keys($keys);
}

function dedupe_favorite_entries(array $entries): array
{
    $result = [];
    $seen = [];
    foreach ($entries as $entry) {
        if (!is_array($entry)) {
            continue;
        }
        $normalized = [
            'label' => (string)($entry['label'] ?? ''),
            'thumb' => (string)($entry['thumb'] ?? ''),
            'path' => trim((string)($entry['path'] ?? '')),
        ];
        $key = favorite_entry_key($normalized);
        if ($key === '' || isset($seen[$key])) {
            continue;
        }
        $seen[$key] = true;
        $result[] = $normalized;
    }
    return $result;
}

function favorite_entry_key(array $entry): string
{
    return trim((string)($entry['path'] ?? ($entry['label'] ?? '')));
}

function build_favorites_xml(array $entries): string
{
    $xml = "<favourites>\n";
    foreach ($entries as $entry) {
        $attrs = '';
        if (($entry['label'] ?? '') !== '') {
            $attrs .= ' name="' . xml_escape((string)$entry['label']) . '"';
        }
        if (($entry['thumb'] ?? '') !== '') {
            $attrs .= ' thumb="' . xml_escape((string)$entry['thumb']) . '"';
        }
        $xml .= '  <favourite' . $attrs . '>' . xml_escape((string)($entry['path'] ?? '')) . "</favourite>\n";
    }
    return $xml . "</favourites>\n";
}

function favorites_items_from_entries(array $entries): array
{
    $items = [];
    $order = 1;
    foreach ($entries as $entry) {
        $path = (string)($entry['path'] ?? '');
        $items[] = [
            'order' => $order++,
            'label' => (string)($entry['label'] ?? ''),
            'thumb' => (string)($entry['thumb'] ?? ''),
            'path' => $path,
            'type' => strpos($path, 'plugin.video.xvault') !== false ? 'video' : 'unknown',
        ];
    }
    return $items;
}

function xml_escape(string $value): string
{
    return htmlspecialchars($value, ENT_XML1 | ENT_QUOTES, 'UTF-8');
}

function ensure_favorites_delta_seeded(PDO $pdo, int $userId): void
{
    $stmt = $pdo->prepare('SELECT revision FROM favorites_sync_meta WHERE user_id = ? LIMIT 1');
    $stmt->execute([$userId]);
    if ($stmt->fetch()) {
        return;
    }

    $legacy = latest_favorites_payload($pdo, $userId);
    $entries = favorites_payload_entries($legacy);
    $now = now();
    $revision = 0;

    $pdo->beginTransaction();
    try {
        $insertMeta = $pdo->prepare('INSERT IGNORE INTO favorites_sync_meta (user_id, revision, created_at, updated_at) VALUES (?, 0, ?, ?)');
        $insertMeta->execute([$userId, $now, $now]);

        $check = $pdo->prepare('SELECT COUNT(*) FROM favorites_items WHERE user_id = ?');
        $check->execute([$userId]);
        if ((int)$check->fetchColumn() === 0) {
            $insert = $pdo->prepare('INSERT INTO favorites_items
                (user_id, key_hash, label, thumb, path, item_hash, sort_order, is_deleted, revision, device_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?)');
            $order = 1;
            foreach ($entries as $entry) {
                $key = favorite_key_hash($entry);
                if ($key === '') {
                    continue;
                }
                $revision++;
                $insert->execute([
                    $userId,
                    $key,
                    short_text($entry['label'] ?? null, 512),
                    (string)($entry['thumb'] ?? ''),
                    (string)($entry['path'] ?? ''),
                    favorite_item_hash($entry, $order),
                    $order++,
                    $revision,
                    $now,
                    $now,
                ]);
            }
        }
        $updateMeta = $pdo->prepare('UPDATE favorites_sync_meta SET revision = GREATEST(revision, ?), updated_at = ? WHERE user_id = ?');
        $updateMeta->execute([$revision, $now, $userId]);
        $pdo->commit();
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        throw $e;
    }
}

function favorite_key_hash(array $entry): string
{
    $key = strtolower(trim((string)($entry['key'] ?? $entry['key_hash'] ?? '')));
    if (preg_match('/^[a-f0-9]{64}$/', $key)) {
        return $key;
    }
    $source = favorite_entry_key($entry);
    return $source !== '' ? hash('sha256', $source) : '';
}

function favorite_delete_key_hash($value): string
{
    $key = strtolower(trim((string)$value));
    if (preg_match('/^[a-f0-9]{64}$/', $key)) {
        return $key;
    }
    return $key !== '' ? hash('sha256', $key) : '';
}

function favorite_item_hash(array $entry, int $order): string
{
    return hash('sha256', json_encode([
        'label' => (string)($entry['label'] ?? ''),
        'thumb' => (string)($entry['thumb'] ?? ''),
        'path' => (string)($entry['path'] ?? ''),
        'order' => $order,
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
}

function favorite_delta_entry(array $entry, int $fallbackOrder = 0): ?array
{
    $path = trim((string)($entry['path'] ?? ''));
    $key = favorite_key_hash($entry);
    if ($key === '' || $path === '') {
        return null;
    }
    $order = (int)($entry['order'] ?? $entry['sort_order'] ?? $fallbackOrder);
    return [
        'key' => $key,
        'label' => short_text($entry['label'] ?? '', 512) ?? '',
        'thumb' => (string)($entry['thumb'] ?? ''),
        'path' => $path,
        'order' => max(0, $order),
    ];
}

function favorite_lock_revision(PDO $pdo, int $userId, string $now): int
{
    $stmt = $pdo->prepare('INSERT IGNORE INTO favorites_sync_meta (user_id, revision, created_at, updated_at) VALUES (?, 0, ?, ?)');
    $stmt->execute([$userId, $now, $now]);

    $stmt = $pdo->prepare('SELECT revision FROM favorites_sync_meta WHERE user_id = ? FOR UPDATE');
    $stmt->execute([$userId]);
    $revision = $stmt->fetchColumn();
    return $revision === false ? 0 : (int)$revision;
}

function favorite_upsert_delta(PDO $pdo, int $userId, ?string $deviceId, array $entry, int $revision, string $now): void
{
    $stmt = $pdo->prepare('INSERT INTO favorites_items
        (user_id, key_hash, label, thumb, path, item_hash, sort_order, is_deleted, revision, device_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
            label = VALUES(label),
            thumb = VALUES(thumb),
            path = VALUES(path),
            item_hash = VALUES(item_hash),
            sort_order = VALUES(sort_order),
            is_deleted = 0,
            revision = VALUES(revision),
            device_id = VALUES(device_id),
            updated_at = VALUES(updated_at)');
    $stmt->execute([
        $userId,
        $entry['key'],
        short_text($entry['label'] ?? '', 512),
        (string)($entry['thumb'] ?? ''),
        (string)($entry['path'] ?? ''),
        favorite_item_hash($entry, (int)($entry['order'] ?? 0)),
        (int)($entry['order'] ?? 0),
        $revision,
        $deviceId,
        $now,
        $now,
    ]);
}

function favorite_delete_delta(PDO $pdo, int $userId, ?string $deviceId, string $key, int $revision, string $now): void
{
    $stmt = $pdo->prepare('INSERT INTO favorites_items
        (user_id, key_hash, label, thumb, path, item_hash, sort_order, is_deleted, revision, device_id, created_at, updated_at)
        VALUES (?, ?, NULL, NULL, NULL, NULL, 0, 1, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
            label = NULL,
            thumb = NULL,
            path = NULL,
            item_hash = NULL,
            sort_order = 0,
            is_deleted = 1,
            revision = VALUES(revision),
            device_id = VALUES(device_id),
            updated_at = VALUES(updated_at)');
    $stmt->execute([$userId, $key, $revision, $deviceId, $now, $now]);
}

function favorites_changes_since(PDO $pdo, int $userId, int $baseRevision): array
{
    $stmt = $pdo->prepare('SELECT key_hash, label, thumb, path, sort_order, is_deleted, revision, updated_at
        FROM favorites_items
        WHERE user_id = ? AND revision > ?
        ORDER BY revision ASC, id ASC');
    $stmt->execute([$userId, $baseRevision]);
    $changes = [];
    foreach ($stmt as $row) {
        $deleted = !empty($row['is_deleted']);
        $change = [
            'key' => $row['key_hash'],
            'deleted' => $deleted,
            'revision' => (int)$row['revision'],
            'updated_at' => $row['updated_at'],
        ];
        if (!$deleted) {
            $change['item'] = [
                'key' => $row['key_hash'],
                'label' => (string)($row['label'] ?? ''),
                'thumb' => (string)($row['thumb'] ?? ''),
                'path' => (string)($row['path'] ?? ''),
                'order' => (int)$row['sort_order'],
            ];
        }
        $changes[] = $change;
    }
    return $changes;
}

function favorites_current_revision(PDO $pdo, int $userId): int
{
    $stmt = $pdo->prepare('SELECT revision FROM favorites_sync_meta WHERE user_id = ? LIMIT 1');
    $stmt->execute([$userId]);
    $revision = $stmt->fetchColumn();
    return $revision === false ? 0 : (int)$revision;
}

function favorites_active_entries(PDO $pdo, int $userId): array
{
    $stmt = $pdo->prepare('SELECT key_hash, label, thumb, path, sort_order
        FROM favorites_items
        WHERE user_id = ? AND is_deleted = 0
        ORDER BY sort_order ASC, revision ASC, id ASC');
    $stmt->execute([$userId]);
    $entries = [];
    foreach ($stmt as $row) {
        $entries[] = [
            'key' => $row['key_hash'],
            'label' => (string)($row['label'] ?? ''),
            'thumb' => (string)($row['thumb'] ?? ''),
            'path' => (string)($row['path'] ?? ''),
            'order' => (int)$row['sort_order'],
        ];
    }
    return $entries;
}

function favorites_payload_from_delta(PDO $pdo, int $userId, ?string $deviceId = null): array
{
    $entries = [];
    foreach (favorites_active_entries($pdo, $userId) as $item) {
        $entries[] = [
            'label' => $item['label'],
            'thumb' => $item['thumb'],
            'path' => $item['path'],
        ];
    }
    $rawXml = build_favorites_xml($entries);
    return [
        'schema_version' => 2,
        'source' => 'kodi_favourites_delta',
        'device_id' => $deviceId,
        'updated_at' => now(),
        'revision' => favorites_current_revision($pdo, $userId),
        'raw_xml' => $rawXml,
        'items' => favorites_items_from_entries($entries),
        'favorites_hash' => hash('sha256', trim(str_replace("\r\n", "\n", $rawXml))),
    ];
}

function favorites_server_hash(PDO $pdo, int $userId): string
{
    $items = favorites_active_entries($pdo, $userId);
    return hash('sha256', json_encode($items, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
}

function favorites_active_count(PDO $pdo, int $userId): int
{
    $stmt = $pdo->prepare('SELECT COUNT(*) FROM favorites_items WHERE user_id = ? AND is_deleted = 0');
    $stmt->execute([$userId]);
    return (int)$stmt->fetchColumn();
}

function replace_favorites_delta_state(PDO $pdo, int $userId, ?string $deviceId, array $payload, string $now): array
{
    ensure_favorites_delta_seeded($pdo, $userId);

    $incoming = [];
    $order = 1;
    foreach (favorites_payload_entries($payload) as $rawEntry) {
        $entry = favorite_delta_entry($rawEntry, $order);
        if (!$entry || isset($incoming[$entry['key']])) {
            $order++;
            continue;
        }
        $entry['order'] = $order++;
        $incoming[$entry['key']] = $entry;
    }

    $pdo->beginTransaction();
    try {
        $revision = favorite_lock_revision($pdo, $userId, $now);
        $current = [];
        $stmt = $pdo->prepare('SELECT key_hash, item_hash, sort_order, is_deleted FROM favorites_items WHERE user_id = ? FOR UPDATE');
        $stmt->execute([$userId]);
        foreach ($stmt as $row) {
            $current[$row['key_hash']] = $row;
        }

        $changed = 0;
        foreach ($current as $key => $row) {
            if (!isset($incoming[$key]) && empty($row['is_deleted'])) {
                $revision++;
                favorite_delete_delta($pdo, $userId, $deviceId, $key, $revision, $now);
                $changed++;
            }
        }

        foreach ($incoming as $key => $entry) {
            $expectedHash = favorite_item_hash($entry, (int)$entry['order']);
            $row = $current[$key] ?? null;
            if (
                !$row
                || !empty($row['is_deleted'])
                || (string)($row['item_hash'] ?? '') !== $expectedHash
                || (int)($row['sort_order'] ?? 0) !== (int)$entry['order']
            ) {
                $revision++;
                favorite_upsert_delta($pdo, $userId, $deviceId, $entry, $revision, $now);
                $changed++;
            }
        }

        if ($changed > 0) {
            $stmt = $pdo->prepare('UPDATE favorites_sync_meta SET revision = ?, updated_at = ? WHERE user_id = ?');
            $stmt->execute([$revision, $now, $userId]);
        }
        $pdo->commit();
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        throw $e;
    }

    return [
        'revision' => favorites_current_revision($pdo, $userId),
        'active_count' => favorites_active_count($pdo, $userId),
        'server_hash' => favorites_server_hash($pdo, $userId),
    ];
}

function favorites_delta(PDO $pdo, array $user, array $data): void
{
    $userId = (int)$user['id'];
    ensure_favorites_delta_seeded($pdo, $userId);

    $deviceId = short_text($data['device_id'] ?? null, 128);
    $baseRevision = max(0, (int)($data['base_revision'] ?? $data['since_revision'] ?? 0));
    $upserts = is_array($data['upserts'] ?? null) ? $data['upserts'] : [];
    $deletes = is_array($data['deletes'] ?? null) ? $data['deletes'] : [];
    $now = now();
    $changed = 0;

    $pdo->beginTransaction();
    try {
        $revision = favorite_lock_revision($pdo, $userId, $now);
        $order = 1;
        foreach ($upserts as $rawEntry) {
            if (!is_array($rawEntry)) {
                continue;
            }
            $entry = favorite_delta_entry($rawEntry, $order++);
            if (!$entry) {
                continue;
            }
            $revision++;
            favorite_upsert_delta($pdo, $userId, $deviceId, $entry, $revision, $now);
            $changed++;
        }
        foreach ($deletes as $rawKey) {
            $key = favorite_delete_key_hash($rawKey);
            if ($key === '') {
                continue;
            }
            $revision++;
            favorite_delete_delta($pdo, $userId, $deviceId, $key, $revision, $now);
            $changed++;
        }
        if ($changed > 0) {
            $stmt = $pdo->prepare('UPDATE favorites_sync_meta SET revision = ?, updated_at = ? WHERE user_id = ?');
            $stmt->execute([$revision, $now, $userId]);
        }
        $pdo->commit();
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        throw $e;
    }

    $currentRevision = favorites_current_revision($pdo, $userId);
    if ($changed > 0) {
        log_sync($pdo, $userId, $deviceId, 'favorites', 'delta', 'ok', $changed . ' local changes');
    }
    respond(true, 'Favoriten synchronisiert', [
        'revision' => $currentRevision,
        'base_revision' => $baseRevision,
        'changes' => favorites_changes_since($pdo, $userId, $baseRevision),
        'changed' => $changed,
        'active_count' => favorites_active_count($pdo, $userId),
        'server_hash' => favorites_server_hash($pdo, $userId),
    ]);
}

function favorites_state(PDO $pdo, array $user): void
{
    $userId = (int)$user['id'];
    $legacy = latest_favorites_payload($pdo, $userId);
    ensure_favorites_delta_seeded($pdo, $userId);
    $revision = favorites_current_revision($pdo, $userId);
    $activeCount = favorites_active_count($pdo, $userId);
    if ($revision === 0 && $activeCount === 0 && !$legacy) {
        respond(false, 'Keine Serverdaten gefunden', null, 'NO_BACKUP_FOUND', 404);
    }
    respond(true, 'OK', [
        'revision' => $revision,
        'active_count' => $activeCount,
        'server_hash' => favorites_server_hash($pdo, $userId),
        'favorites' => favorites_payload_from_delta($pdo, $userId),
    ]);
}

function favorites_push(PDO $pdo, array $user, array $data): void
{
    $payload = $data['favorites'] ?? $data['data'] ?? null;
    if (!is_array($payload)) {
        respond(false, 'Favoritendaten fehlen', null, 'MISSING_FIELDS', 400);
    }
    $deviceId = short_text($data['device_id'] ?? ($payload['device_id'] ?? null), 128);
    $payload = merge_favorites_payload(
        latest_favorites_payload($pdo, (int)$user['id']),
        $payload,
        deleted_favorite_keys($data, $payload),
        $deviceId
    );
    $now = now();
    $result = replace_favorites_payload($pdo, (int)$user['id'], $deviceId, $payload, $now);
    $result['delta'] = replace_favorites_delta_state($pdo, (int)$user['id'], $deviceId, $payload, $now);
    log_sync($pdo, (int)$user['id'], $deviceId, 'favorites', 'push', 'ok', 'current saved');
    respond(true, 'Favoriten wurden gesichert', $result);
}

function favorites_pull(PDO $pdo, array $user): void
{
    $userId = (int)$user['id'];
    ensure_favorites_delta_seeded($pdo, $userId);
    $revision = favorites_current_revision($pdo, $userId);
    $legacy = latest_favorites_payload($pdo, $userId);
    if ($revision > 0 || $legacy) {
        $payload = favorites_payload_from_delta($pdo, $userId);
        log_sync($pdo, $userId, short_text($payload['device_id'] ?? null, 128), 'favorites', 'pull', 'ok', 'delta backup returned');
        respond(true, 'OK', [
            'favorites' => $payload,
            'data_hash' => $payload['favorites_hash'],
            'updated_at' => $payload['updated_at'],
            'device_id' => $payload['device_id'],
            'revision' => $revision,
        ]);
    }

    $stmt = $pdo->prepare('SELECT * FROM favorites_backups WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1');
    $stmt->execute([$user['id']]);
    $row = $stmt->fetch();
    if (!$row) {
        respond(false, 'Keine Serverdaten gefunden', null, 'NO_BACKUP_FOUND', 404);
    }
    log_sync($pdo, (int)$user['id'], $row['device_id'], 'favorites', 'pull', 'ok', 'backup returned');
    respond(true, 'OK', [
        'favorites' => json_decode($row['data_json'], true),
        'data_hash' => $row['data_hash'],
        'updated_at' => $row['updated_at'],
        'device_id' => $row['device_id'],
    ]);
}

function binge_push(PDO $pdo, array $user, array $data): void
{
    $items = $data['items'] ?? [];
    if (!is_array($items)) {
        respond(false, 'Binge-Daten fehlen', null, 'MISSING_FIELDS', 400);
    }
    $deviceId = short_text($data['device_id'] ?? null, 128);
    $count = 0;
    foreach ($items as $item) {
        if (!is_array($item) || empty($item['item_key'])) {
            continue;
        }
        upsert_binge_item($pdo, (int)$user['id'], $deviceId, $item);
        $count++;
    }
    log_sync($pdo, (int)$user['id'], $deviceId, 'binge', 'push', 'ok', $count . ' items');
    respond(true, 'Binge-Stand wurde gesichert', ['count' => $count]);
}

function upsert_binge_item(PDO $pdo, int $userId, ?string $deviceId, array $item): void
{
    $updatedAt = normalize_datetime($item['updated_at'] ?? null);
    $json = json_encode($item, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    $stmt = $pdo->prepare('INSERT INTO binge_state
        (user_id, device_id, item_key, title, season, episode, position_seconds, duration_seconds, watched_percent, completed, provider, data_json, updated_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
            device_id = IF(updated_at <= VALUES(updated_at), VALUES(device_id), device_id),
            title = IF(updated_at <= VALUES(updated_at), VALUES(title), title),
            season = IF(updated_at <= VALUES(updated_at), VALUES(season), season),
            episode = IF(updated_at <= VALUES(updated_at), VALUES(episode), episode),
            position_seconds = IF(updated_at <= VALUES(updated_at), VALUES(position_seconds), position_seconds),
            duration_seconds = IF(updated_at <= VALUES(updated_at), VALUES(duration_seconds), duration_seconds),
            watched_percent = IF(updated_at <= VALUES(updated_at), VALUES(watched_percent), watched_percent),
            completed = IF(completed = 1 AND updated_at > VALUES(updated_at), completed, VALUES(completed)),
            provider = IF(updated_at <= VALUES(updated_at), VALUES(provider), provider),
            data_json = IF(updated_at <= VALUES(updated_at), VALUES(data_json), data_json),
            updated_at = GREATEST(updated_at, VALUES(updated_at))');
    $stmt->execute([
        $userId,
        $deviceId,
        short_text($item['item_key'], 512),
        short_text($item['title'] ?? null, 512),
        nullable_int($item['season'] ?? null),
        nullable_int($item['episode'] ?? null),
        nullable_int($item['position_seconds'] ?? null),
        nullable_int($item['duration_seconds'] ?? null),
        nullable_float($item['watched_percent'] ?? null),
        !empty($item['completed']) ? 1 : 0,
        short_text($item['provider'] ?? null, 255),
        $json,
        $updatedAt,
        $updatedAt,
    ]);
}

function binge_pull(PDO $pdo, array $user): void
{
    $stmt = $pdo->prepare('SELECT data_json FROM binge_state WHERE user_id = ? ORDER BY updated_at DESC');
    $stmt->execute([$user['id']]);
    $items = [];
    foreach ($stmt as $row) {
        $item = json_decode($row['data_json'], true);
        if (is_array($item)) {
            $items[] = $item;
        }
    }
    respond(true, 'OK', ['items' => $items, 'count' => count($items)]);
}

function sync_push(PDO $pdo, array $user, array $data): void
{
    $result = [];
    if (isset($data['favorites']) || isset($data['data'])) {
        $payload = $data['favorites'] ?? $data['data'];
        if (!is_array($payload)) {
            respond(false, 'Favoritendaten fehlen', null, 'MISSING_FIELDS', 400);
        }
        $deviceId = short_text($data['device_id'] ?? ($payload['device_id'] ?? null), 128);
        $payload = merge_favorites_payload(
            latest_favorites_payload($pdo, (int)$user['id']),
            $payload,
            deleted_favorite_keys($data, $payload),
            $deviceId
        );
        $now = now();
        $favoritesResult = replace_favorites_payload($pdo, (int)$user['id'], $deviceId, $payload, $now);
        $result['favorites_hash'] = $favoritesResult['data_hash'];
        $result['favorites_delta'] = replace_favorites_delta_state($pdo, (int)$user['id'], $deviceId, $payload, $now);
    }
    if (isset($data['binge_items']) && is_array($data['binge_items'])) {
        $deviceId = short_text($data['device_id'] ?? null, 128);
        foreach ($data['binge_items'] as $item) {
            if (is_array($item) && !empty($item['item_key'])) {
                upsert_binge_item($pdo, (int)$user['id'], $deviceId, $item);
            }
        }
        $result['binge_count'] = count($data['binge_items']);
    }
    log_sync($pdo, (int)$user['id'], short_text($data['device_id'] ?? null, 128), 'all', 'push', 'ok', 'sync push');
    respond(true, 'Synchronisation abgeschlossen', $result);
}

function sync_pull(PDO $pdo, array $user): void
{
    $fav = null;
    $userId = (int)$user['id'];
    ensure_favorites_delta_seeded($pdo, $userId);
    if (favorites_current_revision($pdo, $userId) > 0 || latest_favorites_payload($pdo, $userId)) {
        $payload = favorites_payload_from_delta($pdo, $userId);
        $fav = [
            'favorites' => $payload,
            'data_hash' => $payload['favorites_hash'],
            'updated_at' => $payload['updated_at'],
            'device_id' => $payload['device_id'],
            'revision' => $payload['revision'],
        ];
    }
    $stmt = $pdo->prepare('SELECT * FROM favorites_backups WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1');
    $stmt->execute([$user['id']]);
    $row = $stmt->fetch();
    if (!$fav && $row) {
        $fav = [
            'favorites' => json_decode($row['data_json'], true),
            'data_hash' => $row['data_hash'],
            'updated_at' => $row['updated_at'],
            'device_id' => $row['device_id'],
        ];
    }
    $stmt = $pdo->prepare('SELECT data_json FROM binge_state WHERE user_id = ? ORDER BY updated_at DESC');
    $stmt->execute([$user['id']]);
    $binge = [];
    foreach ($stmt as $bingeRow) {
        $item = json_decode($bingeRow['data_json'], true);
        if (is_array($item)) {
            $binge[] = $item;
        }
    }
    respond(true, 'OK', ['favorites' => $fav, 'binge_items' => $binge]);
}

function telemetry_ingest(PDO $pdo, array $data, array $config): void
{
    if (empty($data['install_id']) && isset($data['payload']) && is_array($data['payload'])) {
        $data = $data['payload'];
    }
    $installId = (string)($data['install_id'] ?? '');
    if (!preg_match('/^[A-Za-z0-9._:-]{16,128}$/', $installId)) {
        respond(false, 'Installations-ID fehlt', null, 'MISSING_INSTALL_ID', 400);
    }
    $eventName = telemetry_slug($data['event'] ?? 'event', 'event');
    $eventGroup = telemetry_slug($data['event_group'] ?? 'general', 'general');
    $sessionIdRaw = (string)($data['session_id'] ?? '');
    $sessionHash = $sessionIdRaw !== '' ? telemetry_hash($sessionIdRaw, $config) : null;
    $installHash = telemetry_hash($installId, $config);
    $now = now();

    $context = is_array($data['context'] ?? null) ? $data['context'] : [];
    $addonId = short_text($context['addon_id'] ?? $data['addon_id'] ?? null, 64);
    $addonVariant = short_text($context['addon_variant'] ?? $data['addon_variant'] ?? null, 32);
    $addonVersion = short_text($context['addon_version'] ?? $data['addon_version'] ?? null, 32);
    $kodiVersion = short_text($context['kodi_version'] ?? $data['kodi_version'] ?? null, 64);
    $osFamily = short_text($context['os_family'] ?? $context['os_class'] ?? null, 64);
    $osVersion = short_text($context['os_version'] ?? null, 128);
    $deviceClass = short_text($context['device_class'] ?? null, 64);
    $hardwareFamily = short_text($context['hardware_family'] ?? null, 128);
    $cpuArch = short_text($context['cpu_arch'] ?? null, 64);
    $consentVersion = short_text($context['telemetry_consent_version'] ?? null, 32);

    $installationId = telemetry_upsert_installation($pdo, $installHash, $now, $addonId, $addonVariant, $addonVersion, $kodiVersion, $osFamily, $osVersion, $deviceClass, $hardwareFamily, $cpuArch, $consentVersion);
    $sessionDbId = null;
    if ($sessionHash) {
        $sessionDbId = telemetry_upsert_session($pdo, $installationId, $sessionHash, $now, $addonId, $addonVariant, $addonVersion, $kodiVersion, $osFamily, $osVersion, $deviceClass, $hardwareFamily, $cpuArch, $eventName, short_text($data['end_reason'] ?? null, 64));
    }
    if ($eventName !== 'heartbeat') {
        telemetry_store_rollups($pdo, $eventName, $eventGroup, $now, $addonId, $addonVariant, $addonVersion, $kodiVersion, $osFamily, $osVersion, $deviceClass);
    }
    telemetry_store_online_rollup($pdo, $now);
    if (!empty($config['telemetry_store_raw_events']) && $eventName !== 'heartbeat') {
        telemetry_store_event($pdo, $installationId, $sessionDbId, $eventName, $eventGroup, $now, $addonId, $addonVariant, $addonVersion, $kodiVersion, $osFamily, $osVersion, $deviceClass, telemetry_payload($data['payload'] ?? []));
    }
    respond(true, 'OK', ['accepted' => true]);
}

function telemetry_hash(string $value, array $config): string
{
    $salt = (string)($config['telemetry_salt'] ?? '');
    if ($salt === '') {
        $salt = hash('sha256', (string)($config['db_pass'] ?? 'xvault'));
    }
    return hash_hmac('sha256', $value, $salt);
}

function telemetry_upsert_installation(PDO $pdo, string $installHash, string $now, ?string $addonId, ?string $addonVariant, ?string $addonVersion, ?string $kodiVersion, ?string $osFamily, ?string $osVersion, ?string $deviceClass, ?string $hardwareFamily, ?string $cpuArch, ?string $consentVersion): int
{
    $stmt = $pdo->prepare('INSERT INTO telemetry_installations
        (install_hash, first_seen_at, last_seen_at, current_addon_id, addon_variant, current_addon_version, current_kodi_version, os_family, os_version, device_class, hardware_family, cpu_arch, telemetry_consent_version, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
            last_seen_at = VALUES(last_seen_at),
            current_addon_id = COALESCE(VALUES(current_addon_id), current_addon_id),
            addon_variant = COALESCE(VALUES(addon_variant), addon_variant),
            current_addon_version = COALESCE(VALUES(current_addon_version), current_addon_version),
            current_kodi_version = COALESCE(VALUES(current_kodi_version), current_kodi_version),
            os_family = COALESCE(VALUES(os_family), os_family),
            os_version = COALESCE(VALUES(os_version), os_version),
            device_class = COALESCE(VALUES(device_class), device_class),
            hardware_family = COALESCE(VALUES(hardware_family), hardware_family),
            cpu_arch = COALESCE(VALUES(cpu_arch), cpu_arch),
            telemetry_consent_version = COALESCE(VALUES(telemetry_consent_version), telemetry_consent_version),
            updated_at = VALUES(updated_at)');
    $stmt->execute([$installHash, $now, $now, $addonId, $addonVariant, $addonVersion, $kodiVersion, $osFamily, $osVersion, $deviceClass, $hardwareFamily, $cpuArch, $consentVersion, $now, $now]);
    $stmt = $pdo->prepare('SELECT id FROM telemetry_installations WHERE install_hash = ? LIMIT 1');
    $stmt->execute([$installHash]);
    return (int)$stmt->fetchColumn();
}

function telemetry_upsert_session(PDO $pdo, int $installationId, string $sessionHash, string $now, ?string $addonId, ?string $addonVariant, ?string $addonVersion, ?string $kodiVersion, ?string $osFamily, ?string $osVersion, ?string $deviceClass, ?string $hardwareFamily, ?string $cpuArch, string $eventName, ?string $endReason): int
{
    $endedAt = $eventName === 'app_stop' ? $now : null;
    $stmt = $pdo->prepare('INSERT INTO telemetry_sessions
        (installation_id, session_hash, started_at, last_heartbeat_at, ended_at, duration_seconds, addon_id, addon_variant, addon_version, kodi_version, os_family, os_version, device_class, hardware_family, cpu_arch, end_reason, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
            last_heartbeat_at = VALUES(last_heartbeat_at),
            ended_at = COALESCE(VALUES(ended_at), ended_at),
            duration_seconds = GREATEST(0, TIMESTAMPDIFF(SECOND, started_at, VALUES(last_heartbeat_at))),
            addon_id = COALESCE(VALUES(addon_id), addon_id),
            addon_variant = COALESCE(VALUES(addon_variant), addon_variant),
            addon_version = COALESCE(VALUES(addon_version), addon_version),
            kodi_version = COALESCE(VALUES(kodi_version), kodi_version),
            os_family = COALESCE(VALUES(os_family), os_family),
            os_version = COALESCE(VALUES(os_version), os_version),
            device_class = COALESCE(VALUES(device_class), device_class),
            hardware_family = COALESCE(VALUES(hardware_family), hardware_family),
            cpu_arch = COALESCE(VALUES(cpu_arch), cpu_arch),
            end_reason = COALESCE(VALUES(end_reason), end_reason),
            updated_at = VALUES(updated_at)');
    $stmt->execute([$installationId, $sessionHash, $now, $now, $endedAt, $addonId, $addonVariant, $addonVersion, $kodiVersion, $osFamily, $osVersion, $deviceClass, $hardwareFamily, $cpuArch, $endReason, $now, $now]);
    $stmt = $pdo->prepare('SELECT id FROM telemetry_sessions WHERE session_hash = ? LIMIT 1');
    $stmt->execute([$sessionHash]);
    return (int)$stmt->fetchColumn();
}

function telemetry_store_rollups(PDO $pdo, string $eventName, string $eventGroup, string $now, ?string $addonId, ?string $addonVariant, ?string $addonVersion, ?string $kodiVersion, ?string $osFamily, ?string $osVersion, ?string $deviceClass): void
{
    foreach (['hour', 'day'] as $bucketType) {
        $bucketStart = telemetry_bucket_start($now, $bucketType);
        $stmt = $pdo->prepare('INSERT INTO telemetry_event_rollups
            (bucket_type, bucket_start, event_name, event_group, addon_id, addon_variant, addon_version, kodi_version, os_family, os_version, device_class, event_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON DUPLICATE KEY UPDATE
                event_count = event_count + 1,
                updated_at = VALUES(updated_at)');
        $stmt->execute([
            $bucketType,
            $bucketStart,
            $eventName,
            $eventGroup ?: '',
            $addonId ?: '',
            $addonVariant ?: '',
            $addonVersion ?: '',
            $kodiVersion ?: '',
            $osFamily ?: '',
            $osVersion ?: '',
            $deviceClass ?: '',
            $now,
        ]);
    }
}

function telemetry_store_online_rollup(PDO $pdo, string $now): void
{
    $windowStart = date('Y-m-d H:i:s', strtotime($now . ' -35 minutes'));
    $stmt = $pdo->prepare('SELECT COUNT(*) FROM telemetry_installations WHERE last_seen_at >= ?');
    $stmt->execute([$windowStart]);
    $online = (int)$stmt->fetchColumn();
    $bucketStart = telemetry_bucket_start($now, 'hour');
    $stmt = $pdo->prepare('INSERT INTO telemetry_online_rollups
        (bucket_start, max_online, updated_at)
        VALUES (?, ?, ?)
        ON DUPLICATE KEY UPDATE
            max_online = GREATEST(max_online, VALUES(max_online)),
            updated_at = VALUES(updated_at)');
    $stmt->execute([$bucketStart, $online, $now]);
}

function telemetry_bucket_start(string $now, string $bucketType): string
{
    $timestamp = strtotime($now);
    if ($bucketType === 'day') {
        return date('Y-m-d 00:00:00', $timestamp);
    }
    return date('Y-m-d H:00:00', $timestamp);
}

function telemetry_store_event(PDO $pdo, int $installationId, ?int $sessionId, string $eventName, string $eventGroup, string $now, ?string $addonId, ?string $addonVariant, ?string $addonVersion, ?string $kodiVersion, ?string $osFamily, ?string $osVersion, ?string $deviceClass, array $payload): void
{
    $json = $payload ? json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) : null;
    $stmt = $pdo->prepare('INSERT INTO telemetry_events
        (installation_id, session_id, event_name, event_group, occurred_at, addon_id, addon_variant, addon_version, kodi_version, os_family, os_version, device_class, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
    $stmt->execute([$installationId, $sessionId, $eventName, $eventGroup, $now, $addonId, $addonVariant, $addonVersion, $kodiVersion, $osFamily, $osVersion, $deviceClass, $json, $now]);
}

function telemetry_payload($payload): array
{
    if (!is_array($payload)) {
        return [];
    }
    $allowed = ['menu', 'media_type', 'playback_mode', 'error_group', 'source_count', 'working_count', 'blocked_count', 'sync_area', 'setting_group', 'feature'];
    $result = [];
    foreach ($allowed as $key) {
        if (!array_key_exists($key, $payload)) {
            continue;
        }
        if (is_int($payload[$key]) || is_float($payload[$key])) {
            $result[$key] = $payload[$key];
        } else {
            $result[$key] = short_text($payload[$key], 128);
        }
    }
    return $result;
}

function telemetry_slug($value, string $default): string
{
    $slug = strtolower((string)$value);
    $slug = preg_replace('/[^a-z0-9_:-]+/', '_', $slug);
    $slug = trim($slug, '_');
    if ($slug === '') {
        $slug = $default;
    }
    return substr($slug, 0, 64);
}

function log_sync(PDO $pdo, int $userId, ?string $deviceId, string $type, string $direction, string $status, string $message): void
{
    $stmt = $pdo->prepare('INSERT INTO sync_log (user_id, device_id, sync_type, direction, status, message, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)');
    $stmt->execute([$userId, $deviceId, $type, $direction, $status, short_text($message, 512), now()]);
}

function require_method(string $method): void
{
    if ($_SERVER['REQUEST_METHOD'] !== $method) {
        respond(false, 'Methode nicht erlaubt', null, 'METHOD_NOT_ALLOWED', 405);
    }
}

function normalize_datetime($value): string
{
    if (!$value) {
        return now();
    }
    try {
        return (new DateTime((string)$value))->format('Y-m-d H:i:s');
    } catch (Throwable $e) {
        return now();
    }
}

function now(): string
{
    return date('Y-m-d H:i:s');
}

function short_text($value, int $length): ?string
{
    if ($value === null) {
        return null;
    }
    $text = (string)$value;
    if (function_exists('mb_substr')) {
        return mb_substr($text, 0, $length, 'UTF-8');
    }
    return substr($text, 0, $length);
}

function nullable_int($value): ?int
{
    return $value === null || $value === '' ? null : (int)$value;
}

function nullable_float($value): ?float
{
    return $value === null || $value === '' ? null : (float)$value;
}

function respond(bool $success, string $message, $data = null, ?string $errorCode = null, int $status = 200): void
{
    http_response_code($status);
    $response = ['success' => $success, 'message' => $message];
    if ($data !== null) {
        $response['data'] = $data;
    }
    if ($errorCode !== null) {
        $response['error_code'] = $errorCode;
    }
    echo json_encode($response, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function log_error(string $message): void
{
    error_log('[xvault-api] ' . $message);
}
