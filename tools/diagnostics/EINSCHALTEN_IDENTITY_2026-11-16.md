# Einschalten: Filmidentität – unveröffentlichte Korrektur

## Ursache

Aktueller und Legacy-Scraper prüften das Suchergebnis, gaben aber keine `movie_identity` weiter. Die zentrale Prüfung konnte deshalb korrekte Quellen nur als `unknown` behandeln. Zusätzlich wurde der Titel vor dem ersten Bindestrich abgeschnitten, wodurch ein gemeinsamer Titelanfang als Auswahlkriterium genügte.

## Änderung

- Filmkarten über vollständigen normalisierten Titel und Erscheinungsjahr mit der vorhandenen zentralen Prüfung abgleichen. Gültige Staffel-/Episodenaufrufe einschließlich Specials nicht als Film deklarieren.
- Beobachtete Anbieterkarte an den tatsächlich ausgewählten Link binden, primäre Detailseiten-Metadaten mit `movie_identity.from_html` berücksichtigen, inklusive einer dort vorhandenen IMDb-ID. Konflikte vor dem Abruf des Watch-Endpunkts verwerfen. Bei fehlerhafter erster Detailseite weitere passende Kandidaten berücksichtigen.
- Wenn die Detailseite nicht erreichbar ist, nur den Titel und das Jahr aus der zuvor geprüften Anbieterkarte verwenden; niemals Suchparameter zu vermeintlichen Anbieternachweisen umdeklarieren.
- Identitätsdaten am Stream an die zentrale Prüfung weiterreichen. Deren Regeln, Autoplay-Schutz und manuelle Bestätigung unbekannter Quellen bleiben erhalten. Nach erster nutzbarer Quelle stoppen; fehlende oder gesperrte Streams lassen weitere passende Kandidaten zu.
- Pro Aufruf frische Ergebnisliste, deterministische Suchreihenfolge, kodierte Suchbegriffe und keine API-Rohantwort mit möglichen Streamtokens im Fehlerlog.
- Beide Scraper-Varianten geändert. Für Veröffentlichungen enthält der Quellencache bereits die Add-on-Version im Schlüssel; neue Versionen übernehmen deshalb keine alten unbekannten Quellen aus dem vorherigen Build.

## Tests und echte Kodi-Abfrage

122 gezielte Regressionstests bestanden, darunter sieben neue Testmethoden mit beiden Scraper-Varianten: Alien mit Titel/Jahr bestätigt, Präfixkollision und Remake-Jahr abgewiesen, falsches Detailjahr/IMDb-ID vor Watch-Abruf ausgeschlossen, Detailseiten-Ausfall, alternativer Kandidat, Wiederholungen/Specials und URL-Kodierung.

Im lokal installierten Kodi 22 RC1 mit echtem Netzwerkabruf von einschalten.in und dem produktiven Quellenkollektor geprüft:

- „Alien – Das unheimliche Wesen aus einer fremden Welt“, Jahr 1979, angefragte IMDb-ID tt0078748.
- Eine echte Quelle gefunden; beobachteter vollständiger deutscher Titel und Jahr 1979 an den zentralen Kollektor übergeben. Anbieter-Metadaten liefern hierbei keine IMDb-ID; Titel und Jahr genügen gemäß bestehender Regel für `verified`.
- Produktive `_confirmMovieSource` akzeptiert die Quelle ohne Warn-/Bestätigungsdialog.
- Keine Wiedergabe der Filmdatei gestartet; dies ist ein Live-Test der Suche/Identitätsprüfung, keine Garantie für den Inhalt eines fremden Uploads.

Die Website-Gegenprobe zeigt denselben Titel und dasselbe Jahr. Der Watch-Endpunkt liefert nur `releaseName` und `streamUrl`; die Identität wird deshalb nicht aus dem angefragten Film oder allein einem Release-Dateinamen abgeleitet.

Private Rohdaten und Kodi-Ergebnis: `private/2026-11-16/einschalten/`, insbesondere `kodi-live.json`. Test in separatem temporärem QA-Add-on; Originalinstallation nicht überschrieben, keine Profil-/Kontoeinstellungen geändert, keine Veröffentlichung und keine Aktualisierung des Fire-TV-Testbuilds.
