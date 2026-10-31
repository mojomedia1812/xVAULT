"""Bounded, non-playing source observation. Store counts, never stream links."""
import os
import sys
import time

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from resources.lib import dependencies
    dependencies._refresh_python_module_paths(list(dependencies.REQUIRED_EXTERNAL_ADDONS))

_outstanding = []


def probe(meta, budget=12):
    import threading
    from resources.lib import sources
    from resources.lib.requestHandler import bounded_requests
    global _outstanding
    if any(t.is_alive() for t in _outstanding):
        return 'Quellenprüfung noch beschäftigt'
    deadline = time.monotonic() + budget
    collector = sources.sources()
    collector.mediatype = 'episode'
    collector.hostDict = collector._getHostDict()
    providers = [(name, call) for name, call in collector.sourceDict
                 if name in ('serienstream', 'aniworld', 'huhu', 'vixstream')]
    failures = []

    def run(name, call):
        try:
            call.mediatype = 'episode'
            call.episode_title = meta.get('episode_title')
            call.episode_premiered = meta.get('episode_premiered')
            titles = list(dict.fromkeys(t for t in [meta.get('title'), meta.get('originaltitle')] if t))
            with bounded_requests(deadline):
                collector._getSource(titles, meta.get('year'), meta.get('season'), meta.get('episode'),
                                     meta.get('imdb_id') or meta.get('imdbnumber'), name, call,
                                     meta.get('episode_title'), meta.get('episode_premiered'))
        except Exception:
            failures.append(name)

    _outstanding = [threading.Thread(target=run, args=p, daemon=True) for p in providers]
    for thread in _outstanding:
        thread.start()
    for thread in _outstanding:
        thread.join(max(0, deadline - time.monotonic()))
    found = sum(collector._normalizeStreamLanguage(s) in ('de', 'multi') for s in list(collector.sources))
    collector._shutdownExecutor()
    if found:
        return '%d deutsche Quellen gemeldet' % found
    return 'keine deutschen Quellen bestätigt (begrenzte Prüfung)'


def main(identifier):
    import xbmcgui
    from resources.lib import personal
    try:
        value = personal.cached().get(str(identifier))
        if value and value.get('episode'):
            value['source_status'] = probe(value['meta'], 20)
            value['source_checked'] = time.time()
            personal.save_cache(identifier, value)
    finally:
        xbmcgui.Window(10000).clearProperty('xvault.radar.sources')


if __name__ == '__main__':
    main(sys.argv[1])
