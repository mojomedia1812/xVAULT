# xVAULT-Abhängigkeiten

Geprüfter Stand: 2026-06-29

## Kodi-Grundlage

| ID / Komponente | Status | Verwendung | Original-Repository |
|---|---|---|---|
| `xbmc.python >= 3.0.0` | Pflicht | Python-Laufzeit und Kodi-API | https://github.com/xbmc/xbmc |

## Pflichtabhängigkeiten

Diese Module werden vom aktiven Code direkt importiert und müssen mitinstalliert
werden.

| Kodi-ID | Mindestversion | Lokal installiert | Verwendung | Original-Repository |
|---|---:|---:|---|---|
| `script.module.requests` | nicht festgelegt | 2.31.0 | HTTP-Anfragen, Provider, LiveTV, EPG, Metadaten und Medienanalyse | https://github.com/psf/requests |
| `script.module.six` | nicht festgelegt | 1.16.0+matrix.1 | Python-Kompatibilitätsfunktionen | https://github.com/benjaminp/six |
| `script.module.pyaes` | nicht festgelegt | 1.6.1+matrix.1 | AES-Ver- und Entschlüsselung, unter anderem MyJDownloader und Provider | https://github.com/ricmoo/pyaes |
| `script.module.infotagger` | nicht festgelegt | 0.0.8 | Kodi-20+-Metadaten für Filme, Serien, Staffeln und Episoden | https://github.com/jurialmunkey/script.module.infotagger |
| `script.module.resolveurl` | 5.1.100 | Bootstrap | Aufloesen unterstuetzter Video-Hoster und Resolver-Einstellungen | https://github.com/Gujal00/ResolveURL |

Hinweis: `script.module.resolveurl` ist in `addon.xml` absichtlich als optional
markiert, damit Kodi die direkte ZIP-Installation von xVAULT nicht wegen eines
nicht im offiziellen Kodi-Repo vorhandenen Moduls abbricht. xVAULT behandelt es
im Bootstrap weiterhin als Pflichtabhängigkeit und installiert es aus Gujals
offiziellem ResolveURL-Repository nach.

## Optionale Funktionen

| Kodi-ID / Komponente | Lokal installiert | Wann benötigt | Installation / Original-Repository |
|---|---:|---|---|
| `script.module.download-m3u8` | Bootstrap | Nur für direkte HLS-/M3U8-Downloads | Kodi-Paket: https://github.com/chrisklietsch/repository.kc-kodi/tree/main/repo/script.module.download-m3u8 — Upstream: https://github.com/hwaves/m3u8_To_MP4 (Weiterleitung zu https://github.com/tysoong/m3u8_To_MP4) |
| `inputstream.ffmpegdirect` | 21.3.8 | Bevorzugte optionale HLS-LiveTV-Wiedergabe im automatischen Modus, wenn auf der Kodi-Plattform verfuegbar; sonst faellt xVAULT auf Kodis interne HLS-Wiedergabe zurueck | https://github.com/xbmc/inputstream.ffmpegdirect |
| `inputstream.adaptive` | 21.5.21 | Optionale HLS-/DASH-Wiedergabe; fuer LiveTV nur noch bei manueller Auswahl der Wiedergabe-Engine | https://github.com/xbmc/inputstream.adaptive |
| `plugin.video.youtube` | Nein | Trailer-Wiedergabe; ohne Add-on wird die Trailer-Funktion ausgeblendet | https://github.com/anxdpanic/plugin.video.youtube |
| `script.module.pydevd` | Nein | Nur Entwickler-Debugging; aktive Nutzung wurde nicht gefunden | Kodi-Modul: https://github.com/powlo/script.module.pydevd — Upstream: https://github.com/fabioz/PyDev.Debugger |

## Bootstrap-Quellen außerhalb des offiziellen Kodi-Repos

| Kodi-ID | Automatische Quelle |
|---|---|
| `script.module.resolveurl` | Repository-ZIP: https://gujal00.github.io/repository.resolveurl-1.0.0.zip; Metadaten/Fallback: https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml |
| `script.module.download-m3u8` | Metadaten/Fallback: https://raw.githubusercontent.com/chrisklietsch/repository.kc-kodi/main/repo/addons.xml |

## Deklariert, aber nicht benötigt

| Kodi-ID | Befund | Original-Repository |
|---|---|---|
| `script.module.kodi-six` | Im Manifest als Pflichtmodul eingetragen, aber kein aktiver Import im Quelltext gefunden. Das Projekt ist archiviert. Nach einem gesonderten Regressionstest kann der Manifest-Eintrag entfernt werden. | https://github.com/romanvm/kodi.six |

## Externe Dienste und Programme

Diese Komponenten sind keine Kodi-Abhängigkeiten und werden nicht automatisch
mitinstalliert.

| Komponente | Wann benötigt |
|---|---|
| JDownloader / JDownloader 2 | Nur für die entsprechenden Sende- und Downloadfunktionen |
| MyJDownloader-Konto und verbundenes Gerät | Nur für `Sende zu My.JDownloader` |
| pyLoad | Nur für `Sende zu PyLoad` |
| FFmpeg | Empfohlen für das Zusammenführen beziehungsweise Konvertieren von M3U8-Downloads durch `m3u8_To_MP4` |
| TMDB-API-Schlüssel | Film-, Serien-, Personen- und Metadatensuche |
| YouTube-API-Schlüssel | YouTube-Suche innerhalb der Trailer-Funktion |
| XMLTV-EPG-Quelle `epgshare01.online` | Aktuelle Programminformationen fuer den LiveTV-Hinweis vor dem Streamstart |
| Logo-Metadaten `iptv-org.github.io/api/logos.json` | Fallback-Zuordnung fuer fehlende LiveTV-Senderlogos; wird lokal zwischengespeichert |

## Empfohlene Manifestkorrekturen

1. `script.module.kodi-six` nach einem Test ohne das Modul aus den
   Pflichtabhängigkeiten entfernen.
2. `script.module.pydevd` entfernen, wenn keine Remote-Debug-Builds verteilt
   werden sollen.

