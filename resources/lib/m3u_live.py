# edit 2026-06-14

import os
import re
import sys

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import control

try:
    from urllib.parse import parse_qsl, urlencode, urlsplit
except ImportError:
    from urlparse import parse_qsl, urlsplit
    from urllib import urlencode


PLAYLIST_DIR = os.path.join(control.addonPath, 'm3u')
LEGACY_PLAYLIST_DIR = os.path.join(control.addonPath, 'resources', 'm3u')
PLAYLISTS = [
    {'id': 'tv-at', 'file': 'tv-at.m3u', 'label': 'TV AT', 'plot': 'Playlist mit Joyn-AT-Eintraegen'},
    {'id': 'tv', 'file': 'tv.m3u', 'label': 'TV', 'plot': 'Playlist mit Joyn-Eintraegen'},
    {'id': 'tv2', 'file': 'tv2.m3u', 'label': 'TV 2', 'plot': 'Alternative TV-Playlist'},
]


def list_playlists():
    handle = _handle()
    for playlist in PLAYLISTS:
        entries = load_entries(playlist['id'])
        item = _item(
            playlist['label'],
            {
                'plot': '%s\n%s Sender' % (playlist['plot'], len(entries)),
                'title': playlist['label'],
            },
            control.addonPoster(),
        )
        item.setIsFolder(True)
        control.addItem(handle, _addon_url({'action': 'm3uLiveList', 'playlist': playlist['id']}), item, True)

    export_item = _item('M3U-Dateien exportieren', {'plot': 'Schreibt normalisierte xVAULT-M3U-Dateien ins Addon-Profil.'}, control.addonPoster())
    export_item.setProperty('IsPlayable', 'false')
    control.addItem(handle, _addon_url({'action': 'm3uLiveExportAll'}), export_item, False)
    _end(handle)


def list_channels(playlist_id):
    handle = _handle()
    playlist = _playlist(playlist_id)
    entries = load_entries(playlist_id)
    for entry in entries:
        item = _item(
            entry['name'],
            {
                'plot': entry.get('group') or playlist['label'],
                'title': entry['name'],
            },
            entry.get('logo') or control.addonPoster(),
        )
        url = playback_url(entry['url'])
        item.setProperty('IsPlayable', 'true')
        try:
            item.setPath(url)
        except Exception:
            pass
        control.addItem(handle, url, item, False)
    control.sortLabel(handle)
    _end(handle)


def export_all():
    paths = []
    for playlist in PLAYLISTS:
        paths.append(export_playlist(playlist['id'], show_dialog=False))
    xbmcgui.Dialog().ok('xVAULT', 'M3U-Dateien erstellt in:\n%s' % control.addonProfilePath)
    return paths


def export_playlist(playlist_id, show_dialog=True):
    playlist = _playlist(playlist_id)
    entries = load_entries(playlist_id)
    _ensure_dir(control.addonProfilePath)
    output = os.path.join(control.addonProfilePath, playlist['file'])
    with open(output, 'w', encoding='utf-8', newline='\n') as target:
        target.write('#EXTM3U\n')
        for entry in entries:
            target.write('%s\n' % entry['extinf'])
            target.write('%s\n' % playback_url(entry['url']))
    if show_dialog:
        xbmcgui.Dialog().ok('xVAULT', 'M3U-Datei erstellt:\n%s' % output)
    return output


def load_entries(playlist_id):
    playlist = _playlist(playlist_id)
    path = _playlist_path(playlist['file'])
    entries = []
    pending = None
    with open(path, 'r', encoding='utf-8-sig') as source:
        for raw_line in source:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('#EXTINF:'):
                pending = _parse_extinf(line)
                continue
            if line.startswith('#'):
                continue
            if pending:
                pending['url'] = line
                entries.append(pending)
                pending = None
    return entries


def playback_url(url):
    split = urlsplit(url)
    if split.scheme == 'plugin' and split.netloc == 'plugin.video.vavooto':
        params = dict(parse_qsl(split.query))
        name = params.get('name')
        if name:
            return 'plugin://%s/?%s' % (
                control.addonId,
                urlencode({'action': 'vavoo_livePlay', 'name': name.upper()}),
            )
    return url


def _parse_extinf(line):
    name = line.rsplit(',', 1)[-1].strip() if ',' in line else 'Live-TV'
    attrs = dict((key.lower(), value) for key, value in re.findall(r'([\w-]+)="([^"]*)"', line))
    return {
        'extinf': line,
        'name': name,
        'group': attrs.get('group-title', ''),
        'logo': attrs.get('tvg-logo', ''),
        'tvg_id': attrs.get('tvg-id', ''),
    }


def _playlist(playlist_id):
    for playlist in PLAYLISTS:
        if playlist['id'] == playlist_id:
            return playlist
    return PLAYLISTS[0]


def _playlist_path(filename):
    path = os.path.join(PLAYLIST_DIR, filename)
    if os.path.exists(path):
        return path
    return os.path.join(LEGACY_PLAYLIST_DIR, filename)


def _item(label, info, icon):
    item = control.item(label, offscreen=True)
    item.setArt({'icon': icon, 'thumb': icon, 'poster': icon})
    item.setInfo('video', info)
    return item


def _addon_url(params):
    return '%s?%s' % (sys.argv[0], urlencode(params))


def _handle():
    return int(sys.argv[1]) if len(sys.argv) > 1 else -1


def _end(handle):
    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.setPluginCategory(handle, control.addonName + ' / M3U Live-TV')
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
