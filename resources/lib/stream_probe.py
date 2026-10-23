"""Small, bounded GET probes distinguish media from hoster/error pages."""
import re
import ssl
import time
from urllib.error import HTTPError
from urllib.parse import unquote_plus, urlsplit
from urllib.request import Request, urlopen


def _media_body(body, content_type=''):
    stripped = body.lstrip(b'\xef\xbb\xbf \t\r\n')
    lower = stripped[:512].lower()
    # Some CDNs return a browser/ad redirect with HTTP 200, even for .m3u8.
    if not body or lower.startswith((b'<html', b'<!doctype', b'<script', b'{', b'[')):
        return False
    if b'<html' in lower or content_type.lower().startswith('text/html'):
        return False
    if stripped.startswith(b'#EXTM3U'):
        return True
    if re.search(br'<(?:[\w-]+:)?MPD(?:\s|>)', stripped[:4096]):
        return True
    if body[4:8] in (b'ftyp', b'moov', b'mdat', b'styp'):
        return True
    if body.startswith((b'\x1aE\xdf\xa3', b'OggS', b'RIFF', b'FLV', b'ID3', b'\x00\x00\x01\xba', b'\x00\x00\x01\xb3')):
        return True
    if len(body) > 376 and body[0] == body[188] == body[376] == 0x47:
        return True
    if len(body) > 1 and body[0] == 0xff and body[1] & 0xe0 == 0xe0:
        return True
    # Other media containers may have no known signature. Require a media MIME
    # type and binary data, never just a successful status or file extension.
    return content_type.lower().startswith(('video/', 'audio/')) and any(b < 9 or 13 < b < 32 for b in body[:512])


def is_media_stream(stream_url, timeout=8):
    raw, separator, encoded = str(stream_url or '').partition('|')
    parsed = urlsplit(raw)
    if parsed.scheme not in ('http', 'https'):
        return parsed.scheme in ('plugin', 'rtmp', 'rtsp', 'udp', 'pvr', 'file')
    if not parsed.hostname:
        return False
    headers = {}
    context = None
    if separator:
        for part in encoded.split('&'):
            key, equals, value = part.partition('=')
            if equals:
                key, value = unquote_plus(key), unquote_plus(value)
                if key.lower() == 'verifypeer' and value.lower() in ('false', '0'):
                    context = ssl._create_unverified_context()
                if key.lower() not in ('verifypeer', 'connection-timeout', 'seekable'):
                    headers[key] = value
    headers.setdefault('Connection', 'close')
    headers['Accept-Encoding'] = 'identity'
    deadline = time.monotonic() + timeout
    # HEAD is not reliable on media CDNs. A small GET also catches HTML sent
    # under a video-looking URL. Servers rejecting Range get one bounded retry.
    for ranged in (True, False):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        probe_headers = dict(headers)
        if ranged:
            probe_headers['Range'] = 'bytes=0-4095'
        else:
            probe_headers.pop('Range', None)
        try:
            with urlopen(Request(raw, headers=probe_headers), timeout=remaining, context=context) as response:
                body = response.read(4096)
                return _media_body(body, response.headers.get('Content-Type', ''))
        except HTTPError as exc:
            code = exc.code
            exc.close()
            if ranged and code in (400, 403, 405, 416):
                continue
            return False
        except Exception:
            return False
    return False
