# Fire TV: Sync und Navigation am 23.10.2026

## Ursache

Echter Amazon Fire TV AFTSSS / sheldonp, Kodi 21.3, xVAULT 2026.10.22.1. Bei jedem Hauptmenü-Aufruf lief der Geräteabgleich synchron vor dem Menüaufbau. Das Hauptmenü ist nicht als Verzeichnis gecacht und wird beim Zurückgehen aus der Suche erneut aufgebaut.

Drei profilierte Hauptmenü-Aufrufe dauerten 26,40 / 27,33 / 26,85 Sekunden. Rund 22,6–23,5 Sekunden entfielen auf den Sync. Im ersten Lauf brauchte das Anwenden lokaler Daten 12,69 Sekunden, darunter 895 Aufrufe zur Übernahme des Gesehen-Status und mehr als 6.000 Cursor-Abfragen. SQLite-Verbindungsabfragen brauchten zusätzlich rund sieben Sekunden; der Sync hält seine lokale Schreibsperre während der Übernahme. Die eigentliche API-Anfrage brauchte rund 0,98 Sekunden, die Updateprüfung 0,16 Sekunden. Die Profilierung selbst erzeugt zusätzlichen Aufwand; diese Werte sind keine unbeeinflusste Kaltstartmessung.

Die Rückkehr aus der Filmsuche wurde anschließend ohne Profiler zweimal mit 29,16 und 26,34 Sekunden, die Rückkehr aus der Seriensuche mit 15,21 Sekunden gemessen. Je nach gleichzeitigem Hintergrundabgleich fallen Sperr- und Arbeitszeiten unterschiedlich aus.

## Änderung

- Das Menü stellt einen kontogebundenen Auftrag über eine Kodi-Window-Property bereit. Der Hintergrunddienst erkennt neue Aufträge innerhalb seines Ein-Sekunden-Polls und bestätigt erfolgreiche Aufträge über ihre Kennung. Neue Aufträge während eines laufenden Abgleichs bleiben für den nächsten Durchlauf erhalten. Netzwerkfehler oder eine belegte Worker-Lease führen zu einem späteren Versuch. Es startet kein an den Menü-Interpreter gebundener Netzwerkthread.
- Dieselbe Übergabe gilt beim Aufwachen. Der Dienst überträgt das Merkmal aktiver Nutzung weiter an die API. Manuelle Synchronisation, Anmeldung und der Abgleich vor der Wiedergabe bleiben erhalten.
- Effektive Wiedergabe-/Gesehen-Stände erhalten lokale Anwendungssignaturen. Unveränderte Einträge erzeugen keine erneuten Playcount-/Bookmark-Schreibvorgänge. Lokale Ereignisse und noch offene lokale Änderungen invalidieren die betroffenen Signaturen, damit auch ein unveränderter Serverstand nach einem Konflikt wiederhergestellt wird. Während Videowiedergaben zurückgestellte Daten werden nicht vorzeitig als angewendet markiert.
- Notwendige Playcount-Änderungen verwenden eine threadlokale Verbindung und eine gemeinsame Transaktion; einzelne Helfer erhalten weiterhin getrennte Cursor mit ihrer jeweiligen Zeilenstruktur. Fehler rollen die Transaktion zurück. Bookmarks werden gemeinsam und atomar geschrieben.
- Status- und Fortsetzen-Abfragen verwenden reine Lesetransaktionen. Unveränderte Sync-Zustandsdaten und unveränderte Favoriten-/Wiedergabedateien werden nicht erneut gespeichert.

## Ergebnis auf dem Fire TV

Sechs Laufzeitdateien wurden nach Sicherung eingespielt. Nach dem Beenden der Wiedergabe mit Zustimmung des Nutzers und dem Kodi-Neustart wurden echte JSON-RPC- und Fernbedienungsaktionen ausgeführt.

| Prüfung | Vorher | Nachher |
|---|---:|---:|
| Hauptmenü, drei RPC-Aufrufe | 26,40–27,33 s, mit Profiler | 1,88 / 3,90 / 3,86 s, ohne Profiler |
| Hauptmenü über Kodi-Oberfläche | nicht separat gemessen | 4,84 s |
| Zurück aus Filmsuche, ohne Profiler | 26,34–29,16 s | 2,22 s |
| Zurück aus Seriensuche, ohne Profiler | 15,21 s | 2,27 s |
| Filmsuche öffnen | 4,06 s, mit Profiler | 3,56 s, ohne Profiler |
| Seriensuche öffnen | 4,25 s, mit Profiler | 3,27 s, ohne Profiler |

Der Hintergrundabgleich blieb aktiv: Der Zeitstempel der letzten Synchronisation stieg weiter an; Anmeldung, Serverrevision und Entitätszahlen blieben erhalten. Vorher und nachher: Revision 21, 118 Favoriten, 196 Fortschritts- und 720 Gesehen-Einträge, keine ausstehenden Operationen. Die Favoritendatei ist bytegleich; beide gesicherten Sync-Datenbanken bestehen `integrity_check`. Nach der ersten Übernahme sind 915 effektive Wiedergabe-/Gesehen-Stände als angewendet erfasst. Die Kodi-Logs enthalten keine neuen Python-Tracebacks oder Sync-/Monitorfehler.

## Weitere Prüfung

Im installierten Windows-Kodi 22 RC1 bestehen erneut die isolierten Fünf-Profil-Tests für Anmeldung, A–B–A-Wechsel, Aufwachen, Offline-Warteschlange, Konfliktentscheidung, echte Bookmark-/Playcount-Speicher, Interpreter-Neustart, Player-Checkpoint/Pause, Erstübernahme und ausbleibende Rückübertragung unveränderter Serverdaten. Die neue Phase `large-snapshot` übernimmt 1.000 Filme in einer Playcount-Verbindung und überspringt die lokale Anwendung beim unveränderten zweiten Lauf. Gemessen: 0,728 Sekunden für den ersten und 0,221 Sekunden für den zweiten gesamten lokalen Testabgleich. Diese Zeiten stammen vom Windows-Rechner, nicht vom Fire TV.

Die automatisierten Regressionstests prüfen zusätzlich unveränderte große Snapshots, eine einzelne geänderte Entität, kontogebundene Hintergrundaufträge ohne direkten Sync, Statusabfragen bei belegter Schreibsperre, Transaktions-Rollback mit Wiederholung sowie die Wiederherstellung eines unveränderten autoritativen Bookmarks nach einem lokalen Konflikt.

Die gesamte Testsuite besteht: **52 Tests in 204,718 Sekunden**, ohne übersprungene Tests. Dazu gehört die Prüfung konkurrierender Transaktionen mit fünf unabhängigen PHP-Prozessen gegen eine ausschließlich lokale MariaDB-Testdatenbank. Python-Syntaxprüfung, README-Versionsprüfung und der abschließende Bytevergleich aller sechs Laufzeitdateien zwischen Repository, Windows-Kodi und Fire TV bestehen ebenfalls.

Der geprüfte Stand ist Bestandteil von Release 2026.10.23.1. Die Repository-Page und die Download-Pakete werden mit diesem Release aktualisiert; die API bleibt unverändert. Rohprofile, Benutzerdateien und Sicherungen liegen ausschließlich in den ignorierten Verzeichnissen unter `tools/diagnostics/private/2026-10-23/`.

Abschliessende Release-Pruefung fuer 2026.10.23.1: **60 Tests in 203,416 Sekunden bestanden**, ohne uebersprungene Tests, einschliesslich echter MariaDB-Konkurrenztests. Das gebaute ZIP ist vollstaendig mit der lokalen Kodi-Installation abgeglichen. Kodi erkennt die neue Version; Hauptmenue, Film-, Serien- und LiveTV-Menues bestehen den JSON-RPC-Test ohne neue xVAULT-Fehler oder Python-Tracebacks. ZIP-CRC, Python-Syntax, Bildgroessen, lokale Seitenverweise, Paket-Aliase und Kodi-Index-Pruefsumme sind geprueft.
