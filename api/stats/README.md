# Statistik: Release, Nightly und Alpha

`version_stats.php` ergänzt die vorhandene geschützte PHP-Statistik unter
`https://all-stats.de/stats/`. Die bestehende Anmeldung, Server-Konfiguration und
alle anderen Diagramme bleiben erhalten. Das Dashboard selbst enthält bestehende
Anmeldereferenzen und wird deshalb nicht ins Repository kopiert.

`tools.upgrade_stats_dashboard.upgrade(source)` integriert das Modul in den
vorhandenen Dashboard-Quelltext. Die Funktion erwartet die bekannte Struktur,
bricht bei Abweichungen ab und ist wiederholbar. Vor der Bereitstellung Original
sichern, PHP-Syntax prüfen, zunächst das Modul und anschließend das gepatchte
Dashboard über eine temporäre Datei atomar austauschen. Anmeldereferenzen nicht
ausgeben oder in Git übernehmen.

Die Auswertung leitet den Kanal aus vorhandenen Daten ab; eine Datenbankmigration
oder ein neues Add-on-Paket ist nicht nötig:

- Alpha-Kennung in Add-on-ID, Variante oder Version hat Vorrang.
- Ab dem Kanalschema vom 24.10.2026 bedeutet `YYYY.MM.DD.1` Release und eine
  Tagesrevision ab 2 Nightly, auch wenn ältere Clients die Variante `stable` senden.
- Reguläre Versionen vor diesem Datum folgen dem damaligen Release-/Alpha-Schema.
- Fehlende oder ungültige Versionsangaben bleiben als „Unbekannt“ sichtbar.

Die Kanalübersicht zählt zuletzt gemeldete Installationsstände. Die vollständige
Versionsliste enthält alle gespeicherten Version-/Kanal-Kombinationen ohne
Top-20-Grenze, numerisch absteigend sortiert, mit Installationsanzahl und letztem
Meldezeitpunkt in Serverzeit. Sie ist eine Bestandsübersicht, unabhängig vom
Zeitraum der Diagramme. Beim Update einer Installation wechselt ihr aktueller
Versionsstand; dies ist keine historische Download- oder Ereigniszählung.

Prüfung: `python -B -m unittest tools.tests.test_stats_channels -v`.
Die Tests verwenden ausschließlich eine lokale SQLite-Datenbank mit PHP/PDO.
Live-Abnahme: [16.11.2026](../../tools/diagnostics/STATS_CHANNELS_2026-11-16.md).
