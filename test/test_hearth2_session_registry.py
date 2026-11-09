"""Durable security type and terminal session enrollment lifecycle."""
import tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from datetime import datetime,timezone,timedelta
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'mcp'/'memory'))
from hearth2.session_registry import SessionRegistry
from hearth2.delivery import NoticeSession

class SessionRegistryTests(unittest.TestCase):
    def test_restart_deenrollment_rotation_expiry_and_revocation_are_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sessions.sqlite3';target=NoticeSession('session','subject','claude')
            sessions={'session':target};tokens={'subject':'synthetic-secret'}
            registry=SessionRegistry(path);registry.sync(sessions,tokens,{})
            self.assertTrue(SessionRegistry(path).allowed('synthetic-secret',target))
            registry.sync({},tokens,{})
            registry=SessionRegistry(path);registry.sync(sessions,tokens,{})
            self.assertFalse(registry.allowed('synthetic-secret',target))
            self.assertEqual(registry.matches('synthetic-secret'),{'subject'})
            tokens={'subject':'fresh-secret'};registry.sync(sessions,tokens,{})
            self.assertTrue(registry.allowed('fresh-secret',target))
            registry.revoke('session','human')
            registry=SessionRegistry(path);registry.sync(sessions,tokens,{})
            self.assertFalse(registry.allowed('fresh-secret',target))
            tokens={'subject':'expired-secret'}
            registry.sync(sessions,tokens,{'session':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()})
            registry.sync(sessions,tokens,{})
            self.assertFalse(SessionRegistry(path).allowed('expired-secret',target))
            with patch('hearth2.session_registry.datetime') as clock:
                clock.now.return_value=datetime(2000,1,1,tzinfo=timezone.utc)
                self.assertFalse(SessionRegistry(path).allowed('expired-secret',target))
            self.assertEqual(registry.subjects(),{'subject'})

    def test_missing_registry_after_restart_and_rebinding_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sessions.sqlite3'
            dormant=SessionRegistry(path)
            target=NoticeSession('session','subject','claude')
            registry=SessionRegistry(path)
            registry.sync({'session':target},{'subject':'synthetic-secret'},{})
            rebound=NoticeSession('different','other','claude')
            registry.sync({'different':rebound},{'other':'synthetic-secret'},{})
            self.assertFalse(registry.allowed('synthetic-secret',rebound))
            self.assertEqual(registry.matches('synthetic-secret'),{'subject'})
            path.unlink()
            with self.assertRaises(RuntimeError):
                SessionRegistry(path).sync({'session':target},{'subject':'synthetic-secret'},{})
            with self.assertRaises(RuntimeError):
                dormant.subjects()
