from __future__ import annotations

import argparse
import json
import os
import pickle
import runpy
import shutil
import sqlite3
import sys
import tempfile
import time
import types
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from firetv_stick_simulator import FireTvStickProfile, find_profile


@dataclass
class CheckResult:
    name: str
    status: str
    details: str


@dataclass
class SimulationState:
    profile: FireTvStickProfile
    profile_dir: Path
    kodi_version: str
    addon_version: str
    settings: Dict[str, str] = field(default_factory=dict)
    directory_items: List[Dict[str, Any]] = field(default_factory=list)
    builtins: List[str] = field(default_factory=list)
    notifications: List[Dict[str, Any]] = field(default_factory=list)
    dialogs: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    resolved_urls: List[Dict[str, Any]] = field(default_factory=list)
    ended_directories: List[Dict[str, Any]] = field(default_factory=list)
    content: List[Dict[str, Any]] = field(default_factory=list)
    plugin_categories: List[Dict[str, Any]] = field(default_factory=list)
    player_events: List[Dict[str, Any]] = field(default_factory=list)


def addon_version() -> str:
    return ET.parse(str(ROOT / "addon.xml")).getroot().attrib.get("version", "0")


def default_settings(profile_dir: Path) -> Dict[str, str]:
    return {
        "updates.auto": "false",
        "first_install.playback_defaults.applied": "true",
        "fanart": "false",
        "hosts.language": "1",
        "default.action": "2",
        "download.movie.path": str(profile_dir / "downloads" / "movies"),
        "download.tv.path": str(profile_dir / "downloads" / "tvshows"),
    }


def purge_xvault_modules() -> None:
    prefixes = ("resources", "sites", "scrapers")
    for name in list(sys.modules):
        if name == "default" or name in prefixes or name.startswith(tuple(prefix + "." for prefix in prefixes)):
            del sys.modules[name]


def install_kodi_stubs(state: SimulationState) -> None:
    state.profile_dir.mkdir(parents=True, exist_ok=True)
    (state.profile_dir / "temp").mkdir(parents=True, exist_ok=True)
    (state.profile_dir / "downloads" / "movies").mkdir(parents=True, exist_ok=True)
    (state.profile_dir / "downloads" / "tvshows").mkdir(parents=True, exist_ok=True)
    write_startup_state(state)

    xbmc = types.ModuleType("xbmc")
    xbmc.LOGDEBUG = 0
    xbmc.LOGINFO = 1
    xbmc.LOGNOTICE = 1
    xbmc.LOGWARNING = 2
    xbmc.LOGERROR = 3
    xbmc.LOGFATAL = 4
    xbmc.PLAYLIST_VIDEO = 1
    xbmc.ISO_639_1 = 0

    def xbmc_log(message: str, level: int = 0) -> None:
        state.logs.append({"level": level, "message": str(message)})

    def get_info_label(label: str) -> str:
        normalized = label.lower()
        if normalized == "system.buildversion":
            return state.kodi_version
        if normalized == "system.buildversioncode":
            return state.kodi_version
        if normalized == "system.profilename":
            return "FireTV-%s" % state.profile.build_model
        if normalized == "system.friendlyname":
            return state.profile.name
        if normalized == "network.dns1address":
            return "1.1.1.1"
        if normalized == "network.gatewayaddress":
            return "192.168.1.1"
        if normalized == "system.freemoram" or normalized == "system.freememory":
            return str(simulated_free_memory_mb(state.profile))
        return ""

    def get_cond_visibility(query: str) -> bool:
        normalized = query.lower().strip()
        if "system.platform.android" in normalized or "system.platform.linux" in normalized:
            return "android" in normalized
        if normalized.startswith("system.hasaddon("):
            return True
        if "window.isactive" in normalized or "window.isvisible" in normalized:
            return False
        if "container.isupdating" in normalized:
            return False
        return False

    def executebuiltin(command: str, *args: Any) -> None:
        state.builtins.append(str(command))

    def execute_jsonrpc(payload: str) -> str:
        try:
            request = json.loads(payload)
        except Exception:
            return json.dumps({"jsonrpc": "2.0", "id": 1, "error": "invalid"})
        method = request.get("method")
        request_id = request.get("id", 1)
        if method == "Settings.GetSettingValue":
            return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": {"value": True}})
        if method in ("Addons.SetAddonEnabled", "Addons.GetAddonDetails"):
            return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": "OK"})
        return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": "OK"})

    class Monitor:
        def abortRequested(self) -> bool:
            return False

        def waitForAbort(self, timeout: float = 0) -> bool:
            if timeout:
                time.sleep(min(float(timeout), 0.001))
            return False

    class Player:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def play(self, url: str, item: Any = None) -> None:
            state.player_events.append({"event": "play", "url": url, "label": getattr(item, "label", "")})

        def isPlaying(self) -> bool:
            return False

        def getSubtitles(self) -> str:
            return ""

        def setSubtitles(self, subtitle: str) -> None:
            state.player_events.append({"event": "setSubtitles", "subtitle": subtitle})

    class PlayList:
        def __init__(self, playlist_type: int) -> None:
            self.playlist_type = playlist_type
            self.items: List[Any] = []

        def clear(self) -> None:
            self.items = []

        def add(self, url: str, item: Any = None) -> None:
            self.items.append((url, item))

    class Keyboard:
        def __init__(self, default: str = "", heading: str = "", hidden: bool = False) -> None:
            self.text = default
            self.confirmed = False

        def doModal(self) -> None:
            self.confirmed = False

        def isConfirmed(self) -> bool:
            return self.confirmed

        def getText(self) -> str:
            return self.text

        def setDefault(self, value: str) -> None:
            self.text = value

        def setHeading(self, heading: str) -> None:
            pass

        def setHiddenInput(self, hidden: bool) -> None:
            pass

    xbmc.log = xbmc_log
    xbmc.getSkinDir = lambda: "skin.estuary"
    xbmc.getInfoLabel = get_info_label
    xbmc.getCondVisibility = get_cond_visibility
    xbmc.executebuiltin = executebuiltin
    xbmc.executeJSONRPC = execute_jsonrpc
    xbmc.Monitor = Monitor
    xbmc.Player = Player
    xbmc.PlayList = PlayList
    xbmc.Keyboard = Keyboard
    xbmc.sleep = lambda milliseconds: time.sleep(min(float(milliseconds) / 1000.0, 0.001))
    xbmc.getLanguage = lambda mode=None: "de"
    xbmc.convertLanguage = lambda value, mode=None: value[:2].lower()
    xbmc.getFreeMem = lambda: simulated_free_memory_mb(state.profile)
    sys.modules["xbmc"] = xbmc

    xbmcaddon = types.ModuleType("xbmcaddon")

    class Addon:
        def __init__(self, addon_id: Optional[str] = None) -> None:
            self.addon_id = addon_id or "plugin.video.xvault"

        def getAddonInfo(self, key: str) -> str:
            if self.addon_id == "plugin.video.xvault":
                values = {
                    "id": "plugin.video.xvault",
                    "name": "[B]xVAULT[/B]",
                    "version": state.addon_version,
                    "path": str(ROOT),
                    "profile": str(state.profile_dir),
                    "icon": str(ROOT / "resources" / "icon.png"),
                    "fanart": str(ROOT / "resources" / "fanart.png"),
                }
            else:
                values = {
                    "id": self.addon_id,
                    "name": self.addon_id,
                    "version": dependency_version(self.addon_id),
                    "path": str(state.profile_dir / "addons" / self.addon_id),
                    "profile": str(state.profile_dir / "addon_data" / self.addon_id),
                    "icon": "",
                    "fanart": "",
                }
            return values.get(key, "")

        def getSetting(self, key: str) -> str:
            return state.settings.get(key, "")

        def setSetting(self, id: str, value: str = "") -> None:
            state.settings[id] = value

        def openSettings(self) -> None:
            state.dialogs.append({"type": "settings", "addon": self.addon_id})

    xbmcaddon.Addon = Addon
    sys.modules["xbmcaddon"] = xbmcaddon

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.NOTIFICATION_INFO = "INFO"
    xbmcgui.NOTIFICATION_WARNING = "WARNING"
    xbmcgui.NOTIFICATION_ERROR = "ERROR"

    class ListItem:
        def __init__(self, label: str = "", *args: Any, **kwargs: Any) -> None:
            self.label = label
            self.art: Dict[str, str] = {}
            self.info: Dict[str, Dict[str, Any]] = {}
            self.properties: Dict[str, str] = {}
            self.context: List[Any] = []
            self.path = ""
            self.folder = False

        def setArt(self, art: Dict[str, str]) -> None:
            self.art.update(art)

        def setInfo(self, kind: str, info: Dict[str, Any]) -> None:
            self.info[kind] = info

        def setIsFolder(self, value: bool) -> None:
            self.folder = bool(value)

        def setProperty(self, key: str, value: str) -> None:
            self.properties[key] = value

        def addContextMenuItems(self, items: Sequence[Any]) -> None:
            self.context.extend(items)

        def setPath(self, value: str) -> None:
            self.path = value

        def setMimeType(self, value: str) -> None:
            self.properties["mime"] = value

        def setContentLookup(self, value: bool) -> None:
            self.properties["content_lookup"] = str(bool(value))

    class Dialog:
        def notification(self, heading: str, message: str, icon: str = "", time: int = 0, sound: bool = False) -> None:
            state.notifications.append(
                {"heading": heading, "message": message, "icon": icon, "time": time, "sound": sound}
            )

        def yesno(self, *args: Any, **kwargs: Any) -> bool:
            state.dialogs.append({"type": "yesno", "args": [str(arg) for arg in args]})
            return False

        def select(self, heading: str, options: Sequence[str]) -> int:
            state.dialogs.append({"type": "select", "heading": heading, "count": len(options)})
            return -1

        def input(self, heading: str = "", *args: Any, **kwargs: Any) -> str:
            state.dialogs.append({"type": "input", "heading": heading})
            return ""

        def ok(self, *args: Any, **kwargs: Any) -> bool:
            state.dialogs.append({"type": "ok", "args": [str(arg) for arg in args]})
            return True

        def textviewer(self, heading: str, text: str) -> None:
            state.dialogs.append({"type": "textviewer", "heading": heading, "length": len(text)})

    class DialogProgress:
        def create(self, *args: Any, **kwargs: Any) -> None:
            state.dialogs.append({"type": "progress-create", "args": [str(arg) for arg in args]})

        def update(self, *args: Any, **kwargs: Any) -> None:
            pass

        def close(self) -> None:
            pass

        def iscanceled(self) -> bool:
            return False

    class DialogProgressBG(DialogProgress):
        pass

    class Window:
        def __init__(self, window_id: int = 10000) -> None:
            self.window_id = window_id
            self.properties: Dict[str, str] = {}

        def getProperty(self, key: str) -> str:
            return self.properties.get(key, "")

        def setProperty(self, key: str, value: str) -> None:
            self.properties[key] = value

        def clearProperty(self, key: str) -> None:
            self.properties.pop(key, None)

    xbmcgui.ListItem = ListItem
    xbmcgui.Dialog = Dialog
    xbmcgui.DialogProgress = DialogProgress
    xbmcgui.DialogProgressBG = DialogProgressBG
    xbmcgui.Window = Window
    xbmcgui.getCurrentWindowId = lambda: 10000
    sys.modules["xbmcgui"] = xbmcgui

    xbmcplugin = types.ModuleType("xbmcplugin")
    xbmcplugin.SORT_METHOD_LABEL = 1

    def add_directory_item(handle: int, url: str, listitem: ListItem, isFolder: bool = True) -> bool:
        state.directory_items.append(
            {
                "handle": handle,
                "url": url,
                "label": listitem.label,
                "folder": bool(isFolder),
                "properties": dict(listitem.properties),
                "art": dict(listitem.art),
            }
        )
        return True

    xbmcplugin.addDirectoryItem = add_directory_item
    xbmcplugin.endOfDirectory = lambda handle, **kwargs: state.ended_directories.append({"handle": handle, **kwargs})
    xbmcplugin.setContent = lambda handle, content: state.content.append({"handle": handle, "content": content})
    xbmcplugin.setPluginCategory = lambda handle, category: state.plugin_categories.append(
        {"handle": handle, "category": category}
    )
    xbmcplugin.addSortMethod = lambda handle, sortMethod: None
    xbmcplugin.setResolvedUrl = lambda handle, succeeded, item: state.resolved_urls.append(
        {"handle": handle, "succeeded": succeeded, "label": getattr(item, "label", "")}
    )
    sys.modules["xbmcplugin"] = xbmcplugin

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.translatePath = lambda path: translate_path(path, state)
    xbmcvfs.exists = lambda path: Path(translate_path(path, state)).exists()
    xbmcvfs.mkdir = lambda path: Path(translate_path(path, state)).mkdir(parents=True, exist_ok=True) or True
    xbmcvfs.delete = lambda path: delete_path(translate_path(path, state))
    xbmcvfs.rmdir = lambda path: remove_dir(translate_path(path, state))
    xbmcvfs.listdir = lambda path: list_dir(translate_path(path, state))
    xbmcvfs.copy = lambda source, target: shutil.copyfile(translate_path(source, state), translate_path(target, state))
    xbmcvfs.File = lambda path, mode="r": VfsFile(translate_path(path, state), mode)
    sys.modules["xbmcvfs"] = xbmcvfs

    if "six" not in sys.modules:
        six = types.ModuleType("six")
        six.iteritems = lambda value: value.items()
        sys.modules["six"] = six


def dependency_version(addon_id: str) -> str:
    versions = {
        "script.module.requests": "2.31.0",
        "script.module.six": "1.16.0",
        "script.module.kodi-six": "0.1.3",
        "script.module.pyaes": "1.6.1",
        "script.module.infotagger": "0.0.6",
        "script.module.resolveurl": "5.1.100",
        "inputstream.adaptive": "21.5.0",
        "inputstream.ffmpegdirect": "21.3.0",
        "plugin.video.youtube": "7.0.0",
    }
    return versions.get(addon_id, "1.0.0")


def translate_path(path: Any, state: SimulationState) -> str:
    value = str(path)
    replacements = {
        "special://home/addons/plugin.video.xvault": str(ROOT),
        "special://profile/addon_data/plugin.video.xvault": str(state.profile_dir),
        "special://temp": str(state.profile_dir / "temp"),
    }
    for prefix, target in replacements.items():
        if value.startswith(prefix):
            suffix = value[len(prefix):].lstrip("/\\")
            return str(Path(target) / suffix) if suffix else target
    if value.startswith("special://"):
        safe = value.replace("special://", "").replace("/", "_").replace("\\", "_")
        return str(state.profile_dir / "special" / safe)
    return value


def delete_path(path: str) -> bool:
    try:
        Path(path).unlink()
        return True
    except FileNotFoundError:
        return False


def remove_dir(path: str) -> bool:
    try:
        Path(path).rmdir()
        return True
    except OSError:
        return False


def list_dir(path: str) -> Tuple[List[str], List[str]]:
    directory = Path(path)
    if not directory.is_dir():
        return [], []
    dirs: List[str] = []
    files: List[str] = []
    for item in directory.iterdir():
        if item.is_dir():
            dirs.append(item.name)
        else:
            files.append(item.name)
    return dirs, files


class VfsFile:
    def __init__(self, path: str, mode: str = "r") -> None:
        self.path = path
        self.mode = mode
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(path, mode)

    def read(self, *args: Any) -> Any:
        return self.handle.read(*args)

    def write(self, data: Any) -> Any:
        return self.handle.write(data)

    def close(self) -> None:
        self.handle.close()

    def __enter__(self) -> "VfsFile":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def write_startup_state(state: SimulationState) -> None:
    startup = {
        "intro_seen": True,
        "intro_screen_seen": True,
        "last_started_version": state.addon_version,
    }
    (state.profile_dir / "startup_info.json").write_text(json.dumps(startup), encoding="utf-8")


def simulated_free_memory_mb(profile: FireTvStickProfile) -> int:
    if profile.ram_mb <= 1024:
        return 96
    if profile.ram_mb < 2048:
        return 160
    return 320


def run_kodi_smoke(profile: FireTvStickProfile, action: str, kodi_version: str, profile_dir: Path) -> CheckResult:
    state = create_state(profile, kodi_version, profile_dir)
    query = "" if action in ("root", "") else "?action=%s" % action
    old_argv = list(sys.argv)
    old_path = list(sys.path)
    try:
        install_kodi_stubs(state)
        purge_xvault_modules()
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        sys.argv = ["plugin://plugin.video.xvault/", "1", query]
        runpy.run_path(str(ROOT / "default.py"), run_name="__main__")
        if not state.ended_directories and action in ("root", "movieNavigator", "tvNavigator", "toolNavigator"):
            return CheckResult("kodi-smoke", "FAIL", "Kodi-Simulation beendete kein Verzeichnis.")
        return CheckResult(
            "kodi-smoke",
            "PASS",
            "%s: %d DirectoryItems, %d Builtins, %d Notifications"
            % (action, len(state.directory_items), len(state.builtins), len(state.notifications)),
        )
    except SystemExit as exc:
        return CheckResult("kodi-smoke", "FAIL", "default.py beendete mit SystemExit(%s)." % exc)
    except Exception as exc:
        return CheckResult("kodi-smoke", "FAIL", "%s: %s" % (exc.__class__.__name__, exc))
    finally:
        sys.argv = old_argv
        sys.path[:] = old_path


def create_state(profile: FireTvStickProfile, kodi_version: str, profile_dir: Path) -> SimulationState:
    state = SimulationState(profile=profile, profile_dir=profile_dir, kodi_version=kodi_version, addon_version=addon_version())
    state.settings.update(default_settings(profile_dir))
    return state


def run_db_stress(profile: FireTvStickProfile, iterations: int, kodi_version: str, profile_dir: Path) -> List[CheckResult]:
    state = create_state(profile, kodi_version, profile_dir)
    old_path = list(sys.path)
    try:
        install_kodi_stubs(state)
        purge_xvault_modules()
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))

        from resources.lib import bookmarkDB, playcountDB, searchDB

        results = [
            stress_search_storage(searchDB, state, iterations),
            stress_bookmark_storage(bookmarkDB, state, iterations),
            stress_playcount_sqlite(playcountDB, state, iterations),
            atomic_pickle_failure(searchDB, state, "searchDB", "movies.pcl", lambda: searchDB.save_query("after-fault", "movies.pcl")),
            atomic_pickle_failure(
                bookmarkDB,
                state,
                "bookmarkDB",
                "bookmarks.pcl",
                lambda: bookmarkDB.save_query("after-fault", 99, "bookmarks.pcl"),
            ),
            sqlite_commit_failure(playcountDB, state),
            profile_data_budget(state),
        ]
        return results
    except Exception as exc:
        return [CheckResult("db-stress", "FAIL", "%s: %s" % (exc.__class__.__name__, exc))]
    finally:
        sys.path[:] = old_path


def run_playback_settings_check(profile: FireTvStickProfile, kodi_version: str, profile_dir: Path) -> CheckResult:
    state = create_state(profile, kodi_version, profile_dir)
    old_path = list(sys.path)
    try:
        install_kodi_stubs(state)
        purge_xvault_modules()
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))

        settings_path = state.profile_dir / "settings.xml"
        settings_path.write_text(
            '<settings version="2">\n'
            '    <setting id="hosts.mode">Autoplay</setting>\n'
            '    <setting id="default.action">2</setting>\n'
            '</settings>\n',
            encoding="utf-8",
        )

        from resources.lib import playback_settings
        setting_id = playback_settings.SETTING_ID
        legacy_setting_id = "hosts.mode"

        checks = []
        for live_value, expected in (("Verzeichnis", "1"), ("Dialog", "0"), ("Autoplay", "2")):
            state.settings[setting_id] = live_value
            actual = playback_settings.get_mode()
            checks.append("%s=>%s" % (live_value, actual))
            if actual != expected:
                return CheckResult(
                    "playback-settings",
                    "FAIL",
                    "Live-Wert %s ergab %s statt %s; checks=%s" % (live_value, actual, expected, ", ".join(checks)),
                )

        settings_path.write_text(
            '<settings version="2">\n'
            '    <setting id="hosts.mode">Verzeichnis</setting>\n'
            '</settings>\n',
            encoding="utf-8",
        )
        state.settings[setting_id] = "Autoplay"
        migrated = playback_settings.migrate_mode_setting()
        written = state.settings.get(setting_id)
        if migrated != "1" or written != "Verzeichnis":
            return CheckResult(
                "playback-settings",
                "FAIL",
                "Legacy-Migration ergab mode=%s write=%s statt 1/Verzeichnis." % (migrated, written),
            )

        settings_path.write_text(
            '<settings version="2">\n'
            '    <setting id="hosts.mode.v2" default="true">Autoplay</setting>\n'
            '</settings>\n',
            encoding="utf-8",
        )
        state.settings[setting_id] = "Verzeichnis"
        migrated = playback_settings.migrate_mode_setting()
        if migrated != "1" or state.settings.get(setting_id) != "Verzeichnis":
            return CheckResult(
                "playback-settings",
                "FAIL",
                "Default-Profilwert ueberschrieb Live-Wert: mode=%s write=%s." %
                (migrated, state.settings.get(setting_id)),
            )

        settings_path.write_text(
            '<settings version="2">\n'
            '    <setting id="hosts.mode" default="true">2</setting>\n'
            '</settings>\n',
            encoding="utf-8",
        )
        state.settings[setting_id] = ""
        migrated = playback_settings.migrate_mode_setting()
        if migrated != "2" or state.settings.get(setting_id) != "Autoplay":
            return CheckResult(
                "playback-settings",
                "FAIL",
                "Numerischer Altwert wurde nicht auf Label migriert: mode=%s write=%s." %
                (migrated, state.settings.get(setting_id)),
            )

        settings_path.write_text(
            '<settings version="2">\n'
            '    <setting id="hosts.mode">1</setting>\n'
            '</settings>\n',
            encoding="utf-8",
        )
        state.settings[setting_id] = "Autoplay"
        migrated = playback_settings.migrate_mode_setting()
        if migrated != "1" or state.settings.get(setting_id) != "Verzeichnis":
            return CheckResult(
                "playback-settings",
                "FAIL",
                "Numerischer Nicht-Autoplay-Altwert ging verloren: mode=%s write=%s legacy=%s." %
                (migrated, state.settings.get(setting_id), legacy_setting_id),
            )

        settings_path.write_text(
            '<settings version="2">\n'
            '    <setting id="hosts.mode" default="true">1</setting>\n'
            '</settings>\n',
            encoding="utf-8",
        )
        state.settings[setting_id] = "Autoplay"
        migrated = playback_settings.migrate_mode_setting()
        if migrated != "1" or state.settings.get(setting_id) != "Verzeichnis":
            return CheckResult(
                "playback-settings",
                "FAIL",
                "Default-markierter Legacy-Wert wurde nicht bewahrt: mode=%s write=%s." %
                (migrated, state.settings.get(setting_id)),
            )

        settings_path.write_text(
            '<settings version="2">\n'
            '    <setting id="hosts.mode.v2">Verzeichnis</setting>\n'
            '    <setting id="hosts.mode.v2.migrated">true</setting>\n'
            '    <setting id="hosts.mode" default="true">1</setting>\n'
            '</settings>\n',
            encoding="utf-8",
        )
        state.settings[setting_id] = "Autoplay"
        migrated = playback_settings.migrate_mode_setting()
        if migrated != "2" or state.settings.get(setting_id) != "Autoplay":
            return CheckResult(
                "playback-settings",
                "FAIL",
                "Legacy-Wert blockierte Autoplay-Wechsel: mode=%s write=%s." %
                (migrated, state.settings.get(setting_id)),
            )

        return CheckResult("playback-settings", "PASS", "Live-Wechsel und Legacy-Migration konsistent (%s)." % ", ".join(checks))
    except Exception as exc:
        return CheckResult("playback-settings", "FAIL", "%s: %s" % (exc.__class__.__name__, exc))
    finally:
        sys.path[:] = old_path


def stress_search_storage(module: Any, state: SimulationState, iterations: int) -> CheckResult:
    filename = "movies.pcl"
    for index in range(iterations):
        module.save_query("query-%04d" % index, filename)
    terms = module.getSearchTerms(filename)
    target = state.profile_dir / filename
    valid = pickle_file_valid(target)
    if not valid:
        return CheckResult("search-storage", "FAIL", "%s ist nach %d Schreibvorgaengen korrupt." % (target, iterations))
    if len(terms) != iterations:
        return CheckResult("search-storage", "FAIL", "Erwartet %d Eintraege, gefunden %d." % (iterations, len(terms)))
    return CheckResult("search-storage", "PASS", "%d Suchhistorien-Schreibvorgaenge konsistent." % iterations)


def stress_bookmark_storage(module: Any, state: SimulationState, iterations: int) -> CheckResult:
    filename = "bookmarks.pcl"
    for index in range(iterations):
        module.save_query("file-%04d" % index, index, filename)
    target = state.profile_dir / filename
    valid = pickle_file_valid(target)
    if not valid:
        return CheckResult("bookmark-storage", "FAIL", "%s ist nach %d Schreibvorgaengen korrupt." % (target, iterations))
    latest = module.get_query("file-%04d" % (iterations - 1), filename)
    if not latest:
        return CheckResult("bookmark-storage", "FAIL", "Letzter Bookmark-Eintrag fehlt.")
    return CheckResult("bookmark-storage", "PASS", "%d Bookmark-Schreibvorgaenge konsistent." % iterations)


def stress_playcount_sqlite(module: Any, state: SimulationState, iterations: int) -> CheckResult:
    for index in range(iterations):
        title = "Movie %04d" % index
        imdb = "tt%07d" % index
        module.createEntry("movie", title, title, imdb, None, None, None, None)
        module.updatePlaycount("movie", title=title, name=title, id=imdb, playcount=1)
    db_path = state.profile_dir / "playcount.db"
    integrity = sqlite_integrity(db_path)
    if integrity != "ok":
        return CheckResult("playcount-sqlite", "FAIL", "PRAGMA integrity_check: %s" % integrity)
    count = sqlite_count(db_path, "movie")
    if count != iterations:
        return CheckResult("playcount-sqlite", "FAIL", "Erwartet %d Filme, gefunden %d." % (iterations, count))
    return CheckResult("playcount-sqlite", "PASS", "%d Playcount-Transaktionen konsistent." % iterations)


def atomic_pickle_failure(module: Any, state: SimulationState, name: str, filename: str, write_after_fault: Any) -> CheckResult:
    target = state.profile_dir / filename
    if not target.exists():
        with open(target, "wb") as handle:
            pickle.dump({"baseline": True}, handle, protocol=2)
    before = target.read_bytes()
    original_replace = module.os.replace

    def failing_replace(source: str, destination: str) -> None:
        raise OSError("simulated ENOSPC during atomic replace")

    module.os.replace = failing_replace
    try:
        try:
            write_after_fault()
        except OSError:
            pass
        after = target.read_bytes()
        if after != before:
            return CheckResult("%s-atomic-write" % name, "FAIL", "Zieldatei wurde trotz Schreibfehler veraendert.")
        if not pickle_file_valid(target):
            return CheckResult("%s-atomic-write" % name, "FAIL", "Zieldatei ist nach Schreibfehler korrupt.")
        tmp = target.with_name(target.name + ".tmp")
        if tmp.exists():
            return CheckResult("%s-atomic-write" % name, "FAIL", "Temporaere Datei blieb liegen: %s" % tmp)
        return CheckResult("%s-atomic-write" % name, "PASS", "Abgebrochener Schreibvorgang laesst alte Datei intakt.")
    finally:
        module.os.replace = original_replace


def sqlite_commit_failure(module: Any, state: SimulationState) -> CheckResult:
    db_path = state.profile_dir / "playcount.db"
    before = sqlite_integrity(db_path)
    original_connect = module.db.connect

    class FaultConnection:
        def __init__(self, real: sqlite3.Connection) -> None:
            self.real = real

        def cursor(self) -> Any:
            return self.real.cursor()

        def commit(self) -> None:
            raise sqlite3.OperationalError("database or disk is full")

        def close(self) -> None:
            self.real.close()

        def __getattr__(self, name: str) -> Any:
            return getattr(self.real, name)

    def fault_connect(*args: Any, **kwargs: Any) -> FaultConnection:
        return FaultConnection(original_connect(*args, **kwargs))

    module.db.connect = fault_connect
    try:
        try:
            module.updatePlaycount("movie", title="Fault Movie", name="Fault Movie", id="tt9999999", playcount=1)
        except sqlite3.OperationalError:
            pass
    finally:
        module.db.connect = original_connect

    after = sqlite_integrity(db_path)
    if before != "ok" or after != "ok":
        return CheckResult("sqlite-commit-fault", "FAIL", "Integrity vorher=%s nachher=%s." % (before, after))
    return CheckResult("sqlite-commit-fault", "PASS", "Simulierter voller Speicher beschaedigt playcount.db nicht.")


def profile_data_budget(state: SimulationState) -> CheckResult:
    size = directory_size(state.profile_dir)
    budget = profile_data_budget_bytes(state.profile)
    if size > budget:
        return CheckResult(
            "profile-data-budget",
            "WARN",
            "Profil-Daten %d KB liegen ueber synthetischem Budget %d KB." % (size // 1024, budget // 1024),
        )
    return CheckResult(
        "profile-data-budget",
        "PASS",
        "Profil-Daten %d KB innerhalb synthetischem Budget %d KB." % (size // 1024, budget // 1024),
    )


def profile_data_budget_bytes(profile: FireTvStickProfile) -> int:
    if profile.storage_gb <= 8 and profile.ram_mb < 2048:
        return 2 * 1024 * 1024
    if profile.storage_gb <= 8:
        return 4 * 1024 * 1024
    return 8 * 1024 * 1024


def pickle_file_valid(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            pickle.load(handle)
        return True
    except Exception:
        return False


def sqlite_integrity(path: Path) -> str:
    if not path.exists():
        return "missing"
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        return str(row[0]) if row else "no-result"
    finally:
        conn.close()


def sqlite_count(path: Path, table: str) -> int:
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()
        return int(row[0])
    finally:
        conn.close()


def directory_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def profile_limit_report(profile: FireTvStickProfile) -> List[CheckResult]:
    results: List[CheckResult] = []
    if profile.android_api <= 22:
        results.append(CheckResult("android-api", "RISK", "%s / API %d ist ein sehr altes Kodi-Ziel." % (profile.fire_os, profile.android_api)))
    elif profile.android_api <= 25:
        results.append(CheckResult("android-api", "WARN", "%s / API %d: Legacy-Grenze, besonders relevant fuer AFTMM." % (profile.fire_os, profile.android_api)))
    else:
        results.append(CheckResult("android-api", "PASS", "%s / API %d." % (profile.fire_os, profile.android_api)))

    if profile.ram_mb < 2048:
        results.append(CheckResult("ram", "WARN", "%d MB RAM: Datenbank- und Listenoperationen unter Speicherdruck testen." % profile.ram_mb))
    else:
        results.append(CheckResult("ram", "PASS", "%d MB RAM." % profile.ram_mb))

    if profile.storage_gb <= 8:
        results.append(CheckResult("storage", "WARN", "%d GB Storage: abgebrochene Schreibvorgaenge und volle Profile simulieren." % profile.storage_gb))
    else:
        results.append(CheckResult("storage", "PASS", "%d GB Storage." % profile.storage_gb))

    if profile.abi_bits == 32:
        results.append(CheckResult("abi", "INFO", "32-bit ARM-Ziel: native Kodi-Abhaengigkeiten separat pruefen."))

    if "AV1" not in profile.codecs:
        results.append(CheckResult("codec", "INFO", "Kein AV1: H.264/H.265-HLS-Fallbacks pruefen."))

    if profile.profile_id == "fire-tv-stick-4k-1st-gen-2018":
        results.append(
            CheckResult(
                "aftmm-focus",
                "WARN",
                "AFTMM kombiniert 4K, Fire OS 6/API 25, 1.5 GB RAM und 8 GB Storage: DB-Stresslauf empfohlen.",
            )
        )
    return results


def temp_profile_dir(keep: bool, profile: FireTvStickProfile) -> Tuple[Path, Optional[tempfile.TemporaryDirectory]]:
    if keep:
        path = ROOT / "htmlcache" / "firetv-tests" / profile.profile_id
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
        return path, None
    temp = tempfile.TemporaryDirectory(prefix="xvault-firetv-")
    return Path(temp.name), temp


def run_all(profile: FireTvStickProfile, iterations: int, kodi_version: str, keep: bool) -> Tuple[Path, List[CheckResult]]:
    profile_dir, temp = temp_profile_dir(keep, profile)
    results: List[CheckResult] = []
    results.extend(profile_limit_report(profile))
    results.append(run_kodi_smoke(profile, "root", kodi_version, profile_dir))
    results.append(run_kodi_smoke(profile, "movieNavigator", kodi_version, profile_dir))
    results.append(run_playback_settings_check(profile, kodi_version, profile_dir))
    results.extend(run_db_stress(profile, iterations, kodi_version, profile_dir))
    if temp is not None:
        temp.cleanup()
    return profile_dir, results


def format_results(profile: FireTvStickProfile, results: Sequence[CheckResult], profile_dir: Optional[Path] = None) -> str:
    lines = [
        "Fire-TV/Kodi-xVAULT-Test: %s (%s, %s, %d MB RAM)"
        % (profile.name, profile.build_model, profile.fire_os, profile.ram_mb)
    ]
    if profile_dir is not None:
        lines.append("Profilpfad: %s" % profile_dir)
    lines.append("")
    for result in results:
        lines.append("[%s] %s - %s" % (result.status, result.name, result.details))
    return "\n".join(lines)


def has_failures(results: Sequence[CheckResult]) -> bool:
    return any(result.status == "FAIL" for result in results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Testet xVAULT in einer Kodi-Simulation mit Android-basierten Fire-TV-Stick-Grenzen."
    )
    add_runtime_args(parser, defaults=True)

    subparsers = parser.add_subparsers(dest="command", required=True)
    limits = subparsers.add_parser("limits", help="Explizite Profilgrenzen anzeigen.")
    add_runtime_args(limits)

    smoke = subparsers.add_parser("smoke", help="xVAULT in Kodi-Simulation starten.")
    add_runtime_args(smoke)
    smoke.add_argument("--action", default="root", help="xVAULT action, z.B. root oder movieNavigator.")

    db_stress = subparsers.add_parser("db-stress", help="Lokale Datenbanken unter Fire-TV-Profilgrenzen testen.")
    add_runtime_args(db_stress)
    all_parser = subparsers.add_parser("all", help="Limits, Kodi-Smoke und DB-Stress zusammen ausfuehren.")
    add_runtime_args(all_parser)
    return parser


def add_runtime_args(parser: argparse.ArgumentParser, defaults: bool = False) -> None:
    default = None if defaults else argparse.SUPPRESS
    parser.add_argument(
        "--profile",
        default="aftmm" if defaults else default,
        help="Fire-TV-Stick-Profil, Alias oder Build-Model. Standard: aftmm (Fire TV Stick 4K 1st Gen).",
    )
    parser.add_argument("--kodi-version", default="21.2" if defaults else default, help="Simulierte Kodi-Version.")
    parser.add_argument(
        "--iterations",
        type=int,
        default=350 if defaults else default,
        help="DB-Stress-Iterationen.",
    )
    parser.add_argument(
        "--keep-profile",
        action="store_true",
        default=False if defaults else default,
        help="Temporaeres Testprofil behalten.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False if defaults else default,
        help="Ergebnis als JSON ausgeben.",
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    profile = find_profile(args.profile)
    profile_dir, temp = temp_profile_dir(args.keep_profile, profile)
    try:
        if args.command == "limits":
            results = profile_limit_report(profile)
        elif args.command == "smoke":
            results = [run_kodi_smoke(profile, args.action, args.kodi_version, profile_dir)]
        elif args.command == "db-stress":
            results = run_db_stress(profile, args.iterations, args.kodi_version, profile_dir)
        elif args.command == "all":
            results = []
            results.extend(profile_limit_report(profile))
            results.append(run_kodi_smoke(profile, "root", args.kodi_version, profile_dir))
            results.append(run_kodi_smoke(profile, "movieNavigator", args.kodi_version, profile_dir))
            results.append(run_playback_settings_check(profile, args.kodi_version, profile_dir))
            results.extend(run_db_stress(profile, args.iterations, args.kodi_version, profile_dir))
        else:
            raise ValueError("Unknown command: %s" % args.command)

        if args.json:
            payload = {
                "profile": profile.profile_id,
                "profile_dir": str(profile_dir),
                "results": [result.__dict__ for result in results],
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(format_results(profile, results, profile_dir))
        return 1 if has_failures(results) else 0
    finally:
        if temp is not None:
            temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
