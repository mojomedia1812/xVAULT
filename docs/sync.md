# xVAULT Synchronisation

## Zweck

Die xVAULT-Synchronisation sichert benutzerbezogen Kodi-Favoriten und Wiedergabestaende, damit diese nach Neuinstallation, Geraetewechsel oder paralleler Nutzung auf mehreren Geraeten wiederhergestellt und abgeglichen werden koennen.

## API-Endpunkte

Die API akzeptiert JSON und antwortet immer mit JSON.

Aktueller Produktivhost: `http://xvault-sql.ddnss.de/index.php?action=`

- `POST /index.php?action=register`
- `POST /index.php?action=login`
- `POST /index.php?action=favorites_push`
- `GET /index.php?action=favorites_pull`
- `POST /index.php?action=binge_push`
- `GET /index.php?action=binge_pull`
- `POST /index.php?action=sync_push`
- `GET /index.php?action=sync_pull`
- `GET /index.php?action=status`

Wenn URL-Rewriting aktiv ist, funktionieren auch die entsprechenden `/api/...`-Pfade.

## Datenbanktabellen

- `users`: Benutzerkonto, Passwort-Hash, API-Key-Hash, Login-Metadaten.
- `favorites_backups`: aktueller Favoritenstand pro Benutzer. Neue Pushes werden serverseitig mit dem aktuellen Serverstand zusammengefuehrt, ersetzen danach die vorherige Zeile dieses Benutzers und verhindern damit eine unbegrenzte Vollsnapshot-Historie. Explizite `deleted_keys` verhindern, dass entfernte Favoriten durch ein anderes Geraet wieder auftauchen.
- `binge_state`: aktueller Wiedergabe-/Binge-Stand pro stabilem `item_key`. Eintraege werden pro Film/Folge per Upsert zusammengefuehrt; der neuere Fortschritt gewinnt, bereits abgeschlossene Eintraege bleiben gesehen.
- `sync_log`: technische Sync-Historie ohne sensible Inhalte.

## Multi-Geraete-Verhalten

- Beim Start zieht xVAULT den aktuellen Binge-Stand vom Server und wendet Bookmarks/Gesehen-Status lokal an.
- Im laufenden Betrieb prueft der Hintergrunddienst regelmaessig auf Remote-Aenderungen. Dadurch werden Favoriten und Binge-Status auch ohne Neustart auf anderen angemeldeten Geraeten sichtbar.
- Favoriten werden vor jedem Push mit dem letzten Serverstand gemergt. Parallele Hinzufuegungen von PC, Android TV und Raspberry bleiben erhalten.
- Entfernte Favoriten werden als geloeschte Keys mitgesendet, damit ein paralleles Geraet sie nicht durch einen veralteten Snapshot erneut auf den Server schreibt.
- Binge-/Gesehen-Status ist benutzerbezogen. Wenn mehrere Geraete mit demselben xVAULT-Konto angemeldet sind, sehen alle Geraete denselben Stand.

Die Tabellen werden beim ersten API-Aufruf automatisch angelegt.

## Sicherheitskonzept

- Kennwoerter werden serverseitig mit `password_hash()` gespeichert.
- Logins geben einen kryptografisch zufaelligen API-Key zurueck.
- In der Datenbank wird nur der SHA-256-Hash des API-Keys gespeichert.
- Das Kodi-Plugin speichert lokal nur E-Mail-Adresse, API-Key, Geraete-ID, Sync-Status und Hash-/Zeitstempel.
- Kennwoerter werden im Plugin nicht dauerhaft gespeichert.
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

Nach Anmeldung prueft xVAULT, ob ein Favoriten-Backup vorhanden ist. Der Benutzer entscheidet, ob der Serverstand lokale Favoriten ersetzt oder mit ihnen zusammengefuehrt wird. Vor dem Schreiben wird die lokale `favourites.xml` als `.xvault-backup-YYYYMMDDHHMMSS` gesichert.

## Deployment

Serverdateien liegen im Repository unter `api/`.

Auf dem Zielhost muss eine echte `config.php` mit Datenbankzugangsdaten neben `index.php` liegen. Im Repository liegt nur `config.example.php`.

Aktueller Upload fuer den neuen Freehostia-Space:

- `api/index.php` -> `/xvault-sql.ddnss.de/index.php`
- `api/.htaccess` -> `/xvault-sql.ddnss.de/.htaccess`
- lokale, nicht versionierte `api/config.php` -> `/xvault-sql.ddnss.de/config.php`

## Secrets

Keine FTP-, Datenbank-, API- oder Kennwortdaten in Git committen. Fuer lokale Tests `api/config.php`, `.env` oder vergleichbare nicht versionierte Dateien verwenden.
