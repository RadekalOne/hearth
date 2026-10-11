import importlib.util
import tempfile
import unittest
from pathlib import Path


class ReviewerStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        spec = importlib.util.spec_from_file_location('reviewer_fixture', Path(__file__).parents[1]/'mcp/memory/reviewers.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.path = Path(self.temp.name)/'reviewers.sqlite3'
        self.store = self.module.ReviewerStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_full_scope_namespace_and_no_read_migration(self):
        self.assertIsNone(self.store.authenticate('unknown'))
        self.assertFalse(self.path.exists())
        for scope in [None, '', {'wing':'personal'}]:
            with self.assertRaises(ValueError): self.store.provision('fixture', 'token-fixture', scope)
        for name in ['admin','codex','@rad:test','reviewer:codex']:
            with self.assertRaises(ValueError): self.store.provision(name,'token-fixture','full',reserved={'codex'})
        self.store.provision('external-review','fixture-secret','full')
        context=self.store.authenticate('fixture-secret')
        self.assertEqual((context.principal,context.role,context.scope),('reviewer:external-review','reviewer','full'))
        self.assertNotIn(b'fixture-secret',self.path.read_bytes())

    def test_exact_ttl_cross_worker_restart_and_revocation(self):
        self.store.provision('fixture','fixture-secret','full')
        context=self.store.authenticate('fixture-secret')
        cookie=self.store.session(context,now=100)
        other=self.module.ReviewerStore(self.path)
        self.assertIsNotNone(other.session_context(cookie,now=100+86400-1))
        self.assertIsNone(other.session_context(cookie,now=100+86400))
        cookie=self.store.session(context,now=100)
        other.revoke('fixture',actor='@rad:test',now=200)
        self.assertIsNone(self.store.authenticate('fixture-secret'))
        self.assertIsNone(self.store.session_context(cookie,now=201))
        self.assertIsNone(self.module.ReviewerStore(self.path).session_context(cookie,now=201))

    def test_audit_privacy_and_bounded_retention(self):
        self.store.provision('fixture','fixture-secret','full')
        with self.assertRaises(ValueError): self.store.audit('reviewer:fixture','/api/search?query=secret',now=0)
        with self.assertRaises(ValueError): self.store.audit('reviewer:fixture','drawer_secret',now=0)
        self.store.audit('reviewer:fixture','/api/search',now=0)
        self.store.audit('reviewer:fixture','/api/recent',now=31*86400)
        rows=self.store.audit_rows(now=31*86400)
        self.assertEqual(len(rows),1)
        self.assertEqual(set(rows[0]),{'principal','route','at'})
        self.assertEqual(rows[0]['route'],'/api/recent')

    def test_audit_read_expires_without_new_activity_and_caps_entries(self):
        from unittest.mock import patch
        self.store.audit('reviewer:fixture','/api/search',now=0)
        self.assertEqual(self.store.audit_rows(now=30*86400),[])
        with patch.object(self.module,'AUDIT_LIMIT',3):
            for now in range(1,6):self.store.audit('reviewer:fixture','/api/search',now=now)
        self.assertEqual([r['at'] for r in self.store.audit_rows(now=6)],[5,4,3])
        self.assertEqual(self.module.AUDIT_LIMIT,100000)
