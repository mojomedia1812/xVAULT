from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADDON_XML = ROOT / "addon.xml"

AMAZON_DEVICE_SPECS_URL = (
    "https://developer.amazon.com/docs/device-specs/"
    "device-specifications-fire-tv-streaming-media-player.html"
)
AMAZON_IDENTIFY_URL = (
    "https://developer.amazon.com/docs/device-specs/identify-fire-tv-devices.html"
)
AMAZON_AVD_GUIDE_URL = (
    "https://developer.amazon.com/docs/fire-tablets/"
    "ft-testing-without-an-amazon-device.html"
)


@dataclass(frozen=True)
class FireTvStickProfile:
    profile_id: str
    aliases: Sequence[str]
    name: str
    release_year: int
    build_model: str
    fire_os: str
    android_version: str
    android_api: int
    abi_bits: int
    ram_mb: int
    storage_gb: int
    cpu: str
    gpu: str
    max_video: str
    hdr: Sequence[str]
    codecs: Sequence[str]
    network: Sequence[str]
    notes: Sequence[str]

    @property
    def family(self) -> str:
        if self.android_api >= 30:
            return "modern"
        if self.android_api >= 28:
            return "supported-old"
        if self.android_api >= 25:
            return "legacy"
        return "very-legacy"


PROFILES: Sequence[FireTvStickProfile] = (
    FireTvStickProfile(
        profile_id="fire-tv-stick-4k-plus-2025",
        aliases=("4k-plus", "aftma08c15", "plus-2025"),
        name="Fire TV Stick 4K Plus (2025)",
        release_year=2025,
        build_model="AFTMA08C15",
        fire_os="Fire OS 8",
        android_version="Android 11",
        android_api=30,
        abi_bits=32,
        ram_mb=2048,
        storage_gb=8,
        cpu="4x ARM Cortex-A55 up to 1.7 GHz",
        gpu="GE9215 up to 650 MHz",
        max_video="4K 60fps",
        hdr=("HDR10", "HDR10+", "HLG", "Dolby Vision"),
        codecs=("H.265/HEVC", "H.264", "VP9", "AV1", "MPEG-2", "MPEG-4"),
        network=("Wi-Fi 6", "Ethernet adapter"),
        notes=("Current Android-based 4K stick profile.",),
    ),
    FireTvStickProfile(
        profile_id="fire-tv-stick-4k-max-2nd-gen-2023",
        aliases=("4k-max-2", "4k-max-2023", "aftkrt"),
        name="Fire TV Stick 4K Max - 2nd Gen (2023)",
        release_year=2023,
        build_model="AFTKRT",
        fire_os="Fire OS 8",
        android_version="Android 11",
        android_api=30,
        abi_bits=32,
        ram_mb=2048,
        storage_gb=16,
        cpu="4x ARM Cortex-A55 up to 2.0 GHz",
        gpu="GE9215 up to 850 MHz",
        max_video="4K 60fps",
        hdr=("HDR10", "HDR10+", "HLG", "Dolby Vision"),
        codecs=("H.265/HEVC", "H.264", "VP9", "AV1", "MPEG-2", "MPEG-4"),
        network=("Wi-Fi 6E", "Ethernet adapter"),
        notes=("Best stress profile for xVAULT on Fire OS 8 sticks.",),
    ),
    FireTvStickProfile(
        profile_id="fire-tv-stick-4k-2nd-gen-2023",
        aliases=("4k-2", "4k-2023", "aftkm"),
        name="Fire TV Stick 4K - 2nd Gen (2023)",
        release_year=2023,
        build_model="AFTKM",
        fire_os="Fire OS 8",
        android_version="Android 11",
        android_api=30,
        abi_bits=32,
        ram_mb=2048,
        storage_gb=8,
        cpu="4x ARM Cortex-A55 up to 1.7 GHz",
        gpu="GE9215 up to 650 MHz",
        max_video="4K 60fps",
        hdr=("HDR10", "HDR10+", "HLG", "Dolby Vision"),
        codecs=("H.265/HEVC", "H.264", "VP9", "AV1", "MPEG-2", "MPEG-4"),
        network=("Wi-Fi 6", "Ethernet adapter"),
        notes=("Good default target for current Fire OS 8 compatibility.",),
    ),
    FireTvStickProfile(
        profile_id="fire-tv-stick-4k-max-1st-gen-2021",
        aliases=("4k-max-1", "4k-max-2021", "aftka"),
        name="Fire TV Stick 4K Max - 1st Gen (2021)",
        release_year=2021,
        build_model="AFTKA",
        fire_os="Fire OS 7",
        android_version="Android 9",
        android_api=28,
        abi_bits=32,
        ram_mb=2048,
        storage_gb=8,
        cpu="Quad-core 1.8 GHz",
        gpu="IMG GE9215 750 MHz",
        max_video="4K 60fps",
        hdr=("HDR10", "HDR10+", "HLG", "Dolby Vision"),
        codecs=("H.265/HEVC", "H.264", "VP9", "MPEG-2", "MPEG-4"),
        network=("Wi-Fi 6", "Ethernet adapter"),
        notes=("Fast Fire OS 7 profile, useful for regression checks below API 30.",),
    ),
    FireTvStickProfile(
        profile_id="fire-tv-stick-hd-2024",
        aliases=("hd-2024", "aftss-hd", "stick-hd"),
        name="Fire TV Stick HD Alexa Voice Remote (2024)",
        release_year=2024,
        build_model="AFTSS",
        fire_os="Fire OS 7",
        android_version="Android 9",
        android_api=28,
        abi_bits=32,
        ram_mb=1024,
        storage_gb=8,
        cpu="Quad-core 1.7 GHz",
        gpu="IMG GE8300",
        max_video="1080p 60fps",
        hdr=("HDR10", "HDR10+", "HLG"),
        codecs=("H.265/HEVC", "H.264", "VP9", "MPEG-2", "MPEG-4"),
        network=("802.11 a/b/g/n/ac", "Ethernet adapter"),
        notes=("Modern HD stick with low RAM pressure profile.",),
    ),
    FireTvStickProfile(
        profile_id="fire-tv-stick-3rd-gen-2020",
        aliases=("stick-3", "3rd-gen", "aftsss"),
        name="Fire TV Stick - 3rd Gen (2020)",
        release_year=2020,
        build_model="AFTSSS",
        fire_os="Fire OS 7",
        android_version="Android 9",
        android_api=28,
        abi_bits=32,
        ram_mb=1024,
        storage_gb=8,
        cpu="Quad-core 1.7 GHz",
        gpu="IMG GE8300",
        max_video="1080p 60fps",
        hdr=("HDR10", "HDR10+", "HLG"),
        codecs=("H.265/HEVC", "H.264", "VP9", "MPEG-2", "MPEG-4"),
        network=("802.11 a/b/g/n/ac", "Ethernet adapter"),
        notes=("Common 1080p Fire OS 7 baseline.",),
    ),
    FireTvStickProfile(
        profile_id="fire-tv-stick-lite-1st-gen-2020",
        aliases=("lite", "lite-2020", "aftss-lite"),
        name="Fire TV Stick Lite - 1st Gen (2020)",
        release_year=2020,
        build_model="AFTSS",
        fire_os="Fire OS 7",
        android_version="Android 9",
        android_api=28,
        abi_bits=32,
        ram_mb=1024,
        storage_gb=8,
        cpu="Quad-core 1.7 GHz",
        gpu="IMG GE8300",
        max_video="1080p 60fps",
        hdr=("HDR10", "HDR10+", "HLG"),
        codecs=("H.265/HEVC", "H.264", "VP9", "MPEG-2", "MPEG-4"),
        network=("802.11 a/b/g/n/ac", "Ethernet adapter"),
        notes=("Same build model as Fire TV Stick HD 2024, but different retail line.",),
    ),
    FireTvStickProfile(
        profile_id="fire-tv-stick-4k-1st-gen-2018",
        aliases=("4k-1", "4k-2018", "aftmm"),
        name="Fire TV Stick 4K - 1st Gen (2018)",
        release_year=2018,
        build_model="AFTMM",
        fire_os="Fire OS 6",
        android_version="Android 7.1",
        android_api=25,
        abi_bits=32,
        ram_mb=1536,
        storage_gb=8,
        cpu="Quad-core 1.7 GHz",
        gpu="IMG GE8300",
        max_video="4K 60fps",
        hdr=("HDR10", "HDR10+", "HLG", "Dolby Vision"),
        codecs=("H.265/HEVC", "H.264", "VP9", "MPEG-2", "MPEG-4"),
        network=("802.11 a/b/g/n/ac", "Ethernet adapter"),
        notes=("Important Fire OS 6 compatibility floor for 4K devices.",),
    ),
    FireTvStickProfile(
        profile_id="fire-tv-stick-2nd-gen-2016",
        aliases=("stick-2", "2nd-gen", "aftt"),
        name="Fire TV Stick - 2nd Gen (2016-2019)",
        release_year=2016,
        build_model="AFTT",
        fire_os="Fire OS 5",
        android_version="Android 5.1",
        android_api=22,
        abi_bits=32,
        ram_mb=1024,
        storage_gb=8,
        cpu="Quad-core ARM 1.3 GHz",
        gpu="Mali-450 MP4",
        max_video="1080p 30fps",
        hdr=(),
        codecs=("H.265/HEVC", "H.264", "MPEG-2", "MPEG-4"),
        network=("802.11 a/b/g/n/ac", "wireless ADB"),
        notes=("Very old Fire OS 5 profile; use as lowest practical stick check.",),
    ),
    FireTvStickProfile(
        profile_id="fire-tv-stick-basic-edition-2017",
        aliases=("basic", "basic-2017"),
        name="Fire TV Stick - Basic Edition (2017)",
        release_year=2017,
        build_model="AFTT",
        fire_os="Fire OS 5",
        android_version="Android 5.1",
        android_api=22,
        abi_bits=32,
        ram_mb=1024,
        storage_gb=8,
        cpu="Quad-core ARM 1.3 GHz",
        gpu="Mali-450 MP4",
        max_video="1080p 30fps",
        hdr=(),
        codecs=("H.265/HEVC", "H.264", "MPEG-4"),
        network=("802.11 a/b/g/n/ac", "wireless ADB"),
        notes=("Hardware-like twin of 2nd Gen, with simplified Fire TV UI.",),
    ),
    FireTvStickProfile(
        profile_id="fire-tv-stick-1st-gen-2014",
        aliases=("stick-1", "1st-gen", "aftm"),
        name="Fire TV Stick - 1st Gen (2014)",
        release_year=2014,
        build_model="AFTM",
        fire_os="Fire OS 5",
        android_version="Android 5.1",
        android_api=22,
        abi_bits=32,
        ram_mb=1024,
        storage_gb=8,
        cpu="Dual-core ARM Cortex-A9 up to 1.0 GHz",
        gpu="Broadcom VideoCore IV",
        max_video="1080p 30fps",
        hdr=(),
        codecs=("H.264", "MPEG-2", "MPEG-4"),
        network=("802.11 a/b/g/n",),
        notes=("Oldest stick profile; expect Kodi/runtime constraints.",),
    ),
)


def profile_index() -> Dict[str, FireTvStickProfile]:
    index: Dict[str, FireTvStickProfile] = {}
    for profile in PROFILES:
        keys = (profile.profile_id, profile.build_model.lower(), profile.name.lower())
        for key in keys + tuple(profile.aliases):
            index[normalize_key(key)] = profile
    return index


def normalize_key(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def find_profile(value: str) -> FireTvStickProfile:
    key = normalize_key(value)
    index = profile_index()
    if key in index:
        return index[key]
    matches = [profile for profile in PROFILES if key in profile.profile_id]
    if len(matches) == 1:
        return matches[0]
    fail("Unbekanntes Profil '%s'. Nutze 'list' fuer gueltige IDs." % value)


def format_table(rows: Sequence[Sequence[str]]) -> str:
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    lines = []
    for row_index, row in enumerate(rows):
        line = "  ".join(row[column].ljust(widths[column]) for column in range(len(row)))
        lines.append(line.rstrip())
        if row_index == 0:
            lines.append("  ".join("-" * width for width in widths).rstrip())
    return "\n".join(lines)


def list_profiles() -> str:
    rows = [("ID", "Fire OS", "API", "RAM", "Video")]
    for profile in PROFILES:
        rows.append(
            (
                profile.profile_id,
                profile.fire_os,
                str(profile.android_api),
                "%d MB" % profile.ram_mb,
                profile.max_video,
            )
        )
    return format_table(rows)


def profile_to_json(profile: FireTvStickProfile) -> str:
    data = asdict(profile)
    data["source"] = AMAZON_DEVICE_SPECS_URL
    return json.dumps(data, indent=2, sort_keys=True)


def profile_summary(profile: FireTvStickProfile) -> str:
    rows = (
        ("Name", profile.name),
        ("ID", profile.profile_id),
        ("Build model", profile.build_model),
        ("OS", "%s, %s / API %d" % (profile.fire_os, profile.android_version, profile.android_api)),
        ("ABI", "%d-bit" % profile.abi_bits),
        ("RAM", "%d MB" % profile.ram_mb),
        ("Storage", "%d GB" % profile.storage_gb),
        ("CPU", profile.cpu),
        ("GPU", profile.gpu),
        ("Video", profile.max_video),
        ("HDR", ", ".join(profile.hdr) if profile.hdr else "None"),
        ("Codecs", ", ".join(profile.codecs)),
        ("Network", ", ".join(profile.network)),
        ("Notes", " ".join(profile.notes)),
        ("Source", AMAZON_DEVICE_SPECS_URL),
    )
    return "\n".join("%-12s %s" % (label + ":", value) for label, value in rows)


def simulated_properties(profile: FireTvStickProfile) -> Dict[str, str]:
    return {
        "ro.product.manufacturer": "Amazon",
        "ro.product.model": profile.build_model,
        "ro.product.name": profile.profile_id,
        "ro.hardware.fire_tv": "true",
        "ro.build.version.release": profile.android_version.replace("Android ", ""),
        "ro.build.version.sdk": str(profile.android_api),
        "ro.product.cpu.abi": "armeabi-v7a" if profile.abi_bits == 32 else "arm64-v8a",
        "persist.sys.display.max_video": profile.max_video,
        "persist.sys.fire_os": profile.fire_os,
        "persist.sys.ram_mb": str(profile.ram_mb),
        "persist.sys.storage_gb": str(profile.storage_gb),
    }


def format_properties(profile: FireTvStickProfile, output_format: str) -> str:
    props = simulated_properties(profile)
    if output_format == "json":
        return json.dumps(props, indent=2, sort_keys=True)
    if output_format == "env":
        return "\n".join(
            'set %s="%s"' % (property_to_env_name(key), value)
            for key, value in sorted(props.items())
        )
    return "\n".join("[%s]: [%s]" % item for item in sorted(props.items()))


def property_to_env_name(value: str) -> str:
    return "FIRETV_" + value.upper().replace(".", "_").replace("-", "_")


def avd_plan(profile: FireTvStickProfile) -> str:
    width, height = recommended_resolution(profile)
    device_name = "xVAULT %s API %d" % (profile.build_model, profile.android_api)
    android_tv_note = (
        "Amazon beschreibt diesen AVD-Workflow fuer Fire Tablets und weist darauf hin, "
        "dass er Fire TV nicht echt simuliert. Fuer Fire TV Sticks ist das hier deshalb "
        "ein Android-TV-Naeherungsprofil, kein FireOS-Emulator."
    )
    lines = [
        "AVD-Testprofil: %s" % profile.name,
        "",
        android_tv_note,
        "",
        "Android Studio > Tools > Device Manager > Create device > New Hardware Profile",
        "",
        "Device Name: %s" % device_name,
        "Device Type: TV",
        "Screen: %s (%dx%d)" % (recommended_screen_size(profile), width, height),
        "Memory: %d MB" % profile.ram_mb,
        "Input: D-pad/remote-first, no touch assumptions",
        "Cameras: none",
        "Sensors: off",
        "Navigation: hardware/remote keys",
        "RAM pressure target: %s" % ram_pressure_label(profile),
        "",
        "Create Virtual Device",
        "",
        "System image: Android TV / API %d when available" % profile.android_api,
        "ABI: emulator image x86_64 is OK; target device ABI remains %d-bit ARM" % profile.abi_bits,
        "Services: no Google Play or Amazon services assumptions for xVAULT checks",
        "",
        "Suggested ADB smoke keys",
        "",
        "adb shell input keyevent KEYCODE_DPAD_DOWN",
        "adb shell input keyevent KEYCODE_DPAD_CENTER",
        "adb shell input keyevent KEYCODE_BACK",
        "adb shell input keyevent KEYCODE_MEDIA_PLAY_PAUSE",
        "",
        "What this catches",
        "",
        "- Kodi navigation with remote-only input",
        "- UI density and 1080p/4K layout pressure",
        "- low-RAM behavior for menus, source lists and HLS buffering",
        "- Android API compatibility around %s" % profile.fire_os,
        "",
        "What it cannot catch",
        "",
        "- Amazon Launcher/Appstore/Alexa behavior",
        "- Fire-TV-specific media pipeline and DRM behavior",
        "- real hardware decoder quirks",
        "- exact FireOS firmware behavior",
        "",
        "Sources:",
        AMAZON_AVD_GUIDE_URL,
        AMAZON_DEVICE_SPECS_URL,
    ]
    return "\n".join(lines)


def recommended_resolution(profile: FireTvStickProfile) -> Sequence[int]:
    if profile.max_video.startswith("4K"):
        return (3840, 2160)
    return (1920, 1080)


def recommended_screen_size(profile: FireTvStickProfile) -> str:
    if profile.max_video.startswith("4K"):
        return "55 inch TV class"
    return "40 inch TV class"


def ram_pressure_label(profile: FireTvStickProfile) -> str:
    if profile.ram_mb <= 1024:
        return "high"
    if profile.ram_mb < 2048:
        return "medium"
    return "normal"


def load_addon_requires(addon_xml: Path) -> Dict[str, str]:
    if not addon_xml.is_file():
        fail("addon.xml nicht gefunden: %s" % addon_xml)
    root = ET.parse(str(addon_xml)).getroot()
    requires = root.find("requires")
    imports: Dict[str, str] = {}
    if requires is None:
        return imports
    for element in requires.findall("import"):
        addon = element.attrib.get("addon", "").strip()
        if addon:
            imports[addon] = element.attrib.get("version", "").strip()
    return imports


def check_profile(profile: FireTvStickProfile, addon_xml: Path) -> List[str]:
    imports = load_addon_requires(addon_xml)
    messages: List[str] = []

    messages.append("Profil: %s (%s, API %d)" % (profile.name, profile.fire_os, profile.android_api))
    messages.append("Addon:  %s" % addon_xml)

    xbmc_python = imports.get("xbmc.python")
    if xbmc_python:
        messages.append("[OK] xVAULT deklariert xbmc.python %s." % xbmc_python)
        messages.append("[INFO] Das prueft Kodi-Kompatibilitaet, nicht direkt Fire-OS-Kompatibilitaet.")
    else:
        messages.append("[WARN] Kein xbmc.python-Import in addon.xml gefunden.")

    if profile.android_api >= 30:
        messages.append("[OK] Fire OS 8 / API 30: modernes Android-basiertes Fire-TV-Ziel.")
    elif profile.android_api >= 28:
        messages.append("[OK] Fire OS 7 / API 28: wichtiges Android-9-Ziel fuer breite Stick-Kompatibilitaet.")
    elif profile.android_api >= 25:
        messages.append("[WARN] Fire OS 6 / API 25: Legacy-Ziel; Kodi-Version und TLS-Verhalten separat testen.")
    else:
        messages.append("[RISK] Fire OS 5 / API 22: sehr altes Ziel; aktuelle Kodi-Versionen koennen dort fehlen.")

    if profile.ram_mb <= 1024:
        messages.append("[RISK] Nur %d MB RAM: Menues, grosse Quellenlisten und HLS-Puffer klein halten." % profile.ram_mb)
    elif profile.ram_mb < 2048:
        messages.append("[WARN] %d MB RAM: 4K/HLS und grosse Dialoglisten gezielt testen." % profile.ram_mb)
    else:
        messages.append("[OK] %d MB RAM: ausreichend fuer normale xVAULT-Workflows." % profile.ram_mb)

    if profile.abi_bits == 32:
        messages.append("[INFO] 32-bit ABI: reines Python-Addon ist unkritisch; native Kodi-Abhaengigkeiten pruefen.")

    optional = sorted(addon for addon, version in imports.items() if addon.startswith("inputstream."))
    if optional:
        messages.append("[INFO] InputStream-Abhaengigkeiten: %s." % ", ".join(optional))

    if "AV1" not in profile.codecs:
        messages.append("[INFO] Kein AV1-Profil: H.264/H.265-HLS als stabile Fallbacks bevorzugen.")

    messages.append("Quelle: %s" % AMAZON_DEVICE_SPECS_URL)
    return messages


def matrix(addon_xml: Path) -> str:
    rows = [("ID", "OS/API", "RAM", "Status", "Kurzbefund")]
    for profile in PROFILES:
        status, note = profile_status(profile)
        rows.append(
            (
                profile.profile_id,
                "%s/%d" % (profile.fire_os.replace("Fire OS ", "F"), profile.android_api),
                "%d MB" % profile.ram_mb,
                status,
                note,
            )
        )
    header = "Kompatibilitaetsmatrix fuer %s\n" % addon_xml
    return header + format_table(rows)


def profile_status(profile: FireTvStickProfile) -> Sequence[str]:
    if profile.android_api <= 22:
        return ("RISK", "Fire OS 5 und aktuelle Kodi-Builds manuell verifizieren")
    if profile.ram_mb <= 1024:
        return ("WATCH", "RAM-Druck bei Listen, Autoplay und HLS-Puffer testen")
    if profile.android_api <= 25:
        return ("WATCH", "Legacy-API und TLS/Codec-Verhalten testen")
    return ("OK", "Guter Android-basierter Fire-TV-Testkandidat")


def export_profiles(path: Path) -> str:
    data = {
        "source": AMAZON_DEVICE_SPECS_URL,
        "identify_source": AMAZON_IDENTIFY_URL,
        "avd_guide_source": AMAZON_AVD_GUIDE_URL,
        "profiles": [asdict(profile) for profile in PROFILES],
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return "Profile exportiert: %s" % path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Simuliert Android-basierte Fire-OS-Profile fuer Fire-TV-Stick-Varianten. "
            "Es werden keine FireOS-ROMs oder Amazon-Dienste emuliert."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="Alle Android-basierten Stick-Profile anzeigen.")

    show_parser = subparsers.add_parser("show", help="Ein Profil anzeigen.")
    show_parser.add_argument("profile", help="Profil-ID, Alias oder Build-Model.")
    show_parser.add_argument("--json", action="store_true", help="Als JSON ausgeben.")

    props_parser = subparsers.add_parser("properties", help="Simulierte Android-Systemwerte ausgeben.")
    props_parser.add_argument("profile", help="Profil-ID, Alias oder Build-Model.")
    props_parser.add_argument(
        "--format",
        choices=("props", "env", "json"),
        default="props",
        help="Ausgabeformat.",
    )

    avd_parser = subparsers.add_parser(
        "avd-plan",
        help="Android-TV-AVD-Testprofil nach Amazon-AVD-Vorbild ausgeben.",
    )
    avd_parser.add_argument("profile", help="Profil-ID, Alias oder Build-Model.")

    check_parser = subparsers.add_parser("check", help="xVAULT gegen ein Fire-TV-Stick-Profil pruefen.")
    check_parser.add_argument("profile", help="Profil-ID, Alias oder Build-Model.")
    check_parser.add_argument("--addon", type=Path, default=DEFAULT_ADDON_XML, help="Pfad zu addon.xml.")

    matrix_parser = subparsers.add_parser("matrix", help="Alle Profile als Kurzmatrix pruefen.")
    matrix_parser.add_argument("--addon", type=Path, default=DEFAULT_ADDON_XML, help="Pfad zu addon.xml.")

    export_parser = subparsers.add_parser("export-json", help="Profilkatalog als JSON exportieren.")
    export_parser.add_argument("path", type=Path, help="Zielpfad fuer JSON.")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        print(list_profiles())
    elif args.command == "show":
        profile = find_profile(args.profile)
        print(profile_to_json(profile) if args.json else profile_summary(profile))
    elif args.command == "properties":
        print(format_properties(find_profile(args.profile), args.format))
    elif args.command == "avd-plan":
        print(avd_plan(find_profile(args.profile)))
    elif args.command == "check":
        for line in check_profile(find_profile(args.profile), args.addon):
            print(line)
    elif args.command == "matrix":
        print(matrix(args.addon))
    elif args.command == "export-json":
        print(export_profiles(args.path))
    else:
        parser.print_help()
        return 2
    return 0


def fail(message: str) -> None:
    print("firetv-stick-simulator: %s" % message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    raise SystemExit(main())
