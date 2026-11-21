/* The two entry points share one stock window and a physical page wait. */
static int GaiaInheritedPairWindow(const Rom *stock, uint32_t entry, uint32_t marker,
                                   Tok *window)
{
    if (entry == 0x05b9af && marker == 0x05b9cb) {
        /* First prompt opens D3; both second-prompt branches use that box. */
        static const uint8_t first[] = {2, 0xbf, 0xcd, 0xb8, 2, 0xbe, 2, 2, 0x8a, 0xb8};
        static const uint8_t second[] = {2, 0xbf, 0x0c, 0xb9, 2, 0xbe, 2, 2, 0x9f, 0xb8,
                                         0xa5, 0xb8, 0xaa, 0xb8, 0xa5, 0xb8};
        static const uint8_t replies[] = {2, 0xbf, 0xcb, 0xb9, 0x6b, 2, 0xd0, 0x59, 1, 0xb5, 0xb8,
                                          2, 0xbf, 0xaf, 0xb9, 0x6b};
        static const uint8_t opener[] = {0xd3};
        *window = (Tok){.type = T_CMD, .code = 0xd3, .ref = -1};
        return GaiaCalledRaw(stock, 0x05b880, first, sizeof(first)) &&
               GaiaCalledRaw(stock, 0x05b895, second, sizeof(second)) &&
               GaiaCalledRaw(stock, 0x05b8a5, replies, sizeof(replies)) &&
               GaiaCalledRaw(stock, 0x05b8cd, opener, sizeof(opener));
    }
    if (entry == 0x07e092 && marker == 0x07e0ac) {
        /* Ann's opening prompt and repeat call both open TPL:B. The latter
         * jumps to the existing marker through the original same-bank D1. */
        static const uint8_t first[] = {2, 0xbf, 0x7a, 0xdf, 2, 0xbe, 2, 2, 0x20, 0xdf,
                                        0x26, 0xdf, 0x2e, 0xdf, 0x26, 0xdf};
        static const uint8_t reply[] = {2, 0xbf, 0x92, 0xe0, 2, 0xcc, 0xd6, 0x6b};
        static const uint8_t repeat[] = {2, 0xbf, 0xde, 0xe0, 0x6b};
        static const uint8_t jump[] = {0xc2, 0x0b, 0xc2, 1, CMD_JMP, 0xac, 0xe0};
        *window = (Tok){.type = T_CMD, .code = 0xc2, .a = {0x0b}, .ref = -1};
        return GaiaCalledRaw(stock, 0x07df16, first, sizeof(first)) &&
               GaiaCalledRaw(stock, 0x07df26, reply, sizeof(reply)) &&
               GaiaCalledRaw(stock, 0x07df3e, repeat, sizeof(repeat)) &&
               GaiaCalledRaw(stock, 0x07e0de, jump, sizeof(jump)) &&
               GaiaCalledRaw(stock, 0x07df7a, jump, 4);
    }
    return 0;
}

static int GaiaInheritedPairPage(const Tok *window, const Toks *stock,
                                 const Toks *source, Item *out, int returning)
{
    const int last = source->n - 1 - returning;
    if (last < 1 || source->t[last].type != T_CMD ||
        source->t[last].code != (returning ? CMD_FIN : CMD_END) ||
        (returning && (source->t[last + 1].type != T_CMD ||
                       source->t[last + 1].code != CMD_RET)))
        return 0;
    for (int i = 0; i < last; ++i)
        if (!GaiaPageText(&source->t[i]))
            return 0;
    for (int i = 0; i < stock->n - 1; ++i)
        if (stock->t[i].type == T_CMD && stock->t[i].code == CMD_FIN)
            return 0;
    Toks model = {0}, shaped = {0};
    Push(&model, window);
    for (int i = 0; i < stock->n; ++i)
        Push(&model, &stock->t[i]);
    const Toks literal = {.t = source->t, .n = last + 1};
    const int ok = GaiaStockManualPages(&model, &shaped, &literal);
    if (ok)
        for (int i = 1; i < shaped.n; ++i)
            Push(&out->toks, &shaped.t[i]);
    free(shaped.t);
    free(model.t);
    return ok;
}

static int GaiaInheritedPair(const Rom *stock, const Structure *structure, int index,
                             IogPack *pack, unsigned *fill, char *source)
{
    const Label *label = &structure->l[index];
    const uint32_t entry = label->off, marker = entry + label->marker;
    Tok window;
    char *separator = strchr(source, '|');
    if (!label->has_marker || label->unk16 || !separator || strchr(separator + 1, '|') ||
        label->marker < 5 || marker >= stock->size ||
        !GaiaInheritedPairWindow(stock, entry, marker, &window) ||
        stock->rom[marker - 1] != CMD_FIN || StringSpan(stock, marker) < 5 ||
        !GaiaPatchDisjoint(pack, entry, 5) || !GaiaPatchDisjoint(pack, marker, 5))
        return 0;
    for (int i = 0; i < structure->nl; ++i) {
        const Label *other = &structure->l[i];
        const uint32_t inner = other->off + other->marker;
        if (i != index && (other->off - entry < 5 || other->off - marker < 5 ||
            (other->has_marker && (inner - entry < 5 || inner - marker < 5))))
            return 0;
    }

    Toks original = {0}, prefix = {0}, suffix = {0};
    Item first = {0}, last = {0};
    int ok = 0, split = 0;
    *separator++ = 0;
    if (!Decode(stock, entry, &original, 0, 0) ||
        !GaiaDialogue(source, &prefix) || !GaiaDialogue(separator, &suffix))
        goto done;
    while (split < original.n && original.t[split].src < marker)
        ++split;
    if (!split || split >= original.n || original.t[split].src != marker ||
        original.t[split - 1].code != CMD_FIN || original.t[original.n - 1].code != CMD_END)
        goto done;
    const Toks base = {.t = original.t, .n = split};
    const Toks tail = {.t = original.t + split, .n = original.n - split};
    if (!GaiaInheritedPairPage(&window, &base, &prefix, &first, 1) ||
        !GaiaInheritedPairPage(&window, &tail, &suffix, &last, 0))
        goto done;
    const unsigned first_size = (unsigned)Encode(NULL, &first, NULL);
    const unsigned last_size = (unsigned)Encode(NULL, &last, NULL);
    if (!first_size || !last_size || first_size + last_size > kIogVirtualBankSize)
        goto done;
    const uint32_t address = GaiaUiAddress(pack, fill, first_size + last_size);
    if (!address)
        goto done;
    uint8_t *dst = pack->banks[pack->nbanks - 1] + *fill;
    Encode(NULL, &first, dst);
    Encode(NULL, &last, dst + first_size);
    AddRedirect(pack, entry, CMD_PRT, address, CMD_RET);
    AddRedirect(pack, marker, CMD_PRT, address + first_size, CMD_RET);
    *fill += first_size + last_size;
    ok = 1;
done:
    free(first.toks.t);
    free(last.toks.t);
    free(original.t);
    free(prefix.t);
    free(suffix.t);
    return ok;
}

static void GaiaApplyInheritedPair(FILE *file, const Rom *stock, const Structure *structure,
                                   IogPack *pack, unsigned *fill)
{
    if (fseek(file, 0, SEEK_SET))
        return;
    char line[4096];
    while (fgets(line, sizeof(line), file)) {
        if (strncmp(line, "widestring_05B9AF\t", 18) &&
            strncmp(line, "widestring_07E092\t", 18))
            continue;
        line[17] = 0;
        char *source = line + 18;
        if (strncmp(source, "[PAIR]", 6))
            continue;
        source[strcspn(source, "\r\n")] = 0;
        const int li = FindLabel(structure, line);
        if (li >= 0 && GaiaInheritedPair(stock, structure, li, pack, fill, source + 6))
            ++pack->strings_translated;
    }
}
