/* Called dialogue fragments can use the dimensions of a verified stock
 * caller. Keep its box, palette, print calls, and pre-existing waits. */

typedef struct {
    uint32_t offset;
    unsigned char prefix, height, waits, terminal;
    uint32_t print;
} GaiaCalledChapterCase;

static const GaiaCalledChapterCase kGaiaCalledChapter[] = {
    {0x069612, 4, 3, 1, CMD_END, 0x069705},
    {0x069705, 0, 3, 1, CMD_RET, 0},
    {0x08ded3, 1, 4, 3, CMD_RET, 0x08de96},
    {0x08e2f8, 1, 4, 3, CMD_RET, 0x08de96},
    {0x08e98a, 1, 4, 1, CMD_RET, 0x08de96},
    {0x08ebdf, 0, 4, 2, CMD_RET, 0},
    {0x08ec66, 0, 4, 2, CMD_RET, 0},
    {0x08ecea, 0, 4, 2, CMD_RET, 0},
    {0x08edf2, 0, 4, 2, CMD_RET, 0},
    {0x08ee8b, 0, 4, 2, CMD_RET, 0},
};

static int GaiaCalledRaw(const Rom *stock, uint32_t offset, const uint8_t *bytes, size_t size)
{
    return offset < stock->size && size <= stock->size - offset &&
           !memcmp(stock->rom + offset, bytes, size);
}

static int GaiaCalledChapterContext(const Rom *stock, const GaiaCalledChapterCase *rule)
{
    if (rule->offset >= 0x08ebdf) {
        /* D3 / CE / D5 / C5 follows the selected stock ability table entry.
         * Even though the selected fragment returns, the caller then waits
         * and ends. The fragment must not insert a final wait of its own. */
        static const uint8_t caller[] = {0xd3, 0xce, 0xd5, 2, 0xc5, 0xd3, 0xeb, 0xac, 0x0a, CMD_END};
        static const uint8_t table[] = {0xdf, 0xeb, 0x66, 0xec, 0xea, 0xec, 0x6d, 0xed, 0xf2, 0xed, 0x8b, 0xee};
        return GaiaCalledRaw(stock, 0x08eb85, caller, sizeof(caller)) &&
               GaiaCalledRaw(stock, 0x08ebd3, table, sizeof(table));
    }
    if (rule->offset >= 0x08ded3) {
        static const uint8_t print[] = {CMD_PRT, 0x96, 0xde, 0x88};
        static const uint8_t opener[] = {0xd3, 0xce};
        return GaiaCalledRaw(stock, rule->offset, print, sizeof(print)) &&
               GaiaCalledRaw(stock, 0x08de96, opener, sizeof(opener));
    }
    /* The three Seaside Palace voice callers all use the same TPL:A window
     * (13 by 3) and state the same speaker before printing the interruption. */
    static const uint8_t print[] = {0xc2, 0x0a, 0xc2, 0, CMD_PRT, 5, 0x97, 0x86, 0xc3, 0};
    return GaiaCalledRaw(stock, 0x0695af, print, sizeof(print)) &&
           GaiaCalledRaw(stock, 0x069612, print, sizeof(print)) &&
           GaiaCalledRaw(stock, 0x069672, print, sizeof(print));
}

static int GaiaCalledChapter(const Rom *stock, const GaiaCalledChapterCase *rule,
                             Toks *out, const Toks *text)
{
    const int start = rule->print != 0;
    if (text->n <= start + 1 || text->t[text->n - 1].type != T_CMD ||
        text->t[text->n - 1].code != rule->terminal ||
        (start && (text->t[0].type != T_CMD || text->t[0].code != CMD_PRT ||
                   text->t[0].a[0] != rule->print)) ||
        !GaiaCalledChapterContext(stock, rule))
        return 0;

    Toks original = {0};
    int ok = 0;
    if (!Decode(stock, rule->offset, &original, 0, 0) ||
        original.n <= rule->prefix + 1 || original.t[original.n - 1].code != rule->terminal)
        goto done;
    const int final_wait = original.t[original.n - 2].code == CMD_FIN;
    if (final_wait != (text->t[text->n - 2].type == T_CMD &&
                       text->t[text->n - 2].code == CMD_FIN))
        goto done;

    int waits = 0;
    const int stop = original.n - 1 - final_wait;
    for (int i = rule->prefix; i < stop; ++i) {
        const Tok *token = &original.t[i];
        if (!GaiaPageText(token)) {
            if (token->type != T_CMD || token->code != CMD_FIN)
                goto done;
            ++waits;
        }
    }
    if (waits + final_wait != rule->waits)
        goto done;
    const int end = text->n - 1 - final_wait;
    for (int i = start; i < end; ++i) {
        const Tok *token = &text->t[i];
        if (!GaiaPageText(token) && (token->type != T_CMD || token->code != CMD_FIN))
            goto done;
    }
    for (int i = 0; i < rule->prefix; ++i)
        Push(out, &original.t[i]);
    const int before = out->n;
    if (!GaiaWrapPage(text->t + start, text->t + end, out, 26, rule->height, 1))
        goto done;
    for (int i = before; i < out->n; ++i)
        waits -= out->t[i].type == T_CMD && out->t[i].code == CMD_FIN;
    if (waits)
        goto done;
    for (int i = stop; i < original.n; ++i)
        Push(out, &original.t[i]);
    ok = 1;
done:
    free(original.t);
    return ok;
}

static int GaiaCompileCalledChapter(const Rom *stock, uint32_t off, Toks *out, const Toks *source)
{
    for (size_t i = 0; i < sizeof(kGaiaCalledChapter) / sizeof(*kGaiaCalledChapter); ++i)
        if (kGaiaCalledChapter[i].offset == off)
            return GaiaCalledChapter(stock, &kGaiaCalledChapter[i], out, source);
    return 0;
}
