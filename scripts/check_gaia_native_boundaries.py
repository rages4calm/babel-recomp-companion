#!/usr/bin/env python3
"""Private structural cross-check of observed Gaia PC/M/X/E instruction costs.

This does not execute a game, promote native code, infer callable stack context,
or prove timing/campaign coverage. Output contains ROM-derived disassembly and
must remain under this checkout's ignored .local/ directory.
"""
from __future__ import annotations

import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOL_SHA256 = "376109639e9a2a539f2d47ba8b32898433942869e34b43bc964c06c28d0fdfa6"
STOCK_SHA256 = "32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError(f"duplicate JSON key {k!r}")
            result[k] = v
        return result

    def number(text):
        result = float(text)
        if not math.isfinite(result):
            raise ValueError("non-finite JSON number")
        return result

    def constant(text):
        raise ValueError(f"invalid JSON constant {text}")

    data = path.read_bytes()
    if path.suffix == ".gz":
        data = gzip.decompress(data)
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs,
                      parse_float=number, parse_constant=constant)


def integer(value, maximum=0xFFFFFFFFFFFFFFFF):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"expected integer in [0,{maximum}], got {value!r}")
    return value


def address(value):
    if isinstance(value, str):
        if re.fullmatch(r"0[xX][0-9a-fA-F]{1,6}", value):
            value = int(value, 16)
        elif re.fullmatch(r"[0-9a-fA-F]{6}", value):
            value = int(value, 16)
        else:
            raise ValueError(f"ambiguous PC address {value!r}")
    return integer(value, 0xFFFFFF)


def hirom_offset(pc: int, size: int):
    bank, low = pc >> 16, pc & 0xFFFF
    if bank in (0x7E, 0x7F) or (bank & 0x7F) < 0x40 and low < 0x8000:
        return None
    offset = pc & 0x3FFFFF
    # Do not infer cartridge-size mirroring for an unwitnessed bus window.
    return offset if offset + 4 <= size else None


def wram_offset(pc: int):
    bank, low = pc >> 16, pc & 0xFFFF
    if bank in (0x7E,0x7F):
        return (bank-0x7E)*0x10000+low
    if (bank & 0x7F)<0x40 and low<0x2000:
        return low
    return None


def observations(paths):
    totals = collections.Counter()
    inputs = []
    transfers = []
    forced = set()
    for path in paths:
        profile = load(path)
        if profile.get("schema") != "snesrecomp tier2 coverage v2" or profile.get("checkpoint_complete") is not True:
            raise ValueError(f"{path}: expected a completed tier2 coverage v2 checkpoint")
        identity = profile.get("identity", {})
        if identity.get("rom_sha256") != STOCK_SHA256:
            raise ValueError(f"{path}: observation identity is not the stock USA ROM")
        if identity.get("mapper") not in ("hirom", "hi_rom"):
            raise ValueError(f"{path}: unsupported/unknown mapper identity")
        for field in ("dropped_cost_samples", "overflowed_tuples", "journal_write_failures", "ram_routines_overflow"):
            if integer(profile.get(field, 0)):
                raise ValueError(f"{path}: incomplete capture ({field})")
        count = 0
        for row in profile.get("costs", []):
            if row.get("record_kind") != "instruction" or row.get("processor", "snes_cpu") != "snes_cpu":
                continue
            match = re.fullmatch(r"M([01])X([01])", row.get("entry_mx", ""))
            if not match:
                raise ValueError(f"{path}: invalid M/X instruction context")
            m, x = map(int, match.groups())
            e = integer(row["emulation"], 1)
            if e and (m, x) != (1, 1):
                raise ValueError(f"{path}: impossible E1 width context")
            pc = address(row["target_pc24"])
            hits = integer(row["interpreted_instructions"])
            if hits:
                totals[(pc, m, x, e)] += hits
                count += 1
        if not count:
            raise ValueError(f"{path}: no executed main-CPU instruction cost rows")
        inputs.append({"file": str(path), "sha256": digest(path),
                       "identity": identity, "instruction_rows": count})
        for row in profile.get("discoveries", []):
            match = re.fullmatch(r"M([01])X([01])", row.get("entry_mx", ""))
            if not match:
                raise ValueError(f"{path}: invalid transfer target M/X context")
            m, x = map(int, match.groups())
            e = integer(row["emulation"], 1)
            if e and (m,x)!=(1,1):
                raise ValueError(f"{path}: impossible transfer E1 width context")
            pc = address(row["target_pc24"])
            forced.add((pc,m,x,e))
            transfers.append({"site_pc": f"{address(row['site_pc24']):06X}",
                "target_pc":f"{pc:06X}","m":m,"x":x,"e":e,
                "site_kind":row["site_kind"],"fallback_reason":row.get("fallback_reason"),
                "observed_hits":integer(row["observed_hits"]),
                "instruction_execution_observed":(pc,m,x,e) in totals,
                "callable_context_proven":False})
    return totals, inputs, transfers, forced


def generated_index(directory: Path):
    manifest_path = directory / "program_manifest.json"
    manifest = load(manifest_path) if manifest_path.exists() else {"nodes": {}}
    labels, hashes = set(), {}
    for source in sorted(directory.glob("bank*_v2.c")):
        match = re.fullmatch(r"bank([0-9a-fA-F]{2})(?:_part[0-9a-fA-F]+)?_v2\.c", source.name)
        if not match:
            continue
        bank = int(match.group(1), 16)
        hashes[source.name] = digest(source)
        for pc, m, x in re.findall(r"^\s*L_([0-9a-fA-F]{4})_M([01])X([01]):", source.read_text(), re.M):
            labels.add((bank << 16 | int(pc, 16), int(m), int(x)))
    return manifest, labels, {"manifest_sha256": digest(manifest_path) if manifest_path.exists() else None,
                              "generated_files_sha256": hashes}


def self_test():
    """ROM-free regression checks for mapping, evidence refusal and chunk names."""
    checks=0
    def ensure(condition):
        nonlocal checks
        checks+=1
        if not condition:raise AssertionError(f"checker fixture {checks} failed")
    def refuses(callback):
        try:callback()
        except ValueError:ensure(True)
        else:ensure(False)
    for pc,expected in [(0x808000,0x8000),(0x82804D,0x2804D),(0xC00000,0),
                        (0x800402,None),(0x7E8000,None),(0x7F9000,None),(0x3F9000,None)]:
        ensure(hirom_offset(pc,0x200000)==expected)
    for value in [0x808000,"0x808000","808000"]:ensure(address(value)==0x808000)
    with tempfile.TemporaryDirectory(prefix="gaia-boundary-checker-") as directory:
        folder=Path(directory);bad=folder/"bad.json"
        for text in ['{"x":1,"x":2}','{"x":1e9999}','{"x":NaN}']:
            bad.write_text(text);refuses(lambda:load(bad))
        profile={"schema":"snesrecomp tier2 coverage v2","checkpoint_complete":True,
                 "identity":{"rom_sha256":STOCK_SHA256,"mapper":"hirom"},
                 "costs":[{"record_kind":"instruction","target_pc24":"0x808000",
                           "entry_mx":"M1X0","emulation":0,"interpreted_instructions":1}]}
        for field in ("dropped_cost_samples","overflowed_tuples","journal_write_failures","ram_routines_overflow"):
            bad.write_text(json.dumps({**profile,field:1}));refuses(lambda:observations([bad]))
        bad.write_text(json.dumps({**profile,"checkpoint_complete":False}));refuses(lambda:observations([bad]))
        # This is a synthetic label fixture, not extracted game code. New
        # instruction-block output splits banks into hexadecimal part names.
        (folder/"program_manifest.json").write_text('{"nodes":{}}')
        for name in ("bank80_v2.c","bank82_part00_v2.c","bank83_part0a_v2.c","bank84_partial_v2.c"):
            (folder/name).write_text("L_1234_M1X0:\n")
        _,labels,identity=generated_index(folder)
        ensure(len(labels)==3)
        for bank in (0x80,0x82,0x83):ensure((bank<<16|0x1234,1,0)in labels)
        ensure((0x841234,1,0)not in labels)
        ensure(len(identity["generated_files_sha256"])==3)
    print(json.dumps({"passed":True,"checks":checks,"rom_free":True,"chunked_bank_labels":True}))
    return 0


def seed_index(directory: Path):
    exact, physical, hashes = collections.defaultdict(list), collections.defaultdict(list), {}
    for path in sorted(directory.glob("bank*.cfg")):
        text = path.read_text(encoding="utf-8-sig")
        match = re.search(r"^bank\s*=\s*(\d+)", text, re.M)
        if not match:
            continue
        bank = int(match.group(1))
        hashes[path.name] = digest(path)
        for name, pc in re.findall(r"^func\s+(\S+)\s+([0-9a-fA-F]{4})\b", text, re.M):
            logical = bank << 16 | int(pc, 16)
            exact[logical].append(name)
            offset = hirom_offset(logical, 0x200000)
            if offset is not None:
                physical[offset].append({"pc": f"{logical:06X}", "name": name})
    return exact, physical, hashes


def check(args):
    args.out = args.out.resolve()
    if not args.out.is_relative_to((ROOT / ".local").resolve()):
        raise ValueError("ROM-derived report output must stay inside this checkout's ignored .local/")
    if digest(args.romatlas) != TOOL_SHA256:
        raise ValueError("RomAtlas binary differs from the verified analysis tool; review/re-pin it first")
    if digest(args.rom) != STOCK_SHA256:
        raise ValueError("expected the verified bare USA ROM, not a copier-header or patched image")
    rom = args.rom.read_bytes()
    if args.live_rom:
        live = args.live_rom.read_bytes()
        if len(live) != len(rom):
            raise ValueError("live source snapshot size differs; this tool does not infer expanded mappings")
    else:
        live = None
    totals, inputs, transfers, forced = observations(args.coverage)
    manifest, labels, generated = generated_index(args.generated)
    exact_seeds, physical_seeds, seed_hashes = seed_index(ROOT / "recomp")
    assets_path = args.gaialabs / "gaialabs-files.json"
    assets = load(assets_path) if assets_path.exists() else []
    blocks_path = args.gaialabs / "gaialabs-GaiaLib-db-us-blocks.json"
    blocks = load(blocks_path) if blocks_path.exists() else []
    named_blocks = collections.defaultdict(list)
    for row in blocks:
        match = re.search(r"_([0-9a-fA-F]{6})$", row.get("name", ""))
        if match:
            named_blocks[int(match.group(1), 16) & 0x3FFFFF].append(row["name"])
    # Use the framework's independently implemented single-instruction decoder
    # for opcode/length agreement. This does not decode/promote whole functions.
    sys.path.insert(0, str(ROOT / "snesrecomp/recompiler"))
    from snes65816 import decode_insn
    snapshot_checks, snapshots = [], []
    for directory in args.wram_snapshots:
        for path in sorted(directory.glob("*.wram.bin")):
            tag=path.name.removesuffix(".wram.bin")
            info_path=path.with_name(tag+".info.json")
            info=load(info_path)
            frame=integer(info["frame"])
            data=path.read_bytes()
            if len(data)!=0x20000:
                raise ValueError(f"{path}: incomplete WRAM snapshot")
            snapshot_id=len(snapshots)
            snapshots.append({"path":str(path),"sha256":digest(path),
                "info_sha256":digest(info_path),"frame":frame,
                "scope":"bytes at this snapshot frame only; not a historical instruction source witness"})
            for (pc,m,x,e),hits in sorted(totals.items()):
                off=wram_offset(pc)
                if off is None or off+4>len(data):
                    continue
                instruction=decode_insn(data,off,pc&0xFFFF,pc>>16,m,x)
                snapshot_checks.append({"snapshot":snapshot_id,"frame":frame,
                    "pc":f"{pc:06X}","m":m,"x":x,"e":e,"wram_offset":off,
                    "mode_source":"observed cost context; not current snapshot CPU state",
                    "original_bytes":data[off:off+(instruction.length if instruction else 4)].hex(),
                    "framework_mnemonic":instruction.mnem if instruction else None,
                    "length":instruction.length if instruction else None,
                    "romatlas_checked":False,"historical_source_identity_proven":False,
                    "promotion_authorized":False})
    rows = []
    for key, hits in totals.items():
        pc, m, x, e = key
        off = hirom_offset(pc, len(rom))
        node = manifest.get("nodes", {}).get(f"{pc:06X}:M{m}X{x}")
        if e:
            kind = "e_context_not_encoded_by_legacy_manifest"
        elif node:
            kind = "exact_manifest_" + node["disposition"]
        elif (pc, m, x) in labels:
            kind = "generated_internal_label_only"
        else:
            kind = "no_exact_generated_entry_or_label"
        row = {"pc": f"{pc:06X}", "m": m, "x": x, "e": e, "hits": hits,
               "entry_class": kind, "rom_offset": off, "promotion_authorized": False}
        if node:
            row["manifest_instruction_count"] = node.get("instruction_count")
        if off is None:
            row["source_status"] = "not_verified_cartridge_window_requires_bus_bytes"
        else:
            row["exact_cfg_seeds"] = exact_seeds.get(pc, [])
            row["physical_cfg_aliases_not_callable_entries"] = physical_seeds.get(off, [])[:8]
            row["gaialabs_named_blocks_not_code_proof"] = named_blocks.get(off, [])
            region = next((a for a in assets if a["start"] <= off < a["end"]), None)
            if region:
                row["gaialabs_asset_region_requires_review"] = {k: region[k] for k in ("start", "end", "name", "type")}
            if live is not None:
                row["source_status"] = "live_bytes_differ" if live[off:off+4] != rom[off:off+4] else "live_snapshot_bytes_match_original"
            elif args.source_profile == "stock":
                row["source_status"] = "original_bytes_stock_profile_asserted_by_caller"
            else:
                row["source_status"] = "original_only_live_profile_unverified"
            # The current actor routines are dynamically patched for widescreen.
            # Their original instruction bodies must never be blindly promoted.
            if 0x03C5FF <= off < 0x03CA00:
                row["widescreen_actor_overlay_guard_required"] = True
            if rom[off] == 0x02:
                row["cop_dispatch_context_required"] = True
        rows.append(row)
    # Sample by cost, retaining at least one context from each observed bank/MXE
    # group before filling the remaining budget. All rows remain classified.
    candidates = sorted((r for r in rows if r["rom_offset"] is not None), key=lambda r: (-r["hits"],r["pc"],r["m"],r["x"],r["e"]))
    selected, seen, groups = [], set(), set()
    # Transfer discoveries are not callable-context proof; when the matching
    # target instruction was executed, independently check that boundary first.
    for row in candidates:
        key=(int(row["pc"],16),row["m"],row["x"],row["e"])
        if key in forced and len(selected)<args.max_boundaries:
            selected.append(row);seen.add(id(row))
    for row in candidates:
        group = (row["pc"][:2], row["m"], row["x"], row["e"])
        if group not in groups and len(selected) < args.max_boundaries:
            groups.add(group)
            if id(row) not in seen:
                selected.append(row);seen.add(id(row))
    for row in candidates:
        if len(selected) >= args.max_boundaries:
            break
        if id(row) not in seen:
            selected.append(row); seen.add(id(row))

    cached = {}
    if args.reuse_decodes:
        previous=load(args.reuse_decodes)
        if previous.get("tool_sha256")!=TOOL_SHA256 or previous.get("rom_sha256")!=STOCK_SHA256 or previous.get("decoder_sha256")!=digest(ROOT/"snesrecomp/recompiler/snes65816.py"):
            raise ValueError("cached independent decodes have different tool/ROM/decoder identity")
        for old in previous.get("checks",[]):
            if old.get("decode_pass") is True:
                cached[(old["pc"],old["m"],old["x"],old["e"])]=old

    def decode(row):
        pc = int(row["pc"],16); off = row["rom_offset"]
        old=cached.get((row["pc"],row["m"],row["x"],row["e"]))
        if old and old["rom_offset"]==off and old["original_bytes"]==rom[off:off+old["length"]].hex():
            # Reclassifying against a new generated graph does not require
            # re-running unchanged independent original-byte decodes.
            fields=("decode_pass","original_bytes","romatlas_assembly","length",
                    "target","indirect","call","terminal","framework_mnemonic")
            return {**row,**{k:old[k]for k in fields},"decode_reused":True}
        result = subprocess.run([str(args.romatlas), "decode", str(args.rom),
            "--offset", str(off), "--cpu-address", str(pc), "--count", "1",
            "--e", str(bool(row["e"])).lower(), "--m", str(bool(row["m"])).lower(),
            "--x", str(bool(row["x"])).lower()], capture_output=True, text=True, check=True, timeout=20)
        decoded = json.loads(result.stdout)
        if decoded["diagnostics"] or len(decoded["instructions"]) != 1:
            return {**row,"decode_pass":False,"diagnostics":decoded["diagnostics"]}
        instruction = decoded["instructions"][0]["instruction"]
        local = decode_insn(rom,off,pc&0xFFFF,pc>>16,row["m"],row["x"])
        passed = local is not None and local.length == instruction["length"] and local.opcode == instruction["opcode"] and instruction["cpu_address"] == pc
        return {**row,"decode_pass":passed,"original_bytes":rom[off:off+instruction["length"]].hex(),
                "romatlas_assembly":instruction["assembly"],"length":instruction["length"],
                "target":instruction["target"],"indirect":instruction["indirect"],
                "call":instruction["call"],"terminal":instruction["terminal"],
                "framework_mnemonic":local.mnem if local else None}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        checked = list(pool.map(decode,selected))
    report = {"schema":"gaia observed native structural boundaries v1",
        "analysis_only":True,"runtime_oracle":False,"campaign_proof":False,
        "checker_sha256":digest(Path(__file__)),
        "source_profile_assertion":args.source_profile,"inputs":inputs,
        "tool_sha256":digest(args.romatlas),"rom_sha256":digest(args.rom),
        "live_snapshot_sha256":digest(args.live_rom) if args.live_rom else None,
        "wram_snapshots":snapshots,"wram_snapshot_checks":snapshot_checks,
        "generated_identity":generated,"cfg_sha256":seed_hashes,
        "gaialabs_metadata_sha256":{p.name:digest(p) for p in (assets_path,blocks_path) if p.exists()},
        "decoder_sha256":digest(ROOT/"snesrecomp/recompiler/snes65816.py"),
        "observed_contexts":len(rows),"interpreted_instruction_hits":sum(totals.values()),
        "transfer_discoveries":len(transfers),"unique_transfer_target_contexts":len(forced),
        "checked_transfer_target_contexts":sum((int(r["pc"],16),r["m"],r["x"],r["e"]) in forced for r in checked),
        "transfer_rows":transfers,
        "entry_classes":dict(collections.Counter(r["entry_class"] for r in rows)),
        "source_classes":dict(collections.Counter(r["source_status"] for r in rows)),
        "checked_boundaries":len(checked),"decode_mismatches":sum(not r["decode_pass"] for r in checked),
        "reused_decodes":sum(r.get("decode_reused",False)for r in checked),
        "reused_decode_report_sha256":digest(args.reuse_decodes) if args.reuse_decodes else None,
        "checked_hit_weight":sum(r["hits"] for r in checked),
        "rows":sorted(rows,key=lambda r:(r["pc"],r["m"],r["x"],r["e"])),"checks":checked}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,separators=(",",":"),allow_nan=False)+"\n",encoding="utf-8")
    summary = {k:report[k] for k in ("observed_contexts","transfer_discoveries","unique_transfer_target_contexts","checked_transfer_target_contexts","entry_classes","source_classes","checked_boundaries","reused_decodes","decode_mismatches","checked_hit_weight")}
    summary["report"] = str(args.out)
    print(json.dumps(summary,indent=2))
    return int(bool(report["decode_mismatches"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",action="store_true",help="Run ROM-free mapping/schema/chunked-file regression fixtures")
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--coverage", type=Path, action="append")
    parser.add_argument("--romatlas", type=Path)
    parser.add_argument("--generated", type=Path, default=ROOT/"src/gen")
    parser.add_argument("--gaialabs", type=Path, default=ROOT/".local/batch-001/romatlas")
    parser.add_argument("--live-rom", type=Path, help="Optional witnessed cartridge-image snapshot; never inferred from original ROM")
    parser.add_argument("--wram-snapshots", type=Path, action="append", default=[],
                        help="Directory with paired *.wram.bin/*.info.json; byte evidence is scoped to each snapshot frame only")
    parser.add_argument("--reuse-decodes", type=Path,
                        help="Reuse identity/byte-matched independent checks when reclassifying against another generated graph")
    parser.add_argument("--source-profile", choices=("unknown","stock"), default="unknown",
                        help="Explicit caller assertion, not proof supplied by ROM identification")
    parser.add_argument("--max-boundaries", type=int, default=1024)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--out", type=Path, default=ROOT/".local/batch-001/native-002/structural-boundaries.json")
    args = parser.parse_args()
    if args.self_test:return self_test()
    if not args.rom or not args.coverage or not args.romatlas:
        parser.error("--rom, --coverage and --romatlas are required unless --self-test is used")
    if not 1 <= args.max_boundaries <= 50000 or not 1 <= args.jobs <= 16:
        parser.error("max-boundaries must be 1..50000; jobs must be 1..16")
    try:
        return check(args)
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        parser.exit(2,f"Structural check refused: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
