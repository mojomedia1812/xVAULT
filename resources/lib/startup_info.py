# edit 2026-06-14

import json
import os
import re
import time

import xbmcgui

from resources.lib import control


STATE_FILE = os.path.join(control.addonProfilePath, 'startup_info.json')
CHANGELOG_FILE = os.path.join(control.addonPath, 'CHANGELOG.txt')

INTRO_TEXT = """## xVAULT

**xVAULT ist eine Weiterentwicklung von xShip.**

Mit xVAULT führen wir den Gedanken von xShip weiter und bauen auf einer Grundlage auf, die über viele Jahre mit großem Einsatz, Können und Leidenschaft geschaffen wurde.

Unser ausdrücklicher Dank gilt dem ursprünglichen **Team xShip**, insbesondere den öffentlich bekannten Mitwirkenden aus dem xShip-Umfeld, für ihre langjährige Arbeit und ihr Engagement.

xShip war für viele Nutzer ein vertrautes und geschätztes Projekt. Die geleistete Arbeit verdient Anerkennung, Dank und Respekt — besonders für die Zeit, die Mühe und die technische Qualität bis zur Einstellung des Projekts.

Für den Bereich **Live TV** gilt unser besonderer Dank **michaz1988**. Dieser Bereich basiert auf seiner Entwicklung und konnte nur durch seine Arbeit in **xVAULT** integriert werden.

**Danke an das Team xShip.
Danke an michaz1988.
Danke für die Basis.
Danke für eure Arbeit.**

xVAULT blickt nach vorn, ohne zu vergessen, worauf es aufbaut."""


def show_pending_startup_info():
    """Show first-start or update information once for the current version."""
    try:
        state = _load_state()
        current_version = control.addonVersion
        previous_version = _pending_previous_version(state, current_version)
        intro_seen = _intro_seen(state)

        if intro_seen and previous_version and _compare_versions(current_version, previous_version) > 0:
            _show_update_info(previous_version, current_version)
            _store_current_state(state, current_version)
            return

        if not intro_seen:
            _show_text('xVAULT', INTRO_TEXT)
            _store_current_state(state, current_version, intro_seen=True)
            return

        if state.get('last_started_version') != current_version:
            _store_current_state(state, current_version)
    except Exception:
        pass


def record_pending_update(previous_version, target_version):
    """Persist update context for the first start after xVAULT updates itself."""
    try:
        state = _load_state()
        state['pending_update_from'] = previous_version
        state['pending_update_to'] = target_version
        state['updated_at'] = int(time.time())
        _save_state(state)
    except Exception:
        pass


def _pending_previous_version(state, current_version):
    pending_from = state.get('pending_update_from')
    pending_to = state.get('pending_update_to')
    if pending_from and (not pending_to or pending_to == current_version):
        return pending_from

    previous = state.get('last_started_version')
    if previous and previous != current_version:
        return previous

    if not previous and _intro_seen(state):
        return _previous_release_before(current_version)

    return None


def _intro_seen(state):
    return bool(state.get('intro_screen_seen') or state.get('intro_seen'))


def _show_update_info(previous_version, current_version):
    changes = _changes_between(previous_version, current_version)
    if not changes:
        changes = _changes_between('', current_version)

    lines = [
        'xVAULT wurde aktualisiert.',
        '',
        'Vorherige Version: %s' % previous_version,
        'Aktuelle Version: %s' % current_version,
        '',
        'Änderungen seit der zuletzt benutzten Version:',
        '',
    ]

    if changes:
        for release in changes:
            lines.append('xVAULT %s' % release['version'])
            lines.append('Entwickler: %s' % release['developer'])
            for item in release['items']:
                lines.append('- %s' % item)
            lines.append('')
    else:
        lines.append('Für diesen Versionsbereich wurden keine Changelog-Einträge gefunden.')

    _show_text('xVAULT Aktualisierung', '\n'.join(lines).rstrip())


def _changes_between(previous_version, current_version):
    releases = _read_changelog()
    result = []
    for release in releases:
        version = release['version']
        if current_version and _compare_versions(version, current_version) > 0:
            continue
        if previous_version and _compare_versions(version, previous_version) <= 0:
            continue
        result.append(release)
    return result


def _read_changelog():
    try:
        with open(CHANGELOG_FILE, 'r', encoding='utf-8') as handle:
            lines = handle.read().splitlines()
    except TypeError:
        with open(CHANGELOG_FILE, 'r') as handle:
            lines = handle.read().decode('utf-8').splitlines()
    except Exception:
        return []

    releases = []
    current = None
    for line in lines:
        header = re.match(r'^xVAULT\s+([0-9][^\s]*)', line.strip())
        if header:
            if current:
                releases.append(current)
            current = {
                'version': header.group(1),
                'developer': 'Unbekannt',
                'items': [],
            }
            continue

        if not current:
            continue

        developer = re.match(r'^Entwickler:\s*(.+)', line.strip())
        if developer:
            current['developer'] = developer.group(1).strip()
            continue

        item = re.match(r'^\s*-\s+(.+)', line)
        if item:
            current['items'].append(item.group(1).strip())

    if current:
        releases.append(current)
    return releases


def _previous_release_before(version):
    older = [
        release['version']
        for release in _read_changelog()
        if _compare_versions(release['version'], version) < 0
    ]
    return older[0] if older else None


def _show_text(heading, text):
    dialog = xbmcgui.Dialog()
    if hasattr(dialog, 'textviewer'):
        dialog.textviewer(heading, text)
    else:
        dialog.ok(heading, text)


def _load_state():
    try:
        with open(STATE_FILE, 'r') as handle:
            return json.load(handle)
    except Exception:
        return {}


def _store_current_state(state, version, intro_seen=None):
    state['last_started_version'] = version
    if intro_seen is not None:
        state['intro_seen'] = intro_seen
        state['intro_screen_seen'] = intro_seen
        if intro_seen:
            state['intro_screen_seen_version'] = version
    elif _intro_seen(state):
        state['intro_seen'] = True
        state['intro_screen_seen'] = True
        if not state.get('intro_screen_seen_version'):
            state['intro_screen_seen_version'] = version
    elif 'intro_seen' not in state:
        state['intro_seen'] = True
        state['intro_screen_seen'] = True
        state['intro_screen_seen_version'] = version
    state.pop('pending_update_from', None)
    state.pop('pending_update_to', None)
    state['updated_at'] = int(time.time())
    _save_state(state)


def _save_state(state):
    directory = os.path.dirname(STATE_FILE)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    with open(STATE_FILE, 'w') as handle:
        json.dump(state, handle, indent=2, sort_keys=True)


def _compare_versions(left, right):
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    length = max(len(left_parts), len(right_parts))

    for i in range(length):
        left_part = left_parts[i] if i < len(left_parts) else (1, 0)
        right_part = right_parts[i] if i < len(right_parts) else (1, 0)
        if left_part == right_part:
            continue
        return 1 if left_part > right_part else -1
    return 0


def _version_parts(version):
    parts = []
    for part in re.findall(r'\d+|[A-Za-z]+', str(version or '0')):
        if part.isdigit():
            parts.append((1, int(part)))
        else:
            parts.append((0, part.lower()))
    return parts
