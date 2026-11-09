"""Edition identity/isolation checks with synthetic data only."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gaia_editions as edition


def build_identity(payload=b"x" * 32768):
    return {"rom_sha256": hashlib.sha256(payload).hexdigest(), "rom_size": len(payload),
            "source_commits": {"core": "1" * 40, "baserom": "2" * 40, "retranslation": "3" * 40},
            "modules_in_order": ["base", "dungeon-map", "walkable-world-map"],
            "dependency_lock_sha256": "4" * 64, "module_preflight_sha256": "5" * 64}


class ProfileTests(unittest.TestCase):
    def test_original_matches_repository_rom_pin(self):
        text = (edition.ROOT / "rom_identity.txt").read_text(encoding="utf-8")
        self.assertIn("expected_sha256 = " + edition.STOCK_SHA256, text)
        self.assertEqual(edition.original_profile()["build"],
                         {"rom_sha256": edition.STOCK_SHA256, "rom_size": 2097152})
        edition.require_runtime_support(edition.original_profile())

    def test_unknown_or_relabelled_original_is_refused(self):
        for key, value in [("edition", "redux"), ("schema", "future")]:
            profile = edition.original_profile()
            profile[key] = value
            with self.subTest(key=key), self.assertRaises(edition.EditionError):
                edition.validate_profile(profile)
        profile = edition.gaialabs_profile(build_identity())
        profile["edition"] = "original"
        with self.assertRaises(edition.EditionError):
            edition.validate_profile(profile)

    def test_gaialabs_pending_and_runtime_gate_fail_closed(self):
        with self.assertRaises(edition.EditionError):
            edition.gaialabs_profile()
        profile = edition.gaialabs_profile(build_identity())
        with self.assertRaisesRegex(edition.EditionError, "pending integration"):
            edition.require_runtime_support(profile)

    def test_missing_identity_components_are_refused(self):
        for field in edition.BUILD_FIELDS:
            build = build_identity()
            del build[field]
            with self.subTest(field=field), self.assertRaises(edition.EditionError):
                edition.gaialabs_profile(build)
        for field in edition.SOURCE_NAMES:
            build = build_identity()
            del build["source_commits"][field]
            with self.subTest(source=field), self.assertRaises(edition.EditionError):
                edition.gaialabs_profile(build)

    def test_module_order_and_every_hash_change_profile_identity(self):
        original = build_identity()
        expected = edition.gaialabs_profile(original)["profile_id"]
        for field in ["rom_sha256", "dependency_lock_sha256", "module_preflight_sha256", "source_commits", "modules_in_order"]:
            build = copy.deepcopy(original)
            if field == "source_commits":
                build[field]["core"] = "a" * 40
            elif field == "modules_in_order":
                build[field].reverse()
            else:
                build[field] = "a" * 64
            with self.subTest(field=field):
                self.assertNotEqual(edition.gaialabs_profile(build)["profile_id"], expected)
        self.assertEqual(edition.gaialabs_profile(dict(reversed(list(original.items()))))["profile_id"], expected)

    def test_modules_and_hashes_cannot_be_aliases(self):
        for name in ["../original", "original/saves", "C:/save", "\\server", "BASE", "", "base base", 1]:
            build = build_identity()
            build["modules_in_order"] = [name]
            with self.subTest(name=name), self.assertRaises(edition.EditionError):
                edition.gaialabs_profile(build)
        for value in ["main", "1" * 39, "A" * 40, None]:
            build = build_identity()
            build["source_commits"]["core"] = value
            with self.subTest(commit=value), self.assertRaises(edition.EditionError):
                edition.gaialabs_profile(build)
        for modules in [[], ["base", "base"], "base"]:
            build = build_identity()
            build["modules_in_order"] = modules
            with self.subTest(modules=modules), self.assertRaises(edition.EditionError):
                edition.gaialabs_profile(build)

    def test_profile_does_not_alias_mutable_input_or_accept_overrides(self):
        build = build_identity()
        profile = edition.gaialabs_profile(build)
        build["modules_in_order"].append("widescreen")
        self.assertNotIn("widescreen", profile["build"]["modules_in_order"])
        for key, value in [("namespace", "editions/original"), ("runtime_qualified", True)]:
            changed = copy.deepcopy(profile)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(edition.EditionError):
                edition.validate_profile(changed)
        profile["build"]["modules_in_order"].append("widescreen")
        with self.assertRaises(edition.EditionError):
            edition.namespaces(profile)


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.original = edition.original_profile()
        # Even an explicitly supplied matching ROM hash cannot merge editions.
        build = build_identity()
        build.update(rom_sha256=edition.STOCK_SHA256, rom_size=edition.STOCK_SIZE)
        self.gaia = edition.gaialabs_profile(build)

    def test_editions_never_share_save_settings_or_native_namespaces(self):
        one, two = edition.namespaces(self.original), edition.namespaces(self.gaia)
        self.assertTrue(set(one.values()).isdisjoint(two.values()))
        for paths in (one, two):
            self.assertEqual(len(paths.values()), len(set(paths.values())))
            self.assertTrue(all(not p.startswith(("/", "\\")) and ".." not in p.split("/")
                                for p in paths.values()))

    def test_state_bindings_cannot_cross_editions_profiles_or_paths(self):
        for kind in ("saves", "settings"):
            binding = edition.bind_state(self.original, kind)
            edition.validate_state_binding(self.original, binding, kind)
            with self.assertRaises(edition.EditionError):
                edition.validate_state_binding(self.gaia, binding, kind)
            for path in ["build/saves", "editions/gaialabs/../original/saves", "C:/owner/saves"]:
                changed = {**binding, "namespace": path}
                with self.subTest(kind=kind, path=path), self.assertRaises(edition.EditionError):
                    edition.validate_state_binding(self.original, changed, kind)
        with self.assertRaises(edition.EditionError):
            edition.bind_state(self.original, "other")

    def test_native_binding_checks_full_profile_and_cache_identity(self):
        binding = edition.bind_native_graph(self.original, "a" * 40, "b" * 64, "c" * 64)
        edition.validate_native_binding(self.original, binding)
        with self.assertRaises(edition.EditionError):
            edition.validate_native_binding(self.gaia, binding)
        for key in ["rom_sha256", "profile_id", "namespace", "schema"]:
            bad = {**binding, key: "wrong"}
            with self.subTest(key=key), self.assertRaises(edition.EditionError):
                edition.validate_native_binding(self.original, bad)
        for framework, manifest, generation in [("d" * 40, "b" * 64, "c" * 64),
                                                  ("a" * 40, "d" * 64, "c" * 64),
                                                  ("a" * 40, "b" * 64, "d" * 64)]:
            new = edition.bind_native_graph(self.original, framework, manifest, generation)
            self.assertNotEqual(new["namespace"], binding["namespace"])
        with self.assertRaises(edition.EditionError):
            edition.validate_native_binding(self.original, {})


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = b"x" * 32768
        self.rom = self.root / "synthetic.sfc"
        self.rom.write_bytes(self.payload)
        self.profile = edition.gaialabs_profile(build_identity(self.payload))

    def test_exact_image_and_copier_header_hash_the_same_payload(self):
        result = edition.verify_rom(self.profile, self.rom)
        self.assertFalse(result["copier_header_stripped"])
        headed = self.root / "headered.smc"
        headed.write_bytes(bytes(512) + self.payload)
        self.assertTrue(edition.verify_rom(self.profile, headed)["copier_header_stripped"])
        self.assertEqual(self.rom.read_bytes(), self.payload)

    def test_wrong_image_or_changed_bytes_do_not_reuse_profile(self):
        with self.assertRaises(edition.EditionError):
            edition.verify_rom(edition.original_profile(), self.rom)
        self.rom.write_bytes(b"y" + self.payload[1:])
        with self.assertRaises(edition.EditionError):
            edition.verify_rom(self.profile, self.rom)
        self.rom.write_bytes(self.payload + b"extra")
        with self.assertRaises(edition.EditionError):
            edition.verify_rom(self.profile, self.rom)

    def test_rom_symlink_refused(self):
        link = self.root / "alias.sfc"
        try:
            link.symlink_to(self.rom)
        except OSError as error:
            self.skipTest(f"Symlinks unavailable: {error}")
        with self.assertRaises(edition.EditionError):
            edition.verify_rom(self.profile, link)

    def test_cli_pending_gaialabs_or_original_override_creates_nothing(self):
        output = self.root / "no.json"
        for args in [["--edition", "gaialabs"],
                     ["--edition", "original", "--gaialabs-build", str(self.root / "build.json")]]:
            with self.subTest(args=args), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(edition.main([*args, "--rom", str(self.rom), "--output", str(output)]), 1)
            self.assertFalse(output.exists())

    def test_cli_rejects_nonprivate_or_existing_output(self):
        build = self.root / "build.json"
        build.write_text(json.dumps(build_identity(self.payload)), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            code = edition.main(["--edition", "gaialabs", "--gaialabs-build", str(build),
                                 "--rom", str(self.rom), "--output", str(self.root / "public.json")])
        self.assertEqual(code, 1)
        self.assertFalse((self.root / "public.json").exists())


class ActualInputBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.build = build_identity()
        self.lock = self.root / "package-lock.json"
        self.preflight = self.root / "module-preflight.json"
        self.deps = {"@gaialabs/core": {"version": "1.0.5", "resolved": "https://example.invalid/core.tgz",
                                      "integrity": "sha512-synthetic", "npm_git_head": "1" * 40},
                     "@gaialabs/iog-baserom": {"version": "0.2.7", "resolved": "https://example.invalid/base.tgz",
                                             "integrity": "sha512-synthetic", "npm_git_head": "2" * 40}}
        self.report = {"schema": "gaia-module-preflight-v1", "active_modules_in_order": self.build["modules_in_order"],
                       "baserom": {"commit": "2" * 40}, "retranslation": {"commit": "3" * 40},
                       "dependencies": self.deps}
        self.write_inputs()

    def write_inputs(self):
        lock = {"packages": {"node_modules/" + name: {key: dep[key] for key in ("version", "resolved", "integrity")}
                             for name, dep in self.deps.items()}}
        self.lock.write_text(json.dumps(lock), encoding="utf-8")
        self.preflight.write_text(json.dumps(self.report), encoding="utf-8")
        self.build["dependency_lock_sha256"] = hashlib.sha256(self.lock.read_bytes()).hexdigest()
        self.build["module_preflight_sha256"] = hashlib.sha256(self.preflight.read_bytes()).hexdigest()

    def check(self):
        return edition.verify_gaialabs_inputs(edition.gaialabs_profile(self.build), self.preflight, self.lock)

    def test_actual_receipt_order_sources_and_lock_agree(self):
        self.assertTrue(self.check()["module_order_and_sources_match"])
        with self.assertRaises(edition.EditionError):
            edition.verify_gaialabs_inputs(edition.original_profile(), self.preflight, self.lock)

    def test_hashes_cannot_hide_changed_input_files(self):
        for target in (self.lock, self.preflight):
            old = target.read_bytes()
            target.write_bytes(old + b" ")
            with self.subTest(target=target.name), self.assertRaises(edition.EditionError):
                self.check()
            target.write_bytes(old)

    def test_rehashed_wrong_order_or_source_still_refused(self):
        self.build["modules_in_order"] = list(reversed(self.build["modules_in_order"]))
        with self.assertRaises(edition.EditionError):
            self.check()
        self.build["modules_in_order"] = self.report["active_modules_in_order"]
        self.build["source_commits"]["baserom"] = "a" * 40
        with self.assertRaises(edition.EditionError):
            self.check()

    def test_current_source_and_older_package_commit_cannot_be_mixed(self):
        self.report["dependencies"]["@gaialabs/iog-baserom"]["npm_git_head"] = "a" * 40
        self.write_inputs()
        with self.assertRaisesRegex(edition.EditionError, "package/source identity"):
            self.check()

    def test_malformed_nested_receipts_fail_closed(self):
        for key, value in [("baserom", None), ("dependencies", []),
                           ("retranslation", "wrong")]:
            old = self.report[key]
            self.report[key] = value
            self.write_inputs()
            with self.subTest(key=key), self.assertRaises(edition.EditionError):
                self.check()
            self.report[key] = old

    def test_cli_writes_pending_metadata_only_and_never_overwrites(self):
        rom = self.root / "synthetic.sfc"
        rom.write_bytes(b"x" * 32768)
        build = self.root / "build.json"
        build.write_text(json.dumps(self.build), encoding="utf-8")
        output = self.root / ".local/batch-001/receipt.json"
        args = ["--edition", "gaialabs", "--gaialabs-build", str(build), "--module-preflight", str(self.preflight),
                "--dependency-lock", str(self.lock), "--rom", str(rom), "--output", str(output)]
        with patch.object(edition, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(edition.main(args), 0)
            old = output.read_bytes()
            self.assertEqual(edition.main(args), 1)
        self.assertEqual(output.read_bytes(), old)
        report = json.loads(old)
        self.assertEqual(report["runtime_integration"], "pending")
        self.assertFalse(report["native_qualified"])
        self.assertFalse(report["save_migration_performed"])
        self.assertFalse((self.root / "editions").exists())


if __name__ == "__main__":
    unittest.main()
