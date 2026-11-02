"""Synthetic packaging gates: no real game inputs or executables required."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from package_release import PUBLIC_ID, PRIVATE_ID, package


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / "build"
        self.build.mkdir()
        for path in ("assets/image.txt", "i18n/structure.txt", "mods/preloaded/catalog.txt"):
            target = self.build / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("synthetic")
        for path in ("LICENSE", "README.md", "MODS.md", "VERSION", "mods/preloaded/catalog.txt", "snesrecomp/LICENSE",
                     "snesrecomp/THIRD_PARTY_ATTRIBUTION.md", "recomp-ui/LICENSE",
                     "build/_deps/sdl3-src/LICENSE.txt"):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("1.0" if path == "VERSION" else "synthetic notice")
        (self.build / "CMakeCache.txt").write_text("SNESRECOMP_INTERPRETER_ONLY:BOOL=ON\n")
        self.binary = self.build / "babel-recomp.exe"
        self.binary.write_bytes(PUBLIC_ID)

    def pack(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return package(self.build, "windows-test", self.root)

    def test_notices_and_no_owner_state(self):
        (self.build / "config.ini").write_text("owner data - must not ship")
        (self.build / "mods/preloaded/state.toml").write_text("owner mod preferences")
        with zipfile.ZipFile(self.pack()) as archive:
            names = archive.namelist()
        self.assertTrue(any(n.endswith("licenses/snesrecomp/THIRD_PARTY_ATTRIBUTION.md") for n in names))
        self.assertTrue(any(n.endswith("licenses/dependencies/sdl3-src/LICENSE.txt") for n in names))
        self.assertFalse(any(n.endswith("config.ini") for n in names))
        self.assertFalse(any(n.endswith("state.toml") for n in names))

    def test_aot_cache_rejected(self):
        (self.build / "CMakeCache.txt").write_text("SNESRECOMP_INTERPRETER_ONLY:BOOL=OFF\n")
        with self.assertRaisesRegex(ValueError, "INTERPRETER_ONLY"):
            self.pack()

    def test_stale_aot_binary_rejected_even_with_on_cache(self):
        self.binary.write_bytes(PRIVATE_ID)
        with self.assertRaisesRegex(ValueError, "identity"):
            self.pack()

    def test_legacy_unstamped_binary_rejected(self):
        self.binary.write_bytes(b"old executable")
        with self.assertRaisesRegex(ValueError, "identity"):
            self.pack()

    def test_private_nested_data_preserves_previous_archive(self):
        previous = self.pack()
        content = previous.read_bytes()
        (self.root / "mods/preloaded/private.SFC").write_bytes(b"synthetic")
        with self.assertRaisesRegex(ValueError, "Private/player"):
            self.pack()
        self.assertEqual(previous.read_bytes(), content)
        self.assertEqual(list((self.root / "dist").glob(".package-*")), [])

    def test_missing_notice_rejected(self):
        (self.root / "recomp-ui/LICENSE").unlink()
        with self.assertRaisesRegex(ValueError, "license missing"):
            self.pack()

    def test_path_traversal_tag_rejected(self):
        with self.assertRaisesRegex(ValueError, "platform tag"):
            package(self.build, "../../outside", self.root)


if __name__ == "__main__":
    unittest.main()
