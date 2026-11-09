"""Private local receipt inbox. Content is stored as untrusted text, never executed."""
from contextlib import contextmanager
from dataclasses import asdict
import hashlib,json,os,sqlite3,stat
from pathlib import Path
from urllib.parse import urlsplit
from .delivery import NoticeSession


class SessionInboxError(ValueError):pass


def canonical_origin(value):
    try:
        if type(value) is not str or any(c.isspace() for c in value) or '?' in value or '#' in value:raise ValueError()
        url=urlsplit(value)
        if (url.scheme!='https' or not url.hostname or url.username is not None or url.password is not None
                or url.path not in ('','/') or url.query or url.fragment or '%' in url.netloc):raise ValueError()
        url.port
        return 'https://'+url.netloc.lower()
    except (ValueError,TypeError):raise SessionInboxError('a fixed HTTPS origin without credentials or path is required') from None


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


class SessionInbox:
    def __init__(self,path,origin,target):
        if type(target) is not NoticeSession:raise SessionInboxError('named-session enrollment required')
        self.path=Path(path);self.origin=canonical_origin(origin);self.target=target
        self.scope=encoded(dict(origin=self.origin,target=asdict(target)))
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        try:
            fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd);new=True
        except FileExistsError:new=False
        if self.path.is_symlink() or not stat.S_ISREG(self.path.stat().st_mode):raise SessionInboxError('private regular inbox file required')
        with self._db(initializing=new) as db:
            if new:
                db.execute('CREATE TABLE inbox_meta(version INTEGER NOT NULL,scope TEXT NOT NULL)')
                db.execute('INSERT INTO inbox_meta VALUES(1,?)',(self.scope,))
                db.execute('CREATE TABLE messages(notice_id TEXT PRIMARY KEY,digest TEXT NOT NULL,body TEXT NOT NULL,offer TEXT NOT NULL,receipt TEXT)')
            if db.execute('SELECT version,scope FROM inbox_meta').fetchall()!=[(1,self.scope)]:
                raise SessionInboxError('inbox origin or named-session scope differs')

    @contextmanager
    def _db(self,initializing=False):
        db=None
        try:
            db=sqlite3.connect(self.path,timeout=2,isolation_level=None)
            db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            if not initializing and db.execute('SELECT version,scope FROM inbox_meta').fetchall()!=[(1,self.scope)]:
                raise SessionInboxError('inbox origin or named-session scope differs')
            yield db;db.execute('COMMIT')
        except sqlite3.Error:raise SessionInboxError('local session inbox operation failed') from None
        finally:
            if db is not None:
                if db.in_transaction:db.execute('ROLLBACK')
                db.close()

    def store(self,offer):
        body=encoded(offer['notice']);digest=hashlib.sha256(body.encode()).hexdigest()
        if (offer['session_id']!=self.target.session_id or offer['recipient']!=self.target.recipient
                or offer['notice']['recipient']!=self.target.recipient or digest!=offer['notice_digest']):
            raise SessionInboxError('local notice scope or digest differs')
        with self._db() as db:
            prior=db.execute('SELECT digest,body,receipt FROM messages WHERE notice_id=?',(offer['notice']['id'],)).fetchone()
            if prior is not None:
                if prior[:2]!=(digest,body):raise SessionInboxError('local notice content conflict')
                if prior[2] is None:db.execute('UPDATE messages SET offer=? WHERE notice_id=?',(encoded(offer),offer['notice']['id']))
                return False
            db.execute('INSERT INTO messages VALUES(?,?,?,?,NULL)',(offer['notice']['id'],digest,body,encoded(offer)))
            return True

    def confirm(self,receipt):
        if (receipt['actor']!=self.target.principal_id or receipt['session_id']!=self.target.session_id
                or receipt['recipient']!=self.target.recipient):raise SessionInboxError('local receipt scope differs')
        with self._db() as db:
            prior=db.execute('SELECT digest,receipt FROM messages WHERE notice_id=?',(receipt['notice_id'],)).fetchone()
            if prior is None or prior[0]!=receipt['notice_digest']:raise SessionInboxError('local receipt content differs')
            value=encoded(receipt)
            if prior[1] is not None:
                if prior[1]!=value:raise SessionInboxError('local receipt conflict; original retained')
                return False
            db.execute('UPDATE messages SET receipt=? WHERE notice_id=?',(value,receipt['notice_id']))
            return True

    def pending(self):
        with self._db() as db:return [row[0] for row in db.execute('SELECT notice_id FROM messages WHERE receipt IS NULL ORDER BY rowid')]

    def records(self):
        with self._db() as db:
            return [dict(notice=json.loads(body),offer=json.loads(offer),receipt=json.loads(receipt) if receipt else None,
                delivery_state='receipt_recorded' if receipt else 'stored_unconfirmed',understanding_state='unknown')
                for body,offer,receipt in db.execute('SELECT body,offer,receipt FROM messages ORDER BY rowid')]
