"""Durable credential types; removing enrollment never grants broader authority.

This security database is independent of the restorable work record. Only token
fingerprints are retained. Revocation and de-enrollment are terminal per token.
"""
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def fingerprint(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def expiry(value):
    if type(value) is not str:
        raise ValueError('expiry must be an explicit UTC timestamp')
    at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if at.tzinfo is None or at.utcoffset().total_seconds() != 0:
        raise ValueError('expiry must be an explicit UTC timestamp')
    return at.timestamp()


class SessionRegistry:
    def __init__(self, path):
        self.path = Path(path)
        self.marker = self.path.with_suffix('.required')
        self.seen = self.path.exists() or self.marker.exists()

    def connect(self, create=False):
        if (self.seen or self.marker.exists()) and not self.path.exists():
            raise RuntimeError('session credential registry missing')
        if not self.path.exists() and not create:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not self.path.exists()
        if fresh:
            with self.marker.open('x') as marker:
                marker.write('Durable session security state is required; do not reset.\n')
            self.marker.chmod(0o600)
        elif self.path.stat().st_size == 0:
            raise RuntimeError('session credential registry empty')
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        if fresh:
            self.path.chmod(0o600)
            db.execute('''CREATE TABLE credentials (
            digest TEXT PRIMARY KEY, session_id TEXT NOT NULL, principal_id TEXT NOT NULL,
            recipient TEXT NOT NULL, expires REAL, state TEXT NOT NULL,
            retired_by TEXT, retired_at TEXT)''')
        self.seen = True
        return db

    def rows(self):
        db = self.connect()
        if db is None:
            return []
        try:
            return db.execute('SELECT * FROM credentials').fetchall()
        finally:
            db.close()

    def subjects(self):
        return {row['principal_id'] for row in self.rows()}

    def owns_fingerprint(self, digest):
        return any(row['digest'] == digest for row in self.rows())

    def matches(self, token):
        hashes = {fingerprint(token), fingerprint(token.strip())} if token else set()
        return {row['principal_id'] for row in self.rows() if row['digest'] in hashes}

    def sync(self, sessions, tokens, expirations):
        db = self.connect(create=bool(sessions))
        if db is None:
            return tokens() if callable(tokens) else tokens
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                # Read the atomic token file under the registry write lock so a
                # delayed process cannot retire a newly rotated credential from
                # an older token-map snapshot.
                tokens = tokens() if callable(tokens) else tokens
                current = {}
                for key, target in sessions.items():
                    token = tokens.get(target.principal_id)
                    if type(token) is str and token:
                        digest = fingerprint(token)
                        if digest in current:
                            raise RuntimeError('ambiguous session credential')
                        current[digest] = (target, expiry(expirations[key]) if key in expirations else None)
                for row in db.execute('SELECT * FROM credentials').fetchall():
                    entry = current.get(row['digest'])
                    if entry is None or any(row[key] != getattr(entry[0], key)
                            for key in ('session_id', 'principal_id', 'recipient')):
                        db.execute("UPDATE credentials SET state='removed', retired_by='configuration', retired_at=? WHERE digest=? AND state='active'",
                            (datetime.now(timezone.utc).isoformat(), row['digest']))
                for digest, (target, until) in current.items():
                    db.execute("INSERT OR IGNORE INTO credentials VALUES (?,?,?,?,?,'active',NULL,NULL)",
                        (digest, target.session_id, target.principal_id, target.recipient, until))
                    if until is not None:
                        db.execute('UPDATE credentials SET expires=? WHERE digest=? AND (expires IS NULL OR expires>?)',
                            (until, digest, until))
                now=datetime.now(timezone.utc)
                db.execute("UPDATE credentials SET state='expired', retired_by='expiry', retired_at=? WHERE state='active' AND expires<=?",
                    (now.isoformat(),now.timestamp()))
            return tokens
        finally:
            db.close()

    def allowed(self, token, target):
        return any(row['digest'] == fingerprint(token) and row['state'] == 'active'
            and all(row[key] == getattr(target, key) for key in ('session_id', 'principal_id', 'recipient'))
            and (row['expires'] is None or datetime.now(timezone.utc).timestamp() < row['expires'])
            for row in self.rows())

    def revoke(self, session_id, actor):
        db = self.connect()
        if db is None:
            return {'session_id': session_id, 'revoked': 0}
        try:
            with db:
                count = db.execute("UPDATE credentials SET state='revoked', retired_by=?, retired_at=? WHERE session_id=? AND state='active'",
                    (actor, datetime.now(timezone.utc).isoformat(), session_id)).rowcount
            return {'session_id': session_id, 'revoked': count}
        finally:
            db.close()
