# Daryl Dixon: Staffelzuordnung und Quellen-Cache

Meldung: S02E06 startet S01E06, Quellen werden bei jedem Aufruf erneut gesucht.
Der verwendete Anbieter ist dem meldenden Nutzer unbekannt. Ohne die konkrete
Quelle lässt sich deshalb nicht abschließend belegen, welcher Anbieter die
berichtete falsche Videodatei geliefert hat.

## Nachgewiesene Befunde

- Die direkte SerienStream-Seite meldet für Staffel 1 / Folge 6 „Coming Home“ und
  für Staffel 2 / Folge 6 „Au Revoir Les Enfants“, jeweils mit korrektem SxxExx-Kopf.
- Megakino hat getrennte Daryl-Dixon-Seiten für Staffel 3, 2 und 1. Der bisherige
  Suchtrefferabgleich nahm bei Serien den ersten passenden Titel, ohne die
  Staffel zu berücksichtigen; der Episodenparser wählte danach nur `ep6` dieser
  Seite. Damit kann die richtige Folgennummer aus einer falschen Staffel kommen.
- Ein einziger kurzlebiger SerienStream-`/r?t=...`-Link verhinderte das Speichern
  und Wiederverwenden der gesamten Quellenliste, einschließlich stabiler Treffer
  anderer Anbieter. Das erklärt wiederholte Suchen unabhängig vom HTML-Cache.
- Die Anbieterdateien Megakino, SerienStream und KinoGer sind zwischen den
  veröffentlichten Paketen 2026.11.01.1 und 2026.11.17.1 unverändert. Der
  Quellen-Cache enthält die Add-on-Version im Schlüssel; nach einem Update ist
  deshalb eine einmalige neue Suche erwartbar. Eine konkrete neu eingeführte
  Staffelregression in 2026.11.17.1 wurde nicht nachgewiesen.

## Korrekturen im unveröffentlichten Arbeitsstand

Megakino berücksichtigt explizite Staffelnummern im Treffertitel, in der URL und
im Detailseitenkopf. Widersprüchliche Seiten werden verworfen. SerienStream
speichert statt des vergänglichen Tokens einen HTTPS-Verweis mit Episodenpfad,
Link-ID, Hoster und Sprachkennung. Beim Auflösen wird die genaue Episodenseite
ohne HTML-Cache erneut gelesen und ihre S/E-Kennung geprüft. Nur derselbe Link
mit demselben Hoster und derselben Sprache liefert eine neue Weiterleitung;
keine stillschweigende Auswahl einer anderen Folge oder Quelle.

Alte volatile Einzelzeilen werden im Quellen-Cache ausgelassen, ohne die
anderen stabilen Treffer zu verwerfen. Anbieter-Cacheversionen sorgen für eine
einmalige Neuerstellung bisheriger Treffer. Der Quellen-Cache behält seine
vorhandenen Zeitgrenzen: 30 Minuten frisch, bis sechs Stunden sofort anzeigbar
mit Hintergrundaktualisierung. Die HTML-Cache-Einstellung steuert einen anderen
Cache.

## Verifikation

49 gezielte Tests bestanden: Staffelwahl, getrennte S1-/S2-Cache-Schlüssel,
gemischte volatile/stabile Listen, Datenträger-Neuladen, frische SerienStream-
Weiterleitung und Ablehnung falscher Episoden oder Sprachen sowie bestehende
Quellenfehler-, SerienStream-, Wiedergabewechsel- und Starttests.

Live im installierten Kodi über isoliertes QA-Add-on mit dem geänderten Code:
Megakino wählte ausschließlich die S02-Seite und lieferte eine Quelle für Folge
6. SerienStream lieferte zwei stabile S02E06-Referenzen; eine davon ließ sich von
der frisch abgerufenen richtigen Episodenseite in eine aktuelle Weiterleitung
überführen. Der reale Quellenkollektor suchte beim ersten Aufruf einmal, beim
zweiten Aufruf und nach Leeren des RAM-Caches kein weiteres Mal. Jeweils zwei
Treffer; warmer Zugriff rund 1,5 Millisekunden. Dies prüft Quellenauswahl und
Cache, nicht den tatsächlichen Inhalt einer fremd belegten Videodatei.

Die erste Megakino-QA hatte keine Hosterliste übergeben und lieferte deswegen
keine Quellen. Das Testgerüst wurde korrigiert und der vollständige Durchlauf
mit Hosterliste wiederholt; nur der zweite Durchlauf zählt als bestanden.

Rohdaten und serverseitige HTML-Sicherungen ausschließlich unter
`tools/diagnostics/private/2026-11-17/daryl/`. Die reguläre Installation und
öffentliche Pakete bleiben unverändert. Noch keine Veröffentlichung.

Nach Abschluss des gesamten Umsetzungspakets vom Nutzer zur Veröffentlichung als
Nightly `2026.11.17.3` freigegeben. Die erneute Live-Prüfung bestätigt S02E06,
zwei stabile SerienStream-Verweise und Cache-Nutzung ohne erneute Anbietersuche.
