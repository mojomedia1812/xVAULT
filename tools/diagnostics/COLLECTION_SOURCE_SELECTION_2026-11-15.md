# Collections: Wiedergabefehler vor der Quellenauswahl

## Befund

Servicepaket vom 14.11.2026, xVAULT 2026.11.07.2. Beim Aufruf von `collectionPlay` für „Alien – Das unheimliche Wesen aus einer fremden Welt“ protokolliert Kodi sowohl im aktuellen als auch im vorherigen Log `Playlist Player: skipping unplayable item` und `Attempt to set unplayable index 0`.

`collections._movies_directory()` markiert jeden Film als `IsPlayable=true`, obwohl `collections.play()` abhängig von der globalen Standardaktion zunächst eine Quellenliste öffnet. Kodi startet dadurch bereits beim Filmklick seinen Playback-Resolver. Der Quellenlistenwechsel liefert diesem keinen Videostream zurück und erzeugt den Wiedergabefehler. Normale Film-Suchergebnisse setzen diese vorzeitige Kennzeichnung nicht.

Zusätzlich enthält das Paket Fehler gelöschter oder unerreichbarer Hoster sowie einen Fehler von `script.ezmaintenanceplus`. Diese sind von der hier behobenen Kodi-Aufrufart zu unterscheiden. Der Fix repariert keine gelöschten Videodateien.

## Korrektur

Vorzeitige `IsPlayable`-Kennzeichnung des Collection-Films entfernt; derselbe Action-Aufruf wie bei normalen Film-Suchergebnissen. Metadatenübergabe und globale Auswahl Verzeichnis/Dialog/Autoplay bleiben unverändert. Die einzelnen Einträge der Quellenliste bleiben `IsPlayable=true`.

## Prüfungen

- 76 gezielte Unit-/Regressionstests bestanden: Collection-Einträge und Metadatenübergabe, Verzeichnis ohne Resolver-/Playerstart, Dialog und Autoplay, Suchzeitlimits, Filmidentität, Movie2k2-Medienscope, Streamvalidierung, Provider-Begrenzung, persönlicher Bereich, Serienstream und Updates.
- Echte lokale Kodi-22-RC1-Instanz: isoliertes temporäres QA-Plugin rendert Collection-Film mit dem produktiven Collection-Code. Nur Metadaten und Anbieterergebnisse sind Testdaten; `sources.play` und die Darstellung der Quellenliste laufen im Kodi-Prozess. Kein externer Hoster wird abgespielt.
- Vorher: mit alter `IsPlayable=true`-Kennzeichnung beim echten Filmklick `Error resolving item` / `skipping unplayable item` reproduziert.
- Nachher: Film-Eintrag ohne Playback-Kennzeichnung öffnet die Quellenliste (`action=addItem`, ein Testeintrag), kein aktiver Player und keine entsprechenden neuen Playback-Fehler. Einzelne Quelle zeigt weiterhin `IsPlayable=true`.
- Private Belege und wiederverwendbarer QA-Code unter `tools/diagnostics/private/2026-11-15/`. Temporäres Add-on nach Prüfung deaktiviert und entfernt. Bestehende xVAULT-Installation nicht überschrieben; keine Veröffentlichung oder Versionsänderung.
