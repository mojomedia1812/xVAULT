# xVAULT

xVAULT ist ein Kodi-Video-Add-on zum Durchsuchen und Wiedergeben von Filmen, TV-Serien und LiveTV.

## Aktuelle Version

Aktueller Stand: `2026.06.29.4`

Die fuehrende Versionsquelle ist [`addon.xml`](addon.xml). Wenn die Version in `addon.xml` geaendert wird, muss diese README geprueft und bei Bedarf aktualisiert werden.

## Installation

1. Die aktuelle Add-on-ZIP von [xvault.ddnss.de](http://xvault.ddnss.de/) herunterladen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** oeffnen.
3. Die Datei `plugin.video.xvault-2026.06.29.4.zip` auswaehlen.
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
- Fortsetzen von Wiedergaben und automatische Lesezeichen.
- Gesehen/Ungesehen-Status fuer Filme, Folgen, Staffeln und Serien.
- xVAULT-Synchronisation fuer Favoriten und Wiedergabestaende.
- Automatische Updatepruefung kann in den allgemeinen Einstellungen aktiviert oder deaktiviert werden.
- LiveTV-Senderliste mit lokalem Cache, Kategorien, Suche und Favoriten.
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

xVAULT ist ein Kodi-Python-3-Add-on und deklariert in [`addon.xml`](addon.xml) `xbmc.python` ab Version `3.0.0`.
