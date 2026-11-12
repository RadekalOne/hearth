"""Private local crash-safe relay state. No credentials or model execution."""
from contextlib import contextmanager
import json
import hashlib
from pathlib import Path
import sqlite3
import uuid

ACTIVE=('claimed','dispatching','active','held')


class State:
    def __init__(self,path):
        self.path=Path(path).absolute();self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY CHECK(id=1),paused INTEGER NOT NULL,
 enabled INTEGER NOT NULL,epoch INTEGER NOT NULL,status TEXT NOT NULL,activation_at TEXT,last_check TEXT);
INSERT OR IGNORE INTO control VALUES(1,1,0,0,'paused',NULL,NULL);
CREATE TABLE IF NOT EXISTS aliases(alias TEXT PRIMARY KEY,work_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,work_id TEXT NOT NULL,generation INTEGER NOT NULL,
 state TEXT NOT NULL,epoch INTEGER NOT NULL,body TEXT NOT NULL,receipt TEXT,
 UNIQUE(work_id,generation));
CREATE UNIQUE INDEX IF NOT EXISTS one_active ON jobs((1))
 WHERE state IN ('claimed','dispatching','active','held');
CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,body TEXT NOT NULL,state TEXT NOT NULL,event_id TEXT);
''')

    def _open(self):
        db=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        db.row_factory=sqlite3.Row;return db

    @contextmanager
    def connect(self):
        db=self._open()
        try:yield db
        finally:db.close()

    @contextmanager
    def tx(self):
        db=self._open()
        try:
            db.execute('BEGIN IMMEDIATE');yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()

    def control(self):
        with self.connect() as db:return dict(db.execute('SELECT * FROM control WHERE id=1').fetchone())

    def tick(self,at,state):
        with self.tx() as db:db.execute('UPDATE control SET last_check=?,status=CASE WHEN paused=1 THEN status ELSE ? END WHERE id=1',(at,state))

    @staticmethod
    def _job(row):
        value=json.loads(row['body']);value.update(id=row['id'],state=row['state'],epoch=row['epoch'])
        value['receipt']=json.loads(row['receipt']) if row['receipt'] else None
        return value

    def jobs(self):
        with self.connect() as db:return [self._job(r) for r in db.execute('SELECT * FROM jobs ORDER BY rowid')]

    def claim(self,work):
        with self.tx() as db:
            control=db.execute('SELECT * FROM control WHERE id=1').fetchone()
            if control['paused'] or not control['enabled']:return None
            if db.execute("SELECT 1 FROM jobs WHERE state IN ('claimed','dispatching','active','held')").fetchone():return None
            aliases=sorted(set([work['work_id'],*work['aliases']]))
            for alias in aliases:
                old=db.execute('SELECT work_id FROM aliases WHERE alias=?',(alias,)).fetchone()
                if old and old['work_id']!=work['work_id']:return None
            if db.execute('SELECT 1 FROM jobs WHERE work_id=? AND generation=?',(work['work_id'],work['generation'])).fetchone():return None
            ident=uuid.uuid4().hex
            for alias in aliases:db.execute('INSERT OR IGNORE INTO aliases VALUES(?,?)',(alias,work['work_id']))
            body=json.dumps(work,sort_keys=True)
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,NULL)',(ident,work['work_id'],work['generation'],'claimed',control['epoch'],body))
            return {**work,'id':ident,'state':'claimed','epoch':control['epoch']}

    def dispatch(self,job):
        with self.tx() as db:
            c=db.execute('SELECT * FROM control WHERE id=1').fetchone()
            if c['paused'] or not c['enabled'] or c['epoch']!=job['epoch']:return False
            return db.execute("UPDATE jobs SET state='dispatching' WHERE id=? AND state='claimed' AND epoch=?",
                (job['id'],job['epoch'])).rowcount==1

    def finish(self,job,state,receipt,message):
        if state not in {'complete','blocked','held'}:raise ValueError('fixed terminal state required')
        with self.tx() as db:
            control=db.execute('SELECT * FROM control WHERE id=1').fetchone()
            if control['paused'] or control['epoch']!=job['epoch']:return False
            row=db.execute('SELECT state FROM jobs WHERE id=?',(job['id'],)).fetchone()
            if not row or row['state'] not in ACTIVE:return False
            db.execute('UPDATE jobs SET state=?,receipt=? WHERE id=?',(state,json.dumps(receipt,sort_keys=True),job['id']))
            db.execute("INSERT OR IGNORE INTO outbox VALUES(?,?,'pending',NULL)",(job['id'],message))
            return True

    def pause(self):
        with self.tx() as db:
            db.execute("UPDATE control SET paused=1,enabled=0,epoch=epoch+1,status='paused_pending_stop' WHERE id=1")
            return [self._job(r) for r in db.execute("SELECT * FROM jobs WHERE state IN ('claimed','dispatching','active','held')")]

    def paused_result(self,jobs,confirmed,scheduler_disabled=True):
        with self.tx() as db:
            for job in jobs:
                if confirmed.get(job['id']) is True:
                    db.execute("UPDATE jobs SET state='paused' WHERE id=?",(job['id'],))
            state='paused' if scheduler_disabled and all(confirmed.get(j['id']) is True for j in jobs) else 'paused_pending_stop'
            db.execute('UPDATE control SET status=? WHERE id=1',(state,))
            return state

    def notice(self,key,message):
        with self.tx() as db:db.execute("INSERT OR IGNORE INTO outbox VALUES(?,?,'pending',NULL)",(key,message))

    def outbox(self):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT * FROM outbox ORDER BY rowid')]

    def take_post(self):
        with self.tx() as db:
            row=db.execute("SELECT * FROM outbox WHERE state='pending' ORDER BY rowid LIMIT 1").fetchone()
            if not row:return None
            db.execute("UPDATE outbox SET state='uncertain' WHERE id=?",(row['id'],))
            return dict(row)

    def posted(self,ident,event):
        with self.tx() as db:db.execute("UPDATE outbox SET state='sent',event_id=? WHERE id=? AND state='uncertain'",(event,ident))

    def reconcile_post(self,ident,body_hash,event):
        with self.tx() as db:
            row=db.execute("SELECT * FROM outbox WHERE id=? AND state='uncertain'",(ident,)).fetchone()
            if not row or hashlib.sha256(row['body'].encode()).hexdigest()!=body_hash:return False
            db.execute("UPDATE outbox SET state='sent',event_id=? WHERE id=?",(event,ident));return True
