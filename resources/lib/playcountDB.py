

#2021-07-05

import sys, ast
from os import path, stat
from sqlite3 import dbapi2 as db
from sqlite3 import Error as sqlError
from xbmcvfs import mkdir, exists
from resources.lib.control import dataPath, parse_qsl

if not exists(dataPath): mkdir(dataPath)

# DB fÃ¼r Playcount
playcountDB = path.join(dataPath, 'playcount.db')

def _getParams(_params):
    for key, value in _params.items():
        try:
            exec("%s = %s" % (key, value))
        except:
            exec ("%s = '%s'" % (key, value))

def _createSql(table): # IF NOT EXISTS - kÃ¶nnte man auch entfernen
    sql = ''
    if table == 'movie':
        sql = "CREATE TABLE IF NOT EXISTS %s (" \
              "title TEXT, " "name TEXT, " "imdb_id TEXT, " \
              "playcount INT )" % table
    elif table == 'tvshow':
        sql = "CREATE TABLE IF NOT EXISTS %s (" \
              "title TEXT, " "name TEXT, " "imdb_id TEXT, " "number_of_seasons INT, " \
              "playcount INT )" % table
    elif table == 'season':
        sql = "CREATE TABLE IF NOT EXISTS %s (" \
              "title TEXT, " "name TEXT, " "season INT, " "number_of_episodes INT, " \
              "playcount INT)" % table
    elif table == 'episode':
        sql = "CREATE TABLE IF NOT EXISTS %s (" \
              "title TEXT, " "name TEXT, " "season INT, " "episode INT, " \
              "playcount INT)" % table
    return sql

# einmalig Tabellen in der DB anlegen wenn die DateigrÃ¶ÃŸe von der Datenbank Datei 0 ist
if not exists(playcountDB) or stat(playcountDB).st_size == 0: # size DB
    conn = db.connect(playcountDB)
    try:
        cursor = conn.cursor()
        tables = ['movie','tvshow', 'season', 'episode']
        for i in tables:
            sql = _createSql(i)
            cursor.execute(sql)
        cursor.close()
    except sqlError as e:
        print (e)   # test
    except Exception as e:
        print (e)   # test
    finally:
        if not (conn is None):
            conn.close()


# Achtung wird mit MultiThread benutzt
def getPlaycount(mediatype, column_names, column_value, season=None, episode=None):
    conn = _get_connection(playcountDB)
    cursor = conn.cursor()
    sql_get  = _get(mediatype, column_names, column_value, season, episode)
    cursor.execute(sql_get)
    match = cursor.fetchone()
    cursor.close()
    conn.close()
    playcount = match['playcount'] if match else None
    return playcount


def getWatchedItems():
    conn = _get_connection(playcountDB)
    cursor = conn.cursor()
    watched = {'movies': [], 'episodes': [], 'seasons': [], 'tvshows': []}
    try:
        cursor.execute('SELECT title, name, imdb_id, playcount FROM movie WHERE playcount > 0')
        watched['movies'] = cursor.fetchall()
        cursor.execute('SELECT title, name, season, episode, playcount FROM episode WHERE playcount > 0')
        watched['episodes'] = cursor.fetchall()
        cursor.execute('SELECT title, name, season, number_of_episodes, playcount FROM season WHERE playcount > 0')
        watched['seasons'] = cursor.fetchall()
        cursor.execute('SELECT title, name, imdb_id, number_of_seasons, playcount FROM tvshow WHERE playcount > 0')
        watched['tvshows'] = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return watched


def getEpisodeStatus(title, season, episode):
    conn = _get_connection(playcountDB)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT playcount FROM episode WHERE title = ? AND season = ? AND episode = ? ORDER BY playcount DESC LIMIT 1',
            (title, season, episode),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def getSeasonStatus(title, season):
    conn = _get_connection(playcountDB)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT playcount, number_of_episodes FROM season WHERE title = ? AND season = ? ORDER BY playcount DESC, number_of_episodes DESC LIMIT 1',
            (title, season),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def getTvshowStatus(title):
    conn = _get_connection(playcountDB)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT playcount, number_of_seasons FROM tvshow WHERE title = ? ORDER BY playcount DESC, number_of_seasons DESC LIMIT 1',
            (title,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def setSeasonStatus(title, name, season, number_of_episodes, playcount):
    season = _safe_int(season)
    number_of_episodes = _safe_int(number_of_episodes) or 0
    playcount = 1 if _safe_int(playcount) else 0
    if not title or season is None:
        return
    name = name or '%s S%02d' % (title, season)
    conn = db.connect(playcountDB)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT rowid, playcount, number_of_episodes FROM season WHERE title = ? AND season = ? LIMIT 1', (title, season))
        match = cursor.fetchone()
        if match and int(match[1] or 0) > 0 and playcount == 0:
            previous_total = _safe_int(match[2]) or 0
            if previous_total and number_of_episodes > previous_total:
                _mark_previous_episodes(cursor, title, season, previous_total)
        if match:
            cursor.execute(
                'UPDATE season SET name = ?, number_of_episodes = ?, playcount = ? WHERE title = ? AND season = ?',
                (name, number_of_episodes, playcount, title, season),
            )
        else:
            cursor.execute(
                'INSERT INTO season Values (?, ?, ?, ?, ?)',
                (title, name, season, number_of_episodes, playcount),
            )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def _mark_previous_episodes(cursor, title, season, previous_total):
    for episode in range(1, previous_total + 1):
        name = '%s S%02dE%02d' % (title, season, episode)
        cursor.execute(
            'SELECT rowid FROM episode WHERE title = ? AND season = ? AND episode = ? LIMIT 1',
            (title, season, episode),
        )
        if cursor.fetchone():
            cursor.execute(
                'UPDATE episode SET name = ?, playcount = 1 WHERE title = ? AND season = ? AND episode = ?',
                (name, title, season, episode),
            )
        else:
            cursor.execute(
                'INSERT INTO episode Values (?, ?, ?, ?, ?)',
                (title, name, season, episode, 1),
            )


def setTvshowStatus(title, name, imdb, number_of_seasons, playcount):
    number_of_seasons = _safe_int(number_of_seasons) or 0
    playcount = 1 if _safe_int(playcount) else 0
    if not title:
        return
    name = name or title
    imdb = imdb or ''
    conn = db.connect(playcountDB)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT rowid FROM tvshow WHERE title = ? LIMIT 1', (title,))
        match = cursor.fetchone()
        if match:
            cursor.execute(
                'UPDATE tvshow SET name = ?, imdb_id = ?, number_of_seasons = ?, playcount = ? WHERE title = ?',
                (name, imdb, number_of_seasons, playcount, title),
            )
        else:
            cursor.execute(
                'INSERT INTO tvshow Values (?, ?, ?, ?, ?)',
                (title, name, imdb, number_of_seasons, playcount),
            )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def countWatchedSeasons(title):
    conn = _get_connection(playcountDB)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(DISTINCT season) AS total FROM season WHERE title = ? AND season > 0 AND playcount > 0', (title,))
        row = cursor.fetchone()
        return row['total'] if row else 0
    finally:
        cursor.close()
        conn.close()


def _safe_int(value):
    try:
        return int(value)
    except Exception:
        return None

def _has_value(value):
    return value is not None and value != ''


def _get_connection(filename):
    conn = db.connect(filename)
    conn.row_factory = _dict_factory
    return conn

def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def _get(mediatype, column_names, column_value, season, episode):
    if mediatype == 'movie':
        sql_get = 'SELECT playcount FROM movie WHERE %s="%s"' % (column_names, column_value)
    elif _has_value(season) and _has_value(episode):
        sql_get = 'SELECT playcount FROM episode WHERE %s="%s" and season=%s and episode=%s' % (column_names, column_value, season, episode)
    elif _has_value(season):
        sql_get = 'SELECT playcount FROM season WHERE %s = "%s" and season = %s' % (column_names, column_value, season)
    else:
        sql_get = 'SELECT playcount FROM tvshow WHERE %s = "%s"' % (column_names, column_value)
    return sql_get


def createEntry(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, episode):
    if mediatype == 'movie':
        _createEntry(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, episode, column_names = 'name')
    if _has_value(season) and _has_value(episode):
        _createEntry(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, episode)
        name = name[:-3]
        _createEntry(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, None)
        name = name[:-4]
        _createEntry(mediatype, title, name, imdb, number_of_seasons, None, number_of_episodes, None)
    elif _has_value(season):
        _createEntry(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, None)
        name = name[:-4]
        _createEntry(mediatype, title, name, imdb, number_of_seasons, None, number_of_episodes, None)
    else:
        _createEntry(mediatype, title, name, imdb, number_of_seasons, None, number_of_episodes, None)


def _createEntry(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, episode, column_names='title'):
    column_value = title if column_names == 'title' else name
    conn = _get_connection(playcountDB)  # dict
    cursor = conn.cursor()
    sql = _get(mediatype, column_names, column_value, season, episode)
    cursor.execute(sql)
    match = cursor.fetchone()
    if match is None:
        sql_insert, sql_value  = _sql_insert(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, episode)
        cursor.execute(sql_insert , sql_value)
        conn.commit()
    cursor.close()
    conn.close()

def _sql_insert(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, episode):
    if mediatype == 'movie':
        sql_insert = __insert_from_dict('movie', 4)
        sql_value = (title, name, imdb, 0)
    elif _has_value(season) and _has_value(episode):
        sql_insert = __insert_from_dict('episode', 5)
        sql_value = (title, name, season, episode, 0)
    elif _has_value(season):
        sql_insert = __insert_from_dict('season', 5)
        sql_value = (title, name, season, number_of_episodes, 0)
    else:
        sql_insert = __insert_from_dict('tvshow', 5)
        sql_value = (title, name, imdb, number_of_seasons, 0)
    return sql_insert, sql_value

def __insert_from_dict(table, size):
    ''' Create a SQL Insert statement with dictionary values '''
    sql = 'INSERT INTO %s ' % table
    format = ', '.join('?' * size)
    sql_insert = sql + 'Values (%s)' % format
    return sql_insert


def UpdatePlaycount(params): # for context menu
    mediatype = systitle = sysname = imdb_id = number_of_seasons = season = number_of_episodes = episode = playCount = ''
    meta = ast.literal_eval(params['meta'])
    if 'mediatype' in meta and meta['mediatype']: mediatype = meta['mediatype']
    if 'systitle' in meta and meta['systitle']: systitle = meta['systitle']
    if 'sysname' in meta and meta['sysname']: sysname = meta['sysname']
    if 'imdb_id' in meta and meta['imdb_id']: imdb_id = meta['imdb_id']
    if 'number_of_seasons' in meta and _has_value(meta['number_of_seasons']): number_of_seasons = meta['number_of_seasons']
    if 'season' in meta and _has_value(meta['season']): season = meta['season']
    if 'number_of_episodes' in meta and _has_value(meta['number_of_episodes']): number_of_episodes = meta['number_of_episodes']
    if 'episode' in meta and _has_value(meta['episode']): episode = meta['episode']
    if 'playCount' in params and params['playCount']: playCount = int(params['playCount'])
    if mediatype == 'movie':
        column_names = 'imdb_id'
        column_value = imdb_id
    else:
        column_names = 'title'
        column_value = systitle

    status = getPlaycount(mediatype, column_names, column_value, season, episode)
    if status is None: createEntry(mediatype, systitle, sysname, imdb_id, number_of_seasons, season, number_of_episodes, episode)
    _updatePlaycount(mediatype, systitle, sysname, imdb_id, number_of_seasons, season, number_of_episodes, episode, playCount)


def updatePlaycount(mediatype, title='', name='', id='', number_of_seasons=None, season=None, number_of_episodes=None, episode=None, playcount=None):
    #createEntry(mediatype, title, name, id, number_of_seasons, season, number_of_episodes, episode)
    _updatePlaycount(mediatype, title, name, id, number_of_seasons, season, number_of_episodes, episode, playcount)


def _updatePlaycount(mediatype, title, name, id, number_of_seasons, season, number_of_episodes, episode, playcount):
    conn = db.connect(playcountDB)
    cursor = conn.cursor()
    try:
        sql  = _sql_update(mediatype, title, name, id, season, episode, playcount)
        cursor.execute(sql)
        _refresh_parent_status(cursor, mediatype, title, name, id, number_of_seasons, season, number_of_episodes, episode, playcount)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def _refresh_parent_status(cursor, mediatype, title, name, id, number_of_seasons, season, number_of_episodes, episode, playcount):
    if mediatype == 'movie' or not title:
        return
    season = _safe_int(season)
    episode = _safe_int(episode)
    playcount = 1 if _safe_int(playcount) else 0
    if season is None:
        return

    total_episodes = _safe_int(number_of_episodes) or _stored_season_total(cursor, title, season)
    season_name = '%s S%02d' % (title, season)
    season_playcount = playcount

    if episode is not None:
        if not playcount:
            season_playcount = 0
        elif total_episodes:
            watched_episodes = _count_watched_episodes(cursor, title, season)
            season_playcount = 1 if watched_episodes >= total_episodes else 0
        else:
            return

    if total_episodes:
        _upsert_season_status(cursor, title, season_name, season, total_episodes, season_playcount)
    else:
        cursor.execute('UPDATE season SET playcount = ? WHERE title = ? AND season = ?', (season_playcount, title, season))

    if season == 0:
        return

    if not season_playcount:
        _set_tvshow_playcount(cursor, title, name, id, number_of_seasons, 0)
        return

    _refresh_tvshow_status(cursor, title, name, id, number_of_seasons)


def _stored_season_total(cursor, title, season):
    cursor.execute(
        'SELECT number_of_episodes FROM season WHERE title = ? AND season = ? ORDER BY number_of_episodes DESC LIMIT 1',
        (title, season),
    )
    row = cursor.fetchone()
    return _safe_int(row[0]) if row else 0


def _count_watched_episodes(cursor, title, season):
    cursor.execute(
        'SELECT COUNT(DISTINCT episode) FROM episode WHERE title = ? AND season = ? AND playcount > 0',
        (title, season),
    )
    row = cursor.fetchone()
    return _safe_int(row[0]) if row else 0


def _upsert_season_status(cursor, title, name, season, number_of_episodes, playcount):
    cursor.execute('SELECT rowid FROM season WHERE title = ? AND season = ? LIMIT 1', (title, season))
    if cursor.fetchone():
        cursor.execute(
            'UPDATE season SET name = ?, number_of_episodes = ?, playcount = ? WHERE title = ? AND season = ?',
            (name, number_of_episodes, playcount, title, season),
        )
    else:
        cursor.execute(
            'INSERT INTO season Values (?, ?, ?, ?, ?)',
            (title, name, season, number_of_episodes, playcount),
        )


def _refresh_tvshow_status(cursor, title, name, id, number_of_seasons):
    total_seasons = _safe_int(number_of_seasons) or _stored_tvshow_total(cursor, title)
    if not total_seasons:
        return
    cursor.execute('SELECT COUNT(DISTINCT season) FROM season WHERE title = ? AND season > 0 AND playcount > 0', (title,))
    row = cursor.fetchone()
    watched_seasons = _safe_int(row[0]) if row else 0
    playcount = 1 if watched_seasons >= total_seasons else 0
    _set_tvshow_playcount(cursor, title, name, id, total_seasons, playcount)


def _stored_tvshow_total(cursor, title):
    cursor.execute(
        'SELECT number_of_seasons FROM tvshow WHERE title = ? ORDER BY number_of_seasons DESC LIMIT 1',
        (title,),
    )
    row = cursor.fetchone()
    return _safe_int(row[0]) if row else 0


def _set_tvshow_playcount(cursor, title, name, id, number_of_seasons, playcount):
    number_of_seasons = _safe_int(number_of_seasons) or _stored_tvshow_total(cursor, title) or 0
    name = title
    id = id or ''
    cursor.execute('SELECT rowid FROM tvshow WHERE title = ? LIMIT 1', (title,))
    if cursor.fetchone():
        cursor.execute(
            'UPDATE tvshow SET name = ?, imdb_id = ?, number_of_seasons = ?, playcount = ? WHERE title = ?',
            (name, id, number_of_seasons, playcount, title),
        )
    else:
        cursor.execute(
            'INSERT INTO tvshow Values (?, ?, ?, ?, ?)',
            (title, name, id, number_of_seasons, playcount),
        )


def _sql_update(table, title, name, id, season, episode, playcount):
    if table == 'movie':
        sql_update = 'UPDATE movie SET playcount = %s WHERE imdb_id = "%s"' % (playcount, id)
    elif _has_value(season) and _has_value(episode):
        sql_update = 'UPDATE episode SET playcount = %s WHERE name = "%s"' % (playcount, name)
    elif _has_value(season):
        sql_update = 'UPDATE season SET playcount = %s WHERE name = "%s"' % (playcount, name)
    else:
        sql_update = 'UPDATE tvshow SET playcount = %s WHERE name = "%s"' % (playcount, name)
    return sql_update


