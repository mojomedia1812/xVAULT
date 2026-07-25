import base64
import html
import json
import os
import re
import sys
import time
from urllib.parse import quote, urlencode, urljoin

try:
    import requests
except Exception:
    requests = None

from resources.lib import control, log_utils
from resources.lib import linear_tv


BASE_URL = "https://www.2ix2.com"
POSTS_URL = BASE_URL + "/wp-json/wp/v2/posts"
NYDUS_BASE_URL = "https://nydus.org"
NYDUS_LIVE_URL = NYDUS_BASE_URL + "/stream/live/"
NYDUS_EMBED_URL = NYDUS_BASE_URL + "/stream/embedplayer_hq.php?id=%s"
CACHE_FILE = os.path.join(control.addonProfilePath, "linear-tv-lite-catalog.json")
FAVORITES_FILE = os.path.join(control.addonProfilePath, "linear-tv-lite-favorites.json")
CACHE_TTL = 6 * 60 * 60
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
    "Gecko/20100101 Firefox/128.0"
)

CATEGORIES = (
    {"slug": "de", "label": "Deutsche TV", "category_id": 1},
    {"slug": "at", "label": "Österreichische TV", "category_id": 61},
    {"slug": "ch", "label": "Schweizer TV", "category_id": 100},
)

NYDUS_AUSTRIA_IDS = {"orf-1", "orf-2", "servus-tv"}
NYDUS_SWISS_IDS = {"srf1", "srf2", "srf-info", "srfinfo", "3plus", "4plus", "5plus", "6plus"}


def show_home():
    handle = _handle()
    _add_folder(handle, "Senderliste aktualisieren", {"action": "liveTVLiteRefresh"}, False)
    _add_folder(handle, "Favoriten", {"action": "liveTVLiteFavorites"}, True)
    for category in CATEGORIES:
        _add_folder(
            handle,
            category["label"],
            {"action": "liveTVLiteCategory", "category": category["slug"]},
            True,
        )
    _end("LiveTV lite", cache=False)


def refresh():
    channels = _catalog(refresh=True)
    control.infoDialog("LiveTV lite aktualisiert: %d Sender" % len(channels), icon="INFO", time=4000)
    show_home()


def show_category(category_slug):
    category = _category(category_slug)
    if not category:
        control.infoDialog("Kategorie nicht gefunden", icon="WARNING", time=3500)
        _end("LiveTV lite", cache=False)
        return

    channels = [channel for channel in _catalog() if channel.get("category_slug") == category["slug"]]
    _show_channels(channels, category["label"])


def show_favorites():
    _show_channels(_load_favorites(), "Favoriten", favorite_context=True)


def add_favorite(channel_id):
    channel = _channel_by_id(_catalog(), channel_id) or _channel_by_id(_load_favorites(), channel_id)
    if not channel:
        control.infoDialog("Sender nicht gefunden", icon="WARNING", time=3500)
        return
    favorites = _load_favorites()
    if not _channel_by_id(favorites, channel.get("id")):
        favorites.append(_favorite_record(channel))
        _save_favorites(favorites)
    control.infoDialog("TV-Favorit gespeichert", icon="INFO", time=3000)


def remove_favorite(channel_id):
    channel_id = str(channel_id or "")
    favorites = [item for item in _load_favorites() if str(item.get("id") or "") != channel_id]
    _save_favorites(favorites)
    control.infoDialog("TV-Favorit entfernt", icon="INFO", time=3000)
    control.execute("Container.Refresh")


def _show_channels(channels, category_label, favorite_context=False):
    handle = _handle()
    for channel in sorted(channels, key=lambda item: _sort_key(item.get("name"))):
        item = control.item(channel.get("name") or "LiveTV lite", offscreen=True)
        item.setProperty("IsPlayable", "true")
        item.setInfo("video", {
            "title": channel.get("name") or "LiveTV lite",
            "plot": _plot(channel),
            "plotoutline": _plot(channel),
            "mediatype": "video",
        })
        item.setArt(_art(channel))
        item.addContextMenuItems(_context_menu(channel, favorite_context), True)
        control.addItem(handle, _url({"action": "liveTVLitePlay", "id": channel.get("id")}), item, False)
    _end(category_label, cache=False)


def play(channel_id):
    channel = _channel_by_id(_catalog(), channel_id) or _channel_by_id(_load_favorites(), channel_id)
    if not channel:
        control.infoDialog("Sender nicht gefunden", icon="WARNING", time=3500)
        control.resolveUrl(_handle(), False, control.item("LiveTV lite", offscreen=True))
        return

    stream_url = _resolve_channel_stream(channel)
    if not stream_url:
        if channel.get("source") == "nydus":
            control.infoDialog("Nydus-Stream ist in Kodi nicht direkt abspielbar.", icon="WARNING", time=5000)
        else:
            control.infoDialog("Stream konnte nicht gelesen werden", icon="WARNING", time=3500)
        control.resolveUrl(_handle(), False, control.item(channel.get("name") or "LiveTV lite", offscreen=True))
        return
    status = _probe_stream(stream_url, channel.get("page_url"))
    if status and status >= 400:
        source = "Nydus" if channel.get("source") == "nydus" else "2ix2"
        control.infoDialog("%s-Stream aktuell nicht erreichbar (HTTP %s)" % (source, status), icon="WARNING", time=5000)
        control.resolveUrl(_handle(), False, control.item(channel.get("name") or "LiveTV lite", offscreen=True))
        return

    playback_url = _with_kodi_headers(stream_url, channel.get("page_url"))
    item = control.item(channel.get("name") or "LiveTV lite", offscreen=True)
    item.setProperty("IsPlayable", "true")
    item.setInfo("video", {
        "title": channel.get("name") or "LiveTV lite",
        "plot": _plot(channel),
        "plotoutline": _plot(channel),
        "mediatype": "video",
    })
    item.setArt(_art(channel))
    linear_tv._configure_stream(item, playback_url)
    item.setPath(playback_url)
    control.resolveUrl(_handle(), True, item)


def _catalog(refresh=False):
    cached = _read_cache()
    cached_channels = _usable_channels(cached.get("channels") or []) if cached else []
    if not refresh and cached:
        timestamp = int(cached.get("timestamp") or 0)
        if cached_channels and time.time() - timestamp < CACHE_TTL:
            return cached_channels

    channels = _load_channels()
    if channels:
        _write_cache(channels)
        return channels

    fallback = _load_nydus_channels()
    if fallback:
        log_utils.log("LiveTV lite nutzt Nydus als Ersatzquelle: %d Sender" % len(fallback), log_utils.LOGWARNING)
        _write_cache(fallback)
        control.infoDialog("LiveTV lite nutzt Nydus als Ersatzquelle.", icon="WARNING", time=3500)
        return fallback
    if cached_channels:
        control.infoDialog("LiveTV lite nutzt die gespeicherte Senderliste.", icon="WARNING", time=3500)
        return cached_channels
    return []


def _load_channels():
    if requests is None:
        log_utils.log("LiveTV lite failed: requests module is not available", log_utils.LOGWARNING)
        return []

    channels = []
    for category in CATEGORIES:
        try:
            posts = _category_posts(category["category_id"])
        except Exception as exc:
            log_utils.log("LiveTV lite category %s failed: %s" % (category["slug"], str(exc)), log_utils.LOGWARNING)
            continue
        for post in posts:
            channel = _channel_from_post(post, category)
            if channel:
                channels.append(channel)

    return _dedupe_channels(channels)


def _category_posts(category_id):
    response = requests.get(
        POSTS_URL,
        headers=_headers(),
        params={
            "categories": category_id,
            "per_page": 100,
            "_fields": "id,slug,link,title,content",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json() or []


def _channel_from_post(post, category):
    content = post.get("content", {}).get("rendered") or ""
    stream_url = _extract_stream_url(content)
    if not _is_stream_url(stream_url):
        return None

    post_id = str(post.get("id") or post.get("slug") or stream_url)
    return {
        "id": "%s:%s" % (category["slug"], post_id),
        "name": _clean_title(post.get("title", {}).get("rendered") or post.get("slug") or "LiveTV lite"),
        "category": category["label"],
        "category_slug": category["slug"],
        "page_url": post.get("link") or BASE_URL,
        "stream_url": stream_url,
        "source": "2ix2",
    }


def _extract_stream_url(content):
    text = html.unescape(content or "").replace("\\/", "/")
    patterns = (
        r"\bfile\s*:\s*['\"]([^'\"]+)['\"]",
        r"['\"]file['\"]\s*:\s*['\"]([^'\"]+)['\"]",
        r"<source[^>]+src\s*=\s*['\"]([^'\"]+)['\"]",
        r"(https?://[^\s'\"<>]+?\.m3u8(?:\?[^\s'\"<>]+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match and _is_stream_url(match.group(1)):
            return html.unescape(match.group(1)).strip()
    return ""


def _usable_channels(channels):
    return _dedupe_channels([channel for channel in channels or [] if _is_usable_channel(channel)])


def _is_usable_channel(channel):
    if _is_stream_url(channel.get("stream_url")):
        return True
    return channel.get("source") == "nydus" and bool(channel.get("nydus_id"))


def _is_stream_url(value):
    value = html.unescape(value or "").strip()
    if not value.lower().startswith(("http://", "https://")):
        return False
    return ".m3u8" in value.lower()


def _load_nydus_channels():
    if requests is None:
        return []
    try:
        response = requests.get(NYDUS_LIVE_URL, headers=_nydus_headers(), timeout=20)
        response.raise_for_status()
        page = _decode_nydus_page(response.text)
        channels = _parse_nydus_channels(page)
        log_utils.log("LiveTV lite Nydus-Senderliste gelesen: %d Sender" % len(channels), log_utils.LOGINFO)
        return _dedupe_channels(channels)
    except Exception as exc:
        log_utils.log("LiveTV lite Nydus fallback failed: %s" % str(exc), log_utils.LOGWARNING)
        return []


def _decode_nydus_page(content):
    match = re.search(r"var\s+str\s*=\s*['\"]([A-Za-z0-9+/=]+)['\"]", content or "")
    if not match:
        return content or ""
    decoded = _b64decode(match.group(1))
    return decoded or content or ""


def _parse_nydus_channels(content):
    channels = []
    seen = set()
    pattern = re.compile(
        r"<a\b[^>]*href=['\"]([^'\"]*/stream/live/([^'\"]+)/)['\"][^>]*>\s*"
        r"<div\b[^>]*class=['\"][^'\"]*tvsender[^'\"]*['\"][^>]*data-id=['\"]([^'\"]+)['\"][^>]*>\s*"
        r"<img\b[^>]*src=['\"]([^'\"]+)['\"][^>]*alt=['\"]([^'\"]+)['\"]",
        re.I | re.S,
    )
    for match in pattern.finditer(content or ""):
        page_url = urljoin(NYDUS_LIVE_URL, html.unescape(match.group(1)))
        nydus_id = html.unescape(match.group(3)).strip()
        logo_url = urljoin(NYDUS_LIVE_URL, html.unescape(match.group(4)))
        name = _clean_title(html.unescape(match.group(5)).replace("-", " "))
        if not nydus_id or not name:
            continue
        category = _nydus_category(nydus_id)
        if not category:
            continue
        key = (category["slug"], _normalize(name), nydus_id)
        if key in seen:
            continue
        seen.add(key)
        channels.append({
            "id": "nydus:%s:%s" % (category["slug"], nydus_id),
            "name": name,
            "category": category["label"],
            "category_slug": category["slug"],
            "page_url": page_url,
            "stream_url": "",
            "source": "nydus",
            "nydus_id": nydus_id,
            "logo_url": logo_url,
        })
    return channels


def _nydus_category(nydus_id):
    normalized = (nydus_id or "").strip().lower()
    if normalized in NYDUS_AUSTRIA_IDS:
        return _category("at")
    if normalized in NYDUS_SWISS_IDS:
        return _category("ch")
    return _category("de")


def _resolve_channel_stream(channel):
    stream_url = channel.get("stream_url") or ""
    if _is_stream_url(stream_url):
        return stream_url
    if channel.get("source") == "nydus":
        stream_url = _resolve_nydus_stream(channel)
        if _is_stream_url(stream_url):
            channel["stream_url"] = stream_url
            return stream_url
    return ""


def _resolve_nydus_stream(channel):
    if requests is None:
        return ""
    nydus_id = channel.get("nydus_id") or ""
    if not nydus_id:
        return ""
    try:
        embed_url = NYDUS_EMBED_URL % quote(nydus_id, safe="")
        response = requests.get(embed_url, headers=_nydus_headers(channel.get("page_url")), timeout=20)
        response.raise_for_status()
        zdec = re.search(r"zdec\s*=\s*['\"]([^'\"]+)", response.text or "")
        if not zdec:
            return ""
        script = _b64decode(zdec.group(1))
        nested = re.search(r"atob\(['\"]([^'\"]+)", script or "")
        if not nested:
            return ""
        target = _b64decode(nested.group(1))
        if _is_stream_url(target):
            return target
        log_utils.log("LiveTV lite Nydus-Sender ist kein direkter HLS-Stream: %s -> %s" % (nydus_id, target), log_utils.LOGWARNING)
    except Exception as exc:
        log_utils.log("LiveTV lite Nydus resolve failed for %s: %s" % (nydus_id, str(exc)), log_utils.LOGWARNING)
    return ""


def _b64decode(value):
    try:
        return base64.b64decode((value or "").encode("ascii")).decode("utf-8", "replace")
    except Exception:
        return ""


def _dedupe_channels(channels):
    seen = set()
    result = []
    for channel in channels:
        key = (channel.get("category_slug"), _normalize(channel.get("name")))
        if key in seen:
            continue
        seen.add(key)
        result.append(channel)
    return result


def _channel_by_id(channels, channel_id):
    channel_id = str(channel_id or "")
    for channel in channels or []:
        if str(channel.get("id") or "") == channel_id:
            return channel
    return None


def _context_menu(channel, favorite_context=False):
    if favorite_context:
        return [
            ("Aus TV Favoriten entfernen", "RunPlugin(%s)" % _url({"action": "liveTVLiteFavoriteRemove", "id": channel.get("id")})),
        ]
    favorites = _load_favorites()
    if _channel_by_id(favorites, channel.get("id")):
        label = "Aus TV Favoriten entfernen"
        action = "liveTVLiteFavoriteRemove"
    else:
        label = "Zu TV Favoriten hinzufügen"
        action = "liveTVLiteFavoriteAdd"
    return [
        (label, "RunPlugin(%s)" % _url({"action": action, "id": channel.get("id")})),
    ]


def _favorite_record(channel):
    return {
        "id": channel.get("id"),
        "name": channel.get("name"),
        "category": channel.get("category"),
        "category_slug": channel.get("category_slug"),
        "page_url": channel.get("page_url"),
        "stream_url": channel.get("stream_url") or "",
        "source": channel.get("source") or "2ix2",
        "nydus_id": channel.get("nydus_id") or "",
        "logo_url": channel.get("logo_url") or "",
    }


def _load_favorites():
    data = _read_json(FAVORITES_FILE, [])
    return data if isinstance(data, list) else []


def _save_favorites(favorites):
    _write_json(FAVORITES_FILE, favorites)


def _category(slug):
    for category in CATEGORIES:
        if category.get("slug") == slug:
            return category
    return None


def _art(channel):
    icon = channel.get("logo_url") or control.addonIcon()
    return {"icon": icon, "thumb": icon}


def _plot(channel):
    source = "Quelle: Nydus" if channel.get("source") == "nydus" else "Quelle: 2ix2"
    return "%s\n%s\n%s" % (
        channel.get("category") or "LiveTV lite",
        source,
        channel.get("page_url") or BASE_URL,
    )


def _with_kodi_headers(stream_url, referer):
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Referer": referer or BASE_URL + "/",
    }
    separator = "&" if "|" in stream_url else "|"
    return stream_url + separator + urlencode(headers)


def _probe_stream(stream_url, referer):
    if requests is None:
        return None
    try:
        response = requests.get(stream_url, headers=_stream_headers(referer), timeout=10, stream=True)
        try:
            return int(response.status_code)
        finally:
            try:
                response.close()
            except Exception:
                pass
    except Exception as exc:
        log_utils.log("LiveTV lite preflight failed for %s: %s" % (stream_url, str(exc)), log_utils.LOGWARNING)
        return 599


def _stream_headers(referer):
    return {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Referer": referer or BASE_URL + "/",
        "Connection": "close",
    }


def _headers():
    return {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "application/json,text/html,*/*",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.7,en;q=0.6",
        "Referer": BASE_URL + "/",
        "Connection": "close",
    }


def _nydus_headers(referer=None):
    return {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.7,en;q=0.6",
        "Referer": referer or NYDUS_LIVE_URL,
        "Connection": "close",
    }


def _read_cache():
    return _read_json(CACHE_FILE, {})


def _write_cache(channels):
    _write_json(CACHE_FILE, {"timestamp": int(time.time()), "channels": channels})


def _read_json(path, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _write_json(path, data):
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except Exception as exc:
        log_utils.log("LiveTV lite JSON write failed for %s: %s" % (path, str(exc)), log_utils.LOGWARNING)


def _clean_title(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = " ".join(value.split())
    return value.strip()


def _normalize(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _sort_key(value):
    return _normalize(value)


def _add_folder(handle, label, params, is_folder=True):
    item = control.item(label, offscreen=True)
    item.setInfo("video", {"title": label, "plot": label, "mediatype": "video"})
    item.setArt({"icon": control.addonIcon(), "thumb": control.addonIcon()})
    if is_folder:
        item.setIsFolder(True)
    control.addItem(handle, _url(params), item, is_folder)


def _url(params):
    return "%s?%s" % (sys.argv[0], urlencode(params))


def _handle():
    return int(sys.argv[1]) if len(sys.argv) > 1 else -1


def _end(category, cache=False):
    handle = _handle()
    control.content(handle, "videos")
    control.plugincategory(handle, "%s / %s" % (control.addonName, category))
    control.endofdirectory(handle, succeeded=True, cacheToDisc=cache)
