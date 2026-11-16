# Automatische Wiederaufnahme – unveröffentlichter Entwicklungsstand

## Verhalten

- Quelle aus Dialog, Quellenverzeichnis, Autoplay oder Ersatzquellenwahl bleibt als ursprünglicher Anbieter-/Hosterlink ausschließlich im Speicher der Sitzung. Kein erneuter Suchlauf, kein Übernehmen einer alten CDN-URL aus dem Quellen-Cache, kein Wechsel von Sprache oder Upload.
- Reaktion auf Wiedergabefehler, vorzeitiges EOF und 90 Sekunden Stillstand ohne Pause. Bekannte positive Dauer und mindestens eine Sekunde Fortschritt erforderlich; Live-Streams ausgenommen. Konservativer Endbereich: letzte zehn Sekunden oder zwei Prozent nicht neu starten.
- Höchstens zwei Wiederherstellungen je Sitzung; maximal 20 Sekunden Auflösung und 45 Sekunden Startbestätigung pro Versuch. Abbrechbarer Kodi-Dialog. Späte Antworten abgebrochener Auflösungen können keine Wiedergabe auslösen.
- Derselbe Player-Zustand einschließlich Sync-Sitzung, Wiedergabename, Watch-Status und Navigation bleibt erhalten. Interne Stopps beim Neustart finalisieren die Sitzung nicht. Vorzeitiges EOF wird nicht vor der Wiederherstellung als reguläres Ende verbucht. Nach einem Fehler während bereits gestarteter Wiedergabe kein automatischer Wechsel zu einem anderen Upload durch die Quellen-Fallbacks.
- Gemeinsame ListItem-Erstellung bewahrt InputStream-/Manifest-/AES-Header. Beim Ersatzstream wird Kodis `StartOffset` genutzt, anschließend die tatsächlich gemeldete Position geprüft. Dokumentation: https://xbmc.github.io/docs.kodi.tv/master/kodi-base/d8/d29/group__python__xbmcgui__listitem.html
- Unter Wiedergabe standardmäßig aktiviert und abschaltbar. Nach vergeblichen Versuchen verständlicher Hinweis; die letzte bekannte Position wird zur bestehenden Abschluss-/Speicherlogik zurückgegeben.

## Tests

107 gezielte automatische Tests erfolgreich: Recovery-Policy, Stop/Abbrechen, neue fremde Wiedergabe, Sitzungsbudget, verspätete Resolverantworten, nicht fortsetzbare Ersatzstreams, ursprünglicher Link statt CDN-Cache und native StartOffset-Eigenschaft auch bei positivem Pluginhandle. Bestehende Tests zu Sources, Collections, Hosterfehlern, Filmidentität, Suchzeitlimits, Serienstream, Updates, persönlichem Bereich und VIXSTREAM bestehen.

Kontrollierter Testserver mit selbst erzeugtem H.264/AAC-MP4 und Range-Unterstützung. Erste Medienadresse liefert absichtlich eine unvollständige Datei und danach HTTP 503. Erneuter Abruf des ursprünglichen Resolver-Endpunkts liefert eine neue Token-Adresse zur vollständigen Datei. Genuine Quellenauflösung, Recovery-Schleife und Kodi-Player laufen auf dem jeweiligen Gerät. Nur Anbieter, Metadaten, Sync-/Trakt-Seiteneffekte und abschließende Persistenz sind für den Test isoliert. Der Stillstandswert ist ausschließlich im QA-Prozess auf acht Sekunden verkürzt; die geprüften Abbrüche wurden als vorzeitiges EOF erkannt.

| Gerät / Test | Ergebnis |
| --- | --- |
| Windows, Kodi 22 RC1, unterbrochener Stream | Letzte Position 2,918 s; neue Adresse, Fortsetzung bei 2,912 s, danach weiterlaufend. Ein Recovery-Versuch. |
| Amazon AFTSSS, Kodi 21.3, unterbrochener Stream | Letzte Position 2,819 s; neue Adresse, Fortsetzung bei 2,510 s, danach weiterlaufend. Ein Recovery-Versuch. Geringe Abweichung durch native Decoder-/Keyframe-Position. |
| Windows, normaler Stop | Keine Recovery, nur eine Quellenauflösung. |
| Fire TV, normaler Stop | Keine Recovery, nur eine Quellenauflösung. |
| Windows, reguläres Ende einer 12-s-Datei | Reguläres Ende erkannt, keine Recovery, nur eine Quellenauflösung. |

Erster Live-Durchlauf zeigte, dass Kodi den neuen Player bereits vor dem abgeschlossenen Positionswechsel als aktiv melden kann. Zusätzliche AV-Callback-Abhängigkeit war auf Kodi 21 nicht zuverlässig genug; native StartOffset-Vorgabe und Prüfung der tatsächlichen Position beheben dies. Finalen Stand auf beiden Geräten erneut geprüft.

Private Belege und ausführbare QA-Skripte: `private/2026-11-15/recovery/`, insbesondere `local3broken-result.json`, `fire2broken-result.json`, `localstable-result.json`, `firestable-result.json` und `localnatural-result.json`. Dies ist kein Langzeittest fremder CDN-Server und kein Live-Test von HLS/DASH-Wiederaufnahme.

Test mit temporärem separatem QA-Add-on, keine Überschreibung der installierten xVAULT-Originalpakete. Fire-TV-Unterbrechung vorher ausdrücklich erlaubt. Test-Add-ons und Portweiterleitung nach Abschluss entfernen. Keine Versionsänderung, kein Paketbau, kein Git-Push und keine Veröffentlichung.
