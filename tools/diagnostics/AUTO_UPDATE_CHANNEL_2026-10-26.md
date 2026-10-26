# Automatisches Update beim Kanalwechsel

## Befund

Das lokale regulaere Windows-Kodi hatte xVAULT 2026.10.24.1 installiert. Die Einstellungen waren korrekt: eigener Updater aktiviert, Kanal `nightly`, Modus automatisch. Der oeffentliche signierte Katalog lieferte 2026.10.26.2 ohne Netzwerkfehler.

`update_plan()` stufte jedoch jeden Unterschied zwischen dem Kanal der installierten Versionsnummer und dem ausgewaehlten Kanal als `switch` ein. So wurde auch die hoehere Nightly-Version als „Kanal-Rueckwechsel“ gemeldet. Der Hintergrundmonitor installiert automatisch ausschliesslich `update` und liess das Paket deshalb liegen.

Nach einer Installation konnte zudem die fuer die alte Version gespeicherte Updateentscheidung bis zum Ablauf des Pruefintervalls erhalten bleiben. Das konnte zu einem weiteren, anschliessend durch die Installationspruefung abgewiesenen Installationsversuch fuehren.

## Lokale Korrektur

- Der Versionsvergleich entscheidet ueber Vorwaertsupdate und Rueckwechsel. Ein hoeherer Stand im bewusst ausgewaehlten Kanal ist ein Vorwaertsupdate; eine niedrigere Version bleibt bestaetigungspflichtig.
- Der gespeicherte Pruefstand enthaelt die installierte Version. Eine Entscheidung fuer eine andere installierte Version wird auch innerhalb des normalen Intervalls neu geprueft.
- Die Schutzregeln fuer Reparaturen, unplausible Versionsnummern, Paketpruefung und Leerlauf bleiben erhalten.

## Verifikation

24 gezielte Tests bestehen. Drei neue Regressionstests pruefen hoehere Versionen beim Kanalwechsel, niedrigere Versionen im selben Kanal und den automatischen Monitor mit `explicit=False`. Der bestehende HTTP-Test prueft zusaetzlich, dass nach einem Versionswechsel der Cache neu abgeglichen wird.

Fuer den Live-Test wurde ausschliesslich die korrigierte Planfunktion in einem separaten lokalen Kodi-Testskript im Arbeitsspeicher geladen. Die installierten Programmdateien wurden dabei nicht dauerhaft gepatcht; die kurzzeitig verwendete Diagnose-Startdatei wurde vor Ausfuehrung des Tests wiederhergestellt. Die normale automatische Schleife verwendete die wirklichen Benutzereinstellungen, die unveraenderte Leerlaufpruefung und die oeffentlichen HTTPS-Kataloge. Es gab keinen direkten manuellen Installationsaufruf und keine Freigabe mit `explicit=True`.

Der Monitor startete die Installation bei mehr als 300 Sekunden Leerlauf mit `explicit=False`. Das oeffentliche signierte Paket 2026.10.26.2 wurde erfolgreich installiert. Anschliessend wurden der aktuelle Katalog erneut abgeglichen, `repository_match=True`, Originalstatus und der aktivierte Add-on-Status bestaetigt. Es lief keine Wiedergabe. Der Hauptmenue-Aufruf besteht ebenfalls.

Die Installation entspricht dem unveraenderten oeffentlichen Nightly-Paket. Die hier beschriebenen Quellcodekorrekturen sind noch nicht in diesem Paket enthalten und wurden nicht veroeffentlicht. Sie sind fuer die naechste Version vorbereitet. Private Rohdaten und Testskripte liegen unter `private/2026-10-26/update-auto/`.

## Freigabe als Nightly 2026.10.26.3

Die Korrekturen wurden fuer Nightly 2026.10.26.3 zur Veroeffentlichung freigegeben. 24 Update-/Signaturtests und 12 VIXSTREAM-Tests bestehen. Das neue signierte Paket enthaelt auch die vorbereitete Entfernung des Attestierungshinweises. Der Release-Katalog, dessen Kodi-Metadaten und das stabile Paket 2026.10.24.1 bleiben bytegleich erhalten.
