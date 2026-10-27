"""Build-time signing only. No private signing material is distributed."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from resources.lib import release_security as security


def signing_key():
    from cryptography.hazmat.primitives import serialization
    path = Path(os.environ.get('XVAULT_SIGNING_KEY', ROOT / 'tools/diagnostics/private/release-signing-key.pem'))
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    numbers = key.public_key().public_numbers()
    if (numbers.n, numbers.e) != (security.PUBLIC_N, security.PUBLIC_E):
        raise ValueError('Signing key does not match the pinned release verification key')
    return key


def sign(payload):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    signature = signing_key().sign(security.canonical(payload), padding.PKCS1v15(), hashes.SHA256())
    envelope = {'algorithm': 'RSA-PKCS1-SHA256', 'payload': payload,
                'signature': base64.b64encode(signature).decode('ascii')}
    security.verify_envelope(envelope)
    return envelope


def make_integrity(files, version):
    info = security.version_info(version)
    if not info:
        raise ValueError('Use YYYY.MM.DD.1 for release, YYYY.MM.DD.N (N >= 2) for nightly')
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
              if name != security.INTEGRITY_FILE}
    tree = security.tree_digest(hashes)
    payload = dict(schema=1, addon_id=security.ADDON_ID, version=version, channel=info['channel'],
                   build_id=version + '-' + tree[:16], tree_sha256=tree, files=hashes)
    security.validate_integrity_payload(payload)
    return sign(payload)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8', newline='\n')


def companion_addons(docs):
    """Only advertise native packages actually staged for repository delivery."""
    import xml.etree.ElementTree as ET
    result = []
    for manifest in sorted(Path(docs).glob('visualization.*/addon.xml')):
        node = ET.parse(manifest).getroot()
        addon_id, version = node.get('id'), node.get('version')
        if addon_id != manifest.parent.name or not version:
            raise ValueError('Invalid companion metadata')
        package = manifest.parent / ('%s-%s.zip' % (addon_id, version))
        checksum = package.with_suffix('.zip.sha256')
        if not package.is_file() or not checksum.is_file() or checksum.read_text().strip() != security.sha256_file(package):
            raise ValueError('Missing or invalid companion package: ' + addon_id)
        result.append(node)
    return result


def append_companions(root, docs):
    for node in companion_addons(docs):
        for previous in list(root):
            if previous.get('id') == node.get('id'):
                root.remove(previous)
        root.append(node)


def write_catalog(zip_path, envelope, docs):
    payload = security.verify_envelope(envelope)
    version, channel = payload['version'], payload['channel']
    path = Path(zip_path)
    zip_hash = security.sha256_file(path)
    release = {k: payload[k] for k in ('addon_id', 'version', 'channel', 'build_id', 'tree_sha256')}
    release.update(sha256=zip_hash, size=path.stat().st_size,
                   download_url=security.BASE_URL + 'downloads/' + path.name,
                   integrity_url=security.BASE_URL + 'updates/versions/' + version + '.json')
    doc = Path(docs)
    old = doc / 'updates' / (channel + '.json')
    sequence = time.time_ns()
    if old.exists():
        previous_payload = security.verify_envelope(json.loads(old.read_text(encoding='utf-8')))
        sequence = max(sequence, previous_payload['sequence'] + 1)
        previous = previous_payload.get('release')
        if previous and previous['version'] == version and previous['sha256'] != zip_hash:
            # Local rebuilds before publication are allowed only with an explicit flag.
            if os.environ.get('XVAULT_ALLOW_DRAFT_REBUILD') != '1':
                raise ValueError('Version already built with different bytes; increment it or explicitly rebuild an unpublished draft')
    write_json(doc / 'updates' / 'versions' / (version + '.json'), envelope)
    write_json(old, sign(dict(schema=1, channel=channel, sequence=sequence, release=release)))
    for other in ('release', 'nightly'):
        if not (doc / 'updates' / (other + '.json')).exists():
            write_json(doc / 'updates' / (other + '.json'), sign(dict(schema=1, channel=other, sequence=time.time_ns(), release=None)))
    path.with_suffix(path.suffix + '.sha256').write_text(zip_hash + '\n', encoding='ascii')
    # Kodi must see only the selected channel, even when its global updater is enabled.
    from zipfile import ZipFile
    import xml.etree.ElementTree as ET
    with ZipFile(path) as archive:
        addon = ET.fromstring(archive.read(security.ADDON_ID + '/addon.xml'))
    repository = ET.parse(ROOT / 'resources/repository/addon.xml').getroot()
    for selected in ('release', 'nightly'):
        xml_path = doc / 'updates' / selected / 'addons.xml'
        if selected != channel and xml_path.exists():
            if not companion_addons(doc):
                continue
            root = ET.parse(xml_path).getroot()
        else:
            root = ET.Element('addons')
            if selected == channel:
                root.append(addon)
            root.append(repository)
        append_companions(root, doc)
        raw = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='utf-8') + b'\n'
        raw = b'\n'.join(line.rstrip() for line in raw.splitlines()) + b'\n'
        xml_path.parent.mkdir(parents=True, exist_ok=True)
        xml_path.write_bytes(raw)
        xml_path.with_suffix('.xml.md5').write_text(hashlib.md5(raw).hexdigest(), encoding='ascii')
    return release
