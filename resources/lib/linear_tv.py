import json
import os
import re
import sys
import time
import uuid
from urllib.parse import urlencode

import xbmc

try:
    import requests
except Exception:
    requests = None

from resources.lib import control, log_utils


BASE_URLS = ("https://huhu.to", "https://www.huhu.to")
PING_URL = "https://www.vypn.net/api/app/ping"
CATALOG_PATH = "/mediaurl-catalog.json"
RESOLVE_PATH = "/mediaurl-resolve.json"
MEDIA_USER_AGENT = "MediaUrl/2"
CLIENT_VERSION = "3.1.0"
CATALOG_GROUPS = ("Germany", "GERMANY")
CATALOG_FILE = os.path.join(control.addonProfilePath, "linear-tv-catalog.json")
FAVORITES_FILE = os.path.join(control.addonProfilePath, "linear-tv-favorites.json")
SIGNATURE_TTL = 7 * 60
DEFAULT_CACHE_HOURS = 1
MAX_PAGES_PER_GROUP = 20

_signature_cache = {"value": "", "timestamp": 0}
_base_index = 0


CATEGORY_ORDER = (
    "Favoriten",
    "Suche",
    "Alle Sender",
    "Oeffentlich-rechtlich",
    "Private",
    "Nachrichten",
    "Sport",
    "Filme und Serien",
    "Doku und Wissen",
    "Kinder",
    "Musik",
    "Regional",
    "Events und Backup",
    "Sonstige",
)

CATEGORY_RULES = (
    ("Oeffentlich-rechtlich", (
        "ARD", "DAS ERSTE", "ZDF", "3SAT", "ARTE", "PHOENIX", "TAGESSCHAU",
        "ONE", "KIKA", "ALPHA", "DW ", "DEUTSCHE WELLE",
    )),
    ("Regional", (
        "WDR", "NDR", "MDR", "SWR", "BR ", "HR ", "RBB", "SR ", "RADIO BREMEN",
        "HAMBURG", "BERLIN", "BAYERN", "HESSEN", "SACHSEN", "THUERINGEN",
    )),
    ("Nachrichten", (
        "WELT", "NTV", "N-TV", "N24", "EURONEWS", "BILD", "CNN", "BBC NEWS",
        "SKY NEWS", "TAGESSCHAU", "PHOENIX",
    )),
    ("Sport", (
        "SPORT", "DAZN", "SKY BUNDESLIGA", "SKY SPORT", "EUROSPORT", "DYN",
        "MAGENTA", "TELEKOM SPORT", "FIGHT", "MOTORSPORT", "MOTOGP", "FORMEL",
        "FUSSBALL", "FOOTBALL", "TENNIS", "GOLF",
    )),
    ("Kinder", (
        "KIKA", "KINDER", "NICK", "NICKELODEON", "DISNEY", "CARTOON", "BOOMERANG",
        "BABY TV", "TOGGO", "SUPER RTL", "BOSS BABY",
    )),
    ("Doku und Wissen", (
        "DOKU", "DOKUMENTATION", "DISCOVERY", "NATIONAL", "NAT GEO", "PLANET",
        "HISTORY", "ANIMAL", "WISSEN", "SPIEGEL GESCHICHTE", "GEO",
    )),
    ("Musik", (
        "MTV", "DELUXE", "MUSIC", "MUSIK", "VH1", "SCHLAGER", "CLUB", "HITS",
        "RADIO", "JUKEBOX",
    )),
    ("Filme und Serien", (
        "SKY CINEMA", "CINEMA", "FILM", "MOVIE", "SERIE", "SERIES", "WARNER",
        "UNIVERSAL", "13TH STREET", "SYFY", "AXN", "TNT", "RTL CRIME",
        "RTL LIVING", "FOX", "KINOWELT", "NETFLIX", "AMAZON", "CINEDOME",
    )),
    ("Private", (
        "RTL", "SAT.1", "SAT1", "PRO7", "PRO 7", "KABEL", "VOX", "NITRO",
        "SIXX", "DMAX", "TELE 5", "RTLZWEI", "RTL 2",
    )),
    ("Events und Backup", (
        "BACKUP", "EVENT", "RAW", "LIVE DURING EVENTS", "SELECT", "OPTION",
    )),
)

_HIDDEN_TOKENS = ("BACKUP", "EVENT", "RAW", "LIVE DURING EVENTS", "TEST")


def show_home():
    if not _enabled():
        control.infoDialog("LiveTV ist in den Einstellungen deaktiviert.", icon="INFO")
        _end("LiveTV", cache=False)
        return

    channels = _catalog()
    if not channels:
        _end("LiveTV", cache=False)
        return

    handle = _handle()
    _add_folder(handle, "Senderliste aktualisieren", {"action": "liveTVRefresh"}, False)
    _add_folder(handle, "Favoriten", {"action": "liveTVFavorites"}, True, "Favoriten")
    _add_folder(handle, "Suche", {"action": "liveTVSearch"}, True, "Suche")
    _add_folder(handle, "Alle Sender", {"action": "liveTVCategory", "category": "Alle Sender"}, True, "Alle Sender")

    grouped = _group_channels(channels)
    for category in _sorted_categories(grouped):
        label = "%s (%d)" % (category, len(grouped[category]))
        _add_folder(handle, label, {"action": "liveTVCategory", "category": category}, True, category)

    _end("LiveTV", cache=False)


def refresh():
    channels = _catalog(force=True)
    control.infoDialog("LiveTV-Senderliste aktualisiert: %d Sender" % len(channels), icon="INFO", time=4000)
    xbmc.executebuiltin("Container.Refresh")
    _end("LiveTV", cache=False)


def show_category(category):
    channels = _catalog()
    if category and category != "Alle Sender":
        channels = [channel for channel in channels if channel.get("category") == category]
    _show_channels(channels, category or "LiveTV")


def show_search(query=None):
    if query is None:
        keyboard = control.keyboard("", "LiveTV suchen")
        keyboard.doModal()
        if not keyboard.isConfirmed():
            _end("Suche", cache=False)
            return
        query = keyboard.getText().strip()

    if not query:
        _end("Suche", cache=False)
        return

    words = [_normalize(part) for part in query.split() if _normalize(part)]
    channels = []
    for channel in _catalog():
        haystack = _normalize("%s %s" % (channel.get("name", ""), channel.get("category", "")))
        if all(word in haystack for word in words):
            channels.append(channel)
    _show_channels(channels, "Suche: %s" % query)


def show_favorites():
    favorites = _load_favorites()
    _show_channels(favorites, "Favoriten", favorites=True)


def add_favorite(channel_id):
    channel = _channel_by_id(_catalog(), channel_id)
    if not channel:
        control.infoDialog("Sender nicht gefunden", icon="WARNING")
        return
    favorites = _load_favorites()
    if not _channel_by_id(favorites, channel_id):
        favorites.append(_favorite_record(channel))
        _save_favorites(favorites)
    control.infoDialog("Favorit gespeichert", icon="INFO")


def remove_favorite(channel_id):
    favorites = [item for item in _load_favorites() if item.get("id") != channel_id]
    _save_favorites(favorites)
    control.infoDialog("Favorit entfernt", icon="INFO")
    xbmc.executebuiltin("Container.Refresh")


def play(channel_id):
    channel = _channel_by_id(_catalog(), channel_id) or _channel_by_id(_load_favorites(), channel_id)
    if not channel:
        control.infoDialog("Sender nicht gefunden", icon="WARNING", time=4000)
        control.resolveUrl(_handle(), False, control.item("LiveTV", offscreen=True))
        return

    stream_url = _resolve(channel.get("url"))
    if not stream_url:
        control.infoDialog("Stream konnte nicht aufgeloest werden", icon="WARNING", time=4000)
        control.resolveUrl(_handle(), False, control.item(channel.get("name") or "LiveTV", offscreen=True))
        return

    item = control.item(channel.get("name") or "LiveTV", offscreen=True)
    item.setProperty("IsPlayable", "true")
    item.setInfo("video", {
        "title": channel.get("name") or "LiveTV",
        "plot": _plot(channel),
        "mediatype": "video",
    })
    logo = channel.get("logo") or ""
    if logo:
        item.setArt({"thumb": logo, "icon": logo})
    _configure_stream(item, stream_url)
    item.setPath(stream_url)
    control.resolveUrl(_handle(), True, item)


def _show_channels(channels, title, favorites=False):
    handle = _handle()
    for channel in sorted(channels, key=lambda item: _sort_key(item.get("name"))):
        item = control.item(channel.get("name") or "LiveTV", offscreen=True)
        item.setProperty("IsPlayable", "true")
        item.setInfo("video", {"title": channel.get("name") or "LiveTV", "plot": _plot(channel)})
        logo = channel.get("logo") or ""
        if logo:
            item.setArt({"thumb": logo, "icon": logo})
        item.addContextMenuItems(_context_menu(channel, favorites))
        url = _url({"action": "liveTVPlay", "id": channel.get("id")})
        try:
            item.setPath(url)
        except Exception:
            pass
        control.addItem(handle, url, item, False)
    control.sortLabel(handle)
    _end(title, cache=False)


def _catalog(force=False):
    _ensure_profile()
    if not force:
        cached = _read_json(CATALOG_FILE, {})
        if _cache_valid(cached):
            return _visible_channels(cached.get("channels", []))

    channels = _download_catalog()
    if channels:
        _write_json(CATALOG_FILE, {"updated_at": int(time.time()), "channels": channels})
        return _visible_channels(channels)

    cached = _read_json(CATALOG_FILE, {})
    fallback = cached.get("channels", [])
    if fallback:
        control.infoDialog("LiveTV nutzt die gespeicherte Senderliste.", icon="WARNING", time=4000)
        return _visible_channels(fallback)

    control.infoDialog("LiveTV-Senderliste konnte nicht geladen werden.", icon="ERROR", time=5000)
    return []


def _download_catalog():
    if requests is None:
        log_utils.log("LiveTV catalog failed: requests module is not available", log_utils.LOGWARNING)
        return []

    progress = control.progressDialog
    progress.create(control.addonName, "LiveTV-Senderliste wird geladen")
    progress.update(0)
    try:
        merged = {}
        total_steps = len(CATALOG_GROUPS) * MAX_PAGES_PER_GROUP
        done_steps = 0
        for group in CATALOG_GROUPS:
            cursor = None
            for page in range(MAX_PAGES_PER_GROUP):
                if progress.iscanceled():
                    return []
                data = _catalog_page(group, cursor)
                batch = _parse_catalog_items(data.get("items", []))
                for channel in batch:
                    merged[channel["id"]] = channel
                done_steps += 1
                percent = min(99, int(done_steps * 100 / total_steps))
                progress.update(percent, "%d Sender gefunden" % len(merged))
                cursor = data.get("nextCursor")
                if not cursor:
                    break
        return list(merged.values())
    except Exception as exc:
        log_utils.log("LiveTV catalog failed: %s" % str(exc), log_utils.LOGWARNING)
        return []
    finally:
        try:
            progress.close()
        except Exception:
            pass


def _catalog_page(group, cursor, attempts=0):
    response = requests.post(
        _base_url() + CATALOG_PATH,
        json={
            "language": "en",
            "region": "US",
            "catalogId": "iptv",
            "id": "iptv",
            "adult": False,
            "search": "",
            "sort": "",
            "filter": {"group": group},
            "cursor": cursor,
            "clientVersion": CLIENT_VERSION,
        },
        headers=_media_headers(),
        timeout=30,
    )
    if response.status_code == 451:
        if attempts >= len(BASE_URLS):
            response.raise_for_status()
        _switch_base()
        return _catalog_page(group, cursor, attempts + 1)
    response.raise_for_status()
    return response.json()


def _parse_catalog_items(items):
    channels = []
    for item in items:
        if item.get("type") != "iptv":
            continue
        channel_id = (item.get("ids") or {}).get("id") or item.get("id")
        stream_page = item.get("url")
        if not channel_id or not stream_page:
            continue
        name = _clean_name(item.get("name") or item.get("title") or "LiveTV")
        logo = item.get("logo") or item.get("artwork") or ""
        channels.append({
            "id": str(channel_id),
            "name": name,
            "url": stream_page,
            "logo": logo,
            "group": item.get("group") or "Germany",
            "category": _category_for(name),
        })
    return channels


def _resolve(channel_url):
    if not channel_url or requests is None:
        return ""

    signature = _signature()
    if not signature:
        return ""

    for attempt in range(3):
        try:
            response = requests.post(
                _base_url() + RESOLVE_PATH,
                json={
                    "language": "en",
                    "region": "US",
                    "url": channel_url,
                    "clientVersion": CLIENT_VERSION,
                },
                headers=_media_headers(signature),
                timeout=30,
            )
            if response.status_code == 451:
                _switch_base()
                continue
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                return data[0].get("url") or ""
            if isinstance(data, dict):
                return data.get("url") or data.get("streamUrl") or ""
        except Exception as exc:
            log_utils.log("LiveTV resolve attempt %d failed: %s" % (attempt + 1, str(exc)), log_utils.LOGWARNING)
            if attempt == 0:
                signature = _signature(force=True)
    return ""


def _signature(force=False):
    now = time.time()
    if not force and _signature_cache["value"] and (now - _signature_cache["timestamp"]) < SIGNATURE_TTL:
        return _signature_cache["value"]

    if requests is None:
        return ""

    timestamp = int(time.time() * 1000)
    try:
        response = requests.post(
            PING_URL,
            json={
                "reason": "app-focus",
                "locale": "en",
                "theme": "dark",
                "metadata": {
                    "device": {"type": "desktop", "uniqueId": str(uuid.uuid4())},
                    "os": {"name": "win32", "version": "Windows 10", "abis": ["x64"], "host": "Kodi"},
                    "app": {"platform": "electron"},
                    "version": {"package": "net.vypn.app", "binary": CLIENT_VERSION, "js": CLIENT_VERSION},
                },
                "appFocusTime": 0,
                "playerActive": False,
                "playDuration": 0,
                "devMode": False,
                "hasAddon": True,
                "castConnected": False,
                "package": "net.vypn.app",
                "version": CLIENT_VERSION,
                "process": "app",
                "firstAppStart": timestamp,
                "lastAppStart": timestamp,
                "ipLocation": None,
                "adblockEnabled": True,
                "proxy": {"supported": ["ss"], "engine": "Mu", "enabled": False, "autoServer": True},
                "iap": {"supported": False},
            },
            headers={
                "accept": "*/*",
                "user-agent": _browser_user_agent(),
                "Accept-Encoding": "gzip, deflate",
                "Connection": "close",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        signature = data.get("addonSig") or data.get("sig") or data.get("token") or ""
        if signature:
            _signature_cache["value"] = signature
            _signature_cache["timestamp"] = time.time()
        return signature
    except Exception as exc:
        log_utils.log("LiveTV signature failed: %s" % str(exc), log_utils.LOGWARNING)
        return ""


def _media_headers(signature=""):
    headers = {
        "content-type": "application/json; charset=utf-8",
        "user-agent": MEDIA_USER_AGENT,
        "accept": "*/*",
        "Accept-Language": "en",
        "Connection": "close",
    }
    if signature:
        headers["mediaurl-signature"] = signature
    return headers


def _configure_stream(item, stream_url):
    if ".m3u8" not in stream_url.lower() or control.getSetting("livetv.inputstream", "true") == "false":
        return
    item.setProperty("inputstream", "inputstream.adaptive")
    if int(control.getKodiVersion()) < 21:
        item.setProperty("inputstream.adaptive.manifest_type", "hls")
    item.setMimeType("application/vnd.apple.mpegurl")
    item.setContentLookup(False)


def _group_channels(channels):
    grouped = {}
    for channel in channels:
        grouped.setdefault(channel.get("category") or "Sonstige", []).append(channel)
    return grouped


def _sorted_categories(grouped):
    known = [category for category in CATEGORY_ORDER if category in grouped and category not in ("Favoriten", "Suche", "Alle Sender")]
    unknown = sorted([category for category in grouped if category not in known], key=_sort_key)
    return known + unknown


def _category_for(name):
    upper = " %s " % (name or "").upper()
    for category, patterns in CATEGORY_RULES:
        if any(pattern in upper for pattern in patterns):
            return category
    return "Sonstige"


def _visible_channels(channels):
    show_special = control.getSetting("livetv.show.special", "true") != "false"
    result = []
    for channel in channels:
        if not show_special and any(token in (channel.get("name") or "").upper() for token in _HIDDEN_TOKENS):
            continue
        result.append(channel)
    return result


def _context_menu(channel, favorite_context=False):
    if favorite_context:
        return [("Aus Favoriten entfernen", "RunPlugin(%s)" % _url({"action": "liveTVFavoriteRemove", "id": channel.get("id")}))]
    favorites = _load_favorites()
    if _channel_by_id(favorites, channel.get("id")):
        label = "Aus Favoriten entfernen"
        action = "liveTVFavoriteRemove"
    else:
        label = "Zu Favoriten hinzufuegen"
        action = "liveTVFavoriteAdd"
    return [(label, "RunPlugin(%s)" % _url({"action": action, "id": channel.get("id")}))]


def _add_folder(handle, label, params, is_folder, plot=""):
    item = control.item(label, offscreen=True)
    if is_folder:
        item.setIsFolder(True)
        item.setInfo("video", {"title": label, "plot": plot or label})
    else:
        item.setProperty("IsPlayable", "false")
    control.addItem(handle, _url(params), item, is_folder)


def _plot(channel):
    return "%s[CR]%s" % (channel.get("category") or "LiveTV", channel.get("group") or "Germany")


def _favorite_record(channel):
    return {
        "id": channel.get("id"),
        "name": channel.get("name"),
        "url": channel.get("url"),
        "logo": channel.get("logo") or "",
        "group": channel.get("group") or "Germany",
        "category": channel.get("category") or "Sonstige",
    }


def _load_favorites():
    data = _read_json(FAVORITES_FILE, [])
    return data if isinstance(data, list) else []


def _save_favorites(favorites):
    _ensure_profile()
    _write_json(FAVORITES_FILE, favorites)


def _channel_by_id(channels, channel_id):
    channel_id = str(channel_id or "")
    for channel in channels:
        if str(channel.get("id") or "") == channel_id:
            return channel
    return None


def _cache_valid(data):
    if not isinstance(data, dict) or not data.get("channels"):
        return False
    try:
        hours = int(control.getSetting("livetv.cache.hours", str(DEFAULT_CACHE_HOURS)))
    except Exception:
        hours = DEFAULT_CACHE_HOURS
    ttl = max(1, hours) * 3600
    return time.time() - int(data.get("updated_at") or 0) < ttl


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)


def _ensure_profile():
    if not os.path.exists(control.addonProfilePath):
        os.makedirs(control.addonProfilePath)


def _clean_name(name):
    text = re.sub(r"\s+", " ", name or "").strip()
    text = re.sub(r"\s*\|([A-Z])$", r" [\1]", text)
    return text


def _normalize(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _sort_key(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _browser_user_agent():
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def _base_url():
    return BASE_URLS[_base_index % len(BASE_URLS)]


def _switch_base():
    global _base_index
    _base_index += 1


def _url(params):
    return "%s?%s" % (sys.argv[0], urlencode(params))


def _handle():
    return int(sys.argv[1]) if len(sys.argv) > 1 else -1


def _end(title, cache=False):
    handle = _handle()
    control.content(handle, "videos")
    control.plugincategory(handle, "%s / %s" % (control.addonName, title))
    control.endofdirectory(handle, succeeded=True, cacheToDisc=cache)


def _enabled():
    return control.getSetting("livetv.enabled", "true") != "false"
