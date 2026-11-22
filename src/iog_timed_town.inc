/* The town narration runs beside a separate movement actor. Keep its
 * stock waits and close while fitting the approved text above the same
 * bottom edge. */
static int GaiaTownArrival(const Rom *rom, uint32_t offset, Toks *out, const Toks *source)
{
    const int euro = offset == 0x07beda;
    if ((!euro && offset != 0x0780b6) || source->n < 7 ||
        !GaiaStockDefaultDialogue(rom))
        return 0;
    Toks original = {0}, layout = {0}, grouped = {0};
    int ok = 0;
    if (!Decode(rom, offset, &original, 0, 0) || original.n < 7 ||
        original.t[0].code != 0xd3 || original.t[1].code != 0xc2 ||
        original.t[1].a[0] != 0 || original.t[2].code != CMD_SFX ||
        original.t[2].a[0] != 0x10 || original.t[3].code != 0xd5 ||
        original.t[3].a[0] != (euro ? 2 : 3) ||
        original.t[original.n - 3].code != 0xc3 ||
        original.t[original.n - 3].a[0] != 0 ||
        original.t[original.n - 2].code != 0xc8 ||
        original.t[original.n - 1].code != CMD_RET)
        goto done;
    const Tok position = {.type = T_CMD, .code = 0xc1, .a = {2, 15}};
    const Tok size = {.type = T_CMD, .code = 0xc7, .a = {14, 5}};
    const Tok gap = {.type = T_GLYPH, .code = 0xac};
    Push(&layout, &position);
    Push(&layout, &size);
    for (int i = 1; i < original.n - 3; ++i)
        Push(&layout, &original.t[i]);
    Push(&layout, &original.t[original.n - 2]);
    Push(&layout, &original.t[original.n - 1]);
    if (euro) {
        int holds = 0, merged = 0;
        for (int i = 0; i < source->n; ++i) {
            const Tok *t = &source->t[i];
            const int timer = t->type == T_CMD && t->code == 0xc9;
            holds += timer;
            /* Keep the welcome sentences and the festival sentences
             * together at the corresponding stock page boundaries. */
            if (timer && (holds == 4 || holds == 6)) {
                if (t->a[0] != 0x60 || i + 1 >= source->n ||
                    source->t[i + 1].type != T_CMD || source->t[i + 1].code != 0xce)
                    goto done;
                ++i;
                ++merged;
                Push(&grouped, &gap);
            } else {
                Push(&grouped, t);
            }
        }
        if (holds != 7 || merged != 2)
            goto done;
    }
    ok = GaiaTimedStoryDeck(&layout, euro ? &grouped : source, out, 0);
    if (ok) {
        const Tok close = out->t[out->n - 2], end = out->t[out->n - 1];
        out->n -= 2;
        Push(out, &original.t[original.n - 3]);
        Push(out, &close);
        Push(out, &end);
    }
done:
    free(original.t);
    free(layout.t);
    free(grouped.t);
    return ok;
}
