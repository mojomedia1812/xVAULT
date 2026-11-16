# Signature – unveröffentlicht

Nutzervideo `xVAULT_Cinematic_8s_1080p.mp4` unverändert als `resources/media/signature.mp4` übernommen. 8,00 Sekunden, 1920×1080, 60 fps, H.264 High / yuv420p und AAC-LC Stereo. SHA256-Gleichheit mit der Quelldatei geprüft.

Boolean `signature.enabled`, Beschriftung **Signature**, standardmäßig true, in der bestehenden Schnellstart-Kategorie. Erreichbar über Werkzeuge > Einstellungen > xVAULT-Einstellungen > Schnellstart.

Aufruf nur im Hauptstartzweig nach Aufbau des Navigationsmenüs. Wiedergabe mit eigenem schlankem Kodi-Player ohne Quellenauflösung, Sync, Wiederaufnahmelogik oder Bibliothekseintrag. Stop/Ende/Fehler geben den Startablauf frei; maximal 25 Sekunden Wartezeit. Existierende Medien werden nicht ersetzt, Hintergrund-Verzeichnisabfragen außerhalb des Medienfensters spielen nichts ab. Fenster-Eigenschaften schützen vor Doppelstart und erneuter Wiedergabe beim Zurückgehen. Ein Service-Monitor prüft die Navigation ohne Netzverkehr alle 0,5 Sekunden und gibt nach dem Verlassen des Add-ons einen neuen Einstieg frei. Vollbildwiedergabe innerhalb xVAULTs zählt nicht als Verlassen.

## Lokaler Live-Test

Kodi 22 RC1, temporäres separates QA-Add-on, echter Produktionscode für Signature und Original-Videodatei. Bestehendes xVAULT-Originalpaket nicht überschrieben; QA-Schalter nur im Testprozess gesetzt.

- Aktiv: Video einschließlich Ton vollständig abgespielt, reguläres Ende. Gesamter Start-/Wiedergabeaufruf 9,84 Sekunden einschließlich Decoderstart. Zweiter Aufruf im gleichen Besuch übersprungen; danach Videos-Menü wieder aktiv, kein laufender Player.
- Deaktiviert: kein Video, Rückkehr praktisch sofort, auch wiederholter Aufruf bleibt ohne Wiedergabe.
- Erste Prüfung identifizierte eine lokale Wechselwirkung mit SubsMangler: automatische Untertitelsuche pausierte den Clip. Eine ausschließlich für diese Datei geltende `signature.noautosubs` behebt dies; SubsMangler bestätigt im Log die unterdrückte Suche. Keine globale Dienst-/Untertitel-Einstellung geändert.
- Sieben Signature-Regressionsprüfungen für Schalter, Besuchswechsel, Zurück-Navigation, vorhandene Medien, Hintergrundabfragen, Vollbild und Fehlerbereinigung bestanden. Zusammen mit der vorhandenen gezielten Suite 114 Tests erfolgreich.

Private Laufbelege unter `private/2026-11-15/signature/`. Temporäres QA-Add-on deaktiviert und aus Kodi entfernt. Stream-Wiederaufnahme bleibt erhalten. Keine öffentliche Versionsänderung oder Veröffentlichung.

## Installation auf dem Fire TV

Auf ausdrücklichen Folgeauftrag signierten lokalen Testbuild **2026.11.15.3** auf dem Amazon AFTSSS / Kodi 21.3 installiert. Originalpaket 2026.11.15.2 gesichert, Profildaten nicht ersetzt, alle 185 installierten Dateien per SHA256 geprüft. Build und Nachweise unter `private/2026-11-15/firetv-install/`. Öffentliche Feeds und GitHub bleiben auf 2026.11.15.2. Für eine spätere Veröffentlichung eine neue Revision verwenden, da die private .3 bereits auf diesem Gerät existiert.

Der reale Add-on-Start zeigte einen zusätzlichen Kodi-Übergang: nach dem Clip leert Kodi vorübergehend den Container während des Menüaufbaus. Der Navigationsmonitor ignoriert jetzt Busy-/Updating-/Vollbild-Übergänge, damit das Intro nicht versehentlich erneut freigegeben wird. Regression ergänzt, **115 gezielte Tests bestanden**. Auf dem korrigierten Fire-TV-Build genau ein Signature-Start im Log, anschließend Hauptmenü mit 16 Einträgen und erhaltenem Session-Marker. Zurück-Navigation ohne weitere Signature-Wiedergabe; Werkzeuge und Einstellungs-Untermenü zusätzlich über Kodi geprüft.
