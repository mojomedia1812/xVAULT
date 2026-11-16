# Direkter Wechsel zwischen laufenden Wiedergaben

Hellraiser1 meldet, dass nach einem Wechsel ohne vorheriges Stoppen das neue Video abbricht und alte Inhalte erneut starten. Ohne sein Servicepaket lässt sich der konkrete Ablauf nicht abschließend belegen. Im Player wurde jedoch ein passender, reproduzierbarer Fehler gefunden.

## Ursache

Kodi meldet Player-Ereignisse auch an noch lebende ältere Python-Player. Der bisherige `onAVStarted` übernahm ohne Sitzungsprüfung die aktuell laufende Datei und wendete den alten Fortsetzungswert darauf an. Im isolierten Vorher-Test führte der Callback des alten Players zu `seekTime(600.0)` auf dem neuen Video. Auch Fortschrittsüberwachung und verzögerte Navigation waren nicht durchgängig einer Sitzung zugeordnet. Automatische Wiederaufnahme kann einen solchen Konflikt verschärfen.

Die Einstellung `status.position` beeinflusst die Positionierung in der Serienliste. Sie ist damit kein Beleg für eine automatische Wiedergabe der nächsten Folge als Ursache dieses Fehlers.

## Änderung

- Geräteweit über Kodis Home-Window-Properties koordinierte, zufällige Sitzungstokens: Eine neue vorbereitete Wiedergabe übernimmt beim Öffnen die Zuständigkeit. Eine inzwischen überholte Vorbereitung darf sie nicht zurückholen.
- Abgelöste Player behalten ihren zuletzt erfassten Fortschritt und dürfen keine neue Wiedergabe steuern, wiederaufnehmen oder deren Container verändern. Auch identische Stream-Adressen bleiben unterschiedliche Sitzungen.
- Während Kodi das neue Video asynchron öffnet, gelten Ereignisse des noch sichtbaren alten Videos nicht als Start oder Ende des neuen Players.
- Andere Add-ons werden nach dem Start anhand einer abweichenden Mediendatei erkannt. Die Prüfung benötigt keine neue Nutzeroption.

## Prüfung

19 gezielte Tests für Sitzungszuordnung und Wiederaufnahme bestanden. Darunter verspätete AV-/Stop-/End-/Fehlerereignisse, identische URLs, fremde Wiedergaben, veraltete Startabsichten, getrennte Fortschrittswerte und deaktivierte/aktivierte Listenpositionierung.

Live im lokal installierten Kodi mit isoliertem QA-Add-on und synthetischen HTTP-Testvideos geprüft: A bei rund 43 Sekunden laufend durch B ersetzen, ohne A vorher zu stoppen; anschließend verspätete Ereignisse von A auslösen. B lief von rund 0,8 bis 6,8 Sekunden kontinuierlich weiter und behielt die Sitzungszuständigkeit. A wurde abgelöst, sein Fortschritt blieb rund 43 Sekunden; kein alter Resolver und keine alte Navigation wurden gestartet. Der erste Live-Durchlauf deckte zusätzlich das asynchrone Öffnungsfenster auf; dieser Befund wurde korrigiert und der Durchlauf wiederholt.

Zusätzlicher Live-Regressionstest: Einen HTTP-Teststream gezielt nach rund drei Sekunden abbrechen. Dieselbe Quelle wurde genau einmal frisch aufgelöst und bei 2,923 Sekunden statt erneut bei null gestartet; anschließend lief sie bis zum bewussten Test-Stopp weiter. Das deaktivierte QA-Add-on wurde danach aus dem Kodi-Add-on-Verzeichnis archiviert und der lokale Testserver beendet.

66 gezielte Regressionstests für Wiedergabe, Collections, Signature, Filmidentität und Quellenfehler bestanden. Ein zusätzlich gestarteter Gesamtdurchlauf wurde nach mehreren Minuten ohne Ergebnis abgebrochen und zählt nicht als bestanden.

Private Testdaten liegen unter `tools/diagnostics/private/2026-11-16/ownership/`. Das installierte reguläre xVAULT wurde dabei nicht überschrieben. Nach ausdrücklicher Freigabe des Nutzers als Nightly 2026.11.16.3 zur Veröffentlichung vorbereitet. Stabile Version 2026.11.01.1 bleibt unverändert.
