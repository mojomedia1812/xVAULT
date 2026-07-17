
# 2022-10-09
# edit 2026-06-13

import ast
import sys, os, threading
import xml.etree.ElementTree as ET
from random import choice
try:
    import xbmc
except:
    xbmc = None


is_python2 = sys.version_info.major == 2
if is_python2:
    from xbmc import translatePath
    from urlparse import urlparse
else:
    from xbmcvfs import translatePath
    from urllib.parse import urlparse

addonPath = os.path.dirname(os.path.abspath(__file__))
_addonInfoCache = None


def _log(message, level=None):
    try:
        if xbmc:
            xbmc.log('[xVAULT.service] %s' % message, level or xbmc.LOGINFO)
    except:
        pass


def _addon_xml_info():
    global _addonInfoCache
    if _addonInfoCache is not None:
        return _addonInfoCache
    info = {
        'id': 'plugin.video.xvault',
        'name': 'xVAULT',
        'version': '',
        'path': addonPath,
    }
    try:
        root = ET.parse(os.path.join(addonPath, 'addon.xml')).getroot()
        for key in ('id', 'name', 'version'):
            if root.get(key):
                info[key] = root.get(key)
    except:
        pass
    info['profile'] = 'special://profile/addon_data/%s/' % info['id']
    _addonInfoCache = info
    return info


def addonInfo(name):
    return _addon_xml_info().get(name, '')


addonId = addonInfo('id')
addonVersion = addonInfo('version')
addonProfilePath = translatePath(addonInfo('profile'))
settingsFile = os.path.join(addonProfilePath, 'settings.xml')


def _setting_node(root, setting_id):
    for node in root.findall('setting'):
        if node.get('id') == setting_id:
            return node
    return None


def _read_settings_root():
    if os.path.exists(settingsFile):
        try:
            return ET.parse(settingsFile).getroot()
        except:
            pass
    return ET.Element('settings', {'version': '2'})


def _write_settings_root(root):
    folder = os.path.dirname(settingsFile)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)
    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space='    ')
    except:
        pass
    tree.write(settingsFile, encoding='utf-8', xml_declaration=False)


def _setting_args(*args, **kwargs):
    setting_id = kwargs.get('id') or kwargs.get('setting_id')
    if setting_id is None and args:
        setting_id = args[0]
    value = kwargs.get('value')
    if value is None and len(args) > 1:
        value = args[1]
    return setting_id, '' if value is None else str(value)


def setSetting(*args, **kwargs):
    setting_id, value = _setting_args(*args, **kwargs)
    if not setting_id:
        return None
    root = _read_settings_root()
    node = _setting_node(root, setting_id)
    if node is None:
        node = ET.SubElement(root, 'setting', {'id': setting_id})
    node.text = value
    _write_settings_root(root)
    return None


def _getSetting(setting_id):
    root = _read_settings_root()
    node = _setting_node(root, setting_id)
    if node is None:
        return ''
    return (node.text or node.get('value') or '').strip()


_settingsLock = threading.Lock()
SERIENSTREAM_OLD_DOMAIN = '.'.join(('s', 'to'))
PROVIDER_DOMAIN_REPLACEMENTS = {
    ('movie4k', 'movie4k-to.cfd'): 'movie4k.sx',
    ('movie4k', 'www.movie4k-to.cfd'): 'movie4k.sx',
    ('movie4k', 'movie4k.to'): 'movie4k.sx',
    ('movie4k', 'www.movie4k.to'): 'movie4k.sx',
    ('serienstream', SERIENSTREAM_OLD_DOMAIN): 'serienstream.to',
    ('serienstream', 'www.' + SERIENSTREAM_OLD_DOMAIN): 'serienstream.to',
}

def getSetting(Name, default=''):
    result = _getSetting(Name)
    if result: return result
    else: return default

def _setSettingIfChanged(setting_id, value):
    current = getSetting(setting_id, '')
    if current != value:
        setSetting(setting_id, value)

def _cleanup_service_runtime():
    try:
        for module_name, module in list(sys.modules.items()):
            if not module_name.startswith(('resources.', 'scrapers', 'service')):
                continue
            module_dict = getattr(module, '__dict__', {})
            for name in ('xbmcaddon', 'Addon', '_getSetting'):
                if name in module_dict:
                    try:
                        module_dict[name] = None
                    except:
                        pass
        sys.modules.pop('xbmcaddon', None)
    except:
        pass
    try:
        import gc
        gc.collect()
    except:
        pass

# Html Cache beim KodiStart loeschen
def delHtmlCache():
    try:
        from time import time
        deltaDay = int(getSetting('cacheDeltaDay', 3))
        deltaTime = 60*60*24*deltaDay # Tage
        currentTime = int(time())
        should_clear = False
        # einmalig
        if getSetting('delHtmlCache') == 'true':
            should_clear = True
            setSetting('delHtmlCache', 'false')
        # alle x Tage
        elif currentTime >= int(getSetting('lastdelhtml', 0)) + deltaTime:
            should_clear = True
        if should_clear:
            cache = os.path.join(addonProfilePath, 'htmlcache')
            if os.path.isdir(cache):
                for filename in os.listdir(cache):
                    try:
                        os.remove(os.path.join(cache, filename))
                    except:
                        pass
            setSetting('lastdelhtml', str(currentTime))
    except: pass

# Scraper(Seiten) ein- / ausschalten
#  [(providername, domainname), ...]     providername identisch mit dateiname
def _getPluginData():
    sPluginFolder = _get_provider_folder()
    aFileNames = _get_provider_module_names(sPluginFolder)
    aPluginsData = []
    for fileName in aFileNames:
        try:
            module_path = os.path.join(sPluginFolder, fileName + '.py')
            constants = _read_provider_constants(module_path)
            domain = constants.get('SITE_DOMAIN')
            provider = constants.get('SITE_IDENTIFIER')
            if domain and provider:
                aPluginsData.append({'domain': domain, 'provider': provider})
        except:
            pass
    return aPluginsData


def _folder_has_providers(folder):
    if not os.path.isdir(folder):
        return False
    return any(filename.endswith('.py') and not filename.startswith('__') for filename in os.listdir(folder))


def _get_provider_folder():
    sites = os.path.join(addonPath, 'sites')
    legacy = os.path.join(addonPath, 'scrapers', 'scrapers_source', 'de')
    return sites if _folder_has_providers(sites) else legacy


def _get_provider_module_names(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(
        os.path.splitext(filename)[0]
        for filename in os.listdir(folder)
        if filename.endswith('.py') and not filename.startswith('__')
    )


def _read_provider_constants(module_path):
    result = {}
    with open(module_path, 'r', encoding='utf-8') as handle:
        tree = ast.parse(handle.read(), filename=module_path)
    for node in tree.body:
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif hasattr(ast, 'AnnAssign') and isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        for target in targets:
            if isinstance(target, ast.Name) and target.id in ('SITE_DOMAIN', 'SITE_IDENTIFIER'):
                try:
                    result[target.id] = ast.literal_eval(value)
                except:
                    pass
    return result


def check_domains():
    domains = _getPluginData()
    threads = []
    try:
        for item in domains:
            _domain = item['domain']
            _provider = item['provider']
            t = threading.Thread(target=_checkdomain, args=(_domain, _provider))
            threads += [t]
            t.start()
    except:
        pass
    for t in threads:
        t.join()

def RandomUA():
    #Random User Agents aktualisiert 08.06.2025
    FF_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0'
    OPERA_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 OPR/119.0.0.0'
    ANDROID_USER_AGENT = 'Mozilla/5.0 (Linux; Android 15; SM-S931U Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/132.0.6834.163 Mobile Safari/537.36'
    EDGE_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0'
    CHROME_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
    SAFARI_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15'

    _User_Agents = [FF_USER_AGENT, OPERA_USER_AGENT, EDGE_USER_AGENT, CHROME_USER_AGENT, SAFARI_USER_AGENT]
    return choice(_User_Agents)

def _doh_enabled():
    return getSetting('bypassDNSlock.enabled', getSetting('bypassDNSlock', 'false')) == 'true'

def _checkdomain_with_doh(domain):
    _log('DoH domain check skipped in service for %s' % domain)
    return False, domain, None

def _checkdomain(_domain, _provider):
    try:
        import requests
        requests.packages.urllib3.disable_warnings()  # weil verify = False - ansonst Fehlermeldungen im kodi log
        check=None
        status_code=None
        domain = getSetting('provider.'+ _provider +'.domain', _domain)
        domain = PROVIDER_DOMAIN_REPLACEMENTS.get((_provider, domain), domain)
        base_link = 'https://' + domain
        try:
            UA=RandomUA()
            headers = {
                "referer": base_link,
                "user-agent": UA,
            }
            r = requests.head(base_link, verify=False, headers=headers, timeout=8)
            status_code = r.status_code
            if 300 <= status_code <= 400:
                from urllib.parse import urljoin
                url = urljoin(base_link, r.headers.get('Location', ''))
                domain = urlparse(url).hostname
                check = 'true' if domain else 'false'
            elif status_code == 200:
                domain = urlparse(base_link).hostname
                check = 'true'
            else:
                check = 'false'
        except:
            check = 'false'
            #pass
        finally:
            wrongDomain = 'site-maps.cc', 'www.drei.at', 'notice.cuii.info'
            doh_enabled = _doh_enabled()
            if doh_enabled and (check != 'true' or domain in wrongDomain):
                doh_domain = _domain if domain in wrongDomain else domain
                doh_check, doh_domain, doh_status = _checkdomain_with_doh(doh_domain)
                if doh_check and doh_domain not in wrongDomain:
                    check = 'true'
                    domain = doh_domain
                    status_code = 'DoH:%s' % doh_status
                elif domain not in wrongDomain:
                    check = ''
            with _settingsLock:
                if domain in wrongDomain:
                    _setSettingIfChanged('provider.' + _provider + '.check', '')
                    _setSettingIfChanged('provider.' + _provider + '.domain', '')
                else:
                    _setSettingIfChanged('provider.' + _provider + '.check', check)
                    _setSettingIfChanged('provider.' + _provider + '.domain', domain)
            _log('Provider: %s / Statuscode: %s / Domain: %s, Check: %s' % (_provider, status_code, domain, check))
    except: pass

def ensure_youtube_api_keys():
    """Write bundled YouTube API keys to api_keys.json if not already configured.
    Only writes if no user key exists — never overwrites an existing configured key."""
    import json, base64
    try:
        yt_keys_path = translatePath('special://home/userdata/addon_data/plugin.video.youtube/api_keys.json')

        # If file exists, check whether a user key is already present
        if os.path.exists(yt_keys_path):
            try:
                with open(yt_keys_path, 'r') as f:
                    existing = json.load(f)
                if existing.get('keys', {}).get('user', {}).get('api_key', ''):
                    return  # user key already configured — do not touch
            except Exception:
                pass  # unreadable — fall through and write fresh

        # Write bundled fallback keys to api_keys.json.
        # JSON structure is visible as-is; values prefixed 'b64:' are decoded before writing.
        _template = """{
    "keys": {
        "user": {
            "api_key":       "b64:QUl6YVN5RG5sSjBlX0NabExvWm03Q01Obk80MXhJblpnVkZ5T2Jv",
            "client_id":     "b64:ODY5OTIyMDgxNzY5LWQzOTJkdTN2dTZjOGNwbXRsbDExcnBkN2YwOWRldTFuLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29t",
            "client_secret": "b64:R09DU1BYLVpPSWYwSnM3cUFCN3FsTWNvRkFDTlpqVWhfQ2o="
        },
        "developer": {}
    }
}"""

        def _resolve(obj):
            if isinstance(obj, dict):
                return {k: _resolve(v) for k, v in obj.items()}
            if isinstance(obj, str) and obj.startswith('b64:'):
                return base64.b64decode(obj[4:].encode()).decode()
            return obj

        yt_dir = os.path.dirname(yt_keys_path)
        if not os.path.exists(yt_dir):
            os.makedirs(yt_dir)

        with open(yt_keys_path, 'w') as f:
            json.dump(_resolve(json.loads(_template)), f, indent=4)
        _log('YouTube api_keys.json written')
    except Exception as e:
        _log('Failed to write YouTube api_keys.json: %s' % str(e), getattr(xbmc, 'LOGWARNING', None) if xbmc else None)


if __name__ == "__main__":
	check_domains()
	delHtmlCache()
	ensure_youtube_api_keys()
	_cleanup_service_runtime()
