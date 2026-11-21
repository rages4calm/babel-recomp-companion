/* A MusicAndText actor inherits the still-open default box from its
 * preceding PrintDialogString. The jingle itself waits independently. */
static int GaiaJingleOpening(const Rom *rom, uint32_t offset)
{
    static const struct { uint32_t label, site; uint16_t print; } calls[] = {
        {0x08c831, 0x08c7be, 0xc7c9}, {0x08c831, 0x08c885, 0xc88c},
        {0x08c831, 0x08c92d, 0xc934}, {0x08c831, 0x08c9d5, 0xc9dc},
        {0x08c831, 0x08ca7d, 0xca84}, {0x08c831, 0x08cb25, 0xcb2c},
        {0x0aa7ef, 0x0aa760, 0xa7b4}, {0x0aa85c, 0x0aa780, 0xa811},
    };
    int found = 0;
    for (unsigned i = 0; i < sizeof(calls) / sizeof(calls[0]); ++i) {
        if (calls[i].label != offset)
            continue;
        found = 1;
        const unsigned site = calls[i].site;
        const unsigned first = offset == 0x08c831 ? site - 18 : site - 15;
        const unsigned pointer = calls[i].print;
        const uint8_t call[] = {0x02,0x19,0x17,(uint8_t)offset,(uint8_t)(offset>>8),
                                (uint8_t)(0x80|(offset>>16))};
        const uint8_t lead[] = {0x02,0xbf,(uint8_t)pointer,(uint8_t)(pointer>>8),0x02,0xd4};
        if (!GaiaCalledRaw(rom, first, lead, sizeof(lead)) ||
            !GaiaCalledRaw(rom, site, call, sizeof(call)))
            return 0;
        Toks prelude = {0};
        const uint32_t opener = (offset & 0xff0000u) | pointer;
        int ok = Decode(rom, opener, &prelude, 0, 0) && prelude.n >= 3 &&
            prelude.t[0].code == 0xd3 && prelude.t[prelude.n-2].code == CMD_FIN &&
            prelude.t[prelude.n-1].code == CMD_RET;
        for (int j = 1; ok && j < prelude.n - 1; ++j) {
            const Tok *t = &prelude.t[j];
            ok = GaiaPageText(t) || t->code == CMD_FIN || t->code == 0xc3 ||
                 (t->code == 0xc2 && GaiaSpeakerTemplate(t->a[0]));
        }
        free(prelude.t);
        if (!ok)
            return 0;
    }
    return found;
}

static int GaiaCompileJingleNotice(const Rom *rom, uint32_t offset, Toks *out, const Toks *source)
{
    if (source->n < 3 || source->t[source->n-2].code != 0xc9 ||
        source->t[source->n-1].code != CMD_RET || !GaiaJingleOpening(rom, offset))
        return 0;
    Toks stock = {0};
    int ok = 0;
    if (!Decode(rom, offset, &stock, 0, 0) || stock.n < 6 ||
        stock.t[0].code != 0xce || stock.t[1].code != CMD_SFX || stock.t[2].code != 0xd5 ||
        stock.t[stock.n-2].code != 0xc9 || stock.t[stock.n-1].code != CMD_END)
        goto done;
    for (int i = 0; i < source->n - 2; ++i)
        if (!GaiaPageText(&source->t[i]))
            goto done;
    for (int i = 3; i < stock.n - 2; ++i)
        if (!GaiaPageText(&stock.t[i]))
            goto done;
    for (int i = 0; i < 3; ++i)
        Push(out,&stock.t[i]);
    if (!GaiaWrapPage(source->t, source->t+source->n-2, out, 26, 4, 0))
        goto done;
    Push(out,&stock.t[stock.n-2]);
    Push(out,&stock.t[stock.n-1]);
    ok = 1;
done:
    free(stock.t);
    return ok;
}
