# xVAULT Synchronisation

## Zweck

Die xVAULT-Synchronisation sichert benutzerbezogen Kodi-Favoriten und Wiedergabestände, damit diese nach Neuinstallation, Gerätewechsel oder paralleler Nutzung auf mehreren Geräten wiederhergestellt und abgeglichen werden können.

## API-Endpunkte

Die API akzeptiert JSON und antwortet immer mit JSON.

Aktueller API-Host: `https://all-stats.de/index.php?action=`

- `POST /index.php?action=register`
- `POST /index.php?action=login`
- `POST /index.php?action=favorites_push`
- `GET /index.php?action=favorites_pull`
- `POST /index.php?action=favorites_delta`
- `GET /index.php?action=favorites_state`
- `POST /index.php?action=binge_push`
- `GET /index.php?action=binge_pull`
- `POST /index.php?action=sync_push`
- `GET /index.php?action=sync_pull`
- `GET /index.php?action=status`

Wenn URL-Rewriting aktiv ist, funktionieren auch die entsprechenden `/api/...`-Pfade.

## Datenbanktabellen

- `users`: Benutzerkonto, Passwort-Hash, API-Key-Hash, Login-Metadaten.
- `favorites_sync_meta`: aktueller Revisionsstand der Favoriten pro Benutzer.
- `favorites_items`: kompakter Favoritenbestand pro Benutzer. Jeder Favorit liegt als einzelner Eintrag mit stabilem Schlüssel, Hash, Reihenfolge und Revision vor. Löschungen werden als Tombstone gespeichert, damit entfernte Favoriten auf anderen Geräten ebenfalls entfernt werden.
- `favorites_backups`: Rückwärtskompatibler Vollstand pro Benutzer. Neue Clients nutzen bevorzugt `favorites_delta`; alte Clients können weiter über Push/Pull arbeiten.
- `binge_state`: aktueller Wiedergabe-/Binge-Stand pro stabilem `item_key`. Einträge werden pro Film/Folge per Upsert zusammengeführt; der neuere Fortschritt gewinnt, bereits abgeschlossene Einträge bleiben gesehen.
- `sync_log`: technische Sync-Historie ohne sensible Inhalte.

## Multi-Geräte-Verhalten

- Beim Start zieht xVAULT den aktuellen Binge-Stand vom Server und wendet Bookmarks/Gesehen-Status lokal an.
- Im laufenden Betrieb prüft der Hintergrunddienst regelmäßig auf Remote-Änderungen. Dadurch werden Favoriten und Binge-Status auch ohne Neustart auf anderen angemeldeten Geräten sichtbar.
- Favoriten werden revisionsbasiert abgeglichen. Das Plugin merkt sich lokal die letzte bekannte Serverrevision und sendet danach nur neue, geänderte oder gelöschte Favoriten.
- Parallele Hinzufügungen von PC, Android TV und Raspberry bleiben erhalten, weil Favoriten einzeln per stabilem Schlüssel zusammengeführt werden.
- Entfernte Favoriten werden als Löschmarke gespeichert. Dadurch taucht ein gelöschter Favorit nicht wieder auf, nur weil ein anderes Gerät noch einen älteren lokalen Stand hatte.
- Wenn ein Gerät länger offline war, fragt es beim nächsten Abgleich nur die Änderungen seit seiner letzten Revision ab und gleicht sich damit wieder an den gemeinsamen Konto-Stand an.
- Binge-/Gesehen-Status ist benutzerbezogen. Wenn mehrere Geräte mit demselben xVAULT-Konto angemeldet sind, sehen alle Geräte denselben Stand.

Die Tabellen werden beim ersten API-Aufruf automatisch angelegt.

## Sicherheitskonzept

- Kennwörter werden serverseitig mit `password_hash()` gespeichert.
- Logins geben einen kryptografisch zufälligen API-Key zurück.
- In der Datenbank wird nur der SHA-256-Hash des API-Keys gespeichert.
- Das Kodi-Plugin speichert lokal nur E-Mail-Adresse, API-Key, Geräte-ID, Sync-Status, Revisionsnummern und Hash-/Zeitstempel.
- Kennwörter werden im Plugin nicht dauerhaft gespeichert.
- `api/config.php` ist per `.gitignore` ausgeschlossen und darf nicht ins Repository.

## Plugin-Einstellungen

Unter `Einstellungen -> Konten` stehen bereit:

- Synchronisation aktivieren
- E-Mail-Adresse
- Status
- Letzte Synchronisation
- Anmelden
- Registrieren
- Jetzt synchronisieren
- Backup vom Server wiederherstellen
- Status anzeigen
- Datenschutz-Hinweis anzeigen
- Abmelden

## Wiederherstellung

Nach Anmeldung prüft xVAULT, ob ein Favoritenstand vorhanden ist. Der Benutzer entscheidet, ob der Serverstand lokale Favoriten ersetzt oder mit ihnen zusammengeführt wird. Vor dem Schreiben wird die lokale `favourites.xml` als `.xvault-backup-YYYYMMDDHHMMSS` gesichert.

## Deployment

Serverdateien liegen im Repository unter `api/`.

Auf dem Zielhost muss eine echte `config.php` mit Datenbankzugangsdaten neben `index.php` liegen. Im Repository liegt nur `config.example.php`.

Aktueller Upload für den Kasserver-Space:

- `api/index.php` -> `/index.php`
- `api/.htaccess` -> `/.htaccess`
- lokale, nicht versionierte `api/config.php` -> `/config.php`

## Secrets

Keine FTP-, Datenbank-, API- oder Kennwortdaten in Git committen. Für lokale Tests `api/config.php`, `.env` oder vergleichbare nicht versionierte Dateien verwenden.
