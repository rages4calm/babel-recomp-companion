static int GaiaStockDefaultDialogue(const Rom *rom)
{
    static const uint8_t opener[] = {
        0xa9, 0x0d, 0, 0x8d, 0x82, 9, 0xa9, 4, 0, 0x8d, 0x84, 9,
        0xa9, 3, 0, 0x8d, 0x7a, 9, 0xa9, 0x11, 0, 0x8d, 0x7c, 9,
        0xeb, 0x4a, 0x4a, 0x18, 0x6d, 0x7a, 9, 0x18, 0x6d, 0x7a, 9,
        0xaa, 0x8d, 0x98, 9, 0x4c, 0x53, 0xe4
    };
    return GaiaCalledRaw(rom, 0x03e6f7, opener, sizeof(opener));
}

/* Engine-facing closes and pauses follow the verified stock strings even
 * where the approved cards end with a different text command. */
static int GaiaTimedNoticeRules(uint32_t offset, const Toks *stock, const Toks *source,
                                Toks *out)
{
    const int lance = offset == 0x04b75d;
    if (stock->n < 6 || source->n < 4)
        return 0;
    const int tail = stock->n - (lance ? 4 : 2);
    const Tok *tokens = stock->t, *words = source->t;
    int first = 0, voice = -1;
    GaiaBeatWindow box = {.x = -1, .y = -1, .row = 1};
    while (first < tail && !GaiaPageText(&tokens[first])) {
        if (!GaiaTimedStockGeometry(&box, &voice, &tokens[first]))
            return 0;
        Push(out, &tokens[first++]);
    }
    const int skip = lance ? 1 : 0;
    if (lance && (voice != 4 || words[0].type != T_MARK || words[0].code ||
                  words[0].a[0] != 4 || tokens[tail].code != 0xc3 ||
                  tokens[tail + 2].code != 0xc8))
        return 0;
    const int wait = tail + lance;
    const int last = source->n - 2;
    if (first == tail || !box.width || !box.height ||
        tokens[wait].code != 0xc9 || tokens[wait].a[0] != (lance ? 0x28 : 0xff) ||
        tokens[stock->n - 1].code != (lance ? CMD_RET : CMD_END) ||
        words[last].code != 0xc9 || words[last].a[0] != (lance ? 0x28 : 0xa0) ||
        words[last + 1].code != (lance ? CMD_END : CMD_RET))
        return 0;
    for (int i = first; i < tail; ++i)
        if (!GaiaPageText(&tokens[i]))
            return 0;
    for (int i = skip; i < last; ++i)
        if (!GaiaPageText(&words[i]))
            return 0;
    if (!GaiaFitTimedWords(words + skip, words + last, &box, out, box.height))
        return 0;
    for (int i = tail; i < stock->n; ++i)
        Push(out, &tokens[i]);
    return 1;
}

static int GaiaPrayerNotice(const Toks *stock, const Toks *source, Toks *out)
{
    const Tok *tokens = stock->t, *words = source->t;
    if (stock->n < 12 || source->n < 10 || tokens[0].code != 0xd3 ||
        tokens[1].code != CMD_SFX || tokens[1].a[0] || tokens[2].code != 0xd5 ||
        tokens[2].a[0] != 9 || tokens[stock->n - 1].code != CMD_END ||
        words[source->n - 1].code != CMD_END || words[source->n - 2].code != 0xc9 ||
        words[source->n - 2].a[0] != 0x5a)
        return 0;
    int first = 3, last = first;
    while (last < stock->n && GaiaPageText(&tokens[last]))
        ++last;
    if (last <= first || last + 3 >= stock->n || tokens[last - 1].code != CMD_N ||
        tokens[last].code != 0xc9 || tokens[last].a[0] != 0x3c ||
        tokens[last + 1].code != 0xd5 || tokens[last + 1].a[0] != 2)
        return 0;
    const int middle = last + 2;
    last = middle;
    while (last < stock->n && GaiaPageText(&tokens[last]))
        ++last;
    if (last <= middle || last + 2 >= stock->n || tokens[last - 1].code != CMD_N ||
        tokens[last].code != 0xc9 || tokens[last].a[0] != 0x1e)
        return 0;
    const int hold = last++;
    while (last < stock->n && GaiaPageText(&tokens[last]))
        ++last;
    if (last != stock->n - 2 || tokens[last].code != 0xc9 || tokens[last].a[0] != 0x5a)
        return 0;

    int change = 0;
    while (change < source->n - 2 && GaiaPageText(&words[change]))
        ++change;
    if (change <= 1 || words[change - 1].code != CMD_N ||
        words[change].code != 0xc9 || words[change].a[0] != 0x3c)
        return 0;
    int split = change + 1;
    while (split < source->n - 2 && GaiaPageText(&words[split])) {
        if (split >= change + 4 && words[split].type == T_GLYPH && words[split].code == 0xac &&
            words[split - 1].code == 0x2a && words[split - 2].code == 0x2a &&
            words[split - 3].code == 0x2a)
            break;
        ++split;
    }
    if (split == source->n - 2 || words[split].code != 0xac)
        return 0;
    for (int i = split + 1; i < source->n - 2; ++i)
        if (!GaiaPageText(&words[i]))
            return 0;

    GaiaBeatWindow box = {.width = 26, .height = 4, .row = 1};
    for (int i = 0; i < first; ++i)
        Push(out, &tokens[i]);
    if (!GaiaFitTimedWords(words, words + change - 1, &box, out, box.height))
        return 0;
    const Tok newline = {.type = T_CMD, .code = CMD_N, .ref = -1};
    Push(out, &newline);
    ++box.row;
    box.column = 0;
    Push(out, &tokens[middle - 2]);
    Push(out, &tokens[middle - 1]);
    if (!GaiaFitTimedWords(words + change + 1, words + split, &box, out, box.height))
        return 0;
    Push(out, &newline);
    ++box.row;
    box.column = 0;
    Push(out, &tokens[hold]);
    if (!GaiaFitTimedWords(words + split + 1, words + source->n - 2, &box, out, box.height))
        return 0;
    Push(out, &tokens[last]);
    Push(out, &tokens[last + 1]);
    return 1;
}

static int GaiaNewBabelNarration(const Rom *rom, const Toks *stock, const Toks *source, Toks *out)
{
    if (stock->n < 5 || stock->t[0].code != 0xd3 || stock->t[stock->n - 1].code != CMD_RET ||
        source->n < 5 || source->t[source->n - 1].code != CMD_RET ||
        !GaiaStockDefaultDialogue(rom))
        return 0;
    Toks layout = {0};
    const Tok position = {.type = T_CMD, .code = 0xc1, .a = {2, 13}};
    const Tok size = {.type = T_CMD, .code = 0xc7, .a = {14, 6}};
    Push(&layout, &position);
    Push(&layout, &size);
    for (int i = 1; i < stock->n; ++i)
        Push(&layout, &stock->t[i]);
    const int accepted = GaiaTimedStoryDeck(&layout, source, out, 0);
    free(layout.t);
    return accepted;
}

static int GaiaCompileTimedChapter(const Rom *rom, uint32_t offset, Toks *out, const Toks *source)
{
    switch (offset) {
    case 0x04b75d: case 0x04f38d: case 0x04faf9:
    case 0x069975: case 0x0bd558: case 0x0be075:
        break;
    default:
        return 0;
    }
    Toks stock = {0};
    int accepted = 0;
    if (Decode(rom, offset, &stock, 0, 0)) {
        if (offset == 0x069975)
            accepted = GaiaPrayerNotice(&stock, source, out);
        else if (offset == 0x0bd558)
            accepted = GaiaLegacyTimeline(&stock, source, out);
        else if (offset == 0x0be075)
            accepted = GaiaNewBabelNarration(rom, &stock, source, out);
        else
            accepted = GaiaTimedNoticeRules(offset, &stock, source, out);
    }
    free(stock.t);
    return accepted;
}
