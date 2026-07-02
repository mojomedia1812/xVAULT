# xVAULT

xVAULT ist ein Kodi-Video-Add-on zum Durchsuchen und Wiedergeben von Filmen, TV-Serien und LiveTV.

## Aktuelle Version

Aktueller Stand: `2026.07.02.4`

Die fuehrende Versionsquelle ist [`addon.xml`](addon.xml). Wenn die Version in `addon.xml` geaendert wird, muss diese README geprueft und bei Bedarf aktualisiert werden.

## Installation

1. Die aktuelle Add-on-ZIP von [xvault.ddnss.de](http://xvault.ddnss.de/) herunterladen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** oeffnen.
3. Die Datei `plugin.video.xvault-2026.07.02.4.zip` auswaehlen.
4. xVAULT starten.

Alternativ kann das Repository-ZIP von [http://xvault.ddnss.de/repository.xvault.zip](http://xvault.ddnss.de/repository.xvault.zip) installiert werden. Danach findet Kodi neue xVAULT-Versionen ueber das Repository.

Kodi installiert die offiziellen Abhaengigkeiten aus den konfigurierten Repositorys. Nicht im offiziellen Kodi-Repo verfuegbare Module wie ResolveURL werden beim ersten Start von xVAULT automatisch aus ihren offiziellen Quellen nachinstalliert.

Weitere Hinweise zu Abhaengigkeiten stehen in [`DEPENDENCIES.md`](DEPENDENCIES.md).

## Nutzung

- Filme und Serien ueber die xVAULT-Menues suchen.
- LiveTV ueber deutsche Senderkategorien, Suche oder Favoriten starten.
- Eine Quelle auswaehlen oder Autoplay verwenden.
- Favoriten und Wiedergabestaende optional ueber den Kontenbereich synchronisieren.
- Gesehene Folgen, Staffeln und Serien werden aus den aktuellen Wiedergabestaenden abgeleitet.

## Funktionen

- Suche und Wiedergabe von Filmen, TV-Serien und LiveTV.
- Streamquellen fuer Filme und Serien koennen nach bevorzugter Sprache sortiert oder gefiltert werden; mehrere Scraper liefern Deutsch/Englisch-Varianten sauber an die Quellenliste, und Autoplay wird bei Sprache `Alle` automatisch in Dialog oder Verzeichnis umgestellt.
- Filmpalast liest die aktuelle Such- und Quellenstruktur und uebernimmt erkannte Hoster erst ohne vorzeitige ResolveURL-Filterung in die Quellenliste.
- Bei einer frischen Erstinstallation startet xVAULT mit Streamsprache Deutsch und Standard-Aktion Autoplay; bestehende Profile und Updates behalten ihre gewaehlten Einstellungen.
- BS.to ist als optionaler Serien-Scraper eingebunden. Serien, Sprachvarianten und Hoster werden aus der aktuellen Seitenstruktur gelesen; CAPTCHA-geschuetzte Quellen werden ausgeblendet und nicht automatisiert umgangen.
- Fortsetzen von Wiedergaben und automatische Lesezeichen.
- Gesehen/Ungesehen-Status fuer Filme, Folgen, Staffeln und Serien.
- xVAULT-Synchronisation fuer Favoriten und Wiedergabestaende.
- Automatische Updatepruefung kann in den allgemeinen Einstellungen aktiviert oder deaktiviert werden.
- LiveTV-Senderliste mit lokalem Cache, Kategorien, Suche, Favoriten, Senderlogos, einstellbarer Stream-Puffergroesse, plattformneutraler HLS-Wiedergabe-Engine, wiederholter HLS-Stabilitaetspruefung, passendem Ersatzstream-Fallback und EPG-Vorschau fuer aktuell laufende und folgende Sendungen.
- LiveTV lite liest Deutsche TV-, Österreichische TV- und Schweizer TV-Sender direkt aus der 2ix2-WordPress-API und startet die dort hinterlegten HLS-Streams schlank ohne EPG- oder Favoriten-Schicht.
- Download-, Untertitel- und externe Download-Manager-Optionen.

## Fehler und Vorschlaege melden

Fehler und Verbesserungsvorschlaege bitte ueber [GitHub Issues](https://github.com/mojomedia1812/xVAULT/issues) melden. Dort gibt es Vorlagen fuer Fehlermeldungen und Feature-Wuensche.

Gute Fehlermeldungen enthalten:

- verwendete xVAULT-Version
- Kodi-Version und System
- genaue Schritte zum Nachstellen
- erwartetes und tatsaechliches Verhalten
- Screenshots oder Logs, falls vorhanden

## Umami Analytics

Umami wird zur datenschutzfreundlichen Besuchsstatistik der GitHub Page genutzt. Die Website-ID kommt aus Umami und ist im Tracking-Code der HTML-Seiten unter `docs/` eingetragen.

Der Tracking-Code befindet sich in der bestehenden GitHub-Page-Hauptdatei `docs/index.html` und wird fuer die generierten Repository-Listings ueber `tools/build_kodi_zip.py` ausgegeben. Umami ist damit auf allen relevanten GitHub-Pages-Seiten eingebunden.

Do Not Track wird respektiert, URL-Suchparameter werden nicht gesammelt und Linkklicks auf Downloads, Repository-Dateien, GitHub-Links und wichtige interne Links werden als Umami-Events erfasst. Event-Namen enthalten keine privaten Nutzerdaten.

Es werden keine Zugangsdaten, Secrets, API-Keys oder personenbezogenen Inhalte ins Repository geschrieben. Falls eine Datenschutzerklaerung fuer die oeffentliche Nutzung gepflegt wird, sollte dort die Nutzung von Umami fuer Seitenstatistik und Linkklicks sachlich ergaenzt werden.

## Mitwirken

Hinweise fuer Beitraege stehen in [`CONTRIBUTING.md`](CONTRIBUTING.md).

Bei Aenderungen an Version, Einstellungen oder Funktionen muss diese README geprueft und bei Bedarf aktualisiert werden.

## Changelog

- Repository- und Dokumentationsaenderungen: [`CHANGELOG.md`](CHANGELOG.md)
- Plugin-Versionshistorie: [`CHANGELOG.txt`](CHANGELOG.txt)

## Kompatibilitaet

xVAULT ist ein Kodi-Python-3-Add-on und deklariert in [`addon.xml`](addon.xml) `xbmc.python` ab Version `3.0.0`. LiveTV-HLS funktioniert plattformneutral auf Windows, Linux und Android: xVAULT nutzt automatisch FFmpeg Direct, wenn es auf der Plattform installiert und aktiviert ist, und faellt sonst auf Kodis interne HLS-Wiedergabe zurueck. InputStream Adaptive bleibt als manuell auswaehlbare Alternative erhalten.
