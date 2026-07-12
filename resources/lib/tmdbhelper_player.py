import json

from resources.lib import control, log_utils


EMPTY_VALUES = ('', '0', 'None', 'none', 'null', 'undefined', '{imdb}', '{tmdb}')


def _clean(value):
    if value is None:
        return ''
    value = str(value).strip()
    if value.startswith('{') and value.endswith('}'):
        return ''
    return '' if value in EMPTY_VALUES else value


def _int(value, default=0):
    value = _clean(value)
    if not value:
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def _put(meta, key, value):
    value = _clean(value)
    if value:
        meta[key] = value


def _infer_mediatype(params):
    mediatype = _clean(params.get('mediatype') or params.get('type'))
    if mediatype in ('movie', 'tvshow'):
        return mediatype
    if mediatype in ('episode', 'tv', 'show'):
        return 'tvshow'
    if _clean(params.get('season')) or _clean(params.get('episode')) or _clean(params.get('showname')):
        return 'tvshow'
    return 'movie'


def _tmdb_meta(mediatype, title, tmdb_id, year):
    try:
        from resources.lib.tmdb import cTMDB
        return cTMDB().get_meta(mediatype, title, tmdb_id=tmdb_id, year=year, advanced='true') or {}
    except Exception as exc:
        log_utils.log('TMDbHelper metadata enrichment failed: %s' % str(exc), log_utils.LOGWARNING)
        return {}


def build_sysmeta(params):
    mediatype = _infer_mediatype(params)
    title = _clean(params.get('title') or params.get('showname') or params.get('name'))
    originaltitle = _clean(params.get('originaltitle') or params.get('original_name') or title)
    year = _int(params.get('year') or params.get('showyear'), 0)
    season = _int(params.get('season'), 0)
    episode = _int(params.get('episode'), 0)
    tmdb_id = _clean(params.get('tmdb_id') or params.get('tmdb'))
    imdb_id = _clean(params.get('imdb_id') or params.get('imdbnumber') or params.get('imdb'))

    sysmeta = {}
    _put(sysmeta, 'title', title)
    _put(sysmeta, 'originaltitle', originaltitle)
    _put(sysmeta, 'tmdb_id', tmdb_id)
    _put(sysmeta, 'imdb_id', imdb_id)
    _put(sysmeta, 'imdbnumber', imdb_id)
    _put(sysmeta, 'imdb', imdb_id)
    _put(sysmeta, 'premiered', params.get('premiered') or params.get('showpremiered'))
    _put(sysmeta, 'episode_title', params.get('episode_title'))
    _put(sysmeta, 'episode_premiered', params.get('episode_premiered'))
    _put(sysmeta, 'poster', params.get('poster'))
    _put(sysmeta, 'cover_url', params.get('poster'))

    if year:
        sysmeta['year'] = year
    if mediatype == 'tvshow':
        sysmeta['season'] = season
        sysmeta['episode'] = episode
    else:
        sysmeta['season'] = 0
        sysmeta['episode'] = 0
    sysmeta['mediatype'] = mediatype

    enriched = _tmdb_meta(mediatype, title, tmdb_id, year)
    if enriched:
        enriched.update({k: v for k, v in sysmeta.items() if v not in ('', None)})
        sysmeta = enriched

    if mediatype == 'tvshow' and title and season >= 0 and episode:
        sysmeta['sysname'] = '%s S%02dE%02d' % (title, season, episode)
    elif title and year:
        sysmeta['sysname'] = '%s (%s)' % (title, year)

    return sysmeta


def play(params):
    if not control.visible():
        control.busy()
    try:
        params = dict(params)
        params['sysmeta'] = json.dumps(build_sysmeta(params))
        from resources.lib import sources
        sources.sources().play(params)
    except Exception as exc:
        log_utils.log('TMDbHelper playback failed: %s' % str(exc), log_utils.LOGERROR)
        control.infoDialog('TMDbHelper-Uebergabe fehlgeschlagen', sound=True, icon='WARNING', time=2000)
