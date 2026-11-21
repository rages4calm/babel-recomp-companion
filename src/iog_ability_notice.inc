/* The name table is deliberately left in bank 08. Execute the translated
 * opening via a far print, then continue the original indexed lookup from
 * the original bank, followed by the punctuation and original pause. */
static int GaiaCompileAbilityNotice(const Rom *stock, Toks *out, const Toks *text)
{
    static const uint8_t opener[] = {0xd3, 0xd5, 9, CMD_ADR, 0x8f, 0xeb, 0xac, 0x0a, CMD_N};
    static const uint8_t names[] = {0x9b, 0xeb, 0xa2, 0xeb, 0xab, 0xeb, 0xb2, 0xeb,
                                    0xba, 0xeb, 0xc7, 0xeb};
    const unsigned off = 0x08eb68;
    const unsigned span = StringSpan(stock, off);
    if (span != 0x1d || !GaiaCalledRaw(stock, off, opener, sizeof(opener)) ||
        !GaiaCalledRaw(stock, 0x08eb8f, names, sizeof(names)) ||
        text->n < 4 || text->t[text->n - 1].code != CMD_RET ||
        text->t[text->n - 2].code != CMD_N)
        return 0;
    static const uint8_t ending[] = {0xc9, 0x78, CMD_FIN, CMD_RET};
    if (!GaiaCalledRaw(stock, off + span - sizeof(ending), ending, sizeof(ending)))
        return 0;

    int rows = 0, columns = 0;
    for (int i = 0; i < text->n - 1; ++i) {
        const Tok *token = &text->t[i];
        if (token->type == T_GLYPH) {
            if (++columns > 26)
                return 0;
        } else if (token->type != T_CMD || token->code != CMD_N || !columns || ++rows > 3) {
            return 0;
        } else {
            columns = 0;
        }
    }
    if (rows != 2 || columns)
        return 0;
    const Tok setup = {.type = T_CMD, .code = 0xd3, .ref = -1};
    /* Use the authored glyph cadence for the longer notice. The fixed
     * stock pause after the ability name is part of the ROM continuation. */
    const Tok delay = {.type = T_CMD, .code = 0xd5, .a = {5}, .ref = -1};
    Push(out, &setup);
    Push(out, &delay);
    for (int i = 0; i < text->n; ++i)
        Push(out, &text->t[i]);
    return 1;
}

static void GaiaApplyAbilityNotice(FILE *file, const Rom *stock, const Structure *structure,
                                   IogPack *pack, unsigned *fill)
{
    const uint32_t off = 0x08eb68;
    uint8_t patch[] = {CMD_PRT, 0, 0, 0, CMD_ADR, 0x8f, 0xeb, 0xac, 0x0a,
                       0, 0xc9, 0x78, CMD_FIN, CMD_RET};
    if (!GaiaPatchDisjoint(pack, off, sizeof(patch)) || fseek(file, 0, SEEK_SET))
        return;
    const int li = FindLabel(structure, "widestring_08EB68");
    if (li < 0 || structure->l[li].off != off || structure->l[li].has_marker ||
        structure->l[li].unk16)
        return;
    for (int i = 0; i < structure->nl; ++i) {
        const Label *entry = &structure->l[i];
        if (i != li && (entry->off - off < sizeof(patch) ||
            (entry->has_marker && entry->off + entry->marker - off < sizeof(patch))))
            return;
    }

    const char *punctuation = "!";
    if (!GlyphFor(&punctuation, &patch[9]))
        return;
    static const char prefix[] = "widestring_08EB68\t[LAY]";
    char line[4096];
    while (fgets(line, sizeof(line), file)) {
        if (strncmp(line, prefix, sizeof(prefix) - 1))
            continue;
        char *source = line + sizeof(prefix) - 1;
        if (strncmp(source, "[EXT]", 5))
            return;
        source[strcspn(source, "\r\n")] = 0;
        Toks text = {0};
        Item item = {0};
        if (GaiaDialogue(source, &text) && GaiaCompileAbilityNotice(stock, &item.toks, &text)) {
            const unsigned size = (unsigned)Encode(NULL, &item, NULL);
            const uint32_t address = GaiaUiAddress(pack, fill, size);
            if (address) {
                Encode(NULL, &item, pack->banks[pack->nbanks - 1] + *fill);
                *fill += size;
                patch[1] = (uint8_t)address;
                patch[2] = (uint8_t)(address >> 8);
                patch[3] = (uint8_t)(address >> 16);
                AddPatch(pack, off, patch, sizeof(patch));
                ++pack->strings_translated;
            }
        }
        free(text.t);
        free(item.toks.t);
        return;
    }
}
