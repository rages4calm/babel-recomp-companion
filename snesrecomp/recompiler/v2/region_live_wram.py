"""Explicit live unindexed-ABS reads, guarded to ordinary WRAM data only.

A pure plain-code preview validates the target before any guest mutation.
Accepted instructions then fetch operand bytes and data exactly once through
paced authoritative accessors. ROM edits belong at instruction boundaries.
"""
import re
import snes65816 as d

NAMES = {"LDA", "LDX", "LDY", "ADC", "SBC", "AND", "ORA", "EOR",
         "CMP", "CPX", "CPY", "BIT"}


def plan(insn, lines, cpu_cycles):
    if insn.mode != d.ABS or insn.mnem not in NAMES or insn.length != 3:
        return None
    from v2.codegen import _emit_read
    from v2.ir import Read, Value
    from v2.lowering import _segref_for
    width = 1 if (insn.x_flag if insn.mnem in {"LDX", "LDY", "CPX", "CPY"} else insn.m_flag) else 2
    internal = cpu_cycles - 3 - width
    if internal < 0:
        return None
    pc = insn.addr & 0xFFFF
    if pc < 0x8000 or pc > 0xFFFC:
        return None
    text = "\n".join(lines)
    name = f"_lwa_{insn.addr:06X}_{insn.m_flag}{insn.x_flag}"
    matches = []
    for vid in sorted(set(int(v) for v in re.findall(r"\b_v(\d+)\b", text))):
        original = "\n".join(_emit_read(Read(_segref_for(insn), width, Value(vid))))
        if text.count(original) == 1:
            replacement = f"uint{width * 8} _v{vid} = cpu_read{width * 8}_paced(cpu, cpu->DB, {name}_address);"
            matches.append((original, replacement))
    if len(matches) != 1:
        return None
    text = text.replace(*matches[0])
    if re.search(r"\bcpu_(?:read|write)(?:8|16)\(", text):
        return None
    prefix = [
        f"uint16 {name}_preview;",
        f"if (!cpu_preview_code16(cpu, cpu->PB, 0x{pc + 1:04X}u, &{name}_preview)) {{ @FALLBACK@ }}",
        f"if (!((cpu->DB == 0x7Eu || cpu->DB == 0x7Fu) || "
        f"((cpu->DB & 0x7Fu) < 0x40u && {name}_preview <= 0x{0x2000 - width:04X}u))"
        + (f" || {name}_preview == 0xFFFFu" if width == 2 else "") + ") { @FALLBACK@ }",
    ]
    body = [f"uint16 {name}_address = cpu_read8_paced(cpu, cpu->PB, 0x{pc + 1:04X}u);",
            f"{name}_address |= (uint16)cpu_read8_paced(cpu, cpu->PB, 0x{pc + 2:04X}u) << 8;"]
    text = re.sub(r"cpu->master_cycles\s*\+=\s*([^;]+);",
                  r"cpu_add_aot_master_cycles(cpu, \1);", text)
    body.extend(text.split("\n"))
    fetch = f"cpu_region_speed(((uint32)cpu->PB << 16) | 0x{pc:04X}u)"
    if internal:
        fetch += f" + {internal * 6}"
    return fetch, body, prefix
