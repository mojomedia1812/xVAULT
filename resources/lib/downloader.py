

# last edit:
# 2023-03-20

import re
import json
import os, sys
import inspect
import xbmc, xbmcgui, xbmcvfs
try:
    from urlparse import urlparse, parse_qsl
    from urllib import quote_plus, unquote_plus
    from urllib2 import Request, urlopen
except ImportError:
    from urllib.parse import urlparse, quote_plus, parse_qsl, unquote_plus
    from urllib.request import Request, urlopen

def download(name, image, url, subfolder=None):  # new
    if url == None: return

    from resources.lib import control

    try: headers = dict(parse_qsl(url.rsplit('|', 1)[1]))
    except: headers = dict('')

    url = url.split('|')[0]
    content = re.compile(r'(.+?)\sS(\d*)E\d*$').findall(name)

    if int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0]) >= 19:
        table = str.maketrans('', '', '\\/:*?"<>|')
        transname = name.translate(table).strip('.')
    else:
        transname = name.translate(None, '\\/:*?"<>|').strip('.')

    transname = transname.replace(' ', '_') # new

    levels =['../../../..', '../../..', '../..', '..']

    if len(content) == 0:
        dest = control.getSetting('download.movie.path', False) #TODO
        dest = control.translatePath(dest)
        for level in levels:
            try: control.makeFile(os.path.abspath(os.path.join(dest, level)))
            except: pass
        if not control.makeFile(dest):
            xbmcgui.Dialog().ok(name, dest + '[CR]ERROR - Server | Verzeichnis[CR]Download fehlgeschlagen')
            return

        # new
        if subfolder != None:
            dest = os.path.join(dest, subfolder)

        # if subfolder == None:
        #     dest = os.path.join(dest, transname)
        # else:
        #     dest = os.path.join(dest, subfolder)

        if not control.makeFile(dest):
            xbmcgui.Dialog().ok(name, dest + '[CR]ERROR - Server | Verzeichnis[CR]Download fehlgeschlagen')
            return
    else:
        dest = control.getSetting('download.tv.path', False) #TODO
        dest = control.translatePath(dest)
        for level in levels:
            try: control.makeFile(os.path.abspath(os.path.join(dest, level)))
            except: pass
        if not control.makeFile(dest):
            xbmcgui.Dialog().ok(name, dest + '[CR]ERROR - Server | Verzeichnis[CR]Download fehlgeschlagen')
            return

        if int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0]) >= 19:
            table = str.maketrans('', '', '\\/:*?"<>|')
            transtvshowtitle = content[0][0].translate(table).strip('.')
        else:
            transtvshowtitle = content[0][0].translate(None, '\\/:*?"<>|').strip('.')

        dest = os.path.join(dest, transtvshowtitle)
        if not control.makeFile(dest):
            xbmcgui.Dialog().ok(name, dest + '[CR]ERROR - Server | Verzeichnis[CR]Download fehlgeschlagen')
            return
        dest = os.path.join(dest, 'Season %01d' % int(content[0][1]))
        if not control.makeFile(dest):
            xbmcgui.Dialog().ok(name, dest + '[CR]ERROR - Server | Verzeichnis[CR]Download fehlgeschlagen')
            return

    ext = os.path.splitext(urlparse(url).path)[1][1:]
    if not ext in ['mp4', 'mkv', 'flv', 'avi', 'mpg']: ext = 'mp4'
    dest = os.path.join(dest, transname + '.' + ext)

    sysheaders = quote_plus(json.dumps(headers))
    sysurl = quote_plus(url)
    systitle = quote_plus(name)
    sysimage = quote_plus(image)
    sysdest = quote_plus(dest)
    script = inspect.getfile(inspect.currentframe())
    cmd = 'RunScript(%s, %s, %s, %s, %s, %s)' % (script, sysurl, sysdest, systitle, sysimage, sysheaders)
    xbmc.executebuiltin(cmd)


def getResponse(url, headers, size):
    try:
        if size > 0:
            size = int(size)
            headers['Range'] = 'bytes=%d-' % size

        req = Request(url, headers=headers)

        resp = urlopen(req, timeout=30)
        return resp
    except:
        return None


def done(title, dest, downloaded):
    playing = xbmc.Player().isPlaying()

    text = xbmcgui.Window(10000).getProperty('GEN-DOWNLOADED')

    if len(text) > 0:
        text += '[CR]'

    if downloaded:
        text += '%s : %s' % (dest.rsplit(os.sep)[-1], '[COLOR forestgreen]Download erfolgreich[/COLOR]')
    else:
        text += '%s : %s' % (dest.rsplit(os.sep)[-1], '[COLOR red]Download fehlgeschlagen[/COLOR]')

    xbmcgui.Window(10000).setProperty('GEN-DOWNLOADED', text)

    if (not downloaded) or (not playing): 
        xbmcgui.Dialog().ok(title, text)
        xbmcgui.Window(10000).clearProperty('GEN-DOWNLOADED')


def doDownload(url, dest, title, image, headers):
    headers = json.loads(unquote_plus(headers))
    url = unquote_plus(url)
    title = unquote_plus(title)
    image = unquote_plus(image)
    dest = unquote_plus(dest)
    file = dest.rsplit(os.sep, 1)[-1]

    resp = getResponse(url, headers, 0)

    if not resp:
        xbmcgui.Dialog().ok(title, dest + '[CR]Download fehlgeschlagen[CR]Keine Antwort vom Server')
        return

    try:    content = int(resp.headers['Content-Length'])
    except: content = 0

    if ".m3u" in url.lower():
    # if url.lower().endswith('.m3u8'):
        try:
            import m3u8_To_MP4
            if xbmcgui.Dialog().yesno('Download - ' + title, '%s[CR]Weiter mit Download?' % file, 'Weiter', 'Abbrechen') == 1: return
            dest = dest.replace('smb:', '')
            m3u8_To_MP4.multithread_download(url, file_path=dest, max_retry_times=5, max_num_workers=20)
            xbmcgui.Dialog().ok('INFO', '[CR]Download beendet')
        except:
            xbmcgui.Dialog().ok('Error', '[CR]Download fehlgeschlagen[CR]Problem mit "script.module.download-m3u8"')
        finally:
            exit()

    try:    resumable = 'bytes' in resp.headers['Accept-Ranges'].lower()
    except: resumable = False

    #print "Download Header"
    #print resp.headers
    #if resumable: print("Download is resumable")

    if content < 1:
        xbmcgui.Dialog().ok(title, file + ' Unbekannte DateigrÃ¶ÃŸe[CR]Download nicht mÃ¶glich')
        return

    size = 1024 * 1024
    mb = content / (1024 * 1024)

    if content < size:
        size = content

    total = 0
    notify = 0
    errors = 0
    count = 0
    resume = 0
    sleep = 0

    if int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0]) >= 19:
        if xbmcgui.Dialog().yesno('Download - ' + title, '%s[CR]DateigrÃ¶ÃŸe %dMB[CR]Weiter mit Download?' % (file, mb) , 'Weiter', 'Abbrechen') == 1: return
    else:
        if xbmcgui.Dialog().yesno('Download - ' + title, file, 'DateigrÃ¶ÃŸe %dMB' % mb, 'Weiter mit Download?', 'Weiter',  'Abbrechen') == 1: return

    #print('Download File Size : %dMB %s ' % (mb, dest))

    #f = open(dest, mode='wb')
    f = xbmcvfs.File(dest, 'w')

    chunks = []
    while True:
        downloaded = total
        for c in chunks:
            downloaded += len(c)
        percent = min(100 * downloaded / content, 100)
        if percent >= notify:
            # xbmc.executebuiltin( "Notification(%s,%s,%i,%s)" % ( str(int(percent))+'%' + ' - ' + title, dest, 5000, image))
            xbmcgui.Dialog().notification(str(int(percent))+'%' + ' - ' + title, dest, image, 5000, False)
            #print('Download percent : %s %s %dMB downloaded : %sMB File Size : %sMB' % (str(int(percent))+'%', dest, mb, downloaded / 1000000, content / 1000000))
            notify += 20

        chunk = None
        error = False

        try:        
            chunk = resp.read(size)
            if not chunk:
                if percent < 99:
                    error = True
                else:
                    while len(chunks) > 0:
                        c = chunks.pop(0)
                        f.write(c)
                        del c

                    f.close()
                    #print('%s download complete' % (dest))
                    return done(title, dest, True)

        except Exception as e:
            #print(str(e))
            error = True
            sleep = 10
            errno = 0

            if hasattr(e, 'errno'):
                errno = e.errno

            if errno == 10035: # 'A non-blocking socket operation could not be completed immediately'
                pass

            if errno == 10054: #'An existing connection was forcibly closed by the remote host'
                errors = 10 #force resume
                sleep  = 30

            if errno == 11001: # 'getaddrinfo failed'
                errors = 10 #force resume
                sleep  = 30

        if chunk:
            errors = 0
            chunks.append(chunk)
            if len(chunks) > 5:
                c = chunks.pop(0)
                f.write(c)
                total += len(c)
                del c

        if error:
            errors += 1
            count  += 1
            #print('%d Error(s) whilst downloading %s' % (count, dest))
            xbmc.sleep(sleep*1000)

        if (resumable and errors > 0) or errors >= 10:
            if (not resumable and resume >= 50) or resume >= 500:
                #Give up!
                #print('%s download canceled - too many error whilst downloading' % (dest))
                return done(title, dest, False)

            resume += 1
            errors  = 0
            if resumable:
                chunks  = []
                #create new response
                #print('Download resumed (%d) %s' % (resume, dest))
                resp = getResponse(url, headers, total)
            else:
                #use existing response
                pass


if __name__ == '__main__':
    if 'downloader.py' in sys.argv[0]:
        doDownload(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])


