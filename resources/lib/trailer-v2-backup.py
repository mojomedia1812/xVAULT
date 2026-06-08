# -*- coding: utf-8 -*-
# Python 3
#
# Trailer lookup for xVAULT context menu.
# TMDB ID is already known for every xVAULT item — no ID resolution needed.
#
# Lookup waterfall:
#   1.  KinoCheck API         — exact TMDB ID lookup, free, no YT quota
#   1b. KinoCheck YT channel  — fallback only when API is down/rate-limited
#   2.  TMDB videos (German)  — Trailer/Teaser, newest first
#   3.  YouTube search (DE)   — relevanceLanguage=de, strict title filter
#   4.  TMDB videos (English) — Trailer/Teaser, newest first
#   5.  YouTube search (EN)   — English TMDB title, strict title filter
#   5b. TMDB videos (any)    — fallback for 3rd languages (ES, KO, ZH, JA, ...)
#   6.  Give up
#
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

# Cached SmartTube detection: None=unchecked, str=package name, False=not found
_smarttube_pkg = None


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
            ret = subprocess.call(['pm', 'path', pkg],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if ret == 0:
                _smarttube_pkg = pkg
                _log('SmartTube found: %s' % pkg)
                return pkg
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
    Uses urllib.request directly — cRequestHandler mangles percent-encoded
    query parameters (%22 → %2522) which breaks YouTube quoted searches."""
    try:
        import json
        from urllib.request import Request, urlopen
        req = Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        _log('_fetchJSON error: %s url=%s' % (e, url[:120]))
        return {}


# ── YouTube helpers ───────────────────────────────────────────────────────────

def _getYouTubeApiKey():
    try:
        import xbmcvfs, json
        f    = xbmcvfs.File('special://profile/addon_data/plugin.video.youtube/api_keys.json')
        data = json.loads(f.read())
        f.close()
        key = data.get('keys', {}).get('user', {}).get('api_key', '')
        _log('YT-apikey: %s' % ('found (%s...)' % key[:8] if key else 'MISSING'))
        return key
    except Exception as e:
        _log('YT-apikey: exception %s' % e)
        return ''


def _fetchVideoDetails(keys):
    """Call YouTube Data API v3 to get duration, age-restriction, privacy and category for video IDs.
    Returns dict {video_id: {...}} on success (may be empty if videos are unavailable).
    Returns None on API failure (no key, network error, exception)."""
    try:
        apikey = _getYouTubeApiKey()
        if not apikey or not keys:
            return None
        url  = ('https://www.googleapis.com/youtube/v3/videos'
                '?part=contentDetails,status,snippet,statistics&id=%s&key=%s' % (','.join(keys), apikey))
        data = _fetchJSON(url)
        if not data:
            return None   # network/parse error
        result = {}
        for item in data.get('items', []):
            cd  = item.get('contentDetails', {})
            st  = item.get('status', {})
            sn  = item.get('snippet', {})
            stats = item.get('statistics', {})
            dur = cd.get('duration', '')
            m   = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', dur)
            secs = (int(m.group(1) or 0) * 3600
                    + int(m.group(2) or 0) * 60
                    + int(m.group(3) or 0)) if m else 0
            age_restricted = cd.get('contentRating', {}).get('ytRating') == 'ytAgeRestricted'
            unlisted = st.get('privacyStatus') != 'public'
            # categoryId 22 = "People & Blogs" — strong cam-rip / amateur upload signal
            cam_rip = sn.get('categoryId') == '22'
            views = int(stats.get('viewCount', 0))
            result[item['id']] = {'secs': secs, 'age_restricted': age_restricted,
                                  'unlisted': unlisted, 'cam_rip': cam_rip, 'views': views}
        _log('video-details ids=%s result=%s' % (keys, result))
        return result   # may be {} if all videos are unavailable — that's valid
    except Exception as e:
        _log('video-details exception: %s' % e)
        return None


def _filterByDuration(hits, minS=60, maxS=360):
    """Filter YouTube hits by duration [minS, maxS] and remove age-restricted/unlisted/cam-rip videos.
    Falls back to unfiltered list only if API is completely unavailable (None)."""
    if not hits:
        return []
    details = _fetchVideoDetails([h['key'] for h in hits])
    if details is None:
        _log('duration-filter: API unavailable, returning unfiltered (%d hits)' % len(hits))
        return hits
    filtered = []
    for h in hits:
        d = details.get(h['key'])
        if d is None:
            # Video missing from API response → unavailable/restricted → skip
            _log('duration-filter %s: not in API response REJECT' % h['key'])
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
    # best must have ≥10K views AND ≥10× more than the current first pick
    if len(filtered) >= 2:
        views = [(details.get(h['key'], {}).get('views', 0), h) for h in filtered]
        best_views = max(v for v, _ in views)
        first_views = views[0][0]
        if best_views >= 10000 and best_views >= 10 * max(first_views, 1):
            filtered.sort(key=lambda h: details.get(h['key'], {}).get('views', 0), reverse=True)
            _log('view-rank: promoted %s (%d views) over %s (%d views)' % (
                filtered[0]['key'], best_views, views[0][1]['key'], first_views))
    return filtered  # empty = all rejected → waterfall continues to next step


def _filterAgeRestricted(hits):
    """Remove age-restricted, unlisted, cam-rip and unavailable videos — for TMDB results.
    Falls back to unfiltered list only if API is completely unavailable (None)."""
    if not hits:
        return []
    details = _fetchVideoDetails([h['key'] for h in hits])
    if details is None:
        return hits
    filtered = []
    for h in hits:
        d = details.get(h['key'])
        if d is None:
            _log('age-check %s: not in API response SKIP' % h['key'])
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
    """Decode HTML entities in YouTube API snippet titles (&#39; → ', &quot; → ", etc.)."""
    from html import unescape
    return unescape(s)


def _titleOkChannel(vtitle, title, year=''):
    """Title check for curated channel results (KinoCheck): title match, no Shorts, year conflict."""
    vl = _htmlDecode(vtitle).lower()
    if title.lower() not in vl:
        return False
    if '#short' in vl:
        return False
    # Reject if video title contains a different year — catches franchise mix-ups
    # e.g. searching "Terminator" (1984) should reject "Terminator 6 ... (2019)"
    if year:
        found_years = re.findall(r'\((\d{4})\)', vtitle)
        if found_years and year not in found_years:
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
    # Reject if video title contains a different year
    if year:
        found_years = re.findall(r'\((\d{4})\)', vtitle)
        if found_years and year not in found_years:
            return False
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
    # Two stable sorts: first by date descending, then by type rank ascending.
    videos.sort(key=lambda v: v.get('published_at', ''), reverse=True)
    videos.sort(key=lambda v: 0 if v.get('type') == 'Trailer' else 1)
    return videos


# ── Source-specific search functions ─────────────────────────────────────────

def _searchKinoCheckAPI(tmdb_id, mediatype='movie'):
    """Exact TMDB ID lookup via KinoCheck API. Free, no key required, no YT quota.
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
            return [], True   # api_ok=True → they don't have it, skip YT fallback
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
    Year-matched results bubble to the top. Returns list of {name, key}."""
    try:
        from urllib.parse import quote_plus
        apikey = _getYouTubeApiKey()
        if not apikey:
            _log('KinoCheck: no API key, skipping')
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
                hits.insert(0, entry)   # year match → front
            else:
                hits.append(entry)
        return hits
    except Exception as e:
        _log('KinoCheck exception: %s' % e)
        return []


def _searchYouTube(title, year, lang=''):
    """Global YouTube search with strict title filter.
    Tries 'official trailer' first, falls back to 'trailer' if no results.
    Returns list of {name, key}."""
    try:
        from urllib.parse import quote_plus
        apikey = _getYouTubeApiKey()
        if not apikey:
            _log('YouTube-%s: no API key, skipping' % (lang or 'xx'))
            return []
        for suffix in ('official trailer', 'trailer'):
            parts = ['"%s"' % title]
            if year:
                parts.append(str(year))
            parts.append(suffix)
            query = ' '.join(parts)
            url = ('https://www.googleapis.com/youtube/v3/search?part=snippet'
                   '&q=%s&type=video&maxResults=10&key=%s'
                   % (quote_plus(query), apikey))
            if lang:
                url += '&relevanceLanguage=%s' % lang[:2]
            _log('YouTube-%s query: %r' % (lang or 'xx', query))
            data = _fetchJSON(url)
            results = []
            for it in data.get('items', []):
                vtitle = it['snippet']['title']
                ok     = _titleOkGlobal(vtitle, title, year)
                _log('  YouTube-%s %s: %r' % (lang or 'xx', 'PASS' if ok else 'REJECT', vtitle[:80]))
                if ok:
                    results.append({'name': vtitle, 'key': it['id']['videoId']})
            if results:
                return results
            _log('YouTube-%s: no results with "%s", trying fallback' % (lang or 'xx', suffix))
        return []
    except Exception as e:
        _log('YouTube-%s exception: %s' % (lang or 'xx', e))
        return []


# ── Notification + playback ───────────────────────────────────────────────────

def _notify(search_title, step, source, vtype, lang, poster):
    """3-second notification popup (upper-right).
    Heading: search title used (DE or EN).
    Message: #step source · type [lang]  e.g. '#1 TMDB · Trailer [DE]'
    """
    try:
        import xbmcgui
        icon = poster if poster else xbmcgui.NOTIFICATION_INFO
        xbmcgui.Dialog().notification(
            search_title,
            '%s - %s [%s]' % (source, vtype, lang),
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


# ── Main entry point ──────────────────────────────────────────────────────────

def playTrailer(tmdb_id, mediatype='movie', title='', year='', poster=''):
    """6-step trailer waterfall for xVAULT.

    Args:
        tmdb_id:   TMDB numeric ID (string)
        mediatype: 'movie' or 'tv'
        title:     display title in German (for YouTube fallback searches)
        year:      release year string  (for YouTube fallback searches)
        poster:    poster image URL     (shown as notification icon)
    """
    import xbmcgui
    from resources.lib.tmdb import cTMDB

    url_type  = 'movie' if mediatype == 'movie' else 'tv'
    title_key = 'title' if mediatype == 'movie' else 'name'
    tmdb_de   = cTMDB()
    tmdb_en   = cTMDB(lang='en')

    _log('START tmdb_id=%s title=%r year=%s mediatype=%s' % (tmdb_id, title, year, mediatype))

    # ── Pre-flight: offer to enable ISA if off (once per session) ────────
    # Skip if SmartTube is available — ISA is only needed for YouTube addon
    if not _getSmartTubePackage():
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

    # ── Fetch English title up front (needed for accurate popup in all steps) ─
    try:
        en_data  = tmdb_en.getUrl('%s/%s' % (url_type, tmdb_id))
        en_title = (en_data or {}).get(title_key, '') or title
    except Exception:
        en_title = title
    _log('EN title: %r (DE title: %r)' % (en_title, title))

    # ── Step 1: KinoCheck API (exact TMDB ID, free, no YT quota) ─────────
    _log('--- Step 1: KinoCheck API ---')
    kc_api_hits, kc_api_ok = _searchKinoCheckAPI(tmdb_id, mediatype)
    _log('Step1 KinoCheck-API: hits=%d api_ok=%s' % (len(kc_api_hits), kc_api_ok))
    if kc_api_hits:
        _play(kc_api_hits[0]['key'], 1, 'KinoCheck', 'Trailer', 'DE', poster, title)
        return

    # ── Step 1b: KinoCheck YT channel (only if API was down/rate-limited) ─
    if not kc_api_ok:
        _log('--- Step 1b: KinoCheck YT fallback (API was down) ---')
        kc_raw = _searchKinoCheck(title, year)
        kc_hit = _filterByDuration(kc_raw)
        _log('Step1b KinoCheck-YT: raw=%d filtered=%d' % (len(kc_raw), len(kc_hit)))
        if kc_hit:
            _play(kc_hit[0]['key'], 1, 'KinoCheck', 'Trailer', 'DE', poster, title)
            return

    # ── Step 2: TMDB videos (German) ─────────────────────────────────────
    _log('--- Step 2: TMDB-DE videos ---')
    raw2   = tmdb_de.getUrl('%s/%s/videos' % (url_type, tmdb_id))
    videos = _filterAgeRestricted(_tmdbVideos(raw2, lang='de'))
    _log('Step2 TMDB-DE: raw=%d filtered=%d' % (len((raw2 or {}).get('results', [])), len(videos)))
    if videos:
        # TMDB iso_639_1='de' only means German metadata tag — video may be English.
        # If DE title doesn't appear in the video name, treat it as English.
        vname = (videos[0].get('name') or '').lower()
        # Normalize apostrophes/hyphens before comparing (e.g. "Grey's" vs "Greys")
        _norm = lambda s: re.sub(r"['\u2019\-]", '', s.lower())
        if _norm(title) in _norm(vname):
            step2_title, step2_lang = title, 'DE'
        else:
            step2_title, step2_lang = en_title, 'EN'
        _log('Step2 lang-detect: vname=%r -> %s title=%r' % (vname[:60], step2_lang, step2_title))
        _play(videos[0]['key'], 2, 'TMDB', videos[0].get('type', 'Trailer'), step2_lang, poster, step2_title)
        return

    # ── Step 3: YouTube search (German) ──────────────────────────────────
    _log('--- Step 3: YouTube-DE ---')
    yt_raw = _searchYouTube(title, year, lang='de')
    yt_hit = _filterByDuration(yt_raw)
    _log('Step3 YouTube-DE: raw=%d filtered=%d' % (len(yt_raw), len(yt_hit)))
    if yt_hit:
        _play(yt_hit[0]['key'], 3, 'YouTube', 'Trailer', 'DE', poster, title)
        return

    # ── Step 4: TMDB videos (English) ────────────────────────────────────
    _log('--- Step 4: TMDB-EN videos ---')
    raw4   = tmdb_en.getUrl('%s/%s/videos' % (url_type, tmdb_id))
    videos = _filterAgeRestricted(_tmdbVideos(raw4, lang='en'))
    _log('Step4 TMDB-EN: raw=%d filtered=%d' % (len((raw4 or {}).get('results', [])), len(videos)))
    if videos:
        _play(videos[0]['key'], 4, 'TMDB', videos[0].get('type', 'Trailer'), 'EN', poster, en_title)
        return

    # ── Step 5: YouTube search (English TMDB title) ──────────────────────
    _log('--- Step 5: YouTube-EN ---')
    yt_raw5 = _searchYouTube(en_title, year, lang='en')
    yt_hit5 = _filterByDuration(yt_raw5)
    _log('Step5 YouTube-EN title=%r raw=%d filtered=%d' % (en_title, len(yt_raw5), len(yt_hit5)))
    if yt_hit5:
        _play(yt_hit5[0]['key'], 5, 'YouTube', 'Trailer', 'EN', poster, en_title)
        return

    # ── Step 5b: TMDB videos (any language — catches ES, KO, ZH, JA, etc.) ─
    _log('--- Step 5b: TMDB-ANY videos ---')
    # Reuse raw4 (EN endpoint returns all videos, we just filtered for EN before)
    videos = _filterAgeRestricted(_tmdbVideos(raw4))
    # Exclude DE/EN videos we already tried
    videos = [v for v in videos if v.get('iso_639_1') not in ('de', 'en')]
    _log('Step5b TMDB-ANY: filtered=%d' % len(videos))
    if videos:
        vlang = (videos[0].get('iso_639_1') or '??').upper()
        _play(videos[0]['key'], 5, 'TMDB', videos[0].get('type', 'Trailer'), vlang, poster, en_title)
        return

    # ── Step 6: Give up ──────────────────────────────────────────────────
    _log('Step6 give up')
    xbmcgui.Dialog().notification(
        'Trailer', 'Kein Trailer gefunden',
        xbmcgui.NOTIFICATION_WARNING, 3000,
    )
