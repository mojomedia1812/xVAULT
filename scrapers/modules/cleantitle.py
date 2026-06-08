

import re
import unicodedata
from resources.lib.control import HTMLParser, py2_encode, unescape
from resources.lib import log_utils
html = HTMLParser()

def get(title):
    try:
        if title is None:
            return
        try:
            title = py2_encode(title)
        except:
            pass

        try:
            title = unescape(title)
        except:
            pass

        title = title.replace('\\xc3\\x84', 'Ã„').replace('\\xc3\\xa4', 'Ã¤')
        title = title.replace('\\xc3\\x96', 'Ã–').replace('\\xc3\\xb6', 'Ã¶')
        title = title.replace('\\xc3\\x9c', 'Ãœ').replace('\\xc3\\xbc', 'Ã¼')
        title = title.replace('\\xc3\\x9f', 'ÃŸ')

        title = re.sub(r'&#(\d+);', '', title)
        title = re.sub(r'(&#[0-9]+)([^;^0-9]+)', r'\1;\2', title)
        title = title.replace('&quot;', '\"').replace('&amp;', '&')
      # title = re.sub('\n|([[].+?[]])|([(].+?[)])|\s(vs|v[.])\s|(:|;|-|â€"|"|,|\'|\_|\.|\?)|\~|\s', '', title)
        title = re.sub(r"\n|([\[].+?[\]])|([(].+?[)])|\s(vs|v[.])\s|([:;\-â€\",'_.?])|~|\s", '', title)
        return title.lower()
    except Exception as e:
        log_utils.log('Exception Raised: %s' % str(e), log_utils.LOGERROR)


def geturl(title):
    if title is None:
        return
    title = title.lower()

    # title = title.translate(None, ':*?"\'\.<>|&!,')
    try:
        # This gives a weird error saying that translate only takes 1 argument, not 2. However, the Python 2 documentation states 2, but 1 for Python 3.
        # This has most likley to do with titles being unicode (foreign titles)
        title = title.translate(str.maketrans('', '', ':*?\"\'.<>|&!,'))
    except:
        for c in ':*?\"\'.<>|&!,':
            title = title.replace(c, '')

    title = title.replace('/', '-')
    title = title.replace(' ', '-')
    title = title.replace('--', '-')
    return title


def get_url(title):
    if title is None:
        return
    title = title.replace(' ', '%20')
    return title


def get_gan_url(title):
    if title is None:
        return
    title = title.lower()
    title = title.replace('-', '+')
    title = title.replace(' + ', '+-+')
    title = title.replace(' ', '%20')
    return title


def get_simple(title):
    if title is None:
        return
    title = title.lower()
    title = re.sub(r'(\d{4})', '', title)
    title = re.sub(r'&#(\d+);', '', title)
    title = re.sub(r'(&#[0-9]+)([^;^0-9]+)', r'\1;\2', title)
    title = title.replace('&quot;', '\"').replace('&amp;', '&')
  # title = re.sub('\n|\(|\)|\[|\]|\{|\}|\s(vs|v[.])\s|(:|;|-|â€"|"|,|\'|\_|\.|\?)|\~|\s', '', title).lower()
    title = re.sub(r"\n|\(|\)|\[|\]|{|\}|\s(vs|v[.])\s|([:;\-â€\",'_.?])|~|\s", '', title).lower()
    title = re.sub(r'<.*?>', '', title, count=0)
    return title


def getsearch(title):
    if title is None:
        return
    title = title.lower()
    title = re.sub(r'&#(\d+);', '', title)
    title = re.sub(r'(&#[0-9]+)([^;^0-9]+)', r'\1;\2', title)
    title = title.replace('&quot;', '\"').replace('&amp;', '&')
  # title = re.sub('\\\|/|-|â€"|:|;|\*|\?|"|\'|<|>|\|', '', title).lower()
    title = re.sub(r'[\\/\-â€":;*?"\'<>|]', '', title).lower()
    return title


def query(title):
    if title is None:
        return
    title = title.replace('\'', '').rsplit(':', 1)[0].rsplit(' -', 1)[0].replace('-', ' ')
    return title


def get_query(title):
    if title is None:
        return
    title = title.replace(' ', '.').replace(':', '').replace('.-.', '.').replace('\'', '')
    return title


# def normalize(title):
#     from sys import version_info
#     try:
#        if version_info[0] > 2: return title
#        else:
#         try: return title.decode('ascii').encode("utf-8")
#         except: return str(''.join(c for c in unicodedata.normalize('NFKD', unicode(title.decode('utf-8'))) if unicodedata.category(c) != 'Mn'))
#     except:
#         return title

def normalize(title):
    try:
        if isinstance(title, bytes):
            return title.decode('UTF-8')
        return title
    except:
        return title