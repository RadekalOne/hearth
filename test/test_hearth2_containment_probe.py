"""Regression for observer evidence; the privileged kernel boundary is simulated."""
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'containment_probe', Path(__file__).parent / 'fixtures/hearth2_containment_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ObserverEvidenceTests(unittest.TestCase):
    def test_observer_inside_live_workload_is_refused_before_termination(self):
        # The old check read an empty group after termination and falsely passed.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            group = base / 'hearth2-fixture-test'
            mkdir, rmdir = type(group).mkdir, type(group).rmdir
            terminated = []

            def create(path, *args, **kwargs):
                mkdir(path, *args, **kwargs)
                if path == group:
                    (path / 'cgroup.kill').write_text('')
                    (path / 'cgroup.events').write_text('populated 1\n')
                    (path / 'cgroup.procs').write_text(str(os.getpid()) + '\n')

            def remove(path):
                for item in path.iterdir():
                    item.unlink()
                rmdir(path)

            class Process:
                stdout = io.StringIO('CHILD_READY\n')

                def send_signal(self, sig):
                    terminated.append(sig)

                def wait(self, timeout):
                    (group / 'cgroup.events').write_text('populated 0\n')
                    (group / 'cgroup.procs').write_text('')
                    return 0

            # Model cleanup after cgroup.kill without requiring root/cgroup mounts.
            def empty(path):
                (path / 'cgroup.events').write_text('populated 0\n')
                (path / 'cgroup.procs').write_text('')

            with (patch.object(probe, 'Path', return_value=base),
                  patch.object(type(group), 'mkdir', create),
                  patch.object(type(group), 'rmdir', remove),
                  patch.object(probe.subprocess, 'Popen', return_value=Process()),
                  patch('select.select', return_value=([True], [], [])),
                  patch.object(probe, 'wait_empty', side_effect=empty)):
                with self.assertRaisesRegex(AssertionError, 'observer'):
                    probe.process_probe('parent', 'test')
            self.assertEqual(terminated, [], 'must reject before signaling the workload')
            self.assertFalse(group.exists(), 'fixture cleanup must still run')


if __name__ == '__main__':
    unittest.main()
