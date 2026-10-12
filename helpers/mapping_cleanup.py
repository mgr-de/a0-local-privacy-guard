"""Delete only plugin-owned SQLite mappings whose stored chat identity matches."""
import json
import hashlib
from pathlib import Path
import re
import sqlite3

def remove_chat(chat,root=None):
    if not isinstance(chat,str) or not chat or len(chat)>256:raise ValueError('Invalid chat identity.')
    if root is None:
        from helpers import files
        root=Path(files.get_abs_path(files.USER_DIR))/'privacy-mappings'
    root=Path(root)
    if root.is_symlink():raise ValueError('Privacy mapping directory is unsafe.')
    if not root.exists():return 0
    removed=0
    for path in root.glob('*.sqlite'):
        if path.is_symlink() or not re.fullmatch('[a-f0-9]{16}\\.sqlite',path.name):continue
        try:
            connection=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
            try:rows=connection.execute('SELECT identity FROM owner').fetchall()
            finally:connection.close()
            if len(rows)!=1:continue
            if hashlib.sha256(rows[0][0].encode()).hexdigest()[:16]!=path.stem:continue
            identity=json.loads(rows[0][0])
            if not isinstance(identity,list) or len(identity)!=3 or identity[-1]!=chat:continue
        except (sqlite3.Error,ValueError):continue
        targets=[Path(str(path)+suffix) for suffix in ('-wal','-shm','-journal','')]
        if any(target.is_symlink() for target in targets):raise ValueError('A privacy mapping sidecar is unsafe.')
        for target in targets:
            if target.exists():target.unlink()
        from usr.plugins.local_privacy_guard.helpers.detection_cache import spans
        spans.clear_scope(path.stem)
        removed+=1
    return removed
