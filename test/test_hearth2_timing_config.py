"""Default-off timing parsing, without importing a provider or full service."""
import tempfile
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.api import Runtime


class FakeApp:
    def get(self, *args, **kwargs): return lambda method: method
    post = get


class TimingConfigTests(unittest.TestCase):
    def runtime(self, path, enabled, timing):
        return Runtime(FakeApp(), enabled=enabled, data_dir=path, principal=lambda:'admin',
            typed_auth=lambda:None, same_origin=lambda r:True, bearer_principal=lambda r:'controller',
            human_ids=['admin'],controller_ids=['controller'],worker_ids=[],authenticated=True,timing=timing)

    def test_default_off_does_not_parse_invalid_timing_or_create_database(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime=self.runtime(directory,False,{'lease_seconds':'invalid'})
            runtime.initialize()
            self.assertFalse(Path(directory,'hearth2.sqlite3').exists())

    def test_enabled_parses_short_timings_and_fails_before_database_on_invalid_value(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime=self.runtime(directory,True,{'lease_seconds':'5','deadline_seconds':'15'})
            runtime.initialize()
            self.assertEqual((runtime.store.lease_seconds,runtime.store.deadline_seconds),(5,15))
        for value in ['0','-1','1.5','true','7201','',None]:
            with self.subTest(value=value),tempfile.TemporaryDirectory() as directory:
                runtime=self.runtime(directory,True,{'lease_seconds':value})
                with self.assertRaises(RuntimeError):runtime.initialize()
                self.assertFalse(Path(directory,'hearth2.sqlite3').exists())
