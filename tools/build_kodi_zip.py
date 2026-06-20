from pathlib import Path
import hashlib
import html
import re
import xml.etree.ElementTree as ET
import shutil
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parent
SITE_URL = "http://xvault.ddnss.de/"
LEGACY_SITE_URL = "https://mojomedia1812.github.io/xVAULT/"
ADDON = ET.parse(PROJECT_DIR / "addon.xml").getroot()
ADDON_ID = ADDON.attrib["id"]
VERSION = ADDON.attrib["version"]
ZIP_NAME = f"plugin.video.xvault-{VERSION}.zip"
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
M3U_DIR = PROJECT_DIR / "m3u"
DOCS_M3U_DIR = PROJECT_DIR / "docs" / "m3u"
OUTPUTS = (
    REPO_DIR / ZIP_NAME,
    DOWNLOAD_OUTPUT,
    REPOSITORY_PLUGIN_OUTPUT,
)

EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    "docs",
    "scrapers_source",
    "stream-link-auditor",
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


def sync_repository_zip_aliases():
    for output in (REPOSITORY_DIRECT_OUTPUT, REPOSITORY_VERSIONED_DIRECT_OUTPUT):
        shutil.copy2(REPOSITORY_OUTPUT, output)
        validate_repository_zip(output)
        print(output)


def sync_browsable_repository_layout():
    ADDON_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    REPOSITORY_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPOSITORY_PLUGIN_OUTPUT, ADDON_INDEX_OUTPUT)
    validate(ADDON_INDEX_OUTPUT)
    shutil.copy2(PROJECT_DIR / "addon.xml", ADDON_INDEX_DIR / "addon.xml")
    shutil.copy2(PROJECT_DIR / "resources" / "icon.png", ADDON_INDEX_DIR / "icon.png")

    shutil.copy2(REPOSITORY_OUTPUT, REPOSITORY_INDEX_OUTPUT)
    validate_repository_zip(REPOSITORY_INDEX_OUTPUT)
    (REPOSITORY_INDEX_DIR / "addon.xml").write_text(_repository_addon_xml() + "\n", encoding="utf-8", newline="\n")
    shutil.copy2(PROJECT_DIR / "resources" / "icon.png", REPOSITORY_INDEX_DIR / "icon.png")

    _write_index(ADDON_INDEX_DIR, "/xVAULT/plugin.video.xvault/", [
        _entry("addon.xml", ADDON_INDEX_DIR / "addon.xml"),
        _entry("icon.png", ADDON_INDEX_DIR / "icon.png"),
        _entry(ZIP_NAME, ADDON_INDEX_OUTPUT),
    ])
    _write_index(REPOSITORY_INDEX_DIR, "/xVAULT/repository.xvault/", [
        _entry("addon.xml", REPOSITORY_INDEX_DIR / "addon.xml"),
        _entry("icon.png", REPOSITORY_INDEX_DIR / "icon.png"),
        _entry(REPOSITORY_ZIP_NAME, REPOSITORY_INDEX_OUTPUT),
    ])
    _write_index(PROJECT_DIR / "docs" / "zips", "/xVAULT/zips/", [
        _entry("plugin.video.xvault/", PROJECT_DIR / "docs" / "zips" / ADDON_ID),
        _entry("repository.xvault/", PROJECT_DIR / "docs" / "zips" / REPOSITORY_ID),
    ])
    _write_index(PROJECT_DIR / "docs" / "zips" / ADDON_ID, "/xVAULT/zips/plugin.video.xvault/", [
        _entry(ZIP_NAME, REPOSITORY_PLUGIN_OUTPUT),
    ])
    _write_index(PROJECT_DIR / "docs" / "zips" / REPOSITORY_ID, "/xVAULT/zips/repository.xvault/", [
        _entry(REPOSITORY_ZIP_NAME, REPOSITORY_OUTPUT),
    ])


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


def sync_repository_m3u():
    if not M3U_DIR.exists():
        return
    DOCS_M3U_DIR.mkdir(parents=True, exist_ok=True)
    for source in M3U_DIR.glob("*.m3u"):
        shutil.copy2(source, DOCS_M3U_DIR / source.name)


def update_download_page(output):
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
        r'href="downloads/plugin\.video\.xvault-[^"]+\.zip"',
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
    html_content = html_content.replace(LEGACY_SITE_URL, SITE_URL)
    html_content = re.sub(r"(<span>Version ).*?(</span>)", rf"\g<1>{VERSION}\2", html_content)
    html_content = _inject_kodi_listing(html_content)
    page.write_text(html_content, encoding="utf-8", newline="\n")


def _update_archive_links(html):
    marker = r"(<!-- previous-downloads:start -->)(.*?)(<!-- previous-downloads:end -->)"
    archive = _archive_downloads_html()
    return re.sub(marker, rf"\1\n{archive}\n        \3", html, flags=re.S)


def _archive_downloads_html():
    downloads = PROJECT_DIR / "docs" / "downloads"
    versions = []
    for path in downloads.glob("plugin.video.xvault-*.zip"):
        match = re.match(r"plugin\.video\.xvault-(.+)\.zip$", path.name)
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
            '        <li><a href="downloads/%s" download>Version %s herunterladen</a><span>%s</span></li>'
            % (path.name, version, _format_size(path.stat().st_size))
        )
    return "\n".join(lines)


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
""".format(title=html.escape(title), rows=_index_rows(entries, parent="../"))
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
        _entry("plugin.video.xvault/", ADDON_INDEX_DIR),
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
        '<tr><td>[PARENTDIR]</td><td><a href="%s">Parent Directory</a></td><td align="right">-</td><td align="right">-</td></tr>' % parent
    ]
    for entry in entries:
        path = entry["path"]
        name = entry["name"]
        href = html.escape(name, quote=True)
        label = html.escape(name)
        icon = "[DIR]" if name.endswith("/") else "[FILE]"
        rows.append(
            '<tr><td>%s</td><td><a href="%s">%s</a></td><td align="right">%s</td><td align="right">%s</td></tr>'
            % (icon, href, label, _format_index_mtime(path), _format_index_size(path))
        )
    return "\n".join(rows)


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
    sync_repository_m3u()
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
