# xVAULT

xVAULT ist ein Kodi-Video-Add-on zum Durchsuchen und Wiedergeben von Filmen, TV-Serien und LiveTV.

## Aktuelle Version

Aktueller Stand: `2026.06.28.8`

Die fuehrende Versionsquelle ist [`addon.xml`](addon.xml). Wenn die Version in `addon.xml` geaendert wird, muss diese README geprueft und bei Bedarf aktualisiert werden.

## Installation

1. Die aktuelle Add-on-ZIP von [xvault.ddnss.de](http://xvault.ddnss.de/) herunterladen.
2. In Kodi **Add-ons > Aus ZIP-Datei installieren** oeffnen.
3. Die Datei `plugin.video.xvault-2026.06.28.8.zip` auswaehlen.
4. xVAULT starten.

Alternativ kann das Repository-ZIP von [http://xvault.ddnss.de/repository.xvault.zip](http://xvault.ddnss.de/repository.xvault.zip) installiert werden. Danach findet Kodi neue xVAULT-Versionen ueber das Repository.

Kodi installiert die offiziellen Abhaengigkeiten aus den konfigurierten Repositorys. Nicht im offiziellen Kodi-Repo verfuegbare Module wie ResolveURL werden beim ersten Start von xVAULT automatisch aus ihren offiziellen Quellen nachinstalliert.

Weitere Hinweise zu Abhaengigkeiten stehen in [`DEPENDENCIES.md`](DEPENDENCIES.md).

## Nutzung

- Filme und Serien ueber die xVAULT-Menues suchen.
- Eine Quelle auswaehlen oder Autoplay verwenden.
- LiveTV oeffnen, um deutsche Sender aus den VAVOO/HUHU-Listen zu laden und wiederzugeben.
- Favoriten und Wiedergabestaende optional ueber den Kontenbereich synchronisieren.
- Gesehene Folgen, Staffeln und Serien werden aus den aktuellen Wiedergabestaenden abgeleitet.

## Funktionen

- Suche und Wiedergabe von Filmen und TV-Serien.
- LiveTV mit zusammengefuehrten Senderlisten von `vavoo.to/channels` und `huhu.to/channels`.
- Deutsche LiveTV-Kategorien und Stream-Auswahl ueber lokale Mapping-Daten.
- Fortsetzen von Wiedergaben und automatische Lesezeichen.
- Gesehen/Ungesehen-Status fuer Filme, Folgen, Staffeln und Serien.
- xVAULT-Synchronisation fuer Favoriten und Wiedergabestaende.
- Download-, Untertitel- und externe Download-Manager-Optionen.
- Optionaler VAVOO-/Stalker-Bereich.

## Einstellungen

Die Einstellungen werden in [`resources/settings.xml`](resources/settings.xml) definiert. Wenn dort Einstellungen geaendert, hinzugefuegt oder entfernt werden, muss diese Uebersicht geprueft und bei Bedarf aktualisiert werden.

| Bereich | Einstellung | Technischer Name | Bedeutung | Standardwert |
|---|---|---|---|---|
| Allgemein | Standard-Aktion | `hosts.mode` | Verhalten bei Quellen: Dialog, Verzeichnis oder Autoplay. | `2` (Autoplay) |
| Allgemein | Zeitlimit fuer Indexseiten | `scrapers.timeout` | Maximale Wartezeit fuer Indexseiten. | `35` |
| Allgemein | Fanart verwenden | `fanart` | Fanart-Bilder in Listen anzeigen. | `true` |
| Allgemein | Auch nach Dokumentationen suchen | `search.doku` | Dokumentationen in die Suche einbeziehen. | `false` |
| Allgemein | HTTP-Timeout | `requestTimeout` | Timeout fuer HTTP-Anfragen in Sekunden. | `10` |
| Allgemein | HTML-Cachezeit | `cacheTime` | Cachezeit fuer Webseiteninhalte in Sekunden. | `600` |
| Allgemein | HTML nur im RAM cachen | `volatileHtmlCache` | HTML-Inhalte nicht dauerhaft speichern. | `true` |
| Allgemein | HTML-Cache nach Tagen loeschen | `cacheDeltaDay` | Zeitraum fuer Cache-Bereinigung. | `2` |
| Allgemein | HTML-Cache bei Neustart loeschen | `delHtmlCache` | Loescht den HTML-Cache einmalig beim naechsten Neustart. | `false` |
| Allgemein | Filme-Status aktualisieren | `status.refresh.movies` | Gesehen-Status fuer Filme aktualisieren. | `true` |
| Allgemein | Episoden-Status aktualisieren | `status.refresh.episodes` | Gesehen-Status fuer Episoden aktualisieren. | `true` |
| Allgemein | Erste ungesehene Folge auswaehlen | `status.position` | Serienlisten auf die erste ungesehene Folge positionieren. | `true` |
| Allgemein | Debug | `status.debug` | Debug-Ausgaben fuer Statusfunktionen. | `false` |
| Indexseiten (DE) | Alle Quellen aktivieren/deaktivieren | Aktion | Aktiviert oder deaktiviert die deutschen Indexquellen gesammelt. | nicht angegeben |
| Indexseiten (DE) | Deutsche Quellen | `provider.einschalten`, `provider.filmpalast`, `provider.filmpro`, `provider.hdfilme`, `provider.fhdfilme`, `provider.huhu`, `provider.kinoger`, `provider.kinokiste`, `provider.kinox`, `provider.kkiste` | Einzelne Film-/Serienquellen aktivieren. | meist `true` |
| Indexseiten (DE) | KKiste-Streams pruefen | `provider.kkiste.checkHoster` | Streams auf Verfuegbarkeit pruefen. | `true` |
| Indexseiten 2 (DE) | Weitere deutsche Quellen | `provider.megakino`, `provider.movie2k`, `provider.movie2k2`, `provider.movie4k`, `provider.netzkino`, `provider.serienstream`, `provider.streamcloud`, `provider.topstreamfilm`, `provider.vixstream` | Weitere Film-/Serienquellen aktivieren. | meist `true`, `provider.netzkino` ist `false` |
| Indexseiten 2 (DE) | Movie4k-Streams pruefen | `provider.movie4k.checkHoster` | Streams auf Verfuegbarkeit pruefen. | `true` |
| Wiedergabe | Fortschrittsdialog | `progress.dialog` | Fortschritt im Vordergrund oder Hintergrund anzeigen. | `1` |
| Wiedergabe | Hoechste Qualitaet | `hosts.quality` | Maximale bevorzugte Streamqualitaet. | `0` (4K) |
| Wiedergabe | Serien nach Prioritaet sortieren | `hosts.sort.priority` | Indexseiten bei Serien priorisiert sortieren. | `true` |
| Wiedergabe | Nach Anbieter sortieren | `hosts.sort.provider` | Quellen nach Anbieter sortieren. | `true` |
| Wiedergabe | Hosteranzahl begrenzen | `hosts.limit`, `hosts.limit.num` | Quellenliste optional begrenzen. | `false`, `15` |
| Wiedergabe | Hoster ausschliessen | `hosts.filter` | Liste ausgeschlossener Hoster. | leer |
| Wiedergabe | Fortsetzen | `bookmarks` | Wiedergaben fortsetzen. | `true` |
| Wiedergabe | Automatisch fortsetzen | `bookmarks.auto` | Ohne Rueckfrage an letzter Position fortsetzen. | `true` |
| VAVOO.TO | IPTV Autoplay | `vavoo.auto` | LiveTV automatisch, per Countdown oder manuell starten. | `0` |
| VAVOO.TO | Countdown Zeit | `vavoo.count` | Countdown-Dauer bei entsprechender Autoplay-Einstellung. | `5` |
| VAVOO.TO | Streamanzahl im Titel | `vavoo.stream_count` | Anzahl verfuegbarer Streams im Titel anzeigen. | `false` |
| VAVOO.TO | HLS Inputstream Add-on | `vavoo.hlsinputstream` | `ffmpeg` oder `inputstream.adaptive` fuer HLS nutzen. | `1` |
| VAVOO.TO | Kanalfilter verwenden | `vavoo.filter` | LiveTV-Kanaele filtern/kategorisieren. | `true` |
| VAVOO.TO | Senderliste aktualisieren | Aktion | LiveTV-Senderlisten neu laden und zusammenfuehren. | nicht angegeben |
| VAVOO.TO | VAVOO TV verwenden | `vavoo.vavoo` | VAVOO TV-Quelle aktivieren. | `true` |
| VAVOO.TO | Stalkerportal verwenden | `vavoo.stalker` | Stalkerportal-Funktionen aktivieren. | `true` |
| VAVOO.TO | Stalker-Retries und Cache | `vavoo.stalker_retry`, `vavoo.stalk_cache` | Wiederholungen und TV-Cachezeit fuer Stalker. | `10`, `5` |
| VAVOO.TO | Stalker Portal und MAC | `vavoo.stalkerurl`, `vavoo.mac` | Portaladresse und MAC fuer Stalker. | vorbelegt |
| VAVOO.TO | Stream Auswahl | `vavoo.stream_select` | Hoster-Auswahl oder automatische Streamwahl. | `1` |
| VAVOO.TO | Naechsten Stream versuchen | `vavoo.auto_try_next_stream` | Bei Fehlern automatisch aehnliche Streams testen. | `true` |
| VAVOO.TO | Max Stream Qualitaet | `vavoo.stream_quali` | Maximale Qualitaet fuer VAVOO-Streams. | `0` |
| VAVOO.TO | Streams testen | `vavoo.stream_check` | Streams vor Wiedergabe pruefen. | `true` |
| VAVOO.TO | Debug Logging | `vavoo.debug` | VAVOO-Debugausgaben aktivieren. | `false` |
| VAVOO.TO | Cache komprimieren | `vavoo.comp` | VAVOO-Cache komprimieren. | `true` |
| Konten | Synchronisation aktivieren | `sync.enabled` | Favoriten und Wiedergabestaende synchronisieren. | `false` |
| Konten | E-Mail-Adresse | `sync.email` | Konto-E-Mail fuer xVAULT-Sync. | leer |
| Konten | Sync-Status | `sync.status`, `sync.last_sync_at` | Anzeige fuer Login-Status und letzte Synchronisation. | `Nicht angemeldet`, leer |
| Konten | Kontoaktionen | Aktionen | Anmelden, Registrieren, Kennwort wiederherstellen, synchronisieren, Backup wiederherstellen, Status/Datenschutz anzeigen, Abmelden. | nicht angegeben |
| Konten | Interne Sync-Daten | `sync.api_key`, `sync.logged_in`, `sync.device_id`, `sync.last_favorites_hash` | Technische Sync-Daten, nicht direkt bearbeiten. | leer/`false` |
| Konten | SerienStream, FlimmerStube, Aniworld | `serienstream.*`, `flimmerstube.*`, `aniworld.*` | Zugangsdaten fuer optionale Anbieter. | leer |
| Konten | API-Schluessel | `api.tmdb`, `api.trakt`, `api.fanart.tv` | Vorbelegte technische API-Schluessel. | vorbelegt, verborgen |
| Downloads / Untertitel | Downloads aktivieren | `downloads` | Download-Funktionen aktivieren. | `false` |
| Downloads / Untertitel | Downloadpfade | `download.movie.path`, `download.tv.path` | Zielordner fuer Filme und Serien. | leer |
| Downloads / Untertitel | Untertitel aktivieren | `subtitles` | Untertitel-Funktionen aktivieren. | `false` |
| Downloads / Untertitel | OpenSubtitles-Konto | `subtitles.os_user`, `subtitles.os_pass` | Zugangsdaten fuer opensubtitles.org. | leer |
| Downloads / Untertitel | Untertitelsprachen | `subtitles.lang.1`, `subtitles.lang.2` | Haupt- und Zweitsprache fuer Untertitel. | `German`, `English` |
| Downloads / Untertitel | Untertitel nach UTF-8 umwandeln | `subtitles.utf` | Untertiteldateien nach UTF-8 konvertieren. | `false` |
| Downloads / Untertitel | JDownloader | `jd_enabled`, `jd_host`, `jd_port`, `jd_automatic_start`, `jd_grabber` | JDownloader-Anbindung. | `false`, `127.0.0.1`, `10025`, `false`, `true` |
| Downloads / Untertitel | JDownloader 2 | `jd2_enabled`, `jd2_host`, `jd2_port` | JDownloader-2-Anbindung. | `false`, `127.0.0.1`, `9666` |
| Downloads / Untertitel | My.JDownloader | `myjd_enabled`, `myjd_device`, `myjd_user`, `myjd_pass` | My.JDownloader-Anbindung. | `false`, `JDownloader@Device`, leer |
| Downloads / Untertitel | PyLoad | `pyload_enabled`, `pyload_host`, `pyload_port`, `pyload_user`, `pyload_passwd` | PyLoad-Anbindung. | `false`, `127.0.0.1`, `8000`, leer |

## Fehler und Vorschlaege melden

Fehler und Verbesserungsvorschlaege bitte ueber [GitHub Issues](https://github.com/mojomedia1812/xVAULT/issues) melden. Dort gibt es Vorlagen fuer Fehlermeldungen und Feature-Wuensche.

Gute Fehlermeldungen enthalten:

- verwendete xVAULT-Version
- Kodi-Version und System
- genaue Schritte zum Nachstellen
- erwartetes und tatsaechliches Verhalten
- Screenshots oder Logs, falls vorhanden

## Mitwirken

Hinweise fuer Beitraege stehen in [`CONTRIBUTING.md`](CONTRIBUTING.md).

Bei Aenderungen an Version, Einstellungen oder Funktionen muss diese README geprueft und bei Bedarf aktualisiert werden.

## Changelog

- Repository- und Dokumentationsaenderungen: [`CHANGELOG.md`](CHANGELOG.md)
- Plugin-Versionshistorie: [`CHANGELOG.txt`](CHANGELOG.txt)

## Kompatibilitaet

xVAULT ist ein Kodi-Python-3-Add-on und deklariert in [`addon.xml`](addon.xml) `xbmc.python` ab Version `3.0.0`.
