"""ROM-free comparison-policy fixtures; no actual CPU/audio qualification."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compare_native_runs import APU_HEADER, STATE_SUFFIXES, compare


class NativeComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="gaia-comparison-policy-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.reference=self.root/"reference";self.candidate=self.root/"candidate"
        self.lines=[
            "1\t10\t20\tcpu_wr\t0\tAA\t100",
            "1\t11\t25\tcpu_ap\t0\tAA\t101",
            "1\t12\t30\tspc_rd\t0\tAA\t101",
            "1\t13\t31\tspc_wr\t1\tBB\t102",
            "1\t14\t35\tcpu_rd\t1\tBB\t102"]
        receipt={"schema":"iog-native-route-v1","passed":True,"frames_requested":1,"widescreen":False,
            "input_sha256":{"rom":"ab"*32,"route":"cd"*32},"snapshots":[{"tag":"one","frame":1}],
            "execution_share":{"cpu_cycles":1000,"master_cycles":6000,"aot_cycle_pct":5.0}}
        for folder in (self.reference,self.candidate):
            (folder/"snapshots").mkdir(parents=True)
            (folder/"receipt.json").write_text(json.dumps(receipt))
            (folder/"trace.csv").write_text("1,00000000,0000,0000,0000,01ff,0000,00,80,34\n")
            (folder/"final.ppm").write_bytes(b"P6\n1 1\n255\n\x10\x20\x30")
            self.snapshot(folder,"one")

    def snapshot(self,folder,tag,state=True):
        for suffix in STATE_SUFFIXES:
            (folder/"snapshots"/(tag+suffix)).write_bytes(b"synthetic"+suffix.encode())
        (folder/"snapshots"/(tag+".dma.tsv")).write_bytes(b"# synthetic DMA schema retained byte-exact\n")
        (folder/"snapshots"/(tag+".ppuw.tsv")).write_bytes(b"# synthetic PPU schema retained byte-exact\n")
        self.apu(folder,self.lines,tag)
        if state:
            (folder/"snapshots"/(tag+".apu-state.bin")).write_bytes(b"synthetic APU CPU/RAM/DSP state")
            (folder/"snapshots"/(tag+".apu-scheduler.bin")).write_bytes(b"synthetic PCM ring and queue state")

    def apu(self,folder,lines,tag="one"):
        (folder/"snapshots"/(tag+".apu.tsv")).write_bytes(APU_HEADER+b"\n"+"\n".join(lines).encode()+b"\n")

    def sample_compare(self):
        return compare(self.reference,self.candidate,0.001,True,"samples",True)

    def spc_beam_difference(self):
        lines=self.lines.copy()
        for index in (2,3):
            columns=lines[index].split("\t");columns[1]="200";columns[2]="1300";lines[index]="\t".join(columns)
        self.apu(self.candidate,lines)

    def test_assisted_inputs_must_match(self):
        path = self.candidate / "receipt.json"
        original = json.loads(path.read_text())
        for field, value in (("seed_state", "ef" * 32), ("room_reward_multiplier", 8), ("route_assisted", True)):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                if field == "seed_state":
                    changed["input_sha256"][field] = value
                else:
                    changed[field] = value
                path.write_text(json.dumps(changed))
                self.assertFalse(self.sample_compare()["checks"]["matched_inputs"])
        path.write_text(json.dumps(original))

    def test_equal_strict_and_samples_pass(self):
        strict=compare(self.reference,self.candidate,0.001,True)
        samples=self.sample_compare()
        self.assertTrue(strict["passed"]);self.assertTrue(samples["passed"])
        self.assertTrue(strict["raw_apu_equal"]);self.assertEqual(strict["apu_clock_mode"],"strict")
        self.assertTrue(strict["checks"]["full_output_equal"])
        self.assertEqual(strict["full_output"]["reference_sha256"],strict["full_output"]["candidate_sha256"])

    def test_mutated_full_output_fails_even_with_equal_authentic_snapshots(self):
        path=self.candidate/"final.ppm";data=path.read_bytes();path.write_bytes(data[:-1]+b"\x31")
        result=self.sample_compare()
        self.assertFalse(result["passed"]);self.assertFalse(result["checks"]["full_output_equal"])
        self.assertTrue(result["checks"]["snapshots_equal"])

    def test_missing_full_output_on_either_or_both_sides_fails(self):
        for folder in (self.reference,self.candidate):
            with self.subTest(folder=folder.name):
                path=folder/"final.ppm";data=path.read_bytes();path.unlink()
                self.assertFalse(self.sample_compare()["passed"]);path.write_bytes(data)
        for folder in (self.reference,self.candidate):(folder/"final.ppm").unlink()
        self.assertFalse(self.sample_compare()["passed"])

    def test_equal_empty_full_output_is_not_evidence(self):
        for folder in (self.reference,self.candidate):(folder/"final.ppm").write_bytes(b"")
        result=self.sample_compare();self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["full_output_equal"])

    def test_spc_beam_only_difference_is_explicit_and_default_strict_fails(self):
        self.spc_beam_difference()
        strict=compare(self.reference,self.candidate,0.001,True)
        sample=self.sample_compare()
        self.assertFalse(strict["passed"]);self.assertTrue(sample["passed"])
        self.assertFalse(sample["raw_apu_equal"])
        self.assertEqual(len(sample["raw_apu_differences"]),1)
        self.assertEqual(sample["spc_beam_only_differences"],["one.apu.tsv"])
        self.assertIn("not exact SPC cycle",sample["apu_clock_scope"])

    def test_samples_require_devices_and_apu_state(self):
        for devices,state in [(False,False),(True,False),(False,True)]:
            with self.subTest(devices=devices,state=state):
                with self.assertRaises(ValueError):compare(self.reference,self.candidate,0.001,devices,"samples",state)

    def test_real_spc_event_fields_remain_exact(self):
        for column,value in [(0,"2"),(3,"spc_wr"),(4,"1"),(5,"AB"),(6,"102")]:
            with self.subTest(column=column):
                lines=self.lines.copy();columns=lines[2].split("\t");columns[column]=value;lines[2]="\t".join(columns)
                self.apu(self.candidate,lines);result=self.sample_compare()
                self.assertFalse(result["passed"]);self.assertTrue(result["raw_apu_differences"])

    def test_all_cpu_event_beam_stamps_remain_exact(self):
        for index in (0,1,4):
            for column in (1,2):
                with self.subTest(event=index,column=column):
                    lines=self.lines.copy();columns=lines[index].split("\t");columns[column]="999";lines[index]="\t".join(columns)
                    self.apu(self.candidate,lines);self.assertFalse(self.sample_compare()["passed"])

    def test_row_order_missing_and_added_events_fail(self):
        for lines in [self.lines[:2]+[self.lines[3],self.lines[2]]+self.lines[4:],self.lines[:-1],self.lines+[self.lines[-1]]]:
            with self.subTest(lines=lines):
                self.apu(self.candidate,lines);self.assertFalse(self.sample_compare()["passed"])

    def test_unknown_schema_identical_in_both_logs_fails(self):
        for bad in ["1\t12\t30\tunknown\t0\tAA\t101", "1\t12\t30\tspc_rd\t0\tAA\t101\textra",
                    "1\t12\t30\tspc_rd\t4\tAA\t101", "1\t12\t30\tspc_rd\t0\tGG\t101",
                    "-1\t12\t30\tspc_rd\t0\tAA\t101", "1\t12\t30\tspc_rd\t0\tAA\tNaN"]:
            with self.subTest(row=bad):
                self.apu(self.reference,[bad]);self.apu(self.candidate,[bad])
                for mode in ("strict","samples"):
                    result=compare(self.reference,self.candidate,0.001,True,mode,mode=="samples")
                    self.assertFalse(result["passed"]);self.assertFalse(result["checks"]["apu_log_schema_valid"])

    def test_unknown_header_fails_even_when_bytes_match(self):
        for folder in (self.reference,self.candidate):(folder/"snapshots/one.apu.tsv").write_bytes(b"# another schema\n")
        self.assertFalse(self.sample_compare()["passed"])

    def test_non_spc_formatting_or_line_endings_are_not_ignored(self):
        path=self.candidate/"snapshots/one.apu.tsv";path.write_bytes(path.read_bytes().replace(b"\n",b"\r\n"))
        self.assertFalse(self.sample_compare()["passed"])
        self.apu(self.candidate,self.lines)
        lines=self.lines.copy();lines[2]=lines[2].replace("\tAA\t","\tAB\t")
        self.apu(self.candidate,lines);self.assertFalse(self.sample_compare()["passed"])

    def test_missing_or_empty_apu_logs_fail_in_both_modes(self):
        for empty in (False,True):
            with self.subTest(empty=empty):
                for folder in (self.reference,self.candidate):
                    path=folder/"snapshots/one.apu.tsv"
                    if empty:path.write_bytes(b"")
                    elif path.exists():path.unlink()
                for mode in ("strict","samples"):
                    self.assertFalse(compare(self.reference,self.candidate,0.001,True,mode,mode=="samples")["passed"])

    def test_apu_state_and_scheduler_changes_remain_failures(self):
        self.spc_beam_difference()
        for suffix in (".apu-state.bin",".apu-scheduler.bin"):
            with self.subTest(suffix=suffix):
                path=self.candidate/"snapshots"/("one"+suffix);original=path.read_bytes()
                path.write_bytes(original+b"changed")
                result=self.sample_compare();self.assertFalse(result["passed"])
                self.assertTrue(result["raw_apu_differences"])
                self.assertIn("one"+suffix,[d["file"]for d in result["snapshot_differences"]])
                path.write_bytes(original)

    def test_equal_empty_or_missing_state_is_not_evidence(self):
        for suffix in (".apu-state.bin",".apu-scheduler.bin"):
            for mode in ("empty","missing"):
                with self.subTest(suffix=suffix,mode=mode):
                    for folder in (self.reference,self.candidate):
                        path=folder/"snapshots"/("one"+suffix)
                        if mode=="empty":path.write_bytes(b"")
                        elif path.exists():path.unlink()
                    self.assertFalse(self.sample_compare()["passed"])

    def test_every_wram_tag_requires_both_state_files(self):
        for folder in (self.reference,self.candidate):self.snapshot(folder,"two",state=False)
        result=self.sample_compare();self.assertFalse(result["passed"])
        names={d["file"]for d in result["snapshot_differences"]}
        self.assertIn("two.apu-state.bin",names);self.assertIn("two.apu-scheduler.bin",names)

    def test_other_device_and_memory_changes_remain_failures(self):
        for suffix in (".dma.tsv",".ppuw.tsv",".wram.bin",".regs.json"):
            with self.subTest(suffix=suffix):
                path=self.candidate/"snapshots"/("one"+suffix);original=path.read_bytes();path.write_bytes(original+b"changed")
                self.assertFalse(self.sample_compare()["passed"]);path.write_bytes(original)

    def test_cpu_trace_and_cycle_differences_remain_failures(self):
        path=self.candidate/"trace.csv";original=path.read_text();path.write_text(original.replace(",01ff,",",01fe,"))
        self.assertFalse(self.sample_compare()["passed"]);path.write_text(original)
        receipt_path=self.candidate/"receipt.json";original_receipt=json.loads(receipt_path.read_text())
        for field in ("cpu_cycles","master_cycles"):
            changed=copy.deepcopy(original_receipt);changed["execution_share"][field]+=1;receipt_path.write_text(json.dumps(changed))
            self.assertFalse(self.sample_compare()["passed"])
        receipt_path.write_text(json.dumps(original_receipt))

    def test_missing_empty_trace_and_no_snapshot_inventory_fail(self):
        path=self.candidate/"trace.csv";original=path.read_bytes();path.write_bytes(b"")
        self.assertFalse(self.sample_compare()["passed"]);path.unlink();self.assertFalse(self.sample_compare()["passed"]);path.write_bytes(original)
        for folder in (self.reference,self.candidate):
            (folder/"snapshots/one.wram.bin").unlink()
            receipt=json.loads((folder/"receipt.json").read_text());receipt["snapshots"]=[];(folder/"receipt.json").write_text(json.dumps(receipt))
        self.assertFalse(self.sample_compare()["passed"])

    def test_route_inputs_failed_receipts_and_native_threshold_remain_gates(self):
        path=self.candidate/"receipt.json";original=json.loads(path.read_text())
        for change in ("route","frames","widescreen","passed","share"):
            data=copy.deepcopy(original)
            if change=="route":data["input_sha256"]["route"]="ef"*32
            if change=="frames":data["frames_requested"]=2
            if change=="widescreen":data["widescreen"]=True
            if change=="passed":data["passed"]=False
            if change=="share":data["execution_share"]["aot_cycle_pct"]=0
            path.write_text(json.dumps(data));self.assertFalse(self.sample_compare()["passed"])
        path.write_text(json.dumps(original))

    def test_cli_refuses_underscoped_samples_mode(self):
        script=Path(__file__).with_name("compare_native_runs.py")
        result=subprocess.run([sys.executable,str(script),str(self.reference),str(self.candidate),"--apu-clock","samples","--output",str(self.root/"invalid.json")],capture_output=True,text=True)
        self.assertEqual(result.returncode,2);self.assertFalse((self.root/"invalid.json").exists())


if __name__=="__main__":unittest.main()
