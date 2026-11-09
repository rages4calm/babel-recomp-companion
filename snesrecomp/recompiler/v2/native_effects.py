"""Generation-time specialization of fixed, guarded continuation effects.

Only ALU/address helpers and one selected case body are copied from the
LakeSnes-derived interp816 source. No opcode decoder, execution counters or
interpreter entry point is emitted. Resulting game-specific C stays private.
"""
import hashlib
import re
import snes65816 as decoder

SAFE_NAMES = frozenset("""LDA LDX LDY STA STX STY STZ ADC SBC AND ORA EOR CMP
CPX CPY BIT TSB TRB ASL LSR ROL ROR INC DEC INX INY DEX DEY TAX TAY TXA TYA
TXY TYX TCD TDC CLC SEC CLD SED CLV CLI SEI NOP XBA
REP SEP PHP PLP PHA PLA PHX PLX PHY PLY PHD PLD PHK PHB PLB PEA PER PEI
BPL BMI BVC BVS BCC BCS BNE BEQ BRA BRL JMP JML""".split())
LIVE_STATUS_HELPERS = frozenset({"getFlags", "setFlags"})
STATIC_CONTROL_NAMES = frozenset("BPL BMI BVC BVS BCC BCS BNE BEQ BRA BRL JMP JML".split())
STATIC_CONTROL_OPCODES = frozenset({0x10, 0x30, 0x50, 0x70, 0x90, 0xB0,
                                  0xD0, 0xF0, 0x80, 0x82, 0x4C, 0x5C})
FORBIDDEN = frozenset({"runOpcode", "doOpcode", "doInterrupt", "init", "reset",
                       "free", "saveload", "opcode_hook"})


def _end_block(source, opening):
    depth, state, i = 0, "code", opening
    while i < len(source):
        char, pair = source[i], source[i:i + 2]
        if state == "line":
            if char == "\n":
                state = "code"
        elif state == "comment":
            if pair == "*/":
                state = "code"
                i += 1
        elif state in {'"', "'"}:
            if char == "\\":
                i += 1
            elif char == state:
                state = "code"
        elif pair in {"//", "/*"}:
            state = "line" if pair == "//" else "comment"
            i += 1
        elif char in {'"', "'"}:
            state = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if not depth:
                return i + 1
        i += 1
    raise ValueError("Unterminated C helper/case")


def _function(source, name):
    match = re.search(r"(?m)^(?:static\s+)?[\w* ]+\binterp816_" + re.escape(name)
                      + r"\([^;{}\n]*\)\s*\{", source)
    if not match:
        raise ValueError(f"Missing source helper {name}")
    opening = source.index("{", match.start(), match.end())
    return source[match.start():_end_block(source, opening)]


def _body(source, opcode):
    decoder = _function(source, "doOpcode")
    match = re.search(r"\bcase\s+0x" + f"{opcode:02x}" + r"\s*:\s*\{", decoder, re.I)
    if not match:
        raise ValueError(f"Unsupported case shape {opcode:02X}")
    start = decoder.index("{", match.start(), match.end())
    body = decoder[start + 1:_end_block(decoder, start) - 1]
    body = re.sub(r"\s*break\s*;\s*$", "", body)
    if re.search(r"\b(?:break|continue|goto|return|switch)\b", body):
        raise ValueError("Unsupported case control flow")
    return body


def _calls(text):
    return set(re.findall(r"\binterp816_(\w+)\s*\(", text))


def _rename(text, prefix):
    # Every included helper uses the live Interp816 as its first argument.
    text = re.sub(r"\(\s*Interp816\s*\*\s*cpu", "(Interp816 *cpu, NiOperands *_ni", text)
    text = re.sub(r"\binterp816_(\w+)\s*\(\s*cpu\s*(?=[,)])",
                  lambda m: f"{prefix}{m[1]}(cpu, _ni", text)
    return re.sub(r"\binterp816_(\w+)\b", lambda m: prefix + m[1], text)


def emit(source, entries, *, registration_name="IogRegisterNativeContinuations"):
    """Return private C and an identity receipt for exact decoded entries.

    Entry keys: pc24(int), m/x/e(0/1), bytes(bytes), mnemonic, immediate(bool).
    The caller verifies stock ROM identity and original bytes before invoking.
    Registration independently validates mode/length/bytes in the live mapper.
    """
    if not re.fullmatch(r"[A-Za-z_]\w*", registration_name):
        raise ValueError("Unsafe registration symbol")
    table = re.search(r"cyclesPerOpcode\[256\]\s*=\s*\{([^}]+)\}", source)
    if not table:
        raise ValueError("Missing canonical cycle table")
    cycles = [int(n) for n in re.findall(r"\b\d+\b", table[1])]
    if len(cycles) != 256:
        raise ValueError("Malformed cycle table")
    entries = sorted(entries, key=lambda e: (e["pc24"], e["m"], e["x"], e["e"]))
    if not entries or len(entries) > 8192:
        raise ValueError("A bounded nonempty descriptor set is required")
    keys = set()
    bodies, helpers = {}, {}
    for e in entries:
        key = e["pc24"], e["m"], e["x"], e["e"]
        if (key in keys or type(e["pc24"]) is not int or not 0 <= e["pc24"] <= 0xFFFFFF
                or any(type(e[k]) is not int or e[k] not in (0, 1) for k in ("m", "x", "e"))
                or e["e"] or type(e["bytes"]) is not bytes or not 1 <= len(e["bytes"]) <= 4
                or (e["pc24"] & 0xFFFF) < 0x8000
                or (e["pc24"] & 0xFFFF) + len(e["bytes"]) > 0x10000
                or e["mnemonic"] not in SAFE_NAMES or type(e["immediate"]) is not bool):
            raise ValueError("Unsupported or duplicate native effect descriptor")
        keys.add(key)
        opcode = e["bytes"][0]
        # A mnemonic alone also admits indirect JMP/JML addressing forms.
        # Static branches keep the same owning bridge frame; indirect targets
        # and all call/return frames remain outside this emitter contract.
        if e["mnemonic"] in STATIC_CONTROL_NAMES and opcode not in STATIC_CONTROL_OPCODES:
            raise ValueError("Only static branch/jump effects are supported")
        mnemonic, mode, size = decoder.opcode_table()[opcode]
        size = size(e["m"], e["x"]) if callable(size) else size
        if (mnemonic != e["mnemonic"] or size != len(e["bytes"])
                or (mode == decoder.IMM) != e["immediate"]):
            raise ValueError("Descriptor disagrees with canonical instruction metadata")
        bodies[opcode] = _body(source, opcode)
        pending = _calls(bodies[opcode]) | {"readOpcode"}
        while pending:
            name = min(pending)
            pending.remove(name)
            if name in FORBIDDEN:
                raise ValueError(f"Forbidden native dependency {name}")
            if name in helpers:
                continue
            text = _function(source, name)
            if re.search(r"\b(?:g_|s_)\w+|\b(?:fprintf|getenv|malloc|free|exit)\s*\(", text):
                raise ValueError(f"Unsupported nonlocal helper {name}")
            if name != "setFlags" and re.search(r"cpu->(?:mf|xf)\s*=(?!=)", text):
                raise ValueError("Only the status setter may change instruction widths")
            helpers[name] = text
            pending |= _calls(text) - set(helpers)
    parts = ["""/* PRIVATE ROM-derived continuations; never distribute this file.
 * ISA helpers specialized from LakeSnes-derived interp816.c (MIT,
 * copyright2021-2023 angelo_wf and contributors); preserve SDK attribution. */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "snes/interp816.h"
#include "snes/interp_bridge.h"
typedef struct NiOperands {
  uint32_t base; const uint8_t *bytes; unsigned next, length; bool immediate;
} NiOperands;
"""]
    # Helpers are specialized at generation time to the admitted M/X. Every
    # actual fetch still reaches the bus; immutable operands become constants.
    for m, x in sorted({(e["m"], e["x"]) for e in entries}):
        prefix = f"ni_{m}{x}_"
        definitions = {}
        for name, original in sorted(helpers.items()):
            text = _rename(original, prefix)
            # REP/SEP/PLP change live widths for the NEXT instruction. Preserve
            # status reads/writes and index-high truncation in these helpers;
            # ordinary addressing/ALU/stack widths still specialize the entry M/X.
            if name not in LIVE_STATUS_HELPERS:
                text = text.replace("cpu->mf", str(m)).replace("cpu->xf", str(x))
            text = re.sub(r"^(?:static\s+)?", "static inline ", text, count=1)
            if name == "readOpcode":
                text = f"""static inline uint8_t {prefix}readOpcode(Interp816 *cpu, NiOperands *_ni) {{
  unsigned n = _ni->next++;
  cpu->pc = (uint16_t)(_ni->base + n + 1u);
  (void)cpu->read(cpu->mem, _ni->base + n);
  return _ni->bytes[n];
}}"""
            elif name == "read":
                text = f"""static inline uint8_t {prefix}read(Interp816 *cpu, NiOperands *_ni, uint32_t adr) {{
  uint8_t value = cpu->read(cpu->mem, adr);
  if (_ni->immediate && adr > _ni->base && adr - _ni->base < _ni->length)
    return _ni->bytes[adr - _ni->base];
  return value;
}}"""
            definitions[name] = text
        parts += [text[:text.index("{")].rstrip() + ";" for text in definitions.values()]
        parts += list(definitions.values())
    descriptors = []
    for e in entries:
        pc, m, x = e["pc24"], e["m"], e["x"]
        symbol = f"ni_at_{pc:06X}_{m}{x}"
        encoded = ",".join(f"0x{v:02X}" for v in e["bytes"])
        body = _rename(bodies[e["bytes"][0]], f"ni_{m}{x}_")
        body = body.replace("cpu->mf", str(m)).replace("cpu->xf", str(x))
        parts.append(f"""static int {symbol}(Interp816 *cpu) {{
  if (!cpu || !cpu->read || cpu->e || cpu->mf != {m} || cpu->xf != {x} ||
      cpu->k != 0x{pc >> 16:02X} || cpu->pc != 0x{pc & 0xFFFF:04X}) return 0;
  static const uint8_t code[] = {{{encoded}}};
  NiOperands operands = {{0x{pc:06X}u, code, 0, sizeof code, {str(e['immediate']).lower()}}};
  NiOperands *_ni = &operands;
  cpu->cyclesUsed = 0;
  (void)ni_{m}{x}_readOpcode(cpu, _ni);
  cpu->cyclesUsed = {cycles[e['bytes'][0]]};
{body}
  return cpu->cyclesUsed;
}}""")
        descriptors.append(f"  {{0x{pc:06X}u,{m},{x},0,{len(e['bytes'])},{{{encoded}}},{symbol}}}")
    parts.append("static const InterpNativeInstruction ni_entries[] = {\n" + ",\n".join(descriptors) + "\n};")
    parts.append(f"bool {registration_name}(void) {{ return interp_bridge_add_native_instructions(ni_entries, sizeof ni_entries / sizeof *ni_entries); }}")
    result = "\n\n".join(parts) + "\n"
    if re.search(r"\b(?:interp816_|ni_\d\d_)(?:runOpcode|doOpcode)\s*\(", result):
        raise ValueError("Decoder call in native output")
    return result, {"schema": "native continuation specialization v1", "entries": len(entries),
                    "helper_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "generated_source_sha256": hashlib.sha256(result.encode()).hexdigest(),
                    "fixed_opcode_bodies": len(bodies), "helper_functions": sorted(helpers)}
