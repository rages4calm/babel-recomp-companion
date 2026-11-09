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

    def test_legacy_generation_receipt_still_uses_complete_public_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory); (work / "generated").mkdir()
            (work / "generated/program_manifest.json").write_text(json.dumps({"roots": [], "nodes": {
                "legacy": {"disposition": "aot_eligible", "min_pc24": 0x83C728, "max_pc24": 0x83C730}}}), encoding="utf-8")
            with patch.object(native_batch, "bounded_run", return_value={"exit_code": 0}):
                result = native_batch.generate({"generation_command": ["synthetic"]}, work)
            self.assertEqual(result["exit_code"], 3)
            self.assertNotIn("sprite_prefixes", result)
            self.assertEqual(result["guarded_range_violations"], ["legacy"])


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


class SpritePrefixPresetTests(unittest.TestCase):
    """Synthetic stock contract and tiny manifests; never load the owner's ROM."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        for directory in ("recomp", "src", "snesrecomp/tools"):
            (self.project / directory).mkdir(parents=True)
        self.cfg00 = self.project / "recomp/bank00.cfg"
        self.cfg03 = self.project / "recomp/bank03.cfg"
        self.cfg00.write_text("bank = 0\nfunc Synthetic 8000\n", encoding="utf-8")
        self.cfg03.write_text("bank = 3\nfunc SyntheticSprite C714\n", encoding="utf-8")
        (self.project / "framework_pins.txt").write_text("synthetic pins\n", encoding="utf-8")
        self.source = self.project / "src/iog_widescreen.c"
        self.source.write_bytes((native_batch.ROOT / "src/iog_widescreen.c").read_bytes())
        (self.project / "snesrecomp/snesrecomp_cli.py").write_text("# synthetic generator\n", encoding="utf-8")
        self.rom = self.project / "synthetic.sfc"
        image = bytearray(2097152)
        for pc, (opcode, stock, _, _) in native_batch.SPRITE_PATCH_CONTRACT.items():
            image[0x30000 + pc:0x30000 + pc + 3] = bytes((opcode, stock & 255, stock >> 8))
        self.rom.write_bytes(image)
        self.policy = self.project / "policy.json"
        policy = json.loads(native_batch.POLICY.read_text(encoding="utf-8"))
        policy["rom_sha256"] = native_batch.digest(image)
        self.policy.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
        self.work = self.project / ".local/preset"
        self.root_patch = patch.object(native_batch, "ROOT", self.project)
        self.policy_patch = patch.object(native_batch, "POLICY", self.policy)
        self.root_patch.start(); self.policy_patch.start()
        self.addCleanup(self.root_patch.stop); self.addCleanup(self.policy_patch.stop)

    def prep(self, **kwargs):
        options = dict(instruction_blocks=True, region_paced=True, sprite_prefixes=True)
        options.update(kwargs)
        return prepare(self.rom, self.work, [], False, True, **options)

    def test_both_pacing_prerequisites_are_mandatory(self):
        for blocks, paced in ((False, False), (True, False), (False, True)):
            with self.subTest(blocks=blocks, paced=paced), self.assertRaises(ValueError):
                self.prep(instruction_blocks=blocks, region_paced=paced)
        self.assertFalse(self.work.exists())

    def test_default_policy_and_source_cfg_stay_unchanged_and_only_exact_sites_change(self):
        before_policy = self.policy.read_bytes()
        before_cfg = {p.name: p.read_bytes() for p in (self.project / "recomp").glob("bank*.cfg")}
        preset = self.prep()
        default_work = self.project / ".local/default"
        default = prepare(self.rom, default_work, [], False, True, instruction_blocks=True, region_paced=True)
        self.assertNotIn("sprite_prefixes", default)
        self.assertEqual(default["policy_sha256"], native_batch.digest(before_policy))
        self.assertFalse((default_work / "effective-policy.json").exists())
        self.assertEqual(before_policy, self.policy.read_bytes())
        self.assertEqual(before_cfg, {p.name: p.read_bytes() for p in (self.project / "recomp").glob("bank*.cfg")})
        effective = json.loads((self.work / "effective-policy.json").read_text())
        original = json.loads(before_policy)
        self.assertEqual(effective["guard_ranges"][:-1], original["guard_ranges"][:-1])
        self.assertEqual(effective["guard_ranges"][-1]["end_exclusive"], "03C714")
        self.assertEqual(effective["guard_ranges"][-1]["start"], "03C5FF")
        live = "".join(f"live_operand {pc:04X}\n" for pc in native_batch.SPRITE_IMMEDIATES)
        self.assertEqual((self.work / "cfg/bank03.cfg").read_text(),
                         before_cfg["bank03.cfg"].decode().replace("\r\n", "\n") + native_batch.SPRITE_CFG_COMMENT + live)
        def force(work):
            return {int(line.split()[1], 16) for line in (work / "cfg/bank00.cfg").read_text().splitlines()
                    if line.startswith("force_lle ")}
        removed = {alias for pc in range(0x03C714, 0x03CA00) for alias in native_batch.aliases(pc)}
        self.assertEqual(force(default_work) - force(self.work), removed)
        self.assertFalse(force(self.work) - force(default_work))
        self.assertEqual(len(preset["sprite_prefixes"]["live_alias_sites"]), 24)
        self.assertEqual(preset["sprite_prefixes"]["cache_inputs_sha256"], native_batch.sprite_cache_inputs(preset))
        self.assertEqual(preset, self.prep())
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.prep(sprite_prefixes=False)

    def test_real_cfg_parser_expands_all_four_hirom_live_site_contexts(self):
        # Execute the actual loader/alias expansion, not a mirror implemented here.
        sdk = Path(__file__).resolve().parents[1] / "snesrecomp/recompiler"
        with patch.object(sys, "path", [str(sdk), *sys.path]):
            from snes65816 import get_rom_mapping, set_rom_mapping
            from v2.cfg_loader import load_bank_cfg
            from v2.hirom_cfg import expand_hirom_cfgs
            self.prep()
            path = self.work / "cfg/bank03.cfg"
            cfg = load_bank_cfg(str(path))
            old = get_rom_mapping()
            try:
                set_rom_mapping("hirom")
                expanded = expand_hirom_cfgs([(3, path, cfg)])
            finally:
                set_rom_mapping(old)
            banks = {bank: row for bank, _, row in expanded}
            self.assertEqual(set(banks), {3, 0x43, 0x83, 0xC3})
            for bank, row in banks.items():
                with self.subTest(bank=bank):
                    self.assertEqual(row.live_operand, set(native_batch.SPRITE_IMMEDIATES))
                    self.assertNotIn(0xC616, row.live_operand)
                    self.assertNotIn(0xC629, row.live_operand)

    def test_stock_opcode_and_operand_must_match_even_if_rom_identity_is_rebound(self):
        original = self.rom.read_bytes()
        for offset in (0x3C728, 0x3C729, 0x3C616, 0x3C617):
            image = bytearray(original); image[offset] ^= 1; self.rom.write_bytes(image)
            policy = json.loads(self.policy.read_text()); policy["rom_sha256"] = native_batch.digest(image)
            self.policy.write_text(json.dumps(policy), encoding="utf-8")
            with self.subTest(offset=hex(offset)), self.assertRaisesRegex(ValueError, "opcode/operand"):
                self.prep()

    def test_changed_patch_source_or_cull_guard_fails_closed(self):
        source = self.source.read_text()
        for changed in (source.replace("0x0010, 1, 0", "0x0011, 1, 0"),
                        source.replace("kWramCullCamera = 0x1E00", "kWramCullCamera = 0x1E02")):
            self.source.write_text(changed, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "patch contract"):
                self.prep()
        self.source.write_text(source, encoding="utf-8")
        policy = json.loads(self.policy.read_text()); policy["guard_ranges"][-1]["end_exclusive"] = "03C900"
        self.policy.write_text(json.dumps(policy), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "complete culling guard"):
            self.prep()

    def test_existing_patch_directive_does_not_silently_add_duplicate_or_abs_site(self):
        for pc in (0xC728, 0xC616):
            self.cfg03.write_text(f"bank = 3\nlive_operand {pc:04X}\n", encoding="utf-8")
            with self.subTest(pc=hex(pc)), self.assertRaisesRegex(ValueError, "already have live_operand"):
                self.prep()

    def test_each_preparation_identity_change_refuses_before_process_launch(self):
        receipt = self.prep()
        paths = (self.cfg00, self.work / "cfg/bank03.cfg", self.work / "effective-policy.json",
                 self.policy, self.source, self.project / "snesrecomp/snesrecomp_cli.py",
                 self.project / "framework_pins.txt", self.rom)
        for path in paths:
            raw = path.read_bytes()
            path.write_bytes(raw + (b" " if path.suffix == ".json" else b"\n"))
            try:
                with self.subTest(path=path.name), patch.object(native_batch, "bounded_run") as launch:
                    with self.assertRaises(ValueError): native_batch.generate(receipt, self.work)
                    launch.assert_not_called()
            finally:
                path.write_bytes(raw)
        with patch.dict("os.environ", {"SNESRECOMP_EMIT_AOT_DENY_GATE": "1"}), \
                patch.object(native_batch, "bounded_run") as launch:
            with self.assertRaises(ValueError): native_batch.generate(receipt, self.work)
            launch.assert_not_called()
        receipt["generation_command"].append("--unexpected-change")
        with patch.object(native_batch, "bounded_run") as launch:
            with self.assertRaises(ValueError): native_batch.generate(receipt, self.work)
            launch.assert_not_called()

    def test_unbound_sdk_or_explicit_analyzer_override_is_refused(self):
        with patch.dict("os.environ", {"SNESRECOMP_ROOT": str(self.project / "other-sdk")}):
            with self.assertRaisesRegex(ValueError, "SDK source root"):
                self.prep()
        analyzer = self.project / "explicit-analyzer.exe"
        analyzer.write_bytes(b"synthetic executable identity, never executed")
        with patch.dict("os.environ", {"SNESRECOMP_NATIVE_ANALYZER": str(analyzer)}):
            with self.assertRaisesRegex(ValueError, "matching source stamp"):
                self.prep()

    def test_default_analyzer_cold_build_and_stale_rebuild_preserve_reuse(self):
        crate = self.project / "snesrecomp/recompiler-rs"
        (crate / "src").mkdir(parents=True)
        (crate / "src/main.rs").write_text("// synthetic analyzer source\n", encoding="utf-8")
        for cold in (True, False):
            with self.subTest(cold_build=cold):
                self.work = self.project / (".local/cold" if cold else ".local/rebuild")
                identity = native_batch.generator_identity()
                analyzer = Path(identity["analyzer_path"]); analyzer.parent.mkdir(parents=True, exist_ok=True)
                stamp = analyzer.with_name(analyzer.name + ".source-sha256")
                if not cold:
                    analyzer.write_bytes(b"synthetic stale analyzer")
                    stamp.write_text("stale source stamp", encoding="ascii")
                receipt = self.prep()
                initial = receipt["sprite_prefixes"]["analyzer_at_prepare"]
                generated = self.work / "generated"; generated.mkdir()
                (generated / "program_manifest.json").write_text(json.dumps({"roots": [], "nodes": {}}), encoding="utf-8")
                (generated / ".snesrecomp-cache.json").write_text(json.dumps(dict(
                    format_version=5, generator_digest="a" * 64, config_digest="b" * 64,
                    analysis_input_digest="c" * 64)), encoding="utf-8")
                def synthetic_sdk_build(*args):
                    # Reproduce the SDK's documented cold/stale default behavior.
                    analyzer.write_bytes(b"synthetic current analyzer, never executed")
                    stamp.write_text(identity["analyzer_sources_sha256"] + "\n", encoding="ascii")
                    return {"exit_code": 0}
                with patch.object(native_batch, "bounded_run", side_effect=synthetic_sdk_build):
                    first = native_batch.generate(receipt, self.work)
                self.assertEqual(first["exit_code"], 0)
                self.assertEqual(first["sprite_prefixes"]["analyzer_before"], initial)
                self.assertNotEqual(first["sprite_prefixes"]["analyzer_before"], first["sprite_prefixes"]["analyzer_after"])
                self.assertEqual(identity, native_batch.generator_identity())
                self.assertEqual(receipt, self.prep())
                with patch.object(native_batch, "bounded_run", return_value={"exit_code": 0}):
                    second = native_batch.generate(receipt, self.work)
                self.assertEqual(second["exit_code"], 0)
                self.assertEqual(second["sprite_prefixes"]["analyzer_before"], second["sprite_prefixes"]["analyzer_after"])

    def test_explicit_analyzer_binary_and_stamp_remain_pinned(self):
        crate = self.project / "snesrecomp/recompiler-rs"
        (crate / "src").mkdir(parents=True)
        (crate / "src/main.rs").write_text("// synthetic analyzer source\n", encoding="utf-8")
        source_hash = native_batch.generator_identity()["analyzer_sources_sha256"]
        analyzer = self.project / "explicit.exe"; analyzer.write_bytes(b"synthetic analyzer")
        stamp = analyzer.with_name(analyzer.name + ".source-sha256")
        stamp.write_text(source_hash + "\n", encoding="ascii")
        with patch.dict("os.environ", {"SNESRECOMP_NATIVE_ANALYZER": str(analyzer)}):
            receipt = self.prep()
            for path in (analyzer, stamp):
                raw = path.read_bytes(); path.write_bytes(raw + b"x")
                try:
                    with self.subTest(path=path.name), patch.object(native_batch, "bounded_run") as launch:
                        with self.assertRaises(ValueError): native_batch.generate(receipt, self.work)
                        launch.assert_not_called()
                finally:
                    path.write_bytes(raw)

    def test_generation_validates_against_effective_guard_and_records_cache_identity(self):
        receipt = self.prep()
        generated = self.work / "generated"; generated.mkdir()
        manifest = {"roots": ["synthetic"], "nodes": {"synthetic": {
            "disposition": "aot_eligible", "min_pc24": 0x83C714, "max_pc24": 0x83C750}}}
        cache = dict(format_version=5, generator_digest="a" * 64, config_digest="b" * 64,
                     analysis_input_digest="c" * 64)
        (generated / ".snesrecomp-cache.json").write_text(json.dumps(cache), encoding="utf-8")
        (generated / "program_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with patch.object(native_batch, "bounded_run", return_value={"exit_code": 0}):
            result = native_batch.generate(receipt, self.work)
        self.assertEqual(result["exit_code"], 0)  # Global policy would reject it.
        self.assertFalse(result["guarded_range_violations"])
        self.assertEqual(result["sprite_prefixes"]["generator_digest"], "a" * 64)
        self.assertEqual(result["sprite_prefixes"]["effective_policy_sha256"], receipt["policy_sha256"])
        manifest["nodes"]["synthetic"].update(min_pc24=0x83C616, max_pc24=0x83C619)
        (generated / "program_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with patch.object(native_batch, "bounded_run", return_value={"exit_code": 0}):
            result = native_batch.generate(receipt, self.work)
        self.assertEqual(result["exit_code"], 3)
        self.assertEqual(result["guarded_range_violations"], ["synthetic"])
        del cache["analysis_input_digest"]
        (generated / ".snesrecomp-cache.json").write_text(json.dumps(cache), encoding="utf-8")
        with patch.object(native_batch, "bounded_run", return_value={"exit_code": 0}), \
                self.assertRaisesRegex(ValueError, "cache identities"):
            native_batch.generate(receipt, self.work)


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
