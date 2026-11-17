# Scrubs S02E01: Gerätevergleich und unveröffentlichte Korrektur

## Befund

Die Vergleichsabfragen bezogen sich auf Scrubs (2026), IMDb `tt40197357`,
Staffel 2, Folge 1. Lokal waren 16 Quellen gespeichert: SerienStream 6,
OHA 8, Movie2K 2. Auf dem Fire TV waren es nur 2 Movie2K-Quellen.

Auf dem Stick lieferte die alte Domain `www.oha.to` beim Anbietercheck 404;
OHA wurde vor der Suche ausgeschlossen. SerienStream war nach einer vorherigen
zeitüberschreitenden Episoden-Fallbacksuche für Phineas und Ferb S05E21 von
17:12:36 bis 17:22:36 global pausiert. Scrubs wurde um 17:16:13 gesucht.
Die dadurch unvollständige Liste konnte anschließend 30 Minuten im Cache
stehen bleiben, auch nachdem die globale Sperre abgelaufen war.

Movie2K entfernte bei Serien das Suchjahr und verglich lediglich Titel und
Staffel. Ein benachbarter S02E02-Link enthielt die IMDb-ID `tt0285403` der
ursprünglichen Serie; diese stimmt nicht mit der angeforderten Serie überein.

## Korrektur

- Service migriert `www.oha.to` auf `oha.to`. Beim Anbieterladen verhindert
  die alte 404-Markierung dieses Alias die Suche nicht mehr. Ein ausdrücklich
  abgeschalteter Anbieter bleibt abgeschaltet.
- SerienStream erhält wegen des Zeitlimits einer einzelnen Suche keine globale
  Anbietersperre mehr. Entsprechende ältere Sperreinträge werden ignoriert.
  Echte andere Anbieterfehler behalten ihre bestehende Behandlung.
- Alternative Episodensuche mit acht Sekunden Gesamtbudget, begrenzten
  Einzelanfragen und höchstens 24 geprüften Episodenseiten. Eine unvollständige
  Suche darf keine vermeintlich eindeutige andere Folge zuordnen.
- Ausgelassene/fehlgeschlagene Anbieter werden im Cache als fehlend vermerkt.
  Reine Suchzeitlimits werden nach einer Minute erneut geprüft. Bei echten
  Anbietersperren richtet sich die Wiederholungszeit nach deren Ablauf;
  vorzeitige Aufhebung macht den Teilcache ebenfalls ungültig. Vollständige
  Listen behalten ihre normale Laufzeit. Cache-Schlüssel und Anbieterrevisionen
  sind angehoben, damit ältere falsche Ergebnislisten nicht übernommen werden.
- Movie2K prüft Serien anhand übergebener IMDb-ID und IDs aus Anbieter- und
  Streamdaten. Widersprüche werden verworfen. Ohne ID muss ein explizites
  passendes Serienjahr vorliegen; Titel und Staffel allein genügen nicht.

## Tests

51 gezielte Regressionstests bestanden: alte OHA-Markierung, ausdrückliches
Deaktivieren, alte globale SerienStream-Sperre, begrenzte/abgebrochene
Episodenprüfung, kurze Teilcache-Laufzeit, sofortige Wiederverfügbarkeit,
normale vollständige Cache-Laufzeit, widersprüchliche Serien-IDs, positive
Identitätsfälle und bestehende Staffel-/Cache-/Provider-Scope-Prüfungen.

Live im lokalen Windows-Kodi 22 RC1 und per ADB im Fire-TV-Kodi geprüft:

| Prüfung | Windows | Fire TV |
| --- | --- | --- |
| Scrubs (2026) S02E01, frische Suche | 14 | 14 |
| davon OHA | 8 | 8 |
| davon SerienStream | 6 | 6 |
| falsche Movie2K-Treffer | 0 | 0 |
| RAM-Cache ohne erneute Anbieterabfrage | 14 | 14 |
| Datenträger-Cache ohne erneute Anbieterabfrage | 14 | 14 |
| Movie2K-Gegenprobe Scrubs (2001) S02E01 | 2 | 2 |

Im abschließenden Test wurden sowohl eine alte OHA-Domain/404-Markierung als
auch eine noch zehn Minuten gültige alte SerienStream-Timeout-Sperre in den
isolierten Testdaten künstlich gesetzt. Beide Geräte liefern trotzdem die
obigen richtigen Ergebnisse. Warmer Quellenzugriff: etwa 2,2 ms unter Windows
und 11,2 ms auf dem Fire TV. Tests verwenden ausdrückliche Laufzeitprüfungen,
die auch bei optimierter Kodi-Python-Ausführung aktiv bleiben.

Der signierte **private Testbuild 2026.11.17.4** ist auf beiden Geräten
installiert. Unter Windows ist der Dateibaum als original geprüft; auf dem
Fire TV stimmen alle Dateien einschließlich Signaturmanifest mit dem
signierten Paket überein. Die echten OHA-Einstellungen stehen anschließend
auf `oha.to`, Anbieter aktiviert, Erreichbarkeitsstatus `true`.

Ursprüngliche Add-on-Ordner wurden gesichert, Benutzerprofile nicht ersetzt.
Der zwischenzeitlich wieder gestartete Film auf dem Fire TV wurde erst nach
ausdrücklicher Zustimmung des Nutzers für den Neustart beendet.
Kein Test sämtlicher Hosterwiedergaben oder vollständiger Filmlaufzeiten.

**Nichts veröffentlicht:** Hauptmanifest und öffentliche Nightly bleiben
`2026.11.17.3`; keine Änderung an GitHub, Page oder Updatefeeds.
Private Nachweise liegen unter
`tools/diagnostics/private/2026-11-17/scrubs-compare/` und `scrubs-fix/`.

## Veröffentlichungsfreigabe

Vom Nutzer nach erfolgreicher Geräteprüfung als Nightly `2026.11.17.5` freigegeben,
einschließlich öffentlicher Page und DEB. Funktionaler Code unverändert zum
privaten Testbuild `2026.11.17.4`; stabiler Release bleibt `2026.11.17.1`.
