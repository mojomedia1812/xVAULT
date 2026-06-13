from pathlib import Path
import hashlib
import re
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parent
ADDON = ET.parse(PROJECT_DIR / "addon.xml").getroot()
ADDON_ID = ADDON.attrib["id"]
VERSION = ADDON.attrib["version"]
ZIP_NAME = f"plugin.video.xvault-{VERSION}.zip"
OUTPUTS = (
    REPO_DIR / ZIP_NAME,
    PROJECT_DIR / "docs" / "downloads" / ZIP_NAME,
)

EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    "docs",
    "tools",
}
EXCLUDED_FILES = {
    ".gitignore",
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
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in EXCLUDED_FILES or path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        yield path, relative


def build(output):
    output.parent.mkdir(parents=True, exist_ok=True)
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


def update_download_page(output):
    page = PROJECT_DIR / "docs" / "index.html"
    digest = hashlib.sha256(output.read_bytes()).hexdigest().upper()
    size = _format_size(output.stat().st_size)
    html = page.read_text(encoding="utf-8")
    html = re.sub(
        r"(<span>Aktuelle Version</span>\s*<strong>).*?(</strong>)",
        rf"\g<1>{VERSION}\2",
        html,
        flags=re.S,
    )
    html = re.sub(
        r'href="downloads/plugin\.video\.xvault-[^"]+\.zip"',
        f'href="downloads/{ZIP_NAME}"',
        html,
    )
    html = re.sub(r"(ZIP-Datei · ).*?(</p>)", rf"\g<1>{size}\2", html)
    html = re.sub(r"<code>[A-F0-9]{64}</code>", f"<code>{digest}</code>", html)
    html = _update_archive_links(html)
    html = re.sub(r"(<span>Version ).*?(</span>)", rf"\g<1>{VERSION}\2", html)
    page.write_text(html, encoding="utf-8", newline="\n")


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


if __name__ == "__main__":
    for destination in OUTPUTS:
        build(destination)
        validate(destination)
        print(destination)
    update_download_page(OUTPUTS[-1])
