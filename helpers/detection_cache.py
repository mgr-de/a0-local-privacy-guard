"""Process-local span cache: no original texts or original values."""
from collections import OrderedDict
import hashlib
import json
import os
import sys
import threading
import time
_salt = os.urandom(32)
def fingerprint(value):
    return hashlib.blake2b(value.encode(), key=_salt, digest_size=24).digest()
def configuration(value):
    return fingerprint(json.dumps(value, sort_keys=True, default=str))
class SpanCache:
    def __init__(self, limit=32*1024*1024, ttl=900, clock=time.monotonic):
        self.limit,self.ttl,self.clock=limit,ttl,clock
        self.items=OrderedDict();self.bytes=0;self.generation=0;self.lock=threading.RLock()
    def get(self,key):
        with self.lock:
            entry=self.items.get(key)
            if entry is None:return None
            created,spans,size=entry
            if self.clock()-created>=self.ttl:
                self.bytes-=size;del self.items[key];return None
            self.items.move_to_end(key);return spans
    def put(self,key,spans):
        spans=tuple(tuple(span) for span in spans)
        size=512+sum(sys.getsizeof(p) for p in key)+sum(128+sum(sys.getsizeof(p) for p in s) for s in spans)
        with self.lock:
            old=self.items.pop(key,None)
            if old:self.bytes-=old[2]
            if size>self.limit:return
            self.items[key]=(self.clock(),spans,size);self.bytes+=size
            while self.bytes>self.limit:
                _,(_,_,removed)=self.items.popitem(last=False);self.bytes-=removed
    def clear_scope(self,scope):
        with self.lock:
            self.generation+=1
            for key in list(self.items):
                if key[0]==scope:self.bytes-=self.items.pop(key)[2]
spans=SpanCache()
