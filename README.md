# xVAULT

xVAULT ist ein Video-Add-on für Kodi zur Suche und Wiedergabe von Filmen
und TV-Serien.

## Installation

1. `tools/build_kodi_zip.py` ausführen, um ein Kodi-konformes ZIP zu erzeugen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** öffnen.
3. `plugin.video.xvault-2026.06.14.3.zip` auswählen.

Kodi installiert die offiziellen Abhängigkeiten aus den konfigurierten
Repositorys. Nicht im offiziellen Kodi-Repo verfügbare Module wie ResolveURL
werden beim ersten Start von xVAULT automatisch aus ihren offiziellen Quellen
nachinstalliert. Außerdem legt xVAULT automatisch das Kodi-Repository
`repository.xvault` an, damit spätere Updates über Kodi gefunden werden.

Im Menü **LIVE-TV** kann xVAULT außerdem das externe Add-on VAVOO.TO öffnen.
Wenn es noch fehlt, bietet xVAULT eine Installation aus dem Michaz-Repository an.

## Version

Aktueller Stand: `2026.06.14.4`

Weitere Hinweise zu Abhängigkeiten stehen in
[`DEPENDENCIES.md`](DEPENDENCIES.md).
