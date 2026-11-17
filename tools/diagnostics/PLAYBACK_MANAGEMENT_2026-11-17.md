# Wiedergabedaten und persönlicher Startbereich – lokaler Teststand

## Umfang

Unveröffentlichte Änderungen auf dem kanonischen Arbeitsstand einschließlich der
heutigen Staffel-/Quellen-Cachekorrekturen. GitHub, Updatefeeds, Website und
Statistikseite wurden nicht veröffentlicht oder verändert.

- Anzeige unter **Einstellungen / Mein xVAULT**: Aus, nur eigener Menüpunkt
  (Standard), oder zusätzlich Vorschau im Hauptmenü. Weiterschauen, nächste
  Folgen, Radar und Radio lassen sich einzeln ausblenden. Keine zusätzliche
  Vorschau innerhalb des persönlichen Menüs.
- Gemeinsame Kontextaktionen in persönlichen Listen, Film-/Seriensuche,
  Staffeln, Folgen, Collections, Personensuche und Quellen. Ausblenden behält
  die Position und ist geräte-/kontolokal; erfolgreicher erneuter Start macht
  einen ausgeblendeten Titel wieder sichtbar. Zurücksetzen der Position und
  Gesehen-/Ungesehen-Status sind getrennte Aktionen.
- Gemeinsame Wiedergabezustände auch für Kodis ListItem-Status und ResumePoint;
  über Inhalts-IDs empfangene Positionen werden auf lokale Titel übertragen.
- **Werkzeuge / Hilfe und Problembehebung / Wiedergabedaten verwalten**:
  ausgeblendete Titel wieder anzeigen, alle Positionen zurücksetzen,
  Gesehen-Status und Positionen zurücksetzen, lokalen Radioverlauf leeren.
  Umfassende Änderungen verlangen eine Bestätigung und eine lokale Sicherung
  der betreffenden Wiedergabedateien. Konten, Passwörter und Favoriten werden
  nicht gelöscht. Während Videos laufen, sind manuelle Verwaltungsaktionen
  gesperrt.
- Reset mit Nullposition, expliziter Markierung und neuer Sitzung über den
  bestehenden dauerhaften Sync-Ereignisspeicher; keine Löschung der Outbox.
  Verspätete Checkpoints alter Sitzungen unterliegen der vorhandenen
  Revisions-/Konfliktprüfung. Ein absichtlicher späterer Neustart kann wieder
  Fortschritt speichern. Fortschrittserfassung nach Ungesehen-Markierung
  funktioniert auch bei wiederholten Checkpoints.
- Der Player löscht keine Einträge mehr aus Kodis `MyVideos*.db` und ändert
  auch nicht mehr das Prozess-Arbeitsverzeichnis für diesen Zweck.

## Kodi-Bibliothek: Grenzen und Zuordnung

`library_state.py` verwendet ausschließlich Kodis JSON-RPC. Filme werden über
übereinstimmende IMDb-/TMDb-IDs verbunden; bei Folgen zuerst die Serie, dann
Staffel und Folge. Widersprüchliche IDs oder mehrere passende Bibliothekseinträge
werden nicht geraten. Eine Namensgleichheit genügt nicht. Status/Position werden
an passende Bibliothekseinträge übertragen. Die Service-Benachrichtigung
`VideoLibrary.OnUpdate` übernimmt Änderungen bekannter Filme/Folgen außerhalb
laufender Videowiedergaben. Eigene Änderungen erhalten einen Echo-Schutz;
Unbekanntes und fremde Medientypen werden ignoriert. Eine einzelne Folge darf
nicht den gesamten Serienstatus überschreiben. Beim Ungesehen-Setzen wird auch
`lastplayed` geleert, damit Kodi den Status nicht wieder auf gesehen setzt.

Kodi meldet seine allgemeinen Gesehen-Aktionen für reine Plugin-Einträge ohne
Bibliotheks-ID nicht zuverlässig an Add-ons. Dafür sind die expliziten
xVAULT-Aktionen überall vorhanden. Es wird keine universelle Übernahme aller
nativen Kontextbefehle beliebiger Add-ons behauptet.

Die reale lokale Kodi-Bibliothek enthält keine Filme/Serien. Tatsächliche
Bibliotheksabfragen und RPC-Schema wurden live geprüft; Schreib-/Importlogik
mit kontrollierten Identitäten und isolierten Wiedergabedaten. Ein vollständiger
Live-Abgleich mit vorhandenen echten Bibliothekseinträgen ist daher nicht als
durchgeführt ausgewiesen.

## Prüfung

- 74 gezielte Regressionstests für persönliche Funktionen, Staffel/Quellen-
  Cache, SerienStream, Quellenfehler, Movie2k2-Scope, Einstellungen, Playerstart,
  Sitzungszuordnung, Wiederaufnahme, Collections, Signature und Einschalten.
- 19 Integrationstests des unveränderten PHP-Sync-Protokolls mit dem echten
  Python-Client und temporären Profilen bestanden.
- 8 neue Tests für Verwaltungsaktionen, ID-Zuordnung, Native-RPC-Parameter und
  fünf Geräte bestanden: lokal ausgeblendete Titel bleiben auf anderen Geräten
  sichtbar; Position bleibt erhalten; Reset wird offline dauerhaft vorgemerkt,
  verteilt sich auf A–E, ein veralteter Checkpoint verliert als Konflikt, neue
  Sitzungen können wieder Fortschritt speichern; Favoriten/Auth bleiben erhalten.
- Live auf dem installierten **Kodi 22 RC1 / Windows x64**: 13 isolierte
  Prüfblöcke bestanden. Darunter echte Kodi-ListItems und Resume-Tags aller
  geänderten Ansichten, alle drei Hauptmenümodi, Kontextaktionen, Sammel-Reset
  einschließlich Abbrechen des Bestätigungsdialogs, Wiederanzeigen, Sicherung,
  Radioverlauf ohne Favoritenverlust sowie kontrollierte Native-Benachrichtigungen.
- Vollständiger echter xVAULT-Playerstart mit lokalem Testvideo, Sprung auf
  30 Sekunden, gespeichertem Checkpoint und anschließendem Stop bestanden.
  Beim ersten Versuch waren die Wartefunktion des Testgerüsts ausgeschaltet
  und die Sprungposition außerhalb des zweiminütigen Clips. Das Testgerüst
  wurde berichtigt und der vollständige Durchlauf wiederholt.
- Echter installierter Menüaufruf per Kodi-JSON-RPC: Hauptmenü ohne Vorschau,
  persönliches Menü ohne doppelte Vorschau, Weiterschauen und Verwaltung
  erfolgreich. Menüzeiten im privaten Nachweis festgehalten.
- Sämtliche geänderten Python-Dateien kompilieren, Einstellungs-XML gültig,
  `git diff --check` bestanden.

Ein **privates, nicht veröffentlichtes** signiertes Testpaket mit lokaler
Versionskennung `2026.11.17.2` wurde installiert. SHA-256-Dateibaum und
RSA-Signatur sind gültig; 187 Paketdateien. Die ursprüngliche Add-on-Installation
ist im privaten Testordner gesichert; das reguläre Benutzerprofil wurde nicht
durch ein Testprofil ersetzt. Alle Reset-/Lösch-/Sync-Tests verwenden isolierte
Daten bzw. den lokalen temporären PHP-Testserver, keinen produktiven Account.

Private Nachweise: `tools/diagnostics/private/2026-11-17/playback/` mit
`live-result.json`, `installed-menus.json`, `package-check-final.json` und
Testskript; Staffel-/Cache-Nachweise im benachbarten Ordner `daryl/`.

Im Kodi-Log sind daneben bereits bestehende Fehler des separaten Alpha-
Telemetriedienstes (Datenbankquota) sowie des automatischen OpenSubtitles-
Dienstes nach Testvideo-Stop zu sehen. Diese Dienste wurden für diese Aufgabe
nicht umkonfiguriert; sie sind kein erfolgreicher Bestandteil dieses Tests.

## Veröffentlichungsfreigabe

Nach Abschluss der lokalen Tests vom Nutzer als Nightly freigegeben. Veröffentlichung als
`2026.11.17.3`, damit auch der private lokale Testbuild `2026.11.17.2` ein
reguläres Versionsupdate erhält. Funktionaler Code unverändert zum geprüften
Testpaket. Release-Kanal bleibt `2026.11.17.1`.
