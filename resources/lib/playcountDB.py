

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
def getPlaycount(mediatype, column_names, column_value, season=0, episode=0):
    conn = _get_connection(playcountDB)
    cursor = conn.cursor()
    sql_get  = _get(mediatype, column_names, column_value, season, episode)
    cursor.execute(sql_get)
    match = cursor.fetchone()
    cursor.close()
    conn.close()
    playcount = match['playcount'] if match else None
    return playcount

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
    elif season and episode:
        sql_get = 'SELECT playcount FROM episode WHERE %s="%s" and season=%s and episode=%s' % (column_names, column_value, season, episode)
    elif season:
        sql_get = 'SELECT playcount FROM season WHERE %s = "%s" and season = %s' % (column_names, column_value, season)
    else:
        sql_get = 'SELECT playcount FROM tvshow WHERE %s = "%s"' % (column_names, column_value)
    return sql_get


def createEntry(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, episode):
    if mediatype == 'movie':
        _createEntry(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, episode, column_names = 'name')
    if season and episode:
        _createEntry(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, episode)
        name = name[:-3]
        _createEntry(mediatype, title, name, imdb, number_of_seasons, season, number_of_episodes, None)
        name = name[:-4]
        _createEntry(mediatype, title, name, imdb, number_of_seasons, None, number_of_episodes, None)
    elif season:
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
    elif season and episode:
        sql_insert = __insert_from_dict('episode', 5)
        sql_value = (title, name, season, episode, 0)
    elif season:
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
    if 'number_of_seasons' in meta and meta['number_of_seasons']: number_of_seasons = meta['number_of_seasons']
    if 'season' in meta and meta['season']: season = meta['season']
    if 'number_of_episodes' in meta and meta['number_of_episodes']: number_of_episodes = meta['number_of_episodes']
    if 'episode' in meta and meta['episode']: episode = meta['episode']
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
    sql  = _sql_update(mediatype, title, name, id, season, episode, playcount)
    cursor.execute(sql)
    conn.commit()
    if mediatype == 'tvshow':  _check(cursor, conn, mediatype, title, name, id, number_of_seasons, season, number_of_episodes, episode, playcount)
    cursor.close()
    conn.close()

def _check(cursor, conn, mediatype, title, name, id, number_of_seasons, season, number_of_episodes, episode, playcount):
    if playcount == 1:
        sql = _sql_check(title, season, episode)
        if sql == '': return
        cursor.execute(sql)
        matched = cursor.fetchall()
        if not '0' in str(matched) and len(matched) == number_of_episodes or episode == '':
            if episode != '':
                sql = 'UPDATE season SET playcount = %s WHERE title = "%s" and season = %s' % (playcount, title, season)
                cursor.execute(sql)
                conn.commit()
                sql = _sql_check(title, season, None)
                cursor.execute(sql)
                matched = cursor.fetchall()
            if not '0' in str(matched) and len(matched) == number_of_seasons:
                sql = 'UPDATE tvshow SET playcount = %s WHERE title = "%s"' % (playcount, title)
                cursor.execute(sql)
                conn.commit()
    else:
        sql = 'UPDATE tvshow SET playcount = %s WHERE title = "%s"' % (playcount, title)
        cursor.execute(sql)
        conn.commit()
        if episode:
            sql = 'UPDATE season SET playcount = %s WHERE title = "%s" and season = %s' % (playcount, title, season)
            cursor.execute(sql)
            conn.commit()


def _sql_check(title, season, episode):
    if season and episode:
        sql_check = 'SELECT playcount FROM episode WHERE title = "%s" and season = %s' % (title, season)
    elif season:
        sql_check = 'SELECT playcount FROM season WHERE title = "%s"' % title
    else:
        sql_check = ''
    return sql_check


def _sql_update(table, title, name, id, season, episode, playcount):
    if table == 'movie':
        sql_update = 'UPDATE movie SET playcount = %s WHERE imdb_id = "%s"' % (playcount, id)
    elif season and episode:
        sql_update = 'UPDATE episode SET playcount = %s WHERE name = "%s"' % (playcount, name)
    elif season:
        sql_update = 'UPDATE season SET playcount = %s WHERE name = "%s"' % (playcount, name)
    else:
        sql_update = 'UPDATE tvshow SET playcount = %s WHERE name = "%s"' % (playcount, name)
    return sql_update


