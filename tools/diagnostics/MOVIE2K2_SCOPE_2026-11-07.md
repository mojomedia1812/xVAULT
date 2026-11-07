# Movie2k2: nur Filme – Nightly 2026.11.07.2

Auf Nutzerauftrag Movie2k2 aus sämtlichen Serien-/Episodensuchen einschließlich Specials ausschließen. Gemeinsame Medienregel vor dem Einplanen der Anbieter, im Cachepfad, bei direkten Anbieteraufrufen und vor dem Auflösen alter Quellenkontexte. Aktueller Scraper und Legacy-Fallback beachten die Regel. Andere Serienanbieter werden nicht ausgeblendet; Movie2k2 bleibt für Filme aktiviert.

Bei der echten Film-Gegenprobe im lokalen Kodi fiel zusätzlich ein bestehender Fehler auf: Movie2k2 liefert den technischen Qualitätszusatz innerhalb der H1-Überschrift. Die allgemeine Metadatenextraktion erkannte beispielsweise „Inception Qualität:“ als Filmtitel und verwarf den Treffer. Der Movie2k2-Scraper entfernt ausschließlich diesen abschließenden UI-Zusatz. Die bestehende Prüfung widersprüchlicher IDs und Jahre bleibt wirksam; ein Test mit gleichnamigen Filmen verschiedener Jahre sichert dies ab.

Gezielte automatische Prüfungen: 66 Tests für Medienrestriktion, Filmidentität, Suchlimits, begrenzte Provideranfragen, signierte Updates, SerienStream und Streamvalidierung bestanden. Die neue Prüfung umfasst Serien-Metadaten, Zahlen-/String-Koordinaten, Specials, beide Scraper, alte Cachewerte und alte Wiedergabekontexte sowie weiterhin erlaubte Filmabfragen.

Lokaler Kodi-Test mit installiertem signiertem Paket, echten Kodi-Python-Modulen und isolierten temporären Cachepfaden. Keine Benutzerfavoriten, Anmeldedaten oder Kontostände für die Tests verändert. Rohdaten unter tools/diagnostics/private/2026-11-07/. Erste Filmproben vor der Qualitätskorrektur werden nicht als erfolgreiche Quellenabnahme gewertet. Finale Film-Gegenprobe und öffentliche Auslieferung separat in den privaten Ergebnissen dokumentieren.

Release 2026.11.01.1 und Statistikseite bleiben unverändert.

Finale Abnahme: Inception (2010) liefert im echten lokalen Kodi nach der Filmkopf-Korrektur zwei Movie2k2-Quellen. Direkte Serien-/Special-Aufrufe bleiben leer; der reale Collector entfernt Movie2k2 aus alten Serien-Caches und verweigert alte Serien-Wiedergabekontexte. Film-, Serien- und Hauptmenü geöffnet. Installiertes Paket als unverändertes Original geprüft. Keine Wiedergabe jedes einzelnen Hosterlinks behauptet.
