# VOE / Byse: Wiedergabestart in Nightly 2026.11.16.3

Gemeldete Beispiele: Resident Evil (2026) bei Megakino, Matchbox – Der Film
bei Filmo sowie The Fix – Sie ist die Zukunft bei Filmo. VOE spielt im Browser,
xVAULT startet die Quelle nicht; auch Byse ist betroffen.

## Ursache und Korrektur

Das lokale Kodi-Log enthält erfolgreiche VOE-Auflösungen, unmittelbar gefolgt von
`Playback start failed: cannot access local variable 'uuid' where it is not associated with a value`.
Der Fehler wurde durch die Sitzungszuordnung in Nightly 2026.11.16.3 eingeführt:
`player.run` verwendet `uuid` schon am Anfang, hatte aber später im selben
Funktionsrumpf noch einen lokalen Import. Python behandelt dadurch den Namen
im gesamten Funktionsrumpf als lokale Variable. Die frühere Verwendung scheitert
unabhängig davon, ob Geräte-Sync aktiviert ist.

Das ist ein allgemeiner Fehler des Film-/Serienstarts nach der Quellenauflösung,
keine Sperre von VOE oder Byse und kein spezifischer Filmfehler. Der spätere
lokale Import wurde entfernt; beide Stellen verwenden den vorhandenen
Modulimport. Resolver, Zertifikatsprüfung und Wiedergabesitzungsschutz wurden
nicht verändert.

## Prüfungen

Der neue Regressionstest `tools/tests/test_player_start.py` führt den vollständigen
`run`-Einstieg mit seinen Laufzeitimporten aus und prüft, dass Streamöffnung und
Überwachung erreicht werden: ohne Sync sowie mit angemeldetem Sync. Vor der
Korrektur scheiterten beide Fälle, danach bestanden sie. Die frühere
Wiedergabewechsel-QA hatte die Streamöffnung direkt verwendet und diesen
Fehler im davorliegenden Startpfad deshalb übersehen.

48 gezielte Tests für Start, Wiedergabewechsel, Wiederaufnahme, Collections,
Signature und Quellenfehler bestanden.

Live unter lokalem Kodi 22 RC1 mit isoliertem QA-Add-on: echte Anbieterlinks
aufgelöst, mit dem korrigierten produktiven `player.run` gestartet und den
Zeitfortschritt über neun Sekunden protokolliert. Danach die jeweilige
Testwiedergabe bewusst gestoppt. Tests verändern keine persönlichen Sync-/Trakt-
Wiedergabestände. Die Live-Nachweise enthalten Filmtitel, Anbieter, Hoster,
Anbietersprachlabel, bekannte Dauer und gemessenen Fortschritt; dies ist ein
Start-/Kurztest, keine Prüfung der vollständigen Filmlaufzeit oder Tonspur.

Erfolgreiche Gegenproben:

- Resident Evil: VOE von der genannten Megakino-Seite (9,331 Sekunden) und
  deutsch gelistete Byse-Quelle von Filmo (9,416 Sekunden).
- Matchbox: deutsch gelistete VOE-Quelle von Filmo (9,598 Sekunden); Byse
  zunächst über den vorhandenen englisch gelisteten Eintrag (9,539 Sekunden),
  zusätzlich direkt über den auf der Webseite deutsch markierten Byse-Chip
  (9,945 Sekunden).
- The Fix: deutsch gelistete VOE-Quelle (9,499 Sekunden); Byse zunächst über
  den englisch gelisteten Eintrag (9,652 Sekunden), zusätzlich direkt über
  den deutsch markierten Byse-Chip (9,767 Sekunden).

Damit acht erfolgreiche Start-/Fortschrittsprüfungen. Nach der Korrektur kein
`uuid`-Startfehler im aktuellen Kodi-Log. Die Sprachlabels beschreiben die
Anbieterangabe; die tatsächliche Tonspur wurde nicht inhaltlich geprüft.

Private Belege: `tools/diagnostics/private/2026-11-16/resident-evil/`.
Während der isolierten QA wurde das reguläre installierte xVAULT nicht verändert.
Die Korrektur wurde zunächst ausschließlich lokal geprüft.

## Lokale Installation zum Nutzertest

Anschließend auf ausdrücklichen Nutzerwunsch als privater, signierter Testbuild
2026.11.16.4 in das reguläre lokale Kodi installiert. Paket mit 184 Dateien und
installierten Dateibaum geprüft: Signatur gültig, Integritätsstatus `original`.
Kodi wurde im Leerlauf beendet, der bisherige Add-on-Ordner unter
`private/2026-11-16/resident-evil/local-testbuild/installed-before/` gesichert und
der geprüfte Dateibaum ausgetauscht. `addon_data` wurde nicht ausgetauscht.

Nach Neustart meldet Kodi per JSON-RPC 2026.11.16.4, aktiviert; das echte
xVAULT-Hauptmenü liefert 19 Einträge und wurde für den Nutzertest geöffnet.
Öffentliche Pakete, Repository-Feed und Quellversionsnummer bleiben 2026.11.16.3.

## Öffentliche Nightly 2026.11.16.5

Nach ausdrücklicher Nutzerfreigabe zur Veröffentlichung als 2026.11.16.5
vorbereitet. Der private Testbuild 2026.11.16.4 bleibt unverändert. ZIP-Vergleich:
identische Dateimenge und identischer Programmcode; Unterschiede ausschließlich
`addon.xml`, beide Changelogs und signiertes Integritätsmanifest.

91 kombinierte Regressionstests bestanden. Der erste kombinierte Durchlauf
deckte eine Testisolation auf: ein schon importiertes echtes Modul blieb am
Elternpaket zwischengespeichert. Der neue Starttest isoliert nun auch das
Elternpaket; die vollständige Auswahl besteht unabhängig von den übrigen
Modulimporten. Keine zusätzliche Änderung am produktiven Player dafür nötig.

Signiertes Originalpaket mit 184 Dateien geprüft. Öffentlicher stabiler Katalog
und Release-Indizes bytegleich erhalten. Nightly-Feed, Webseite und Kodi-Indizes
auf 2026.11.16.5 ausgerichtet. Öffentliche Download-Adressen und DEB-Eintrag
werden nach Bereitstellung separat verifiziert. Private Publikationsnachweise
im Unterordner `resident-evil/publication/`.
