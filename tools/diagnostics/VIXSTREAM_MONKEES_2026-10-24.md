# VIXSTREAM / Die Monkees: lokale Prüfung vom 24.10.2026

## Befund

Geprüft wurde das installierte Windows-Kodi 22 RC1 mit xVAULT 2026.10.23.1. Die Suche liefert „Die Monkees“ (1966), IMDb `tt0060010`, TMDB `7626`. Staffel 1, Folgen 1–7 wurden jeweils über den echten xVAULT-Quellenresolver und Player gestartet. Die Diagnose verwendet ausschließlich VIXSTREAM, frische Quellenabfragen, getrennte Bookmark-/Playcount-Dateien und deaktivierten Konten-/Trakt-Abgleich im Diagnose-Interpreter. Die gespeicherten Benutzereinstellungen bleiben erhalten.

Der gemeldete vollständige Wiedergabeausfall war hier mit der veröffentlichten Version nicht reproduzierbar: Alle sieben Folgen starteten mit H.264-Bild und AAC-Ton und liefen jeweils mehr als acht Sekunden weiter. Die tatsächlichen Laufzeiten liegen bei ungefähr 25 Minuten. Daraus folgt keine Bestätigung einer Wiedergabe auf Peters unbekanntem Gerät bzw. seiner Kodi-/Add-on-Version.

Bestätigt sind dagegen zwei Plugin-Probleme:

- VIXSTREAM meldet die angeforderte Sprache (`lang=de`) auch ohne nachgewiesene Audiosprache als Deutsch. Die Monkees-Manifeste enthalten keine Sprachkennung; Kodi meldet `und`. Der Nutzer bestätigt englischen Ton. Die alte Quellenliste behauptet außerdem pauschal 1080p, obwohl das Master-Manifest nur eine SD-Variante ausweist und Kodi ungefähr 720×544 Pixel decodiert.
- Der Wiedergabe-Header-Sonderfall erfasst nur `vixcloud.co`, während der aktuelle Anbieter die Manifestadresse unter `vixsrc.to/playlist/...` liefert. Der erste native Kodi-Zugriff protokolliert vor der Korrektur einen `CCurlFile::Stat`-HTTP-Fehler. InputStream Adaptive kann die Wiedergabe hier anschließend dennoch starten. Ein Zusammenhang mit Peters Totalausfall ist damit nicht bewiesen.

## Lokale Korrektur

- HLS-Master und untergeordnete Videolisten werden auf gültigen Inhalt geprüft, mit begrenzter Verschachtelung und Schleifenschutz. HTML-/Fehlerseiten werden auch bei HTTP 200 verworfen.
- Nur nachgewiesene deutsche oder englische Tonspuren erhalten das entsprechende Sprachlabel. Ein Anforderungsparameter und deutsche Untertitel sind kein Sprachnachweis. Ohne Kennung bleibt die Quelle als „Sprache unbekannt“ verfügbar; der bestehende Sprachfilter entscheidet über Anzeige oder Ausschluss. Den vom Nutzer als Englisch erkannten, aber nicht maschinenlesbar gekennzeichneten Ton behandeln wir nicht als verifiziertes Deutsch.
- Die Qualitätsangabe stammt aus der HLS-Auflösung. Die sieben Monkees-Folgen erscheinen als SD. Unbekannte Sprachvarianten werden nicht doppelt für deutsche und englische Anforderungsparameter angezeigt.
- Eine VIXSTREAM-Anbieterrevision ist Teil des Quellen-Cache-Schlüssels. Alte, falsch beschriftete Treffer werden bei der nächsten Suche nicht wiederverwendet.
- Der erste Kodi-Zugriff auf endungslose `/playlist/<ID>`-Manifeste behält seine Wiedergabe-Header auch auf der aktuellen und auf konfigurierbaren Ersatzdomains.

## Nachprüfung

Alle sieben Folgen wurden nach Einspielen der drei geänderten Laufzeitdateien erneut über den normalen Plugin-Player gestartet. Alle sieben frisch abgeschlossenen Diagnose-Interpreter bestätigen `language=unknown`, `quality=SD` und die sichtbare Angabe „Sprache unbekannt“.

| Folge | Fortlaufende Wiedergabe nach Korrektur |
|---|---:|
| S01E01 | 9,94 s |
| S01E02 | 8,21 s |
| S01E03 | 8,02 s |
| S01E04 | 8,22 s |
| S01E05 | 9,91 s |
| S01E06 | 9,92 s |
| S01E07 | 10,17 s |

Ein weiterer echter Kodi-Quellenlauf mit „nur Deutsch“, strengem Sprachfilter und ausgeschlossenen unbekannten Sprachen liefert für Folge 1 korrekt keinen VIXSTREAM-Treffer. Es wird keine englische bzw. unbestätigte Tonspur als deutscher Treffer ausgegeben. Bei der unveränderten lokalen Einstellung „Deutsch bevorzugen / unbekannte Sprachen behalten“ bleiben die unbekannten Quellen auswählbar.

19 gezielte Regressionstests (`tools.tests.test_vixstream` und `tools.tests.test_stream_validation`) bestehen. Sie prüfen unter anderem fehlende Kennungen, englischen Ton in untergeordneten Listen, verifizierten deutschen Ton, Untertitel, defekte Listen, Schleifen, Cache-Invalidierung und Header auf Ersatzdomains. Dies ist kein erneuter Lauf der gesamten Sync-/MariaDB-Testsuite.

Der Laufzeitstand ist im installierten Kodi bytegleich zum Repository geprüft. Nach der Korrektur treten weder neue Python-Tracebacks noch VIXSTREAM-Anbieterfehler oder die zuvor beobachteten nativen Manifest-Stat-Fehler auf. Alle Testplayer sind beendet und die ursprüngliche Startdatei ist wiederhergestellt. Rohadressen, HLS-Token, Diagnoseprofile und Sicherungen liegen ausschließlich unter dem ignorierten `private/2026-10-24/vixstream/`.

Dieser Stand ist lokal installiert und noch nicht veröffentlicht. Die genaue Ursache von Peters ursprünglichem Wiedergabeausfall bleibt ohne seine Geräte-/Versionsangaben oder ein zugehöriges Log offen.
