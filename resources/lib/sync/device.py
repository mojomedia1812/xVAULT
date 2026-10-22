import uuid

from resources.lib.sync import storage


def get_device_id():
    device_id = storage.get_setting(storage.DEVICE_ID)
    if not device_id:
        device_id = str(uuid.uuid4())
        storage.set_setting(storage.DEVICE_ID, device_id)
    return device_id


def get_device_name():
    name = storage.get_setting('sync.device_name')
    if not name:
        import xbmc
        import platform
        name = xbmc.getInfoLabel('System.FriendlyName') or platform.node() or 'Kodi'
        storage.set_setting('sync.device_name', name[:128])
    return name[:128]
