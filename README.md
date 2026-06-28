# xVAULT

xVAULT ist ein Kodi-Video-Add-on zum Durchsuchen und Wiedergeben von Filmen, TV-Serien und LiveTV.

## Aktuelle Version

Aktueller Stand: `2026.06.28.9`

Die fuehrende Versionsquelle ist [`addon.xml`](addon.xml). Wenn die Version in `addon.xml` geaendert wird, muss diese README geprueft und bei Bedarf aktualisiert werden.

## Installation

1. Die aktuelle Add-on-ZIP von [xvault.ddnss.de](http://xvault.ddnss.de/) herunterladen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** oeffnen.
3. Die Datei `plugin.video.xvault-2026.06.28.9.zip` auswaehlen.
4. xVAULT starten.

Alternativ kann das Repository-ZIP von [http://xvault.ddnss.de/repository.xvault.zip](http://xvault.ddnss.de/repository.xvault.zip) installiert werden. Danach findet Kodi neue xVAULT-Versionen ueber das Repository.

Kodi installiert die offiziellen Abhaengigkeiten aus den konfigurierten Repositorys. Nicht im offiziellen Kodi-Repo verfuegbare Module wie ResolveURL werden beim ersten Start von xVAULT automatisch aus ihren offiziellen Quellen nachinstalliert.

Weitere Hinweise zu Abhaengigkeiten stehen in [`DEPENDENCIES.md`](DEPENDENCIES.md).

## Nutzung

- Filme und Serien ueber die xVAULT-Menues suchen.
- Eine Quelle auswaehlen oder Autoplay verwenden.
- LiveTV oeffnen, um deutsche Sender aus den VAVOO/HUHU-Listen zu laden und wiederzugeben.
- Favoriten und Wiedergabestaende optional ueber den Kontenbereich synchronisieren.
- Gesehene Folgen, Staffeln und Serien werden aus den aktuellen Wiedergabestaenden abgeleitet.

## Funktionen

- Suche und Wiedergabe von Filmen und TV-Serien.
- LiveTV mit zusammengefuehrten Senderlisten von `vavoo.to/channels` und `huhu.to/channels`.
- Deutsche LiveTV-Kategorien und Stream-Auswahl ueber lokale Mapping-Daten.
- Fortsetzen von Wiedergaben und automatische Lesezeichen.
- Gesehen/Ungesehen-Status fuer Filme, Folgen, Staffeln und Serien.
- xVAULT-Synchronisation fuer Favoriten und Wiedergabestaende.
- Download-, Untertitel- und externe Download-Manager-Optionen.
- Optionaler VAVOO-/Stalker-Bereich.

## Fehler und Vorschlaege melden

Fehler und Verbesserungsvorschlaege bitte ueber [GitHub Issues](https://github.com/mojomedia1812/xVAULT/issues) melden. Dort gibt es Vorlagen fuer Fehlermeldungen und Feature-Wuensche.

Gute Fehlermeldungen enthalten:

- verwendete xVAULT-Version
- Kodi-Version und System
- genaue Schritte zum Nachstellen
- erwartetes und tatsaechliches Verhalten
- Screenshots oder Logs, falls vorhanden

## Mitwirken

Hinweise fuer Beitraege stehen in [`CONTRIBUTING.md`](CONTRIBUTING.md).

Bei Aenderungen an Version, Einstellungen oder Funktionen muss diese README geprueft und bei Bedarf aktualisiert werden.

## Changelog

- Repository- und Dokumentationsaenderungen: [`CHANGELOG.md`](CHANGELOG.md)
- Plugin-Versionshistorie: [`CHANGELOG.txt`](CHANGELOG.txt)

## Kompatibilitaet

xVAULT ist ein Kodi-Python-3-Add-on und deklariert in [`addon.xml`](addon.xml) `xbmc.python` ab Version `3.0.0`.
