# Fire TV: Empfangsstörungen laufender Streams

## Erhebung

Am 15.11.2026 über den bereits autorisierten ADB-Zugang vom Amazon AFTSSS gelesen: `temp/kodi.log` und `temp/kodi.old.log`, installierter Player-/Quellencode, aktuelle WLAN-Metriken und Kodi-Cache-/Decoder-Einstellungen. Keine Wiedergabe gestartet oder gestoppt, kein Neustart und keine Einstellungsänderung. Rohdaten, SHA256 und maschinenlesbare Zusammenfassung liegen ausschließlich im ignorierten `private/2026-11-15/firetv-streams/`.

Kodi 21.3, xVAULT 2026.11.07.2. Installierte `player.py` und `sources.py` stimmen nach Zeilenendennormalisierung mit dem kanonischen Repository überein.

## Belegt

- 25 Meldungen `Failure when receiving data from the peer(56)` im vorherigen Log vom 14.11., drei im aktuellen Log vom 15.11. Fehler 56 bezeichnet einen Fehler beim Empfang von Netzwerkdaten: https://curl.se/libcurl/c/libcurl-errors.html
- Am 15.11. startet die über SerienStream/VOE aufgelöste Wiedergabe um 12:27:28; um 12:29:37, 12:30:47 und 12:33:40 treten Empfangsfehler mit anschließendem `Reconnect, (re)try 1` auf.
- Am 14.11. wiederholte Empfangsfehler unter anderem ab 13:25:10 und 15:37:28. Betroffene direkte Medienabrufe gehören zur Domain `cloudwindow-route.com`; VOE-Auflösung ist für mehrere dieser Sitzungen im Log sichtbar.
- Kodi versucht die bestehende Verbindung erneut aufzubauen. Ein erneutes xVAULT-Auflösen der ursprünglichen Hoster-Seite während dieser Reconnects ist nicht protokolliert.
- Zusätzlich Android-MediaCodec-Ausgabepufferfehler, teilweise beim Schließen des Players, teilweise bereits während einer folgenden Wiedergabe. Ein eigenständiger Decoderdefekt oder eine kausale Folge der Netzwerkfehler lässt sich daraus nicht abschließend bestimmen.
- Keine Meldung des xVAULT-Startzeitlimits oder des 90-Sekunden-Stillstandsabbruchs in den beiden gelesenen Logs.
- Aktuelle WLAN-Momentaufnahme: 5 GHz, RSSI -56 dBm, ausgehandelte Linkrate 780 Mbit/s. Dies belegt weder den Internetdurchsatz noch die Verbindungsqualität zu den damaligen Fehlerzeitpunkten.

## Einordnung und nächster Ansatz

Die Logs bestätigen Empfangsstörungen bereits laufender Medienabrufe. Sie unterscheiden nicht sicher zwischen CDN-Störung, Störung auf dem Internetpfad oder lokaler Verbindungsunterbrechung. Kein HTTP-403-/Tokenablaufnachweis für die untersuchten Empfangsfehler. Ebenso kein belastbarer Vorher-/Nachher-Nachweis, dass exakt dieselbe Quelle nach manuellem Neustart vollständig durchlief. `eof` allein beweist kein vorzeitiges Ende; normale Folgenenden und Benutzerstopps müssen berücksichtigt werden.

Ein manueller Neustart löst die Hoster-Seite erneut auf und öffnet eine neue Medienverbindung. Das passt zur Nutzermeldung, beweist jedoch keine bestimmte CDN-Ursache. Sinnvoller Folgetest: dieselbe betroffene Quelle mit frischer Auflösung und abgesicherter Fortsetzungsposition vergleichen. Eine mögliche automatische Wiederherstellung muss echte Fehler von bewusstem Stoppen und regulärem Ende unterscheiden, Versuche begrenzen und die ursprüngliche Quelle erhalten. Keine pauschale Cache-/Decoder-Änderung aus diesem Befund ableiten.
