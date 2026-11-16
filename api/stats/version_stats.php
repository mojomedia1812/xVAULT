<?php
declare(strict_types=1);

// Derive channels on read so older clients and stored rows need no migration.
function xvault_stats_channel(string $version, string $variant = '', string $addonId = ''): string
{
    if (stripos($addonId, 'xvaultalpha') !== false ||
        preg_match('/^(alpha|alpa)$/i', trim($variant)) ||
        preg_match('/(?:alpha|alpa)/i', $version)) {
        return 'Alpha';
    }
    if (!preg_match('/^(\d{4})\.(\d{2})\.(\d{2})\.([1-9]\d*)$/D', trim($version), $m) ||
        !checkdate((int)$m[2], (int)$m[3], (int)$m[1])) {
        return 'Unbekannt';
    }
    // Before 24 October the revision was not a release-channel indicator.
    return strcmp(substr(trim($version), 0, 10), '2026.10.24') < 0 || $m[4] === '1'
        ? 'Release' : 'Nightly';
}

function xvault_stats_versions(PDO $pdo): array
{
    $rows = $pdo->query("SELECT COALESCE(current_addon_version, '') AS version,
        COALESCE(addon_variant, '') AS variant, COALESCE(current_addon_id, '') AS addon_id,
        COUNT(*) AS installations, MAX(last_seen_at) AS last_seen
        FROM telemetry_installations
        GROUP BY current_addon_version, addon_variant, current_addon_id")->fetchAll(PDO::FETCH_ASSOC);
    $versions = [];
    $channels = ['Release' => 0, 'Nightly' => 0, 'Alpha' => 0, 'Unbekannt' => 0];
    foreach ($rows as $row) {
        $channel = xvault_stats_channel($row['version'], $row['variant'], $row['addon_id']);
        $version = trim($row['version']) ?: 'unbekannt';
        $key = $channel . ':' . $version;
        if (!isset($versions[$key])) {
            $versions[$key] = ['version' => $version, 'channel' => $channel,
                'installations' => 0, 'last_seen' => ''];
        }
        $versions[$key]['installations'] += (int)$row['installations'];
        $versions[$key]['last_seen'] = max($versions[$key]['last_seen'], (string)$row['last_seen']);
        $channels[$channel] += (int)$row['installations'];
    }
    $versions = array_values($versions);
    usort($versions, static function (array $a, array $b): int {
        return version_compare($b['version'], $a['version']) ?: strcmp($a['channel'], $b['channel']);
    });
    $channelRows = [];
    foreach ($channels as $label => $count) {
        if ($label !== 'Unbekannt' || $count > 0) {
            $channelRows[] = ['label' => $label, 'value' => $count];
        }
    }
    return ['channels' => $channelRows, 'versions' => $versions];
}

function xvault_stats_versions_html(array $rows, ?string $channel = null): string
{
    $escape = static fn($value): string => htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    $options = ['' => 'Alle', 'release' => 'Release', 'nightly' => 'Nightly', 'alpha' => 'Alpha', 'unknown' => 'Unbekannt'];
    $selected = $channel ?? ($_GET['channel'] ?? '');
    $selected = is_string($selected) ? strtolower(trim($selected)) : '';
    if (!array_key_exists($selected, $options)) {
        $selected = '';
    }
    $allCount = count($rows);
    if ($selected !== '') {
        $rows = array_values(array_filter($rows, static fn(array $row): bool => $row['channel'] === $options[$selected]));
    }
    $html = '<section id="xvault-versionen" class="panel" style="grid-column:1/-1"><h2>xVAULT-Versionen – vollständig</h2>';
    $html .= '<p class="muted">Alle aktuell gemeldeten Installationsstände, neueste Version zuerst. '
        . 'Der gewählte Diagrammzeitraum begrenzt diese Bestandsliste nicht. '
        . 'Versionen vor dem 24.10.2026 folgen dem damaligen Release-/Alpha-Schema.</p>';
    $html .= '<form method="get" action="#xvault-versionen" style="display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:16px 0">';
    foreach (['range', 'os'] as $key) {
        if (isset($_GET[$key]) && is_string($_GET[$key])) {
            $html .= '<input type="hidden" name="' . $key . '" value="' . $escape($_GET[$key]) . '">';
        }
    }
    $html .= '<label for="xvault-channel">Kanal</label><select id="xvault-channel" name="channel" '
        . 'style="font:inherit;padding:8px;background:#161b22;color:#e6edf3;border:1px solid #667085;border-radius:6px">';
    foreach ($options as $value => $label) {
        $html .= '<option value="' . $value . '"' . ($selected === $value ? ' selected' : '') . '>' . $label . '</option>';
    }
    $html .= '</select><button type="submit" style="font:inherit;padding:8px 14px;cursor:pointer;'
        . 'background:#161b22;color:#e6edf3;border:1px solid #667085;border-radius:6px">Anwenden</button></form>';
    $html .= '<p class="muted">' . count($rows) . ' von ' . $allCount . ' Versionsständen'
        . ($selected !== '' ? ' · Kanal: ' . $options[$selected] : ' · Alle Kanäle') . '</p>';
    if (!$rows) {
        return $html . '<p class="muted">' . ($selected !== '' ? 'Keine Versionsdaten für diesen Kanal vorhanden.' : 'Keine Versionsdaten vorhanden.') . '</p></section>';
    }
    $html .= '<div style="overflow-x:auto"><table><thead><tr><th>Version</th><th>Kanal</th>'
        . '<th>Installationen</th><th>Zuletzt gemeldet (Serverzeit)</th></tr></thead><tbody>';
    foreach ($rows as $row) {
        $html .= '<tr data-channel="' . $escape($row['channel']) . '"><td>' . $escape($row['version'])
            . '</td><td>' . $escape($row['channel']) . '</td><td>' . (int)$row['installations']
            . '</td><td>' . $escape($row['last_seen'] ?: 'unbekannt') . '</td></tr>';
    }
    return $html . '</tbody></table></div></section>';
}
