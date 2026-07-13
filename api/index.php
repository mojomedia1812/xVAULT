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
    dispatch($pdo);
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
}

function dispatch(PDO $pdo): void
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

    $user = require_user($pdo);
    switch ($action) {
        case 'favorites_push':
            require_method('POST');
            favorites_push($pdo, $user, input_json());
            break;
        case 'favorites_pull':
            favorites_pull($pdo, $user);
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
        'binge/push' => 'binge_push',
        'binge/pull' => 'binge_pull',
        'sync/push' => 'sync_push',
        'sync/pull' => 'sync_pull',
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
    $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    $hash = hash('sha256', $json);
    $now = now();
    $stmt = $pdo->prepare('INSERT INTO favorites_backups (user_id, device_id, data_json, data_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)');
    $stmt->execute([$user['id'], $deviceId, $json, $hash, $now, $now]);
    log_sync($pdo, (int)$user['id'], $deviceId, 'favorites', 'push', 'ok', 'backup saved');
    respond(true, 'Favoriten wurden gesichert', ['data_hash' => $hash, 'updated_at' => $now]);
}

function favorites_pull(PDO $pdo, array $user): void
{
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
        $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        $hash = hash('sha256', $json);
        $now = now();
        $stmt = $pdo->prepare('INSERT INTO favorites_backups (user_id, device_id, data_json, data_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)');
        $stmt->execute([$user['id'], $deviceId, $json, $hash, $now, $now]);
        $result['favorites_hash'] = $hash;
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
    $stmt = $pdo->prepare('SELECT * FROM favorites_backups WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1');
    $stmt->execute([$user['id']]);
    $row = $stmt->fetch();
    if ($row) {
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
