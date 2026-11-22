/* Long late-game conversations use named speakers outside the stock
 * template range. Restore their stock role only at the approved turn
 * boundary, then fit complete turns without changing controls. */
static int GaiaBranchBeginsWith(const Tok *tokens, int count, const char *words)
{
    for (int i = 0; *words; ++i) {
        uint8_t glyph;
        if (i == count || tokens[i].type != T_GLYPH ||
            !GlyphFor(&words, &glyph) || tokens[i].code != glyph)
            return 0;
    }
    return 1;
}

static int GaiaCompileBranchDialogue(const Rom *stock, uint32_t offset, Toks *out,
                                     const Toks *source)
{
    static const GaiaReturningChapterRule rules[] = {
        {0x07cf75, 0x07cf75, 0, 0x0b, 0xff, CMD_END},
        {0x089b8b, 0x089b8b, 0, 0xd3, 0xff, CMD_END},
        {0x098903, 0x098903, 0, 0x09, 0xff, CMD_END},
        {0x0989a2, 0x0989a2, 0, 0x0b, 0xff, CMD_END},
    };
    static const struct { uint32_t offset; const char *words; uint8_t voice; } omitted[] = {
        {0x089b8b, "Will...", 2},
        {0x089b8b, "I'm dreaming", 2},
        {0x098903, "Will. It's me", 4},
        {0x0989a2, "The Tower of Babel", 4},
        {0x0989a2, "Olman:", 4},
    };
    for (unsigned r = 0; r < sizeof(rules) / sizeof(*rules); ++r) {
        if (rules[r].offset != offset)
            continue;
        Toks text = {0};
        for (int i = 0; i < source->n; ++i) {
            if (!i || source->t[i - 1].code == CMD_FIN) {
                for (unsigned v = 0; v < sizeof(omitted) / sizeof(*omitted); ++v) {
                    if (omitted[v].offset != offset ||
                        !GaiaBranchBeginsWith(source->t + i, source->n - i, omitted[v].words))
                        continue;
                    const Tok voice = {.type = T_MARK, .a = {omitted[v].voice}, .ref = -1};
                    Push(&text, &voice);
                }
            }
            Push(&text, &source->t[i]);
        }
        const int accepted = GaiaCompileReturningRule(stock, &rules[r], out, &text, 0);
        free(text.t);
        return accepted;
    }
    return 0;
}

/* Gem counts the player's jewels in the same box as the opening greeting.
 * The localized sentence can move the number within that box, but the
 * displayed value must remain the original two-digit BCD read. */
static int GaiaCompileJewelerCount(const Rom *stock, uint32_t offset, Toks *out,
                                   const Toks *source)
{
    static const uint8_t caller[] = {2, 0xbf, 0x94, 0xd0, 0xad, 0xb0, 0x0a, 0xf0, 4,
                                    2, 0xbf, 0xc8, 0xd0};
    static const uint8_t opener[] = {0xd3};
    if (offset != 0x08d0c8 || source->n < 4 ||
        !GaiaCalledRaw(stock, 0x08cec9, caller, sizeof(caller)) ||
        !GaiaCalledRaw(stock, 0x08d094, opener, sizeof(opener)) ||
        source->t[source->n - 2].code != CMD_FIN ||
        source->t[source->n - 1].code != CMD_RET)
        return 0;

    Toks original = {0};
    Tok number = {0};
    int accepted = 0;
    if (!Decode(stock, offset, &original, 0, 0) || original.n < 4 ||
        original.t[original.n - 2].code != CMD_FIN ||
        original.t[original.n - 1].code != CMD_RET)
        goto done;
    for (int i = 0; i < original.n - 2; ++i) {
        const Tok *token = &original.t[i];
        if (GaiaPageText(token))
            continue;
        if (number.code || token->type != T_CMD || token->code != 0xc6 ||
            token->a[0] != 2 || token->a[1] != 0x0ab0)
            goto done;
        number = *token;
    }
    if (!number.code)
        goto done;

    int digits = 0, columns = 0, rows = 1;
    for (int i = 0; i < source->n - 2; ++i) {
        const Tok *token = &source->t[i];
        if (token->type == T_GLYPH) {
            ++columns;
        } else if (token->type == T_CMD && token->code == CMD_N) {
            if (!columns || ++rows > 4)
                goto done;
            columns = 0;
        } else if (token->type == T_CMD && token->code == 0xc3 && !token->a[0] &&
                   i + 2 < source->n - 2) {
            const Tok *value = token + 1, *restore = token + 2;
            if (digits++ || value->type != T_CMD || value->code != number.code ||
                value->a[0] != number.a[0] || value->a[1] != number.a[1] ||
                restore->type != T_CMD || restore->code != 0xc3 || restore->a[0] != 4)
                goto done;
            columns += number.a[0];
            Push(out, &number);
            i += 2;
            if (columns > 26)
                goto done;
            continue;
        } else {
            goto done;
        }
        if (columns > 26)
            goto done;
        Push(out, token);
    }
    if (digits != 1 || !columns)
        goto done;
    Push(out, &original.t[original.n - 2]);
    Push(out, &original.t[original.n - 1]);
    accepted = 1;
done:
    free(original.t);
    return accepted;
}
