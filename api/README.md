# Geräteabgleich, Protokoll 2

`index.php` lädt `sync_v2.php`. Beide Dateien müssen gemeinsam ausgeliefert werden. Die bestehende `config.php` bleibt erhalten; es sind keine neuen Produktionszugänge erforderlich. Der neue Client ruft `POST ?action=sync_exchange` auf. Alle Daten und Geräte bleiben an das authentifizierte Konto gebunden.

## Anmeldung und Umstellung

Registrierung und Anmeldung geben weiterhin `email` und `api_key` zurück. Eine Anmeldung erzeugt einen zusätzlichen gehashten Schlüssel in `sync_sessions`, statt den Kontoschlüssel zu ersetzen. Ein optionales `device_id` bindet den Schlüssel an die Installation. Bestehende Kontoschlüssel bleiben gültig und werden beim ersten Geräteabgleich einer Installation zugeordnet. Ein Kennwort-Reset entfernt alle Sitzungen und den alten Kontoschlüssel.

Die Tabellen `sync_devices`, `sync_sessions`, `sync_accounts`, `sync_entities` und `sync_operations` werden automatisch als InnoDB/utf8mb4 angelegt. Für die erste produktive Umstellung ist vorher ein Datenbankbackup erforderlich. Es werden keine bestehenden Favoriten- oder Wiedergabetabellen gelöscht.

Beim ersten Abgleich eines Kontos werden die bisherigen Serverfavoriten einschließlich Löschmarken und die bisherigen Wiedergabe-/Gesehen-Stände in das neue Format übernommen. Film, Serie, Staffel und Folge erhalten eindeutige, zwischen PHP und Python identische Inhaltsschlüssel. Die bisherigen Tabellen bleiben als Migrationsquelle erhalten; danach ist der neue Kontostand maßgeblich.

Nach der Umstellung eines Kontos lehnt die API alte schreibende Sync-Endpunkte mit `CLIENT_UPDATE_REQUIRED` ab. Das verhindert, dass alte Clients ungeprüfte Vollstände in den neuen Abgleich schreiben. Deshalb müssen alle beteiligten Geräte auf die neue Plugin-Version wechseln. Eine bereits ungültige alte Anmeldung benötigt einmalig eine neue Anmeldung.

Für die Veröffentlichung zuerst Datenbank und Serverdateien sichern, dann beide API-Dateien zusammen ausliefern und anschließend die neue Plugin-Version auf allen Geräten verteilen. Ein späteres Zurückrollen darf neue Änderungen nicht aus den inzwischen veralteten Legacy-Tabellen rekonstruieren: nach der Migration ist vor einem Rollback auch der neue Kontostand zu sichern und gegebenenfalls zu übertragen.

## Austausch

Die Anfrage enthält `device_id`, `device_name`, den zuletzt lokal gespeicherten `cursor`, optional `active` und höchstens 200 `operations`. Jede Operation enthält:

- eine unveränderliche UUID `id` zur Wiederholung nach Verbindungsabbrüchen;
- `kind` (`favorite`, `progress`, `watch`) und den Inhaltsschlüssel `key`;
- `base_revision`, die beim Erstellen bekannte Eintragsversion;
- ein `patch` mit tatsächlich geänderten Feldern oder `deleted: true`;
- bei einer bewussten Konfliktentscheidung die ursprüngliche ID in `resolves`.

Die Kontenzeile wird innerhalb einer Datenbanktransaktion gesperrt. Feldversionen erlauben unabhängige Änderungen am selben Favoriten; widersprüchliche Änderungen oder veraltete Wiederherstellungen gelöschter Einträge werden als Konflikt protokolliert. Die Operation wird genau einmal verarbeitet. Die Antwort enthält Ergebnisse, den konsistenten Kontostand mit Revision, Geräte, die letzten 100 Protokolleinträge und sämtliche offenen Konflikte. Für persönliche Konten wird zunächst ein vollständiger Antwort-Snapshot verwendet; nur lokale Änderungen werden hochgeladen. Der Cursor bestätigt den zuletzt empfangenen Stand und löst keine Datenlöschung aus.

Serverrevisionen entscheiden über Aktualität. Gerätezeiten dienen ausschließlich der historischen Anzeige bzw. einmaligen Übernahme alter Daten. Das Protokoll hat zusätzlich eine pro Konto fortlaufende Ereignisnummer, damit auch Konflikte eindeutig geordnet sind. `last_seen_at` erfasst Erreichbarkeit, `last_used_at` aktive Nutzung und `last_changed_at` angenommene Änderungen. Ein Hintergrundabruf allein macht ein Gerät nicht zum zuletzt benutzten Gerät.

Wiedergaben erhalten Sitzungskennungen und aufsteigende Sequenznummern. Alte Zwischenstände derselben Sitzung werden ignoriert, bewusstes Zurückspulen bleibt möglich. Konkurrierende Sitzungen bleiben im Änderungsprotokoll erhalten; pro Sitzung wird nur die jüngste offene Alternative angeboten. Eine Konfliktauswahl beginnt einen neuen Zweig, damit alte Player sie nicht rückgängig machen. Explizite Gesehen-Markierungen sind vom Fortschritt getrennt. Während einer laufenden Videowiedergabe werden lokale Lesezeichen und Gesehen-Stände nicht durch fremde Snapshots ersetzt.

`revoke_device` widerruft ausschließlich die Sitzungen des ausgewählten Geräts im eigenen Konto. Die Gerätehistorie bleibt erhalten. Ein normaler Logout versucht ebenfalls den serverseitigen Widerruf; offline erfolgt zumindest die lokale Abmeldung.

## Lokale Prüfung

`python -B -m unittest discover -s tools/tests -v` startet isolierte PHP-Testserver mit SQLite. PHP benötigt `pdo_sqlite`. Echte konkurrierende Datenbanktransaktionen werden zusätzlich mit einer **ausschließlich für Tests vorgesehenen** MariaDB-/MySQL-Datenbank geprüft:

```powershell
# Diese Variablen ausschließlich auf eine leere lokale Testdatenbank setzen:
$env:XVAULT_TEST_MYSQL_DSN = 'mysql:host=127.0.0.1;port=33379;dbname=xvault_sync_test;charset=utf8mb4'
$env:XVAULT_TEST_MYSQL_USER = 'test_user'
# Passwort im lokalen Prozess hinterlegen, niemals ins Repository schreiben.
python -B -m unittest discover -s tools/tests -v
```

Der Testadapter verwendet die echten PHP-Handler und zusätzlich fünf unabhängige PHP-Prozesse für den Sperrentest. Die Tests erzeugen temporäre Konten und Tabellen; niemals auf eine produktive Datenbank richten. Der installierte Kodi wird getrennt mit `tools/kodi_sync_smoke.py` und einem privaten Loopback-Testprofil geprüft. Rohprofile, Zugangsschlüssel und Testdaten liegen ausschließlich im ignorierten Diagnoseverzeichnis.
