# Geräteabgleich – lokale Abnahme am 20.10.2026

Entwicklungsstand auf Basis von xVAULT 2026.10.20.1. Noch kein Release und keine Änderung an all-stats.de oder der öffentlichen Repository-Seite.

Nachprüfung für Release 2026.10.22.1 am 22.10.2026: Alle 47 Tests der gesamten Testsuite bestehen einschließlich der echten MariaDB-Sperrprüfung. Das vollständige Release-Paket wurde im installierten Kodi mit fünf isolierten Profilen erneut geprüft: Anmeldung, A–B–A-Wechsel, Offline-Warteschlange, Konfliktentscheidung, echte Bookmark-/Playcount-Speicher, Interpreter-Neustart, Player-Checkpoint und Pause, Erstübernahme sowie ausbleibende Rückübertragung unveränderter Serverdaten. Die produktive API wurde nach vollständiger Datenbank- und Dateisicherung aktualisiert. HTTPS-Prüfungen mit einem getrennten temporären Konto bestätigen fünf Sitzungen, parallele Änderungen, Geräteverlauf, idempotente Wiederholung, Konfliktentscheidung, Schutz vor alten Clients und gezielten Gerätewiderruf. Das Testkonto und temporäre Serverhelfer wurden entfernt; die Statistikdateien und Serverkonfiguration sind unverändert. Die folgenden Abschnitte dokumentieren den ursprünglichen Abnahmelauf.

## Testumgebung

- Installiertes Kodi 22 RC1 unter Windows, Steuerung über JSON-RPC auf `127.0.0.1:9090` und sichtbare Prüfung der Kodi-Dialoge.
- Tatsächliche Sync-Module und Player-Callbacks des Entwicklungsstands wurden vorübergehend in die installierte Add-on-Kopie übernommen. Anschließend wurden elf Laufzeitdateien aus der Sicherung wiederhergestellt bzw. neu hinzugefügte Testdateien entfernt. Die ursprünglichen Dateihashes stimmen; Kodi meldet wieder die aktivierte Version 2026.10.20.1, das Serienmenü liefert acht Einträge und es läuft kein Testplayer.
- Separate Testprofile A bis E im selben Kodi, anschließend zusätzliche Profile F/G zur Prüfung der Erstübernahme. Das simuliert mehrere Installationen; es ist kein Test auf fünf physischen Geräten und kein Fire-TV-Test.
- Lokale PHP-Testserver, PHP 8.4 und portable MariaDB 11.4.8. Alle Dienste ausschließlich auf Loopback. Zusätzlich SQLite als isolierter API-Testadapter.
- Echte Produktionshandler für Anmeldung, Schlüsselprüfung, Migration, Abgleich und Protokoll. Testadapter ersetzt nur Konfiguration und Datenbankbereitstellung.
- Eigenständige Favoriten-, Bookmark-, Playcount-, Auth- und SQLite-Dateien in einem ignorierten Testverzeichnis. Echte Konten und ihre Serverdaten wurden nicht für die Sync-Tests verwendet.

## Automatisierte Prüfung

35 unterschiedliche Testmethoden über Gesamtlauf und gezielte Nachläufe bestanden: 14 bestehende SerienStream-/Providerprüfungen, 12 API-/Datenbankprüfungen und 9 Clientprüfungen. Der Gesamtlauf mit 32 Methoden bestand; die danach ergänzten Migrations-, Erstimport- und Rückkopplungsprüfungen sowie betroffene Clienttests bestanden separat.

Geprüft wurden insbesondere:

- fünf gleichzeitig gültige Geräteanmeldungen einschließlich bestehender Kontoschlüssel;
- A → B → A mit nachvollziehbaren Änderungsautoren;
- fünf unabhängige PHP-Prozesse gegen dieselbe MariaDB: fünf unabhängige Änderungen bleiben erhalten; bei fünf widersprüchlichen Feldänderungen wird genau eine angenommen, vier bleiben als Konflikte erhalten;
- Zusammenführen unabhängiger Felder, Löschmarken und bewusste Wiederherstellung;
- Wiederholung nach verlorenem Antwortpaket ohne doppelte Verarbeitung;
- Gerätebindung, gezielter Sitzungswiderruf und Widerruf aller Sitzungen nach Kennwort-Reset;
- Sperren alter schreibender Clients nach der Kontoumstellung;
- getrennte Wiedergabesitzungen, ignorierte veraltete Zwischenstände, bewusstes Zurückspulen und falsche Geräteuhren;
- manuelle Gesehen-/Ungesehen-Markierungen, gemeinsame Inhaltsschlüssel und gleiche Schlüsselberechnung in Python/PHP;
- Migration bestehender Serverfavoriten, Löschmarken, Fortschritte und manueller Markierungen;
- dauerhafte Offline-Warteschlange über einen Interpreter-Neustart und lokale Änderungen während einer laufenden HTTP-Anfrage;
- keine Änderung lokaler Lesezeichen während laufender Videowiedergabe;
- Erstübernahme fehlender lokaler Favoriten und Wiedergabestände sowie Sicherung des ursprünglichen lokalen Verlaufs;
- keine künstlichen Uploads durch die Sortierung gleichzeitig hinzugefügter Favoriten.

PHP-Lint, Python-Syntax, XML der Einstellungen, Versionsabgleich mit README und `git diff --check` waren erfolgreich.

## Im installierten Kodi geprüft

1. Fünf getrennte Testprofile melden sich beim lokalen Server an und bleiben gleichzeitig angemeldet.
2. A fügt einen Favoriten hinzu; B übernimmt ihn nach dem Aufwachen. Eine Änderung auf B erscheint anschließend auf A.
3. Eine simulierte Netzunterbrechung hinterlässt eine dauerhafte ausstehende Änderung; nach Wiederverbindung erscheint diese auf E.
4. Ein Fortsetzungspunkt von 20 Minuten wird in Kodis tatsächlichen Bookmark-Speicher auf B übertragen. Eine konkurrierende Position von 10 Minuten bleibt erhalten und wird nach bewusster Auswahl auf A übernommen.
5. Manuelle Gesehen-/Ungesehen-Markierungen wirken auf die tatsächliche lokale Playcount-Datenbank und entfernen veraltete Fortsetzungspunkte.
6. Getrennte Kodi-Python-Aufrufe behalten Anmeldung und Kontostand für alle fünf Profile.
7. Der tatsächliche xVAULT-Player-Checkpoint und `onPlayBackPaused` speichern zunächst 15 Minuten und anschließend ein bewusstes Zurückspulen auf 10 Minuten. C übernimmt den zweiten Stand.
8. Die Geräteübersicht zeigt die fünf Testgeräte. Der Änderungsverlauf zeigt Geräte, Aktionen und Positionen. Die Fortsetzungsauswahl zeigt konkurrierende Positionen; die visuell gewählte Position von 5 Minuten wird bestätigt, der Konflikt geschlossen und ein neuer Sitzungszweig angelegt.
9. Vorhandene lokale Favoriten und ein alter lokaler Wiedergabestand von 15 Minuten werden beim ersten Login von F übernommen und anschließend auf G sichtbar.
10. Unabhängige Favoritenänderungen auf C/D bleiben erhalten; ein weiterer Abgleich erzeugt keine künstliche Änderung.

Die ersten Durchläufe deckten unterschiedliche Schlüssel für Wiedergabe und manuelle Filmmarkierung auf; dies wurde korrigiert und mit Regressionstests sowie erneutem Kodi-Test geprüft. Ein anfänglich fehlgeschlagener Callback-Test beruhte auf nicht rekonstruierten Einstellungen im Testadapter; der Adapter lädt nun die gespeicherte Testanmeldung vor jedem Profilwechsel.

Kodi war zunächst im Hintergrund; dadurch blieb eine Dialog-Schließanimation stehen und JSON-RPC-Eingaben wurden ignoriert. Nach Aktivieren des Kodi-Fensters waren die Dialoge normal bedienbar. Es entstand kein neuer Python-Fehler im Kodi-Log durch die geprüften Sync-Abläufe. Bereits vorhandene, unabhängige Telemetrie-Warnungen des installierten Alpha-Add-ons gehören nicht zu diesem Test.

## Veröffentlichung und Grenzen

Die neue API muss gemeinsam mit dem neuen Plugin ausgerollt werden. Nach der ersten Kontoumstellung dürfen alte Clients nicht weiter schreiben; sie erhalten eine Aktualisierungsaufforderung. Bereits ungültige alte Anmeldungen benötigen einmalig eine neue Anmeldung. Die Servermigration behält bestehende Tabellen; ein produktives Datenbankbackup bleibt vor der Einführung erforderlich.

Die Tests bestätigen das Verhalten auf dem installierten Windows-Kodi und echte konkurrierende MariaDB-Transaktionen. Netzlatenzen realer Geräte, Android-Suspend und sehr große Konten sind damit nicht separat auf Hardware geprüft. Für persönliche Konten wird ein konsistenter vollständiger Antwort-Snapshot verwendet; lokale Uploads bestehen aus Änderungen.

Rohdaten, lokale Testzugänge, fehlgeschlagene Zwischenläufe und Sicherungen liegen ausschließlich unter `tools/diagnostics/private/2026-10-20/device-sync/`. Sie dürfen nicht ins Release oder ins Repository gelangen.

Die beiden dauerhaften lokalen PHP-Testserver und die portable MariaDB wurden nach Abschluss beendet. Die Änderungen am Entwicklungsrepository sind lokal und noch nicht committet oder veröffentlicht.
