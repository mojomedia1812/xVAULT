import uuid

from resources.lib.sync import storage


def get_device_id():
    device_id = storage.get_setting(storage.DEVICE_ID)
    if not device_id:
        device_id = str(uuid.uuid4())
        storage.set_setting(storage.DEVICE_ID, device_id)
    return device_id
