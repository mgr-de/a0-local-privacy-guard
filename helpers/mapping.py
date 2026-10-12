"""Transactional, local, per-profile/chat mapping. No legacy type-token import."""
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path

TOKEN = re.compile(r"\[LPG_[a-f0-9]{16}_[A-Z_]+_\d+(?:_V\d+)?\]")


class Mapping:
    def __init__(self, owner, chat, root=None):
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
        os.chmod(self.path, 0o600)

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def entries(self):
        with self.connect() as db:
            return db.execute("SELECT token,kind,original FROM mapping ORDER BY length(original) DESC").fetchall()

    def token(self, kind, value, canonical=None):
        kind = re.sub(r"[^A-Z_]", "_", kind.upper())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT token FROM mapping WHERE kind=? AND original=?", (kind,value)).fetchone()
            if row:
                return row[0]
            number = db.execute("SELECT count(*) FROM mapping").fetchone()[0] + 1
            token = (re.sub(r"_V\d+(?=\])", "", canonical)[:-1] + f"_V{number}]") if canonical else f"[LPG_{self.namespace}_{kind}_{number}]"
            db.execute("INSERT INTO mapping VALUES (?,?,?)", (token,kind,value))
            return token

    def restore(self, text):
        known = {token: original for token, _, original in self.entries()}
        # Recover nested entries made by older development builds; new filters
        # reject overlaps with existing tokens. Bound recursion and cycles.
        seen=set()
        for _ in range(16):
            if text in seen:break
            seen.add(text)
            restored=TOKEN.sub(lambda match: known.get(match.group(), match.group()), text)
            if restored==text:break
            text=restored
        return text
