# Radio: leere Kodi-Favoritenverwaltung

## Befund

Das übermittelte Supportlog zeigt xVAULT 2026.10.27.4 unter Windows mit Kodi 21.3. Die Genreübersicht öffnet sich; `radioList` mit Genre `80er` bricht am 28.10.2026 um 08:56:13 mit `xVAULT Radio: TypeError` ab. Das bisherige Fehlerhandling protokolliert keine Aufrufstelle.

Im getrennten lokalen Kodi-21.3-Profil liefert die echte JSON-RPC-Abfrage `Favourites.GetFavourites` bei leerer Favoritenverwaltung `favourites: null`. Die bisherige Dictionary-Comprehension in `radio.favorites()` versucht, über `None` zu iterieren. Der Fehler `TypeError: 'NoneType' object is not iterable` wurde so reproduziert. Nur die Normalisierung dieser Antwort im Diagnosetest erlaubte anschließend das Laden der 80er-Liste. Die Senderquelle und der Audioplayer waren für diesen Fehler nicht verantwortlich.

## Korrektur in Nightly 2026.10.28.2

- Fehlendes `favourites`, JSON `null` und leere Favoritenlisten ergeben eine leere Radiofavoriten-Zuordnung. Vorhandene gültige Favoriten werden unverändert weiterverarbeitet; andere Kodi-Favoriten werden nicht als Radiofavoriten behandelt.
- Unerwartete Radiofehler protokollieren zusätzlich den Aufrufpfad. Ausnahmeinhalte und lokale Variablen werden nicht ausgegeben, damit etwaige Stream-Tokens aus Fehlermeldungen nicht übernommen werden.
- Der Release-Kanal bleibt auf 2026.10.28.1. Die Repository-Seite erhält den Nightly-Hinweis und einen korrigierten, nicht auf das Release-Paket zeigenden Nightly-Downloadlink. Das Handbuch erläutert den leeren Favoritenfall.

## Live-Test des fertigen Pakets

Das signierte Nightly-ZIP wurde in ein getrenntes portables Kodi 21.3 installiert. Alle Aufrufe erfolgten per TCP-JSON-RPC über die normale xVAULT-Einstiegsdatei; die Senderliste, Favoritenabfrage und Wiedergabe wurden nicht gemockt. Das normale Kodi-Benutzerprofil bleibt unverändert.

| Prüfung | Ergebnis |
| --- | --- |
| Native Favoritenabfrage | `favourites: null`, erwarteter Ausgangszustand |
| Radio-Hauptmenü | 10 Einträge |
| Genres | 22 Einträge |
| Senderfamilien | 26 Einträge |
| Genre 80er | 252 Einträge einschließlich Navigation |
| Senderfamilie NDR | 39 Einträge einschließlich Navigation |
| Gesamtliste, Seiten 1 und 2 | Je 251 Einträge einschließlich Navigation |
| Leere Radiofavoriten | 0 Einträge, kein Abbruch |
| Suche Deutschlandfunk | 23 Einträge |
| Temporär angelegter Radiofavorit | Genau ein Eintrag mit Favoritenmarkierung; anschließend wieder entfernt |
| Deutschlandfunk MP3 128k | Echter Audioplayer, Geschwindigkeit 1; Wiedergabezeit von 0,419 auf 12,422 Sekunden |

Die Audiowiedergabe wurde nach dem Test beendet. Keine neue `xVAULT Radio:`-Fehlermeldung im Testabschnitt. Dies ist ein Start-/Fortschrittstest, kein Langzeittest und kein eigener Android-/Linux-Livetest.

102 gezielte Tests aus `test_radio`, `test_radio_visualisation`, `test_native_delivery` und `test_release_updates` bestanden. Neue Regressionstests decken leere und fehlende Favoritenwerte, erhaltene Radiofavoriten, die normale Senderlisten-Dispatch-Funktion und die datensparsame Fehlerprotokollierung ab. Rohdaten des lokalen Tests liegen ausschließlich im ignorierten Unterverzeichnis `tools/diagnostics/private/radio-favorites-2026-10-28/`.
