import hashlib

from resources.lib import bookmarkDB, control


COMPLETED_REMAINING_SECONDS = 10 * 60
RESUME_MIN_SECONDS = 3 * 60


def is_completed_position(current_time, total_time):
    try:
        current = float(current_time or 0)
        total = float(total_time or 0)
    except Exception:
        return False
    if current <= 0 or total <= 0:
        return False
    if current >= total:
        return True
    return (total - current) <= COMPLETED_REMAINING_SECONDS


def should_store_resume(current_time, total_time):
    try:
        current = float(current_time or 0)
    except Exception:
        return False
    return current > RESUME_MIN_SECONDS and not is_completed_position(current_time, total_time)


def resume_for_meta(meta, fallback_title=None):
    try:
        if control.getSetting('bookmarks') != 'true':
            return 0
        name, year = playback_identity(meta, fallback_title)
        if not name:
            return 0
        return resume_for_identity(name, year)
    except Exception:
        return 0


def resume_for_identity(name, year=''):
    try:
        match = bookmarkDB.get_query(bookmark_id(name, year), 'bookmarks.pcl')
        if not match:
            return 0
        seconds = int(float(match[1] or 0))
        return seconds if seconds > RESUME_MIN_SECONDS else 0
    except Exception:
        return 0


def bookmark_id(name, year=''):
    digest = hashlib.md5()
    for value in (name, year):
        for char in str(value or ''):
            try:
                digest.update(str(char).encode('utf-8'))
            except Exception:
                digest.update(str(char))
    return str(digest.hexdigest())


def playback_identity(meta, fallback_title=None):
    meta = meta or {}
    mediatype = meta.get('mediatype')
    title = fallback_title or meta.get('systitle') or meta.get('title') or meta.get('originaltitle') or meta.get('name') or ''
    year = str(meta.get('year')) if 'year' in meta else ''
    if mediatype == 'movie':
        if meta.get('year'):
            return '%s (%s)' % (title, meta.get('year')), year
        return title, year

    season = _maybe_int(meta.get('season'))
    episode = _maybe_int(meta.get('episode'))
    if season is not None and episode is not None:
        return '%s S%02dE%02d' % (title, season, episode), year
    return meta.get('sysname') or title, year


def apply_resume_label(label, meta, fallback_title=None):
    resume = resume_for_meta(meta, fallback_title)
    if not resume or _maybe_int((meta or {}).get('playcount')) > 0:
        return label, 0
    return '%s [COLOR=gold][B]\u23f1[/B][/COLOR] [COLOR=gold](ab %s)[/COLOR]' % (label, format_time(resume)), resume


def mark_in_progress_meta(meta, resume):
    if not resume:
        return meta
    try:
        meta.update({'playcount': 0, 'overlay': 6, 'xvault_watch_state': 'in_progress', 'xvault_resume_seconds': int(resume)})
    except Exception:
        pass
    return meta


def format_time(seconds):
    try:
        seconds = int(float(seconds or 0))
    except Exception:
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return '%d:%02d:%02d' % (hours, minutes, seconds)
    return '%02d:%02d' % (minutes, seconds)


def _maybe_int(value):
    try:
        return int(value)
    except Exception:
        return None
