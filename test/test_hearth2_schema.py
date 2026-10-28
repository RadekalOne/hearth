"""New-store lifecycle: catches accidental H1 writes and destructive migrations."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'mcp/memory'))
try:
    from hearth2.schema import Schema, SchemaError
except ImportError:
    Schema = None
    SchemaError = RuntimeError


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Schema, 'Hearth 2 schema is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'trial' / 'hearth2.sqlite3'

    def test_disabled_does_not_touch_filesystem(self):
        Schema.initialize(self.path, enabled=False)
        self.assertFalse(self.path.parent.exists())

    def test_initialize_is_idempotent_and_preserves_existing_rows(self):
        Schema.initialize(self.path, enabled=True)
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO projects VALUES('p','Project','idea',1,'{}')")
            original = db.execute('SELECT * FROM record_meta').fetchall()
        Schema.initialize(self.path, enabled=True)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT id,title FROM projects').fetchall(), [('p', 'Project')])
            self.assertEqual(db.execute('SELECT * FROM record_meta').fetchall(), original)
            self.assertEqual(db.execute('SELECT version FROM schema_migrations').fetchall(), [(1,)])

    def test_unknown_schema_and_changed_checksum_fail_closed(self):
        Schema.initialize(self.path, enabled=True)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE schema_migrations SET checksum='tampered'")
        with self.assertRaises(SchemaError):
            Schema.initialize(self.path, enabled=True)
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE schema_migrations SET version=2')
        with self.assertRaises(SchemaError):
            Schema.initialize(self.path, enabled=True)

    def test_foreign_database_is_never_adopted(self):
        self.path.parent.mkdir()
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE drawers(id TEXT PRIMARY KEY)')
        with self.assertRaises(SchemaError):
            Schema.initialize(self.path, enabled=True)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [('drawers',)])

    def test_empty_forward_backward_forward(self):
        Schema.initialize(self.path, enabled=True)
        Schema.migrate(self.path, 0, backup_path=self.path.with_suffix('.before'))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall(), [])
        Schema.initialize(self.path, enabled=True)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT version FROM schema_migrations').fetchone(), (1,))

    def test_nonempty_downgrade_refuses_data_loss_and_backup_is_usable(self):
        Schema.initialize(self.path, enabled=True)
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO projects VALUES('p','Keep this','idea',1,'{}')")
        backup = self.path.with_suffix('.before')
        with self.assertRaises(SchemaError):
            Schema.migrate(self.path, 0, backup_path=backup)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT title FROM projects').fetchone(), ('Keep this',))
        with sqlite3.connect(backup) as db:
            self.assertEqual(db.execute('SELECT title FROM projects').fetchone(), ('Keep this',))

    def test_failed_migration_does_not_publish_partial_schema(self):
        # A real SQLite authorization failure during DDL leaves no committed H2 tables.
        self.path.parent.mkdir()
        db = sqlite3.connect(self.path, isolation_level=None)
        calls = []
        def authorize(action, a, b, c, d):
            if action == sqlite3.SQLITE_CREATE_TABLE:
                calls.append(a)
                if a == 'runs':
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        db.set_authorizer(authorize)
        with self.assertRaises(sqlite3.DatabaseError):
            Schema.apply_initial(db)
        db.close()
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])
        self.assertIn('runs', calls)

if __name__ == '__main__':
    unittest.main()
