/* A few verified chapter boxes keep their original speaker, live number,
 * page waits, and return. The glyphs can wrap inside those same pages. */

static int GaiaStaticChapterGap(const Tok *token)
{
    return (token->type == T_GLYPH && token->code == 0xac) ||
           (token->type == T_CMD && token->code == CMD_N);
}

static int GaiaStaticChapterColumns(const Tok *token, int number)
{
    if (token->type == T_GLYPH)
        return 1;
    if (number && token->type == T_CMD && token->code == 0xc6 &&
        token->a[0] == 3 && token->a[1] == 0x0aac)
        return 3;
    return 0;
}

/* Stop only at a page boundary. A value is allowed once on either side and
 * must remain on the same page. No other executable text command is copied. */
static int GaiaStaticChapterPage(const Toks *tokens, int start, int number, int *values)
{
    *values = 0;
    for (int i = start; i < tokens->n; ++i) {
        const Tok *token = &tokens->t[i];
        if (token->type == T_CMD && (token->code == CMD_FIN || token->code == CMD_END))
            return i > start ? i : -1;
        if (!GaiaStaticChapterGap(token) && !GaiaStaticChapterColumns(token, number))
            return -1;
        if (token->type == T_CMD && token->code == 0xc6 && ++*values != 1)
            return -1;
    }
    return -1;
}

static int GaiaStaticChapterWrap(const Tok *begin, const Tok *end, Toks *out, int height)
{
    enum { Width = 26 };
    int column = 0, row = 1;
    while (begin < end) {
        while (begin < end && GaiaStaticChapterGap(begin))
            ++begin;
        const Tok *word = begin;
        int width = 0;
        while (begin < end && !GaiaStaticChapterGap(begin))
            width += GaiaStaticChapterColumns(begin++, 1);
        if (word == begin)
            break;
        if (width > Width)
            return 0;
        if (column) {
            Tok gap = {.type = T_GLYPH, .code = 0xac, .ref = -1};
            if (column + 1 + width > Width) {
                if (++row > height)
                    return 0;
                gap.type = T_CMD;
                gap.code = CMD_N;
                column = 0;
            } else {
                ++column;
            }
            Push(out, &gap);
        }
        for (; word < begin; ++word)
            Push(out, word);
        column += width;
    }
    return column > 0;
}

static int GaiaStaticChapter(const Rom *stock, uint32_t offset, Toks *out, const Toks *text)
{
    const int score = offset == 0x08b025 || offset == 0x08b052;
    const int cottage = offset == 0x05ddc0;
    const int dive = offset == 0x05b59b;
    if (!score && !cottage && !dive)
        return 0;

    const int height = dive ? 4 : 3;
    const int prefix = dive ? 1 : 2;
    const int returning = !score;
    int first = 0, original = prefix, numbers = 0, ok = 0;
    Toks p = {0};
    if (!Decode(stock, offset, &p, 0, 0) || p.n < prefix + 2 || text->n < 2 ||
        p.t[0].type != T_CMD || p.t[0].code != (dive ? 0xd3 : 0xc2) ||
        p.t[0].a[0] != (dive ? 0 : 0x0a))
        goto done;
    if (score && (p.t[1].type != T_CMD || p.t[1].code != 0xd5 || p.t[1].a[0] != 2))
        goto done;
    if (cottage) {
        if (p.t[1].type != T_CMD || p.t[1].code != 0xc2 || p.t[1].a[0] != 1 ||
            text->t[0].type != T_MARK || text->t[0].code || text->t[0].a[0] != 1)
            goto done;
        first = 1;
    }
    if (p.t[p.n - 1].type != T_CMD || p.t[p.n - 1].code != (returning ? CMD_RET : CMD_END) ||
        (returning && (p.t[p.n - 2].type != T_CMD || p.t[p.n - 2].code != CMD_FIN)))
        goto done;
    for (int i = 0; i < prefix; ++i)
        Push(out, &p.t[i]);
    while (original < p.n - returning && first < text->n) {
        int stock_values, authored_values;
        const int stock_end = GaiaStaticChapterPage(&p, original, score, &stock_values);
        const int end = GaiaStaticChapterPage(text, first, score, &authored_values);
        if (stock_end < 0 || end < 0 || stock_values != authored_values)
            goto done;
        const int final = stock_end + 1 + returning == p.n;
        if (text->t[end].code != (final ? CMD_END : CMD_FIN) ||
            (final && end + 1 != text->n))
            goto done;
        if (!GaiaStaticChapterWrap(text->t + first, text->t + end, out, height))
            goto done;
        numbers += authored_values;
        Push(out, &p.t[stock_end]);
        original = stock_end + 1;
        first = end + 1;
    }
    if (original != p.n - returning || first != text->n || numbers != score)
        goto done;
    if (returning)
        Push(out, &p.t[p.n - 1]);
    ok = 1;
done:
    free(p.t);
    return ok;
}

/* Call after the established dialogue and interface overlays have been
 * allocated. A new bank keeps their existing save-state addresses stable. */
static void GaiaApplyStaticChapter(FILE *file, const Rom *stock, const Structure *structure, IogPack *pack)
{
    if (fseek(file, 0, SEEK_SET))
        return;
    unsigned fill = kIogVirtualBankSize;
    char line[4096];
    while (fgets(line, sizeof(line), file)) {
        if (strncmp(line, "widestring_", 11))
            continue;
        char *text = strchr(line, '\t');
        if (!text)
            continue;
        *text++ = 0;
        const int li = FindLabel(structure, line);
        if (li < 0)
            continue;
        const Label *label = &structure->l[li];
        const uint32_t off = label->off;
        if (off != 0x05b59b && off != 0x05ddc0 && off != 0x08b025 && off != 0x08b052)
            continue;
        if (label->has_marker || label->unk16 || StringSpan(stock, off) < 5 ||
            !GaiaPatchDisjoint(pack, off, 5))
            continue;
        int overlap = 0;
        for (int i = 0; i < structure->nl && !overlap; ++i) {
            const Label *other = &structure->l[i];
            overlap = i != li && (other->off - off < 5 ||
                (other->has_marker && other->off + other->marker - off < 5));
        }
        if (overlap)
            continue;
        text[strcspn(text, "\r\n")] = 0;
        if (!strncmp(text, "[LAY]", 5))
            text += 5;
        Toks authored = {0};
        Item item = {0};
        if (GaiaDialogue(text, &authored) && GaiaStaticChapter(stock, off, &item.toks, &authored)) {
            const unsigned size = (unsigned)Encode(NULL, &item, NULL);
            const uint32_t addr = GaiaUiAddress(pack, &fill, size);
            if (addr) {
                Encode(NULL, &item, pack->banks[pack->nbanks - 1] + fill);
                AddRedirect(pack, off, CMD_PRT, addr, CMD_RET);
                fill += size;
                ++pack->strings_translated;
            }
        }
        free(item.toks.t);
        free(authored.t);
    }
}
