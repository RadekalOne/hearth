"""A failed Docker daemon query is not evidence that a workload is absent."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('native_probe',
    Path(__file__).parent/'fixtures/hearth2_native_policy_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


class CleanupEvidenceTests(unittest.TestCase):
    def fixture(self):
        process=probe.NativeProcess.__new__(probe.NativeProcess)
        process.name='hearth2-native-policy-fixture'
        process.process=Mock();process.process.stdin.closed=True
        process.process.poll.return_value=0
        process.selector=Mock();process.log=Mock();process.cleanup_verified=False
        return process

    def test_unreachable_daemon_never_counts_as_verified_cleanup(self):
        process=self.fixture()
        unavailable=subprocess.CompletedProcess([],1,stdout='',stderr='Cannot connect to the Docker daemon')
        with patch.object(probe.subprocess,'run',return_value=unavailable):
            with self.assertRaises(RuntimeError):process.close()
        self.assertFalse(process.cleanup_verified)

    def test_automatic_removal_race_requires_a_successful_absent_inventory(self):
        process=self.fixture()
        responses=[subprocess.CompletedProcess([],0,stdout=process.name+'\n',stderr=''),
                   subprocess.CompletedProcess([],0,stdout=process.name+'\n',stderr=''),
                   subprocess.CompletedProcess([],1,stdout='',stderr='No such container'),
                   subprocess.CompletedProcess([],0,stdout='',stderr='')]
        with patch.object(probe.subprocess,'run',side_effect=responses):process.close()
        self.assertTrue(process.cleanup_verified)

    def test_remaining_named_container_never_counts_as_cleaned_up(self):
        process=self.fixture()
        responses=[subprocess.CompletedProcess([],0,stdout=process.name+'\n',stderr=''),
                   subprocess.CompletedProcess([],0,stdout=process.name+'\n',stderr=''),
                   subprocess.CompletedProcess([],1,stdout='',stderr='Removal failed'),
                   subprocess.CompletedProcess([],0,stdout=process.name+'\n',stderr='')]
        with patch.object(probe.subprocess,'run',side_effect=responses):
            with self.assertRaises(RuntimeError):process.close()
        self.assertFalse(process.cleanup_verified)


if __name__ == '__main__':unittest.main()
