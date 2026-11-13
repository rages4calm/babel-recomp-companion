"""ROM-free title-policy boundaries for explicit fixed-instruction scopes."""
import json
from pathlib import Path
import unittest
from native_effects import validate_owner_policy

ROOT=Path(__file__).resolve().parents[1]


class FixedInstructionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy=json.loads((ROOT/'recomp/native/policy.json').read_text())

    def check(self,pc,flags=None,nmi=False,opcode=0xea):
        key=(pc,0,0,0)
        validate_owner_policy({key:{'bytes':bytes([opcode])}},{}if flags is None else{key:flags},{key}if nmi else set(),self.policy)

    def test_existing_ordinary_selection_keeps_legacy_contract(self):
        self.check(0x838100)

    def test_all_four_protected_aliases_need_explicit_owner(self):
        for upper in(0,0x40,0x80,0xc0):
            for pc in(0x82ff,0x028100):
                with self.assertRaises(ValueError):self.check(upper<<16|pc)
                self.check(upper<<16|pc,1)

    def test_nmi_scope_needs_separate_exact_grant(self):
        for flags in(2,3):
            with self.assertRaises(ValueError):self.check(0x8082ff,flags)
            self.check(0x8082ff,flags,True)

    def test_only_two_long_jump_vectors_allowed(self):
        for pc in(0x8007,0x800b):
            self.check(pc,1,opcode=0x5c)
            with self.assertRaises(ValueError):self.check(pc,1)
            with self.assertRaises(ValueError):self.check(pc,opcode=0x5c)

    def test_reset_and_irq_remain_excluded(self):
        for pc in(0x8000,0x8006,0x800f,0x8013):
            with self.assertRaises(ValueError):self.check(pc,3,True,0x5c)

    def test_rdnmi_controls_remain_excluded(self):
        for pc in self.policy['fixed_instruction_scopes']['forbidden_sites']:
            with self.assertRaises(ValueError):self.check(int(pc,16),3,True)

    def test_whole_function_floors_do_not_revoke_existing_fixed_effects(self):
        for pc in self.policy['fixed_instruction_scopes']['historical_whole_function_NMI_floors']:
            self.check(int(pc,16))

    def test_bad_scope_types_and_bits_refused(self):
        for flags in(0,4,True,'1',None):
            with self.assertRaises(ValueError):self.check(0x828100,flags)

    def test_missing_policy_refused(self):
        with self.assertRaises(ValueError):validate_owner_policy({}, {},set(),{})


if __name__=='__main__':unittest.main()
