static int GaiaStockPromptContract(const Rom *stock, uint32_t label, int *options, int *skip)
{
    const uint32_t bank = label & 0xff0000u;
    if ((label & 0xffffu) < 0x8000u || bank + 0x10000u > stock->size)
        return 0;
    const uint8_t expected[] = {0x02, 0xbf, (uint8_t)label, (uint8_t)(label >> 8), 0x02, 0xbe};
    int found = 0;
    for (uint32_t site = bank + 0x8000u; site + 10 <= bank + 0x10000u; ++site) {
        if (memcmp(stock->rom + site, expected, sizeof(expected)))
            continue;
        const int count = stock->rom[site + 6], skip_rows = stock->rom[site + 7];
        const unsigned targets = Rd16(stock, site + 8);
        if (count < 2 || count > 7 || skip_rows + count > 7 || targets < 0x8000 ||
            targets + 2u * (count + 1) > 0x10000u)
            return 0;
        for (int i = 0; i <= count; ++i)
            if (Rd16(stock, bank + targets + 2u * i) < 0x8000)
                return 0;
        if (found && (*options != count || *skip != skip_rows))
            return 0;
        *options = count;
        *skip = skip_rows;
        found = 1;
    }
    return found;
}

static int GaiaChoiceKey(const Tok *at, const Tok *end, char key[64])
{
    unsigned size = 0;
    for (; at < end; ++at) {
        if (at->type != T_GLYPH) {
            if (at->code != 0xc3)
                return 0;
            continue;
        }
        const char *glyph = GlyphText(at->code);
        if (!glyph || !*glyph)
            return 0;
        for (; *glyph; ++glyph) {
            char c = *glyph;
            if (c == ' ' || c == '.' || c == '?' || c == '!')
                continue;
            if (size == 63)
                return 0;
            key[size++] = c >= 'A' && c <= 'Z' ? c + 'a' - 'A' : c;
        }
    }
    key[size] = 0;
    return size != 0;
}

/* The fixed fingerprints record independently checked stock and authored
 * labels for one original branch index. The branch table stays in the ROM. */
static uint64_t GaiaPromptBranchKey(const char *key)
{
    uint64_t hash = UINT64_C(14695981039346656037);
    for (; *key; ++key)
        hash = (hash ^ (uint8_t)*key) * UINT64_C(1099511628211);
    return hash;
}

static int GaiaPromptBranchMatch(uint32_t label, unsigned choice, const char *stock, const char *source)
{
    if (!strcmp(stock, source))
        return 1;
    static const struct { uint32_t label; unsigned choice; uint64_t stock, source; } audited[] = {
        {0x04E6E6u, 0, UINT64_C(0xce76ee2a46793071), UINT64_C(0xb3d577aa799df7bc)},
        {0x04E6E6u, 1, UINT64_C(0x6f0847c7ddddbf0b), UINT64_C(0xd92b4f47eeba183a)},
        {0x07DF7Au, 0, UINT64_C(0x032494139abbb2c4), UINT64_C(0x997b221d0e1c90e0)},
        {0x07DF7Au, 1, UINT64_C(0xe74a40e60a70ff0a), UINT64_C(0x82d5c38f5eef6641)},
        {0x08A027u, 0, UINT64_C(0x4ce6531fbfddd605), UINT64_C(0xeaf8ecbe78f1db9a)},
        {0x08A027u, 1, UINT64_C(0x1dee6107b26f8bb6), UINT64_C(0x0f5de3aad0ac2648)},
        {0x098053u, 0, UINT64_C(0x1dee6107b26f8bb6), UINT64_C(0x47e83eaa4b387e3b)},
        {0x098053u, 1, UINT64_C(0xb95b372fbeab0f9e), UINT64_C(0x6117fb5c24c955ea)},
    };
    const uint64_t old_key = GaiaPromptBranchKey(stock);
    const uint64_t new_key = GaiaPromptBranchKey(source);
    for (unsigned i = 0; i < sizeof(audited) / sizeof(audited[0]); ++i)
        if (audited[i].label == label && audited[i].choice == choice &&
            audited[i].stock == old_key && audited[i].source == new_key)
            return 1;
    return 0;
}

static int GaiaPromptChoices(Toks *out, const Tok *start, const Tok *end,
                             const Tok *source, const Tok *source_end, int width)
{
    int columns = 0, first = 0;
    while (source < source_end && source->type == T_GLYPH && source->code == 0xac)
        ++source;
    while (source_end > source && source_end[-1].type == T_GLYPH && source_end[-1].code == 0xac)
        --source_end;
    for (; start < end; ++start) {
        if (start->type == T_CMD && start->code == 0xc3) {
            Push(out, start);
        } else if (start->type == T_GLYPH && start->code == 0xac && !first) {
            Push(out, start);
            ++columns;
        } else if (start->type == T_GLYPH) {
            if (!first) {
                first = 1;
                if (source == source_end || source_end - source + columns > width)
                    return 0;
                for (; source < source_end; ++source)
                    Push(out, source);
            }
        } else {
            return 0;
        }
    }
    return first;
}

/* Fit an overlong question across the existing manual page boundaries,
 * without changing the number of advances or moving text between speakers. */
static int GaiaPromptPageCarry(const Toks *stock, const Toks *authored, Toks *out,
                               const Toks *prose, const Tok *controls, int n_controls,
                               int width, int height, int *rows)
{
    int old_voice, new_voice;
    if (GaiaManualTurnEnd(stock, 0, 0, &old_voice) != stock->n ||
        GaiaManualTurnEnd(authored, 0, 1, &new_voice) != authored->n || old_voice != new_voice)
        return 0;
    Toks carry = {0};
    for (int i = 0; i < authored->n; ++i)
        Push(&carry, &authored->t[i]);
    const Tok finish = {.type=T_CMD,.code=CMD_FIN,.ref=-1};
    const Tok blank = {.type=T_GLYPH,.code=0xac};
    int accept = 0;
    for (int split = 0; split < prose->n; ++split) {
        if (split && prose->t[split - 1].code != blank.code)
            continue;
        Toks tail = {0}, prefix = {0};
        if (GaiaWrapPage(prose->t + split, prose->t + prose->n, &tail, width, height, 0)) {
            const int old_n = carry.n;
            for (int i = 0; i < split; ++i)
                Push(&carry, &prose->t[i]);
            Push(&carry, &finish);
            if (GaiaStockManualPages(stock, &prefix, &carry)) {
                for (int i = 0; i < prefix.n; ++i)
                    Push(out, &prefix.t[i]);
                for (int i = 0; i < n_controls; ++i)
                    Push(out, &controls[i]);
                *rows = 1;
                for (int i = 0; i < tail.n; ++i) {
                    const Tok *t = &tail.t[i];
                    *rows += t->type == T_CMD && t->code == CMD_N;
                    Push(out, t);
                }
                accept = 1;
            }
            carry.n = old_n;
        }
        free(tail.t);
        free(prefix.t);
        if (accept)
            break;
    }
    free(carry.t);
    return accept;
}

static int GaiaCompilePrompt(const Rom *stock, uint32_t offset, Toks *out, const Toks *source)
{
    Toks before = {0}, authored = {0}, proposed = {0}, choices = {0};
    int accepted = 0, options = 0, skip = 0;
    if (!source->n || source->t[source->n - 1].code != CMD_RET ||
        !GaiaStockPromptContract(stock, offset, &options, &skip) ||
        !Decode(stock, offset, &before, 0, 0) || !before.n ||
        before.t[before.n - 1].code != CMD_RET)
        goto done;
    for (int i = 0; i < source->n; ++i) {
        const Tok *token = &source->t[i];
        if ((token->type == T_CMD || token->type == T_MARK) && token->code == 0xc3)
            continue;
        Push(&authored, token);
    }
    int s = 0, n = 0;
    for (int i = 0; i < before.n - 1; ++i)
        if (before.t[i].code == CMD_FIN)
            s = i + 1;
    for (int i = 0; i < authored.n - 1; ++i)
        if (authored.t[i].code == CMD_FIN)
            n = i + 1;
    if ((s == 0) != (n == 0)) {
        if (s || n != 1 || authored.t[0].code != CMD_FIN)
            goto done;
    }
    const Toks stock_prior = {.t=before.t,.n=s};
    const Toks author_prior = {.t=authored.t,.n=n};
    const int prelude_ok = !s || GaiaStockManualTurns(&stock_prior, &proposed, &author_prior);
    if (!prelude_ok && !skip)
        goto done;
    const int final_prefix = proposed.n;
    GaiaBeatWindow window = {.row=1,.x=-1,.y=-1};
    int voice = -1;
    for (int i = 0; i < s; ++i) {
        const Tok *t = &before.t[i];
        if (!GaiaPageText(t) && !GaiaBeatBoundary(t) && !GaiaBeatStockControl(&window, &voice, t))
            goto done;
    }
    int start = s;
    while (start < before.n - 1 && !GaiaPageText(&before.t[start])) {
        if (!GaiaBeatStockControl(&window, &voice, &before.t[start]))
            goto done;
        Push(&proposed, &before.t[start++]);
    }
    if (window.width < 1 || window.height < skip + options)
        goto done;
    int stock_rows[8] = {start}, nstock = 1;
    for (int i = start; i < before.n - 1; ++i)
        if (before.t[i].type == T_CMD && before.t[i].code == CMD_N) {
            if (nstock == 8)
                goto done;
            stock_rows[nstock++] = i + 1;
        }
    if (nstock != skip + options)
        goto done;
    int source_rows[32] = {n}, nsource = 1;
    for (int i = n; i < authored.n - 1; ++i)
        if (authored.t[i].type == T_CMD && authored.t[i].code == CMD_N) {
            if (nsource == 32)
                goto done;
            source_rows[nsource++] = i + 1;
        }
    if (nsource < options || (skip == 0 && nsource != options))
        goto done;
    int author_choices = nsource - options;
    for (int i = 0; i < options; ++i) {
        const int a = skip + i, u = author_choices + i;
        const int old_end = a + 1 < nstock ? stock_rows[a + 1] - 1 : before.n - 1;
        const int new_end = u + 1 < nsource ? source_rows[u + 1] - 1 : authored.n - 1;
        char old_key[64], new_key[64];
        if (!GaiaChoiceKey(before.t + stock_rows[a], before.t + old_end, old_key) ||
            !GaiaChoiceKey(authored.t + source_rows[u], authored.t + new_end, new_key) ||
            !GaiaPromptBranchMatch(offset, (unsigned)i, old_key, new_key) ||
            !GaiaPromptChoices(&choices, before.t + stock_rows[a], before.t + old_end,
                               authored.t + source_rows[u], authored.t + new_end, window.width))
            goto done;
        Push(&choices, &before.t[old_end]);
    }
    if (skip) {
        const int prose_end = stock_rows[skip] - 1;
        for (int i = start; i < prose_end; ++i)
            if (!GaiaPageText(&before.t[i]) && before.t[i].code != 0xc3)
                goto done;
        Toks prose = {0};
        int ok = 1;
        for (int i = n; i < source_rows[author_choices] - 1; ++i) {
            Tok t = authored.t[i];
            if (t.type == T_MARK && !t.code && (int)GaiaSpeakerIdentity(t.a[0]) == voice)
                continue;
            /* Source's extra presentation wait cannot replace the stock selector. */
            if (t.type == T_CMD && t.code == 0xd0)
                continue;
            if (t.type == T_CMD && t.code == CMD_N)
                t = (Tok){.type = T_GLYPH, .code = 0xac};
            if (t.type != T_GLYPH) {
                ok = 0;
                break;
            }
            Push(&prose, &t);
        }
        const int mark = proposed.n;
        int rows = 1;
        if (!ok || !prose.n) {
            free(prose.t);
            goto done;
        }
        if (prelude_ok && GaiaWrapPage(prose.t, prose.t + prose.n, &proposed, window.width, skip, 0)) {
            for (int i = mark; i < proposed.n; ++i)
                rows += proposed.t[i].type == T_CMD && proposed.t[i].code == CMD_N;
        } else {
            Toks carried = {0};
            int final_voice;
            (void)GaiaManualTurnEnd(&stock_prior, 0, 0, &final_voice);
            const Tok *controls = mark > final_prefix ? proposed.t + final_prefix : NULL;
            ok = s && final_voice == voice &&
                GaiaPromptPageCarry(&stock_prior, &author_prior, &carried, &prose,
                                    controls, mark - final_prefix, window.width, skip, &rows);
            if (ok) {
                free(proposed.t);
                proposed = carried;
            }
            if (!ok) {
                free(carried.t);
                free(prose.t);
                goto done;
            }
        }
        free(prose.t);
        for (int i = start; i < prose_end; ++i)
            if (before.t[i].type==T_CMD && before.t[i].code==0xc3)
                Push(&proposed, &before.t[i]);
        const Tok next={.type=T_CMD,.code=CMD_N,.ref=-1};
        while (rows++ <= skip)
            Push(&proposed, &next);
    }
    for (int i = 0; i < choices.n; ++i)
        Push(&proposed, &choices.t[i]);
    for (int i = 0; i < proposed.n; ++i)
        Push(out, &proposed.t[i]);
    accepted = 1;
done:
    free(before.t);
    free(authored.t);
    free(proposed.t);
    free(choices.t);
    return accepted;
}
