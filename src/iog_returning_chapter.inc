/* These non-choice fragments have verified stock window and caller layouts.
 * Reshape prose within the original speaking turns and leave their controls. */
typedef struct {
    uint32_t offset, window, caller;
    uint8_t opener, implicit_voice, source_terminal;
} GaiaReturningChapterRule;

static const GaiaReturningChapterRule kGaiaReturningChapter[] = {
    /* Seaside key notification begins under the key-use actor's D3 box. */
    {0x0391d9, 0x039179, 0x039174, 0xd3, 2, CMD_END},
    {0x04ca41, 0x04ca41, 0, 0x0a, 0xff, CMD_END},
    {0x04ce4a, 0x04ce4a, 0, 0x0b, 0xff, CMD_END},
    /* Lily's reply shares the stock Yes/No prompt's TPL:B window. */
    {0x04e778, 0x04e6e6, 0x04e61e, 0x0b, 0xff, CMD_END},
    {0x04ea77, 0x04ea77, 0, 0xd3, 0xff, CMD_RET},
    {0x05cbf7, 0x05cbf7, 0, 0x0b, 0xff, CMD_END},
    {0x068ea9, 0x068ea9, 0, 0xd3, 0xff, CMD_END},
    {0x069377, 0x069377, 0, 0xd3, 0xff, CMD_RET},
    /* Euro and Dao replies retain the speaker and geometry of their prompt. */
    {0x07ce54, 0x07ce28, 0x07ce1d, 0xd3, 0xff, CMD_END},
    {0x08b21a, 0x08b1ef, 0x08b187, 0xd3, 0xff, CMD_RET},
    {0x08c7c9, 0x08c7c9, 0, 0xd3, 0, CMD_RET},
    /* The Jeweler's greeting opens the box before the first-tier cascade. */
    {0x08d2d0, 0x08d094, 0x08d017, 0xd3, 0xff, CMD_RET},
    {0x08d31a, 0x08d094, 0x08d020, 0xd3, 0xff, CMD_RET},
    {0x099a91, 0x099a91, 0, 0x0a, 0xff, CMD_END},
    {0x0acf4a, 0x0acf4a, 0, 0xd3, 0, CMD_END},
};

static int GaiaCompileReturningRule(const Rom *stock, const GaiaReturningChapterRule *rule,
                                    Toks *out, const Toks *source, int source_only_wait)
{
    if (source->n < 2 || source->t[source->n - 1].type != T_CMD ||
        source->t[source->n - 1].code != rule->source_terminal)
        return 0;

    const int default_layout = rule->opener == 0xd3 || rule->opener == 0xc1;
    const Tok opener = {.type = T_CMD, .code = default_layout ? 0xd3 : 0xc2,
                        .a = {default_layout ? 0 : rule->opener}, .ref = -1};
    const uint8_t window[] = {opener.code, (uint8_t)opener.a[0]};
    const uint8_t caller[] = {0x02, 0xbf, (uint8_t)rule->offset, (uint8_t)(rule->offset >> 8)};
    if (rule->opener == 0xc1) {
        static const uint8_t letter_window[] = {0xc1, 3, 0x11, 0xc7, 0x0d, 4};
        if (!GaiaCalledRaw(stock, rule->window, letter_window, sizeof(letter_window)))
            return 0;
    } else if (!GaiaCalledRaw(stock, rule->window, window, default_layout ? 1 : 2)) {
        return 0;
    }
    if (rule->caller && !GaiaCalledRaw(stock, rule->caller, caller, sizeof(caller)))
        return 0;

    Toks original = {0}, authored = {0}, turn = {0}, rendered = {0};
    int ok = 0;
    if (!Decode(stock, rule->offset, &original, 0, 0) || original.n < 2)
        goto done;
    const Tok terminal = original.t[original.n - 1];
    const int returning = terminal.code == CMD_RET;
    if ((returning && original.t[original.n - 2].code != CMD_FIN) ||
        (!returning && terminal.code != CMD_END))
        goto done;
    original.n -= returning;

    if (rule->implicit_voice != 0xff && source->t[0].type != T_MARK) {
        const Tok voice = {.type = T_MARK, .a = {rule->implicit_voice}, .ref = -1};
        Push(&authored, &voice);
    }
    for (int i = 0; i < source->n - 1; ++i) {
        const Tok *token = &source->t[i];
        if (token->type != T_GLYPH && token->code == 0xc3)
            continue; /* Retain the stock palette changes. */
        if (source_only_wait && token->type == T_CMD && token->code == 0xd0 &&
            i > 0 && source->t[i - 1].type == T_GLYPH &&
            !strcmp(GlyphText(source->t[i - 1].code), ",") &&
            source->t[i + 1].type == T_CMD && source->t[i + 1].code == CMD_N) {
            source_only_wait = 0;
            continue; /* These two stock scripts have no mid-line input gate. */
        }
        if (!GaiaPageText(token) &&
            !(token->type == T_CMD && token->code == CMD_FIN) &&
            !(token->type == T_MARK && !token->code && GaiaSpeakerTemplate(token->a[0])))
            goto done;
        Push(&authored, token);
    }
    if (source_only_wait)
        goto done;
    if (authored.n && authored.t[authored.n - 1].type == T_CMD &&
        authored.t[authored.n - 1].code == CMD_FIN)
        --authored.n;
    Push(&authored, &original.t[original.n - 1]);

    int start = 0, first = 0;
    while (start < original.n && first < authored.n) {
        int stock_voice, source_voice;
        const int stop = GaiaManualTurnEnd(&original, start, 0, &stock_voice);
        const int end = GaiaManualTurnEnd(&authored, first, 1, &source_voice);
        if (stop <= start || end <= first || stock_voice != source_voice ||
            (stop == original.n) != (end == authored.n))
            goto done;

        /* Supply the same layout to the fitter on every returning turn;
         * the synthetic token is never added to the runtime bytecode. */
        turn.n = 0;
        rendered.n = 0;
        Push(&turn, &opener);
        for (int i = start; i < stop; ++i)
            Push(&turn, &original.t[i]);
        const Toks words = {.t = authored.t + first, .n = end - first};
        if (!GaiaStockManualPages(&turn, &rendered, &words))
            goto done;
        for (int i = 1; i < rendered.n; ++i)
            Push(out, &rendered.t[i]);
        start = stop;
        first = end;
    }
    if (start == original.n && first == authored.n) {
        if (returning)
            Push(out, &terminal);
        ok = 1;
    }
done:
    free(original.t);
    free(authored.t);
    free(turn.t);
    free(rendered.t);
    return ok;
}

static int GaiaCompileReturningChapter(const Rom *stock, uint32_t offset, Toks *out,
                                       const Toks *source)
{
    for (unsigned i = 0; i < sizeof(kGaiaReturningChapter) / sizeof(*kGaiaReturningChapter); ++i)
        if (kGaiaReturningChapter[i].offset == offset)
            return GaiaCompileReturningRule(stock, &kGaiaReturningChapter[i], out, source, 0);
    return 0;
}

/* Run after the initial returning and paired passes so earlier redirects
 * keep their exact payload locations. */
static int GaiaCompileManualChapter(const Rom *stock, uint32_t offset, Toks *out,
                                     const Toks *source)
{
    static const GaiaReturningChapterRule rules[] = {
        {0x04a81f, 0x04a81f, 0, 0x0e, 0xff, CMD_END},  /* Jackal's mark */
        {0x04c8fb, 0x04c8fb, 0, 0x0b, 0xff, CMD_END},  /* Edward Castle maid */
        {0x04d4b1, 0x04d4b1, 0x04d329, 0xc1, 0xff, CMD_RET}, /* Kara's letter */
        {0x05ec0e, 0x05eb4f, 0x05e8e9, 0xd3, 0, CMD_END},     /* Nazca left foot */
    };
    if (offset == 0x05ec0e) {
        static const uint8_t puzzle[] = {2, 0xbf, 0x4f, 0xeb, 2, 0xbf, 0x94, 0xeb,
            2, 0xbe, 4, 0, 0xd9, 0xe8, 0xe3, 0xe8, 0xe3, 0xe8, 0xe3, 0xe8,
            0xe9, 0xe8, 0xe3, 0xe8};
        if (!GaiaCalledRaw(stock, 0x05e8cb, puzzle, sizeof(puzzle)))
            return 0;
    }
    for (unsigned i = 0; i < sizeof(rules) / sizeof(*rules); ++i)
        if (rules[i].offset == offset)
            return GaiaCompileReturningRule(stock, &rules[i], out, source, i < 2);
    return 0;
}
