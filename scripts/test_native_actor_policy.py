"""ROM-free actor selection must preserve the live culling operand boundary."""
import json
from pathlib import Path
import re
import unittest

from native_effects import validate_owner_policy

ROOT = Path(__file__).resolve().parents[1]


class ImmutableActorPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / "recomp/native/policy.json").read_text())
        self.contract = self.policy["fixed_instruction_scopes"]
        self.ranges = [(int(row["start"], 16), int(row["end_exclusive"], 16))
                       for row in self.contract["mutable_operand_ranges"]]

    def check(self, pc, length=1, scopes=1, nmi=False):
        key = pc, 0, 0, 0
        validate_owner_policy({key: {"bytes": bytes([0xEA]) * length}},
                              {} if scopes is None else {key: scopes},
                              {key} if nmi else set(), self.policy)

    def test_operand_intervals_match_every_actual_culling_patch_word(self):
        source = (ROOT / "src/iog_widescreen.c").read_text()
        sites = source.split("static const CullSite kCullSites[] = {", 1)[1].split("};", 1)[0]
        offsets = [int(value, 16) for value in re.findall(r"\{0x([0-9A-Fa-f]+),", sites)]
        self.assertEqual(len(offsets), 10)
        self.assertEqual(self.ranges, [(value, value + 2) for value in offsets])
        self.assertEqual(len({byte for lo, hi in self.ranges for byte in range(lo, hi)}), 20)

    def test_any_intersecting_instruction_byte_is_excluded_in_every_alias(self):
        for alias in (0, 0x400000, 0x800000, 0xC00000):
            for lo, hi in self.ranges:
                for length in range(1, 5):
                    for start in range(lo - length + 1, hi):
                        with self.subTest(alias=alias, pc=start, length=length):
                            with self.assertRaisesRegex(ValueError, "live patched operand"):
                                self.check(alias | start, length, scopes=3, nmi=True)

    def test_neighboring_immutable_bytes_do_not_gain_an_extra_exclusion(self):
        for alias in (0, 0x400000, 0x800000, 0xC00000):
            for lo, hi in self.ranges:
                self.check(alias | (lo - 1))
                self.check(alias | hi)

    def test_actor_instructions_require_exact_owner_scope_and_nmi_grant(self):
        for alias in (0, 0x400000, 0x800000, 0xC00000):
            pc = alias | 0x03C600
            for flags in (None, 0, 4, True, "1"):
                with self.assertRaises(ValueError):
                    self.check(pc, scopes=flags)
            self.check(pc, scopes=1)
            for flags in (2, 3):
                with self.assertRaises(ValueError):
                    self.check(pc, scopes=flags)
                self.check(pc, scopes=flags, nmi=True)
            self.check(alias | 0x03C5FE, scopes=None)
            self.check(alias | 0x03CA00, scopes=None)

    def test_whole_function_and_rdnmi_barriers_remain(self):
        self.assertEqual([(row["start"], row["end_exclusive"])
                          for row in self.policy["guard_ranges"]],
                         [("008000", "008014"), ("0082DE", "008387"),
                          ("02803B", "028191"), ("03C5FF", "03CA00")])
        self.assertEqual(self.contract["forbidden_sites"],
                         ["828049", "82804D", "828051", "828053", "828195"])
        for pc in self.contract["forbidden_sites"]:
            with self.assertRaises(ValueError):
                self.check(int(pc, 16), scopes=3, nmi=True)


if __name__ == "__main__":
    unittest.main()
