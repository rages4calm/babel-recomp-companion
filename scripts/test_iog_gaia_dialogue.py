#!/usr/bin/env python3
"""Check stock-window Gaia dialogue handling with ROM-free synthetic messages."""
import argparse
from pathlib import Path
import subprocess

from import_gaialabs_dialogue import convert, convert_extended, convert_return

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r"""
#include "iog_text.c"

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "%s\n", #expr); exit(1); } } while (0)

static int CountToken(const Toks *tokens, uint8_t type, uint8_t code, unsigned argument)
{
    int count = 0;
    for (int i = 0; i < tokens->n; i++) {
        const Tok *token = &tokens->t[i];
        count += token->type == type && token->code == code && token->a[0] == argument;
    }
    return count;
}

static void CheckWindow(const uint8_t *data, size_t size, const char *text,
                        int accepted, int pages, int will, int kara)
{
    Rom stock = {.rom = data, .size = size};
    Toks parsed = {0}, rendered = {0};
    CHECK(GaiaDialogue(text, &parsed));
    const int actual = GaiaStockWindow(&stock, 0, &rendered, &parsed, 1);
    if (actual != accepted)
        fprintf(stderr, "unexpected result for %s\n", text);
    CHECK(actual == accepted);
    if (accepted) {
        CHECK(CountToken(&rendered, T_CMD, CMD_FIN, 0) == pages - 1);
        CHECK(CountToken(&rendered, T_CMD, 0xc2, 0) == will);
        CHECK(CountToken(&rendered, T_CMD, 0xc2, 1) == kara);
        CHECK(rendered.t[rendered.n - 1].code == CMD_END);
    }
    free(parsed.t);
    free(rendered.t);
}

static void RejectMalformed(const char *text)
{
    Toks tokens = {0};
    CHECK(!GaiaDialogue(text, &tokens));
    free(tokens.t);
}

static void CheckStockSound(void)
{
    const uint8_t leading[] = {0xc2, 9, CMD_SFX, 0x10, 0x40, CMD_END};
    const uint8_t midpage[] = {0xc2, 9, 0x40, CMD_SFX, 0x10, 0x41, CMD_END};
    const uint8_t next_page[] = {0xc2, 9, 0x40, CMD_FIN, CMD_SFX, 0x10, 0x41, CMD_END};
    Rom stock = {.rom = leading, .size = sizeof(leading)};
    Toks parsed = {0}, rendered = {0};
    CHECK(GaiaDialogue("A[END]", &parsed));
    CHECK(GaiaStockWindow(&stock, 0, &rendered, &parsed, 1));
    CHECK(rendered.n == 4 && rendered.t[1].code == CMD_SFX && rendered.t[1].a[0] == 0x10);
    free(parsed.t);
    free(rendered.t);
    CheckWindow(midpage, sizeof(midpage), "A[END]", 0, 0, 0, 0);
    stock = (Rom){.rom = next_page, .size = sizeof(next_page)};
    parsed = (Toks){0};
    rendered = (Toks){0};
    CHECK(GaiaDialogue("A[FIN]B[END]", &parsed));
    CHECK(GaiaStockWindow(&stock, 0, &rendered, &parsed, 1));
    CHECK(rendered.n == 6 && rendered.t[2].code == CMD_FIN);
    CHECK(rendered.t[3].code == CMD_SFX && rendered.t[3].a[0] == 0x10);
    free(parsed.t);
    free(rendered.t);
    CheckWindow(next_page, sizeof(next_page), "A B[END]", 0, 0, 0, 0);
    RejectMalformed("[SFX:10]A[END]");
}

static void CheckPageControls(void)
{
    const uint8_t pauses[] = {0xc9, 0x1e, 0xc2, 9, 0x40, CMD_FIN,
        0xc1, 3, 17, 0xc7, 13, 3, 0xce, 0xd5, 1, 0x41, 0xc9, 0x28, 0xc3, 0, CMD_END};
    const uint8_t no_reset[] = {0xd3, 0x40, CMD_END};
    const uint8_t mid_pause[] = {0xd3, 0x40, 0xc9, 0x1e, 0x41, CMD_END};
    Rom stock = {.rom = pauses, .size = sizeof(pauses)};
    Toks parsed = {0}, rendered = {0};
    const char *verified = "[PAU:1E]A[FIN]B[PAU:28][PAL:00][END]";
    CHECK(GaiaDialogue(verified, &parsed));
    CHECK(GaiaStockWindow(&stock, 0, &rendered, &parsed, 1));
    Item item = {.toks = rendered};
    uint8_t encoded[sizeof(pauses)] = {0};
    CHECK(Encode(NULL, &item, NULL) == sizeof(pauses));
    Encode(NULL, &item, encoded);
    CHECK(!memcmp(encoded, pauses, sizeof(pauses)));
    free(parsed.t);
    free(rendered.t);
    CheckWindow(pauses, sizeof(pauses), "[PAU:28]A[FIN]B[PAU:1E][PAL:00][END]", 0, 0, 0, 0);
    CheckWindow(pauses, sizeof(pauses), "[PAU:1E]A[FIN]B[PAL:00][END]", 0, 0, 0, 0);
    CheckWindow(pauses, sizeof(pauses), "[PAU:1E]A B[PAU:28][PAL:00][END]", 0, 0, 0, 0);
    CheckWindow(no_reset, sizeof(no_reset), "A[PAL:00][END]", 0, 0, 0, 0);
    CheckWindow(mid_pause, sizeof(mid_pause), "A B[PAU:1E][END]", 0, 0, 0, 0);
    RejectMalformed("A[PAU:1E]B[END]");
    RejectMalformed("A[PAU:00][END]");
    RejectMalformed("A[PAL:04][END]");
}

static void CheckReturningFragments(void)
{
    const uint8_t choice[] = {0xd3, 0xce, 0x40, CMD_N, 0xc3, 0,
        0xac, 0x41, CMD_N, 0xac, 0x42, CMD_RET};
    const uint8_t number[] = {0xd3, 0x40, 0xc6, 2, 0xb0, 0xa, 0x41, CMD_RET};
    Rom stock = {.rom = choice, .size = sizeof(choice)};
    Toks parsed = {0}, rendered = {0};
    CHECK(GaiaDialogue("Go?[N] Yes[N] No[RET]", &parsed));
    CHECK(!GaiaStockWindow(&stock, 0, &rendered, &parsed, 0));
    CHECK(GaiaStockWindow(&stock, 0, &rendered, &parsed, 1));
    CHECK(CountToken(&rendered, T_CMD, CMD_N, 0) == 2);
    CHECK(CountToken(&rendered, T_CMD, 0xc3, 0) == 1);
    CHECK(rendered.t[rendered.n - 1].code == CMD_RET);
    free(parsed.t);
    free(rendered.t);

    CheckWindow(choice, sizeof(choice), "Go?[N]Yes[N] No[RET]", 0, 0, 0, 0);
    CheckWindow(choice, sizeof(choice), "Go?[N] Yes[RET]", 0, 0, 0, 0);
    CheckWindow(choice, sizeof(choice), "Go?[N] Yes[N] No[END]", 0, 0, 0, 0);
    CheckWindow(number, sizeof(number), "A[BCD:2,0AB1]B[RET]", 0, 0, 0, 0);
    RejectMalformed("A[BCD:0,0AB0]B[RET]");
    RejectMalformed("A[BCD:2,AB0]B[RET]");
}

static void CheckSupplement(const uint8_t *data, size_t size, const char *text,
                            int accepted, int final, int waits)
{
    Rom stock = {.rom = data, .size = size};
    Toks parsed = {0}, rendered = {0};
    CHECK(GaiaDialogue(text, &parsed));
    int actual = GaiaStockWindow(&stock, 0, &rendered, &parsed, kGaiaExtended);
    if (actual != accepted)
        fprintf(stderr, "unexpected supplemental result for %s\n", text);
    CHECK(actual == accepted);
    if (accepted) {
        CHECK(rendered.n && rendered.t[rendered.n - 1].code == final);
        CHECK(CountToken(&rendered, T_CMD, CMD_FIN, 0) == waits);
    }
    free(parsed.t);
    free(rendered.t);
}

static void CheckExtendedControls(void)
{
    const uint8_t timed[] = {0xc9, 0x1e, 0xc2, 9, 0xc2, 1,
        0x40, 0xd0, 0x41, 0xc9, 0x28, 0x42, 0xc3, 4, CMD_END};
    const uint8_t number[] = {0xd3, 0x40, 0xc6, 2, 0, 0xb0, 0xa, 0x41, CMD_END};
    const uint8_t large[] = {0xc1, 2, 4, 0xc7, 14, 2, 0x40, CMD_RET};
    const uint8_t small[] = {0xc2, 9, 0x40, CMD_RET};
    CheckSupplement(timed, sizeof(timed),
        "[EXT][PAU:1E][TPL:01]First[WAI]second[PAU:28]third[PAL:04][END]",
        1, CMD_END, 0);
    CheckSupplement(timed, sizeof(timed),
        "[EXT][PAU:1E][TPL:01]First[WAI]second[PAU:29]third[PAL:04][END]",
        0, 0, 0);
    CheckSupplement(timed, sizeof(timed),
        "[EXT][PAU:1E][TPL:00]First[WAI]second[PAU:28]third[PAL:04][END]",
        0, 0, 0);
    CheckSupplement(timed, sizeof(timed),
        "[EXT][PAU:1E][TPL:01]First second[PAU:28]third[PAL:04][END]",
        0, 0, 0);
    CheckSupplement(timed, sizeof(timed),
        "[EXT][PAU:1E][TPL:01]First[WAI]second[PAU:28]third[PAL:00][END]",
        0, 0, 0);
    CheckSupplement(number, sizeof(number), "[EXT]A[BCD:2,0AB0]B[END]", 1, CMD_END, 0);
    CheckSupplement(number, sizeof(number), "[EXT]A[BCD:2,0AB1]B[END]", 0, 0, 0);
    CheckSupplement(large, sizeof(large), "[EXT]ABCDEFGHIJKLMNOPQRSTUVWXYZ[RET]", 1, CMD_RET, 0);
    CheckSupplement(small, sizeof(small), "[EXT]ABCDEFGHIJKLMNOPQRSTUVWXYZ[RET]", 0, 0, 0);
    RejectMalformed("[EXT]A[PAL:02]B[END]");
    RejectMalformed("[EXT]A[PAU:00]B[END]");
    RejectMalformed("[EXT]A[BCD:6,0AB0]B[END]");
}

static void CheckProse(void)
{
    const uint8_t inherited[] = {0x40, 0x41, 0x42, CMD_N, 0x43, 0x44, 0x45, CMD_END};
    const uint8_t open[] = {0xd3, 0x40, CMD_N, 0x41, CMD_FIN, CMD_RET};
    const uint8_t choice[] = {0xd3, 0x40, CMD_N, 0xac, 0x41, CMD_N, 0xac, 0x42, CMD_RET};
    CheckSupplement(inherited, sizeof(inherited), "AB[FIN]CD[END]", 1, CMD_END, 0);
    CheckSupplement(inherited, sizeof(inherited), "ABCD[FIN]EF[END]", 0, 0, 0);
    CheckSupplement(open, sizeof(open), "A short sentence fits.[FIN][RET]", 1, CMD_RET, 1);
    CheckSupplement(open, sizeof(open), "Keep the final wait.[RET]", 0, 0, 0);
    CheckSupplement(choice, sizeof(choice), "A short prompt?[N] Yes[N] No[RET]", 1, CMD_RET, 0);
    CheckSupplement(choice, sizeof(choice), "A short prompt?[FIN] Yes[N] No[RET]", 0, 0, 0);
}

static void CheckAnchored(const uint8_t *data, size_t size, const char *text,
                          int accepted, int calls, int waits)
{
    Rom stock = {.rom = data, .size = size};
    Toks parsed = {0}, rendered = {0};
    CHECK(GaiaDialogue(text, &parsed));
    const int actual = GaiaStockWindow(&stock, 0, &rendered, &parsed, kGaiaStockAnchors);
    if (actual != accepted)
        fprintf(stderr, "unexpected stock-anchor result for %s\n", text);
    CHECK(actual == accepted);
    if (accepted) {
        CHECK(CountToken(&rendered, T_CMD, CMD_PRT, 0x88de96) == calls);
        CHECK(CountToken(&rendered, T_CMD, CMD_FIN, 0) == waits);
    }
    free(parsed.t);
    free(rendered.t);
}

static void CheckStockAnchors(void)
{
    const uint8_t advice[] = {CMD_PRT, 0x96, 0xde, 0x88, 0x40, CMD_N, 0x41,
                              CMD_FIN, CMD_RET};
    const uint8_t speakers[] = {0xc2, 9, 0xc2, 0, 0x40, CMD_FIN,
                                 0xc2, 9, 0xc2, 1, 0x41, CMD_END};
    CheckAnchored(advice, sizeof(advice),
                  "[EXT][PRT:08DE96]First page here.[FIN][RET]", 1, 1, 1);
    CheckAnchored(advice, sizeof(advice),
                  "[EXT][PRT:069705]First page here.[FIN][RET]", 0, 0, 0);
    CheckAnchored(advice, sizeof(advice),
                  "[EXT][PRT:08DE96]First long page[FIN]Twenty one more words[N]"
                  "all have to fit in one[N]four row advice window[N]"
                  "without removing waits.[FIN][RET]", 0, 0, 0);
    CheckAnchored(advice, sizeof(advice),
                  "[EXT]Extra.[PRT:08DE96]First page.[FIN]Next page.[FIN][RET]", 0, 0, 0);
    RejectMalformed("[EXT][PRT:08DE97]A[END]");
    RejectMalformed("[EXT][PRT:8DE96]A[END]");
    CheckAnchored(speakers, sizeof(speakers),
                  "[TPL:00]A[N]short line.[FIN][TPL:01]Reply.[END]", 1, 0, 1);
    CheckAnchored(speakers, sizeof(speakers),
                  "[TPL:00]A[N]short line.[FIN][TPL:03]Reply.[END]", 0, 0, 0);
    CheckAnchored(speakers, sizeof(speakers),
                  "[TPL:00]A[N]short line.[FIN]Reply.[END]", 0, 0, 0);
}

static void CheckMarkerTails(void)
{
    const uint32_t base = 0x049b82;
    const uint8_t data[] = {0xc9, 0x40, 0xc2, 9, 0x40, CMD_FIN, 0x41, CMD_END};
    uint8_t *bytes = calloc(base + sizeof(data), 1);
    CHECK(bytes);
    memcpy(bytes + base, data, sizeof(data));
    Rom stock = {.rom = bytes, .size = base + sizeof(data)};
    Label label = {.off = base, .marker = 2, .has_marker = 1};
    CHECK(GaiaMarkerTailOffset(&stock, &label) == base + 2);
    label.marker = 1;
    CHECK(!GaiaMarkerTailOffset(&stock, &label));
    label.marker = 2;
    bytes[base + 1] = 0x41;
    CHECK(!GaiaMarkerTailOffset(&stock, &label));
    Toks parsed = {0}, rendered = {0};
    CHECK(GaiaDialogue("[EXT]A short line.[FIN]B short line.[END]", &parsed));
    CHECK(GaiaStockMarkerTail(&stock, base + 2, &rendered, &parsed) == 0);
    free(parsed.t);
    free(rendered.t);
    free(bytes);
}

static void CheckMeasuredLayouts(void)
{
    const uint8_t box[] = {0xc2, 9, 0x40, CMD_END};
    const uint8_t timed[] = {0xc1, 0, 23, 0xc7, 15, 3,
        0x40, 0xc9, 0x28, 0xce, 0x41, 0x42, 0xc9, 0x3c, 0xc8, CMD_RET};
    Rom stock = {.rom = box, .size = sizeof(box)};
    Toks text = {0}, out = {0};
    CHECK(GaiaDialogue("[EXT]ABCDEFGHIJKLMNOPQRSTUVWXYZ[END]", &text));
    CHECK(!GaiaStockWindow(&stock, 0, &out, &text, kGaiaExtended));
    out.n = 0;
    CHECK(GaiaStockWindow(&stock, 0, &out, &text, kGaiaStockLayout));
    CHECK(out.n == 28 && out.t[27].code == CMD_END);
    RejectMalformed("[EXT]ABCDEFGHIJKLMNOPQRSTUVWXYZX[END]");
    stock = (Rom){.rom = timed, .size = sizeof(timed)};
    text.n = out.n = 0;
    CHECK(GaiaDialogue("[EXT]A short line[N]fits[PAU:28][CLR]The next timed[N]card[PAU:3C][CLD][RET]", &text));
    CHECK(GaiaStockWindow(&stock, 0, &out, &text, kGaiaStockLayout));
    CHECK(CountToken(&out, T_CMD, 0xc9, 0x28) == 1);
    CHECK(CountToken(&out, T_CMD, 0xc9, 0x3c) == 1);
    CHECK(CountToken(&out, T_CMD, 0xce, 0) == 1);
    CHECK(CountToken(&out, T_CMD, 0xc8, 0) == 1);
    CHECK(CountToken(&out, T_CMD, CMD_FIN, 0) == 0);
    text.n = out.n = 0;
    CHECK(GaiaDialogue("[EXT]Wrong[PAU:29][CLR]Card[PAU:3C][CLD][RET]", &text));
    CHECK(!GaiaStockWindow(&stock, 0, &out, &text, kGaiaStockLayout));
    text.n = out.n = 0;
    CHECK(GaiaDialogue("[EXT]Right[PAU:28][CLD]Card[PAU:3C][CLD][RET]", &text));
    CHECK(!GaiaStockWindow(&stock, 0, &out, &text, kGaiaStockLayout));
    RejectMalformed("[EXT]A[JMP:06BF7D]");
    free(text.t);
    free(out.t);
}

static void CheckSharedBoxes(void)
{
    uint8_t commands[] = {
        0xc2, 9, 0xc2, 0, 0x40, CMD_FIN, 0xc2, 1, 0x41, 0xc3, 0, CMD_END
    };
    Rom stock = {.rom = commands, .size = sizeof(commands)};
    Toks text = {0}, out = {0};
    CHECK(GaiaDialogue("[EXT][TPL:00]First speaker.[FIN][TPL:00]Continues.[FIN]"
                       "[TPL:01]Second speaker uses[N]the same wide box.[END]", &text));
    CHECK(!GaiaStockWindow(&stock, 0, &out, &text, kGaiaStockLayout));
    out.n = 0;
    CHECK(GaiaStockWindow(&stock, 0, &out, &text, kGaiaSharedBox));
    CHECK(CountToken(&out, T_CMD, 0xc2, 0) == 1);
    CHECK(CountToken(&out, T_CMD, 0xc2, 1) == 1);
    CHECK(CountToken(&out, T_CMD, 0xc2, 9) == 1);
    CHECK(CountToken(&out, T_CMD, 0xc3, 0) == 1);
    CHECK(CountToken(&out, T_CMD, CMD_END, 0) == 1);
    text.n = out.n = 0;
    CHECK(GaiaDialogue("[EXT][TPL:00]First.[FIN][TPL:02]Wrong speaker.[END]", &text));
    CHECK(!GaiaStockWindow(&stock, 0, &out, &text, kGaiaSharedBox));
    free(text.t);
    free(out.t);
}

static void CheckInheritedChoices(void)
{
    const uint32_t result = 0x088d1f;
    const uint8_t commands[] = {0xce, 0x40, 0xc3, 0, CMD_END};
    const size_t size = result + sizeof(commands);
    uint8_t *raw = calloc(size, 1);
    CHECK(raw != NULL);
    memcpy(raw + result - sizeof(commands), commands, sizeof(commands));
    memcpy(raw + result, commands, sizeof(commands));
    Rom stock = {.rom = raw, .size = size};
    Toks text = {0}, out = {0};
    CHECK(GaiaDialogue("A longer result[N]keeps this box open.[END]", &text));
    CHECK(!GaiaStockWindow(&stock, result, &out, &text, kGaiaSharedBox));
    out.n = 0;
    CHECK(GaiaStockWindow(&stock, result, &out, &text, kGaiaInheritedChoice));
    CHECK(CountToken(&out, T_CMD, 0xce, 0) == 1);
    CHECK(CountToken(&out, T_CMD, 0xc3, 0) == 1);
    CHECK(CountToken(&out, T_CMD, CMD_END, 0) == 1);
    CHECK(CountToken(&out, T_CMD, CMD_FIN, 0) == 0);
    out.n = 0;
    CHECK(!GaiaStockWindow(&stock, result - sizeof(commands), &out, &text,
                           kGaiaInheritedChoice));
    raw[result] = 0xc8;
    CHECK(!GaiaStockWindow(&stock, result, &out, &text, kGaiaInheritedChoice));
    free(text.t);
    free(out.t);
    free(raw);
}

static void CheckInterfaceText(void)
{
    Tok stock_tokens[] = {{.type = T_GLYPH}, {.type = T_GLYPH},
                          {.type = T_CMD, .code = 0x0d},
                          {.type = T_GLYPH}, {.type = T_GLYPH}};
    Toks menu = {.t = stock_tokens, .n = 5};
    uint8_t encoded[128];
    CHECK(GaiaMenuText(&menu, "AB[DBL]a?", encoded, 0) == 6);
    const uint8_t expected[] = {0x41, 0x42, 0x0d, 0x61, 0x3f, 0};
    CHECK(!memcmp(encoded, expected, sizeof(expected)));
    CHECK(!GaiaMenuText(&menu, "ABC[DBL]a?", encoded, 0));
    CHECK(!GaiaMenuText(&menu, "AB[N]a?", encoded, 0));
    CHECK(!GaiaMenuText(&menu, "AB[DBL][TBL]", encoded, 0));
    --menu.n;
    CHECK(!GaiaMenuText(&menu, "A[DBL]ab", encoded, 0));
    CHECK(GaiaMenuText(&menu, "A[DBL]ab", encoded, 1) == 5);
    CHECK(!GaiaMenuText(&menu, "A[DBL]abc", encoded, 1));
    CHECK(GaiaMenuExtendedText(NULL, "[DBL]By [TBL:@item_name_table_lola,B24].[DBL]END", encoded, 10, 2, 0x0d) == 14);
    CHECK(!GaiaMenuExtendedText(NULL, "[DBL]By [TBL:@item_name_table_lola,B25]", encoded, 10, 2, 0x0d));
    CHECK(!GaiaMenuExtendedText(NULL, "[DBL]A[DBL]B[DBL]C", encoded, 10, 2, 0x0d));
    CHECK(!GaiaMenuExtendedText(NULL, "A[DBL]B", encoded, 10, 2, 0x0d));

    const uint8_t rom[] = {0, 1, 8, 0, 2, 10, 0, 0, 0, CMD_RET, 1, CMD_RET};
    const Rom stock = {.rom = rom, .size = sizeof(rom)};
    const Structure layout = {.map_table = 1, .map_start = 8, .map_end = sizeof(rom)};
    const GaiaMapName names[] = {{8, "A"}, {10, "A"}};
    IogPack *pack = calloc(1, sizeof(*pack));
    CHECK(pack != NULL);
    GaiaMapSprites(&stock, &layout, pack, names, 2);
    CHECK(pack->sprite_translated == 2 && pack->npatches == 2);
    CHECK(pack->patches[0].data[0] == 1 && pack->patches[0].data[3] == 2);
    CHECK(pack->patches[0].data[1] == 8 && pack->patches[0].data[4] == 8);
    CHECK(pack->patches[1].len == 2 && pack->patches[1].data[1] == CMD_RET);
    IogTextFreePack(pack);

    const uint8_t scene_rom[] = {0, 4, 0, 0, 0xff, 0x40, 0x41, 0x42,
                                 0x43, 0x44, 0x45, CMD_RET, 0};
    const Rom scene = {.rom = scene_rom, .size = sizeof(scene_rom)};
    const Structure scene_layout = {.scene_table = 1, .scene_n = 1};
    unsigned occupied = kIogVirtualBankSize;
    pack = calloc(1, sizeof(*pack));
    CHECK(pack != NULL);
    CHECK(!GaiaTitle(&scene, &scene_layout, pack, &occupied, 4, "[END]", 18));
    CHECK(!GaiaTitle(&scene, &scene_layout, pack, &occupied, 4, "This title is too wide", 18));
    CHECK(!GaiaTitle(&scene, &scene_layout, pack, &occupied, 3, "Incorrect source", 26));
    CHECK(GaiaTitle(&scene, &scene_layout, pack, &occupied, 4, "This title is too wide", 26));
    CHECK(pack->npatches == 1 && pack->nbanks == 1 && pack->patches[0].len == 7);
    CHECK(pack->patches[0].data[4] == 0xcc && pack->patches[0].data[5] == 11);
    IogTextFreePack(pack);
}

static void CheckPairedEntry(void)
{
    uint8_t rom[] = {0, 0xd3, 0x40, 0x40, 0x40, 0x40, CMD_FIN,
                     0xd3, 0x40, 0x40, 0x40, 0x40, CMD_END};
    const Rom stock = {.rom = rom, .size = sizeof(rom)};
    Label label = {.off = 1, .marker = 6, .has_marker = 1};
    const Structure structure = {.l = &label, .nl = 1};
    IogPack *pack = calloc(1, sizeof(*pack));
    unsigned used = kIogVirtualBankSize;
    CHECK(pack != NULL);
    char paired[] = "[EXT]First page[FIN][RET]|[EXT]Shared second page[END]";
    char refused[] = "[EXT]First page[FIN][RET]|[EXT]Shared second page[END]";
    rom[6] = CMD_N;
    CHECK(!GaiaPairedEntry(&stock, &structure, 0, pack, &used, refused, 0));
    CHECK(pack->npatches == 0);
    rom[6] = CMD_FIN;
    CHECK(GaiaPairedEntry(&stock, &structure, 0, pack, &used, paired, 0));
    CHECK(pack->npatches == 2 && pack->patches[0].offset == 1 && pack->patches[1].offset == 7);
    unsigned tail = pack->patches[1].data[1];
    CHECK(tail > 0 && pack->banks[0][tail - 1] == CMD_FIN && pack->banks[0][tail] == 0xd3);
    IogTextFreePack(pack);
}

static void CheckStockReflow(void)
{
    const uint8_t stock_prose[] = {0xd3, 0x40, CMD_FIN, 0xce, 0x41, CMD_END};
    const Rom stock = {.rom = stock_prose, .size = sizeof(stock_prose)};
    Toks text = {0}, out = {0};
    CHECK(GaiaDialogue("[EXT]One longer message has[N]two different sentences.[END]", &text));
    CHECK(GaiaTryStockReflow(&stock, 0, &out, &text, 0));
    CHECK(CountToken(&out, T_CMD, 0xd3, 0) == 1);
    CHECK(CountToken(&out, T_CMD, CMD_FIN, 0) == 1);
    CHECK(CountToken(&out, T_CMD, 0xce, 0) == 1);
    text.n = out.n = 0;
    CHECK(GaiaDialogue("[EXT]A timed[PAU:22] line[END]", &text));
    CHECK(!GaiaTryStockReflow(&stock, 0, &out, &text, 0));

    const uint8_t stock_options[] = {0xd3, 0x40, CMD_N, 0xac, 0x41, CMD_N,
                                    0xac, 0x42, CMD_RET};
    const Rom prompt = {.rom = stock_options, .size = sizeof(stock_options)};
    text.n = out.n = 0;
    CHECK(GaiaDialogue("[EXT]Continue?[N]Yes[N]No[RET]", &text));
    CHECK(GaiaTryStockReflow(&prompt, 0, &out, &text, 0));
    CHECK(CountToken(&out, T_GLYPH, 0xac, 0) == 2);
    CHECK(CountToken(&out, T_CMD, CMD_N, 0) == 2);
    CHECK(CountToken(&out, T_CMD, CMD_RET, 0) == 1);
    const uint8_t stock_hold[] = {0xd3, 0x40, 0xc9, 0x30, 0xc8, CMD_RET};
    const Rom timed = {.rom = stock_hold, .size = sizeof(stock_hold)};
    text.n = out.n = 0;
    CHECK(GaiaDialogue("[EXT]A revised timed card[PAU:2A][RET]", &text));
    CHECK(GaiaTryStockReflow(&timed, 0, &out, &text, 1));
    CHECK(CountToken(&out, T_CMD, 0xc9, 0x30) == 1);
    CHECK(CountToken(&out, T_CMD, 0xc8, 0) == 1);
    CHECK(CountToken(&out, T_CMD, CMD_FIN, 0) == 0);
    text.n = out.n = 0;
    CHECK(GaiaDialogue("[EXT]A pause[PAU:2A] in the middle[RET]", &text));
    CHECK(!GaiaTryStockReflow(&timed, 0, &out, &text, 1));
    free(text.t);
    free(out.t);
}

static void CheckTimedBeats(void)
{
    const uint8_t cards[] = {0xd3, 0x40, 0xc9, 0x10, 0xce, 0x41,
                             0xc9, 0x20, 0xc8, CMD_RET};
    const Rom two_cards = {.rom = cards, .size = sizeof(cards)};
    Toks source = {0}, output = {0};
    CHECK(GaiaDialogue("[EXT]First card[PAU:30][CLR]Second card[PAU:40][CLD][RET]",
                       &source));
    CHECK(GaiaTryStockReflow(&two_cards, 0, &output, &source, 2));
    CHECK(CountToken(&output, T_CMD, 0xc9, 0x10) == 1);
    CHECK(CountToken(&output, T_CMD, 0xc9, 0x20) == 1);
    CHECK(CountToken(&output, T_CMD, 0xce, 0) == 1);
    CHECK(CountToken(&output, T_CMD, 0xc8, 0) == 1);
    CHECK(CountToken(&output, T_CMD, CMD_FIN, 0) == 0);
    source.n = output.n = 0;
    CHECK(GaiaDialogue("[EXT]First[PAU:20]Second[PAU:20]Third[RET]", &source));
    CHECK(!GaiaTryStockReflow(&two_cards, 0, &output, &source, 2));

    const uint8_t continuation[] = {0xc1, 3, 3, 0xc7, 3, 1, 0x40, 0xc9, 0x10,
                                    0x41, 0xc9, 0x20, 0xc8, CMD_RET};
    const Rom one_line = {.rom = continuation, .size = sizeof(continuation)};
    source.n = output.n = 0;
    CHECK(GaiaDialogue("[EXT]Word[PAU:10]dog[PAU:20][RET]", &source));
    CHECK(!GaiaTryStockReflow(&one_line, 0, &output, &source, 2));
    source.n = output.n = 0;
    CHECK(GaiaDialogue("[EXT]Word[PAU:10]up[PAU:20][RET]", &source));
    CHECK(GaiaTryStockReflow(&one_line, 0, &output, &source, 2));
    free(source.t);
    free(output.t);
}

static void CheckStockPrompts(void)
{
    static uint8_t bytes[0x10000];
    const uint8_t prompt[] = {0xd3, 0x40, CMD_FIN, 0x41, CMD_N,
                              0xc3, 0, 0xac, 0x69, 0x84, 0xa3, CMD_N,
                              0xac, 0x4d, 0x8e, 0xc3, 4, CMD_RET};
    const uint8_t caller[] = {0x02, 0xbf, 0, 0xa0, 0x02, 0xbe, 2, 1, 0, 0x90};
    const uint8_t branches[] = {0x10, 0x90, 0x20, 0x90, 0x30, 0x90};
    memcpy(bytes + 0xa000, prompt, sizeof(prompt));
    memcpy(bytes + 0x8010, caller, sizeof(caller));
    memcpy(bytes + 0x9000, branches, sizeof(branches));
    const Rom stock = {.rom = bytes, .size = sizeof(bytes)};
    Toks source = {0}, output = {0};

    CHECK(GaiaDialogue("A prelude.[FIN]Do you want to keep[N]going from here today?[N]Yes[N]No[RET]",
                       &source));
    CHECK(GaiaCompilePrompt(&stock, 0xa000, &output, &source));
    CHECK(CountToken(&output, T_CMD, 0xd3, 0) == 1);
    CHECK(CountToken(&output, T_CMD, CMD_FIN, 0) == 1);
    CHECK(CountToken(&output, T_CMD, 0xc3, 0) == 1);
    CHECK(CountToken(&output, T_CMD, 0xc3, 4) == 1);
    CHECK(CountToken(&output, T_CMD, CMD_RET, 0) == 1);
    int last_page = output.n - 1;
    while (last_page > 0 && output.t[last_page].code != CMD_FIN)
        --last_page;
    CHECK(last_page > 0);
    const Toks final_page = {.t = output.t + last_page + 1, .n = output.n - last_page - 1};
    CHECK(CountToken(&final_page, T_CMD, CMD_N, 0) == 2);

    source.n = output.n = 0;
    CHECK(GaiaDialogue("Prelude.[FIN]Continue?[N]No[N]Yes[RET]", &source));
    CHECK(!GaiaCompilePrompt(&stock, 0xa000, &output, &source));
    CHECK(output.n == 0);

    source.n = 0;
    memcpy(bytes + 0x8030, caller, sizeof(caller));
    bytes[0x8037] = 2;
    CHECK(GaiaDialogue("Prelude.[FIN]Continue?[N]Yes[N]No[RET]", &source));
    CHECK(!GaiaCompilePrompt(&stock, 0xa000, &output, &source));
    free(output.t);
    free(source.t);
}

static void CheckJewelerAmounts(void)
{
    static uint8_t bytes[0x90000];
    const uint8_t opener[] = {0xc1,3,0x0b,0xc7,8,7,0xce,0xd2,0,0xca};
    const uint8_t caller[] = {0x02,0xbf,0x5e,0xd6};
    const uint8_t list_call[] = {0x02,0xbf,0x67,0xd2,0x02,0xbf,0x17,0xd6};
    uint8_t label[] = {0x40,0xac,0xac,0xac,0xac,0xac,0xac,0xac,
                       0xac,0xac,0xac,0xac,0xac,0xac,0x21,0x22,
                       CMD_N,0xc3,0,CMD_RET};
    memcpy(bytes + 0x08d617, opener, sizeof(opener));
    memcpy(bytes + 0x08cfa6, list_call, sizeof(list_call));
    memcpy(bytes + 0x08cfe2, caller, sizeof(caller));
    memcpy(bytes + 0x08d65e, label, sizeof(label));
    const Rom stock = {.rom = bytes, .size = sizeof(bytes)};
    Toks source = {0}, output = {0};
    CHECK(GaiaDialogue("Power Force:    12[N][RET]", &source));
    CHECK(GaiaCompileJewelerReward(&stock, 0x08d65e, &output, &source));
    CHECK(output.n == 19 && output.t[14].code == 0x21 && output.t[15].code == 0x22);
    CHECK(output.t[16].code == CMD_N && output.t[17].code == 0xc3);
    CHECK(output.t[17].a[0] == 0 && output.t[18].code == CMD_RET);
    source.n = output.n = 0;
    CHECK(GaiaDialogue("Power Force:    13[N][RET]", &source));
    CHECK(!GaiaCompileJewelerReward(&stock, 0x08d65e, &output, &source));
    source.n = 0;
    CHECK(GaiaDialogue("Longer than room 12[N][RET]", &source));
    CHECK(!GaiaCompileJewelerReward(&stock, 0x08d65e, &output, &source));
    source.n = 0;
    bytes[0x08d61b] = 9;
    CHECK(GaiaDialogue("Power Force:    12[N][RET]", &source));
    CHECK(!GaiaCompileJewelerReward(&stock, 0x08d65e, &output, &source));
    CHECK(output.n == 0);
    free(output.t);
    free(source.t);
}

static void CheckSelectorReplies(void)
{
    static uint8_t bytes[0x50000];
    const uint8_t call[] = {0x02,0xbf,0x0e,0xc4,0x02,0xbe,2,2,0xf6,0xc3};
    const uint8_t table[] = {0xfc,0xc3,0x02,0xc4,0xfc,0xc3};
    const uint8_t reply_call[] = {0x02,0xbf,0xd5,0xc4};
    const uint8_t prompt[] = {0xc2,0x0f,0xc2,4,0x40,CMD_FIN,0x41,CMD_RET};
    const uint8_t reply[] = {0xce,0xc2,4,0x42,CMD_FIN,CMD_RET};
    memcpy(bytes + 0x04c3ec, call, sizeof(call));
    memcpy(bytes + 0x04c3f6, table, sizeof(table));
    memcpy(bytes + 0x04c3fc, reply_call, sizeof(reply_call));
    memcpy(bytes + 0x04c40e, prompt, sizeof(prompt));
    memcpy(bytes + 0x04c4d5, reply, sizeof(reply));

    const Rom stock = {.rom = bytes, .size = sizeof(bytes)};
    Toks source = {0}, output = {0};
    CHECK(GaiaDialogue("A longer reply from the[N]same speaker.[FIN][RET]", &source));
    CHECK(GaiaCompileSelectorReply(&stock, 0x04c4d5, &output, &source));
    CHECK(CountToken(&output, T_CMD, 0xce, 0) == 1);
    CHECK(CountToken(&output, T_CMD, 0xc2, 4) == 1);
    CHECK(CountToken(&output, T_CMD, CMD_FIN, 0) == 1);
    CHECK(CountToken(&output, T_CMD, CMD_RET, 0) == 1);
    CHECK(CountToken(&output, T_CMD, 0xd3, 0) == 0);

    output.n = 0;
    bytes[0x04c3fa] = 0x02;
    CHECK(!GaiaCompileSelectorReply(&stock, 0x04c4d5, &output, &source));
    bytes[0x04c3fa] = 0xfc;
    bytes[0x04c40f] = 4;
    CHECK(!GaiaCompileSelectorReply(&stock, 0x04c4d5, &output, &source));
    CHECK(output.n == 0);
    free(output.t);
    free(source.t);
}

static void CheckAbilityNotice(void)
{
    uint8_t *bytes = calloc(1, 0x090000);
    CHECK(bytes);
    const Rom stock = {.rom = bytes, .size = 0x090000};
    uint8_t *notice = bytes + 0x08eb68;
    const uint8_t opener[] = {0xd3, 0xd5, 9, CMD_ADR, 0x8f, 0xeb, 0xac, 0x0a, CMD_N};
    memcpy(notice, opener, sizeof(opener));
    const uint8_t ending[] = {0xc9, 0x78, CMD_FIN, CMD_RET};
    memcpy(notice + 25, ending, sizeof(ending));
    const uint8_t table[] = {0x9b, 0xeb, 0xa2, 0xeb, 0xab, 0xeb, 0xb2, 0xeb,
                             0xba, 0xeb, 0xc7, 0xeb};
    memcpy(bytes + 0x08eb8f, table, sizeof(table));
    Toks source = {0}, result = {0};
    CHECK(GaiaDialogue("[EXT]Example[N]Power[N][RET]", &source));
    CHECK(GaiaCompileAbilityNotice(&stock, &result, &source));
    CHECK(result.t[0].code == 0xd3 && result.t[1].code == 0xd5 &&
          result.t[1].a[0] == 5 && result.t[result.n - 1].code == CMD_RET);
    CHECK(CountToken(&result, T_CMD, CMD_N, 0) == 2);
    CHECK(CountToken(&result, T_CMD, CMD_ADR, 0xeb8f) == 0);
    result.n = 0;
    bytes[0x08eb8f]++;
    CHECK(!GaiaCompileAbilityNotice(&stock, &result, &source));
    bytes[0x08eb8f]--;
    notice[6]++;
    CHECK(!GaiaCompileAbilityNotice(&stock, &result, &source));
    notice[6]--;
    notice[26]--;
    CHECK(!GaiaCompileAbilityNotice(&stock, &result, &source));
    free(source.t);
    free(result.t);
    free(bytes);
}

static void CheckClosedTimedLayout(void)
{
    uint8_t bytes[] = {0xc1,3,4,0xc7,13,1,0x40,0xc9,0x5a,0xc8,CMD_RET};
    const Rom stock = {.rom = bytes, .size = sizeof(bytes)};
    Toks source = {0}, output = {0};
    CHECK(GaiaDialogue("[EXT]A fuller description of[N]the scene unfolds.[PAU:40][RET]", &source));
    CHECK(GaiaCompileLegacyTiming(&stock, 0, &output, &source));
    CHECK(output.t[0].code == 0xc1 && output.t[0].a[0] == 3 && output.t[0].a[1] == 4);
    CHECK(output.t[1].code == 0xc7 && output.t[1].a[0] == 13 && output.t[1].a[1] == 2);
    CHECK(CountToken(&output, T_CMD, 0xc9, 0x5a) == 1);
    CHECK(CountToken(&output, T_CMD, 0xc8, 0) == 1);
    CHECK(CountToken(&output, T_CMD, CMD_RET, 0) == 1);
    output.n = source.n = 0;
    CHECK(GaiaDialogue("[EXT]A description[PAU:20][N]with one extra hold[PAU:40][RET]", &source));
    CHECK(!GaiaCompileLegacyTiming(&stock, 0, &output, &source));
    bytes[9] = CMD_RET;
    output.n = source.n = 0;
    CHECK(GaiaDialogue("[EXT]A fuller description of[N]the scene unfolds.[PAU:40][RET]", &source));
    CHECK(!GaiaCompileLegacyTiming(&stock, 0, &output, &source));
    free(output.t);
    free(source.t);
}

static void CheckJingleNotice(void)
{
    static uint8_t bytes[0x0b0000];
    const uint8_t before[] = {0x02,0xbf,0xb4,0xa7,0x02,0xd4};
    const uint8_t call[] = {0x02,0x19,0x17,0xef,0xa7,0x8a};
    const uint8_t lead[] = {0xd3,0x40,CMD_FIN,CMD_RET};
    const uint8_t notice[] = {0xce,CMD_SFX,0,0xd5,9,0x41,0xc9,0xff,CMD_END};
    memcpy(bytes + 0x0aa751, before, sizeof(before));
    memcpy(bytes + 0x0aa760, call, sizeof(call));
    memcpy(bytes + 0x0aa7b4, lead, sizeof(lead));
    memcpy(bytes + 0x0aa7ef, notice, sizeof(notice));
    const Rom rom = {.rom = bytes, .size = sizeof(bytes)};
    Toks source = {0}, output = {0};
    CHECK(GaiaDialogue("[EXT]You got a key.[PAU:D0][RET]", &source));
    CHECK(GaiaCompileJingleNotice(&rom, 0x0aa7ef, &output, &source));
    CHECK(CountToken(&output, T_CMD, CMD_SFX, 0) == 1);
    CHECK(CountToken(&output, T_CMD, 0xd5, 9) == 1);
    CHECK(CountToken(&output, T_CMD, 0xc9, 0xff) == 1);
    CHECK(CountToken(&output, T_CMD, CMD_END, 0) == 1);
    CHECK(CountToken(&output, T_CMD, CMD_RET, 0) == 0);
    bytes[0x0aa7b6] = CMD_END;
    output.n = 0;
    CHECK(!GaiaCompileJingleNotice(&rom, 0x0aa7ef, &output, &source));
    CHECK(output.n == 0);
    free(output.t);
    free(source.t);
}

int main(void)
{
    const uint8_t plain[] = {0xc2, 9, 0x40, CMD_END};
    const uint8_t changed[] = {0xc2, 9, 0xc2, 0, 0x40, CMD_FIN,
                               0xc2, 1, 0x41, 0xc3, 0, CMD_END};
    const uint8_t moving_box[] = {0xc2, 9, 0x40, CMD_FIN, 0xc2, 8, 0x41, CMD_END};
    const uint8_t mid_speaker[] = {0xc2, 9, 0x40, 0xc2, 1, 0x41, CMD_END};
    const uint8_t extra_clear[] = {0xc2, 9, 0x40, 0xce, 0x41, CMD_END};
    const uint8_t inherited[] = {0xce, 0x40, CMD_END};
    CheckWindow(plain, sizeof(plain), "A[N]B[N]C[END]", 1, 1, 0, 0);
    CheckWindow(plain, sizeof(plain),
                "For longer text[N]wrap the words[N]across a second page[END]", 1, 2, 0, 0);
    CheckWindow(plain, sizeof(plain), "[TPL:01]A[END]", 1, 1, 0, 0);
    CheckWindow(changed, sizeof(changed), "[TPL:00]A[N]B[N]C[FIN][TPL:01]D[END]", 1, 2, 1, 1);
    CheckWindow(changed, sizeof(changed), "[TPL:00]A[FIN][TPL:02]B[END]", 0, 0, 0, 0);
    CheckWindow(changed, sizeof(changed), "A[FIN]B[END]", 0, 0, 0, 0);
    CheckWindow(moving_box, sizeof(moving_box), "A[FIN]B[END]", 1, 2, 0, 0);
    CheckWindow(moving_box, sizeof(moving_box), "A[FIN]B[N]C[END]", 1, 2, 0, 0);
    CheckWindow(moving_box, sizeof(moving_box),
                "A[FIN]This line uses its limit[N]Another full line[END]", 0, 0, 0, 0);
    CheckWindow(mid_speaker, sizeof(mid_speaker), "A[FIN][TPL:01]B[END]", 0, 0, 0, 0);
    CheckWindow(extra_clear, sizeof(extra_clear), "A[N]B[N]C[END]", 0, 0, 0, 0);
    CheckWindow(inherited, sizeof(inherited), "A[END]", 1, 1, 0, 0);
    CheckWindow(inherited, sizeof(inherited), "AB[END]", 0, 0, 0, 0);
    RejectMalformed("[TPL:11]A[END]");
    RejectMalformed("A[TPL:01]B[END]");
    RejectMalformed("[TPL:+1]A[END]");
    RejectMalformed("[TPL:01][TPL:01]A[END]");
    CheckStockSound();
    CheckPageControls();
    CheckReturningFragments();
    CheckExtendedControls();
    CheckProse();
    CheckStockAnchors();
    CheckMarkerTails();
    CheckMeasuredLayouts();
    CheckSharedBoxes();
    CheckInheritedChoices();
    CheckInterfaceText();
    CheckPairedEntry();
    CheckStockReflow();
    CheckTimedBeats();
    CheckStockPrompts();
    CheckJewelerAmounts();
    CheckSelectorReplies();
    CheckClosedTimedLayout();
    CheckJingleNotice();
    CheckAbilityNotice();
    puts("Passed Gaia stock-window and speaker checks");
    return 0;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="clang")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT / ".local").resolve()):
        parser.error("--out must be within the project's .local directory")
    out.mkdir(parents=True, exist_ok=False)
    assert convert("[TPL:A][TPL:0]A[N]B[N]C[N]D[FIN][TPL:1]E[END]", []) == (
        "[TPL:00]A[N]B[N]C[FIN]D[FIN][TPL:01]E[END]"
    )
    assert convert("[PAU:1E][DLG:3,11][SIZ:D,3]A[FIN]B[PAU:28][PAL:0][END]", []) == (
        "[PAU:1E]A[FIN]B[PAU:28][PAL:00][END]"
    )
    assert convert("[DEF]Pick one?[N][PAL:0] Yes[N] No", []) == (
        "Pick one?[N] Yes[N] No[RET]"
    )
    assert convert("Kept [BCD:2,AB0][N]pieces.[RET]", []) == (
        "Kept [BCD:2,0AB0][N]pieces.[RET]"
    )
    assert convert_return("[PRT:@dialogstring_08DE96]Example[FIN]", (), extended=True) == (
        "[EXT][PRT:08DE96]Example[FIN][RET]"
    )
    notice = "[TPL:E][DLY:5]Example[N]Power[N][ADR:&table_08EB8F,AAC]![PAU:50][FIN]"
    assert convert_extended("08EB68", notice, ()) == "[LAY][EXT]Example[N]Power[N][RET]"
    try:
        convert_extended("08EB68", notice.replace("08EB8F", "08EBD3"), ())
    except ValueError:
        pass
    else:
        raise AssertionError("Unexpected ability name table was accepted")
    for invalid_call in ("[PRT:@dialogstring_08DE97]", "[PRT:@dialogstring_08DE96+M]"):
        try:
            convert_return(invalid_call + "Example[FIN]", (), extended=True)
        except ValueError:
            pass
        else:
            raise AssertionError("Unexpected Gaia print target was accepted")
    for invalid in (
        "[SIZ:D,3]A[END]", "[DLG:3,11]A[END]", "[DLG:1F,11][SIZ:D,3]A[END]",
        "A[PAU:1E]B[END]", "A[PAL:0]B[END]", "A[PAL:0][FIN]B[END]",
    ):
        try:
            convert(invalid, [])
        except ValueError:
            continue
        raise AssertionError(f"Accepted malformed dialogue {invalid!r}")
    source = out / "test.c"
    source.write_text(HARNESS, encoding="ascii")
    binary = out / "test.exe"
    subprocess.run([args.compiler, "-std=c11", "-I", str(ROOT / "src"),
                    str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
