# Fire TV Stick Simulator

Dieser Simulator bildet Android-basierte Fire-OS-Profile fuer Fire-TV-Stick-Varianten ab. Er ist kein FireOS-ROM-Emulator und enthaelt keine Amazon-Firmware, keine DRM-Komponenten und keine proprietaeren Amazon-Dienste. Vega OS ist bewusst nicht enthalten.

Ziel ist ein schnelles Kompatibilitaetslabor fuer xVAULT:

- Fire-TV-Stick-Profil auswaehlen
- Fire OS, Android-Version, API-Level, Build-Model, RAM, Storage, ABI und Codec-Klasse sehen
- xVAULTs `addon.xml` gegen die wichtigsten Fire-TV-Risiken pruefen
- simulierte Android-Systemwerte als `getprop`-aehnliche Ausgabe, JSON oder Windows-Env-Werte exportieren
- Android-TV-AVD-Testprofil nach dem Amazon-AVD-Vorgehen planen

## Nutzung

Alle Befehle werden aus dem Repository-Root ausgefuehrt.

```powershell
python tools/firetv_stick_simulator.py list
python tools/firetv_stick_simulator.py show fire-tv-stick-4k-max-2nd-gen-2023
python tools/firetv_stick_simulator.py check fire-tv-stick-2nd-gen-2016
python tools/firetv_stick_simulator.py matrix
python tools/firetv_stick_simulator.py properties aftkm --format json
python tools/firetv_stick_simulator.py avd-plan aftkrt
```

Fuer Tests von Kodi mit installiertem xVAULT gibt es zusaetzlich den Kodi-Simulator. Der Standard ist bewusst `aftmm`, also Fire TV Stick 4K - 1st Gen (2018), weil dieses Profil mit Fire OS 6 / API 25, 1.5 GB RAM und 8 GB Storage eine kritische Grenze bildet.

```powershell
python tools/kodi_firetv_test.py limits --profile aftmm
python tools/kodi_firetv_test.py smoke --profile aftmm --action root
python tools/kodi_firetv_test.py db-stress --profile aftmm
python tools/kodi_firetv_test.py all --profile aftmm --keep-profile
```

Der Kodi-Simulator stubbt die wichtigsten Kodi-Python-Module (`xbmc`, `xbmcaddon`, `xbmcgui`, `xbmcplugin`, `xbmcvfs`) und startet xVAULT gegen ein temporaeres Profil. Der DB-Stresslauf prueft lokale Pickle-Speicher und `playcount.db` auf Konsistenz nach vielen Schreibvorgaengen, simuliert volle-Speicher-Fehler und fuehrt `PRAGMA integrity_check` fuer SQLite aus.

Profile koennen ueber ID, Alias oder Build-Model ausgewaehlt werden. Beispiele:

- `aftkrt` fuer Fire TV Stick 4K Max - 2nd Gen (2023)
- `aftkm` fuer Fire TV Stick 4K - 2nd Gen (2023)
- `aftss` fuer Fire TV Stick Lite / HD-Klasse
- `aftt` fuer Fire TV Stick 2nd Gen / Basic Edition

## Umfang

Enthalten sind Android-basierte Fire-TV-Stick-Varianten mit Fire OS 5, 6, 7 und 8. Fuer xVAULT sind besonders diese Grenzen interessant:

- Fire OS 8 / Android 11 / API 30: aktuelles Android-basiertes Ziel
- Fire OS 7 / Android 9 / API 28: breite 1080p- und 4K-Basis
- Fire OS 6 / Android 7.1 / API 25: Legacy-4K-Basis
- Fire OS 5 / Android 5.1 / API 22: sehr altes Ziel mit hohem Kodi-Risiko

## Grenzen

Der Simulator startet kein echtes Fire OS. Er simuliert Profile und Kompatibilitaetsrisiken, aber nicht:

- Amazon Launcher, Appstore, Alexa, DRM oder Widevine-Verhalten
- echte Android-Medienpipeline
- echte Fernbedienungs-Events
- Kodi selbst
- sideloading oder Geraete-Firmware

Fuer echte Laufzeittests bleibt ein physischer Fire TV Stick oder ein Android-Emulator mit vergleichbarem API-Level noetig. Der Android-Emulator kann Fire OS aber nicht vollstaendig ersetzen, weil Fire-TV-spezifische Amazon-Dienste und Fire-TV-UI fehlen.

## Android-TV-AVD nach Amazon-Vorbild

Amazon beschreibt fuer Fire Tablets einen Weg ueber den Android Virtual Device Manager: Hardwareprofil anlegen, Speicher und Display passend setzen, danach ein virtuelles Android-Geraet erzeugen. Die Amazon-Seite sagt ausdruecklich, dass diese Schritte Fire TV nicht simulieren koennen. Fuer xVAULT ist der Ansatz trotzdem nuetzlich, wenn er als Android-TV-Naeherung verstanden wird.

Das Tool erzeugt mit `avd-plan` eine Checkliste fuer Android Studio:

- Device Type: TV
- Screen: 1080p oder 4K passend zur Stick-Klasse
- Memory: RAM des Fire-TV-Stick-Profils
- Input: Remote/D-Pad statt Touch
- Sensors und Cameras: aus
- System image: Android TV mit dem naechsten passenden API-Level

Beispiel:

```powershell
python tools/firetv_stick_simulator.py avd-plan fire-tv-stick-4k-2nd-gen-2023
```

Damit lassen sich Kodi-Navigation, Layoutdruck, API-Level und RAM-Grenzen frueh testen. Amazon Launcher, Appstore, Alexa, DRM, Decoder-Eigenheiten und exaktes FireOS-Verhalten bleiben Tests fuer echte Hardware.

## AFTMM-Fokus

Der Fire TV Stick 4K - 1st Gen (2018), Build-Model `AFTMM`, ist als Problemprofil besonders interessant:

- Fire OS 6 / Android 7.1 / API 25
- 32-bit ABI
- 1.5 GB RAM
- 8 GB Storage
- 4K/HDR faehig, aber ohne AV1

Der empfohlene Lauf fuer dieses Profil ist:

```powershell
python tools/kodi_firetv_test.py all --profile aftmm --iterations 500 --keep-profile
```

Wenn dabei `FAIL` erscheint, ist die Ursache sofort im Ergebnis benannt. `WARN` markiert Grenzen, die auf echter Hardware nachgetestet werden sollten.

## Datenbasis

Die Profile basieren auf Amazons offiziellen Entwicklerseiten:

- https://developer.amazon.com/docs/device-specs/device-specifications-fire-tv-streaming-media-player.html
- https://developer.amazon.com/docs/device-specs/identify-fire-tv-devices.html
- https://developer.amazon.com/docs/fire-tablets/ft-testing-without-an-amazon-device.html
