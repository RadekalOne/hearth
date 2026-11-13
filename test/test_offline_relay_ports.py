"""Ports fail closed; real native-process acceptance is an explicit separate script."""
import importlib
from pathlib import Path
import sys
import unittest
import os
import subprocess
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'ops/hearth2'))


class PortTests(unittest.TestCase):
    def test_scheduler_success_is_mocked_not_a_live_write(self):
        import types
        with patch('offline_relay_ports.subprocess.run',return_value=types.SimpleNamespace(returncode=0)) as call:
            self.assertTrue(importlib.import_module('offline_relay_ports').HostPorts().disable())
            self.assertIn('Hearth-Codex-Offline-Relay',call.call_args.args[0][-1])
    def test_scheduler_timeout_is_unconfirmed_not_success(self):
        ports=importlib.import_module('offline_relay_ports').HostPorts()
        with patch('offline_relay_ports.subprocess.run',side_effect=subprocess.TimeoutExpired('scheduler',30)):
            self.assertIs(ports.disable(),False)

    def test_live_adapters_do_not_assume_account_or_launch_support(self):
        ports=importlib.import_module('offline_relay_ports').HostPorts()
        self.assertIs(ports.allowance()['included_only'],False)
        self.assertEqual(ports.allowance()['source'],'unavailable')
        with self.assertRaises(RuntimeError):ports.launch({'id':'a'*32})
        with self.assertRaises(RuntimeError):ports.poll()

    def test_trial_remote_command_rejects_untrusted_ids_or_operations(self):
        driver=importlib.import_module('offline_relay_ports').RemoteSandbox()
        for op,ident in [('launch','x;id'),('shell','a'*32),('stop','../other')]:
            with self.assertRaises(ValueError):driver.command(op,ident)
        command=driver.command('stop','a'*32)
        self.assertIn('root@179.236.82.242',command)
        self.assertNotIn('OPENAI_API_KEY',' '.join(command))


if __name__=='__main__':unittest.main()
