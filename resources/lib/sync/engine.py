"""Revision-based device sync. SQLite persists the outbox before network I/O.

Only explicit local edits enter the outbox. Applying a remote snapshot never
imports local playcount rows as new changes. Client clocks are display-only.
"""
import contextlib
import hashlib
import json
import os
import sqlite3
import time
import uuid

from resources.lib.sync import storage, device


def _path():
    account = hashlib.sha256(storage.email().lower().encode('utf-8')).hexdigest()[:24]
    return storage.profile_path('sync_v2_%s.db' % account)


@contextlib.contextmanager
def database(path=None):
    # A SQLite transaction is also the cross-process local lock (service/player/UI).
    conn = sqlite3.connect(path or _path(), timeout=15)
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, data TEXT NOT NULL, attempted INTEGER NOT NULL DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS lease (id INTEGER PRIMARY KEY, owner TEXT, expires REAL)')
        conn.commit()
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT data FROM state WHERE id=1').fetchone()
        state = json.loads(row[0]) if row else {'revision': 0, 'entities': [], 'favorites': None}
        yield conn, state
        conn.execute('INSERT OR REPLACE INTO state VALUES (1, ?)', (json.dumps(state),))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _entity(state, kind, key):
    return next((e for e in state.get('entities', []) if e['kind'] == kind and e['key'] == key), None)


def enqueue(conn, state, kind, key, patch, deleted=False, resolves=None):
    existing = _entity(state, kind, key)
    base = existing['revision'] if existing else -1
    # Coalesce only operations that have never left the device. A timed-out
    # request retains its ID and exact payload until the server acknowledges it.
    for op_id, raw in conn.execute('SELECT id, data FROM outbox WHERE attempted=0').fetchall():
        op = json.loads(raw)
        if op['kind'] == kind and op['key'] == key and not op.get('resolves') and not resolves:
            op['patch'].update(patch)
            op['deleted'] = deleted
            conn.execute('UPDATE outbox SET data=? WHERE id=?', (json.dumps(op), op_id))
            return
    op = {'id': str(uuid.uuid4()), 'kind': kind, 'key': key, 'base_revision': base, 'patch': patch, 'deleted': deleted}
    if resolves:
        op['resolves'] = resolves
    conn.execute('INSERT INTO outbox (id, data) VALUES (?, ?)', (op['id'], json.dumps(op)))


def record(item, kind='progress', session_id=None, base_revision=None):
    if not storage.is_enabled() or not storage.is_logged_in():
        return False
    with database() as (conn, state):
        value = dict(item)
        if session_id:
            value['session_id'] = session_id
        # Events are durable even while another worker is exchanging a snapshot.
        event = {'kind': kind, 'key': item['item_key'], 'value': value, 'base_revision': base_revision}
        conn.execute('INSERT INTO events VALUES (?, ?)', (str(uuid.uuid4()), json.dumps(event)))
    return True


def _capture(conn, state):
    from resources.lib.sync import favorites_sync
    entries = {e['key']: favorites_sync._delta_payload(e) for e in favorites_sync._delta_entries()}
    baseline = state.get('favorites')
    if baseline is not None:
        for key, entry in entries.items():
            previous = baseline.get(key, {})
            patch = {k: v for k, v in entry.items() if k != 'key' and previous.get(k) != v}
            if patch:
                enqueue(conn, state, 'favorite', key, patch)
        for key in baseline.keys() - entries.keys():
            enqueue(conn, state, 'favorite', key, {}, deleted=True)
    # A first connection does not assume all local favorites are new edits.
    # Import missing local entries only after the first authoritative snapshot.
    state['favorites'] = entries
    for event_id, raw in conn.execute('SELECT id, data FROM events ORDER BY rowid').fetchall():
        event = json.loads(raw)
        enqueue(conn, state, event['kind'], event['key'], {'value': event['value']})
        if event.get('base_revision') is not None:
            # Playback is based on the state seen before playback began, not a
            # snapshot pulled by the service while this session was playing.
            for op_id, op_raw in conn.execute('SELECT id, data FROM outbox WHERE attempted=0').fetchall():
                op = json.loads(op_raw)
                if op['kind'] == event['kind'] and op['key'] == event['key']:
                    op['base_revision'] = event['base_revision']
                    conn.execute('UPDATE outbox SET data=? WHERE id=?', (json.dumps(op), op_id))
        conn.execute('DELETE FROM events WHERE id=?', (event_id,))


def synchronize(client=None, apply_bookmarks=True, active=False):
    if not storage.is_enabled() or not storage.is_logged_in():
        return False
    from resources.lib.sync.api_client import Client
    from resources.lib import control
    client = client or Client()
    account = storage.email()
    path = _path()
    owner = str(uuid.uuid4())
    with database(path) as (conn, state):
        lease = conn.execute('SELECT owner, expires FROM lease WHERE id=1').fetchone()
        if lease and lease[1] > time.time():
            return False
        conn.execute('INSERT OR REPLACE INTO lease VALUES (1, ?, ?)', (owner, time.time() + 120))
        first = state.get('favorites') is None
        if first:
            from resources.lib.sync import binge_sync
            # Retain the pre-migration local copy for recovery. Only missing
            # server entries may be bootstrapped; existing server data wins.
            state['legacy_items'] = binge_sync.load_items()
        _capture(conn, state)
        operations = [json.loads(row[0]) for row in conn.execute('SELECT data FROM outbox ORDER BY rowid LIMIT 200')]
        for op in operations:
            conn.execute('UPDATE outbox SET attempted=1 WHERE id=?', (op['id'],))
        request = {'device_id': device.get_device_id(), 'device_name': device.get_device_name(), 'cursor': state.get('revision', 0), 'operations': operations, 'active': active}
    # Outbox and attempted flags are committed before making the request.
    try:
        response = client.exchange(request)
        if response.get('protocol') != 2:
            raise RuntimeError('Server unterstützt den Geräteabgleich nicht.')
        if storage.email() != account or not storage.is_logged_in():
            return False
        with database(path) as (conn, state):
            lease = conn.execute('SELECT owner FROM lease WHERE id=1').fetchone()
            if not lease or lease[0] != owner:
                return False
            for result in response.get('results', []):
                if result['status'] in ('accepted', 'conflict'):
                    conn.execute('DELETE FROM outbox WHERE id=?', (result['id'],))
            # Capture edits made while the HTTP request was running before
            # replacing the visible favorites with the returned snapshot.
            _capture(conn, state)
            state.update({k: response[k] for k in ('revision', 'entities', 'devices', 'activity', 'conflicts')})
            notices = []
            for conflict in response.get('conflicts', []):
                op = json.loads(conflict['operation_json'])
                notices.append('%s:%s:%s:%s' % (op['kind'], op['key'], conflict['device_id'], op.get('patch', {}).get('value', {}).get('session_id', '')))
            notify = bool(set(notices) - set(state.get('conflict_notice', [])))
            state['conflict_notice'] = notices
            if first:
                from resources.lib.sync import binge_sync
                remote = {e['key'] for e in response['entities'] if e['kind'] == 'favorite'}
                for key, entry in state['favorites'].items():
                    if key not in remote:
                        enqueue(conn, state, 'favorite', key, {k: v for k, v in entry.items() if k != 'key'})
                known = {(e['kind'], e['key']) for e in response['entities']}
                known.update((o['kind'], o['key']) for o in (json.loads(r[0]) for r in conn.execute('SELECT data FROM outbox')))
                for old_item in state.get('legacy_items', []):
                    item = binge_sync.normalize_legacy_item(old_item)
                    kind = 'watch' if item.get('provider') in ('xvault-manual', 'xvault-playcount') else 'progress'
                    if (kind, item['item_key']) not in known:
                        enqueue(conn, state, kind, item['item_key'], {'value': item})
            _apply(conn, state, apply_bookmarks)
            bootstrap_pending = first and conn.execute('SELECT COUNT(*) FROM outbox').fetchone()[0] > 0
            conn.execute('DELETE FROM lease WHERE id=1 AND owner=?', (owner,))
        storage.update_last_sync(time.strftime('%Y-%m-%d %H:%M:%S'))
        storage.set_status('Angemeldet als %s' % storage.email())
        if notify:
            control.infoDialog('Sync-Konflikte vorhanden: unter Geräte & Sync-Verlauf prüfen.', icon='WARNING')
        if bootstrap_pending:
            return synchronize(client=client, apply_bookmarks=apply_bookmarks, active=active)
        return True
    finally:
        with database(path) as (conn, state):
            conn.execute('DELETE FROM lease WHERE id=1 AND owner=?', (owner,))


def _apply(conn, state, apply_bookmarks):
    from resources.lib.sync import favorites_sync, binge_sync
    from resources.lib import control
    favorites = {e['key']: dict(e['data'], key=e['key']) for e in state['entities'] if e['kind'] == 'favorite' and not e['deleted']}
    # Unacknowledged local changes remain visible and are never silently lost.
    for raw, in conn.execute('SELECT data FROM outbox ORDER BY rowid'):
        op = json.loads(raw)
        if op['kind'] != 'favorite':
            continue
        if op.get('deleted'):
            favorites.pop(op['key'], None)
        else:
            favorites.setdefault(op['key'], {'key': op['key']}).update(op['patch'])
    entries = favorites_sync._sort_delta_entries(favorites.values())
    raw = favorites_sync._build_xml(entries)
    if favorites_sync.favorites_hash(raw) != favorites_sync.favorites_hash():
        favorites_sync.write_favourites(raw, backup=True)
    # Kodi's XML stores list position, not the server's explicit order field.
    # Baseline the rendered list so ties from independent additions do not
    # become artificial "local edits" on the next poll.
    state['favorites'] = {e['key']: favorites_sync._delta_payload(e) for e in favorites_sync._delta_entries(raw)}
    favorites_sync.mark_delta_synced(raw, state['revision'])
    # Never replace a bookmark or watched state while any video is playing.
    import xbmc
    if not apply_bookmarks or xbmc.Player().isPlayingVideo():
        return
    local_ops = [json.loads(r[0]) for r in conn.execute('SELECT data FROM outbox ORDER BY rowid')]
    events = [json.loads(r[0]) for r in conn.execute('SELECT data FROM events ORDER BY rowid')]
    pending = {o['key'] for o in local_ops + events}
    items = {e['key']: e['data']['value'] for e in state['entities'] if e['kind'] == 'progress' and not e['deleted']}
    watch_entities = {e['key']: e for e in state['entities'] if e['kind'] == 'watch' and not e['deleted']}
    for op in local_ops + events:
        value = op.get('patch', {}).get('value') or op.get('value')
        if op['kind'] == 'progress' and value:
            items[op['key']] = value
        elif op['kind'] == 'watch' and value:
            watch_entities[op['key']] = {'key': op['key'], 'revision': state['revision'], 'data': {'value': value}}
    for entity in watch_entities.values():
        item = dict(items.get(entity['key'], {}))
        watch = entity['data']['value']
        if not item:
            item = dict(watch)
        item['completed'] = watch.get('completed', False)
        item['watch_state'] = 'watched' if item['completed'] else 'unwatched'
        if not item['completed'] and entity['key'] not in pending:
            binge_sync.apply_to_unwatched(watch)
            progress = _entity(state, 'progress', entity['key'])
            if progress is None or entity['revision'] > progress['revision']:
                from resources.lib import bookmarkDB
                bookmarkDB.remove_query(binge_sync._bookmark_id(item.get('name') or item.get('title'), item.get('year') or '0'), 'bookmarks')
                item['position_seconds'] = 0
        items[entity['key']] = item
    storage.write_json(binge_sync.FILENAME, {'schema_version': 2, 'items': list(items.values())})
    for key, item in items.items():
        if item.get('completed') and key not in pending:
            from resources.lib import bookmarkDB
            bookmarkDB.remove_query(binge_sync._bookmark_id(item.get('name') or item.get('title'), item.get('year') or '0'), 'bookmarks')
    binge_sync.apply_to_bookmarks([v for k, v in items.items() if k not in pending])


def playback_base(key, kind='progress'):
    with database() as (_, state):
        entity = _entity(state, kind, key)
        return entity['revision'] if entity else -1


def inspect():
    with database() as (conn, state):
        result = dict(state)
        result['pending'] = conn.execute('SELECT COUNT(*) FROM outbox').fetchone()[0] + conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        return result


def resolve(conflict, use_local):
    op = json.loads(conflict['operation_json'])
    with database() as (conn, state):
        current = _entity(state, op['kind'], op['key'])
        patch = op['patch'] if use_local else (current or {}).get('data', {})
        deleted = op.get('deleted', False) if use_local else (current or {}).get('deleted', False)
        enqueue(conn, state, op['kind'], op['key'], patch, deleted, conflict['operation_id'])


def on_wake():
    try:
        synchronize(active=True)
    except Exception:
        pass  # A failed network request remains in the durable outbox.
