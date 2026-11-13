"""Prepare private physical WRAM copy effects from hash-bound fetch witnesses."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "snesrecomp/recompiler"))
from v2.native_wram_effects import emit


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(rom, contexts, output):
    private = (ROOT / ".local").resolve()
    output = Path(output).resolve()
    if not output.is_relative_to(private) or output.exists():
        raise ValueError("Fresh private output required")
    expected = re.search(r"(?m)^expected_sha256\s*=\s*(\w+)",
                         (ROOT / "rom_identity.txt").read_text())[1]
    image = Path(rom).read_bytes()
    if len(image) != 2097152 or hashlib.sha256(image).hexdigest() != expected:
        raise ValueError("Verified bare USA ROM required")
    plan = json.loads(Path(contexts).read_text())
    if plan.get("ROM_four_alias_expansion") is not False:
        raise ValueError("WRAM entries must retain exact physical banks")
    witnesses = plan.get("source_probe_hashes")
    if not isinstance(witnesses, dict) or not witnesses:
        raise ValueError("Actual fetched-byte witness identities required")
    for name, digest in witnesses.items():
        path = Path(name).resolve()
        if not path.is_relative_to(private) or sha(path) != digest:
            raise ValueError("Private actual-fetch witness changed")
    entries = []
    for row in plan["contexts"]:
        entry = {k: row[k] for k in ("stub_pc", "m", "x", "e", "scopes")}
        for key in ("pc24", "nmi_owner_pc24"):
            value = row[key]
            entry[key] = int(value, 16) if type(value) is str else value
        entries.append(entry)
    if len(entries) != plan["new_physical_descriptors"]:
        raise ValueError("Physical context count differs from qualified proposal")
    helper = ROOT / "snesrecomp/runner/src/snes/interp816.c"
    result, receipt = emit(helper.read_text(), entries)
    receipt.update(source_file="native_wram.c", rom_sha256=expected,
                   context_plan_sha256=sha(contexts), source_probe_hashes=witnesses,
                   helper_file_sha256=sha(helper),
                   emitter_sha256=sha(ROOT / "snesrecomp/recompiler/v2/native_wram_effects.py"),
                   driver_sha256=sha(__file__), compiled=False, executed=False)
    output.mkdir(parents=True)
    (output / "native_wram.c").write_text(result, encoding="utf-8")
    receipt["generated_source_sha256"] = sha(output / "native_wram.c")
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("contexts", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.rom, args.contexts, args.output), indent=2))
