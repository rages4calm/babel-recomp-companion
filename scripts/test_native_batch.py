"""Resource guards exercised with synthetic child trees, never game inputs."""
from pathlib import Path
import sys
import tempfile
import unittest

from native_batch import bounded_run


class ResourceGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / "child.log"

    def run_child(self, code, timeout=5):
        return bounded_run([sys.executable, "-c", code], self.log, 128, timeout)

    def test_normal_child_is_released_after_guard_assignment(self):
        result = self.run_child('print("guarded synthetic child")')
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result["timed_out"])
        self.assertIn("guarded synthetic child", self.log.read_text())

    def test_timeout_stops_owned_child_tree(self):
        result = self.run_child(
            'import subprocess,sys,time\n'
            'subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])\n'
            'time.sleep(30)', timeout=0.5)
        self.assertEqual(result["exit_code"], 124)
        self.assertTrue(result["timed_out"])
        self.assertLess(result["wall_seconds"], 10)

    def test_memory_cap_rejects_large_child_allocation(self):
        result = self.run_child('data=bytearray(512*1024*1024); print(len(data))')
        self.assertNotEqual(result["exit_code"], 0)
        self.assertFalse(result["timed_out"])
        self.assertIn("MemoryError", self.log.read_text())

    def test_invalid_limits_do_not_launch_a_child(self):
        with self.assertRaises(ValueError):
            bounded_run(["does-not-exist"], self.log, 0, 1)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
