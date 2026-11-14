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

    def test_exact_acknowledgements_need_original_bytes_and_scheduler_only(self):
        for pc in (0x828049,0x828053,0x828195):
            key=(pc,1,0,0);entry={'bytes':bytes.fromhex('af104280'),'mnemonic':'LDA'}
            validate_owner_policy({key:entry},{key:1},set(),self.policy)
            for flags in (None,0,2,3,True,'1'):
                with self.assertRaises(ValueError):
                    validate_owner_policy({key:entry},{}if flags is None else{key:flags},set(),self.policy)
            with self.assertRaises(ValueError):validate_owner_policy({key:entry},{key:1},{key},self.policy)
            for byte in range(4):
                code=bytearray(entry['bytes']);code[byte]^=1
                with self.assertRaises(ValueError):validate_owner_policy({key:dict(entry,bytes=bytes(code))},{key:1},set(),self.policy)
            with self.assertRaises(ValueError):validate_owner_policy({key:dict(entry,mnemonic='NOP')},{key:1},set(),self.policy)

    def test_acknowledgements_do_not_expand_aliases_modes_or_poll_sites(self):
        entry={'bytes':bytes.fromhex('af104280'),'mnemonic':'LDA'}
        for pc in (0x828049,0x828053,0x828195):
            for bank in (2,0x42,0xc2):
                key=(bank<<16|(pc&0xffff),1,0,0)
                with self.assertRaises(ValueError):validate_owner_policy({key:entry},{key:1},set(),self.policy)
            for mode in ((0,0,0),(1,1,0),(1,0,1)):
                key=(pc,*mode)
                with self.assertRaises(ValueError):validate_owner_policy({key:entry},{key:1},set(),self.policy)
        for pc in (0x82804d,0x828051):
            key=(pc,1,0,0)
            with self.assertRaises(ValueError):validate_owner_policy({key:entry},{key:1},set(),self.policy)

    def test_old_policy_keeps_all_acknowledgements_protected(self):
        policy=json.loads(json.dumps(self.policy));del policy['fixed_instruction_scopes']['qualified_rdnmi_ack_contexts']
        key=(0x828049,1,0,0);entry={'bytes':bytes.fromhex('af104280'),'mnemonic':'LDA'}
        with self.assertRaises(ValueError):validate_owner_policy({key:entry},{key:1},set(),policy)

    def test_malformed_acknowledgement_policy_is_rejected(self):
        rows=self.policy['fixed_instruction_scopes']['qualified_rdnmi_ack_contexts']
        for bad in ([rows[0],rows[0]],[dict(rows[0],m=True)],[dict(rows[0],x=1)],[dict(rows[0],pc24='82804D')]):
            policy=json.loads(json.dumps(self.policy));policy['fixed_instruction_scopes']['qualified_rdnmi_ack_contexts']=bad
            with self.assertRaises(ValueError):validate_owner_policy({}, {},set(),policy)

    def test_whole_function_floors_do_not_revoke_existing_fixed_effects(self):
        for pc in self.policy['fixed_instruction_scopes']['historical_whole_function_NMI_floors']:
            self.check(int(pc,16))

    def test_bad_scope_types_and_bits_refused(self):
        for flags in(0,4,True,'1',None):
            with self.assertRaises(ValueError):self.check(0x828100,flags)

    def test_missing_policy_refused(self):
        with self.assertRaises(ValueError):validate_owner_policy({}, {},set(),{})


if __name__=='__main__':unittest.main()
