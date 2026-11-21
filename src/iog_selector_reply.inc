/* Stock replies reached by one of the preceding selector's result slots.
 * The selector leaves its box open. The reply clears its interior, writes
 * in that same window, accepts the original advance, and returns. */
static int GaiaCompileSelectorReply(const Rom *stock, uint32_t offset, Toks *out, const Toks *source)
{
    static const struct {
        uint32_t label, reply_call, selector_call, selector, box_source;
        uint16_t table;
        uint8_t slots, reply_slot, skip;
    } rules[] = {
        {0x04c4d5,0x04c3fc,0x04c3ec,0x04c40e,0x04c40e,0xc3f6,2,2,2},
        {0x04ecab,0x04e9b8,0x04e9a0,0x04ec46,0x04ec46,0xe9aa,2,1,2},
        {0x05ebe5,0x05e8e3,0x05e8cf,0x05eb94,0x05eb4f,0xe8d9,4,1,0},
    };
    unsigned rule = 0;
    while (rule < sizeof(rules) / sizeof(rules[0]) && rules[rule].label != offset)
        ++rule;
    if (rule == sizeof(rules) / sizeof(rules[0]) || source->n < 2)
        return 0;
    const uint32_t selector = rules[rule].selector;
    const uint16_t table = rules[rule].table;
    const uint8_t selector_call[] = {
        0x02,0xbf,(uint8_t)selector,(uint8_t)(selector >> 8),0x02,0xbe,
        rules[rule].slots,rules[rule].skip,(uint8_t)table,(uint8_t)(table >> 8),
    };
    if (!GaiaCalledRaw(stock, rules[rule].selector_call, selector_call, sizeof(selector_call)))
        return 0;
    const uint8_t reply_call[] = {0x02,0xbf,(uint8_t)offset,(uint8_t)(offset >> 8)};
    const uint32_t bank = offset & 0xff0000u;
    const uint32_t slot = bank + rules[rule].table + 2u * rules[rule].reply_slot;
    if (slot + 2 > stock->size || Rd16(stock, slot) != (rules[rule].reply_call & 0xffffu) ||
        !GaiaCalledRaw(stock, rules[rule].reply_call, reply_call, sizeof(reply_call)))
        return 0;
    if (rules[rule].selector != rules[rule].box_source) {
        /* Nazca prints the marked default-box opener immediately before
         * the no-prose choice card. Check the real preceding actor calls. */
        static const uint8_t setup[] = {0x02,0xbf,0x4f,0xeb,0x02,0xbf,0x94,0xeb,0x02,0xbe};
        if (!GaiaCalledRaw(stock, 0x05e8cb, setup, sizeof(setup)))
            return 0;
    }
    Toks area = {0}, original = {0};
    int accepted = 0;
    GaiaBeatWindow window = {.x = -1,.y = -1,.row = 1};
    int voice = -1;
    if (!Decode(stock, rules[rule].box_source, &area, 0, 0) ||
        !Decode(stock, offset, &original, 0, 0) || original.n < 5 ||
        original.t[0].code != 0xce || original.t[1].code != 0xc2 ||
        !GaiaSpeakerTemplate(original.t[1].a[0]) ||
        original.t[original.n - 2].code != CMD_FIN ||
        original.t[original.n - 1].code != CMD_RET)
        goto done;
    for (int i = 0; i < area.n; ++i) {
        const Tok *t = &area.t[i];
        if (GaiaPageText(t) || t->code == CMD_FIN || t->code == CMD_RET)
            continue;
        if (!GaiaBeatStockControl(&window, &voice, t))
            goto done;
    }
    if (window.closed || !window.width || !window.height)
        goto done;
    for (int i = 2; i < original.n - 2; ++i)
        if (!GaiaPageText(&original.t[i]))
            goto done;
    int stop = source->n - 1;
    if (source->t[stop].code == CMD_RET && source->t[stop - 1].code == CMD_FIN)
        --stop;
    else if (source->t[stop].code != CMD_END)
        goto done;
    for (int i = 0; i < stop; ++i)
        if (!GaiaPageText(&source->t[i]))
            goto done;
    const int used = out->n;
    Push(out, &original.t[0]);
    Push(out, &original.t[1]);
    if (!GaiaWrapPage(source->t, source->t + stop, out, window.width, window.height, 0)) {
        out->n = used;
        goto done;
    }
    Push(out, &original.t[original.n - 2]);
    Push(out, &original.t[original.n - 1]);
    accepted = 1;
done:
    free(original.t);
    free(area.t);
    return accepted;
}
