"""Transactional, local, per-profile/chat mapping. No legacy type-token import."""
import hashlib
import json
import os
import re
import sqlite3
import time
import threading
import weakref
from contextlib import contextmanager
from pathlib import Path

TOKEN = re.compile(r"\[LPG_[a-f0-9]{16}_[A-Z_]+_\d+(?:_V\d+)?\]")


_TOKEN_PARTS = re.compile(r"\[LPG_([a-f0-9]{16})_[A-Z_]+_(\d+)(?:_V(\d+))?\]")


class TokenResolver:
    """Resolve a changed type only when namespace, ID and variant are unique.

    This is a local display/output recovery mechanism, never an input proof.
    Numeric IDs are not enough when a historical database is ambiguous.
    """
    def __init__(self, namespace, rows):
        self.known = {token: original for token, _, original in rows}
        self.identities = {}
        self.namespace = namespace
        for token in self.known:
            match = _TOKEN_PARTS.fullmatch(token)
            if match and match[1] == namespace:
                key = (match[2], match[3])
                candidates = self.identities.setdefault(key, set())
                candidates.add(token)

    def canonical(self, token):
        if token in self.known:
            return token
        match = _TOKEN_PARTS.fullmatch(token)
        if not match or match[1] != self.namespace:
            return token
        candidates = self.identities.get((match[2], match[3]), ())
        return next(iter(candidates)) if len(candidates) == 1 else token

    def canonicalize(self, text):
        return TOKEN.sub(lambda match: self.canonical(match.group()), text)

    def restore(self, text, *, recover_types=False):
        # Recover nested entries from older builds; bound recursion and cycles.
        seen = set()
        for _ in range(16):
            if text in seen:
                break
            seen.add(text)
            restored = TOKEN.sub(lambda match: self.known.get(
                (self.canonical(match.group()) if recover_types else match.group()), match.group()), text)
            if restored == text:
                break
            text = restored
        return text


_live = weakref.WeakSet()
_lock = threading.RLock()

class Mapping:
    def __init__(self, owner, chat, root=None):
        self.metrics={"sql_statements":0,"database_seconds":0.0}
        self.identity = json.dumps([*owner, str(chat)], ensure_ascii=False)
        self.namespace = hashlib.sha256(self.identity.encode()).hexdigest()[:16]
        if root is None:
            from helpers import files
            root = Path(files.get_abs_path(files.USER_DIR)) / "privacy-mappings"
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
        self.path = root / (self.namespace + ".sqlite")
        # Files are never selected from model/user-supplied paths.
        if self.path.is_symlink():
            raise ValueError("Privacy mapping path must not be a symbolic link.")
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS owner(identity TEXT PRIMARY KEY)")
            values = db.execute("SELECT identity FROM owner").fetchall()
            if values and values != [(self.identity,)]:
                raise ValueError("Privacy mapping belongs to another chat.")
            db.execute("INSERT OR IGNORE INTO owner VALUES (?)", (self.identity,))
            db.execute("CREATE TABLE IF NOT EXISTS mapping(token TEXT PRIMARY KEY, kind TEXT, original TEXT, UNIQUE(kind,original))")
            db.execute("CREATE TABLE IF NOT EXISTS revision(value INTEGER NOT NULL)")
            db.execute("INSERT INTO revision SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM revision)")
            db.execute("CREATE TRIGGER IF NOT EXISTS mapping_revision AFTER INSERT ON mapping BEGIN UPDATE revision SET value=value+1; END")
        os.chmod(self.path, 0o600)
        self._snapshot = None
        with _lock:_live.add(self)

    @contextmanager
    def connect(self):
        started=time.perf_counter()
        connection=sqlite3.connect(self.path, timeout=30)
        def counted(statement):self.metrics['sql_statements']+=1
        connection.set_trace_callback(counted)
        try:
            with connection:yield connection
        finally:
            connection.close()
            self.metrics['database_seconds']+=time.perf_counter()-started

    def entries(self):
        with self.connect() as db:
            return db.execute("SELECT token,kind,original FROM mapping ORDER BY length(original) DESC").fetchall()

    def snapshot(self):
        # One revision check per filter pass. Read rows in the same transaction.
        with _lock, self.connect() as db:
            db.execute('BEGIN')
            revision=db.execute('SELECT value FROM revision').fetchone()[0]
            if self._snapshot is None or self._snapshot[0]!=revision:
                self._snapshot=[revision,db.execute('SELECT token,kind,original FROM mapping ORDER BY length(original) DESC').fetchall()]
            return self._snapshot

    def token_many(self, values):
        result=[]
        with _lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for kind,value,canonical in values:
                kind=re.sub(r'[^A-Z_]', '_', kind.upper())
                row=db.execute('SELECT token FROM mapping WHERE kind=? AND original=?',(kind,value)).fetchone()
                if row:token=row[0]
                else:
                    number=db.execute('SELECT count(*) FROM mapping').fetchone()[0]+1
                    token=(re.sub(r'_V\d+(?=\])','',canonical)[:-1]+f'_V{number}]') if canonical else f'[LPG_{self.namespace}_{kind}_{number}]'
                    db.execute('INSERT INTO mapping VALUES (?,?,?)',(token,kind,value))
                result.append(token)
            revision=db.execute('SELECT value FROM revision').fetchone()[0]
            rows=db.execute('SELECT token,kind,original FROM mapping ORDER BY length(original) DESC').fetchall()
        # Publish only committed data to snapshots used by concurrent local passes.
        with _lock:
            for mapping in list(_live):
                if mapping.path==self.path and mapping._snapshot is not None and mapping._snapshot[0]<=revision:
                    mapping._snapshot[:]=[revision,rows]
        return result

    def token(self, kind, value, canonical=None):
        return self.token_many([(kind,value,canonical)])[0]

    def restore_many(self, texts, *, recover_types=False):
        resolver = TokenResolver(self.namespace, self.snapshot()[1])
        return [resolver.restore(text, recover_types=recover_types) for text in texts]

    def restore(self, text, *, recover_types=False):
        return self.restore_many([text], recover_types=recover_types)[0]
