"""Select only native packages built for the running Kodi API and architecture."""
import re
import struct
import sys
import platform

PROFILES = {
    'windows-x86_64/kodi22': '22.0.2',
    'android-armv7/kodi21': '21.0.2',
    'android-aarch64/kodi21': '21.0.2',
}


def profile(xbmc_module=None):
    try:
        if xbmc_module is None:
            import xbmc as xbmc_module
        major = int(re.match(r'^(\d+)', str(xbmc_module.getInfoLabel('System.BuildVersion'))).group(1))
        bits = struct.calcsize('P') * 8
        machine = platform.machine().lower()
        if sys.platform == 'win32' and bits == 64 and machine in ('amd64', 'x86_64') and major == 22:
            return 'windows-x86_64/kodi22'
        if xbmc_module.getCondVisibility('System.Platform.Android') and major == 21:
            # uname may report the 64-bit kernel even for a 32-bit Kodi process.
            # The library ABI must follow Kodi's pointer size, not the handset.
            arm = machine.startswith('arm') or machine == 'aarch64'
            if bits == 32 and arm:
                return 'android-armv7/kodi21'
            if bits == 64 and machine in ('aarch64', 'arm64'):
                return 'android-aarch64/kodi21'
    except (ValueError, AttributeError, ImportError):
        pass
    return ''


def required_version(xbmc_module=None):
    return PROFILES.get(profile(xbmc_module), '')
