from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ADDON_XML = ROOT / "addon.xml"
README = ROOT / "README.md"


def main():
    if not ADDON_XML.is_file():
        fail("addon.xml wurde nicht gefunden.")
    if not README.is_file():
        fail("README.md wurde nicht gefunden.")

    version = ET.parse(str(ADDON_XML)).getroot().attrib.get("version", "").strip()
    if not version:
        fail("In addon.xml wurde keine Version gefunden.")

    readme = README.read_text(encoding="utf-8")
    if version not in readme:
        fail("README.md enthaelt nicht die aktuelle Add-on-Version %s aus addon.xml." % version)

    install_zip = "plugin.video.xvault-%s.zip" % version
    if install_zip not in readme:
        fail("README.md enthaelt nicht den aktuellen Installations-ZIP-Namen %s." % install_zip)

    print("README.md passt zur Add-on-Version %s." % version)


def fail(message):
    print("README-Versioncheck fehlgeschlagen: %s" % message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
