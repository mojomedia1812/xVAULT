# Radio Browser – lokaler Teststand 2026.10.26.4

Dieser Bericht dokumentiert den lokalen Entwurf vor der Freigabe. Während dieser Tests wurden öffentliche Release-/Nightly-Manifeste, Kodi-Repository-Indizes und Page nicht verändert. Der geprüfte Python-Laufzeitcode wird unverändert in Nightly 2026.10.27.2 übernommen.

## Kodi-Technik

- Native Verzeichnisse, MusicInfoTag, Kodi-Bildcache, Dialoge und Add-on-Einstellungen.
- Wiedergabe per `setResolvedUrl` im Kodi-Audioplayer; kein eigener Player, kein ResolveURL und keine Film-/Serien-Watched-Verarbeitung.
- Favoriten per `Favourites.GetFavourites` / `Favourites.AddFavourite`, stabile Sender-UUID im Pluginpfad. Kodis AddFavourite schaltet den Eintrag um. Der bestehende Abgleich von `favourites.xml` erfasst die Radiofavoriten mit.
- Eigener Code nur für Radio-Browser-HTTP/JSON, strenge Filter, Genre-/Familienzuordnung, Variantenwahl und den begrenzten Sendercache.

## Filter und Navigation

`countrycode=DE`, `lastcheckok=1`; zusätzlicher lokaler Filter auch für API-Antworten und Cache. Zusätzliche Betreiber-Metadaten / Verified sind nicht erforderlich. Ein positiver letzter API-Check garantiert keine aktuelle Erreichbarkeit. Vor Wiedergabe erfolgen erneut UUID-/Statusprüfung und ein kurzer Stream-GET. Ein nicht mehr passender Sender wird nicht durch einen ähnlich benannten Sender ersetzt.

API-Abfrage am 26.10. vor dem erweiterten Dublettenabgleich: 6.318 Streamvarianten, 5.201 Programme, 22 Genregruppen, 25 erkannte Senderfamilien und eine Gruppe weiterer Sender. Darunter sind 68 SUNSHINE-LIVE-Programme. 6.063 Varianten ohne Verified-Kennzeichnung werden jetzt ebenfalls berücksichtigt. Genres und Familien sind kombinierbar. Suche, Votes-/Namens-/Bitratensortierung, Kodi-Favoriten und gerätelokaler Hörverlauf sind integriert. Öffentliche Votes werden für den führenden API-Eintrag angezeigt und nicht über Streamvarianten addiert.

Quelle und API-Semantik: [Radio-Browser-Dokumentation](https://api.radio-browser.info/). Der zunächst vorgesehene Verified-Filter wurde auf Benutzerwunsch vollständig aus Abfrage, Validierung und Oberfläche entfernt. Das Cacheformat wurde auf Schema 2 angehoben, damit alte, eingeschränkte Listen unmittelbar neu geladen werden. Die Seitengrenze wurde für den größeren Deutschland-Katalog erweitert; unvollständige Ergebnisse werden weiterhin nicht gespeichert.

## Mehrstufige Dublettenerkennung

- Gleiche Streamadressen werden sofort zusammengefasst. Passende Namen plus dieselbe Betreiber-Domain erkennen Qualitätsvarianten. Fehlende Betreiber-Daten oder nur ähnliche Namen reichen nicht.
- Der Kodi-Service prüft nur plausible Namensvarianten (beispielsweise mit zusätzlichem „Radio“), höchstens sechs Streamadressen pro Durchlauf. Zwischen Durchläufen liegen 15 Sekunden; während einer Wiedergabe startet kein neuer Durchlauf. Die Verzeichnisanzeige wartet auf keine Streamprüfungen.
- Die Weiterleitung wird mit begrenzten HTTP-GETs bestätigt. HTML, leere Antworten und Redirect-Schleifen gelten nicht als Identitätsnachweis. Zielbeobachtungen gelten 24 Stunden; Fehlversuche erhalten sechs Stunden Wartezeit. Abgelaufene, defekte oder fehlgeschlagene Cacheeinträge führen nicht zu einer Zusammenführung.
- Identität berücksichtigt Pfad, Protokoll und Query-Werte. Ausschließlich bekannte Messparameter `sABC`, `aw_0_1st.playerid` und `amsparams` auf programmspezifischen `*.streamabc.net/regc-...`-Adressen werden beim Vergleich ignoriert. Wiedergabe-URLs werden dafür nicht verändert; Routing-/Zugangswerte und andere Anbieter bleiben unverändert.
- Bekannte Programme wie Rock, Dance, NRW und Bayern bleiben getrennt, auch bei widersprüchlich gleichen API-URLs. Eine namenlose Zwischenstation kann solche Programme nicht transitiv zusammenführen.
- Alle ursprünglichen UUIDs und Suchnamen bleiben erhalten. Der Eintrag mit den meisten Votes führt die Gruppe; Votes werden nicht addiert. Identische Zielstreams werden einmal geprüft, bei einem weggefallenen API-Eintrag können weitere IDs derselben Quelle genutzt werden. Unterschiedliche Qualitätsvarianten bleiben als Alternativen erhalten.
- Tests mit einem echten lokalen HTTP-Server bestätigen Weiterleitungen zweier Alias-URLs auf denselben Stream und die Abweisung von HTML und Weiterleitungsschleifen. Weitere Tests prüfen Konflikte, Query-Parameter, TTL, Fehler-Backoff, Limits, Abbruch und die Auflösung alter Favoriten-/Verlaufs-IDs.

## Prüfung

`python -m unittest tools.tests.test_radio tools.tests.test_release_updates tools.tests.test_vixstream tools.tests.test_service_provider_checks -q`: **88 Tests erfolgreich**.

Im installierten lokalen Kodi geprüft:

- Radio-Hauptmenü, Genres, Familien, Sender nach Votes, Genre/Familie kombiniert und Suchergebnisse.
- Erweiterte Dublettenerkennung im echten Kodi-Service: zunächst zwei Einträge „80s80s“ / „80s80s Radio“, nach dem Hintergrundabgleich ein gemeinsamer Eintrag mit drei erhaltenen API-IDs und einem Streamziel. Rock, Dance, NRW und Bayern bleiben separat.
- Ein temporärer nativer Favorit mit der alten „80s80s Radio“-ID erscheint als gemeinsamer „80s80s“-Favorit. Wiedergabe über diese alte ID läuft im Kodi-Audioplayer mit MP3, 192 kbit/s, Stereo und 44,1 kHz. Danach temporären Favoriten entfernt, alle 72 ursprünglichen Favoriten identisch wiederhergestellt und den Hintergrunddienst fortgesetzt.
- MP3, 128 kbit/s, Stereo, 44,1 kHz: knapp eine Minute fortlaufende Wiedergabe.
- HE-AAC, etwa 64 kbit/s, Stereo, 44,1 kHz: fortlaufende Wiedergabe, Titel-/Künstlermetadaten aus dem Stream.
- Nach Filterentfernung: alle 5.201 Programme, SUNSHINE-LIVE-Familie (68 Programme plus Genreordner), Genres und Familien im lokal installierten Kodi erneut geprüft. „Sunshine Live – Die 90er“ spielt als MP3 mit 192 kbit/s, Stereo, 44,1 kHz. Senderlisten werden über Kodis native Sammelfunktion `addDirectoryItems` übergeben. Die Gesamtliste benötigt lokal trotzdem etwa 33 Sekunden; die SUNSHINE-LIVE-Familie etwa 5,5 Sekunden. Die Sammelübergabe allein verbessert diese Gesamtladezeit nicht wesentlich.
- Nativer Favorit hinzugefügt, im Sync-Payload vorhanden, wieder entfernt. Alle 72 vorhandenen Favoriten anschließend identisch. Hintergrundsynchronisation während temporärer Favoritenänderungen pausiert.
- Echter Kodi-Bestätigungsdialog mit simulierter Vote-API: genau ein Aufruf, zweiter Aufruf lokal durch Wartefrist unterdrückt. **Keine öffentliche Teststimme gesendet.** Ablehnung, Abbruch und verlorene Antwort zusätzlich in Regressionstests.
- Simulierter API-Ausfall: Hinweis und zulässige alte Liste. Cache über 48 Stunden zurückgewiesen. Aktuelle Senderprüfung vor Wiedergabe bleibt erforderlich.
- Formatvorgabe nach AAC-Test auf ursprünglichen Wert zurückgesetzt; temporäre Vote-Daten entfernt.
- Signierter installierter Entwurf: `original`, keine fehlenden, veränderten oder zusätzlichen Paketdateien.

Private Rohdaten, Proben und signierte Test-ZIP liegen ausschließlich im ignorierten Verzeichnis `tools/diagnostics/private/2026-10-26/radio-browser/`. Der Entwurf ist keine öffentliche Nightly-Freigabe. Verfügbarkeit einzelner Sender und tatsächliche Radio-Browser-Stimmenannahme hängen weiterhin vom jeweiligen Dienst ab; für die Abstimmung wurden absichtlich keine öffentlichen Teststimmen erzeugt.

## Lokale Prüfung der Menüoptimierung 2026.10.27.3 (27.10.2026)

Ursache in Nightly 2026.10.27.2: Jeder Familienaufruf liest alle Rohdaten, normalisiert 6.318 Einträge mehrfach, gruppiert sie erneut und berechnet sämtliche Ordnerzahlen. Hinzu kommen wiederholte Modulimporte, GUI-Locks bei ListItems ohne Offscreen-Modus und große, ungeteilte Senderlisten.

Änderungen im lokalen Teststand:

- Fertiger Programmkatalog sowie kleine Familien-/Genreübersichten einschließlich kombinierter Filterzahlen werden wiederverwendet. Die Familienansicht lädt keine vollständige Senderliste.
- Quelldatei-Stempel, Add-on-Version, Datenalter und bestätigte Streamziel-Laufzeiten invalidieren den Index. Programmdaten und Metadaten werden atomar geschrieben; der Datenhash wird beim Laden des vollständigen Index geprüft. Externe Änderungen der Rohdatei verwerfen auch alte Window-Daten.
- Kodis Verzeichnis-Cache für Übersichten und revisionsgebundene Ordner-URLs; dynamische Sender-/Favoriten-/Verlaufslisten bleiben ohne Verzeichnis-Cache. Alle neuen ListItems werden offscreen vorbereitet.
- Netzwerkbibliothek erst bei tatsächlichen HTTP-Abrufen importieren. Ein API-Ausfall löst bei vorhandener alter Liste nicht bei jedem Menüwechsel neue Versuche aus: fünf Minuten Wartezeit, weiterhin maximal 48 Stunden alte Daten und aktuelle Sender-/Streamprüfung vor Wiedergabe.
- Große Listen zeigen 250 Sender je Seite. Sortierung, Suche, Genre-/Familienfilter und Favoritenmodus bleiben beim Seitenwechsel erhalten. Unterschiedliche Seiten wurden live auf Überschneidungen geprüft.
- Der Dubletten-Hintergrunddienst baut nach Änderungen den Index im Leerlauf vor und reagiert während der Wartephase zeitnah auf Wartung/Beenden.

Messungen über dieselbe lokale Kodi-JSON-RPC-Schnittstelle, einschließlich Add-on-Start:

| Vorgang | Nightly 2026.10.27.2 | Lokaler Stand 2026.10.27.3 |
| --- | --- | --- |
| Senderfamilien mit vorhandenem Cache | 5,94 s | 1,63 s |
| Senderfamilien innerhalb Dance & EDM | nicht separat gemessen | 1,67 s |
| 80s80s-Senderliste | rund 5–6 s bei vorherigen Familienansichten | 2,01 s |
| Gesamtliste nach Votes | 33,06 s für 4.887 Einträge | 3,15 s für Seite 1 mit 250 Einträgen |
| Zweite Seite | nicht vorhanden | 3,19 s für 250 weitere Einträge |

Einmaliger Aufbau des vorbereiteten Index bleibt nötig, wenn Daten fehlen, ablaufen oder sich ändern. Der erste Aufruf des Vorentwurfs einschließlich Indexaufbau benötigte 6,29 Sekunden; die obigen Endmessungen verwenden den vorhandenen Index. Der direkte GUI-Rücksprung von 80s80s zur Familienübersicht wurde zusätzlich im Kodi-Fenster geprüft und behält die Auswahl bei.

`python -m unittest tools.tests.test_radio tools.tests.test_release_updates tools.tests.test_vixstream tools.tests.test_service_provider_checks -q`: **98 Tests erfolgreich**. Live-Wiedergabe über die alte 80s80s-Radio-ID nach der Umstellung erfolgreich: Kodi-Audioplayer, MP3 192 kbit/s, Stereo 44,1 kHz. Keine öffentlichen Stimmen und keine Favoritenänderungen für diese Optimierung. Während dieser lokalen Tests blieben öffentliche Page und Updatekanäle unverändert. Der identische Python-Laufzeitcode wird anschließend als Nightly 2026.10.27.3 freigegeben.
