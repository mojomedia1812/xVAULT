

"""
SimplePlugin micro-framework for Kodi content plugins
**License**: `GPL v.3 <https://www.gnu.org/copyleft/gpl.html>`_
"""

import os,sys
import time
import hashlib
import pickle
from copy import deepcopy
import xbmc, xbmcvfs

if sys.version_info.major == 3:
    from collections.abc import MutableMapping
else:
    from collections import MutableMapping


class _Storage(MutableMapping):
    """
    Storage(storage_dir, filename='storage.pcl')

    Persistent storage for arbitrary data with a dictionary-like interface

    It is designed as a context manager and better be used
    with 'with' statement.

    :param storage_dir: directory for storage
    :type storage_dir: str
    :param filename: the name of a storage file (optional)
    :type filename: str

    Usage::

        with Storage('/foo/bar/storage/') as storage:
            storage['key1'] = value1
            value2 = storage['key2']

    .. note:: After exiting :keyword:`with` block a :class:`Storage` instance
        is invalidated. Storage contents are saved to disk only for
        a new storage or if the contents have been changed.
    """
    def __init__(self, storage_dir, filename='storage.pcl'):
        """
        Class constructor

        :type storage_dir: str
        :type filename: str
        """
        # insert by kasi
        name, ext = os.path.splitext(filename)
        if not ext:
            ext = '.pcl'
            filename = name + ext

        self._storage = {}
        self._hash = None
        self._filename = os.path.join(storage_dir, filename)

        try:
            with open(self._filename, 'rb') as fo:
                contents = fo.read()
            self._storage = pickle.loads(contents)
            self._hash = hashlib.md5(contents).hexdigest()
        except (IOError, pickle.PickleError, EOFError, AttributeError):
            pass

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        self.flush()

    def __getitem__(self, key):
        return self._storage[key]

    def __setitem__(self, key, value):
        self._storage[key] = value

    def __delitem__(self, key):
        del self._storage[key]

    def __iter__(self):
        return iter(self._storage)

    def __len__(self):
        return len(self._storage)

    def __str__(self):
        return '<Storage {0}>'.format(self._storage)

    def flush(self):
        """
        Save storage contents to disk

        This method saves new and changed :class:`Storage` contents to disk
        and invalidates the Storage instance. Unchanged Storage is not saved
        but simply invalidated.
        """
        contents = pickle.dumps(self._storage, protocol=2)
        if self._hash is None or hashlib.md5(contents).hexdigest() != self._hash:
            tmp = self._filename + '.tmp'
            start = time.time()
            while os.path.exists(tmp):
                if time.time() - start > 2.0:
                    raise TimeoutError(
                        'Exceeded timeout for saving {0} contents!'.format(self)
                    )
                xbmc.sleep(100)
            try:
                with open(tmp, 'wb') as fo:
                    fo.write(contents)
                    try:
                        fo.flush()
                        os.fsync(fo.fileno())
                    except OSError:
                        pass
                _replace_file(tmp, self._filename)
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        del self._storage

    def copy(self):
        """
        Make a copy of storage contents

        .. note:: this method performs a *deep* copy operation.

        :return: a copy of storage contents
        :rtype: dict
        """
        return deepcopy(self._storage)

def _py2_decode(s, encoding='utf-8'):
    """
    Decode Python 2 ``str`` to ``unicode``
    In Python 3 the string is not changed.
    """
    if sys.version_info.major == 2 and isinstance(s, bytes):
        s = s.decode(encoding)
    return s


def _replace_file(source, destination):
    for attempt in range(50):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt >= 49:
                raise
            time.sleep(0.05)

def _get_storage(filename='storage.pcl'):
    """
    Get a persistent :class:`Storage` instance for storing arbitrary values
    between addon calls.
    A :class:`Storage` instance can be used as a context manager.
    Example::

        with plugin.get_storage() as storage:
            storage['param1'] = value1
            value2 = storage['param2']

    .. note:: After exiting :keyword:`with` block a :class:`Storage`
        instance is invalidated.

    :param filename: the name of a storage file (optional)
    :type filename: str
    :return: Storage object
    :rtype: Storage
    """
    import xbmcaddon
    addon = xbmcaddon.Addon()
    try:
        _profile_dir = _py2_decode(xbmcvfs.translatePath(addon.getAddonInfo('profile')))
    finally:
        del addon

    return _Storage(_profile_dir, filename)


def _get_queries(storage):
    queries = storage.get('queries', [])
    if not isinstance(queries, list):
        queries = []
    clean_queries = []
    for item in queries:
        if not isinstance(item, dict) or 'idFile' not in item:
            continue
        clean_queries.append({
            'idFile': item.get('idFile'),
            'time': item.get('time', '')
        })
    storage['queries'] = clean_queries
    return clean_queries


def save_query(idFile, timeInSeconds, filename=None):
    with _get_storage(filename) as storage:
        queries = _get_queries(storage)
        entry = {
            'idFile': idFile,
            'time': timeInSeconds
        }
        storage['queries'] = [item for item in queries if item.get('idFile') != idFile]
        storage['queries'].insert(0, entry)


def remove_query(idFile, filename=None):
    with _get_storage(filename) as storage:
        queries = _get_queries(storage)
        storage['queries'] = [item for item in queries if item.get('idFile') != idFile]


def get_query(idFile, filename=None):
    with _get_storage(filename) as storage:
        for item in _get_queries(storage):
            if item.get('idFile') == idFile:
                return [idFile, item.get('time')]
    return []



#
# def getSearchTerms(filename=None):
#     with _get_storage(filename) as storage:
#         if 'queries' not in storage:
#             storage['queries'] = []
#         return storage['queries']

