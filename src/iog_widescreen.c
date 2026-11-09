/*
 * Illusion of Gaia widescreen policy.
 *
 * The host rasterizes a field widened on both sides (native_widescreen). IoG
 * maps are authored as a world [0, map_bounds_x) that the camera scrolls
 * across, so each margin may show real map content only as far as the world
 * extends past the camera on that side; beyond the world edge the BG tilemap
 * just wraps (on the title screen a second copy of the logo, in rooms the far
 * end of the map). Those pixels stay black instead.
 *
 * This is the zelda3 model (PpuSetExtraSideSpace): margins are recomputed
 * every frame from the camera and the map bounds. Terrain/HUD composition
 * leaves guest graphics/register memory untouched. The culling path below
 * separately checks/patches ten in-memory ROM operands and writes a scratch
 * WRAM camera word; it restores stock operands when the margin goes to0.
 * These policies remain finite scene/presentation work, not full widescreen.
 */

#include "iog_widescreen.h"
#include "iog_randomizer.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common_cpu_infra.h"
#include "common_rtl.h"
#include "snes/ppu.h"
#include "snes/snes.h"
#include "snes/cart.h"
#include "snes/ws_shadow.h"

/* WRAM (GaiaLabs RAM map). */
enum {
    kWramCameraX    = 0x068A,  /* logical map-layer camera X */
    kWramMapBoundsX = 0x0692,  /* logical map-layer world width, px */
};

static uint16_t WramWord(uint32_t addr)
{
    const uint8_t *ram = g_snes->ram;
    return (uint16_t)(ram[addr] | ram[addr + 1] << 8);
}

/* Camera for the line the PPU is about to render. The phase comes from the
 * physical layer's live scroll; WRAM supplies the bits
 * the 10-bit hardware scroll has lost. */
static int ScrollWorld(uint32_t address, uint16_t scroll)
{
    int wram = WramWord(address);
    int cam = (wram & ~0x3FF) | (scroll & 0x3FF);
    if (cam - wram > 512) cam -= 1024;
    if (wram - cam > 512) cam += 1024;
    return cam;
}

typedef struct MapLayer {
    uint16_t width, height, map, definitions;
    uint8_t logical, physical;
    int blank;
    bool valid;
} MapLayer;

static MapLayer s_map_layers[2];
static bool s_map_frame;
static uint16_t s_map_scene;
static bool s_reset_for_draw;
static bool s_preview_centered_hud;
static int Clamp(int v, int lo, int hi);

void IogWidescreenSetPreviewCenteredHud(bool enabled)
{
    s_preview_centered_hud = enabled;
}

/* Source: $82:ADA2..AF5E. Arrangement bytes are grouped into 256x256px
 * pages. Each byte selects four 8x8 SNES entries (TL,TR,BL,BR). The decoded
 * arrangement and definitions are live WRAM, including original puzzle edits.
 * Never write these buffers or guest VRAM to extend presentation. */
static bool ReadMapLayer(int logical, MapLayer *layer)
{
    int x = logical * 2;
    layer->logical = (uint8_t)logical;
    layer->physical = (uint8_t)(logical ^ ((g_snes->ram[0x06EE] >> 7) & 1));
    layer->width = WramWord(0x0692 + x);
    layer->height = WramWord(0x0696 + x);
    layer->map = WramWord(0x069E + x);
    layer->definitions = WramWord(0x06AE + x);
    uint32_t size = (uint32_t)(layer->width >> 8) * (layer->height >> 8) * 256u;
    return layer->width >= 256 && layer->height >= 256 &&
        !(layer->width & 255) && !(layer->height & 255) &&
        layer->height <= kWsShadowYTiles * 8 &&
        layer->width <= kWsShadowXTiles * 8 &&
        layer->map == (logical ? 0xC000 : 0xA000) &&
        layer->definitions == (logical ? 0x2800 : 0x2000) &&
        size == WramWord(0x069A + x) && layer->map + size <= 0x10000u &&
        !PPU_bigTiles(g_ppu, layer->physical) &&
        !PPU_bgTilemapHigher(g_ppu, layer->physical) &&
        PPU_bgTilemapAdr(g_ppu, layer->physical) == WramWord(0x06BA + x);
}

static uint16_t MapTile(const MapLayer *layer, unsigned x, unsigned y)
{
    uint32_t offset = layer->map +
        (((y >> 8) * (layer->width >> 8) + (x >> 8)) << 8) +
        (((y >> 4) & 15) << 4) + ((x >> 4) & 15);
    unsigned index = g_snes->ram[offset];
    return WramWord(layer->definitions + index * 8 +
                    ((y >> 3) & 1) * 4 + ((x >> 3) & 1) * 2);
}

/* Transparent SNES character verified from this frame's live 4bpp graphics,
 * rather than assuming character zero is blank in every tileset. */
static int BlankTile(int physical)
{
    unsigned base = PPU_bgTileAdr(g_ppu, physical);
    for (unsigned tile = 0; tile < 1024; tile++) {
        unsigned n;
        for (n = 0; n < 16; n++)
            if (g_ppu->vram[(base + tile * 16 + n) & 0x7FFF]) break;
        if (n == 16) return (int)tile;
    }
    return -1;
}

void IogWidescreenBeginFrame(void)
{
    /* CaptureSimulationFrame calls this immediately before GameDrawPpuFrame:
     * no shadow consumer or writer runs before its BeforeDraw. That draw may
     * consume this reset once. A direct/repeated draw still resets below. */
    WsShadowReset();
    s_map_frame = false;
    s_reset_for_draw = true;
}

static int PhysicalMapLayer(void)
{
    return (g_snes->ram[0x06EE] >> 7) & 1;
}

/* Refresh after simulation, and again after each line's HDMA/IRQ. A frame
 * sample cannot stand in for a parallax layer's current scanline scroll. */
void IogWidescreenBeforeLine(int line)
{
    if (!g_ppu || !g_snes || !g_ppu->extraLeftRight) return;
    if (s_map_frame) {
        bool current = WramWord(0x0644) == s_map_scene && (g_ppu->bgmode & 7) == 1;
        for (int i = 0; i < 2 && current; i++) {
            const MapLayer *layer = &s_map_layers[i];
            MapLayer live;
            bool valid = ReadMapLayer(i, &live);
            bool enabled = ((g_ppu->screenEnabled[0] | g_ppu->screenEnabled[1]) &
                            (1 << live.physical)) != 0;
            if (enabled && (!valid || !layer->valid || live.physical != layer->physical ||
                live.width != layer->width || live.height != layer->height ||
                ScrollWorld(0x068A + i * 2, g_ppu->hScroll[live.physical]) < 0 ||
                ScrollWorld(0x068E + i * 2, g_ppu->vScroll[live.physical]) < 0)) current = false;
        }
        if (!current) {
            WsShadowReset();
            s_map_frame = false;
        }
    }
    int budget = g_ppu->extraLeftRight;
    int cam = ScrollWorld(0x068A, g_ppu->hScroll[PhysicalMapLayer()]);
    int left = Clamp(cam, 0, budget);
    int right = Clamp((int)WramWord(0x0692) - cam - 256, 0, budget);
    if ((g_ppu->bgmode & 7) == 7) {
        left = right = budget;
    } else if (!s_map_frame || (g_ppu->bgmode & 7) != 1) {
        left = right = 0;
    }
    PpuSetExtraSideSpace(g_ppu, left, right, 0);
    if (!s_map_frame) return;
    for (int i = 0; i < 2; i++) {
        const MapLayer *layer = &s_map_layers[i];
        if (!layer->valid) continue;
        int physical = layer->physical;
        int wx = ScrollWorld(0x068A + i * 2, g_ppu->hScroll[physical]);
        int wy = ScrollWorld(0x068E + i * 2, g_ppu->vScroll[physical]);
        if (wx < 0 || wy < 0) continue;
        WsShadowSetWorld(physical, (uint32_t)wx, (uint32_t)wy);
        WsShadowSetScroll(physical, g_ppu->hScroll[physical], g_ppu->vScroll[physical]);
        int y = (wy + line) & ~7;
        int begin = (wx - budget) & ~7;
        int end = (wx + 256 + budget + 7) & ~7;
        for (int x = begin; x < end; x += 8) {
            if (x >= 0 && x < layer->width && y >= 0 && y < layer->height)
                WsShadowPrefillTile(physical, (uint32_t)x >> 3, (uint32_t)y >> 3,
                                   MapTile(layer, (unsigned)x, (unsigned)y));
        }
        /* The tile renderer asks for a whole 8px cell. Fine scroll can put
         * its first/last cell partly inside the authentic viewport, including
         * a 33rd cell that WsShadowFrame's 32-column capture does not retain.
         * Those overlapping cells must use the real native VRAM entry, not
         * CPU-map prefill, even if a staged strip currently disagrees. */
        for (int edge = 0; edge < 2; edge++) {
            int sx = edge ? 255 : 0;
            unsigned tx = (g_ppu->hScroll[physical] + sx) >> 3;
            unsigned ty = (g_ppu->vScroll[physical] + line) >> 3;
            unsigned address = PPU_bgTilemapAdr(g_ppu, physical) +
                               ((ty & 31) << 5) + (tx & 31);
            if (PPU_bgTilemapWider(g_ppu, physical) && (tx & 32)) address += 0x400;
            WsShadowForceTile(physical, (unsigned)(wx + sx) >> 3,
                              (unsigned)(wy + line) >> 3,
                              g_ppu->vram[address & 0x7FFF]);
        }
    }
}

static int Clamp(int v, int lo, int hi)
{
    return v < lo ? lo : v > hi ? hi : v;
}

void IogWidescreenBeforeDraw(void)
{
    if (!s_reset_for_draw)
        WsShadowReset();
    s_reset_for_draw = false;
    s_map_frame = false;
    if (!g_ppu || !g_snes || g_ppu->extraLeftRight == 0)
        return;
    const int budget = g_ppu->extraLeftRight;
    int bounds = WramWord(kWramMapBoundsX);
    /* No world loaded (boot, some menus): keep the authentic 256 columns. */
    if (bounds < 256)
        bounds = 256;
    const int cam = ScrollWorld(kWramCameraX, g_ppu->hScroll[PhysicalMapLayer()]);
    int left = Clamp(cam, 0, budget);
    int right = Clamp(bounds - (cam + 256), 0, budget);
    /* Mode 7 (prologue sea, world map) is a plane that genuinely continues
     * past the screen edges; map bounds do not apply to it. */
    if ((g_ppu->bgmode & 7) == 7)
        left = right = budget;
    /* Scene $08 is the South Cape church/classroom interior. Its 512px
     * storage plane exposes a repeated partial room/window beyond the
     * authentic view. Keep that interior at 256px until an independent
     * interior composition is available; plane size is not a visible-room
     * contract. This presentation policy does not lock the guest camera. */
    else if ((g_ppu->bgmode & 7) == 1 && !IogRandomizerActive() &&
             WramWord(0x0644) < 0x00F0 && WramWord(0x0644) != 0x0008 &&
             !(g_snes->ram[0x06EF] & 8)) {
        bool known = true;
        for (int i = 0; i < 2; i++) {
            MapLayer *layer = &s_map_layers[i];
            layer->valid = ReadMapLayer(i, layer);
            layer->blank = layer->valid ? BlankTile(layer->physical) : -1;
            bool enabled = ((g_ppu->screenEnabled[0] | g_ppu->screenEnabled[1]) &
                            (1 << layer->physical)) != 0;
            if (enabled && (!layer->valid || layer->blank < 0)) known = false;
        }
        if (known && s_map_layers[0].valid) {
            s_map_frame = true;
            s_map_scene = WramWord(0x0644);
            for (int i = 0; i < 2; i++) {
                MapLayer *layer = &s_map_layers[i];
                if (!layer->valid) continue;
                int physical = layer->physical;
                int wx = ScrollWorld(0x068A + i * 2, g_ppu->hScroll[physical]);
                int wy = ScrollWorld(0x068E + i * 2, g_ppu->vScroll[physical]);
                if (wx < 0 || wy < 0) continue;
                WsShadowSetWorld(physical, (uint32_t)wx, (uint32_t)wy);
                WsShadowSetScroll(physical, g_ppu->hScroll[physical], g_ppu->vScroll[physical]);
                WsShadowSetRetainHistory(physical, false);
                WsShadowSetBlankTile(physical, layer->blank);
            }
            WsShadowFrame(g_ppu);
            for (int i = 0; i < 2; i++) {
                int physical = s_map_layers[i].physical;
                bool enabled = ((g_ppu->screenEnabled[0] | g_ppu->screenEnabled[1]) &
                                (1 << physical)) != 0;
                if (enabled && !WsShadowLayerActive(physical)) s_map_frame = false;
            }
            if (!s_map_frame) {
                WsShadowReset();
                left = right = 0;
            }
        } else left = right = 0;
    } else left = right = 0;
    PpuSetExtraSideSpace(g_ppu, left, right, 0);
    /* In-game HUD (BG3 rows 0-3: PLAYER + life orbs | DP ornament | ENEMY):
     * anchor its outer groups to the widened edges. Only while the HUD is
     * really there, so title, file select, menus and the prologue keep their
     * BG3 layout. Keyed on the DP ornament (row 1: $0EF at columns 11 and 20,
     * $01E at 15), which is drawn with the HUD in every release; the PLAYER
     * label is blank for a while after a scene loads. */
    const uint16_t *map = &g_ppu->vram[PPU_bgTilemapAdr(g_ppu, 2) & 0x7fff];
    const uint16_t *row1 = map + 32;
    if ((row1[11] & 0x3ff) == 0x0EF && (row1[20] & 0x3ff) == 0x0EF &&
        (row1[15] & 0x3ff) == 0x01E) {
        PpuSetWidescreenHudSplit(g_ppu, 32, 88, 168);
        PpuSetWidescreenHudAlwaysVisible(g_ppu, true);
    } else {
        /* The split is sticky PPU state: drop it as soon as the HUD goes
         * (file select, menus), or their BG3 boxes get torn at column 168. */
        PpuSetWidescreenHudSplit(g_ppu, 0, 0, 0);
        PpuSetWidescreenHudAlwaysVisible(g_ppu, false);
    }
    if (s_preview_centered_hud) {
        /* The preview keeps source UI centered. Do not combine a copied
         * original center with the legacy edge anchors: that duplicates HUD.
         * Clip only BG3 margin ink, leaving the real native256 unchanged. */
        PpuSetWidescreenHudSplit(g_ppu, 0, 0, 0);
        PpuSetWidescreenHudAlwaysVisible(g_ppu, false);
        PpuSetWidescreenLayerWorldClipBand(g_ppu, 2, 0, 224, 2, 0, 256);
    }
    /* The renderer only writes the live span of each line; what lies outside
     * it would keep an older frame's pixels, so blank it first. */
    if (g_ppu->renderBuffer) {
        for (int y = 0; y < 240; y++) {
            uint32_t *line = (uint32_t *)&g_ppu->renderBuffer[(size_t)y * g_ppu->renderPitch];
            memset(line, 0, sizeof(uint32_t) * (size_t)budget);
            memset(line + budget + 256, 0, sizeof(uint32_t) * (size_t)budget);
        }
    }
    static unsigned log_frame;
    static bool last_map_frame;
    if (getenv("IOG_WS_LOG") && (!(log_frame++ % 60) || last_map_frame != s_map_frame)) {
        WsShadowMarginStat a, b;
        WsShadowGetMarginStats(0, &a);
        WsShadowGetMarginStats(1, &b);
        fprintf(stderr, "[iog_ws] cam=%d wram=%d hs=%d bounds=%d -> L=%d R=%d cur=%d/%d map=%d active=%d/%d prefill=%llu/%llu raw=%llu/%llu\n", cam,
                WramWord(kWramCameraX), g_ppu->hScroll[0], bounds, left, right,
                g_ppu->extraLeftCur, g_ppu->extraRightCur, s_map_frame,
                WsShadowLayerActive(0), WsShadowLayerActive(1),
                (unsigned long long)a.prefillSeed, (unsigned long long)b.prefillSeed,
                (unsigned long long)(a.westRawFallback + a.eastRawFallback),
                (unsigned long long)(b.westRawFallback + b.eastRawFallback));
        last_map_frame = s_map_frame;
    }
}

/* ---- sprite culling --------------------------------------------------------
 *
 * Two routines of bank $03 drop what lies outside the native 256 columns.
 * Operands are retargeted in the in-memory ROM image; originals are checked
 * first and restored when the margin goes. Qualified native sprite paths
 * read these changing operands at execution time, including live absolute
 * WRAM addresses. That proof does not imply all actors/extra-list parts or
 * arbitrary ultrawide layouts are qualified.
 *
 *  - Actor list (func_03C5FF): keeps an actor whose box overlaps
 *    [camera, camera+256):  SBC $068A ; CMP #$0100.  The camera operand is
 *    pointed at a spare WRAM word holding camera - margin, and the window
 *    becomes 256 + 2*margin wide (WIDESCREEN_PATTERNS P7: widen, keep base).
 *  - OAM writer (func_03C714 / sub $C849): base $1A = camera - 16; each
 *    piece is kept when x + 16 < $0110 and written as x = (sum) - 16. Base,
 *    limit and bias grow by the margin so pieces in the margins get their
 *    9-bit X instead of being parked at $E080. Same for the player path.
 *  - Extra sprite list ($7F:3100, $C797): x - camera < $0110; widening the
 *    limit lets the right margin through (its stored X is not biased, so
 *    the left margin cannot be reached without new code).
 *
 * Nothing is patched while the margin is 0 (4:3 is untouched). */
enum { kWramCullCamera = 0x1E00 };   /* spare word, never used by the game */

typedef struct CullSite {
    uint32_t offset;
    uint16_t stock;
    int16_t per_margin;              /* value = stock + per_margin * margin */
    uint8_t camera;                  /* operand becomes kWramCullCamera */
} CullSite;

static const CullSite kCullSites[] = {
    {0x03C617, 0x068A, 0, 1}, {0x03C61A, 0x0100, 2, 0},   /* actor list, left */
    {0x03C62A, 0x068A, 0, 1}, {0x03C62D, 0x0100, 2, 0},   /* actor list, right */
    {0x03C729, 0x0010, 1, 0},                              /* OAM base */
    {0x03C8E5, 0x0110, 2, 0}, {0x03C8EA, 0x000F, 1, 0},   /* actor pieces */
    {0x03C9C2, 0x0110, 2, 0}, {0x03C9C7, 0x000F, 1, 0},   /* player pieces */
    {0x03C7BE, 0x0110, 1, 0},                              /* extra list */
};
enum { kNumCullSites = sizeof(kCullSites) / sizeof(kCullSites[0]) };
static int g_cull_margin;            /* margin the ROM is patched for, 0: stock */
static int g_cull_unknown;           /* not the ROM we know: leave it alone */

static void PatchCull(int margin)
{
    Cart *cart = g_snes ? g_snes->cart : NULL;
    if (!cart || g_cull_unknown || margin == g_cull_margin)
        return;
    if (!g_cull_margin) {
        for (int i = 0; i < kNumCullSites; i++) {
            const CullSite *c = &kCullSites[i];
            if (c->offset + 2 > cart->romSize ||
                (cart->rom[c->offset] | cart->rom[c->offset + 1] << 8) != c->stock) {
                g_cull_unknown = 1;
                return;
            }
        }
    }
    for (int i = 0; i < kNumCullSites; i++) {
        const CullSite *c = &kCullSites[i];
        uint16_t v = !margin ? c->stock
                   : c->camera ? kWramCullCamera
                   : (uint16_t)(c->stock + c->per_margin * margin);
        cart->rom[c->offset] = (uint8_t)v;
        cart->rom[c->offset + 1] = (uint8_t)(v >> 8);
    }
    g_cull_margin = margin;
}

void IogWidescreenBeforeFrame(void)
{
    if (!g_ppu || !g_snes)
        return;
    static int disabled = -1;
    if (disabled < 0)
        disabled = getenv("IOG_WS_NO_CULL_PATCH") != NULL;
    PatchCull(disabled || IogRandomizerActive() ? 0 : g_ppu->extraLeftRight);
    if (g_cull_margin) {
        uint16_t cam = (uint16_t)(WramWord(kWramCameraX) - g_cull_margin);
        g_snes->ram[kWramCullCamera] = (uint8_t)cam;
        g_snes->ram[kWramCullCamera + 1] = (uint8_t)(cam >> 8);
    }
}
