"""Canonical release manifests and signature verification without Kodi dependencies."""
import base64
import datetime
import hashlib
import json
import os
import re
import stat

ADDON_ID = 'plugin.video.xvault'
BASE_URL = 'https://xvault.repowork.de/'
INTEGRITY_FILE = 'resources/release-integrity.json'
# Public verification key only. The private key never belongs in an addon/repository.
PUBLIC_N = 4233901086815027274709007213048646342327915960114632431577360659395479420466199439582203805675888314281839087256162542573735476670179738751028724428816673866071838099460649150282418487755360281663372879622227972686862845997405944216005034363873348491473925847862989632926200087230249567984814171702364450827250495037823780043865751591663574573640346476078702593909963186248207734449322730695838257961064499776485186179568468850510816489148603447262698389624797704252760962460991048519669475196278502830292071068927370143298972227701903435789744692881707597012048785880815736365625942818979405044939947947768709218367838272663353717139951149249056392616458016533745084491412584748708721443623835607168865962290265937900299645185907855621790386930068558364863519513250492967380740597226725028592111305131522238663991587131424716733970420973207902112971134907251032840620157969493293473648449979145411356460773034959264024641117
PUBLIC_E = 65537
IGNORED_DIRS = {'.git', '__pycache__', 'docs', 'api', 'tools', 'cookies', 'htmlcache', '.pytest_cache'}
IGNORED_FILES = {'.iptv_merge', '.DS_Store'}


class VerificationError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def verify_envelope(envelope, public_key=None):
    try:
        payload = envelope['payload']
        signature = base64.b64decode(envelope['signature'], validate=True)
        n, e = public_key or (PUBLIC_N, PUBLIC_E)
        size = (n.bit_length() + 7) // 8
        if envelope.get('algorithm') != 'RSA-PKCS1-SHA256' or len(signature) != size:
            raise VerificationError('Unbekannte oder ungueltige Signatur')
        sig = int.from_bytes(signature, 'big')
        if sig >= n:
            raise VerificationError('Ungueltige Signatur')
        encoded = pow(sig, e, n).to_bytes(size, 'big')
        digest_info = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(canonical(payload)).digest()
        expected = b'\x00\x01' + b'\xff' * (size - len(digest_info) - 3) + b'\x00' + digest_info
        if encoded != expected:
            raise VerificationError('Release-Signatur stimmt nicht')
        return payload
    except VerificationError:
        raise
    except Exception as exc:
        raise VerificationError('Release-Referenz ist ungueltig') from exc


def version_info(version):
    match = re.fullmatch(r'(\d{4})\.(\d{1,2})\.(\d{1,2})\.(\d+)', str(version or ''))
    if not match:
        return None
    year, month, day, revision = map(int, match.groups())
    try:
        date = datetime.date(year, month, day)
    except ValueError:
        return None
    if revision < 1:
        return None
    return {'date': date, 'revision': revision, 'channel': 'release' if revision == 1 else 'nightly'}


def version_warning(version, latest=None, today=None):
    info = version_info(version)
    if not info:
        return 'Unplausible Versionsnummer: %s' % version
    reference = version_info(latest) if latest else None
    # A verified published date is preferable to the user's potentially wrong clock.
    reference_date = reference['date'] if reference else (today or datetime.date.today())
    if info['date'] > reference_date + datetime.timedelta(days=7):
        return 'Unplausible Versionsnummer: %s (Referenz %s)' % (version, latest or reference_date.isoformat())
    return ''


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(256 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def tree_digest(files):
    return hashlib.sha256(canonical(files)).hexdigest()


def safe_relative(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise VerificationError('Ungueltiger Paketpfad')
    if any(p in ('', '.', '..') for p in name.split('/')) or name.startswith('/'):
        raise VerificationError('Unsicherer Paketpfad')
    return name


def is_runtime_file(name):
    return (name == INTEGRITY_FILE or name in IGNORED_FILES or
            name.endswith(('.pyc', '.pyo')) or any(p in IGNORED_DIRS for p in name.split('/')))


def validate_integrity_payload(payload):
    files = payload.get('files')
    if payload.get('addon_id') != ADDON_ID or payload.get('schema') != 1 or not isinstance(files, dict) or not files:
        raise VerificationError('Falsche Integritaetsreferenz')
    info = version_info(payload.get('version'))
    if not info or info['channel'] != payload.get('channel'):
        raise VerificationError('Version und Kanal passen nicht zusammen')
    for name, digest in files.items():
        safe_relative(name)
        if name == INTEGRITY_FILE or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise VerificationError('Ungueltiger Datei-Hash')
    if payload.get('tree_sha256') != tree_digest(files):
        raise VerificationError('Paket-Dateimanifest stimmt nicht')
    return files


def inspect_tree(root, envelope=None):
    try:
        if envelope is None:
            with open(os.path.join(root, INTEGRITY_FILE), encoding='utf-8') as f:
                envelope = json.load(f)
        payload = verify_envelope(envelope)
        expected = validate_integrity_payload(payload)
    except FileNotFoundError:
        return {'state': 'unverified', 'message': 'Originalstatus nicht pruefbar: keine signierte Referenz vorhanden.'}
    except (VerificationError, ValueError, OSError) as exc:
        return {'state': 'invalid_reference', 'message': 'Originalstatus nicht bestaetigt: %s' % exc}
    actual, missing, changed, extra = {}, [], [], []
    try:
        for name in expected:
            path = os.path.join(root, *name.split('/'))
            if not os.path.isfile(path):
                missing.append(name)
                continue
            if os.path.islink(path):
                changed.append(name)
                continue
            actual[name] = sha256_file(path)
            if actual[name] != expected[name]:
                changed.append(name)
        for base, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for name in names:
                rel = os.path.relpath(os.path.join(base, name), root).replace(os.sep, '/')
                if rel not in expected and not is_runtime_file(rel):
                    extra.append(rel)
    except OSError as exc:
        return {'state': 'unverified', 'message': 'Dateipruefung fehlgeschlagen: %s' % exc}
    ok = not (missing or changed or extra)
    return {'state': 'original' if ok else 'modified', 'version': payload['version'],
            'channel': payload['channel'], 'build_id': payload['build_id'],
            'expected_sha256': payload['tree_sha256'], 'installed_sha256': tree_digest(actual),
            'changed': changed, 'missing': missing, 'extra': extra,
            'message': 'Originalpaket: SHA-256 und Release-Signatur stimmen.' if ok else
                       'Kein unveraendertes Original-Add-on: Dateien wurden geaendert, entfernt oder hinzugefuegt.'}
