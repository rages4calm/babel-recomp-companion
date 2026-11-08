"""Synthetic source-profile safety tests; no ROMs or network needed."""
import base64
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import inspect_gaia_modules as subject


SOURCE = """import { rebuild as rebuildInternal } from '@gaialabs/iog-baserom';
export async function rebuild(inPath: string, outPath: string) {
    const modules = [
        './modules/base',
        './modules/dungeon-map',
        //'./modules/minimap-v2',
        './modules/walkable-world-map',
        //'./modules/widescreen'
    ];
    await rebuildInternal(inPath, outPath, null, modules, ["artifacts"]);
}
"""
MODULES = ["base", "dungeon-map", "minimap-v2", "walkable-world-map", "widescreen", "unlisted"]
DEPS = {"@gaialabs/core": "1.0.5", "@gaialabs/iog-baserom": "0.2.7"}
INTEGRITY = "sha512-" + base64.b64encode(bytes(range(64))).decode()


class SelectionTests(unittest.TestCase):
    def test_current_simple_array_preserves_order_and_comments(self):
        active, disabled = subject.selected_modules(SOURCE)
        self.assertEqual(active, ["base", "dungeon-map", "walkable-world-map"])
        self.assertEqual(disabled, ["minimap-v2", "widescreen"])

    def test_code_in_comments_and_strings_is_not_a_selection(self):
        sample = "// const modules = ['bad'];\nconst example = \"const modules = ['bad'];\";\n"
        self.assertEqual(subject.selected_modules(sample + SOURCE), subject.selected_modules(SOURCE))

    def test_malformed_dynamic_and_escape_selections_refused(self):
        for replacement in ["'../modules/base',", "'./modules/../escape',", "'C:/secret',",
                            "...otherModules,", "pickModule(),", "'./modules/base', './modules/widescreen',",
                            "'./modules/base',\n './modules/base',", "'./modules/bad_name',"]:
            with self.subTest(replacement=replacement), self.assertRaises(subject.InspectionError):
                subject.selected_modules(SOURCE.replace("'./modules/base',", replacement))

    def test_mutation_or_missing_forwarding_refused(self):
        for suffix in ["modules.push('other');", "const alias = modules;", "const x = `${modules.pop()}`;"]:
            with self.subTest(suffix=suffix), self.assertRaises(subject.InspectionError):
                subject.selected_modules(SOURCE + suffix)
        with self.assertRaises(subject.InspectionError):
            subject.selected_modules(SOURCE.replace("null, modules,", "null, other,"))

    def test_manifest_does_not_imply_activation(self):
        manifest = {"modules": [{"groups": [{"options": [{"module": None}, {"module": "widescreen"}]}]}]}
        self.assertEqual(subject.manifest_modules(manifest), ["widescreen"])
        for bad in ["../outside", "C:/outside", "bad/name", "bad\\name", 1]:
            with self.subTest(bad=bad), self.assertRaises(subject.InspectionError):
                subject.manifest_modules({"modules": [{"groups": [{"options": [{"module": bad}]}]}]})

    def test_duplicate_json_and_nonfinite_metadata_refused(self):
        for text in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e9999}']:
            with self.subTest(text=text), self.assertRaises(subject.InspectionError):
                subject.json_text(text)


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.translation = self.root / "translation"
        self.base = self.root / "baserom"
        self.hooks = self.root / "empty-hooks"
        self.hooks.mkdir()
        for root in (self.translation, self.base):
            root.mkdir()
            self.run_git(root, "init", "--quiet")
            self.write(root, "LICENSE", "Synthetic root GPL notice\n")
            self.write(root, ".gitignore", ".ignored\n")
        self.write(self.translation, "scripts/index.ts", SOURCE)
        self.write(self.translation, "modules/manifest.json", json.dumps({"modules": [{"groups": [{"options": [{"module": "widescreen"}, {"module": None}]}]}]}))
        self.write(self.translation, "package.json", json.dumps({"devDependencies": DEPS}))
        self.lock = {"packages": {"": {"devDependencies": DEPS}}}
        for name, version in DEPS.items():
            self.lock["packages"]["node_modules/" + name] = {
                "version": version, "resolved": f"https://registry.npmjs.org/{name}/-/{name.split('/')[-1]}-{version}.tgz",
                "integrity": INTEGRITY, "license": "MIT"}
        self.write(self.translation, "package-lock.json", json.dumps(self.lock))
        for name in MODULES:
            self.write(self.translation, f"modules/{name}/feature.patch.asm", "; synthetic input\n")
        self.write(self.translation, "modules/widescreen/map_synthetic.map", "synthetic binary placeholder")
        self.write(self.base, "src/index.ts", "// synthetic; never executed\n")
        self.write(self.base, "package.json", '{"name":"@gaialabs/iog-baserom","version":"0.2.7","license":"MIT"}')
        self.types = {"Tilemap": {"extension": "map", "header": 2, "compressed": True, "type": "Tilemap"}}
        self.write(self.base, "db-us/fileTypes.json", json.dumps(self.types))
        self.write(self.base, "baserom/base.patch.asm", "; synthetic\n")
        self.translation_commit = self.commit(self.translation)
        self.base_commit = self.commit(self.base)

    @staticmethod
    def write(root, path, data):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding="utf-8")

    def run_git(self, root, *args):
        result = subprocess.run(["git", "-c", "core.hooksPath=" + str(self.hooks), "-c", "user.name=Synthetic Test",
                                 "-c", "user.email=synthetic@example.invalid", "-C", str(root), *args],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self, root):
        self.run_git(root, "add", "--all")
        self.run_git(root, "commit", "--quiet", "-m", "Synthetic fixture")
        return self.run_git(root, "rev-parse", "HEAD")

    def inspect(self, metadata=None):
        return subject.inspect(self.translation, self.translation_commit, self.base, self.base_commit, metadata)

    def changed_lock(self):
        self.write(self.translation, "package-lock.json", json.dumps(self.lock))
        self.translation_commit = self.commit(self.translation)

    def test_clean_pinned_profile_hashes_inputs_without_copying_content(self):
        before = {str(p): p.read_bytes() for root in (self.translation, self.base) for p in root.rglob("*") if p.is_file() and ".git" not in p.parts}
        report = self.inspect()
        self.assertFalse(report["native_qualified"])
        self.assertFalse(report["build_executed"])
        self.assertEqual(report["commented_modules"], ["minimap-v2", "widescreen"])
        self.assertEqual(report["manifest_modules"], ["widescreen"])
        self.assertIn("unlisted", report["module_files"])
        item = report["module_files"]["widescreen"][-1]
        self.assertEqual(len(item["sha256"]), 64)
        self.assertNotIn("synthetic binary placeholder", json.dumps(report))
        self.assertEqual(before, {str(p): p.read_bytes() for root in (self.translation, self.base) for p in root.rglob("*") if p.is_file() and ".git" not in p.parts})

    def test_wrong_commit_and_short_commit_refused(self):
        for commit in ["0" * 40, self.translation_commit[:8], "main"]:
            with self.subTest(commit=commit), self.assertRaises(subject.InspectionError):
                subject.checkout(self.translation, commit)

    def test_dirty_tracked_and_untracked_checkout_refused(self):
        path = self.translation / "scripts/index.ts"
        path.write_text(SOURCE + "\n// changed", encoding="utf-8")
        with self.assertRaisesRegex(subject.InspectionError, "Dirty"):
            self.inspect()
        path.write_text(SOURCE, encoding="utf-8")
        (self.translation / "untracked.txt").write_text("new", encoding="utf-8")
        with self.assertRaisesRegex(subject.InspectionError, "Dirty"):
            self.inspect()

    def test_ignored_added_module_file_is_not_silently_ingested(self):
        self.write(self.translation, "modules/base/.ignored", "not covered by commit")
        self.assertEqual(self.run_git(self.translation, "status", "--porcelain"), "")
        with self.assertRaisesRegex(subject.InspectionError, "tracked regular"):
            self.inspect()

    def test_ignored_added_baserom_file_is_not_silently_ingested(self):
        self.write(self.base, "baserom/.ignored", "not covered by commit")
        with self.assertRaisesRegex(subject.InspectionError, "tracked regular"):
            self.inspect()

    def test_symlink_module_or_file_refused(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "payload.patch.asm").write_text("private", encoding="utf-8")
        link = self.translation / "modules" / "escape"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symlink creation unavailable: {error}")
        # A gitignored link must still be rejected during module traversal.
        self.write(self.translation, ".gitignore", ".ignored\nmodules/escape\n")
        self.translation_commit = self.commit(self.translation)
        with self.assertRaisesRegex(subject.InspectionError, "Symlink/junction"):
            self.inspect()

    def test_path_traversal_and_missing_module_refused(self):
        for value in ["../outside", "modules/../outside", "C:/outside", "modules\\base"]:
            with self.subTest(value=value), self.assertRaises(subject.InspectionError):
                subject.safe_path(self.translation.resolve(), value)
        self.write(self.translation, "scripts/index.ts", SOURCE.replace("modules/base", "modules/missing"))
        self.translation_commit = self.commit(self.translation)
        with self.assertRaisesRegex(subject.InspectionError, "Missing module"):
            self.inspect()

    def test_lock_version_declaration_registry_or_integrity_mismatch_refused(self):
        initial = copy.deepcopy(self.lock)
        cases = [("version", "9.9.9"), ("resolved", "https://example.invalid/tool.tgz"),
                 ("integrity", "sha512-bad"), ("integrity", "sha256-" + base64.b64encode(bytes(32)).decode())]
        for key, value in cases:
            self.lock = copy.deepcopy(initial)
            self.lock["packages"]["node_modules/@gaialabs/core"][key] = value
            self.changed_lock()
            with self.subTest(key=key, value=value), self.assertRaises(subject.InspectionError):
                self.inspect()
        self.lock = copy.deepcopy(initial)
        self.lock["packages"][""]["devDependencies"] = {**DEPS, "@gaialabs/core": "9.9.9"}
        self.changed_lock()
        with self.assertRaisesRegex(subject.InspectionError, "Root dependency"):
            self.inspect()

    def test_optional_local_registry_metadata_must_match_lock(self):
        registry = {name: {"name": name, "version": version, "license": "MIT", "gitHead": "a" * 40,
                           "dist": {"integrity": INTEGRITY, "tarball": self.lock["packages"]["node_modules/" + name]["resolved"]}}
                    for name, version in DEPS.items()}
        report = self.inspect(registry)
        self.assertEqual(report["dependencies"]["@gaialabs/core"]["npm_git_head"], "a" * 40)
        registry["@gaialabs/core"]["dist"]["integrity"] = "other"
        with self.assertRaisesRegex(subject.InspectionError, "metadata integrity"):
            self.inspect(registry)

    def test_raw_map_format_change_requires_review(self):
        self.types["Tilemap"]["header"] = 4
        self.write(self.base, "db-us/fileTypes.json", json.dumps(self.types))
        self.base_commit = self.commit(self.base)
        with self.assertRaisesRegex(subject.InspectionError, "raw-map contract changed"):
            self.inspect()

    def test_output_outside_private_batch_is_refused_before_inspection(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = subject.main(["--retranslation", str(self.translation), "--retranslation-commit", self.translation_commit,
                                   "--baserom", str(self.base), "--baserom-commit", self.base_commit,
                                   "--output", str(self.root / "public.json")])
        self.assertEqual(result, 1)
        self.assertIn(".local/batch-001", output.getvalue())
        self.assertFalse((self.root / "public.json").exists())


if __name__ == "__main__":
    unittest.main()
