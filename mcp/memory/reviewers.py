"""Isolated reviewer credentials, persistent sessions, and explicit read policy.

Provisioning is an operator action; importing or reading an empty store creates nothing.
Only explicit full-corpus scope is implemented. Limited scopes fail closed.
"""
import hashlib
import re
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import NamedTuple

TTL = 86400
RETENTION = 30 * TTL
AUDIT_LIMIT = 100000
REST_READS = frozenset({
    '/api/status','/api/export','/api/search','/api/recent','/api/taxonomy',
    '/api/drawer/{drawer_id}','/api/relays','/api/checkpoints','/api/agents',
    '/api/inbox','/api/surfaces','/api/surfaces/detail','/api/activity/event',
    '/api/timeline','/api/work','/api/work/agents','/api/dashboard/work',
    '/api/dashboard/memory-health','/api/work/tasks/{task_id}/context',
    '/api/work/communication','/api/coordination',
})
AUTH_ROUTES = frozenset({'/api/auth/status','/api/auth/login','/api/auth/logout'})
READ_TOOLS = frozenset({'memory_status','memory_bootstrap','memory_search',
    'memory_get','memory_get_many','diary_read','memory_checkpoint_read',
    'relay_inbox','coordination_state','work_board','work_context'})
READ_RESOURCES = frozenset({'hearth://bootstrap'})


class AuthContext(NamedTuple):
    principal: str
    role: str
    auth_kind: str
    scope: str
    credential_generation: int


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class ReviewerStore:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        db.executescript('''
            CREATE TABLE IF NOT EXISTS accounts (
              name TEXT PRIMARY KEY, credential_hash TEXT UNIQUE, generation INTEGER,
              enabled INTEGER, scope TEXT);
            CREATE TABLE IF NOT EXISTS sessions (
              hash TEXT PRIMARY KEY, name TEXT, generation INTEGER, expires REAL);
            CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, principal TEXT, route TEXT, at REAL);
        ''')
        return db

    def provision(self,name,credential,scope,*,reserved=()):
        if scope != 'full': raise ValueError('Only explicit full-corpus scope is supported')
        if not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9.-]{0,63}',name) or name in {'admin','anonymous'}|set(reserved):
            raise ValueError('Invalid or reserved reviewer name')
        if not isinstance(credential,str) or len(credential)<12: raise ValueError('Invalid reviewer credential')
        with closing(self.connect()) as db,db:
            db.execute('INSERT INTO accounts VALUES(?,?,1,1,?)',(name,digest(credential),scope))

    @staticmethod
    def context(row,kind):
        if row is None or not row['enabled'] or row['scope']!='full': return None
        return AuthContext('reviewer:'+row['name'],'reviewer',kind,row['scope'],row['generation'])

    def owns_credential(self,credential):
        if not credential or not self.path.exists(): return False
        with closing(self.connect()) as db:
            return db.execute("SELECT 1 FROM accounts WHERE credential_hash=?",(digest(credential),)).fetchone() is not None

    def authenticate(self,credential):
        if not credential or not self.path.exists(): return None
        with closing(self.connect()) as db:
            return self.context(db.execute('SELECT * FROM accounts WHERE credential_hash=?',(digest(credential),)).fetchone(),'reviewer_bearer')

    def session(self,context,*,now=None):
        now=time.time() if now is None else now
        cookie=secrets.token_urlsafe(32)
        with closing(self.connect()) as db,db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM accounts WHERE name=?',(context.principal.removeprefix('reviewer:'),)).fetchone()
            current=self.context(row,'reviewer_session')
            if current is None or current.credential_generation!=context.credential_generation: raise ValueError('Reviewer revoked')
            db.execute('DELETE FROM sessions WHERE expires<=?',(now,))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(cookie),row['name'],row['generation'],now+TTL))
        return cookie

    def session_context(self,cookie,*,now=None):
        if not cookie or not self.path.exists(): return None
        now=time.time() if now is None else now
        with closing(self.connect()) as db:
            row=db.execute('''SELECT a.* FROM accounts a JOIN sessions s ON a.name=s.name
                WHERE s.hash=? AND s.expires>? AND a.generation=s.generation''',(digest(cookie),now)).fetchone()
            return self.context(row,'reviewer_session')

    def logout(self,cookie):
        if self.path.exists():
            with closing(self.connect()) as db,db: db.execute('DELETE FROM sessions WHERE hash=?',(digest(cookie),))

    @staticmethod
    def append_audit(db,principal,route,now):
        # Only policy-normalized route names, never queries or record identifiers.
        if route not in REST_READS|AUTH_ROUTES|{'reviewer/revoke'}: raise ValueError('Audit route is not normalized')
        db.execute('DELETE FROM audit WHERE at<?',(now-RETENTION,))
        db.execute('INSERT INTO audit(principal,route,at) VALUES(?,?,?)',(principal,route,now))
        db.execute('DELETE FROM audit WHERE id NOT IN (SELECT id FROM audit ORDER BY id DESC LIMIT ?)',(AUDIT_LIMIT,))

    def audit(self,principal,route,*,now=None):
        with closing(self.connect()) as db,db:
            self.append_audit(db,principal,route,time.time() if now is None else now)

    def audit_rows(self,*,now=None):
        if not self.path.exists(): return []
        with closing(self.connect()) as db,db:
            db.execute('DELETE FROM audit WHERE at<=?',((time.time() if now is None else now)-RETENTION,))
            return [dict(r) for r in db.execute('SELECT principal,route,at FROM audit ORDER BY id DESC')]

    def accounts(self):
        if not self.path.exists(): return []
        with closing(self.connect()) as db:
            return [dict(r) for r in db.execute('SELECT name,scope,generation,enabled FROM accounts ORDER BY name')]

    def revoke(self,name,*,actor,now=None):
        with closing(self.connect()) as db,db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute('UPDATE accounts SET enabled=0,generation=generation+1 WHERE name=?',(name,)).rowcount
            if not changed: raise ValueError('Reviewer account not found')
            db.execute('DELETE FROM sessions WHERE name=?',(name,))
            self.append_audit(db,actor,'reviewer/revoke',time.time() if now is None else now)


def rest_allowed(method,route):
    return (method=='GET' and route in REST_READS|{'/api/auth/status'}) or (method=='POST' and route in {'/api/auth/login','/api/auth/logout'})


def mcp_allowed(method,params):
    params=params or {}
    if method=='tools/call': return params.get('name') in READ_TOOLS
    if method=='resources/read': return params.get('uri') in READ_RESOURCES
    return method in {'initialize','ping','tools/list','resources/list','resources/templates/list','notifications/initialized','notifications/cancelled'}
