from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parent
VERSION = "2026.06.09"
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
            archive_name = (Path(PROJECT_DIR.name) / relative).as_posix()
            archive.write(source, archive_name)


def validate(output):
    with ZipFile(output) as archive:
        names = archive.namelist()

    expected_addon = f"{PROJECT_DIR.name}/addon.xml"
    if expected_addon not in names:
        raise RuntimeError(f"{expected_addon} fehlt im ZIP")
    if any("\\" in name for name in names):
        raise RuntimeError("ZIP enthält nicht Kodi-konforme Backslash-Pfade")
    if any(name.startswith(f"{PROJECT_DIR.name}/docs/") for name in names):
        raise RuntimeError("Website-Dateien wurden in das Add-on-Paket aufgenommen")


if __name__ == "__main__":
    for destination in OUTPUTS:
        build(destination)
        validate(destination)
        print(destination)
