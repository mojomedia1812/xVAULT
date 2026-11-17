"""Shared playback actions. Hiding is local; explicit resets travel via sync CAS."""
import contextlib
import hashlib
import json
import os
import sqlite3
import time
import uuid
from urllib.parse import urlencode

from resources.lib import control


def normalize(meta):
    value = dict(meta)
    value['title'] = value.get('systitle') or value.get('title') or value.get('showtitle') or value.get('name') or ''
    value['imdb_id'] = value.get('imdb_id') or value.get('imdbnumber') or value.get('imdb') or ''
    if value.get('episode') is not None:
        value['mediatype'] = 'episode'
    elif value.get('season') is not None:
        value['mediatype'] = 'season'
    else:
        value.setdefault('mediatype', 'movie')
    value.setdefault('year', '0')
    if not value.get('sysname'):
        if value['mediatype'] == 'episode':
            value['sysname'] = '%s S%02dE%02d' % (value['title'], int(value['season']), int(value['episode']))
        elif value['mediatype'] == 'movie':
            value['sysname'] = '%s (%s)' % (value['title'], value['year'])
        else:
            value['sysname'] = value['title']
    return value


def probe(meta):
    from resources.lib.sync import binge_sync
    return binge_sync._manual_watch_item(normalize(meta), False)


def matches(left, right):
    from resources.lib.sync import binge_sync
    a, b = left.get('extra') or {}, right.get('extra') or {}
    if any(a.get(k) and b.get(k) and str(a[k]) != str(b[k]) for k in ('imdb_id', 'tmdb_id')):
        return False
    return bool(set(binge_sync._candidate_keys(left)).intersection(binge_sync._candidate_keys(right)))


@contextlib.contextmanager
def views():
    from resources.lib.sync import storage
    # Account-specific hiding must not leak between accounts on the same device.
    scope = hashlib.sha256(storage.email().strip().lower().encode('utf-8')).hexdigest()
    os.makedirs(control.dataPath, exist_ok=True)
    conn = sqlite3.connect(os.path.join(control.dataPath, 'playback_views.sqlite'), timeout=5)
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS hidden (scope TEXT, key TEXT, meta TEXT, PRIMARY KEY(scope,key))')
        yield conn, scope
        conn.commit()
    finally:
        conn.close()


def hidden(meta):
    item = probe(meta)
    with views() as (conn, scope):
        return any(matches(item, json.loads(raw)) for raw, in conn.execute('SELECT meta FROM hidden WHERE scope=?', (scope,)))


def hide(meta):
    item = probe(meta)
    with views() as (conn, scope):
        conn.execute('INSERT OR REPLACE INTO hidden VALUES (?,?,?)', (scope, item['item_key'], json.dumps(item)))


def started(meta):
    """A deliberate successful restart makes a hidden title visible again."""
    item = probe(meta)
    with views() as (conn, scope):
        keys = [key for key, raw in conn.execute('SELECT key,meta FROM hidden WHERE scope=?', (scope,)) if matches(item, json.loads(raw))]
        conn.executemany('DELETE FROM hidden WHERE scope=? AND key=?', [(scope, key) for key in keys])


def restore_hidden():
    with views() as (conn, scope):
        conn.execute('DELETE FROM hidden WHERE scope=?', (scope,))


def context_items(meta):
    meta = normalize(meta)
    if not meta['title']:
        return []
    actions = [('Als gesehen markieren · xVAULT', 'watched'), ('Als ungesehen markieren · xVAULT', 'unwatched')]
    if meta['mediatype'] in ('movie', 'episode'):
        actions += [('Aus Weiterschauen ausblenden (Position behalten)', 'hide'), ('Wiedergabeposition zurücksetzen …', 'reset')]
    return [(label, 'RunPlugin(plugin://plugin.video.xvault/?%s)' % urlencode(
        {'action': 'playbackAction', 'operation': op, 'sysmeta': json.dumps(meta)})) for label, op in actions]


def merge_context(items, meta):
    return [(label, command) for label, command in items if 'action=UpdatePlayCount' not in command] + context_items(meta)


def decorate(item, meta):
    """Give every renderer the same explicit watch/resume state."""
    from resources.lib.sync import binge_sync
    wanted = probe(meta)
    states = [i for i in binge_sync.load_items() if matches(wanted, i)]
    if not states:
        return
    state = max(states, key=lambda i: i.get('updated_at') or '')
    tag = item.getVideoInfoTag()
    tag.setPlaycount(1 if state.get('completed') else 0)
    position = 0 if state.get('completed') or state.get('progress_reset') else float(state.get('position_seconds') or 0)
    tag.setResumePoint(position, float(state.get('duration_seconds') or 0))


def _replace(item):
    from resources.lib.sync import binge_sync, storage
    # A manual reset is authoritative locally, including same-second changes.
    items = [old for old in binge_sync.load_items() if not matches(item, old)]
    if not storage.write_json(binge_sync.FILENAME, {'schema_version': 2, 'items': items + [item]}):
        raise OSError('Wiedergabedaten konnten nicht gespeichert werden')


def reset_progress(meta, watched=None, write_native=True):
    from resources.lib.sync import binge_sync, engine
    from resources.lib import bookmarkDB
    meta = normalize(meta)
    item = probe(meta)
    old = [old for old in binge_sync.load_items() if matches(item, old)]
    if old:
        item = dict(max(old, key=lambda i: i.get('updated_at') or ''))
    if watched is not None:
        item.update(completed=bool(watched), watch_state='watched' if watched else 'unwatched', watched_percent=100 if watched else 0)
    item.update(position_seconds=0, duration_seconds=0, progress_reset=True,
                session_id='reset:' + str(uuid.uuid4()), sequence=0, updated_at=binge_sync.iso_now())
    item.setdefault('extra', {})['meta'] = meta
    _replace(item)
    keys = {binge_sync._bookmark_id(i.get('name') or i.get('title'), i.get('year') or '0') for i in old + [item]}
    keys.add(binge_sync._bookmark_id(meta['sysname'], meta['year']))
    bookmarkDB.update_queries({}, keys, 'bookmarks')
    binge_sync.apply_local_states({item['item_key']: item}, {item['item_key']}, apply_library=False)
    # A new session prevents stale checkpoints of the old session bypassing CAS.
    engine.record(item, kind='progress', session_id=item['session_id'])
    if watched is not None:
        engine.record(item, kind='watch')
    if write_native:
        from resources.lib import library_state
        library_state.write(meta, completed=watched, position=0, total=0)
    engine.request_background(active=True)
    return item


def set_watched(meta, watched, write_native=True):
    from resources.lib.sync import binge_sync
    from resources.lib import personal
    meta = normalize(meta)
    # A series/season action also resets known episode progress in its scope.
    if meta['mediatype'] in ('tvshow', 'season'):
        for item in list(binge_sync.load_items()):
            child = personal.item_meta(item)
            same_show = matches(probe(dict(meta, mediatype='tvshow', season=None, episode=None)),
                                probe(dict(child, mediatype='tvshow', season=None, episode=None)))
            if child.get('mediatype') == 'episode' and same_show and (meta['mediatype'] == 'tvshow' or str(child.get('season')) == str(meta.get('season'))):
                reset_progress(child, watched, write_native=write_native)
    return reset_progress(meta, watched, write_native=write_native)


def _idle():
    import xbmc
    if xbmc.Player().isPlayingVideo():
        control.infoDialog('Bitte zuerst die laufende Wiedergabe beenden.')
        return False
    return True


def _confirm(text):
    import xbmcgui
    from resources.lib.sync import storage
    scope = '\nBei aktivem Konto-Sync gilt das Zurücksetzen auch auf verbundenen Geräten.' if storage.is_enabled() and storage.is_logged_in() else '\nDiese Änderung betrifft die lokalen Wiedergabedaten.'
    return xbmcgui.Dialog().yesno('Wiedergabedaten', text + scope + '\nFavoriten und Anmeldungen bleiben erhalten.')


def backup():
    """Back up only playback files, never credentials or the sync operation queue."""
    import shutil
    target = os.path.join(control.dataPath, 'playback-backups', time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    os.makedirs(target, exist_ok=True)
    for name in ('sync_binge_state.json', 'playcount.db', 'playback_views.sqlite', 'bookmarks.pcl'):
        source = os.path.join(control.dataPath, name)
        if not os.path.isfile(source):
            continue
        if name.endswith(('.db', '.sqlite')):
            with sqlite3.connect(source) as src, sqlite3.connect(os.path.join(target, name)) as dst:
                src.backup(dst)
        else:
            shutil.copy2(source, os.path.join(target, name))
    return target


def dispatch(params):
    import xbmcgui
    operation = params.get('operation')
    if not _idle():
        return
    meta = json.loads(params.get('sysmeta') or '{}')
    if operation == 'hide':
        hide(meta)
    elif operation in ('watched', 'unwatched', 'reset'):
        if operation == 'reset' and not _confirm('Wiedergabeposition dieses Titels zurücksetzen? Der Gesehen-Status bleibt erhalten.'):
            return
        if operation == 'reset':
            reset_progress(meta)
        else:
            set_watched(meta, operation == 'watched')
            try:
                from resources.lib import trakt
                trakt.update_watch_status_from_params({'meta': json.dumps(normalize(meta)), 'playCount': '1' if operation == 'watched' else '0'}, silent=True)
            except Exception:
                pass
    elif operation == 'restore':
        restore_hidden()
    elif operation in ('resetAll', 'unwatchAll'):
        if not _confirm('Alle gespeicherten Wiedergabepositionen zurücksetzen?' if operation == 'resetAll' else 'Alle gespeicherten Gesehen-Markierungen und Positionen zurücksetzen?'):
            return
        backup()
        from resources.lib import personal
        from resources.lib.sync import binge_sync
        items = list(binge_sync.load_items())
        if operation == 'unwatchAll':
            items += binge_sync.collect_local_playcount_items()
        seen = set()
        for item in items:
            if item['item_key'] in seen:
                continue
            seen.add(item['item_key'])
            reset_progress(personal.item_meta(item), False if operation == 'unwatchAll' else None)
        from resources.lib import bookmarkDB
        with bookmarkDB._get_storage('bookmarks') as store:
            store['queries'] = []
    elif operation == 'radioClear':
        if not xbmcgui.Dialog().yesno('Radioverlauf löschen', 'Nur die Liste zuletzt gehörter Sender auf diesem Gerät löschen? Radiofavoriten bleiben erhalten.'):
            return
        from resources.lib import radio
        target = backup()
        with open(os.path.join(target, 'radio-history.json'), 'w', encoding='utf-8') as handle:
            json.dump(radio.stored('radio.history'), handle, ensure_ascii=False)
        radio.addon().setSetting('radio.history', '{}')
    control.execute('Container.Refresh')


def manage():
    import sys
    import xbmcplugin
    from resources.lib import personal
    for label, op in [('Ausgeblendete Titel wieder anzeigen (dieses Gerät)', 'restore'),
                      ('Alle Wiedergabepositionen zurücksetzen …', 'resetAll'),
                      ('Gesehen-Status und Positionen vollständig zurücksetzen …', 'unwatchAll'),
                      ('Zuletzt gehörte Radiosender löschen …', 'radioClear')]:
        import xbmcgui
        item = xbmcgui.ListItem(label=label, offscreen=True)
        item.setInfo('video', {'plot': 'Favoriten, Konten und Zugangsdaten bleiben erhalten. Vor umfassenden Änderungen wird eine lokale Sicherung der Wiedergabedaten erstellt.'})
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), personal.url('playbackAction', operation=op), item, False)
    xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc=False)
