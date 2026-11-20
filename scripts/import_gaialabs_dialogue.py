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
GLYPHS = frozenset(" 0123456789.,\":ABCDEFGHIJKLMNOPQRSTUVWXYZ!/*-()"
                   "abcdefghijklmnopqrstuvwxyz;?'")
TYPOGRAPHY = str.maketrans({"…": "...", "ˮ": '"'})
COSMETICS = {"TPL": 0x24, "BOR": 0xD, "DLY": 0xFF, "SFX": 0xFF}
STOCK_SPEAKER_TEMPLATES = frozenset(range(8)) | frozenset(range(0x12, 0x16))


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
        raise ValueError("No explicit terminal END")
    pages, lines, line, speaker = [], [], "", None
    for part in re.split(r"(\[[^\]]*\])", source.translate(TYPOGRAPHY)):
        if not part:
            continue
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
        elif command in ("FIN", "END") and raw_arg is None:
            lines.append(line)
            if not any(row.strip() for row in lines):
                raise ValueError("Empty dialogue page")
            pages.append((speaker, lines))
            lines, line, speaker = [], "", None
        elif command in ("CLD", "CLR", "DEF") and raw_arg is None and not (lines or line.strip()):
            continue
        else:
            raise ValueError(f"Unsupported command {command}")
    if source.count("[END]") != 1 or lines or line:
        raise ValueError("Unexpected terminal command structure")

    rendered = []
    for speaker, page in pages:
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
            rendered.append(marker + "[N]".join(group))
    return "[FIN]".join(rendered) + "[END]"


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
