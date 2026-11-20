#!/usr/bin/env python3
"""Check stock-window Gaia dialogue handling with ROM-free synthetic messages."""
import argparse
from pathlib import Path
import subprocess

from import_gaialabs_dialogue import convert, convert_return

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
    CHECK(GaiaMenuText(&menu, "AB[DBL]a?", encoded) == 6);
    const uint8_t expected[] = {0x41, 0x42, 0x0d, 0x61, 0x3f, 0};
    CHECK(!memcmp(encoded, expected, sizeof(expected)));
    CHECK(!GaiaMenuText(&menu, "ABC[DBL]a?", encoded));
    CHECK(!GaiaMenuText(&menu, "AB[N]a?", encoded));
    CHECK(!GaiaMenuText(&menu, "AB[DBL][TBL]", encoded));

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
    CHECK(!GaiaTitle(&scene, &scene_layout, pack, &occupied, 4, "[END]"));
    CHECK(!GaiaTitle(&scene, &scene_layout, pack, &occupied, 4, "This title is too wide"));
    CHECK(!GaiaTitle(&scene, &scene_layout, pack, &occupied, 3, "Incorrect source"));
    CHECK(GaiaTitle(&scene, &scene_layout, pack, &occupied, 4, "Long title"));
    CHECK(pack->npatches == 1 && pack->nbanks == 1 && pack->patches[0].len == 7);
    CHECK(pack->patches[0].data[4] == 0xcc && pack->patches[0].data[5] == 7);
    IogTextFreePack(pack);
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
