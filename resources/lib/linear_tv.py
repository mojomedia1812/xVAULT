import calendar
import concurrent.futures
import gzip
import io
import json
import os
import re
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import urlencode, urljoin

import xbmc
import xbmcaddon

try:
    import requests
except Exception:
    requests = None

from resources.lib import control, log_utils


BASE_URLS = ("https://huhu.to", "https://www.huhu.to")
PING_URL = "https://www.vypn.net/api/app/ping"
CATALOG_PATH = "/mediaurl-catalog.json"
RESOLVE_PATH = "/mediaurl-resolve.json"
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz"
LOGOS_URL = "https://iptv-org.github.io/api/logos.json"
MEDIA_USER_AGENT = "MediaUrl/2"
CLIENT_VERSION = "3.1.0"
CATALOG_GROUPS = ("Germany", "GERMANY")
CATALOG_FILE = os.path.join(control.addonProfilePath, "linear-tv-catalog.json")
FAVORITES_FILE = os.path.join(control.addonProfilePath, "linear-tv-favorites.json")
EPG_FILE = os.path.join(control.addonProfilePath, "linear-tv-epg.json")
LOGOS_FILE = os.path.join(control.addonProfilePath, "linear-tv-logos.json")
HEALTH_FILE = os.path.join(control.addonProfilePath, "linear-tv-health-session.json")
PVR_PLAYLIST_FILE = os.path.join(control.addonProfilePath, "xvault-livetv.m3u8")
PVR_EPG_FILE = os.path.join(control.addonProfilePath, "xvault-livetv.xml")
SIGNATURE_TTL = 7 * 60
DEFAULT_CACHE_HOURS = 1
DEFAULT_EPG_CACHE_HOURS = 6
EPG_LOOKAHEAD_HOURS = 24
EPG_LOOKBEHIND_HOURS = 2
LOGOS_TTL = 14 * 24 * 3600
MAX_PAGES_PER_GROUP = 20
DEFAULT_BUFFER_MB = 0
MAX_BUFFER_MB = 200
HLS_PREFLIGHT_SEGMENTS = 6
HLS_PREFLIGHT_MIN_GOOD = 2
HLS_PREFLIGHT_RECHECK_DELAY = 2.5
HLS_PREFLIGHT_CONFIRM_ROUNDS = 2
HLS_FALLBACK_LIMIT = 6
HLS_PREFLIGHT_FATAL_STATUSES = (404, 410, 451)
HLS_PREFLIGHT_FATAL_MARKERS = ("dns_error", "connection_error", "network_error")
HEALTH_CHECK_TIMEOUT = 8
HEALTH_SEGMENT_LIMIT = 2
HEALTH_CHECK_WORKERS = 8
PLAYBACK_ENGINE_AUTO = 0
PLAYBACK_ENGINE_NATIVE = 1
PLAYBACK_ENGINE_FFMPEG_DIRECT = 2
PLAYBACK_ENGINE_ADAPTIVE = 3

_signature_cache = {"value": "", "timestamp": 0}
_epg_memory_cache = {"data": None, "mtime": 0}
_logo_memory_cache = {"data": None, "mtime": 0}
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

SPORT_CATEGORY_OVERRIDES = (
    "FC BAYERN",
    "BAYERN MUENCHEN",
    "BAYERN MÜNCHEN",
    "BAYERN MUNICH",
)

_HIDDEN_TOKENS = ("BACKUP", "EVENT", "RAW", "LIVE DURING EVENTS", "TEST")

_XMLTV_TIME_RE = re.compile(r"^(\d{14})(?:\s*([+-])(\d{2})(\d{2}))?")
_EPG_DROP_RE = re.compile(
    r"\b(HD|FHD|UHD|SD|RAW|BACKUP|EVENT|EVENTS|OPTION|SELECT|NUR|STREAMING|STREAM)\b",
    re.IGNORECASE,
)
_EPG_ALIAS_REPLACEMENTS = (
    ("rtl2", "rtlzwei"),
    ("rtlzwei", "rtl2"),
    ("pro7", "prosieben"),
    ("prosieben", "pro7"),
    ("kabel1", "kabeleins"),
    ("kabeleins", "kabel1"),
    ("13thstreetuniversal", "13thstreet"),
    ("13thstreet", "13thstreetuniversal"),
    ("rtlsuper", "superrtl"),
    ("superrtl", "rtlsuper"),
)


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
    _add_folder(handle, "Senderliste auf Funktion prüfen", {"action": "liveTVHealthCheck"}, True, "Prüft alle aktuell sichtbaren Sender und blendet nicht erreichbare Sender bis zum nächsten xVAULT-Hauptstart aus.")
    _add_folder(handle, "M3U/XMLTV-Dateien erstellen", {"action": "liveTVPvrFiles"}, False, "Erzeugt nur die lokalen M3U- und XMLTV-Dateien, ohne IPTV Simple automatisch zu konfigurieren.")
    _add_folder(handle, "Kodi-TV Integration aktualisieren", {"action": "liveTVPvrExport"}, False, "Erzeugt lokale M3U- und XMLTV-Dateien und richtet IPTV Simple automatisch ein, wenn das PVR-Modul verfügbar ist.")
    _add_folder(handle, "Favoriten", {"action": "liveTVFavorites"}, True, "Favoriten")
    _add_folder(handle, "Suche", {"action": "liveTVSearch"}, True, "Suche")
    _add_folder(handle, "Alle Sender", {"action": "liveTVCategory", "category": "Alle Sender"}, True, "Alle Sender")

    grouped = _group_channels(channels)
    for category in _sorted_categories(grouped):
        label = "%s (%d)" % (category, len(grouped[category]))
        _add_folder(handle, label, {"action": "liveTVCategory", "category": category}, True, category)

    _end("LiveTV", cache=False)


def refresh():
    clear_session_health()
    channels = _catalog(force=True)
    control.infoDialog("LiveTV-Senderliste aktualisiert: %d Sender" % len(channels), icon="INFO", time=4000)
    xbmc.executebuiltin("Container.Refresh")
    _end("LiveTV", cache=False)


def check_channel_health():
    if requests is None:
        control.infoDialog("Streamprüfung nicht möglich: requests fehlt.", icon="ERROR", time=5000)
        _end("LiveTV", cache=False)
        return

    if not _confirm_health_check():
        control.infoDialog("LiveTV-Senderprüfung abgebrochen.", icon="INFO", time=3000)
        _end("LiveTV", cache=False)
        return

    clear_session_health()
    channels = _catalog()
    if not channels:
        control.infoDialog("Keine LiveTV-Sender zum Prüfen gefunden.", icon="WARNING", time=4000)
        _end("LiveTV", cache=False)
        return

    total = len(channels)
    blocked = {}
    reachable = 0
    checked = 0
    cancelled = False
    progress = control.progressDialog
    progress.create(control.addonName, "LiveTV-Sender werden geprüft")
    progress.update(0, "Vorbereitung")

    try:
        _signature(force=True)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=HEALTH_CHECK_WORKERS)
        futures = {}
        try:
            for channel in channels:
                futures[executor.submit(_check_channel_reachable, channel)] = channel

            for future in concurrent.futures.as_completed(futures):
                if progress.iscanceled():
                    cancelled = True
                    break
                channel = futures[future]
                name = channel.get("name") or "LiveTV"
                checked += 1
                percent = min(99, int(checked * 100 / total))
                progress.update(
                    percent,
                    "Geprüft %d/%d: %s" % (checked, total, _truncate(name, 60)),
                )
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"ok": False, "reason": _truncate(str(exc), 120)}
                if result.get("ok"):
                    reachable += 1
                else:
                    blocked[str(channel.get("id") or channel.get("url") or name)] = {
                        "name": name,
                        "reason": result.get("reason") or "nicht erreichbar",
                        "checked_at": int(time.time()),
                    }
        finally:
            for future in futures:
                if not future.done():
                    future.cancel()
            try:
                executor.shutdown(wait=not cancelled, cancel_futures=True)
            except TypeError:
                executor.shutdown(wait=not cancelled)

        _save_health_state(blocked, checked, reachable, cancelled)
    finally:
        try:
            progress.close()
        except Exception:
            pass

    hidden = len(blocked)
    if cancelled:
        message = "Prüfung abgebrochen: %d geprüft, %d funktionieren, %d temporär gesperrt." % (
            checked,
            reachable,
            hidden,
        )
        icon = "WARNING"
    else:
        message = "Prüfung abgeschlossen: %d geprüft, %d funktionieren, %d temporär gesperrt." % (
            checked,
            reachable,
            hidden,
        )
        icon = "INFO"
    try:
        control.dialog.ok("LiveTV-Senderprüfung", message)
    except Exception:
        control.infoDialog(message, icon=icon, time=6000)
    xbmc.executebuiltin("Container.Refresh")
    _end("LiveTV", cache=False)


def clear_session_health():
    try:
        if os.path.exists(HEALTH_FILE):
            os.remove(HEALTH_FILE)
    except Exception as exc:
        log_utils.log("LiveTV health state reset failed: %s" % str(exc), log_utils.LOGWARNING)


def _confirm_health_check():
    message = (
        "Die Prüfung der kompletten LiveTV-Senderliste kann je nach System bis zu 30 Minuten dauern. "
        "Für schwache Systeme wird der Vorgang nicht empfohlen. Jetzt trotzdem starten?"
    )
    try:
        return bool(control.dialog.yesno("LiveTV-Senderliste prüfen", message))
    except Exception as exc:
        log_utils.log("LiveTV health confirmation failed: %s" % str(exc), log_utils.LOGWARNING)
        return True


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
    control.infoDialog("TV-Favorit gespeichert", icon="INFO")


def remove_favorite(channel_id):
    favorites = [item for item in _load_favorites() if item.get("id") != channel_id]
    _save_favorites(favorites)
    control.infoDialog("TV-Favorit entfernt", icon="INFO")
    xbmc.executebuiltin("Container.Refresh")


def play(channel_id, pvr=False):
    catalog = _catalog()
    channel = _channel_by_id(catalog, channel_id) or _channel_by_id(_load_favorites(), channel_id)
    if not channel:
        control.infoDialog("Sender nicht gefunden", icon="WARNING", time=4000)
        control.resolveUrl(_handle(), False, control.item("LiveTV", offscreen=True))
        return

    programmes = _programme_pair(channel, refresh=True)
    if not pvr:
        _show_programme_before_play(channel, programmes[0])

    stream_url, playback_channel = _select_live_stream(channel, catalog)
    if not stream_url:
        control.infoDialog("Stream konnte nicht aufgelöst werden", icon="WARNING", time=4000)
        control.resolveUrl(_handle(), False, control.item(channel.get("name") or "LiveTV", offscreen=True))
        return

    if playback_channel.get("id") != channel.get("id"):
        control.infoDialog("Nutze Ersatzstream: %s" % (playback_channel.get("name") or "LiveTV"), icon="INFO", time=3500)

    item = control.item(playback_channel.get("name") or "LiveTV", offscreen=True)
    item.setProperty("IsPlayable", "true")
    item.setInfo("video", {
        "title": playback_channel.get("name") or "LiveTV",
        "plot": _plot(playback_channel, programmes),
        "plotoutline": _plot(playback_channel, programmes),
        "mediatype": "video",
    })
    _set_channel_art(item, playback_channel)
    _configure_stream(item, stream_url)
    item.setPath(stream_url)
    control.resolveUrl(_handle(), True, item)


def export_pvr_files(interactive=False, configure=True):
    playlist_path = export_pvr_playlist()
    epg_path = export_pvr_epg()
    pvr_ready = _configure_iptv_simple(playlist_path, epg_path, interactive=interactive) if configure else False
    if interactive:
        if configure:
            pvr_text = (
                "IPTV Simple wurde auf xVAULT konfiguriert."
                if pvr_ready else
                "IPTV Simple wurde nicht verändert. Kodi kann die erzeugten Dateien trotzdem manuell verwenden."
            )
            title = "Kodi-TV Integration"
        else:
            pvr_text = "IPTV Simple wurde nicht verändert. Die Dateien können manuell in IPTV Simple, IPTV Merge oder einer anderen PVR-Lösung verwendet werden."
            title = "M3U/XMLTV-Dateien"
        control.dialog.ok(
            title,
            "Die lokalen PVR-Dateien stehen bereit:\n\n"
            "M3U:\n%s\n\n"
            "XMLTV:\n%s\n\n"
            "%s\n\n"
            "IPTV Merge kann xVAULT außerdem über die mitgelieferte .iptv_merge-Datei als Add-on-Quelle erkennen."
            % (playlist_path, epg_path, pvr_text),
        )
    return playlist_path, epg_path, pvr_ready


def export_pvr_files_only(interactive=True):
    return export_pvr_files(interactive=interactive, configure=False)


def configure_pvr_integration():
    export_pvr_files(interactive=True)


def export_pvr_playlist(output=None):
    output_path = _pvr_output_path(output, PVR_PLAYLIST_FILE)
    epg = _epg_data(refresh=True) if _epg_enabled() else {}
    channels = _pvr_channels(epg)
    changed = _write_text(output_path, _pvr_playlist(channels, epg))
    action = "exported" if changed else "unchanged"
    log_utils.log("LiveTV PVR playlist %s: %s (%d Sender)" % (action, output_path, len(channels)), log_utils.LOGINFO)
    return output_path


def export_pvr_epg(output=None):
    output_path = _pvr_output_path(output, PVR_EPG_FILE)
    epg = _epg_data(refresh=True) if _epg_enabled() else {}
    channels = _pvr_channels(epg)
    programme_count, changed = _write_pvr_epg(output_path, channels, epg)
    action = "exported" if changed else "unchanged"
    log_utils.log("LiveTV PVR EPG %s: %s (%d Programme)" % (action, output_path, programme_count), log_utils.LOGINFO)
    return output_path


def _configure_iptv_simple(playlist_path, epg_path, interactive=True):
    if not _ensure_pvr_dependencies(interactive=interactive):
        return False

    try:
        addon = xbmcaddon.Addon("pvr.iptvsimple")
        profile = control.translatePath(addon.getAddonInfo("profile"))
        _write_iptv_simple_instance(profile, playlist_path, epg_path)
        _set_addon_settings(addon, playlist_path, epg_path)
        _enable_kodi_addon("pvr.iptvsimple")
        xbmc.executebuiltin("UpdateLocalAddons")
        log_utils.log("LiveTV PVR client configured for IPTV Simple", log_utils.LOGINFO)
        return True
    except Exception as exc:
        log_utils.log("LiveTV PVR client configuration failed: %s" % str(exc), log_utils.LOGWARNING)
        return False


def _ensure_pvr_dependencies(interactive=True):
    try:
        _log_optional_inputstream_state()
        return _ensure_iptv_simple(interactive=interactive)
    except Exception as exc:
        log_utils.log("LiveTV PVR dependency check failed: %s" % str(exc), log_utils.LOGWARNING)
        return _addon_available("pvr.iptvsimple")


def _log_optional_inputstream_state():
    addon_ids = (
        "inputstream.adaptive",
        "inputstream.ffmpegdirect",
        "inputstream.rtmp",
    )
    states = []
    for addon_id in addon_ids:
        state = "enabled" if _addon_enabled(addon_id) else "missing-or-disabled"
        states.append("%s=%s" % (addon_id, state))
    log_utils.log("LiveTV optional inputstream state: %s" % ", ".join(states), log_utils.LOGINFO)


def _ensure_iptv_simple(interactive=True):
    addon_id = "pvr.iptvsimple"
    details = _addon_details(addon_id)
    if not details:
        if not interactive or not _confirm_pvr_change(
            "IPTV Simple ist nicht installiert.",
            "Soll Kodi den IPTV Simple Client jetzt installieren und aktivieren?",
            "Das passiert nur für die ausgewählte Kodi-TV Integration.",
        ):
            log_utils.log("LiveTV PVR setup skipped: IPTV Simple is not installed", log_utils.LOGINFO)
            return False
        try:
            from resources.lib import dependencies
            if not dependencies.install_addon(addon_id):
                return False
        except Exception as exc:
            log_utils.log("LiveTV PVR install failed: %s" % str(exc), log_utils.LOGWARNING)
            return False
        details = _addon_details(addon_id)

    if details and not bool(details.get("enabled")):
        if not interactive or not _confirm_pvr_change(
            "IPTV Simple ist installiert, aber deaktiviert.",
            "Soll xVAULT den IPTV Simple Client jetzt aktivieren?",
            "Eine bewusst deaktivierte PVR-Einstellung wird ohne Zustimmung nicht geändert.",
        ):
            log_utils.log("LiveTV PVR setup skipped: IPTV Simple is disabled", log_utils.LOGINFO)
            return False
        _enable_kodi_addon(addon_id)
        try:
            xbmc.Monitor().waitForAbort(1)
        except Exception:
            pass

    return _addon_enabled(addon_id) or _addon_available(addon_id)


def _confirm_pvr_change(line1, line2, line3):
    try:
        return control.yesnoDialog(
            line1,
            line2,
            line3,
            heading="Kodi-TV Integration",
            nolabel="Abbrechen",
            yeslabel="Fortfahren",
        )
    except Exception:
        return False


def _write_iptv_simple_instance(profile, playlist_path, epg_path):
    if not profile:
        return
    if not os.path.exists(profile):
        os.makedirs(profile)

    instance_path = _iptv_simple_instance_path(profile, playlist_path)
    content = (
        '<settings version="1">\n'
        '  <setting id="kodi_addon_instance_name">xVAULT LiveTV</setting>\n'
        '  <setting id="m3uPathType">0</setting>\n'
        '  <setting id="m3uPath">%s</setting>\n'
        '  <setting id="m3uUrl"></setting>\n'
        '  <setting id="m3uCache">false</setting>\n'
        '  <setting id="startNum">1</setting>\n'
        '  <setting id="numberByOrder">false</setting>\n'
        '  <setting id="m3uRefreshMode">1</setting>\n'
        '  <setting id="m3uRefreshIntervalMins">60</setting>\n'
        '  <setting id="m3uRefreshHour">4</setting>\n'
        '  <setting id="epgPathType">0</setting>\n'
        '  <setting id="epgPath">%s</setting>\n'
        '  <setting id="epgUrl"></setting>\n'
        '  <setting id="epgCache">false</setting>\n'
        '  <setting id="epgTimeShift">0</setting>\n'
        '  <setting id="epgTSOverride">false</setting>\n'
        '  <setting id="epgIgnoreCaseForChannelIds">true</setting>\n'
        '  <setting id="logoPathType">1</setting>\n'
        '  <setting id="logoPath"></setting>\n'
        '  <setting id="logoBaseUrl"></setting>\n'
        '  <setting id="useLogosLocalPathOnly">false</setting>\n'
        '  <setting id="logoFromEpg">1</setting>\n'
        '  <setting id="tvGroupMode">0</setting>\n'
        '  <setting id="radioGroupMode">0</setting>\n'
        '  <setting id="defaultProviderName">xVAULT</setting>\n'
        '  <setting id="enableProviderMappings">false</setting>\n'
        '  <setting id="connectioncheckinterval">10</setting>\n'
        '  <setting id="connectionchecktimeout">20</setting>\n'
        '</settings>\n'
    ) % (_xml_escape(playlist_path), _xml_escape(epg_path))
    _write_text(instance_path, content)


def _iptv_simple_instance_path(profile, playlist_path):
    marker = "xVAULT LiveTV"
    for name in os.listdir(profile):
        if not name.startswith("instance-settings-") or not name.endswith(".xml"):
            continue
        path = os.path.join(profile, name)
        try:
            content = open(path, "r", encoding="utf-8").read()
            if marker in content or playlist_path in content:
                return path
        except Exception:
            continue
    return os.path.join(profile, "instance-settings-1.xml")


def _set_addon_settings(addon, playlist_path, epg_path):
    settings = {
        "m3uPathType": "0",
        "m3uPath": playlist_path,
        "m3uUrl": "",
        "m3uCache": "false",
        "m3uRefreshMode": "1",
        "m3uRefreshIntervalMins": "60",
        "epgPathType": "0",
        "epgPath": epg_path,
        "epgUrl": "",
        "epgCache": "false",
        "defaultProviderName": "xVAULT",
    }
    for key, value in settings.items():
        try:
            addon.setSetting(key, value)
        except Exception:
            pass


def _enable_kodi_addon(addon_id):
    try:
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Addons.SetAddonEnabled",
            "params": {"addonid": addon_id, "enabled": True},
        })
        xbmc.executeJSONRPC(payload)
    except Exception:
        pass


def _addon_details(addon_id):
    try:
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Addons.GetAddonDetails",
            "params": {
                "addonid": addon_id,
                "properties": ["enabled", "version"],
            },
        })
        response = json.loads(xbmc.executeJSONRPC(payload) or "{}")
        return response.get("result", {}).get("addon")
    except Exception:
        return None


def _addon_enabled(addon_id):
    details = _addon_details(addon_id)
    return bool(details and details.get("enabled"))


def _addon_available(addon_id):
    try:
        return bool(xbmc.getCondVisibility("System.HasAddon(%s)" % addon_id))
    except Exception:
        return False


def _pvr_channels(epg=None):
    channels = _catalog()
    if epg:
        channels = _enrich_channel_logos(channels, epg)
    return sorted(channels, key=lambda item: _sort_key(item.get("name")))


def _pvr_playlist(channels, epg=None):
    lines = ["#EXTM3U"]
    for index, channel in enumerate(channels, 1):
        name = channel.get("name") or "LiveTV"
        logo = _channel_logo(channel, epg) or channel.get("logo") or ""
        group = channel.get("category") or "LiveTV"
        lines.append(
            '#EXTINF:-1 tvg-id="%s" tvg-chno="%d" tvg-name="%s" tvg-logo="%s" group-title="%s",%s'
            % (
                _m3u_attr(_pvr_channel_id(channel)),
                index,
                _m3u_attr(name),
                _m3u_attr(logo),
                _m3u_attr(group),
                _m3u_label(name),
            )
        )
        lines.append(_pvr_play_url(channel))
    return "\n".join(lines) + "\n"


def _write_pvr_epg(output_path, channels, epg):
    root = ET.Element("tv", {
        "generator-info-name": "xVAULT",
        "generator-info-url": "plugin://%s" % control.addonId,
    })
    programme_count = 0

    for channel in channels:
        channel_id = _pvr_channel_id(channel)
        channel_elem = ET.SubElement(root, "channel", {"id": channel_id})
        display_name = ET.SubElement(channel_elem, "display-name")
        display_name.text = _xml_text(channel.get("name") or "LiveTV")
        logo = _channel_logo(channel, epg)
        if logo:
            ET.SubElement(channel_elem, "icon", {"src": logo})

    for channel in channels:
        source_id = _epg_channel_id(channel, epg) if epg else ""
        if not source_id:
            continue
        channel_id = _pvr_channel_id(channel)
        for programme in epg.get("programmes", {}).get(source_id, []):
            start = int(programme.get("start") or 0)
            stop = int(programme.get("stop") or 0)
            if not start or not stop:
                continue
            programme_elem = ET.SubElement(root, "programme", {
                "start": _xmltv_local_time(start),
                "stop": _xmltv_local_time(stop),
                "channel": channel_id,
            })
            title = ET.SubElement(programme_elem, "title")
            title.text = _xml_text(programme.get("title") or "Unbekannte Sendung")
            subtitle = programme.get("subtitle") or ""
            if subtitle:
                sub_title = ET.SubElement(programme_elem, "sub-title")
                sub_title.text = _xml_text(subtitle)
            desc = programme.get("desc") or ""
            if desc:
                desc_elem = ET.SubElement(programme_elem, "desc")
                desc_elem.text = _xml_text(desc)
            programme_count += 1

    xml_data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    changed = _write_bytes(output_path, xml_data)
    return programme_count, changed


def _pvr_play_url(channel):
    return "plugin://%s/?%s" % (
        control.addonId,
        urlencode({"action": "liveTVPlay", "id": channel.get("id"), "pvr": "1"}),
    )


def _pvr_channel_id(channel):
    raw = str(channel.get("id") or _normalize(channel.get("name")) or uuid.uuid5(uuid.NAMESPACE_URL, channel.get("name") or "livetv"))
    safe = re.sub(r"[^A-Za-z0-9_.:-]+", "_", raw).strip("._")
    return "xvault.%s" % (safe or "livetv")


def _m3u_attr(value):
    return re.sub(r"[\r\n]+", " ", str(value or "")).replace('"', "'").strip()


def _m3u_label(value):
    return re.sub(r"[\r\n]+", " ", str(value or "LiveTV")).strip()


def _xml_text(value):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or ""))


def _xml_escape(value):
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _xmltv_local_time(timestamp):
    return time.strftime("%Y%m%d%H%M%S %z", time.localtime(int(timestamp)))


def _pvr_output_path(output, default_path):
    _ensure_profile()
    path = output or default_path
    if path.startswith("special://"):
        path = control.translatePath(path)
    return path


def _write_text(path, content):
    return _write_bytes(path, content.encode("utf-8"))


def _write_bytes(path, content):
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent)
    try:
        if os.path.exists(path):
            with open(path, "rb") as handle:
                if handle.read() == content:
                    return False
    except Exception:
        pass
    with open(path, "wb") as handle:
        handle.write(content)
    return True


def _show_channels(channels, title, favorites=False):
    handle = _handle()
    epg = _epg_data(refresh=True) if _epg_enabled() else {}
    channels = _enrich_channel_logos(channels, epg)
    _add_folder(handle, "Senderliste auf Funktion prüfen", {"action": "liveTVHealthCheck"}, True, "Prüft alle aktuell sichtbaren Sender und blendet nicht erreichbare Sender bis zum nächsten xVAULT-Hauptstart aus.")
    for channel in sorted(channels, key=lambda item: _sort_key(item.get("name"))):
        programmes = _programme_pair(channel, epg=epg)
        plot = _plot(channel, programmes, include_empty_epg=_epg_enabled())
        item = control.item(channel.get("name") or "LiveTV", offscreen=True)
        item.setProperty("IsPlayable", "true")
        item.setInfo("video", {
            "title": channel.get("name") or "LiveTV",
            "plot": plot,
            "plotoutline": plot,
            "mediatype": "video",
        })
        _set_channel_art(item, channel, epg)
        item.addContextMenuItems(_context_menu(channel, favorites), True)
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
            return _visible_channels(_apply_current_categories(cached.get("channels", [])))

    channels = _download_catalog()
    if channels:
        channels = _apply_current_categories(channels)
        _write_json(CATALOG_FILE, {"updated_at": int(time.time()), "channels": channels})
        return _visible_channels(channels)

    cached = _read_json(CATALOG_FILE, {})
    fallback = _apply_current_categories(cached.get("channels", []))
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
        logo = _logo_value(item.get("logo") or item.get("artwork"))
        channels.append({
            "id": str(channel_id),
            "name": name,
            "url": stream_page,
            "logo": logo,
            "group": item.get("group") or "Germany",
            "category": _category_for(name),
        })
    return channels


def _resolve(channel_url, force_signature=False):
    if not channel_url or requests is None:
        return ""

    signature = _signature(force=force_signature)
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


def _check_channel_reachable(channel):
    stream_url = _resolve(channel.get("url"))
    if not stream_url:
        stream_url = _resolve(channel.get("url"), force_signature=True)
    if not stream_url:
        return {"ok": False, "reason": "Resolve fehlgeschlagen"}
    return _health_stream_reachable(stream_url)


def _health_stream_reachable(stream_url):
    if ".m3u8" not in (stream_url or "").lower():
        try:
            response = requests.get(
                stream_url,
                headers=_hls_probe_headers(range_request=True),
                timeout=HEALTH_CHECK_TIMEOUT,
                stream=True,
            )
            try:
                status = int(response.status_code)
            finally:
                response.close()
            return {"ok": _hls_status_ok(status), "reason": "HTTP %s" % status}
        except Exception as exc:
            return {"ok": False, "reason": _truncate(str(exc), 120)}

    try:
        segment_urls = _hls_probe_segments(stream_url, timeout=HEALTH_CHECK_TIMEOUT)
        if not segment_urls:
            return {"ok": True, "reason": "HLS-Segmente nicht prüfbar"}
        sample = segment_urls[-HEALTH_SEGMENT_LIMIT:]
        statuses = [_probe_segment_status_safe(segment_url, timeout=HEALTH_CHECK_TIMEOUT) for segment_url in sample]
        good = [status for status in statuses if _hls_status_ok(status)]
        latest = statuses[-1] if statuses else None
        if good and _hls_status_ok(latest):
            return {"ok": True, "reason": "HTTP %s" % latest}
        if _hls_statuses_allow_kodi_fallback(statuses):
            return {"ok": True, "reason": "Segmentprüfung unklar, Kodi entscheidet"}
        return {"ok": False, "reason": "HLS Segment HTTP %s" % latest}
    except Exception as exc:
        status = _preflight_exception_status(exc)
        if _hls_status_fatal(status):
            return {"ok": False, "reason": _truncate(str(exc), 120)}
        return {"ok": True, "reason": "Segmentprüfung unklar, Kodi entscheidet"}


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
    _apply_live_buffer()
    if ".m3u8" not in stream_url.lower():
        try:
            item.setContentLookup(False)
        except Exception:
            pass
        return

    engine = _setting_int("livetv.playback.engine", PLAYBACK_ENGINE_AUTO, PLAYBACK_ENGINE_AUTO, PLAYBACK_ENGINE_ADAPTIVE)
    # Some signed HLS manifests reject Kodi's extra mimetype query parameter.
    item.setContentLookup(False)

    if engine == PLAYBACK_ENGINE_ADAPTIVE:
        if _configure_adaptive_stream(item):
            return
        control.infoDialog("InputStream Adaptive ist auf dieser Kodi-Plattform nicht verfügbar oder deaktiviert. Kodi intern wird genutzt.", icon="WARNING", time=5000)
        return

    if engine == PLAYBACK_ENGINE_FFMPEG_DIRECT:
        if _configure_ffmpeg_direct_stream(item):
            return
        control.infoDialog("FFmpeg Direct ist auf dieser Kodi-Plattform nicht verfügbar oder deaktiviert. Kodi intern wird genutzt.", icon="WARNING", time=5000)
        return

    if engine == PLAYBACK_ENGINE_AUTO and _configure_ffmpeg_direct_stream(item):
        return

    log_utils.log("LiveTV uses Kodi internal HLS playback", log_utils.LOGINFO)


def _configure_ffmpeg_direct_stream(item):
    if not _addon_enabled("inputstream.ffmpegdirect"):
        return False
    item.setProperty("inputstream", "inputstream.ffmpegdirect")
    item.setProperty("inputstream.ffmpegdirect.manifest_type", "hls")
    item.setProperty("inputstream.ffmpegdirect.open_mode", "ffmpeg")
    item.setProperty("inputstream.ffmpegdirect.is_realtime_stream", "true")
    item.setProperty("inputstream.ffmpegdirect.playback_as_live", "true")
    item.setProperty("inputstream.ffmpegdirect.stream_mode", "timeshift")
    log_utils.log("LiveTV uses InputStream FFmpeg Direct for HLS playback", log_utils.LOGINFO)
    return True


def _configure_adaptive_stream(item):
    if not _addon_enabled("inputstream.adaptive"):
        return False
    item.setProperty("inputstream", "inputstream.adaptive")
    if int(control.getKodiVersion()) < 21:
        item.setProperty("inputstream.adaptive.manifest_type", "hls")
    log_utils.log("LiveTV uses InputStream Adaptive for HLS playback", log_utils.LOGINFO)
    return True


def _addon_enabled(addon_id):
    try:
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Addons.GetAddonDetails",
            "params": {"addonid": addon_id, "properties": ["enabled"]},
        })
        response = json.loads(xbmc.executeJSONRPC(payload))
        if response.get("error"):
            return _addon_available(addon_id)
        return bool(response.get("result", {}).get("addon", {}).get("enabled"))
    except Exception:
        return _addon_available(addon_id)


def _select_live_stream(channel, catalog):
    playable = []
    kodi_fallback = []
    for candidate, force_signature in _stream_candidates(channel, catalog):
        stream_url = _resolve(candidate.get("url"), force_signature=force_signature)
        if not stream_url:
            continue

        report = _stream_preflight_report(stream_url, candidate)
        if report.get("ok") and not report.get("unstable"):
            if _confirm_preflight(stream_url, candidate, report):
                return stream_url, candidate
            continue

        if report.get("ok"):
            playable.append((stream_url, candidate, report))
        elif _preflight_allows_kodi_fallback(report):
            kodi_fallback.append((stream_url, candidate, report))

    for stream_url, candidate, report in sorted(playable, key=lambda item: _preflight_score(item[2]), reverse=True):
        if _confirm_preflight(stream_url, candidate, report):
            return stream_url, candidate

    for stream_url, candidate, report in sorted(kodi_fallback, key=lambda item: _preflight_score(item[2]), reverse=True):
        log_utils.log(
            "LiveTV preflight lets Kodi decide for %s: %s" % (
                candidate.get("name") or candidate.get("id") or "unknown",
                report.get("reason") or "segment probe inconclusive",
            ),
            log_utils.LOGWARNING,
        )
        return stream_url, candidate

    return "", channel


def _stream_candidates(channel, catalog):
    seen = set()

    def add(candidate, force_signature=False):
        if not candidate:
            return None
        key = "%s:%s" % (candidate.get("id") or candidate.get("url"), force_signature)
        if key in seen:
            return None
        seen.add(key)
        return candidate, force_signature

    for force_signature in (False, True):
        candidate = add(channel, force_signature)
        if candidate:
            yield candidate

    for fallback in _fallback_channels(channel, catalog):
        for force_signature in (False, True):
            candidate = add(fallback, force_signature)
            if candidate:
                yield candidate


def _fallback_channels(channel, catalog):
    key = _fallback_key(channel.get("name"))
    if not key:
        return []

    candidates = []
    for candidate in list(catalog or []) + _load_favorites():
        if not isinstance(candidate, dict):
            continue
        if candidate.get("id") == channel.get("id"):
            continue
        if _fallback_key(candidate.get("name")) != key:
            continue
        candidates.append(candidate)

    candidates.sort(key=lambda item: _fallback_score(channel, item))
    return candidates[:HLS_FALLBACK_LIMIT]


def _fallback_key(name):
    text = re.sub(r"\[[A-Z]\]|\|[A-Z]\b", " ", name or "", flags=re.I)
    text = re.sub(r"\([^)]*\bBACKUP\b[^)]*\)", " ", text, flags=re.I)
    text = re.sub(r"\b(BACKUP|RAW|EVENT|EVENTS|TEST|UHD|FHD|HD|SD)\b", " ", text, flags=re.I)
    text = text.replace("+", " ")
    return _normalize(text)


def _fallback_score(original, candidate):
    name = (candidate.get("name") or "").upper()
    original_name = (original.get("name") or "").upper()
    score = 0
    if "BACKUP" in name:
        score += 30
    if "BACKUP" in original_name and "BACKUP" in name:
        score -= 10
    if "HD+" in name:
        score -= 8
    if "FHD" in name or "UHD" in name:
        score -= 4
    score += abs(len(candidate.get("name") or "") - len(original.get("name") or ""))
    return score


def _confirm_preflight(stream_url, candidate, report):
    if not report.get("ok"):
        return _preflight_allows_kodi_fallback(report)
    if requests is None or ".m3u8" not in (stream_url or "").lower():
        return True
    if control.getSetting("livetv.preflight", "true") == "false":
        return True

    confirm = report
    for _ in range(HLS_PREFLIGHT_CONFIRM_ROUNDS):
        time.sleep(HLS_PREFLIGHT_RECHECK_DELAY)
        confirm = _stream_preflight_report(stream_url, candidate)
        if not confirm.get("ok"):
            return _preflight_allows_kodi_fallback(confirm)
        if confirm.get("unstable"):
            log_utils.log(
                "LiveTV preflight confirmed with unstable segments for %s: %s" % (
                    candidate.get("name") or candidate.get("id") or "unknown",
                    confirm.get("reason") or "segment probe partially failed",
                ),
                log_utils.LOGWARNING,
            )
            return True
        if not confirm.get("unstable"):
            return True
    return True


def _preflight_allows_kodi_fallback(report):
    if not isinstance(report, dict):
        return False
    if report.get("fatal"):
        return False
    return bool(report.get("kodi_fallback"))


def _preflight_report(ok=False, unstable=True, good=0, tested=0, latest=None, reason="", kodi_fallback=False, fatal=False):
    return {
        "ok": bool(ok),
        "unstable": bool(unstable),
        "good": int(good or 0),
        "tested": int(tested or 0),
        "latest": latest,
        "reason": reason,
        "kodi_fallback": bool(kodi_fallback),
        "fatal": bool(fatal),
    }


def _probe_segment_status_safe(segment_url, timeout=10):
    try:
        return _probe_segment_status(segment_url, timeout=timeout)
    except Exception as exc:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        if status is not None:
            try:
                return int(status)
            except Exception:
                return status
        message = str(exc).lower()
        return _preflight_exception_status(exc, message)


def _preflight_exception_status(exc, message=None):
    message = message if message is not None else str(exc).lower()
    if "timed out" in message or "timeout" in message:
        return "timeout"
    if "name resolution" in message or "getaddrinfo failed" in message or "no address associated" in message:
        return "dns_error"
    if "network is unreachable" in message or "no route to host" in message:
        return "network_error"
    if "failed to establish a new connection" in message or "connection refused" in message:
        return "connection_error"
    return "probe_error"


def _hls_status_fatal(status):
    if str(status) in HLS_PREFLIGHT_FATAL_MARKERS:
        return True
    try:
        return int(status) in HLS_PREFLIGHT_FATAL_STATUSES
    except Exception:
        return False


def _hls_statuses_allow_kodi_fallback(statuses):
    if not statuses:
        return True
    return not any(_hls_status_fatal(status) for status in statuses)


def _preflight_score(report):
    tested = int(report.get("tested") or 0)
    good = int(report.get("good") or 0)
    latest = report.get("latest")
    score = good * 10
    if tested and good == tested:
        score += 40
    if report.get("ok"):
        score += 20
    if _hls_status_ok(latest):
        score += 10
    if report.get("unstable"):
        score -= max(0, tested - good) * 8
    return score


def _stream_preflight_report(stream_url, channel):
    if requests is None or ".m3u8" not in (stream_url or "").lower():
        return _preflight_report(ok=True, unstable=False, reason="not_hls")
    if control.getSetting("livetv.preflight", "true") == "false":
        return _preflight_report(ok=True, unstable=False, reason="disabled")

    try:
        segment_urls = _hls_probe_segments(stream_url)
        if not segment_urls:
            log_utils.log(
                "LiveTV preflight inconclusive %s: HLS manifest has no testable segments" % (
                    channel.get("name") or channel.get("id") or "unknown"
                ),
                log_utils.LOGWARNING,
            )
            return _preflight_report(
                ok=False,
                unstable=True,
                good=0,
                tested=0,
                latest=None,
                reason="HLS manifest has no testable segments",
                kodi_fallback=True,
            )

        recent = segment_urls[-HLS_PREFLIGHT_SEGMENTS:]
        statuses = [_probe_segment_status_safe(segment_url) for segment_url in recent]
        good = [status for status in statuses if _hls_status_ok(status)]
        needed = min(HLS_PREFLIGHT_MIN_GOOD, len(recent))
        latest_ok = _hls_status_ok(statuses[-1] if statuses else None)
        latest = statuses[-1] if statuses else None
        fatal = any(_hls_status_fatal(status) for status in statuses)
        kodi_fallback = not fatal and _hls_statuses_allow_kodi_fallback(statuses)

        report = _preflight_report(
            ok=latest_ok and len(good) >= needed,
            unstable=len(good) < len(recent),
            good=len(good),
            tested=len(recent),
            latest=latest,
            reason="%d/%d segments usable, latest HTTP %s" % (len(good), len(recent), latest),
            kodi_fallback=kodi_fallback,
            fatal=fatal,
        )
        if report["ok"]:
            if report["unstable"]:
                log_utils.log(
                    "LiveTV preflight tolerated %s: %d/%d segments usable, latest HTTP %s" % (
                        channel.get("name") or channel.get("id") or "unknown",
                        report["good"],
                        report["tested"],
                        report["latest"],
                    ),
                    log_utils.LOGWARNING,
                )
            return report

        log_utils.log(
            "LiveTV preflight blocked %s: %d/%d segments usable, latest HTTP %s" % (
                channel.get("name") or channel.get("id") or "unknown",
                report["good"],
                report["tested"],
                report["latest"],
            ),
            log_utils.LOGWARNING,
        )
        return report
    except Exception as exc:
        status = _preflight_exception_status(exc)
        fatal = _hls_status_fatal(status)
        log_utils.log(
            "LiveTV preflight inconclusive %s: %s" % (channel.get("name") or channel.get("id") or "unknown", str(exc)),
            log_utils.LOGWARNING,
        )
        return _preflight_report(
            ok=False,
            unstable=True,
            latest=status,
            reason=_truncate(str(exc), 120),
            kodi_fallback=not fatal,
            fatal=fatal,
        )


def _hls_probe_segment(manifest_url, depth=0):
    segments = _hls_probe_segments(manifest_url, depth=depth)
    return segments[-1] if segments else ""


def _hls_probe_segments(manifest_url, depth=0, timeout=10):
    if depth > 2:
        return []

    response = requests.get(manifest_url, headers=_hls_probe_headers(), timeout=timeout)
    if response.status_code >= 400:
        return [manifest_url]
    text = response.text or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF"):
            continue
        for next_line in lines[index + 1:]:
            if next_line.startswith("#"):
                continue
            return _hls_probe_segments(urljoin(manifest_url, next_line), depth + 1, timeout=timeout)

    return [urljoin(manifest_url, line) for line in lines if line and not line.startswith("#")]


def _probe_segment_status(segment_url, timeout=10):
    response = requests.get(segment_url, headers=_hls_probe_headers(range_request=True), timeout=timeout, stream=True)
    try:
        status = int(response.status_code)
    finally:
        try:
            response.close()
        except Exception:
            pass

    if _hls_status_ok(status):
        return status

    response = requests.get(segment_url, headers=_hls_probe_headers(range_request=False), timeout=timeout, stream=True)
    try:
        return int(response.status_code)
    finally:
        try:
            response.close()
        except Exception:
            pass


def _hls_status_ok(status):
    if status is None:
        return True
    try:
        status = int(status)
    except Exception:
        return False
    return 200 <= status < 400 or status == 416


def _hls_probe_headers(range_request=False):
    headers = {
        "User-Agent": _browser_user_agent(),
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    if range_request:
        headers["Range"] = "bytes=0-0"
    return headers


def _apply_live_buffer():
    buffer_mb = _setting_int("livetv.buffer.mb", DEFAULT_BUFFER_MB, 0, MAX_BUFFER_MB)
    if buffer_mb <= 0:
        return

    _set_kodi_setting("filecache.buffermode", 4)
    _set_kodi_setting("filecache.memorysize", buffer_mb)


def _set_kodi_setting(setting, value):
    try:
        current = _get_kodi_setting(setting)
        if current == value:
            return True
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Settings.SetSettingValue",
            "params": {"setting": setting, "value": value},
        })
        response = json.loads(xbmc.executeJSONRPC(payload))
        if response.get("error"):
            log_utils.log("LiveTV buffer setting failed for %s: %s" % (setting, response.get("error")), log_utils.LOGWARNING)
            return False
        return True
    except Exception as exc:
        log_utils.log("LiveTV buffer setting failed for %s: %s" % (setting, str(exc)), log_utils.LOGWARNING)
        return False


def _get_kodi_setting(setting):
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Settings.GetSettingValue",
        "params": {"setting": setting},
    })
    response = json.loads(xbmc.executeJSONRPC(payload))
    if response.get("error"):
        return None
    return response.get("result", {}).get("value")


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
    if any(pattern in upper for pattern in SPORT_CATEGORY_OVERRIDES):
        return "Sport"
    for category, patterns in CATEGORY_RULES:
        if any(pattern in upper for pattern in patterns):
            return category
    return "Sonstige"


def _apply_current_categories(channels):
    result = []
    for channel in channels or []:
        if not isinstance(channel, dict):
            continue
        current = dict(channel)
        current["category"] = _category_for(current.get("name"))
        result.append(current)
    return result


def _visible_channels(channels):
    show_special = control.getSetting("livetv.show.special", "true") != "false"
    blocked = _health_blocked_ids()
    result = []
    for channel in channels:
        if not show_special and any(token in (channel.get("name") or "").upper() for token in _HIDDEN_TOKENS):
            continue
        if str(channel.get("id") or "") in blocked:
            continue
        result.append(channel)
    return result


def _context_menu(channel, favorite_context=False):
    check_entry = ("Senderliste auf Funktion prüfen", "RunPlugin(%s)" % _url({"action": "liveTVHealthCheck"}))
    if favorite_context:
        return [
            ("Aus TV Favoriten entfernen", "RunPlugin(%s)" % _url({"action": "liveTVFavoriteRemove", "id": channel.get("id")})),
            check_entry,
        ]
    favorites = _load_favorites()
    if _channel_by_id(favorites, channel.get("id")):
        label = "Aus TV Favoriten entfernen"
        action = "liveTVFavoriteRemove"
    else:
        label = "Zu TV Favoriten hinzufügen"
        action = "liveTVFavoriteAdd"
    return [
        (label, "RunPlugin(%s)" % _url({"action": action, "id": channel.get("id")})),
        check_entry,
    ]


def _health_blocked_ids():
    state = _read_json(HEALTH_FILE, {})
    if not isinstance(state, dict):
        return set()
    blocked = state.get("blocked") or {}
    if not isinstance(blocked, dict):
        return set()
    return set(str(channel_id) for channel_id in blocked.keys())


def _save_health_state(blocked, checked, reachable, cancelled):
    _ensure_profile()
    state = {
        "checked_at": int(time.time()),
        "checked": int(checked),
        "reachable": int(reachable),
        "hidden": len(blocked),
        "cancelled": bool(cancelled),
        "blocked": blocked,
    }
    _write_json(HEALTH_FILE, state)


def _add_folder(handle, label, params, is_folder, plot=""):
    item = control.item(label, offscreen=True)
    if is_folder:
        item.setIsFolder(True)
        item.setInfo("video", {"title": label, "plot": plot or label})
    else:
        item.setProperty("IsPlayable", "false")
    control.addItem(handle, _url(params), item, is_folder)


def _plot(channel, programmes=None, include_empty_epg=False):
    lines = []
    current, next_programme = _normalise_programme_pair(programmes)
    if current:
        lines.append("Aktuell: %s %s" % (_programme_time_range(current), _programme_title(current)))
        description = current.get("desc") or ""
        if description:
            lines.append(description)
    elif include_empty_epg:
        lines.append("Aktuell: Keine EPG-Daten")
    if next_programme:
        lines.append("Gleich: %s %s" % (_programme_time_range(next_programme), _programme_title(next_programme)))
    elif include_empty_epg:
        lines.append("Gleich: Keine EPG-Daten")
    lines.append(channel.get("category") or "LiveTV")
    lines.append(channel.get("group") or "Germany")
    return "[CR]".join([line for line in lines if line])


def _current_programme(channel, refresh=False):
    return _programme_pair(channel, refresh=refresh)[0]


def _programme_pair(channel, epg=None, refresh=False):
    if not _epg_enabled():
        return None, None

    epg = epg if epg is not None else _epg_data(refresh=refresh)
    if not epg:
        return None, None

    channel_id = _epg_channel_id(channel, epg)
    if not channel_id:
        return None, None

    now = int(time.time())
    current = None
    next_programme = None
    for programme in epg.get("programmes", {}).get(channel_id, []):
        start = int(programme.get("start") or 0)
        stop = int(programme.get("stop") or 0)
        if start <= now < stop:
            current = programme
            continue
        if start > now and next_programme is None:
            next_programme = programme
            break
    return current, next_programme


def _normalise_programme_pair(programmes):
    if isinstance(programmes, (list, tuple)):
        current = programmes[0] if len(programmes) > 0 else None
        next_programme = programmes[1] if len(programmes) > 1 else None
        return current, next_programme
    return programmes, None


def _set_channel_art(item, channel, epg=None):
    logo = _channel_logo(channel, epg)
    if not logo:
        return
    item.setArt({
        "icon": logo,
        "thumb": logo,
        "poster": logo,
        "clearlogo": logo,
    })


def _show_programme_before_play(channel, programme):
    if not programme or not _epg_enabled():
        return

    heading = channel.get("name") or "LiveTV"
    if control.getSetting("livetv.epg.dialog", "false") == "true":
        control.dialog.ok("LiveTV EPG", _programme_dialog_text(heading, programme))
        return

    control.infoDialog(
        _truncate("Jetzt %s: %s" % (_programme_time_range(programme), _programme_title(programme)), 110),
        heading=heading,
        icon=channel.get("logo") or "INFO",
        time=7000,
    )
    xbmc.sleep(1800)


def _programme_dialog_text(channel_name, programme):
    lines = [
        channel_name,
        "",
        "Jetzt: %s" % _programme_time_range(programme),
        "[B]%s[/B]" % _programme_title(programme),
    ]
    description = programme.get("desc") or ""
    if description:
        lines.extend(["", _truncate(description, 900)])
    return "\n".join(lines)


def _programme_title(programme):
    title = programme.get("title") or "Unbekannte Sendung"
    subtitle = programme.get("subtitle") or ""
    if subtitle and subtitle not in title:
        return "%s - %s" % (title, subtitle)
    return title


def _programme_time_range(programme):
    start = _local_hm(programme.get("start"))
    stop = _local_hm(programme.get("stop"))
    if start and stop:
        return "%s-%s" % (start, stop)
    return ""


def _local_hm(timestamp):
    try:
        return time.strftime("%H:%M", time.localtime(int(timestamp)))
    except Exception:
        return ""


def _epg_data(refresh=False):
    _ensure_profile()
    cached = _read_epg_cache()
    if not refresh:
        return cached if _epg_cache_usable(cached, strict=True) else {}
    if _epg_cache_usable(cached, strict=True):
        return cached

    epg = _download_epg()
    if epg:
        _write_json(EPG_FILE, epg)
        _epg_memory_cache["data"] = epg
        try:
            _epg_memory_cache["mtime"] = os.path.getmtime(EPG_FILE)
        except Exception:
            _epg_memory_cache["mtime"] = time.time()
        return epg

    if _epg_cache_usable(cached, strict=False):
        control.infoDialog("LiveTV nutzt gespeicherte EPG-Daten.", icon="WARNING", time=3500)
        return cached
    return {}


def _read_epg_cache():
    try:
        mtime = os.path.getmtime(EPG_FILE)
    except Exception:
        mtime = 0
    if _epg_memory_cache["data"] is not None and _epg_memory_cache["mtime"] == mtime:
        return _epg_memory_cache["data"]
    data = _read_json(EPG_FILE, {})
    _epg_memory_cache["data"] = data
    _epg_memory_cache["mtime"] = mtime
    return data


def _epg_cache_usable(data, strict=True):
    if not isinstance(data, dict) or not data.get("programmes") or not data.get("alias_to_id"):
        return False

    try:
        hours = int(control.getSetting("livetv.epg.cache.hours", str(DEFAULT_EPG_CACHE_HOURS)))
    except Exception:
        hours = DEFAULT_EPG_CACHE_HOURS
    ttl = max(1, hours) * 3600
    now = time.time()
    if strict and now - int(data.get("updated_at") or 0) >= ttl:
        return False
    return int(data.get("valid_until") or 0) > int(now)


def _download_epg():
    if requests is None:
        log_utils.log("LiveTV EPG failed: requests module is not available", log_utils.LOGWARNING)
        return {}

    progress = control.progressDialog
    progress.create(control.addonName, "LiveTV-EPG wird geladen")
    progress.update(5)
    try:
        response = requests.get(EPG_URL, headers=_epg_headers(), timeout=45)
        response.raise_for_status()
        progress.update(30, "LiveTV-EPG wird ausgewertet")
        return _parse_epg(response.content)
    except Exception as exc:
        log_utils.log("LiveTV EPG failed: %s" % str(exc), log_utils.LOGWARNING)
        return {}
    finally:
        try:
            progress.close()
        except Exception:
            pass


def _parse_epg(raw):
    try:
        xml_data = gzip.decompress(raw)
    except Exception:
        xml_data = raw

    now = int(time.time())
    window_start = now - (EPG_LOOKBEHIND_HOURS * 3600)
    window_end = now + (EPG_LOOKAHEAD_HOURS * 3600)
    channels = {}
    programmes = {}

    for event, elem in _iter_xmltv(xml_data):
        tag = _xml_tag(elem.tag)
        if tag == "channel":
            channel_id = elem.attrib.get("id") or ""
            if channel_id:
                names = _display_names(elem)
                channels[channel_id] = {
                    "names": names,
                    "aliases": sorted(_epg_aliases(channel_id, names)),
                    "logos": _channel_icons(elem),
                }
            elem.clear()
        elif tag == "programme":
            channel_id = elem.attrib.get("channel") or ""
            start = _xmltv_timestamp(elem.attrib.get("start"))
            stop = _xmltv_timestamp(elem.attrib.get("stop"))
            if channel_id and start and stop and stop > window_start and start < window_end:
                title = _child_text(elem, "title")
                if title:
                    programmes.setdefault(channel_id, []).append({
                        "title": title,
                        "subtitle": _child_text(elem, "sub-title"),
                        "desc": _child_text(elem, "desc"),
                        "start": start,
                        "stop": stop,
                    })
            elem.clear()

    alias_to_id = {}
    for channel_id, meta in channels.items():
        if channel_id not in programmes:
            continue
        programmes[channel_id].sort(key=lambda item: int(item.get("start") or 0))
        for alias in meta.get("aliases", []):
            alias_to_id.setdefault(alias, channel_id)

    if not alias_to_id:
        return {}

    return {
        "updated_at": now,
        "valid_until": window_end,
        "source": EPG_URL,
        "channels": channels,
        "programmes": programmes,
        "alias_to_id": alias_to_id,
        "stats": {
            "channels": len(channels),
            "matched_channels": len(programmes),
            "aliases": len(alias_to_id),
        },
    }


def _iter_xmltv(xml_data):
    return ET.iterparse(io.BytesIO(xml_data), events=("end",))


def _display_names(elem):
    names = []
    for child in elem:
        if _xml_tag(child.tag) == "display-name" and child.text:
            text = _clean_text(child.text)
            if text and text not in names:
                names.append(text)
    return names


def _channel_icons(elem):
    icons = []
    for child in elem:
        if _xml_tag(child.tag) == "icon":
            logo = _logo_value(child.attrib.get("src") or "")
            if logo and logo not in icons:
                icons.append(logo)
    return icons


def _child_text(elem, tag_name):
    for child in elem:
        if _xml_tag(child.tag) == tag_name and child.text:
            return _clean_text(child.text)
    return ""


def _xml_tag(tag):
    return tag.rsplit("}", 1)[-1]


def _xmltv_timestamp(value):
    match = _XMLTV_TIME_RE.match(value or "")
    if not match:
        return 0
    try:
        stamp = time.strptime(match.group(1), "%Y%m%d%H%M%S")
        if not match.group(2):
            return int(time.mktime(stamp))
        timestamp = calendar.timegm(stamp)
        offset = (int(match.group(3)) * 3600) + (int(match.group(4)) * 60)
        return int(timestamp - offset if match.group(2) == "+" else timestamp + offset)
    except Exception:
        return 0


def _epg_channel_id(channel, epg):
    aliases = _live_channel_aliases(channel)
    alias_to_id = epg.get("alias_to_id", {})
    for alias in aliases:
        channel_id = alias_to_id.get(alias)
        if channel_id:
            return channel_id

    for alias in aliases:
        if len(alias) < 6:
            continue
        for known_alias, channel_id in alias_to_id.items():
            if len(known_alias) >= 6 and (alias in known_alias or known_alias in alias):
                return channel_id
    return ""


def _enrich_channel_logos(channels, epg=None):
    channels = list(channels or [])
    alias_to_logo = {}

    for channel in channels:
        logo = _logo_value(channel.get("logo"))
        if logo:
            for alias in _live_channel_aliases(channel):
                alias_to_logo.setdefault(alias, logo)

    for channel_id, meta in (epg or {}).get("channels", {}).items():
        for logo in meta.get("logos", []):
            if not logo:
                continue
            for alias in meta.get("aliases") or _epg_aliases(channel_id, meta.get("names", [])):
                alias_to_logo.setdefault(alias, logo)

    needs_logo_fallback = any(_logo_should_replace(channel.get("logo")) for channel in channels)
    fallback_logos = _logo_data().get("logos", {}) if needs_logo_fallback else {}
    alias_to_logo.update(fallback_logos)

    for channel in channels:
        existing = _logo_value(channel.get("logo"))
        if existing and not _logo_should_replace(existing):
            continue
        logo = _logo_for_aliases(_live_channel_aliases(channel), fallback_logos) or _logo_for_aliases(_live_channel_aliases(channel), alias_to_logo)
        if logo and logo != existing:
            channel["logo"] = logo
    return channels


def _channel_logo(channel, epg=None):
    logo = _logo_value(channel.get("logo"))
    aliases = _live_channel_aliases(channel)

    if logo and _logo_should_replace(logo):
        fallback = _logo_for_aliases(aliases, _logo_data().get("logos", {}))
        if fallback:
            channel["logo"] = fallback
            return fallback

    if logo:
        return logo

    alias_to_logo = {}
    for channel_id, meta in (epg or {}).get("channels", {}).items():
        for logo in meta.get("logos", []):
            if not logo:
                continue
            for alias in meta.get("aliases") or _epg_aliases(channel_id, meta.get("names", [])):
                alias_to_logo.setdefault(alias, logo)
    if alias_to_logo:
        logo = _logo_for_aliases(aliases, alias_to_logo)
        if logo:
            channel["logo"] = logo
            return logo

    logo = _logo_for_aliases(aliases, _logo_data().get("logos", {}))
    if logo:
        channel["logo"] = logo
    return logo


def _logo_should_replace(logo):
    logo = _logo_value(logo).lower()
    return not logo or "logo.huhu.to/" in logo


def _logo_for_aliases(aliases, alias_to_logo):
    for alias in aliases:
        logo = alias_to_logo.get(alias)
        if logo:
            return logo
    for alias in aliases:
        if len(alias) < 6:
            continue
        for known_alias, logo in alias_to_logo.items():
            if len(known_alias) >= 6 and (alias in known_alias or known_alias in alias):
                return logo
    return ""


def _logo_data():
    _ensure_profile()
    cached = _read_logo_cache()
    if _logo_cache_valid(cached):
        return cached

    logos = _download_logo_data()
    if logos:
        _write_json(LOGOS_FILE, logos)
        _logo_memory_cache["data"] = logos
        try:
            _logo_memory_cache["mtime"] = os.path.getmtime(LOGOS_FILE)
        except Exception:
            _logo_memory_cache["mtime"] = time.time()
        return logos
    return cached if isinstance(cached, dict) else {}


def _read_logo_cache():
    try:
        mtime = os.path.getmtime(LOGOS_FILE)
    except Exception:
        mtime = 0
    if _logo_memory_cache["data"] is not None and _logo_memory_cache["mtime"] == mtime:
        return _logo_memory_cache["data"]
    data = _read_json(LOGOS_FILE, {})
    _logo_memory_cache["data"] = data
    _logo_memory_cache["mtime"] = mtime
    return data


def _logo_cache_valid(data):
    if not isinstance(data, dict) or not data.get("logos"):
        return False
    return time.time() - int(data.get("updated_at") or 0) < LOGOS_TTL


def _download_logo_data():
    if requests is None:
        log_utils.log("LiveTV logo catalog failed: requests module is not available", log_utils.LOGWARNING)
        return {}

    progress = control.progressDialog
    progress.create(control.addonName, "LiveTV-Senderlogos werden geladen")
    progress.update(10)
    try:
        response = requests.get(LOGOS_URL, headers=_epg_headers(), timeout=45)
        response.raise_for_status()
        progress.update(60, "LiveTV-Senderlogos werden zugeordnet")
        return _parse_logo_data(response.json())
    except Exception as exc:
        log_utils.log("LiveTV logo catalog failed: %s" % str(exc), log_utils.LOGWARNING)
        return {}
    finally:
        try:
            progress.close()
        except Exception:
            pass


def _parse_logo_data(items):
    if not isinstance(items, list):
        return {}

    logos = {}
    for item in items:
        channel_id = item.get("channel") or ""
        if not channel_id.lower().endswith(".de"):
            continue
        logo = _logo_value(item.get("url"))
        if not logo:
            continue
        for alias in _epg_aliases(channel_id, []):
            logos.setdefault(alias, logo)
    return {
        "updated_at": int(time.time()),
        "source": LOGOS_URL,
        "logos": logos,
    } if logos else {}


def _logo_value(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("logo", "src", "url", "thumb", "poster", "icon"):
            logo = _logo_value(value.get(key))
            if logo:
                return logo
        return ""
    if isinstance(value, (list, tuple)):
        for item in value:
            logo = _logo_value(item)
            if logo:
                return logo
    return ""


def _epg_aliases(channel_id, names):
    aliases = set()
    parts = [channel_id.rsplit(".", 1)[0] if channel_id.lower().endswith(".de") else channel_id]
    parts.extend(names or [])
    for value in parts:
        aliases.update(_alias_variants(_normalise_channel_name(value)))
    return set([alias for alias in aliases if alias])


def _live_channel_aliases(channel):
    name = channel.get("name") or ""
    aliases = set()
    aliases.update(_alias_variants(_normalise_channel_name(name)))
    aliases.update(_alias_variants(_normalise_channel_name(_strip_live_suffixes(name))))
    return sorted([alias for alias in aliases if alias], key=len, reverse=True)


def _strip_live_suffixes(value):
    text = re.sub(r"\[[^\]]*\]", " ", value or "")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\bHD\+", " ", text, flags=re.IGNORECASE)
    text = _EPG_DROP_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalise_channel_name(value):
    value = _strip_live_suffixes(value)
    value = value.replace("&", " und ")
    value = value.replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _alias_variants(alias):
    aliases = set([alias])
    if alias.endswith("plus"):
        aliases.add(alias[:-4] + "up")
    if alias.endswith("up"):
        aliases.add(alias[:-2] + "plus")
    for old, new in _EPG_ALIAS_REPLACEMENTS:
        if old in alias:
            aliases.add(alias.replace(old, new))
    return aliases


def _clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _truncate(value, length):
    value = value or ""
    if len(value) <= length:
        return value
    return value[:max(0, length - 3)].rstrip() + "..."


def _epg_headers():
    return {
        "User-Agent": _browser_user_agent(),
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
    }


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
        hours = _setting_int("livetv.cache.hours", DEFAULT_CACHE_HOURS, 1, 24)
    except Exception:
        hours = DEFAULT_CACHE_HOURS
    ttl = max(1, hours) * 3600
    return time.time() - int(data.get("updated_at") or 0) < ttl


def _setting_int(name, default, minimum=None, maximum=None):
    try:
        value = int(float(control.getSetting(name, str(default))))
    except Exception:
        value = int(default)
    if minimum is not None:
        value = max(int(minimum), value)
    if maximum is not None:
        value = min(int(maximum), value)
    return value


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


def _epg_enabled():
    return control.getSetting("livetv.epg.enabled", "true") != "false"
