/*
 * GaiaLabs "Minimal HUD" (package iog.gaialabs, plugin iog.gaialabs.minimal_hud).
 *
 * GaiaLabs hides the player's status display (PLAYER / DP / ENEMY) in
 * non-combat areas: towns and cutscene rooms, where the scene sets the combat
 * lock, playerFlags ($09AE) bit 3, when the player spawns. Its patch makes
 * LoadHudTilemap skip the HUD and UpdateHUD return early there. UpdateHUD
 * also plays out herb healing (hpToHeal $0B22 raises playerHp every eighth
 * frame), so skipping it stops a herb from healing in a town. Here the game
 * runs exactly as stock and only the picture changes:
 *
 *  - The HUD is BG3 tilemap rows 0-4 (LoadHudTilemap's 159-word stream at
 *    $7F:0200, uploaded to the BG3 map at VRAM $7800; the per-frame stat and
 *    enemy-bar redraws upload rows 2-6 of the same buffer, of which only rows
 *    0-4 ever hold HUD art). Every dialogue, title card, radar and pause box
 *    is drawn below those rows while the HUD is up
 *    (ClearBg3TilemapBuffer_PreserveHud keeps the first $140 bytes).
 *  - For the one frame being drawn, while the combat lock is set and the HUD
 *    is actually in VRAM, those five rows are set to the cleared tilemap
 *    word ($0000, what
 *    ClearBg3TilemapBuffer_Full writes). Right after the raster the original
 *    words are put back, so WRAM, VRAM between frames, save states, rewind
 *    and the native/interpreter comparison all see the stock game.
 *  - The draw is shared by every picture: Original 4:3 and Classic 16:9
 *    rasterise from VRAM, and the wide view copies VRAM into its picture
 *    epochs and captures the BG3 plane during the same raster, so all three
 *    lose the HUD and nothing else.
 *
 * "The HUD is in VRAM" means every one of the 41 fixed tiles of
 * HudTilemapData (brackets, labels, ornament; read from the ROM, never
 * redrawn by the stat updates) is in place. A box or menu drawn over any of
 * them, or a frame without the HUD, is drawn untouched. If the ROM does not
 * hold the stock loader, the DP ornament alone is the test (the one
 * IogWidescreenBeforeDraw uses).
 *
 * The lock is read every frame, so a scene that lifts it (Dao's snake game,
 * the Freejia kidnapper) shows the HUD at once, and one that sets it hides
 * it. A frame without the HUD (inventory, file select, Mode 7, a scene whose
 * display preset turns the HUD off) is left alone.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "mod_runtime.h"
#include "snes/cart.h"
#include "snes/ppu.h"
#include "snes/snes.h"

#include "iog_minimal_hud.h"

extern Ppu *g_ppu;
extern Snes *g_snes;

enum {
    kPlayerFlags = 0x09AE,
    kCombatLock = 0x08,
    kHudWords = 5 * 32,         /* BG3 tilemap rows 0-4 */
    kBlankWord = 0x0000,
};

static bool g_on;
static bool g_blanked;
static uint16_t g_base;         /* VRAM word address of the BG3 map */
static uint32_t g_writes;       /* vramWriteCount right after blanking */
static uint16_t g_saved[kHudWords];

/* LoadHudTilemap's fixed tiles, expanded from the ROM's HudTilemapData. */
enum {
    kLoaderRom = 0x3DECD,       /* LoadHudTilemap, $03:DECD */
    kStreamRom = 0x3DF0A,       /* HudTilemapData, $03:DF0A */
    kMaxFixed = 64,
};
static int g_fixed_count = -1;  /* -1 not read yet, 0 stock loader not found */
static uint8_t g_fixed_pos[kMaxFixed];
static uint16_t g_fixed_word[kMaxFixed];

static void ReadFixedTiles(void)
{
    g_fixed_count = 0;
    const Cart *cart = g_snes ? g_snes->cart : NULL;
    if (!cart || !cart->rom || cart->romSize < kStreamRom + 256) return;
    /* The stock loader: LDA $09ED / BIT #$40 / BEQ / RTL / PHP / REP #$20 /
     * PHB / PHK / PLB / LDY #0 / TYX / LDA $DF0A,Y. */
    static const uint8_t kLoader[] = {
        0xAD, 0xED, 0x09, 0x89, 0x40, 0xF0, 0x01, 0x6B, 0x08, 0xC2, 0x20,
        0x8B, 0x4B, 0xAB, 0xA0, 0x00, 0x00, 0xBB, 0xB9, 0x0A, 0xDF,
    };
    if (memcmp(cart->rom + kLoaderRom, kLoader, sizeof(kLoader))) {
        fprintf(stderr, "[minimal_hud] no stock HUD loader in the ROM: DP ornament test\n");
        return;
    }
    const uint8_t *p = cart->rom + kStreamRom, *end = cart->rom + kStreamRom + 256;
    unsigned pos = 0, n = 0;
    while (p + 4 <= end) {
        uint16_t word = (uint16_t)(p[0] | p[1] << 8);
        if (word) {
            if (pos >= kHudWords || n >= kMaxFixed) return;
            g_fixed_pos[n] = (uint8_t)pos; g_fixed_word[n] = word; n++;
            pos++; p += 2;
            continue;
        }
        uint16_t skip = (uint16_t)(p[2] | p[3] << 8);
        if (!skip) {
            g_fixed_count = (int)n;
            fprintf(stderr, "[minimal_hud] %d fixed HUD tiles from the ROM\n", g_fixed_count);
            return;
        }
        pos += skip; p += 4;
    }
}

static bool HudInVram(const uint16_t *map)
{
    if (g_fixed_count < 0) ReadFixedTiles();
    if (g_fixed_count > 0) {
        for (int i = 0; i < g_fixed_count; i++)
            if (map[g_fixed_pos[i]] != g_fixed_word[i]) return false;
        return true;
    }
    /* The DP ornament in row 1 ($0EF at columns 11 and 20, $01E at 15). */
    const uint16_t *row1 = map + 32;
    return (row1[11] & 0x3ff) == 0x0EF && (row1[20] & 0x3ff) == 0x0EF &&
           (row1[15] & 0x3ff) == 0x01E;
}

void IogMinimalHudBeginDraw(void)
{
    g_blanked = false;
    if (!g_on || !g_ppu || !g_snes || !g_snes->ram) return;
    if (!(g_snes->ram[kPlayerFlags] & kCombatLock)) return;
    if ((g_ppu->bgmode & 7) != 1) return;
    uint16_t base = (uint16_t)(PPU_bgTilemapAdr(g_ppu, 2) & 0x7fff);
    if (base + kHudWords > 0x8000) return;
    uint16_t *map = &g_ppu->vram[base];
    if (!HudInVram(map)) return;
    memcpy(g_saved, map, sizeof(g_saved));
    for (int i = 0; i < kHudWords; i++) map[i] = kBlankWord;
    /* Host-only change counter: lets frame caches see the different map. */
    g_ppu->vramWriteCount++;
    g_writes = g_ppu->vramWriteCount;
    g_base = base;
    g_blanked = true;
}

void IogMinimalHudEndDraw(void)
{
    if (!g_blanked || !g_ppu) return;
    g_blanked = false;
    uint16_t *map = &g_ppu->vram[g_base];
    if (g_ppu->vramWriteCount == g_writes) {
        memcpy(map, g_saved, sizeof(g_saved));
    } else {
        /* The guest stored to VRAM during the raster: keep any word it wrote
         * there and put back only the ones still blanked. */
        for (int i = 0; i < kHudWords; i++)
            if (map[i] == kBlankWord) map[i] = g_saved[i];
    }
    g_ppu->vramWriteCount++;
}

static void Activate(void) { g_on = true; g_fixed_count = -1; }

static void Reset(void)
{
    /* Runs before active plugins: a disabled feature draws the stock HUD. */
    g_on = false;
}

SNES_MOD_CONSTRUCTOR(register_iog_minimal_hud)
{
    snes_mod_register_reset_callback(Reset);
    snes_mod_register_activation_plugin("iog.gaialabs.minimal_hud", Activate);
}
