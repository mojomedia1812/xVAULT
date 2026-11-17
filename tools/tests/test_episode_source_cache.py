import ast
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import types
import unittest
from unittest.mock import Mock
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]


class EpisodeCacheTests(unittest.TestCase):
    def test_stable_sources_survive_mixed_volatile_rows_and_disk_reload(self):
        methods={'_sourceCacheFile','_readSourceCache','_writeSourceCache','_hasVolatileSourceUrls',
                 '_readSourceCachePayload','_writeSourceCachePayload','_normalizeSourceCachePayload','_sourceCacheKey'}
        tree=ast.parse((ROOT/'resources/lib/sources.py').read_text(encoding='utf8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='sources')
        cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in methods]
        props={}
        with tempfile.TemporaryDirectory() as folder:
            control=types.SimpleNamespace(dataPath=folder,addonVersion='test',getSetting=lambda k:'',
                window=types.SimpleNamespace(getProperty=lambda k:props.get(k,''),setProperty=props.__setitem__))
            scope=dict(control=control,log_utils=Mock(),os=os,time=time,json=json,hashlib=hashlib,urlparse=urlparse,
                       py2_decode=lambda v:v,SOURCE_CACHE_TTL=1800,SOURCE_CACHE_STALE_TTL=21600,
                       SOURCE_CACHE_LIMIT=60,SERIES_CACHE_LIMIT=200)
            exec(compile(ast.Module(body=[cls],type_ignores=[]),'sources.py','exec'),scope)
            p=scope['sources']();p.sourceCacheProperty='qa.cache';p.mediatype='tvshow';p.aliases=[]
            args=['Daryl Dixon',2023,'tt13062500',2,6,'Daryl Dixon','','Au Revoir Les Enfants','2024-11-03',[]]
            key=p._sourceCacheKey(*args)
            args[3]=1
            self.assertNotEqual(key,p._sourceCacheKey(*args))
            stable={'provider':'serienstream','url':'https://serienstream.to/serie/daryl/staffel-2/episode-6#xvault-link=123'}
            other={'provider':'megakino','url':'https://voe.sx/e/fixture'}
            volatile={'provider':'serienstream','url':'https://serienstream.to/r?t=old'}
            p._writeSourceCache(key,[stable,volatile,other])
            props.clear()
            q=scope['sources']();q.sourceCacheProperty='qa.cache'
            self.assertEqual(q._readSourceCache(key),([stable,other],False))
            payload=q._readSourceCachePayload()
            payload['entries'][key]['items'].append(volatile)
            q._writeSourceCachePayload(payload)
            self.assertEqual(q._readSourceCache(key),([stable,other],False))
            self.assertIsNone(q._readSourceCache('wrong-season')[0])


class MegakinoSeasonTests(unittest.TestCase):
    def scraper(self):
        tree=ast.parse((ROOT/'sites/megakino.py').read_text(encoding='utf8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        def parse(s,p):
            result=re.findall(p,s,re.S);return bool(result),result
        def single(s,p):
            m=re.search(p,s,re.S);return (True,m.group(1)) if m else (False,'')
        scope=dict(re=re,getSetting=lambda k,default='':default,SITE_IDENTIFIER='megakino',SITE_DOMAIN='fixture.invalid',
                   cleantitle=types.SimpleNamespace(get=lambda s:re.sub(r'\W','',s.lower())),
                   cParser=types.SimpleNamespace(parse=parse,parseSingleResult=single),
                   source_utils=types.SimpleNamespace(is_host_valid=lambda *a:(True,'VOE')))
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'megakino.py','exec'),scope)
        return scope['source']()

    def test_second_season_is_selected_even_when_first_and_third_are_listed_first(self):
        p=self.scraper();p.mediatype='tvshow'
        search=''.join('<a class="poster grid-item" href="/daryl-staffel-%d.html"><img alt="Daryl Dixon - Staffel %d"></a>'%(n,n) for n in [1,3,2])
        def get(url):
            if 'index.php' in url:return search
            return '<h1>Daryl Dixon - Staffel 2</h1><select id="ep6"><option value="https://voe.sx/e/s2e6">VOE</option></select>'
        p.get_html=get
        rows=p.run(['Daryl Dixon'],2023,2,6)
        self.assertEqual([r['url'] for r in rows],['https://voe.sx/e/s2e6'])

    def test_wrong_season_detail_page_is_rejected(self):
        p=self.scraper()
        p.get_html=lambda u:'<h1>Daryl Dixon - Staffel 1</h1><select id="ep6"><option value="https://voe.sx/e/s1e6">VOE</option></select>'
        p.get_sources('https://fixture.invalid/daryl-staffel-1.html',2023,2,6,None)
        self.assertEqual(p.sources,[])
        self.assertEqual(p._season_numbers('daryl-2024-staffel-2.html'),{2})


if __name__=='__main__':unittest.main()
