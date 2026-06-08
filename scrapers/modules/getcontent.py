

#2022-04-14
# edit 2023-01-22

import os, sys, time, requests
from contextlib import closing
from xbmcvfs import File
from resources.lib.control import py2_decode, translatePath, addonInfo
#from resources.lib.requestHandler import cRequestHandler, logger
from resources.lib.requestHandler import logger

def _removeBreakLines(sContent):
    sContent = sContent.replace('\\n', '').replace('\\r\\t', '')
    sContent = sContent.replace('\n', '').replace('\r\t', '')
    sContent = sContent.replace('&nbsp;', '')
    return sContent

def _timedelta(file):
    currentTime = int(time.time())
    m_time = os.path.getmtime(file)
    #c_time = os.path.getctime(file)
    if currentTime >= m_time + 60*60*24*7: return False # one day 60*60*24
    else: return True

def _writeContentFile(file, content):
    line = ''
    try:
        if sys.version_info[0] == 2:
            with open(file, 'w') as f:
                f.write(content)
        else:
            with open(file, 'wb') as f:
                f.write(content.encode('utf8'))
        with open(file, 'rb') as f:
            for line in f:
                pass
            if '</html>' in str(line): return True
        return True
    except Exception:
        logger.error('Could not write ContentCache')
        return False

def _getcontent(file, url):
    if os.path.isfile(file):
        if _timedelta(file):
            with closing(File(file)) as fo:
                sContent = fo.read()
            return True, _removeBreakLines(sContent)
    #oRequest = cRequestHandler(url)
    #oRequest.removeNewLines(False)
    #oRequest.removeBreakLines(False)
    #sContent = oRequest.request()
    sContent = requests.get(url).text
    if _writeContentFile(file, sContent):
        return True, _removeBreakLines(sContent)
    else:
        return False, ''

def Serienstream(url):
    file = os.path.join(py2_decode(translatePath(addonInfo('profile'))), 'serienstream.txt')
    return _getcontent(file, url)

def aniworld(url):
    file = os.path.join(py2_decode(translatePath(addonInfo('profile'))), 'aniworld.txt')
    return _getcontent(file, url)