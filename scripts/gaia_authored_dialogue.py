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
# GaiaLabs speaker themes. Stock has a counterpart for three recurring voices;
# the place themes have none and use the plain narration colours.
THEMES = {theme: None for theme in range(0x16, 0x25)}
THEMES.update({0x21: 0x02, 0x22: 0x01, 0x23: 0x04, 0x24: 0x04})
GLYPHS = frozenset(" 0123456789.,\":ABCDEFGHIJKLMNOPQRSTUVWXYZ!/*-()"
                   "abcdefghijklmnopqrstuvwxyz;?'")
# The stock font has no ellipsis, closing-quote or heart tile.
TYPOGRAPHY = str.maketrans({"…": "...", "ˮ": '"', "♥": " "})
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


def on_screen(box):
    left, top, right, bottom = box_rect(box)
    # One spare tile row below the border holds the continuation cursor.
    # Tile rows 0-4 hold the status display; closing a box there would erase it.
    return left >= 1 and top >= 5 and right <= 30 and bottom <= 26 and box[2] >= 2 and box[3] >= 1


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


def simulate(stream, box=None):
    """Run a stock-engine command stream. Returns a summary of what it did.

    `box` is the box the calling script left open, if any.

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
        elif name == "BCD":
            digits = int(argument.split(",")[0])
            if box is None:
                raise Unsupported("text outside a known box")
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
                raise Unsupported("page exceeds its box")
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
            if not on_screen(opened):
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
    if "[::]" in plain or "[JMP:" in plain or "[PRT:" in plain or "[ADR:" in plain or "[ESC:" in plain:
        raise Unsupported("stock string has entry points or references")
    plain = re.sub(r"\[SEP:[^\]]*\]", "", plain)
    # Stock rows can scroll and reuse an open box; only its commands matter.
    profile = {"first_speaker": None, "pauses": [], "sfx": set(), "speakers": [], "waits": 0, "opens_first": None,
               "trailing_palette": False, "terminal": None}
    previous = None
    for name, argument in tokens(plain):
        if name in ("glyph", "BCD") and profile["opens_first"] is None:
            profile["opens_first"] = False
        elif name == "DEF" or name == "SIZ" or (name == "TPL" and number(argument) in STOCK_BOXES):
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
           0x10: ("bottom", 5), 0x12: ("top", 5)}
_TEMPLATE = {("top", rows): 0x07 + rows for rows in range(1, 5)}
_TEMPLATE.update({("bottom", rows): 0x0B + rows for rows in range(1, 5)})
_TEMPLATE.update({("top", 5): 0x12, ("bottom", 5): 0x10})


def fit_rows(source, names):
    """Expand names and refit pages whose rows no longer fit their box.

    The stock font has no ellipsis tile, so an authored row can grow past 26
    columns once names and ellipses are spelled out. Such a page is wrapped
    again, and its box template is raised when it needs another row.
    """
    def name(match):
        value = int(match[1], 16)
        if value >= len(names):
            raise Unsupported("name entry")
        return names[value]

    source = re.sub(r"\[NAM:([0-9A-F]+)\]", name, source.translate(TYPOGRAPHY))
    parts = [part for part in TOKEN.split(source) if part]
    out, page = [], []
    family = rows = None

    def flush():
        nonlocal family, rows
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
                opener = index
            elif command == "DEF":
                family, rows, opener = "bottom", 4, index
            elif command == "SIZ":
                family, rows, opener = None, pair(argument)[1], None
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
                elif not part.startswith("["):
                    total += len(part)
            return total
        if rows is None or (all(width(line) <= COLUMNS for line in lines) and len(lines) <= rows):
            out.extend(head + body + tail)
            return
        needed = lines
        if any(width(line) > COLUMNS for line in lines):
            text = []
            for line in lines:
                if any(part.startswith("[") for part in line):
                    raise Unsupported("wide row with inline commands")
                row = "".join(line)
                if row != row.strip() or "  " in row:
                    raise Unsupported("wide row with authored spacing")
                if row:
                    text.append(row)
            words = " ".join(text).split(" ")
            wrapped = [words[0]]
            for word in words[1:]:
                if len(wrapped[-1]) + 1 + len(word) <= COLUMNS:
                    wrapped[-1] += " " + word
                else:
                    wrapped.append(word)
            if any(len(row) > COLUMNS for row in wrapped):
                raise Unsupported("word wider than the box")
            needed = [[row] for row in wrapped]
        if len(needed) > rows:
            if family is None or len(needed) > 5:
                raise Unsupported("page needs more rows than its box")
            rows = len(needed)
            template = f"[TPL:{_TEMPLATE[family, rows]:X}]"
            if opener is None:
                head.append(template)
            else:
                head[opener] = template
        out.extend(head)
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


def _choice_page(source, options, skip, final_box, stock_rows, plain):
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
    if len(text) > skip:
        sentences = re.split(r'(?<=[.!?"])\s+', " ".join(text))
        keep = []
        while sentences and len(_wrap(" ".join(sentences[-1:] + keep))) <= skip:
            keep.insert(0, sentences.pop())
        if keep or not skip:
            early, text = _wrap(" ".join(sentences)), _wrap(" ".join(keep)) if keep else []
        else:
            early, text = text[:len(text) - skip], text[len(text) - skip:]
    out = before
    family = "top" if final_box[1] < 12 else "bottom"
    while early:
        shown, early = early[:4], early[4:]
        out += f"[TPL:{_TEMPLATE[family, len(shown)]:X}]" + "".join(speaker + presentation) + "[N]".join(shown) + "[FIN]"
        presentation = []
    text += [""] * (skip - len(text))
    return out + "[BOX]" + "".join(speaker + presentation) + "[N]".join(text + choices)


def transcribe(source, stock, names, rom=None, offset=None, entry_box=None, contract=None):
    """Return the stock-engine stream for one authored string.

    `source` is the GaiaLabs declaration body, `stock` the decoded USA string
    in the same notation. With `rom` and `offset`, strings that share a box
    with their calling script are supported as well. The result starts with
    a `[BOX:x,y,w,h]` tag when the string prints into an inherited box.
    `entry_box` and `contract` supply the open box and the script's choice
    command for a second entry point, which has no script site of its own.
    Raises Unsupported when the result cannot be shown to keep the stock
    string's behaviour.
    """
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
    else:
        raise Unsupported("stock string returns in the middle of a page")
    source = fit_rows(source, names)
    if "[::]" in source:
        raise Unsupported("authored entry point")
    if mode == "end":
        # A close after the final END never runs: END already closes the box.
        source = re.sub(r"\[END\](?:\[CLD\])+$", "[END]", source)
        if not source.endswith("[END]"):
            raise Unsupported("authored string does not end the dialogue")
    elif "[END]" in source or "[RET]" in source:
        raise Unsupported("authored string ends a dialogue the stock string continues")
    elif mode == "closed":
        if not source.endswith("[CLD]"):
            raise Unsupported("authored string leaves its box open")
    elif mode == "page":
        if not source.endswith("[FIN]"):
            raise Unsupported("authored string returns in the middle of a page")
        source += "[BOX]"
    else:
        source = _choice_page(source, contract[0], contract[1], final["box"], final["row"] + 1 - contract[1],
                              "[PAL:00]" in stock[stock.rfind("[FIN]") + 1:])
    if mode != "end":
        source += "[RET]"

    out = []
    box = inherited
    # An inherited box keeps the caller's colours until the string names a speaker.
    speaker = active = _INHERIT if inherited else None
    delay = sound = None          # requested typing delay and per-character sound
    shown_delay = shown_sound = None
    fresh = False                 # a delay or sound was requested since the last text
    page_text = False             # a glyph was printed since the page began
    position = None
    parts = list(tokens(source))

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
        if not on_screen(opened):
            raise Unsupported("box leaves the screen")
        if box is not None and not covers(opened, box):
            out.append("[CLD]")
        out.append(command)
        if speaker is _INHERIT:
            # Opening a box drops the caller's colours. Stock names its
            # speaker itself in that case; an authored string may not.
            speaker = profile["first_speaker"]
        box = opened
        # Opening a box restores the default colours, sound and typing speed.
        active = shown_delay = shown_sound = None
        if not fresh:
            delay = sound = None
        page_text = False

    def select_speaker():
        nonlocal active, shown_delay, shown_sound, fresh
        if speaker != active:
            if speaker is None:
                out.append("[PAL:00][SFX:10]")
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
                speaker = THEMES.get(template, template)
                sound = None
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
    result = simulate(stream, inherited)
    if result["terminal"] != ("RET" if profile["terminal"] == "JMP" else profile["terminal"]) or not result["glyphs"]:
        raise Unsupported("transcription lost its terminal or text")
    if (mode == "end" and inherited is None and not result["opens_first"]) or result["box"] != \
            (final["box"] if mode in ("page", "choice") else None if mode == "closed" else result["box"]):
        raise Unsupported("transcription leaves a different box")
    if mode == "choice":
        options, skip = contract
        rows = result["rows"]
        if len(rows) != final["row"] + 1 or any(not row.startswith(" ") or not row.strip() for row in rows[skip:]):
            raise Unsupported("choices are not on the rows the script expects")
    if mode == "closed" and not result["waits"] and result["pauses"] != profile["pauses"]:
        raise Unsupported("timed string changes its timeline")
    if inherited:
        stream = "[BOX:%02X,%02X,%02X,%02X]" % inherited + stream
    if profile["terminal"] == "JMP":
        stream = "[JMP]" + stream
    # END waits for input, so the pauses only pace a page the player dismisses.
    if any(value not in profile["pauses"] and value > 0x40 for value in result["pauses"]):
        raise Unsupported("long pause absent from the stock string")
    if not result["sfx"] <= profile["sfx"] | {0x00, 0x10}:
        raise Unsupported("sound outside the stock string")
    return stream


# ---- stock ROM strings -----------------------------------------------------

_ARGUMENTS = {0xC0: 0, 0xC1: 2, 0xC2: 1, 0xC3: 1, 0xC4: 0, 0xC5: 4, 0xC6: 4, 0xC7: 2, 0xC8: 0,
              0xC9: 1, 0xCA: 0, 0xCB: 0, 0xCC: 1, 0xCD: 3, 0xCE: 0, 0xCF: 0, 0xD0: 0, 0xD1: 2,
              0xD2: 1, 0xD3: 0, 0xD4: 3, 0xD5: 1, 0xD6: 1, 0xD7: 1}
_NAMES = {0xC0: "END", 0xC2: "TPL", 0xC3: "PAL", 0xC4: "HLT", 0xC5: "ADR", 0xC8: "CLD", 0xC9: "PAU",
          0xCA: "RET", 0xCB: "N", 0xCC: "SKP", 0xCD: "PRT", 0xCE: "CLR", 0xCF: "FIN", 0xD0: "WAI",
          0xD1: "JMP", 0xD2: "SFX", 0xD3: "DEF", 0xD4: "SEP", 0xD5: "DLY", 0xD6: "LU1", 0xD7: "LU2"}
_FONT = {0x2A: ".", 0x2B: ",", 0x2D: '"', 0x2F: ":", 0x4F: "!", 0x6B: "/", 0x6C: "*", 0x6D: "-",
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
        if name in ("glyph", "BCD"):
            column += int(argument[0]) if name == "BCD" else 1
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
        elif name in ("PRT", "ADR", "ESC", "::"):
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


def _choice_caller(rom, offset):
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
                box = state["box"] or caller_box(rom, prompt, 3)
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
    choice = _choice_caller(rom, offset) if depth < 3 else None
    if linear and choice and linear != choice:
        return None
    return linear or choice


def transcribe_entry(source, rom, offset, marker, names):
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
        same = [(n, int(a, 16)) for n, a in tokens(first)] == [(n, int(a, 16)) for n, a in tokens(head)]             if all(a and n != "glyph" for n, a in list(tokens(first)) + list(tokens(head))) else False
        if not same:
            raise Unsupported("first part is too short to redirect")
        return "", transcribe(second, tail, names, rom, offset + marker, entry_box=opened["box"], contract=contract)
    full = transcribe(first + second, whole, names, rom, offset, contract=contract)
    entry = transcribe(second, tail, names, rom, offset + marker, entry_box=opened["box"], contract=contract)
    return full, entry
