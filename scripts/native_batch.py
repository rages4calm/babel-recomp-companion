"""Prepare/generate a private Gaia native closure without changing the baseline cfg.

Examples:
  python scripts/native_batch.py --prepare --profile .local/batch-001/native-002/profile-boot/capture.json
  python scripts/native_batch.py --generate --profile .local/batch-001/native-002/profile-boot/capture.json

Builds and matched replays are separate. This script never builds, replaces the game,
changes runtime state, disables fallback or declares native execution qualified.
"""
from __future__ import annotations
import argparse
import copy
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
SPRITE_IMMEDIATES = (0xC728, 0xC7BD, 0xC8E4, 0xC8E9, 0xC9C1, 0xC9C6)
# Host patch contract, not extracted game code. Absolute-address operands and
# both actor-list comparisons remain inside the complete protected function.
SPRITE_PATCH_CONTRACT = {
    0xC616: (0xED, 0x068A, 0, 1), 0xC619: (0xC9, 0x0100, 2, 0),
    0xC629: (0xED, 0x068A, 0, 1), 0xC62C: (0xC9, 0x0100, 2, 0),
    0xC728: (0xE9, 0x0010, 1, 0), 0xC7BD: (0xC9, 0x0110, 1, 0),
    0xC8E4: (0xC9, 0x0110, 2, 0), 0xC8E9: (0xE9, 0x000F, 1, 0),
    0xC9C1: (0xC9, 0x0110, 2, 0), 0xC9C6: (0xE9, 0x000F, 1, 0),
}
SPRITE_GUARD_REASON = ("Private candidate: complete SortActorsByDepth including both mutable ABS operands; "
                       "later six immediate-only sites require pre-effect interpreter refusal.")
SPRITE_LIVE_GUARD_REASON = ("Private candidate: complete SortActorsByDepth including both mutable ABS operands; "
                            "later six immediate-only sites use timed live fetches with pre-effect interpreter fallback when unsupported.")
SPRITE_CFG_COMMENT = "\n# PRIVATE sprite-prefix experiment: changed immediates must refuse before effects.\n"


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
               ' resource.setrlimit(resource.RLIMIT_AS,(int(sys.argv[1])*1048576,)*2)\n'
               'sys.stdin.buffer.read(1)\n'
               'command=json.loads(sys.stdin.buffer.read().decode("utf-8"))\n'
               'sys.exit(subprocess.call(command))\n')
    started = time.monotonic(); job = WindowsJob(memory_mib) if os.name == "nt" else None
    process = None; timed_out = False; peak = None
    try:
        with log.open("w", encoding="utf-8") as output:
            process = subprocess.Popen([sys.executable, "-c", starter, str(memory_mib)], cwd=ROOT,
                                       stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=os.name != "nt")
            if job:
                job.attach(process.pid)
            # Keep the gated command in the pipe. JSON on the wrapper's argv
            # doubles Windows path backslashes and can exceed CreateProcess's
            # limit even when the actual generation command still fits.
            process.stdin.write(b"x" + json.dumps(command).encode("utf-8"))
            process.stdin.flush(); process.stdin.close()
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


def json_digest(value) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def cfg_identity(directory: Path) -> dict:
    paths = list(directory.glob("bank*.cfg"))
    paths.extend(directory / name for name in ("symbols.toml", "disassembly-layout.json")
                 if (directory / name).is_file())
    return {p.name: digest(p.read_bytes()) for p in sorted(paths)}


def sprite_prefix_policy(policy: dict, image: bytes, region_live_immediates: bool = False) -> dict:
    """Validate the stock host-patch boundary before narrowing a private guard."""
    source = (ROOT / "src/iog_widescreen.c").read_text(encoding="utf-8")
    match = re.search(r"static\s+const\s+CullSite\s+kCullSites\[\]\s*=\s*\{(.*?)\};", source, re.S)
    if not match:
        raise ValueError("Sprite-prefix patch contract: missing kCullSites table")
    body = re.sub(r"/\*.*?\*/|//[^\n]*", "", match[1], flags=re.S)
    rows = re.findall(r"\{\s*(0x[0-9A-Fa-f]+)\s*,\s*(0x[0-9A-Fa-f]+)\s*,\s*(-?\d+)\s*,\s*(\d+)\s*\}\s*,?", body)
    remainder = re.sub(r"\{\s*0x[0-9A-Fa-f]+\s*,\s*0x[0-9A-Fa-f]+\s*,\s*-?\d+\s*,\s*\d+\s*\}\s*,?", "", body)
    expected = {0x30000 + pc + 1: (stock, margin, camera)
                for pc, (_, stock, margin, camera) in SPRITE_PATCH_CONTRACT.items()}
    observed = {int(offset, 16): (int(stock, 16), int(margin), int(camera))
                for offset, stock, margin, camera in rows}
    if (remainder.strip() or len(rows) != len(expected) or observed != expected or
            not re.search(r"\bkWramCullCamera\s*=\s*0x1E00\b", source, re.I)):
        raise ValueError("Sprite-prefix patch contract differs from iog_widescreen.c")
    for pc, (opcode, stock, _, _) in SPRITE_PATCH_CONTRACT.items():
        offset = 0x30000 + pc
        if image[offset:offset + 3] != bytes((opcode, stock & 255, stock >> 8)):
            raise ValueError(f"Sprite-prefix stock opcode/operand mismatch at 03{pc:04X}")
    effective = copy.deepcopy(policy)
    cull = [item for item in effective["guard_ranges"] if item["start"] == "03C5FF"]
    if len(cull) != 1 or cull[0]["end_exclusive"] != "03CA00":
        raise ValueError("Sprite-prefix preset requires the original complete culling guard")
    cull[0].update(end_exclusive="03C714", reason=SPRITE_LIVE_GUARD_REASON if region_live_immediates else SPRITE_GUARD_REASON)
    return effective


def generator_identity() -> dict:
    """Bind source inputs and analyzer selection; SDK still owns cache validation.

    Source hashes exclude bytecode, generated C, Cargo targets and game inputs.
    An existing analyzer's binary/stamp identity is recorded as well. The SDK
    checks/rebuilds its default analyzer; explicit overrides require a matching
    source stamp here because the SDK deliberately trusts explicit binaries.
    """
    sdk = ROOT / "snesrecomp"
    if os.environ.get("SNESRECOMP_ROOT") and Path(os.environ["SNESRECOMP_ROOT"]).resolve() != sdk.resolve():
        raise ValueError("Sprite-prefix preparation requires this project's SDK source root")
    paths = {Path(__file__).resolve(), sdk / "snesrecomp_cli.py"}
    for directory, suffix in ((sdk / "recompiler", ".py"), (sdk / "tools", ".py"),
                              (sdk / "recompiler-rs/src", ".rs")):
        paths.update(p for p in directory.rglob("*" + suffix) if p.is_file())
    paths.update(sdk / "recompiler-rs" / name for name in ("Cargo.toml", "Cargo.lock")
                 if (sdk / "recompiler-rs" / name).is_file())
    # __file__ can be outside a synthetic test project; retain a stable label.
    files = {(p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else "scripts/native_batch.py"):
             digest(p.read_bytes()) for p in sorted(paths)}
    analyzer = Path(os.environ.get("SNESRECOMP_NATIVE_ANALYZER") or
                    sdk / "recompiler-rs/target/release" /
                    ("snesrecomp-analyze.exe" if os.name == "nt" else "snesrecomp-analyze")).resolve()
    stamp = analyzer.with_name(analyzer.name + ".source-sha256")
    crate = sdk / "recompiler-rs"
    analyzer_sources = [p for p in (crate / "src").rglob("*") if p.is_file()]
    analyzer_sources.extend(crate / name for name in ("Cargo.toml", "Cargo.lock") if (crate / name).is_file())
    source_hash = hashlib.sha256()
    for path in sorted(analyzer_sources, key=lambda p: p.relative_to(crate).as_posix()):
        source_hash.update(path.relative_to(crate).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    analyzer_source_sha256 = source_hash.hexdigest() if analyzer_sources else None
    if os.environ.get("SNESRECOMP_NATIVE_ANALYZER") and (
            not analyzer.is_file() or not analyzer_source_sha256 or not stamp.is_file() or
            stamp.read_text(encoding="ascii").strip() != analyzer_source_sha256):
        raise ValueError("Sprite-prefix explicit analyzer needs a matching source stamp")
    identity = {"source_files_sha256": files, "source_tree_sha256": json_digest(files),
            "analyzer_sources_sha256": analyzer_source_sha256,
            "analyzer_selection": "explicit" if os.environ.get("SNESRECOMP_NATIVE_ANALYZER") else "default",
            "analyzer_path": str(analyzer),
            "emit_environment": {key: value for key, value in sorted(os.environ.items())
                                 if key.startswith("SNESRECOMP_EMIT_")}}
    # Default bootstrap/rebuild is intentional SDK behavior. Its actual binary
    # is an observation, not an immutable preparation input. Explicit overrides
    # are trusted by the SDK, so keep their verified binary/stamp strictly pinned.
    if identity["analyzer_selection"] == "explicit":
        identity.update(analyzer_sha256=digest(analyzer.read_bytes()),
                        analyzer_source_stamp_sha256=digest(stamp.read_bytes()))
    return identity


def analyzer_observation(identity: dict) -> dict:
    analyzer = Path(identity["analyzer_path"])
    stamp = analyzer.with_name(analyzer.name + ".source-sha256")
    return {"path": str(analyzer), "binary_sha256": digest(analyzer.read_bytes()) if analyzer.is_file() else None,
            "source_stamp_sha256": digest(stamp.read_bytes()) if stamp.is_file() else None,
            "source_stamp": stamp.read_text(encoding="ascii").strip() if stamp.is_file() else None}


def sprite_cache_inputs(receipt: dict) -> str:
    """Preparation binding; distinct from SDK analysis/bank cache digests."""
    keys = ("rom_sha256", "policy_sha256", "framework_pins_sha256", "prepared_cfg_sha256",
            "profiles", "historical_profiles", "analysis_limits", "cfg_roots", "all_width_hypotheses",
            "instruction_blocks", "region_paced", "generation_command")
    inputs = {key: receipt.get(key) for key in keys}
    # Preserve the 007 cache-input wire shape when the new capability is off.
    if receipt.get("region_live_immediates"):
        inputs["region_live_immediates"] = True
    inputs["generator_identity"] = receipt["sprite_prefixes"]["generator_identity"]
    return json_digest(inputs)


def sprite_receipt_policy(receipt: dict, work: Path) -> dict:
    """Validate immutable preset preparation before launching or using a cache."""
    preset = receipt["sprite_prefixes"]
    region_live_immediates = receipt.get("region_live_immediates", False)
    if (type(region_live_immediates) is not bool or
            receipt["generation_command"].count("--region-live-immediates") != int(region_live_immediates)):
        raise ValueError("Region-live-immediates receipt and command identity disagree")
    expected_aliases = [f"{pc:06X}" for site in SPRITE_IMMEDIATES for pc in sorted(aliases(0x030000 | site))]
    if (preset.get("schema") != "gaia sprite-prefix preparation v1" or
            preset.get("effective_policy_file") != "effective-policy.json" or
            preset.get("effective_policy_sha256") != receipt["policy_sha256"] or
            preset.get("protected_function") != ["03C5FF", "03C714"] or
            preset.get("live_immediate_sites") != [f"{pc:04X}" for pc in SPRITE_IMMEDIATES] or
            preset.get("live_alias_sites") != expected_aliases or
            preset.get("cache_inputs_sha256") != sprite_cache_inputs(receipt) or
            not receipt.get("instruction_blocks") or not receipt.get("region_paced")):
        raise ValueError("Sprite-prefix preparation identity or prerequisites changed")
    policy_path = work / "effective-policy.json"
    policy_data = policy_path.read_bytes()
    command = receipt["generation_command"]
    rom = Path(command[command.index("--rom") + 1]).read_bytes()
    image = rom[512:] if len(rom) == 2097664 else rom
    public = POLICY.read_bytes()
    effective = sprite_prefix_policy(json.loads(public), image, region_live_immediates)
    if (digest(public) != preset["public_policy_sha256"] or
            digest(policy_data) != receipt["policy_sha256"] or
            json.loads(policy_data) != effective or
            receipt["rom_sha256"] != digest(image) or
            cfg_identity(ROOT / "recomp") != receipt["source_cfg_sha256"] or
            cfg_identity(work / "cfg") != receipt["prepared_cfg_sha256"] or
            generator_identity() != preset["generator_identity"] or
            digest((ROOT / "src/iog_widescreen.c").read_bytes()) != preset["source_widescreen_sha256"] or
            digest((ROOT / "framework_pins.txt").read_bytes()) != receipt["framework_pins_sha256"] or
            json_digest(command) != preset["generation_command_sha256"]):
        raise ValueError("Sprite-prefix preparation identity changed; use a fresh --work directory")
    for capture in receipt["profiles"]["captures"]:
        if digest(Path(capture["path"]).read_bytes()) != capture["sha256"]:
            raise ValueError("Sprite-prefix profile identity changed")
    for historical in receipt.get("historical_profiles", []):
        for capture in historical["profile"]["captures"]:
            if digest(Path(capture["path"]).read_bytes()) != capture["sha256"]:
                raise ValueError("Sprite-prefix historical profile identity changed")
    return effective


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
            historical_profiles: list[Path] | None = None, sprite_prefixes: bool = False,
            region_live_immediates: bool = False) -> dict:
    if max_insns <= 0 or max_nodes <= 0 or (region_paced and not instruction_blocks):
        raise ValueError("Positive analysis limits and instruction-blocks for region-paced emission are required")
    if sprite_prefixes and not (instruction_blocks and region_paced):
        raise ValueError("--sprite-prefixes requires --instruction-blocks and --region-paced")
    if region_live_immediates and not (sprite_prefixes and instruction_blocks and region_paced):
        raise ValueError("--region-live-immediates requires --sprite-prefixes, --instruction-blocks and --region-paced")
    public_policy = POLICY.read_bytes()
    policy = json.loads(public_policy)
    blocked, ranges = guards(policy)
    image = rom.read_bytes()
    if len(image) == 2097664:
        image = image[512:]
    if len(image) != 2097152 or digest(image) != policy["rom_sha256"]:
        raise ValueError("The ROM does not match the supported unmodified USA image")
    if sprite_prefixes:
        private_path(work)
        policy = sprite_prefix_policy(policy, image, region_live_immediates)
        blocked, ranges = guards(policy)
    policy_data = (json.dumps(policy, indent=2) + "\n").encode("utf-8") if sprite_prefixes else public_policy
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
            bool(previous.get("sprite_prefixes")) != sprite_prefixes or
            bool(previous.get("region_live_immediates")) != region_live_immediates or
            previous["policy_sha256"] != digest(policy_data) or
            previous["framework_pins_sha256"] != digest((ROOT / "framework_pins.txt").read_bytes())):
            raise ValueError("This private batch is immutable and its inputs changed. Choose a new --work directory.")
        if sprite_prefixes:
            sprite_receipt_policy(previous, work)
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
        if sprite_prefixes and path.name.lower() == "bank03.cfg":
            existing_live = {int(v, 16) for v in re.findall(r"^live_operand\s+([0-9a-fA-F]+)", text, re.M)}
            if existing_live.intersection(SPRITE_PATCH_CONTRACT):
                raise ValueError("Sprite-prefix patch sites already have live_operand directives")
            text += SPRITE_CFG_COMMENT
            text += "".join(f"live_operand {pc:04X}\n" for pc in SPRITE_IMMEDIATES)
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
    if region_live_immediates:
        command.append("--region-live-immediates")
    if not profile_only:
        command.append("--cfg-roots")
    for profile in profiles:
        command.extend(("--profile-manifest", str(profile)))
    for profile in historical_profiles or []:
        command.extend(("--historical-profile-manifest", str(profile)))
    receipt = {"schema": "gaia native batch preparation v1", "rom_sha256": policy["rom_sha256"],
               "policy_sha256": digest(policy_data), "framework_pins_sha256": digest((ROOT / "framework_pins.txt").read_bytes()),
               "declared_functions": declarations, "cfg_roots": not profile_only, "all_width_hypotheses": all_widths,
               "analysis_limits": {"max_insns": max_insns, "max_nodes": max_nodes},
               "instruction_blocks": instruction_blocks, "region_paced": region_paced,
               "guarded_addresses_with_aliases": len(blocked), "source_cfg_sha256": inputs,
               "prepared_cfg_sha256": outputs, "profiles": evidence, "generation_command": command,
               "evidence_scope": "Private analysis/generation candidates; no native execution qualification."}
    if historical:
        receipt["historical_profiles"] = historical
    if region_live_immediates:
        receipt["region_live_immediates"] = True
    if sprite_prefixes:
        if not (prepared / "bank03.cfg").is_file():
            raise ValueError("Sprite-prefix preset requires bank03.cfg")
        (work / "effective-policy.json").write_bytes(policy_data)
        receipt["sprite_prefixes"] = {
            "schema": "gaia sprite-prefix preparation v1", "experimental": True,
            "public_policy_sha256": digest(public_policy),
            "effective_policy_file": "effective-policy.json", "effective_policy_sha256": digest(policy_data),
            "protected_function": ["03C5FF", "03C714"],
            "live_immediate_sites": [f"{pc:04X}" for pc in SPRITE_IMMEDIATES],
            "live_alias_sites": [f"{pc:06X}" for site in SPRITE_IMMEDIATES for pc in sorted(aliases(0x030000 | site))],
            "source_widescreen_sha256": digest((ROOT / "src/iog_widescreen.c").read_bytes()),
            "generator_identity": generator_identity(),
            "generation_command_sha256": json_digest(command),
            "scope": "Opt-in private sprite-prefix analysis; complete SortActorsByDepth and every other guard retained. "
                     + ("Six live immediates use timed live fetches with pre-effect interpreter fallback when unsupported; "
                        "no campaign qualification." if region_live_immediates else
                        "Six live immediates require pre-effect interpreter refusal; no campaign qualification.")}
        receipt["sprite_prefixes"]["cache_inputs_sha256"] = sprite_cache_inputs(receipt)
        receipt["sprite_prefixes"]["analyzer_at_prepare"] = analyzer_observation(receipt["sprite_prefixes"]["generator_identity"])
    (work / "prepare-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def generate(receipt: dict, work: Path, memory_mib: int = 4096, timeout_seconds: int = 300) -> dict:
    if receipt.get("region_live_immediates") and not receipt.get("sprite_prefixes"):
        raise ValueError("Region-live-immediates generation requires the sprite-prefix preset")
    policy = (sprite_receipt_policy(receipt, work) if receipt.get("sprite_prefixes")
              else json.loads(POLICY.read_text(encoding="utf-8")))
    cache_before = work / "generated/.snesrecomp-cache.json"
    cache_before_sha256 = digest(cache_before.read_bytes()) if receipt.get("sprite_prefixes") and cache_before.is_file() else None
    analyzer_before = analyzer_observation(receipt["sprite_prefixes"]["generator_identity"]) if receipt.get("sprite_prefixes") else None
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
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")); _, ranges = guards(policy)
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
        if receipt.get("sprite_prefixes"):
            cache_path = work / "generated/.snesrecomp-cache.json"
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            identity_keys = ("generator_digest", "config_digest", "analysis_input_digest")
            if (type(cache.get("format_version")) is not int or cache["format_version"] <= 0 or
                    any(not re.fullmatch(r"[0-9a-f]{64}", str(cache.get(key, ""))) for key in identity_keys)):
                raise ValueError("Sprite-prefix generation lacks complete SDK cache identities")
            generator_after = generator_identity()
            if generator_after != receipt["sprite_prefixes"]["generator_identity"]:
                raise ValueError("Sprite-prefix generator source/selection changed during generation")
            summary["sprite_prefixes"] = {"effective_policy_sha256": receipt["policy_sha256"],
                                           "preparation_sha256": json_digest(receipt),
                                           "cache_inputs_sha256": receipt["sprite_prefixes"]["cache_inputs_sha256"],
                                           "cache_before_sha256": cache_before_sha256,
                                           "cache_sha256": digest(cache_path.read_bytes()),
                                           "cache_format_version": cache.get("format_version"),
                                           **{key: cache[key] for key in identity_keys},
                                           "generator_after": generator_after,
                                           "analyzer_before": analyzer_before,
                                           "analyzer_after": analyzer_observation(generator_after)}
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
    parser.add_argument("--sprite-prefixes", action="store_true", help="Opt in to private sprite prefixes with six live immediate refusals; requires --instruction-blocks --region-paced and retains complete SortActorsByDepth fallback")
    parser.add_argument("--region-live-immediates", action="store_true", help="Opt in to SDK region-paced live immediate reads; requires --sprite-prefixes --instruction-blocks --region-paced")
    args = parser.parse_args()
    if not (args.prepare or args.generate):
        parser.error("choose --prepare or --generate")
    if args.region_paced and not args.instruction_blocks:
        parser.error("--region-paced requires --instruction-blocks")
    if args.sprite_prefixes and not (args.instruction_blocks and args.region_paced):
        parser.error("--sprite-prefixes requires --instruction-blocks and --region-paced")
    if args.region_live_immediates and not (args.sprite_prefixes and args.instruction_blocks and args.region_paced):
        parser.error("--region-live-immediates requires --sprite-prefixes, --instruction-blocks and --region-paced")
    work = private_path(args.work); work.mkdir(parents=True, exist_ok=True)
    receipt = prepare(args.rom.resolve(), work, [p.resolve() for p in args.profile], args.all_widths, args.profile_only, args.max_insns, args.max_nodes, args.instruction_blocks, args.region_paced,
                      [p.resolve() for p in args.historical_profile], args.sprite_prefixes, args.region_live_immediates)
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
