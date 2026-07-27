# Changelog

## [Unreleased]

## [2026.07.27.2] - 2026-07-27

- VIXSTREAM prüft HLS-Audiospuren vor der Quellenanzeige und blendet falsch als Deutsch erkannte Vixcloud-Treffer aus, wenn Deutsch nur als Untertitel vorhanden ist.
- Alte zwischengespeicherte Quellenlisten werden für diese Sprachprüfung automatisch ignoriert.

## [2026.07.27.1] - 2026-07-27

- Handbuch als GitHub-Pages-Wissensdatenbank erweitert: Menüs, Suche, Quellen, Wiedergabe, Sync, Trakt, LiveTV, Downloads, Werkzeuge, Einstellungen und Fehlerhilfe ausführlicher beschrieben.
- Sichtbare GitHub-Pages-Texte und deutsch benannte Link-Events mit korrekten Umlauten vereinheitlicht.
- Abhängigkeitsprüfung für direkte ZIP-Installationen stabilisiert: xVAULT installiert und aktiviert benötigte Laufzeitmodule nach dem ersten Start selbst.
- Kodi-TV-Integration für LiveTV ergänzt: xVAULT erzeugt M3U- und XMLTV-Dateien und konfiguriert IPTV Simple automatisch, wenn das PVR-Modul verfügbar ist.
- Handbuch um eine ausführliche Erststart-Anleitung für IPTV Simple erweitert.

## [2026.07.26.1] - 2026-07-26

- Weitere Quelltextoptimierung.

## [2026.07.25.3] - 2026-07-25

- LiveTV und LiveTV lite trennen TV-Favoriten klar von Kodis eigenen Favoriten; LiveTV lite besitzt jetzt einen eigenen Favoritenordner.

## [2026.07.25.2] - 2026-07-25

- Filme und Episoden gelten erst als gesehen, wenn höchstens noch zehn Minuten Restlaufzeit übrig sind oder die Wiedergabe regulär endet.
- Angefangene Filme und Episoden bleiben ungesehen, zeigen in Listen ein Uhrsymbol und die Fortsetzen-Position hinter dem Titel.
- Fortsetzen-Lesezeichen werden bei fertig gesehenen Titeln entfernt und bei laufenden Titeln beibehalten.

## [2026.07.25.1] - 2026-07-25

- Quellensuche für Filme und Serien beschleunigt: Quellenlisten werden persistent im Kodi-Profil zwischengespeichert, erfolgreiche Serienanbieter werden bevorzugt und temporär fehlerhafte Indexseiten kurzzeitig übersprungen.
- Autoplay bereitet mehrere Quellen parallel vor, behält aber die bestehende Qualitäts-, Sprach- und Providerreihenfolge bei.
- Die parallele Scraper-Ausführung passt sich besser an Windows, Linux und Android an.

## [2026.07.23.3] - 2026-07-23

- Quelltextoptimierung.

## [2026.07.23.2] - 2026-07-23

- Quelltextoptimierung.

## [2026.07.23.1] - 2026-07-23

- Quelltextoptimierung.

## [2026.07.19.1] - 2026-07-19

- Vixstream-Quellen über Vixcloud behalten die benötigten Manifest-Header jetzt auch im Kodi-Abspielpfad, damit Kodi die HLS-Playlist nicht mehr mit HTTP 403 ablehnt.

## [2026.07.18.3] - 2026-07-18

- weitere Quelltextverbesserung.

## [2026.07.18.2] - 2026-07-18

- weitere Quelltextverbesserung.

## [2026.07.17.9] - 2026-07-17

- Die Standard-Aktion nutzt in den Kodi-Einstellungen kein Kodi-Enum/Labelenum-Dropdown mehr, sondern einen xVAULT-eigenen Auswahl-Dialog und speichert den Wert in einer eigenen Profildatei.
- Vorhandene Werte aus `hosts.mode.v3`, `hosts.mode.v2`, `hosts.mode` und `default.action` werden weiterhin einmalig übernommen, danach können alte Kodi-Defaultwerte den Wechsel nicht mehr zurückschreiben.
- Die Kodi-Settings-Action ruft den xVAULT-Auswahldialog mit gequoteter Plugin-URL auf, damit der Wechsel auch aus Kodis Einstellungsdialog zuverlässig ausgeführt wird.
- Der Fire-TV/Kodi-Test prüft jetzt die xVAULT-Profildatei, den v2/v3-Updatepfad und den Wechsel zurück auf `Autoplay` nach gesetztem Migrationsmarker.

## [2026.07.17.8] - 2026-07-17

- Die Standard-Aktion nutzt in laufendem Kodi wieder den Live-Wert aus der Add-on-API, damit ein Wechsel zwischen `Dialog`, `Verzeichnis` und `Autoplay` sofort uebernommen wird.
- Die Einstellung nutzt eine neue Kodi-Label-Enum-ID mit `Dialog`/`Verzeichnis`/`Autoplay`; alte numerische `hosts.mode`/`default.action`-Werte bleiben als Legacy-Quelle erhalten und werden beim Start migriert.
- Der Fire-TV/Kodi-Test prueft den Standard-Aktionswechsel jetzt explizit gegen stale/default-markierte Profil-Dateien und alte `default.action`-Werte.

## [2026.07.17.7] - 2026-07-17

- Die Standard-Aktion `Dialog`/`Verzeichnis`/`Autoplay` liest wieder den tatsaechlich gespeicherten Profilwert und faellt nicht mehr durch den Kodi-Default auf `Autoplay` zurueck.
- Vorhandene alte Standard-Aktionswerte werden nach `hosts.mode` migriert; die Erstinstallation ueberschreibt vorhandene Profilwerte nicht mehr mit `Autoplay`.
- Provider-Checks auf Fire TV/Android speichern bei aktivem DNS over HTTPS fehlgeschlagene direkte Service-Checks nicht mehr als harte Deaktivierung, damit DoH-faehige Indexseiten aktiv bleiben.

## [2026.07.17.6] - 2026-07-17

- Add-on-Laufzeitcode auf den finalen Stand `2026.07.17.2` zurueckgesetzt und als neue Version veroeffentlicht.
- Diese Version ersetzt die spaeteren Aenderungen aus `2026.07.17.3` bis `2026.07.17.5`, um den stabileren Stand fuer Fire-TV-Tests wieder bereitzustellen.

## [2026.07.17.5] - 2026-07-17

- Staffellisten grosser Serien wie Murdoch Mysteries werden auf Fire TV/Android schlanker aufgebaut, damit Kodi beim Scrollen nicht durch schwere TV-Show-InfoTags, Cast-Bilder oder leere Streamdetails belastet wird.
- Staffel-Metadaten werden nur noch begrenzt parallel geladen und nach der Gesehen-Status-Pruefung ohne Episodenlisten im Staffelcache gehalten; die Staffelliste nutzt einen allgemeinen Videocontent statt `tvshows`.

## [2026.07.17.3] - 2026-07-17

- Kodi-Wrapper-Objekte wie Dialoge, Fenster, Player, Playlists und Addon-Handles werden nicht mehr als langlebige Modul-Globals gehalten, damit CPythonInvoker-Cleanup-Warnungen nach xVAULT-Aufrufen vermieden werden.
- Progress-Dialoge werden verwaltet freigegeben und beim Add-on-Ende bereinigt; Serienqueue nutzt lokale Player-/Playlist-Objekte fuer die Kodi-Uebergabe.
- Der Kodi-Service ist von `control.py`/`xbmcaddon` entkoppelt und liest Provider-Konstanten direkt aus den Dateien, damit Service-Starts ohne CPythonInvoker-Addon-Klassenreste enden.

## [2026.07.17.2] - 2026-07-17

- Supportfunktion fuer redigierte Diagnosepakete hinzugefuegt: Kodi-/Addon-Kontext, relevante Abhaengigkeiten, redigierte Einstellungen, xVAULT-bezogene Logzeilen sowie Dateilisten werden automatisch gesammelt und als UUID-ZIP gepackt.
- Supportpakete werden erst nach Nutzerbestaetigung zu `filebin.net` hochgeladen, erhalten eine kurze Service-ID ueber `da.gd` und das lokale ZIP wird nach dem Upload geloescht.
- Sync-API um Telemetry-Tabellen und einen unauthentifizierten, datensparsam gefilterten Telemetry-Endpunkt erweitert; Installations- und Sitzungs-IDs werden serverseitig gehasht.

## [2026.07.17.1] - 2026-07-17

- Scraper erhalten die aktuelle ResolveURL-Hosterliste, damit Quellen von FHDFilme, HDfilme, Megakino, StreamCloud, TopStreamFilm und aehnlichen Anbietern nicht mehr vorzeitig ausgefiltert werden.
- Die Standard-Aktion `Verzeichnis` liefert Quellenlisten auch bei RPC-, Favoriten- und externen Aufrufen wieder als Kodi-Verzeichnis statt in den Dialog zurueckzufallen.
- VIXSTREAM-Playlist-Streams ohne `.m3u8`-Endung werden als HLS erkannt und mit gemeinsamen InputStream-Adaptive-Headern abgespielt, damit Manifest, Segmente und AES-Schluessel erreichbar bleiben.

## [2026.07.14.3] - 2026-07-14

- xVAULT-Synchronisation nutzt den neuen API-Host `xvault-sql.ddnss.de` und den neuen Datenbankspace fuer Favoriten und Binge-/Wiedergabestaende.
- Sync-API auf dem neuen Space bereitgestellt; Status, Registrierung, Favoriten-/Binge-Sync und Pull wurden gegen die neue Datenbank getestet.
- Sync-Client verwendet fuer den neuen Host zuerst den erreichbaren HTTP-Endpunkt, damit fehlendes HTTPS nicht vor jedem Sync zu Wartezeiten fuehrt.

## [2026.07.14.2] - 2026-07-14

- Lokale Pickle-Speicher schreiben Daten jetzt per atomischem Dateiersatz mit kurzem Retry bei Windows-Dateisperren, damit abgebrochene Schreibvorgaenge bei vollem Speicher oder OneDrive-Locks die bestehende Datei nicht beschaedigen.
- Autoplay und Streamauswahl brechen haengende Resolver- oder Player-Starts jetzt mit Timeout ab, versuchen bei Autoplay weitere Quellen und beenden den Wiedergabe-Waechter auch dann, wenn Kodi keinen Stop-Callback liefert.
- Zuletzt gefundene Quellenlisten fuer Filme und Serien werden kurz zwischengespeichert, damit ein Quellenwechsel nicht erneut alle Indexseiten abfragen muss.
- DNS over HTTPS nutzt eine neue Einstellungs-ID und ist dadurch auch bei bestehenden Profilen standardmaessig aktiv, bleibt danach aber ueber die allgemeinen Einstellungen abschaltbar.
- Die Standard-Aktion wird beim Start von Filmen und Folgen frisch aus Kodis aktuellem Add-on-Setting gelesen und nutzt die Profil-Datei nur als Rueckfall, damit Aenderungen aus dem Kodi-Settingsdialog sofort fuer die naechste Wiedergabe gelten.
- Die Standard-Aktion nutzt wieder Kodis native Enum-Speicherung und migriert alte Textwerte bei jedem Plugin-Aufruf, damit Aenderungen aus Add-on-Settings in aktiven Favoriten- und Folgenlisten wirklich gespeichert werden.

## [2026.07.14.1] - 2026-07-14

- Trakt-Anmeldung nutzt jetzt Device-Code-OAuth: xVAULT zeigt einen Geraetecode an, der unter trakt.tv/activate freigegeben wird.
- Trakt-Zugangsdaten werden robust im xVAULT-Profil gespeichert; Token-Refresh bleibt auch dann stabil, wenn Kodi Settings leere Werte zurueckliefern.
- Trakt-Status, Watchlist, Collection, Gesehen-Import, Alias-Suche, Token-Refresh sowie die Schreib-Payloads fuer History, Scrobbling und Bewertungen wurden lokal und in Kodi geprueft.

## [2026.07.06.1] - 2026-07-06

- Filmpalast-Suchpfade werden nicht mehr doppelt kodiert, damit Titel mit Leerzeichen und Umlauten wieder Treffer liefern.
- Filmpalast nutzt die bestehende RequestHandler-Logik mit unveraendert kodierten URLs und wertet VOE-HD-Links aus der aktuellen Streamstruktur wieder aus.

## [2026.07.05.5] - 2026-07-05

- LiveTV lite bleibt auch bei temporaer nicht erreichbarer 2ix2-API nutzbar und liest dann Nydus als Ersatzquelle.
- Nydus-Sender werden nach Deutsche TV, Österreichische TV und Schweizer TV einsortiert; echte HLS-Streams werden beim Start aus dem Nydus-Player dynamisch aufgeloest.
- Browser-only- oder Cloudflare-Embed-Ziele aus Nydus werden nicht als defekter Kodi-Stream gestartet, sondern mit Hinweis abgefangen.

## [2026.07.05.4] - 2026-07-05

- Zuletzt gefundene Quellenlisten fuer Filme und Serien werden fuer die aktuelle Kodi-Sitzung kurz zwischengespeichert, damit ein erneuter Quellenwechsel nicht sofort wieder alle Indexseiten abfragt.
- Der Quellen-Cache ist auf wenige Eintraege und 15 Minuten begrenzt und beruecksichtigt Titel, Folge, Sprache, Qualitaet, Sortierung, Limit und aktivierte Provider.
- Hoster-Links werden weiterhin frisch aufgeloest und getestet; der Cache speichert nur die bereits gesammelte Quellenliste.
- Der Wiedergabe-Waechter prueft den Fortschritt erst, wenn Kodi eine gueltige Gesamtlaufzeit meldet.
- Das GitHub-Pages-Downloadarchiv wird auf die aktuelle Version plus zwei Vorversionen begrenzt, damit Deployments stabil kleiner bleiben.

## [2026.07.05.3] - 2026-07-05

- Serienwiedergaben brechen nicht mehr vor dem Kodi-Player-Start ab, wenn die Metadaten nur `imdb_id` statt `imdbnumber` enthalten.
- Player-InfoLabels werden robuster aus vorhandenen Metadaten aufgebaut, damit Favoriten, alte Listen und Android/Kodi-Varianten keine fehlenden Pflichtfelder erzwingen.
- Startfehler im Player werden jetzt im Kodi-Log als Playback-Startfehler protokolliert, statt still verschluckt zu werden.
- VOE-Quellen werden bei Bedarf direkt in xVAULT auf einen abspielbaren MP4/HLS-Link aufgeloest, auch wenn ResolveURL die aktuelle VOE-Ausweichdomain noch nicht kennt.
- Hoster-Seiten, die ResolveURL nicht zu einem echten Direktstream aufloesen kann, werden nicht mehr an Kodi als Video uebergeben.
- Lokale Cookie-Laufzeitdaten werden beim Release-Build nicht mehr in das Add-on-ZIP aufgenommen.
- Das GitHub-Pages-Downloadarchiv wird auf die aktuelle Version plus die letzten 10 Vorversionen begrenzt, damit die Repo-Page zuverlässig deployed.

## [2026.07.05.2] - 2026-07-05

- SerienStream nutzt als feste Domain `serienstream.to`.
- Alte lokal gespeicherte SerienStream-Domainwerte werden beim Providercheck und beim Scraperstart automatisch auf `serienstream.to` migriert.
- Der SerienStream-DoH-Fallback wurde auf die neue Domain und die passende aktuelle Fallback-IP umgestellt.
- Bei Serien mit gleichem Veröffentlichungsdatum mehrerer Folgen hat der Episodentitel jetzt Vorrang; Datums-Fallbacks werden nur noch genutzt, wenn sie eindeutig sind.

## [2026.07.05.1] - 2026-07-05

- SerienStream prueft bei Serienfolgen mit abweichender Anbieter-Staffelzaehlung den Episodentitel und die Erstausstrahlung, statt nur die direkte SxxExx-Nummer blind zu uebernehmen.
- Folgen wie `Chilling Adventures of Sabrina` S1E12 werden dadurch auf die passende Anbieter-Staffel und Anbieter-Folge gemappt, wenn TMDB/xVAULT und Anbieter die Staffeln unterschiedlich schneiden.
- Direkt gefundene Anbieterfolgen werden bei vorhandenem Episodentitel validiert, damit Quellen nicht auf eine falsche Folge zeigen.

## [2026.07.04.7] - 2026-07-04

- `Jetzt synchronisieren` bricht nicht mehr mit PluginError ab, wenn lokale Bookmark-Daten doppelte oder beschädigte Fortsetzen-Einträge enthalten.
- Der Bookmark-Speicher bereinigt doppelte Einträge beim Speichern und Entfernen und findet Fortsetzen-Einträge auch dann wieder, wenn sie nicht an erster Stelle stehen.
- Die manuelle Synchronisation gleicht den Login-Zustand vor dem Start ab und meldet unerwartete lokale Sync-Fehler sauber statt mit Python-Traceback.

## [2026.07.04.6] - 2026-07-04

- Die Einstellung `Standard-Aktion` verwendet im Kodi-Settingsdialog stabile Textwerte statt anfaelliger numerischer Enum-Werte.
- Alte Profile mit `0`, `1` oder `2` werden weiter verstanden und beim Start auf `Dialog`, `Verzeichnis` oder `Autoplay` migriert.
- `Dialog` bleibt dadurch auch dann gespeichert, wenn die Add-on-Einstellungen aus einer aktiven Folgen- oder Quellenliste heraus geoeffnet werden.

## [2026.07.04.5] - 2026-07-04

- Film- und Serienstarts verwenden die aktuelle Einstellung `Standard-Aktion` wieder als fuehrende Auswahl.
- Alte Favoriten oder externe Wiedergabe-Links mit gespeichertem Autoplay-Wert koennen `Dialog` oder `Verzeichnis` nicht mehr ueberstimmen.
- Neue externe Wiedergabe-Links speichern die Standard-Aktion nicht mehr fest in den Medien-Metadaten.

## [2026.07.04.4] - 2026-07-04

- Die xVAULT-Synchronisation verwendet die lokale Auth-Datei jetzt als fuehrende Login-Quelle, wenn Kodi-Settings und Auth-Datei auseinanderlaufen.
- Veraltete Sync-API-Keys in den Kodi-Settings werden automatisch mit der Auth-Datei abgeglichen.
- Server-Backups von Favoriten koennen dadurch wiederhergestellt werden, ohne faelschlich mit `Nicht angemeldet` abgewiesen zu werden.
- Der Sync-API-Client versucht bei `UNAUTHORIZED` einen weiteren gespeicherten Key, falls Kodi noch einen abweichenden Key in den Settings haelt.

## [2026.07.04.3] - 2026-07-04

- Neuer Einstellungsbereich `Indexseiten 3 (DE)` fuer CINE.TO, FILMFANS, NOX, SERIENFANS und STREAMCLOUD.FORUM.
- Neue lokale Scraper fuer CINE.TO, FILMFANS, NOX, SERIENFANS und STREAMCLOUD.FORUM wurden eingebunden.
- STREAMCLOUD.FORUM kann Filme und Serien ueber die Such- und Playerstruktur auswerten und blendet interne Hilfslinks ohne abspielbaren Medienbezug aus.
- Der bisherige Einstellungsbereich `Indexseiten (DE)` heisst nun `Indexseiten 1 (DE)`.
- Movie4k wurde auf die aktuelle API-Struktur ueber `movie4k.sx` umgestellt; alte gespeicherte Movie4k-Domains werden beim Providercheck automatisch migriert.
- Die DoH-Logik wurde fuer die aktiven Indexseiten vereinheitlicht, sodass Seitenabrufe bei aktivierter Option ueber den xVAULT-RequestHandler mit Cloudflare-DoH laufen.
- BS.to und SerienStream nutzen direkte Session-Requests nur noch als Rueckfall, wenn DNS over HTTPS deaktiviert ist.

## [2026.07.04.2] - 2026-07-04

- DNS over HTTPS kann in den allgemeinen Einstellungen aktiviert oder deaktiviert werden.
- xVAULT nutzt bei aktivierter Option Cloudflare DNS over HTTPS fuer HTTP-Anfragen, ohne die urspruengliche Domain im Request zu ersetzen.
- SerienStream/serienstream.to nutzt ebenfalls den neuen DoH-Weg; die bekannte feste SerienStream-IP wird nur noch als Rueckfall verwendet, wenn Cloudflare-DoH keine nutzbare Verbindung liefert.
- Der Provider-Domaincheck beim Kodi-Start prueft bei aktivem DoH blockierte oder fehlgeschlagene Domains ein zweites Mal ueber den xVAULT-RequestHandler, damit Quellen nicht vorzeitig deaktiviert werden.

## [2026.07.04.1] - 2026-07-04

- Serien pruefen nun auch TMDB-Staffel 0 und zeigen vorhandene Specials oder Pilotfilme als eigenen Eintrag in der Staffelliste an.
- Specials werden in der Episodenliste als `Special 01` statt als `0x01` dargestellt.
- Staffel-0-Folgen bleiben beim Abspielen echte Serienfolgen und werden nicht mehr als Filme an die Scraper uebergeben.
- SerienStream, BS.to und Vixstream koennen Staffel-0-Folgen jetzt gezielt als Serien-Specials behandeln.
- Fehlende Ausstrahlungsdaten bei Staffeln oder Folgen blenden Eintraege nicht mehr versehentlich aus.

## [2026.07.03.4] - 2026-07-03

- SerienStream findet Sonderfolgen nun ueber Staffel 0, wenn die normale Serienfolge auf serienstream.to nicht vorhanden ist und der Episodentitel zur Special-Folge passt.
- Episodentitel und Episoden-Erstausstrahlung werden an die Quellen-Scraper weitergereicht, damit Anbieter-Sonderfaelle gezielter erkannt werden koennen.
- Vixstream speichert keine kurzlebigen Embed-Links mehr in der Quellenliste, sondern loest sie frisch beim Abspielen auf.
- Filmpalast akzeptiert bei Serien nur noch Treffer mit passender SxxEyy-Kennung und nimmt S01E10 nicht mehr als Ersatz fuer S01E11.

## [2026.07.03.3] - 2026-07-03

- Nach Film- oder Episodenende konkurrieren automatischer Listenrefresh, Serien-Positionslogik und Positionswiederherstellung nicht mehr miteinander.
- Serienlisten mit aktivierter Option `Status - Bei Serien die erste ungesehene Folge auswählen` setzen die Auswahl nun selbst; der Player stellt in diesem Fall nicht zusaetzlich die alte Episode wieder her.
- Der doppelte Listenreload bei Serien wurde entfernt, damit Kodi nach Playback-Ende nicht zweimal hintereinander die Folgenliste neu aufbaut.
- Handbuch um BS.to-Hinweise, Erstinstallationsvorgaben, Filmpalast-Verhalten sowie Konto-, Kennwort- und Synchronisationsaktionen ergaenzt.

## [2026.07.03.2] - 2026-07-03

- LiveTV-Senderlisten bieten eine Funktion, mit der alle aktuell sichtbaren Sender auf erreichbare Streams geprueft werden koennen.
- Vor Start der LiveTV-Senderpruefung warnt xVAULT vor einer moeglichen Laufzeit von bis zu 30 Minuten und weist darauf hin, dass der Vorgang fuer schwache Systeme nicht empfohlen wird.
- Nach Abschluss der LiveTV-Senderpruefung zeigt xVAULT in einem Ergebnisdialog an, wie viele Sender geprueft wurden, wie viele funktionieren und wie viele temporaer gesperrt wurden.
- Nicht erreichbare LiveTV-Sender werden nach der Pruefung temporaer bis zum naechsten xVAULT-Hauptstart ausgeblendet.
- Die LiveTV-Senderpruefung zeigt waehrend des Laufs Status und Fortschritt an und kann ueber den Kodi-Fortschrittsdialog abgebrochen werden.
- GitHub-Pages-Unterseite `handbuch/` als umfassende xVAULT-Wissensdatenbank ergaenzt.
- Startseite der GitHub Page verlinkt das neue Handbuch mit Umami-Event.
- README-Hinweise zu Handbuch und Umami-Einbindung aktualisiert.

## [2026.07.03.1] - 2026-07-03

- Vorbereitete LiveTV-Senderlisten-Pruefung mit Fortschrittsdialog, Warnhinweis und temporaerer Ausblendung nicht erreichbarer Sender.

## [2026.07.02.4] - 2026-07-02

- Neuer Hauptmenuepunkt `LiveTV lite` direkt nach `LiveTV` ergaenzt.
- LiveTV lite liest Deutsche TV, Österreichische TV und Schweizer TV aus der 2ix2-WordPress-API, extrahiert die JWPlayer-HLS-Streams und spielt sie mit der bestehenden xVAULT-HLS-Konfiguration ab.
- Nicht erreichbare 2ix2-HLS-Manifeste werden vor dem Kodi-Start abgefangen, damit tote Quellen keinen Playback-Fehler ausloesen.

## [2026.07.02.3] - 2026-07-02

- LiveTV bestaetigt HLS-Kandidaten vor der Kodi-Uebergabe in zwei weiteren kurzen Pruefrunden, damit flappende Sender mit wechselnden HTTP-500-Segmenten nicht in einem haengenden Player landen.
- Leere oder nicht auswertbare HLS-Manifeste werden jetzt explizit blockiert, statt als scheinbar brauchbarer Stream durchzurutschen.

## [2026.07.02.2] - 2026-07-02

- LiveTV startet HLS-Sender nur noch, wenn das neueste Segment erreichbar ist; defekte Live-Rand-Segmente fuehren nun zum Ersatzstream statt zum Kodi-Playback-Fehler.
- Signierte HLS-Manifest-URLs werden ohne Kodi-MIME-Query gestartet, damit Anbieter die URL nicht wegen zusaetzlicher Parameter ablehnen.

## [2026.07.02.1] - 2026-07-02

- LiveTV prueft vor dem Start mehrere aktuelle HLS-Segmente statt nur das letzte Segment der Playlist.
- Fehlerhafte Range-Requests werden mit einem normalen Segmentabruf gegengeprueft, damit brauchbare Streams nicht faelschlich blockiert werden.
- Bei instabilen Sendern nutzt xVAULT automatisch eng passende Ersatzstreams wie HD+ oder Backup-Varianten, ohne auf fremde Sender zu wechseln.

## [2026.06.30.9] - 2026-06-30

- Filmpalast erkennt die aktuelle Suchergebnis- und Streamlink-Struktur wieder.
- Filmpalast nutzt fuer Such- und Detailseiten eine eigene HTTPS-Anfrage, damit `%20`-Suchpfade in Kodi nicht doppelt kodiert werden.
- Filmpalast-Quellen werden nicht mehr vorzeitig durch ResolveURL gefiltert, damit gueltige Hoster in der Quellenliste sichtbar bleiben.
- Parser- und Kodi-RPC-Test gegen Over Your Dead Body (2026), The Greatest Showman und Shrek 2 - Der tollkuehne Held kehrt zurueck erfolgreich durchgefuehrt.

## [2026.06.30.8] - 2026-06-30

- Frische Erstinstallationen setzen einmalig die Streamsprache auf Deutsch und die Standard-Aktion auf Autoplay.
- Bestehende Profile und spaetere Updates behalten ihre gewaehlten Wiedergabe-Einstellungen; die Erstinstallationsvorgabe wird dort nicht erneut erzwungen.

## [2026.06.30.7] - 2026-06-30

- LiveTV ordnet FC-Bayern-Sender jetzt der Kategorie Sport statt Regional zu.
- LiveTV berechnet Kategorien auch beim Laden eines vorhandenen Senderlisten-Caches neu, damit Korrekturen ohne manuellen Refresh greifen.

## [2026.06.30.6] - 2026-06-30

- BS.to zeigt nur noch Quellen an, die ohne reCAPTCHA-Anforderung erkannt werden.
- CAPTCHA-geschuetzte BS.to-Quellen werden vor der Quellenliste ausgefiltert und nicht automatisiert umgangen.
- Der optionale BS.to-Login bleibt freiwillig; ohne Zugangsdaten wird weiterhin nach frei verfuegbaren Quellen gesucht.

## [2026.06.30.5] - 2026-06-30

- Optionaler Serien-Scraper fuer BS.to im xVAULT-Provider-System ergaenzt.
- Serienliste, Staffel-/Episodenlinks, Deutsch/Englisch/Deutsch-Sub-Sprachen und Hoster werden aus der aktuellen BS.to-Seitenstruktur gelesen.
- Optionaler BS.to-Login in den Konten-Einstellungen ergaenzt; CAPTCHA-geschuetzte Hoster werden markiert und nicht automatisiert umgangen.

## [2026.06.30.4] - 2026-06-30

- Kinox erkennt die neue Suchseiten-Struktur und uebernimmt Deutsch, Englisch sowie Deutsch/Englisch als echte Stream-Sprachen.
- Kinokiste, KKiste und Movie2k verwenden browsernahe API-Header, robuste Watch-URL-Fallbacks und uebernehmen die Sprache aus der Watch-Antwort.
- VixStream reicht die bevorzugte Sprache bis in Embed- und Playlist-URL weiter; Huhu ist als mehrsprachiger Scraper markiert.
- Movie2k2 verhindert breite Fallback-Falschtreffer wie Resident Alien zu Resident Evil.
- Ignorierte RequestHandler-Fehler erzeugen keine Kodi-Error-Logs mehr; SerienStream wertet Fehler-Sentinel beim Login nicht mehr als erfolgreichen Login.
- Die neue Projektregel verlangt nach Plugin-Aenderungen einen Kodi-Test per JSON-RPC.

## [2026.06.30.3] - 2026-06-30

- SerienStream liest jetzt alle Sprachvarianten einer Episode ein, statt nur deutsche Links zu uebernehmen.
- Bei Resident Alien S01E01 werden bei Sprache `Alle` nun deutsche, englische und Ger-Sub-Quellen angezeigt.
- Die zentrale Sprachzuordnung priorisiert explizite Scraper-Sprachangaben vor Zusatzinfos, damit `Ger-Sub` nicht faelschlich als `MULTI` markiert wird.
- Fix lokal in Kodi 21.3 per JSON-RPC gegen Resident Alien S01E01 getestet.

## [2026.06.30.2] - 2026-06-30

- Autoplay wird fuer Filme und Serien automatisch verhindert, wenn die bevorzugte Stream-Sprache auf `Alle` steht.
- Bei Sprache `Alle` fragt xVAULT einmal nach `Dialog` oder `Verzeichnis` und speichert diese Auswahl als neue Standard-Aktion.
- Autoplay bleibt fuer `Deutsch`, `Englisch` und `Mehrsprachig` weiterhin nutzbar.

## [2026.06.30.1] - 2026-06-30

- Film- und Serienquellen koennen jetzt nach bevorzugter Stream-Sprache sortiert oder strikt gefiltert werden.
- Wiedergabe-Einstellungen um bevorzugte Stream-Sprache, Sprachfilter-Modus, unbekannte Sprache und Mehrsprachig-erlauben Optionen ergaenzt.
- Streamlisten zeigen die erkannte Sprache mit `DE`, `EN`, `MULTI` oder `?` direkt in der Quellenzeile an; LiveTV bleibt unveraendert deutsch.

## [2026.06.29.8] - 2026-06-29

- LiveTV-HLS startet jetzt plattformneutral ueber eine neue Wiedergabe-Engine-Auswahl: automatisch, Kodi intern, FFmpeg Direct oder InputStream Adaptive.
- Der automatische Modus bevorzugt FFmpeg Direct, wenn es auf der Kodi-Plattform installiert und aktiviert ist, und faellt sonst auf Kodis interne HLS-Wiedergabe zurueck.
- xVAULT prueft vor dem Start eines HLS-LiveTV-Streams Manifest und aktuelles Segment und loest defekte oder nicht erreichbare Streams einmal neu auf, damit Kodi nicht in einen nativen Crashpfad laeuft.

## [2026.06.29.7] - 2026-06-29

- LiveTV-Einstellungen um eine Puffergroesse in MB ergaenzt; 0 MB laesst den Kodi-Standard unveraendert.
- Beim Start eines LiveTV-Streams setzt xVAULT die Kodi-Dateicachegroesse auf den gewaehlten Wert und aktiviert Netzwerkstream-Pufferung.

## [2026.06.29.6] - 2026-06-29

- LiveTV-Senderlisten zeigen im Infofeld des markierten Senders jetzt `Aktuell` und `Gleich` aus dem EPG.
- Senderlogos werden als Poster/Thumb/Icon gesetzt, damit im Infofenster links oben das passende Senderlogo erscheint.
- Fehlende Senderlogos werden ueber lokale Alias-Zuordnung und einen gecachten Logo-Fallback ergaenzt.

## [2026.06.29.5] - 2026-06-29

- LiveTV zeigt vor dem Streamstart die aktuell laufende Sendung aus einem lokalen XMLTV-EPG-Cache an.
- EPG-Daten werden mit deutschem Kanal-Mapping lokal zwischengespeichert und auf LiveTV-Sendernamen wie RTL 2, 3sat, 13th Street oder Das Erste abgeglichen.
- LiveTV-Einstellungen um EPG an/aus, EPG-Dialog und EPG-Cachezeit ergaenzt.

## [2026.06.29.4] - 2026-06-29

- LiveTV-Refresh beendet den Kodi-Directory-Aufruf jetzt sauber, damit beim Aktualisieren der Senderliste kein `GetDirectory`-Fehler im Kodi-Log entsteht.
- Live-Test in Kodi 21.3 mit lokaler Installation durchgefuehrt: Senderliste geladen und ein HLS-Sender erfolgreich gestartet.

## [2026.06.29.3] - 2026-06-29

- LiveTV als eigenstaendiges xVAULT-Modul neu integriert.
- Deutsche Sender werden ueber `huhu.to` geladen, lokal gecacht, kategorisiert und erst beim Abspielen aufgeloest.
- LiveTV-Menue mit Kategorien, Suche, Favoriten, Refresh-Aktion und eigenen Einstellungen ergaenzt.
- Historische Texte und GitHub-Page-Hinweise neutralisiert, damit keine alten Quellnamen mehr in den veroeffentlichten Dateien auftauchen.

## [2026.06.29.2] - 2026-06-29

- Einstellung `Automatische Updates aktivieren` im Bereich Allgemein ergaenzt; Standard ist aktiviert.
- Interner Update-Check und automatisches Repository-Bootstrap respektieren die neue Einstellung.
- README, Changelog, Add-on-Metadaten und GitHub Page auf Version `2026.06.29.2` aktualisiert.

## [2026.06.29.1] - 2026-06-29

- Alter LiveTV-/Livestream-Bereich vollstaendig aus Menue, Routing, Einstellungen, Daten und Repository-Playlisten entfernt.
- Eingebettete Altmodule und zugehoerige Senderdaten entfernt.
- README, DEPENDENCIES.md, Add-on-Metadaten und GitHub Page auf Filme/Serien abgeglichen.
- Umami Analytics auf allen GitHub-Pages-HTML-Seiten mit Do-Not-Track, ausgeschlossenen URL-Suchparametern und Link-Events ergaenzt.
- GitHub-Page-Bereich `Neu in` wird beim Build automatisch aus `CHANGELOG.txt` aktualisiert.

## [2026.06.28.10] - 2026-06-28

- Umami-Tracking-Script im Head der GitHub Page ergaenzt.
- Umami-Pixel auf der GitHub Page ergaenzt.
- Episodenstatus wird nach natuerlichem Playback-Ende oder Stop ab 90 Prozent sofort als gesehen gespeichert.
- Folgenlisten werden nach dem Playback ueber den gespeicherten Staffel-Container gezielt neu geladen.

## [2026.06.28.9] - 2026-06-28

- Einstellungsuebersicht aus README.md entfernt; README-Versioncheck entsprechend angepasst.
- Staffel-/Serien-Gesehenstatus wird nach Episoden-Playback sofort aktualisiert und Repository-ZIPs wurden neu gebaut.

## [2026.06.28.8] - 2026-06-28

- GitHub Issue Forms fuer Fehler und Verbesserungsvorschlaege ergaenzt.
- README-Dokumentation auf die aktuelle Plugin-Version `2026.06.28.8` und die Einstellungen aus `resources/settings.xml` abgeglichen.
- Schutzmassnahmen ergaenzt, damit README bei Versions- und Einstellungsaenderungen aktualisiert wird.
- CONTRIBUTING-Hinweise fuer Issues, README-Pflege und GitHub-Page-Schutz ergaenzt.
