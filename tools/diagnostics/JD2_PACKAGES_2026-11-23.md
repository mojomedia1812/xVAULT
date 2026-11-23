# JDownloader 2: Paketnamen und Zielordner

Nightly 2026.11.23.2 behebt verlorene Film-/Episodenmetadaten zwischen
Quellenkontextmenü und lokalem JD2-Handler. Der vorhandene Kontexttoken
transportiert Metadaten; alte Kontextmenüs erhalten den formatierten Namen
als Rückfall. Paketnamen bestehen aus Titel und bekanntem Jahr bzw. SxxExx
(einschließlich Staffel 00) sowie bekannter Qualität. Fehlendes wird nicht erfunden.

Das bestehende UTF-8-Formular /flash/add erhält package und bei gesetztem
jd2_directory zusätzlich dir. Der optionale Textpfad gilt auf dem JD2-Rechner,
nicht zwingend auf dem Kodi-/LibreELEC-Gerät. Leer bleibt die JD2-Vorgabe.
Die Wahl von jd_url, Roh-URL und Referer bleibt erhalten. Andere Download-
Manager und interne Downloads erhalten keine neue Funktionalität.

Paketnamen gruppieren Links. Keine pauschale Umbenennung: Das Handbuch
beschreibt eine optionale, gezielt auf kryptische Dateinamen begrenzte
JD2-Paketverwalter-Regel. Lesbare Originalnamen sollen erhalten bleiben.

40 Tests bestanden, davon sieben neue JD2-Testmethoden mit Falltabellen,
echtem HTTP-POST an einen isolierten lokalen Testserver, UTF-8/Sonderzeichen,
Film/Jahr, Episoden/Specials, unbekannter Qualität, Zielordner gesetzt/leer,
URL-/Referer-Auswahl sowie JD1-/MyJD-/PyLoad-Regressionsprüfungen.
Weitere Tests decken Quellenkontext, Serienumfang, Einstellungen und
Release-/Updateprüfung ab. Kein echter JD2-/LibreELEC-Livetest durch uns;
die gemeldeten erfolgreichen Umbenennungstests sind Nutzerberichte.

Signatur, sämtliche Paketdateihashes, Katalog und XML-Prüfsummen vor und nach
Veröffentlichung prüfen. Stabiler Release 2026.11.18.1 unverändert erhalten.
Private Prüfnachweise: tools/diagnostics/private/2026-11-23/nightly-jd2/.
