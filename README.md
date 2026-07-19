# xVAULT

xVAULT ist ein Kodi-Video-Add-on zum Durchsuchen und Wiedergeben von Filmen, TV-Serien und LiveTV.

## Aktuelle Version

Aktueller Stand: `2026.07.19.1`

Die führende Versionsquelle ist [`addon.xml`](addon.xml). Wenn die Version in `addon.xml` geändert wird, muss diese README geprüft und bei Bedarf aktualisiert werden.

## Installation

1. Die aktuelle Add-on-ZIP von [xvault.ddnss.de](http://xvault.ddnss.de/) herunterladen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** öffnen.
3. Die Datei `plugin.video.xvault-2026.07.19.1.zip` auswählen.
4. xVAULT starten.

Alternativ kann das Repository-ZIP von [http://xvault.ddnss.de/repository.xvault.zip](http://xvault.ddnss.de/repository.xvault.zip) installiert werden. Danach findet Kodi neue xVAULT-Versionen über das Repository.

Kodi installiert die offiziellen Abhängigkeiten aus den konfigurierten Repositorys. Nicht im offiziellen Kodi-Repo verfügbare Module wie ResolveURL werden beim ersten Start von xVAULT automatisch aus ihren offiziellen Quellen nachinstalliert.

Weitere Hinweise zu Abhängigkeiten stehen in [`DEPENDENCIES.md`](DEPENDENCIES.md).

## Nutzung

- Das ausführliche Handbuch steht als GitHub-Pages-Unterseite unter [xvault.ddnss.de/handbuch/](http://xvault.ddnss.de/handbuch/) bereit.
- Filme und Serien über die xVAULT-Menüs suchen.
- LiveTV über deutsche Senderkategorien, Suche oder Favoriten starten.
- Eine Quelle auswählen oder Autoplay verwenden.
- Favoriten und Wiedergabestände optional über den Kontenbereich synchronisieren.
- Gesehene Folgen, Staffeln und Serien werden aus den aktuellen Wiedergabeständen abgeleitet.

## Funktionen

- Suche und Wiedergabe von Filmen, TV-Serien und LiveTV.
- xVAULT kann als Player für TMDbHelper genutzt werden, ohne die eigene Quellenlogik, Resolver-Auswahl und Wiedergabeüberwachung zu verlieren.
- Das Playback-Label zeigt beim laufenden Stream Hoster und Indexseite an, z.B. `VOE @ SerienStream`.
- Serien zeigen vorhandene Specials aus TMDB-Staffel 0 als eigenen Staffel-Eintrag an; Sonderfolgen bleiben beim Abspielen echte Serienfolgen.
- SerienStream verwendet `serienstream.to`; alte gespeicherte Domainwerte werden automatisch auf diese Domain migriert.
- SerienStream prüft bei abweichender Anbieter-Staffelzählung Episodentitel und Erstausstrahlung, damit Folgen auch dann gefunden werden, wenn TMDB/xVAULT und Anbieter die Staffeln unterschiedlich schneiden; gleiche Veröffentlichungsdaten mehrerer Folgen werden dabei nicht mehr als eindeutiger Treffer behandelt.
- Serienwiedergaben starten auch dann stabil, wenn Metadaten aus Favoriten, alten Listen oder Android/Kodi-Varianten nur `imdb_id` statt `imdbnumber` liefern; Startfehler werden im Kodi-Log klarer protokolliert.
- VOE-Quellen können direkt in xVAULT aufgelöst werden, wenn die installierte ResolveURL-Version die aktuelle VOE-Ausweichdomain noch nicht kennt.
- Nicht aufgelöste Hoster-Seiten werden nicht mehr als Video an Kodi übergeben; xVAULT versucht stattdessen weitere Quellen oder meldet, dass keine nutzbare Quelle verfügbar ist.
- Autoplay und manuelle Streamauswahl begrenzen hängende Resolver- und Player-Starts per Timeout; bei Autoplay probiert xVAULT danach weitere gefundene Quellen und beendet die Wiedergabeüberwachung auch ohne Kodi-Stop-Callback sauber.
- Zuletzt gefundene Quellenlisten für Filme und Serien werden kurz für die aktuelle Kodi-Sitzung zwischengespeichert. Beim erneuten Quellenwechsel für denselben Titel kann xVAULT die Liste wiederverwenden, während Hoster-Links weiterhin frisch aufgelöst und getestet werden.
- Streamquellen für Filme und Serien können nach bevorzugter Sprache sortiert oder gefiltert werden; mehrere Scraper liefern Deutsch/Englisch-Varianten sauber an die Quellenliste, und Autoplay wird bei Sprache `Alle` automatisch in Dialog oder Verzeichnis umgestellt.
- Die Standard-Aktion `Dialog`, `Verzeichnis` oder `Autoplay` wird beim Start von Filmen und Folgen frisch aus Kodis aktuellem Add-on-Setting gelesen; die Profil-Datei dient als Rückfall. Alte Favoriten oder externe Aufrufe frieren die Auswahl nicht mehr auf einen früheren Wert ein.
- Die Standard-Aktion wird über einen xVAULT-eigenen Auswahl-Dialog gespeichert und migriert alte `hosts.mode.v2`-/`hosts.mode`-/`default.action`-Werte automatisch, damit Kodi-Defaultwerte die Auswahl nicht mehr auf Autoplay zurücksetzen.
- Filmpalast liest die aktuelle Such- und Quellenstruktur, schützt bereits korrekt kodierte Suchpfade vor Doppel-Kodierung und übernimmt erkannte Hoster erst ohne vorzeitige ResolveURL-Filterung in die Quellenliste.
- Scraper erhalten die aktuelle ResolveURL-Hosterliste, damit Quellen von FHDFilme, HDfilme, Megakino, StreamCloud, TopStreamFilm und ähnlichen Anbietern nicht mehr vorzeitig ausgefiltert werden.
- Die Standard-Aktion `Verzeichnis` liefert Quellenlisten auch aus Favoriten, RPC- und externen Aufrufen wieder als Kodi-Verzeichnis, statt ungewollt in den Dialog zurückzufallen.
- VIXSTREAM-Playlist-Streams ohne `.m3u8`-Endung werden als HLS erkannt und behalten die benötigten Vixcloud-Header beim Kodi-Start im Abspielpfad, damit Manifest, Segmente und AES-Schlüssel erreichbar bleiben.
- Movie4k nutzt die aktuelle API-Struktur über `movie4k.sx`; alte Movie4k-Domainwerte werden beim Providercheck automatisch auf die funktionierende Domain migriert.
- Neuer Einstellungsbereich `Indexseiten 3 (DE)` für CINE.TO, FILMFANS, NOX, SERIENFANS und STREAMCLOUD.FORUM; der bisherige Bereich `Indexseiten (DE)` heißt jetzt `Indexseiten 1 (DE)`.
- Bei einer frischen Erstinstallation startet xVAULT mit Streamsprache Deutsch und Standard-Aktion Autoplay; bestehende Profile und Updates behalten ihre gewählten Einstellungen.
- BS.to ist als optionaler Serien-Scraper eingebunden. Serien, Sprachvarianten und Hoster werden aus der aktuellen Seitenstruktur gelesen; CAPTCHA-geschützte Quellen werden ausgeblendet und nicht automatisiert umgangen.
- Fortsetzen von Wiedergaben und automatische Lesezeichen.
- Gesehen/Ungesehen-Status für Filme, Folgen, Staffeln und Serien.
- Nach beendeter Wiedergabe wird der Gesehen-Status aktualisiert, ohne dass die Auswahl mehrfach zwischen alter Position und nächster ungesehener Folge springt.
- DNS over HTTPS ist standardmäßig aktiv und kann in den allgemeinen Einstellungen deaktiviert werden. xVAULT nutzt Cloudflare für die DNS-Auflösung seiner HTTP-Anfragen; die aktivierten Indexseiten laufen über dieselbe RequestHandler-Logik, feste IPs bleiben nur Rückfall.
- xVAULT-Synchronisation für Favoriten und Wiedergabestände.
- Die xVAULT-Synchronisation nutzt den neuen API-Host `xvault-sql.ddnss.de` für Favoriten- und Binge-/Wiedergabestände.
- Die Synchronisation gleicht gespeicherte Login-Daten automatisch ab, damit Server-Backups auch nach einem veralteten lokalen API-Key wiederhergestellt werden können.
- `Jetzt synchronisieren` bereinigt doppelte lokale Fortsetzen-Einträge und bricht dadurch nicht mehr mit einem PluginError ab, wenn alte Bookmark-Daten mehrfach vorhanden sind.
- Über **Werkzeuge > Support** kann ein redigiertes Diagnosepaket erstellt, nach Bestätigung hochgeladen und über eine kurze Service-ID weitergegeben werden; lokale ZIP-Dateien werden nach dem Upload gelöscht.
- Automatische Updateprüfung kann in den allgemeinen Einstellungen aktiviert oder deaktiviert werden.
- LiveTV-Senderliste mit lokalem Cache, Kategorien, Suche, Favoriten, Senderlogos, einstellbarer Stream-Puffergröße, plattformneutraler HLS-Wiedergabe-Engine, wiederholter HLS-Stabilitätsprüfung, passendem Ersatzstream-Fallback, EPG-Vorschau für aktuell laufende und folgende Sendungen sowie einer Senderlisten-Prüfung, die vor dem Start warnt, am Ende per Ergebnisdialog geprüfte, funktionierende und temporär gesperrte Sender zählt und nicht erreichbare Sender temporär bis zum nächsten xVAULT-Hauptstart ausblendet.
- LiveTV lite liest Deutsche TV-, Österreichische TV- und Schweizer TV-Sender direkt aus der 2ix2-WordPress-API und startet die dort hinterlegten HLS-Streams schlank ohne EPG- oder Favoriten-Schicht; wenn 2ix2 temporär nicht erreichbar ist, nutzt xVAULT Nydus als Ersatzquelle und löst dort echte HLS-Streams beim Start dynamisch auf.
- Download-, Untertitel- und externe Download-Manager-Optionen.

## Fehler und Vorschläge melden

Fehler und Verbesserungsvorschläge bitte über [GitHub Issues](https://github.com/mojomedia1812/xVAULT/issues) melden. Dort gibt es Vorlagen für Fehlermeldungen und Feature-Wünsche.

Gute Fehlermeldungen enthalten:

- verwendete xVAULT-Version
- Kodi-Version und System
- genaue Schritte zum Nachstellen
- erwartetes und tatsächliches Verhalten
- Screenshots oder Logs, falls vorhanden

## Umami Analytics

Umami wird zur datenschutzfreundlichen Besuchsstatistik der GitHub Page genutzt. Die Website-ID kommt aus Umami und ist im Tracking-Code der HTML-Seiten unter `docs/` eingetragen.

Der Tracking-Code befindet sich in der bestehenden GitHub-Page-Hauptdatei `docs/index.html`, in der Handbuch-Unterseite `docs/handbuch/index.html` und wird für die generierten Repository-Listings über `tools/build_kodi_zip.py` ausgegeben. Umami ist damit auf allen relevanten GitHub-Pages-Seiten eingebunden.

Do Not Track wird respektiert, URL-Suchparameter werden nicht gesammelt und Linkklicks auf Downloads, Repository-Dateien, GitHub-Links und wichtige interne Links werden als Umami-Events erfasst. Event-Namen enthalten keine privaten Nutzerdaten.

Es werden keine Zugangsdaten, Secrets, geheimen API-Schlüssel oder personenbezogenen Inhalte ins Repository geschrieben. Falls eine Datenschutzerklärung für die öffentliche Nutzung gepflegt wird, sollte dort die Nutzung von Umami für Seitenstatistik und Linkklicks sachlich ergänzt werden.

## Add-on-Nutzungsstatistik

Die optionale xVAULT-Nutzungsstatistik nutzt Supabase als Backend und kann im eigenen Add-on-Einstellungsbereich **Statistik** aktiviert oder deaktiviert werden. Neue Profile starten mit aktivierter Statistik.

Erfasst werden nur technische Lebenszyklusdaten: Installation erstellt, Add-on gestartet, Add-on beendet, Heartbeat alle 10 Minuten, Kodi-Version, xVAULT-Version, OS-Klasse, Geräteklasse, Online-Status und zuletzt gesehen. Das Plugin sendet keine Titel, Suchbegriffe, Stream-URLs, Favoriten, Zugangsdaten, geheimen API-Schlüssel, privaten Pfade oder persönlichen Eingaben.

Die lokale Installation-ID ist eine zufällig erzeugte UUID. In Supabase wird sie über die Ingest-Funktion gehasht gespeichert. Direkte Tabellenzugriffe sind per RLS gesperrt; das Plugin nutzt nur den öffentlichen Supabase-RPC-Endpunkt mit Publishable Key.

## Mitwirken

Hinweise für Beiträge stehen in [`CONTRIBUTING.md`](CONTRIBUTING.md).

Bei Änderungen an Version, Einstellungen oder Funktionen muss diese README geprüft und bei Bedarf aktualisiert werden.

## Changelog

- Repository- und Dokumentationsänderungen: [`CHANGELOG.md`](CHANGELOG.md)
- Plugin-Versionshistorie: [`CHANGELOG.txt`](CHANGELOG.txt)

## Kompatibilität

xVAULT ist ein Kodi-Python-3-Add-on und deklariert in [`addon.xml`](addon.xml) `xbmc.python` ab Version `3.0.0`. LiveTV-HLS funktioniert plattformneutral auf Windows, Linux und Android: xVAULT nutzt automatisch FFmpeg Direct, wenn es auf der Plattform installiert und aktiviert ist, und fällt sonst auf Kodis interne HLS-Wiedergabe zurück. InputStream Adaptive bleibt als manuell auswählbare Alternative erhalten.

Für Android-basierte Fire-TV-Stick-Tests gibt es einen Profil-Simulator unter [`docs/firetv-stick-simulator.md`](docs/firetv-stick-simulator.md). Er ersetzt keinen echten FireOS-ROM-Emulator, hilft aber beim Prüfen von Fire OS, Android-API-Level, RAM, Codec-Klasse und Kodi-Risiken und kann Android-TV-AVD-Testprofile nach dem Amazon-AVD-Vorgehen skizzieren.

Für Kodi mit installiertem xVAULT gibt es zusätzlich `tools/kodi_firetv_test.py`. Der Standardlauf zielt auf `aftmm`, also Fire TV Stick 4K - 1st Gen, und prüft neben Kodi-Smoke-Tests auch lokale Datenbankkonsistenz bei simuliertem Speicher- und Schreibfehlerdruck.
