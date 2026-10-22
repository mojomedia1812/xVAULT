<?php
declare(strict_types=1);

// The account row serializes writes. Revisions, never client clocks, order changes.
function sync2_schema(PDO $pdo): void
{
    foreach ([
        'sync_devices' => 'user_id INT NOT NULL, device_id VARCHAR(128) NOT NULL, name VARCHAR(128) NOT NULL, last_seen_at VARCHAR(32) NOT NULL, last_used_at VARCHAR(32), last_changed_at VARCHAR(32), acknowledged_revision BIGINT NOT NULL DEFAULT 0, PRIMARY KEY(user_id, device_id)',
        'sync_sessions' => 'token_hash CHAR(64) PRIMARY KEY, user_id INT NOT NULL, device_id VARCHAR(128), created_at VARCHAR(32) NOT NULL',
        'sync_accounts' => 'user_id INT PRIMARY KEY, revision BIGINT NOT NULL DEFAULT 0',
        'sync_entities' => 'user_id INT NOT NULL, kind VARCHAR(16) NOT NULL, entity_key VARCHAR(128) NOT NULL, revision BIGINT NOT NULL, deleted INT NOT NULL, data_json LONGTEXT NOT NULL, fields_json TEXT NOT NULL, device_id VARCHAR(128), PRIMARY KEY(user_id, kind, entity_key)',
        'sync_operations' => 'user_id INT NOT NULL, operation_id VARCHAR(64) NOT NULL, device_id VARCHAR(128), revision BIGINT NOT NULL, event_sequence BIGINT NOT NULL, created_at VARCHAR(32) NOT NULL, operation_json LONGTEXT NOT NULL, result_json LONGTEXT NOT NULL, resolved INT NOT NULL DEFAULT 0, PRIMARY KEY(user_id, operation_id)',
    ] as $table => $definition) {
        $options = $pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'mysql' ? ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci' : '';
        $pdo->exec("CREATE TABLE IF NOT EXISTS $table ($definition)" . $options);
    }
}

function sync2_query(PDO $pdo, string $sql, array $args = []): PDOStatement
{
    $stmt = $pdo->prepare($sql);
    $stmt->execute($args);
    return $stmt;
}

function sync2_lock(PDO $pdo, int $userId): void
{
    // SQLite is used by the local integration harness; production uses InnoDB.
    $suffix = $pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'mysql' ? ' FOR UPDATE' : '';
    sync2_query($pdo, 'SELECT id FROM users WHERE id = ?' . $suffix, [$userId])->fetch();
}

function sync2_issue_session(PDO $pdo, int $userId, array $data): string
{
    $deviceId = substr(trim((string)($data['device_id'] ?? '')), 0, 128) ?: null;
    $key = bin2hex(random_bytes(32));
    sync2_query($pdo, 'INSERT INTO sync_sessions (token_hash, user_id, device_id, created_at) VALUES (?, ?, ?, ?)',
        [hash('sha256', $key), $userId, $deviceId, now()]);
    return $key;
}

function sync2_seed(PDO $pdo, int $userId): void
{
    if (sync2_query($pdo, 'SELECT user_id FROM sync_accounts WHERE user_id = ?', [$userId])->fetch()) {
        return;
    }
    sync2_query($pdo, 'INSERT INTO sync_accounts (user_id, revision) VALUES (?, 0)', [$userId]);
    // Import the server's existing state, not a stale device's whole profile.
    $favorites = sync2_query($pdo, 'SELECT key_hash, label, thumb, path, sort_order, is_deleted FROM favorites_items WHERE user_id = ?', [$userId])->fetchAll();
    if (!$favorites && function_exists('latest_favorites_payload')) {
        $legacy = latest_favorites_payload($pdo, $userId);
        foreach (($legacy['items'] ?? []) as $item) {
            $entry = favorite_delta_entry($item, count($favorites) + 1);
            if ($entry) {
                $favorites[] = ['key_hash' => $entry['key'], 'label' => $entry['label'], 'thumb' => $entry['thumb'], 'path' => $entry['path'], 'sort_order' => $entry['order'], 'is_deleted' => 0];
            }
        }
    }
    foreach ($favorites as $row) {
        sync2_store($pdo, $userId, 'favorite', $row['key_hash'], ['label' => $row['label'], 'thumb' => $row['thumb'], 'path' => $row['path'], 'order' => (int)$row['sort_order']], (bool)$row['is_deleted'], 0, null, []);
    }
    $legacyItems = sync2_query($pdo, 'SELECT item_key, data_json FROM binge_state WHERE user_id = ?', [$userId])->fetchAll();
    usort($legacyItems, function (array $a, array $b): int {
        return strcmp((string)(json_decode($a['data_json'], true)['updated_at'] ?? ''), (string)(json_decode($b['data_json'], true)['updated_at'] ?? ''));
    });
    foreach ($legacyItems as $row) {
        $item = json_decode($row['data_json'], true);
        if (is_array($item)) {
            $item['item_key'] = sync2_item_key($item);
            $kind = in_array($item['provider'] ?? '', ['xvault-manual', 'xvault-playcount'], true) ? 'watch' : 'progress';
            sync2_store($pdo, $userId, $kind, $item['item_key'], ['value' => $item], false, 0, null, []);
        }
    }
}

function sync2_item_key(array $item): string
{
    $extra = $item['extra'] ?? [];
    $season = isset($item['season']) && is_numeric($item['season']) ? (int)$item['season'] : null;
    $episode = isset($item['episode']) && is_numeric($item['episode']) ? (int)$item['episode'] : null;
    $kind = $extra['mediatype'] ?? ($episode !== null ? 'episode' : 'movie');
    if ($kind === 'movie') {
        $season = $episode = null;
    } elseif ($season !== null && $episode !== null && $episode > 0) {
        $kind = 'episode';
    } elseif ($kind === 'season') {
        $episode = null;
    } else {
        $kind = 'tvshow';
        $season = $episode = null;
    }
    $suffix = ($season === null ? '' : (string)$season) . ':' . ($episode === null ? '' : (string)$episode);
    if (!empty($extra['tmdb_id'])) {
        $base = $kind . ':tmdb:' . $extra['tmdb_id'] . ':' . $suffix;
    } elseif (!empty($extra['imdb_id'])) {
        $base = $kind . ':imdb:' . $extra['imdb_id'] . ':' . $suffix;
    } else {
        $base = $kind . ':name:' . trim((string)($item['title'] ?? $item['name'] ?? '')) . ':' . ($item['year'] ?? '0') . ':' . $suffix;
    }
    return hash('sha256', $base);
}

function sync2_store(PDO $pdo, int $userId, string $kind, string $key, array $data, bool $deleted, int $revision, ?string $deviceId, array $fields): void
{
    sync2_query($pdo, 'DELETE FROM sync_entities WHERE user_id = ? AND kind = ? AND entity_key = ?', [$userId, $kind, $key]);
    sync2_query($pdo, 'INSERT INTO sync_entities (user_id, kind, entity_key, revision, deleted, data_json, fields_json, device_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [$userId, $kind, $key, $revision, (int)$deleted, json_encode($data), json_encode($fields), $deviceId]);
}

function sync2_entity(array $row): array
{
    return ['kind' => $row['kind'], 'key' => $row['entity_key'], 'revision' => (int)$row['revision'], 'deleted' => (bool)$row['deleted'], 'data' => json_decode($row['data_json'], true), 'device_id' => $row['device_id']];
}

function sync2_apply(PDO $pdo, int $userId, string $deviceId, array $op, int &$revision): array
{
    $id = (string)($op['id'] ?? '');
    $kind = (string)($op['kind'] ?? '');
    $key = (string)($op['key'] ?? '');
    if (!preg_match('/^[a-zA-Z0-9-]{16,64}$/', $id) || !in_array($kind, ['favorite', 'progress', 'watch'], true) || !preg_match('/^[a-f0-9]{64}$/', $key)) {
        throw new InvalidArgumentException('Invalid sync operation');
    }
    $previous = sync2_query($pdo, 'SELECT result_json FROM sync_operations WHERE user_id = ? AND operation_id = ?', [$userId, $id])->fetchColumn();
    if ($previous !== false) {
        return json_decode($previous, true);
    }
    $row = sync2_query($pdo, 'SELECT * FROM sync_entities WHERE user_id = ? AND kind = ? AND entity_key = ?', [$userId, $kind, $key])->fetch();
    $base = max(-1, (int)($op['base_revision'] ?? -1));
    $patch = $op['patch'] ?? [];
    if (!is_array($patch) || strlen(json_encode($patch)) > 32768) {
        throw new InvalidArgumentException('Invalid patch');
    }
    $allowed = $kind === 'favorite' ? ['label', 'thumb', 'path', 'order'] : ['value'];
    if (array_diff(array_keys($patch), $allowed)) {
        throw new InvalidArgumentException('Invalid patch fields');
    }
    if ($kind !== 'favorite' && (!is_array($patch['value'] ?? null) || ($patch['value']['item_key'] ?? '') !== $key)) {
        throw new InvalidArgumentException('Invalid playback item');
    }
    $deleted = !empty($op['deleted']);
    $current = $row ? json_decode($row['data_json'], true) : [];
    $fields = $row ? json_decode($row['fields_json'], true) : [];
    $conflict = false;
    if ($row) {
        if ($deleted || (bool)$row['deleted']) {
            $conflict = (int)$row['revision'] > $base;
        } else {
            foreach ($patch as $field => $value) {
                if ((int)($fields[$field] ?? 0) > $base && ($current[$field] ?? null) !== $value) {
                    $conflict = true;
                }
            }
        }
    }
    if ($base > $revision) {
        throw new InvalidArgumentException('Future base revision');
    }
    // Subsequent checkpoints of the same playback session are ordered by a
    // monotonic sequence. Delayed retries cannot rewind that session.
    $sameSession = $kind === 'progress' && !empty($patch['value']['session_id'])
        && ($patch['value']['session_id'] === ($current['value']['session_id'] ?? null))
        && ($row['device_id'] ?? null) === $deviceId && empty($op['resolves']);
    $obsoleteCheckpoint = false;
    if ($sameSession) {
        $conflict = false;
        $obsoleteCheckpoint = (int)($patch['value']['sequence'] ?? 0) <= (int)($current['value']['sequence'] ?? 0);
    }
    if ($kind === 'watch' && isset($current['value']['completed'])
        && (bool)$current['value']['completed'] === (bool)($patch['value']['completed'] ?? false)) {
        $conflict = false;
        $obsoleteCheckpoint = true; // A timestamp or title is not a watched-state edit.
    }
    if ($kind === 'progress' && !empty($op['resolves']) && !$conflict) {
        // A deliberate choice starts a new branch: delayed checkpoints from
        // either old player must not undo the user's conflict resolution.
        $patch['value']['session_id'] = 'choice:' . $id;
        $patch['value']['sequence'] = 0;
    }
    $result = ['id' => $id, 'status' => $conflict ? 'conflict' : 'accepted'];
    $result['before'] = $row ? sync2_entity($row) : null;
    if ($obsoleteCheckpoint) {
        $result['unchanged'] = true;
    }
    if (!$conflict && !$obsoleteCheckpoint) {
        $revision++;
        foreach ($patch as $field => $value) {
            $current[$field] = $value;
            $fields[$field] = $revision;
        }
        sync2_store($pdo, $userId, $kind, $key, $current, $deleted, $revision, $deviceId, $fields);
        $result['revision'] = $revision;
    } else {
        if ($conflict) {
            $result['current'] = sync2_entity($row);
        }
    }
    if (!$conflict && !empty($op['resolves'])) {
        sync2_query($pdo, 'UPDATE sync_operations SET resolved = 1 WHERE user_id = ? AND operation_id = ?', [$userId, $op['resolves']]);
    }
    $superseded = 0;
    if ($conflict && $kind === 'progress' && !empty($patch['value']['session_id'])) {
        foreach (sync2_query($pdo, 'SELECT operation_id, operation_json, result_json FROM sync_operations WHERE user_id = ? AND device_id = ? AND resolved = 0', [$userId, $deviceId])->fetchAll() as $prior) {
            $priorOp = json_decode($prior['operation_json'], true);
            if ((json_decode($prior['result_json'], true)['status'] ?? '') === 'conflict'
                && $priorOp['kind'] === $kind && $priorOp['key'] === $key
                && ($priorOp['patch']['value']['session_id'] ?? null) === $patch['value']['session_id']) {
                if ((int)($priorOp['patch']['value']['sequence'] ?? 0) < (int)($patch['value']['sequence'] ?? 0)) {
                    sync2_query($pdo, 'UPDATE sync_operations SET resolved = 1 WHERE user_id = ? AND operation_id = ?', [$userId, $prior['operation_id']]);
                } else {
                    $superseded = 1;
                }
            }
        }
    }
    $eventSequence = 1 + (int)sync2_query($pdo, 'SELECT MAX(event_sequence) FROM sync_operations WHERE user_id = ?', [$userId])->fetchColumn();
    sync2_query($pdo, 'INSERT INTO sync_operations (user_id, operation_id, device_id, revision, event_sequence, created_at, operation_json, result_json, resolved) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [$userId, $id, $deviceId, $revision, $eventSequence, now(), json_encode($op), json_encode($result), $superseded]);
    return $result;
}

function sync2_exchange(PDO $pdo, array $user, array $data): array
{
    $userId = (int)$user['id'];
    $deviceId = substr(trim((string)($data['device_id'] ?? '')), 0, 128);
    if (!$deviceId || count($data['operations'] ?? []) > 200) {
        throw new InvalidArgumentException('Invalid device or batch');
    }
    if (!empty($user['_device_id']) && $deviceId !== $user['_device_id']) {
        respond(false, 'Dieses Profil wurde kopiert. Bitte dieses Gerät neu anmelden.', null, 'DEVICE_MISMATCH', 409);
    }
    $pdo->beginTransaction();
    try {
        sync2_lock($pdo, $userId);
        if (!empty($user['_auth_hash'])) {
            $session = sync2_query($pdo, 'SELECT device_id FROM sync_sessions WHERE user_id = ? AND token_hash = ?', [$userId, $user['_auth_hash']])->fetch();
            $legacy = sync2_query($pdo, 'SELECT id FROM users WHERE id = ? AND api_key_hash = ? AND is_active = 1', [$userId, $user['_auth_hash']])->fetch();
            if (!$session && !$legacy) {
                $pdo->rollBack();
                respond(false, 'Anmeldung wurde widerrufen.', null, 'UNAUTHORIZED', 401);
            }
            if (!$session) {
                sync2_query($pdo, 'INSERT INTO sync_sessions (token_hash, user_id, device_id, created_at) VALUES (?, ?, ?, ?)', [$user['_auth_hash'], $userId, $deviceId, now()]);
            } elseif (!$session['device_id']) {
                sync2_query($pdo, 'UPDATE sync_sessions SET device_id = ? WHERE token_hash = ?', [$deviceId, $user['_auth_hash']]);
            } elseif ($session['device_id'] !== $deviceId) {
                $pdo->rollBack();
                respond(false, 'Bitte dieses Gerät neu anmelden.', null, 'DEVICE_MISMATCH', 409);
            }
        }
        sync2_seed($pdo, $userId);
        if (!empty($data['revoke_device'])) {
            $target = substr((string)$data['revoke_device'], 0, 128);
            sync2_query($pdo, 'UPDATE users SET api_key_hash = NULL WHERE id = ? AND api_key_hash IN (SELECT token_hash FROM sync_sessions WHERE user_id = ? AND device_id = ?)', [$userId, $userId, $target]);
            sync2_query($pdo, 'DELETE FROM sync_sessions WHERE user_id = ? AND device_id = ?', [$userId, $target]);
        }
        $revision = (int)sync2_query($pdo, 'SELECT revision FROM sync_accounts WHERE user_id = ?', [$userId])->fetchColumn();
        $results = [];
        $before = $revision;
        foreach (($data['operations'] ?? []) as $operation) {
            $results[] = sync2_apply($pdo, $userId, $deviceId, $operation, $revision);
        }
        sync2_query($pdo, 'UPDATE sync_accounts SET revision = ? WHERE user_id = ?', [$revision, $userId]);
        $old = sync2_query($pdo, 'SELECT * FROM sync_devices WHERE user_id = ? AND device_id = ?', [$userId, $deviceId])->fetch();
        $ack = min($revision, max(0, (int)($data['cursor'] ?? 0)));
        $name = substr(trim((string)($data['device_name'] ?? 'Kodi')), 0, 128) ?: 'Kodi';
        $changed = $revision > $before ? now() : ($old['last_changed_at'] ?? null);
        $used = !empty($data['active']) || $revision > $before ? now() : ($old['last_used_at'] ?? null);
        if ($old) {
            sync2_query($pdo, 'UPDATE sync_devices SET name = ?, last_seen_at = ?, last_used_at = ?, last_changed_at = ?, acknowledged_revision = ? WHERE user_id = ? AND device_id = ?', [$name, now(), $used, $changed, $ack, $userId, $deviceId]);
        } else {
            sync2_query($pdo, 'INSERT INTO sync_devices (user_id, device_id, name, last_seen_at, last_used_at, last_changed_at, acknowledged_revision) VALUES (?, ?, ?, ?, ?, ?, ?)', [$userId, $deviceId, $name, now(), $used, $changed, $ack]);
        }
        // A consistent full snapshot is deliberately used for small personal accounts.
        // The cursor is informational; the snapshot and revision share the same lock.
        $entities = array_map('sync2_entity', sync2_query($pdo, 'SELECT * FROM sync_entities WHERE user_id = ?', [$userId])->fetchAll());
        $devices = sync2_query($pdo, 'SELECT device_id, name, last_seen_at, last_used_at, last_changed_at, acknowledged_revision FROM sync_devices WHERE user_id = ? ORDER BY last_used_at DESC, last_seen_at DESC', [$userId])->fetchAll();
        foreach ($devices as &$registeredDevice) {
            $registeredDevice['authenticated'] = (int)sync2_query($pdo, 'SELECT COUNT(*) FROM sync_sessions WHERE user_id = ? AND device_id = ?', [$userId, $registeredDevice['device_id']])->fetchColumn() > 0;
        }
        unset($registeredDevice);
        $activity = sync2_query($pdo, 'SELECT operation_id, device_id, revision, event_sequence, created_at, operation_json, result_json, resolved FROM sync_operations WHERE user_id = ? ORDER BY event_sequence DESC LIMIT 100', [$userId])->fetchAll();
        $conflicts = [];
        foreach (sync2_query($pdo, 'SELECT operation_id, device_id, operation_json, result_json FROM sync_operations WHERE user_id = ? AND resolved = 0', [$userId])->fetchAll() as $event) {
            if ((json_decode($event['result_json'], true)['status'] ?? '') === 'conflict') {
                $conflicts[] = $event;
            }
        }
        $pdo->commit();
        return ['protocol' => 2, 'revision' => $revision, 'results' => $results, 'entities' => $entities, 'devices' => $devices, 'activity' => $activity, 'conflicts' => $conflicts];
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        throw $e;
    }
}
