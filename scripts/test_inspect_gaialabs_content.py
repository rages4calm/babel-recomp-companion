"""Synthetic private-build admission tests; no game data or runtime needed."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import inspect_gaialabs_content as subject


class ReceivedContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        image = bytearray(65536); image[0xFFD5] = 0x31; image[0xFFFC:0xFFFE] = b"\x00\x80"
        self.rom = self.root / "fixture.smc"; self.rom.write_bytes(image)
        self.bso = self.root / "fixture.bso"; self.bso.write_bytes(b"synthetic")
        self.archive = self.root / "fixture.zip"
        self.make_zip()

    def make_zip(self, altered=False, extra=False):
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(self.rom.name, self.rom.read_bytes())
            z.writestr(self.bso.name, b"different" if altered else self.bso.read_bytes())
            if extra: z.writestr("../escape", b"x")

    def args(self):
        result = []
        for path in (self.archive, self.rom, self.bso):
            result += [path, hashlib.sha256(path.read_bytes()).hexdigest()]
        return result

    def test_exact_members_and_no_mutation(self):
        before = [p.read_bytes() for p in (self.archive, self.rom, self.bso)]
        result = subject.inspect_received(*self.args())
        self.assertTrue(result["archive_members_match"])
        self.assertEqual(result["rom"]["bare_bytes"], 65536)
        self.assertEqual(before, [p.read_bytes() for p in (self.archive, self.rom, self.bso)])

    def test_external_hash_mismatch(self):
        args = self.args(); args[3] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            subject.inspect_received(*args)

    def test_archive_payload_mismatch(self):
        self.make_zip(altered=True)
        with self.assertRaisesRegex(ValueError, "differs"):
            subject.inspect_received(*self.args())

    def test_extra_or_escaping_member(self):
        self.make_zip(extra=True)
        with self.assertRaisesRegex(ValueError, "exactly"):
            subject.inspect_received(*self.args())

    def test_invalid_header_is_not_runtime_admission(self):
        self.rom.write_bytes(bytes(65536)); self.make_zip()
        with self.assertRaisesRegex(ValueError, "HiROM"):
            subject.inspect_received(*self.args())

    def test_diagnostic_never_mints_qualified_profile(self):
        with patch.object(subject, "inspect_source", return_value={"candidate_map_inputs": []}):
            result = subject.inspect(*self.args(), self.root, "a" * 40)
        self.assertIsNone(result["edition_contract"]["gaialabs_profile"])
        self.assertFalse(result["runtime_support_enabled"])
        self.assertFalse(result["native_graph_bound"])
        self.assertFalse(result["source_recipe_reproduced"])
        self.assertIn("modules_in_order", result["edition_contract"]["missing_matching_recipe_fields"])


if __name__ == "__main__":
    unittest.main()
