"""Patch the existing protected PHP dashboard without storing its credentials."""
import re


def upgrade(source: str) -> str:
    if 'xvault_stats_versions($pdo)' in source:
        return source
    replacements = [
        (r'^\$versionRows = query_rows\([^\n]+\);',
         "require_once __DIR__ . '/version_stats.php';\n$versionStats = xvault_stats_versions($pdo);"),
        (r'^\$variantRows = query_rows\([^\n]+\);', "$variantRows = $versionStats['channels'];"),
        (r"table_block\('Varianten', \$variantRows\)", "table_block('Release / Nightly / Alpha', $variantRows)"),
        (r"table_block\('xVAULT-Versionen', \$versionRows\)", "xvault_stats_versions_html($versionStats['versions'])"),
    ]
    for pattern, replacement in replacements:
        source, count = re.subn(pattern, lambda _: replacement, source, flags=re.M)
        if count != 1:
            raise ValueError('Unexpected dashboard layout: ' + pattern)
    return source
