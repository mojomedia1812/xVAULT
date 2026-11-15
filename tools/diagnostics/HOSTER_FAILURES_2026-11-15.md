# Gelöschte und unerreichbare Quellen

## Live-Befund

Repräsentative Links aus dem Servicepaket vom 14.11.2026 mit begrenzten GET-Anfragen und unveränderter TLS-Prüfung geprüft:

- StreamTape und VOE: HTTP 404.
- UpStream: Zertifikatsprüfung fehlgeschlagen.
- SuperVideo: URL-/Namensauflösungsfehler.
- GoodStream: Zeitüberschreitung.
- Filemoon und Veev: HTTP 200 für die Webseite; dies bestätigt ausdrücklich keinen abspielbaren Stream.

Installiertes ResolveURL 5.1.213 entspricht bei der Prüfung dem offiziellen Repository `Gujal00/smrzips/master/addons.xml`. Ein pauschales Resolver-Update ist somit keine belegte Lösung. Private Ergebnisdatei: `private/2026-11-15/hoster-live.json`.

## Gefundener xVAULT-Fehler

Die bisherige Fehler-Sperre wurde nach Anbieter und Hoster gebildet. Ein gelöschter StreamTape-Upload konnte daher andere, funktionierende StreamTape-Videos desselben Anbieters für fünf Minuten verstecken. Außerdem löste der Resolver nach eindeutigen Lösch-/HTTP-/TLS-Fehlern denselben Link erneut mit Popup-Freigabe und weiteren Fallbacks auf.

## Korrektur

- Sperre nach SHA256 aus Anbieter und vollständigem ursprünglichen Link inklusive Query-/Header-Identität. Neue Sperren speichern weder URL noch Token oder rohe Fehlermeldung. Alte hosterweite Sperren verfallen bei der Normalisierung, maximal 500 aktuelle Link-Sperren.
- Fehler zentral klassifizieren: explizit gelöschte Datei 24 Stunden, 404/410 30 Minuten, bekannte vorübergehende HTTP-/TLS-/Netzwerkfehler fünf Minuten. Allgemeine Parserfehler werden nicht als Löschbestätigung behandelt.
- Eindeutige Fehler aus Provider und ResolveURL sofort durchreichen und einzeln merken; keine wiederholte Auflösung derselben Fehlermeldung mit denselben Resolvern.
- Gespeicherte Quellen, direkte Wiedergabe alter Quellenkontexte, Autoplay und automatische Ersatzquellen beachten die Sperren. Andere Uploads desselben Hosters bleiben nutzbar. Allgemeine Fehlerbehandlung verkürzt eine vorhandene Löschsperre nicht.
- Gleichzeitige Fehlermeldungen innerhalb des Prefetch-Prozesses werden serialisiert, damit sie einander nicht überschreiben.
- Kein Abschalten der Zertifikatsprüfung. Keine Vollprüfung aller gefundenen Links beim Menüaufbau; unbekannte tote Links können deshalb bis zum ersten Auflösungsversuch erscheinen. Entfernte Dateien lassen sich nicht wiederherstellen.

## Prüfung

84 gezielte automatische Tests bestanden, darunter Löschfehler nur einmal auflösen, HTTP/TLS/Netzwerk, Ablauf und Erneuerung, Query-Identität, Speicherung über Instanzen, alte hosterweite Sperren, parallele Meldungen, Ersatzquellen und funktionierende andere Uploads desselben Hosters. Bestehende Tests für Medien-GET/HTML-Erkennung, Filmidentität, Movie2k2, Serienstream, Suchzeitlimits, Collections, persönlichen Bereich und Updates ebenfalls erfolgreich.

Im lokalen Kodi 22 RC1 mit dem tatsächlich installierten ResolveURL 5.1.213 geprüft: Originaler StreamTape-Link aus dem Servicepaket liefert `deleted`; genau ein Resolverversuch, Wiederholung ohne neuen Resolveraufruf. Eine kontrollierte gültige Medien-URL unter demselben Anbieter-/Hoster-Namen wird weiterhin akzeptiert und über den echten HTTP-Medienprobe-Code geprüft. Das ist kein Nachweis, dass ein anderer StreamTape-Upload live abspielbar ist. Private Belege unter `private/2026-11-15/hoster-kodi-live.json`; temporäres QA-Add-on danach deaktiviert und entfernt.

Die bestehende xVAULT-Installation wurde nicht überschrieben; keine Wiedergabe auf dem Fire TV gestartet oder unterbrochen, keine Version erhöht und nichts veröffentlicht.
