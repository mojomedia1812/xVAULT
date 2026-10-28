# xVAULT

xVAULT ist ein Kodi-Video-Add-on zum Durchsuchen und Wiedergeben von Filmen, TV-Serien und LiveTV.

## Aktuelle Version

Aktueller Release-Stand: `2026.10.28.1`

Aktueller Nightly-Stand: `2026.10.27.4` (`plugin.video.xvault-2026.10.27.4.zip`). Endnummer `.1` gehört zum Release-Kanal; alle anderen Endnummern gehören zum Nightly-Kanal. Der VIXSTREAM-Schlüsselheader-Fix und die Korrektur automatischer Vorwaertsupdates beim Kanalwechsel sind auch im Release 2026.10.28.1 enthalten.

VIXSTREAM übergibt die Wiedergabe-Header auch an den separaten HLS-Schlüsselabruf. Kodi bis Version 21 nutzt dafür `inputstream.adaptive.license_key`, Kodi ab Version 22 die AES-Konfiguration über `inputstream.adaptive.drm`. Details zur Vorher-/Nachher-Prüfung stehen in [`tools/diagnostics/VIXSTREAM_KEY_HEADERS_2026-10-26.md`](tools/diagnostics/VIXSTREAM_KEY_HEADERS_2026-10-26.md).

Die führende Versionsquelle ist [`addon.xml`](addon.xml). Wenn die Version in `addon.xml` geändert wird, muss diese README geprüft und bei Bedarf aktualisiert werden.

Nightly `2026.10.27.2` ergänzt den lokal geprüften Radio-Bereich mit Radio Browser. Der stabile Release-Kanal bleibt auf `2026.10.28.1`.

Nightly `2026.10.27.3` beschleunigt den Radio-Bereich mit vorbereitetem Senderindex und schnellen Senderfamilien-Menüs. Familien/Genres verwenden fertige Zähler, Übersichten Kodis Verzeichnis-Cache und ListItems den Offscreen-Modus. Große Senderlisten zeigen 250 Einträge pro Seite; bei API-Ausfällen wird höchstens alle fünf Minuten erneut versucht. Der stabile Release bleibt auf `2026.10.28.1`.

Nightly `2026.10.27.4` ergänzt das eigenständige xVAULT-Visuals. Der native Windows-Build `22.0.1` enthält sieben über Kodis Presetliste umschaltbare Modi; Details unter [`native/visualization.xvault/README.md`](native/visualization.xvault/README.md). Der stabile Release bleibt auf `2026.10.28.1`.

Release `2026.10.28.1` ordnet die Werkzeuge in **Einstellungen**, **Updates und Version** und **Hilfe und Problembehebung**. Der Hauptmenüeintrag „Stream-URL abspielen“ entfällt. Der Release enthält auch Radio, die beschleunigten Radio-Menüs und xVAULT-Visuals aus den Nightlys vom 27.10.2026.

## Radio (ab Nightly 2026.10.27.2)

**Radio** verwendet Kodis Audioplayer, MusicInfoTag, Bildcache, Dialoge, Einstellungen und zentrale Favoriten. Es wird kein zusätzlicher Player und keine eigene Favoritendatenbank verwendet. Der vorhandene xVAULT-Favoritenabgleich kann diese Kodi-Favoriten mit übernehmen. „Zuletzt gehört“ und die Audioformat-Vorgabe bleiben gerätelokal.

Die Senderquelle ist [Radio Browser](https://api.radio-browser.info/). Zugelassen sind ausschließlich `countrycode=DE` und `lastcheckok=1`. Dies ist keine Garantie für die aktuelle Erreichbarkeit; vor Wiedergabe werden API-Status und Stream erneut geprüft. Auch Suche und Favoriten umgehen diesen Filter nicht.

Genres werden aus API-Tags abgeleitet; bekannte Senderfamilien aus Namen und Homepage-Domains. Genre und Familie sind kombinierbar. Qualitätsvarianten desselben Programms werden zusammengefasst. Votes gehören zum führenden API-Eintrag und werden nicht über Varianten addiert. Sortierung: Votes, Name oder höchste Bitrate. Eine bestätigte Abstimmung wird genau einmal gesendet; ein Verbindungsfehler führt zu keiner automatischen Wiederholung. Radio Browser begrenzt Stimmen pro Sender/IP auf zehn Minuten. Wiedergaben werden als Aufruf gemeldet. Radio Browser und Streamserver sehen dabei wie bei einem normalen Radioabruf die öffentliche IP-Adresse.

Die Senderliste wird sechs Stunden zwischengespeichert. Bei API-Ausfall wird höchstens eine 48 Stunden alte Liste mit Hinweis verwendet. Die Wiedergabe verlangt weiterhin eine erfolgreiche aktuelle Senderprüfung. Eine Verified-Kennzeichnung oder zusätzliche Betreiber-Metadaten sind nicht erforderlich.

Dublettenerkennung: Identische Streamadressen und frisch bestätigte Weiterleitungsziele werden zusammengefasst. Qualitätsvarianten benötigen passende Namen und dieselbe Betreiber-Domain. Bekannte Spartensender mit unterschiedlichen Programmkennungen bleiben getrennt, auch wenn fehlerhafte API-Einträge dieselbe URL angeben. Alle Sender-UUIDs und Suchnamen bleiben erhalten; Favoriten und Hörverlauf können weiterhin über alte IDs aufgelöst werden. Doppelte Zielstreams werden bei der Variantenwahl nur einmal versucht.

Der Kodi-Hintergrunddienst prüft nach einem Radioaufruf nur plausible Namensvarianten, höchstens sechs URLs pro Durchlauf mit 15 Sekunden Pause zwischen Durchläufen. Bei Wiedergabe werden keine neuen Prüfungen gestartet. Die Liste selbst wartet nicht auf Streamprüfungen. Erfolgreiche Ziele gelten 24 Stunden, Fehler werden sechs Stunden zurückgestellt. Beim nächsten Öffnen einer Liste wird der aktuelle Abgleich berücksichtigt. Für eindeutig benannte Regiocast-Streamadressen werden ausschließlich bekannte Messparameter bei der Identitätsbildung ignoriert; die Wiedergabe-URL bleibt unverändert. Andere Query-, Programm- und Zugangswerte bleiben Bestandteil der Identität.

Lokale Regressionstests: `python -m unittest tools.tests.test_radio`. Öffentliche Teststimmen werden nicht abgegeben.

## Installation

1. Die aktuelle Add-on-ZIP von [xvault.repowork.de](https://xvault.repowork.de/) herunterladen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** öffnen.
3. Die Datei `plugin.video.xvault-2026.10.28.1.zip` auswählen.
4. xVAULT starten.

Alternativ kann das Repository-ZIP von [https://xvault.repowork.de/repository.xvault.zip](https://xvault.repowork.de/repository.xvault.zip) installiert werden. Danach findet Kodi neue xVAULT-Versionen über das Repository.

Kodi installiert die offiziellen Abhängigkeiten aus den konfigurierten Repositorys. Damit eine direkte ZIP-Installation nicht an noch fehlenden Modulen scheitert, installiert und aktiviert xVAULT seine benötigten Laufzeitmodule beim ersten Start zusätzlich selbst. Nicht im offiziellen Kodi-Repo verfügbare Module wie ResolveURL werden dabei aus ihren offiziellen Quellen nachinstalliert. Optionale binäre InputStream-Komponenten werden nicht beim Pluginstart erzwungen, weil sie je nach Kodi-Plattform nicht immer verfügbar sind.

Weitere Hinweise zu Abhängigkeiten stehen in [`DEPENDENCIES.md`](DEPENDENCIES.md).

## Originalstatus und Updatekanaele

Die offizielle Repository- und Updateadresse ist `https://xvault.repowork.de/`. Ein Netzfehler gilt nicht als Nachweis einer veraenderten Installation.

Unter **Werkzeuge > Updates und Version > Version und Originalstatus anzeigen** zeigt xVAULT die neu berechneten SHA-256-Dateihashes, den signierten Referenzstand, KodiBox-Merkmale, die Versionsplausibilitaet und den letzten Updatecheck. Die Pruefung laeuft beim Hauptstart und Service-Start sowie an Wiedergabe-, Update- und Support-Einstiegspunkten. Bekannte KodiBox-Kopien werden von einem unveraenderten Originalpaket innerhalb einer KodiBox-Umgebung unterschieden. Das Diagnosepaket enthaelt den Herkunftsstatus direkt in `environment.json`.

**Release** verwendet `YYYY.MM.DD.1`, **Nightly** Revisionen ab `YYYY.MM.DD.2`. Die Auswahl gilt pro Geraet und wird nicht mit dem Konto synchronisiert. Releases werden alle sechs Stunden, Nightlys stuendlich im Hintergrund geprueft; die manuelle Pruefung ist jederzeit verfuegbar. Standard ist Benachrichtigung. Optional werden echte Vorwaertsupdates im Leerlauf installiert. Reparaturen und Rueckwechsel auf eine niedrigere Version verlangen eine ausdrueckliche Bestaetigung. Die eigenen Pruefungen verwenden nicht Kodis globale Update-Einstellung; Kodis xVAULT-Repository wird auf den gewaehlten Kanal ausgerichtet.

ZIP-SHA-256, signiertes Dateimanifest und tatsaechlich installierte Dateien werden getrennt geprueft. Die Installation wird vorbereitet, erneut validiert und durch einen separaten Helfer mit Sicherung und Ruecksetzung ausgefuehrt. Persoenliche Daten unter `addon_data` bleiben ausserhalb des Pakettauschs.

Zum Bauen wird Python mit `cryptography` sowie der private Release-Schluessel aus `XVAULT_SIGNING_KEY` benoetigt. Lokal wird ersatzweise die ignorierte Datei `tools/diagnostics/private/release-signing-key.pem` verwendet. Dieser Schluessel darf niemals ins Repository oder Add-on gelangen und muss separat gesichert werden. Der oeffentliche Pruefschluessel ist in `resources/lib/release_security.py` hinterlegt. `python -B tools/build_kodi_zip.py` erzeugt reproduzierbare ZIPs, signierte Kanaldateien, versionsbezogene Dateimanifeste und getrennte Kodi-Kanalindizes. Fuer eine Nightly wird die Quellversion vor dem Build auf eine Tagesrevision ab 2 gesetzt; Nightlys ersetzen weder den Release-Kanal noch dessen Downloadseite. Bereits gebaute Versionen werden nicht mit anderen Bytes wiederveroeffentlicht. Nur fuer noch unveroeffentlichte lokale Entwuerfe erlaubt `XVAULT_ALLOW_DRAFT_REBUILD=1` einen erneuten Build derselben Versionsnummer.

## Nutzung

- Das ausführliche Handbuch steht als GitHub-Pages-Unterseite unter [xvault.repowork.de/handbuch/](https://xvault.repowork.de/handbuch/) bereit.
- Filme und Serien über die xVAULT-Menüs suchen.
- LiveTV und LiveTV lite über Senderkategorien oder eigene TV-Favoriten starten.
- Eine Quelle auswählen oder Autoplay verwenden.
- Favoriten und Wiedergabestände optional über den Kontenbereich synchronisieren.
- Gesehene Folgen, Staffeln und Serien werden aus den aktuellen Wiedergabeständen abgeleitet.

## Funktionen

- Suche und Wiedergabe von Filmen, TV-Serien und LiveTV.
- Film- und Serienlisten können über TMDb-Watch-Provider nach Streaming-Anbietern im deutschen Markt gefiltert werden; danach nutzt xVAULT weiterhin die normale Quellen- und Resolverlogik.
- xVAULT kann als Player für TMDbHelper genutzt werden, ohne die eigene Quellenlogik, Resolver-Auswahl und Wiedergabeüberwachung zu verlieren.
- Der Hauptmenüpunkt `Collections` zeigt Filmreihen aus Filmo, speichert die Übersichten 24 Stunden im Cache, sortiert enthaltene Filme chronologisch und filtert die Detailansicht über TMDb-Filmreihen gegen offensichtliche Fremdtreffer.
- Das Playback-Label zeigt beim laufenden Stream Hoster und Indexseite an, z.B. `VOE @ SerienStream`.
- Serien zeigen vorhandene Specials aus TMDB-Staffel 0 als eigenen Staffel-Eintrag an; Sonderfolgen bleiben beim Abspielen echte Serienfolgen.
- SerienStream verwendet `serienstream.to`; alte gespeicherte Domainwerte werden automatisch auf diese Domain migriert.
- SerienStream.to arbeitet ohne Zugangsdatenpflicht; die Quellensuche läuft auch ohne hinterlegte Login-Daten.
- SerienStream und AniWorld gleichen Serien- und Episodentreffer über Titel, Slugs, Jahr, Kapitelnummern und deutsche/englische Episodentitel robuster ab; Untertitelvarianten werden nicht mehr als Tonspur-Sprache gewertet.
- SerienStream gleicht abweichende Anbieter-Staffelzählungen über eindeutige Episodentitel und Kapitelnummern ab. Upload-Daten der Webseite werden nicht als Erstausstrahlung gewertet; Folgen ohne deutsche Fassung behalten ihre englischen Quellen. Generische Einträge mit dem Hosternamen `Provider` werden ausgelassen.
- Serienwiedergaben starten auch dann stabil, wenn Metadaten aus Favoriten, alten Listen oder Android/Kodi-Varianten nur `imdb_id` statt `imdbnumber` liefern; Startfehler werden im Kodi-Log klarer protokolliert.
- VOE-Quellen können direkt in xVAULT aufgelöst werden, wenn die installierte ResolveURL-Version die aktuelle VOE-Ausweichdomain noch nicht kennt.
- xVAULT kennt zusätzliche VOE-, Streamix-, Playmate- und FireStream-Ausweichdomains, damit Quellen auch dann nutzbar bleiben, wenn die installierte ResolveURL-Version diese Domains noch nicht selbst enthält.
- KinoGer-Spezialhosts werden gezielt dem passenden Resolver zugeordnet; bei `kinoger.be` bevorzugt xVAULT echte HLS-Varianten statt problematischer Werbe-Playlists.
- Der KinoGer-Scraper gibt erkannte Spezialhosts als Resolver-Quellen weiter, damit Dialog, Verzeichnis und Autoplay denselben geprüften Auflösungsweg verwenden.
- Nicht aufgelöste Hoster-Seiten werden nicht mehr als Video an Kodi übergeben; xVAULT versucht stattdessen weitere Quellen oder meldet, dass keine nutzbare Quelle verfügbar ist.
- Bereits vom Anbieter aufgelöste Direktstreams werden anhand ihrer Mediendaten erkannt, auch ohne Video-Dateiendung, und nicht erneut als Hoster-Seite aufgelöst. Die Stream-Prüfung verwendet einen kleinen GET-Abruf statt einer vorausgesetzten HEAD-Unterstützung; HTML-/Werbeweiterleitungen werden auch hinter `.m3u8`-Adressen verworfen und die vorhandene Ersatzquellen-Suche kann fortfahren.
- Beim Wechsel von der Quellensuche in die Quellenliste schließt xVAULT Kodis Busy-Overlay gezielt, damit die fertige Liste nicht hinter einer weiterdrehenden Ladeanzeige liegen bleibt.
- Autoplay und manuelle Streamauswahl begrenzen hängende Resolver- und Player-Starts per Timeout; bei Autoplay probiert xVAULT danach weitere gefundene Quellen und beendet die Wiedergabeüberwachung auch ohne Kodi-Stop-Callback sauber.
- Gefundene Quellenlisten für Filme und Serien werden im Kodi-Profil zwischengespeichert. Beim erneuten Quellenwechsel für denselben Titel kann xVAULT die Liste wiederverwenden, während Hoster-Links weiterhin frisch aufgelöst und getestet werden.
- Serien merken sich erfolgreiche Anbieter für spätere Folgen derselben Serie, damit passende Indexseiten schneller nach vorne rücken, ohne andere aktive Anbieter dauerhaft auszuschließen.
- Fehlerhafte oder hängende Indexseiten werden nur kurzzeitig übersprungen, damit ein einzelner Timeout die Suche nicht bei jedem Start erneut ausbremst.
- Fehlerhafte oder hängende Hoster-Auflösungen werden ebenfalls kurzzeitig pro Provider-/Hoster-Kombination übersprungen, damit ein erneuter Quellenwechsel nicht sofort wieder an derselben problematischen Quelle startet.
- Die parallele Quellensuche passt die Thread-Anzahl an die Plattform an und bereitet bei Autoplay mehrere aussichtsreiche Quellen parallel vor, behält aber die bisherige Sortier- und Auswahlreihenfolge bei.
- Streamquellen für Filme und Serien können nach bevorzugter Sprache sortiert oder gefiltert werden; mehrere Scraper liefern Deutsch/Englisch-Varianten sauber an die Quellenliste, und Autoplay wird bei Sprache `Alle` automatisch in Dialog oder Verzeichnis umgestellt.
- Trakt-Watchlists fallen bei temporaeren Trakt-Serverfehlern des Sync-Endpunkts automatisch auf den Benutzer-Watchlist-Endpunkt zurueck; Trakt-Collections werden paginiert geladen.
- Die Standard-Aktion `Dialog`, `Verzeichnis` oder `Autoplay` wird beim Start von Filmen und Folgen frisch aus Kodis aktuellem Add-on-Setting gelesen; die Profil-Datei dient als Rückfall. Alte Favoriten oder externe Aufrufe frieren die Auswahl nicht mehr auf einen früheren Wert ein.
- Die Standard-Aktion wird über einen xVAULT-eigenen Auswahl-Dialog gespeichert und migriert alte `hosts.mode.v2`-/`hosts.mode`-/`default.action`-Werte automatisch, damit Kodi-Defaultwerte die Auswahl nicht mehr auf Autoplay zurücksetzen.
- xVAULT schreibt Kodi-Settings nur, wenn sich der Zielwert wirklich geändert hat; identische Werte werden übersprungen, um die Profil-Settings zu schonen.
- Filmpalast liest die aktuelle Such- und Quellenstruktur, schützt bereits korrekt kodierte Suchpfade vor Doppel-Kodierung, durchsucht mehrere Trefferseiten und übernimmt erkannte Hoster erst ohne vorzeitige ResolveURL-Filterung in die Quellenliste.
- Filmo ist als aktivierbare Filmquelle in die normale Quellensuche eingebunden; xVAULT liest Filmo-Suche und Filmseiten, löst Providerchips mit CSRF-Token, Session-Cookies und Redirect-Auswertung über den Filmo-Mint-Endpunkt auf und übernimmt Deutsch-/Englisch-Hoster in die Quellenliste.
- MoFlix ist als optionale Film- und Serienquelle eingebunden; xVAULT prueft Treffer ueber Titel, Jahr und IMDb-ID, faellt bei blockierter JSON-API auf Browser-HTML-Daten zurueck und repariert veraltete Healthcheck-Sperren automatisch.
- Bei MoFlix werden Treffer mit einer widersprüchlichen IMDb-ID verworfen. Ohne passende IMDb-ID darf auch ein deutlich anderes Erscheinungsjahr keinen gleichnamigen Film ersetzen; veraltete Quellenlisten werden nach einer Anbieterrevision neu ermittelt.
- AnimeToast ist als eigener Serien-Scraper eingebunden. xVAULT nutzt dort nur konkrete Episoden aus der Ajax-Playerlogik oder eindeutige Einzel-Episodenlinks; reine Staffelbereichs-Container werden nicht als einzelne Folge übernommen.
- Internet Archive ist als optionale Filmquelle vorhanden. Die Suche ist bewusst streng auf passende Titel-/Jahr-Treffer und echte Videodateien begrenzt, damit Archiv-, Bonus- oder Trailer-Treffer die normale Quellenliste nicht verfälschen.
- Quellenlisten behalten die vom Scraper gelieferte Reihenfolge, werden nach Qualitäts-/Sprachlogik stabil dedupliziert und berücksichtigen manuelle Hoster-Ausschlüsse erst danach.
- Kodi-Wrapper für Add-on, Fenster, Dialoge, Player, Playlists und Fortschrittsdialoge werden kontrolliert erzeugt und beim Add-on-Ende freigegeben, damit Kodi nach xVAULT-Aufrufen keine unnötigen CPythonInvoker-Cleanup-Warnungen protokolliert.
- Scraper erhalten die ResolveURL-Hosterliste aus den installierten ResolveURL-Plugin-Dateien, damit Quellen von FHDFilme, HDfilme, Megakino, StreamCloud, TopStreamFilm und ähnlichen Anbietern nicht mehr vorzeitig ausgefiltert werden; die eigentliche ResolveURL-Auflösung wird erst beim Start einer Quelle geladen und danach wieder aus dem xVAULT-Invoker gelöst.
- Settings-Lesezugriffe nutzen Profil- und Default-XML mit Cache, damit aktuelle Kodi-Einstellungen sofort greifen und keine unnötigen Add-on-Wrapper entstehen.
- Die Standard-Aktion `Verzeichnis` liefert Quellenlisten auch aus Favoriten, RPC- und externen Aufrufen wieder als Kodi-Verzeichnis, statt ungewollt in den Dialog zurückzufallen.
- VIXSTREAM-Playlist-Streams ohne `.m3u8`-Endung werden als HLS erkannt und behalten die benötigten Vixcloud-Header beim Kodi-Start im Abspielpfad, damit Manifest, Segmente und AES-Schlüssel erreichbar bleiben.
- VIXSTREAM prüft auch nachgelagerte HLS-Listen und zeigt eine Quelle nur bei einem Sprachnachweis als Deutsch oder Englisch an. Fehlende Sprachkennungen bleiben „Sprache unbekannt“; der angeforderte `lang`-Parameter und Untertitel zählen nicht als Nachweis. Der Sprachfilter entscheidet wie bei anderen Anbietern über unbekannte Quellen. Die Qualitätsangabe stammt aus dem Manifest statt aus einer pauschalen 1080p-Vorgabe.
- Optionale InputStream-Komponenten werden beim Pluginstart, bei Film-/Serien-HLS und bei der Kodi-TV-/IPTV-Simple-Integration nicht mehr erzwungen; xVAULT nutzt vorhandene Engines oder fällt auf Kodis interne Wiedergabe zurück.
- Movie4k nutzt die aktuelle API-Struktur über `movie4k.sx`; alte Movie4k-Domainwerte werden beim Providercheck automatisch auf die funktionierende Domain migriert.
- Neuer Einstellungsbereich `Indexseiten 3 (DE)` für CINE.TO, FILMFANS, NOX, SERIENFANS und STREAMCLOUD.FORUM; der bisherige Bereich `Indexseiten (DE)` heißt jetzt `Indexseiten 1 (DE)`.
- Bei einer frischen Erstinstallation startet xVAULT mit Streamsprache Deutsch und Standard-Aktion Autoplay; bestehende Profile und Updates behalten ihre gewählten Einstellungen.
- AniWorld.to ist als optionaler Serienanbieter eingebunden und kann in den Indexseiten aktiviert oder deaktiviert werden; Zugangsdaten sind optional im Kontenbereich hinterlegbar.
- Fortsetzen von Wiedergaben und automatische Lesezeichen.
- Angefangene Filme und Folgen bleiben ungesehen, zeigen ein Uhrsymbol und nennen die Fortsetzen-Position direkt hinter dem Titel.
- Gesehen-Haken für Filme und Folgen erscheinen erst, wenn höchstens noch zehn Minuten Restlaufzeit übrig sind oder die Wiedergabe regulär endet.
- Gesehen/Ungesehen-Status für Filme, Folgen, Staffeln und Serien.
- Nach beendeter Wiedergabe wird der Gesehen-Status aktualisiert, ohne dass die Auswahl mehrfach zwischen alter Position und nächster ungesehener Folge springt.
- Nach dem Stoppen oder Ende eines Streams nutzt xVAULT keine blinde Kodi-ParentDir-Navigation mehr, sondern kehrt über den gespeicherten xVAULT-Containerpfad zurück, damit Kodi auf verschiedenen Plattformen geöffnet bleibt.
- DNS over HTTPS ist standardmäßig aktiv und kann in den allgemeinen Einstellungen deaktiviert werden. xVAULT nutzt Cloudflare für die DNS-Auflösung seiner HTTP-Anfragen; die aktivierten Indexseiten laufen über dieselbe RequestHandler-Logik, feste IPs bleiben nur Rückfall. Der Providercheck im Hintergrunddienst beachtet dieselbe Einstellung und sperrt Anbieter bei vorübergehenden Netzwerkfehlern nicht dauerhaft.
- xVAULT-Synchronisation für Favoriten und Wiedergabestände.
- Der Geräteabgleich unterstützt mindestens fünf gleichzeitig angemeldete Geräte mit eigenen Zugangsschlüsseln. Alle beteiligten Geräte müssen auf Version 2026.10.22.1 oder neuer aktualisiert werden. Eine bereits ungültige Anmeldung erfordert einmalig eine neue Anmeldung.
- Unter **Konten & Sync > Geräte & Sync-Verlauf** sind Gerätenamen, letzte Nutzung, Änderungen mit ihrem Ursprungsgerät und offene Konflikte einsehbar. Ein einzelnes Gerät lässt sich abmelden, ohne andere Geräte abzumelden.
- Beim Start von xVAULT, nach dem Aufwachen, vor der Wiedergabe und im Hintergrund etwa alle 30 Sekunden wird der Kontostand abgeglichen. Änderungen während einer Netzunterbrechung bleiben in einer lokalen SQLite-Warteschlange erhalten.
- Hauptmenü und Aufwachen beauftragen den Hintergrunddienst, ohne auf den Sync zu warten. Unveränderte Wiedergabe-/Gesehen-Stände werden nicht erneut lokal angewendet; Änderungen werden mit einer gemeinsamen Playcount-Transaktion und einem gemeinsamen Bookmark-Schreibvorgang übernommen. Statusabfragen benötigen keine Sync-Schreibsperre.
- Serverrevisionen schützen vor veralteten Updates und falschen Geräteuhren. Unabhängige Favoritenfelder werden zusammengeführt; widersprüchliche Änderungen bleiben zur Auswahl erhalten. Bei konkurrierenden Wiedergaben bietet xVAULT vor dem Fortsetzen die gespeicherten Positionen an.
- Die xVAULT-Synchronisation nutzt den API-Host `all-stats.de` für Favoriten- und Binge-/Wiedergabestände.
- Bei der Sync-Registrierung prüft xVAULT die E-Mail-Adresse auf plausibles Format und die API zusätzlich, ob die angegebene Domain per DNS erreichbar ist.
- Favoriten werden revisionsbasiert als einzelne Einträge mit Löschmarken synchronisiert; Geräte übertragen nur neue, geänderte oder gelöschte Favoriten, statt bei jedem Abgleich den kompletten Favoritenbestand zu senden.
- Die Anmeldung bleibt über einen lokal gespeicherten Zugangsschlüssel erhalten. Das Kontopasswort wird dafür nicht lokal gespeichert. Ein Kennwort-Reset widerruft alle Geräteanmeldungen.
- `Jetzt synchronisieren` bereinigt doppelte lokale Fortsetzen-Einträge und bricht dadurch nicht mehr mit einem PluginError ab, wenn alte Bookmark-Daten mehrfach vorhanden sind.
- Sync-Zustandsdateien werden bei kurz gesperrten Profil-Dateien mit Retry und Fallback geschrieben, damit Wiedergabeende und Synchronisation keine unnötigen Datei-Zugriffsfehler erzeugen.
- Über **Werkzeuge > Hilfe und Problembehebung > Diagnosepaket erstellen und hochladen** kann ein redigiertes Diagnosepaket erstellt, nach Bestätigung hochgeladen und über eine kurze Service-ID weitergegeben werden; lokale ZIP-Dateien werden nach dem Upload gelöscht.
- Beschädigte gespeicherte xVAULT-Einstellungen werden beim Pluginstart erkannt; der Nutzer kann die defekte `settings.xml` sichern und zurücksetzen lassen. Dieselbe Prüfung ist unter **Werkzeuge > Hilfe und Problembehebung > Einstellungen auf Fehler prüfen** sowie in den Einstellungen unter **Wartung & Support** manuell erreichbar.
- Automatische Updateprüfung kann in den allgemeinen Einstellungen aktiviert oder deaktiviert werden.
- LiveTV-Senderliste mit lokalem Cache, Kategorien, Suche, eigenen TV-Favoriten, Senderlogos, einstellbarer Stream-Puffergröße, plattformneutraler HLS-Wiedergabe-Engine, wahlweiser reiner M3U/XMLTV-Erstellung, nutzergesteuerter Kodi-TV/IPTV-Simple-Integration, wiederholter HLS-Stabilitätsprüfung, passendem Ersatzstream-Fallback, EPG-Vorschau für aktuell laufende und folgende Sendungen sowie einer Senderlisten-Prüfung, die vor dem Start warnt, am Ende per Ergebnisdialog geprüfte, funktionierende und temporär gesperrte Sender zählt und nicht erreichbare Sender temporär bis zum nächsten xVAULT-Hauptstart ausblendet.
- LiveTV lite liest Deutsche TV-, Österreichische TV- und Schweizer TV-Sender direkt aus der 2ix2-WordPress-API, besitzt einen eigenen TV-Favoritenordner und startet die dort hinterlegten HLS-Streams schlank ohne EPG-Schicht; wenn 2ix2 temporär nicht erreichbar ist, nutzt xVAULT Nydus als Ersatzquelle und löst dort echte HLS-Streams beim Start dynamisch auf.
- Interne Downloads und externe Download-Manager sind getrennt: lokale Downloads benötigen Zielordner, My.JDownloader/JDownloader/PyLoad erscheinen unabhängig davon im Kontextmenü einzelner Quellen, wenn die Quellenansicht als Verzeichnis geöffnet wird.
- LiveTV verwendet die neue OHA-Schnittstelle unter `/live/`: Senderliste mit Deutschlandfilter und Cursor-Paginierung, Typ `live` und Stream-Auflösung per GET. Alte Kataloge werden gesichert und neu geladen; eindeutig gleichnamige Sender behalten alte Kennungen als Alias. Das frühere Signatur-Ping ist nicht mehr erforderlich.

## Fehler und Vorschläge melden

Fehler und Verbesserungsvorschläge bitte über [GitHub Issues](https://github.com/mojomedia1812/xVAULT/issues) melden. Dort gibt es Vorlagen für Fehlermeldungen und Feature-Wünsche.

Gute Fehlermeldungen enthalten:

- verwendete xVAULT-Version
- Kodi-Version und System
- genaue Schritte zum Nachstellen
- erwartetes und tatsächliches Verhalten
- Screenshots oder Logs, falls vorhanden

## Sicherheit

Sicherheitslücken bitte nicht öffentlich in Issues, Diskussionen oder Foren melden. Die Meldewege, unterstützten Versionen und der Umfang sicherheitsrelevanter Meldungen stehen in [`SECURITY.md`](SECURITY.md).

## Verhaltenskodex

Für Issues, Pull Requests, Diskussionen und Projektkommunikation gilt der [`Code of Conduct`](CODE_OF_CONDUCT.md).

## Lizenz

xVAULT wird unter der GNU General Public License Version 3 only (`GPL-3.0-only`) veröffentlicht. Der vollständige Lizenztext steht in [`LICENSE`](LICENSE).

Im Repository enthaltene Drittkomponenten behalten ihre jeweiligen Lizenz- und Copyright-Hinweise. Eine kurze Übersicht steht in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Umami Analytics

Umami wird zur datenschutzfreundlichen Besuchsstatistik der GitHub Page genutzt. Die Website-ID kommt aus Umami und ist im Tracking-Code der HTML-Seiten unter `docs/` eingetragen.

Der Tracking-Code befindet sich in der bestehenden GitHub-Page-Hauptdatei `docs/index.html`, in der Handbuch-Unterseite `docs/handbuch/index.html` und wird für die generierten Repository-Listings über `tools/build_kodi_zip.py` ausgegeben. Umami ist damit auf allen relevanten GitHub-Pages-Seiten eingebunden.

Do Not Track wird respektiert, URL-Suchparameter werden nicht gesammelt und Linkklicks auf Downloads, Repository-Dateien, GitHub-Links und wichtige interne Links werden als Umami-Events erfasst. Event-Namen enthalten keine privaten Nutzerdaten.

Es werden keine Zugangsdaten, Secrets, geheimen API-Schlüssel oder personenbezogenen Inhalte ins Repository geschrieben. Falls eine Datenschutzerklärung für die öffentliche Nutzung gepflegt wird, sollte dort die Nutzung von Umami für Seitenstatistik und Linkklicks sachlich ergänzt werden.

## Add-on-Nutzungsstatistik

Die optionale xVAULT-Nutzungsstatistik nutzt die xVAULT-API als Backend und kann im eigenen Add-on-Einstellungsbereich **Statistik** aktiviert oder deaktiviert werden. Neue Profile starten mit aktivierter Statistik.

Erfasst werden nur technische Lebenszyklusdaten: Installation erstellt, Add-on gestartet, Add-on beendet, Heartbeat alle 30 Minuten, Kodi-Version, xVAULT-Version, OS-Klasse, Geräteklasse, Online-Status und zuletzt gesehen. Das Plugin sendet keine Titel, Suchbegriffe, Stream-URLs, Favoriten, Zugangsdaten, geheimen API-Schlüssel, privaten Pfade oder persönlichen Eingaben.

Die lokale Installation-ID ist eine zufällig erzeugte UUID. Auf dem API-Server wird sie vor der Speicherung gehasht. Heartbeats aktualisieren nur den aktuellen Geräte-/Sitzungszustand; technische Ereignisse werden serverseitig verdichtet, damit die Datenmenge klein bleibt.

## Mitwirken

Hinweise für Beiträge stehen in [`CONTRIBUTING.md`](CONTRIBUTING.md).

Bei Änderungen an Version, Einstellungen oder Funktionen muss diese README geprüft und bei Bedarf aktualisiert werden.

## Changelog

- Repository- und Dokumentationsänderungen: [`CHANGELOG.md`](CHANGELOG.md)
- Plugin-Versionshistorie: [`CHANGELOG.txt`](CHANGELOG.txt)

## Kompatibilität

xVAULT ist ein Kodi-Python-3-Add-on und deklariert in [`addon.xml`](addon.xml) `xbmc.python` ab Version `3.0.0`. Die Python-Laufzeitmodule und ResolveURL werden beim Start geprüft und bei Bedarf über Kodi beziehungsweise die hinterlegten offiziellen Quellen installiert und aktiviert. Optionale binäre InputStream-Komponenten werden beim Start nicht erzwungen, weil sie plattformabhängig sind und auf einzelnen Kodi-Ports fehlen können. Der IPTV Simple Client wird nicht mehr beim xVAULT-Start oder nach Updates automatisch installiert oder aktiviert; xVAULT fragt nur bei der ausdrücklich ausgewählten Kodi-TV-Integration nach. LiveTV-HLS funktioniert plattformneutral: xVAULT nutzt automatisch FFmpeg Direct, wenn es auf der Plattform installiert und aktiviert ist, und fällt sonst auf Kodis interne HLS-Wiedergabe zurück. InputStream Adaptive bleibt als manuell auswählbare Alternative erhalten.

Für Android-basierte Fire-TV-Stick-Tests gibt es einen Profil-Simulator unter [`docs/firetv-stick-simulator.md`](docs/firetv-stick-simulator.md). Er ersetzt keinen echten FireOS-ROM-Emulator, hilft aber beim Prüfen von Fire OS, Android-API-Level, RAM, Codec-Klasse und Kodi-Risiken und kann Android-TV-AVD-Testprofile nach dem Amazon-AVD-Vorgehen skizzieren.

Für Kodi mit installiertem xVAULT gibt es zusätzlich `tools/kodi_firetv_test.py`. Der Standardlauf zielt auf `aftmm`, also Fire TV Stick 4K - 1st Gen, und prüft neben Kodi-Smoke-Tests auch lokale Datenbankkonsistenz bei simuliertem Speicher- und Schreibfehlerdruck.
