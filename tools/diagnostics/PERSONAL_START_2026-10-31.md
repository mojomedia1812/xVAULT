# Persönlicher Startbereich – Nightly 2026.10.31.2

## Umfang

- Persönliche Hauptmenü-Vorschau und „Mein xVAULT“: Weiterschauen, nächste ausgestrahlte reguläre Folge, Serien-Radar, Radiofavoriten und zuletzt gehörte Sender.
- Fortschritt lokal alle 30 Sekunden; vorhandener Sync v2 mit dauerhafter Outbox, fünf Geräteprofilen und Konfliktwahl bleibt führend. Stabile IDs übertragen Positionen auf abweichende lokale Titel; Episoden mit `mediatype=tvshow` werden getrennt gespeichert.
- Radar: TMDb, maximal zwei Staffeln pro Prüfung, 25 Sekunden Metadatenbudget, sechs Stunden Cache, fünf Minuten Fehlerpause und eine Serie pro Service-Durchlauf. Ohne Verlauf die jüngste ausgestrahlte Folge der aktuellen Staffel. Beschränkte deutsche Quellenbeobachtung ohne Wiedergabe/Hosterauflösung; Anbieterangaben sind kein Audio-Nachweis.
- Radio: Kodi AlarmClock/CancelAlarm, Schutz anderer Wiedergaben, lokale Sender-Presets und Rücknahme der temporären globalen Vorgabe.
- Systemcheck: Status ohne automatische Reparatur, explizite Hintergrundprüfung, vorhandene bestätigte Reparatur-/Anmeldewege.

## Verifikation

Lokales Kodi 22 RC1 / Windows x64. Hauptmenü und alle neuen Verzeichnisse per echter JSON-RPC-Verzeichnisabfrage geöffnet und im nativen Kodi-Fenster kontrolliert. Rohdaten bleiben unter `tools/diagnostics/private/2026-10-31/`.

Realer Player mit lokal erzeugter MJPEG-/PCM-Testdatei: Start an einer unter anderem Titel gespeicherten Position von 650 Sekunden, tatsächliche Startposition 651,6 Sekunden. Während laufender Wiedergabe nach 30 Sekunden lokaler Zwischenstand 680 Sekunden. Das Testprofil war temporär, Cloud-Schreibzugriffe und Trakt-Scrobbles im Test deaktiviert. Ein vorhandener fremder Untertitel-Dienst öffnete zunächst einen Fehlerdialog und pausierte die Testwiedergabe; für die Wiederholung vorübergehend deaktiviert und anschließend wieder aktiviert. Die ersten dadurch unbrauchbaren Durchläufe zählen nicht als bestanden.

NDR 2 live wiedergegeben, senderbezogener Modus Eclipse (5) visuell bestätigt. 15-Minuten-Timer über den Kodi-Dialog gesetzt; realen Kodi-Alarm für den Test auf drei Sekunden verkürzt und automatischen Stopp des Radios bestätigt. Testvorgaben anschließend zurückgesetzt.

TMDb lieferte für FBI nach S01E01 die Folge S01E02. Begrenzte Live-Quellenprüfung meldete deutsche Quellen; dies bestätigt die Quellenangabe, nicht die tatsächliche Tonspur jedes Videos.

Automatisierte Prüfungen: bestehende Radio-/Visuals-/Sync-Tests, neue SQLite-/Staffelwechsel-/Timer-Tests, ID-basierter Gerätewechsel und getrennte Episoden, begrenzte HTTP-Antworten, Suchlimits, Providerchecks, Abhängigkeiten, native Plattformauswahl, Filmidentität, SerienStream, VIXSTREAM und signierte Updatepakete.

Keine Änderung an all-stats.de, produktiver Datenbank oder dem geplanten stabilen Funktionsstand 2026.10.30.2. Neue Abonnements und Sender-Vorgaben sind gerätelokal. Metadaten sind keine Zusicherung verfügbarer deutscher Streams.
