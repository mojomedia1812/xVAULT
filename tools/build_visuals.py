"""Build the standalone Windows x64 Kodi 22 native visualization locally.

Requires LLVM-MinGW and Kodi's matching kodi-dev-kit headers. Does not publish
or change any repository feeds. Output must be outside the source directory.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'native/visualization.xvault'


def build(toolchain, sdk, output):
    compiler = toolchain / 'bin/clang++.exe'
    include = sdk / 'xbmc/addons/kodi-dev-kit/include'
    if not compiler.is_file() or not (include / 'kodi/addon-instance/Visualization.h').is_file():
        raise ValueError('LLVM-MinGW compiler or Kodi SDK headers missing')
    output.mkdir(parents=True, exist_ok=True)
    addon = output / 'visualization.xvault'
    addon.mkdir(exist_ok=True)
    flags = [str(compiler), '-std=c++17', '-O2', '-static', '-DWIN32', '-DTARGET_WINDOWS', '-DNOMINMAX',
             '-I' + str(include)]
    test = output / 'bands_test.exe'
    subprocess.run(flags + [str(SOURCE / 'tests/bands_test.cpp'), '-o', str(test)], check=True)
    subprocess.run([str(test)], check=True)
    subprocess.run(flags + ['-shared', str(SOURCE / 'src/Visuals.cpp'), '-o',
        str(addon / 'visualization.xvault.dll'), '-ld3d11', '-ld3dcompiler', '-lwindowscodecs', '-lole32', '-luuid'], check=True)
    shutil.copy2(SOURCE / 'addon.xml', addon / 'addon.xml')
    shutil.copy2(ROOT / 'LICENSE', addon / 'LICENSE')
    (addon / 'resources').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'resources/icon.png', addon / 'resources/icon.png')
    if (SOURCE / 'resources').exists():
        shutil.copytree(SOURCE / 'resources', addon / 'resources', dirs_exist_ok=True)
    # Keep corresponding source with the private package as well as in Git.
    for path in (SOURCE / 'src').glob('*'):
        (addon / 'src').mkdir(exist_ok=True)
        shutil.copy2(path, addon / 'src' / path.name)
    version = ET.parse(SOURCE / 'addon.xml').getroot().get('version')
    package = output / ('visualization.xvault-%s-windows-x86_64.zip' % version)
    with ZipFile(package, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(addon.rglob('*')):
            if path.is_file():
                archive.write(path, 'visualization.xvault/' + path.relative_to(addon).as_posix())
    return package


def publish_repository(package, docs):
    """Stage a tested native package in Kodi's standard id/version layout."""
    with ZipFile(package) as archive:
        manifest = archive.read('visualization.xvault/addon.xml')
        addon = ET.fromstring(manifest)
        if addon.get('id') != 'visualization.xvault':
            raise ValueError('Unexpected native addon')
        folder = docs / addon.get('id')
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / ('%s-%s.zip' % (addon.get('id'), addon.get('version')))
        if destination.exists() and destination.read_bytes() != package.read_bytes():
            raise ValueError('Native version already staged with different bytes')
        shutil.copy2(package, destination)
        (folder / 'addon.xml').write_bytes(manifest)
        for name in archive.namelist():
            relative = name.removeprefix('visualization.xvault/')
            if relative.startswith('resources/') and not name.endswith('/'):
                target = folder / relative
                if not target.resolve().is_relative_to(folder.resolve()):
                    raise ValueError('Unsafe native resource path')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
    data = destination.read_bytes()
    for algorithm in ('md5', 'sha256'):
        destination.with_suffix('.zip.' + algorithm).write_text(hashlib.new(algorithm, data).hexdigest() + '\n', encoding='ascii')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--publish-repository', action='store_true', help='Stage the package under docs; never pushes Git')
    args = parser.parse_args()
    package = build(args.toolchain.resolve(), args.sdk.resolve(), args.output.resolve())
    print(package)
    if args.publish_repository:
        print(publish_repository(package, ROOT / 'docs'))
