"""ROM-free mixed alias recipes preserve existing keys and exact new grants."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import native_effects as driver


class AliasRecipeTests(unittest.TestCase):
    def test_legacy_default_and_false_keep_all_four_banks(self):
        row = dict(pc24="838100")
        self.assertEqual(driver.context_banks(row), [3, 0x43, 0x83, 0xC3])
        self.assertEqual(driver.context_banks(dict(row, physical_only=False)),
                         driver.context_banks(row))

    def test_explicit_physical_and_global_no_aliases(self):
        row = dict(pc24="838100", physical_only=True)
        self.assertEqual(driver.context_banks(row), [0x83])
        self.assertEqual(driver.context_banks(row, False), [0x83])
        self.assertEqual(driver.context_banks(dict(pc24="438100"), False), [0x43])

    def test_invalid_physical_flag_cannot_fall_back_to_expansion(self):
        for value in (0, 1, None, "true", [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                driver.context_banks(dict(pc24="838100", physical_only=value))

    def test_address_must_fit_the_physical_bus(self):
        for pc in ("-1", "1000000"):
            with self.subTest(pc=pc), self.assertRaises(ValueError):
                driver.context_banks(dict(pc24=pc, physical_only=True))

    def fixture(self, folder):
        real = driver.ROOT
        root = Path(folder)
        image = bytearray([0xEA]) * 2097152
        driver.decoder.set_rom_mapping("hirom")
        rows = []
        for pc, code, mnemonic, exact in ((0x838100, b"\xA9\x34\x12", "LDA", False),
                                         (0x838104, b"\x02\x00", "COP", True),
                                         (0x838108, b"\x54\x7F\x7E", "MVN", True)):
            offset = driver.decoder.rom_offset(pc >> 16, pc & 65535)
            image[offset:offset + len(code)] = code
            row = dict(pc24=f"{pc:06X}", m=0, x=0, e=0,
                       original_bytes=code.hex(), mnemonic=mnemonic)
            if exact:
                row["physical_only"] = True
            rows.append(row)
        rom = root / "synthetic.sfc"
        rom.write_bytes(image)
        digest = hashlib.sha256(image).hexdigest()
        (root / "rom_identity.txt").write_text("expected_sha256 = " + digest + "\n")
        for name in ("snesrecomp/runner/src/snes/interp816.c",
                     "snesrecomp/recompiler/v2/native_effects.py"):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(real / name, target)
        policy = root / "recomp/native/policy.json"
        policy.parent.mkdir(parents=True)
        policy.write_text(json.dumps(dict(fixed_instruction_scopes=dict(
            schema="gaia fixed instruction owner scopes v1", scope_only_ranges=[],
            forbidden_sites=[], vector_jumps=[]))))
        plan = dict(rom_sha256=digest, candidate_contexts=rows,
                    native_nmi_owner_entry_pc24="00800B",
                    native_nmi_grant_contexts=[copy.deepcopy(rows[0])],
                    native_frame_grant_contexts=[copy.deepcopy(rows[1])],
                    native_owner_scope_contexts=[dict(r, scopes=3 if i == 0 else 1)
                                                 for i, r in enumerate(rows)])
        return root, rom, plan

    def prepare(self, root, rom, plan, name, **kwargs):
        context = root / (name + ".json")
        context.write_text(json.dumps(plan))
        output = root / ".local" / name
        with patch.object(driver, "ROOT", root):
            receipt = driver.prepare(rom, context, output, **kwargs)
        return receipt, (output / "native_continuations.c").read_text()

    def test_mixed_candidates_and_all_permission_lists_keep_the_same_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            root, rom, plan = self.fixture(folder)
            receipt, text = self.prepare(root, rom, plan, "mixed", outline_effects=True)
            self.assertEqual((receipt["entries"], receipt["native_nmi_grants"],
                              receipt["native_frame_grants"], receipt["native_owner_scope_limits"]),
                             (6, 4, 1, 6))
            self.assertEqual((receipt["physical_only_source_contexts"], receipt["legacy_source_contexts"]), (2, 1))
            for bank in (3, 0x43, 0x83, 0xC3):
                self.assertIn(f"static int ni_at_{bank:02X}8100_00", text)
                for pc in (0x8104, 0x8108):
                    self.assertEqual(f"static int ni_at_{bank:02X}{pc:04X}_00" in text, bank == 0x83)

    def test_annotation_cannot_expand_an_exact_frame_into_unregistered_aliases(self):
        with tempfile.TemporaryDirectory() as folder:
            root, rom, plan = self.fixture(folder)
            plan["native_frame_grant_contexts"][0].pop("physical_only")
            with self.assertRaisesRegex(ValueError, "unregistered frame"):
                self.prepare(root, rom, plan, "bad_frame")
            self.assertFalse((root / ".local/bad_frame").exists())

    def test_global_no_aliases_still_restricts_legacy_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            root, rom, plan = self.fixture(folder)
            receipt, _ = self.prepare(root, rom, plan, "no_aliases", aliases=False)
            self.assertEqual((receipt["entries"], receipt["native_nmi_grants"],
                              receipt["native_frame_grants"]), (3, 1, 1))

    def test_explicit_false_preserves_legacy_generated_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root, rom, plan = self.fixture(folder)
            for key in ("candidate_contexts", "native_nmi_grant_contexts", "native_owner_scope_contexts"):
                plan[key] = plan[key][:1]
            plan["native_frame_grant_contexts"] = []
            first, text = self.prepare(root, rom, plan, "legacy", outline_effects=True)
            for key in ("candidate_contexts", "native_nmi_grant_contexts", "native_owner_scope_contexts"):
                plan[key][0]["physical_only"] = False
            second, other = self.prepare(root, rom, plan, "false", outline_effects=True)
            self.assertEqual(text, other)
            self.assertEqual(first["generated_source_sha256"], second["generated_source_sha256"])
            self.assertNotIn("physical_only_source_contexts", first)
            self.assertNotIn("physical_only_source_contexts", second)


if __name__ == "__main__":
    unittest.main()
