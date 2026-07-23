from pathlib import Path
import hashlib
import html
import re
import xml.etree.ElementTree as ET
import shutil
import time
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parent
SITE_URL = "http://xvault.ddnss.de/"
LEGACY_SITE_URL = "https://mojomedia1812.github.io/xVAULT/"
ADDON = ET.parse(PROJECT_DIR / "addon.xml").getroot()
ADDON_ID = ADDON.attrib["id"]
VERSION = ADDON.attrib["version"]
ZIP_NAME = f"{ADDON_ID}-{VERSION}.zip"
REPOSITORY_TEMPLATE = PROJECT_DIR / "resources" / "repository" / "addon.xml"
REPOSITORY = ET.parse(REPOSITORY_TEMPLATE).getroot()
REPOSITORY_ID = REPOSITORY.attrib["id"]
REPOSITORY_VERSION = REPOSITORY.attrib["version"]
REPOSITORY_ZIP_NAME = f"{REPOSITORY_ID}-{REPOSITORY_VERSION}.zip"
REPOSITORY_DIRECT_ZIP_NAME = f"{REPOSITORY_ID}.zip"
DOWNLOAD_OUTPUT = PROJECT_DIR / "docs" / "downloads" / ZIP_NAME
REPOSITORY_PLUGIN_OUTPUT = PROJECT_DIR / "docs" / "zips" / ADDON_ID / ZIP_NAME
REPOSITORY_OUTPUT = PROJECT_DIR / "docs" / "zips" / REPOSITORY_ID / REPOSITORY_ZIP_NAME
REPOSITORY_DIRECT_OUTPUT = PROJECT_DIR / "docs" / REPOSITORY_DIRECT_ZIP_NAME
REPOSITORY_VERSIONED_DIRECT_OUTPUT = PROJECT_DIR / "docs" / REPOSITORY_ZIP_NAME
ADDON_INDEX_DIR = PROJECT_DIR / "docs" / ADDON_ID
REPOSITORY_INDEX_DIR = PROJECT_DIR / "docs" / REPOSITORY_ID
ADDON_INDEX_OUTPUT = ADDON_INDEX_DIR / ZIP_NAME
REPOSITORY_INDEX_OUTPUT = REPOSITORY_INDEX_DIR / REPOSITORY_ZIP_NAME
ADDONS_XML = PROJECT_DIR / "docs" / "addons.xml"
CHANGELOG = PROJECT_DIR / "CHANGELOG.txt"
RELEASE_NOTES_LIMIT = 5
DOWNLOAD_ARCHIVE_KEEP = 2
UMAMI_TRACKING = """  <script
    defer
    src="https://cloud.umami.is/script.js"
    data-website-id="9a7c0b38-aea1-468a-bccc-e258aeeb365d"
    data-domains="xvault.ddnss.de"
    data-do-not-track="true"
    data-exclude-search="true">
  </script>"""
UMAMI_SCRIPT_PATTERN = r"\s*<script\b(?=[^>]*cloud\.umami\.is/script\.js).*?</script>"
UMAMI_PIXEL_PATTERN = r"\s*<img\b(?=[^>]*cloud\.umami\.is/p/)[^>]*>\s*"
OUTPUTS = (
    REPO_DIR / ZIP_NAME,
    DOWNLOAD_OUTPUT,
    REPOSITORY_PLUGIN_OUTPUT,
)

EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    "docs",
    "api",
    "backups",
    "cookies",
    "scrapers_source",
    "stream-link-auditor",
    "supabase",
    "tools",
    ".pytest_cache",
    ".venv",
}
EXCLUDED_FILES = {
    ".gitignore",
    "DEPENDENCIES.md",
    "README.md",
}
EXCLUDED_RELATIVE = {
    Path("resources/media/_movies-search.png"),
    Path("resources/media/_series-search.png"),
    Path("resources/media/box-office.png"),
    Path("resources/media/downloads.png"),
    Path("resources/media/highly-rated.png"),
    Path("resources/media/in-theaters.png"),
    Path("resources/media/most-popular.png"),
    Path("resources/media/most-voted.png"),
    Path("resources/media/plugin-info.png"),
    Path("resources/media/resolveurl.png"),
    Path("resources/media/tmdb_search.png"),
    Path("resources/media/tools.png"),
    Path("resources/media/url.png"),
    Path("sites/README.md"),
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".zip",
}


def addon_files():
    for path in PROJECT_DIR.rglob("*"):
        relative = path.relative_to(PROJECT_DIR)
        if not path.is_file():
            continue
        if relative in EXCLUDED_RELATIVE:
            continue
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in EXCLUDED_FILES or path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        yield path, relative


def build(output):
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for source, relative in addon_files():
            archive_name = (Path(ADDON_ID) / relative).as_posix()
            archive.write(source, archive_name)


def validate(output):
    with ZipFile(output) as archive:
        names = archive.namelist()

    expected_addon = f"{ADDON_ID}/addon.xml"
    if expected_addon not in names:
        raise RuntimeError(f"{expected_addon} fehlt im ZIP")
    if any(not name.startswith(f"{ADDON_ID}/") for name in names):
        raise RuntimeError("ZIP enthält Dateien außerhalb des Add-on-Wurzelordners")
    if any("\\" in name for name in names):
        raise RuntimeError("ZIP enthält nicht Kodi-konforme Backslash-Pfade")
    if any(name.startswith(f"{ADDON_ID}/docs/") for name in names):
        raise RuntimeError("Website-Dateien wurden in das Add-on-Paket aufgenommen")


def build_repository_zip(output):
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(f"{REPOSITORY_ID}/addon.xml", _repository_addon_xml())
        archive.write(PROJECT_DIR / "resources" / "icon.png", f"{REPOSITORY_ID}/icon.png")


def validate_repository_zip(output):
    with ZipFile(output) as archive:
        names = archive.namelist()
        expected_addon = f"{REPOSITORY_ID}/addon.xml"
        if expected_addon not in names:
            raise RuntimeError(f"{expected_addon} fehlt im Repository-ZIP")
        if any(not name.startswith(f"{REPOSITORY_ID}/") for name in names):
            raise RuntimeError("Repository-ZIP enthält Dateien außerhalb des Add-on-Wurzelordners")
        root = ET.fromstring(archive.read(expected_addon))
        if root.attrib.get("id") != REPOSITORY_ID:
            raise RuntimeError("Repository-ZIP enthält falsche Add-on-ID")


def _file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_file_content(source, output):
    if not output.exists():
        return False
    try:
        if source.stat().st_size != output.stat().st_size:
            return False
        return _file_digest(source) == _file_digest(output)
    except OSError:
        return False


def copy2_retry(source, output, attempts=12, delay=0.75):
    source = Path(source)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if _same_file_content(source, output):
        return output

    last_error = None
    for _ in range(attempts):
        try:
            shutil.copy2(source, output)
            return output
        except OSError as exc:
            last_error = exc
            time.sleep(delay)
            if _same_file_content(source, output):
                return output
    raise last_error


def sync_repository_zip_aliases():
    for output in (REPOSITORY_DIRECT_OUTPUT, REPOSITORY_VERSIONED_DIRECT_OUTPUT):
        copy2_retry(REPOSITORY_OUTPUT, output)
        validate_repository_zip(output)
        print(output)


def sync_browsable_repository_layout():
    ADDON_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    REPOSITORY_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    _prune_browsable_archives()

    addon_index_entries = [
        _entry("addon.xml", ADDON_INDEX_DIR / "addon.xml"),
        _entry("icon.png", ADDON_INDEX_DIR / "icon.png"),
        _entry("resources/", ADDON_INDEX_DIR / "resources"),
    ]
    zip_index_entries = []
    for archive in _retained_addon_archives():
        addon_output = ADDON_INDEX_DIR / archive.name
        zips_output = PROJECT_DIR / "docs" / "zips" / ADDON_ID / archive.name
        copy2_retry(archive, addon_output)
        copy2_retry(archive, zips_output)
        validate(addon_output)
        validate(zips_output)
        addon_index_entries.append(_entry(archive.name, addon_output))
        zip_index_entries.append(_entry(archive.name, zips_output))

    copy2_retry(PROJECT_DIR / "addon.xml", ADDON_INDEX_DIR / "addon.xml")
    copy2_retry(PROJECT_DIR / "resources" / "icon.png", ADDON_INDEX_DIR / "icon.png")
    _sync_addon_assets()

    copy2_retry(REPOSITORY_OUTPUT, REPOSITORY_INDEX_OUTPUT)
    validate_repository_zip(REPOSITORY_INDEX_OUTPUT)
    (REPOSITORY_INDEX_DIR / "addon.xml").write_text(_repository_addon_xml() + "\n", encoding="utf-8", newline="\n")
    copy2_retry(PROJECT_DIR / "resources" / "icon.png", REPOSITORY_INDEX_DIR / "icon.png")

    _write_index(ADDON_INDEX_DIR, f"/xVAULT/{ADDON_ID}/", addon_index_entries)
    _write_index(ADDON_INDEX_DIR / "resources", f"/xVAULT/{ADDON_ID}/resources/", [
        _entry("fanart.png", ADDON_INDEX_DIR / "resources" / "fanart.png"),
        _entry("icon.png", ADDON_INDEX_DIR / "resources" / "icon.png"),
        _entry("media/", ADDON_INDEX_DIR / "resources" / "media"),
    ])
    _write_index(ADDON_INDEX_DIR / "resources" / "media", f"/xVAULT/{ADDON_ID}/resources/media/", [
        _entry("banner.png", ADDON_INDEX_DIR / "resources" / "media" / "banner.png"),
    ])
    _write_index(REPOSITORY_INDEX_DIR, "/xVAULT/repository.xvault/", [
        _entry("addon.xml", REPOSITORY_INDEX_DIR / "addon.xml"),
        _entry("icon.png", REPOSITORY_INDEX_DIR / "icon.png"),
        _entry(REPOSITORY_ZIP_NAME, REPOSITORY_INDEX_OUTPUT),
    ])
    _write_index(PROJECT_DIR / "docs" / "zips", "/xVAULT/zips/", [
        _entry(f"{ADDON_ID}/", PROJECT_DIR / "docs" / "zips" / ADDON_ID),
        _entry("repository.xvault/", PROJECT_DIR / "docs" / "zips" / REPOSITORY_ID),
    ])
    _write_index(PROJECT_DIR / "docs" / "zips" / ADDON_ID, f"/xVAULT/zips/{ADDON_ID}/", zip_index_entries)
    _write_index(PROJECT_DIR / "docs" / "zips" / REPOSITORY_ID, "/xVAULT/zips/repository.xvault/", [
        _entry(REPOSITORY_ZIP_NAME, REPOSITORY_OUTPUT),
    ])


def _prune_browsable_archives():
    retained_addon_names = _retained_addon_archive_names()
    keep = {
        ADDON_INDEX_DIR: retained_addon_names,
        PROJECT_DIR / "docs" / "zips" / ADDON_ID: retained_addon_names,
        REPOSITORY_INDEX_DIR: {REPOSITORY_ZIP_NAME},
        PROJECT_DIR / "docs" / "zips" / REPOSITORY_ID: {REPOSITORY_ZIP_NAME},
    }
    for directory, keep_names in keep.items():
        if not directory.exists():
            continue
        for archive in directory.glob("*.zip"):
            if archive.name not in keep_names:
                archive.unlink()


def _retained_addon_archive_names():
    return {path.name for path in _retained_addon_archives()}


def _retained_addon_archives():
    downloads = PROJECT_DIR / "docs" / "downloads"
    archives = []
    for path in downloads.glob(f"{ADDON_ID}-*.zip"):
        match = re.match(rf"{re.escape(ADDON_ID)}-(.+)\.zip$", path.name)
        if match:
            archives.append((match.group(1), path))
    archives.sort(key=lambda item: _version_key(item[0]), reverse=True)
    return [path for _version, path in archives]


def _sync_addon_assets():
    assets = [
        Path("resources/icon.png"),
        Path("resources/fanart.png"),
        Path("resources/media/banner.png"),
    ]
    for relative in assets:
        source = PROJECT_DIR / relative
        if source.exists():
            copy2_retry(source, ADDON_INDEX_DIR / relative)


def update_kodi_repository_metadata():
    content = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<addons>\n'
        f'{_xml_body((PROJECT_DIR / "addon.xml").read_text(encoding="utf-8"))}\n\n'
        f'{_xml_body(_repository_addon_xml())}\n'
        '</addons>\n'
    )
    ADDONS_XML.write_text(content, encoding="utf-8", newline="\n")
    (ADDONS_XML.with_suffix(ADDONS_XML.suffix + ".md5")).write_text(
        hashlib.md5(content.encode("utf-8")).hexdigest(),
        encoding="utf-8",
        newline="\n",
    )


def update_download_page(output):
    prune_download_archives()
    sync_browsable_repository_layout()
    page = PROJECT_DIR / "docs" / "index.html"
    digest = hashlib.sha256(output.read_bytes()).hexdigest().upper()
    size = _format_size(output.stat().st_size)
    html_content = page.read_text(encoding="utf-8")
    html_content = re.sub(
        r"(<span>Aktuelle Version</span>\s*<strong>).*?(</strong>)",
        rf"\g<1>{VERSION}\2",
        html_content,
        flags=re.S,
    )
    html_content = re.sub(
        r'href="downloads/plugin\.video\.xvault(?:alpha)?-[^"]+\.zip"',
        f'href="downloads/{ZIP_NAME}"',
        html_content,
    )
    html_content = re.sub(
        r'href="(?:zips/repository\.xvault/)?repository\.xvault(?:-[^"]+)?\.zip"',
        f'href="{REPOSITORY_DIRECT_ZIP_NAME}"',
        html_content,
    )
    html_content = re.sub(r"(ZIP-Datei · ).*?(</p>)", rf"\g<1>{size}\2", html_content)
    html_content = re.sub(r"<code>[A-F0-9]{64}</code>", f"<code>{digest}</code>", html_content)
    html_content = _update_archive_links(html_content)
    html_content = _update_release_notes(html_content)
    html_content = html_content.replace(LEGACY_SITE_URL, SITE_URL)
    html_content = re.sub(r"(<span>Version ).*?(</span>)", rf"\g<1>{VERSION}\2", html_content)
    html_content = _inject_kodi_listing(html_content)
    html_content = _ensure_umami_tracking(html_content)
    page.write_text(html_content, encoding="utf-8", newline="\n")
    _update_manual_download_links()


def _update_manual_download_links():
    manual = PROJECT_DIR / "docs" / "handbuch" / "index.html"
    if not manual.exists():
        return
    html_content = manual.read_text(encoding="utf-8")
    html_content = re.sub(
        r'href="\.\./downloads/plugin\.video\.xvault(?:alpha)?-[^"]+\.zip"',
        f'href="../downloads/{ZIP_NAME}"',
        html_content,
    )
    html_content = re.sub(
        r"plugin\.video\.xvault(?:alpha)?-[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]+\.zip",
        ZIP_NAME,
        html_content,
    )
    html_content = re.sub(
        r"Handbuch zu xVAULT\s+[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]+",
        "Handbuch zu xVAULT %s" % VERSION,
        html_content,
    )
    manual.write_text(html_content, encoding="utf-8", newline="\n")


def _ensure_umami_tracking(html_content):
    html_content = re.sub(UMAMI_SCRIPT_PATTERN, "", html_content, flags=re.S)
    html_content = re.sub(UMAMI_PIXEL_PATTERN, "", html_content, flags=re.S)
    return html_content.replace("</head>", f"{UMAMI_TRACKING}\n</head>", 1)


def _update_archive_links(html):
    marker = r"(<!-- previous-downloads:start -->)(.*?)(<!-- previous-downloads:end -->)"
    archive = _archive_downloads_html()
    return re.sub(marker, rf"\1\n{archive}\n        \3", html, flags=re.S)


def _update_release_notes(html_content):
    notes = _release_notes_html()
    marked = r"(<!-- release-notes:start -->)(.*?)(<!-- release-notes:end -->)"
    if re.search(marked, html_content, flags=re.S):
        return re.sub(
            marked,
            lambda match: "%s\n%s\n    %s" % (match.group(1), notes, match.group(3)),
            html_content,
            flags=re.S,
        )
    legacy = (
        r"\s*<section class=\"panel update-panel\">.*?</section>"
        r"(?:\s*<section class=\"panel update-panel\">.*?</section>)*"
        r"(?=\s*<section class=\"panel tribute-panel\">)"
    )
    replacement = "\n    <!-- release-notes:start -->\n%s\n    <!-- release-notes:end -->" % notes
    return re.sub(legacy, replacement, html_content, count=1, flags=re.S)


def _release_notes_html():
    releases = _read_changelog_releases()[:RELEASE_NOTES_LIMIT]
    if not releases:
        return (
            '    <section class="panel update-panel">\n'
            '      <p class="section-kicker">Neu in %s</p>\n'
            '      <h2>Aktuelle Änderungen</h2>\n'
            '      <p>Details stehen in CHANGELOG.txt.</p>\n'
            '    </section>'
        ) % html.escape(VERSION)
    blocks = []
    for index, (version, bullets) in enumerate(releases):
        visible_bullets = bullets if index == 0 else bullets[:4]
        items = "\n".join("        <li>%s</li>" % html.escape(bullet) for bullet in visible_bullets)
        blocks.append(
            '    <section class="panel update-panel">\n'
            '      <p class="section-kicker">Neu in %s</p>\n'
            '      <h2>%s</h2>\n'
            '      <ul class="update-list">\n'
            '%s\n'
            '      </ul>\n'
            '    </section>' % (
                html.escape(version),
                html.escape(_release_title(bullets)),
                items,
            )
        )
    return "\n\n".join(blocks)


def _read_changelog_releases():
    if not CHANGELOG.exists():
        return []
    releases = []
    current_version = None
    current_bullets = []
    for raw_line in CHANGELOG.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        match = re.match(r"^xVAULT\s+(.+)$", line)
        if match:
            if current_version and current_bullets:
                releases.append((current_version, current_bullets))
            current_version = match.group(1).strip()
            current_bullets = []
            continue
        if line.startswith("- "):
            current_bullets.append(line[2:].strip())
    if current_version and current_bullets:
        releases.append((current_version, current_bullets))
    return releases


def _release_title(bullets):
    return "Änderungen im Überblick"


def _archive_downloads_html():
    downloads = PROJECT_DIR / "docs" / "downloads"
    versions = []
    for path in downloads.glob(f"{ADDON_ID}-*.zip"):
        match = re.match(rf"{re.escape(ADDON_ID)}-(.+)\.zip$", path.name)
        if not match:
            continue
        version = match.group(1)
        if version == VERSION:
            continue
        versions.append((version, path))

    versions.sort(key=lambda item: _version_key(item[0]), reverse=True)
    if not versions:
        return '        <li><span>Keine vorherigen Versionen verfuegbar</span></li>'

    lines = []
    for version, path in versions:
        lines.append(
            '        <li><a href="downloads/%s" download data-umami-event="Vorherige Version heruntergeladen">Version %s herunterladen</a><span>%s</span></li>'
            % (path.name, version, _format_size(path.stat().st_size))
        )
    return "\n".join(lines)

def prune_download_archives():
    downloads = PROJECT_DIR / "docs" / "downloads"
    versions = []
    for path in downloads.glob(f"{ADDON_ID}-*.zip"):
        match = re.match(rf"{re.escape(ADDON_ID)}-(.+)\.zip$", path.name)
        if not match:
            continue
        versions.append((match.group(1), path))

    versions.sort(key=lambda item: _version_key(item[0]), reverse=True)
    keep = set()
    previous = 0
    for version, path in versions:
        if version == VERSION:
            keep.add(path)
            continue
        if previous < DOWNLOAD_ARCHIVE_KEEP:
            keep.add(path)
            previous += 1

    for version, path in versions:
        if path not in keep:
            path.unlink()


def _version_key(version):
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"[.-]", version))


def _format_size(size):
    if size >= 1024 * 1024:
        return ("%.1f MB" % (size / 1024.0 / 1024.0)).replace(".", ",")
    return ("%.1f KB" % (size / 1024.0)).replace(".", ",")


def _entry(name, path):
    return {"name": name, "path": path}


def _write_index(directory, title, entries):
    directory.mkdir(parents=True, exist_ok=True)
    content = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="description" content="{title}">
{tracking}
</head>
<body>
<h2>Index of {title}</h2>
<table>
<tbody>
<tr><th></th><th><a href="?C=N;O=D">Name</a></th><th><a href="?C=M;O=A">Last modified</a></th><th><a href="?C=S;O=A">Size</a></th></tr>
<tr><th colspan="4"><hr></th></tr>
{rows}
<tr><th colspan="4"><hr></th></tr>
</tbody>
</table>
</body>
</html>
""".format(title=html.escape(title), tracking=UMAMI_TRACKING, rows=_index_rows(entries, parent="../"))
    (directory / "index.html").write_text(content, encoding="utf-8", newline="\n")


def _inject_kodi_listing(html_content):
    style = """<!-- kodi-listing-style:start -->
  <style>
    .kodi-index { display: none; }
    .kodi-client .page { display: none; }
    .kodi-client .kodi-index { display: block; padding: 24px; font-family: Arial, sans-serif; color: #111; background: #fff; }
    .kodi-index table { border-collapse: collapse; width: 100%; max-width: 900px; }
    .kodi-index th, .kodi-index td { padding: 4px 10px; text-align: left; }
  </style>
  <script>
    if (/Kodi/i.test(navigator.userAgent)) {
      document.documentElement.classList.add('kodi-client');
    }
  </script>
  <!-- kodi-listing-style:end -->"""
    listing = _kodi_listing_fragment()
    html_content = re.sub(
        r"\s*<!-- kodi-listing-style:start -->.*?<!-- kodi-listing-style:end -->",
        "",
        html_content,
        flags=re.S,
    )
    html_content = re.sub(
        r"\s*<!-- kodi-listing:start -->.*?<!-- kodi-listing:end -->",
        "",
        html_content,
        flags=re.S,
    )
    html_content = html_content.replace("</head>", f"{style}\n</head>")
    return html_content.replace("<body>", f"<body>\n{listing}", 1)


def _kodi_listing_fragment():
    entries = [
        _entry(f"{ADDON_ID}/", ADDON_INDEX_DIR),
        _entry("repository.xvault/", REPOSITORY_INDEX_DIR),
        _entry("addons.xml", ADDONS_XML),
        _entry("addons.xml.md5", ADDONS_XML.with_suffix(ADDONS_XML.suffix + ".md5")),
        _entry(REPOSITORY_DIRECT_ZIP_NAME, REPOSITORY_DIRECT_OUTPUT),
        _entry(REPOSITORY_ZIP_NAME, REPOSITORY_VERSIONED_DIRECT_OUTPUT),
    ]
    return """<!-- kodi-listing:start -->
  <section id="kodi-index" class="kodi-index">
    <h2>Index of /xVAULT/</h2>
    <table>
      <tbody>
        <tr><th></th><th><a href="?C=N;O=D">Name</a></th><th><a href="?C=M;O=A">Last modified</a></th><th><a href="?C=S;O=A">Size</a></th></tr>
        <tr><th colspan="4"><hr></th></tr>
{rows}
        <tr><th colspan="4"><hr></th></tr>
      </tbody>
    </table>
  </section>
  <!-- kodi-listing:end -->""".format(rows=_indent(_index_rows(entries, parent="../"), 8))


def _index_rows(entries, parent):
    rows = [
        '<tr><td>[PARENTDIR]</td><td><a href="%s" data-umami-event="Verzeichnisnavigation geöffnet">Parent Directory</a></td><td align="right">-</td><td align="right">-</td></tr>' % parent
    ]
    for entry in entries:
        path = entry["path"]
        name = entry["name"]
        href = html.escape(name, quote=True)
        label = html.escape(name)
        icon = "[DIR]" if name.endswith("/") else "[FILE]"
        rows.append(
            '<tr><td>%s</td><td><a href="%s"%s>%s</a></td><td align="right">%s</td><td align="right">%s</td></tr>'
            % (icon, href, _index_link_attrs(name), label, _format_index_mtime(path), _format_index_size(path))
        )
    return "\n".join(rows)


def _index_link_attrs(name):
    if name.endswith("/"):
        event = "Verzeichnis geöffnet"
    elif name.endswith(".zip"):
        event = "Datei heruntergeladen"
    elif name.endswith(".md5"):
        event = "Checksum geöffnet"
    elif name.endswith(".xml"):
        event = "Repository-Metadaten geöffnet"
    else:
        event = "Repository-Datei geöffnet"
    return ' data-umami-event="%s"' % html.escape(event, quote=True)


def _indent(text, spaces):
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _format_index_mtime(path):
    if not path.exists():
        return "-"
    from datetime import datetime
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d.%b.%Y %H:%M:%S")


def _format_index_size(path):
    if not path.exists() or path.is_dir():
        return "-"
    size = path.stat().st_size
    if size >= 1024 * 1024:
        return "%.2f MB" % (size / 1024.0 / 1024.0)
    if size >= 1024:
        return "%.2f KB" % (size / 1024.0)
    return "%.2f B" % size


def _repository_addon_xml():
    return REPOSITORY_TEMPLATE.read_text(encoding="utf-8").strip()


def _xml_body(content):
    return re.sub(r"^\s*<\?xml[^>]*>\s*", "", content, flags=re.S).strip()


if __name__ == "__main__":
    for destination in OUTPUTS:
        build(destination)
        validate(destination)
        print(destination)
    build_repository_zip(REPOSITORY_OUTPUT)
    validate_repository_zip(REPOSITORY_OUTPUT)
    print(REPOSITORY_OUTPUT)
    sync_repository_zip_aliases()
    update_kodi_repository_metadata()
    update_download_page(DOWNLOAD_OUTPUT)
