"""Private, source-qualified bank-copy stub effects with live operand fetches.

Only the PHB/MVN/PLB/RTS architectural bodies and their ISA helpers are copied.
The caller supplies independently qualified physical contexts and owners; this
module neither samples RAM nor infers executable bytes from an old profile PC.
"""
import hashlib
import re

from .native_effects import _body, _calls, _function, FORBIDDEN, LIVE_STATUS_HELPERS

OFFSETS = {0: 0x8B, 1: 0x54, 4: 0xAB, 5: 0x60}


def emit(source, entries, *, registration_name="IogRegisterNativeWramCopyContinuations"):
    if not re.fullmatch(r"[A-Za-z_]\w*", registration_name):
        raise ValueError("Unsafe registration symbol")
    entries = list(entries)
    if not entries or len(entries) > 65535:
        raise ValueError("Bounded nonempty physical WRAM contexts required")
    keys = set()
    for row in entries:
        required = ("pc24", "stub_pc", "m", "x", "e", "scopes", "nmi_owner_pc24")
        if any(type(row.get(k)) is not int for k in required):
            raise ValueError("Explicit integer WRAM context and owner fields required")
        pc, base = row["pc24"], row["stub_pc"]
        bank = pc >> 16
        key = pc, row["m"], row["x"], row["e"]
        if (key in keys or not 0 <= pc <= 0xFFFFFF or not 1 <= base <= 0x1FFA
                or (pc & 65535) - base not in OFFSETS
                or not (bank < 0x40 or 0x80 <= bank < 0xC0 or bank == 0x7E)
                or row["m"] not in (0, 1) or row["x"] not in (0, 1) or row["e"]
                or row["scopes"] not in (1, 2, 3)):
            raise ValueError("Unsupported or duplicate physical WRAM context")
        owner = row["nmi_owner_pc24"]
        if row["scopes"] & 2:
            if (not 0 <= owner <= 0xFFFFFF or owner & 65535 < 0x8000
                    or owner >> 16 in (0x7E, 0x7F)):
                raise ValueError("Exact finite upper-ROM NMI owner required")
        elif owner:
            raise ValueError("Scheduler-only WRAM context cannot grant an NMI owner")
        keys.add(key)
    entries.sort(key=lambda row: (row["pc24"], row["m"], row["x"], row["e"]))
    cycle_match = re.search(r"cyclesPerOpcode\[256\]\s*=\s*\{([^}]+)\}", source)
    if not cycle_match:
        raise ValueError("Missing canonical cycle table")
    cycles = [int(n) for n in re.findall(r"\b\d+\b", cycle_match[1])]
    if len(cycles) != 256:
        raise ValueError("Malformed cycle table")
    opcodes = {OFFSETS[(row["pc24"] & 65535) - row["stub_pc"]] for row in entries}
    bodies = {opcode: _body(source, opcode) for opcode in opcodes}
    helpers = {}
    pending = {"readOpcode"}
    for body in bodies.values():
        pending |= _calls(body)
    while pending:
        name = min(pending)
        pending.remove(name)
        if name in FORBIDDEN:
            raise ValueError("Interpreter engine dependency is forbidden")
        if name in helpers:
            continue
        text = _function(source, name)
        if re.search(r"\b(?:g_|s_)\w+|\b(?:fprintf|getenv|malloc|free|exit)\s*\(", text):
            raise ValueError("Nonlocal WRAM helper dependency")
        if name != "setFlags" and re.search(r"cpu->(?:mf|xf)\s*=(?!=)", text):
            raise ValueError("Unexpected instruction width mutation")
        helpers[name] = text
        pending |= _calls(text) - set(helpers)
    parts = ["""/* PRIVATE source-qualified WRAM continuations; never distribute game output.
 * ISA helpers from LakeSnes-derived interp816.c (MIT,
 * copyright2021-2023 angelo_wf and contributors); preserve SDK attribution. */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "snes/interp816.h"
#include "snes/interp_native_wram.h"
"""]
    for m, x in sorted({(row["m"], row["x"]) for row in entries}):
        prefix = f"wc_{m}{x}_"
        definitions = []
        for name, original in sorted(helpers.items()):
            text = re.sub(r"\binterp816_(\w+)\b", lambda match: prefix + match[1], original)
            if name not in LIVE_STATUS_HELPERS:
                text = text.replace("cpu->mf", str(m)).replace("cpu->xf", str(x))
            text = re.sub(r"^(?:static\s+)?", "static inline ", text, count=1)
            definitions.append(text)
        parts += [text[:text.index("{")].rstrip() + ";" for text in definitions]
        parts += definitions
    descriptors = []
    for row in entries:
        pc, m, x = row["pc24"], row["m"], row["x"]
        opcode = OFFSETS[(pc & 65535) - row["stub_pc"]]
        prefix = f"wc_{m}{x}_"
        body = re.sub(r"\binterp816_(\w+)\b", lambda match: prefix + match[1], bodies[opcode])
        body = body.replace("cpu->mf", str(m)).replace("cpu->xf", str(x))
        symbol = f"wc_at_{pc:06X}_{m}{x}"
        parts.append(f"""static int {symbol}(Interp816 *cpu) {{
  if (!cpu || !cpu->read || !cpu->write || cpu->e || cpu->mf != {m} || cpu->xf != {x} ||
      cpu->k != 0x{pc >> 16:02X} || cpu->pc != 0x{pc & 65535:04X}) return 0;
  cpu->cyclesUsed = 0;
  (void){prefix}readOpcode(cpu);
  cpu->cyclesUsed = {cycles[opcode]};
{body}
  return cpu->cyclesUsed;
}}""")
        descriptors.append(f"  {{0x{pc:06X}u,0x{row['stub_pc']:04X}u,{m},{x},0,{row['scopes']}u,0x{row['nmi_owner_pc24']:06X}u,{symbol}}}")
    parts.append("static const InterpNativeWramCopyInstruction wc_entries[] = {\n" +
                 ",\n".join(descriptors) + "\n};")
    parts.append(f"""bool {registration_name}(void) {{
  return interp_bridge_add_native_wram_copy_instructions(wc_entries,
      sizeof wc_entries / sizeof *wc_entries);
}}""")
    result = "\n\n".join(parts) + "\n"
    receipt = {"schema": "physical live-operand WRAM copy effects v1",
               "entries": len(entries), "physical_aliases_expanded": False,
               "fixed_opcode_bodies": len(bodies), "helper_functions": sorted(helpers),
               "native_wram_NMI_grants": sum(bool(row["scopes"] & 2) for row in entries),
               "helper_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
               "generated_source_sha256": hashlib.sha256(result.encode()).hexdigest(),
               "scope": "One real opcode/MVN byte per callback; actual live fetches and original retirement. Caller qualifies source/owners."}
    return result, receipt
