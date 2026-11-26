#!/usr/bin/env python3
"""Transcribe GaiaLabs-authored dialogue pages for the stock USA text engine.

The Retranslation source is written for GaiaLabs' modified renderer. Most of
its commands exist unchanged in the stock renderer, so a string that opens its
own boxes can keep the authored pages, rows and box sizes. Three differences
are handled here:

* Stock opens a box before selecting the speaker, because opening a box
  resets the text palette and the per-character sound.
* Stock has no five-row templates and no speaker themes above $15.
* Opening a box does not erase the previous one. A box that does not cover
  the previous box needs a [CLD] first.

`simulate` models the stock renderer (box origin and size, cursor row and
column, page waits). It is run on every transcribed string, and on the stock
string to find the commands a replacement must keep.
"""

import re

COLUMNS = 26
# Stock template table at $01:CA95. Speakers set colours and voice only.
STOCK_SPEAKERS = frozenset(range(8)) | frozenset(range(0x13, 0x16))
STOCK_BOXES = {
    0x08: (3, 6, 13, 1), 0x09: (3, 6, 13, 2), 0x0A: (3, 6, 13, 3), 0x0B: (3, 6, 13, 4),
    0x0C: (3, 17, 13, 1), 0x0D: (3, 17, 13, 2), 0x0E: (3, 17, 13, 3), 0x0F: (3, 17, 13, 4),
}
DEFAULT_BOX = (3, 17, 13, 4)
# GaiaLabs adds five-row boxes as templates $10 (bottom) and $12 (top). Its
# top boxes start at tile row 4; stock keeps rows 0-4 for the status display,
# so the tall top box starts at the stock row 6 and covers the stock top boxes.
AUTHORED_TALL = {0x10: (3, 15, 13, 5), 0x12: (3, 6, 13, 5)}
# Six-row boxes for timed cards (the epilogue) whose page nobody can advance:
# internal numbers, never written to a stream.
TIMED_TALL = {0x60: (3, 13, 13, 6), 0x61: (3, 6, 13, 6)}
AUTHORED_TALL.update(TIMED_TALL)
# GaiaLabs speaker themes $16-$24 do not exist in stock. A stock speaker
# template is two text colours, a voice and a palette switch, and the same
# four commands reproduce a theme's text colours and voice. `load_themes`
# reads them from the pinned source; without them a theme falls back to the
# stock voices it shares, or to the plain narration colours.
THEMES = {theme: None for theme in range(0x16, 0x25)}
THEMES.update({0x21: 0x02, 0x22: 0x01, 0x23: 0x04, 0x24: 0x04})
THEME_COLOURS = {}


def load_themes(table_source):
    """Read each theme's text colours and voice from dialog_template_table.asm."""
    names = re.search(r"dialog_template_table \[(.*?)\]", table_source, re.S)
    order = re.findall(r"&(\w+)\s*;([0-9A-F]{2})", names[1]) if names else []
    found = {}
    for label, index in order:
        body = re.search(rf"(?m)^{label} `([^`]*)`", table_source)
        if int(index, 16) not in THEMES or body is None:
            continue
        colours = dict(re.findall(r"\[SEP:(11|12),([0-9A-F]{1,4})\]", body[1]))
        voice = re.search(r"\[SFX:([0-9A-F]{1,2})\]", body[1])
        if set(colours) == {"11", "12"} and "[PAL:4]" in body[1]:
            found[int(index, 16)] = (int(colours["11"], 16), int(colours["12"], 16),
                                     int(voice[1], 16) if voice else None)
    THEME_COLOURS.clear()
    THEME_COLOURS.update(found)
    return found
GLYPHS = frozenset(" 0123456789.,\":ABCDEFGHIJKLMNOPQRSTUVWXYZ!/*-()"
                   "abcdefghijklmnopqrstuvwxyz?'")
# The stock font has no ellipsis, closing-quote, heart or semicolon tile.
# Tile $8F, which older tables list as a semicolon, draws only a stray mark.
TYPOGRAPHY = str.maketrans({"…": "...", "ˮ": '"', "♥": " ", ";": ","})
TOKEN = re.compile(r"(\[[^\]]*\])")
STOCK_LOOKUP = re.compile(r"\[(?:LU1|LU2):[0-9A-F]+\]")


class Unsupported(ValueError):
    """The string needs something this transcription does not model."""


def box_rect(box):
    """Tile rectangle a box covers, border included."""
    x, y, width, height = box
    return x - 1, y - 1, x + 2 * width, y + 2 * height


def covers(new, old):
    a, b = box_rect(new), box_rect(old)
    return a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]


TOP_ROW = 6        # stock top boxes; tile rows 0-4 hold the status display


# Stock boxes that run to the edge of the picture: the ending's lesson card.
# Only the string whose stock version opens one may open it.
EDGE_BOXES = {(0, 0x17, 0x0F, 3)}


def on_screen(box, top_row=TOP_ROW):
    left, top, right, bottom = box_rect(box)
    # One spare tile row below the border holds the continuation cursor.
    # Closing a box over the status display would erase it; `top_row` is
    # lower only for a scene whose stock string opens a box there itself.
    return left >= 1 and top >= top_row - 1 and right <= 30 and bottom <= 26 and box[2] >= 2 and box[3] >= 1


def tokens(text):
    for part in TOKEN.split(text):
        if not part:
            continue
        if part.startswith("["):
            name, _, argument = part[1:-1].partition(":")
            yield name, argument
        else:
            for glyph in part:
                yield "glyph", glyph


def number(argument):
    if not re.fullmatch(r"[0-9A-F]{1,2}", argument):
        raise Unsupported(f"operand {argument!r}")
    return int(argument, 16)


def pair(argument):
    first, separator, second = argument.partition(",")
    if not separator:
        raise Unsupported(f"operand {argument!r}")
    return number(first), number(second)


def simulate(stream, box=None, scroll=False):
    """Run a stock-engine command stream. Returns a summary of what it did.

    `box` is the box the calling script left open, if any. With `scroll`,
    a row below the last one scrolls the page up, as the renderer does.

    Raises Unsupported when text would leave its box, when a box is opened
    over one it does not cover, or when text is printed with no known box.
    """
    column = row = 0
    position = None
    rows = [""]
    summary = {"waits": 0, "pauses": [], "boxes": [], "sfx": set(), "terminal": None,
               "glyphs": 0, "trailing_palette": False, "opens_first": None}
    previous = None
    for name, argument in tokens(stream):
        if summary["terminal"]:
            raise Unsupported("commands after the terminal")
        if name == "glyph":
            if summary["opens_first"] is None:
                summary["opens_first"] = False
            if box is None:
                raise Unsupported("text outside a known box")
            column += 1
            rows[-1] += argument
            if column > 2 * box[2]:
                raise Unsupported("row exceeds its box")
            summary["glyphs"] += 1
        elif name in ("BCD", "ESC"):
            # A number prints its digits; raw tiles print one tile each.
            digits = int(argument.split(",")[0]) if name == "BCD" else len(argument) // 2
            if box is None:
                raise Unsupported("text outside a known box")
            rows[-1] += "#" * digits
            column += digits
            if column > 2 * box[2]:
                raise Unsupported("row exceeds its box")
            summary["glyphs"] += 1
        elif name == "N":
            if box is None:
                raise Unsupported("line break outside a known box")
            row += 1
            column = 0
            rows.append("")
            if row >= box[3]:
                if not scroll:
                    raise Unsupported("page exceeds its box")
                row -= 1
                rows.pop(0)
        elif name in ("FIN", "WAI"):
            summary["waits"] += 1
            if name == "FIN":
                column = row = 0
                rows = [""]
        elif name == "CLR":
            column = row = 0
            rows = [""]
        elif name == "CLD":
            box = None
            column = row = 0
            rows = [""]
        elif name in ("TPL", "DEF", "SIZ"):
            if name == "TPL":
                template = number(argument)
                if template in STOCK_SPEAKERS:
                    previous = (name, argument)
                    continue
                if template not in STOCK_BOXES:
                    raise Unsupported(f"template {template:02X}")
                opened = STOCK_BOXES[template]
            elif name == "DEF":
                opened = DEFAULT_BOX
            else:
                if position is None:
                    raise Unsupported("box size without a position")
                opened = position + pair(argument)
                position = None
            if not on_screen(opened, min(TOP_ROW, opened[1])) and opened not in EDGE_BOXES:
                raise Unsupported("box leaves the screen")
            if box is not None and not covers(opened, box):
                raise Unsupported("box does not cover the open box")
            if summary["opens_first"] is None:
                summary["opens_first"] = True
            box = opened
            column = row = 0
            rows = [""]
            summary["boxes"].append(opened)
        elif name == "DLG":
            position = pair(argument)
        elif name == "PAU":
            summary["pauses"].append(number(argument))
        elif name == "SFX":
            summary["sfx"].add(number(argument))
        elif name in ("PAL", "DLY"):
            number(argument)
        elif name == "SEP":
            if not re.fullmatch(r"1[12],[0-9A-F]{4}", argument):
                raise Unsupported("palette write outside the two text colours")
        elif name == "PRT" and previous is None and box is not None:
            pass        # a shared stock string printed first; `box` is what it leaves
        elif name in ("END", "RET"):
            summary["terminal"] = name
            summary["trailing_palette"] = previous == ("PAL", "00") or previous == ("PAL", "0")
            if name == "END":
                summary["waits"] += 1
        else:
            raise Unsupported(f"command {name}")
        previous = (name, argument)
    if position is not None:
        raise Unsupported("box position without a size")
    summary.update(box=box, rows=rows, after_wait=previous == ("FIN", ""))
    return summary


def stock_profile(stock):
    """Commands of the stock string that a replacement has to respect."""
    plain = STOCK_LOOKUP.sub("x", stock)
    # A final same-bank jump continues in another stock string.
    plain = re.sub(r"\[JMP:[0-9A-F]{4}\]$", "[JMP]", plain)
    if "[::]" in plain or "[JMP:" in plain or "[PRT:" in plain or "[ADR:" in plain:
        raise Unsupported("stock string has entry points or references")
    plain = re.sub(r"\[SEP:[^\]]*\]", "", plain)
    # Stock rows can scroll and reuse an open box; only its commands matter.
    profile = {"first_speaker": None, "pauses": [], "sfx": set(), "speakers": [], "waits": 0, "opens_first": None,
               "trailing_palette": False, "terminal": None}
    previous = None
    for name, argument in tokens(plain):
        if name in ("glyph", "BCD", "ESC") and profile["opens_first"] is None:
            profile["opens_first"] = False
        elif name == "DEF" or name == "SIZ" or (name == "TPL" and (number(argument) in STOCK_BOXES
                                                                   or number(argument) == 0x10)):
            # Stock template $10 is a second copy of the default box.
            if profile["opens_first"] is None:
                profile["opens_first"] = True
        elif name == "TPL" and number(argument) in STOCK_SPEAKERS:
            speaker = number(argument)
            if profile["opens_first"] is not False and not profile["speakers"]:
                profile["first_speaker"] = speaker
            if not profile["speakers"] or profile["speakers"][-1] != speaker:
                profile["speakers"].append(speaker)
        elif name == "PAU":
            profile["pauses"].append(number(argument))
        elif name == "SFX":
            profile["sfx"].add(number(argument))
        elif name in ("FIN", "WAI"):
            profile["waits"] += 1
        elif name in ("END", "RET", "JMP"):
            profile["terminal"] = name
            profile["trailing_palette"] = previous in (("PAL", "00"), ("PAL", "0"))
        if name != "glyph":
            previous = (name, argument)
        else:
            previous = None
    return profile


_FAMILY = {**{t: ("top", t - 0x07) for t in range(0x08, 0x0C)},
           **{t: ("bottom", t - 0x0B) for t in range(0x0C, 0x10)},
           0x10: ("bottom", 5), 0x12: ("top", 5), 0x60: ("bottom", 6), 0x61: ("top", 6)}
_TEMPLATE = {("top", rows): 0x07 + rows for rows in range(1, 5)}
_TEMPLATE.update({("bottom", rows): 0x0B + rows for rows in range(1, 5)})
_TEMPLATE.update({("top", 5): 0x12, ("bottom", 5): 0x10, ("top", 6): 0x61, ("bottom", 6): 0x60})


def fit_rows(source, names, inherited=None):
    """Expand names and refit pages whose rows no longer fit their box.

    The stock font has no ellipsis tile, so an authored row can grow past 26
    columns once names and ellipses are spelled out. Such a page is wrapped
    again, and its box template is raised when it needs another row.
    `inherited` is the box the calling script left open, if any: a page that
    needs more rows than it has opens the next template of the same kind.
    """
    def name(match):
        value = int(match[1], 16)
        if value >= len(names):
            raise Unsupported("name entry")
        return names[value]

    source = re.sub(r"\[NAM:([0-9A-F]+)\]", name, source.translate(TYPOGRAPHY))
    parts = [part for part in TOKEN.split(source) if part]
    # A card that only pauses cannot wait for a button in the middle of a
    # sentence, so its box may grow to six rows instead.
    tallest = 6 if "[PAU:" in source and "[FIN]" not in source and "[WAI]" not in source else 5
    out, page = [], []
    family = rows = None
    columns = 2 * inherited[2] if inherited else COLUMNS
    for template, geometry in STOCK_BOXES.items():
        if geometry == inherited:
            family, rows = _FAMILY[template]

    def flush():
        nonlocal family, rows, columns
        head = []
        body = list(page)
        page.clear()
        while body and body[0].startswith("[") and body[0] != "[N]":
            head.append(body.pop(0))
        tail = []
        while body and body[-1].startswith("[") and body[-1] != "[N]":
            tail.insert(0, body.pop())
        position = None
        opener = None
        for index, tag in enumerate(head):
            command, _, argument = tag[1:-1].partition(":")
            if command == "TPL" and int(argument, 16) in _FAMILY:
                family, rows = _FAMILY[int(argument, 16)]
                opener, columns = index, COLUMNS
            elif command == "DEF":
                family, rows, opener, columns = "bottom", 4, index, COLUMNS
            elif command == "SIZ":
                family, rows, opener = None, pair(argument)[1], None
                columns = 2 * pair(argument)[0]
        lines = [[]]
        for part in body:
            if part == "[N]":
                lines.append([])
            else:
                lines[-1].append(part)
        def width(line):
            total = 0
            for part in line:
                if part.startswith("[BCD:"):
                    total += int(part[5])
                elif part.startswith("[ESC:"):
                    total += len(part[5:-1].replace(",", "")) // 2
                elif not part.startswith("["):
                    total += len(part)
            return total
        if rows is None or (all(width(line) <= columns for line in lines) and len(lines) <= rows):
            out.extend(head + body + tail)
            return
        needed = lines
        if any(width(line) > columns for line in lines):
            # Words keep the commands written in front of them (a pause, a
            # typing speed), which take no room on the row.
            words, pending = [], []
            for line in lines:
                row = "".join(part for part in line if not part.startswith("[") or part.startswith("[BCD:"))
                if row != row.strip() or "  " in row.replace("[BCD:", ""):
                    raise Unsupported("wide row with authored spacing")
                for part in line:
                    if part.startswith("[") and not part.startswith("[BCD:"):
                        pending.append(part)
                        continue
                    pieces = [part] if part.startswith("[BCD:") else part.split(" ")
                    for index, piece in enumerate(pieces):
                        if index or not words or words[-1][2]:
                            words.append([pending, [], False])
                            pending = []
                        elif pending:
                            words[-1][1].extend(pending)
                            pending = []
                        if piece:
                            words[-1][1].append(piece)
                    if not part.startswith("[BCD:") and part.endswith(" "):
                        words[-1][2] = True
                if words:
                    words[-1][2] = True          # a row break separates words
            words = [word for word in words if word[1] or word[0]]
            if pending and words:
                words[-1][1].extend(pending)
            needed, used = [[]], 0
            for prefix, body_parts, _ in words:
                size = width(body_parts)
                if size > columns:
                    raise Unsupported("word wider than the box")
                if used and used + 1 + size > columns:
                    needed.append([])
                    used = 0
                if used:
                    needed[-1].append(" ")
                    used += 1
                needed[-1].extend(prefix + body_parts)
                used += size
        if len(needed) > rows:
            # A page no box can hold is left as it is: the choice layout
            # may still move rows to another page, and the renderer model
            # refuses the string otherwise.
            # Six rows with no sentence end to turn the page at would leave
            # a word or two alone on a second page; they get a six-row box.
            limit = tallest
            if len(needed) == 6 and not any("".join(line).rstrip().endswith((".", "!", "?", '"'))
                                            for line in needed[:5]):
                limit = 6
            if family is not None and len(needed) <= limit:
                rows = len(needed)
                template = f"[TPL:{_TEMPLATE[family, rows]:X}]"
                if opener is None:
                    head.append(template)
                else:
                    head[opener] = template
        out.extend(head)
        capacity = max(rows, tallest) if family is not None else rows
        if family is not None and rows == 6:
            capacity = 6
        if len(needed) > capacity and not any(
                part.startswith("[") for line in needed for part in line):
            # Wrapping made the page taller than any box. It continues on a
            # second page, broken after the last row that ends a sentence.
            cut = max((index for index in range(1, capacity + 1)
                       if "".join(needed[index - 1]).rstrip().endswith((".", "!", "?", '"'))), default=capacity)
            if len(needed) - cut <= capacity:
                for index, line in enumerate(needed[:cut]):
                    out.extend((["[N]"] if index else []) + line)
                out.append("[FIN]")
                needed = needed[cut:]
        for index, line in enumerate(needed):
            if index:
                out.append("[N]")
            out.extend(line)
        out.extend(tail)

    def opens(part):
        command, _, argument = part[1:-1].partition(":")
        return part.startswith("[") and (command in ("DEF", "DLG") or
                                         (command == "TPL" and int(argument, 16) in _FAMILY))

    for part in parts:
        if opens(part) and any(not item.startswith("[") for item in page):
            # A box opened after text starts the page again, as in stock.
            while page[-1] == "[N]":
                page.pop()
            flush()
        if part in ("[FIN]", "[END]", "[CLD]", "[CLR]"):
            flush()
            out.append(part)
            if part == "[CLD]":
                family = rows = None
        else:
            page.append(part)
    flush()
    return "".join(out)


_INHERIT = object()


def _opener(box):
    """GaiaLabs-notation tag that opens a stock box geometry in `transcribe`."""
    for template, geometry in STOCK_BOXES.items():
        if geometry == box:
            return f"[TPL:{template:X}]"
    return f"[DLG:{box[0]:X},{box[1]:X}][SIZ:{box[2]:X},{box[3]:X}]"


def _wrap(text):
    rows = []
    for word in text.split():
        if rows and len(rows[-1]) + 1 + len(word) <= COLUMNS:
            rows[-1] += " " + word
        else:
            rows.append(word)
    if any(len(row) > COLUMNS for row in rows):
        raise Unsupported("word wider than the box")
    return rows


def _choice_page(source, options, skip, final_box, stock_rows, plain, scroll=False):
    """Rebuild the last page so the choices start on the row the script expects.

    COP $BE places its cursor `skip` rows below the box origin and GaiaLabs
    scripts may use another row. The question keeps the sentences that fit
    in those rows; earlier sentences get a page of their own.
    """
    cut = max(source.rfind(tag) + len(tag) if tag in source else 0 for tag in ("[FIN]", "[CLD]", "[CLR]"))
    before, page = source[:cut], source[cut:]
    parts = [part for part in TOKEN.split(page) if part]
    head = []
    while parts and parts[0].startswith("[") and parts[0] != "[N]" and not parts[0].startswith("[PAL"):
        head.append(parts.pop(0))
    rows = [""]
    for part in parts:
        if part == "[N]":
            rows.append("")
        elif part.startswith("[PAL") or part == "[WAI]":
            continue        # Stock choices use the box's plain colours and no extra wait.
        elif part.startswith("["):
            raise Unsupported("commands inside the choice page")
        else:
            rows[-1] += part
    first = len(rows)
    while first and rows[first - 1].startswith(" ") and rows[first - 1].strip():
        first -= 1
    choices, text = rows[first:], [row for row in rows[:first] if row.strip()]
    # An option may continue on a second row, as in stock. The script's
    # cursor only visits `options` rows, so the row count has to match stock.
    if len(choices) < options or len(choices) != stock_rows:
        raise Unsupported("choice rows differ from the stock page")
    if plain:
        choices[0] = "[PAL:0]" + choices[0]
    if final_box[3] < skip + len(choices):
        raise Unsupported("stock box is smaller than the choice page")
    speaker = [tag for tag in head if tag.startswith("[TPL:") and int(tag[5:-1], 16) not in _FAMILY]
    presentation = [tag for tag in head if tag.startswith(("[DLY", "[SFX", "[PAU"))]
    early = []
    if scroll and len(text) > skip and final_box[3] == skip + len(choices):
        # The page is exactly as tall as the stock choice page, so extra rows
        # above scroll away and leave the choices on their rows.
        pass
    elif len(text) > skip:
        sentences = re.split(r'(?<=[.!?"])\s+', " ".join(text))
        keep = []
        while sentences and len(_wrap(" ".join(sentences[-1:] + keep))) <= skip:
            keep.insert(0, sentences.pop())
        last = _wrap(sentences[-1]) if sentences else []
        if not keep and len(last) <= final_box[3] and final_box[3] == skip + len(choices):
            # The question itself is taller than the rows above the choices.
            # As GaiaLabs writes it ([WAI] before the choices), the whole
            # question is read first and the choices then scroll in under
            # its last rows. A page of its own left the choices under blank
            # rows with nothing asked. Earlier sentences keep their pages.
            out = before
            family = "top" if final_box[1] < 12 else "bottom"
            early = _wrap(" ".join(sentences[:-1]))
            while early:
                shown, early = early[:4], early[4:]
                out += f"[TPL:{_TEMPLATE[family, len(shown)]:X}]" + "".join(speaker + presentation) + "[N]".join(shown) + "[FIN]"
                presentation = []
            return (out + "[BOX]" + "".join(speaker + presentation) + "[N]".join(last) +
                    "[WAI][N]" + "[N]".join(choices)), True
        # When even the last sentence needs more rows than the script leaves
        # above the choices, it gets its own page whole and the choices
        # follow alone. Breaking it across a button press reads worse.
        early, text = _wrap(" ".join(sentences)), _wrap(" ".join(keep)) if keep else []
    out = before
    family = "top" if final_box[1] < 12 else "bottom"
    while early:
        shown, early = early[:4], early[4:]
        out += f"[TPL:{_TEMPLATE[family, len(shown)]:X}]" + "".join(speaker + presentation) + "[N]".join(shown) + "[FIN]"
        presentation = []
    text += [""] * (skip - len(text))
    return out + "[BOX]" + "".join(speaker + presentation) + "[N]".join(text + choices), False


def transcribe(source, stock, names, rom=None, offset=None, entry_box=None, contract=None, entry=False,
               scroll=False, tail=False):
    """Return the stock-engine stream for one authored string.

    `source` is the GaiaLabs declaration body, `stock` the decoded USA string
    in the same notation. With `rom` and `offset`, strings that share a box
    with their calling script are supported as well. The result starts with
    a `[BOX:x,y,w,h]` tag when the string prints into an inherited box.
    `entry_box` and `contract` supply the open box and the script's choice
    command for a second entry point, which has no script site of its own.
    `tail` marks a string that another string prints through a lookup table
    and then ends the dialogue: it may return with text still on the page.
    Raises Unsupported when the result cannot be shown to keep the stock
    string's behaviour.
    """
    shared = re.match(r"\[PRT:([0-9A-F]{6})\]", stock)
    if shared:
        # Both versions begin by printing the same stock string from the ROM.
        target = int(shared[1], 16) & 0x3FFFFF
        if rom is None or not source.startswith(f"[PRT:@dialogstring_{target:06X}]"):
            raise Unsupported("shared print call differs")
        left = stock_state(decode_stock(rom, target)[0])
        if left["terminal"] != "RET" or left["box"] is None or not left["after_wait"]:
            raise Unsupported("shared string does not leave an empty box")
        stock = stock[len(shared[0]):]
        source = source[source.index("]") + 1:]
        entry_box = left["box"]
    profile = stock_profile(stock)
    inherited = None
    if not profile["opens_first"]:
        inherited = entry_box or (caller_box(rom, offset) if rom is not None else None)
        if inherited is None or not stock_state(stock, inherited)["fits"]:
            raise Unsupported("the calling script's box is not known")
    final = stock_state(stock, inherited)
    if contract is None and rom is not None and profile["terminal"] == "RET":
        contract = prompt_contract(rom, offset)
    if profile["terminal"] == "END":
        mode = "end"
    elif profile["terminal"] == "JMP":
        # The jump stays in the ROM bank; the text returns to it. The target
        # string continues in the box this one leaves open.
        if not final["after_wait"] or final["box"] is None:
            raise Unsupported("stock string jumps in the middle of a page")
        mode = "page"
        source, jumps = re.subn(r"(?:\[CLD\])*\[JMP:[^\]]*\]$", "", source)
        if jumps != 1:
            raise Unsupported("authored string does not jump where stock does")
    elif profile["terminal"] != "RET":
        raise Unsupported("stock string does not end or return")
    elif contract:
        mode = "choice"
    elif final["box"] is None and profile["opens_first"]:
        mode = "closed"
    elif final["after_wait"] and final["box"] is not None:
        mode = "page"
    elif tail and final["box"] is not None:
        mode = "tail"
    else:
        raise Unsupported("stock string returns in the middle of a page")
    if profile["terminal"] == "RET" and source.endswith("[RET]"):
        source = source[:-5]        # GaiaLabs sometimes writes the return out
    source = fit_rows(source, names, inherited)
    if "[::]" in source:
        raise Unsupported("authored entry point")
    if mode == "end":
        # A close after the final END never runs: END already closes the box.
        source = re.sub(r"\[END\](?:\[CLD\])+$", "[END]", source)
        if not source.endswith("[END]"):
            raise Unsupported("authored string does not end the dialogue")
    elif mode == "closed" and source.endswith("[END]") and source.count("[END]") == 1 and "[RET]" not in source:
        # Stock closes its box and returns. An authored END does the same
        # after one more input wait.
        source = source[:-5] + "[WAI][CLD]"
    elif mode == "page" and source.endswith("[END]") and source.count("[END]") == 1 and "[RET]" not in source:
        source = source[:-5] + "[FIN][BOX]"     # the script closes the box itself
    elif "[END]" in source or "[RET]" in source:
        raise Unsupported("authored string ends a dialogue the stock string continues")
    elif mode == "closed":
        if not source.endswith("[CLD]"):
            raise Unsupported("authored string leaves its box open")
    elif mode == "tail":
        if source.endswith(("[FIN]", "[CLD]")):
            raise Unsupported("authored string leaves nothing for the caller's wait")
    elif mode == "page":
        if not source.endswith("[FIN]"):
            raise Unsupported("authored string returns in the middle of a page")
        source += "[BOX]"
    else:
        source, scrolled = _choice_page(source, contract[0], contract[1], final["box"], final["row"] + 1 - contract[1],
                                        "[PAL:00]" in stock[stock.rfind("[FIN]") + 1:], scroll)
        scroll = scroll or scrolled
    if mode != "end":
        source += "[RET]"

    # The ending and a few other scenes have no status display, and their
    # stock strings open the top box two rows higher. Authored top boxes
    # follow the stock row there.
    stock_rows = [pair(a)[1] for n, a in tokens(re.sub(r"\[SEP:[^\]]*\]", "", STOCK_LOOKUP.sub("x", stock))) if n == "DLG"]
    top_row = min([TOP_ROW] + [row for row in stock_rows if row < TOP_ROW])
    constant = {}
    for kind in ("DLY", "SFX"):
        old = set(re.findall(r"\[%s:([0-9A-F]+)\]" % kind, stock))
        new = set(re.findall(r"\[%s:([0-9A-F]+)\]" % kind, source))
        if len(old) == 1 and len(new) == 1 and int(min(old), 16) == int(min(new), 16):
            constant[kind] = int(min(old), 16)
    out = []
    box = inherited
    # An inherited box keeps the caller's colours until the string names a speaker.
    speaker = active = _INHERIT if inherited else None
    if entry and speaker is None and profile["first_speaker"] is not None:
        # A script can reach an entry point without the speaker the first
        # part selected. Stock names the speaker again there; GaiaLabs
        # relies on its engine keeping the colours.
        speaker = profile["first_speaker"]
    delay = sound = None          # requested typing delay and per-character sound
    shown_delay = shown_sound = None
    fresh = False                 # a delay or sound was requested since the last text
    page_text = False             # a glyph was printed since the page began
    position = None
    parts = list(tokens(source))

    lead = re.match(r"\[DLG:([0-9A-F]+),([0-9A-F]+)\]\[SIZ:([0-9A-F]+),([0-9A-F]+)\]", stock)
    stock_box = tuple(int(v, 16) for v in lead.groups()) if lead else None

    later_speaker = None
    for part_name, part_argument in tokens(source):
        if part_name == "TPL" and (number(part_argument) in STOCK_SPEAKERS or number(part_argument) in THEMES):
            later_speaker = THEME_COLOURS.get(number(part_argument), THEMES.get(number(part_argument),
                                                                              number(part_argument)))
            break

    def open_box(opened, command):
        nonlocal box, active, page_text, delay, sound, shown_delay, shown_sound, speaker
        if page_text:
            # GaiaLabs may open the next box after an input wait on the same
            # page. Stock redraws the body, which starts the page again.
            if not out or out[-1] not in ("[WAI]", "[N]"):
                raise Unsupported("box opened in the middle of a page")
            while out[-1] == "[N]":
                out.pop()
            if out[-1] != "[WAI]":
                raise Unsupported("box opened in the middle of a page")
        if opened[1] == TOP_ROW and top_row < TOP_ROW:
            opened = (opened[0], top_row, opened[2], opened[3])
            command = "[DLG:%02X,%02X][SIZ:%02X,%02X]" % opened
        # A box the stock string opens itself is the scene's own layout, even
        # where it runs to the edge of the picture (the ending's lesson card).
        if not on_screen(opened, top_row) and opened != stock_box:
            raise Unsupported("box leaves the screen")
        if box is not None and not covers(opened, box):
            out.append("[CLD]")
        out.append(command)
        if speaker is _INHERIT:
            # Opening a box drops the caller's colours. Stock names its
            # speaker itself in that case; an authored string may not.
            speaker = profile["first_speaker"]
            if speaker is None:
                # Neither version names the speaker here: the conversation's
                # first string did. When the authored string names one on a
                # later page, the same character is still talking.
                speaker = later_speaker
        box = opened
        # Opening a box restores the default colours, sound and typing speed.
        active = shown_delay = shown_sound = None
        if not fresh:
            # A string that keeps one typing speed or sound throughout in
            # both versions keeps it across the boxes it opens.
            delay = constant.get("DLY") if delay is not None else None
            sound = constant.get("SFX") if sound is not None else None
        page_text = False

    def select_speaker():
        nonlocal active, shown_delay, shown_sound, fresh
        if speaker != active:
            if speaker is None:
                out.append("[PAL:00][SFX:10]")
            elif isinstance(speaker, tuple):
                first, second, voice = speaker
                out.append(f"[SEP:11,{first:04X}][SEP:12,{second:04X}]"
                           + (f"[SFX:{voice:02X}]" if voice is not None else "") + "[PAL:04]")
            else:
                out.append(f"[TPL:{speaker:02X}]")
            active = speaker
            shown_sound = None
        if sound is not None and sound != shown_sound:
            out.append(f"[SFX:{sound:02X}]")
            shown_sound = sound
        if delay is not None and delay != shown_delay:
            out.append(f"[DLY:{delay:02X}]")
            shown_delay = delay
        fresh = False

    for index, (name, argument) in enumerate(parts):
        last = index == len(parts) - 1
        if name == "glyph":
            if argument not in GLYPHS:
                raise Unsupported("glyph outside the stock font")
            if box is None:
                raise Unsupported("text before a box")
            select_speaker()
            out.append(argument)
            page_text = True
        elif name == "NAM":
            value = number(argument)
            if value >= len(names) or any(ch not in GLYPHS for ch in names[value]):
                raise Unsupported("name entry")
            if box is None:
                raise Unsupported("text before a box")
            select_speaker()
            out.append(names[value])
            page_text = True
        elif name == "TPL":
            template = number(argument)
            if template in STOCK_SPEAKERS or template in THEMES:
                speaker = THEME_COLOURS.get(template, THEMES.get(template, template))
                sound = constant.get("SFX") if sound is not None else None
            elif template in STOCK_BOXES:
                open_box(STOCK_BOXES[template], f"[TPL:{template:02X}]")
            elif template in AUTHORED_TALL:
                x, y, width, height = AUTHORED_TALL[template]
                open_box((x, y, width, height), f"[DLG:{x:02X},{y:02X}][SIZ:{width:02X},{height:02X}]")
            else:
                raise Unsupported(f"template {template:02X}")
        elif name == "DEF":
            x, y, width, height = DEFAULT_BOX
            open_box(DEFAULT_BOX, "[DEF]")
        elif name == "DLG":
            position = pair(argument)
        elif name == "SIZ":
            if position is None:
                raise Unsupported("box size without a position")
            width, height = pair(argument)
            x, y = position
            position = None
            if y < top_row:
                y = top_row     # GaiaLabs' top row is 4; stock keeps the status display there
            open_box((x, y, width, height), f"[DLG:{x:02X},{y:02X}][SIZ:{width:02X},{height:02X}]")
        elif name in ("BOR", "SEP"):
            continue
        elif name == "BOX":
            # The script continues in the box the stock string leaves open.
            if box != final["box"]:
                x, y, width, height = final["box"]
                tag = _opener(final["box"])
                open_box(final["box"], f"[TPL:{int(tag[5:-1], 16):02X}]" if tag.startswith("[TPL")
                         else f"[DLG:{x:02X},{y:02X}][SIZ:{width:02X},{height:02X}]")
            if mode == "page":
                if speaker is not _INHERIT:
                    speaker = final["speaker"]
                    select_speaker()
        elif name == "RET" and last:
            out.append("[RET]")
        elif name == "N":
            out.append("[N]")
        elif name == "FIN":
            out.append("[FIN]")
            page_text = False
        elif name == "WAI":
            out.append("[WAI]")
        elif name == "CLR":
            if box is None:
                continue
            out.append("[CLR]")
            page_text = False
        elif name == "CLD":
            if box is not None:
                out.append("[CLD]")
            # Authored narration after a closed box names no speaker.
            box = speaker = active = None
            if last and mode != "closed":
                raise Unsupported("authored string closes a box the script keeps")
            page_text = False
        elif name == "PAU":
            value = number(argument)
            if not value:
                raise Unsupported("empty pause")
            out.append(f"[PAU:{value:02X}]")
        elif name == "PAL":
            value = number(argument)
            if value & ~0x1C:
                raise Unsupported("palette operand")
            if box is None:
                continue
            select_speaker()
            out.append(f"[PAL:{value:02X}]")
        elif name == "DLY":
            value = number(argument)
            if value > 9:
                raise Unsupported("typing delay operand")
            delay, fresh = value, True
        elif name == "SFX":
            value = number(argument)
            if value in profile["sfx"] | {0x00, 0x10}:
                sound, fresh = value, True
        elif name == "BCD":
            match = re.fullmatch(r"([1-5]),([0-9A-F]{1,4})", argument)
            if not match or box is None:
                raise Unsupported("number command")
            select_speaker()
            out.append(f"[BCD:{match[1]},{int(match[2], 16):04X}]")
            page_text = True
        elif name == "ESC":
            # Raw tiles (the hieroglyph row). Only a run the stock string
            # prints itself is accepted.
            payload = argument.replace(",", "").upper()
            if box is None or f"[ESC:{payload}]" not in stock:
                raise Unsupported("raw tiles differ from the stock string")
            select_speaker()
            out.append(f"[ESC:{payload}]")
            page_text = True
        elif name == "END":
            if last:
                if profile["trailing_palette"] and box is not None:
                    out.append("[PAL:00]")
                out.append("[END]")
            else:
                # An inner END waits for input and closes the box. The rest
                # of the authored string is the continuation of this scene.
                if box is None:
                    raise Unsupported("dialogue ends before a box")
                out.append("[WAI][CLD]")
                box = speaker = active = None
                page_text = False
        else:
            raise Unsupported(f"command {name}")
    if position is not None:
        raise Unsupported("box position without a size")

    stream = "".join(out)
    result = simulate(stream, inherited, scroll)
    if result["terminal"] != ("RET" if profile["terminal"] == "JMP" else profile["terminal"]) or not result["glyphs"]:
        raise Unsupported("transcription lost its terminal or text")
    if (mode == "end" and inherited is None and not result["opens_first"]) or result["box"] != \
            (final["box"] if mode in ("page", "choice") else None if mode == "closed" else result["box"])             or (mode == "tail" and result["box"] is None):
        raise Unsupported("transcription leaves a different box")
    if mode == "choice":
        options, skip = contract
        rows = result["rows"]
        if len(rows) != final["row"] + 1 or any(not row.startswith(" ") or not row.strip() for row in rows[skip:]):
            raise Unsupported("choices are not on the rows the script expects")
    if (mode == "closed" and not result["waits"] and not profile["waits"]
            and abs(sum(result["pauses"]) - sum(profile["pauses"])) * 5 > sum(profile["pauses"])):
        # Neither version waits for the player, so the pauses are the scene's
        # timeline. GaiaLabs pages its cards differently; the card may hold
        # for up to a fifth longer or shorter than the stock one in all.
        raise Unsupported("timed string changes its timeline")
    if inherited:
        stream = "[BOX:%02X,%02X,%02X,%02X]" % inherited + stream
    if shared:
        stream = stream[:17] + shared[0] + stream[17:]
    if scroll:
        stream = "[SCR]" + stream
    if profile["terminal"] == "JMP":
        stream = "[JMP]" + stream
    # END waits for input, so the pauses only pace a page the player dismisses.
    # A pause may not hold longer than the longest one stock uses here.
    if any(value > max(profile["pauses"] + [0x78]) for value in result["pauses"]):
        raise Unsupported("long pause absent from the stock string")
    # Explicit sounds come from the stock string; a speaker brings its voice,
    # and themes use the voices of the stock speaker templates.
    if not result["sfx"] <= profile["sfx"] | {0x00, 0x10, 0x19, 0x1A, 0x1B, 0x1C}:
        raise Unsupported("sound outside the stock string")
    return stream


# ---- stock ROM strings -----------------------------------------------------

_ARGUMENTS = {0xC0: 0, 0xC1: 2, 0xC2: 1, 0xC3: 1, 0xC4: 0, 0xC5: 4, 0xC6: 4, 0xC7: 2, 0xC8: 0,
              0xC9: 1, 0xCA: 0, 0xCB: 0, 0xCC: 1, 0xCD: 3, 0xCE: 0, 0xCF: 0, 0xD0: 0, 0xD1: 2,
              0xD2: 1, 0xD3: 0, 0xD4: 3, 0xD5: 1, 0xD6: 1, 0xD7: 1}
_NAMES = {0xC0: "END", 0xC2: "TPL", 0xC3: "PAL", 0xC4: "HLT", 0xC5: "ADR", 0xC8: "CLD", 0xC9: "PAU",
          0xCA: "RET", 0xCB: "N", 0xCC: "SKP", 0xCD: "PRT", 0xCE: "CLR", 0xCF: "FIN", 0xD0: "WAI",
          0xD1: "JMP", 0xD2: "SFX", 0xD3: "DEF", 0xD4: "SEP", 0xD5: "DLY", 0xD6: "LU1", 0xD7: "LU2"}
_FONT = {0x2A: ".", 0x2B: ",", 0x2D: '"', 0x2E: '"', 0x2F: ":", 0x4F: "!", 0x6B: "/", 0x6C: "*", 0x6D: "-",
         0x6E: "(", 0x6F: ")", 0x8F: ";", 0xAC: " ", 0x0D: "?", 0x0E: "'"}
_FONT.update({0x20 + i: c for i, c in enumerate("0123456789")})
_FONT.update({0x40 + i: c for i, c in enumerate("ABCDEFGHIJKLMNO")})
_FONT.update({0x60 + i: c for i, c in enumerate("PQRSTUVWXYZ")})
_FONT.update({0x80 + i: c for i, c in enumerate("abcdefghijklmno")})
_FONT.update({0xA0 + i: c for i, c in enumerate("pqrstuvwxyz")})


def decode_stock(rom, offset, stop=None):
    """Return (notation, bytes) of the USA string at a ROM file offset.

    With `stop`, decode only the commands before that offset: the part of a
    string in front of its second entry point, which has no terminal.
    """
    start = offset
    out = []
    while offset < len(rom) and offset - start < 4096:
        if offset == stop:
            return "".join(out), bytes(rom[start:offset])
        byte = rom[offset]
        offset += 1
        if byte < 0xC0:
            if byte not in _FONT:
                raise Unsupported("stock tile outside the dialogue font")
            out.append(_FONT[byte])
            continue
        if byte == 0xD8:
            end = rom.index(0, offset)
            out.append("[ESC:" + rom[offset:end].hex().upper() + "]")
            offset = end + 1
            continue
        if byte not in _ARGUMENTS:
            raise Unsupported("stock bytes are not dialogue")
        data = rom[offset:offset + _ARGUMENTS[byte]]
        offset += len(data)
        if byte == 0xC1:
            out.append(f"[DLG:{data[0]:02X},{data[1]:02X}]")
        elif byte == 0xC7:
            out.append(f"[SIZ:{data[0]:02X},{data[1]:02X}]")
        elif byte == 0xC6:
            out.append(f"[BCD:{data[0]},{data[2] | data[3] << 8:04X}]")
        elif byte == 0xD4:
            out.append(f"[SEP:{data[0]:02X},{data[1] | data[2] << 8:04X}]")
        else:
            out.append(f"[{_NAMES[byte]}" + (":" + data[::-1].hex().upper() if data else "") + "]")
        if byte in (0xC0, 0xCA, 0xD1, 0xC4):
            return "".join(out), bytes(rom[start:offset])
    raise Unsupported("stock string does not terminate")


def stock_signature(data):
    """FNV-1a of the stock string bytes; the runtime checks it before patching."""
    value = 0x811C9DC5
    for byte in data:
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


# ---- strings that share a box with their calling script ---------------------

def stock_state(stock, box=None):
    """Follow a stock string and report the state it leaves behind.

    `box` is the box the calling script left open, or None. Stock rows may
    scroll, so only a row wider than its box makes the string unusable as
    evidence for a guessed caller box.
    """
    plain = re.sub(r"\[SEP:[^\]]*\]", "", STOCK_LOOKUP.sub("x", stock))
    column = row = 0
    position = speaker = None
    state = {"terminal": None, "fits": True, "after_wait": False, "text": False}
    for name, argument in tokens(plain):
        if name in ("glyph", "BCD", "ESC"):
            column += int(argument[0]) if name == "BCD" else len(argument) // 2 if name == "ESC" else 1
            state["text"] = True
            state["after_wait"] = False
            if box is None or column > 2 * box[2]:
                state["fits"] = False
        elif name == "N":
            row += 1
            column = 0
            state["after_wait"] = False
        elif name in ("FIN", "CLR"):
            column = row = 0
            state["after_wait"] = name == "FIN"
        elif name == "CLD":
            box = speaker = None
            column = row = 0
        elif name == "DLG":
            position = pair(argument)
        elif name == "SIZ" and position is not None:
            box, position, speaker = position + pair(argument), None, None
            column = row = 0
        elif name == "DEF":
            box, speaker = DEFAULT_BOX, None
            column = row = 0
        elif name == "TPL":
            template = number(argument)
            if template in STOCK_BOXES or template == 0x10:
                box, speaker = STOCK_BOXES.get(template, DEFAULT_BOX), None
                column = row = 0
            elif template in STOCK_SPEAKERS or template == 0x12:
                speaker = template
        elif name in ("END", "RET", "JMP", "HLT"):
            state["terminal"] = name
        elif name in ("PRT", "ADR", "::"):
            state["fits"] = False
    state.update(box=box, speaker=speaker, row=row)
    return state


def print_sites(rom, offset):
    """ROM offsets of the script commands (COP $BF) that print the string."""
    bank = offset & 0xFF0000
    needle = bytes((0x02, 0xBF, offset & 0xFF, offset >> 8 & 0xFF))
    sites, at = [], rom.find(needle, bank, bank + 0x10000)
    while at >= 0:
        sites.append(at)
        at = rom.find(needle, at + 1, bank + 0x10000)
    return sites


def prompt_contract(rom, offset):
    """(options, skipped rows) of the choice the script runs after the string."""
    found = None
    for site in print_sites(rom, offset):
        if rom[site + 4:site + 6] != b"\x02\xBE":
            continue
        contract = rom[site + 6], rom[site + 7]
        if contract[0] < 2 or sum(contract) > 7 or found not in (None, contract):
            raise Unsupported("choice command differs between callers")
        found = contract
    return found


def _branched_past(rom, at, site):
    """True when the print at `at` is the other arm of a branch that leads to `site`.

    Item scripts print what the player did, test where they stand, and then
    print either a failure line and return, or the result. The arm before
    `site`'s block must end with a return or an unconditional branch, and a
    branch or script command after the routine's earlier print must name
    that block as its target.
    """
    if rom[site - 1] == 0x60 or rom[site - 2] == 0x80:
        block = site            # the arm before it returned or branched away
    elif rom[at + 4] == 0x60 and at + 5 <= site and b"\x02\xBF" not in rom[at + 5:site]:
        block = at + 5
    else:
        return False
    before = rom.rfind(b"\x02\xBF", max((at & 0xFF0000) + 0x8000, at - 0x100), at)
    if before < 0:
        return False
    # The branch sits before this print, which it skips, or after it when
    # this print's arm has already returned.
    spans = [range(before + 4, at)] + ([range(at + 5, block - 1)] if rom[at + 4] == 0x60 else [])
    for position in (position for span in spans for position in span):
        if rom[position] | rom[position + 1] << 8 == block & 0xFFFF:
            return True         # a script command's target operand
        if rom[position] in (0x10, 0x30, 0x80, 0x90, 0xB0, 0xD0, 0xF0):
            reach = rom[position + 1]
            if position + 2 + (reach - 256 if reach & 0x80 else reach) == block:
                return True     # a relative branch
    return False


def caller_box(rom, offset, depth=0):
    """Box left open by the script before it prints the string, if provable.

    Every script site that prints the string must be preceded, in the same
    script, by a string that returns with the same box open, and the stock
    text has to fit that box.
    """
    sites = print_sites(rom, offset)
    if not sites or depth > 3:
        return None
    bank = offset & 0xFF0000
    found = None
    for site in sites:
        box = None
        at = rom.rfind(b"\x02\xBF", max(bank + 0x8000, site - 0x300), site)
        while at >= 0 and box is None:
            target = bank | rom[at + 2] | rom[at + 3] << 8
            try:
                earlier = decode_stock(rom, target)[0] if target & 0x8000 and target != offset else None
            except (Unsupported, ValueError):
                earlier = None
            if earlier is not None and _branched_past(rom, at, site):
                earlier = None          # the other arm of a branch; look further back
            if earlier is not None:
                state = stock_state(earlier)
                if state["terminal"] != "RET":
                    break       # The previous dialogue ended; nothing is open.
                box = state["box"]
                if box is None:
                    box = caller_box(rom, target, depth + 1)
                break
            at = rom.rfind(b"\x02\xBF", max(bank + 0x8000, site - 0x300), at)
        if box is None or found not in (None, box):
            return None
        found = box
    return found


def _choice_caller(rom, offset, depth=0):
    """Box left by the prompt whose choice table leads to the string's script site."""
    bank = offset & 0xFF0000
    found = None
    at = rom.find(b"\x02\xBE", bank + 0x8000, bank + 0x10000)
    while at >= 0:
        if rom[at - 4:at - 2] == b"\x02\xBF" and 2 <= rom[at + 2] <= 7:
            table = bank | rom[at + 4] | rom[at + 5] << 8
            targets = {bank | rom[table + 2 * i] | rom[table + 2 * i + 1] << 8 for i in range(rom[at + 2] + 1)}
            if any(0 <= site - target < 32 and b"\x02\xBF" not in rom[target:site]
                   for site in print_sites(rom, offset) for target in targets):
                prompt = bank | rom[at - 2] | rom[at - 1] << 8
                try:
                    state = stock_state(decode_stock(rom, prompt)[0])
                except (Unsupported, ValueError):
                    return None
                box = state["box"] or caller_box(rom, prompt, depth + 1)
                for start in range(prompt - 1, prompt - 9, -1):
                    # The prompt may be a second entry point; the commands in
                    # front of it open the box for the script's first visit.
                    if box is not None:
                        break
                    try:
                        whole, data = decode_stock(rom, start)
                        head = decode_stock(rom, start, prompt)[0]
                    except (Unsupported, ValueError):
                        continue
                    if start + len(data) > prompt and not stock_state(head + "[RET]")["text"]:
                        box = stock_state(head + "[RET]")["box"]
                if state["terminal"] != "RET" or box is None or found not in (None, box):
                    return None
                found = box
        at = rom.find(b"\x02\xBE", at + 1, bank + 0x10000)
    return found


_linear_caller_box = caller_box


def caller_box(rom, offset, depth=0):
    """Box the calling script left open: the string printed just before, or
    the prompt whose choice leads here. Both kinds of evidence must agree."""
    linear = _linear_caller_box(rom, offset, depth)
    choice = _choice_caller(rom, offset, depth) if depth < 3 else None
    if linear and choice and linear != choice:
        return None
    return linear or choice


def transcribe_entry(source, rom, offset, marker, names, scroll=False):
    """Transcribe a stock string that has a second entry point.

    Scripts start such a string either at its beginning or `marker` bytes
    in. Returns the stream for the whole string and the stream for the
    entry, which begins in the box the first part leaves open.
    """
    if source.count("[::]") != 1:
        raise Unsupported("authored entry point differs")
    first, second = source.split("[::]")
    head = decode_stock(rom, offset, offset + marker)[0]
    tail = decode_stock(rom, offset + marker)[0]
    whole = decode_stock(rom, offset)[0]
    if head + tail != whole:
        raise Unsupported("entry point is not on a command boundary")
    opened = stock_state(STOCK_LOOKUP.sub("x", head) + "[RET]",
                         None if stock_profile(whole)["opens_first"] else caller_box(rom, offset))
    contract = None
    if whole.endswith("[RET]"):
        contracts = {c for c in (prompt_contract(rom, offset), prompt_contract(rom, offset + marker)) if c}
        if len(contracts) > 1:
            raise Unsupported("choice command differs between entries")
        contract = contracts.pop() if contracts else None
    if marker < 5:
        # A redirect needs five bytes. A shorter first part stays in the ROM
        # when it is only commands that the authored string repeats.
        value = lambda text: [(n, int(a, 16) if a else None) for n, a in tokens(text)]
        same = value(first) == value(head) and all(n != 'glyph' for n, _ in tokens(first))
        if not same:
            raise Unsupported("first part is too short to redirect")
        return "", transcribe(second, tail, names, rom, offset + marker, entry_box=opened["box"], contract=contract,
                              entry=True, scroll=scroll)
    full = transcribe(first + second, whole, names, rom, offset, contract=contract)
    entry = transcribe(second, tail, names, rom, offset + marker, entry_box=opened["box"], contract=contract,
                       entry=True)
    return full, entry


def transcribe_frame(source, stock):
    """A stock string that only opens a box: accept an authored size change."""
    stock = re.sub(r"\[SEP:[^\]]*\]", "", stock)
    old, new = list(tokens(stock)), list(tokens(source + "[RET]"))
    value = lambda parts: [(n, tuple(int(x, 16) for x in a.split(",")) if a else None) for n, a in parts]
    if any(n == "glyph" for n, _ in old + new) or len(old) != len(new) or not stock.endswith("[RET]"):
        raise Unsupported("not a box-only string")
    differing = [(a, b) for a, b in zip(value(old), value(new)) if a != b]
    if [a[0] for a, b in differing] != ["SIZ"] or differing[0][1][0] != "SIZ":
        raise Unsupported("box-only string differs in more than its size")
    out, position = [], None
    for name, argument in new:
        if name == "DLG":
            position = pair(argument)
        if name == "SIZ":
            if position is None or not on_screen(position + pair(argument)):
                raise Unsupported("box leaves the screen")
            box = position + pair(argument)
            out.append("[DLG:%02X,%02X][SIZ:%02X,%02X]" % box)
        elif name != "DLG":
            out.append(f"[{name}" + (f":{int(argument, 16):02X}" if argument else "") + "]")
    return "".join(out), box


def transcribe_row(source, stock, names, box):
    """One list row printed into a box another string opened.

    The stock commands around the text are kept; the authored text replaces
    the row and has to fit the box.
    """
    stock = STOCK_LOOKUP.sub("x", stock)
    old = re.fullmatch(r"(\[CLR\])?([^\[\]]+)((?:\[N\]|\[PAL:00\])*)\[(RET|END)\]", stock)
    text = re.sub(r"\[NAM:([0-9A-F]+)\]", lambda m: names[int(m[1], 16)], source.translate(TYPOGRAPHY))
    new = re.fullmatch(r"(\[CLR\])?([^\[\]]+)((?:\[N\]|\[PAL:0\])*)(\[END\])?", text)
    if not old or not new or new[3].replace("[PAL:0]", "[PAL:00]") != old[3] or bool(new[4]) != (old[4] == "END"):
        raise Unsupported("list row differs from the stock row")
    if any(ch not in GLYPHS for ch in new[2]) or len(new[2]) > 2 * box[2]:
        raise Unsupported("list row does not fit its box")
    stream = (old[1] or "") + new[2] + old[3] + f"[{old[4]}]"
    simulate(stream, box)
    return "[BOX:%02X,%02X,%02X,%02X]" % box + stream
