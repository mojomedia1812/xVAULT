from resources.lib import playcountDB
from resources.lib.sync import binge_sync


def episode_playcount(title, season, episode, meta=None, season_status=None):
    season = _maybe_int(season)
    episode = _maybe_int(episode)
    if not title or not season or not episode:
        return 0
    local_status = _safe_call(playcountDB.getEpisodeStatus, title, season, episode) or {}
    if _row_playcount(local_status):
        return 1
    if binge_sync.is_episode_watched(title, season, episode, meta):
        return 1
    season_status = season_status if season_status is not None else _safe_call(playcountDB.getSeasonStatus, title, season)
    if _row_playcount(season_status):
        stored_total = _maybe_int(season_status.get('number_of_episodes'))
        if stored_total and episode <= stored_total:
            return 1
    return 0


def season_playcount(title, season, episodes=None, number_of_episodes=None, season_status=None, tvshow_status=None):
    season = _maybe_int(season)
    if not title or not season:
        return 0
    season_status = season_status if season_status is not None else _safe_call(playcountDB.getSeasonStatus, title, season)
    episode_numbers = _episode_numbers(episodes)
    current_total = len(episode_numbers) or _maybe_int(number_of_episodes)
    stored_total = _maybe_int((season_status or {}).get('number_of_episodes'))

    if current_total:
        if _row_playcount(season_status) and stored_total and stored_total >= current_total:
            return 1
        tvshow_status = tvshow_status if tvshow_status is not None else _safe_call(playcountDB.getTvshowStatus, title)
        if season_status is None and _row_playcount(tvshow_status):
            stored_seasons = _maybe_int(tvshow_status.get('number_of_seasons'))
            if stored_seasons and season <= stored_seasons:
                return 1
        if episode_numbers:
            for episode in episode_numbers:
                meta = _episode_meta(episodes, episode)
                if not episode_playcount(title, season, episode, meta=meta, season_status=season_status):
                    return 0
            return 1
        if binge_sync.is_season_watched(title, season, current_total):
            return 1
        return 0

    if _row_playcount(season_status):
        return 1
    tvshow_status = tvshow_status if tvshow_status is not None else _safe_call(playcountDB.getTvshowStatus, title)
    if _row_playcount(tvshow_status):
        stored_seasons = _maybe_int(tvshow_status.get('number_of_seasons'))
        if stored_seasons and season <= stored_seasons:
            return 1
    return 0


def tvshow_playcount(title, seasons=None, number_of_seasons=None, tvshow_status=None):
    if not title:
        return 0
    current_total = _maybe_int(number_of_seasons)
    tvshow_status = tvshow_status if tvshow_status is not None else _safe_call(playcountDB.getTvshowStatus, title)
    if seasons:
        season_numbers = sorted(set(_maybe_int(item.get('season')) for item in seasons if _maybe_int(item.get('season'))))
        current_total = current_total or len(season_numbers)
        if not current_total or len(season_numbers) < current_total:
            return 0
        watched = set(_maybe_int(item.get('season')) for item in seasons if _maybe_int(item.get('season')) and _maybe_int(item.get('playcount')) > 0)
        return 1 if len(watched) >= current_total else 0

    if current_total:
        if playcountDB.countWatchedSeasons(title) >= current_total:
            return 1
        stored_total = _maybe_int((tvshow_status or {}).get('number_of_seasons'))
        if _row_playcount(tvshow_status) and stored_total and stored_total >= current_total:
            return 1
    return 0


def store_season_status(title, name, season, number_of_episodes, playcount):
    try:
        playcountDB.setSeasonStatus(title, name, season, number_of_episodes, playcount)
    except Exception as exc:
        binge_sync.log_sync_warning('failed to store derived season status: %s' % exc)


def store_tvshow_status(title, name, imdb, number_of_seasons, playcount):
    try:
        playcountDB.setTvshowStatus(title, name, imdb, number_of_seasons, playcount)
    except Exception as exc:
        binge_sync.log_sync_warning('failed to store derived tvshow status: %s' % exc)


def _episode_numbers(episodes):
    numbers = []
    for item in episodes or []:
        episode = _maybe_int(item.get('episode') or item.get('episode_number'))
        if episode:
            numbers.append(episode)
    return sorted(set(numbers))


def _episode_meta(episodes, episode):
    for item in episodes or []:
        if _maybe_int(item.get('episode') or item.get('episode_number')) == episode:
            return item
    return None


def _row_playcount(row):
    if not row:
        return 0
    return 1 if _maybe_int(row.get('playcount')) else 0


def _maybe_int(value):
    try:
        return int(value)
    except Exception:
        return None


def _safe_call(func, *args):
    try:
        return func(*args)
    except Exception:
        return None
