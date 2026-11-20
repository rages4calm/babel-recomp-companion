#!/usr/bin/env python3
"""Convert pinned public GaiaLabs chapter dialogue for Companion's stock text engine."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import textwrap


REVISION = "754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc"
ROOT = Path(__file__).resolve().parents[1]
PATCHES = "modules/base/patches"
# GaiaCore allows the closing delimiter to be omitted when the text ends in
# an explicit halt command. The converter verifies its terminal END itself.
LABEL = re.compile(r"dialogstring_([0-9A-F]{6})!\s+`([^`]*)`?!?\s*(?:;.*)?")
TAG = re.compile(r"\[([A-Z][A-Z0-9]*)(?::([0-9A-F]+))?\]")
BOX_TAG = re.compile(r"\[(DLG|SIZ):([0-9A-F]{1,2}),([0-9A-F]{1,2})\]")
GLYPHS = frozenset(" 0123456789.,\":ABCDEFGHIJKLMNOPQRSTUVWXYZ!/*-()"
                   "abcdefghijklmnopqrstuvwxyz;?'")
TYPOGRAPHY = str.maketrans({"…": "...", "ˮ": '"'})
COSMETICS = {"TPL": 0x24, "BOR": 0xD, "DLY": 0xFF, "SFX": 0xFF}
STOCK_SPEAKER_TEMPLATES = frozenset(range(8)) | frozenset(range(0x12, 0x16))
RETURN_WIDTH = 24
EXTENDED_SOURCE_WIDTH = 26
MAX_PAGE_ROWS = 7


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


def convert_return(source, names, *, extended=False):
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
        if part in ("[CLD]", "[CLR]", "[DEF]") or BOX_TAG.fullmatch(part):
            continue
        if part == "[RET]" and source.endswith(part):
            continue
        if extended and part == "[END]" and source.endswith(part) and source.count(part) == 1:
            continue
        if extended and part == "[WAI]":
            parts.append(part)
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
    pages = candidate.split("[FIN]")
    if extended:
        if not (re.sub(r"\[[^\]]+\]", "", candidate).strip() or "[BCD:" in candidate):
            raise ValueError("Empty return fragment")
    elif not any(any(ch in GLYPHS - {" "} for ch in p) for p in pages):
        raise ValueError("Empty return fragment")
    width = EXTENDED_SOURCE_WIDTH if extended else RETURN_WIDTH
    for page in pages:
        lines = page.split("[N]")
        visible_lines = (re.sub(
            r"\[BCD:([1-5]),[0-9A-F]{4}\]", lambda m: "0" * int(m[1]), row
        ) for row in lines)
        if extended:
            visible_lines = (re.sub(r"\[[^\]]+\]", "", row) for row in visible_lines)
        if len(lines) > MAX_PAGE_ROWS or any(len(row) > width for row in visible_lines):
            raise ValueError("Return fragment exceeds stock bounds")
    if extended:
        terminal = "[END]" if source.endswith("[END]") else "[RET]"
        return "[EXT]" + candidate + terminal
    return candidate + "[RET]"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="local IOGRetranslation git checkout")
    parser.add_argument("output", type=Path, help="new TSV path under the project's .local directory")
    parser.add_argument("--chapters", nargs="+", type=int, default=range(1, 37))
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".local").resolve()) or output.is_file():
        parser.error("output must be a new file within the project's .local directory")
    if any(chapter < 1 or chapter > 36 for chapter in args.chapters):
        parser.error("chapters must be between 1 and 36")

    names = load_names(args.checkout.resolve())
    labels = stock_labels(ROOT / "i18n/structure.txt")
    rows, excluded, seen = [], {}, set()
    for chapter in sorted(set(args.chapters)):
        source = read_source(args.checkout, f"{PATCHES}/chapter{chapter:02d}.patch.asm")
        for line in source.splitlines():
            if not line.startswith("dialogstring_"):
                continue
            match = LABEL.fullmatch(line)
            if not match:
                raise ValueError("Unexpected active chapter dialogue declaration")
            offset, content = match.groups()
            if offset in seen:
                raise ValueError(f"Duplicate replacement at {offset}")
            seen.add(offset)
            if offset not in labels:
                excluded[offset] = "No unique marker-free stock label"
                continue
            try:
                converted = convert(content, names)
            except ValueError as error:
                # Leave existing rows byte-identical. The runtime checks the
                # new pool after allocating the established dialogue addresses.
                try:
                    converted = convert_return(content, names, extended=True)
                except ValueError:
                    excluded[offset] = str(error)
                    continue
            rows.append((offset, labels[offset], converted))
    if not rows:
        raise ValueError("No supported dialogue rows")

    with output.open("x", encoding="ascii", newline="\n") as stream:
        for _, label, converted in sorted(rows):
            stream.write(f"{label}\t{converted}\n")
    print(json.dumps({"revision": REVISION, "source_rows": len(seen), "output_rows": len(rows),
                      "excluded": dict(Counter(excluded.values()))}, sort_keys=True))


if __name__ == "__main__":
    main()
