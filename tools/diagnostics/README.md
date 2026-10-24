# Lokale Diagnosen

Der lokale Stand zu signierten Paketen, Originalstatus, KodiBox-Erkennung und Release-/Nightly-Kanaelen steht in [UPDATE_CHANNELS_2026-10-24.md](UPDATE_CHANNELS_2026-10-24.md).

Die Prüfung des Diagnosepakets zu „Colony (2026)“ und die allgemeine MoFlix-Korrektur gegen falsche gleichnamige Filme stehen in [COLONY_2026-10-24.md](COLONY_2026-10-24.md).

Die lokale Wiedergabeprüfung von VIXSTREAM mit „Die Monkees“, die Korrektur falscher Sprach-/Qualitätsangaben und der Manifest-Header stehen in [VIXSTREAM_MONKEES_2026-10-24.md](VIXSTREAM_MONKEES_2026-10-24.md).

`private/` ist fuer Rohlogs, Profileinstellungen, Sync-Zustaende und lokale Sicherungen reserviert. Der Ordner ist in Git ignoriert; `tools/` wird vom Add-on-Build ausgeschlossen. Inhalte hier koennen Zugangsdaten und persoenliche Wiedergabedaten enthalten und werden nicht veroeffentlicht.

Bestehende Diagnosen bleiben unveraendert erhalten. Verschiebungen werden mit Dateigroesse und SHA256 in `private/archive-manifest-2026-10-19.json` dokumentiert. Der Abgleich der alten Arbeitskopien liegt unter `private/2026-10-19/reconciliation/`.

Einen echten Kodi-Test aus dem Repository-Root starten:

```powershell
python -B tools/kodi_rpc_smoke.py --output tools/diagnostics/private/2026-10-19/kodi-windows.json
```

`--sources` prueft zusaetzlich Film- und Serienquellen. `--play-lite` startet Pro7 fuer einen kurzen Wiedergabetest und stoppt den dabei gestarteten Player. Bereits aktive Wiedergaben werden nicht ersetzt. `--host IP` waehlt ein anderes Kodi mit aktiviertem JSON-RPC-TCP-Port 9090. Das Werkzeug protokolliert keine Stream-URLs oder Zugangsdaten.

Ein Simulationslauf ist getrennt von einem Geraetetest zu bewerten:

```powershell
python -B tools/kodi_firetv_test.py all --profile aftmm --iterations 100
```

Die Simulation bestaetigt keine Fire-TV-Medienwiedergabe. Fuer einen echten Fire-TV-Test muessen das Geraet und sein Kodi erreichbar sein.

Gezielte Tests des Providerchecks: `python -B -m unittest discover -s tools/tests -v`.

Die Testauswahl enthält inzwischen auch den Geräteabgleich. Voraussetzungen und der MariaDB-Sperrentest stehen in [api/README.md](../../api/README.md). Die lokale Kodi-Abnahme des Geräteabgleichs ist in [DEVICE_SYNC_2026-10-20.md](DEVICE_SYNC_2026-10-20.md) dokumentiert. `tools/kodi_sync_smoke.py` verwendet ausschließlich einen privaten Loopback-Testserver und getrennte Testprofile.

Die Messungen und Nachprüfung des Sync-bedingten Start-/Navigationsproblems auf einem echten Fire-TV-Stick stehen in [FIRETV_SYNC_PERFORMANCE_2026-10-23.md](FIRETV_SYNC_PERFORMANCE_2026-10-23.md). Die zusätzliche Kodi-Smoke-Phase `large-snapshot` prüft 1.000 Einträge und einen unveränderten Folgelauf in einem isolierten Profil.

Die Quellen-/Resolverdiagnose für „The Adam Project“ und die zugehörigen Korrekturen stehen in [ADAM_PROJECT_2026-10-23.md](ADAM_PROJECT_2026-10-23.md). `tools/tests/test_stream_validation.py` verwendet ausschließlich einen lokalen HTTP-Testserver und prüft echte GET-Antworten sowie die zentrale Resolverlogik.
