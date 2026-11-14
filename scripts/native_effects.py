"""Emit private, source-qualified continuation effects without changing CFGs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "snesrecomp/recompiler"))
import snes65816 as decoder
from v2.native_effects import emit


def context_banks(row, aliases=True):
    """Explicit physical additions need not speculate about unobserved mirrors.

    Absent/false retains the original four-alias recipe. The same recipe must
    be carried by candidate and permission rows; permissions still have to name
    registered keys. Mutable WRAM has its own generator and is not expanded here.
    """
    physical_only = row.get("physical_only", False)
    if type(physical_only) is not bool:
        raise ValueError("physical_only must be an explicit bool")
    pc = int(row["pc24"], 16)
    if not 0 <= pc <= 0xFFFFFF:
        raise ValueError("Invalid physical instruction address")
    bank = pc >> 16
    return ([bank] if physical_only or not aliases else
            [bank & 0x3F | n for n in (0, 0x40, 0x80, 0xC0)])


def validate_owner_policy(entries, scope_limits, grant_keys, policy):
    """Title policy for finite instructions, without weakening AOT barriers."""
    contract = policy.get("fixed_instruction_scopes", {})
    if contract.get("schema") != "gaia fixed instruction owner scopes v1":
        raise ValueError("Missing fixed-instruction owner policy")
    canonical = lambda pc: pc & 0x3FFFFF
    ranges = [(canonical(int(r["start"], 16)), canonical(int(r["end_exclusive"], 16)))
              for r in contract["scope_only_ranges"]]
    mutable = [(canonical(int(r["start"], 16)), canonical(int(r["end_exclusive"], 16)))
               for r in contract.get("mutable_operand_ranges", [])]
    forbidden = {canonical(int(pc, 16)) for pc in contract["forbidden_sites"]}
    acknowledgements = set()
    for row in contract.get("qualified_rdnmi_ack_contexts", []):
        key = (int(row["pc24"], 16), row["m"], row["x"], row["e"])
        if (key in acknowledgements or any(type(n) is not int for n in key)
                or not 0 <= key[0] <= 0xFFFFFF or key[1:] != (1, 0, 0)
                or canonical(key[0]) not in forbidden
                or canonical(key[0]) in (0x02804D, 0x028051)):
            raise ValueError("Invalid exact RDNMI acknowledgement policy")
        acknowledgements.add(key)
    vectors = {canonical(int(pc, 16)) for pc in contract["vector_jumps"]}
    for key, entry in entries.items():
        pc = canonical(key[0])
        if any(pc < hi and pc + len(entry["bytes"]) > lo for lo, hi in mutable):
            raise ValueError("Immutable fixed instruction intersects a live patched operand")
        if pc in forbidden:
            if (key not in acknowledgements or entry["bytes"] != b"\xaf\x10\x42\x80"
                    or entry.get("mnemonic") != "LDA"
                    or type(scope_limits.get(key)) is not int
                    or scope_limits[key] != 1 or key in grant_keys):
                raise ValueError("Protected RDNMI acknowledgement/poll control")
        vector = 0x8000 <= pc < 0x8014
        if vector and (pc not in vectors or entry["bytes"][0] != 0x5C):
            raise ValueError("Reset/IRQ or non-long-jump vector remains protected")
        if vector or any(lo <= pc < hi for lo, hi in ranges):
            flags = scope_limits.get(key)
            if type(flags) is not int or flags not in (1, 2, 3):
                raise ValueError("Protected fixed instruction requires an explicit owner scope")
            if flags & 2 and key not in grant_keys:
                raise ValueError("NMI-scoped fixed instruction requires its exact NMI grant")


def prepare(rom: Path, contexts: Path, output: Path, aliases: bool = True, *,
            outline_effects: bool = False):
    output = output.resolve()
    if not output.is_relative_to((ROOT / ".local").resolve()) or output.exists():
        raise ValueError("Fresh project-private output required")
    image = rom.read_bytes()
    expected = re.search(r"^expected_sha256\s*=\s*([0-9a-f]{64})$",
                         (ROOT / "rom_identity.txt").read_text(), re.M)[1]
    digest = hashlib.sha256(image).hexdigest()
    if len(image) != 2097152 or digest != expected:
        raise ValueError("Verified bare stock USA ROM required")
    plan = json.loads(contexts.read_text(encoding="utf-8"))
    if plan["rom_sha256"] != digest:
        raise ValueError("Context source identity mismatch")
    decoder.set_rom_mapping("hirom")
    entries = {}
    for row in plan["candidate_contexts"]:
        original = int(row["pc24"], 16)
        bank, pc = original >> 16, original & 65535
        banks = context_banks(row, aliases)
        for pb in banks:
            offset = decoder.rom_offset(pb, pc)
            insn = decoder.decode_insn(image, offset, pc, pb, row["m"], row["x"])
            code = image[offset:offset + insn.length]
            if code != bytes.fromhex(row["original_bytes"]) or insn.mnem != row["mnemonic"]:
                raise ValueError("Decoded context/opcode source mismatch")
            entry = dict(pc24=(pb << 16) | pc, m=row["m"], x=row["x"], e=row["e"],
                         bytes=code, mnemonic=insn.mnem, immediate=insn.mode == decoder.IMM)
            key = entry["pc24"], entry["m"], entry["x"], entry["e"]
            if key in entries and entries[key] != entry:
                raise ValueError("Conflicting contexts")
            entries[key] = entry
    helper = ROOT / "snesrecomp/runner/src/snes/interp816.c"
    grant_rows = plan.get("native_nmi_grant_contexts", [])
    grant_keys = set()
    for row in grant_rows:
        pc = int(row["pc24"], 16)
        for pb in context_banks(row, aliases):
            key = ((pb << 16) | (pc & 65535), row["m"], row["x"], row["e"])
            if key in grant_keys or key not in entries:
                raise ValueError("Duplicate or unregistered finite-NMI context")
            grant_keys.add(key)
    owner = int(plan["native_nmi_owner_entry_pc24"], 16) if grant_rows else None
    frame_keys = set()
    for row in plan.get("native_frame_grant_contexts", []):
        pc = int(row["pc24"], 16)
        for pb in context_banks(row, aliases):
            key = ((pb << 16) | (pc & 65535), row["m"], row["x"], row["e"])
            if key in frame_keys or key not in entries:
                raise ValueError("Duplicate or unregistered frame-effect context")
            frame_keys.add(key)
    scope_limits = {}
    for row in plan.get("native_owner_scope_contexts", []):
        pc = int(row["pc24"], 16)
        for pb in context_banks(row, aliases):
            key = ((pb << 16) | (pc & 65535), row["m"], row["x"], row["e"])
            if key in scope_limits or key not in entries:
                raise ValueError("Duplicate or unregistered owner-scope context")
            scope_limits[key] = row["scopes"]
    validate_owner_policy(entries, scope_limits, grant_keys,
                          json.loads((ROOT / "recomp/native/policy.json").read_text()))
    result, receipt = emit(helper.read_text(encoding="utf-8"), list(entries.values()),
                           nmi_owner_pc24=owner, nmi_keys=sorted(grant_keys),
                           frame_keys=sorted(frame_keys),
                           scope_limits=sorted(scope_limits.items()),
                           outline_effects=outline_effects)
    receipt.update(rom_sha256=digest, context_plan_sha256=hashlib.sha256(contexts.read_bytes()).hexdigest(),
                   helper_file_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),
                   emitter_sha256=hashlib.sha256((ROOT / "snesrecomp/recompiler/v2/native_effects.py").read_bytes()).hexdigest(),
                   driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_file="native_continuations.c", compiled=False, executed=False,
                   source_contexts=len(plan["candidate_contexts"]), physical_aliases=aliases)
    exact_count = sum(row.get("physical_only", False)
                      for row in plan["candidate_contexts"])
    if exact_count:
        receipt.update(physical_only_source_contexts=exact_count,
                       legacy_source_contexts=len(plan["candidate_contexts"]) - exact_count,
                       alias_recipe="Legacy rows follow the launch alias option; physical_only rows retain their exact PBR. Permissions use the same per-row recipe.")
    output.mkdir(parents=True, exist_ok=False)
    (output / receipt["source_file"]).write_text(result, encoding="utf-8", newline="\n")
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rom", "contexts", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--no-aliases", action="store_true")
    parser.add_argument("--outline-effects", action="store_true",
                        help="Outline exact repeated effects behind unchanged guarded PC wrappers")
    args = parser.parse_args()
    print(json.dumps(prepare(args.rom, args.contexts, args.output, not args.no_aliases,
                             outline_effects=args.outline_effects)))
