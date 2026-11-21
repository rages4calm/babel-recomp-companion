/* Keep the original timeline while fitting approved timed prose. */
static int GaiaFitTimedWords(const Tok *start, const Tok *stop, GaiaBeatWindow *window,
                             Toks *out, int row_limit)
{
    GaiaBeatWindow trial = *window;
    trial.height = row_limit;
    const int first = out->n;
    if (GaiaFitBeatWords(start, stop, &trial, out)) {
        window->row = trial.row;
        window->column = trial.column;
        return 1;
    }
    out->n = first;
    Toks soft = {0};
    for (; start < stop; ++start) {
        Tok token = *start;
        if (token.type == T_CMD && token.code == CMD_N)
            token = (Tok){.type=T_GLYPH,.code=0xac};
        Push(&soft, &token);
    }
    trial = *window;
    trial.height = row_limit;
    const int ok = soft.n && GaiaFitBeatWords(soft.t, soft.t + soft.n, &trial, out);
    free(soft.t);
    if (ok) {
        window->row = trial.row;
        window->column = trial.column;
    } else {
        out->n = first;
    }
    return ok;
}

static int GaiaStockRowState(GaiaBeatWindow *window, const Tok *token)
{
    if (window->closed || !window->width || !window->height)
        return 0;
    if (token->type == T_CMD && token->code == CMD_N) {
        ++window->row;
        window->column = 0;
    } else if (token->type == T_GLYPH) {
        if (++window->column > window->width)
            return 0;
    } else {
        return 0;
    }
    return window->row <= 16;
}

static int GaiaTimedStockGeometry(GaiaBeatWindow *window, int *voice, const Tok *token)
{
    if (token->type != T_CMD || token->code != 0xc7)
        return GaiaBeatStockControl(window, voice, token);
    const int width = (int)token->a[0] * 2;
    const int height = (int)token->a[1];
    if (window->x < 1 || window->y < 1 || width < 2 || height < 1 ||
        window->x + width > 31 || window->y + 2 * height + 2 > 31 || height > 7)
        return 0;
    window->width = width;
    window->height = height;
    window->closed = 0;
    window->row = 1;
    window->column = 0;
    return 1;
}

static int GaiaLegacyTimeline(const Toks *stock, const Toks *source, Toks *out)
{
    if (!stock->n || !source->n || stock->t[stock->n - 1].code != source->t[source->n - 1].code)
        return 0;
    int oldvoice = -1, s = 0, n = 0, holds = 0;
    GaiaBeatWindow old = {.x=-1,.y=-1,.row=1}, next = old;
    while (s < stock->n && n < source->n) {
        while (s < stock->n && !GaiaPageText(&stock->t[s]) && !GaiaBeatBoundary(&stock->t[s])) {
            const Tok *t = &stock->t[s++];
            const int was_open = !old.closed && old.width;
            if (!GaiaTimedStockGeometry(&old, &oldvoice, t) ||
                !GaiaTimedStockGeometry(&next, &oldvoice, t))
                return 0;
            if (t->code == 0xce || t->code == 0xc8 || was_open != (!old.closed && old.width)) {
                while (n < source->n && source->t[n].type == T_CMD &&
                       (source->t[n].code == 0xce || source->t[n].code == 0xc8))
                    ++n;
            }
            Push(out, t);
        }
        int newvoice = -1;
        while (n < source->n && source->t[n].type == T_MARK) {
            const Tok *t = &source->t[n++];
            if (!t->code)
                newvoice = (int)GaiaSpeakerIdentity(t->a[0]);
            else if (t->code != 0xc3)
                return 0;
        }
        const int prose = s;
        while (s < stock->n && GaiaPageText(&stock->t[s])) {
            if (!GaiaStockRowState(&old, &stock->t[s++]))
                return 0;
        }
        if (s == stock->n)
            return 0;
        if (s != prose) {
            const int begin = n;
            while (n < source->n && GaiaPageText(&source->t[n]))
                ++n;
            if (n == begin || (newvoice != -1 && oldvoice != newvoice) ||
                !GaiaFitTimedWords(source->t + begin, source->t + n, &next, out,
                                   old.row > old.height ? old.row : old.height))
                return 0;
        }
        while (s < stock->n && !GaiaBeatBoundary(&stock->t[s])) {
            const Tok *t = &stock->t[s++];
            if (!GaiaTimedStockGeometry(&old, &oldvoice, t) ||
                !GaiaTimedStockGeometry(&next, &oldvoice, t))
                return 0;
            Push(out, t);
        }
        if (s == stock->n || n == source->n)
            return 0;
        const Tok *end = &stock->t[s++];
        const int code = GaiaBeatBoundary(end);
        if (code == 0xc9 || code == 0xd0)
            ++holds;
        if (code == CMD_RET && next.column && !next.closed)
            return 0;
        if (code != GaiaBeatBoundary(&source->t[n])) {
            /* Source may omit a trailing layout clear that the stock script
             * owns. It cannot omit an advance between two pieces of prose. */
            if (source->t[n].type != T_CMD ||
                (source->t[n].code != 0xc8 && source->t[n].code != 0xce))
                return 0;
            ++n;
        }
        if (n == source->n || code != GaiaBeatBoundary(&source->t[n++]))
            return 0;
        Push(out, end);
        if (code == CMD_FIN)
            old.row = next.row = 1, old.column = next.column = 0;
    }
    return s == stock->n && n == source->n && holds > 0;
}

static int GaiaExplicitTimedWindow(const Rom *rom, const Toks *stock, int open, Toks *copy)
{
    const Tok *template = &stock->t[open];
    const unsigned id = template->a[0];
    if (template->code == 0xc1 && stock->t[open + 1].code == 0xc7) {
        for (int i = 0; i < stock->n; ++i)
            Push(copy,&stock->t[i]);
        return 1;
    }
    if (template->code != 0xc2 || id < 8 || id > 0x10 ||
        !GaiaCalledRaw(rom, 0x01ca95 + id * 2, (const uint8_t[]){
            (uint8_t)(0x27 + (id - 8) * 7), 0xcb
        }, 2))
        return 0;
    const uint8_t y = id < 12 ? 6 : 17;
    const uint8_t h = kGaiaTemplateRows[id - 8];
    const uint8_t expected[] = {0xc1, 3, y, 0xc7, 13, h, CMD_RET};
    if (!GaiaCalledRaw(rom, 0x01cb27 + (id - 8) * 7, expected, sizeof(expected)))
        return 0;
    for (int i = 0; i < open; ++i)
        Push(copy,&stock->t[i]);
    const Tok pos = {.type = T_CMD, .code = 0xc1, .a = {3,y}};
    const Tok size = {.type = T_CMD, .code = 0xc7, .a = {13,h}};
    Push(copy,&pos);
    Push(copy,&size);
    for (int i = open + 1; i < stock->n; ++i)
        Push(copy,&stock->t[i]);
    return 1;
}

static int GaiaCompileLegacyTiming(const Rom *rom, uint32_t offset, Toks *out, const Toks *source)
{
    Toks stock = {0};
    if (!Decode(rom, offset, &stock, 0, 0) || !stock.n) {
        free(stock.t);
        return 0;
    }
    int ok = GaiaLegacyTimeline(&stock, source, out);
    if (!ok && stock.n > 3 && stock.t[stock.n - 2].code == 0xc8 &&
        stock.t[stock.n - 1].code == CMD_RET) {
        int open = 0;
        while (open < stock.n - 2 && stock.t[open].code == 0xc9)
            ++open;
        Toks copy = {0};
        if (GaiaExplicitTimedWindow(rom, &stock, open, &copy)) {
            const int old_x = (int)copy.t[open].a[0], old_width = (int)copy.t[open + 1].a[0];
            const int old_height = (int)copy.t[open + 1].a[1];
            for (int change = 1; !ok && change <= 4; ++change) {
                for (int horizontal = 0; !ok && horizontal <= change; ++horizontal) {
                    if (old_x - horizontal < 1)
                        continue;
                    copy.t[open].a[0] = old_x - horizontal;
                    copy.t[open + 1].a[0] = old_width + horizontal;
                    copy.t[open + 1].a[1] = old_height + change - horizontal;
                    out->n = 0;
                    ok = GaiaLegacyTimeline(&copy, source, out);
                }
            }
        }
        free(copy.t);
    }
    free(stock.t);
    return ok;
}
