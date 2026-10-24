# Originalstatus und Updatekanaele – lokaler Pruefstand

Unveroeffentlichter Kandidat: xVAULT **2026.10.24.1**, Repository **1.0.3**.
Es wurden weder GitHub noch Hosting, DNS oder die Statistikseite veraendert.

## Umsetzung

- Neue Repository-, Download-, Seiten- und Updateadressen verwenden `https://xvault.repowork.de/`.
- Ein signiertes Dateimanifest enthaelt die SHA-256-Werte des ausgelieferten Paketinhalts. Beim Start werden die installierten Dateien neu gehasht; geaenderte, fehlende und zusaetzliche Dateien werden erkannt. Der ZIP-Hash wird vor der Installation separat geprueft. Ein neu berechneter ZIP-Hash allein legitimiert keine veraenderte Kopie.
- Herkunftsstatus und KodiBox-Merkmale werden bei Start, Dienststart, Wiedergabe, Updates und Supportinformationen geprueft. Bekannte Android-Pakete und die lokal vorhandene Windows-KodiBox werden erkannt. Nur fuer den belegten APK-Fingerabdruck wird die Basisversion 2026.10.11.1 genannt. Unbekannte Referenzen oder Netzwerkausfaelle werden nicht als Faelschung bezeichnet.
- Release umfasst Tagesrevision `.1`, Nightly Revisionen ab `.2`. Die Pruefintervalle betragen sechs Stunden beziehungsweise eine Stunde; manuelle Pruefungen sind jederzeit moeglich. Kanalwahl und Originalstatus sind unter Werkzeuge erreichbar.
- Der eigene Updater arbeitet unabhaengig von Kodis globaler Updateeinstellung. Standard ist Benachrichtigung, optional werden Vorwaertsupdates im Leerlauf installiert. Kanalwechsel auf niedrigere Versionsnummern und Reparaturen erfordern eine ausdrueckliche Auswahl. Zukunftsversionen und wiederholte alte Katalogstaende werden geprueft.
- Signierte Pakete werden vor dem Austausch entpackt und erneut vollstaendig geprueft. Ein separater Helfer stoppt den Hintergrunddienst kooperativ, sichert den alten Stand und setzt bei Fehlern zurueck. Persoenliche Daten in `addon_data` bleiben ausserhalb des Pakettauschs. Zwei durch den Helfer markierte Sicherungen bleiben erhalten.
- Die allgemeinen MoFlix-Identitaetskorrekturen fuer Colony und die VIXSTREAM-Korrekturen fuer Wiedergabeheader, verschachtelte HLS-Listen und unbelegte Sprachangaben sind enthalten. Einzelheiten stehen in den beiden zugehoerigen Diagnoseberichten.

## Pruefverfahren

Die automatischen Tests decken Signatur- und Hashmanipulationen, fehlende und zusaetzliche Dateien, ZIP-Pfadmanipulationen, Kanaltrennung, Versionsplausibilitaet, HTTP-Abgleich, Rollback und die Synchronisation mit fuenf Geraeten ab. Der kooperative Dienststopp besitzt einen eigenen Test: Eine Freigabe erfolgt erst nach Ende der Netzwerk-Threads.

Die Live-Pruefung verwendet das installierte regulaere Windows-Kodi 22 RC1 und einen ausschliesslich lokal erreichbaren HTTP-Testserver mit echt signierten Paketen. Dieser Testzugang ist keine konfigurierbare Ausnahme fuer Produktionsserver. Geprueft werden Originalerkennung, manipulierte Kopie, bekannte KodiBox-Kopie, Download/Installation, Nightly `.9` und der bestaetigte Rueckwechsel auf Release `.1`. Ein nach der Vorbereitung manipuliertes Paket wird vor dem Austausch abgewiesen und die installierte Version bleibt erhalten.

Die bereits lokal vorhandene Windows-KodiBox wurde fuer die Herkunftserkennung geprueft; dort wurde kein xVAULT-Paket installiert. Rohlogs, private Testprofile, Paketsicherungen und der private Signierschluessel liegen ausschliesslich im ignorierten Verzeichnis `private/`.

## Abschliessende Ergebnisse

- Gesamtlauf: 100 Tests, 99 bestanden und ein MariaDB-spezifischer Test ausgelassen. Dieser Test mit fuenf unabhaengigen PHP-Prozessen wurde anschliessend gegen die lokale MariaDB separat ausgefuehrt und bestanden. Die 21 gezielten Update-/Signaturtests bestehen auch nach der letzten Korrektur am Dienststopp.
- Echter Paketwechsel im laufenden Kodi: Release `.1`, abgewiesenes manipuliertes Nightly-Paket, Nightly `.9`, zurueck auf Release `.1`. Alle vier Erwartungen erfuellt; bei den abschliessenden Paketwechseln keine erzwungene Dienstbeendigung und kein Python-Traceback.
- Alle 169 Paketdateien stimmen bytegenau mit der installierten Version ueberein. Die vollstaendige Signatur-/Integritaetspruefung meldet `original`; ZIP-CRC und Katalogsignaturen bestehen. Kein privater Schluessel und keine Testwerkzeuge sind im Add-on-Paket.
- Hauptmenue: zehn Eintraege, etwa 2,5 Sekunden je Aufruf; Werkzeuge: zehn Eintraege, etwa 1,7 Sekunden. Der neue Statusdialog wurde sichtbar im Kodi-Fenster kontrolliert und geschlossen. Die urspruengliche globale Kodi-Updateeinstellung ist wiederhergestellt.
- „Die Monkees“ S01E01 erneut ueber VIXSTREAM abgespielt: mehr als zehn Sekunden fortschreitende Wiedergabe, angebotene Sprache unbekannt, SD. Colony (2026) erneut ueber VIXSTREAM abgespielt: mehr als zehn Sekunden fortschreitende Wiedergabe, koreanischer Ton, H.264, Laufzeit etwa 122 Minuten. Beide Testplayer sind beendet.

## Grenzen vor einer Freigabe

Die Produktionsdomain antwortete anfangs mit Zeitueberschreitungen. Beim abschliessenden HTTPS-Abruf sind Startseite und `addons.xml` erreichbar (HTTP 200), der neue signierte Katalog `updates/release.json` fehlt noch (HTTP 404). Die vorbereiteten neuen Dateien und der Download ueber die Produktionsdomain koennen deshalb erst nach der genehmigten Bereitstellung abschliessend geprueft werden. Kein Ergebnis des lokalen Testservers wird als erfolgreicher Produktionsabruf ausgegeben.

Ein modifizierter Kodi-Host kann lokale Pruefungen entfernen oder deren Anzeige manipulieren. Signaturen sichern die Referenzen und unveraenderten Clients ab, schaffen aber keine nicht umgehbare Host-Attestierung. Die Anzeige benennt diesen Unterschied.

Der private Signierschluessel muss vor der ersten Veroeffentlichung separat gesichert werden; er gehoert weder ins Repository noch in das Add-on. Die erstellten ZIPs und Kanaldateien bleiben bis zur ausdruecklichen Freigabe lokal.

## Veroeffentlichungsfreigabe

Nach Abschluss der lokalen Pruefungen hat der Benutzer die Veroeffentlichung ausdruecklich genehmigt. Die Release-Kennzeichnung wurde aktualisiert und das Paket erneut signiert; Laufzeitcode und Einstellungen bleiben gegenueber dem geprueften Kandidaten unveraendert. Der private Signierschluessel ist zusaetzlich ausserhalb des Repositorys benutzergebunden verschluesselt gesichert.
