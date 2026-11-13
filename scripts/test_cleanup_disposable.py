"""ROM-free guard tests for the fixed disposable allowlist (Windows only)."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.name == "nt", "Windows cleanup contract")
class DisposableCleanupTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(__file__).resolve().parents[1]
        parent = self.project / ".local/project-cleanup/disposable-20261112/tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name).resolve()
        assert self.root.is_relative_to(parent.resolve())
        (self.root / "scripts").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "HANDOFF.md").write_text("fake ROM-free project")
        (self.root / "docs/PROJECT-CLEANUP.md").write_text("fixture")
        shutil.copyfile(self.project / "scripts/cleanup_disposable.ps1",
                        self.root / "scripts/cleanup_disposable.ps1")
        shutil.copyfile(self.project / "scripts/cleanup_obsolete_objects.ps1",
                        self.root / "scripts/cleanup_obsolete_objects.ps1")
        self.prank = self.root / ".local/batch-001/native-018/classroom-preview/nightclub"
        self.prank.mkdir(parents=True)
        self.build = self.root / ".local/batch-001/native-018/build"
        self.build.mkdir()
        self.owner = self.root / "build/owner.sav"
        self.owner.parent.mkdir()
        self.owner.write_bytes(b"owner must survive")
        (self.build / "babel-classroom-preview-v18.exe").write_bytes(b"keep v18")

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, *args):
        return subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile",
                               "-ExecutionPolicy", "Bypass", "-File",
                               str(self.root / "scripts/cleanup_disposable.ps1"), *args],
                              capture_output=True, text=True, timeout=45)

    def test_preview_preserves_everything(self):
        target = self.prank / "prank.txt"
        target.write_text("disposable")
        result = self.run_script("-Preview")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(target.exists())
        self.assertEqual(self.owner.read_bytes(), b"owner must survive")

    def test_exact_allowlist_and_surviving_hardlink(self):
        normal = self.root / "build/normal.pcm"
        normal.write_bytes(b"normal soundtrack")
        os.link(normal, self.prank / "music.pcm")
        old = self.build / "babel-classroom-preview-v17.exe"
        old.write_bytes(b"old private experiment")
        diagnostic = self.build / "babel-owner-diagnostic-v1.exe"
        diagnostic.write_bytes(b"retired diagnostic")
        receipt = self.build / "retained-proof.json"
        receipt.write_text("retain")
        unrelated = self.build / "babel-recomp.exe"
        unrelated.write_bytes(b"master")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.prank.exists())
        self.assertFalse(old.exists())
        self.assertFalse(diagnostic.exists())
        self.assertEqual(receipt.read_text(), "retain")
        self.assertEqual(normal.read_bytes(), b"normal soundtrack")
        self.assertEqual(normal.stat().st_nlink, 1)
        self.assertEqual(unrelated.read_bytes(), b"master")
        self.assertEqual((self.build / "babel-classroom-preview-v18.exe").read_bytes(), b"keep v18")
        self.assertEqual(self.owner.read_bytes(), b"owner must survive")
        self.assertEqual(self.run_script().returncode, 0)  # idempotent leftovers retry

    def test_junction_is_refused_without_touching_destination(self):
        outside = self.root / "outside-allowlist"
        outside.mkdir()
        sentinel = outside / "owner.txt"
        sentinel.write_text("keep")
        junction = self.prank / "junction"
        command = f"New-Item -ItemType Junction -Path '{junction}' -Target '{outside}' | Out-Null"
        made = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                              capture_output=True, text=True)
        self.assertEqual(made.returncode, 0, made.stderr)
        try:
            result = self.run_script()
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("Reparse point refused", result.stdout)
            self.assertEqual(sentinel.read_text(), "keep")
        finally:
            # Remove only the fixture junction itself before TemporaryDirectory cleanup.
            os.rmdir(junction)

    def test_running_consumer_is_retained(self):
        target = self.prank / "data.txt"
        target.write_text("busy")
        consumer = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(40)",
                                     str(self.prank)], creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            result = self.run_script()
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertEqual(target.read_text(), "busy")
        finally:
            consumer.terminate()
            consumer.wait(timeout=10)

    def test_project_lease_refuses_concurrent_cleanup(self):
        import msvcrt
        target = self.prank / "data.txt"
        target.write_text("keep while leased")
        lease = self.root / ".local/project-cleanup/run.lock"
        lease.parent.mkdir(parents=True)
        with lease.open("w+b") as stream:
            stream.write(b"\0")
            stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                result = self.run_script()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("project lease", result.stdout + result.stderr)
                self.assertEqual(target.read_text(), "keep while leased")
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def test_object_cleanup_missing_or_changed_plan_cannot_delete(self):
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(self.root / "scripts/cleanup_obsolete_objects.ps1")]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plan = self.root / ".local/project-cleanup/disposable-20261112/obsolete-objects-proposal.json"
        plan.parent.mkdir(parents=True)
        plan.write_text('{}')
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Object plan changed", result.stdout + result.stderr)
        self.assertEqual(self.owner.read_bytes(), b"owner must survive")


if __name__ == "__main__":
    unittest.main()
