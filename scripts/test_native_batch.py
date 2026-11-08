"""Resource guards exercised with synthetic child trees, never game inputs."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

import native_batch
from native_batch import bounded_run, read_profiles, read_historical_profiles, prepare


class GaiaGuardTests(unittest.TestCase):
    def test_math_leaf_is_separate_from_poll_and_mutable_guards(self):
        policy = json.loads(native_batch.POLICY.read_text(encoding="utf-8"))
        blocked, _ = native_batch.guards(policy)
        for base in (0x000000, 0x400000, 0x800000, 0xC00000):
            for offset in (0x028000, 0x028002, 0x02803A):
                self.assertNotIn(base | offset, blocked)
            for offset in (0x02803B, 0x028043, 0x02804D, 0x028051, 0x028190,
                           0x008000, 0x0082F8, 0x008386, 0x03C5FF, 0x03C9FF):
                self.assertIn(base | offset, blocked)


class ProfileRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "capture.json"
        self.record = {
            "schema": "snesrecomp tier2 coverage v2", "capture_id": "synthetic",
            "identity": {"rom_sha256": "a" * 64, "build_digest": "b" * 64,
                         "mapper": "hirom", "module_id": "main"},
            "checkpoint_complete": True, "overflowed_tuples": 0,
            "dropped_cost_samples": 0, "ram_routines_overflow": 0,
            "journal_write_failures": 0, "discoveries": [], "costs": []}

    def read(self, raw=None):
        self.path.write_text(raw if raw is not None else json.dumps(self.record), encoding="utf-8")
        return read_profiles([self.path], "a" * 64)

    def test_complete_lossless_v2_retains_provenance(self):
        result = self.read()
        self.assertEqual(result["captures"][0]["capture_id"], "synthetic")
        self.assertEqual(result["counts"], {"transfer_rows": 0, "cost_rows": 0})

    def test_each_actual_loss_counter_is_required_integer_zero(self):
        for key in ("overflowed_tuples", "dropped_cost_samples", "ram_routines_overflow", "journal_write_failures"):
            for value in (1, -1, False, "0", 0.0, None):
                with self.subTest(key=key, value=value):
                    self.record[key] = value
                    with self.assertRaises(ValueError): self.read()
            del self.record[key]
            with self.subTest(key=key, missing=True), self.assertRaises(ValueError): self.read()
            self.record[key] = 0

    def test_checkpoint_must_be_explicit_true(self):
        for value in (False, None, 1, "true"):
            self.record["checkpoint_complete"] = value
            with self.subTest(value=value), self.assertRaises(ValueError): self.read()
        del self.record["checkpoint_complete"]
        with self.assertRaises(ValueError): self.read()

    def test_duplicate_keys_including_nested_identity_are_rejected(self):
        for raw in ('{"schema":1,"schema":2}', '{"identity":{"mapper":"hirom","mapper":"lorom"}}'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "Duplicate"): self.read(raw)

    def test_nonfinite_json_numbers_are_rejected_anywhere(self):
        for value in ("NaN", "Infinity", "-Infinity", "1e9999", "-1e9999"):
            raw = json.dumps(self.record)[:-1] + ',"nested":{"ignored":' + value + '}}'
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Non-finite"): self.read(raw)

    def test_legacy_loss_aliases_cannot_hide_loss(self):
        for key in ("dropped_costs", "cost_overflow"):
            self.record[key] = 1
            with self.subTest(key=key), self.assertRaises(ValueError): self.read()
            del self.record[key]

    def test_different_build_costs_cannot_be_aggregated(self):
        self.read()
        other = Path(self.temp.name) / "other.json"
        self.record["identity"]["build_digest"] = "c" * 64
        other.write_text(json.dumps(self.record), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "different program/build"):
            read_profiles([self.path, other], "a" * 64)

    def test_cost_counter_cannot_be_truncated_or_negative(self):
        for value in (-1, True, 0.5, "100", None):
            self.record["costs"] = [{"target_pc24": "0x808000", "guest_cycles": value}]
            with self.subTest(value=value), self.assertRaises(ValueError): self.read()

    def test_record_arrays_cannot_be_objects(self):
        for key in ("discoveries", "costs", "ram_routines"):
            self.record[key] = {}
            with self.subTest(key=key), self.assertRaises(ValueError): self.read()
            self.record[key] = []

    def test_historical_costs_and_legacy_metadata_remain_separate(self):
        self.record["costs"] = [{"target_pc24": "0x808000", "guest_cycles": 10}]
        self.read()
        original = self.path.read_bytes()
        other = Path(self.temp.name) / "historical-other.json"
        self.record["identity"].update(build_digest="c" * 64, program_digest="d" * 64)
        self.record["costs"][0]["guest_cycles"] = 20
        other.write_text(json.dumps(self.record), encoding="utf-8")
        evidence = read_historical_profiles([self.path, other], "a" * 64)
        self.assertEqual([x["profile"]["highest_costs"][0]["guest_cycles"] for x in evidence], [10, 20])
        self.assertEqual(evidence[0]["program_identity_status"], "legacy_metadata_missing_program_digest")
        self.assertEqual(evidence[1]["program_identity_status"], "recorded")
        self.assertNotIn("program_digest", evidence[0]["profile"]["captures"][0]["identity"])
        self.assertEqual(self.path.read_bytes(), original)

    def test_historical_does_not_bypass_loss_or_rom_validation(self):
        for key, value in (("dropped_cost_samples", 1), ("checkpoint_complete", False)):
            original = self.record[key]
            self.record[key] = value
            self.path.write_text(json.dumps(self.record), encoding="utf-8")
            with self.subTest(key=key), self.assertRaises(ValueError):
                read_historical_profiles([self.path], "a" * 64)
            self.record[key] = original
        self.read()
        with self.assertRaises(ValueError): read_historical_profiles([self.path], "e" * 64)

    def prepare_fixture(self, work_name, historical=None):
        project = Path(self.temp.name) / "project"
        (project / "recomp").mkdir(parents=True, exist_ok=True)
        (project / "recomp/bank00.cfg").write_text("bank = 0\nfunc synthetic 8000\n", encoding="utf-8")
        (project / "framework_pins.txt").write_text("synthetic pins\n", encoding="utf-8")
        rom = project / "synthetic.sfc"
        rom.write_bytes(bytes(2097152))
        rom_hash = native_batch.digest(rom.read_bytes())
        policy = project / "policy.json"
        policy.write_text(json.dumps({"schema": "gaia native batch policy v1", "mapper": "hirom",
                                      "rom_sha256": rom_hash, "guard_ranges": []}), encoding="utf-8")
        current = project / "current.json"
        record = json.loads(json.dumps(self.record))
        record["identity"].update(rom_sha256=rom_hash, build_digest="f" * 64)
        current.write_text(json.dumps(record), encoding="utf-8")
        for path in historical or []:
            record = json.loads(path.read_text())
            record["identity"]["rom_sha256"] = rom_hash
            path.write_text(json.dumps(record), encoding="utf-8")
        with patch.object(native_batch, "ROOT", project), patch.object(native_batch, "POLICY", policy):
            return prepare(rom, project / work_name, [current], False, True,
                           historical_profiles=historical)

    def test_prepare_history_is_explicit_and_immutable(self):
        self.read()
        historical = [self.path]
        result = self.prepare_fixture("with-history", historical)
        command = result["generation_command"]
        self.assertIn("--profile-manifest", command)
        self.assertIn("--historical-profile-manifest", command)
        self.assertEqual(command[command.index("--historical-profile-manifest") + 1], str(self.path))
        self.assertEqual(len(result["historical_profiles"]), 1)
        self.assertEqual(result, self.prepare_fixture("with-history", historical))
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.prepare_fixture("with-history", [])
        record = json.loads(self.path.read_text())
        record["capture_id"] = "changed-history"
        self.path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.prepare_fixture("with-history", historical)

    def test_prepare_default_retains_old_receipt_shape_and_refuses_added_history(self):
        result = self.prepare_fixture("without-history")
        self.assertNotIn("historical_profiles", result)
        self.assertNotIn("--historical-profile-manifest", result["generation_command"])
        self.assertEqual(result, self.prepare_fixture("without-history"))
        self.read()
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.prepare_fixture("without-history", [self.path])


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

    def test_long_backslash_argument_survives_guard_transport(self):
        # This child command fits CreateProcess's limit, but passing a JSON
        # copy through another command line doubled the slashes past 32 KiB.
        payload = "\\" * 18000
        result = bounded_run([sys.executable, "-c", "import sys; print(len(sys.argv[1]))", payload],
                             self.log, 128, 5)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(self.log.read_text().strip(), "18000")

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
