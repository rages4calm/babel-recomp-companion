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
 * would. Text must stay inside a box this string opened itself. */
static int GaiaAuthoredTokens(const char *text, Toks *out)
{
    static const struct { const char *name; uint8_t code; } plain[] = {
        {"[N]", CMD_N}, {"[FIN]", CMD_FIN}, {"[WAI]", 0xd0}, {"[CLR]", 0xce},
        {"[CLD]", 0xc8}, {"[DEF]", 0xd3}, {"[END]", CMD_END},
    };
    static const struct { const char *name; uint8_t code; } operand[] = {
        {"[TPL:", 0xc2}, {"[PAL:", 0xc3}, {"[PAU:", 0xc9}, {"[SFX:", CMD_SFX}, {"[DLY:", 0xd5},
    };
    unsigned width = 0, height = 0, column = 0, row = 0, glyphs = 0;
    int placed = 0;
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
            if (!width || ++row >= height)
                return 0;
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
            /* Tile rows 0-4 hold the status display. */
            if (placed || !a || b < 6)
                return 0;
            placed = 1;
            break;
        case 0xc7:
            /* Two tiles per column and row, one border tile on each side,
             * and a spare tile row for the continuation cursor. */
            if (!placed || a < 2 || !b || out->t[out->n - 1].code != 0xc1 ||
                out->t[out->n - 1].a[0] + 2 * a > 30 || out->t[out->n - 1].a[1] + 2 * b > 26)
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
        case CMD_END:
            Push(out, &token);
            return !*text && !placed && glyphs;
        default:
            break;
        }
        Push(out, &token);
    }
    return 0;
}

static void GaiaApplyAuthored(FILE *file, const Rom *stock, const Structure *structure,
                              IogPack *pack, unsigned *fill)
{
    if (fseek(file, 0, SEEK_SET))
        return;
    char line[4096];
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
        const int index = FindLabel(structure, line);
        if (index < 0)
            continue;
        const Label *label = &structure->l[index];
        const uint32_t offset = label->off;
        const uint32_t span = StringSpan(stock, offset);
        if (label->has_marker || label->unk16 || span < 5 ||
            stock->rom[offset + span - 1] != CMD_END ||
            GaiaStockSignature(stock, offset, span) != signature ||
            !GaiaPatchDisjoint(pack, offset, 5))
            continue;
        int disjoint = 1;
        for (int i = 0; disjoint && i < structure->nl; ++i) {
            const Label *other = &structure->l[i];
            if (i != index)
                disjoint = other->off - offset >= 5 &&
                    (!other->has_marker || other->off + other->marker - offset >= 5);
        }
        if (!disjoint)
            continue;
        Item item = {0};
        if (GaiaAuthoredTokens(cursor, &item.toks)) {
            const unsigned size = (unsigned)Encode(NULL, &item, NULL);
            const uint32_t address = GaiaUiAddress(pack, fill, size);
            if (address) {
                Encode(NULL, &item, pack->banks[pack->nbanks - 1] + *fill);
                AddRedirect(pack, offset, CMD_PRT, address, CMD_RET);
                *fill += size;
                ++pack->strings_translated;
            }
        }
        free(item.toks.t);
    }
}
