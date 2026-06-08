# xVAULT Sites Folder

`xVAULT` unterstützt jetzt ein eigenes `sites/`-Verzeichnis auf Addon-Ebene,
analog zu `plugin.video.xstream/sites`.

- Wenn hier Provider-Module (`*.py`) liegen, werden diese bevorzugt geladen.
- Wenn das Verzeichnis leer ist, nutzt `xVAULT` weiterhin automatisch die
  bisherigen Legacy-Provider unter `scrapers/scrapers_source/de`.

Damit kannst du beide Addons mit derselben Ordnerstruktur pflegen.
