

# edit 2025-07-14

# Sammelsurium

import json, os, re
import unicodedata
import requests
import xbmcvfs
from resources.lib.control import urlparse, showparentdiritems, getInfoLabel, sleep, getSetting, urlretrieve, quote_plus, progressDialog
from six.moves import urllib_error, urllib_request, urllib_parse
from operator import itemgetter
from functools import cmp_to_key
from resources.lib import log_utils, hoster_compat


def getHostDict():
    hostblockDict = ['flashx', 'streamlare', 'evoload', 'drop.download']  # permanenter Block
    blockedHoster = getSetting('hosts.filter').split(',')  # aus setting.xml blockieren
    if len(blockedHoster) <= 1: blockedHoster = getSetting('hosts.filter').split()
    for i in blockedHoster: hostblockDict.append(i.lower())
    return  hostblockDict

def isBlockedHoster(url, isResolve=True):
    import html
    from resources.lib import log_utils
    resolver = None
    if isResolve:
        try:
            import resolveurl as resolver
        except Exception as exc:
            log_utils.log('ResolveURL konnte fuer Hoster-Pruefung nicht geladen werden: %s' % str(exc), log_utils.LOGWARNING)

    requests.packages.urllib3.disable_warnings()
    from resources.lib.requestHandler import cRequestHandler
    if url.startswith("//"): url = 'http:%s' % url
    parsed = urlparse(url)
    if parsed.scheme in ['http', 'https'] and not parsed.hostname:
        log_utils.log('Ungueltige Stream-URL ohne Domain verworfen: %s' % url, log_utils.LOGINFO)
        return True, '', url, 100
    if parsed.hostname and parsed.hostname.lower() in ['redirect']:
        log_utils.log('Ungueltige Redirect-URL verworfen: %s' % url, log_utils.LOGINFO)
        return True, parsed.hostname, url, 100

    if parsed.hostname and parsed.scheme:
        UA = cRequestHandler.RandomUA()
        headers = {
            "referer": parsed.scheme +'://' + parsed.hostname + '/',
            "user-agent": UA,
        }
        try:
            r = requests.head(url, verify=False, headers=headers, timeout=3)
        except:
            pass
        else:
            status_code = r.status_code
            if 300 <= status_code <= 400:
                url = r.headers.get('Location') or url
                parsed = urlparse(url)
                if parsed.scheme in ['http', 'https'] and not parsed.hostname:
                    log_utils.log('Ungueltige Redirect-Ziel-URL verworfen: %s' % url, log_utils.LOGINFO)
                    return True, '', url, 100
                if parsed.hostname and parsed.hostname.lower() in ['redirect']:
                    log_utils.log('Ungueltige Redirect-Ziel-URL verworfen: %s' % url, log_utils.LOGINFO)
                    return True, parsed.hostname, url, 100
        
    sDomain = urlparse(url).path if urlparse(url).hostname == None else urlparse(url).hostname
    hostblockDict = getHostDict()
    prioHoster = 100
    for i in hostblockDict:
        if i in sDomain.lower() or i.split('.')[0] in sDomain.lower(): return True, sDomain, url, prioHoster
    if isResolve:
        if resolver is None:
            sUrl = hoster_compat.resolve(url)
            if sUrl:
                return False, hoster_compat.display_name(sDomain) or sDomain, sUrl, 90
            return False, sDomain, url, prioHoster
        try:
            url = html.unescape(url)    # https://github.com/Gujal00/ResolveURL/pull/1115
            hmf = resolver.HostedMediaFile(url=url, include_disabled=True, include_universal=False)
            if hmf.valid_url():
                try:
                    if hmf._HostedMediaFile__resolvers[0].isPopup():
                        prioHoster = hmf._HostedMediaFile__resolvers[0].priority
                        return False, sDomain, url, max(prioHoster, 999)
                except: pass
                try:
                    sUrl = hmf.resolve()
                except:
                    sUrl = None
                if not sUrl:
                    sUrl = hoster_compat.resolve(url)
                try: prioHoster = hmf._HostedMediaFile__resolvers[0].priority
                except: pass
                if sUrl:
                    return False, hoster_compat.display_name(sDomain) or sDomain, sUrl, prioHoster
                return False, sDomain, sUrl, prioHoster
            else:
                sUrl = hoster_compat.resolve(url)
                if sUrl:
                    return False, hoster_compat.display_name(sDomain) or sDomain, sUrl, 90
                log_utils.log('In resolveUrl keine Domain für Url %s' % url, log_utils.LOGWARNING)
                return True, sDomain, url, prioHoster
        except:
            sUrl = hoster_compat.resolve(url)
            if sUrl:
                return False, hoster_compat.display_name(sDomain) or sDomain, sUrl, 90
            return True, sDomain, url, prioHoster
    else:
        if resolver is None:
            if hoster_compat.is_supported_host(sDomain):
                return False, hoster_compat.display_name(sDomain) or sDomain, url, prioHoster
            return False, sDomain, url, prioHoster
        status = resolver.relevant_resolvers(domain=sDomain)
        if status == []:
            if hoster_compat.is_supported_host(sDomain):
                return False, hoster_compat.display_name(sDomain) or sDomain, url, prioHoster
            return True, sDomain, url, prioHoster
        else:
            prioHoster = status[0].priority
            return False, sDomain, url, prioHoster

    # elif checkResolver:   # Ãœberprüfung in resolveUrl
    #     if resolver.relevant_resolvers(domain=sDomain) == []: # sDomain nicht in resolveUrl gefunden
    #         log_utils.log('In resolveUrl keine Domain für Url %s' % url, log_utils.LOGWARNING)
    #         return True, sDomain, prioHoster
    # return False, sDomain, prioHoster


def cmp(x, y):
    """
    Replacement for built-in function cmp that was removed in Python 3

    Compare the two objects x and y and return an integer according to
    the outcome. The return value is negative if x < y, zero if x == y
    and strictly positive if x > y.

    https://portingguide.readthedocs.io/en/latest/comparisons.html#the-cmp-function
    """

    return (x > y) - (x < y)

def multikeysort(items, columns):
    # a = multikeysort(b, ['-column1', 'column2']) # - revers / b z.B. self.list
    comparers = [
        ((itemgetter(col[1:].strip()), -1) if col.startswith('-') else (itemgetter(col.strip()), 1))
        for col in columns
    ]
    def comparer(left, right):
        comparer_iter = (
            cmp(fn(left), fn(right)) * mult
            for fn, mult in comparers
        )
        return next((result for result in comparer_iter if result), 0)
    return sorted(items, key=cmp_to_key(comparer))


def getExtIDS(imdb, type): # get external IDS
    try:
        from resources.lib import trakt
        return trakt.get_external_ids(imdb, type)
    except:
        return {}


def getAliases(imdb, type):
    try:
        from resources.lib import trakt
        return trakt.get_aliases(imdb, type)
    except:
        return [], ''

def aliases_to_array(aliases, filter=None):
    try:
        if not filter:
            filter = []
        if isinstance(filter, type(u"")):
            filter = [filter]
        return [x.get('title') for x in aliases if not filter or x.get('country') in filter]
    except:
        return []

def getsearch(title):
    if title is None:
        return
    title = title.lower()
    title = re.sub(r'&#(\d+);', '', title)
    title = re.sub(r'(&#[0-9]+)([^;^0-9]+)', r'\1;\2', title)
    title = title.replace('&quot;', '\"').replace('&amp;', '&')
  # title = re.sub('\\\|/|-|â€"|:|;|\*|\?|"|\'|<|>|\|', '', title).lower()
    title = re.sub(r'[\\/\-â€":;*?"\'<>|]', '', title).lower()
    title = re.sub(r'\s+', ' ', title)
    return title

def get_titles_for_search(localtitle, title, aliases):
    titles = []
    try:
        if "country':" in str(aliases): aliases = aliases_to_array(aliases)
        if localtitle != '':
            localtitle = localtitle.lower()
            titles.append(localtitle)
            titles.append(getsearch(localtitle))
        if title != '':
            title = title.lower()
            if localtitle != title:
                titles.append(title)
                titles.append(getsearch(title))
        for i in aliases:
            try:
                #if str(i).lower() != title and str(i).lower() != localtitle and i != '' :
                if not str(i).lower() in titles:
                    titles.append(str(i).lower())
                j = getsearch(str(i))
                if not j.lower() in titles:
                    titles.append(j)
            except:
                pass
        #titles = [str(i) for i in titles if all(ord(c) < 128 for c in i)]
        titles = [item for i, item in enumerate(titles) if item not in titles[:i]]
        titles = more_titles(titles)
        return titles
    except:
        return titles

#TODO
# def title_article(titles):
#     try:
#         articles_en = ['the']  # ['the', 'a', 'an']
#         articles_de = ['die', 'der']  # ['der', 'die', 'das']
#         for title in titles:
#             match = re.match('^((\w+)\s+)', title.lower())
#             if match and match.group(2) in articles_en:
#                 for i in articles_de:
#                     title = title.replace(title[:3], i)
#                     if title not in titles: titles.append(title)
#         return titles
#     except:
#         return titles


def more_titles(titles):
    for i in titles:
        temp = _titleclean(i)
        if temp and temp not in titles:
            titles.append(temp)
    return titles

def _titleclean(title):
    try:
        if 'IV' == title.rsplit(' ',1)[1]:
            title.replace(' IV', ' 4')
        elif 'VI' == title.rsplit(' ',1)[1]:
            title.replace(' VI', ' 6')
        elif 'V' == title.rsplit(' ',1)[1]:
            title.replace(' V', ' 5')
        elif 'III' == title.rsplit(' ',1)[1]:
            title.replace(' III', ' 3')
        elif 'II' == title.rsplit(' ',1)[1]:
            title.replace(' II', ' 2')
        # elif 'I' == title.rsplit(' ',1)[1]:
        #     title.replace('I', '1')
        elif '2' == title.rsplit(' ',1)[1]:
            title.replace(' 2', ' II')
        elif '3' == title.rsplit(' ',1)[1]:
            title.replace(' 3', ' III')
        elif '4' == title.rsplit(' ',1)[1]:
            title.replace(' 4', ' IV')
        elif '5' == title.rsplit(' ',1)[1]:
            title.replace(' 5', ' V')
        elif '6' == title.rsplit(' ',1)[1]:
            title.replace(' 6', ' VI')
        return title
    except:
        pass


def check_302(url, headers={}):
    try:
        while True:
            host = urlparse(url).netloc
            headers.update({'Host': host})
            r = requests.get(url, allow_redirects=False, headers=headers, timeout=7)
            if 300 <= r.status_code <= 400:
                url = r.headers['Location']
            elif 400 <= r.status_code:
                return
            elif 200 == r.status_code:
                return url
            elif 300 > r.status_code:
                return url
            else:
                break
        return
    except:
        return


def test_stream(stream_url):
    """
    Returns True if the stream_url gets a non-failure http status (i.e. <400) back from the server
    otherwise return False

    Intended to catch stream urls returned by resolvers that would fail to playback
    """
    # parse_qsl doesn't work because it splits elements by ';' which can be in a non-quoted UA
    try:
        headers = dict([item.split('=', 1) for item in (stream_url.split('|')[1]).split('&') if '=' in item])
    except:
        headers = {}
    for header in headers:
        headers[header] = urllib_parse.unquote_plus(headers[header])
    log_utils.log('Setting Headers on UrlOpen: %s' % headers, log_utils.LOGDEBUG)

    import ssl
    try:
        #- streamurl mit ungültigen Zertifikat abweisen
        ssl_context = ssl.create_default_context()
        #ssl_context.check_hostname = False
        #ssl_context.verify_mode = ssl.CERT_NONE
        opener = urllib_request.build_opener(urllib_request.HTTPSHandler(context=ssl_context))
        urllib_request.install_opener(opener)
    except:
        pass

    try:
        msg = ''
        request = urllib_request.Request(stream_url.split('|')[0], headers=headers)
        # only do a HEAD request. gujal
        request.get_method = lambda: 'HEAD'
        #  set urlopen timeout to 15 seconds
        http_code = urllib_request.urlopen(request, timeout=15).getcode()
    except urllib_error.HTTPError as e:
        if isinstance(e, urllib_error.HTTPError):
            http_code = e.code
            if http_code == 405:
                http_code = 200
        else:
            http_code = 600
    except urllib_error.URLError as e:
        http_code = 500
        if hasattr(e, 'reason'):
            # treat an unhandled url type as success
            if 'unknown url type' in str(e.reason).lower():
                return True
            elif 'certificate verify failed' in str(e.reason).lower():
                return True
            else:
                msg = e.reason
        if not msg:
            msg = str(e)

    except Exception as e:
        http_code = 601
        msg = str(e)
        if msg == "''":
            http_code = 504

    # added this log line for now so that we can catch any logs on streams that are rejected due to test_stream failures
    # we can remove it once we are sure this works reliably
    if int(http_code) >= 400 and int(http_code) != 504:
        log_utils.log('Stream UrlOpen Failed: Url: %s \n HTTP Code: %s Msg: %s' % (stream_url, http_code, msg), log_utils.LOGWARNING)

    if not (int(http_code) < 400 or int(http_code) == 504):
        return False

    return _test_stream_body(stream_url, headers)


def _test_stream_body(stream_url, headers):
    try:
        raw_url = stream_url.split('|', 1)[0]
        parsed = urllib_parse.urlparse(raw_url)
        if parsed.scheme not in ['http', 'https']:
            return True
        path = (parsed.path or '').lower()
        if path.endswith(('.m3u', '.m3u8', '.mpd')):
            return True

        probe_headers = dict(headers)
        probe_headers.setdefault('Range', 'bytes=0-0')
        probe_headers.setdefault('Connection', 'close')
        return _read_stream_probe(raw_url, probe_headers)
    except urllib_error.HTTPError as e:
        code = int(getattr(e, 'code', 500))
        if code == 416:
            return True
        if code in [400, 403, 405]:
            try:
                fallback_headers = dict(headers)
                fallback_headers.pop('Range', None)
                fallback_headers.setdefault('Connection', 'close')
                return _read_stream_probe(stream_url.split('|', 1)[0], fallback_headers)
            except:
                return False
        return code < 400
    except:
        return False


def _read_stream_probe(raw_url, headers):
    request = urllib_request.Request(raw_url, headers=headers)
    response = urllib_request.urlopen(request, timeout=15)
    try:
        return bool(response.read(1))
    finally:
        try:
            response.close()
        except:
            pass

def normalize(title):
    from sys import version_info
    try:
       if version_info[0] > 2: return title
       else:
        try: return title.decode('ascii').encode("utf-8")
        except: return str(''.join(c for c in unicodedata.normalize('NFKD', unicode(title.decode('utf-8'))) if unicodedata.category(c) != 'Mn'))
    except:
        return title

# def normalize(title):
#     import codecs
#     try:
#         return codecs.decode(title, 'UTF-8')
#     except:
#         return title


def _container_item_position(pos):
    try:
        pos = int(pos)
    except:
        return None, None
    if pos < 1:
        return None, None
    index = pos if showparentdiritems() else pos - 1
    if index < 0:
        index = 0
    return pos, index


def _safeSetFocusPosition(pos, _name='', content='', timeout=3.0, settle_delay=0.15):
    """Select a list position without touching xbmcgui.ControlList directly."""
    import time
    import xbmc

    pos, index = _container_item_position(pos)
    if pos is None:
        return False

    isdebug = getSetting('status.debug') == 'true'
    monitor = xbmc.Monitor()
    deadline = time.time() + float(timeout)
    last_control_id = ''

    while time.time() < deadline and not monitor.abortRequested():
        try:
            if xbmc.getCondVisibility('Container.IsUpdating') or \
                    xbmc.getCondVisibility('Window.IsActive(busydialog)') or \
                    xbmc.getCondVisibility('Window.IsActive(busydialognocancel)') or \
                    xbmc.getCondVisibility('Window.IsActive(fullscreenvideo)'):
                monitor.waitForAbort(settle_delay)
                continue

            current_content = getInfoLabel('Container.Content')
            if content and current_content != content:
                monitor.waitForAbort(settle_delay)
                continue

            control_id = getInfoLabel('System.CurrentControlID')
            last_control_id = control_id
            control_id_int = int(control_id)
            if control_id_int <= 0:
                monitor.waitForAbort(settle_delay)
                continue

            # Kodi kann die Listenposition selbst fokussieren. Direkte
            # ControlList-Python-Bindings koennen auf macOS/tvOS native
            # SIGSEGV-Abstuerze ausloesen und werden deshalb vermieden.
            import xbmc as _xbmc
            _xbmc.executebuiltin('SetFocus(%i,%i)' % (control_id_int, index))
            monitor.waitForAbort(0.2)

            try:
                if int(getInfoLabel('Container().CurrentItem')) == pos:
                    if isdebug:
                        log_utils.log('%s - list position restored via SetFocus: %s' % (_name, pos), log_utils.LOGINFO)
                    return True
            except:
                if isdebug:
                    log_utils.log('%s - SetFocus requested for list position: %s' % (_name, pos), log_utils.LOGINFO)
                return True
        except:
            monitor.waitForAbort(settle_delay)

    if isdebug:
        log_utils.log('%s - list position restore skipped: pos=%s content=%s control=%s' % (_name, pos, content, last_control_id), log_utils.LOGWARNING)
    return False


## setzt Auswahl nach letzte als gesehen markierte Episode / Staffel
def setPosition(pos, _name, content='movies'): # org.: episodes
    return _safeSetFocusPosition(pos, _name, content, timeout=3.0)


def restoreListPosition(pos, content='', _name=''):
    """Restore the exact selected media item after playback or a container refresh."""
    import time
    import xbmc

    pos, index = _container_item_position(pos)
    if pos is None:
        return False

    deadline = time.time() + 12
    monitor = xbmc.Monitor()
    stable_checks = 0
    monitor.waitForAbort(0.5)

    while time.time() < deadline and not monitor.abortRequested():
        try:
            if xbmc.getCondVisibility('Container.IsUpdating') or \
                    xbmc.getCondVisibility('Window.IsActive(busydialog)') or \
                    xbmc.getCondVisibility('Window.IsActive(busydialognocancel)'):
                stable_checks = 0
                monitor.waitForAbort(0.2)
                continue

            current_content = getInfoLabel('Container.Content')
            if content and current_content != content:
                stable_checks = 0
                monitor.waitForAbort(0.2)
                continue

            control_id = int(getInfoLabel('System.CurrentControlID'))
            if control_id <= 0:
                stable_checks = 0
                monitor.waitForAbort(0.2)
                continue
            xbmc.executebuiltin('SetFocus(%i,%i)' % (control_id, index))
            monitor.waitForAbort(0.25)

            if int(getInfoLabel('Container().CurrentItem')) == pos:
                stable_checks += 1
                if stable_checks >= 3:
                    if getSetting('status.debug') == 'true':
                        log_utils.log('%s - restored list position: %s' % (_name, pos), log_utils.LOGINFO)
                    return True
            else:
                stable_checks = 0
        except:
            stable_checks = 0
        monitor.waitForAbort(0.2)

    if getSetting('status.debug') == 'true':
        log_utils.log('%s - failed to restore list position: %s' % (_name, pos), log_utils.LOGWARNING)
    return False


def getParams(_params):
    for key, value in _params.items():
        try:
            exec("%s = %s" % (key, value))
        except:
            exec ("%s = '%s'" % (key, value))


# Funktionen ab hier auch für xstream
def translatePath(*args):
    from sys import version_info
    if version_info.major == 2:
        from xbmc import translatePath
        return translatePath(*args).decode("utf-8")
    else:
        from xbmcvfs import translatePath
        return translatePath(*args)

def download_url(url, dest, dp=None):
    # download_url(url, src, dp=[None / True / False / Dialog])
    if dp == None or dp == True:
        dp = progressDialog
        dp.create("URL Downloader", " \n  Downloading  File:  [B]%s[/B]" % url.split('/')[-1])
    elif dp == False:
        return urlretrieve(url, dest)
    try:
        dp.update(0)
        urlretrieve(url, dest, lambda nb, bs, fs, url=url: _pbhook(nb, bs, fs, dp))
        dp.close()
    except:
        urlretrieve(url, dest)

def _pbhook(numblocks, blocksize, filesize, dp):
    try:
        percent = min((numblocks * blocksize * 100) / filesize, 100)
        dp.update(int(percent))
    except:
        percent = 100
        dp.update(percent)
    if dp.iscanceled():
        dp.close()
        raise Exception("Canceled")


def unzip_recursive(path, dirs, dest):
    for directory in dirs:
        dirs_dir = os.path.join(path, directory)
        dest_dir = os.path.join(dest, directory)
        xbmcvfs.mkdir(dest_dir)
        dirs2, files = xbmcvfs.listdir(dirs_dir)
        if dirs2:
            unzip_recursive(dirs_dir, dirs2, dest_dir)
        for file in files:
            # unzip_file(os.path.join(dirs_dir, file.decode('utf-8')), os.path.join(dest_dir, file.decode('utf-8')))
            unzip_file(os.path.join(dirs_dir, file), os.path.join(dest_dir, file))

def unzip_file(path, dest):
    ''' Unzip specific file. Path should start with zip:// '''
    xbmcvfs.copy(path, dest)
    #LOG.debug("unzip: %s to %s", path, dest)

def unzip(path, dest, folder=None):
    ''' Unzip file. zipfile module seems to fail on android with badziperror.'''
    path = quote_plus(path)
    root = "zip://" + path + '/'

    if folder:
        xbmcvfs.mkdir(os.path.join(dest, folder))
        dest = os.path.join(dest, folder)
        root = get_zip_directory(root, folder)
    dirs, files = xbmcvfs.listdir(root)
    if dirs:
        unzip_recursive(root, dirs, dest)

    for file in files:
        unzip_file(os.path.join(root, file), os.path.join(dest, file))
    #LOG.warn("Unzipped %s", path)

def get_zip_directory(path, folder):
    dirs, files = xbmcvfs.listdir(path)
    if folder in dirs:
        return os.path.join(path, folder)
    for directory in dirs:
        result = get_zip_directory(os.path.join(path, directory), folder)
        if result:
            return result

## ist Müll !!
# def remove_dir(path):
#     from xbmcvfs import rmdir, listdir, delete
#     dirList, flsList = listdir(path)
#     for fl in flsList:
#         delete(os.path.join(path, fl))
#     for dr in dirList:
#         remove_dir(os.path.join(path, dr))
#     ## rmdir(path)  # gefährlich !!!

def remove_dir(folder):
    import os, shutil, stat
    for filename in os.listdir(folder):
        if filename == '.idea': continue
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                if os.path.isfile(file_path): os.chmod(file_path, stat.S_IWRITE)
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

## der patch nicht mehr notwendig
def patchResolver():
    from os import path
    search = 'if order_matters'
    insert = 'for i in relevant: i.priority = i._get_priority()'
    file = translatePath('special://home/addons/script.module.resolveurl/lib/resolveurl/__init__.py')
    ln = 0
    column = 0
    if path.isfile(file):
        isEdit = False
        with open(file) as f:
            for lineno, line in enumerate(f):
                if search in line:
                        # print("{} {}".format(lineno + 1, line.find(search) + 1))
                        ln = lineno
                        column = line.find(search)
                elif insert in line:
                    isEdit = True
                    break

        if isEdit == False:
            with open(file, 'r+') as f:
                lines = f.readlines()
                lines[ln+2] = lines[ln][0:column] + insert + '\n\n'# + lines[ln][column:]
                # Delete the file
                f.seek(0)
                for i in lines:
                    # Append the lines
                    f.write(i)
