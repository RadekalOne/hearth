"""Offline operator workflow runs in new processes without a service or credentials."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CLITests(unittest.TestCase):
    def test_init_export_restore_and_refused_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);database=root/'record.sqlite3';bundle=root/'record.json';target=root/'restored.sqlite3'
            env={**os.environ,'PYTHONPATH':str(Path(__file__).parents[1]/'mcp/memory')}
            def run(*args):return subprocess.run([sys.executable,'-m','hearth2',*args],env=env,capture_output=True,text=True)
            init=run('init','--database',str(database))
            self.assertEqual(init.returncode,0,init.stderr)
            self.assertEqual(run('export','--database',str(database),'--bundle',str(bundle)).returncode,0)
            refused=run('restore','--database',str(target),'--bundle',str(bundle))
            self.assertNotEqual(refused.returncode,0)
            self.assertFalse(target.exists())
            restored=run('restore','--database',str(target),'--bundle',str(bundle),'--controller-stopped')
            self.assertEqual(restored.returncode,0,restored.stderr)
            original=target.read_bytes()
            self.assertNotEqual(run('restore','--database',str(target),'--bundle',str(bundle),'--controller-stopped').returncode,0)
            self.assertEqual(target.read_bytes(),original)
