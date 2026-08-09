# Mitwirken

Vielen Dank fuer deine Unterstuetzung.

## Verhaltenskodex

Für alle Beiträge, Issues, Pull Requests und Diskussionen gilt der [`Code of Conduct`](CODE_OF_CONDUCT.md).

## Fehler melden

Bitte nutze GitHub Issues und die Vorlage **Fehler melden**.

Gute Meldungen enthalten:

- eine klare Beschreibung
- Schritte zum Nachstellen
- erwartetes Verhalten
- tatsaechliches Verhalten
- Screenshots oder Logs, falls vorhanden
- Angaben zur xVAULT-Version und Umgebung

## Verbesserungen vorschlagen

Bitte nutze GitHub Issues und die Vorlage **Verbesserung vorschlagen**.

Beschreibe moeglichst konkret:

- was verbessert oder neu eingebaut werden soll
- welches Problem damit geloest wird
- welche Einstellungen oder Bereiche betroffen sind

## Lizenz von Beiträgen

Mit dem Einreichen eines Beitrags bestätigst du, dass dein Beitrag unter der Projektlizenz `GPL-3.0-only` veröffentlicht werden darf.

Wenn du Code aus anderen Projekten übernimmst oder darauf aufbaust, müssen die jeweiligen Lizenz- und Copyright-Hinweise erhalten bleiben. Ergänze bei im Repository gespeichertem Drittcode bei Bedarf [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## README aktuell halten

Wenn du die Plugin-Version in `addon.xml` aenderst, musst du auch `README.md` pruefen und bei Bedarf aktualisieren.

Wenn du Plugin-Einstellungen in `resources/settings.xml` aenderst, hinzufuegst oder entfernst, musst du `README.md` pruefen und bei Bedarf aktualisieren.

Wenn du Funktionen aenderst, musst du die Funktionsuebersicht in `README.md` pruefen und bei Bedarf aktualisieren.

## Kodi-RPC-Testpflicht

Nach jeder Plugin-Aenderung muss die installierte lokale Kodi-Version per JSON-RPC getestet werden.

Der Test muss mindestens pruefen, dass das Add-on startet, die betroffene Funktion ohne Python-Fehler erreichbar ist und Kodi keine neuen xVAULT-Fehler in das Log schreibt. Wenn dabei Fehler auftreten, muessen sie vor der Veroeffentlichung behoben werden.

## GitHub Page

Die bestehende GitHub Page unter `docs/` ist Teil der Kodi-Repository-Funktion. Aendere sie nur defensiv und pruefe, dass Downloadseite, Kodi-Dateilisting, `addons.xml` und Repository-ZIP weiter funktionieren.
