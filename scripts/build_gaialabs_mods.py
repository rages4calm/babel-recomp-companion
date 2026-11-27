"""Build i18n/gaialabs-mods.bin: GaiaLabs Retranslation optional modules as
in-place data patches for the stock USA ROM.

GaiaLabs ships its options as modules for its own ROM rebuild (assembly
patches plus extracted art). The Companion runs the stock ROM with native
code generated from it, so code patches cannot be taken over; data the game
reads (graphics, palettes, tilemaps, parallax tables) can. This turns each
supported module into records the game loads itself:

  W  write bytes at a ROM offset; the stock bytes there must hash to the
     recorded SHA-256 or the runtime refuses the whole feature;
  T  a parallax table that is longer than its stock slot: the runtime places
     it in free space in bank $01 and repoints the game's own table entry;
  S  art or a palette the console may already hold from a save state made
     with the other setting, for the runtime to swap in place.

Art is recompressed with the game's QuintetLZ (minimum-bit parse) and goes
back into the stock span. The one asset that is still larger is placed in
the padding at the end of bank $06 and its scene_meta pointers are moved.

The output holds only module data (GPL-3.0, GaiaLabs) plus offsets and
hashes; no stock ROM bytes. Usage:

  python scripts/build_gaialabs_mods.py <retranslation checkout> <commit>
      <baserom checkout> <USA ROM> <output .bin>
"""
import hashlib, json, re, struct, subprocess, sys
from pathlib import Path

MAGIC = b"IOGGLM01"

# feature id -> (module, [asset files])
FEATURES = {
    "jp_edward":   ("jp-edward-mountains", ["gfx_castle.bin", "map_ec0A_effect.map", "pal_castle.pal", "set_castle_effect.set"]),
    "jp_itory":    ("jp-itory-mountains", ["gfx_itory_effect.bin", "map_it18_effect.map", "map_itory_effect.map",
                                           "map_itory_interior_effect.map", "pal_itory.pal", "pal_itory_interior.pal",
                                           "set_itory_effect.set"]),
    "jp_wall":     ("jp-wall-dunes", ["gfx_greatwall.bin", "map_greatwall_effect.map", "pal_greatwall.pal", "set_greatwall_effect.set"]),
    "red_fountain": ("red-fountain", []),
    "jp_church":   ("jp-church-cross", ["gfx_southcape_effect.bin"]),
    "jp_mines":    ("jp-mines", ["pal_mine.pal"]),
    "jp_prologue": ("jp-prologue-palettes", ["pal_prologue_legends.pal", "pal_prologue_missing.pal"]),
    "jp_viper":    ("jp-viper", ["gfx_viper.bin"]),
}
PARALLAX_TABLE = 0x1CC00          # 16-bit pointers into bank $01, one per index
RELOCATE_SPACE = (0x06DCD8, 0x070000)   # $FF padding at the end of bank $06


# ---- QuintetLZ (after gaia-core src/compression/QuintetLZ.ts, GaiaLabs) ----

def expand(d, pos):
    n = d[pos] | d[pos + 1] << 8
    dic = bytearray([0x20]) * 256; dp = 0xEF; out = bytearray(); bit = (pos + 2) * 8
    def rb(k):
        nonlocal bit
        v = 0
        for _ in range(k):
            v = v << 1 | (d[bit >> 3] >> (7 - (bit & 7)) & 1); bit += 1
        return v
    while len(out) < n:
        if rb(1):
            v = rb(8); out.append(v); dic[dp] = v; dp = (dp + 1) & 255
        else:
            idx = rb(8); ln = rb(4) + 2
            for _ in range(ln):
                b = dic[idx]; idx = (idx + 1) & 255
                if len(out) < n: out.append(b)
                dic[dp] = b; dp = (dp + 1) & 255
    return bytes(out), (bit + 7) // 8 - pos


def compact(src):
    """Minimum-bit parse. The dictionary after k output bytes depends only on
    those bytes, so the matches available at every position are fixed."""
    n = len(src)
    def longest(i):
        dic = bytearray([0x20]) * 256
        for k in range(max(0, i - 256), i): dic[(0xEF + k) & 255] = src[k]
        off = (0xEF + i) & 255; maxlen = min(n - i, 17); best = (0, 0)
        if maxlen < 2: return best
        for start in range(256):
            size = 0; ci = start; si = i; end = False
            while size < maxlen:
                if end:
                    if src[si] != src[i + size]: break
                    si += 1
                elif dic[ci] != src[si]: break
                else:
                    si += 1; ci = (ci + 1) & 255
                    if ci == off: si = i; end = True
                size += 1
            if size > best[0]: best = (size, start)
            if size == maxlen: break
        return best
    INF = 1 << 60; cost = [INF] * (n + 1); how = [None] * (n + 1); cost[0] = 0
    for i in range(n):
        if cost[i] + 9 < cost[i + 1]: cost[i + 1] = cost[i] + 9; how[i + 1] = (i, None)
        length, start = longest(i)
        for L in range(2, length + 1):
            if cost[i] + 13 < cost[i + L]: cost[i + L] = cost[i] + 13; how[i + L] = (i, start)
    steps = []; j = n
    while j: i, st = how[j]; steps.append((i, j - i, st)); j = i
    bits = []
    def wb(v, k):
        for s in range(k - 1, -1, -1): bits.append(v >> s & 1)
    for i, L, st in reversed(steps):
        if st is None: wb(1, 1); wb(src[i], 8)
        else: wb(0, 1); wb(st, 8); wb(L - 2, 4)
    while len(bits) % 8: bits.append(0)
    out = bytearray([n & 255, n >> 8])
    for k in range(0, len(bits), 8):
        v = 0
        for b in bits[k:k + 8]: v = v << 1 | b
        out.append(v)
    out = bytes(out)
    assert expand(out, 0)[0] == src
    return out


# ---- inputs ----

class Sources:
    def __init__(self, retranslation, commit, baserom, rom):
        self.re, self.commit, self.rom = retranslation, commit, rom
        self.baserom = baserom
        head = subprocess.run(["git", "-C", retranslation, "rev-parse", commit + "^{commit}"],
                              capture_output=True, text=True, check=True).stdout.strip()
        if head != commit: raise SystemExit("commit %s is not a full commit id" % commit)
        files = json.load(open(Path(baserom) / "db-us" / "files.json"))
        self.types = json.load(open(Path(baserom) / "db-us" / "fileTypes.json"))
        self.files = {}
        def walk(o):
            for k, v in o.items():
                if isinstance(v, dict) and "start" in v: self.files[k] = v
                elif isinstance(v, dict): walk(v)
        walk(files)

    def module(self, path):
        return subprocess.run(["git", "-C", self.re, "show", "%s:modules/%s" % (self.commit, path)],
                              capture_output=True, check=True).stdout

    def type_of(self, name):
        ext = name.split(".", 1)[1]
        return next(t for t in self.types.values() if t["extension"] == ext)


class Pack:
    def __init__(self, rom):
        self.rom, self.records = rom, []
    def write(self, feature, offset, data):
        stock = self.rom[offset:offset + len(data)]
        self.records.append((b"W", feature, offset, data, hashlib.sha256(stock).digest()))
    def table(self, feature, index, data):
        # the stock table this replaces, so the runtime can free its slot
        at = PARALLAX_TABLE + 2 * index
        self.records.append((b"T", feature, at, data, hashlib.sha256(self.rom[at:at + 2]).digest()))
    def swap(self, feature, form, offset, data):
        """Art already in the console's memory (a save state made with the
        other setting): the runtime finds the stock version in VRAM, WRAM or
        CGRAM and swaps it. form b"z": QuintetLZ stream (the stock one is
        expanded from the ROM at offset); b"p": a raw palette span."""
        self.records.append((b"S", feature, offset, form + data, hashlib.sha256(b"").digest()))
    def save(self, path, source):
        out = bytearray(MAGIC)
        src = source.encode()
        out += struct.pack("<H", len(src)) + src + struct.pack("<I", len(self.records))
        for kind, feature, offset, data, digest in self.records:
            f = feature.encode()
            out += kind + struct.pack("<B", len(f)) + f + struct.pack("<II", offset, len(data)) + digest + data
        Path(path).write_bytes(out)


def asset(src, pack, feature, module, name, relocated):
    rom = src.rom
    base = name.split(".")[0]; s = src.files[base]; t = src.type_of(name)
    data = src.module("%s/%s" % (module, name))
    start, end = s["start"], s["end"]
    if t["type"] == "Palette":
        span = end - start
        if any(data[span:]): raise SystemExit("%s uses more colours than the stock palette" % name)
        pack.write(feature, start, data[:span]); pack.swap(feature, b"p", start, data[:span]); return
    if not t.get("compressed"): raise SystemExit("unsupported asset type %s" % name)
    header = t.get("header", 0)
    if header:
        if data[:header] != rom[start:start + header]:
            raise SystemExit("%s changes its tilemap size" % name)
        start += header; data = data[header:]
    if rom[start] | rom[start + 1] << 8 == 0:     # stored raw behind a zero header
        if len(data) + 2 != end - start: raise SystemExit("%s size differs" % name)
        pack.write(feature, start, b"\0\0" + data); return
    stock, used = expand(rom, start)
    if len(stock) != len(data): raise SystemExit("%s: %d bytes, stock %d" % (name, len(data), len(stock)))
    packed = compact(data)
    if data != stock: pack.swap(feature, b"z", start, packed)
    if len(packed) <= end - start:
        pack.write(feature, start, packed); return
    # Too large for its span: place it in bank $06's padding, move the pointers.
    lo, hi = relocated
    if lo + len(packed) > hi: raise SystemExit("no room for %s" % name)
    target = s["start"]          # scene_meta points at the header
    blob = rom[target:start] + packed
    pointer = bytes([target & 255, target >> 8 & 255, 0xC0 | target >> 16])
    sites = [m.start() for m in re.finditer(re.escape(pointer), rom)]
    if not sites or any(not 0x0D8000 <= p < 0x0E0000 for p in sites):
        raise SystemExit("%s: unexpected references %s" % (name, sites))
    pack.write(feature, lo, blob)
    moved = bytes([lo & 255, lo >> 8 & 255, 0xC0 | lo >> 16])
    for p in sites: pack.write(feature, p, moved)
    relocated[0] = lo + len(blob)


def spritemap(src, pack, feature, module, name, relocated):
    """A spritemap (sprite layout, expanded into WRAM). The JP Viper's is 52
    bytes shorter than stock: it is padded with the stock tail so the scene's
    size word and every WRAM address after it stay as they are, then moved to
    bank $06's padding (its stream is longer than the stock span)."""
    rom = src.rom
    s = src.files[name.split(".")[0]]
    start, end = s["start"], s["end"]
    stock, _ = expand(rom, start)
    data = src.module("%s/%s" % (module, name))
    if len(data) > len(stock): raise SystemExit("%s is longer than stock" % name)
    data = data + stock[len(data):]
    packed = compact(data)
    pack.swap(feature, b"z", start, packed)
    if len(packed) <= end - start:
        pack.write(feature, start, packed); return
    lo, hi = relocated
    if lo + len(packed) > hi or lo & 0xFFFF < 0x8000: raise SystemExit("no room for %s" % name)
    sites = []
    for bank in (0x80, 0xC0):
        pointer = bytes([start & 255, start >> 8 & 255, bank | start >> 16])
        sites += [(m.start(), bank) for m in re.finditer(re.escape(pointer), rom)
                  if 0x0D8000 <= m.start() < 0x0E0000]
    if not sites: raise SystemExit("%s: no scene_meta references" % name)
    for p, bank in sites:
        if rom[p - 4] != 0x10 or rom[p - 1] != 0: raise SystemExit("%s: unexpected reference at %x" % (name, p))
    pack.write(feature, lo, packed)
    for p, bank in sites:
        pack.write(feature, p, bytes([lo & 255, lo >> 8 & 255, bank | lo >> 16]))
    relocated[0] = lo + len(packed)


def crystal_ring(src, pack):
    """The inventory's crystal ring: new art in the (uncompressed) inventory
    sprite sheet and its sprite part moved to palette 5, which the stock
    inventory palette already holds (the module's own exprite palette is for
    GaiaLabs' equipped-item icon, which this port does not have)."""
    module = "crystal-ring-palette"
    sheet = src.files["gfx_inventory_sprites"]["start"]
    if src.rom[sheet:sheet + 2] != b"\0\0": raise SystemExit("inventory sprites are not stored raw")
    data = src.module(module + "/gfx_inventory_sprites.bin")
    stock = src.rom[sheet + 2:sheet + 2 + len(data)]
    diff = [i for i in range(len(data)) if data[i] != stock[i]]
    lo, hi = diff[0] & ~31, (diff[-1] | 31) + 1
    pack.write("crystal_ring", sheet + 2 + lo, data[lo:hi])
    patch = src.module(module + "/CrystalRingPalette.patch.asm").decode()
    part = re.search(r"sprite_part\s*<\s*#01,\s*#00,\s*#00,\s*#00,\s*#00,\s*#\$([0-9A-Fa-f]{4})\s*>", patch)
    group = 0x10898C
    if src.rom[group + 13] != 1 or struct.unpack_from("<H", src.rom, group + 18)[0] != 0x0760 or not part:
        raise SystemExit("crystal ring: sprite group does not match the stock layout")
    pack.write("crystal_ring", group + 18, struct.pack("<H", int(part.group(1), 16)))


def no_shira(src, pack):
    """Shira's dream (scene $2A) without the closing spotlight. Her talk
    handler ($05:9484) sets flag $0E, which the dream's zoom controller waits
    on to close in, then asks the comet question. The module drops the flag.
    The handler is reached through the inline operand of SetInteractHandler,
    which the game's COP handler reads as data, so a copy without the flag
    goes into bank $05's padding (an address with no native body runs in the
    interpreter) and the operand points there. The string is printed from its
    start, not +2 as the module does, so the dialogue pack's text (keyed by
    the string's address) still applies; it opens with the same pause."""
    patch = src.module("no-shira-spotlight/NoShiraSpotlight.patch.asm").decode()
    if "SetFlagByte" in patch or not re.search(r"COP \[BF\] \( &dialogstring_0594B8\+2 \)", patch) or \
            not re.search(r"COP \[BE\] \( #02, #01, &code_list_059491 \)", patch):
        raise SystemExit("no-shira-spotlight: the module is not the expected change")
    stock = bytes.fromhex("02cc0e02bfb89402be02019194")      # SetFlagByte #0E; print; options
    handler, operand, at = 0x059484, 0x05947D, 0x05FFE4
    if src.rom[handler:handler + len(stock)] != stock or src.rom[operand - 2:operand + 2] != b"\x02\xc0\x84\x94":
        raise SystemExit("no-shira-spotlight: stock handler differs")
    code = stock[3:]                                            # print + options, without the flag
    if any(b != 0xFF for b in src.rom[at - 16:at + len(code) + 16]):
        raise SystemExit("no-shira-spotlight: bank $05 padding is not free")
    pack.write("no_shira", at, code)
    pack.write("no_shira", operand, struct.pack("<H", at & 0xFFFF))


# ---- script options: GaiaLabs code rebuilt in free space ----------------------

# Free $FF padding per bank, split between options so any combination can be
# on at once (bank $05: freejia_shortcut, then no_shira's handler at $05:FFE4).
SCRIPT_SPACE = {
    "thankful_flower": [(0x09F700, 0x09F900)],
    "south_cape_return": [(0x04FB40, 0x04FFF0)],
    "blue_journal": [(0x07E930, 0x07EF00), (0x03F210, 0x03F600)],
    "freejia_shortcut": [(0x05FED4, 0x05FFDC)],
    "angkor_shortcut": [(0x08FD20, 0x08FFF0)],
}
SCRIPT_MODULES = {
    "thankful_flower": "thankful-flower",
    "south_cape_return": "south-cape-return",
    "blue_journal": "blue-journal",
    "freejia_shortcut": "freejia-shortcut",
    "angkor_shortcut": "angkor-shortcut",
}


# Changes to a module's text before assembly, each matched exactly once:
#   freejia_shortcut: Sam's mine room ($47) has no world-map place name, so the
#     world-map trip GaiaLabs stages (COP $65) hung on the travel screen; Sam
#     takes Will straight to Freejia with the module's own scene change.
SCRIPT_FIXUPS = {
    "freejia_shortcut": [("    COP [65] ( #$0334, #$0334, #00, #0B )\n", "")],
}
# Stock routines rebuilt with an option because native code reaches the
# replaced routine by falling through, not through data:
#   angkor_shortcut: code_089AD4 (the Gorgon Flower vision, reached through
#     BranchOnFlagByte's operand) falls through into code_089B1F, the routine
#     GaiaLabs replaces; so is it, cut where code_089B1F begins and followed by
#     the new code_089B1F, and the two jewel/herb branches that jump back into
#     it (reached through BranchIfHasItem's operands) come along.
SCRIPT_PULL = {
    "angkor_shortcut": ("awBF_spirit_guide.asm", [("code_089AD4", "code_089B1F:"), ("code_089B31", None), ("code_089B54", None)]),
}


def pull_stock(src, feature):
    """Stock routines from the disassembly, as '!' blocks of module text."""
    fname, wanted = SCRIPT_PULL[feature]
    path = next((Path(src.baserom) / "extracted").rglob(fname))
    text = path.read_text(encoding="utf-8")
    consts = "".join("!%s %s\n" % m for m in re.findall(r"^!(\w+)\s+([0-9A-Fa-f]+)\s*$", text, re.M))
    out = []
    for name, cut in wanted:
        m = re.search(r"^%s\s*\{(.*?)^\}" % name, text, re.M | re.S)
        if not m: raise SystemExit("%s: %s not in %s" % (feature, name, fname))
        body = m.group(1)
        if cut:
            if cut not in body: raise SystemExit("%s: %s has no %s" % (feature, name, cut))
            body = body[:body.index(cut)]
        out.append("%s! {%s}\n" % (name, body))
    return consts, out


def learn_stock(src, db, consts, block_text, name):
    """Assemble a copied stock routine at its own address. Labels the
    disassembly gives no address for (`file.entry`) are read from the ROM's
    bytes at their operand; every other byte must equal the ROM, so the copy
    is checked as well as resolved. Returns {label: ROM offset}."""
    import gaialabs_asm as ga
    unknown = []

    class Learn(ga.Assembler):
        def addr(self, label):
            try:
                return super().addr(label)
            except ga.AsmError:
                if label not in unknown: unknown.append(label)
                return 0x400000            # the same placeholder the copy is built with

    _, blocks = ga.parse(block_text)
    asm = Learn(db, consts, blocks)
    at = db.stock(name)
    asm.place(at, [name])
    got = asm.emit(name)
    rom = src.rom[at:at + len(got)]
    # The baserom disassembly is not the stock game byte for byte: its
    # transforms rewrite some constants for GaiaLabs' base (LDA #$FFF0 reads
    # #$FFFC there), and some labels have no address. Every byte that differs
    # is taken from the ROM in the copy; instruction lengths must agree (a
    # handful of differing bytes, never a different layout).
    patch = {k: rom[k] for k in range(len(got)) if got[k] != rom[k]}
    if len(patch) > 16:
        raise SystemExit("%s: %d bytes differ from the ROM; not a faithful copy" % (name, len(patch)))
    return {label: 0x400000 for label in unknown}, patch


def stock_refs(src, db, label):
    """Every place in the stock game that reaches `label` through data: COP
    operands (`COP [Name] ( ... &label ... )`) and pointer lists. Returns ROM
    offsets of the 16-bit words to rewrite, found in the ROM and counted
    against the disassembly so nothing is missed or guessed."""
    import gaialabs_asm as ga
    target = db.stock(label)
    word = struct.pack("<H", target & 0xFFFF)
    want, sites = 0, []
    ex = Path(src.baserom) / "extracted"
    for f in ex.rglob("*.asm"):
        t = f.read_text(encoding="utf-8", errors="ignore")
        if ("&" + label) not in t and ("@" + label) not in t:
            continue
        for m in re.finditer(r"^\s*(JSR|JSL|JMP|JML|BRA|BRL)\b[^\n]*[&@$]%s\b" % re.escape(label), t, re.M):
            raise SystemExit("%s is reached by an instruction (%s): its new body would not run" % (label, f.name))
        for m in re.finditer(r"^\s*COP \[(\w+)\] \((.*)\)\s*$", t, re.M):
            args = [a.strip() for a in m.group(2).split(",")]
            if "&" + label not in args:
                continue
            want += 1
            cid = db.cop_id[m.group(1)]; parts = db.cop[cid]
            k = args.index("&" + label)
            size = {"Byte": 1, "@dma-channel": 1, "Word": 2, "&Code": 2, "&&Code": 2, "&DialogString": 2}
            off = 2 + sum(size.get(p, 3) for p in parts[:k])
            bank = target & 0xFF0000
            for p in range(bank, bank + 0x10000 - off - 2):
                if src.rom[p] == 0x02 and src.rom[p + 1] == cid and src.rom[p + off:p + off + 2] == word:
                    if p + off not in sites: sites.append(p + off)
        for m in re.finditer(r"^(\w+)\s*\[(.*?)^\]", t, re.M | re.S):
            body = [l.split(";")[0].strip() for l in m.group(2).splitlines()]
            if not all(re.fullmatch(r"[&@]\w+", l) for l in body if l):
                continue   # not a pointer list (an actor definition, a table)
            entries = re.findall(r"[&@](\w+)", m.group(2))
            for i, e in enumerate(entries):
                if e == label:
                    want += 1
                    at = db.stock(m.group(1)) + 2 * i
                    if src.rom[at:at + 2] != word: raise SystemExit("%s: list %s does not hold it" % (label, m.group(1)))
                    sites.append(at)
    if len(sites) != want or not want:
        raise SystemExit("%s: %d references in the disassembly, %d found in the ROM" % (label, want, len(sites)))
    return sites


def gaia_names(src):
    """GaiaLabs' English name table ([NAM:n]), read as the dialogue importer
    reads it."""
    import import_gaialabs_dialogue as imp
    return imp.load_names(src.re)


def gaia_themes(src):
    """GaiaLabs' speaker themes ($16-$24): text colours and voice."""
    import import_gaialabs_dialogue as imp, gaia_authored_dialogue as g
    return g.load_themes(imp.read_source(src.re, "modules/base/asm/dialog_template_table.asm"))


def script_option(src, pack, feature):
    """A GaiaLabs module whose changes are script code and dialogue: its
    blocks are assembled into the option's free space (one bank per group),
    and every stock pointer to a replaced routine or string is moved there."""
    import gaialabs_asm as ga
    db = ga.Db(src.baserom, src.rom, gaia_names(src), gaia_themes(src))
    text = ""
    module = SCRIPT_MODULES[feature]
    for name in subprocess.run(["git", "-C", src.re, "ls-tree", "--name-only", src.commit, "modules/%s/" % module],
                               capture_output=True, text=True, check=True).stdout.split():
        if name.endswith(".asm"):
            text += src.module(name[len("modules/"):]).decode("utf-8") + "\n"
    text = text.replace("\r\n", "\n")
    for old, new in SCRIPT_FIXUPS.get(feature, []):
        if text.count(old) != 1: raise SystemExit("%s: fixup %r does not match once" % (feature, old))
        text = text.replace(old, new)
    follows, learned, rom_bytes = {}, {}, {}
    if feature in SCRIPT_PULL:
        stock_consts, pulled = pull_stock(src, feature)
        sc, _ = ga.parse(stock_consts)
        for (name, cut), block in zip(SCRIPT_PULL[feature][1], pulled):
            # the copy as it stands in the stock ROM (uncut), checked byte for byte
            full = re.search(r"^%s\s*\{(.*?)^\}" % name, next((Path(src.baserom) / "extracted").rglob(
                SCRIPT_PULL[feature][0])).read_text(encoding="utf-8"), re.M | re.S).group(1)
            lab, patch = learn_stock(src, db, sc, "%s {%s}\n" % (name, full), name)
            learned.update(lab)
            rom_bytes[name] = patch
        text = stock_consts + "".join(pulled) + text
        follows = {name: cut.rstrip(":") for name, cut in SCRIPT_PULL[feature][1] if cut}
    consts, blocks = ga.parse(text)
    blocks = [b for b in blocks if not (b.mode == "+" and not b.body.strip())]
    # a routine cut where it falls through is placed right before the block it
    # falls into, so the fall-through lands on the new code
    for name, nxt in follows.items():
        order = [b.name for b in blocks]
        if nxt not in order: raise SystemExit("%s: %s falls into %s, which the module lacks" % (feature, name, nxt))
        moved = blocks.pop(order.index(nxt))
        blocks.insert([b.name for b in blocks].index(name) + 1, moved)
    # A replaced stock string is used only by this module's own new code: stock
    # references keep the stock address, where the dialogue pack puts its text
    # (moving them would bypass it). A replaced string nothing new uses is dropped.
    code = "\n".join(b.body for b in blocks if b.kind != "string")
    blocks = [b for b in blocks if not (b.kind == "string" and b.mode == "!"
              and not re.search(r"[&@]%s\b" % re.escape(b.name), code))]
    for b in blocks:
        if b.kind == "string" and b.mode == "!":
            b.mode = ""          # placed as a new string; stock references stay
    for b in blocks:
        if b.mode in "+-" and b.mode:
            raise SystemExit("%s: %s%s is not supported" % (feature, b.name, b.mode))
    asm = ga.Assembler(db, consts, blocks, stock_override=learned)
    # group blocks by the bank they must live in: a replaced routine or
    # string in the bank of the stock code that reaches it; new blocks with
    # the replaced routine that uses them
    spaces = {r[0] >> 16: list(r) for r in SCRIPT_SPACE[feature]}
    groups = {}
    for b in blocks:
        bank = (db.stock(b.name) >> 16) if b.mode == "!" else None
        groups.setdefault(bank, []).append(b.name)
    if None in groups:
        users = {db.stock(b.name) >> 16 for b in blocks if b.mode == "!" and b.kind == "code"}
        if len(users) != 1:
            raise SystemExit("%s: new blocks used from banks %s" % (feature, sorted(users)))
        groups[users.pop()] += groups.pop(None)
    for bank, names in groups.items():
        if bank not in spaces: raise SystemExit("%s: no free space reserved in bank $%02X" % (feature, bank))
        lo, hi = spaces[bank]
        end = asm.place(lo, names)
        if end > hi: raise SystemExit("%s: %d bytes do not fit bank $%02X's %d" % (feature, end - lo, bank, hi - lo))
    for bank, names in groups.items():
        lo = spaces[bank][0]
        parts = []
        for n in names:
            piece = bytearray(asm.emit(n))
            for k, v in rom_bytes.get(n, {}).items():
                if k < len(piece): piece[k] = v       # the ROM's own byte (see learn_stock)
            parts.append(bytes(piece))
        blob = b"".join(parts)
        if any(x != 0xFF for x in src.rom[lo:lo + len(blob)]): raise SystemExit("%s: space not free" % feature)
        pack.write(feature, lo, blob)
    for b in blocks:
        if b.mode == "!":
            new = struct.pack("<H", asm.addr(b.name) & 0xFFFF)
            for site in stock_refs(src, db, b.name):
                pack.write(feature, site, new)
    return asm


SLAVE_SPACE = (0x07F600, 0x07FF00)
SCENE_ACTORS = 0x0C8000            # 256 word pointers into bank $0C, one per scene


def scene_record(rom, scene, index):
    """ROM offset of record `index` in a scene's actor list: 7-byte spawns,
    9-byte enemies (a nonzero byte +6), ended by $FF."""
    p = 0x0C0000 | struct.unpack_from("<H", rom, SCENE_ACTORS + 2 * scene)[0]
    for i in range(index):
        if rom[p] == 0xFF: raise SystemExit("scene $%02X has no record %d" % (scene, index))
        p += 9 if rom[p + 6] else 7
    return p


def slave_return(src, pack):
    """Freejia slave return (GaiaLabs freejia-slave-return). If you do not
    give the runaway laborer away, the stock game never pays the Red Jewel
    the slaver does when you do (flag $5A); GaiaLabs has the laborer pay it
    later instead (flag $107), so either way there are 50. The harborer's
    door opens, the laborer and the harborer get new lines, and the slavers
    leave, as in the module.

    Bank $05, where these actors live, has no free space left, so their new
    code is in bank $07: each actor's record in its room list (a 24-bit
    pointer, data) points at a copy of its header followed by the module's
    checks; a talk handler (stored as 16 bits and run in the actor's current
    bank) sits in the same bank as the code that sets it; the stock paths are
    reached with long jumps. The module's text is used as written (its one
    [JMP] into another string is expanded)."""
    import gaialabs_asm as ga
    db = ga.Db(src.baserom, src.rom, gaia_names(src), gaia_themes(src))
    module = src.module("freejia-slave-return/FreejiaSlaveReturn.patch.asm").decode("utf-8").replace("\r\n", "\n")
    strings = dict(re.findall(r"^(freejia_\w+_str)\s+`([^`]*)`", module, re.M))
    need = ["freejia_slave_return_str", "freejia_slave_recognize_str", "freejia_slave_inv_full_str",
            "freejia_slave_farewell_str", "freejia_harborer_return_str", "freejia_harborer_escaped_str",
            "freejia_harborer_rumor_str"]
    if any(n not in strings for n in need): raise SystemExit("freejia-slave-return: strings changed")
    # [JMP:freejia_slave_recognize_str+M] continues at the [::] marker
    rec = strings["freejia_slave_recognize_str"]
    if "[::]" not in rec or not strings["freejia_slave_return_str"].endswith("[JMP:freejia_slave_recognize_str+M]"):
        raise SystemExit("freejia-slave-return: [JMP] layout changed")
    tail = rec[rec.index("[::]") + 4:]
    strings["freejia_slave_return_str"] = strings["freejia_slave_return_str"].replace(
        "[JMP:freejia_slave_recognize_str+M]", "[TPL:A]" + tail)
    strings["freejia_slave_recognize_str"] = rec.replace("[::]", "")
    # the module's flags and checks (constants as the module names them)
    for name, value in (("slave_captured_flag", "5A"), ("return_flag", "8D"), ("dao_return_flag", "B6"),
                        ("slave_reward_flag", "0107")):
        if not re.search(r"^!%s\s+%s\s*$" % (name, value), module, re.M):
            raise SystemExit("freejia-slave-return: %s changed" % name)
    # where things are in the stock ROM
    door_rec, sym_rec = scene_record(src.rom, 0x32, 0x0A), scene_record(src.rom, 0x3A, 0x03)
    harb_rec = scene_record(src.rom, 0x3A, 0x04)
    sl1_rec, sl2_rec = scene_record(src.rom, 0x32, 0x22), scene_record(src.rom, 0x32, 0x23)
    def ptr(r): return ((src.rom[r + 5] & 0x3F) << 16) | struct.unpack_from("<H", src.rom, r + 3)[0]
    expect = {door_rec: 0x05CFBC, sym_rec: 0x05C30E, harb_rec: 0x05BC56, sl1_rec: 0x05B816, sl2_rec: 0x05B852}
    for r, a in expect.items():
        if ptr(r) != a: raise SystemExit("freejia-slave-return: record at %x points at %x, not %x" % (r, ptr(r), a))
    # town_door's address, from a stock record the disassembly names
    # (scene $01, record 3: actor-spawn < #20, #0E, #00, @town_door >)
    td_rec = scene_record(src.rom, 0x01, 0x03)
    town_door = ptr(td_rec)
    if src.rom[town_door:town_door + 3] != bytes([0x01, 0x00, 0x10]):
        raise SystemExit("freejia-slave-return: town_door header not at %x" % town_door)
    code = r"""
sr_door {
    COP [D0] ( #5A, #01, &sr_door_open )
    COP [D0] ( #B6, #01, &sr_door_open )
    COP [D1] ( #$0107, #01, &sr_door_open )
    JML @code_05CFBF
  sr_door_open:
    LDA #&town_door+3
    STA $00
    LDA #*town_door
    STA $02
    JML @town_door+3
}
sr_slave {
    COP [D0] ( #5A, #01, &sr_die )
    COP [D1] ( #$0107, #01, &sr_die )
    LDA #$0200
    TSB $12
    COP [0B]
    COP [C0] ( &sr_slave_talk )
    COP [C1]
    RTL
}
sr_die {
    COP [E0]
}
sr_slave_talk {
    COP [D1] ( #$0107, #01, &sr_slave_farewell )
    COP [D0] ( #8D, #01, &sr_slave_return )
    JML @code_05C327
  sr_slave_return:
    COP [D0] ( #59, #01, &sr_slave_recognize )
    COP [BF] ( &freejia_slave_return_str )
    BRA sr_slave_give
  sr_slave_recognize:
    COP [BF] ( &freejia_slave_recognize_str )
  sr_slave_give:
    COP [D4] ( #01, &sr_slave_full )
    COP [CD] ( #$0107 )
    RTL
  sr_slave_full:
    COP [BF] ( &freejia_slave_inv_full_str )
    RTL
  sr_slave_farewell:
    COP [BF] ( &freejia_slave_farewell_str )
    RTL
}
sr_harborer {
    COP [D0] ( #B6, #01, &sr_harborer_stay )
    COP [D0] ( #5A, #01, &sr_die )
  sr_harborer_stay:
    COP [C0] ( &sr_harborer_talk )
    COP [0B]
    COP [C1]
    RTL
}
sr_harborer_talk {
    COP [D0] ( #5A, #01, &sr_harborer_escaped )
    COP [D0] ( #B6, #01, &sr_harborer_rumor )
    COP [D1] ( #$0107, #00, &sr_harborer_default )
    COP [D0] ( #8D, #01, &sr_harborer_return )
  sr_harborer_default:
    JML @code_05BC6A
  sr_harborer_return:
    COP [BF] ( &freejia_harborer_return_str )
    RTL
  sr_harborer_escaped:
    COP [BF] ( &freejia_harborer_escaped_str )
    RTL
  sr_harborer_rumor:
    COP [BF] ( &freejia_harborer_rumor_str )
    RTL
}
sr_slaver1 {
    COP [D0] ( #5A, #01, &sr_die )
    COP [D0] ( #B6, #01, &sr_die )
    COP [D1] ( #$0107, #01, &sr_die )
    COP [0B]
    COP [C0] ( &code_05B83B )
    JML @code_05B825
}
sr_slaver2 {
    COP [D0] ( #5A, #01, &sr_die )
    COP [D0] ( #B6, #01, &sr_die )
    COP [D1] ( #$0107, #01, &sr_die )
    COP [0B]
    COP [C0] ( &code_05B880 )
    COP [DA] ( #07 )
    JML @code_05B864
}
"""
    code += "".join("%s `%s`\n" % (n, strings[n]) for n in need)
    consts, blocks = ga.parse(code)
    asm = ga.Assembler(db, consts, blocks, stock_override={"town_door": town_door})
    # each actor: a copy of its stock header, then its code
    order = [("sr_door", 0x05CFBC), ("sr_slave", 0x05C30E), ("sr_harborer", 0x05BC56),
             ("sr_slaver1", 0x05B816), ("sr_slaver2", 0x05B852)]
    lo, hi = SLAVE_SPACE
    at, heads = lo, {}
    for name, stock in order:
        heads[name] = at
        at = asm.place(at + 3, [name])
    rest = [b.name for b in blocks if b.name not in dict(order)]
    end = asm.place(at, rest)
    if end > hi: raise SystemExit("freejia-slave-return: does not fit")
    blob = bytearray()
    for name, stock in order:
        blob += src.rom[stock:stock + 3] + asm.emit(name)
    blob += b"".join(asm.emit(n) for n in rest)
    if len(blob) != end - lo or any(x != 0xFF for x in src.rom[lo:end]):
        raise SystemExit("freejia-slave-return: layout or space check failed")
    pack.write("slave_return", lo, bytes(blob))
    for (name, stock), rec in zip(order, (door_rec, sym_rec, harb_rec, sl1_rec, sl2_rec)):
        bank, addr = ga.hiroms(heads[name])
        pack.write("slave_return", rec + 3, struct.pack("<HB", addr, bank))


KRESS_SPACE = (0x07EF00, 0x07F600)
KRESS_LIST = 0x0CCA02          # scene $A9's actor list (Mountain Temple, top)


SPIRIT_TILES = (0x45, 0x5B)       # tiles of npc_props animation $04 (all four frames)
FX_SOURCE = "misc_fx_1CD580"      # uploaded to tile $40 in non-combat scenes
NAME_TABLE_1 = 0x5000             # VRAM word address of OBJ tile $100 (OBSEL = $02)
CACHE_SLOT_BG_D = 0x0675          # scene-art source cache for VRAM page $50 (mode 1)

# exact edits to the module text, each matched once
UPLOAD = ("    COP [4F] ( @%s+%X, #$%04X, #$%04X )\n"
          "    STZ $%04X\n") % (FX_SOURCE, (SPIRIT_TILES[0] - 0x40) * 32, NAME_TABLE_1 + SPIRIT_TILES[0] * 16,
                               (SPIRIT_TILES[1] - SPIRIT_TILES[0]) * 32, CACHE_SLOT_BG_D + 1)
KRESS_FIXUPS = [
    # name table 1 for every sub-sprite, before the first frame is staged
    ("    COP [88] ( @spriteset_npc_props )\n",
     "    COP [88] ( @spriteset_npc_props )\n    LDA #$0100\n    TSB $0E\n"),
    # idle loop, every frame: when the scene's sprite art has been loaded since
    # the last upload (the cache slot holds a source again: entering the room,
    # or the room reloaded after the inventory screen), upload the tiles;
    # AdhocVramDma yields until the NMI has run it and leaves the entry point
    # on itself, so the loop head is set again afterwards
    ("    COP [C1]\n    COP [C1]\n    COP [89]\n",
     "  kress_upload:\n    COP [C1]\n    LDA $%04X\n    BEQ kress_anim\n" % (CACHE_SLOT_BG_D + 1) + UPLOAD
     + "    BRA kress_upload\n  kress_anim:\n    COP [89]\n"),
    # stand as the stock spirit guide does (awBF_spirit_guide): solid on two
    # tiles and drawn between them, so Will stops beside it instead of
    # walking half into it (GaiaLabs marks one tile and does not nudge). The
    # guide is met from below and leans right; Will comes along the vine from
    # the right here, so the spirit leans left (onto the end of the vine) and
    # Will's stop, and the talk distance from it, stay as they were
    ("    COP [0B]\n    COP [C0] ( &shortcut_interact )\n",
     "    COP [0B]\n    COP [0D] ( #FF, #00 )\n    COP [BC] ( #F8, #00 )\n    COP [C0] ( &shortcut_interact )\n"),
]




def kress_shortcut(src, pack):
    """Mt. Kress: a spirit at the top of the Mountain Temple (scene $A9) that
    offers to take Will to the bottom once flag $223 is set. GaiaLabs appends
    a spawn record to the room's actor list; bank $0C, where the lists live,
    has no free space, so the room's camera actor record (the same 7 bytes)
    is pointed at a wrapper instead: it has the camera actor's own header, so
    it starts as the camera did, spawns the spirit where GaiaLabs places it
    with the flags its header would give, and goes on as the stock camera.

    $A9 is a combat room, which never loads the props sprite sheet the spirit
    is drawn from (those name-table-0 tiles hold effect and ability art). So
    the spirit draws from OBJ name table 1 instead (bit 8 of its OAM word),
    which in $A9 holds only the Kress enemies' art and the room has none, and
    copies its own tiles there from the stock ROM with the game's
    AdhocVramDma whenever the scene's sprite art has just been (re)loaded;
    it clears that VRAM's scene-art cache slot so the next room reloads its
    enemies. Will's ability tiles are never touched."""
    import gaialabs_asm as ga
    db = ga.Db(src.baserom, src.rom, gaia_names(src), gaia_themes(src))
    text = src.module("kress-shortcut/KressShortcut.patch.asm").decode("utf-8").replace("\r\n", "\n")
    for old, new in KRESS_FIXUPS:
        if text.count(old) != 1: raise SystemExit("kress-shortcut: fixup %r does not match once" % old)
        text = text.replace(old, new)
    m = re.search(r"actor-def\s*<\s*#(\w\w),\s*#(\w\w),\s*#(\w\w),\s*\{(.*)\n\}\s*\n-+\s*\n\?INCLUDE 'scene_actors'",
                  text, re.S)
    spawn = re.search(r"actor-spawn\s*<\s*#(\w\w),\s*#(\w\w),\s*#(\w\w),\s*@KressShortcut\s*>", text)
    if not m or not spawn:
        raise SystemExit("kress-shortcut: the module is not the expected shape")
    header = bytes(int(m.group(k), 16) for k in (1, 2, 3))
    tx, ty, attr = (int(spawn.group(k), 16) for k in (1, 2, 3))
    if attr & 1:
        raise SystemExit("kress-shortcut: spawn parameter records are not handled")
    record = KRESS_LIST + 7
    if src.rom[record + 3:record + 6] != bytes([0xED, 0xEA, 0x80]) or src.rom[KRESS_LIST + 21] != 0xFF:
        raise SystemExit("kress-shortcut: scene $A9's actor list is not the stock one")
    # the tiles are copied from the stock ROM at run time; check they are the spirit's
    fx = db.stock(FX_SOURCE)
    if src.files.get(FX_SOURCE, {}).get("start") != fx or src.files[FX_SOURCE]["end"] - fx < SPIRIT_TILES[1] * 32 - 0x40 * 32:
        raise SystemExit("kress-shortcut: %s is not where the database puts it" % FX_SOURCE)
    camera = 0x00EAED
    cam_header = src.rom[camera:camera + 3]
    flags = (header[1] | header[2] << 8) | 0x4000
    wrapper = ("kress_wrapper {\n    COP [A0] ( @kress_shortcut_main, #$%04X, #$%04X, #$%04X )\n"
               "    COP [C7] ( @CameraScrollUpdate )\n}\n" % (tx * 16, ty * 16, flags))
    consts, blocks = ga.parse(m.group(4) + "\n" + wrapper)
    asm = ga.Assembler(db, consts, blocks, stock_override={
        "CameraScrollUpdate": camera + 3, "spriteset_npc_props": 0x0EDA00})
    lo, hi = KRESS_SPACE
    names = [b.name for b in blocks if b.name != "kress_wrapper"]
    whead = asm.place(lo + 3, names)
    end = asm.place(whead + 3, ["kress_wrapper"])
    if end > hi:
        raise SystemExit("kress-shortcut: does not fit")
    blob = header + b"".join(asm.emit(n) for n in names) + cam_header + asm.emit("kress_wrapper")
    if len(blob) != end - lo or any(x != 0xFF for x in src.rom[lo:end]):
        raise SystemExit("kress-shortcut: layout or space check failed")
    pack.write("kress_shortcut", lo, blob)
    bank, addr = ga.hiroms(whead)
    pack.write("kress_shortcut", record + 3, struct.pack("<HB", addr, bank))


def words(block):
    return [int(v, 16) for v in re.findall(r"#\$([0-9A-Fa-f]{4})", block)]


def blocks(text):
    """label -> body for 'label! ...' and 'label ...' definitions."""
    out = {}
    for m in re.finditer(r"^(\w+)(!?)\s+(\[.*?\]|#\$?[0-9A-Fa-f]+)", text, re.M | re.S):
        out[m.group(1)] = (m.group(3), m.group(2) == "!")
    return out


def parallax(src, pack, feature, patch, label):
    body, _ = blocks(patch)[label]
    data = bytes.fromhex(body[1:])
    stock_at = int(label.split("_")[1], 16)
    for index in range(64):
        if struct.unpack_from("<H", src.rom, PARALLAX_TABLE + 2 * index)[0] == stock_at & 0xFFFF:
            pack.table(feature, index, data); return
    raise SystemExit("no parallax index for %s" % label)


def word_list(src, pack, feature, patch, label):
    body, _ = blocks(patch)[label]
    values = words(body)
    pack.write(feature, int(label.split("_")[1], 16), b"".join(struct.pack("<H", v) for v in values))


def red_fountain(src, pack):
    """Same shape as stock: twelve bundles, eleven single colours then a list
    of twelve. The new colours go into the stock words; the bundles keep
    pointing at them and take the module's timings."""
    patch = src.module("red-fountain/RedFountain.patch.asm").decode()
    b = blocks(patch)
    entries = re.findall(r"palette-bundle\s*<\s*#(\w\w),\s*&(\w+),\s*#(\w\w),\s*#(\w\w),\s*#(\w\w)\s*>",
                         b["palette_bundle_1693F9"][0])
    table = 0x1693F9
    if len(entries) != 12: raise SystemExit("red fountain: %d bundles" % len(entries))
    stock_words = [struct.unpack_from("<H", src.rom, table + 6 * i + 1)[0] for i in range(12)]
    out = bytearray(src.rom[table:table + 6 * 12])
    for i, (count, label, a, c, timing) in enumerate(entries):
        values = words(b[label][0])
        expect = 12 if i == 11 else 1
        if len(values) != expect or stock_words[i] != 0x9442 + 2 * i:
            raise SystemExit("red fountain: bundle %d does not match the stock layout" % i)
        if (int(count, 16), int(a, 16), int(c, 16)) != (src.rom[table + 6 * i], src.rom[table + 6 * i + 3],
                                                       src.rom[table + 6 * i + 4]):
            raise SystemExit("red fountain: bundle %d changes more than colour and timing" % i)
        out[6 * i + 5] = int(timing, 16)
        pack.write("red_fountain", 0x160000 + stock_words[i],
                   b"".join(struct.pack("<H", v) for v in values))
    pack.write("red_fountain", table, bytes(out))


def main():
    if len(sys.argv) != 6: raise SystemExit(__doc__)
    retranslation, commit, baserom, rom_path, output = sys.argv[1:]
    rom = Path(rom_path).read_bytes()
    identity = (Path(__file__).resolve().parent.parent / "rom_identity.txt").read_text()
    if hashlib.sha256(rom).hexdigest() not in identity:
        raise SystemExit("%s is not the stock USA ROM named in rom_identity.txt" % rom_path)
    src = Sources(retranslation, commit, baserom, rom)
    pack = Pack(rom)
    relocated = list(RELOCATE_SPACE)
    for feature, (module, assets) in FEATURES.items():
        for name in assets:
            asset(src, pack, feature, module, name, relocated)
    edward = src.module("jp-edward-mountains/JpEdwardMountains.patch.asm").decode()
    parallax(src, pack, "jp_edward", edward, "binary_01CC4A")
    word_list(src, pack, "jp_edward", edward, "word_168320")
    itory = src.module("jp-itory-mountains/JpItoryMountains.patch.asm").decode()
    parallax(src, pack, "jp_itory", itory, "binary_01CC89")
    red_fountain(src, pack)
    spritemap(src, pack, "jp_viper", "jp-viper", "spm_viper.spm", relocated)
    crystal_ring(src, pack)
    no_shira(src, pack)
    slave_return(src, pack)
    for feature in SCRIPT_MODULES:
        script_option(src, pack, feature)
    kress_shortcut(src, pack)
    # stock words must be replaced one for one
    for kind, feature, offset, data, _ in pack.records:
        if kind == b"W" and offset + len(data) > len(rom): raise SystemExit("record past the ROM")
    pack.save(output, "IOGRetranslation " + commit)
    print("%d records, %d bytes -> %s" % (len(pack.records), Path(output).stat().st_size, output))


if __name__ == "__main__":
    main()
