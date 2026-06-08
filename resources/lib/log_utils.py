

#2021-01-26
#edit 2023-02-24

import time
import inspect
import cProfile
try:
    from StringIO import StringIO
    from xbmc import LOGNOTICE as LOGINFO
except:
    from io import StringIO
    from xbmc import LOGINFO
try:
    basestring
except NameError:
    basestring = str                           

import pstats
import json
import xbmc
from xbmc import LOGDEBUG, LOGERROR, LOGFATAL, LOGWARNING
from resources.lib import control
name = control.addonInfo('name')

DEBUGPREFIX = '[ '+name+' DEBUG ]'

def log(msg, level=LOGDEBUG, caller=None):

    #if control.getSetting('addon_debug') == 'true' and level == LOGDEBUG:
        #level = LOGNOTICE

    try:
        if caller is not None and level == LOGDEBUG:
            func = inspect.currentframe().f_back.f_code
            line_number = inspect.currentframe().f_back.f_lineno
            caller = "%s.%s()" % (caller, func.co_name)
            msg = 'From func name: %s Line # :%s\n                       msg : %s' % (caller, line_number, msg)

        if caller is not None and level == LOGERROR:
            msg = 'From func name: %s.%s() Line # :%s\n                       msg : %s'%(caller[0], caller[1], caller[2], msg)
        #TODO
        # import pydevd
        # pydevd.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
        # if isinstance(msg, type(u"")):
        #     msg = '%s (ENCODED)' % (msg.encode('utf-8'))
        if not isinstance(msg, str):
            msg = str(msg)

        xbmc.log('%s: %s' % (DEBUGPREFIX, msg), level)
    except Exception as e:
        try:
            xbmc.log('Logging Failure: %s' % (e), level)
        except:
            pass  # just give up


def error(message=None, exception=True):
    try:
        import sys
        if exception:
            type, value, traceback = sys.exc_info()
            sysaddon = sys.argv[0].split('//')[1].replace('/', '.')
            filename = (traceback.tb_frame.f_code.co_filename).replace('\\', '.').replace('.py', '')
            filename = filename.split(sysaddon)[1].replace('\\', '.')
            name = traceback.tb_frame.f_code.co_name
            linenumber = traceback.tb_lineno
            errortype = type.__name__
            errormessage = str(value)
            if errormessage == '':
                raise Exception()
            if message:
                message += ' -> '
            else:
                message = ''
            message += str(errortype) + ' -> ' + str(errormessage)
            caller = [filename, name, linenumber]
        else:
            caller = None
        log(msg=message, level = LOGERROR, caller=caller)
    except:
        pass



class Profiler(object):
    def __init__(self, file_path, sort_by='time', builtins=False):
        self._profiler = cProfile.Profile(builtins=builtins)
        self.file_path = file_path
        self.sort_by = sort_by

    def profile(self, f):
        def method_profile_on(*args, **kwargs):
            try:
                self._profiler.enable()
                result = self._profiler.runcall(f, *args, **kwargs)
                self._profiler.disable()
                return result
            except Exception as e:
                log('Profiler Error: %s' % (e), LOGWARNING)
                return f(*args, **kwargs)

        def method_profile_off(*args, **kwargs):
            return f(*args, **kwargs)

        if _is_debugging():
            return method_profile_on
        else:
            return method_profile_off

    def __del__(self):
        self.dump_stats()

    def dump_stats(self):
        if self._profiler is not None:
            s = StringIO()
            params = (self.sort_by,) if isinstance(self.sort_by, basestring) else self.sort_by
            ps = pstats.Stats(self._profiler, stream=s).sort_stats(*params)
            ps.print_stats()
            if self.file_path is not None:
                with open(self.file_path, 'w') as f:
                    f.write(s.getvalue())


def trace(method):
    def method_trace_on(*args, **kwargs):
        start = time.time()
        result = method(*args, **kwargs)
        end = time.time()
        log('{name!r} time: {time:2.4f}s args: |{args!r}| kwargs: |{kwargs!r}|'.format(name=method.__name__, time=end - start, args=args, kwargs=kwargs), LOGDEBUG)
        return result

    def method_trace_off(*args, **kwargs):
        return method(*args, **kwargs)

    if _is_debugging():
        return method_trace_on
    else:
        return method_trace_off


def _is_debugging():
    command = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.getSettings', 'params': {'filter': {'section': 'system', 'category': 'logging'}}}
    js_data = execute_jsonrpc(command)
    for item in js_data.get('result', {}).get('settings', {}):
        if item['id'] == 'debug.showloginfo':
            return item['value']
    return False


def execute_jsonrpc(command):
    if not isinstance(command, basestring):
        command = json.dumps(command)
    response = control.jsonrpc(command)
    return json.loads(response)
