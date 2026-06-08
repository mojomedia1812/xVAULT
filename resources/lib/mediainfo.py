# Media info probing for xVAULT streams
# Detects stream type (HLS/DASH/MP4) and extracts resolution, codec, FPS, audio, bitrate, duration

import re
import time
import threading
from resources.lib import log_utils, control

TOTAL_TIMEOUT = 20  # seconds budget for entire probe


def _fetchWithDeadline(dialog, pct, msg, func, deadline):
    """Run func() in a background thread, showing countdown to deadline on dialog."""
    result = [None]
    error = [None]
    def run():
        try: result[0] = func()
        except Exception as e: error[0] = e
    t = threading.Thread(target=run)
    t.start()
    while t.is_alive():
        remaining = int(deadline - time.time())
        if remaining <= 0:
            break
        dialog.update(pct, msg)
        if dialog.iscanceled():
            return None
        t.join(timeout=1)
    t.join(timeout=0.5)
    if error[0]:
        raise error[0]
    return result[0]


def _remaining(deadline):
    """Seconds left until deadline, minimum 2."""
    return max(2, deadline - time.time())


def getMediaInfo(url, dialog, deadline=None):
    """Detect stream type and probe media info. Returns formatted info string or None."""
    import requests
    if not deadline:
        deadline = time.time() + TOTAL_TIMEOUT
    stream_url = url.split('|')[0]
    url_lower = stream_url.lower()

    # 1. Check URL extension first (fast path)
    if '.m3u8' in url_lower:
        return _probeHLS(url, dialog, deadline)
    if '.mpd' in url_lower:
        return _probeDASH(url, dialog, deadline)

    # 2. Fetch a small chunk to detect by Content-Type + content sniffing
    headers = _parseHeaders(url)
    try:
        r = _fetchWithDeadline(dialog, 55, 'Erkenne Stream-Typ...',
            lambda: requests.get(stream_url, headers=headers, timeout=_remaining(deadline), verify=False, stream=True),
            deadline)
        if r is None:
            return None
        if r.status_code >= 400:
            return 'Stream nicht erreichbar (HTTP %d)' % r.status_code

        ct = r.headers.get('Content-Type', '').lower()
        content_length = r.headers.get('Content-Length', '')

        # Read first 8KB for sniffing
        peek = next(r.iter_content(chunk_size=8192), b'')
        r.close()

        # Detect HLS by Content-Type or content
        if 'mpegurl' in ct or 'apple' in ct or peek.lstrip().startswith(b'#EXTM3U'):
            return _probeHLS(url, dialog, deadline)

        # Detect DASH by Content-Type or content
        if 'dash' in ct or (peek.lstrip().startswith(b'<?xml') and b'<MPD' in peek):
            return _probeDASH(url, dialog, deadline)

        # Otherwise: direct file (MP4, MKV, etc.)
        return _probeDirect(url, dialog, deadline, content_length)

    except Exception as e:
        log_utils.log('getMediaInfo Error: %s' % str(e), log_utils.LOGERROR)
        return 'Stream-Typ konnte nicht erkannt werden'


def _probeHLS(url, dialog=None, deadline=None):
    import requests
    if not deadline:
        deadline = time.time() + TOTAL_TIMEOUT
    try:
        stream_url = url.split('|')[0]
        headers = _parseHeaders(url)

        r = requests.get(stream_url, headers=headers, timeout=_remaining(deadline), verify=False)
        content = r.text

        if '#EXT-X-STREAM-INF' not in content:
            return 'HLS Stream (Single-Bitrate)\n\nKeine Auflösungsinfo im Manifest verfügbar.'

        lines = content.strip().split('\n')
        variants = []
        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF'):
                res_match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
                bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                codec_match = re.search(r'CODECS="([^"]+)"', line)

                width = int(res_match.group(1)) if res_match else 0
                height = int(res_match.group(2)) if res_match else 0
                bandwidth = int(bw_match.group(1)) if bw_match else 0
                codecs = codec_match.group(1) if codec_match else ''

                # Next non-comment line is the variant URL
                variant_url = ''
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() and not lines[j].startswith('#'):
                        variant_url = lines[j].strip()
                        break

                variants.append((width, height, bandwidth, codecs, variant_url))

        if not variants:
            return 'HLS Stream\n\nKeine Auflösungsinfo gefunden.'

        variants.sort(key=lambda x: x[1], reverse=True)
        best = variants[0]

        result = 'Typ:  HLS Stream\n'
        result += 'Auflösung:  %dx%d (%s)\n' % (best[0], best[1], _resLabel(best[1]))
        if best[3]:
            vc = [c.strip() for c in best[3].split(',') if c.strip()[:3].lower() in ('avc', 'hev', 'hvc', 'av0', 'vp0', 'vp8', 'vp9', 'mp4')]
            ac = [c.strip() for c in best[3].split(',') if c.strip() not in vc]
            # mp4a is audio, not video
            vc_final = [c for c in vc if not c.strip().lower().startswith('mp4a')]
            ac_final = ac + [c for c in vc if c.strip().lower().startswith('mp4a')]
            if vc_final: result += 'Video-Codec:  %s\n' % _codecName(','.join(vc_final))

            # Parse #EXT-X-MEDIA:TYPE=AUDIO lines for language info
            audio_tracks = []
            for line in lines:
                if line.startswith('#EXT-X-MEDIA') and 'TYPE=AUDIO' in line:
                    lang_m = re.search(r'LANGUAGE="([^"]*)"', line)
                    lang = lang_m.group(1) if lang_m else ''
                    audio_tracks.append(lang)

            if audio_tracks:
                codec_str = _codecName(','.join(ac_final)) if ac_final else ''
                seen_langs = set()
                for lang in audio_tracks:
                    lang_key = lang.lower()
                    if lang_key in seen_langs:
                        continue
                    seen_langs.add(lang_key)
                    lang_str = _langName(lang)
                    if lang_str and codec_str:
                        result += 'Audio:  %s — %s\n' % (codec_str, lang_str)
                    elif codec_str:
                        result += 'Audio:  %s\n' % codec_str
                    elif lang_str:
                        result += 'Audio:  %s\n' % lang_str
            elif ac_final:
                result += 'Audio:  %s\n' % _codecName(','.join(ac_final))
            else:
                result += 'Audio:  !! Kein Audio !!\n'

        if best[2]: result += 'Bitrate:  %s\n' % _fmtBitrate(best[2])

        # Fetch media playlist for duration + estimated size
        variant_url = best[4] if len(best) > 4 else ''
        if variant_url and time.time() < deadline:
            try:
                # Resolve relative URLs
                if not variant_url.startswith('http'):
                    base = stream_url.rsplit('/', 1)[0]
                    variant_url = base + '/' + variant_url
                r2 = requests.get(variant_url, headers=headers, timeout=_remaining(deadline), verify=False)
                total_dur = 0.0
                for m in re.finditer(r'#EXTINF:([\d.]+)', r2.text):
                    total_dur += float(m.group(1))
                if total_dur > 0:
                    hours = int(total_dur) // 3600
                    mins = (int(total_dur) % 3600) // 60
                    secs = int(total_dur) % 60
                    if hours > 0:
                        result += 'Dauer:  %d:%02d:%02d (geschätzt)\n' % (hours, mins, secs)
                    else:
                        result += 'Dauer:  %d:%02d (geschätzt)\n' % (mins, secs)
                    if best[2]:
                        est_size = (best[2] * total_dur) / 8
                        est_mb = est_size / (1024.0 * 1024.0)
                        if est_mb >= 1024:
                            result += 'Dateigröße:  %.1f GB (geschätzt)\n' % (est_mb / 1024.0)
                        else:
                            result += 'Dateigröße:  %.0f MB (geschätzt)\n' % est_mb
            except:
                pass

        return result.rstrip()

    except Exception as e:
        log_utils.log('_probeHLS Error: %s' % str(e), log_utils.LOGERROR)
        return None


def _probeDASH(url, dialog=None, deadline=None):
    import requests
    import xml.etree.ElementTree as ET
    if not deadline:
        deadline = time.time() + TOTAL_TIMEOUT
    try:
        stream_url = url.split('|')[0]
        headers = _parseHeaders(url)

        r = requests.get(stream_url, headers=headers, timeout=_remaining(deadline), verify=False)
        root = ET.fromstring(r.content)

        # Handle XML namespace
        ns = ''
        ns_match = re.match(r'\{(.+?)\}', root.tag)
        if ns_match:
            ns = '{%s}' % ns_match.group(1)

        variants = []
        for rep in root.iter('%sRepresentation' % ns):
            width = rep.get('width')
            height = rep.get('height')
            bandwidth = rep.get('bandwidth')
            codecs = rep.get('codecs', '')
            mime = rep.get('mimeType', '')
            # Also check parent AdaptationSet
            parent = None
            for adapt in root.iter('%sAdaptationSet' % ns):
                if rep in list(adapt):
                    parent = adapt
                    break
            if not mime and parent is not None:
                mime = parent.get('mimeType', '')
            if not codecs and parent is not None:
                codecs = parent.get('codecs', '')

            if width and height:
                variants.append((int(width), int(height), int(bandwidth) if bandwidth else 0, codecs, mime))

        if not variants:
            return 'DASH Stream\n\nKeine Auflösungsinfo im Manifest verfügbar.'

        # Deduplicate and sort by height descending
        seen = set()
        unique = []
        for v in variants:
            key = (v[0], v[1], v[2])
            if key not in seen:
                seen.add(key)
                unique.append(v)
        unique.sort(key=lambda x: (x[1], x[2]), reverse=True)

        best = unique[0]

        result = 'Typ:  DASH Stream\n'
        result += 'Auflösung:  %dx%d (%s)\n' % (best[0], best[1], _resLabel(best[1]))
        if best[3]: result += 'Video-Codec:  %s\n' % _codecName(best[3])
        if best[2]: result += 'Bitrate:  %s\n' % _fmtBitrate(best[2])

        # Audio info from audio AdaptationSets
        has_audio = False
        for adapt in root.iter('%sAdaptationSet' % ns):
            mime = adapt.get('mimeType', '')
            if 'audio' not in mime:
                continue
            has_audio = True
            lang = adapt.get('lang', '')
            lang_str = _langName(lang)
            for rep in adapt.iter('%sRepresentation' % ns):
                ac = rep.get('codecs', '') or adapt.get('codecs', '')
                if ac:
                    if lang_str:
                        result += 'Audio:  %s — %s\n' % (_codecName(ac), lang_str)
                    else:
                        result += 'Audio:  %s\n' % _codecName(ac)
                    break
        if not has_audio:
            result += 'Audio:  !! Kein Audio !!\n'

        return result.rstrip()

    except Exception as e:
        log_utils.log('_probeDASH Error: %s' % str(e), log_utils.LOGERROR)
        return None


def _fetchRange(url, headers, start, end, dialog, deadline, pct, msg):
    """Fetch a byte range, showing progress. Returns (bytes, total_size) or (None, 0).
    total_size is extracted from Content-Range header when available."""
    import requests
    h = dict(headers)
    h['Range'] = 'bytes=%d-%d' % (start, end)
    try:
        r = _fetchWithDeadline(dialog, pct, msg,
            lambda: requests.get(url, headers=h, timeout=_remaining(deadline), verify=False, stream=True),
            deadline)
        if r is None or r.status_code >= 400:
            return None, 0
    except:
        return None, 0

    # Extract total file size from Content-Range: bytes 0-65535/TOTALSIZE
    total_size = 0
    cr = r.headers.get('Content-Range', '')
    if '/' in cr:
        try: total_size = int(cr.split('/')[-1])
        except: pass

    data = b''
    want = end - start + 1
    for chunk in r.iter_content(chunk_size=65536):
        data += chunk
        remaining = int(deadline - time.time())
        dialog.update(pct, '%s %.0f KB' % (msg, len(data) / 1024.0))
        if len(data) >= want:
            break
        if dialog.iscanceled() or remaining <= 0:
            break
    r.close()
    return data, total_size


def _findSecondTrak(data, moov_off):
    """Find the offset of the second trak box inside moov (where audio usually lives).
    Returns offset relative to file start, or None."""
    import struct
    # Scan moov children
    p = moov_off + 8  # skip moov box header
    trak_count = 0
    while p < len(data) - 8:
        try:
            box_size = struct.unpack('>I', data[p:p+4])[0]
            box_type = data[p+4:p+8]
        except:
            break
        if box_size < 8:
            break
        if box_type == b'trak':
            trak_count += 1
            if trak_count == 2:
                return p - moov_off  # offset relative to moov start
        p += box_size
    # If first trak extends beyond data, calculate 2nd trak offset
    p = moov_off + 8
    while p < len(data) - 8:
        try:
            box_size = struct.unpack('>I', data[p:p+4])[0]
            box_type = data[p+4:p+8]
        except:
            break
        if box_size < 8:
            break
        if box_type == b'trak':
            return (p - moov_off) + box_size  # end of first trak = start of second
        p += box_size
    return None


def _findMoov(data):
    """Scan top-level MP4 boxes to find moov offset and size.
    Returns (offset, size) or (None, None)."""
    import struct
    p = 0
    while p < len(data) - 8:
        try:
            box_size = struct.unpack('>I', data[p:p+4])[0]
            box_type = data[p+4:p+8]
        except:
            break
        if box_size < 8:
            break
        if box_type == b'moov':
            return p, box_size
        if box_type == b'mdat':
            return None, None  # moov is after mdat (at end of file)
        p += box_size
    return None, None


def _probeDirect(url, dialog, deadline, file_size_str=''):
    import requests, struct
    try:
        stream_url = url.split('|')[0]
        headers = _parseHeaders(url)

        # Step 1: fetch first 64 KB to scan box headers + get total file size
        INITIAL = 65536
        data, total_size = _fetchRange(stream_url, headers, 0, INITIAL - 1, dialog, deadline, 65, 'Lade Datei-Header...')
        if data is None:
            return 'Typ:  Direkter Stream\n\nServer nicht erreichbar'

        # Fallback file size from caller or HEAD request
        if not total_size and file_size_str:
            try: total_size = int(file_size_str)
            except: pass
        content_type = ''
        if not total_size:
            try:
                r_check = requests.head(stream_url, headers=headers, timeout=_remaining(deadline), verify=False)
                content_type = r_check.headers.get('Content-Type', '')
                try: total_size = int(r_check.headers.get('Content-Length', '0'))
                except: pass
            except:
                pass

        # Step 2: scan top-level boxes to locate moov
        moov_off, moov_size = _findMoov(data)

        # We only need structural metadata (mvhd, tkhd, mdhd, stsd, stts),
        # not sample tables (stsz, stsc, stco) — cap at 256 KB
        MOOV_CAP = 262144

        if moov_off is not None:
            # moov found at start — fetch more if we don't have it all
            fetch_size = min(moov_size, MOOV_CAP)
            moov_end = moov_off + fetch_size
            if moov_end > len(data):
                dialog.update(70, 'Lade Video-Info... (%d KB)' % (fetch_size // 1024))
                extra, _ = _fetchRange(stream_url, headers, len(data), moov_end - 1,
                    dialog, deadline, 70, 'Lade Video-Info...')
                if extra:
                    data = data + extra
        elif total_size > INITIAL:
            # moov not at start (mdat first) — try from end
            tail_size = min(total_size, MOOV_CAP)
            tail_start = total_size - tail_size
            tail, _ = _fetchRange(stream_url, headers, tail_start, total_size - 1,
                dialog, deadline, 75, 'Lade Video-Info...')
            if tail:
                moov_off, moov_size = _findMoov(tail)
                if moov_off is not None:
                    moov_end = moov_off + min(moov_size, MOOV_CAP)
                    if moov_end > len(tail):
                        abs_moov_start = tail_start + moov_off
                        abs_moov_end = abs_moov_start + min(moov_size, MOOV_CAP) - 1
                        extra, _ = _fetchRange(stream_url, headers, abs_moov_start, abs_moov_end,
                            dialog, deadline, 80, 'Lade Video-Info...')
                        if extra:
                            data = extra
                        else:
                            data = tail
                    else:
                        data = tail
                else:
                    data = tail

        dialog.update(85, 'Analysiere Video-Header...')

        width, height, codec, duration_sec, fps, audio_traks = _parseMp4(data)

        # If no audio found and moov is larger than what we fetched,
        # the audio trak may be beyond MOOV_CAP — skip over the video trak and fetch it
        if not audio_traks and moov_off is not None and moov_size > MOOV_CAP and time.time() < deadline:
            audio_rel = _findSecondTrak(data, moov_off)
            if audio_rel:
                abs_audio = moov_off + audio_rel
                if abs_audio >= len(data):
                    audio_data, _ = _fetchRange(stream_url, headers, abs_audio,
                        abs_audio + 65535, dialog, deadline, 88, 'Lade Audio-Info...')
                    if audio_data:
                        _, _, _, _, _, extra_audio = _parseMp4(audio_data)
                        if extra_audio:
                            audio_traks = extra_audio

        result = 'Typ:  Direkter Stream\n'

        if width and height:
            label = _resLabel(height)
            result += 'Auflösung:  %dx%d (%s)\n' % (width, height, label)
        else:
            result += 'Auflösung:  nicht aus Datei-Header ermittelbar\n'

        if codec:
            result += 'Video-Codec:  %s\n' % _codecName(codec)
        if fps:
            if fps == int(fps):
                result += 'FPS:  %d\n' % int(fps)
            else:
                fps_str = '%.3f' % fps
                result += 'FPS:  %s\n' % fps_str.rstrip('0').rstrip('.')
        if not audio_traks:
            result += 'Audio:  !! Kein Audio-Track !!\n'
        for at in audio_traks:
            parts = [_codecName(at.get('audio_codec', ''))]
            if at.get('audio_channels'):
                parts.append(_channelLabel(at['audio_channels']))
            if at.get('audio_samplerate'):
                parts.append('%.1f kHz' % (at['audio_samplerate'] / 1000.0))
            lang_str = _langName(at.get('lang', ''))
            if lang_str:
                result += 'Audio:  %s — %s\n' % (',  '.join(parts), lang_str)
            else:
                result += 'Audio:  %s\n' % ',  '.join(parts)
        if total_size > 0 and duration_sec and duration_sec > 0:
            bitrate = int(total_size * 8 / duration_sec)
            result += 'Bitrate:  %s (Durchschnitt)\n' % _fmtBitrate(bitrate)
        if duration_sec and duration_sec > 0:
            hours = int(duration_sec) // 3600
            mins = (int(duration_sec) % 3600) // 60
            secs = int(duration_sec) % 60
            if hours > 0:
                result += 'Dauer:  %d:%02d:%02d\n' % (hours, mins, secs)
            else:
                result += 'Dauer:  %d:%02d\n' % (mins, secs)
        if content_type and 'octet' not in content_type:
            result += 'Dateityp:  %s\n' % content_type
        if total_size > 0:
            size_mb = total_size / (1024.0 * 1024.0)
            if size_mb >= 1024:
                result += 'Dateigröße:  %.1f GB\n' % (size_mb / 1024.0)
            else:
                result += 'Dateigröße:  %.0f MB\n' % size_mb

        return result.rstrip()

    except Exception as e:
        log_utils.log('_probeDirect Error: %s' % str(e), log_utils.LOGERROR)
        return None


def _parseMp4(data):
    """Parse MP4 box structure to extract video/audio info.
    Returns (width, height, codec, duration_sec, fps, audio_traks)."""
    import struct
    if len(data) < 8:
        return None, None, None, None, None, []

    width = height = None
    codec = None
    duration_sec = None
    fps = None
    current_trak = {}
    video_trak = None
    audio_traks = []

    def read_boxes(data, start, end, depth=0):
        nonlocal duration_sec, current_trak, video_trak, audio_traks
        if depth > 10:
            return
        p = start
        while p < end - 8:
            try:
                box_size = struct.unpack('>I', data[p:p+4])[0]
                box_type = data[p+4:p+8]
            except:
                break
            if box_size < 8:
                break
            if p + box_size > end:
                box_size = end - p

            if box_type == b'moov':
                read_boxes(data, p + 8, p + box_size, depth + 1)

            elif box_type == b'trak':
                current_trak = {}
                read_boxes(data, p + 8, p + box_size, depth + 1)
                if 'codec' in current_trak and not video_trak:
                    video_trak = current_trak
                elif 'audio_codec' in current_trak:
                    audio_traks.append(current_trak)

            elif box_type in (b'mdia', b'minf', b'stbl'):
                read_boxes(data, p + 8, p + box_size, depth + 1)

            # mvhd — movie header with duration
            elif box_type == b'mvhd':
                version = data[p + 8] if p + 9 <= end else 0
                if version == 0 and p + 28 <= end:
                    ts = struct.unpack('>I', data[p+20:p+24])[0]
                    dur = struct.unpack('>I', data[p+24:p+28])[0]
                    if ts > 0 and dur > 0:
                        duration_sec = float(dur) / ts
                elif version == 1 and p + 40 <= end:
                    ts = struct.unpack('>I', data[p+28:p+32])[0]
                    dur = struct.unpack('>Q', data[p+32:p+40])[0]
                    if ts > 0 and dur > 0:
                        duration_sec = float(dur) / ts

            # tkhd — track header with display dimensions (fallback)
            elif box_type == b'tkhd' and box_size >= 84:
                version = data[p + 8] if p + 9 <= end else 0
                if version == 0 and p + 92 <= end:
                    w_raw = struct.unpack('>I', data[p+84:p+88])[0]
                    h_raw = struct.unpack('>I', data[p+88:p+92])[0]
                    w, h = w_raw >> 16, h_raw >> 16
                    if 120 <= w <= 7680 and 90 <= h <= 4320:
                        current_trak['tkhd_w'] = w
                        current_trak['tkhd_h'] = h
                elif version == 1 and p + 104 <= end:
                    w_raw = struct.unpack('>I', data[p+96:p+100])[0]
                    h_raw = struct.unpack('>I', data[p+100:p+104])[0]
                    w, h = w_raw >> 16, h_raw >> 16
                    if 120 <= w <= 7680 and 90 <= h <= 4320:
                        current_trak['tkhd_w'] = w
                        current_trak['tkhd_h'] = h

            # mdhd — media header with track timescale (for FPS) + language
            elif box_type == b'mdhd':
                version = data[p + 8] if p + 9 <= end else 0
                if version == 0 and p + 24 <= end:
                    ts = struct.unpack('>I', data[p+20:p+24])[0]
                    if ts > 0:
                        current_trak['mdhd_ts'] = ts
                    if p + 30 <= end:
                        lang = struct.unpack('>H', data[p+28:p+30])[0]
                        lang_str = chr(((lang >> 10) & 0x1F) + 0x60) + chr(((lang >> 5) & 0x1F) + 0x60) + chr((lang & 0x1F) + 0x60)
                        current_trak['lang'] = lang_str
                elif version == 1 and p + 32 <= end:
                    ts = struct.unpack('>I', data[p+28:p+32])[0]
                    if ts > 0:
                        current_trak['mdhd_ts'] = ts
                    if p + 42 <= end:
                        lang = struct.unpack('>H', data[p+40:p+42])[0]
                        lang_str = chr(((lang >> 10) & 0x1F) + 0x60) + chr(((lang >> 5) & 0x1F) + 0x60) + chr((lang & 0x1F) + 0x60)
                        current_trak['lang'] = lang_str

            # stsd — sample description: codec + resolution/audio info
            elif box_type == b'stsd' and box_size > 24:
                if p + 24 <= end:
                    codec_tag = data[p+20:p+24]
                    is_video = False
                    if codec_tag in (b'avc1', b'avc3'):
                        current_trak['codec'] = 'avc1'
                        is_video = True
                    elif codec_tag in (b'hev1', b'hvc1'):
                        current_trak['codec'] = 'hev1'
                        is_video = True
                    elif codec_tag in (b'av01',):
                        current_trak['codec'] = 'av01'
                        is_video = True
                    elif codec_tag in (b'vp09',):
                        current_trak['codec'] = 'vp09'
                        is_video = True
                    elif codec_tag == b'mp4v':
                        current_trak['codec'] = 'mp4v'
                        is_video = True
                    # Video sample entry: width(uint16) at p+48, height at p+50
                    if is_video and p + 52 <= end:
                        coded_w = struct.unpack('>H', data[p+48:p+50])[0]
                        coded_h = struct.unpack('>H', data[p+50:p+52])[0]
                        if 16 <= coded_w <= 7680 and 16 <= coded_h <= 4320:
                            current_trak['stsd_w'] = coded_w
                            current_trak['stsd_h'] = coded_h
                    # Audio sample entry: channels at p+40, samplerate at p+48
                    if not is_video:
                        audio_tags = {b'mp4a': 'mp4a', b'ac-3': 'ac-3', b'ec-3': 'ec-3',
                                      b'dtsh': 'dtsh', b'dtsl': 'dtsl', b'Opus': 'opus',
                                      b'opus': 'opus', b'fLaC': 'flac'}
                        if codec_tag in audio_tags:
                            current_trak['audio_codec'] = audio_tags[codec_tag]
                            if p + 52 <= end:
                                ch = struct.unpack('>H', data[p+40:p+42])[0]
                                sr = struct.unpack('>I', data[p+48:p+52])[0] >> 16
                                if 1 <= ch <= 16:
                                    current_trak['audio_channels'] = ch
                                if 8000 <= sr <= 192000:
                                    current_trak['audio_samplerate'] = sr

            # stts — sample-to-time: first delta gives frame duration
            elif box_type == b'stts' and p + 24 <= end:
                entry_count = struct.unpack('>I', data[p+12:p+16])[0]
                if entry_count >= 1:
                    delta = struct.unpack('>I', data[p+20:p+24])[0]
                    if delta > 0:
                        current_trak['stts_delta'] = delta

            p += box_size

    try:
        read_boxes(data, 0, len(data))
    except:
        pass

    if video_trak:
        codec = video_trak.get('codec')
        if 'stsd_w' in video_trak:
            width = video_trak['stsd_w']
            height = video_trak['stsd_h']
        elif 'tkhd_w' in video_trak:
            width = video_trak['tkhd_w']
            height = video_trak['tkhd_h']
        mdhd_ts = video_trak.get('mdhd_ts')
        stts_delta = video_trak.get('stts_delta')
        if mdhd_ts and stts_delta:
            fps = round(float(mdhd_ts) / stts_delta, 3)

    return width, height, codec, duration_sec, fps, audio_traks


# --- Helper functions ---

def _resLabel(h):
    if h >= 2160: return '4K UHD'
    if h >= 1440: return 'QHD'
    if h >= 1080: return 'Full HD'
    if h >= 720:  return 'HD'
    if h >= 480:  return 'SD'
    return '%dp' % h

def _channelLabel(ch):
    if ch == 1: return 'Mono'
    if ch == 2: return 'Stereo'
    if ch == 6: return '5.1'
    if ch == 8: return '7.1'
    return '%d Kanäle' % ch

def _codecName(raw):
    if not raw: return ''
    parts = [c.strip() for c in raw.split(',')]
    names = []
    for p in parts:
        pl = p.lower()
        if pl.startswith('avc') or pl.startswith('h264') or pl == 'h.264':
            names.append('H.264')
        elif pl.startswith('hev') or pl.startswith('hvc') or pl.startswith('h265') or pl == 'h.265' or pl == 'hevc':
            names.append('H.265')
        elif pl.startswith('av01') or pl == 'av1':
            names.append('AV1')
        elif pl.startswith('vp9') or pl.startswith('vp09'):
            names.append('VP9')
        elif pl.startswith('mp4a.6b') or pl == 'mp3':
            names.append('MP3')
        elif pl.startswith('mp4a') or pl == 'aac':
            names.append('AAC')
        elif pl.startswith('ec-3') or pl.startswith('eac') or pl == 'e-ac-3':
            names.append('Dolby Digital+')
        elif pl.startswith('ac-3') or pl.startswith('ac3'):
            names.append('Dolby Digital')
        elif pl.startswith('dts'):
            names.append('DTS')
        elif pl.startswith('opus'):
            names.append('Opus')
        elif pl.startswith('flac'):
            names.append('FLAC')
        else:
            names.append(p)
    seen = set()
    unique = []
    for n in names:
        if n not in seen:
            seen.add(n)
            unique.append(n)
    return ' + '.join(unique)

def _langName(code):
    if not code: return ''
    names = {
        'de': 'Deutsch', 'deu': 'Deutsch', 'ger': 'Deutsch',
        'en': 'Englisch', 'eng': 'Englisch',
        'fr': 'Französisch', 'fra': 'Französisch', 'fre': 'Französisch',
        'es': 'Spanisch', 'spa': 'Spanisch',
        'it': 'Italienisch', 'ita': 'Italienisch',
        'ja': 'Japanisch', 'jpn': 'Japanisch',
        'ko': 'Koreanisch', 'kor': 'Koreanisch',
        'pt': 'Portugiesisch', 'por': 'Portugiesisch',
        'ru': 'Russisch', 'rus': 'Russisch',
        'tr': 'Türkisch', 'tur': 'Türkisch',
        'zh': 'Chinesisch', 'zho': 'Chinesisch', 'chi': 'Chinesisch',
        'ar': 'Arabisch', 'ara': 'Arabisch',
        'hi': 'Hindi', 'hin': 'Hindi',
        'nl': 'Niederländisch', 'nld': 'Niederländisch', 'dut': 'Niederländisch',
        'pl': 'Polnisch', 'pol': 'Polnisch',
        'sv': 'Schwedisch', 'swe': 'Schwedisch',
        'da': 'Dänisch', 'dan': 'Dänisch',
        'no': 'Norwegisch', 'nor': 'Norwegisch',
        'fi': 'Finnisch', 'fin': 'Finnisch',
        'cs': 'Tschechisch', 'ces': 'Tschechisch', 'cze': 'Tschechisch',
        'el': 'Griechisch', 'ell': 'Griechisch', 'gre': 'Griechisch',
        'he': 'Hebräisch', 'heb': 'Hebräisch',
        'th': 'Thailändisch', 'tha': 'Thailändisch',
        'uk': 'Ukrainisch', 'ukr': 'Ukrainisch',
        'und': '',
    }
    return names.get(code.lower(), code.upper())

def _fmtBitrate(bw):
    if not bw or bw <= 0: return ''
    if bw >= 1000000:
        return '%.1f Mbit/s' % (bw / 1000000.0)
    return '%d kbit/s' % (bw / 1000)

def _parseHeaders(url):
    headers = {}
    if '|' in url:
        try:
            header_str = url.split('|', 1)[1]
            headers = dict([item.split('=', 1) for item in header_str.split('&')])
            for h in headers:
                headers[h] = control.unquote_plus(headers[h])
        except:
            pass
    return headers
