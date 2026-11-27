"""A small assembler for GaiaLabs module patches (IOGRetranslation modules),
enough to rebuild their script code for the native Companion build.

GaiaLabs writes actor scripts in its own syntax: COP calls with typed
operands (`COP [BF] ( &dialogstring_0594B8 )`), a few 65816 instructions,
lists of pointers (`name [ &a &b ]`) and dialogue strings in backticks with
markup (`[TPL:16]Welcome back [NAM:0]![END]`). Operand layouts come from the
baserom's own copdef.json and the string encoding from stringTypes.json, so
nothing here guesses at the game's formats.

Native code ignores changed ROM code, so a replaced routine is not patched
in place: its new body is assembled into free space and the data that
reaches it (a COP operand such as SetInteractHandler's, a pointer list) is
pointed there. An address with no native body runs in the interpreter.

Every new block of one option goes into one free region of one bank, because
COP '&' operands and pointer lists are 16-bit, bank-relative to the code.
"""
import json, re, struct
from pathlib import Path

HEX = re.compile(r"[0-9A-Fa-f]+")


class AsmError(Exception):
    pass


def hiroms(offset):
    """ROM offset -> bank byte and 16-bit address. The game's own 24-bit
    pointers use the $80-$BF mirror (FastROM), e.g. $84:BE57."""
    return 0x80 | (offset >> 16), offset & 0xFFFF


class Db:
    """The baserom database: COP layouts, string encoding, stock labels."""

    def __init__(self, baserom, rom, names=None, themes=None):
        base = Path(baserom)
        self.rom = rom
        self.names = names or []
        self.themes = themes or {}
        self.cop = {}
        for name, v in json.load(open(base / "db-us" / "copdef.json", encoding="utf-8")).items():
            self.cop[v["id"]] = v["parts"]
            self.cop[name] = v["parts"]
            self.cop_id = getattr(self, "cop_id", {})
            self.cop_id[name] = v["id"]
        st = json.load(open(base / "db-us" / "stringTypes.json", encoding="utf-8"))["DialogString"]
        self.cmds = {k: (v["id"], v["types"]) for k, v in st["commands"].items()}
        self.glyph = {}
        for i, ch in enumerate(st["layers"][0]["map"]):
            if ch and ch not in self.glyph:
                self.glyph[ch] = ((i >> 4) << 5) | (i & 0xF)
        for i, ch in enumerate(st["layers"][1]["map"]):
            if ch and ch not in self.glyph:
                self.glyph[ch] = st["layers"][1]["base"] + i
        # the game's word dictionaries ([LU1:n], [LU2:n]): two bytes per word
        self.words = []
        for d in st.get("dictionaries", {}).values():
            for n, w in enumerate(d["entries"]):
                self.words.append((w, d["command"], n))
        self.words.sort(key=lambda e: -len(e[0]))
        self.extracted = base / "extracted"
        self._named = None

    def stock(self, label):
        """ROM offset of a stock label: <kind>_BBAAAA names carry it; other
        names are found in the disassembly and must be followed by a
        BBAAAA-named label at a fixed distance, checked against the ROM."""
        m = re.fullmatch(r"\w+?_([0-9A-F]{6})", label)
        if m:
            v = int(m.group(1), 16)
            return (v & 0x3F0000) | (v & 0xFFFF)
        if self._named is None:
            self._named = {}
            for f in self.extracted.rglob("*.asm"):
                t = f.read_text(encoding="utf-8", errors="ignore")
                for mm in re.finditer(r"^(\w+)\s*\[\s*\n\s*actor-def\s*<[^{]*\{\s*\n\s*code_([0-9A-F]{6}):", t, re.M):
                    v = int(mm.group(2), 16)
                    self._named[mm.group(1)] = ((v & 0x3F0000) | (v & 0xFFFF)) - 3
                for mm in re.finditer(r"^(\w+)\s*\{\s*\n(?:\s*;[^\n]*\n)*\s*(?:code|loc)_([0-9A-F]{6}):", t, re.M):
                    v = int(mm.group(2), 16)
                    self._named.setdefault(mm.group(1), (v & 0x3F0000) | (v & 0xFFFF))
        if label not in self._named:
            raise AsmError("unknown stock label %s" % label)
        return self._named[label]


# ---- dialogue strings ---------------------------------------------------------

# The USA text engine knows commands $C0-$D8 only; [BOR] ($D9) and [NAM]
# ($DA) belong to the Retranslation's own engine. Names are spelled out as the
# dialogue importer does, and the stock font has no ellipsis or heart tile.
STOCK_LAST_COMMAND = 0xD8
TYPOGRAPHY = str.maketrans({"…": "...", "ˮ": '"', "♥": " ", ";": ","})


def template(db, n):
    """A GaiaLabs [TPL:n] in stock terms, as the dialogue importer converts
    them (gaia_authored_dialogue): stock speakers and boxes stay; GaiaLabs'
    speaker themes ($16-$24) become their text colours and voice; its tall
    boxes become explicit box geometry. The stock table at $01:CA95 ends at
    $15, so anything else would read string bytes as a template."""
    import gaia_authored_dialogue as g
    if n in g.STOCK_SPEAKERS or n in g.STOCK_BOXES:
        return "[TPL:%02X]" % n
    if n in g.THEMES:
        if n in db.themes:
            first, second, voice = db.themes[n]
            return "[SEP:11,%04X][SEP:12,%04X]" % (first, second) + ("[SFX:%02X]" % voice if voice is not None else "") + "[PAL:4]"
        if g.THEMES[n] is not None:
            return "[TPL:%02X]" % g.THEMES[n]
        return "[PAL:0][SFX:10]"
    if n in g.AUTHORED_TALL and n not in g.TIMED_TALL:
        x, y, w, h = g.AUTHORED_TALL[n]
        return "[DLG:%X,%X][SIZ:%X,%X]" % (x, y, w, h)
    raise AsmError("template %02X has no stock equivalent" % n)


def encode_string(db, text, resolve):
    """GaiaLabs dialogue markup -> game bytes for the stock text engine."""
    def name(m):
        n = int(m.group(1), 16)
        if not db.names or n >= len(db.names):
            raise AsmError("[NAM:%s] without the name table" % m.group(1))
        return db.names[n]
    text = re.sub(r"\[NAM:([0-9A-Fa-f]+)\]", name, text).translate(TYPOGRAPHY)
    # Opening a box resets the speaker colour, so the box goes first, as in
    # the dialogue pack ("[TPL:0B][TPL:03]"); a speaker colour is put back to
    # the narration palette before the string ends, as the pack does.
    import gaia_authored_dialogue as g
    def boxed(n):
        n = int(n, 16)
        return n in g.STOCK_BOXES or (n in g.AUTHORED_TALL and n not in g.TIMED_TALL)
    text = re.sub(r"\[TPL:([0-9A-Fa-f]+)\]\[TPL:([0-9A-Fa-f]+)\]",
                  lambda m: ("[TPL:%s][TPL:%s]" % (m.group(2), m.group(1))) if boxed(m.group(2)) and not boxed(m.group(1))
                  else m.group(0), text)
    speakers = [int(n, 16) for n in re.findall(r"\[TPL:([0-9A-Fa-f]+)\]", text) if not boxed(n)]
    if speakers and text.endswith("[END]") and not text.endswith("[PAL:0][END]") and not text.endswith("[PAL:00][END]"):
        text = text[:-len("[END]")] + "[PAL:0][END]"
    text = re.sub(r"\[TPL:([0-9A-Fa-f]+)\]", lambda m: template(db, int(m.group(1), 16)), text)
    out = bytearray()
    i = 0
    while i < len(text):
        c = text[i]
        if c == "[":
            j = text.index("]", i)
            tag = text[i + 1:j]
            name, _, args = tag.partition(":")
            if name not in db.cmds:
                raise AsmError("unknown text command [%s]" % tag)
            cid, types = db.cmds[name]
            if cid > STOCK_LAST_COMMAND:
                raise AsmError("[%s] is not a command of the stock text engine" % tag)
            out.append(cid)
            vals = [a for a in args.split(",")] if args else []
            if len(vals) != len(types):
                raise AsmError("[%s] needs %d operands" % (tag, len(types)))
            for v, t in zip(vals, types):
                if t == "Byte":
                    out.append(int(v, 16))
                elif t == "Word":
                    out += struct.pack("<H", int(v, 16))
                elif t == "Address":
                    off = resolve(v.lstrip("@"))
                    bank, addr = hiroms(off)
                    out += struct.pack("<HB", addr, bank)
                else:
                    raise AsmError("text operand type %s not supported" % t)
            i = j + 1
            continue
        word = next((w for w in db.words if len(w[0]) > 2 and text.startswith(w[0], i)), None)
        if word:
            out += bytes([word[1], word[2]]); i += len(word[0]); continue
        if c not in db.glyph:
            raise AsmError("no glyph for %r" % c)
        out.append(db.glyph[c])
        i += 1
    return bytes(out)


# ---- source parsing -------------------------------------------------------------

def strip_comment(line):
    out, q = [], None
    for ch in line:
        if q:
            out.append(ch)
            if ch == q: q = None
        elif ch in "`|":
            q = ch; out.append(ch)
        elif ch == ";":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


class Block:
    def __init__(self, name, mode, kind, body):
        self.name, self.mode, self.kind, self.body = name, mode, kind, body
        self.items = []      # assembled pieces
        self.size = 0
        self.addr = None     # ROM offset once placed


def parse(text):
    """Module patch -> (constants, [Block]). mode: '!' replaces a stock label,
    '+' appends to one, '-' inserts before it, '' is new."""
    consts, blocks = {}, []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = strip_comment(lines[i])
        line = raw.strip()
        i += 1
        if not line or line.startswith("---") or line.startswith("?INCLUDE") or line.startswith("?BANK"):
            continue
        m = re.match(r"^!(\w+)\s+([0-9A-Fa-f]+)$", line)
        if m:
            consts[m.group(1)] = m.group(2); continue
        m = re.match(r"^(\w+)([!+-]?)\s*(\{|\[|`|\|)(.*)$", line)
        if not m:
            raise AsmError("cannot parse: %s" % line)
        name, mode, open_, rest = m.groups()
        if open_ in "`|":
            body = rest
            while (open_ not in body):
                body += "\n" + lines[i]; i += 1
            body = body[:body.index(open_)]
            blocks.append(Block(name, mode, "string" if open_ == "`" else "console", body))
            continue
        close = "}" if open_ == "{" else "]"
        depth, body = 1, []
        if rest.strip():
            body.append(rest)
        while depth:
            l = strip_comment(lines[i]); i += 1
            depth += l.count(open_) - l.count(close)
            if depth <= 0:
                l = l[:l.rindex(close)]
            body.append(l)
        blocks.append(Block(name, mode, "code" if open_ == "{" else "list", "\n".join(body)))
    return consts, blocks


# ---- 65816 subset ---------------------------------------------------------------

# mnemonic -> {mode: opcode}; modes: imp, imm, dp, abs, long, dpx, absx, rel, longx
OPS = {
    "LDA": {"imm": 0xA9, "dp": 0xA5, "abs": 0xAD, "long": 0xAF, "absx": 0xBD, "absy": 0xB9, "longx": 0xBF, "dpx": 0xB5},
    "STA": {"dp": 0x85, "abs": 0x8D, "long": 0x8F, "absx": 0x9D, "absy": 0x99, "longx": 0x9F, "dpx": 0x95},
    "LDX": {"imm": 0xA2, "dp": 0xA6, "abs": 0xAE},
    "LDY": {"imm": 0xA0, "dp": 0xA4, "abs": 0xAC},
    "STX": {"dp": 0x86, "abs": 0x8E}, "STY": {"dp": 0x84, "abs": 0x8C},
    "STZ": {"dp": 0x64, "abs": 0x9C, "absx": 0x9E},
    "TSB": {"dp": 0x04, "abs": 0x0C}, "TRB": {"dp": 0x14, "abs": 0x1C},
    "CMP": {"imm": 0xC9, "dp": 0xC5, "abs": 0xCD, "long": 0xCF},
    "AND": {"imm": 0x29, "dp": 0x25, "abs": 0x2D}, "ORA": {"imm": 0x09, "dp": 0x05, "abs": 0x0D},
    "EOR": {"imm": 0x49}, "ADC": {"imm": 0x69, "dp": 0x65, "abs": 0x6D}, "SBC": {"imm": 0xE9, "abs": 0xED},
    "BIT": {"imm": 0x89, "dp": 0x24, "abs": 0x2C},
    "INC": {"imp": 0x1A, "dp": 0xE6, "abs": 0xEE}, "DEC": {"imp": 0x3A, "dp": 0xC6, "abs": 0xCE},
    "BRA": {"rel": 0x80}, "BEQ": {"rel": 0xF0}, "BNE": {"rel": 0xD0}, "BCC": {"rel": 0x90},
    "BCS": {"rel": 0xB0}, "BPL": {"rel": 0x10}, "BMI": {"rel": 0x30},
    "RTL": {"imp": 0x6B}, "RTS": {"imp": 0x60}, "JML": {"long": 0x5C}, "JSL": {"long": 0x22},
    "JMP": {"abs": 0x4C}, "JSR": {"abs": 0x20},
    "SEP": {"imm8": 0xE2}, "REP": {"imm8": 0xC2},
    "TAX": {"imp": 0xAA}, "TAY": {"imp": 0xA8}, "TXA": {"imp": 0x8A}, "TYA": {"imp": 0x98},
    "PHA": {"imp": 0x48}, "PLA": {"imp": 0x68}, "PHX": {"imp": 0xDA}, "PLX": {"imp": 0xFA},
    "PHP": {"imp": 0x08}, "PLP": {"imp": 0x28}, "CLC": {"imp": 0x18}, "SEC": {"imp": 0x38},
    "XBA": {"imp": 0xEB}, "ASL": {"imp": 0x0A}, "LSR": {"imp": 0x4A}, "NOP": {"imp": 0xEA},
}


class Assembler:
    def __init__(self, db, consts, blocks, stock_override=None):
        self.db, self.consts, self.blocks = db, consts, {b.name: b for b in blocks}
        self.order = blocks
        self.local = {}           # local label -> ROM offset
        self.stock_override = stock_override or {}

    # labels -------------------------------------------------------------
    def addr(self, name):
        """ROM offset of a label: this option's blocks and local labels first,
        then the stock ROM."""
        off = 0
        m = re.match(r"^(\w+)([+-]\w+)?$", name)
        if m and m.group(2):
            name, off = m.group(1), int(m.group(2), 16)
        if name in self.local:
            return self.local[name] + off
        if name in self.blocks and self.blocks[name].addr is not None:
            return self.blocks[name].addr + off
        if name in self.blocks:
            raise AsmError("%s is not placed" % name)
        if name in self.stock_override:
            return self.stock_override[name] + off
        return self.db.stock(name) + off

    def value(self, tok, bits):
        tok = tok.strip()
        if tok.startswith("#"): tok = tok[1:]
        if tok.startswith("$&") or tok.startswith("&"):
            return self.addr(tok.lstrip("$&")) & 0xFFFF
        if tok.startswith("$*") or tok.startswith("*"):
            return hiroms(self.addr(tok.lstrip("$*")))[0]
        if tok.startswith("@"):
            b, a = hiroms(self.addr(tok[1:])); return b << 16 | a
        if tok.startswith("$"):
            tok = tok[1:]
            if tok in self.consts: tok = self.consts[tok]
            return int(tok, 16)
        if tok in self.consts: return int(self.consts[tok], 16)
        if HEX.fullmatch(tok): return int(tok, 16)
        raise AsmError("bad operand %s" % tok)

    # code ----------------------------------------------------------------
    def code_lines(self, block):
        """[(label or None, statement)]"""
        out = []
        for l in block.body.splitlines():
            l = l.strip()
            if not l: continue
            m = re.match(r"^(\w+):\s*(.*)$", l)
            if m:
                out.append((m.group(1), None))
                if m.group(2): out.append((None, m.group(2)))
            else:
                out.append((None, l))
        return out

    def size_of(self, stmt):
        return len(self.encode(stmt, None, dry=True))

    def encode(self, stmt, pc, dry=False):
        m = re.match(r"^COP\s*\[(\w+)\]\s*(?:\((.*)\))?$", stmt)
        if m:
            key = m.group(1)
            cid = int(key, 16) if HEX.fullmatch(key) and len(key) == 2 else self.db.cop_id[key]
            parts = self.db.cop[cid]
            args = [a.strip() for a in m.group(2).split(",")] if m.group(2) and m.group(2).strip() else []
            if len(args) != len(parts):
                raise AsmError("COP %s takes %d operands: %s" % (key, len(parts), stmt))
            out = bytearray([0x02, cid])
            for a, p in zip(args, parts):
                if p == "Byte" or p == "@dma-channel":
                    out.append(0 if dry else self.value(a, 8) & 0xFF)
                elif p in ("Word", "&Code", "&&Code", "&DialogString"):
                    out += struct.pack("<H", 0 if dry else self.value(a, 16) & 0xFFFF)
                elif p in ("@Code", "@DialogString", "Address", "@&sprite-set"):
                    v = 0 if dry else self.value(a if a.startswith(("@", "#", "$", "&")) else "@" + a, 24)
                    bank = v >> 16 & 0xFF
                    if p == "Address" and a.lstrip("#$").startswith("@"):
                        bank = bank & 0x3F | 0xC0   # data pointers use the $C0 mirror, code the $80 one
                    out += struct.pack("<HB", v & 0xFFFF, bank)
                else:
                    raise AsmError("COP operand type %s" % p)
            return bytes(out)
        m = re.match(r"^([A-Z]{3})\s*(.*)$", stmt)
        if not m:
            raise AsmError("cannot assemble: %s" % stmt)
        mn, op = m.group(1), m.group(2).strip()
        modes = OPS.get(mn)
        if modes is None:
            raise AsmError("instruction %s not supported" % mn)
        if not op:
            return bytes([modes["imp"]])
        if "rel" in modes:
            if dry: return bytes([modes["rel"], 0])
            t = self.addr(op.lstrip("&"))
            d = t - (pc + 2)
            if not -128 <= d < 128: raise AsmError("branch out of range: %s" % stmt)
            return bytes([modes["rel"], d & 0xFF])
        if "imm8" in modes:
            return bytes([modes["imm8"], self.value(op, 8) & 0xFF])
        if op.startswith("#"):
            body = op[1:]
            wide = not (body.startswith("$") and len(body) == 3 and HEX.fullmatch(body[1:]))
            v = 0 if dry else self.value(op, 16)
            return bytes([modes["imm"]]) + (struct.pack("<H", v & 0xFFFF) if wide else bytes([v & 0xFF]))
        idx = None
        mm = re.match(r"^(.*),\s*([XY])$", op)
        if mm: op, idx = mm.group(1).strip(), mm.group(2)
        if op.startswith("$@") or op.startswith("@"):
            mode, size = "long", 3
        elif op.startswith("$&") or op.startswith("&"):
            mode, size = "abs", 2
        else:
            digits = op.lstrip("$")
            digits = self.consts.get(digits, digits)
            size = {2: 1, 4: 2, 6: 3}.get(len(digits))
            mode = {1: "dp", 2: "abs", 3: "long"}[size]
        if idx: mode += idx.lower()
        if mode not in modes:
            raise AsmError("%s has no %s mode" % (mn, mode))
        if dry: return bytes([modes[mode]]) + bytes(size)
        tok = op.replace("$@", "@").replace("$&", "&")
        if tok.startswith("@"):
            b, a = hiroms(self.addr(tok[1:])); v = b << 16 | a
        elif tok.startswith("&"):
            v = self.addr(tok[1:]) & 0xFFFF
        else:
            v = self.value(op, size * 8)
        return bytes([modes[mode]]) + v.to_bytes(size, "little")

    # layout ---------------------------------------------------------------
    def block_size(self, b):
        if b.kind == "string":
            return len(encode_string(self.db, b.body, lambda n: 0x400000))   # size only
        if b.kind == "list":
            return 2 * len(re.findall(r"[&@]\w+", b.body))
        if b.kind == "code":
            return sum(self.size_of(s) for l, s in self.code_lines(b) if s)
        raise AsmError("%s blocks are not supported" % b.kind)

    def place(self, base, names):
        """Lay the named blocks out from ROM offset `base`; returns the end."""
        at = base
        for n in names:
            b = self.blocks[n]
            b.addr = at
            if b.kind == "code":
                pc = at
                for l, s in self.code_lines(b):
                    if l: self.local[l] = pc
                    else: pc += self.size_of(s)
            at += self.block_size(b)
        return at

    def emit(self, name):
        b = self.blocks[name]
        if b.kind == "string":
            return encode_string(self.db, b.body, self.addr)
        if b.kind == "list":
            return b"".join(struct.pack("<H", self.addr(x.lstrip("&@")) & 0xFFFF)
                            for x in re.findall(r"[&@]\w+", b.body))
        out = bytearray(); pc = b.addr
        for l, s in self.code_lines(b):
            if s:
                enc = self.encode(s, pc)
                out += enc; pc += len(enc)
        return bytes(out)
