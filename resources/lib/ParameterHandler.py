
# Python 2/3
# 2023-03-11
import sys
#from urllib.parse import parse_qsl, urlsplit, unquote_plus, urlencode
from resources.lib.control import parse_qsl, urlsplit, unquote_plus, urlencode

class ParameterHandler:
    def __init__(self):
        params = dict()
        if len(sys.argv) >= 3 and len(sys.argv[2]) > 0:
            params = dict(parse_qsl(urlsplit(sys.argv[2]).query))
        self._params = params

    def getAllParameters(self):
        # returns all parameters as dictionary
        return self._params

    def getValue(self, paramName):
        # returns value of one parameter as string, if parameter does not exists "False" is returned
        if self.exist(paramName):
            return self._params[paramName]
            # paramValue = self._params[paramName]
            # return unquote_plus(paramValue)
        return False

    def exist(self, paramName):
        # checks if paramter with the name "paramName" exists
        return paramName in self._params

    def setParam(self, paramName, paramValue):
        # set the value of the parameter with the name "paramName" to "paramValue"
        # if there is no such parameter, the parameter is created
        # if no value is given "paramValue" is set "None"
        paramValue = str(paramValue)
        self._params.update({paramName: paramValue})

    def addParams(self, paramDict):
        # adds a whole dictionary {key1:value1,...,keyN:valueN} of parameters to the ParameterHandler
        # existing parameters are updated
        for key, value in paramDict.items():
            self._params.update({key: str(value)})

    def getParameterAsUri(self): # action
        outParams = dict()
        if 'params' in self._params:
            del self._params['params']
        if 'action' in self._params:
            del self._params['action']
        # if 'function' in self._params:
        #     del self._params['function']
        # if 'title' in self._params:
        #     del self._params['title']
        # if 'site' in self._params:
        #     del self._params['site']

        if len(self._params) > 0:
            for param in self._params:
                if len(self._params[param]) < 1:
                    continue
                outParams[param] = unquote_plus(self._params[param])
            return urlencode(outParams)
        return 'params=0'
