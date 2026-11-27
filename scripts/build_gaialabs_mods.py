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
    handler, operand, at = 0x059484, 0x05947D, 0x05FEF0
    if src.rom[handler:handler + len(stock)] != stock or src.rom[operand - 2:operand + 2] != b"\x02\xc0\x84\x94":
        raise SystemExit("no-shira-spotlight: stock handler differs")
    code = stock[3:]                                            # print + options, without the flag
    if any(b != 0xFF for b in src.rom[at - 16:at + len(code) + 16]):
        raise SystemExit("no-shira-spotlight: bank $05 padding is not free")
    pack.write("no_shira", at, code)
    pack.write("no_shira", operand, struct.pack("<H", at & 0xFFFF))


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
    # stock words must be replaced one for one
    for kind, feature, offset, data, _ in pack.records:
        if kind == b"W" and offset + len(data) > len(rom): raise SystemExit("record past the ROM")
    pack.save(output, "IOGRetranslation " + commit)
    print("%d records, %d bytes -> %s" % (len(pack.records), Path(output).stat().st_size, output))


if __name__ == "__main__":
    main()
