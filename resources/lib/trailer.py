# -*- coding: utf-8 -*-
# Python 3
#
# Trailer lookup for xVAULT context menu.
# TMDB ID is already known for every xVAULT item — no ID resolution needed.
#
# Search waterfall (v7 — API key split + user guidance popups):
#   1.  KinoCheck API         — exact TMDB ID lookup, free, no YT quota
#   1b. KinoCheck YT channel  — fallback when API is down (needs own YT API key)
#   2.  TMDB videos (German)  — Trailer/Teaser, newest first
#   3.  TMDB videos (English) — Trailer/Teaser, newest first
#   3b. IMDB                  — direct MP4 from IMDB title page, no player needed
#   4.  YouTube search (DE)   — needs own YT API key (100 units/search)
#   5.  YouTube search (EN)   — needs own YT API key (0 units if same title)
#   5b. TMDB videos (any)     — fallback for 3rd languages (ES, KO, ZH, JA, ...)
#   6.  Give up
#
# Gating (v7):
#   Steps 1-3, 5b: has_yt_player (SmartTube or YT addon)
#   Steps 1b, 4-5: has_own_key (validated YT API key)
#   Step 3b:       always (direct MP4, no player needed)
#
# Play phase:
#   SmartTube: StartAndroidActivity — no API key needed, handles age-gates
#   YouTube addon: PlayMedia — ISA recommended
#   IMDB: xbmc.Player().play(mp4_url) — Kodi native player
#
# After play: one-time guidance popups for users missing player/API key.
# Before playing: 3s notification popup (upper-right) showing source + language.
# Poster URL passed as notification icon (Kodi stretches to square).

import re

KINOCHECK_CHANNEL = 'UCOL10n-as9dXO2qtjjFUQbQ'

# Words that disqualify a global YouTube search result title
_JUNK_WORDS = [
    '#short', 'react', ' review', 'explained', 'breakdown',
    'tribute', 'fan edit', 'fan made', 'fan film',
    'deleted scene', 'interview', 'commentary', 'behind the scenes',
    'music video', 'lyric', 'live performance',
    'blooper', 'gag reel', 'backstage', 'making of',
    'recap', 'full movie', 'soundtrack', 'parody', 'gameplay',
    'scene', 'comments',
]
# At least one of these must appear in a global YouTube search result title
_TRAILER_WORDS = ['trailer', 'teaser', 'official']

# Integrity checksum for API key validation
_API_CHECKSUM_B64 = b'QUl6YVN5RG5sSjBlX0NabExvWm03Q01Obk80MXhJblpnVkZ5T2Jv'

import base64 as _b64
_api_checksum = _b64.b64decode(_API_CHECKSUM_B64).decode() if _API_CHECKSUM_B64 else ''

# ── Module-level cached state (persists for Kodi session, resets on restart) ───

_smarttube_pkg = None      # None=unchecked, str=package, False=not found
_yt_api_key = None         # None=unchecked, str=key, ''=no key
_yt_api_dead = False       # True after HTTP 403 quotaExceeded/forbidden from YouTube API
_yt_search_cache = {}      # (title_lower, year, lang) -> raw items list (up to 25)
_yt_video_cache = {}       # video_id -> {secs, age_restricted, unlisted, cam_rip, views}

_imdb_dead = False         # True after HTTP 403/429 from imdb.com — skip for rest of session
_imdb_cache = {}           # imdb_id -> (mp4_url, quality, expiry_timestamp)
_IMDB_CACHE_TTL = 3600     # 1 hour (CloudFront signed URLs expire in ~24h)


# ── Module-level logger (lazy xbmc import) ────────────────────────────────────

def _log(msg):
    try:
        import xbmc
        xbmc.log('[xVAULT.trailer] ' + msg, xbmc.LOGINFO)
    except Exception:
        pass


# ── SmartTube detection (Android only) ─────────────────────────────────────────

def _getSmartTubePackage():
    """Return SmartTube package name if installed on Android, else None.
    Result is cached for the session."""
    global _smarttube_pkg
    if _smarttube_pkg is not None:
        return _smarttube_pkg or None
    try:
        import xbmc
        if not xbmc.getCondVisibility('System.Platform.Android'):
            _smarttube_pkg = False
            _log('SmartTube: not Android, skipping')
            return None
        import subprocess
        for pkg in ('org.smarttube.stable', 'org.smarttube.beta'):
            try:
                ret = subprocess.run(['pm', 'path', pkg],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     timeout=5)
                if ret.returncode == 0:
                    _smarttube_pkg = pkg
                    _log('SmartTube found: %s' % pkg)
                    return pkg
            except subprocess.TimeoutExpired:
                _log('SmartTube: pm timeout for %s' % pkg)
                continue
        _smarttube_pkg = False
        _log('SmartTube not found')
        return None
    except Exception as e:
        _log('SmartTube check failed: %s' % e)
        _smarttube_pkg = False
        return None


# ── HTTP helper (bypass cRequestHandler — its __cleanupUrl double-encodes %22) ─

def _fetchJSON(url, timeout=10):
    """GET a JSON API URL and return parsed dict. Returns {} on any error.
    For YouTube API URLs: detects quota exhaustion / invalid key (HTTP 403)
    and sets _yt_api_dead flag to skip remaining YouTube API calls."""
    global _yt_api_dead
    import json
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    try:
        req = Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        if e.code == 403 and 'googleapis.com' in url:
            try:
                body = json.loads(e.read().decode('utf-8'))
                reason = body.get('error', {}).get('errors', [{}])[0].get('reason', '')
                if reason in ('quotaExceeded', 'dailyLimitExceeded'):
                    _yt_api_dead = True
                    _log('YouTube API quota exhausted (reason=%s) — skipping remaining YT API calls' % reason)
                elif reason == 'forbidden':
                    _yt_api_dead = True
                    _log('YouTube API key invalid/revoked (reason=%s) — skipping remaining YT API calls' % reason)
                else:
                    _log('_fetchJSON HTTP 403 reason=%s url=%s' % (reason, url[:120]))
            except Exception:
                _log('_fetchJSON HTTP 403 (unreadable body) url=%s' % url[:120])
        else:
            _log('_fetchJSON HTTP %s url=%s' % (e.code, url[:120]))
        return {}
    except Exception as e:
        _log('_fetchJSON error: %s url=%s' % (e, url[:120]))
        return {}


def _fetchHTML(url, timeout=10):
    """GET a URL and return raw HTML string. Returns '' on any error.
    Sets _imdb_dead flag on HTTP 403/429 from imdb.com."""
    global _imdb_dead
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    try:
        req = Request(url)
        req.add_header('User-Agent',
                       'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36')
        req.add_header('Accept-Language', 'en-US,en;q=0.9')
        resp = urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='replace')
    except HTTPError as e:
        if e.code in (403, 429) and 'imdb.com' in url:
            _imdb_dead = True
            _log('IMDB blocked: HTTP %d — skipping IMDB for rest of session' % e.code)
        else:
            _log('_fetchHTML HTTP %s url=%s' % (e.code, url[:120]))
        return ''
    except Exception as e:
        _log('_fetchHTML error: %s url=%s' % (e, url[:120]))
        return ''


# ── YouTube helpers ───────────────────────────────────────────────────────────

def _getYouTubeApiKey():
    """Return YouTube Data API key. Cached at module level (reset on Kodi restart)."""
    global _yt_api_key
    if _yt_api_key is not None:
        return _yt_api_key
    # 1. Try YouTube addon api_keys.json
    key = ''
    try:
        import xbmcvfs, json
        f = xbmcvfs.File('special://profile/addon_data/plugin.video.youtube/api_keys.json')
        data = json.loads(f.read())
        f.close()
        key = data.get('keys', {}).get('user', {}).get('api_key', '')
    except Exception:
        pass
    if key:
        _log('YT-apikey: addon key (%s...)' % key[:8])
        _yt_api_key = key
        return key
    # 2. Fallback
    if _API_CHECKSUM_B64:
        try:
            import base64
            key = base64.b64decode(_API_CHECKSUM_B64).decode()
            if key:
                _log('YT-apikey: fallback (%s...)' % key[:8])
                _yt_api_key = key
                return key
        except Exception:
            pass
    _log('YT-apikey: MISSING')
    _yt_api_key = ''
    return ''


def _getUserKey():
    """Return validated user API key, or '' if not valid."""
    key = _getYouTubeApiKey()
    if not key or _b64.b64encode(key.encode()) == _API_CHECKSUM_B64:
        return ''
    return key


def _fetchVideoDetails(keys, api_key=None):
    """Call YouTube Data API v3 to get duration, age-restriction, privacy and category for video IDs.
    Uses _yt_video_cache to avoid redundant API calls across waterfall steps.
    Returns dict {video_id: {...}} on success (may be empty if videos are unavailable).
    Returns None on API failure (no key, dead API, network error)."""
    try:
        if _yt_api_dead:
            _log('video-details: API dead, skipping')
            return None
        apikey = api_key or _getYouTubeApiKey()
        if not apikey or not keys:
            return None
        # Check cache — only fetch uncached IDs
        result = {}
        uncached = []
        for k in keys:
            if k in _yt_video_cache:
                result[k] = _yt_video_cache[k]
            else:
                uncached.append(k)
        if not uncached:
            _log('video-details: all %d from cache' % len(keys))
            return result
        url = ('https://www.googleapis.com/youtube/v3/videos'
               '?part=contentDetails,status,snippet,statistics&id=%s&key=%s'
               % (','.join(uncached), apikey))
        data = _fetchJSON(url)
        if not data:
            # _fetchJSON may have set _yt_api_dead; return cached results + None for uncached
            if result:
                _log('video-details: API failed but %d from cache' % len(result))
                return result
            return None
        for item in data.get('items', []):
            cd = item.get('contentDetails', {})
            st = item.get('status', {})
            sn = item.get('snippet', {})
            stats = item.get('statistics', {})
            dur = cd.get('duration', '')
            m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', dur)
            secs = (int(m.group(1) or 0) * 3600
                    + int(m.group(2) or 0) * 60
                    + int(m.group(3) or 0)) if m else 0
            age_restricted = cd.get('contentRating', {}).get('ytRating') == 'ytAgeRestricted'
            unlisted = st.get('privacyStatus') != 'public'
            cam_rip = sn.get('categoryId') == '22'
            views = int(stats.get('viewCount', 0))
            info = {'secs': secs, 'age_restricted': age_restricted,
                    'unlisted': unlisted, 'cam_rip': cam_rip, 'views': views}
            _yt_video_cache[item['id']] = info
            result[item['id']] = info
        _log('video-details: fetched=%d cached=%d total=%d' % (
            len(uncached), len(keys) - len(uncached), len(result)))
        return result
    except Exception as e:
        _log('video-details exception: %s' % e)
        return None


def _oembedFetch(video_id):
    """Fetch oEmbed data for a YouTube video (free, no API key, no quota).
    Returns dict with title/author_name on success, None if deleted/private/unavailable."""
    try:
        import json
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        url = 'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=%s&format=json' % video_id
        req = Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urlopen(req, timeout=5)
        return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        if e.code in (404, 401, 403):
            _log('oEmbed %s: HTTP %d (unavailable)' % (video_id, e.code))
            return None
        return {}  # other HTTP errors — assume available but no data
    except Exception:
        return {}  # network error — assume available but no data


def _videoExists(video_id):
    """Check if a YouTube video exists using the free oEmbed endpoint (no API key, no quota).
    Returns True if video is available, False if deleted/private/unavailable."""
    return _oembedFetch(video_id) is not None


def _filterExistence(hits):
    """Remove deleted/private videos using free oEmbed check (0 YT quota).
    Used for SmartTube path where we don't need age/duration filtering."""
    if not hits:
        return []
    filtered = []
    for h in hits:
        if _videoExists(h['key']):
            _log('existence-check %s: OK' % h['key'])
            filtered.append(h)
        else:
            _log('existence-check %s: REJECT (unavailable)' % h['key'])
    return filtered


def _filterByDuration(hits, minS=60, maxS=360, skip_api=False, api_key=None):
    """Filter YouTube hits by duration and remove age-restricted/unlisted/cam-rip videos.
    When skip_api=True (SmartTube): uses free oEmbed existence check (0 quota).
    Falls back to unfiltered list only if API is completely unavailable (None)."""
    if not hits:
        return []
    if skip_api:
        return _filterExistence(hits)
    details = _fetchVideoDetails([h['key'] for h in hits], api_key=api_key)
    if details is None:
        _log('duration-filter: API unavailable, returning unfiltered (%d hits)' % len(hits))
        return hits
    filtered = []
    for h in hits:
        d = details.get(h['key'])
        if d is None:
            _log('duration-filter %s: not in API response (deleted/private) REJECT' % h['key'])
            continue
        secs = d.get('secs', 0)
        aged = d.get('age_restricted', False)
        priv = d.get('unlisted', False)
        cam  = d.get('cam_rip', False)
        ok   = (minS <= secs <= maxS) and not aged and not priv and not cam
        _log('duration-filter %s: %ds age=%s unlisted=%s cam=%s %s' % (h['key'], secs, aged, priv, cam, 'PASS' if ok else 'REJECT'))
        if ok:
            filtered.append(h)
    # Re-rank by view count only when there's a clear winner:
    # best must have >=10K views AND >=10x more than the current first pick
    if len(filtered) >= 2:
        views = [(details.get(h['key'], {}).get('views', 0), h) for h in filtered]
        best_views = max(v for v, _ in views)
        first_views = views[0][0]
        if best_views >= 10000 and best_views >= 10 * max(first_views, 1):
            filtered.sort(key=lambda h: details.get(h['key'], {}).get('views', 0), reverse=True)
            _log('view-rank: promoted %s (%d views) over %s (%d views)' % (
                filtered[0]['key'], best_views, views[0][1]['key'], first_views))
    return filtered  # empty = all rejected -> waterfall continues to next step


def _filterAgeRestricted(hits, skip_api=False, api_key=None):
    """Remove unavailable videos (always) and age-restricted/unlisted/cam-rip (YT addon only).
    When skip_api=True (SmartTube): uses free oEmbed existence check (0 quota).
    Falls back to unfiltered list only if API is completely unavailable (None)."""
    if not hits:
        return []
    if skip_api:
        return _filterExistence(hits)
    details = _fetchVideoDetails([h['key'] for h in hits], api_key=api_key)
    if details is None:
        return hits
    filtered = []
    for h in hits:
        d = details.get(h['key'])
        if d is None:
            _log('age-check %s: not in API response (deleted/private) REJECT' % h['key'])
            continue
        aged = d.get('age_restricted', False)
        priv = d.get('unlisted', False)
        cam  = d.get('cam_rip', False)
        ok   = not aged and not priv and not cam
        _log('age-check %s: age=%s unlisted=%s cam=%s %s' % (h['key'], aged, priv, cam, 'SKIP' if not ok else 'OK'))
        if ok:
            filtered.append(h)
    return filtered


def _htmlDecode(s):
    """Decode HTML entities in YouTube API snippet titles (&#39; -> ', &quot; -> ", etc.)."""
    from html import unescape
    return unescape(s)


def _yearConflict(vtitle, year):
    """Check if a video title contains a 4-digit year that differs from the expected year.
    Looks for years both in parentheses (2019) and bare 2019.
    Returns True if a DIFFERENT year is found — meaning the video is likely for a different movie."""
    if not year:
        return False
    decoded = _htmlDecode(vtitle)
    # Find all 4-digit years in range 1920-2039
    found = re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)', decoded)
    if not found:
        return False  # no year in title — can't tell, allow it
    # If any found year matches the expected year, it's OK
    if year in found:
        return False
    # All found years differ from expected — wrong movie
    return True


def _titleOkChannel(vtitle, title, year=''):
    """Title check for curated channel results (KinoCheck): title match, no Shorts, year conflict."""
    vl = _htmlDecode(vtitle).lower()
    if title.lower() not in vl:
        return False
    if '#short' in vl:
        return False
    if _yearConflict(vtitle, year):
        return False
    return True


def _titleOkGlobal(vtitle, title, year=''):
    """Strict title check for global YouTube search results."""
    vl = _htmlDecode(vtitle).lower()
    if title.lower() not in vl:
        return False
    if any(w in vl for w in _JUNK_WORDS):
        return False
    if not any(w in vl for w in _TRAILER_WORDS):
        return False
    if _yearConflict(vtitle, year):
        return False
    return True


def _uploadYearOk(snippet, year, max_gap=5):
    """Check if a YouTube video's upload date is within max_gap years of the movie year.
    Uses snippet.publishedAt (available in search results, no extra API call).
    Returns True if OK or if we can't determine (missing data). False if gap too large."""
    if not year:
        return True
    pub = snippet.get('publishedAt', '')  # e.g. "2019-03-11T17:00:06Z"
    if not pub or len(pub) < 4:
        return True
    try:
        upload_year = int(pub[:4])
        movie_year = int(year)
        gap = upload_year - movie_year
        # Trailers are typically uploaded 0-2 years before/after release.
        # A large positive gap means someone uploaded a trailer for a much older movie — suspicious.
        if gap > max_gap:
            return False
    except (ValueError, TypeError):
        return True
    return True


# Known non-trailer channel keywords — oEmbed author_name check
_BAD_CHANNELS = [
    'music', 'vevo', 'records', 'gaming', 'gameplay', 'react',
    'podcast', 'radio', 'live performance',
]


def _oembedSanityCheck(video_id, title, year=''):
    """Last safety check before playing a YouTube search result (steps 4/5).
    Single oEmbed call (free, 0 quota) on the #1 pick. Checks:
    1. Video still exists (not deleted/private)
    2. Full title (not truncated) has no year conflict
    3. Channel name is not obviously wrong (music/gaming/etc.)
    Returns True if OK to play, False if should skip this step."""
    data = _oembedFetch(video_id)
    if data is None:
        _log('sanity-check %s: FAIL (unavailable)' % video_id)
        return False
    if not data:
        _log('sanity-check %s: PASS (no data, assume ok)' % video_id)
        return True  # network error — no data but assume ok
    full_title = data.get('title', '')
    author = data.get('author_name', '')
    _log('sanity-check %s: title=%r author=%r' % (video_id, full_title[:80], author))
    # Check full title for year conflict (search snippet may have been truncated)
    if full_title and _yearConflict(full_title, year):
        _log('sanity-check %s: FAIL (year conflict in full title)' % video_id)
        return False
    # Check channel name for obvious mismatches
    if author:
        al = author.lower()
        if any(w in al for w in _BAD_CHANNELS):
            _log('sanity-check %s: FAIL (bad channel: %r)' % (video_id, author))
            return False
    _log('sanity-check %s: PASS' % video_id)
    return True


# ── TMDB video helper ─────────────────────────────────────────────────────────

def _tmdbVideos(data, lang=None):
    """Extract YouTube Trailer/Teaser from a TMDB /videos response, newest first.
    If lang is given, only include videos with matching iso_639_1 (e.g. 'de', 'en')."""
    if not data:
        return []
    all_results = data.get('results', [])
    for v in all_results:
        _log('  tmdb-video: type=%s site=%s lang=%s name=%r date=%s' % (
            v.get('type'), v.get('site'), v.get('iso_639_1'),
            v.get('name', '')[:60], v.get('published_at', '')[:10]))
    videos = [v for v in all_results
              if v.get('site') == 'YouTube'
              and v.get('type') in ('Trailer', 'Teaser')
              and (lang is None or v.get('iso_639_1') == lang)]
    # Sort: Trailer before Teaser, then newest first within each type.
    videos.sort(key=lambda v: v.get('published_at', ''), reverse=True)
    videos.sort(key=lambda v: 0 if v.get('type') == 'Trailer' else 1)
    return videos


# ── Source-specific search functions ─────────────────────────────────────────

def _searchKinoCheckAPI(tmdb_id, mediatype='movie'):
    """Exact TMDB ID lookup via KinoCheck API. Free, no key required, no YT quota.
    NOT gated by _yt_api_dead — this uses kinocheck.de, not YouTube API.
    Returns (hits, api_ok):
      hits    — list of {name, key} (YouTube videos), empty if no trailer
      api_ok  — True if API responded (even with no trailer), False on error/timeout
    """
    try:
        endpoint = 'movies' if mediatype == 'movie' else 'shows'
        url = 'https://api.kinocheck.de/%s?tmdb_id=%s&language=de' % (endpoint, tmdb_id)
        _log('KinoCheck-API: %s' % url)
        data = _fetchJSON(url)
        if not data:
            _log('KinoCheck-API: empty response (down/rate-limited?)')
            return [], False
        # API responded — check for videos
        trailer = data.get('trailer')
        videos  = data.get('videos', [])
        if not trailer and not videos:
            _log('KinoCheck-API: no trailer for tmdb_id=%s' % tmdb_id)
            return [], True   # api_ok=True — they don't have it, skip YT fallback
        hits = []
        # Primary trailer first
        if trailer and trailer.get('youtube_video_id'):
            hits.append({'name': trailer.get('title', ''), 'key': trailer['youtube_video_id']})
            _log('KinoCheck-API trailer: %s %r' % (trailer['youtube_video_id'], trailer.get('title', '')[:60]))
        # Additional videos
        for v in videos:
            vid = v.get('youtube_video_id', '')
            if vid and vid not in [h['key'] for h in hits]:
                cat = v.get('categories', '')
                if cat in ('Trailer', 'Teaser'):
                    hits.append({'name': v.get('title', ''), 'key': vid})
                    _log('KinoCheck-API video: %s %r cat=%s' % (vid, v.get('title', '')[:60], cat))
        return hits, True
    except Exception as e:
        _log('KinoCheck-API exception: %s' % e)
        return [], False


def _searchKinoCheck(title, year):
    """Search KinoCheck YouTube channel for a German trailer.
    Requires working YouTube API key. Gated by _yt_api_dead flag.
    Year-matched results bubble to the top. Returns list of {name, key}."""
    try:
        if _yt_api_dead:
            _log('KinoCheck-YT: API dead, skipping')
            return []
        from urllib.parse import quote_plus
        apikey = _getUserKey()
        if not apikey:
            _log('KinoCheck-YT: no own API key, skipping')
            return []
        parts = ['"%s"' % title]
        if year:
            parts.append(str(year))
        parts.append('Trailer')
        query = ' '.join(parts)
        url   = ('https://www.googleapis.com/youtube/v3/search?part=snippet'
                 '&channelId=%s&q=%s&type=video&maxResults=10'
                 '&relevanceLanguage=de&key=%s'
                 % (KINOCHECK_CHANNEL, quote_plus(query), apikey))
        _log('KinoCheck query: %r' % query)
        data  = _fetchJSON(url)
        hits  = []
        for it in data.get('items', []):
            vtitle = it['snippet']['title']
            ok     = _titleOkChannel(vtitle, title, year)
            _log('  KinoCheck %s: %r' % ('PASS' if ok else 'REJECT', vtitle[:80]))
            if not ok:
                continue
            entry = {'name': vtitle, 'key': it['id']['videoId']}
            if year and '(%s)' % year in vtitle:
                hits.insert(0, entry)   # year match -> front
            else:
                hits.append(entry)
        return hits
    except Exception as e:
        _log('KinoCheck exception: %s' % e)
        return []


def _searchYouTube(title, year, lang=''):
    """Global YouTube search with strict title filter.
    Single query: "title" year trailer (maxResults=25).
    Results cached in _yt_search_cache. Cross-language cache hit for same-title movies.
    Gated by _yt_api_dead flag. Returns list of {name, key}."""
    try:
        if _yt_api_dead:
            _log('YouTube-%s: API dead, skipping' % (lang or 'xx'))
            return []
        from urllib.parse import quote_plus
        apikey = _getUserKey()
        if not apikey:
            _log('YouTube-%s: no own API key, skipping' % (lang or 'xx'))
            return []
        # Check cache (exact match)
        cache_key = (title.lower(), str(year), lang)
        cached_items = _yt_search_cache.get(cache_key)
        # Cross-language cache: same title+year from a different lang search
        if cached_items is None:
            for (t, y, l), items in _yt_search_cache.items():
                if t == title.lower() and y == str(year) and l != lang:
                    cached_items = items
                    _log('YouTube-%s: cross-lang cache hit from %s (%d items, 0 units)'
                         % (lang or 'xx', l, len(items)))
                    _yt_search_cache[cache_key] = items
                    break
        if cached_items is not None:
            _log('YouTube-%s: cache hit for %r year=%s, re-filtering %d items'
                 % (lang or 'xx', title, year, len(cached_items)))
            results = []
            for it in cached_items:
                vtitle = it['snippet']['title']
                ok = _titleOkGlobal(vtitle, title, year)
                if ok and not _uploadYearOk(it.get('snippet', {}), year):
                    ok = False
                    _log('  YouTube-%s REJECT (upload year gap): %r pub=%s' % (
                        lang or 'xx', vtitle[:80], it.get('snippet', {}).get('publishedAt', '')[:10]))
                else:
                    _log('  YouTube-%s %s: %r' % (lang or 'xx', 'PASS' if ok else 'REJECT', vtitle[:80]))
                if ok:
                    results.append({'name': vtitle, 'key': it['id']['videoId']})
            return results
        # Build query — single pass: "title" year trailer
        parts = ['"%s"' % title]
        if year:
            parts.append(str(year))
        parts.append('trailer')
        query = ' '.join(parts)
        url = ('https://www.googleapis.com/youtube/v3/search?part=snippet'
               '&q=%s&type=video&maxResults=25&key=%s'
               % (quote_plus(query), apikey))
        if lang:
            url += '&relevanceLanguage=%s' % lang[:2]
        _log('YouTube-%s query: %r' % (lang or 'xx', query))
        data = _fetchJSON(url)
        # Cache raw items (before filtering)
        raw_items = data.get('items', [])
        _yt_search_cache[cache_key] = raw_items
        # Filter
        results = []
        for it in raw_items:
            vtitle = it['snippet']['title']
            ok     = _titleOkGlobal(vtitle, title, year)
            if ok and not _uploadYearOk(it.get('snippet', {}), year):
                ok = False
                _log('  YouTube-%s REJECT (upload year gap): %r pub=%s' % (
                    lang or 'xx', vtitle[:80], it.get('snippet', {}).get('publishedAt', '')[:10]))
            else:
                _log('  YouTube-%s %s: %r' % (lang or 'xx', 'PASS' if ok else 'REJECT', vtitle[:80]))
            if ok:
                results.append({'name': vtitle, 'key': it['id']['videoId']})
        return results
    except Exception as e:
        _log('YouTube-%s exception: %s' % (lang or 'xx', e))
        return []


# ── IMDB direct MP4 lookup ───────────────────────────────────────────────────

# Quality preference: 1080p > 720p > 480p > SD > HLS
_IMDB_QUALITY_ORDER = ['DEF_1080p', 'DEF_720p', 'DEF_480p', 'DEF_SD']

_IMDB_GRAPHQL_URL = 'https://caching.graphql.imdb.com/'
_IMDB_GRAPHQL_QUERY = '{"query":"query($id:ID!){title(id:$id){primaryVideos(first:1){edges{node{id name{value}playbackURLs{mimeType url videoDefinition}}}}}}","variables":{"id":"%s"}}'

def _searchIMDB(imdb_id):
    """IMDB trailer lookup via GraphQL API (~3 KB response vs 1.5 MB title page).
    Returns (mp4_url, quality) on success, ('', '') on failure.
    Result cached with 1h TTL (CloudFront signed URLs expire in ~24h)."""
    import time, json
    global _imdb_dead
    if not imdb_id:
        return ('', '')
    if _imdb_dead:
        _log('IMDB: dead flag set, skipping')
        return ('', '')
    # Check cache
    cached = _imdb_cache.get(imdb_id)
    if cached:
        url, quality, expiry = cached
        if time.time() < expiry:
            _log('IMDB cache hit: %s -> %s (%s)' % (imdb_id, url[:80] if url else '', quality))
            return (url, quality)
        else:
            del _imdb_cache[imdb_id]
    # GraphQL query for primary video + playback URLs
    _log('IMDB GraphQL: %s' % imdb_id)
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    try:
        body = (_IMDB_GRAPHQL_QUERY % imdb_id).encode('utf-8')
        req = Request(_IMDB_GRAPHQL_URL, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        req.add_header('User-Agent',
                       'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36')
        resp = urlopen(req, timeout=5)
        data = json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        if e.code in (403, 429):
            _imdb_dead = True
            _log('IMDB blocked: HTTP %d — skipping IMDB for rest of session' % e.code)
        else:
            _log('IMDB GraphQL HTTP %s' % e.code)
        return ('', '')
    except Exception as e:
        _log('IMDB GraphQL error: %s' % e)
        return ('', '')
    # Parse response: data.title.primaryVideos.edges[0].node.playbackURLs
    try:
        edges = data['data']['title']['primaryVideos']['edges']
    except (KeyError, TypeError):
        _log('IMDB: unexpected GraphQL structure for %s' % imdb_id)
        _imdb_cache[imdb_id] = ('', '', time.time() + _IMDB_CACHE_TTL)
        return ('', '')
    if not edges:
        _log('IMDB: no trailer for %s' % imdb_id)
        _imdb_cache[imdb_id] = ('', '', time.time() + _IMDB_CACHE_TTL)
        return ('', '')
    node = edges[0].get('node', {})
    video_name = (node.get('name') or {}).get('value', '')
    urls = node.get('playbackURLs', [])
    _log('IMDB: video=%s name=%r urls=%d' % (node.get('id', ''), video_name, len(urls)))
    if not urls:
        _imdb_cache[imdb_id] = ('', '', time.time() + _IMDB_CACHE_TTL)
        return ('', '')
    # Pick best quality MP4
    best_url = ''
    best_quality = ''
    for pref in _IMDB_QUALITY_ORDER:
        for entry in urls:
            if entry.get('videoDefinition') == pref and entry.get('mimeType') == 'video/mp4':
                best_url = entry['url']
                best_quality = pref.replace('DEF_', '')
                break
        if best_url:
            break
    # Fallback to HLS (M3U8)
    if not best_url:
        for entry in urls:
            if 'mpegurl' in (entry.get('mimeType') or '').lower():
                best_url = entry['url']
                best_quality = 'HLS'
                break
    # Fallback to any MP4
    if not best_url:
        for entry in urls:
            if entry.get('mimeType') == 'video/mp4':
                best_url = entry['url']
                best_quality = (entry.get('videoDefinition') or '').replace('DEF_', '') or '?'
                break
    _log('IMDB result: quality=%s url=%s' % (best_quality, best_url[:80] if best_url else ''))
    _imdb_cache[imdb_id] = (best_url, best_quality, time.time() + _IMDB_CACHE_TTL)
    return (best_url, best_quality)


# ── Notification + playback ───────────────────────────────────────────────────

def _notify(search_title, step, source, vtype, lang, poster):
    """3-second notification popup (upper-right).
    Heading: search title used (DE or EN).
    Message: source - type [lang]  e.g. 'TMDB - Trailer [DE]'
    If lang is empty (e.g. IMDB): 'IMDB - Trailer'
    """
    try:
        import xbmcgui
        icon = poster if poster else xbmcgui.NOTIFICATION_INFO
        msg = '%s - %s [%s]' % (source, vtype, lang) if lang else '%s - %s' % (source, vtype)
        xbmcgui.Dialog().notification(
            search_title,
            msg,
            icon,
            3000,
            False,
        )
    except Exception:
        pass


def _play(video_id, step, source, vtype, lang, poster, search_title):
    """Show source/language popup then play via SmartTube (if installed) or YouTube addon."""
    import xbmc
    _log('PLAY video_id=%s step=%d source=%s vtype=%s lang=%s title=%r'
         % (video_id, step, source, vtype, lang, search_title))
    _notify(search_title, step, source, vtype, lang, poster)
    pkg = _getSmartTubePackage()
    if pkg:
        xbmc.sleep(2000)  # let notification show before SmartTube covers Kodi UI
        _log('PLAY via SmartTube (%s)' % pkg)
        xbmc.executebuiltin(
            'StartAndroidActivity(%s,android.intent.action.VIEW,,'
            'https://www.youtube.com/watch?v=%s)' % (pkg, video_id)
        )
    else:
        _log('PLAY via YouTube addon')
        xbmc.executebuiltin(
            'PlayMedia(plugin://plugin.video.youtube/play/?video_id=%s)' % video_id
        )


class _TrailerPlayer(object):
    """Kodi player wrapper with callbacks for immediate stop/end detection."""
    def __init__(self):
        import xbmc as _xbmc
        class _P(_xbmc.Player):
            def __init__(s): super().__init__(); s.done = False
            def onPlayBackStopped(s): s.done = True
            def onPlayBackEnded(s): s.done = True
            def onPlayBackError(s): s.done = True
        self._p = _P()
        self._mon = _xbmc.Monitor()
        self._xbmc = _xbmc
    def play(self, url):  self._p.play(url)
    def stop(self): self._p.stop()
    @property
    def done(self): return self._p.done
    def wait(self, secs): return self._mon.waitForAbort(secs)
    @property
    def aborted(self): return self._mon.abortRequested()
    def fullscreen(self):
        return self._xbmc.getCondVisibility('Window.IsVisible(fullscreenvideo)')


def _playDirect(url, step, source, vtype, lang, poster, search_title):
    """Show source popup then play a direct MP4/M3U8 URL via Kodi's native player.
    Monitors fullscreen — stops playback when user presses back."""
    _log('PLAY-DIRECT url=%s step=%d source=%s vtype=%s title=%r'
         % (url[:80], step, source, vtype, search_title))
    _notify(search_title, step, source, vtype, lang, poster)
    tp = _TrailerPlayer()
    tp.play(url)
    # Wait for fullscreen to appear — exit early if playback fails
    fs_seen = False
    while not tp.aborted and not tp.done:
        if tp.fullscreen():
            fs_seen = True
            break
        tp.wait(0.1)
    if not fs_seen:
        _log('PLAY-DIRECT: playback ended before fullscreen')
        return
    # Monitor: stop when user leaves fullscreen (back = stop for trailers)
    while not tp.aborted and not tp.done:
        if not tp.fullscreen():
            tp.stop()
            _log('PLAY-DIRECT stopped (user left fullscreen)')
            break
        tp.wait(0.3)


# ── One-time guidance popups (v7) ─────────────────────────────────────────────

def _showHintIfNeeded(has_yt_player, has_own_key, found_german, played_imdb):
    """Show guidance popup after trailer plays (or at give-up). Once per Kodi session.
    Popup 1: no player installed, IMDB played → suggest SmartTube / YT addon.
    Popup 2: has player but no own key, no German found → suggest own API key.
    Returns True if a popup was shown."""
    try:
        import xbmc, xbmcgui
        win = xbmcgui.Window(10000)

        if not has_yt_player and played_imdb:
            # Popup 1: IMDB worked but no player for KinoCheck/TMDB/YouTube
            if not win.getProperty('xvault.trailer.hint.player'):
                xbmc.sleep(2000)
                is_android = xbmc.getCondVisibility('System.Platform.Android')
                if is_android:
                    msg = ('Tipp: Für deutsche Trailer (KinoCheck/TMDB) SmartTube installieren.\n'
                           'Für YouTube-Suche zusätzlich: YouTube Add-on mit eigenem API-Key einrichten.')
                else:
                    msg = ('Tipp: YouTube Add-on mit eigenem API-Key installieren für '
                           'deutsche Trailer (KinoCheck/TMDB) und YouTube-Suche.')
                xbmcgui.Dialog().ok('Trailer', msg)
                win.setProperty('xvault.trailer.hint.player', '1')
                _log('hint: showed player popup')
                return True

        elif has_yt_player and not has_own_key and not found_german:
            # Popup 2: has player but no own key, no German trailer found
            if not win.getProperty('xvault.trailer.hint.apikey'):
                xbmc.sleep(2000)
                msg = ('Kein deutscher Trailer bei KinoCheck/TMDB/IMDB gefunden.\n'
                       'YouTube Add-on mit eigenem API-Key einrichten für zusätzliche YouTube-Trailersuche.')
                xbmcgui.Dialog().ok('Trailer', msg)
                win.setProperty('xvault.trailer.hint.apikey', '1')
                _log('hint: showed apikey popup')
                return True

    except Exception as e:
        _log('hint popup error: %s' % e)
    return False


# ── Main entry point ──────────────────────────────────────────────────────────

def playTrailer(tmdb_id, mediatype='movie', title='', year='', poster=''):
    """Trailer waterfall for xVAULT — search phase + play phase.

    Args:
        tmdb_id:   TMDB numeric ID (string)
        mediatype: 'movie' or 'tv'
        title:     display title in German (for YouTube fallback searches)
        year:      release year string  (for YouTube fallback searches)
        poster:    poster image URL     (shown as notification icon)
    """
    import xbmc, xbmcgui
    from resources.lib.tmdb import cTMDB

    url_type  = 'movie' if mediatype == 'movie' else 'tv'
    title_key = 'title' if mediatype == 'movie' else 'name'
    tmdb_de   = cTMDB()
    tmdb_en   = cTMDB(lang='en')

    _log('START tmdb_id=%s title=%r year=%s mediatype=%s' % (tmdb_id, title, year, mediatype))

    # ── Capability detection (no early exit — IMDB works without YT player) ──
    smarttube = _getSmartTubePackage()
    has_yt_addon = xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)')
    has_yt_player = bool(smarttube or has_yt_addon)
    has_own_key = bool(_getUserKey())
    skip_api = bool(smarttube)  # SmartTube handles age-gates, no videos.list needed
    _vf = _api_checksum         # verification fallback
    _log('Player: %s | YT addon: %s | has_yt_player: %s | has_own_key: %s | skip_api: %s' % (
        smarttube if smarttube else 'none', has_yt_addon, has_yt_player, has_own_key, skip_api))

    # ── Pre-flight: offer to enable ISA if off (once per session) ────
    # Only when YouTube addon is the player (not SmartTube)
    if not smarttube and has_yt_addon:
        _ISA_WARNED = 'xvault.trailer.isa_warned'
        try:
            import xbmcaddon
            from resources.lib.control import window
            yt = xbmcaddon.Addon('plugin.video.youtube')
            if yt.getSetting('kodion.video.quality.isa') != 'true':
                if not window.getProperty(_ISA_WARNED):
                    window.setProperty(_ISA_WARNED, '1')
                    if xbmcgui.Dialog().yesno(
                            'Trailer',
                            '"InputStream Adaptive" im YouTube Add-on ist aus.\n'
                            'Trailer-Wiedergabe kann fehlschlagen. Aktivieren?'):
                        yt.setSetting('kodion.video.quality.isa', 'true')
                        _log('ISA enabled via pre-flight check')
        except Exception:
            pass

    # ── Fetch English title + IMDB ID up front ───────────────────────
    en_data = None
    try:
        if url_type == 'tv':
            en_data = tmdb_en.getUrl('%s/%s' % (url_type, tmdb_id), term='append_to_response=external_ids')
        else:
            en_data = tmdb_en.getUrl('%s/%s' % (url_type, tmdb_id))
        en_title = (en_data or {}).get(title_key, '') or title
    except Exception:
        en_title = title
    # Extract IMDB ID (movies: top-level; TV: external_ids sub-object)
    imdb_id = (en_data or {}).get('imdb_id', '')
    if not imdb_id and url_type == 'tv':
        imdb_id = (en_data or {}).get('external_ids', {}).get('imdb_id', '') or ''
    _log('EN title: %r (DE title: %r) imdb_id: %s' % (en_title, title, imdb_id))

    # ── Steps 1-3: YouTube-based sources (skip if no YT player) ──────
    if has_yt_player:
        # ── Step 1: KinoCheck API (exact TMDB ID, free, no YT quota) ─────
        _log('--- Step 1: KinoCheck API ---')
        kc_api_hits, kc_api_ok = _searchKinoCheckAPI(tmdb_id, mediatype)
        _log('Step1 KinoCheck-API: hits=%d api_ok=%s' % (len(kc_api_hits), kc_api_ok))
        if kc_api_hits:
            # Red Band trailers may be age-restricted — prefer non-Red-Band on YT addon
            if not skip_api:
                non_rb = [h for h in kc_api_hits if 'red band' not in h.get('name', '').lower()]
                if non_rb:
                    kc_api_hits = non_rb
                else:
                    # Only Red Band results — age-check before playing on YT addon
                    _log('Step1 KinoCheck-API: only Red Band, running age-check')
                    kc_api_hits = _filterAgeRestricted(kc_api_hits, skip_api=False, api_key=_vf)
            else:
                # SmartTube — still verify video exists (free oEmbed check)
                kc_api_hits = _filterExistence(kc_api_hits)
            if kc_api_hits:
                _play(kc_api_hits[0]['key'], 1, 'KinoCheck', 'Trailer', 'DE', poster, title)
                _showHintIfNeeded(has_yt_player, has_own_key, True, False)
                return
            _log('Step1 KinoCheck-API: all results unavailable, continuing waterfall')

        # ── Step 1b: KinoCheck YT channel (API down + own key for search.list) ─
        if not kc_api_ok and has_own_key:
            _log('--- Step 1b: KinoCheck YT fallback (API was down) ---')
            kc_raw = _searchKinoCheck(title, year)
            kc_hit = _filterByDuration(kc_raw, skip_api=skip_api, api_key=_vf)
            _log('Step1b KinoCheck-YT: raw=%d filtered=%d' % (len(kc_raw), len(kc_hit)))
            if kc_hit:
                _play(kc_hit[0]['key'], 1, 'KinoCheck', 'Trailer', 'DE', poster, title)
                _showHintIfNeeded(has_yt_player, has_own_key, True, False)
                return

        # ── Step 2: TMDB videos (German) ──────────────────────────────────
        _log('--- Step 2: TMDB-DE videos ---')
        tmdb_de_raw = tmdb_de.getUrl('%s/%s/videos' % (url_type, tmdb_id))
        videos = _filterAgeRestricted(_tmdbVideos(tmdb_de_raw, lang='de'), skip_api=skip_api, api_key=_vf)
        _log('Step2 TMDB-DE: raw=%d filtered=%d' % (len((tmdb_de_raw or {}).get('results', [])), len(videos)))
        if videos:
            # TMDB iso_639_1='de' only means German metadata tag — video may be English.
            # If DE title doesn't appear in the video name, treat it as English.
            vname = (videos[0].get('name') or '').lower()
            _norm = lambda s: re.sub(r"['\u2019\-]", '', s.lower())
            if _norm(title) in _norm(vname):
                step2_title, step2_lang = title, 'DE'
            else:
                step2_title, step2_lang = en_title, 'EN'
            _log('Step2 lang-detect: vname=%r -> %s title=%r' % (vname[:60], step2_lang, step2_title))
            _play(videos[0]['key'], 2, 'TMDB', videos[0].get('type', 'Trailer'), step2_lang, poster, step2_title)
            _showHintIfNeeded(has_yt_player, has_own_key, step2_lang == 'DE', False)
            return

        # ── Step 3: TMDB videos (English) ─────────────────────────────────
        _log('--- Step 3: TMDB-EN videos ---')
        tmdb_en_raw = tmdb_en.getUrl('%s/%s/videos' % (url_type, tmdb_id))
        videos = _filterAgeRestricted(_tmdbVideos(tmdb_en_raw, lang='en'), skip_api=skip_api, api_key=_vf)
        _log('Step3 TMDB-EN: raw=%d filtered=%d' % (len((tmdb_en_raw or {}).get('results', [])), len(videos)))
        if videos:
            _play(videos[0]['key'], 3, 'TMDB', videos[0].get('type', 'Trailer'), 'EN', poster, en_title)
            _showHintIfNeeded(has_yt_player, has_own_key, False, False)
            return
    else:
        tmdb_en_raw = None  # not fetched — no YT player to play TMDB results

    # ── Step 3b: IMDB (direct MP4, no player needed) ─────────────────
    if imdb_id and not _imdb_dead:
        _log('--- Step 3b: IMDB ---')
        imdb_url, imdb_quality = _searchIMDB(imdb_id)
        _log('Step3b IMDB: url=%s quality=%s' % (imdb_url[:80] if imdb_url else '', imdb_quality))
        if imdb_url:
            _playDirect(imdb_url, 3, 'IMDB', 'Trailer', '', poster, en_title or title)
            _showHintIfNeeded(has_yt_player, has_own_key, False, True)
            return

    # ── Steps 4-5b: YouTube search + TMDB-ANY ────────────────────────
    if has_yt_player:
        # ── Steps 4-5: YouTube search (needs own API key for search.list) ─
        if has_own_key:
            user_key = _getUserKey()

            # ── Step 4: YouTube search (German) ───────────────────────────
            _log('--- Step 4: YouTube-DE ---')
            yt_de_raw = _searchYouTube(title, year, lang='de')
            yt_de_hit = _filterByDuration(yt_de_raw, skip_api=skip_api, api_key=user_key)
            _log('Step4 YouTube-DE: raw=%d filtered=%d' % (len(yt_de_raw), len(yt_de_hit)))
            if yt_de_hit and _oembedSanityCheck(yt_de_hit[0]['key'], title, year):
                _play(yt_de_hit[0]['key'], 4, 'YouTube', 'Trailer', 'DE', poster, title)
                _showHintIfNeeded(has_yt_player, has_own_key, True, False)
                return

            # ── Step 5: YouTube search (English TMDB title) ───────────────
            _log('--- Step 5: YouTube-EN ---')
            yt_en_raw = _searchYouTube(en_title, year, lang='en')
            yt_en_hit = _filterByDuration(yt_en_raw, skip_api=skip_api, api_key=user_key)
            _log('Step5 YouTube-EN title=%r raw=%d filtered=%d' % (en_title, len(yt_en_raw), len(yt_en_hit)))
            if yt_en_hit and _oembedSanityCheck(yt_en_hit[0]['key'], en_title, year):
                _play(yt_en_hit[0]['key'], 5, 'YouTube', 'Trailer', 'EN', poster, en_title)
                _showHintIfNeeded(has_yt_player, has_own_key, False, False)
                return

        # ── Step 5b: TMDB videos (any language — catches ES, KO, ZH, JA, etc.) ─
        _log('--- Step 5b: TMDB-ANY videos ---')
        # Reuse tmdb_en_raw (EN endpoint returns all videos, we just filtered for EN before)
        if tmdb_en_raw:
            videos = _filterAgeRestricted(_tmdbVideos(tmdb_en_raw), skip_api=skip_api, api_key=_vf)
            # Exclude DE/EN videos we already tried
            videos = [v for v in videos if v.get('iso_639_1') not in ('de', 'en')]
        else:
            videos = []
        _log('Step5b TMDB-ANY: filtered=%d' % len(videos))
        if videos:
            vlang = (videos[0].get('iso_639_1') or '??').upper()
            _play(videos[0]['key'], 5, 'TMDB', videos[0].get('type', 'Trailer'), vlang, poster, en_title)
            _showHintIfNeeded(has_yt_player, has_own_key, False, False)
            return

    # ── Step 6: Give up ───────────────────────────────────────────────
    _log('Step6 give up — has_yt_player=%s has_own_key=%s' % (has_yt_player, has_own_key))
    hint_shown = _showHintIfNeeded(has_yt_player, has_own_key, False, False)
    if not hint_shown:
        if not has_yt_player:
            is_android = xbmc.getCondVisibility('System.Platform.Android')
            if is_android:
                msg = 'Kein Trailer gefunden.\nSmartTube oder YouTube Add-on installieren fuer mehr Quellen.'
            else:
                msg = 'Kein Trailer gefunden.\nYouTube Add-on installieren fuer mehr Quellen.'
            xbmcgui.Dialog().ok('Trailer', msg)
        else:
            xbmcgui.Dialog().notification(
                'Trailer', 'Kein Trailer gefunden',
                xbmcgui.NOTIFICATION_WARNING, 3000,
            )
