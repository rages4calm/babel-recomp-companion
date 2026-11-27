"""Check scripts/gaialabs_asm.py against the stock game: every stock routine in
the baserom disassembly that the assembler supports must reassemble, placed
at its own address, to the ROM's bytes exactly; stock dialogue must encode to
the ROM's bytes (dictionary words included); [NAM] is spelled out and text
commands the stock engine lacks are refused.

  python scripts/test_gaialabs_asm.py --rom "Illusion of Gaia (USA).sfc" --baserom <gaia-iog-baserom checkout>
"""
import argparse, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gaialabs_asm as ga


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--baserom", required=True)
    ap.add_argument("--min", type=int, default=1300, help="routines that must reassemble")
    a = ap.parse_args()
    rom = Path(a.rom).read_bytes()
    db = ga.Db(a.baserom, rom, ["Will", "Kara", "Lilly", "Erik", "Lance"])
    same = differ = 0
    for p in sorted((Path(a.baserom) / "extracted").rglob("*.asm")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"^(code_([0-9A-F]{6}))\s*\{(.*?)^\}", text, re.M | re.S):
            name = m.group(1)
            off = db.stock(name)
            try:
                consts, blocks = ga.parse("%sX {\n%s\n}\n" % (name, m.group(3)))
                asm = ga.Assembler(db, consts, blocks)
                asm.place(off, [name + "X"])
                got = asm.emit(name + "X")
            except (ga.AsmError, KeyError, ValueError):
                continue        # outside the supported subset
            if got == rom[off:off + len(got)]:
                same += 1
            else:
                differ += 1
                print("DIFFERS %s %s\n  asm %s\n  rom %s" % (p.name, name, got.hex(" "), rom[off:off + len(got)].hex(" ")))
    print("%d stock routines reassemble byte for byte, %d differ" % (same, differ))
    assert differ == 0 and same >= a.min, "assembler does not match the ROM"

    enc = ga.encode_string(db, "[DEF]You're not equipped.[END]", lambda n: 0)
    assert enc == rom[0x384C4:0x384C4 + len(enc)], enc.hex(" ")
    assert ga.encode_string(db, "[NAM:4]...", lambda n: 0) == ga.encode_string(db, "Lance...", lambda n: 0)
    # GaiaLabs speaker themes become stock commands; the stock table ends at $15
    db.themes = {0x16: (0x7FFB, 0x762F, 0x10)}
    themed = ga.encode_string(db, "[TPL:16][TPL:C]Hi[END]", lambda n: 0)
    # box first (opening a box resets the speaker colour), then the theme's
    # colours and voice, the text, and the narration palette before [END]
    assert themed[:2] == bytes([0xC2, 0x0C]), themed.hex(" ")
    assert themed[2:14] == bytes([0xD4, 0x11, 0xFB, 0x7F, 0xD4, 0x12, 0x2F, 0x76, 0xD2, 0x10, 0xC3, 0x04]), themed.hex(" ")
    assert themed.endswith(bytes([0xC3, 0x00, 0xC0])), themed.hex(" ")
    assert not any(themed[i] == 0xC2 and themed[i + 1] > 0x15 for i in range(len(themed) - 1))
    for bad in ("[BOR:1]", "[NAM:20]", "[TPL:11]", "[TPL:30]"):
        try:
            ga.encode_string(db, bad, lambda n: 0)
        except ga.AsmError:
            continue
        raise AssertionError("%s was accepted" % bad)
    print("dialogue encoding matches the ROM; names spelled out; non-stock commands refused")


if __name__ == "__main__":
    main()
