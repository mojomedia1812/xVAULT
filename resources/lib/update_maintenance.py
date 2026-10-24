"""Cooperative service shutdown before replacing an installed addon."""
import threading
import time

REQUEST = 'xvault.update.maintenance'
RUNNING = 'xvault.service.running'
STOPPED = 'xvault.service.stopped'


def window():
    import xbmcgui
    return xbmcgui.Window(10000)


def requested():
    return bool(window().getProperty(REQUEST))


def started():
    window().setProperty(RUNNING, '1')
    window().clearProperty(STOPPED)


def finished():
    win = window()
    token = win.getProperty(REQUEST)
    if token:
        # Network workers finish before the helper is allowed to replace code.
        deadline = time.monotonic() + 80
        current = threading.current_thread()
        while time.monotonic() < deadline:
            workers = [t for t in threading.enumerate()
                       if t is not current and t.name.startswith('xvault-') and t.is_alive()]
            if not workers:
                win.setProperty(STOPPED, token)
                break
            for worker in workers:
                worker.join(.1)
    win.clearProperty(RUNNING)
