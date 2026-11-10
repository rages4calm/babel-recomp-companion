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


def prepare(rom: Path, contexts: Path, output: Path, aliases: bool = True):
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
        banks = [bank] if not aliases else [bank & 0x3F | n for n in (0, 0x40, 0x80, 0xC0)]
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
        for pb in ([pc >> 16] if not aliases else
                   [pc >> 16 & 0x3F | n for n in (0, 0x40, 0x80, 0xC0)]):
            key = ((pb << 16) | (pc & 65535), row["m"], row["x"], row["e"])
            if key in grant_keys or key not in entries:
                raise ValueError("Duplicate or unregistered finite-NMI context")
            grant_keys.add(key)
    owner = int(plan["native_nmi_owner_entry_pc24"], 16) if grant_rows else None
    result, receipt = emit(helper.read_text(encoding="utf-8"), list(entries.values()),
                           nmi_owner_pc24=owner, nmi_keys=sorted(grant_keys))
    receipt.update(rom_sha256=digest, context_plan_sha256=hashlib.sha256(contexts.read_bytes()).hexdigest(),
                   helper_file_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),
                   emitter_sha256=hashlib.sha256((ROOT / "snesrecomp/recompiler/v2/native_effects.py").read_bytes()).hexdigest(),
                   driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_file="native_continuations.c", compiled=False, executed=False,
                   source_contexts=len(plan["candidate_contexts"]), physical_aliases=aliases)
    output.mkdir(parents=True, exist_ok=False)
    (output / receipt["source_file"]).write_text(result, encoding="utf-8", newline="\n")
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rom", "contexts", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--no-aliases", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(args.rom, args.contexts, args.output, not args.no_aliases)))
