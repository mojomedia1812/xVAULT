# Changelog

## [Unreleased]

## [2026.07.04.1] - 2026-07-04

- Serien pruefen nun auch TMDB-Staffel 0 und zeigen vorhandene Specials oder Pilotfilme als eigenen Eintrag in der Staffelliste an.
- Specials werden in der Episodenliste als `Special 01` statt als `0x01` dargestellt.
- Staffel-0-Folgen bleiben beim Abspielen echte Serienfolgen und werden nicht mehr als Filme an die Scraper uebergeben.
- SerienStream, BS.to und Vixstream koennen Staffel-0-Folgen jetzt gezielt als Serien-Specials behandeln.
- Fehlende Ausstrahlungsdaten bei Staffeln oder Folgen blenden Eintraege nicht mehr versehentlich aus.

## [2026.07.03.4] - 2026-07-03

- SerienStream findet Sonderfolgen nun ueber Staffel 0, wenn die normale Serienfolge auf s.to nicht vorhanden ist und der Episodentitel zur Special-Folge passt.
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
