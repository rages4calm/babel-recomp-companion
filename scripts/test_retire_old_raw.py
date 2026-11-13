"""ROM-free contracts and actual Windows unlink/lock tests; no owner fixtures."""
import os
import json
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(os.name == "nt", "Windows retirement helper")
class RawRetirementTests(unittest.TestCase):
    def setUp(self):
        project = Path(__file__).resolve().parents[1]
        parent = project / ".local/project-cleanup/disposable-20261112/raw-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name).resolve()
        assert self.root.is_relative_to(parent.resolve())
        (self.root / "scripts").mkdir()
        self.script = self.root / "scripts/retire_old_raw.ps1"
        shutil.copyfile(project / "scripts/retire_old_raw.ps1", self.script)
        (self.root / "HANDOFF.md").write_text("fake project")
        self.owner = self.root / "owner.sav"
        self.owner.write_bytes(b"owner data")

    def tearDown(self):
        self.temp.cleanup()

    def ps(self, code):
        return subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-Command", code],
                              capture_output=True, text=True, timeout=45)

    def contract(self, code):
        return self.ps(f"$ErrorActionPreference='Stop'; . {quote(self.script)}; {code}; Write-Output 'CONTRACT_OK'")

    def native(self, code):
        source = re.search(r"Add-Type @'\n(.*?)\n'@", self.script.read_text(), re.S)[1]
        return self.ps("$ErrorActionPreference='Stop'; Add-Type @'\n" + source + "\n'@\n" + code)

    def raw(self):
        p = self.root / ".local/batch-001/native-015/qualification-final/case/reference/snapshots/test.wram.bin"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"ROM-free raw fixture")
        return p

    def call(self, p, remove, file_id=None):
        s = p.stat()
        return (f"[GaiaRawRetirement]::Unlink({quote(p)},{quote(self.root)},"
                f"[uint64]{file_id if file_id is not None else s.st_ino},"
                f"[long]{s.st_size},[long]{s.st_mtime_ns},${str(remove).lower()})")

    def test_raw_relative_allowlist(self):
        prefix = ".local/batch-001/native-017/qualification-final/case/reference/"
        for rel in [prefix + "snapshots/a.wram.bin", prefix + "trace.csv", prefix + "final.ppm"]:
            r = self.contract(f"Assert-RawRelative {quote(rel)}")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_state_source_owner_traversal_and_other_batches_refused(self):
        prefix = ".local/batch-001/native-015/qualification-final/case/reference/"
        paths = [prefix + "saves/save0.sav", prefix + "receipt.json", prefix + "tier2-journal.jsonl",
                 prefix + "route.txt", prefix + "run.log", prefix + "rom.bin",
                 prefix + "inputs/a.ppm", prefix + "../outside.ppm",
                 prefix.replace("015", "018") + "final.ppm", "C:/owner/final.ppm"]
        code = "$bad=@(" + ",".join(quote(p) for p in paths) + "); foreach($p in $bad){try{Assert-RawRelative $p;throw 'ACCEPTED'}catch{if($_.Exception.Message -eq 'ACCEPTED'){throw}}}"
        r = self.contract(code)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_failed_partial_wrong_binary_and_string_pass_proofs_refused(self):
        docs = ["@{passed=$false;pairs=82;captures=164;complete=$true;binary_sha256='b'}",
                "@{passed=$true;pairs=81;captures=162;complete=$true;binary_sha256='b'}",
                "@{passed=$true;pairs=82;captures=164;complete=$false;binary_sha256='b'}",
                "@{passed=$true;pairs=82;captures=164;complete=$true;binary_sha256='wrong'}",
                "@{passed='true';pairs=82;captures=164;complete=$true;binary_sha256='b'}"]
        code = "$docs=@(" + ",".join(docs) + ");foreach($d in $docs){try{Assert-ProofSummary renderer82 $d b;throw 'ACCEPTED'}catch{if($_.Exception.Message -eq 'ACCEPTED'){throw}}}"
        r = self.contract(code)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.contract("Assert-ProofSummary renderer82 @{passed=$true;pairs=82;captures=164;complete=$true;binary_sha256='b'} b")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_missing_go_skips_without_deletion(self):
        p = self.raw()
        r = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(self.script)],
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Skipping", r.stdout)
        self.assertTrue(p.exists())
        # A hash-bound completion receipt is a conservative no-op, even if a
        # later fixture recreates a filename; it never silently deletes it again.
        store = self.root / ".local/project-cleanup/disposable-20261112"
        store.mkdir(parents=True)
        plan_hash = 'f7eceb57257047c58476093f0ac8817d113876af34f7cd414a43f38a8bb09d49'
        (store / 'RAW-RETIREMENT-GO.json').write_text('{}')
        closed = store / 'RAW-FINAL-RECEIPT.json'
        closed.write_text(json.dumps(dict(passed=True, raw_files_all_absent=True,
                                         removed_raw_files=34308, plan_sha256=plan_hash)))
        (store / 'RAW-RETIREMENT-COMPLETED.json').write_text(json.dumps(dict(
            schema='gaia verified raw retirement completion v1', plan_sha256=plan_hash,
            closeout_sha256=hashlib.sha256(closed.read_bytes()).hexdigest())))
        r = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(self.script)],
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('already completed', r.stdout)
        self.assertTrue(p.exists())

    def test_changed_plan_is_refused_after_marker(self):
        p = self.raw()
        store = self.root / ".local/project-cleanup/disposable-20261112"
        store.mkdir(parents=True)
        (store / "RAW-RETIREMENT-GO.json").write_text('{}')
        (store / "raw-retirement-plan.json").write_text('{}')
        r = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(self.script)],
                           capture_output=True, text=True, timeout=30)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("plan changed", r.stderr)
        self.assertTrue(p.exists())

    def test_actual_preview_wrong_identity_and_delete(self):
        p = self.raw()
        r = self.native("$r=" + self.call(p, False) + ";if($r.Status -ne 'preview'){throw 'preview'}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(p.exists())
        r = self.native(self.call(p, True, file_id=1))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("identity", r.stderr)
        self.assertTrue(p.exists())
        r = self.native("$r=" + self.call(p, True) + ";if($r.Status -ne 'removed'){throw 'not removed'}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(p.exists())
        self.assertEqual(self.owner.read_bytes(), b"owner data")

    def test_actual_hardlink_unlink_preserves_normal_file(self):
        p = self.raw()
        normal = self.root / "normal-track.pcm"
        os.link(p, normal)
        original = normal.read_bytes()
        r = self.native("$r=" + self.call(p, True) + ";if($r.Links -ne 2){throw 'link count'}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(p.exists())
        self.assertEqual(normal.read_bytes(), original)

    def test_actual_open_writer_is_retained(self):
        p = self.raw()
        with p.open("r+b"):
            r = self.native(self.call(p, True))
            self.assertNotEqual(r.returncode, 0)
            self.assertTrue(p.exists())

    def test_actual_junction_is_refused(self):
        outside = self.root / "outside-allowlist"
        outside.mkdir()
        sentinel = outside / "sentinel.bin"
        sentinel.write_bytes(b"keep")
        junction = self.root / "junction"
        made = self.ps(f"New-Item -ItemType Junction -Path {quote(junction)} -Target {quote(outside)}|Out-Null")
        self.assertEqual(made.returncode, 0, made.stderr)
        try:
            r = self.native(f"[GaiaRawRetirement]::Safe({quote(junction / 'sentinel.bin')},{quote(self.root)})")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("Reparse", r.stderr)
            self.assertEqual(sentinel.read_bytes(), b"keep")
        finally:
            os.rmdir(junction)


if __name__ == "__main__":
    unittest.main()
