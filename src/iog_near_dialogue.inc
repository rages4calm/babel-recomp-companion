/* A near JMP cannot execute in a virtual overlay bank. Return from the
 * localized reply first and run the original near JMP from the real bank. */
static unsigned GaiaCompileNearReply(const Rom *stock, uint32_t offset, Toks *out,
                                      const Toks *source)
{
    static const uint8_t kara[] = {2, 0xbf, 0x20, 0xaa, 2, 0xbe, 2, 0, 0xf7, 0xa6,
                                   0x03, 0xa7, 0xfd, 0xa6, 0x03, 0xa7, 2, 0xbf, 0x7d, 0xaa};
    static const uint8_t neil[] = {2, 0xbf, 0x46, 0xde, 2, 0xbe, 2, 1, 0xa5, 0xdd,
                                   0xab, 0xdd, 0xb1, 0xdd, 0xab, 0xdd, 2, 0xbf, 0x9f, 0xdf};
    static const uint8_t curtain[] = {0xc2, 0x0b};
    const int is_kara = offset == 0x04aa7d;
    const unsigned target = is_kara ? 0xaaca : 0xdf92;
    const unsigned voice = is_kara ? 1 : 6;
    if ((!is_kara && offset != 0x05df9f) || source->n < 3 ||
        source->t[source->n - 2].code != CMD_FIN ||
        source->t[source->n - 1].code != CMD_RET ||
        !GaiaCalledRaw(stock, is_kara ? 0x04a6ed : 0x05dd9b,
                       is_kara ? kara : neil, sizeof(kara)) ||
        !GaiaCalledRaw(stock, is_kara ? 0x04aa20 : 0x05de46, curtain, sizeof(curtain)))
        return 0;
    const int first = is_kara ? 1 : 0;
    if (is_kara) {
        if (source->t[0].type != T_MARK || source->t[0].code || source->t[0].a[0] != voice)
            return 0;
    } else if (!GaiaBranchBeginsWith(source->t, source->n, "Neil:")) {
        return 0;
    }
    for (int i = first; i < source->n - 2; ++i)
        if (!GaiaPageText(&source->t[i]))
            return 0;

    Toks original = {0};
    unsigned accepted = 0;
    if (!Decode(stock, offset, &original, 0, 0) || original.n < 5 ||
        original.t[0].code != 0xce ||
        original.t[1].code != 0xc2 || original.t[1].a[0] != voice ||
        original.t[original.n - 2].code != CMD_FIN ||
        original.t[original.n - 1].code != CMD_JMP ||
        original.t[original.n - 1].a[0] != target)
        goto done;
    for (int i = 2; i < original.n - 2; ++i)
        if (!GaiaPageText(&original.t[i]))
            goto done;
    Push(out, &original.t[0]);
    Push(out, &original.t[1]);
    if (!GaiaWrapPage(source->t + first, source->t + source->n - 2, out, 26, 4, 0))
        goto done;
    Push(out, &original.t[original.n - 2]);
    Push(out, &source->t[source->n - 1]);
    accepted = target;
done:
    free(original.t);
    return accepted;
}

static void GaiaApplyNearReplies(FILE *file, const Rom *stock, const Structure *structure,
                                IogPack *pack, unsigned *fill)
{
    if (fseek(file, 0, SEEK_SET))
        return;
    char line[4096];
    while (fgets(line, sizeof(line), file)) {
        static const char kara_line[] = "widestring_04AA7D\t";
        static const char neil_line[] = "widestring_05DF9F\t";
        if (strncmp(line, kara_line, sizeof(kara_line) - 1) &&
            strncmp(line, neil_line, sizeof(neil_line) - 1))
            continue;
        char *source = strchr(line, '\t');
        *source++ = 0;
        if (strncmp(source, "[LAY][EXT]", sizeof("[LAY][EXT]") - 1))
            continue;
        source += sizeof("[LAY]") - 1;
        source[strcspn(source, "\r\n")] = 0;
        const int index = FindLabel(structure, line);
        if (index < 0)
            continue;
        const Label *label = &structure->l[index];
        const uint32_t offset = label->off;
        uint8_t patch[] = {CMD_PRT, 0, 0, 0, CMD_JMP, 0, 0};
        if (label->has_marker || label->unk16 || StringSpan(stock, offset) < sizeof(patch) ||
            !GaiaPatchDisjoint(pack, offset, sizeof(patch)))
            continue;
        int disjoint = 1;
        for (int i = 0; disjoint && i < structure->nl; ++i) {
            const Label *other = &structure->l[i];
            if (i != index)
                disjoint = other->off - offset >= sizeof(patch) &&
                    (!other->has_marker || other->off + other->marker - offset >= sizeof(patch));
        }
        if (!disjoint)
            continue;
        Toks text = {0};
        Item item = {0};
        const unsigned target = GaiaDialogue(source, &text) ?
            GaiaCompileNearReply(stock, offset, &item.toks, &text) : 0;
        if (target) {
            const unsigned size = (unsigned)Encode(NULL, &item, NULL);
            const uint32_t address = GaiaUiAddress(pack, fill, size);
            if (address) {
                Encode(NULL, &item, pack->banks[pack->nbanks - 1] + *fill);
                *fill += size;
                patch[1] = (uint8_t)address;
                patch[2] = (uint8_t)(address >> 8);
                patch[3] = (uint8_t)(address >> 16);
                patch[5] = (uint8_t)target;
                patch[6] = (uint8_t)(target >> 8);
                AddPatch(pack, offset, patch, sizeof(patch));
                ++pack->strings_translated;
            }
        }
        free(text.t);
        free(item.toks.t);
    }
}
