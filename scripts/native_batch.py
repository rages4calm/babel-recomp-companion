"""Prepare/generate a private Gaia native closure without changing the baseline cfg.

Examples:
  python scripts/native_batch.py --prepare --profile .local/batch-001/native-002/profile-boot/capture.json
  python scripts/native_batch.py --generate --profile .local/batch-001/native-002/profile-boot/capture.json

Builds and matched replays are separate. This script never builds, replaces the game,
changes runtime state, disables fallback or declares native execution qualified.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "recomp/native/policy.json"
DEFAULT_WORK = ROOT / ".local/batch-001/native-002/large-batch"


class WindowsJob:
    """Limit only the gated child tree created by this invocation.

    Win32 structures/semantics:
    https://learn.microsoft.com/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information
    """
    def __init__(self, memory_mib: int):
        import ctypes as c
        from ctypes import wintypes as w
        class Basic(c.Structure):
            _fields_ = [("process_time", c.c_longlong), ("job_time", c.c_longlong), ("flags", w.DWORD),
                        ("min_ws", c.c_size_t), ("max_ws", c.c_size_t), ("active", w.DWORD),
                        ("affinity", c.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class Io(c.Structure):
            _fields_ = [(name, c.c_ulonglong) for name in ("reads", "writes", "other", "read_bytes", "write_bytes", "other_bytes")]
        class Extended(c.Structure):
            _fields_ = [("basic", Basic), ("io", Io), ("process_limit", c.c_size_t), ("job_limit", c.c_size_t),
                        ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]
        self.c, self.info_type = c, Extended
        self.api = c.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]; self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]; self.api.SetInformationJobObject.restype = w.BOOL
        self.api.QueryInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p]; self.api.QueryInformationJobObject.restype = w.BOOL
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]; self.api.AssignProcessToJobObject.restype = w.BOOL
        self.api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; self.api.OpenProcess.restype = w.HANDLE
        self.api.CloseHandle.argtypes = [w.HANDLE]; self.api.CloseHandle.restype = w.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise c.WinError(c.get_last_error())
        limits = Extended(); limits.basic.flags = 0x200 | 0x2000 | 0x400
        limits.job_limit = memory_mib * 1024 * 1024
        if not self.api.SetInformationJobObject(self.handle, 9, c.byref(limits), c.sizeof(limits)):
            error = c.WinError(c.get_last_error()); self.close(); raise error

    def attach(self, pid: int) -> None:
        process = self.api.OpenProcess(0x100 | 0x1, False, pid)  # SET_QUOTA | TERMINATE, created/gated child only
        if not process:
            raise self.c.WinError(self.c.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process):
                raise self.c.WinError(self.c.get_last_error())
        finally:
            self.api.CloseHandle(process)

    def peak(self) -> int | None:
        info = self.info_type()
        if self.api.QueryInformationJobObject(self.handle, 9, self.c.byref(info), self.c.sizeof(info), None):
            return int(info.peak_job)
        return None

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle); self.handle = None


def bounded_run(command: list[str], log: Path, memory_mib: int, timeout_seconds: float) -> dict:
    """Gate execution until limits apply; timeout closes only this owned job/tree."""
    if memory_mib < 32 or memory_mib > 8192 or timeout_seconds <= 0:
        raise ValueError("Invalid process resource limits")
    starter = ('import json,os,subprocess,sys\n'
               'if os.name != "nt":\n'
               ' import resource\n'
               ' resource.setrlimit(resource.RLIMIT_AS,(int(sys.argv[2])*1048576,)*2)\n'
               'sys.stdin.buffer.read(1)\n'
               'sys.exit(subprocess.call(json.loads(sys.argv[1])))\n')
    started = time.monotonic(); job = WindowsJob(memory_mib) if os.name == "nt" else None
    process = None; timed_out = False; peak = None
    try:
        with log.open("w", encoding="utf-8") as output:
            process = subprocess.Popen([sys.executable, "-c", starter, json.dumps(command), str(memory_mib)], cwd=ROOT,
                                       stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=os.name != "nt")
            if job:
                job.attach(process.pid)
            process.stdin.write(b"x"); process.stdin.flush(); process.stdin.close()
            try:
                code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                if job:
                    peak = job.peak(); job.close()
                else:
                    import signal
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10); code = 124
        if job and job.handle:
            peak = job.peak()
        return {"exit_code": code, "timed_out": timed_out, "wall_seconds": round(time.monotonic() - started, 4),
                "memory_limit_mib": memory_mib, "timeout_seconds": timeout_seconds,
                "memory_guard": "windows-job-commit-tree" if job else "posix-RLIMIT_AS-per-process",
                "peak_job_commit_bytes": peak}
    finally:
        if job:
            job.close()
        if process and process.poll() is None:
            # Failure before gate release: this invocation's waiting starter has no children.
            process.kill(); process.wait(timeout=10)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(pc: int) -> int:
    """Physical HiROM grouping; raw execution PCs remain in original profiles."""
    bank, addr = pc >> 16, pc & 0xffff
    if bank in (0x7e, 0x7f) or (bank & 0x7f) < 0x40 and addr < 0x8000:
        raise ValueError(f"Not a plain HiROM code address: {pc:06X}")
    return ((bank & 0x3f) | 0xc0) << 16 | addr


def aliases(pc: int) -> set[int]:
    key = canonical(pc)
    bank, addr = key >> 16 & 0x3f, key & 0xffff
    return {((bank | upper) << 16) | addr for upper in (0, 0x40, 0x80, 0xc0)
            if addr >= 0x8000 or upper in (0x40, 0xc0)}


def private_path(path: Path) -> Path:
    path = path.resolve()
    private = (ROOT / ".local").resolve()
    if path == private or private not in path.parents:
        raise ValueError("Native batch output must be beneath this project's ignored .local directory.")
    return path


def guards(policy: dict) -> tuple[set[int], list[tuple[int, int, str]]]:
    if policy.get("schema") != "gaia native batch policy v1" or policy.get("mapper") != "hirom":
        raise ValueError("Unsupported native policy")
    blocked: set[int] = set(); ranges = []
    for item in policy["guard_ranges"]:
        start, end = int(item["start"], 16), int(item["end_exclusive"], 16)
        if start >> 16 != (end - 1) >> 16 or not 0 <= start < end <= 0x1000000:
            raise ValueError("Guard must be a bounded, single-bank range")
        ranges.append((canonical(start), canonical(end - 1) + 1, item["reason"]))
        for pc in range(start, end):
            blocked.update(aliases(pc))
    return blocked, ranges


def read_profiles(paths: list[Path], rom_sha256: str) -> dict:
    """The official generator validates full profiles; this only records bounded provenance/costs."""
    profile_records = []; count = Counter(); costs = Counter(); capture_identity = None
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate profile JSON key: {key}")
            result[key] = value
        return result
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Non-finite profile JSON number")
        return result
    def invalid_constant(value):
        raise ValueError(f"Non-finite profile JSON constant: {value}")
    for path in paths:
        data = path.read_bytes()
        record = json.loads(data, object_pairs_hook=pairs, parse_float=finite_float,
                            parse_constant=invalid_constant)
        if not isinstance(record, dict) or record.get("schema") != "snesrecomp tier2 coverage v2":
            raise ValueError("Use complete v2 capture.json profiles; do not relabel legacy or partial records.")
        if record.get("checkpoint_complete") is not True:
            raise ValueError("Profile must be an explicitly complete v2 checkpoint")
        identity = record.get("identity", {})
        if not isinstance(identity, dict) or identity.get("rom_sha256") != rom_sha256 or identity.get("mapper") != "hirom" or identity.get("module_id") != "main":
            raise ValueError("Profile ROM/mapper/module does not match this stock Gaia batch")
        if not record.get("capture_id") or not identity.get("build_digest"):
            raise ValueError("Profile must retain its actual capture and executable identity")
        current_identity = tuple(identity.get(key) for key in
                                 ("rom_sha256", "module_id", "mapper", "program_digest", "build_digest", "generation_digest"))
        if capture_identity is not None and current_identity != capture_identity:
            raise ValueError("Cannot aggregate profile costs from different program/build identities")
        capture_identity = current_identity
        for key in ("overflowed_tuples", "dropped_cost_samples", "ram_routines_overflow", "journal_write_failures"):
            if type(record.get(key)) is not int or record[key] != 0:
                raise ValueError(f"Profile reports {key}; investigate it rather than treating it as complete")
        # Refuse historical aliases too; they must not hide an explicit loss
        # value in a hand-authored checkpoint alongside the actual v2 fields.
        for key in ("dropped_costs", "cost_overflow"):
            if key in record and (type(record[key]) is not int or record[key] != 0):
                raise ValueError(f"Profile reports {key}; investigate it rather than treating it as complete")
        for key in ("discoveries", "costs", "ram_routines"):
            if not isinstance(record.get(key, []), list):
                raise ValueError(f"Profile {key} must be an array")
        profile_records.append({"path": str(path), "sha256": digest(data), "capture_id": record["capture_id"], "identity": identity})
        count["transfer_rows"] += len(record.get("discoveries", []))
        count["cost_rows"] += len(record.get("costs", []))
        for row in record.get("costs", []):
            if not isinstance(row, dict) or type(row.get("guest_cycles")) is not int or row["guest_cycles"] < 0:
                raise ValueError("Profile cost guest_cycles must be a nonnegative integer")
            pc = row["target_pc24"]
            pc = pc if isinstance(pc, int) else int(pc, 0)
            costs[(pc, row.get("entry_mx"), row.get("emulation"))] += int(row.get("guest_cycles", 0))
    return {"captures": profile_records, "counts": dict(count),
            "highest_costs": [{"pc24": f"{pc:06X}", "entry_mx": mx, "emulation": e, "guest_cycles": n}
                              for (pc, mx, e), n in costs.most_common(24)]}


def read_historical_profiles(paths: list[Path], rom_sha256: str) -> list[dict]:
    """Retain each historical checkpoint independently, never combine its costs.

    The SDK's historical-root path unions analysis seeds and exclusions only;
    missing older program metadata remains explicit rather than being rebound.
    """
    result = []
    for path in paths:
        evidence = read_profiles([path], rom_sha256)
        identity = evidence["captures"][0]["identity"]
        result.append({"profile": evidence,
                       "program_identity_status": "recorded" if identity.get("program_digest") else "legacy_metadata_missing_program_digest",
                       "evidence_scope": "Historical analysis seeds/exclusions only; costs apply only to this original checkpoint, not the current build."})
    return result


def prepare(rom: Path, work: Path, profiles: list[Path], all_widths: bool, profile_only: bool,
            max_insns: int = 1024, max_nodes: int = 12000, instruction_blocks: bool = False, region_paced: bool = False,
            historical_profiles: list[Path] | None = None) -> dict:
    if max_insns <= 0 or max_nodes <= 0 or (region_paced and not instruction_blocks):
        raise ValueError("Positive analysis limits and instruction-blocks for region-paced emission are required")
    policy = json.loads(POLICY.read_text(encoding="utf-8")); blocked, ranges = guards(policy)
    image = rom.read_bytes()
    if len(image) == 2097664:
        image = image[512:]
    if len(image) != 2097152 or digest(image) != policy["rom_sha256"]:
        raise ValueError("The ROM does not match the supported unmodified USA image")
    evidence = read_profiles(profiles, policy["rom_sha256"])
    historical = read_historical_profiles(historical_profiles or [], policy["rom_sha256"])
    source = ROOT / "recomp"; prepared = work / "cfg"
    existing_receipt = work / "prepare-receipt.json"
    if existing_receipt.is_file():
        previous = json.loads(existing_receipt.read_text(encoding="utf-8"))
        current = {p.name: digest(p.read_bytes()) for p in source.glob("bank*.cfg")}
        current.update({name: digest((source / name).read_bytes()) for name in ("symbols.toml", "disassembly-layout.json") if (source / name).is_file()})
        if (previous["source_cfg_sha256"] != current or previous["profiles"] != evidence or
            previous.get("historical_profiles", []) != historical or
            previous["all_width_hypotheses"] != all_widths or previous["cfg_roots"] != (not profile_only) or
            bool(previous.get("instruction_blocks")) != instruction_blocks or
            bool(previous.get("region_paced")) != region_paced or
            previous.get("analysis_limits", {"max_insns": 4096, "max_nodes": 100000}) != {"max_insns": max_insns, "max_nodes": max_nodes} or
            previous["policy_sha256"] != digest(POLICY.read_bytes()) or
            previous["framework_pins_sha256"] != digest((ROOT / "framework_pins.txt").read_bytes())):
            raise ValueError("This private batch is immutable and its inputs changed. Choose a new --work directory.")
        return previous
    prepared.mkdir(parents=True, exist_ok=True)
    inputs = {}; outputs = {}; declarations = 0
    for path in sorted(source.glob("bank*.cfg")):
        raw = path.read_bytes(); text = raw.decode("utf-8"); inputs[path.name] = digest(raw)
        declarations += len(re.findall(r"^func\s", text, re.M))
        if all_widths:
            # The native analyzer supports this declaration. Widths are analysis
            # hypotheses, never execution proof; Python emission follows its manifest.
            text = re.sub(r"^(func\s+[^\n\r]+)$", r"\1 force_variants:0,0;0,1;1,0;1,1", text, flags=re.M)
        if path.name.lower() == "bank00.cfg":
            existing = {int(v, 16) for v in re.findall(r"^force_lle\s+([0-9a-fA-F]+)", text, re.M)}
            text += "\n# Private native batch safety policy: every guarded byte and HiROM alias.\n"
            text += "".join(f"force_lle {pc:06X}\n" for pc in sorted(blocked - existing))
        data = text.replace("\r\n", "\n").encode("utf-8")
        (prepared / path.name).write_bytes(data); outputs[path.name] = digest(data)
    for name in ("symbols.toml", "disassembly-layout.json"):
        path = source / name
        if path.is_file():
            raw = path.read_bytes(); (prepared / name).write_bytes(raw); inputs[name] = digest(raw); outputs[name] = digest(raw)
    command = [sys.executable, str(ROOT / "snesrecomp/snesrecomp_cli.py"), "generate", "--rom", str(rom),
               "--cfg-dir", str(prepared), "--out-dir", str(work / "generated"),
               "--funcs-h", str(prepared / "funcs.h"), "--project-root", str(ROOT),
               "--expected-sha256", policy["rom_sha256"], "--expected-crc32", "1c3848c0", "--no-host-root-scan"]
    command.extend(("--max-insns", str(max_insns), "--max-nodes", str(max_nodes)))
    if instruction_blocks:
        command.append("--instruction-blocks")
    if region_paced:
        command.append("--region-paced")
    if not profile_only:
        command.append("--cfg-roots")
    for profile in profiles:
        command.extend(("--profile-manifest", str(profile)))
    for profile in historical_profiles or []:
        command.extend(("--historical-profile-manifest", str(profile)))
    receipt = {"schema": "gaia native batch preparation v1", "rom_sha256": policy["rom_sha256"],
               "policy_sha256": digest(POLICY.read_bytes()), "framework_pins_sha256": digest((ROOT / "framework_pins.txt").read_bytes()),
               "declared_functions": declarations, "cfg_roots": not profile_only, "all_width_hypotheses": all_widths,
               "analysis_limits": {"max_insns": max_insns, "max_nodes": max_nodes},
               "instruction_blocks": instruction_blocks, "region_paced": region_paced,
               "guarded_addresses_with_aliases": len(blocked), "source_cfg_sha256": inputs,
               "prepared_cfg_sha256": outputs, "profiles": evidence, "generation_command": command,
               "evidence_scope": "Private analysis/generation candidates; no native execution qualification."}
    if historical:
        receipt["historical_profiles"] = historical
    (work / "prepare-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def generate(receipt: dict, work: Path, memory_mib: int = 4096, timeout_seconds: int = 300) -> dict:
    index = 1
    log = work / "generation.log"
    while log.exists():
        index += 1
        log = work / f"generation-attempt-{index:03}.log"
    run = bounded_run(receipt["generation_command"], log, memory_mib, timeout_seconds)
    exit_code = run["exit_code"]
    summary = {"schema": "gaia native batch generation v1", "exit_code": exit_code, "attempt": index,
               "log": str(log), "resource_guard": run,
               "qualified": False, "evidence_scope": "Generation/link-closure only; root must compile, execute and compare matched guest state."}
    manifest_path = work / "generated/program_manifest.json"
    if exit_code == 0:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")); policy = json.loads(POLICY.read_text(encoding="utf-8")); _, ranges = guards(policy)
        violations = []; dispositions = Counter(); nodes = manifest["nodes"]
        for key, node in nodes.items():
            dispositions[node["disposition"]] += 1
            if node["disposition"] != "aot_eligible":
                continue
            lo, hi = canonical(node["min_pc24"]), canonical(node["max_pc24"])
            if any(lo < end and hi >= start for start, end, _ in ranges):
                violations.append(key)
        summary.update(roots=len(manifest["roots"]), variants=len(nodes), dispositions=dict(dispositions),
                       guarded_range_violations=violations, manifest_sha256=digest(manifest_path.read_bytes()),
                       generated_bytes=sum(p.stat().st_size for p in (work / "generated").glob("*.c")))
        if violations:
            summary["exit_code"] = 3
    content = json.dumps(summary, indent=2) + "\n"
    (work / f"generation-receipt-attempt-{index:03}.json").write_text(content, encoding="utf-8")
    (work / "generation-receipt.json").write_text(content, encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--rom", type=Path, default=ROOT / "Illusion of Gaia (USA).sfc")
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--profile", type=Path, action="append", default=[])
    parser.add_argument("--historical-profile", type=Path, action="append", default=[],
                        help="Retain a historical checkpoint's analysis seeds/exclusions with separate original identity and cost provenance (repeatable)")
    parser.add_argument("--all-widths", action="store_true", help="Analyze all four M/X hypotheses at every existing declared entry")
    parser.add_argument("--profile-only", action="store_true", help="Use architectural/profile roots without bulk cfg roots")
    parser.add_argument("--memory-mib", type=int, default=4096, help="Limit the generation child tree to this committed-memory budget (default 4096 MiB)")
    parser.add_argument("--timeout-seconds", type=int, default=300, help="Wall-time limit for the owned generation process tree")
    parser.add_argument("--max-insns", type=int, default=1024, help="Maximum analyzed instructions per routine; increase only with a measured resource budget")
    parser.add_argument("--max-nodes", type=int, default=12000, help="Maximum analyzed program variants")
    parser.add_argument("--region-paced", action="store_true", help="Opt in to conservative per-access region timing (requires --instruction-blocks)")
    parser.add_argument("--instruction-blocks", action="store_true", help="Check host deadlines at each guest instruction boundary")
    args = parser.parse_args()
    if not (args.prepare or args.generate):
        parser.error("choose --prepare or --generate")
    if args.region_paced and not args.instruction_blocks:
        parser.error("--region-paced requires --instruction-blocks")
    work = private_path(args.work); work.mkdir(parents=True, exist_ok=True)
    receipt = prepare(args.rom.resolve(), work, [p.resolve() for p in args.profile], args.all_widths, args.profile_only, args.max_insns, args.max_nodes, args.instruction_blocks, args.region_paced,
                      [p.resolve() for p in args.historical_profile])
    print(json.dumps({"work": str(work), "declared_functions": receipt["declared_functions"],
                      "guarded_addresses_with_aliases": receipt["guarded_addresses_with_aliases"],
                      "profile_counts": receipt["profiles"]["counts"]}))
    if args.generate:
        result = generate(receipt, work, args.memory_mib, args.timeout_seconds); print(json.dumps(result)); return int(result["exit_code"])
    print(subprocess.list2cmdline(receipt["generation_command"])); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"native_batch: {error}", file=sys.stderr); raise SystemExit(2)
