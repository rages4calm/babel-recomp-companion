"""Synthetic temporary workspaces only: never compact real project fixtures."""
import json
import contextlib
import io
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import project_cleanup as cleanup


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cold = ".local/batch-001/native-001/test/native"
        self.hot = ".local/batch-001/native-012"
        self.write(".local/owner-inventory.json", json.dumps({"protected_files": [
            {"path": "build/save.srm"}, {"path": self.cold + "/owner-protected.tsv"}]}))
        self.policy()
        self.write(self.cold + "/receipt.json", json.dumps({"schema": cleanup.RECEIPT_SCHEMA, "passed": False}))
        self.write(self.cold + "/cycles.tsv", b"pc\tcycles\n" * 100)
        self.write(self.cold + "/duplicate.tsv", b"pc\tcycles\n" * 100)
        self.write(self.cold + "/snapshots/000001.wram.bin", bytes(range(256)))
        self.write(self.cold + "/assets/game.ttf", b"font" * 100)
        self.workspace = cleanup.Workspace(self.root)

    def write(self, rel, data):
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data.encode() if isinstance(data, str) else data)
        return target

    def policy(self, pins=None):
        self.write(cleanup.POLICY, json.dumps({"schema": "gaia active cleanup pins v1",
            "active_batches": pins or [self.hot], "protected_owner_inventory": ".local/owner-inventory.json"}))

    def prepared(self):
        return self.workspace.preview([".local/batch-001"])

    def archived(self):
        plan_rel, plan = self.prepared()
        index = self.workspace.archive(plan_rel)
        return plan_rel, plan, index

    def test_dedup_roundtrip_and_idempotence(self):
        plan_rel, plan, index_rel = self.archived()
        original = {e["path"]: (self.root / e["path"]).read_bytes() for e in plan["entries"]}
        stamps = {e["path"]: (self.root / e["path"]).stat().st_mtime_ns for e in plan["entries"]}
        self.assertEqual(len(plan["entries"]), 4)
        index = self.workspace.verify(index_rel)
        self.assertEqual(index["payloads"], 3)
        archive = self.root / index["archive"]
        sha = cleanup.digest_file(archive)
        archive_stamp = archive.stat().st_mtime_ns
        with zipfile.ZipFile(archive) as stored:
            self.assertEqual(len(stored.namelist()), 3)
        self.assertEqual(self.workspace.apply(plan_rel)["removed_files"], 4)
        self.assertTrue(all(not (self.root / rel).exists() for rel in original))
        self.assertTrue((self.root / self.cold / "receipt.json").exists())
        self.assertEqual(self.workspace.apply(plan_rel)["removed_files"], 0)
        self.assertEqual(self.workspace.archive(plan_rel), index_rel)
        self.assertEqual(sha, cleanup.digest_file(archive))
        self.assertEqual(archive_stamp, archive.stat().st_mtime_ns)
        result = self.workspace.restore(index_rel, self.cold)
        self.assertEqual(result["restored_files"], 4)
        for rel, data in original.items():
            self.assertEqual((self.root / rel).read_bytes(), data)
            self.assertEqual((self.root / rel).stat().st_mtime_ns, stamps[rel])
        self.assertEqual(self.workspace.restore(index_rel, self.cold)["restored_files"], 0)

    def test_metadata_rom_owner_tools_build_and_active_pins_untouched(self):
        protected = [self.cold + "/owner-protected.tsv", self.cold + "/game.sfc",
            self.cold + "/save.srm", self.cold + "/trace.csv", self.cold + "/route.json",
            self.cold + "/journal.jsonl", self.cold + "/run.log", self.cold + "/game.exe",
            self.cold + "/unrecognized.bin", self.cold + "/msu1/track.tsv",
            self.cold + "/owner-load/snapshot.wram.bin", self.cold + "/archives/old.tsv",
            self.hot + "/test/cycles.tsv", ".local/batch-001/native-007/tool-versions/tool.tsv",
            ".local/no-receipt/trace.tsv", "build/owner.wram.bin"]
        for rel in protected:
            self.write(rel, b"keep")
        for rel in [self.hot + "/test/receipt.json", ".local/batch-001/native-007/tool-versions/receipt.json"]:
            self.write(rel, json.dumps({"schema": cleanup.RECEIPT_SCHEMA}))
        self.write(self.cold + "/master/CMakeCache.txt", "master build")
        protected.append(self.cold + "/master/font.otf")
        self.write(protected[-1], b"keep")
        plan_rel, plan = self.prepared()
        self.assertFalse(set(protected) & {e["path"] for e in plan["entries"]})
        self.workspace.archive(plan_rel)
        self.workspace.apply(plan_rel)
        self.assertTrue(all((self.root / rel).read_bytes() == b"keep" for rel in protected))

    def test_missing_or_invalid_policy_fails_closed(self):
        (self.root / cleanup.POLICY).unlink()
        with self.assertRaises(cleanup.CleanupError):
            cleanup.Workspace(self.root)
        self.policy()
        self.write(".local/owner-inventory.json", "{}")
        with self.assertRaises(cleanup.CleanupError):
            cleanup.Workspace(self.root)

    def test_late_source_mutation_stops_and_prior_removals_are_recoverable(self):
        plan_rel, plan, index = self.archived()
        originals = {e["path"]: (self.root / e["path"]).read_bytes() for e in plan["entries"]}
        changed = plan["entries"][-1]["path"]
        self.write(changed, b"changed")
        with self.assertRaises(cleanup.CleanupError):
            self.workspace.apply(plan_rel)
        self.assertEqual((self.root / changed).read_bytes(), b"changed")
        for entry in plan["entries"][:-1]:
            self.assertFalse((self.root / entry["path"]).exists())
            self.workspace.restore(index, entry["path"])
            self.assertEqual((self.root / entry["path"]).read_bytes(), originals[entry["path"]])

    def test_changed_duplicate_copy_is_never_deleted(self):
        plan_rel, plan = self.prepared()
        changed = self.cold + "/duplicate.tsv"
        original = (self.root / self.cold / "cycles.tsv").read_bytes()
        self.write(changed, b"changed duplicate copy")
        # Duplicate contents are not reread during archive construction. The
        # unique stream and roundtrip must still match the original preview.
        with patch.object(self.workspace, "_source", wraps=self.workspace._source) as checks:
            index = self.workspace.archive(plan_rel)
            self.assertEqual(checks.call_count, 0)
        self.workspace.verify(index)
        with self.assertRaises(cleanup.CleanupError):
            self.workspace.apply(plan_rel)
        self.assertEqual((self.root / changed).read_bytes(), b"changed duplicate copy")
        self.workspace.restore(index, self.cold + "/cycles.tsv")
        self.assertEqual((self.root / self.cold / "cycles.tsv").read_bytes(), original)

    def test_corrupt_unique_copy_stream_keeps_originals_and_no_completed_index(self):
        plan_rel, plan = self.prepared()
        original = {e["path"]: (self.root / e["path"]).read_bytes() for e in plan["entries"]}
        target = self.root / plan["entries"][0]["path"]
        real_open = Path.open
        def corrupt_stream(path, mode="r", *args, **kwargs):
            if path == target and mode == "rb":
                return io.BytesIO(b"synthetic corruption while copying unique source")
            return real_open(path, mode, *args, **kwargs)
        with patch.object(Path, "open", corrupt_stream), self.assertRaisesRegex(cleanup.CleanupError, "while archiving"):
            self.workspace.archive(plan_rel)
        archive, index = self.workspace.locations(plan)
        self.assertTrue((self.root / archive).exists())
        self.assertFalse((self.root / index).exists())
        for rel, contents in original.items():
            self.assertEqual((self.root / rel).read_bytes(), contents)

    def test_windows_sharing_locks_retain_only_locked_file_and_resume(self):
        plan_rel, plan, index = self.archived()
        locked_rel = self.cold + "/cycles.tsv"
        locked = self.root / locked_rel
        original = {e["path"]: (self.root / e["path"]).read_bytes() for e in plan["entries"]}
        real_unlink = Path.unlink
        for winerror in (32, 33):
            with self.subTest(winerror=winerror):
                def guarded_unlink(target, *args, **kwargs):
                    if target == locked:
                        exc = OSError("synthetic sharing lock")
                        exc.winerror = winerror
                        raise exc
                    return real_unlink(target, *args, **kwargs)
                with patch.object(Path, "unlink", guarded_unlink):
                    result = self.workspace.apply(plan_rel)
                self.assertEqual(result["removed_files"], len(plan["entries"]) - 1)
                self.assertEqual(result["skipped_locked"], [{"path": locked_rel,
                    "bytes": len(original[locked_rel]), "winerror": winerror}])
                self.assertTrue(result["pending_locked_files"])
                self.assertEqual(result["skipped_locked_files"], 1)
                self.assertEqual(result["skipped_locked_bytes"], len(original[locked_rel]))
                self.assertEqual(locked.read_bytes(), original[locked_rel])
                self.assertTrue(all(not (self.root / e["path"]).exists()
                    for e in plan["entries"] if e["path"] != locked_rel))
                with contextlib.redirect_stdout(io.StringIO()) as console:
                    self.assertEqual(cleanup.report_apply(result), 3)
                self.assertIn("Cleanup pending", console.getvalue())
                resumed = self.workspace.apply(plan_rel)
                self.assertEqual(resumed["removed_files"], 1)
                self.assertFalse(resumed["pending_locked_files"])
                self.workspace.restore(index, self.cold)
                for rel, data in original.items():
                    self.assertEqual((self.root / rel).read_bytes(), data)

    def test_access_denied_is_fail_stop_not_a_skipped_lock(self):
        plan_rel, plan, index = self.archived()
        denied = self.root / plan["entries"][0]["path"]
        real_unlink = Path.unlink
        def denied_unlink(target, *args, **kwargs):
            if target == denied:
                exc = PermissionError("synthetic access denied")
                exc.winerror = 5
                raise exc
            return real_unlink(target, *args, **kwargs)
        with patch.object(Path, "unlink", denied_unlink), self.assertRaises(PermissionError):
            self.workspace.apply(plan_rel)
        self.assertTrue(all((self.root / e["path"]).exists() for e in plan["entries"]))
        self.workspace.verify(index)

    def test_lease_refuses_nested_same_process_and_releases_on_exception(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic exit"):
            with cleanup.cleanup_lease(self.workspace, "native timing"):
                with self.assertRaisesRegex(cleanup.CleanupError, "Another cleanup/validation.*native timing"):
                    with cleanup.cleanup_lease(self.root):
                        self.fail("Nested lease admitted")
                raise RuntimeError("synthetic exit")
        with cleanup.cleanup_lease(self.root):
            self.assertTrue((self.root / cleanup.STORE / "run.lock").exists())

    def test_actual_subprocess_lease_refusal_release_and_process_exit(self):
        scripts = str(Path(cleanup.__file__).parent)
        holder_code = """from pathlib import Path
import sys
sys.path.insert(0,sys.argv[1])
from project_cleanup import cleanup_lease
with cleanup_lease(Path(sys.argv[2]), 'synthetic native timing'):
    Path(sys.argv[3]).write_text('ready')
    sys.stdin.readline()
"""
        probe_code = """from pathlib import Path
import sys
sys.path.insert(0,sys.argv[1])
from project_cleanup import cleanup_lease,CleanupError
try:
    with cleanup_lease(Path(sys.argv[2])):
        print('acquired')
except CleanupError as exc:
    print(exc)
    sys.exit(9)
"""
        ready = self.root / ".local/holder-ready.txt"
        holder = subprocess.Popen([sys.executable, "-u", "-c", holder_code, scripts, str(self.root), str(ready)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def stop():
            if holder.poll() is None:
                holder.kill()
            holder.communicate(timeout=5)
        self.addCleanup(stop)
        deadline = time.monotonic() + 5
        while not ready.exists() and holder.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(ready.exists(), "Child did not acquire lease within bound")
        probe = [sys.executable, "-u", "-c", probe_code, scripts, str(self.root)]
        result = subprocess.run(probe, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertIn("Another cleanup/validation operation is running", result.stdout)
        self.assertIn("synthetic native timing", result.stdout)
        # Execute every real CLI branch against this fake project, proving the
        # lease refuses before scanning or reading even a nonexistent plan/index.
        fake_cli = self.write("scripts/project_cleanup.py", Path(cleanup.__file__).read_bytes())
        for arguments in (["preview"], ["clean"], ["archive", "--plan", "unused"],
                          ["apply", "--plan", "unused"], ["verify", "--index", "unused"],
                          ["restore", "--index", "unused", "--prefix", self.cold]):
            result = subprocess.run([sys.executable, "-u", str(fake_cli), *arguments],
                capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1, (arguments, result.stderr))
            self.assertIn("Another cleanup/validation operation is running", result.stderr)
            self.assertNotIn('"phase"', result.stdout)
        # Abrupt process exit must release the OS lease without deleting any file.
        holder.kill()
        holder.communicate(timeout=5)
        result = subprocess.run(probe, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("acquired", result.stdout)
        self.assertTrue((self.root / cleanup.STORE / "run.lock").exists())

    def test_pins_and_owner_inventory_identity_rechecked(self):
        plan_rel, plan, _ = self.archived()
        self.policy([self.hot, ".local/batch-001/native-001"])
        with self.assertRaises(cleanup.CleanupError):
            self.workspace.apply(plan_rel)
        new_workspace = cleanup.Workspace(self.root)
        with self.assertRaises(cleanup.CleanupError):
            new_workspace.load_plan(plan_rel)
        self.assertTrue(all((self.root / e["path"]).exists() for e in plan["entries"]))
        self.policy()
        self.write(".local/owner-inventory.json", json.dumps({"protected_files": [{"path": self.cold + "/cycles.tsv"}]}))
        with self.assertRaises(cleanup.CleanupError):
            self.workspace.apply(plan_rel)

    def test_corrupt_or_missing_archive_never_unlinks(self):
        plan_rel, plan, index_rel = self.archived()
        index = self.workspace.read(index_rel)
        archive = self.root / index["archive"]
        original = archive.read_bytes()
        archive.write_bytes(original[:-4] + b"oops")
        with self.assertRaises(cleanup.CleanupError):
            self.workspace.apply(plan_rel)
        archive.unlink()
        with self.assertRaises(OSError):
            self.workspace.apply(plan_rel)
        self.assertTrue(all((self.root / e["path"]).exists() for e in plan["entries"]))
        # A completed index never authorizes recreating its missing old archive.
        with self.assertRaises(OSError):
            self.workspace.archive(plan_rel)

    def test_roundtrip_corruption_and_missing_member_detected_even_with_new_zip_digest(self):
        plan_rel, plan, index_rel = self.archived()
        index = self.workspace.read(index_rel)
        archive = self.root / index["archive"]
        with zipfile.ZipFile(archive, "w") as stored:
            for entry in {e["sha256"]: e for e in plan["entries"]}.values():
                stored.writestr("payload/" + entry["sha256"], b"x" * entry["bytes"])
        index["archive_sha256"], index["archive_bytes"] = cleanup.digest_file(archive)
        self.write(index_rel, json.dumps(index))
        with self.assertRaisesRegex(cleanup.CleanupError, "roundtrip"):
            self.workspace.apply(plan_rel)
        with zipfile.ZipFile(archive, "w"):
            pass
        index["archive_sha256"], index["archive_bytes"] = cleanup.digest_file(archive)
        self.write(index_rel, json.dumps(index))
        with self.assertRaisesRegex(cleanup.CleanupError, "member set"):
            self.workspace.verify(index_rel)

    def test_archive_failure_leaves_originals_and_never_recreates_partial(self):
        plan_rel, plan = self.prepared()
        with patch.object(self.workspace, "_verify_payloads", side_effect=cleanup.CleanupError("synthetic corruption")):
            with self.assertRaises(cleanup.CleanupError):
                self.workspace.archive(plan_rel)
        archive_rel, index_rel = self.workspace.locations(plan)
        self.assertTrue((self.root / archive_rel).exists())
        self.assertFalse((self.root / index_rel).exists())
        with self.assertRaisesRegex(cleanup.CleanupError, "without completed index"):
            self.workspace.archive(plan_rel)
        self.assertTrue(all((self.root / e["path"]).exists() for e in plan["entries"]))

    def test_restore_prefix_and_nonidentical_overwrite_refusal(self):
        plan_rel, plan, index_rel = self.archived()
        self.workspace.apply(plan_rel)
        self.assertEqual(self.workspace.restore(index_rel, self.cold + "/assets")["restored_files"], 1)
        self.write(self.cold + "/cycles.tsv", b"new user data")
        with self.assertRaises(cleanup.CleanupError):
            self.workspace.restore(index_rel, self.cold)
        self.assertFalse((self.root / self.cold / "duplicate.tsv").exists())
        self.assertEqual((self.root / self.cold / "cycles.tsv").read_bytes(), b"new user data")
        with self.assertRaises(cleanup.CleanupError):
            self.workspace.restore(index_rel, "build")

    def test_traversal_ads_absolute_metadata_and_owner_plan_forgery_refused(self):
        for rel in ["../outside", ".local/../../outside", "C:/outside", "/outside",
                    ".local/x:stream", ".local/CON", ".local/a./x", ".local//x"]:
            with self.subTest(rel=rel), self.assertRaises(cleanup.CleanupError):
                self.workspace.path(rel)
        plan_rel, plan = self.prepared()
        for rel in ["build/owner.wram.bin", self.cold + "/receipt.json", self.cold + "/owner-protected.tsv"]:
            forged = json.loads(json.dumps(plan))
            forged["entries"][0]["path"] = rel
            forged["plan_id"] = cleanup.plan_digest(forged)
            with self.subTest(rel=rel), self.assertRaises(cleanup.CleanupError):
                self.workspace.validate_plan(forged)
        plan["entries"][0]["bytes"] += 1
        self.write(plan_rel, json.dumps(plan))
        with self.assertRaisesRegex(cleanup.CleanupError, "identity"):
            self.workspace.archive(plan_rel)

    def test_reparse_attributes_and_symlink_ancestor_skip_refuse(self):
        self.assertTrue(cleanup.reparse(SimpleNamespace(st_mode=0o100644, st_file_attributes=0x400)))
        target = self.root / self.cold / "linked"
        outside = self.root / "external"
        outside.mkdir()
        (outside / "secret.tsv").write_bytes(b"keep")
        try:
            target.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Symlinks unavailable: {exc}")
        _, plan = self.prepared()
        self.assertEqual(plan["skipped_reparse_points"], 1)
        with self.assertRaisesRegex(cleanup.CleanupError, "Reparse"):
            self.workspace.path(self.cold + "/linked/secret.tsv")
        plan_rel, plan, index_rel = self.archived()
        self.workspace.apply(plan_rel)
        assets = self.root / self.cold / "assets"
        assets.rmdir()
        assets.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(cleanup.CleanupError, "Reparse"):
            self.workspace.restore(index_rel, self.cold)
        self.assertEqual((outside / "secret.tsv").read_bytes(), b"keep")

    def test_scaled_classification_reads_are_per_fixture_not_per_file(self):
        for fixture in range(100):
            base = f".local/batch-001/native-002/scaled-{fixture}/native"
            self.write(base + "/receipt.json", json.dumps({"schema": cleanup.RECEIPT_SCHEMA}))
            for number in range(10):
                self.write(base + f"/trace-{number}.tsv", b"small synthetic payload\n")
        original_load = json.load
        receipts = []
        def counted(stream, *args, **kwargs):
            if Path(stream.name).name == "receipt.json":
                receipts.append(stream.name)
            return original_load(stream, *args, **kwargs)
        with patch.object(cleanup.json, "load", side_effect=counted), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(self.workspace, "_check_ancestors", wraps=self.workspace._check_ancestors) as walks:
            rel, plan = self.prepared()
            self.assertEqual(len(plan["entries"]), 1004)
            self.workspace.load_plan(rel)
            self.workspace.load_plan(rel)
        self.assertLessEqual(len(receipts), 202)  # <=2 reads per101fixtures, not3000+
        self.assertLess(walks.call_count, 650)  # Read-only path walks scale with directories.

    def test_cached_receipt_mutation_cmake_and_owner_protections_remain_live(self):
        rel = self.cold + "/cycles.tsv"
        self.assertEqual(self.workspace.eligible(rel), "raw-tsv")
        self.write(self.cold + "/receipt.json", "{broken changed metadata")
        self.assertIsNone(self.workspace.eligible(rel))
        self.write(self.cold + "/receipt.json", json.dumps({"schema": cleanup.RECEIPT_SCHEMA}))
        self.assertEqual(self.workspace.eligible(rel), "raw-tsv")
        plan_rel, plan, _ = self.archived()
        self.write(".local/batch-001/native-001/CMakeCache.txt", "new ancestor build")
        with self.assertRaises(cleanup.CleanupError):
            self.workspace.apply(plan_rel)
        self.assertTrue(all((self.root / e["path"]).exists() for e in plan["entries"]))

    def test_immutable_preview_reuse_and_incomplete_collision_get_fresh_name(self):
        rel, plan = self.prepared()
        self.assertEqual(self.prepared()[0], rel)
        self.write(rel, "interrupted prior write")
        replacement, new_plan = self.prepared()
        self.assertNotEqual(replacement, rel)
        self.assertEqual(new_plan, plan)
        self.assertEqual((self.root / rel).read_text(), "interrupted prior write")

    def test_receipted_rasters_and_mutation_time_ancestor_marker(self):
        for extension in ("ppm", "bgrx", "bmp", "tga"):
            self.write(self.cold + f"/full-frames/frame123.{extension}", b"raster")
            self.write(f".local/loose/frame123.{extension}", b"keep loose")
            self.write(f"art/frame123.{extension}", b"keep source")
        self.write(self.cold + "/full-frames/ui.png", b"keep png")
        plan_rel, plan, _ = self.archived()
        self.assertEqual(sum(e["kind"] == "raw-raster" for e in plan["entries"]), 4)
        real_unlink = Path.unlink
        removed = []
        def add_build_marker_after_first(target, *args, **kwargs):
            real_unlink(target, *args, **kwargs)
            removed.append(target)
            if len(removed) == 1:
                self.write(".local/batch-001/native-001/CMakeCache.txt", "concurrent ancestor marker")
        with patch.object(Path, "unlink", add_build_marker_after_first), self.assertRaises(cleanup.CleanupError):
            self.workspace.apply(plan_rel)
        self.assertEqual(len(removed), 1)
        self.assertTrue((self.root / self.cold / "full-frames/ui.png").exists())
        self.assertTrue((self.root / "art/frame123.ppm").exists())


if __name__ == "__main__":
    unittest.main()
