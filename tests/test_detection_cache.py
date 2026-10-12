import concurrent.futures
from types import SimpleNamespace
import pytest
from usr.plugins.local_privacy_guard.helpers import pii_detector as pd
from usr.plugins.local_privacy_guard.helpers.detection_cache import SpanCache, spans, fingerprint
from usr.plugins.local_privacy_guard.helpers.mapping import Mapping

class NLP:
    meta={'version':'test'}
    def __init__(self):self.calls=[]
    def pipe(self,texts,batch_size=32):
        for text in texts:
            self.calls.append(text)
            ents=[SimpleNamespace(start_char=0,end_char=len(text),text=text,label_='PERSON')] if text.startswith('Anna') else []
            yield SimpleNamespace(ents=ents)

def scanner(monkeypatch,scope='cache-test',**changes):
    nlp=NLP();monkeypatch.setattr(pd,'_get_nlp',lambda lang:nlp)
    spans.clear_scope(scope)
    return pd.PIIFilter({'use_regex':False,'languages':['en'],'_cache_scope':scope,**changes}),nlp

def test_units_reused_independent_of_neighbor(monkeypatch):
    filt,nlp=scanner(monkeypatch)
    first=filt.filter('Anna Weber\nplain text')
    second=filt.filter('different neighbor\nAnna Weber')
    assert nlp.calls==['Anna Weber','plain text','different neighbor']
    assert second.detections[0].original=='Anna Weber'
    assert second.detections[0].start==len('different neighbor\n')
    assert filt.metrics['cache_hits']==1
    assert first.filtered_text=='<PERSON>\nplain text'

def test_negative_cache_and_model_change(monkeypatch):
    filt,nlp=scanner(monkeypatch)
    filt.filter('plain');filt.filter('plain')
    assert nlp.calls==['plain']
    nlp.meta={'version':'changed'};filt.filter('plain')
    assert nlp.calls==['plain','plain']

def test_cache_keeps_no_originals(monkeypatch):
    filt,nlp=scanner(monkeypatch)
    filt.filter('Anna Weber')
    entries=[(key,value) for key,value in spans.items.items() if key[0]=='cache-test']
    assert 'Anna Weber' not in repr(entries)
    assert '<PERSON>' not in repr(entries)

def test_ttl_lru_and_scope_deletion():
    now=[0];cache=SpanCache(limit=1400,ttl=10,clock=lambda:now[0])
    a=('A',fingerprint('one'));b=('B',fingerprint('two'))
    cache.put(a,());assert cache.get(a)==()
    now[0]=10;assert cache.get(a) is None
    cache.put(a,());cache.put(b,());cache.clear_scope('A')
    assert cache.get(a) is None and cache.get(b)==()
    for i in range(30):cache.put(('B',str(i)),())
    assert cache.bytes<=cache.limit and len(cache.items)<30

def test_mapping_snapshots_follow_local_commit(tmp_path):
    a=Mapping(('','test'),'one',tmp_path);b=Mapping(('','test'),'one',tmp_path)
    before=a.snapshot();assert before[1]==[]
    token=b.token('PERSON','Anna Weber')
    assert before[1]==[(token,'PERSON','Anna Weber')]
    assert a.snapshot()[0]==1

def test_concurrent_atomic_batch_identity(tmp_path):
    def allocate(i):
        mapping=Mapping(('','test'),'same',tmp_path)
        return mapping.token_many([('PERSON','Anna Weber',None),('PERSON',f'Person {i}',None)])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(allocate,range(16)))
    assert len({row[0] for row in rows})==1
    entries=Mapping(('','test'),'same',tmp_path).entries()
    assert len(entries)==17 and len({x[0] for x in entries})==17

def test_cross_process_revision_refresh(tmp_path):
    import subprocess,sys
    mapping=Mapping(('','test'),'other-process',tmp_path);old=mapping.snapshot()
    subprocess.run([sys.executable,'-c',"import sqlite3;d=sqlite3.connect(__import__('sys').argv[1]);d.execute(\"INSERT INTO mapping VALUES ('synthetic','PERSON','Anna Weber')\");d.commit()",str(mapping.path)],check=True)
    assert old[1]==[]
    assert mapping.snapshot()[1][0][0]=='synthetic'
