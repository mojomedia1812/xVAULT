import html
import json
import os
import re
import sys
import time
from urllib.parse import urlencode

try:
    import requests
except Exception:
    requests = None

from resources.lib import control, log_utils
from resources.lib import linear_tv


BASE_URL = "https://www.2ix2.com"
POSTS_URL = BASE_URL + "/wp-json/wp/v2/posts"
CACHE_FILE = os.path.join(control.addonProfilePath, "linear-tv-lite-catalog.json")
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


def show_home():
    handle = _handle()
    _add_folder(handle, "Senderliste aktualisieren", {"action": "liveTVLiteRefresh"}, False)
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
        item.setArt({"icon": control.addonIcon(), "thumb": control.addonIcon()})
        control.addItem(handle, _url({"action": "liveTVLitePlay", "id": channel.get("id")}), item, False)
    _end(category["label"], cache=False)


def play(channel_id):
    channel = _channel_by_id(_catalog(), channel_id)
    if not channel:
        control.infoDialog("Sender nicht gefunden", icon="WARNING", time=3500)
        control.resolveUrl(_handle(), False, control.item("LiveTV lite", offscreen=True))
        return

    stream_url = channel.get("stream_url") or ""
    if not stream_url:
        control.infoDialog("Stream konnte nicht gelesen werden", icon="WARNING", time=3500)
        control.resolveUrl(_handle(), False, control.item(channel.get("name") or "LiveTV lite", offscreen=True))
        return
    status = _probe_stream(stream_url, channel.get("page_url"))
    if status and status >= 400:
        control.infoDialog("2ix2-Stream aktuell nicht erreichbar (HTTP %s)" % status, icon="WARNING", time=5000)
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
    item.setArt({"icon": control.addonIcon(), "thumb": control.addonIcon()})
    linear_tv._configure_stream(item, playback_url)
    item.setPath(playback_url)
    control.resolveUrl(_handle(), True, item)


def _catalog(refresh=False):
    cached = _read_cache()
    if not refresh and cached:
        timestamp = int(cached.get("timestamp") or 0)
        channels = cached.get("channels") or []
        if channels and time.time() - timestamp < CACHE_TTL:
            return channels

    channels = _load_channels()
    if channels:
        _write_cache(channels)
        return channels
    if cached and cached.get("channels"):
        control.infoDialog("LiveTV lite nutzt die gespeicherte Senderliste.", icon="WARNING", time=3500)
        return cached.get("channels") or []
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
    if not stream_url:
        return None

    post_id = str(post.get("id") or post.get("slug") or stream_url)
    return {
        "id": "%s:%s" % (category["slug"], post_id),
        "name": _clean_title(post.get("title", {}).get("rendered") or post.get("slug") or "LiveTV lite"),
        "category": category["label"],
        "category_slug": category["slug"],
        "page_url": post.get("link") or BASE_URL,
        "stream_url": stream_url,
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
        if match:
            return html.unescape(match.group(1)).strip()
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
    for channel in channels or []:
        if channel.get("id") == channel_id:
            return channel
    return None


def _category(slug):
    for category in CATEGORIES:
        if category.get("slug") == slug:
            return category
    return None


def _plot(channel):
    return "%s\n%s" % (channel.get("category") or "LiveTV lite", channel.get("page_url") or BASE_URL)


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


def _read_cache():
    try:
        if not os.path.exists(CACHE_FILE):
            return {}
        with open(CACHE_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _write_cache(channels):
    try:
        directory = os.path.dirname(CACHE_FILE)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        with open(CACHE_FILE, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"timestamp": int(time.time()), "channels": channels}, handle, ensure_ascii=False, indent=2)
    except Exception as exc:
        log_utils.log("LiveTV lite cache failed: %s" % str(exc), log_utils.LOGWARNING)


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
