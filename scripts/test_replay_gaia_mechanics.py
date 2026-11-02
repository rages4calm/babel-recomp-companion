"""Private-plan refusal and replay orchestration tests; no engine is executed."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import replay_gaia_mechanics as replay


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.private = self.root / ".local"
        self.private.mkdir(parents=True)
        self.patch = patch.object(replay, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.rom = self.root / "synthetic-input.bin"
        self.rom.write_bytes(b"\0" * 2097152)
        self.rom_hash = replay.sha(self.rom)
        (self.root / "rom_identity.txt").write_text("expected_sha256 = " + self.rom_hash + "\n")
        self.binary = self.private / "synthetic-executable.bin"
        self.binary.write_bytes(b"not executable; mock only")
        self.script = self.private / "route.txt"
        self.script.write_text("loadstate 0\nwait 60\ndump effect\n")
        self.seed = self.private / "synthetic-seed.bin"
        self.seed.write_bytes(b"fixture seed")
        self.witness = self.private / "witness"
        (self.witness / "snapshots").mkdir(parents=True)
        (self.witness / "mods/preloaded").mkdir(parents=True)
        for name in ("trace.csv", "final.ppm", "mods/preloaded/state.toml"):
            (self.witness / name).write_bytes(b"synthetic data")
        for suffix in replay.SUFFIXES:
            (self.witness / "snapshots" / ("effect" + suffix)).write_bytes(b"synthetic data")
        self.receipt = {
            "schema": "iog-native-route-v1", "passed": True, "checks": {"synthetic": True},
            "frames_requested": 60, "frames_traced": 60, "widescreen": False,
            "infinite_hp": True, "room_reward_multiplier": 1,
            "input_sha256": {"rom": self.rom_hash, "route": replay.sha(self.script),
                             "seed_state": replay.sha(self.seed), "binary": "b" * 64},
            "fixture_mod_state_sha256": replay.sha(self.witness / "mods/preloaded/state.toml"),
            "snapshots": [{"tag": "effect", "wram_sha256": replay.sha(self.witness / "snapshots/effect.wram.bin")}],
        }
        self.receipt_path = self.witness / "receipt.json"
        self.receipt_path.write_text(json.dumps(self.receipt))
        self.case = {
            "name": "synthetic-effect", "script": str(self.script), "script_sha256": replay.sha(self.script),
            "seed": str(self.seed), "seed_sha256": replay.sha(self.seed), "frames": 60, "rate": 1,
            "infinite_hp": True, "wide": False, "expect_scene": 182,
            "witness_dir": str(self.witness), "witness_receipt_sha256": replay.sha(self.receipt_path),
            "witness_files_sha256": replay.witness_inventory(self.witness, self.receipt),
            "semantic_attestation": {"scope": "Synthetic test only; no game qualification", "condition": "mock"},
        }
        self.plan_data = {"schema": replay.SCHEMA, "cases": [self.case]}
        self.plan = self.private / "plan.json"
        self.output = self.private / "fresh-output"
        self.write_plan()

    def write_plan(self):
        self.plan.write_text(json.dumps(self.plan_data))

    def update_receipt(self):
        self.receipt_path.write_text(json.dumps(self.receipt))
        self.case["witness_receipt_sha256"] = replay.sha(self.receipt_path)
        self.write_plan()

    def validate(self):
        self.write_plan()
        return replay.validate_plan(self.plan, self.output)

    def test_valid_plan_normalizes_without_creating_output(self):
        got = self.validate()
        self.assertEqual(got["cases"][0]["script"], str(self.script.resolve()))
        self.assertFalse(self.output.exists())

    def test_case_count_and_unique_safe_names(self):
        original = deepcopy(self.case)
        for cases in ([], [deepcopy(original)] * 65, [original, deepcopy(original)]):
            self.plan_data["cases"] = cases
            with self.subTest(count=len(cases)), self.assertRaises(ValueError):
                self.validate()
        self.plan_data["cases"] = [self.case]
        for name in ("../escape", "..", "a/b", "a\\b", "Uppercase", "a" * 65, "", "con", "nul", "aux", "com1", "lpt9"):
            self.case["name"] = name
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.validate()

    def test_strict_bounded_options(self):
        for key, values in {"frames": [59, 10001, True, 60.0], "rate": [0, 9, False, "1"],
                            "infinite_hp": [1, None], "wide": [0, "false"], "expect_scene": [-1, 256, True]}.items():
            previous = self.case[key]
            for value in values:
                self.case[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.validate()
            self.case[key] = previous

    def test_missing_fields_and_wrong_schema(self):
        for key in ("script_sha256", "seed_sha256", "witness_receipt_sha256", "witness_files_sha256", "semantic_attestation", "expect_scene"):
            value = self.case.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate()
            self.case[key] = value
        self.plan_data["schema"] = "other"
        with self.assertRaises(ValueError):
            self.validate()

    def test_outside_paths_and_existing_output(self):
        outside = self.root / "owner.txt"
        outside.write_text("owner")
        for key in ("script", "seed", "witness_dir"):
            previous = self.case[key]
            self.case[key] = str(outside)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate()
            self.case[key] = previous
        with self.assertRaises(ValueError):
            replay.validate_plan(outside, self.output)
        with self.assertRaises(ValueError):
            replay.validate_plan(self.plan, self.root / "outside-output")
        self.output.mkdir()
        with self.assertRaises(ValueError):
            self.validate()

    def test_changed_script_seed_receipt_and_snapshot_hashes(self):
        for path in (self.script, self.seed, self.receipt_path, self.witness / "snapshots/effect.vram.bin"):
            before = path.read_bytes()
            path.write_bytes(before + b"changed")
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                self.validate()
            path.write_bytes(before)

    def test_missing_or_extra_or_empty_witness_artifacts(self):
        path = self.witness / "snapshots/effect.apu-clock.tsv"
        previous = path.read_bytes()
        path.unlink()
        with self.assertRaises(ValueError):
            self.validate()
        path.write_bytes(b"")
        with self.assertRaises(ValueError):
            self.validate()
        path.write_bytes(previous)
        (self.witness / "snapshots/unbound.wram.bin").write_bytes(b"unbound")
        with self.assertRaises(ValueError):
            self.validate()

    def test_failed_witness_even_with_rebound_receipt_hash(self):
        self.receipt["passed"] = False
        self.update_receipt()
        with self.assertRaisesRegex(ValueError, "passed route"):
            self.validate()
        self.receipt["passed"] = True
        self.receipt["checks"]["synthetic"] = False
        self.update_receipt()
        with self.assertRaisesRegex(ValueError, "passed route"):
            self.validate()

    def test_witness_options_or_input_identity_cannot_be_rebound(self):
        for key, value in (("frames_requested", 61), ("frames_traced", 59), ("widescreen", True),
                           ("infinite_hp", False), ("room_reward_multiplier", 8)):
            old = self.receipt[key]
            self.receipt[key] = value
            self.update_receipt()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "options mismatch"):
                self.validate()
            self.receipt[key] = old
        self.receipt["input_sha256"]["route"] = "f" * 64
        self.update_receipt()
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.validate()

    def test_unsafe_duplicate_tags_and_false_wram_receipt_hash(self):
        self.receipt["snapshots"].append(deepcopy(self.receipt["snapshots"][0]))
        self.update_receipt()
        with self.assertRaisesRegex(ValueError, "Duplicate witness"):
            self.validate()
        self.receipt["snapshots"].pop()
        self.receipt["snapshots"][0]["tag"] = "../escape"
        self.update_receipt()
        with self.assertRaisesRegex(ValueError, "snapshot tag"):
            self.validate()
        self.receipt["snapshots"][0] = {"tag": "effect", "wram_sha256": "f" * 64}
        self.update_receipt()
        with self.assertRaisesRegex(ValueError, "WRAM receipt"):
            self.validate()

    def test_duplicate_and_nonfinite_json_refused(self):
        for raw in ('{"schema":1,"schema":2}', '{"nested":{"x":1,"x":2}}',
                    '{"x":NaN}', '{"x":Infinity}', '{"x":1e9999}'):
            self.plan.write_text(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                replay.validate_plan(self.plan, self.output)

    def test_symlink_cannot_escape_private_tree(self):
        outside = self.root / "owner-file"
        outside.write_text("owner")
        link = self.private / "link.txt"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Platform does not allow symlink creation")
        self.case["script"] = str(link)
        with self.assertRaises(ValueError):
            self.validate()

    def mocked_run(self, binary, rom, script, output, frames, seed, **options):
        output.mkdir()
        receipt = {"passed": True, "interpret_all": options["interpret_all"]}
        (output / "receipt.json").write_text(json.dumps(receipt))
        return receipt

    def enable_write_contract(self):
        self.case["watch_wram"] = [0x10B6, 0x10B7]
        self.case["expected_write_events"] = [{"frame": 20, "bank": 0x7F, "address": 0x10B6,
                                               "value": 0, "width": 1, "reference_ipc": "83BFF0"}]
        self.receipt["watch_wram"] = self.case["watch_wram"]
        self.receipt["interpret_all"] = True
        (self.witness / "wram-writes.log").write_text("f20 7F:10B6=00 w1 old_interp IPC=83BFF0\n")
        self.case["witness_files_sha256"] = replay.witness_inventory(self.witness, self.receipt)
        self.update_receipt()

    def test_watch_and_expected_event_contracts_are_strict_and_bounded(self):
        self.enable_write_contract()
        good = deepcopy(self.case)
        for key, values in {"watch_wram": [None, [], [2, 1], [False, 1], [0, 65536]],
                            "expected_write_events": ["old event", [good["expected_write_events"][0]] * 65]}.items():
            for value in values:
                self.case[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.validate()
            self.case[key] = deepcopy(good[key])
        event = self.case["expected_write_events"][0]
        for key, values in {"frame": [-1, 60, True], "bank": [-1, 256], "address": [0, 65536],
                            "width": [0, 3, False], "value": [-1, 256], "reference_ipc": ["bad", 83]}.items():
            old = event[key]
            for value in values:
                event[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.validate()
            event[key] = old

    def test_diagnostic_watch_without_hit_assertions_remains_explicit(self):
        self.enable_write_contract()
        self.case["expected_write_events"] = []
        self.assertEqual(self.validate()["cases"][0]["watch_wram"], [0x10B6, 0x10B7])

    def test_watched_witness_log_is_hash_bound_and_must_contain_source_event(self):
        self.enable_write_contract()
        self.validate()
        path = self.witness / "wram-writes.log"
        path.write_text("f19 7F:10B6=00 w1 old_interp IPC=83BFF0\n")
        with self.assertRaisesRegex(ValueError, "artifact hashes"):
            self.validate()
        self.case["witness_files_sha256"] = replay.witness_inventory(self.witness, self.receipt)
        with self.assertRaisesRegex(ValueError, "event absent"):
            self.validate()

    def test_write_parser_rejects_malformed_width_context_and_bounds(self):
        for line in ("garbage", "f20 7F:10B6=0000 w1 fn IPC=83BFF0", "f20 7F:10B6=00 w1 fn",
                     "f20 7F:10B6=00 w1 fn IPC=83BFF0 IPC=83BFF0", "f60 7F:10B6=00 w1 fn IPC=83BFF0",
                     "f20 7F:9999=00 w1 fn IPC=83BFF0"):
            with self.subTest(line=line), self.assertRaises(ValueError):
                replay.parse_write_line(line, 60, [0x10B6, 0x10B7])

    def test_write_log_cap_and_reference_ipc_are_enforced(self):
        self.enable_write_contract()
        path = self.witness / "wram-writes.log"
        path.write_text("f20 7F:10B6=00 w1 new_native IPC=000000\n")
        expected = self.case["expected_write_events"]
        self.assertTrue(replay.check_write_events(self.witness, expected, 60, self.case["watch_wram"], False)["passed"])
        with self.assertRaisesRegex(ValueError, "event absent"):
            replay.check_write_events(self.witness, expected, 60, self.case["watch_wram"], True)
        with patch.object(replay, "WLOG_CAP", 1), self.assertRaisesRegex(ValueError, "capped"):
            replay.check_write_events(self.witness, expected, 60, self.case["watch_wram"], False)

    def test_historical_event_cannot_satisfy_missing_fresh_log(self):
        self.enable_write_contract()
        with patch.object(replay, "run", side_effect=self.mocked_run), \
             patch.object(replay, "compare", return_value={"passed": True}):
            result = replay.replay(self.binary, self.rom, self.plan, self.output)
        self.assertFalse(result["passed"])
        self.assertFalse(result["cases"][0]["semantic_conditions_carried"])
        self.assertIn("reference", result["cases"][0]["error"])
        self.assertTrue((self.witness / "wram-writes.log").exists())

    def test_fresh_native_event_missing_despite_witness_and_state_parity(self):
        self.enable_write_contract()
        def run(*args, **kwargs):
            result = self.mocked_run(*args, **kwargs)
            frame = 20 if kwargs["interpret_all"] else 19
            (args[3] / "wram-writes.log").write_text(f"f{frame} 7F:10B6=00 w1 fresh_fn IPC=83BFF0\n")
            return result
        with patch.object(replay, "run", side_effect=run), patch.object(replay, "compare", return_value={"passed": True}):
            result = replay.replay(self.binary, self.rom, self.plan, self.output)
        self.assertFalse(result["passed"])
        self.assertIn("event absent", result["cases"][0]["error"])

    def test_fresh_events_required_both_modes_with_native_label_ipc_independent(self):
        self.enable_write_contract()
        def run(*args, **kwargs):
            result = self.mocked_run(*args, **kwargs)
            ipc = "83BFF0" if kwargs["interpret_all"] else "000000"
            (args[3] / "wram-writes.log").write_text(f"f20 7F:10B6=00 w1 fresh_fn IPC={ipc}\n")
            return result
        with patch.object(replay, "run", side_effect=run) as run, patch.object(replay, "compare", return_value={"passed": True}):
            result = replay.replay(self.binary, self.rom, self.plan, self.output)
        self.assertTrue(result["passed"])
        self.assertTrue(all(c.kwargs["watch_wram"] == (0x10B6, 0x10B7) for c in run.call_args_list))
        proofs = result["cases"][0]["write_events"]
        self.assertEqual(proofs["reference"]["matches"][0]["observed"]["ipc"], "83BFF0")
        self.assertEqual(proofs["native"]["matches"][0]["observed"]["ipc"], "000000")
        self.assertTrue(all(str(self.output) in proof["log"] for proof in proofs.values()))

    def test_replay_binds_two_capture_runs_and_three_comparisons(self):
        with patch.object(replay, "run", side_effect=self.mocked_run) as run, \
             patch.object(replay, "compare", return_value={"passed": True}) as compare:
            result = replay.replay(self.binary, self.rom, self.plan, self.output)
        self.assertTrue(result["passed"])
        self.assertTrue(result["cases"][0]["semantic_conditions_carried"])
        self.assertEqual(run.call_count, 2)
        self.assertEqual([c.kwargs["interpret_all"] for c in run.call_args_list], [True, False])
        self.assertTrue(all(c.kwargs["capture"] for c in run.call_args_list))
        self.assertEqual([c.args[2] for c in compare.call_args_list], [0, 0, .001, .001])
        self.assertTrue(all(c.kwargs == {"devices": True, "apu_clock": "cycles", "apu_state": True}
                            for c in compare.call_args_list))
        self.assertTrue((self.output / "synthetic-effect/witness-reference.json").is_file())
        self.assertEqual(result["lineage"]["cases"][0]["witness_receipt_sha256"], self.case["witness_receipt_sha256"])

    def test_witness_mismatch_prevents_semantic_carry_and_keeps_reports(self):
        with patch.object(replay, "run", side_effect=self.mocked_run), \
             patch.object(replay, "compare", side_effect=[{"passed": True}, {"passed": False}, {"passed": True}, {"passed": False}]):
            result = replay.replay(self.binary, self.rom, self.plan, self.output)
        self.assertFalse(result["passed"])
        self.assertFalse(result["cases"][0]["semantic_conditions_carried"])
        self.assertTrue((self.output / "synthetic-effect/witness-reference.json").is_file())

    def test_all_cases_validated_before_any_engine_or_output(self):
        other = deepcopy(self.case)
        other["name"] = "late-bad-case"
        other["script_sha256"] = "f" * 64
        self.plan_data["cases"].append(other)
        self.write_plan()
        with patch.object(replay, "run") as run, self.assertRaises(ValueError):
            replay.replay(self.binary, self.rom, self.plan, self.output)
        run.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_malformed_witness_preflight_refuses_before_engine(self):
        with patch.object(replay, "run") as run, patch.object(replay, "compare", return_value={"passed": False}), \
             self.assertRaisesRegex(ValueError, "Malformed/incomplete"):
            replay.replay(self.binary, self.rom, self.plan, self.output)
        run.assert_not_called()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
