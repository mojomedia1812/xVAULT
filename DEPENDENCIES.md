# xVAULT-Abhängigkeiten

Geprüfter Stand: 2026-08-05

## Kodi-Grundlage

| ID / Komponente | Status | Verwendung | Original-Repository |
|---|---|---|---|
| `xbmc.python >= 3.0.0` | Pflicht | Python-Laufzeit und Kodi-API | https://github.com/xbmc/xbmc |

## Pflichtabhängigkeiten

Diese Module werden vom aktiven Code direkt importiert und müssen nach der
Installation verfügbar sein. Damit Kodi eine direkte ZIP-Installation nicht
wegen lokal noch nicht indexierter Module abbricht, sind sie in `addon.xml` als
optional deklariert. xVAULT behandelt sie beim ersten Start trotzdem als
Pflichtabhängigkeiten und installiert beziehungsweise aktiviert sie automatisch.

| Kodi-ID | Mindestversion | Lokal installiert | Verwendung | Original-Repository |
|---|---:|---:|---|---|
| `script.module.requests` | nicht festgelegt | 2.31.0 | HTTP-Anfragen, Provider, LiveTV, EPG, Metadaten und Medienanalyse | https://github.com/psf/requests |
| `script.module.six` | nicht festgelegt | 1.16.0+matrix.1 | Python-Kompatibilitätsfunktionen | https://github.com/benjaminp/six |
| `script.module.pyaes` | nicht festgelegt | 1.6.1+matrix.1 | AES-Ver- und Entschlüsselung, unter anderem MyJDownloader und Provider | https://github.com/ricmoo/pyaes |
| `script.module.infotagger` | nicht festgelegt | 0.0.8 | Kodi-20+-Metadaten für Filme, Serien, Staffeln und Episoden | https://github.com/jurialmunkey/script.module.infotagger |
| `script.module.resolveurl` | 5.1.100 | Bootstrap | Auflösen unterstützter Video-Hoster und Resolver-Einstellungen | https://github.com/Gujal00/ResolveURL |

Hinweis: `script.module.resolveurl` wird bei Bedarf aus Gujals offiziellem
ResolveURL-Repository nachinstalliert, falls es nicht über Kodis Repositorys
bereitsteht.

## Optionale Funktionen

Optionale binäre Kodi-Komponenten werden nicht beim allgemeinen xVAULT-Start
automatisch nachinstalliert. Sie sind plattformabhängig und können zum Beispiel
auf einzelnen webOS-/Embedded-Kodi-Builds fehlen. xVAULT nutzt sie nur, wenn sie
auf dem jeweiligen System installiert und aktiviert sind, und fällt für LiveTV
sonst auf Kodis interne HLS-Wiedergabe zurück.

| Kodi-ID / Komponente | Lokal installiert | Wann benötigt | Installation / Original-Repository |
|---|---:|---|---|
| `script.module.download-m3u8` | Bootstrap | Nur für direkte HLS-/M3U8-Downloads | Kodi-Paket: https://github.com/chrisklietsch/repository.kc-kodi/tree/main/repo/script.module.download-m3u8 — Upstream: https://github.com/hwaves/m3u8_To_MP4 (Weiterleitung zu https://github.com/tysoong/m3u8_To_MP4) |
| `inputstream.ffmpegdirect` | optional | Bevorzugte optionale HLS-LiveTV-Wiedergabe im automatischen Modus, wenn auf der Kodi-Plattform verfügbar; sonst fällt xVAULT auf Kodis interne HLS-Wiedergabe zurück | https://github.com/xbmc/inputstream.ffmpegdirect |
| `inputstream.adaptive` | optional | Optionale HLS-/DASH-Wiedergabe; für LiveTV nur noch bei manueller Auswahl der Wiedergabe-Engine | https://github.com/xbmc/inputstream.adaptive |
| `inputstream.rtmp` | optional | Optionale RTMP-Wiedergabe, wenn Kodi oder eine Plattformquelle sie für einen Stream benötigt | https://github.com/xbmc/inputstream.rtmp |
| `pvr.iptvsimple` | nutzergesteuert | Optionale Kodi-TV/PVR-Integration für die von xVAULT erzeugte LiveTV-M3U- und XMLTV-Ausgabe | https://github.com/kodi-pvr/pvr.iptvsimple |
| `plugin.video.youtube` | Nein | Trailer-Wiedergabe; ohne Add-on wird die Trailer-Funktion ausgeblendet | https://github.com/anxdpanic/plugin.video.youtube |
| `script.module.pydevd` | Nein | Nur Entwickler-Debugging; aktive Nutzung wurde nicht gefunden | Kodi-Modul: https://github.com/powlo/script.module.pydevd — Upstream: https://github.com/fabioz/PyDev.Debugger |

## Bootstrap-Quellen außerhalb des offiziellen Kodi-Repos

| Kodi-ID | Automatische Quelle |
|---|---|
| `script.module.resolveurl` | Repository-ZIP: https://gujal00.github.io/repository.resolveurl-1.0.0.zip; Metadaten/Fallback: https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml |
| `script.module.download-m3u8` | Metadaten/Fallback: https://raw.githubusercontent.com/chrisklietsch/repository.kc-kodi/main/repo/addons.xml |

InputStream-Komponenten und PVR-Clients werden nicht über diese Bootstrap-
Quellen ausgeliefert. Kodi muss dafür die zur Plattform passende Add-on-Version
bereitstellen.

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
| XMLTV-EPG-Quelle `epgshare01.online` | Aktuelle Programminformationen für den LiveTV-Hinweis vor dem Streamstart |
| Logo-Metadaten `iptv-org.github.io/api/logos.json` | Fallback-Zuordnung für fehlende LiveTV-Senderlogos; wird lokal zwischengespeichert |

## Empfohlene Manifestkorrekturen

1. `script.module.pydevd` entfernen, wenn keine Remote-Debug-Builds verteilt
   werden sollen.

