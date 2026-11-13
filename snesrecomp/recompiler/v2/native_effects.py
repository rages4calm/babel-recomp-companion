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
BPL BMI BVC BVS BCC BCS BNE BEQ BRA BRL JMP JML JSR JSL RTS RTL MVN""".split())
LIVE_STATUS_HELPERS = frozenset({"getFlags", "setFlags"})
STATIC_CONTROL_NAMES = frozenset("BPL BMI BVC BVS BCC BCS BNE BEQ BRA BRL JMP JML".split())
STATIC_CONTROL_OPCODES = frozenset({0x10, 0x30, 0x50, 0x70, 0x90, 0xB0,
                                  0xD0, 0xF0, 0x80, 0x82, 0x4C, 0x5C})
DIRECT_CALL_RETURN_NAMES = frozenset({"JSR", "JSL", "RTS", "RTL"})
DIRECT_CALL_RETURN_OPCODES = frozenset({0x20, 0x22, 0x60, 0x6B})
INDIRECT_JUMP_OPCODES = frozenset({0x7C})
INDEXED_CALL_OPCODES = frozenset({0xFC})
NMI_EXCLUDED_OPCODES = frozenset({0x7C, 0x54, 0xFC})
FRAME_NAMES = frozenset({"COP", "RTI"})
FRAME_OPCODES = frozenset({0x02, 0x40})
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


def emit(source, entries, *, registration_name="IogRegisterNativeContinuations",
         nmi_owner_pc24=None, nmi_keys=(), frame_keys=(), scope_limits=(), outline_effects=False):
    """Return private C and an identity receipt for exact decoded entries.

    Entry keys: pc24(int), m/x/e(0/1), bytes(bytes), mnemonic, immediate(bool).
    The caller verifies stock ROM identity and original bytes before invoking.
    Registration independently validates mode/length/bytes in the live mapper.
    """
    if type(outline_effects) is not bool:
        raise ValueError("outline_effects must be an explicit bool")
    if not re.fullmatch(r"[A-Za-z_]\w*", registration_name):
        raise ValueError("Unsafe registration symbol")
    table = re.search(r"cyclesPerOpcode\[256\]\s*=\s*\{([^}]+)\}", source)
    if not table:
        raise ValueError("Missing canonical cycle table")
    cycles = [int(n) for n in re.findall(r"\b\d+\b", table[1])]
    if len(cycles) != 256:
        raise ValueError("Malformed cycle table")
    entries = sorted(entries, key=lambda e: (e["pc24"], e["m"], e["x"], e["e"]))
    if not entries or len(entries) > 131072:
        raise ValueError("A bounded nonempty descriptor set is required")
    keys = set()
    scopes = {}
    for key, flags in scope_limits:
        if (type(key) is not tuple or len(key) != 4
                or any(type(n) is not int for n in key) or key in scopes
                or type(flags) is not int or flags not in (1, 2, 3)):
            raise ValueError("Explicit unique existing-owner scope limits required")
        scopes[key] = flags
    frame_keys = list(frame_keys)
    frame_set = set()
    for key in frame_keys:
        if (type(key) is not tuple or len(key) != 4
                or any(type(n) is not int for n in key) or key in frame_set):
            raise ValueError("Explicit unique frame-effect keys required")
        frame_set.add(key)
    bodies, helpers = {}, {}
    for e in entries:
        key = e["pc24"], e["m"], e["x"], e["e"]
        if (key in keys or type(e["pc24"]) is not int or not 0 <= e["pc24"] <= 0xFFFFFF
                or any(type(e[k]) is not int or e[k] not in (0, 1) for k in ("m", "x", "e"))
                or e["e"] or type(e["bytes"]) is not bytes or not 1 <= len(e["bytes"]) <= 4
                or (e["pc24"] & 0xFFFF) < 0x8000
                or (e["pc24"] & 0xFFFF) + len(e["bytes"]) > 0x10000
                or e["mnemonic"] not in SAFE_NAMES | FRAME_NAMES or type(e["immediate"]) is not bool):
            raise ValueError("Unsupported or duplicate native effect descriptor")
        keys.add(key)
        opcode = e["bytes"][0]
        if (opcode in FRAME_OPCODES) != (key in frame_set):
            raise ValueError("COP/RTI require an exact explicit frame-effect grant")
        # A mnemonic alone also admits indirect JMP/JML addressing forms.
        # Static branches and direct calls/returns keep the same owning bridge
        # frame. Only the qualified indexed-indirect JMP is admitted;
        # other indirect opcode forms remain outside this contract.
        if (e["mnemonic"] in STATIC_CONTROL_NAMES
                and opcode not in STATIC_CONTROL_OPCODES | INDIRECT_JUMP_OPCODES):
            raise ValueError("Only static or indexed-indirect jump effects are supported")
        if (e["mnemonic"] in DIRECT_CALL_RETURN_NAMES
                and opcode not in DIRECT_CALL_RETURN_OPCODES | INDEXED_CALL_OPCODES):
            raise ValueError("Only direct or indexed-indirect call/return effects are supported")
        mnemonic, mode, size = decoder.opcode_table()[opcode]
        size = size(e["m"], e["x"]) if callable(size) else size
        if (mnemonic != e["mnemonic"] or size != len(e["bytes"])
                or (mode == decoder.IMM) != e["immediate"]):
            raise ValueError("Descriptor disagrees with canonical instruction metadata")
        # The source case is shared by every PC/MX descriptor for this opcode.
        # Extract it once; specialization below still uses each exact entry.
        if opcode not in bodies:
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
    if not frame_set <= keys:
        raise ValueError("Unregistered frame-effect key")
    if not scopes.keys() <= keys:
        raise ValueError("Unregistered owner-scope key")
    frame_keys.sort()
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
    if 0x20 in bodies:
        # Preserve the source JSR's opt-in AFC7 observer, including getenv's
        # presence semantics. Other cohorts keep their exact previous bytes.
        parts[0] = parts[0].replace("#include <stddef.h>",
            "#include <stddef.h>\n#include <stdio.h>\n#include <stdlib.h>")
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
    nmi_keys = list(nmi_keys)
    if nmi_keys or nmi_owner_pc24 is not None:
        if (not nmi_keys or type(nmi_owner_pc24) is not int
                or not 0 <= nmi_owner_pc24 <= 0xFFFFFF
                or nmi_owner_pc24 & 0xFFFF < 0x8000
                or nmi_owner_pc24 >> 16 in (0x7E, 0x7F)):
            raise ValueError("Explicit finite upper-ROM NMI owner and sites required")
        seen = set()
        by_key = {(e['pc24'], e['m'], e['x'], e['e']): e for e in entries}
        for key in nmi_keys:
            if (type(key) is not tuple or len(key) != 4
                    or any(type(n) is not int for n in key)
                    or key in seen or key not in by_key
                    or by_key[key]['bytes'][0] in NMI_EXCLUDED_OPCODES
                    or (key in scopes and not scopes[key] & 2)):
                raise ValueError("Unsupported, duplicate or unregistered NMI data site")
            seen.add(key)
        nmi_keys.sort()
    outlined_groups = {}
    if outline_effects:
        parts.append("""#if defined(_MSC_VER)
#define NI_NOINLINE __declspec(noinline)
#elif defined(__GNUC__) || defined(__clang__)
#define NI_NOINLINE __attribute__((noinline))
#else
#error Outlined effects require a supported noinline attribute
#endif""")
        for e in entries:
            group = (e["bytes"], e["m"], e["x"], e["e"], e["immediate"])
            if group in outlined_groups:
                continue
            symbol = f"ni_effect_{len(outlined_groups):05d}"
            outlined_groups[group] = symbol
            m, x = e["m"], e["x"]
            encoded = ",".join(f"0x{v:02X}" for v in e["bytes"])
            body = _rename(bodies[e["bytes"][0]], f"ni_{m}{x}_")
            body = body.replace("cpu->mf", str(m)).replace("cpu->xf", str(x))
            parts.append(f"""static NI_NOINLINE int {symbol}(Interp816 *cpu, uint32_t base) {{
  static const uint8_t code[] = {{{encoded}}};
  NiOperands operands = {{base, code, 0, sizeof code, {str(e['immediate']).lower()}}};
  NiOperands *_ni = &operands;
  cpu->cyclesUsed = 0;
  (void)ni_{m}{x}_readOpcode(cpu, _ni);
  cpu->cyclesUsed = {cycles[e['bytes'][0]]};
{body}
  return cpu->cyclesUsed;
}}""")
    descriptors, descriptor_by_key = [], {}
    for e in entries:
        pc, m, x = e["pc24"], e["m"], e["x"]
        symbol = f"ni_at_{pc:06X}_{m}{x}"
        encoded = ",".join(f"0x{v:02X}" for v in e["bytes"])
        body = _rename(bodies[e["bytes"][0]], f"ni_{m}{x}_")
        body = body.replace("cpu->mf", str(m)).replace("cpu->xf", str(x))
        if outline_effects:
            group = (e["bytes"], m, x, e["e"], e["immediate"])
            parts.append(f"""static int {symbol}(Interp816 *cpu) {{
  if (!cpu || !cpu->read || cpu->e || cpu->mf != {m} || cpu->xf != {x} ||
      cpu->k != 0x{pc >> 16:02X} || cpu->pc != 0x{pc & 0xFFFF:04X}) return 0;
  return {outlined_groups[group]}(cpu, 0x{pc:06X}u);
}}""")
        else:
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
        descriptor = f"  {{0x{pc:06X}u,{m},{x},0,{len(e['bytes'])},{{{encoded}}},{symbol}}}"
        descriptors.append(descriptor)
        descriptor_by_key[(pc, m, x, e['e'])] = descriptor
    parts.append("static const InterpNativeInstruction ni_entries[] = {\n" + ",\n".join(descriptors) + "\n};")
    if nmi_keys:
        parts.append("static const InterpNativeInstruction ni_nmi_entries[] = {\n" +
                     ",\n".join(descriptor_by_key[k] for k in nmi_keys) + "\n};")
    for flags in sorted(set(scopes.values())):
        parts.append(f"static const InterpNativeInstruction ni_scope_{flags}_entries[] = {{\n" +
                     ",\n".join(descriptor_by_key[k] for k in sorted(scopes) if scopes[k] == flags) + "\n};")
    if frame_keys:
        parts.append("static const InterpNativeInstruction ni_frame_entries[] = {\n" +
                     ",\n".join(descriptor_by_key[k] for k in frame_keys) + "\n};")
    if frame_keys or scopes:
        setup = (f"bool {registration_name}(void) {{\n"
                 "  if (!interp_bridge_add_native_instructions(ni_entries, sizeof ni_entries / sizeof *ni_entries)) return false;\n")
        for flags in sorted(set(scopes.values())):
            setup += f"  if (!interp_bridge_restrict_native_instructions(ni_scope_{flags}_entries, sizeof ni_scope_{flags}_entries / sizeof *ni_scope_{flags}_entries, {flags}u)) return false;\n"
        if frame_keys:
            setup += "  if (!interp_bridge_allow_native_frame_instructions(ni_frame_entries, sizeof ni_frame_entries / sizeof *ni_frame_entries)) return false;\n"
        if nmi_keys:
            setup += (f"  return interp_bridge_allow_native_nmi_instructions(0x{nmi_owner_pc24:06X}u, ni_nmi_entries, sizeof ni_nmi_entries / sizeof *ni_nmi_entries);\n}}")
        else:
            setup += "  return true;\n}"
        parts.append(setup)
    elif nmi_keys:
        parts.append(f"""bool {registration_name}(void) {{
  if (!interp_bridge_add_native_instructions(ni_entries, sizeof ni_entries / sizeof *ni_entries)) return false;
  return interp_bridge_allow_native_nmi_instructions(0x{nmi_owner_pc24:06X}u, ni_nmi_entries, sizeof ni_nmi_entries / sizeof *ni_nmi_entries);
}}""")
    else:
        parts.append(f"bool {registration_name}(void) {{ return interp_bridge_add_native_instructions(ni_entries, sizeof ni_entries / sizeof *ni_entries); }}")
    result = "\n\n".join(parts) + "\n"
    if re.search(r"\b(?:interp816_|ni_\d\d_)(?:runOpcode|doOpcode)\s*\(", result):
        raise ValueError("Decoder call in native output")
    receipt = {"schema": "native continuation specialization v1", "entries": len(entries),
                    "helper_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "generated_source_sha256": hashlib.sha256(result.encode()).hexdigest(),
                    "fixed_opcode_bodies": len(bodies), "helper_functions": sorted(helpers)}
    if nmi_keys:
        receipt.update(native_nmi_owner_pc24=nmi_owner_pc24, native_nmi_grants=len(nmi_keys))
    if frame_keys:
        receipt.update(native_frame_grants=len(frame_keys))
    if scopes:
        receipt.update(native_owner_scope_limits=len(scopes))
    if outline_effects:
        grouping = "\n".join(f"{code.hex()}:{m}:{x}:{e}:{int(immediate)}"
                             for code, m, x, e, immediate in outlined_groups)
        receipt.update(outline_effects=True,
                       outlined_effect_bodies=len(outlined_groups),
                       outlined_effect_wrappers=len(entries),
                       outline_grouping="exact bytes,M,X,E,immediate",
                       outline_group_keys_sha256=hashlib.sha256(grouping.encode()).hexdigest())
    return result, receipt
