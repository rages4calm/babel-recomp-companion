#!/usr/bin/env python3
"""Convert pinned public GaiaLabs chapter dialogue for Companion's stock text engine."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import textwrap

import gaia_authored_dialogue


REVISION = "754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc"
ROOT = Path(__file__).resolve().parents[1]
PATCHES = "modules/base/patches"
# GaiaCore allows the closing delimiter to be omitted when the text ends in
# an explicit halt command. The converter verifies its terminal END itself.
LABEL = re.compile(r"dialogstring_([0-9A-F]{6})!\s+`([^`]*)`?!?\s*(?:;.*)?")
TAG = re.compile(r"\[([A-Z][A-Z0-9]*)(?::([0-9A-F]+))?\]")
BOX_TAG = re.compile(r"\[(DLG|SIZ):([0-9A-F]{1,2}),([0-9A-F]{1,2})\]")
PRINT_TAG = re.compile(r"\[PRT:@dialogstring_(08DE96|069705)\]")
GLYPHS = frozenset(" 0123456789.,\":ABCDEFGHIJKLMNOPQRSTUVWXYZ!/*-()"
                   "abcdefghijklmnopqrstuvwxyz?'")
# Tile $8F is not a semicolon in the stock font; it draws a stray mark.
TYPOGRAPHY = str.maketrans({"…": "...", "ˮ": '"', ";": ","})
COSMETICS = {"TPL": 0x24, "BOR": 0xD, "DLY": 0xFF, "SFX": 0xFF}
STOCK_SPEAKER_TEMPLATES = frozenset(range(8)) | frozenset(range(0x12, 0x16))
RETURN_WIDTH = 24
EXTENDED_SOURCE_WIDTH = 26
MAX_PAGE_ROWS = 7
STOCK_JUMPS = {
    "06BE1F": "06BF7C",
    "06BE85": "06BF7C",
    "06BF0A": "06BF7C",
}
TAIL_PREFIXES = {
    "049B82": (2, "[PAU:40]"),
    "09BE70": (4, "[TPL:2]"),
}

# Every string is first transcribed with the pages, rows, box sizes and
# speaker colours GaiaLabs wrote (gaia_authored_dialogue checks each one
# against the stock renderer and its script). The stock-window conversions
# below remain for the strings that transcription does not support.

# Slips in the pinned source text, found while replaying the scenes. Each is
# applied only to its own string and must match exactly, so a corrected
# upstream revision makes the import stop instead of passing unnoticed.
CORRECTIONS = {
    "049BE5": (("momoent", "moment"),),
    "04A3BB": (("bring[N]you you back home", "bring[N]you back home"),),
    "04D8D2": (("going on be", "going to be"), ("gradually become quiet", "gradually became quiet")),
}

# The Jeweler. His reward list is a box-only string followed by one string
# per row; GaiaLabs widens the box by a column so the longer labels fit,
# and the rows are printed into it. His menu has a second entry point three
# bytes in, after the commands that open the box, which the source does not
# mark; the greeting above the question scrolls away as GaiaLabs wrote it,
# leaving the options on the rows the script's cursor visits. His deposit
# reply prints into that menu box: the script reaches it from the menu's
# choice through code that counts and removes the jewels without printing.
JEWELER_FRAME = "08D617"
JEWELER_ROWS = ("08D621", "08D636", "08D64A", "08D65E", "08D672", "08D67D", "08D68A")
JEWELER_MENU = "08D0F1"
JEWELER_MENU_HEAD = ("[TPL:16][TPL:F]", "[DEF][PAL:0][::][CLR]")
# The reward checks run straight after that reply, so the Herb and Dark
# Friar reward messages print into the same box.
CALLER_BOXES = {offset: gaia_authored_dialogue.DEFAULT_BOX for offset in ("08D20F", "08D2D0", "08D4E3", "08D5AE")}

# GaiaLabs ends this crew member's line by jumping to the second part of
# 058394, Will's aside. A jump cannot leave an overlay bank, and the stock
# string has none to return to, so the aside is printed in line.
INLINE_CONTINUATIONS = {"0583E7": "058394"}

INTERFACE_FILES = (
    ("menu", "ItemStrings", r"^consolestring_([0-9A-F]{6})!\s+\|([^|]*)\|"),
    ("scene", "MapNames", r"^scene_event_([0-9A-F]{6})_value!\s+`([^`]*)`"),
    ("sprite", "OverworldNameSwitch", r"^spritestring_([0-9A-F]{6})!\s+~([^~]*)~"),
    ("prologue", "chapter01", r"^spritestring_([0-9A-F]{6})!\s+~([^~]*)~"),
)


def read_source(repo, path):
    return subprocess.check_output(
        ("git", "-C", str(repo), "show", f"{REVISION}:{path}"),
        encoding="utf-8-sig",
    )


def load_names(repo):
    source = read_source(repo, f"{PATCHES}/SwitchNameDictionary.patch.asm")
    table = re.search(r"(?m)^name_dictionary_en \[\s*\n(.*?)^\]", source, re.S)
    if table is None:
        raise ValueError("English name table is missing")
    refs = re.findall(r"(?m)^\s+&(name_\w+)\s*;[0-9A-F]+\s*$", table[1])
    names = dict(re.findall(r"(?m)^(name_\w+)\s+`([^`]+)`!?\s*$", source))
    if len(refs) != 27 or len(set(refs)) != len(refs):
        raise ValueError("Unexpected English name table")
    return [names[ref] for ref in refs]


def stock_labels(path):
    labels = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[0] == "S" and fields[2] == "widestring":
            offset = fields[3].upper()
            if offset in labels:
                raise ValueError(f"Duplicate marker-free stock label at {offset}")
            labels[offset] = fields[1]
    return labels


def stock_tail_labels(path):
    labels = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 5 or fields[0] != "S" or fields[2] != "widestring":
            continue
        offset = fields[3].upper()
        if offset in TAIL_PREFIXES and int(fields[4], 16) == TAIL_PREFIXES[offset][0]:
            if offset in labels:
                raise ValueError(f"Duplicate stock tail label at {offset}")
            labels[offset] = fields[1]
    return labels


def stock_pair_labels(path):
    labels = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if (len(fields) == 5 and fields[0] == "S" and fields[2] == "widestring"
                and int(fields[4], 16) >= 5 and fields[3].upper() not in TAIL_PREFIXES):
            labels[fields[3].upper()] = fields[1]
    return labels


def convert_pair(source, names):
    prefix, marker, tail = source.partition("[::]")
    if not marker or "[::]" in tail:
        raise ValueError("Expected one stock entry marker")
    body = convert_return(prefix, names, extended=True, wrap_prose=True)
    if not body.endswith("[FIN][RET]"):
        # The runtime must retain the USA boundary. This source can include
        # a new visual pause after the manual wait, before the interior entry.
        body = re.sub(r"\[FIN\](?:\[PAU:[0-9A-F]{2}\])+\[RET\]$", "[FIN][RET]", body)
        if not body.endswith("[FIN][RET]"):
            raise ValueError("Marker does not follow a page wait")
    extra = convert_return(tail, names, extended=True, wrap_prose=True)
    return "[PAIR]" + body + "|" + extra


def convert_tail(offset, source, names):
    prefix, marker, tail = source.partition("[::]")
    if not marker or prefix != TAIL_PREFIXES[offset][1] or "[::]" in tail:
        raise ValueError("Stock tail prefix differs")
    return "[TAIL]" + convert_return(tail, names, extended=True)


def convert(source, names):
    if not source.endswith("[END]"):
        return convert_return(source, names)
    pages, lines, line, speaker = [], [], "", None
    opening_pause = closing_pause = None
    palette_reset = False
    position = None
    has_box = False
    for part in re.split(r"(\[[^\]]*\])", source.translate(TYPOGRAPHY)):
        if not part:
            continue
        at_start = not (lines or line.strip())
        if box := BOX_TAG.fullmatch(part):
            kind, first, second = box.groups()
            x, y = int(first, 16), int(second, 16)
            if kind == "DLG" and at_start and position is None and not has_box:
                position = (x, y)
                continue
            if kind == "SIZ" and position is not None:
                left, top = position
                # Stock uses two tiles per column and two tile rows per line.
                if not (x >= 2 and y >= 1 and left > 0 and top > 0
                        and left + 2 * x <= 33 and top + 2 * y <= 31):
                    raise ValueError("Invalid dialogue box bounds")
                position = None
                has_box = True
                continue
            raise ValueError("Unpaired or inline dialogue box")
        if position is not None:
            raise ValueError("Unpaired or inline dialogue box")
        if palette_reset and part != "[END]":
            raise ValueError("Inline palette reset")
        if closing_pause is not None and part not in ("[PAL:0]", "[FIN]", "[END]"):
            raise ValueError("Inline pause")
        if not part.startswith("["):
            if any(ch not in GLYPHS for ch in part):
                raise ValueError("Unsupported stock glyph")
            line += part
            continue
        match = TAG.fullmatch(part)
        if not match:
            raise ValueError("Structured or pointer command")
        command, raw_arg = match.groups()
        if command in COSMETICS and raw_arg is not None:
            # Keep the stock message's window and typing presentation.
            value = int(raw_arg, 16)
            if value > COSMETICS[command]:
                raise ValueError("Invalid cosmetic argument")
            if (command == "TPL" and value in STOCK_SPEAKER_TEMPLATES
                    and not (lines or line.strip()) and speaker is None):
                speaker = value
        elif command == "NAM" and raw_arg is not None:
            # The stock engine lacks the selectable GaiaLabs name dictionary.
            # Use the upstream default English spelling for this profile.
            index = int(raw_arg, 16)
            if index >= len(names) or any(ch not in GLYPHS for ch in names[index]):
                raise ValueError("Unsupported name entry")
            line += names[index]
        elif command == "N" and raw_arg is None:
            lines.append(line)
            line = ""
        elif command == "PAU" and raw_arg is not None and 0 < int(raw_arg, 16) <= 0xFF:
            if at_start and opening_pause is None:
                opening_pause = int(raw_arg, 16)
            elif not at_start:
                closing_pause = int(raw_arg, 16)
            else:
                raise ValueError("Repeated opening pause")
        elif command == "PAL" and raw_arg == "0" and not at_start:
            palette_reset = True
        elif command in ("FIN", "END") and raw_arg is None:
            lines.append(line)
            if not any(row.strip() for row in lines):
                raise ValueError("Empty dialogue page")
            pages.append((speaker, lines, opening_pause, closing_pause, palette_reset))
            lines, line, speaker = [], "", None
            opening_pause = closing_pause = None
            palette_reset = has_box = False
        elif command in ("CLD", "CLR", "DEF") and raw_arg is None and not (lines or line.strip()):
            continue
        else:
            raise ValueError(f"Unsupported command {command}")
    if source.count("[END]") != 1 or lines or line:
        raise ValueError("Unexpected terminal command structure")

    rendered = []
    for speaker, page, opening_pause, closing_pause, palette_reset in pages:
        rows = []
        for text in page:
            layout = textwrap.wrap(text.strip(), 24, break_long_words=False, break_on_hyphens=False)
            if any(len(row) > 24 for row in layout):
                raise ValueError("Word exceeds stock dialogue width")
            rows.extend(layout or [""])
        for start in range(0, len(rows), 3):
            group = rows[start:start + 3]
            if not any(group):
                raise ValueError("Empty dialogue page after repagination")
            marker = f"[TPL:{speaker:02X}]" if speaker is not None and start == 0 else ""
            if opening_pause is not None and start == 0:
                marker += f"[PAU:{opening_pause:02X}]"
            suffix = ""
            if start + 3 >= len(rows):
                if closing_pause is not None:
                    suffix += f"[PAU:{closing_pause:02X}]"
                if palette_reset:
                    suffix += "[PAL:00]"
            rendered.append(marker + "[N]".join(group) + suffix)
    return "[FIN]".join(rendered) + "[END]"


def convert_return(source, names, *, extended=False, wrap_prose=False, timed=False):
    """Keep authored rows intact for stock window and terminal validation."""
    parts = []
    for part in re.split(r"(\[[^\]]*\])", source.translate(TYPOGRAPHY)):
        if not part:
            continue
        if not part.startswith("["):
            if any(ch not in GLYPHS for ch in part):
                raise ValueError("Unsupported stock glyph")
            parts.append(part)
            continue
        if part in ("[N]", "[FIN]"):
            parts.append(part)
            continue
        if timed and part in ("[CLR]", "[CLD]"):
            parts.append(part)
            continue
        if part in ("[CLD]", "[CLR]", "[DEF]") or BOX_TAG.fullmatch(part):
            continue
        if part == "[RET]" and source.endswith(part):
            continue
        if extended and part == "[END]" and source.endswith(part) and source.count(part) == 1:
            continue
        if extended and part == "[WAI]":
            parts.append(part)
            continue
        if extended and (call := PRINT_TAG.fullmatch(part)):
            # Keep the stock call target available for operand verification.
            # These two script families name the same shared stock fragments.
            parts.append(f"[PRT:{call[1]}]")
            continue
        if match := TAG.fullmatch(part):
            command, arg = match.groups()
            value = int(arg, 16) if arg is not None else -1
            if command in COSMETICS and 0 <= value <= COSMETICS[command]:
                if extended and command == "TPL" and value in STOCK_SPEAKER_TEMPLATES:
                    parts.append(f"[TPL:{value:02X}]")
                continue
            if extended and command == "PAL" and value in range(0, 0x20, 4):
                parts.append(f"[PAL:{value:02X}]")
                continue
            if command == "PAL" and value in (0, 4):
                continue
            if command == "NAM" and 0 <= value < len(names):
                if all(ch in GLYPHS for ch in names[value]):
                    parts.append(names[value])
                    continue
            if extended and command == "PAU" and 0 < value <= 0xFF:
                parts.append(f"[PAU:{value:02X}]")
                continue
        if match := re.fullmatch(r"\[BCD:([1-5]),([0-9A-F]{1,4})\]", part):
            digits, address = match.groups()
            parts.append(f"[BCD:{digits},{int(address, 16):04X}]")
            continue
        raise ValueError("Unverified return-fragment command")
    if source.count("[RET]") > 1 or not parts:
        raise ValueError("Invalid return fragment")
    candidate = "".join(parts)
    delimiters = r"(\[(?:FIN|CLR|CLD)\])" if timed else r"(\[FIN\])"
    pages = re.split(delimiters, candidate)
    if extended:
        if not (re.sub(r"\[[^\]]+\]", "", candidate).strip() or "[BCD:" in candidate):
            raise ValueError("Empty return fragment")
    elif not any(any(ch in GLYPHS - {" "} for ch in p) for p in pages):
        raise ValueError("Empty return fragment")
    width = EXTENDED_SOURCE_WIDTH if extended else RETURN_WIDTH
    layouts = []
    for index, page in enumerate(pages):
        if index % 2:
            layouts.append(page)
            continue
        lines = page.split("[N]")
        visible_lines = (re.sub(
            r"\[BCD:([1-5]),[0-9A-F]{4}\]", lambda m: "0" * int(m[1]), row
        ) for row in lines)
        if extended:
            visible_lines = (re.sub(r"\[[^\]]+\]", "", row) for row in visible_lines)
        layout = []
        for line, visible in zip(lines, visible_lines):
            if len(visible) <= width:
                layout.append(line)
                continue
            # Keep a bound on transported rows. Split ordinary prose at
            # spaces while retaining its speaker selector, if present.
            prose = re.fullmatch(
                r"((?:\[(?:TPL|PAU|PAL):[0-9A-F]{2}\])*)([^\[\]]+)"
                r"((?:\[(?:PAU|PAL):[0-9A-F]{2}\])*)", line
            ) if wrap_prose else None
            if prose is None:
                raise ValueError("Return fragment exceeds stock bounds")
            prefix, content, suffix = prose.groups()
            wrapped = textwrap.wrap(content, width, break_long_words=False, break_on_hyphens=False)
            if not wrapped or any(len(row) > width for row in wrapped):
                raise ValueError("Return fragment exceeds stock bounds")
            wrapped[0] = prefix + wrapped[0]
            wrapped[-1] += suffix
            layout.extend(wrapped)
        if len(layout) > MAX_PAGE_ROWS:
            raise ValueError("Return fragment exceeds stock bounds")
        layouts.append("[N]".join(layout))
    if extended:
        terminal = "[END]" if source.endswith("[END]") else "[RET]"
        return "[EXT]" + "".join(layouts) + terminal
    return candidate + "[RET]"


def convert_stock_jump(offset, source, names):
    target = STOCK_JUMPS[offset]
    body, separator, operand = source.rpartition("[JMP:")
    if not separator or operand != f"&dialogstring_{target}]" or not body.endswith(("[FIN]", "[FIN][CLD]")):
        raise ValueError("Stock jump target or boundary differs")
    return convert_return(body, names, extended=True, wrap_prose=True).removesuffix("[RET]") + f"[JMP:{target}]"


def convert_extended(offset, source, names):
    if offset == "0BD558":
        # Keep the stock clear between the two separately timed cards.
        boundary = "[PAU:78][TPL:A]"
        if source.count(boundary) != 1 or not source.endswith("[PAU:B4][CLD]"):
            raise ValueError("Unexpected Comet opening timeline")
        return "[LATE]" + convert_return(
            source.replace(boundary, "[PAU:78][CLR][TPL:A]"),
            names, extended=True, wrap_prose=True, timed=True,
        )
    near_reply_targets = {"04AA7D": "04AAAD", "05DF9F": "05DE46"}
    if offset in near_reply_targets:
        body, separator, target = source.rpartition("[JMP:")
        if (not separator or not body.endswith("[FIN]") or
                target != f"&dialogstring_{near_reply_targets[offset]}+M]"):
            raise ValueError("Unexpected reply continuation")
        # The in-ROM wrapper keeps the actual same-bank JMP operand.
        return "[LAY]" + convert_return(body, names, extended=True, wrap_prose=True)
    if offset == "08EB68":
        # The runtime keeps the indexed name lookup in the original ROM bank.
        body, separator, tail = source.partition("[ADR:&table_08EB8F,AAC]")
        if (not separator or not body.startswith("[TPL:E][DLY:5]") or
                not body.endswith("[N]") or tail != "![PAU:50][FIN]"):
            raise ValueError("Unexpected ability-name announcement")
        return "[LAY]" + convert_return(body, names, extended=True)
    try:
        return convert_return(source, names, extended=True)
    except ValueError:
        pass
    return "[LAY]" + convert_stock_layout(offset, source, names)


def convert_stock_layout(offset, source, names):
    if offset in STOCK_JUMPS:
        return convert_stock_jump(offset, source, names)
    try:
        return convert_return(source, names, extended=True, wrap_prose=True)
    except ValueError:
        if "[PAU:" not in source or not ("[CLR]" in source or "[CLD]" in source):
            raise
    return convert_return(source, names, extended=True, wrap_prose=True, timed=True)


def interface_rows(repo, names):
    for kind, filename, declaration in INTERFACE_FILES:
        rows = {}
        source = read_source(repo, f"{PATCHES}/{filename}.patch.asm")
        for address, content in re.findall(declaration, source, re.MULTILINE):
            if address in rows:
                raise ValueError(f"Duplicate {kind} label at {address}")
            text = content.translate(TYPOGRAPHY)
            if kind == "scene":
                if not text:
                    continue
                text = re.sub(r"\[NAM:([0-9A-F]+)\]",
                              lambda tag: names[int(tag[1], 16)], text)
            if not text.isascii() or any(not 32 <= ord(char) < 127 for char in text):
                continue
            rows[address] = text
        for address, text in sorted(rows.items()):
            yield kind, address, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="local IOGRetranslation git checkout")
    parser.add_argument("output", type=Path, help="new TSV path under the project's .local directory")
    parser.add_argument("--rom", type=Path, default=ROOT / "Illusion of Gaia (USA).sfc",
                        help="verified USA ROM; authored pages are omitted when it is absent")
    parser.add_argument("--chapters", nargs="+", type=int,
                        help="import only the selected chapters and omit interface text")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".local").resolve()) or output.is_file():
        parser.error("output must be a new file within the project's .local directory")
    chapters = args.chapters or range(1, 37)
    if any(chapter < 1 or chapter > 36 for chapter in chapters):
        parser.error("chapters must be between 1 and 36")

    names = load_names(args.checkout.resolve())
    structure = ROOT / "i18n/structure.txt"
    labels = stock_labels(structure)
    tails = stock_tail_labels(structure)
    pairs = stock_pair_labels(structure)
    rows, excluded, seen = [], {}, set()
    # Every dialogue label with its second entry point, if it has one.
    entries = {}
    for line in structure.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) in (4, 5) and fields[0] == "S" and fields[2] == "widestring":
            entries[fields[3].upper()] = (fields[1], int(fields[4], 16) if len(fields) == 5 else None)
    rom = args.rom.read_bytes() if args.rom.is_file() else None
    if rom is not None and len(rom) != 0x200000:
        parser.error("the ROM must be the unheadered 2 MiB USA image")
    authored = 0
    unsupported = {}
    if rom is not None:
        gaia_authored_dialogue.load_themes(read_source(args.checkout, "modules/base/asm/dialog_template_table.asm"))
    jeweler = {}
    deferred = []
    # Strings another string prints through a lookup table and then ends on.
    # The host's box is the box they print into.
    table_boxes = {}
    if rom is not None:
        hosted = {}
        for line in structure.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) > 3 and fields[0] == "T":
                hosted[fields[2].upper()[-4:]] = [name[-6:].upper() for name in fields[3:]]
        for offset in entries:
            try:
                text = gaia_authored_dialogue.decode_stock(rom, int(offset, 16))[0]
            except (gaia_authored_dialogue.Unsupported, ValueError):
                continue
            call = re.search(r"\[ADR:[0-9A-F]{4}([0-9A-F]{4})\]", text)
            if call and call[1] in hosted and text[call.end():] == "[END]":
                box = gaia_authored_dialogue.stock_state(text[:call.start()] + "[RET]")["box"]
                for member in hosted[call[1]]:
                    table_boxes[member] = box if table_boxes.get(member, box) == box else None
    sources = {}
    declarations = []
    for chapter in sorted(set(chapters)):
        declarations.extend(read_source(args.checkout, f"{PATCHES}/chapter{chapter:02d}.patch.asm").splitlines())
    if rom is not None:
        # The USA ROM sometimes holds one copy of a string per actor (the six
        # Pyramid slates). GaiaLabs points them all at the first copy and
        # declares only that one, so each byte-identical copy gets the same
        # declaration here.
        declared = {match[1]: line for line in declarations
                    if line.startswith("dialogstring_") and (match := LABEL.fullmatch(line))}
        copies = {}
        for offset in entries:
            try:
                data = gaia_authored_dialogue.decode_stock(rom, int(offset, 16))[1]
            except (gaia_authored_dialogue.Unsupported, ValueError):
                continue
            if len(data) >= 8:
                copies.setdefault(data, []).append(offset)
        for group in copies.values():
            first = next((offset for offset in sorted(group) if offset in declared), None)
            for offset in sorted(group):
                if first is not None and offset not in declared:
                    declarations.append(declared[first].replace(first, offset, 1))
    for _ in (0,):
        for line in declarations:
            if not line.startswith("dialogstring_"):
                continue
            match = LABEL.fullmatch(line)
            if not match:
                raise ValueError("Unexpected active chapter dialogue declaration")
            offset, content = match.groups()
            sources[offset] = content
            for wrong, right in CORRECTIONS.get(offset, ()):
                if content.count(wrong) != 1:
                    raise ValueError(f"Correction for {offset} no longer matches the source")
                content = content.replace(wrong, right)
            if offset in seen:
                raise ValueError(f"Duplicate replacement at {offset}")
            seen.add(offset)
            if offset in INLINE_CONTINUATIONS:
                deferred.append((offset, content))
                continue
            if rom is not None and offset in JEWELER_ROWS + (JEWELER_FRAME,):
                jeweler[offset] = content
                continue
            if rom is not None and offset in entries:
                label, marker = entries[offset]
                try:
                    stock, data = gaia_authored_dialogue.decode_stock(rom, int(offset, 16))
                    if offset == JEWELER_MENU:
                        if not content.startswith(JEWELER_MENU_HEAD[0]):
                            raise gaia_authored_dialogue.Unsupported("Jeweler menu source changed")
                        stream = "[MRK]" + "|".join(gaia_authored_dialogue.transcribe_entry(
                            JEWELER_MENU_HEAD[1] + content[len(JEWELER_MENU_HEAD[0]):], rom, int(offset, 16),
                            marker, names, scroll=True))
                    elif table_boxes.get(offset) and "[::]" not in content and marker is None:
                        stream = gaia_authored_dialogue.transcribe(content, stock, names, rom, int(offset, 16),
                                                                   entry_box=table_boxes[offset], tail=True)
                    elif offset in CALLER_BOXES:
                        stream = gaia_authored_dialogue.transcribe(content, stock, names, rom, int(offset, 16),
                                                                   entry_box=CALLER_BOXES[offset])
                    elif marker is None:
                        stream = gaia_authored_dialogue.transcribe(content, stock, names, rom, int(offset, 16))
                    else:
                        stream = "[MRK]" + "|".join(gaia_authored_dialogue.transcribe_entry(
                            content, rom, int(offset, 16), marker, names))
                except gaia_authored_dialogue.Unsupported as error:
                    unsupported[offset] = str(error)
                else:
                    signature = gaia_authored_dialogue.stock_signature(data)
                    rows.append((offset, label, f"[RAW:{signature:08X}]{stream}"))
                    authored += 1
                    continue
            if offset not in labels:
                if offset in tails:
                    try:
                        rows.append((offset, tails[offset], convert_tail(offset, content, names)))
                    except ValueError as error:
                        excluded[offset] = str(error)
                    continue
                if offset in pairs:
                    try:
                        rows.append((offset, pairs[offset], convert_pair(content, names)))
                    except ValueError as error:
                        excluded[offset] = str(error)
                    continue
                excluded[offset] = "No unique marker-free stock label"
                continue
            try:
                converted = convert(content, names)
            except ValueError as error:
                # Leave existing rows byte-identical. The runtime checks the
                # new pool after allocating the established dialogue addresses.
                try:
                    converted = convert_extended(offset, content, names)
                except ValueError:
                    excluded[offset] = str(error)
                    continue
            rows.append((offset, labels[offset], converted))
    for offset, content in deferred:
        body, jump, _ = content.rpartition("[JMP:")
        aside = sources.get(INLINE_CONTINUATIONS[offset], "").partition("[::]")[2]
        try:
            if not jump or not body.endswith("[END]") or not aside.endswith("[END]") or rom is None:
                raise gaia_authored_dialogue.Unsupported("continuation differs from the pinned source")
            stock, data = gaia_authored_dialogue.decode_stock(rom, int(offset, 16))
            stream = gaia_authored_dialogue.transcribe(body + aside, stock, names, rom, int(offset, 16))
        except gaia_authored_dialogue.Unsupported as error:
            excluded[offset] = str(error)
        else:
            rows.append((offset, entries[offset][0],
                         f"[RAW:{gaia_authored_dialogue.stock_signature(data):08X}]{stream}"))
            authored += 1
    if JEWELER_FRAME in jeweler:
        # The rows are only as wide as the box the frame string opens.
        def sign(offset):
            return gaia_authored_dialogue.stock_signature(gaia_authored_dialogue.decode_stock(rom, int(offset, 16))[1])
        stock = lambda offset: gaia_authored_dialogue.decode_stock(rom, int(offset, 16))[0]
        try:
            frame, box = gaia_authored_dialogue.transcribe_frame(jeweler[JEWELER_FRAME], stock(JEWELER_FRAME))
            listing = [(offset, gaia_authored_dialogue.transcribe_row(jeweler[offset], stock(offset), names, box))
                       for offset in JEWELER_ROWS]
        except (gaia_authored_dialogue.Unsupported, KeyError) as error:
            raise ValueError(f"Jeweler list no longer matches the source: {error}")
        for offset, stream in [(JEWELER_FRAME, frame)] + listing:
            rows.append((offset, entries[offset][0], f"[RAW:{sign(offset):08X}]{stream}"))
            authored += 1
    if not rows:
        raise ValueError("No supported dialogue rows")

    interface = list(interface_rows(args.checkout.resolve(), names)) if args.chapters is None else []
    with output.open("x", encoding="ascii", newline="\n") as stream:
        for _, label, converted in sorted(rows):
            stream.write(f"{label}\t{converted}\n")
        for kind, address, content in interface:
            stream.write(f"{kind}_{address}\t{content}\n")
    print(json.dumps({"revision": REVISION, "source_rows": len(seen), "output_rows": len(rows),
                      "authored_rows": authored,
                      "authored_unsupported": dict(Counter(unsupported.values())),
                      "interface": dict(Counter(kind for kind, _, _ in interface)),
                      "excluded": dict(Counter(excluded.values()))}, sort_keys=True))


if __name__ == "__main__":
    main()
