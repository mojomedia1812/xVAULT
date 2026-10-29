"""Build an unpublished Kodi 21 Android ARM32 visualization with the official NDK."""
import argparse
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'native/visualization.xvault'


def build(ndk, sdk, output):
    from PIL import Image
    if output.resolve().is_relative_to(SOURCE.resolve()):
        raise ValueError('Build output must be outside the source tree')
    versions=(sdk/'kodi/versions.h').read_text(encoding='utf-8')
    if 'ADDON_INSTANCE_VERSION_VISUALIZATION          "4.0.0"' not in versions:
        raise ValueError('This renderer requires the Kodi 21 visualization API 4.0.0 SDK')
    output.mkdir(parents=True, exist_ok=True)
    addon = output / 'visualization.xvault'; addon.mkdir(exist_ok=True)
    compiler = ndk / 'toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe'
    flags = [str(compiler), '--target=armv7a-linux-androideabi21', '-std=c++17', '-O2', '-fPIC', '-shared', '-static-libstdc++', '-fvisibility=hidden', '-DTARGET_ANDROID', '-DANDROID', '-DTARGET_POSIX', '-I'+str(sdk), '-I'+str(output)]
    test_flags=[f for f in flags if f != '-shared']
    subprocess.run(test_flags + [str(SOURCE/'tests/bands_test.cpp'), '-o',str(output/'bands_test-armv7'),'-latomic'],check=True)
    subprocess.run(flags + [str(SOURCE/'src/VisualsGLES.cpp'), '-o', str(addon/'visualization.xvault.so'), '-lGLESv3', '-llog', '-latomic', '-Wl,-z,max-page-size=16384'], check=True)
    manifest = ET.parse(SOURCE / 'addon.xml')
    root = manifest.getroot(); root.set('version','21.0.2')
    for imp in root.findall('./requires/import'):
        if imp.get('addon')=='kodi.binary.global.main': imp.set('version','2.0.2'); imp.set('minversion','2.0.0')
        if imp.get('addon')=='kodi.binary.instance.visualization': imp.set('version','4.0.0'); imp.set('minversion','4.0.0')
    extension=root.find("extension[@point='xbmc.player.musicviz']"); extension.attrib.pop('library_windows',None); extension.set('library_android','visualization.xvault.so')
    root.find("./extension[@point='xbmc.addon.metadata']/platform").text='android-armv7'
    manifest.write(addon/'addon.xml',encoding='utf-8',xml_declaration=True)
    shutil.copytree(SOURCE/'resources',addon/'resources',dirs_exist_ok=True)
    shutil.copy2(ROOT/'resources/icon.png',addon/'resources/icon.png')
    image=Image.open(SOURCE/'resources/radio-wordmark.png').convert('RGBA').resize((2048,690))
    (addon/'resources/emblem.rgba').write_bytes(image.tobytes())
    shutil.copy2(ROOT/'LICENSE',addon/'LICENSE')
    shutil.copytree(SOURCE/'src',addon/'src',dirs_exist_ok=True)
    package=output/'visualization.xvault-21.0.2-android-armv7.zip'
    with ZipFile(package,'w',ZIP_DEFLATED) as z:
        for p in sorted(addon.rglob('*')):
            if p.is_file():z.write(p,'visualization.xvault/'+p.relative_to(addon).as_posix())
    return package

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ndk','sdk','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(build(a.ndk.resolve(),a.sdk.resolve(),a.output.resolve()))
