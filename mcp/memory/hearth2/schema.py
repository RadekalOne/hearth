"""Explicit, transactional migrations for the separate trial work record.

No production/Hearth 1 paths are inferred. Empty schema rollback is supported;
nonempty rollback uses an operator's preserved pre-migration database instead.
"""
import hashlib
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS = Path(__file__).with_name('migrations')
UP = (MIGRATIONS / '001_initial.up.sql').read_text()
DOWN = (MIGRATIONS / '001_initial.down.sql').read_text()
CHECKSUM = hashlib.sha256(UP.encode()).hexdigest()
TABLES = ('projects', 'plans', 'tasks', 'dependencies', 'role_grants', 'claims',
          'runs', 'decisions', 'notices', 'incidents', 'incident_attempts',
          'scorecard_events', 'audit_events')


class SchemaError(ValueError):
    pass


def statements(sql):
    """Preserve transaction ownership; executescript would implicitly commit."""
    pending = ''
    for line in sql.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            yield pending
            pending = ''
    if pending.strip():
        raise SchemaError('incomplete migration statement')


def open_existing(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=rw', uri=True,
                         timeout=15, isolation_level=None)
    db.execute('PRAGMA foreign_keys=ON')
    return db


def exclusive_file(path):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)


class Schema:
    @staticmethod
    def validate(db):
        try:
            versions = db.execute('SELECT version,checksum FROM schema_migrations').fetchall()
            if versions != [(1, CHECKSUM)]:
                raise SchemaError('unsupported schema version or migration checksum')
            if db.execute('SELECT schema_version FROM record_meta WHERE id=1').fetchone() != (1,):
                raise SchemaError('invalid record metadata')
            actual = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not set(TABLES + ('record_meta', 'schema_migrations')).issubset(actual):
                raise SchemaError('incomplete schema')
        except sqlite3.DatabaseError as error:
            raise SchemaError('not a valid Hearth 2 database') from error

    @staticmethod
    def apply_initial(db):
        if db.in_transaction:
            raise SchemaError('migration requires exclusive transaction ownership')
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        try:
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            if tables:
                if 'schema_migrations' not in tables:
                    raise SchemaError('refusing to adopt a foreign database')
                Schema.validate(db)
            else:
                for statement in statements(UP):
                    db.execute(statement)
                stamp = datetime.now(timezone.utc).isoformat()
                db.execute('INSERT INTO schema_migrations VALUES(1,?,?)', (CHECKSUM, stamp))
                db.execute('INSERT INTO record_meta VALUES(1,?,?,1)', (uuid.uuid4().hex, uuid.uuid4().hex))
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise

    @staticmethod
    def initialize(path: Path, *, enabled: bool):
        if not enabled:
            return
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            exclusive_file(path)
        except FileExistsError:
            pass
        with closing(open_existing(path)) as db:
            Schema.apply_initial(db)

    @staticmethod
    def migrate(path: Path, target: int, *, backup_path: Path):
        if type(target) is not int or target not in (0, 1):
            raise SchemaError('unsupported migration target')
        path, backup_path = Path(path), Path(backup_path)
        if path.resolve() == backup_path.resolve():
            raise SchemaError('backup must be a separate new path')
        with closing(open_existing(path)) as db:
            Schema.validate(db)
            exclusive_file(backup_path)
            with closing(sqlite3.connect(backup_path)) as backup:
                db.backup(backup)
            if target == 1:
                return
            db.execute('BEGIN IMMEDIATE')
            try:
                if any(db.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone() for table in TABLES):
                    raise SchemaError('nonempty downgrade refused; restore the preserved pre-migration backup while stopped')
                for statement in statements(DOWN):
                    db.execute(statement)
                db.execute('COMMIT')
            except BaseException:
                if db.in_transaction:
                    db.execute('ROLLBACK')
                raise
