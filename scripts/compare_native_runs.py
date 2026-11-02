"""Compare matched private routes; generated code alone cannot pass a native gate."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

FIELDS = ("frame", "wram_crc32", "A", "X", "Y", "S", "D", "DB", "PB", "P")
STATE_SUFFIXES = (".wram.bin", ".sram.bin", ".vram.bin", ".cgram.bin", ".oam.bin", ".fb.bgrx", ".regs.json")
APU_STATE_SUFFIXES = (".apu-state.bin", ".apu-scheduler.bin")
APU_HEADER = b"# frame\tscanline\thclock\tevent\tport\tvalue\tsample"
APU_EVENTS = {b"cpu_wr", b"cpu_ap", b"cpu_rd", b"spc_rd", b"spc_wr"}
SPC_EVENTS = {b"spc_rd", b"spc_wr"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apu_sample_rows(data: bytes) -> tuple[bytes | None, list[dict]]:
    """Ignore ONLY scanline/hclock fields on validated SPC port-event rows.

    Preserve header, row order, line endings and every other byte. CPU rows
    remain unchanged. A DSP-produced sample index is not an exact SPC cycle.
    """
    rows = data.splitlines(keepends=True)
    if not rows or rows[0].rstrip(b"\r\n") != APU_HEADER:
        return None, [{"row": 1, "reason": "missing_or_unknown_apu_header"}]
    normalized = [rows[0]]
    errors = []
    for number, raw in enumerate(rows[1:], 2):
        ending = b"\r\n" if raw.endswith(b"\r\n") else b"\n" if raw.endswith(b"\n") else b""
        body = raw[:-len(ending)] if ending else raw
        columns = body.split(b"\t")
        reason = None
        if len(columns) != 7:
            reason = "unknown_apu_column_count"
        elif columns[3] not in APU_EVENTS:
            reason = "unknown_apu_event"
        elif not all(re.fullmatch(rb"[0-9]+", columns[i]) for i in (0, 1, 2, 4, 6)):
            reason = "invalid_apu_integer"
        elif not (int(columns[0]) <= 0xFFFFFFFF and int(columns[1]) <= 0xFFFF and
                  int(columns[2]) <= 0xFFFF and int(columns[4]) <= 3 and
                  int(columns[6]) <= 0xFFFFFFFFFFFFFFFF):
            reason = "apu_integer_out_of_range"
        elif not re.fullmatch(rb"[0-9A-F]{2}", columns[5]):
            reason = "invalid_apu_byte_value"
        if reason:
            errors.append({"row": number, "reason": reason})
            continue
        if columns[3] in SPC_EVENTS:
            columns[1] = columns[2] = b"<spc-beam>"
            normalized.append(b"\t".join(columns) + ending)
        else:
            normalized.append(raw)
    return (None if errors else b"".join(normalized)), errors


def first_raw_apu_difference(a: bytes, b: bytes) -> dict:
    left, right = a.splitlines(), b.splitlines()
    for number, (x, y) in enumerate(zip(left, right), 1):
        if x != y:
            return {"row": number, "reference": x.decode("ascii", "backslashreplace"),
                    "candidate": y.decode("ascii", "backslashreplace")}
    if len(left) != len(right):
        return {"row": min(len(left), len(right)) + 1,
                "reference_rows": len(left), "candidate_rows": len(right)}
    return {"reason": "raw_byte_format_or_line_ending_difference"}


def compare(reference: Path, candidate: Path, minimum_native: float, devices: bool = False,
            apu_clock: str = "strict", apu_state: bool = False) -> dict:
    if apu_clock not in ("strict", "samples"):
        raise ValueError("unknown APU clock comparison mode")
    if apu_clock == "samples" and not (devices and apu_state):
        raise ValueError("APU samples mode requires both devices and complete APU state comparison")
    if not math.isfinite(minimum_native) or not 0 <= minimum_native <= 100:
        raise ValueError("native threshold must be finite and within 0..100")
    ref = json.loads((reference / "receipt.json").read_text())
    got = json.loads((candidate / "receipt.json").read_text())
    identity = {key: ref["input_sha256"][key] == got["input_sha256"][key] for key in ("rom", "route")}
    identity["frames"] = ref["frames_requested"] == got["frames_requested"]
    identity["widescreen"] = ref["widescreen"] == got["widescreen"]
    identity["seed_state"] = ref["input_sha256"].get("seed_state") == got["input_sha256"].get("seed_state")
    identity["room_reward_multiplier"] = ref.get("room_reward_multiplier", 1) == got.get("room_reward_multiplier", 1)
    identity["assisted_mode"] = ref.get("route_assisted", False) == got.get("route_assisted", False)
    a = (reference / "trace.csv").read_text().splitlines() if (reference / "trace.csv").is_file() else []
    b = (candidate / "trace.csv").read_text().splitlines() if (candidate / "trace.csv").is_file() else []
    traces_valid = bool(a and b) and all(len(row.split(",")) == len(FIELDS) for row in a+b)
    first = next((i for i, (left, right) in enumerate(zip(a, b)) if left != right), None)
    delta = None
    if first is not None:
        left, right = a[first].split(","), b[first].split(",")
        delta = {"row": first + 1, "fields": {key: {"reference": x, "candidate": y}
                 for key, x, y in zip(FIELDS, left, right) if x != y}}
    elif len(a) != len(b):
        delta = {"row": min(len(a), len(b)) + 1, "reference_rows": len(a), "candidate_rows": len(b)}
    if not traces_valid:
        delta = {"reason":"missing_empty_or_unknown_trace_schema", "reference_rows":len(a), "candidate_rows":len(b)}
    snapshots = []
    raw_apu_differences = []
    apu_schema_errors = []
    spc_beam_only_differences = []
    tags = {p.name.removesuffix(".wram.bin") for folder in (reference,candidate)
            for p in (folder/"snapshots").glob("*.wram.bin")}
    tag_errors = []
    for receipt in (ref,got):
        for snapshot in receipt.get("snapshots",[]):
            tag = snapshot.get("tag")
            if isinstance(tag,str) and re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*",tag) and tag not in (".",".."):
                tags.add(tag)
            else:
                tag_errors.append({"reason":"invalid_snapshot_tag","tag":tag})
    suffixes = STATE_SUFFIXES + ((".apu.tsv", ".dma.tsv", ".ppuw.tsv") if devices else ())
    if apu_state:
        suffixes += APU_STATE_SUFFIXES
    for suffix in suffixes:
        expected = {p.name: p for p in (reference / "snapshots").glob("*" + suffix)}
        actual = {p.name: p for p in (candidate / "snapshots").glob("*" + suffix)}
        for name in sorted(expected.keys() | actual.keys() | {tag+suffix for tag in tags}):
            ref_path,candidate_path = expected.get(name),actual.get(name)
            present_a = ref_path is not None and ref_path.is_file()
            present_b = candidate_path is not None and candidate_path.is_file()
            raw_a = ref_path.read_bytes() if present_a else b""
            raw_b = candidate_path.read_bytes() if present_b else b""
            complete = present_a and present_b and bool(raw_a) and bool(raw_b)
            equal = complete and raw_a == raw_b
            raw_equal = equal
            if suffix == ".apu.tsv":
                if not raw_equal:
                    raw_apu_differences.append({"file":name,"reference_present":present_a,"candidate_present":present_b,
                        "reference_sha256":hashlib.sha256(raw_a).hexdigest() if present_a else None,
                        "candidate_sha256":hashlib.sha256(raw_b).hexdigest() if present_b else None,
                        "first_difference":first_raw_apu_difference(raw_a,raw_b)})
                normalized_a,errors_a = apu_sample_rows(raw_a)
                normalized_b,errors_b = apu_sample_rows(raw_b)
                if errors_a or errors_b:
                    apu_schema_errors.append({"file":name,"reference_errors":errors_a,"candidate_errors":errors_b})
                    equal = False
                elif apu_clock == "samples":
                    equal = complete and normalized_a == normalized_b
                    if equal and not raw_equal:
                        spc_beam_only_differences.append(name)
            if not equal:
                snapshots.append({"file":name,"reference_present":present_a,"candidate_present":present_b,
                    "reference_bytes":len(raw_a),"candidate_bytes":len(raw_b),
                    "reason":"missing_or_empty" if not complete else "content_or_schema_difference"})
    share = got.get("execution_share") or {}
    reference_share = ref.get("execution_share") or {}
    native = share.get("aot_cycle_pct", 0)
    apu_state_differences = [row for row in snapshots if row["file"].endswith(APU_STATE_SUFFIXES)]
    full_reference_path=reference/"final.ppm"
    full_candidate_path=candidate/"final.ppm"
    full_reference=full_reference_path.read_bytes() if full_reference_path.is_file() else b""
    full_candidate=full_candidate_path.read_bytes() if full_candidate_path.is_file() else b""
    full_output={"reference_present":full_reference_path.is_file(),"candidate_present":full_candidate_path.is_file(),
                 "reference_bytes":len(full_reference),"candidate_bytes":len(full_candidate),
                 "reference_sha256":hashlib.sha256(full_reference).hexdigest() if full_reference else None,
                 "candidate_sha256":hashlib.sha256(full_candidate).hexdigest() if full_candidate else None}
    checks = {"matched_inputs": all(identity.values()), "reference_route_passed": ref["passed"],
              "candidate_route_passed": got["passed"], "cpu_wram_trace_equal": traces_valid and delta is None,
              "snapshot_inventory_present":bool(tags) and not tag_errors,
              "snapshots_equal": not snapshots,
              "apu_log_schema_valid":bool(tags) and not apu_schema_errors if devices else True,
              "apu_state_equal":bool(tags) and not apu_state_differences if apu_state else True,
              "full_output_equal":bool(full_reference) and bool(full_candidate) and full_reference==full_candidate,
              "cpu_cycles_equal": "cpu_cycles" in reference_share and reference_share["cpu_cycles"] == share.get("cpu_cycles"),
              "master_cycles_equal": "master_cycles" in reference_share and reference_share["master_cycles"] == share.get("master_cycles"),
              "native_cycle_threshold_met": math.isfinite(native) and native >= minimum_native}
    return {"schema": "iog-native-comparison-v1", "passed": all(checks.values()), "checks": checks,
            "identity_checks": identity, "first_trace_divergence": delta, "snapshot_differences": snapshots,
            "frames": len(b), "execution_share": share, "minimum_native_cycle_pct": minimum_native,
            "full_output":full_output,
            "device_logs_compared": devices,
            "apu_clock_mode":apu_clock,"apu_state_compared":apu_state,
            "apu_state_snapshot_tags":sorted(tags) if apu_state else [],
            "apu_state_differences":apu_state_differences,
            "raw_apu_equal":not raw_apu_differences if devices else None,
            "raw_apu_differences":raw_apu_differences,
            "apu_schema_errors":apu_schema_errors,"snapshot_tag_errors":tag_errors,
            "spc_beam_only_differences":spc_beam_only_differences,
            "apu_clock_scope":"Strict raw bytes by default. Samples mode ignores only scanline/hclock on SPC read/write rows; frame, event/order, port/value and DSP-produced sample count remain exact, as do full CPU rows. DSP-produced sample count is not exact SPC cycle time; APU state, PCM ring and scheduler/queue snapshots must also match.",
            "evidence_scope": "matched route CPU/WRAM, saved memory/PPU/frame snapshots and nonempty byte-identical full final.ppm output including widescreen margins; device logs and complete APU state only when explicitly selected; no campaign certification"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--minimum-native-cycle-pct", type=float, default=0.001)
    parser.add_argument("--devices", action="store_true")
    parser.add_argument("--apu-clock",choices=("strict","samples"),default="strict")
    parser.add_argument("--apu-state",action="store_true",help="Require equal nonempty APU and scheduler/PCM/queue snapshots for every WRAM tag")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.minimum_native_cycle_pct <= 100:
        parser.error("native threshold must be 0..100")
    if args.apu_clock=="samples" and not(args.devices and args.apu_state):
        parser.error("--apu-clock samples requires --devices and --apu-state")
    result = compare(args.reference, args.candidate, args.minimum_native_cycle_pct, args.devices,args.apu_clock,args.apu_state)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
