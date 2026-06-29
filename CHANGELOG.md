# Changelog

## [Unreleased]

## [2026.06.29.6] - 2026-06-29

- LiveTV-Senderlisten zeigen im Infofeld des markierten Senders jetzt `Aktuell` und `Gleich` aus dem EPG.
- Senderlogos werden als Poster/Thumb/Icon gesetzt, damit im Infofenster links oben das passende Senderlogo erscheint.
- Fehlende Senderlogos werden ueber lokale Alias-Zuordnung und einen gecachten Logo-Fallback ergaenzt.

## [2026.06.29.5] - 2026-06-29

- LiveTV zeigt vor dem Streamstart die aktuell laufende Sendung aus einem lokalen XMLTV-EPG-Cache an.
- EPG-Daten werden mit deutschem Kanal-Mapping lokal zwischengespeichert und auf LiveTV-Sendernamen wie RTL 2, 3sat, 13th Street oder Das Erste abgeglichen.
- LiveTV-Einstellungen um EPG an/aus, EPG-Dialog und EPG-Cachezeit ergaenzt.

## [2026.06.29.4] - 2026-06-29

- LiveTV-Refresh beendet den Kodi-Directory-Aufruf jetzt sauber, damit beim Aktualisieren der Senderliste kein `GetDirectory`-Fehler im Kodi-Log entsteht.
- Live-Test in Kodi 21.3 mit lokaler Installation durchgefuehrt: Senderliste geladen und ein HLS-Sender erfolgreich gestartet.

## [2026.06.29.3] - 2026-06-29

- LiveTV als eigenstaendiges xVAULT-Modul neu integriert.
- Deutsche Sender werden ueber `huhu.to` geladen, lokal gecacht, kategorisiert und erst beim Abspielen aufgeloest.
- LiveTV-Menue mit Kategorien, Suche, Favoriten, Refresh-Aktion und eigenen Einstellungen ergaenzt.
- Historische Texte und GitHub-Page-Hinweise neutralisiert, damit keine alten Quellnamen mehr in den veroeffentlichten Dateien auftauchen.

## [2026.06.29.2] - 2026-06-29

- Einstellung `Automatische Updates aktivieren` im Bereich Allgemein ergaenzt; Standard ist aktiviert.
- Interner Update-Check und automatisches Repository-Bootstrap respektieren die neue Einstellung.
- README, Changelog, Add-on-Metadaten und GitHub Page auf Version `2026.06.29.2` aktualisiert.

## [2026.06.29.1] - 2026-06-29

- Alter LiveTV-/Livestream-Bereich vollstaendig aus Menue, Routing, Einstellungen, Daten und Repository-Playlisten entfernt.
- Eingebettete Altmodule und zugehoerige Senderdaten entfernt.
- README, DEPENDENCIES.md, Add-on-Metadaten und GitHub Page auf Filme/Serien abgeglichen.
- Umami Analytics auf allen GitHub-Pages-HTML-Seiten mit Do-Not-Track, ausgeschlossenen URL-Suchparametern und Link-Events ergaenzt.
- GitHub-Page-Bereich `Neu in` wird beim Build automatisch aus `CHANGELOG.txt` aktualisiert.

## [2026.06.28.10] - 2026-06-28

- Umami-Tracking-Script im Head der GitHub Page ergaenzt.
- Umami-Pixel auf der GitHub Page ergaenzt.
- Episodenstatus wird nach natuerlichem Playback-Ende oder Stop ab 90 Prozent sofort als gesehen gespeichert.
- Folgenlisten werden nach dem Playback ueber den gespeicherten Staffel-Container gezielt neu geladen.

## [2026.06.28.9] - 2026-06-28

- Einstellungsuebersicht aus README.md entfernt; README-Versioncheck entsprechend angepasst.
- Staffel-/Serien-Gesehenstatus wird nach Episoden-Playback sofort aktualisiert und Repository-ZIPs wurden neu gebaut.

## [2026.06.28.8] - 2026-06-28

- GitHub Issue Forms fuer Fehler und Verbesserungsvorschlaege ergaenzt.
- README-Dokumentation auf die aktuelle Plugin-Version `2026.06.28.8` und die Einstellungen aus `resources/settings.xml` abgeglichen.
- Schutzmassnahmen ergaenzt, damit README bei Versions- und Einstellungsaenderungen aktualisiert wird.
- CONTRIBUTING-Hinweise fuer Issues, README-Pflege und GitHub-Page-Schutz ergaenzt.
