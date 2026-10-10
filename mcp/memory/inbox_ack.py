"""Human inbox snoozes bound to source revisions; no Matrix writes."""
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class StaleAcknowledgement(ValueError):
    pass


def identity(item):
    return item['kind'], item.get('id') or item['event_id']


def state_key(item):
    kind, key = identity(item)
    revision = (item.get('revision', 0), item.get('state'), item.get('receipt_source'),
                item.get('checkpoint_at'), item.get('latest_qualifying_event'), item.get('event_id'))
    return hashlib.sha256(json.dumps([kind,key,revision],sort_keys=True).encode()).hexdigest()


class Acknowledgements:
    def __init__(self,path):
        self.path=str(path)

    def connect(self):
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(self.path,timeout=15)
        db.executescript('''CREATE TABLE IF NOT EXISTS acknowledgements (
            kind TEXT, item_id TEXT, state_key TEXT, actor TEXT, at TEXT,
            PRIMARY KEY(kind,item_id));
            CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY,kind TEXT,item_id TEXT,state_key TEXT,actor TEXT,at TEXT,action TEXT);''')
        return db

    def project(self,items):
        # Reads of a new installation do not create a file or run migrations.
        rows={}
        if Path(self.path).exists():
            with closing(self.connect()) as db:
                rows={(r[0],r[1]):r for r in db.execute('SELECT kind,item_id,state_key,actor,at FROM acknowledgements')}
        result=[]
        for item in items:
            key=state_key(item);stored=rows.get(identity(item));active=bool(stored and stored[2]==key)
            result.append({**item,'state_key':key,'acknowledged':active,
                           'acknowledged_by':stored[3] if active else None,
                           'acknowledged_at':stored[4] if active else None})
        return result

    def set(self,item,key,actor,acknowledged):
        current=state_key(item)
        if not isinstance(key,str) or key!=current:
            raise StaleAcknowledgement('The item changed; refresh before acknowledging or reopening.')
        kind,item_id=identity(item)
        with closing(self.connect()) as db,db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT state_key FROM acknowledgements WHERE kind=? AND item_id=?',(kind,item_id)).fetchone()
            if (acknowledged and old and old[0]==key) or (not acknowledged and not old):
                return
            at=datetime.now(timezone.utc).isoformat()
            if acknowledged:
                db.execute('INSERT OR REPLACE INTO acknowledgements VALUES(?,?,?,?,?)',(kind,item_id,key,actor,at))
            else:
                db.execute('DELETE FROM acknowledgements WHERE kind=? AND item_id=?',(kind,item_id))
            db.execute('INSERT INTO audit(kind,item_id,state_key,actor,at,action) VALUES(?,?,?,?,?,?)',
                       (kind,item_id,key,actor,at,'acknowledge' if acknowledged else 'reopen'))

    def audit(self):
        if not Path(self.path).exists():return []
        with closing(self.connect()) as db:
            return list(db.execute('SELECT kind,item_id,state_key,actor,at,action FROM audit ORDER BY id'))
