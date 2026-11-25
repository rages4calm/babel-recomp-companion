/* Authored pages. The importer (scripts/gaia_authored_dialogue.py) writes the
 * complete stock-engine command stream for a string that opens its own
 * boxes, together with a signature of the USA bytes it was derived from.
 * This pass applies a row only when that stock string is present, and it
 * checks every page against the box it is printed in. */

static uint32_t GaiaStockSignature(const Rom *stock, uint32_t offset, uint32_t span)
{
    uint32_t value = 0x811c9dc5u;
    for (uint32_t i = 0; i < span; ++i)
        value = (value ^ stock->rom[offset + i]) * 0x01000193u;
    return value;
}

static int GaiaAuthoredHex(const char **text, unsigned digits, char end, unsigned *value)
{
    *value = 0;
    for (unsigned i = 0; i < digits; ++i) {
        const char c = *(*text)++;
        if (c >= '0' && c <= '9')
            *value = *value << 4 | (unsigned)(c - '0');
        else if (c >= 'A' && c <= 'F')
            *value = *value << 4 | (unsigned)(c - 'A' + 10);
        else
            return 0;
    }
    return *(*text)++ == end;
}

/* Parse the literal stream and follow the cursor as the stock renderer
 * would. Text must stay inside a box this string opened itself, or inside
 * the box a leading [BOX:x,y,w,h] says the calling script left open. The
 * stream has to end the way the stock string does. [SCR] in front lets a
 * page scroll, as stock does when a row is printed below the last one.
 * `textless` allows a string that only opens a box, and `shared` is the
 * stock string's own leading print call, which the stream may repeat. */
static int GaiaAuthoredTokens(const char *text, Toks *out, uint8_t terminal, int textless,
                              const uint8_t *shared, const uint8_t *stock, uint32_t span, unsigned top_row)
{
    static const struct { const char *name; uint8_t code; } plain[] = {
        {"[N]", CMD_N}, {"[FIN]", CMD_FIN}, {"[WAI]", 0xd0}, {"[CLR]", 0xce},
        {"[CLD]", 0xc8}, {"[DEF]", 0xd3}, {"[END]", CMD_END}, {"[RET]", CMD_RET},
    };
    static const struct { const char *name; uint8_t code; } operand[] = {
        {"[TPL:", 0xc2}, {"[PAL:", 0xc3}, {"[PAU:", 0xc9}, {"[SFX:", CMD_SFX}, {"[DLY:", 0xd5},
    };
    unsigned width = 0, height = 0, column = 0, row = 0, glyphs = 0;
    int placed = 0;
    /* A box the stock string opens first is the scene's own layout, even
     * where it runs to the edge of the picture. */
    const int own = stock && span > 6 && stock[0] == 0xc1 && stock[3] == 0xc7;
    const int scroll = !strncmp(text, "[SCR]", 5);
    if (scroll)
        text += 5;
    if (!strncmp(text, "[BOX:", 5)) {
        unsigned x, y, w, h;
        text += 5;
        if (!GaiaAuthoredHex(&text, 2, ',', &x) || !GaiaAuthoredHex(&text, 2, ',', &y) ||
            !GaiaAuthoredHex(&text, 2, ',', &w) || !GaiaAuthoredHex(&text, 2, ']', &h) ||
            !x || y < top_row || w < 2 || !h || x + 2 * w > 30 || y + 2 * h > 26)
            return 0;
        width = 2 * w;
        height = h;
    }
    if (!strncmp(text, "[PRT:", 5)) {
        unsigned address;
        text += 5;
        if (!shared || !width || !GaiaAuthoredHex(&text, 6, ']', &address) ||
            address != (unsigned)(shared[0] | shared[1] << 8 | shared[2] << 16))
            return 0;
        Tok call = {.type = T_CMD, .code = CMD_PRT, .ref = -1, .a = {address}};
        Push(out, &call);
    }
    while (*text) {
        Tok token = {.type = T_CMD, .ref = -1};
        unsigned a = 0, b = 0;
        int matched = 0;
        if (*text != '[') {
            token.type = T_GLYPH;
            if ((unsigned char)*text >= 128 || !GlyphFor(&text, &token.code) ||
                !width || ++column > width)
                return 0;
            ++glyphs;
            Push(out, &token);
            continue;
        }
        for (size_t i = 0; !matched && i < sizeof(plain) / sizeof(plain[0]); ++i) {
            const size_t size = strlen(plain[i].name);
            if (strncmp(text, plain[i].name, size))
                continue;
            token.code = plain[i].code;
            text += size;
            matched = 1;
        }
        for (size_t i = 0; !matched && i < sizeof(operand) / sizeof(operand[0]); ++i) {
            if (strncmp(text, operand[i].name, 5))
                continue;
            text += 5;
            if (!GaiaAuthoredHex(&text, 2, ']', &a))
                return 0;
            token.code = operand[i].code;
            token.a[0] = a;
            matched = 1;
        }
        if (!matched && (!strncmp(text, "[DLG:", 5) || !strncmp(text, "[SIZ:", 5))) {
            token.code = text[1] == 'D' ? 0xc1 : 0xc7;
            text += 5;
            if (!GaiaAuthoredHex(&text, 2, ',', &a) || !GaiaAuthoredHex(&text, 2, ']', &b))
                return 0;
            token.a[0] = a;
            token.a[1] = b;
            matched = 1;
        }
        if (!matched && !strncmp(text, "[SEP:", 5)) {
            /* A speaker's two text colours, as the stock speaker templates set them. */
            text += 5;
            if (!GaiaAuthoredHex(&text, 2, ',', &a) || !GaiaAuthoredHex(&text, 4, ']', &b) ||
                (a != 0x11 && a != 0x12))
                return 0;
            token.code = 0xd4;
            token.a[0] = a;
            token.a[1] = b;
            matched = 1;
        }
        if (!matched && !strncmp(text, "[ESC:", 5)) {
            /* Raw tiles: only a run that the stock string prints itself. */
            text += 5;
            token.code = CMD_ESC;
            while (*text != ']') {
                unsigned tile;
                const char separator = text[0] && text[1] ? text[2] : 0;
                if (token.blen >= sizeof(token.bin) || !separator ||
                    !GaiaAuthoredHex(&text, 2, separator, &tile) || !tile)
                    return 0;
                --text;         /* leave the cursor on the next pair or the bracket */
                token.bin[token.blen++] = (uint8_t)tile;
            }
            ++text;
            int present = 0;
            for (uint32_t i = 0; stock && i + token.blen + 2 <= span; ++i)
                present |= stock[i] == CMD_ESC && !memcmp(stock + i + 1, token.bin, token.blen) &&
                           !stock[i + 1 + token.blen];
            if (!present || !width || (column += token.blen) > width)
                return 0;
            ++glyphs;
            matched = 1;
        }
        if (!matched && !strncmp(text, "[BCD:", 5)) {
            text += 5;
            if (!GaiaAuthoredHex(&text, 1, ',', &a) || !GaiaAuthoredHex(&text, 4, ']', &b) ||
                a < 1 || a > 5 || !width || (column += a) > width)
                return 0;
            token.code = 0xc6;
            token.a[0] = a;
            token.a[1] = b;
            ++glyphs;
            matched = 1;
        }
        if (!matched)
            return 0;
        switch (token.code) {
        case CMD_N:
            if (!width || (++row >= height && !scroll))
                return 0;
            if (row >= height)
                row = height - 1;
            column = 0;
            break;
        case CMD_FIN: case 0xce:
            if (!width)
                return 0;
            column = row = 0;
            break;
        case 0xc8:
            width = height = column = row = 0;
            break;
        case 0xc1:
            /* Tile rows 0-4 hold the status display; `top_row` is lower only
             * when the stock string opens a box there itself. */
            if (placed || ((!a || b < top_row) && !(own && a == stock[1] && b == stock[2])))
                return 0;
            placed = 1;
            break;
        case 0xc7:
            /* Two tiles per column and row, one border tile on each side,
             * and a spare tile row for the continuation cursor. */
            if (!placed || a < 2 || !b || out->t[out->n - 1].code != 0xc1)
                return 0;
            if ((!out->t[out->n - 1].a[0] || out->t[out->n - 1].a[0] + 2 * a > 30 ||
                 out->t[out->n - 1].a[1] + 2 * b > 26) &&
                !(own && out->t[out->n - 1].a[0] == stock[1] && out->t[out->n - 1].a[1] == stock[2] &&
                  a == stock[4] && b == stock[5]))
                return 0;
            placed = 0;
            width = 2 * a;
            height = b;
            column = row = 0;
            break;
        case 0xd3:
            width = 26;
            height = 4;
            column = row = 0;
            break;
        case 0xc2:
            if (a >= 8 && a <= 0x0f) {
                width = 26;
                height = kGaiaTemplateRows[a - 8];
                column = row = 0;
            } else if (a > 7 && (a < 0x13 || a > 0x15)) {
                return 0;
            }
            break;
        case 0xc3:
            if (a & ~0x1cu)
                return 0;
            break;
        case 0xc9:
            if (!a)
                return 0;
            break;
        case 0xd5:
            if (a > 9)
                return 0;
            break;
        case CMD_END: case CMD_RET:
            Push(out, &token);
            return !*text && !placed && (glyphs || textless) && token.code == terminal;
        default:
            break;
        }
        Push(out, &token);
    }
    return 0;
}

/* No other label or entry point may begin inside the bytes a patch replaces. */
static int GaiaAuthoredClear(const Structure *structure, const IogPack *pack, int index,
                             uint32_t at, unsigned length)
{
    if (!GaiaPatchDisjoint(pack, at, length))
        return 0;
    for (int i = 0; i < structure->nl; ++i) {
        const Label *other = &structure->l[i];
        if (i != index && other->off - at < length)
            return 0;
        if (other->has_marker && other->off + other->marker != at &&
            other->off + other->marker - at < length)
            return 0;
    }
    return 1;
}

static uint32_t GaiaAuthoredPlace(IogPack *pack, unsigned *fill, const Item *item)
{
    const unsigned size = (unsigned)Encode(NULL, item, NULL);
    const uint32_t address = GaiaUiAddress(pack, fill, size);
    if (address) {
        Encode(NULL, item, pack->banks[pack->nbanks - 1] + *fill);
        *fill += size;
    }
    return address;
}

/* Row forms after the signature:
 *   stream            the string ends or returns as stock does
 *   [JMP]stream       stock ends in a same-bank jump: the text returns and
 *                     the original jump runs from the ROM bank
 *   [MRK]full|entry   stock has a second entry point: `full` replaces the
 *                     string and `entry` the part scripts enter directly.
 *                     `full` is empty when the first part is shorter than
 *                     a redirect; those commands then stay in the ROM. */
static void GaiaApplyAuthored(FILE *file, const Rom *stock, const Structure *structure,
                              IogPack *pack, unsigned *fill)
{
    if (fseek(file, 0, SEEK_SET))
        return;
    char line[8192];
    while (fgets(line, sizeof(line), file)) {
        char *text = strchr(line, '\t');
        if (!text || strncmp(line, "widestring_", 11) || strncmp(text + 1, "[RAW:", 5))
            continue;
        *text = 0;
        const char *cursor = text + 6;
        unsigned signature;
        if (!GaiaAuthoredHex(&cursor, 8, ']', &signature))
            continue;
        text[1 + strcspn(text + 1, "\r\n")] = 0;
        const int jump = !strncmp(cursor, "[JMP]", 5);
        const int entry = !strncmp(cursor, "[MRK]", 5);
        if (jump || entry)
            cursor += 5;
        char *second = entry ? strchr(cursor, '|') : NULL;
        if (entry && !second)
            continue;
        if (second)
            *second++ = 0;
        const int index = FindLabel(structure, line);
        if (index < 0)
            continue;
        const Label *label = &structure->l[index];
        const uint32_t offset = label->off;
        const uint32_t span = StringSpan(stock, offset);
        const unsigned length = jump ? 7 : 5;
        const int prefix = entry && !*cursor;       /* only the entry is redirected */
        if (label->unk16 || span < length || !label->has_marker != !entry ||
            GaiaStockSignature(stock, offset, span) != signature ||
            (!prefix && !GaiaAuthoredClear(structure, pack, index, offset, length)))
            continue;
        uint8_t terminal = stock->rom[offset + span - 1];
        if (jump) {
            if (stock->rom[offset + span - 3] != CMD_JMP)
                continue;
            terminal = CMD_RET;
        } else if (terminal != CMD_END && terminal != CMD_RET) {
            continue;
        }
        if (entry && ((label->marker < 5) != prefix || label->marker + 5 > span ||
                      !GaiaAuthoredClear(structure, pack, index, offset + label->marker, 5)))
            continue;
        Item whole = {0}, part = {0};
        /* A stock string with no text only sets up a box for later strings. */
        Toks original = {0};
        const int decoded = Decode(stock, offset, &original, 0, 0);
        int textless = terminal == CMD_RET && stock->rom[offset] == 0xc1 && decoded;
        unsigned top_row = 6;
        for (int i = 0; i < original.n; ++i) {
            textless &= original.t[i].type != T_GLYPH;
            if (original.t[i].type == T_CMD && original.t[i].code == 0xc1 &&
                original.t[i].a[1] >= 2 && original.t[i].a[1] < top_row)
                top_row = original.t[i].a[1];
        }
        free(original.t);
        const uint8_t *shared = stock->rom[offset] == CMD_PRT && span > 4 ? stock->rom + offset + 1 : NULL;
        if ((prefix || GaiaAuthoredTokens(cursor, &whole.toks, terminal, textless, shared,
                                          stock->rom + offset, span, top_row)) &&
            (!entry || GaiaAuthoredTokens(second, &part.toks, terminal, 0, NULL, stock->rom + offset, span,
                                          top_row))) {
            const uint32_t address = prefix ? 1 : GaiaAuthoredPlace(pack, fill, &whole);
            const uint32_t inner = address && entry ? GaiaAuthoredPlace(pack, fill, &part) : 0;
            if (address && (!entry || inner)) {
                if (prefix) {
                    /* The first part runs from the ROM and falls into the entry. */
                } else if (jump) {
                    const uint8_t patch[7] = {CMD_PRT, (uint8_t)address, (uint8_t)(address >> 8),
                                              (uint8_t)(address >> 16), CMD_JMP,
                                              stock->rom[offset + span - 2], stock->rom[offset + span - 1]};
                    AddPatch(pack, offset, patch, sizeof(patch));
                } else {
                    AddRedirect(pack, offset, CMD_PRT, address, CMD_RET);
                }
                if (entry)
                    AddRedirect(pack, offset + label->marker, CMD_PRT, inner, CMD_RET);
                ++pack->strings_translated;
            }
        }
        free(whole.toks.t);
        free(part.toks.t);
    }
}
