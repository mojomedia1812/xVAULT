# xVAULT

xVAULT ist ein Video-Add-on für Kodi zur Suche und Wiedergabe von Filmen,
TV-Serien und LiveTV.

## Installation

1. `tools/build_kodi_zip.py` ausführen, um ein Kodi-konformes ZIP zu erzeugen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** öffnen.
3. `plugin.video.xvault-2026.06.19.1.zip` auswählen.

Kodi installiert die offiziellen Abhängigkeiten aus den konfigurierten
Repositorys. Nicht im offiziellen Kodi-Repo verfügbare Module wie ResolveURL
werden beim ersten Start von xVAULT automatisch aus ihren offiziellen Quellen
nachinstalliert. Außerdem legt xVAULT automatisch das Kodi-Repository
`repository.xvault` an, damit spätere Updates über Kodi gefunden werden.

LiveTV ist wieder aktiviert. Beim Öffnen lädt xVAULT die Senderlisten von
VAVOO und HUHU, speichert sie als `v-channels.json` und `h-channels.json`
im Add-on-Profil, migriert sie nach `channels.json` und zeigt nur deutsche
Sender mit passender Stream-ID aus `stream-link-auditor.json` an.

## Version

Aktueller Stand: `2026.06.19.1`

Weitere Hinweise zu Abhängigkeiten stehen in
[`DEPENDENCIES.md`](DEPENDENCIES.md).
