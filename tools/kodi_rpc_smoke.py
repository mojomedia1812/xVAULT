"""Run bounded smoke checks against a real Kodi instance without logging stream URLs."""
import argparse
import codecs
import json
from pathlib import Path
import socket
import time
from urllib.parse import urlencode


def rpc(host, method, params=None, timeout=45):
    request = {'jsonrpc': '2.0', 'id': 71, 'method': method}
    if params is not None:
        request['params'] = params
    deadline = time.monotonic() + timeout
    with socket.create_connection((host, 9090), timeout=5) as connection:
        connection.sendall(json.dumps(request).encode('utf-8'))
        pending = ''
        utf8 = codecs.getincrementaldecoder('utf-8')()
        decoder = json.JSONDecoder()
        while time.monotonic() < deadline:
            connection.settimeout(max(0.1, deadline - time.monotonic()))
            chunk = connection.recv(262144)
            if not chunk:
                break
            pending += utf8.decode(chunk)
            while pending.strip():
                pending = pending.lstrip()
                try:
                    response, end = decoder.raw_decode(pending)
                except ValueError:
                    break
                pending = pending[end:]
                if response.get('id') == 71:
                    if 'error' in response:
                        raise RuntimeError(json.dumps(response['error']))
                    return response.get('result')
    raise TimeoutError(method + ' returned no matching response')


def directory(host, **params):
    return rpc(host, 'Files.GetDirectory', {
        'directory': 'plugin://plugin.video.xvault/?' + urlencode(params),
        'media': 'video', 'properties': ['title'],
    }, timeout=55).get('files', [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sources', action='store_true')
    parser.add_argument('--play-lite', action='store_true')
    args = parser.parse_args()
    results = []

    def check(name, callback):
        start = time.monotonic()
        try:
            details = callback()
            result = {'name': name, 'status': 'PASS', 'details': details}
        except Exception as exc:
            result = {'name': name, 'status': 'FAIL', 'error_type': type(exc).__name__}
        result['seconds'] = round(time.monotonic() - start, 2)
        results.append(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False), flush=True)

    check('kodi-version', lambda: rpc(args.host, 'Application.GetProperties', {'properties': ['version', 'name']}))
    check('xvault-version', lambda: rpc(args.host, 'Addons.GetAddonDetails', {
        'addonid': 'plugin.video.xvault', 'properties': ['version', 'enabled']}))
    for action in ['root', 'movieNavigator', 'tvNavigator', 'liveTVNavigator', 'liveTVLiteNavigator']:
        def menu(action=action):
            items = directory(args.host, action=action)
            if not items:
                raise RuntimeError('empty directory')
            return {'count': len(items), 'labels': [i.get('label', '') for i in items[:15]]}
        check(action, menu)

    channels = []

    def lite():
        channels.extend(directory(args.host, action='liveTVLiteCategory', category='de'))
        if not channels:
            raise RuntimeError('empty channel list')
        return {'count': len(channels), 'pro7_found': any('pro7' in i.get('label', '').lower() for i in channels)}
    check('liveTVLite-de', lite)

    if args.sources:
        for name, meta in [
            ('movie-sources', {'mediatype': 'movie', 'title': 'Terminator', 'originaltitle': 'The Terminator',
                               'year': 1984, 'imdb_id': 'tt0088247', 'tmdb_id': '218', 'season': 0, 'episode': 0}),
            ('episode-sources', {'mediatype': 'tvshow', 'title': 'Phineas und Ferb', 'originaltitle': 'Phineas and Ferb',
                                 'year': 2007, 'imdb_id': 'tt0852863', 'tmdb_id': '1877', 'season': 1, 'episode': 1}),
        ]:
            def sources(meta=meta):
                items = directory(args.host, action='play', select='1', sysmeta=json.dumps(meta))
                if not items:
                    raise RuntimeError('empty source list')
                labels = [i.get('label', '') for i in items]
                return {'count': len(items), 'moflix_count': sum('moflix' in x.lower() for x in labels),
                        'serienstream_count': sum('serienstream' in x.lower() for x in labels)}
            check(name, sources)

    if args.play_lite:
        def playback():
            active = rpc(args.host, 'Player.GetActivePlayers')
            if active:
                raise RuntimeError('another player is active')
            candidate = next(i for i in channels if 'pro7' in i.get('label', '').lower())
            rpc(args.host, 'Player.Open', {'item': {'file': candidate['file']}})
            player_id = None
            try:
                for _ in range(12):
                    time.sleep(2)
                    active = rpc(args.host, 'Player.GetActivePlayers')
                    if active:
                        player_id = active[0]['playerid']
                        break
                if player_id is None:
                    raise RuntimeError('playback did not start')
                first = rpc(args.host, 'Player.GetProperties', {'playerid': player_id, 'properties': ['time', 'speed']})
                last = first
                for _ in range(6):
                    time.sleep(5)
                    last = rpc(args.host, 'Player.GetProperties', {'playerid': player_id, 'properties': ['time', 'speed']})
                    if last['speed'] > 0 and last['time'] != first['time']:
                        break
                if last['speed'] <= 0 or last['time'] == first['time']:
                    raise RuntimeError('playback did not advance')
                return {'channel': 'Pro7', 'first': first, 'last': last}
            finally:
                # Playback can appear after the startup deadline. The check
                # starts only with no active player, so clean up that late start.
                for active_player in rpc(args.host, 'Player.GetActivePlayers'):
                    rpc(args.host, 'Player.Stop', {'playerid': active_player['playerid']})
        check('liveTVLite-playback', playback)
    return 1 if any(r['status'] == 'FAIL' for r in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
