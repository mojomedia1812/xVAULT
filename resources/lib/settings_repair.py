import os
import shutil
import time
import xml.etree.ElementTree as ET


ADDON_ID = "plugin.video.xvault"
SETTINGS_FILE = "settings.xml"


def check_and_offer_repair(interactive=True, source="startup"):
    result = inspect_settings()
    if result.get("ok"):
        return False

    _log("xVAULT settings check failed via %s: %s" % (source, result.get("message", "")))
    if not interactive:
        return False

    if not _confirm_repair(result):
        return False

    try:
        backup = repair_settings_file(result["path"])
    except Exception as exc:
        _show_error("Die Einstellungen konnten nicht zurückgesetzt werden.\n\n%s" % _short(str(exc), 500))
        return False

    _show_done(backup)
    return True


def manual_check():
    result = inspect_settings()
    if result.get("ok"):
        _show_ok(result)
        return False
    return check_and_offer_repair(interactive=True, source="manual")


def inspect_settings():
    return inspect_settings_file(settings_path())


def settings_path():
    return os.path.join(_profile_path(), SETTINGS_FILE)


def inspect_settings_file(path):
    if not path:
        return _invalid(path, "Der Profilpfad konnte nicht ermittelt werden.")
    if not os.path.exists(path):
        return {"ok": True, "path": path, "state": "missing", "message": "Keine gespeicherte settings.xml vorhanden."}

    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except Exception as exc:
        return _invalid(path, "Die Datei kann nicht gelesen werden: %s" % str(exc))

    if not raw or not raw.strip():
        return _invalid(path, "Die Datei ist leer.")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return _invalid(path, "Die XML-Struktur ist beschädigt: %s" % str(exc))
    except Exception as exc:
        return _invalid(path, "Die XML-Datei konnte nicht geprüft werden: %s" % str(exc))

    if root.tag != "settings":
        return _invalid(path, "Die Datei enthält keinen gültigen settings-Wurzelknoten.")

    return {"ok": True, "path": path, "state": "valid", "message": "Die xVAULT-Einstellungen sind lesbar."}


def repair_settings_file(path):
    if not path or not os.path.exists(path):
        return ""

    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    backup = _unique_backup_path(path)
    shutil.copy2(path, backup)
    if not os.path.exists(backup):
        raise IOError("Backup konnte nicht erstellt werden.")
    os.remove(path)
    return backup


def _profile_path():
    special = "special://profile/addon_data/%s/" % ADDON_ID
    try:
        import xbmcvfs
        return xbmcvfs.translatePath(special)
    except Exception:
        try:
            import xbmc
            return xbmc.translatePath(special)
        except Exception:
            return os.path.join(os.getcwd(), "addon_data", ADDON_ID)


def _unique_backup_path(path):
    base = "%s.corrupt-%s.bak" % (path, time.strftime("%Y%m%d-%H%M%S"))
    backup = base
    counter = 1
    while os.path.exists(backup):
        backup = "%s.%d" % (base, counter)
        counter += 1
    return backup


def _invalid(path, message):
    return {"ok": False, "path": path, "state": "corrupt", "message": message}


def _confirm_repair(result):
    try:
        from resources.lib import control
        return control.yesnoDialog(
            "Die xVAULT-Einstellungen scheinen beschädigt zu sein.",
            _short(result.get("message", ""), 220),
            "Defekte settings.xml sichern und zurücksetzen?",
            heading="xVAULT Einstellungen reparieren",
            nolabel="Abbrechen",
            yeslabel="Reparieren",
        )
    except Exception:
        return False


def _show_done(backup):
    try:
        from resources.lib import control
        control.dialog.ok(
            "xVAULT Einstellungen repariert",
            "Die defekte settings.xml wurde gesichert:\n%s\n\n"
            "Kodi erzeugt die Einstellungen beim nächsten Start neu. Bitte Kodi neu starten."
            % (backup or "kein Backup vorhanden"),
        )
    except Exception:
        pass


def _show_ok(result):
    try:
        from resources.lib import control
        control.dialog.ok(
            "xVAULT Einstellungen",
            "%s\n\nPfad:\n%s" % (result.get("message", ""), result.get("path", "")),
        )
    except Exception:
        pass


def _show_error(message):
    try:
        from resources.lib import control
        control.dialog.ok("xVAULT Einstellungen", message)
    except Exception:
        pass


def _short(value, limit):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit - 3] + "..."


def _log(message):
    try:
        from resources.lib import log_utils
        log_utils.log(message, log_utils.LOGWARNING)
    except Exception:
        pass
