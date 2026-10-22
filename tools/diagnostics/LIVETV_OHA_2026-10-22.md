# LiveTV: OHA-Umstellung, 22.10.2026

## Ursache und Änderung

Das installierte xVAULT 2026.10.20.1 verwendete `POST /mediaurl-catalog.json` und `POST /mediaurl-resolve.json`. Diese Endpunkte liefern HTTP 404. Die aktuelle OHA-Webseite lädt ein Repository-Manifest unter `/mhub-addon.json` und das Live-Manifest unter `/live/mhub-addon.json` mit `specVersion: 2`.

`resources/lib/linear_tv.py` verwendet jetzt:

- `GET /live/catalog/live/channels.json` mit `filter[group]=Germany` und `cursor`;
- den Sendertyp `live`, neue Senderkennungen und `ids.tvg` für die EPG-Zuordnung;
- `GET /live/resolve?url=...` für aktuelle `/live/play/`-Adressen;
- Domain-Fallback bei HTTP 404/451, Server- und Netzwerkfehlern mit gemeinsamem Zeitbudget;
- einen versionierten Cache. Der alte Katalog wird vor der Umstellung gesichert und anschließend neu geladen. Ein veralteter MediaUrl-Katalog wird bei einem Netzfehler nicht als kompatibler Rückfall behandelt;
- Aliase für alte Senderkennungen ausschließlich bei eindeutig gleichem Namen. Mehrdeutige Namen werden nicht automatisch einem neuen Sender zugeordnet.

Das alte Signatur-Ping ist entfernt. Wiederholte oder unvollständig abgearbeitete Cursorfolgen überschreiben den Cache nicht mit einem Teilergebnis. Ein kompatibler neuer Cache bleibt bei einer Netzunterbrechung als Rückfall erhalten.

## Lokale Reparatur

Nur die LiveTV-Laufzeitdatei wurde in die installierte Kodi-Kopie übernommen. Die bereits vorhandenen Änderungen am Geräteabgleich wurden dabei nicht installiert. Das ursprüngliche Modul, der alte Katalog und die Profileinstellungen wurden im ignorierten Diagnoseverzeichnis gesichert.

Die bereits konfigurierte IPTV-Simple-Instanz verwies auf fehlende Dateien. Über die vorhandenen Exportaktionen wurden diese neu erstellt, ohne ihre konfigurierten Pfade zu ändern:

- `xvault-livetv.m3u8`: 1.906 Sender, gültige xVAULT-Plugin-Adressen;
- `xvault-livetv.xml`: 1.906 Kanaldefinitionen und 28.017 Programme, gültiges XML; Programme im Bereich 21.–23.10.2026.

Die API ist dynamisch; Senderzahlen können sich ändern. Der externe Erstabruf enthielt 1.896, der anschließende vollständige Kodi-Abruf 1.906 Einträge einschließlich Varianten.

## Tests

26 automatisierte Tests bestanden: zwölf neue OHA-Regressionstests sowie die 14 bestehenden SerienStream-/Providerchecks. Neue Fälle prüfen GET-Parameter, Typ-/ID-/EPG-Verarbeitung, Auflösung ohne Signaturdienst, Domainwechsel bei 404, begrenztes Verhalten bei Authentifizierungsfehlern, Cachemigration und -rückfall, Cursorwiederholung sowie mehrdeutige Sendernamen.

Live im installierten Windows-Kodi 22 RC1 geprüft:

| Prüfung | Ergebnis |
|---|---|
| LiveTV-Menü | 18 Einträge mit Kategorien |
| Suchergebnis „ZDF HD“ | 7 Einträge |
| ZDF HD (1), direkt aus xVAULT | Wiedergabe startet; Fortschritt über 12 Sekunden |
| PRO7 MAXX (1), direkt aus xVAULT | Wiedergabe startet; Fortschritt über 12 Sekunden |
| IPTV Simple nach sauberem Kodi-Neustart | 1.906 Sender und 28.017 EPG-Einträge geladen |
| ZDF HD (1) über PVR-Kanal-ID | Wiedergabe läuft von 11:09 auf 11:21 weiter |
| Installiertes Modul | SHA256 stimmt mit der Quelldatei überein |
| Finale LiveTV-Logs | Keine neuen Katalog-/Resolverfehler oder Python-Tracebacks im erfolgreichen Lauf |

Die globale PVR-Liste enthält zusätzlich Sender eines bereits vorhandenen anderen PVR-Clients; ihre Gesamtzahl von 2.102 ist daher nicht die Zahl der xVAULT-Sender. Alle Testplayer wurden gestoppt, Kodi bleibt gestartet und IPTV Simple aktiviert.

Beim ersten Versuch, den bereits laufenden PVR-Client kurz aus- und wieder einzuschalten, endete Kodi während der asynchronen PVR-Neuladung. Das Log bestätigte bereits den erfolgreichen Dateiimport, enthält aber keine abschließende Absturzursache. Dieser Vorgang wurde nicht wiederholt. Nach einem vollständigen Kodi-Neustart funktionierten Dateiimport, direkte LiveTV-Wiedergaben und PVR-Wiedergabe. Das Neuladen ist keine Änderung des Plugin-Codes; ein Defekt der nativen PVR-Komponenten ist damit weder bewiesen noch ausgeschlossen.

Die bisherige LiveTV-lite-Implementierung und die Statistikseite wurden nicht verändert. Beim ursprünglichen Prüflauf verwendete Kodi die Add-on-Versionsnummer 2026.10.20.1 mit der reparierten LiveTV-Datei. Für die anschließende Veröffentlichung wurde das vollständige Paket 2026.10.22.1 installiert und nach einem sauberen Kodi-Neustart erneut geprüft. Kodi meldet diese Version als aktiviert; Hauptmenü, Film-/Serienmenüs, LiveTV und LiveTV lite sind erreichbar. Die Repository-Page und das Handbuch werden mit dem Release aktualisiert.

Rohlogs, Sicherungen und JSON-Testresultate befinden sich ausschließlich im ignorierten Ordner `tools/diagnostics/private/2026-10-22/livetv-oha-v2/`. Streamadressen aus Rohlogs dürfen nicht veröffentlicht werden.
