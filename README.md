# xVAULT

xVAULT ist ein Kodi-Video-Add-on zum Durchsuchen und Wiedergeben von Filmen, TV-Serien und LiveTV.

## Aktuelle Version

Aktueller Stand: `2026.07.17.6`

Die fuehrende Versionsquelle ist [`addon.xml`](addon.xml). Wenn die Version in `addon.xml` geaendert wird, muss diese README geprueft und bei Bedarf aktualisiert werden.

## Installation

1. Die aktuelle Add-on-ZIP von [xvault.ddnss.de](http://xvault.ddnss.de/) herunterladen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** oeffnen.
3. Die Datei `plugin.video.xvault-2026.07.17.6.zip` auswaehlen.
4. xVAULT starten.

Alternativ kann das Repository-ZIP von [http://xvault.ddnss.de/repository.xvault.zip](http://xvault.ddnss.de/repository.xvault.zip) installiert werden. Danach findet Kodi neue xVAULT-Versionen ueber das Repository.

Kodi installiert die offiziellen Abhaengigkeiten aus den konfigurierten Repositorys. Nicht im offiziellen Kodi-Repo verfuegbare Module wie ResolveURL werden beim ersten Start von xVAULT automatisch aus ihren offiziellen Quellen nachinstalliert.

Weitere Hinweise zu Abhaengigkeiten stehen in [`DEPENDENCIES.md`](DEPENDENCIES.md).

## Nutzung

- Das ausfuehrliche Handbuch steht als GitHub-Pages-Unterseite unter [xvault.ddnss.de/handbuch/](http://xvault.ddnss.de/handbuch/) bereit.
- Filme und Serien ueber die xVAULT-Menues suchen.
- LiveTV ueber deutsche Senderkategorien, Suche oder Favoriten starten.
- Eine Quelle auswaehlen oder Autoplay verwenden.
- Favoriten und Wiedergabestaende optional ueber den Kontenbereich synchronisieren.
- Gesehene Folgen, Staffeln und Serien werden aus den aktuellen Wiedergabestaenden abgeleitet.

## Funktionen

- Suche und Wiedergabe von Filmen, TV-Serien und LiveTV.
- xVAULT kann als Player fuer TMDbHelper genutzt werden, ohne die eigene Quellenlogik, Resolver-Auswahl und Wiedergabeueberwachung zu verlieren.
- Das Playback-Label zeigt beim laufenden Stream Hoster und Indexseite an, z.B. `VOE @ SerienStream`.
- Serien zeigen vorhandene Specials aus TMDB-Staffel 0 als eigenen Staffel-Eintrag an; Sonderfolgen bleiben beim Abspielen echte Serienfolgen.
- SerienStream verwendet `serienstream.to`; alte gespeicherte Domainwerte werden automatisch auf diese Domain migriert.
- SerienStream prueft bei abweichender Anbieter-Staffelzaehlung Episodentitel und Erstausstrahlung, damit Folgen auch dann gefunden werden, wenn TMDB/xVAULT und Anbieter die Staffeln unterschiedlich schneiden; gleiche Veroeffentlichungsdaten mehrerer Folgen werden dabei nicht mehr als eindeutiger Treffer behandelt.
- Serienwiedergaben starten auch dann stabil, wenn Metadaten aus Favoriten, alten Listen oder Android/Kodi-Varianten nur `imdb_id` statt `imdbnumber` liefern; Startfehler werden im Kodi-Log klarer protokolliert.
- VOE-Quellen koennen direkt in xVAULT aufgeloest werden, wenn die installierte ResolveURL-Version die aktuelle VOE-Ausweichdomain noch nicht kennt.
- Nicht aufgeloeste Hoster-Seiten werden nicht mehr als Video an Kodi uebergeben; xVAULT versucht stattdessen weitere Quellen oder meldet, dass keine nutzbare Quelle verfuegbar ist.
- Autoplay und manuelle Streamauswahl begrenzen haengende Resolver- und Player-Starts per Timeout; bei Autoplay probiert xVAULT danach weitere gefundene Quellen und beendet die Wiedergabeueberwachung auch ohne Kodi-Stop-Callback sauber.
- Zuletzt gefundene Quellenlisten fuer Filme und Serien werden kurz fuer die aktuelle Kodi-Sitzung zwischengespeichert. Beim erneuten Quellenwechsel fuer denselben Titel kann xVAULT die Liste wiederverwenden, waehrend Hoster-Links weiterhin frisch aufgeloest und getestet werden.
- Streamquellen fuer Filme und Serien koennen nach bevorzugter Sprache sortiert oder gefiltert werden; mehrere Scraper liefern Deutsch/Englisch-Varianten sauber an die Quellenliste, und Autoplay wird bei Sprache `Alle` automatisch in Dialog oder Verzeichnis umgestellt.
- Die Standard-Aktion `Dialog`, `Verzeichnis` oder `Autoplay` wird beim Start von Filmen und Folgen frisch aus Kodis aktuellem Add-on-Setting gelesen; die Profil-Datei dient als Rueckfall. Alte Favoriten oder externe Aufrufe frieren die Auswahl nicht mehr auf einen frueheren Wert ein.
- Die Standard-Aktion nutzt Kodis native Enum-Speicherung und migriert alte Textwerte automatisch, damit Aenderungen aus den Add-on-Settings auch aus einer aktiven Favoriten- oder Folgenliste heraus fuer die naechste Wiedergabe gelten.
- Filmpalast liest die aktuelle Such- und Quellenstruktur, schuetzt bereits korrekt kodierte Suchpfade vor Doppel-Kodierung und uebernimmt erkannte Hoster erst ohne vorzeitige ResolveURL-Filterung in die Quellenliste.
- Scraper erhalten die aktuelle ResolveURL-Hosterliste, damit Quellen von FHDFilme, HDfilme, Megakino, StreamCloud, TopStreamFilm und aehnlichen Anbietern nicht mehr vorzeitig ausgefiltert werden.
- Die Standard-Aktion `Verzeichnis` liefert Quellenlisten auch aus Favoriten, RPC- und externen Aufrufen wieder als Kodi-Verzeichnis, statt ungewollt in den Dialog zurueckzufallen.
- VIXSTREAM-Playlist-Streams ohne `.m3u8`-Endung werden als HLS erkannt und mit gemeinsamen InputStream-Adaptive-Headern abgespielt, damit Manifest, Segmente und AES-Schluessel erreichbar bleiben.
- Movie4k nutzt die aktuelle API-Struktur ueber `movie4k.sx`; alte Movie4k-Domainwerte werden beim Providercheck automatisch auf die funktionierende Domain migriert.
- Neuer Einstellungsbereich `Indexseiten 3 (DE)` fuer CINE.TO, FILMFANS, NOX, SERIENFANS und STREAMCLOUD.FORUM; der bisherige Bereich `Indexseiten (DE)` heisst jetzt `Indexseiten 1 (DE)`.
- Bei einer frischen Erstinstallation startet xVAULT mit Streamsprache Deutsch und Standard-Aktion Autoplay; bestehende Profile und Updates behalten ihre gewaehlten Einstellungen.
- BS.to ist als optionaler Serien-Scraper eingebunden. Serien, Sprachvarianten und Hoster werden aus der aktuellen Seitenstruktur gelesen; CAPTCHA-geschuetzte Quellen werden ausgeblendet und nicht automatisiert umgangen.
- Fortsetzen von Wiedergaben und automatische Lesezeichen.
- Gesehen/Ungesehen-Status fuer Filme, Folgen, Staffeln und Serien.
- Nach beendeter Wiedergabe wird der Gesehen-Status aktualisiert, ohne dass die Auswahl mehrfach zwischen alter Position und naechster ungesehener Folge springt.
- DNS over HTTPS ist standardmaessig aktiv und kann in den allgemeinen Einstellungen deaktiviert werden. xVAULT nutzt Cloudflare fuer die DNS-Aufloesung seiner HTTP-Anfragen; die aktivierten Indexseiten laufen ueber dieselbe RequestHandler-Logik, feste IPs bleiben nur Rueckfall.
- xVAULT-Synchronisation fuer Favoriten und Wiedergabestaende.
- Die xVAULT-Synchronisation nutzt den neuen API-Host `xvault-sql.ddnss.de` fuer Favoriten- und Binge-/Wiedergabestaende.
- Die Synchronisation gleicht gespeicherte Login-Daten automatisch ab, damit Server-Backups auch nach einem veralteten lokalen API-Key wiederhergestellt werden koennen.
- `Jetzt synchronisieren` bereinigt doppelte lokale Fortsetzen-Eintraege und bricht dadurch nicht mehr mit einem PluginError ab, wenn alte Bookmark-Daten mehrfach vorhanden sind.
- Ueber **Werkzeuge > Support** kann ein redigiertes Diagnosepaket erstellt, nach Bestaetigung hochgeladen und ueber eine kurze Service-ID weitergegeben werden; lokale ZIP-Dateien werden nach dem Upload geloescht.
- Automatische Updatepruefung kann in den allgemeinen Einstellungen aktiviert oder deaktiviert werden.
- LiveTV-Senderliste mit lokalem Cache, Kategorien, Suche, Favoriten, Senderlogos, einstellbarer Stream-Puffergroesse, plattformneutraler HLS-Wiedergabe-Engine, wiederholter HLS-Stabilitaetspruefung, passendem Ersatzstream-Fallback, EPG-Vorschau fuer aktuell laufende und folgende Sendungen sowie einer Senderlisten-Pruefung, die vor dem Start warnt, am Ende per Ergebnisdialog gepruefte, funktionierende und temporaer gesperrte Sender zaehlt und nicht erreichbare Sender temporaer bis zum naechsten xVAULT-Hauptstart ausblendet.
- LiveTV lite liest Deutsche TV-, Österreichische TV- und Schweizer TV-Sender direkt aus der 2ix2-WordPress-API und startet die dort hinterlegten HLS-Streams schlank ohne EPG- oder Favoriten-Schicht; wenn 2ix2 temporaer nicht erreichbar ist, nutzt xVAULT Nydus als Ersatzquelle und loest dort echte HLS-Streams beim Start dynamisch auf.
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

Der Tracking-Code befindet sich in der bestehenden GitHub-Page-Hauptdatei `docs/index.html`, in der Handbuch-Unterseite `docs/handbuch/index.html` und wird fuer die generierten Repository-Listings ueber `tools/build_kodi_zip.py` ausgegeben. Umami ist damit auf allen relevanten GitHub-Pages-Seiten eingebunden.

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

Fuer Android-basierte Fire-TV-Stick-Tests gibt es einen Profil-Simulator unter [`docs/firetv-stick-simulator.md`](docs/firetv-stick-simulator.md). Er ersetzt keinen echten FireOS-ROM-Emulator, hilft aber beim Pruefen von Fire OS, Android-API-Level, RAM, Codec-Klasse und Kodi-Risiken und kann Android-TV-AVD-Testprofile nach dem Amazon-AVD-Vorgehen skizzieren.

Fuer Kodi mit installiertem xVAULT gibt es zusaetzlich `tools/kodi_firetv_test.py`. Der Standardlauf zielt auf `aftmm`, also Fire TV Stick 4K - 1st Gen, und prueft neben Kodi-Smoke-Tests auch lokale Datenbankkonsistenz bei simuliertem Speicher- und Schreibfehlerdruck.
