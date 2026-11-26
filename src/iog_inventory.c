/*
 * Inventory enhancements (trusted plugins "iog.stacking" and "iog.equipped").
 *
 * Stacking: Red Jewels ($01), Herbs ($06) and Crystals ($0E) keep a single
 * inventory slot; the extra units wait in the save-area bytes GaiaLabs uses
 * for the same purpose ($0B56 jewels, $0B55 herbs, $0B57 crystals: unused by
 * the game, inside the $0A00-$0BFF block every save slot stores). Using the
 * visible unit (a herb, or a jewel given to the Gem Man, who counts them in
 * $0AB0 one by one) brings the next one out, re-equipped if it was equipped.
 *
 * Counters and the equipped marker are drawn over the inventory screen
 * (scene $FF) after each frame is rasterised, with the digits of the game's
 * own BG3 font taken from VRAM. The slot positions come from the menu's
 * table at $02:EB86 in the player's ROM.
 */

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include "common_cpu_infra.h"
#include "common_rtl.h"
#include "mod_runtime.h"
#include "iog_randomizer.h"
#include "snes/ppu.h"
#include "snes/snes.h"

#include "iog_inventory.h"

extern Ppu *g_ppu;

enum {
    kSlots = 0x0AB4, kEquippedSlot = 0x0AC4, kEquippedType = 0x0AC6,
    kSlotTable = 0x02EB86,   /* 16 x (x16, y16): sprite position of each slot */
};

typedef struct Stack { uint8_t item; uint16_t extra_at; } Stack;
static const Stack kStacks[] = { {0x01, 0x0B56}, {0x06, 0x0B55}, {0x0E, 0x0B57} };

static bool g_stacking, g_equipped;
static uint8_t g_prev_equipped_type;

static uint8_t *Ram(void) { return g_snes->ram; }
static uint16_t Rd(uint32_t a) { return Ram()[a] | Ram()[a + 1] << 8; }
static void Wr(uint32_t a, uint16_t v) { Ram()[a] = (uint8_t)v; Ram()[a + 1] = (uint8_t)(v >> 8); }

static bool InPlay(void)
{
    /* The title and file select reuse this RAM; act only with a game loaded. */
    return Rd(0x09AA) != 0 || Rd(0x0644) == 0x00FF;
}

/* ---- the Jeweler takes every stacked jewel ---------------------------------
 * Gem's "Give you Red Jewels" counts the jewel items in the 16 slots, adds
 * them to $0AB0 (BCD), removes them and pays the reward tiers. With stacking
 * only one jewel is in a slot, so he took one per talk. While his menu is up
 * (a choice menu, $065C, with Gem's actor beside the player), the stacked
 * jewels are laid out into the free slots so his own count takes them; any
 * that do not fit are added to his count once he has taken the rest. */
static bool g_gem_session;
static uint16_t g_gem_given_before;

static bool GemBeside(void)
{
    const uint8_t *ram = Ram();
    const int px = (int16_t)Rd(0x1014), py = (int16_t)Rd(0x1016);
    unsigned a = Rd(0x56), n = 0;
    while (a >= 0x1000 && a < 0x1FC0 && n++ < 84) {
        const unsigned pc = Rd(a);
        if ((ram[a + 2] & 0x3F) == 0x08 && pc >= 0xCEA3 && pc < 0xD093) {
            const int dx = (int16_t)Rd(a + 0x14) - px, dy = (int16_t)Rd(a + 0x16) - py;
            return dx * dx + dy * dy < 48 * 48;
        }
        a = Rd(a + 6);
    }
    return false;
}

static uint16_t BcdAdd(uint16_t bcd, unsigned add)
{
    unsigned v = ((bcd >> 12) & 15) * 1000 + ((bcd >> 8) & 15) * 100 + ((bcd >> 4) & 15) * 10 + (bcd & 15) + add;
    if (v > 9999) v = 9999;
    return (uint16_t)((v / 1000) << 12 | (v / 100 % 10) << 8 | (v / 10 % 10) << 4 | (v % 10));
}

/* True while the jewels are laid out for Gem: the merge below waits. */
static bool GemFrame(void)
{
    uint8_t *slots = &Ram()[kSlots];
    const bool menu = Rd(0x065C) != 0, message = (Rd(0x09EC) & 0x6000) != 0;
    if (!g_gem_session) {
        if (!menu || !Ram()[0x0B56] || !GemBeside())
            return false;
        bool held = false;
        for (int i = 0; i < 16; i++) held |= slots[i] == 0x01;
        if (!held) return false;
        g_gem_session = true;
        g_gem_given_before = Rd(0x0AB0);
        for (int i = 0; i < 16 && Ram()[0x0B56]; i++)
            if (!slots[i]) { slots[i] = 0x01; Ram()[0x0B56]--; }
        return true;
    }
    bool held = false;
    for (int i = 0; i < 16; i++) held |= slots[i] == 0x01;
    if (!held && Rd(0x0AB0) != g_gem_given_before) {
        /* He took every jewel in the slots: hand him the rest too. */
        if (Ram()[0x0B56]) {
            Wr(0x0AB0, BcdAdd(Rd(0x0AB0), Ram()[0x0B56]));
            Ram()[0x0B56] = 0;
        }
        g_gem_session = false;
        return false;
    }
    if (!menu && !message) {   /* closed without giving: stack them again */
        g_gem_session = false;
        return false;
    }
    return true;
}

static void StackFrame(void)
{
    if (!g_snes || !InPlay())
        return;
    if (GemFrame())
        return;
    uint8_t *slots = &Ram()[kSlots];
    const int equipped = (int16_t)Rd(kEquippedSlot);
    for (size_t k = 0; k < sizeof(kStacks) / sizeof(kStacks[0]); k++) {
        const Stack *s = &kStacks[k];
        int first = -1, count = 0;
        for (int i = 0; i < 16; i++)
            if (slots[i] == s->item) {
                if (first < 0)
                    first = i;
                count++;
            }
        uint8_t extra = Ram()[s->extra_at];
        if (count > 1) {
            /* Merge: keep the first slot, count the rest. */
            for (int i = first + 1; i < 16; i++)
                if (slots[i] == s->item) {
                    slots[i] = 0;
                    if (equipped == i)
                        Wr(kEquippedSlot, (uint16_t)first);
                    if (extra < 0xFF)
                        extra++;
                }
        } else if (count == 0 && extra) {
            /* The visible unit was used: bring out the next one. */
            for (int i = 0; i < 16; i++)
                if (!slots[i]) {
                    slots[i] = s->item;
                    extra--;
                    if (g_prev_equipped_type == s->item && (int16_t)Rd(kEquippedSlot) < 0) {
                        Wr(kEquippedSlot, (uint16_t)i);
                        Wr(kEquippedType, s->item);
                    }
                    break;
                }
        }
        Ram()[s->extra_at] = extra;
    }
    if ((int16_t)Rd(kEquippedSlot) >= 0)
        g_prev_equipped_type = (uint8_t)Rd(kEquippedType);
    else if (!InPlay())
        g_prev_equipped_type = 0;
}

static void ActivateStacking(void)
{
    if (IogRandomizerActive())
        return;   /* IoGR stacks herbs its own way */
    g_stacking = true;
    snes_mod_register_frame_callback(StackFrame);
}

static void ActivateEquipped(void) { g_equipped = true; }

/* Cheat (in-game settings): hold every red jewel not yet given to the Gem
 * Man, i.e. 50 minus $0AB0 (a BCD count). One visible jewel, the rest in
 * the stacking store ($0B56), so stacking is switched on too. Returns how
 * many are held after, or -1 if there is no free slot. */
int IogInventoryAllRedJewels(void)
{
    if (!g_snes || !Rd(0x09AA))
        return -1;
    const unsigned bcd = Rd(0x0AB0) & 0xFF;
    const int given = (bcd >> 4) * 10 + (bcd & 15);
    const int want = given < 50 ? 50 - given : 0;
    uint8_t *slots = &Ram()[kSlots];
    int slot = -1;
    for (int i = 0; i < 16 && slot < 0; i++)
        if (slots[i] == 0x01) slot = i;
    for (int i = 0; i < 16 && slot < 0 && want; i++)
        if (!slots[i]) slot = i;
    if (want && slot < 0)
        return -1;
    for (int i = 0; i < 16; i++)   /* one visible jewel, the rest stacked */
        if (slots[i] == 0x01 && i != slot) slots[i] = 0;
    if (want) {
        slots[slot] = 0x01;
        Ram()[0x0B56] = (uint8_t)(want - 1);
    } else {
        if (slot >= 0) slots[slot] = 0;
        Ram()[0x0B56] = 0;
    }
    if (!g_stacking && !IogRandomizerActive()) {
        g_stacking = true;
        snes_mod_register_frame_callback(StackFrame);
        snes_mod_runtime_persist_feature_c("iog.enhancements", "stacking", 1, NULL, NULL);
    }
    return want;
}

static void ResetInventoryMods(void) { g_stacking = g_equipped = false; }

/* ---- overlay ------------------------------------------------------------- */

static uint32_t Shade(uint32_t rgb)
{
    const uint32_t m = g_ppu->brightnessMult[31];
    return (((rgb >> 16) & 0xff) * m / 255) << 16 | (((rgb >> 8) & 0xff) * m / 255) << 8 |
           ((rgb & 0xff) * m / 255);
}

/* Plot one native pixel (screen x in [-extra, 256+extra)) at 1x and, on a
 * line that has a 4x version, as a 4x4 block there too. */
static void Plot(int x, int y, uint32_t rgb)
{
    const int W = 256 + 2 * g_ppu->extraLeftRight;
    const int bx = x + g_ppu->extraLeftRight;
    if (bx < 0 || bx >= W || y < 0 || y >= 224 || !g_ppu->renderBuffer)
        return;
    rgb = Shade(rgb);
    ((uint32_t *)(g_ppu->renderBuffer + (size_t)y * g_ppu->renderPitch))[bx] = rgb;
    if (g_ppu->m7hdBuffer && g_ppu->m7hdLine[y])
        for (int s = 0; s < 4; s++) {
            uint32_t *d = g_ppu->m7hdBuffer + (size_t)(4 * y + s) * g_ppu->m7hdPitch + 4 * bx;
            d[0] = d[1] = d[2] = d[3] = rgb;
        }
}

/* A bold 4x7 digit font of our own. The game's BG3 font, read from VRAM,
 * came out garbled at this size (its colour indices are not an outline). */
static const uint8_t kDigits[10][7] = {   /* 4 bits per row, MSB = left */
    {0x6,0x9,0x9,0x9,0x9,0x9,0x6}, {0x2,0x6,0x2,0x2,0x2,0x2,0x7},
    {0x6,0x9,0x1,0x2,0x4,0x8,0xF}, {0xE,0x1,0x1,0x6,0x1,0x1,0xE},
    {0x9,0x9,0x9,0xF,0x1,0x1,0x1}, {0xF,0x8,0xE,0x1,0x1,0x9,0x6},
    {0x6,0x8,0x8,0xE,0x9,0x9,0x6}, {0xF,0x1,0x1,0x2,0x2,0x4,0x4},
    {0x6,0x9,0x9,0x6,0x9,0x9,0x6}, {0x6,0x9,0x9,0x7,0x1,0x1,0x6},
};

static void Digit(int x, int y, unsigned d, uint32_t fg)
{
    for (int r = 0; r < 7; r++)
        for (int c = 0; c < 4; c++)
            if (kDigits[d][r] & (8 >> c))
                Plot(x + c, y + r, fg);
}

static void Number(int x, int y, unsigned n)
{
    char buf[8];
    int len = 0;
    do buf[len++] = (char)('0' + n % 10); while ((n /= 10) && len < 3);
    /* A dark badge with a light rim, so it reads on both the light platform
     * and the dark sea. Right-aligned on x, 5-pixel advance. */
    const int left = x - 5 * len - 2, right = x + 1, top = y - 2, bottom = y + 8;
    for (int py = top; py <= bottom; py++)
        for (int px = left; px <= right; px++) {
            const bool edge = py == top || py == bottom || px == left || px == right;
            const bool corner = (py == top || py == bottom) && (px == left || px == right);
            if (!corner)
                Plot(px, py, edge ? 0xB8C0D8 : 0x101828);
        }
    for (int i = 0; i < len; i++)
        Digit(x - 5 * (i + 1) + 1, y, (unsigned)(buf[i] - '0'), 0xFFFFFF);
}

static void Frame(int x0, int y0, int w, int h, uint32_t rgb)
{
    for (int i = 0; i < w; i++) {
        Plot(x0 + i, y0, rgb);
        Plot(x0 + i, y0 + h - 1, rgb);
    }
    for (int j = 0; j < h; j++) {
        Plot(x0, y0 + j, rgb);
        Plot(x0 + w - 1, y0 + j, rgb);
    }
}

/* Is an item icon on screen over the slot at (x, y)? The inventory page
 * draws each held item as a sprite just above its slot (the equipped one
 * lifted); the Cond. page and the menu's transitions do not. */
static bool SlotIconShown(int x, int y)
{
    for (int i = 0; i < 128; i++) {
        const int lo = g_ppu->oam[i * 2], hb = (g_ppu->highOam[i >> 2] >> ((i & 3) * 2)) & 3;
        int sx = (lo & 0xff) | (hb & 1) << 8;
        const int sy = lo >> 8;
        if (sx >= 256) sx -= 512;
        if (sx + 8 >= x - 12 && sx + 8 <= x + 12 && sy >= y - 30 && sy <= y - 6) {
            return true;
        }
    }
    return false;
}

/* Every held item has its icon over its slot: the inventory page itself.
 * One match is not enough: on the Cond. page Will's portrait sits where
 * the icon of the seventh slot would be. */
static bool AllSlotIconsShown(void)
{
    const uint8_t *rom = g_snes->cart->rom;
    const uint8_t *slots = &Ram()[kSlots];
    int held = 0;
    for (int i = 0; i < 16; i++) {
        const uint8_t *e = rom + kSlotTable + 4 * i;
        if (!slots[i])
            continue;
        ++held;
        if (!SlotIconShown(e[0] | e[1] << 8, e[2] | e[3] << 8))
            return false;
    }
    return held > 0;
}

/* The inventory page of the pause menu is fully on screen. */
int IogInventoryPageShown(void)
{
    if (!g_snes || !g_ppu || Rd(0x0644) != 0x00FF || g_ppu->brightnessMult[31] != 255)
        return 0;
    return AllSlotIconsShown();
}

void IogInventoryOverlay(void)
{
    if (!g_snes || !g_ppu || (!g_stacking && !g_equipped) || Rd(0x0644) != 0x00FF ||
        RtlSpeculativeFrame())   /* the companion's captures keep the stock art */
        return;
    const uint8_t *rom = g_snes->cart->rom;
    const uint8_t *slots = &Ram()[kSlots];
    const int equipped = (int16_t)Rd(kEquippedSlot);
    /* Only on the inventory page itself: not on Cond., not mid-transition. */
    if (!AllSlotIconsShown())
        return;
    for (int i = 0; i < 16; i++) {
        const uint8_t *e = rom + kSlotTable + 4 * i;
        const int x = e[0] | e[1] << 8, y = e[2] | e[3] << 8;
        if (g_equipped && i == equipped && slots[i])
            Frame(x - 10, y - 13, 20, 16, 0xF8D050);
        if (!g_stacking || !slots[i])
            continue;
        for (size_t k = 0; k < sizeof(kStacks) / sizeof(kStacks[0]); k++)
            if (kStacks[k].item == slots[i]) {
                const unsigned n = 1u + Ram()[kStacks[k].extra_at];
                if (n > 1)
                    Number(x + 12, y - 5, n);
            }
    }
}

SNES_MOD_CONSTRUCTOR(register_iog_inventory)
{
    snes_mod_register_reset_callback(ResetInventoryMods);
    snes_mod_register_activation_plugin("iog.stacking", ActivateStacking);
    snes_mod_register_activation_plugin("iog.equipped", ActivateEquipped);
}
