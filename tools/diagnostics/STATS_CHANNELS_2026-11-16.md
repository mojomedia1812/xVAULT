# all-stats.de: getrennte Kanäle und vollständige Versionsliste

Auftrag: Release, Nightly und Alpha getrennt darstellen, Versionsbegrenzung
entfernen und Nightly-Eingang produktiv prüfen. Kein neues Kodi-Paket.

## Befund

Die produktive Statistik war bytegleich zum gesicherten Stand vom 22.10.2026.
`addon_variant` unterschied lediglich reguläres xVAULT (`stable`) und Alpha;
die Versionstabelle begrenzte sich auf die 20 häufigsten Einträge. Der reguläre
Client sendet die vollständige Nightly-Versionsnummer mit Variante `stable`.
Das ist anhand der Versionsnummer serverseitig eindeutig auflösbar.

Die produktive Datenbank enthält Nightlys. Vor dem Test wurden unter anderem
14 Installationen von 2026.11.16.3, eine von 2026.11.16.2 und 80 von 2026.11.15.2
ermittelt. Die Werte sind eine Momentaufnahme, keine festen Sollwerte.

## Umsetzung und Abnahme

Das neue Modul `api/stats/version_stats.php` klassifiziert vorhandene Daten beim
Lesen und erzeugt die vollständige Versionstabelle mit Kanal und letztem Eingang.
Das vorhandene Dashboard lädt das Modul; seine Anmeldung und alle anderen
Bereiche bleiben erhalten. Unbekannte Versionen werden nicht als Release gezählt.
Keine Umschreibung vorhandener Daten, kein Schemawechsel und keine Änderung
der produktiven Sync-/Telemetrie-API oder Server-Konfiguration.

Drei lokale Tests bestanden: Klassifikation einschließlich alter Clients und
historischer Versionen, mehr als 20 Versionen mit numerischer Sortierung,
Aggregation und HTML-Escaping sowie wiederholbare Integration bei unverändertem
Authentifizierungsblock. Beide PHP-Dateien syntaxgeprüft.

Live über HTTPS auf all-stats.de geprüft:

- Produktive Aggregatabfragen vor und nach der Änderung erfolgreich.
- Eine eindeutig markierte Testinstallation sendete über den echten öffentlichen
  `?action=telemetry`-Endpunkt einen Heartbeat für 2026.11.16.3 mit Variante
  `stable`. Annahme und Datenbankeintrag bestätigt; die neue Auswertung ordnete
  ihn als Nightly ein.
- Testinstallation anschließend gezielt entfernt und Abwesenheit bestätigt.
  Der stündliche Online-Spitzenwert blieb unverändert bei 1422. Keine Sitzung
  oder Ereignis-Rollups für den synthetischen Heartbeat erzeugt.
- Den tatsächlich bereitgestellten Dashboard-Code serverseitig über einen
  temporären, mit zufälligem Header-Schlüssel geschützten QA-Zugang gerendert.
  Die produktive Anmeldung wurde dafür nicht verändert. Die Ausgabe enthielt
  alle drei Kanalgruppen und sämtliche Version-/Kanal-Zeilen der Datenabfrage,
  einschließlich 2026.11.16.3, ohne PHP-Warnungen oder -Fehler.
- Der reguläre Aufruf von `/stats/` ohne Anmeldung liefert weiterhin HTTP 401.
  Authentifizierungsblock bytegleich. Konfiguration, Root-API, Sync-Handler und
  Statistik-`.htaccess` per SHA-256 unverändert bestätigt.
- Temporären QA-Zugang entfernt; danach HTTP 404 bestätigt.

Private Sicherung des bisherigen Dashboards, Vorher-/Nachher-Aggregate,
Testnachweise und serverseitige HTML-Ausgabe liegen ausschließlich unter
`tools/diagnostics/private/2026-11-16/stats/`.

## Ergänzung: Kanalfilter

Über der vollständigen Versionsliste steht ein serverseitiges GET-Formular mit
„Alle“, „Release“, „Nightly“, „Alpha“ und „Unbekannt“. Die Tabelle nennt sichtbare
und gesamte Versionsstände. Diagrammzeitraum und OS-Auswahl bleiben beim Anwenden
erhalten; der Anker führt zur Versionsliste zurück. Kein JavaScript nötig.

Vier lokale Tests einschließlich Filterwechsel, Zurücksetzen, leerer Auswahl,
ungültiger Parameter und Array-Parameter bestanden. Produktiv den tatsächlich
bereitgestellten Dashboard-Code über einen temporären geschützten QA-Zugang
gerendert und alle Filter geprüft: Alle 82, Release 62, Nightly 16, Alpha 1 und
Unbekannt 3 Versionsstände. Ungültige Parameter ergaben korrekt die gesamte Liste.
Die Werte sind Momentaufnahmen. Bestehender Dashboard-Code, Authentifizierung,
Konfiguration und API blieben bytegleich; nur das Statistikmodul wurde ersetzt.
Keine Datenbankänderungen. QA-Zugang entfernt und HTTP 404 bestätigt.
Private Prüfbelege liegen im Unterordner `stats/filter/`.
