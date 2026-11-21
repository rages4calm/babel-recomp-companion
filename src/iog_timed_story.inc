/* These long finale scenes are standalone. Stock speaker and clear beats
 * own the stage. The approved source can use an explicit restored name. */
static int GaiaStorySpeaker(const Toks *text, int at, int end)
{
    if (at >= end)
        return -1;
    if (text->t[at].type == T_MARK && !text->t[at].code)
        return (int)GaiaSpeakerIdentity(text->t[at].a[0]);
    char name[12] = {0};
    unsigned n = 0;
    for (; at < end && text->t[at].type == T_GLYPH; ++at) {
        const char *letter = GlyphText(text->t[at].code);
        if (!letter || !*letter || n == sizeof(name) - 1)
            return -1;
        if (*letter == ':') {
            static const char *const speakers[] = {"Will", "Kara", "Shira", "", "Olman"};
            for (unsigned who = 0; who < sizeof(speakers) / sizeof(speakers[0]); ++who)
                if (n && !strcmp(name, speakers[who]))
                    return (int)who;
            return -1;
        }
        name[n++] = *letter;
    }
    return -1;
}

static int GaiaSentenceEnd(uint8_t glyph)
{
    return glyph == 0x2a || glyph == 0x0d || glyph == 0x4f;
}

static int GaiaTimedStoryCard(const Tok *old, const Tok *end, const Tok *source, const Tok *stop,
                              Toks *out, GaiaBeatWindow window)
{
    const Tok *waits[2];
    int waits_n = 0, first_sentence = 0;
    uint8_t last = 0;
    for (const Tok *t = old; t < end; ++t) {
        if (t->type == T_CMD && t->code == 0xc9) {
            if (waits_n == 2 || !last)
                return 0;
            if (!waits_n)
                first_sentence = GaiaSentenceEnd(last);
            waits[waits_n++] = t;
        } else if (t->type == T_GLYPH) {
            if (t->code != 0xac)
                last = t->code;
        } else if (t->type != T_CMD || t->code != CMD_N) {
            return 0;
        }
    }
    if (!waits_n || waits[waits_n - 1] != end - 1)
        return 0;
    Toks copy = {0};
    int anchors[2], anchors_n = 0, accepted = 0;
    for (; source < stop; ++source) {
        Tok t = *source;
        if (t.type != T_GLYPH && t.code == 0xc9) {
            if (anchors_n == 2 || !copy.n)
                goto done;
            anchors[anchors_n++] = copy.n;
            continue;
        }
        if (t.type == T_CMD && t.code == 0xc3)
            continue;
        if (t.type == T_CMD && (t.code == 0xc8 || t.code == 0xce))
            t = (Tok){.type = T_GLYPH, .code = 0xac};
        if (t.type == T_CMD && t.code == CMD_N)
            t = (Tok){.type = T_GLYPH, .code = 0xac};
        if (t.type != T_GLYPH)
            goto done;
        Push(&copy, &t);
    }
    if (anchors_n < 1 || anchors[anchors_n - 1] != copy.n)
        goto done;
    int split = 0;
    if (waits_n == 2) {
        if (anchors_n == 2) {
            split = anchors[0];
        } else if (first_sentence) {
            /* These finale cards use the short hold after the first
             * complete sentence. Continue at the corresponding authored
             * sentence boundary when the source has only its closing hold. */
            for (int i = 1; i < copy.n - 1; ++i) {
                if (GaiaSentenceEnd(copy.t[i - 1].code) && copy.t[i].code == 0xac) {
                    split = i;
                    break;
                }
            }
        }
        if (split <= 0 || split >= copy.n ||
            !GaiaFitTimedWords(copy.t, copy.t + split, &window, out, window.height))
            goto done;
        Push(out, waits[0]);
    } else if (anchors_n != 1) {
        goto done;
    }
    if (!GaiaFitTimedWords(copy.t + split, copy.t + copy.n, &window, out, window.height))
        goto done;
    Push(out, waits[waits_n - 1]);
    accepted = 1;
done:
    free(copy.t);
    return accepted;
}

static int GaiaTimedStoryDeck(const Toks *stock, const Toks *source, Toks *out, int merge_father)
{
    GaiaBeatWindow window = {.x = -1, .y = -1, .row = 1};
    int s = 0, n = 0, voice = -1, shown = 0;
    while (s < stock->n - 2 && n < source->n - 2) {
        int changed = 0;
        while (s < stock->n - 1 && !GaiaPageText(&stock->t[s])) {
            const Tok *t = &stock->t[s++];
            changed |= t->code == 0xc2 && GaiaSpeakerTemplate(t->a[0]);
            /* The body has two tile rows per line, one cursor row, and
             * a bottom border. All must fit in the visible 224 pixels. */
            if (t->code == 0xc7 && window.y + 2 * (int)t->a[1] + 2 > 28)
                return 0;
            if (!GaiaTimedStockGeometry(&window, &voice, t))
                return 0;
            Push(out, t);
        }
        while (
            n < source->n - 1 && source->t[n].type == T_CMD &&
            (source->t[n].code == 0xc3 || source->t[n].code == 0xc8 || source->t[n].code == 0xce))
            ++n;
        const int speaker = GaiaStorySpeaker(source, n, source->n - 1);
        if ((speaker >= 0 && speaker != voice) || (changed && speaker < 0))
            return 0;
        if (n < source->n - 1 && source->t[n].type == T_MARK && !source->t[n].code)
            ++n;
        const int start = s, first = n;
        while (s < stock->n - 1 && (GaiaPageText(&stock->t[s]) || stock->t[s].code == 0xc9))
            ++s;
        while (n < source->n - 1 && (GaiaPageText(&source->t[n]) || source->t[n].code == 0xc9 ||
                                     source->t[n].code == 0xc3))
            ++n;
        if (merge_father && shown == 4 && speaker == 4 && n < source->n - 1 &&
            (source->t[n].code == 0xce || source->t[n].code == 0xc8)) {
            const int skip = ++n;
            while (n < source->n - 1 && (GaiaPageText(&source->t[n]) || source->t[n].code == 0xc9 ||
                                         source->t[n].code == 0xc3))
                ++n;
            if (n == skip)
                return 0;
        }
        if (s == start || n == first ||
            !GaiaTimedStoryCard(stock->t + start, stock->t + s, source->t + first, source->t + n,
                                out, window))
            return 0;
        ++shown;
    }
    if (s != stock->n - 2 || n != source->n - 2 || stock->t[s].code != 0xc8 ||
        source->t[n].code != 0xc8)
        return 0;
    Push(out, &stock->t[s]);
    Push(out, &stock->t[s + 1]);
    return shown > 0;
}

static int GaiaCompileTimedStory(const Rom *rom, uint32_t offset, Toks *out, const Toks *source)
{
    if (offset != 0x0bd740 && offset != 0x0bd9fa && offset != 0x0bded4)
        return 0;
    Toks stock = {0};
    int ok = 0;
    if (!Decode(rom, offset, &stock, 0, 0) || stock.n < 6 || source->n < 3 ||
        stock.t[0].code != 0xc1 || stock.t[1].code != 0xc7 ||
        stock.t[stock.n - 1].code != CMD_RET || source->t[source->n - 1].code != CMD_RET)
        goto done;
    const int old_x = (int)stock.t[0].a[0], old_width = (int)stock.t[1].a[0];
    const int old_height = (int)stock.t[1].a[1];
    const int old_y = (int)stock.t[0].a[1];
    /* Keep both characters visible below the second Comet scene's text. */
    const int max_height = offset == 0x0bd9fa ? 5 : 7;
    for (int add = 0; !ok && add <= 4; ++add) {
        for (int side = 0; !ok && side <= add; ++side) {
            if (old_x - side < 1 || old_height + add - side > max_height)
                continue;
            stock.t[0].a[0] = old_x - side;
            /* The world-map card has a bottom anchor inside the 224-line field. */
            if (offset == 0x0bded4)
                stock.t[0].a[1] = old_y - 2 * (add - side);
            stock.t[1].a[0] = old_width + side;
            stock.t[1].a[1] = old_height + add - side;
            out->n = 0;
            ok = GaiaTimedStoryDeck(&stock, source, out, offset == 0x0bd740);
        }
    }
done:
    free(stock.t);
    return ok;
}
