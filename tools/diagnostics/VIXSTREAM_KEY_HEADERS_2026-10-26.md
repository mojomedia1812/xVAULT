# VIXSTREAM: separater HLS-Schlüsselabruf

## Ursache

Das übermittelte `kodi.zip` enthält am 25.10.2026 um 18:35:04 einen HTTP-403-Fehler beim Abruf von `/storage/enc.key`. Das Manifest wurde zuvor erfolgreich geladen. Betroffen: Die Monkees, S01E01, TMDb 7626; Kodi 21.3 unter Windows mit InputStream Adaptive 21.5.25 und xVAULT 2026.10.24.1. Ein weiterer VIXSTREAM-Film zeigt denselben Fehler.

Die bisherige Player-Konfiguration setzte Manifest-, Stream- und Common-Header. InputStream Adaptive 21.5.25 verwendet beim AES-Schlüsselabruf jedoch eine eigene Headerliste aus dem zweiten, durch `|` getrennten Teil von `license_key`. Common-Header sind erst ab Kodi 22 für diesen Fall vorgesehen. Der normale HLS-Manifesttest erkannte den späteren Schlüsselabruf daher nicht als Problem.

Primärquellen:

- [InputStream Adaptive 21.5.25: HLSTree.cpp](https://github.com/xbmc/inputstream.adaptive/blob/21.5.25-Omega/src/parser/HLSTree.cpp): `OnDataArrived`, `keyParts[1]`, `DownloadKey`.
- [Integration](https://github.com/xbmc/inputstream.adaptive/wiki/Integration): Versionierung von `common_headers` und Trennung der Headerkanäle.
- [HLS AES-128 unter Kodi 22](https://github.com/xbmc/inputstream.adaptive/wiki/Integration-DRM#hls--aes-128-play-encrypted-video-stream-from-add-on): `none.license.req_headers`.

## Korrektur

`resources/lib/player.py` übergibt bei den bereits erkannten endungslosen VIXSTREAM-HLS-Playlistadressen die vorhandenen Wiedergabe-Header zusätzlich an den AES-Schlüsselabruf:

- Kodi bis 21: `inputstream.adaptive.license_key = '|' + headers`.
- Kodi ab 22: `inputstream.adaptive.drm` mit `none.license.req_headers`.

Die Schlüsseladresse aus `EXT-X-KEY` bleibt unverändert. Kein fest eingebauter Schlüssel, keine zusätzliche DRM-Lizenz, kein Proxy und keine Abschaltung von HTTPS-Prüfungen. Andere Wiedergabepfade und vorhandene Spracheinstellungen bleiben unverändert.

## Live-Prüfung

Die Testaufrufe wurden per Kodi-TCP-JSON-RPC ausgelöst. Der echte VIXSTREAM-Resolver und die ListItem-Konfiguration des echten xVAULT-Players wurden verwendet. Ein Diagnose-Player unterbindet abschließende Gesehen-/Fortsetzen-/Sync-Schreibvorgänge und beendet den Test nach zwölf Zeitmessungen. Das ist ein Wiedergabestart-/Fortschritts- und Sprungtest, kein vollständiger Durchlauf der Folgen.

| Umgebung | Versuch | Ergebnis |
| --- | --- | --- |
| Installiertes Kodi 22 Beta 1, ISA 22.3.23 | S01E01, neue Konfiguration | H.264-Bild und AAC-Ton; fortlaufende Wiedergabe rund elf Sekunden |
| Separates portables Kodi 21.3, ISA 21.5.25 | S01E01, zusätzliche Schlüsselheader gezielt deaktiviert | Ursprünglicher HTTP 403 für `enc.key` reproduziert; kein Wiedergabefortschritt |
| Dasselbe Kodi 21.3 / ISA 21.5.25 | S01E01, Schlüsselheader aktiviert | H.264-Bild und AAC-Ton; Zeitmessungen von 2,08 bis 13,02 Sekunden |
| Dasselbe Kodi 21.3 / ISA 21.5.25 | S01E02, Schlüsselheader aktiviert, Sprung auf Minute 10 | Bild und Ton; anschließender Fortschritt von 605,21 bis 612,39 Sekunden |

Im korrigierten Kodi-21-Testabschnitt gibt es keine erneute Schlüssel-403-Meldung und keinen `Codec id 27 require extradata`-Fehler. Die Vorher-/Nachher-Prüfung belegt die fehlende Schlüsselheader-Übergabe als Ursache dieses reproduzierten Ausfalls. Andere mögliche 403-Ursachen, beispielsweise serverseitige IP-Sperren, werden dadurch nicht pauschal ausgeschlossen.

63 ausgewählte Regressionstests bestehen: `test_release_updates`, `test_service_provider_checks`, `test_serienstream_episodes`, `test_moflix_identity`, `test_vixstream` und `test_stream_validation`. Der neue Test deckt die Headerkanäle für Kodi 19–23 ab; echte Wiedergabe wurde nur unter den beiden oben genannten Windows-Kodi-Versionen geprüft, nicht unter Android oder Linux.

Testdaten und Sicherungen liegen im ignorierten Verzeichnis `tools/diagnostics/private/vix-key-2026-10-26/`. Die temporären Diagnose-Einstiegspunkte werden nach dem Test entfernt. Die lokale Kodi-Installation erhält den Fix auf Basis von 2026.10.24.1; es wurde weder eine neue öffentliche Version erstellt noch etwas hochgeladen. Die lokale Änderung weicht erwartungsgemäß vom signierten öffentlichen Paket ab.
