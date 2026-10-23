# The Adam Project: Quellenprüfung am 23.10.2026

## Umgebung und Befund

Installiertes Windows-Kodi 22 RC1 mit xVAULT 2026.10.22.1, später dem Stand für 2026.10.23.1. Geprüft wurde „The Adam Project“ (2022), IMDb `tt2463208`. Die gespeicherte lokale Anbieterauswahl enthielt nur MoFlix als Filmquelle; beide gefundenen Einträge scheiterten. Für eine erweiterte Diagnose wurden weitere Anbieter ausschließlich innerhalb eines isolierten Kodi-Interpreters aktiviert. Die gespeicherte Auswahl blieb erhalten. Die erweiterte Abfrage lieferte 29 Einträge; 16 davon wurden untersucht, acht bestanden die bisherige Stream-Prüfung.

| Eintrag | Diagnose |
|---|---|
| MoFlix / Veev | Hoster-Seite erreichbar, Video-CDN nicht erreichbar; TCP-/HTTP-Verbindungs-Timeout. Betriebssystem-DNS und unabhängiges DoH liefern dieselbe Adresse. |
| MoFlix / FileLions | Videolink vorhanden, aber Lese-Timeout am Video-Server. |
| Filmpalast / Vinovo | Resolver meldet „File Not Found or Removed“. Ein anderer Vinovo-Eintrag von Movie2k2 liefert gültige MP4-Daten. |
| Huhu / Vidoza | HTTP 404. |
| Huhu / Server T1 | Veev meldet „Video removed“. |
| Huhu / Doodstream | Aufgelöster Videolink, aber Lese-Timeout am CDN. |
| Huhu / Supervideo | Statt HLS kommen HTML und JavaScript-Weiterleitungen. Auch andere korrekte Referer/User-Agent-Varianten liefern keine Videoliste. Eine Weiterleitung endet auf einer externen Werbe-/Browser-Zwischenseite. Diese Seite wurde nicht als Video akzeptiert. |
| Einschalten / vide0.net | Der Anbieter löst den Hoster bereits korrekt auf. Der zentrale Resolver versucht den endungslosen CDN-Link erneut aufzulösen und verwirft ihn. Derselbe Direktlink spielt in Kodi mehr als zwölf Sekunden weiter. |

Eine generelle Kodi-Wiedergabestörung ist nicht erkennbar: VOE und Byse wurden als Gegenproben mit jeweils mehr als zehn Sekunden Fortschritt abgespielt. Alle drei positiven Gegenproben haben dieselbe Filmlaufzeit von 6.397 Sekunden.

Ein bewusst direkter Test des nicht erreichbaren Veev-CDNs löste Kodis wiederholte native Curl-Timeouts aus und blockierte den Test länger als erwartet. Der Test wurde durch einen Kodi-Neustart beendet. Vorher lief kein Nutzerplayer. Die temporäre Diagnose-Startdatei wurde wiederhergestellt; die Rohlogs vor dem Neustart wurden gesichert.

## Korrektur

- Ist das Anbieter-Ergebnis eine geänderte URL und kein bekannter Hoster-Link, prüft xVAULT zunächst die Mediendaten. Ein gültiger Direktstream wird übernommen, ohne ihn erneut durch ResolveURL zu schicken. Bekannte Hoster-Redirects werden nicht vorab konsumiert; ihre normale Auflösung bleibt erhalten.
- Die zentrale Stream-Prüfung verwendet einen kleinen GET-/Range-Abruf statt HEAD plus unzureichender Dateiendungsprüfung. MP4/weitere Mediencontainer werden anhand ihrer Daten erkannt, HLS anhand von `#EXTM3U`, DASH anhand des MPD-Dokuments. HTML, JavaScript-Zwischenseiten und Fehlerseiten gelten auch bei HTTP 200 und Video-Dateiendung nicht als abspielbar.
- Lehnen Server den Range-Header ab, erfolgt ein zeitlich begrenzter Versuch ohne Range. Wiedergabe-Header bleiben erhalten; Kodi-spezifische Optionen werden nicht als HTTP-Header versendet. Eine ausdrücklich in der Stream-URL enthaltene TLS-Option bleibt auf den einzelnen Abruf beschränkt; es wird kein globaler HTTP-/TLS-Opener verändert.
- Bei einer verworfenen Quelle bleibt die vorhandene Ersatzquellen-Suche zuständig. Gelöschte Dateien oder nicht erreichbare externe Server können durch diesen Plugin-Fix nicht wiederhergestellt werden.

## Prüfung

Acht neue lokale HTTP-/Resolver-Regressionstests prüfen endungslose MP4-Daten, abgelehntes HEAD, echte HLS-Daten einschließlich `.txt`-Adressen, HTML hinter `.m3u8`, HTTP 404, Range-Ablehnung, erhaltene Referer-/User-Agent-Header, einmalige Übernahme eines bereits aufgelösten Direktstreams und die unveränderte Behandlung bekannter Hoster-Redirects.

Die Live-Prüfung verwendet die echten xVAULT-Resolver und den normalen Player in Kodi, mit getrennten lokalen Bookmark-/Playcount-Dateien und deaktiviertem Sync/Trakt ausschließlich im Diagnose-Interpreter. Rohadressen, Benutzerdateien und Sicherungen bleiben unter `tools/diagnostics/private/2026-10-23/` und gehören nicht ins Release. Die Produktions-API benötigt für diese Korrektur keine Änderung.

Mit dem korrigierten Stand wurden drei Wiedergaben über den echten Plugin-/Player-Aufruf gestartet: Einschalten/vide0.net (10,06 Sekunden Fortschritt), Filmo/Byse (10,22 Sekunden) und die Auswahl des nicht abspielbaren Supervideo-Eintrags mit automatischem Wechsel zu Filmo/VOE (10,02 Sekunden). Die Player-Beschriftung bestätigte jeweils den tatsächlich verwendeten Hoster. Alle Testplayer wurden gestoppt, und die temporäre Startdatei wurde durch die Originaldatei ersetzt.

Abschliessende Release-Pruefung fuer 2026.10.23.1: **60 Tests in 203,416 Sekunden bestanden**, ohne uebersprungene Tests, einschliesslich echter MariaDB-Konkurrenztests. Das gebaute ZIP ist vollstaendig mit der lokalen Kodi-Installation abgeglichen. Kodi erkennt die neue Version; Hauptmenue, Film-, Serien- und LiveTV-Menues bestehen den JSON-RPC-Test ohne neue xVAULT-Fehler oder Python-Tracebacks. ZIP-CRC, Python-Syntax, Bildgroessen, lokale Seitenverweise, Paket-Aliase und Kodi-Index-Pruefsumme sind geprueft.
