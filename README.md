# xVAULT

xVAULT ist ein Video-Add-on für Kodi zur Suche und Wiedergabe von Filmen
und TV-Serien.

## Installation

1. `tools/build_kodi_zip.py` ausführen, um ein Kodi-konformes ZIP zu erzeugen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** öffnen.
3. `plugin.video.xvault-2026.06.14.8.zip` auswählen.

Kodi installiert die offiziellen Abhängigkeiten aus den konfigurierten
Repositorys. Nicht im offiziellen Kodi-Repo verfügbare Module wie ResolveURL
werden beim ersten Start von xVAULT automatisch aus ihren offiziellen Quellen
nachinstalliert. Außerdem legt xVAULT automatisch das Kodi-Repository
`repository.xvault` an, damit spätere Updates über Kodi gefunden werden.

Im Menü **LIVE-TV** ist VAVOO.TO nativ in xVAULT eingebunden. Zusätzlich nutzt
xVAULT die gebündelten M3U-Listen `tv-at.m3u`, `tv.m3u` und `tv2.m3u` aus dem Repository-Unterordner `m3u` unter
**M3U Live-TV**. Alte VAVOO.TO-Playlist-URLs werden intern auf
`plugin.video.xvault` umgeschrieben.

## Version

Aktueller Stand: `2026.06.14.8`

Weitere Hinweise zu Abhängigkeiten stehen in
[`DEPENDENCIES.md`](DEPENDENCIES.md).
