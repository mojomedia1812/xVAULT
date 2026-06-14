# xVAULT

xVAULT ist ein Video-Add-on für Kodi zur Suche und Wiedergabe von Filmen
und TV-Serien.

## Installation

1. `tools/build_kodi_zip.py` ausführen, um ein Kodi-konformes ZIP zu erzeugen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** öffnen.
3. `plugin.video.xvault-2026.06.14.10.zip` auswählen.

Kodi installiert die offiziellen Abhängigkeiten aus den konfigurierten
Repositorys. Nicht im offiziellen Kodi-Repo verfügbare Module wie ResolveURL
werden beim ersten Start von xVAULT automatisch aus ihren offiziellen Quellen
nachinstalliert. Außerdem legt xVAULT automatisch das Kodi-Repository
`repository.xvault` an, damit spätere Updates über Kodi gefunden werden.

LiveTV ist in dieser Version deaktiviert. Der frühere LiveTV-Menüpunkt wird
nicht mehr angezeigt; alte direkte LiveTV-, M3U- und VAVOO-Live-URLs werden
mit einer kurzen Meldung abgefangen.

## Version

Aktueller Stand: `2026.06.14.10`

Weitere Hinweise zu Abhängigkeiten stehen in
[`DEPENDENCIES.md`](DEPENDENCIES.md).
