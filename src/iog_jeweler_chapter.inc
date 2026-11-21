/* Jeweler's reward list prints one fragment per row within the 16-column
 * box. Keep the amount in the original column and leave award flags and
 * claimed-row palette selection in the actor script. */
static int GaiaJewelerAmount(const Toks *text, int stop)
{
    for (int i = stop - 1; i >= 0; --i) {
        const Tok *token = &text->t[i];
        if (token->type != T_GLYPH)
            return -1;
        if (token->code < 0x20 || token->code > 0x29)
            return token->code == 0xac && i < stop - 1 ? i + 1 : -1;
    }
    return -1;
}

static int GaiaCompileJewelerReward(const Rom *stock, uint32_t offset, Toks *out, const Toks *source)
{
    static const struct { uint32_t label, caller; } rows[] = {
        {0x08d636,0x08cfc6}, {0x08d64a,0x08cfd4}, {0x08d65e,0x08cfe2},
        {0x08d672,0x08cff0}, {0x08d67d,0x08cffe},
    };
    static const uint8_t opener[] = {0xc1,3,0x0b,0xc7,8,7,0xce,0xd2,0,0xca};
    static const uint8_t list_call[] = {0x02,0xbf,0x67,0xd2,0x02,0xbf,0x17,0xd6};
    const unsigned width = 2u * opener[4];
    uint32_t caller = 0;
    for (unsigned i = 0; i < sizeof(rows) / sizeof(rows[0]); ++i)
        if (rows[i].label == offset)
            caller = rows[i].caller;
    const uint8_t print[] = {0x02,0xbf,(uint8_t)offset,(uint8_t)(offset>>8)};
    if (!caller || !GaiaCalledRaw(stock, caller, print, sizeof(print)) ||
        !GaiaCalledRaw(stock, 0x08cfa6, list_call, sizeof(list_call)) ||
        !GaiaCalledRaw(stock, 0x08d617, opener, sizeof(opener)) ||
        source->n < 5 || source->t[source->n - 2].code != CMD_N ||
        source->t[source->n - 1].code != CMD_RET)
        return 0;

    Toks old = {0};
    int accepted = 0;
    if (!Decode(stock, offset, &old, 0, 0) || old.n != (int)width + 3 ||
        old.t[width].code != CMD_N || old.t[width + 1].code != 0xc3 ||
        old.t[width + 1].a[0] != 0 || old.t[width + 2].code != CMD_RET)
        goto done;
    const int old_number = GaiaJewelerAmount(&old, (int)width);
    const int source_number = GaiaJewelerAmount(source, source->n - 2);
    if (old_number < 0 || source_number < 0 ||
        (int)width - old_number != source->n - 2 - source_number)
        goto done;
    for (unsigned i = 0; i < width - old_number; ++i)
        if (old.t[old_number + i].code != source->t[source_number + i].code)
            goto done;
    int label_end = source_number - 1;
    while (label_end && source->t[label_end - 1].code == 0xac)
        --label_end;
    if (label_end < 1 || label_end >= old_number)
        goto done;
    for (int i = 0; i < label_end; ++i) {
        if (source->t[i].type != T_GLYPH)
            goto done;
    }
    for (int i = 0; i < label_end; ++i)
        Push(out, &source->t[i]);
    const Tok space = {.type = T_GLYPH, .code = 0xac};
    for (int i = label_end; i < old_number; ++i)
        Push(out, &space);
    for (int i = old_number; i < old.n; ++i)
        Push(out, &old.t[i]);
    accepted = 1;
done:
    free(old.t);
    return accepted;
}
