# xVAULT-Visuals

Eigenständiges natives Kodi-Musikvisualisierungs-Add-on, ID `visualization.xvault`.
Keine Abhängigkeit von Shadertoy, Spectrum oder Waveform.

## Sieben umschaltbare Modi (nativer Build 22.0.2)

| Modus | Darstellung und Musikreaktion |
| --- | --- |
| Pastelllinien | Drei weich auslaufende Frequenzlinien und feste himmelblaue Nulllinie; bisheriger Standard |
| Resonance | Geöffnete Tresorringe, rote Lichtpunkte und gravierter Schriftzug; Bass öffnet die Ringe, Höhen beleuchten die Kanten |
| Liquid Emblem | Flüssig verformter xVAULT-Schriftzug in einer dunklen metallischen Membran; alle drei Bänder bewegen Oberfläche und Reflexe |
| Klangarchiv | Perspektivische Konturschichten aus dem tatsächlichen Audioverlauf; 24 sichtbare Schichten zu je 250 ms |
| Lichtgewebe | Sich kreuzende Lichtfasern um den Schriftzug; Mitten spannen das Gewebe, Bass und Höhen bewegen die Fasern und Lichtimpulse |
| Eclipse | Dunkle Scheibe vor einem weichen Lichtring; Bass öffnet den Abstand, Mitten/Höhen verändern Lichtspalten und Randlicht |
| Gravity | Drei orbitale Lichtbahnen mit kleinen Leuchtkörpern; Bass und Impulse verändern die Ausdehnung, Höhen die Lichtpunkte |

Die Szenen nutzen den freigegebenen xVAULT-Schriftzug mit schrägem Neon-Radio aus `resources/radio-wordmark.png`.
Die neuen Modi werden unmittelbar in voller Bildschirmauflösung über den eigenen
HLSL-Renderer gezeichnet. Es gibt keinen Shader-Download und keinen fremden Renderer.

Umschalten über Kodis native Visualisierungs-Presetliste (im Vollbild Taste **P**)
oder den Visualisierungsbereich im Musik-OSD. Auswahl mit Fernbedienung bestätigen,
mit Zurück die Liste schließen. **V** öffnet die Einstellungen mit derselben Auswahl.
Auch Kodis Aktionen `NextPreset`, `PreviousPreset`, `RandomPreset` und `LockPreset`
werden unterstützt. Es gibt keinen automatischen Moduswechsel. Der zuletzt gewählte
Modus wird gespeichert und beim nächsten Audiostart wiederhergestellt.
Zwischen den sechs neuen Szenen wird weich übergeblendet.

## Audio und Pastelllinien

Bass (40–250 Hz) ist Rosé, Mitten (250–4000 Hz) Mint und Höhen (4000–16000 Hz)
Lavendel. Drei einzelne Hauptlinien mit sanftem Glow bewegen sich um eine feste,
himmelblaue Nulllinie. Biquad-Filter trennen das echte PCM-Audiosignal von Kodi;
RMS-Pegel, Attack/Release und zeitliche Glättung steuern die Amplituden.
Stille ergibt ruhige Linien. Keine Loopback-Aufnahme und kein externer Dienst.

Der Windows-Renderer zeichnet direkt über Kodis Direct3D-11-Kontext in dessen
voller Viewport-Auflösung. Kurven werden pro Bildschirmpixel abgetastet und als
geglättete Dreiecksbänder mit analytischer Kantenglättung gezeichnet. Kein
herunterskaliertes Bild und kein Hochskalieren einer Shader-Vorschau.
Der gemeinsam genutzte Kodi-Grafikzustand wird nach dem Zeichnen wiederhergestellt.
Die Frequenzlinien besitzen keinen scharfen Kern: ein kontinuierliches
Gauß-Helligkeitsprofil lässt sie breit und diffus nach außen auslaufen.
Dabei bleiben es drei einzelne Linien ohne versetzte Echos.

Der veröffentlichte Windows-Build unterstützt **Kodi 22 / API 5.0, Windows x86_64**.
Für Android/Fire TV ist seit Nightly 2026.10.29.3 zusätzlich **ARM32-Build 21.0.2 für Kodi 21 / API 4.0** veröffentlicht. Getestet auf AFTSSS (sheldonp), Fire OS 7.7.1.7 und Kodi 21.3. Der separate **ARM64-Build 21.0.2** ist lokal auf Samsung Galaxy Note20 5G (SM-N981B), Android 13, Mali-G77 und offiziellem Kodi 21.3 geprüft: alle sieben Modi in voller Auflösung (2308 × 1080) mit etwa 59–60 FPS, native Audiotests, automatische Erstinstallation, gespeicherter Modus über einen Kodi-Neustart sowie echter Radiostart mit Ein/Aus und Wiederherstellung der globalen Auswahl. Das ARM64-Paket wird mit Nightly 2026.10.30.2 veröffentlicht. Kodi 22 auf Android ist nicht unterstützt; die Windows-DLL darf dort nicht installiert werden.
Der Audiofilter ist plattformunabhängig. Das Windows-Paket `22.0.2` wird
mit Nightly `2026.10.29.3` im offiziellen xVAULT-Repository ausgeliefert.

## Lokaler Build

`python tools/build_visuals.py --toolchain <LLVM-MinGW-Ordner> --sdk <Kodi-Quellbaum> --output <privater Ausgabeordner>`

Verwendet werden LLVM-MinGW 20261020 (UCRT x86_64) und die Kodi-Header des lokal
installierten RC1-Commits `28ea2eac1eb7af8fdcbd2672d933ce87f594be79`.
Der Build führt vorab native Tests mit 18 Ton-/Samplerate-/Kanalkombinationen,
Stille, ungültigen Samples sowie Auswahl und zyklischen Grenzen der sieben Presets
durch. Er erzeugt ausschließlich ein lokales ZIP.
Quelle und entsprechende Lizenz liegen im Paket bei.

Das Video-Add-on enthält nur den optionalen Import und die Radio-Anbindung.
Native Quelltexte und plattformspezifische DLLs sind von dessen ZIP ausgeschlossen.

## Android / Fire OS (ARM32 und ARM64)

`python tools/build_visuals_android.py --ndk <Android-NDK-r27d> --sdk <Kodi-21.3-kodi-dev-kit-include> --output <privater-Ausgabeordner>`

Ohne weitere Angabe entsteht ARM32; `--arch arm64` baut ein getrenntes Paket für 64-Bit-Kodi auf Android. Für jede Architektur einen eigenen Ausgabeordner verwenden.

Der Builder prüft die Visualisierungs-API 4.0.0, baut eine passende ARMv7- oder AArch64-Shared-Library für Android API 21 und erstellt ein separates ZIP mit passenden Android-Abhängigkeiten, Lizenz und Quelltexten. Er ändert keine öffentlichen Feeds und veröffentlicht nichts. Die Shared-Library verwendet 16-KiB-Segmentausrichtung. Benötigt Python mit Pillow, die offiziellen Android-NDK-Windows-Werkzeuge und die Header aus dem Kodi-Tag `21.3-Omega`.

Der GLES-3-Renderer zeichnet die drei Pastelllinien in voller Bildschirmauflösung. Die sechs weiteren Szenen verwenden native Kurvengeometrie anstelle teurer Vollbild-Schleifen im Fragmentshader. Konturen, Frequenzreaktion, Audioverlauf, weicher Glow und gespeicherte native Preset-Auswahl bleiben erhalten; die mobilen Szenen sind an die GPU des Sticks angepasst. Die Wortmarke nutzt das freigegebene transparente Radio-Logo; beide Renderer verwenden dasselbe PNG. Übergänge zwischen den sechs Szenen werden überblendet.

Der gemeinsame Audiofilter und die Preset-Tests werden außerdem als Testprogramm in der gewählten Architektur gebaut und können über ADB direkt auf dem Gerät ausgeführt werden. Live-Smoke-Tests erfolgen getrennt mit lokal erzeugtem PCM-Ton und tatsächlicher Radiowiedergabe; dadurch ersetzen reine Bildratenmessungen nicht die Prüfung des Radio-Starts.

## Automatische Installation und Aktualisierung

Das Video-Add-on erkennt Betriebssystem, Prozessarchitektur und Kodi-Hauptversion. Kodi 22 / Windows x86_64 sowie Kodi 21 / Android ARM32 und ARM64 verwenden getrennte native Profile. Die Prozessarchitektur entscheidet auch bei einem 32-Bit-Kodi auf einem 64-Bit-Android-Kernel. Der ARM64-Index ist ab Nightly 2026.10.30.2 verfügbar. Kodi bekommt einen passenden zusätzlichen Repository-Index. Fehlende Pakete installiert Kodis normaler Add-on-Installer. Wenn kein passendes Paket erreichbar ist, bleibt Radio benutzbar; die optionale Installation meldet keinen Pflichtfehler.

Nach dem Nachladen von Python-Abhängigkeiten liest xVAULT deren von Kodi installierte Modulmanifeste und macht die dort deklarierten Bibliothekspfade auch im bereits laufenden Interpreter verfügbar. Dadurch kann der Radio-Monitor bei einer frischen Kodi-Installation ohne zusätzlichen Neustart starten. Kodis Installer bleibt für Installation und Aktivierung zuständig; Quelltexte werden nicht extern nachgeladen oder am Modulpfad vorbeigeladen.

Da Kodis `InstallAddon` bereits installierte Add-ons nicht aktualisiert, werden ältere Visuals-Pakete über einen separaten Paketwechsel aktualisiert: signierte Plattformreferenz, SHA-256, Größen- und ABI-Prüfung, Vorbereitung in einem Nebenordner, Sicherung und Rücksetzung bei Fehlern. Während einer Medienwiedergabe wird kein Austausch gestartet. Die persönlichen Visuals-Einstellungen bleiben erhalten. Sicherungen enthalten kein aktives `addon.xml`, damit Kodi sie nicht als zusätzliche Installation entdeckt.
