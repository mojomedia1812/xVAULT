"""Native companion repository delivery, checksums and channel preservation."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from tools.build_visuals import publish_repository
from tools.release_packaging import append_companions, companion_addons


class NativeDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.docs = self.root / 'docs'
        self.package = self.root / 'native.zip'
        with ZipFile(self.package, 'w') as archive:
            archive.writestr('visualization.xvault/addon.xml',
                '<addon id="visualization.xvault" version="22.0.1"><extension point="xbmc.addon.metadata"><platform>windows-x86_64</platform></extension></addon>')
            archive.writestr('visualization.xvault/visualization.xvault.dll', b'fixture')
            archive.writestr('visualization.xvault/resources/icon.png', b'icon')

    def test_published_package_uses_kodi_path_and_matching_hash(self):
        path = publish_repository(self.package, self.docs)
        self.assertEqual(path.name, 'visualization.xvault-22.0.1.zip')
        self.assertEqual(path.with_suffix('.zip.sha256').read_text().strip(), hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(companion_addons(self.docs)[0].get('version'), '22.0.1')

    def test_invalid_binary_is_not_advertised(self):
        path = publish_repository(self.package, self.docs)
        path.write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            companion_addons(self.docs)

    def test_companion_merge_preserves_video_channels_without_duplicates(self):
        publish_repository(self.package, self.docs)
        for version in ('2026.10.26.1', '2026.10.27.4'):
            root = ET.fromstring('<addons><addon id="plugin.video.xvault" version="%s"/></addons>' % version)
            append_companions(root, self.docs)
            append_companions(root, self.docs)
            self.assertEqual(root.find("addon[@id='plugin.video.xvault']").get('version'), version)
            self.assertEqual(len(root.findall("addon[@id='visualization.xvault']")), 1)


if __name__ == '__main__':
    unittest.main()
