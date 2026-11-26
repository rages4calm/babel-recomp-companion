/*
 * Companion screen for Illusion of Gaia, in the game's own art.
 *
 * The pause menu (Select: the stone pedestal with the inventory, scene $FF)
 * and its "Cond." page are opened OFF-SCREEN with the host's speculative
 * capture (snes_host_capture.h): the presses happen in a speculative
 * timeline, the game draws its own screens, the pictures are kept and the
 * timeline is thrown away. Text uses the game's own font (BG3, from VRAM),
 * and the boxes of every page are cut from the menu's box art. Nothing of
 * the art is shipped: it is the player's ROM, drawn by the game.
 *
 * Paused pages: SAVES (the framework's save-state slots), MAP, ACHIEVEMENTS,
 * SETTINGS (hands over to the settings menu). Beside the running game (Dual /
 * Flip Grip): ITEMS (equip by pad or touch), STATUS, MAP (the area around the
 * player, live), SAVES, SETTINGS. Composed at the game's 256x224.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common_cpu_infra.h"
#include "common_rtl.h"
#include "snes/ppu.h"
#include "snes/snes.h"
#include "snes_host_capture.h"
#include "snes_overlay_draw.h"
#include "snes_savestate_menu.h"
#include "snes_settings_menu.h"

#include "iog_companion.h"
#include "iog_inventory.h"
#include "iog_map_host.h"
#include "companion_achievements/presentation.h"
int IogCompletionPercent(void);
#include "iog_i18n.h"

extern Ppu *g_ppu;

enum { kW = 256, kH = 224, kCapW = 512, kCapH = 240, kMaxScale = 4 };
enum { kPadSelect = 0x004 };
/* The paused Companion screen has the pages only it provides. The game's own
 * pause menu (Select) is the one Items and Status screen; the two live pages
 * below exist only for the Dual / Flip Grip second screen, which sits beside
 * the running game where that menu is not on view. Map is on both lists: the
 * paused one hands over to the full map, the live one draws the area around
 * the player in its own box, every frame. */
enum { kPageSaves, kPageMap, kPageAchievements, kPageSettings, kPageCount,
       kLiveItems = kPageCount, kLiveStatus, kPageKinds, kLiveCount = 5 };
static const char *const kPageNames[kPageKinds] = {"Saves", "Map", "Achievements", "Config", "Items", "Status"};
static const int kModalPages[kPageCount] = {kPageSaves, kPageMap, kPageAchievements, kPageSettings};
static const int kLivePages[kLiveCount] = {kLiveItems, kLiveStatus, kPageMap, kPageSaves, kPageSettings};

static uint32_t g_inv[kCapW * kCapH];
static int g_inv_w, g_have_inv;
static uint32_t g_canvas[kW * kH];                              /* composed at 1x */
static uint32_t g_panel[kW * kMaxScale * kH * kMaxScale];       /* presented at g_scale */
static int g_scale = 2;

static int g_open, g_page = kPageSaves, g_live_page = kLiveItems, g_slot, g_save_slot, g_confirm = -1;
/* Live (Dual / Flip Grip): drawn beside the running game every frame. */
static int g_live, g_live_seen, g_live_far;   /* far: the live map's wider view */
static uint8_t g_inv_items[16];   /* the inventory the capture shows */
static uint32_t g_prev_nav;
static int g_ptr_down;
static int g_map_requested,g_map_start_held,g_map_start_consumed;

int IogHostPadLabel(uint32_t snes_bit, char label[8], uint32_t *color);
static int PadPresent(void) { char l[8]; uint32_t c; return IogHostPadLabel(SNES_PAD_B, l, &c) != 0; }
static int Page(void) { return g_live ? g_live_page : g_page; }
static const int *Pages(void) { return g_live ? kLivePages : kModalPages; }
static int PageTotal(void) { return g_live ? kLiveCount : kPageCount; }
static int PageIndex(void)
{
    for (int i = 0; i < PageTotal(); i++) if (Pages()[i] == Page()) return i;
    return 0;
}

static uint16_t Rd(uint32_t a) { return g_snes->ram[a] | g_snes->ram[a + 1] << 8; }
static void Wr(uint32_t a, uint16_t v) { g_snes->ram[a] = (uint8_t)v; g_snes->ram[a + 1] = (uint8_t)(v >> 8); }

/* ---- capture --------------------------------------------------------------
 * One picture of the game's own menu: the pages' backdrop, the box art cut
 * from it and the menu font. Select opens it; stop once it has been up. */
typedef struct { int menu_frames, until_menu; } CapCtx;

static uint32_t CapInput(int frame, void *ud)
{
    (void)ud;
    return frame < 2 ? kPadSelect : 0;
}

static int CapStop(int frame, void *ud)
{
    CapCtx *c = (CapCtx *)ud;
    (void)frame;
    if (Rd(0x0644) == 0x00FF) c->menu_frames++;
    return c->menu_frames >= c->until_menu;
}

static int InPlayQuiet(void)
{
    return g_snes && Rd(0x09AA) != 0 && Rd(0x0644) != 0x00FF && !(Rd(0x09EC) & 0x6000);
}
int IogCompanionInput(uint32_t *human)
{
    if(!human||RtlSpeculativeFrame())return 0;
    const int held=!!(*human&SNES_PAD_START);
    if(!held){g_map_start_held=g_map_start_consumed=0;return 0;}
    const int pressed=!g_map_start_held;g_map_start_held=1;
    if(g_map_start_consumed){*human&=~SNES_PAD_START;return 0;}
    const char *original=getenv("IOG_ORIGINAL_AREA_MAP");
    if(!pressed||(original&&*original=='1')||!InPlayQuiet()||
        !IogMapHostAvailable()||(Rd(0x09ae)&8))return 0;
    /* Source GlobalInputHandler: Start opens local radar only with combat-lock
     * bit3 clear. Its pause-only path and unavailable/world-map scenes retain
     * their original input. No guest code, flags or map data are patched. */
    *human&=~SNES_PAD_START;g_map_start_consumed=1;g_map_requested=1;
    return 1;
}

/* The menu's own font (BG3 2bpp, 256 characters), taken from VRAM while
 * the captured menu is on screen: the gameplay font differs in places. */
static uint16_t g_font[256 * 8];
static int g_have_font;

static void GrabFont(void *ud)
{
    (void)ud;
    if (!g_ppu) return;
    const uint16_t *vram = PpuRenderVram(g_ppu);
    const unsigned base = PPU_bgTileAdr(g_ppu, 2);
    for (int i = 0; i < 256 * 8; i++)
        g_font[i] = vram[(base + i) & 0x7fff];
    g_have_font = 1;
}

static int Capture(uint32_t *dst, int *w)
{
    CapCtx c = {0, 22};
    snes_host_speculative_set_grab(GrabFont);
    int cw = 0, ch = 0;
    if (!InPlayQuiet()) return 0;
    IogMapHostSuspend(true);
    int captured=snes_host_speculative_capture(CapInput, CapStop, &c, 120, SNES_SPEC_FULL_BRIGHTNESS,
                                       dst, kCapW * kCapH, &cw, &ch);
    IogMapHostSuspend(false);
    if (!captured)
        return 0;
    *w = cw;
    return 1;
}

/* The player opened the pause menu: keep its picture as it is drawn (no
 * speculative frames, so no cost). Called after the frame is rasterised,
 * before the inventory enhancements draw over it. */
void IogCompanionGrabMenu(void)
{
    if (!g_ppu || !g_ppu->renderBuffer || RtlSpeculativeFrame() || !IogInventoryPageShown())
        return;
    const int w = 256 + 2 * g_ppu->extraLeftRight;
    if (w > kCapW)
        return;
    for (int y = 0; y < kH; y++)
        memcpy(g_inv + y * w, g_ppu->renderBuffer + (size_t)y * g_ppu->renderPitch, (size_t)w * 4);
    g_inv_w = w;
    g_have_inv = 1;
    memcpy(g_inv_items, &g_snes->ram[0x0AB4], 16);
    GrabFont(NULL);
}

int IogCompanionCaptureInventory(void)
{
    if (Capture(g_inv, &g_inv_w)) {
        g_have_inv = 1;
        memcpy(g_inv_items, &g_snes->ram[0x0AB4], 16);
    }
    return g_have_inv;
}

const uint32_t *IogCompanionInventoryImage(int *w, int *h)
{
    if (!g_have_inv) return NULL;
    if (w) *w = g_inv_w;
    if (h) *h = kH;
    return g_inv;
}

/* ---- drawing ---------------------------------------------------------------- */
static void Put(int x, int y, uint32_t c)
{
    if (x >= 0 && y >= 0 && x < kW && y < kH) g_canvas[y * kW + x] = c | 0xFF000000u;
}

static void Fill(int x, int y, int w, int h, uint32_t c)
{
    for (int j = 0; j < h; j++)
        for (int i = 0; i < w; i++)
            Put(x + i, y + j, c);
}

/* The 256 centre columns of a (possibly widescreen) capture. */
static void Blit(const uint32_t *src, int src_w)
{
    const int off = (src_w - kW) / 2;
    for (int y = 0; y < kH; y++)
        memcpy(g_canvas + y * kW, src + y * src_w + (off > 0 ? off : 0), kW * 4);
}

/* A box in the menu's art: corners and edges cut from the left box of the
 * captured menu, (8,151)-(82,216), borders 5/7 px left/right, 8/6 top/bottom.
 * Without a capture: a plain frame in its colours. */
static void Box(int x, int y, int w, int h)
{
    enum { BX = 8, BY = 151, BR = 82, BB = 216, L = 5, R = 7, T = 8, B = 6 };
    if (!g_have_inv) {
        Fill(x, y, w, h, 0x9C9CBD);
        Fill(x + 2, y + 2, w - 4, h - 4, 0x3952B5);
        Fill(x + 5, y + 5, w - 10, h - 10, 0x000000);
        return;
    }
    const int off = (g_inv_w - kW) / 2;
    const uint32_t *s = g_inv + (off > 0 ? off : 0);
    const int sw = g_inv_w;
#define SRC(px, py) s[(py) * sw + (px)]
    for (int j = 0; j < h; j++) {
        int sy;
        if (j < T) sy = BY + j;
        else if (j >= h - B) sy = BB - (h - j);
        else sy = BY + T + 20;               /* an interior row of the edge */
        for (int i = 0; i < w; i++) {
            int sx;
            if (i < L) sx = BX + i;
            else if (i >= w - R) sx = BR - (w - i);
            else sx = BX + L + 30;
            const int inside = i >= L && i < w - R && j >= T && j < h - B;
            Put(x + i, y + j, inside ? 0x000000 : SRC(sx, sy));
        }
    }
#undef SRC
}

/* A character of the game's font (BG3, 2bpp; tile = ASCII code). */
/* ASCII -> the game's character codes (GaiaLabs' ASCIIString map): mostly
 * the same, but '.' is $20, '-' is $2E, '(' ')' are $3C $3E and "'" $5C. */
static unsigned char GameCode(unsigned char c)
{
    switch (c) {
    case '.': return 0x20;
    case '-': return 0x2E;
    case '(': return 0x3C;
    case ')': return 0x3E;
    case '\'': return 0x5C;
    default: return c;
    }
}

static void CharRaw(int x, int y, unsigned char code, uint32_t fg, uint32_t shade);

/* A character of the game's font: plane value 1 is the face, 2 its shading
 * (the beige of the menu's text), 3 the drop shadow. */
static void Char(int x, int y, unsigned char ch, uint32_t fg, uint32_t shade)
{
    if (ch == ' ') return;
    if (!g_have_font) {
        if (!g_ppu) return;
        GrabFont(NULL);   /* fallback: the gameplay font in VRAM now */
        g_have_font = 0;
    }
    CharRaw(x, y, GameCode(ch), fg, shade);
}

static void CharRaw(int x, int y, unsigned char ch, uint32_t fg, uint32_t shade)
{
    if (!g_have_font && g_ppu) {
        GrabFont(NULL);
        g_have_font = 0;
    }
    for (int r = 0; r < 8; r++) {
        const uint16_t w = g_font[ch * 8 + r];
        for (int c = 0; c < 8; c++) {
            const int p = ((w >> (7 - c)) & 1) | ((w >> (15 - c)) & 1) << 1;
            if (p == 1) Put(x + c, y + r, fg);
            else if (p == 2) Put(x + c, y + r, shade);
            else if (p == 3) Put(x + c, y + r, 0x101010);
        }
    }
}

static uint32_t Shade(uint32_t fg)
{
    /* The menu's text: white face, beige shading; other colours darken. */
    if (fg == 0xFFFFFF || fg == 0xDEC6B5) return 0xDEC6B5;
    return (fg >> 1) & 0x7F7F7F;
}

/* UTF-8 accents -> the European font's codes (read off the font itself):
 * ü $83 é $84 á $85 í $86 ó $87 ú $88 ñ $89 Ñ $8A ¿ $8B ¡ $8C. It has no
 * accented capitals: those are drawn plain. */
static unsigned char AccentCode(unsigned cp)
{
    switch (cp) {
    case 0xFC: return 0x83; case 0xE9: return 0x84; case 0xE1: return 0x85;
    case 0xED: return 0x86; case 0xF3: return 0x87; case 0xFA: return 0x88;
    case 0xF1: return 0x89; case 0xD1: return 0x8A; case 0xBF: return 0x8B;
    case 0xA1: return 0x8C;
    case 0xC1: return 'A'; case 0xC9: return 'E'; case 0xCD: return 'I';
    case 0xD3: return 'O'; case 0xDA: return 'U'; case 0xDC: return 'U';
    default: return '?';
    }
}

static void Text(int x, int y, const char *s, uint32_t fg)
{
    const unsigned char *p = (const unsigned char *)s;
    for (; *p; x += 8) {
        unsigned cp = *p++;
        if ((cp & 0xE0) == 0xC0 && (*p & 0xC0) == 0x80) {
            cp = (cp & 0x1F) << 6 | (*p++ & 0x3F);
            CharRaw(x, y, AccentCode(cp), fg, Shade(fg));
            continue;
        }
        Char(x, y, (unsigned char)cp, fg, Shade(fg));
    }
}

/* The companion's words in the game's language. */
#include "iog_map_ui.h"

static const char *T(const char *en)
{
    static const char *const kEs[][2] = {
        {"Items", "Objetos"}, {"Status", "Estado"}, {"Saves", "Partida"}, {"Config", "Ajustes"},
        {"Map", "Mapa"}, {"Achievements", "Logros"},
        {"Touch to choose", "Toca para elegir"},
        {"A: Equip", "A: Equipar"}, {"(empty)", "(vacío)"}, {"Equipped", "Equipado"},
        {"Slot %02d", "Ranura %02d"}, {"Empty", "Vacía"}, {"Completed", "Completado"},
        {"Load", "Cargar"}, {"Save", "Guardar"}, {"Yes, load", "Sí, cargar"}, {"Yes, save", "Sí, guardar"},
        {"Cancel", "Cancelar"}, {"Open", "Abrir"}, {"Page", "Pág."}, {"Back", "Atrás"}, {"Settings", "Ajustes"},
        {"Display and sound", "Pantalla y sonido"}, {"Language and text", "Idioma y texto"},
        {"Map and radar buttons", "Botones de mapa y radar"}, {"Cheats", "Trucos"},
        {"Save states, reset, quit", "Estados, reiniciar, salir"},
        {"No area map here", "Sin mapa aquí"}, {"Achievements unavailable", "Logros no disponibles"},
        {"A: Zoom", "A: Zoom"}, {"Exit", "Salida"}, {"Chest", "Cofre"},
        {"A again: LOAD", "A otra vez: CARGAR"}, {"X again: SAVE", "X otra vez: GUARDAR"},
        {"A: Load", "A: Cargar"}, {"X: Save", "X: Guardar"}, {"A: Settings", "A: Ajustes"},
    };
    if (!en || strcmp(IogI18nLanguage(), "es")) return en;
    for (size_t i = 0; i < sizeof(kEs) / sizeof(kEs[0]); i++)
        if (!strcmp(kEs[i][0], en)) return kEs[i][1];
    return en;
}

/* Characters, not bytes: the Spanish strings are UTF-8. */
static int TextLen(const char *s)
{
    int n = 0;
    for (; *s; s++) n += (*s & 0xC0) != 0x80;
    return n;
}

static void Cursor(int x, int y, uint32_t c)
{
    for (int j = 0; j < 7; j++)
        for (int i = 0; i <= (j < 4 ? j : 6 - j); i++)
            Put(x + i, y + j, c);
}

static void Frame(int x, int y, int w, int h, uint32_t c)
{
    Fill(x, y, w, 1, c);
    Fill(x, y + h - 1, w, 1, c);
    Fill(x, y, 1, h, c);
    Fill(x + w - 1, y, 1, h, c);
}

enum { kText = 0xFFFFFF, kHi = 0xFFE890, kGold = 0xF8D050, kTeal = 0x73E6CE, kDim = 0x8C8CA5 };

/* The page rows in the list box's interior (159..209): four on the paused
 * screen, five closer together on the live one. The paused screen's box is
 * wide enough for "Achievements"; the live one keeps the narrow box. */
enum { kPageRowY = 160, kHintRows = 4 };
static int PageRowPitch(void) { return g_live ? 10 : 12; }
static const int kHintY[kHintRows] = {160, 173, 186, 200};
static int ListW(void) { return g_live ? 74 : 120; }
static int HintX(void) { return 8 + ListW() + 9; }

static void Backdrop(void)
{
    if (g_have_inv) Blit(g_inv, g_inv_w); else Fill(0, 0, kW, kH, 0x001060);
}

static void PageList(void)
{
    Box(8, 151, ListW(), 65);
    for (int i = 0; i < PageTotal(); i++) {
        const int y = kPageRowY + i * PageRowPitch(), p = Pages()[i];
        if (p == Page()) Cursor(14, y, kHi);
        Text(22, y, T(kPageNames[p]), p == Page() ? kHi : kText);
    }
}

/* ---- button prompts ---------------------------------------------------------
 * A prompt names the control the player presses now: the controller button
 * bound to that SNES button, as the glyph printed on it, or the keyboard key
 * when no controller is in use. Glyphs are drawn on the scaled panel, over the
 * place the 1x page left for them; each prompt is also a pointer target. */
enum { kActNone, kActActivate, kActSave, kActBack, kActPrev, kActNext };
typedef struct { int x, y, x1, action; char glyph[8]; uint32_t color; } PromptAt;
static PromptAt g_prompts[12];
static int g_prompt_count;

static int GlyphK(void) { return g_scale >= 3 ? 2 : 1; }
static int GlyphCells(const char *glyph, uint32_t color)
{
    return (IogMapUiGlyphWidth(glyph, color, GlyphK()) + g_scale - 1) / g_scale + 3;
}

static int PromptWidth(uint32_t bit, const char *key, const char *text)
{
    char glyph[8]; uint32_t color;
    IogMapHostPrompt(bit, key, NULL, glyph, &color, NULL);
    return (glyph[0] ? GlyphCells(glyph, color) : 0) + (text ? 8 * TextLen(T(text)) : 0);
}

static int Prompt(int x, int y, uint32_t bit, const char *key, const char *text, uint32_t fg, int action)
{
    char glyph[8]; uint32_t color;
    IogMapHostPrompt(bit, key, NULL, glyph, &color, NULL);
    PromptAt *q = g_prompt_count < 12 ? &g_prompts[g_prompt_count++] : NULL;
    if (q) { q->x = x; q->y = y; q->action = action; memcpy(q->glyph, glyph, 8); q->color = color; }
    if (glyph[0]) x += GlyphCells(glyph, color);
    if (text) { Text(x, y, T(text), fg); x += 8 * TextLen(T(text)); }
    if (q) q->x1 = x;
    return x;
}

static void HintBox(void) { Box(8 + ListW(), 151, 242 - ListW(), 65); }

/* The two rows every paused page ends with. */
static void PageBackPrompts(void)
{
    int x = Prompt(HintX(), kHintY[2], SNES_PAD_L, "Q", NULL, kTeal, kActPrev);
    Prompt(x, kHintY[2], SNES_PAD_R, "E", "Page", kTeal, kActNext);
    Prompt(HintX(), kHintY[3], SNES_PAD_B, "Esc", "Back", kTeal, kActBack);
}

static void LiveHint(const char *l1, const char *l2)
{
    HintBox();
    if (l1) Text(HintX() + 1, 160, T(l1), kText);
    if (l2) Text(HintX() + 1, 172, T(l2), kText);
    Text(HintX() + 1, 200, T("Touch to choose"), kTeal);
}

/* ---- pages ---------------------------------------------------------------- */
static void SlotPos(int i, int *x, int *y)
{
    const uint8_t *e = g_snes->cart->rom + 0x02EB86 + 4 * i;   /* the menu's slot table */
    *x = e[0] | e[1] << 8;
    *y = e[2] | e[3] << 8;
}

/* Live only. */
static void DrawItems(void)
{
    Backdrop();
    const uint8_t *slots = &g_snes->ram[0x0AB4];
    const int equipped = (int16_t)Rd(0x0AC4);
    for (int i = 0; i < 16; i++) {
        int x, y;
        SlotPos(i, &x, &y);
        if (i == equipped && slots[i]) Frame(x - 10, y - 13, 20, 16, kGold);
        if (i == g_slot) {
            Frame(x - 11, y - 14, 22, 18, kHi);
            Frame(x - 12, y - 15, 24, 20, 0x3952B5);
        }
    }
    PageList();
    LiveHint(slots[g_slot] ? "A: Equip" : "(empty)", g_slot == equipped ? "Equipped" : NULL);
}

static void Number(int x, int y, unsigned n, int width)
{
    char buf[8];
    snprintf(buf, sizeof(buf), "%*u", width, n);
    Text(x, y, buf, kHi);
}

/* Live only: the values, drawn (the game's own screen is not captured). */
static void DrawStatus(void)
{
    Backdrop();
    Box(8, 8, 240, 136);
    Text(24, 24, "HP", kTeal);
    Number(56, 24, Rd(0x0ACE), 3);
    Text(80, 24, "/", kText);
    Number(88, 24, Rd(0x0ACA), 3);
    Text(24, 40, "DP", kTeal);
    Number(56, 40, Rd(0x0AD6), 3);
    Text(24, 56, "STR", kTeal);
    Number(56, 56, Rd(0x0ADE), 3);
    Text(24, 72, "DEF", kTeal);
    Number(56, 72, Rd(0x0ADC), 3);
    PageList();
    LiveHint(NULL, NULL);
}

/* Live only: the area around the player in the content box's interior, drawn
 * by the map's own renderer each frame. A is the wider view and back. */
enum { kMapX = 13, kMapY = 16, kMapW = 230, kMapH = 128 };
static void Notice(const char *l1, const char *l2, const char *l3);
static void DrawLiveMap(void)
{
    Backdrop();
    Box(8, 8, 242, 142);
    const int map = IogMapHostDrawLive(g_canvas + kMapY * kW + kMapX, kW, kMapW, kMapH, g_live_far ? 4 : 8);
    if (!map) Notice("Map", "No area map here", NULL);
    PageList();
    LiveHint(map ? "A: Zoom" : NULL, NULL);
    /* The markers on view, in the map's colours (iog_map_host.c). */
    int x = HintX() + 1;
    if (map & IOG_MAP_LIVE_EXITS) {
        Fill(x, 173, 5, 5, 0x69D9D3);
        Text(x + 8, 172, T("Exit"), kText);
        x += 8 * (TextLen(T("Exit")) + 2);
    }
    if (map & IOG_MAP_LIVE_CHESTS) {
        Fill(x, 173, 5, 5, 0xFFBE60);
        Text(x + 8, 172, T("Chest"), kText);
    }
}

static uint32_t g_thumb[SNES_SAVESTATE_THUMB_W * SNES_SAVESTATE_THUMB_H];

static void DrawSaves(void)
{
    Backdrop();
    Box(8, 8, 242, 142);
    const int first = g_save_slot - 1 < 0 ? 0 : g_save_slot - 1 > SNES_SAVESTATE_SLOTS - 3
                      ? SNES_SAVESTATE_SLOTS - 3 : g_save_slot - 1;
    for (int k = 0; k < 3; k++) {
        const int s = first + k, y = 18 + k * 42;
        char buf[40];
        if (s == g_save_slot) Cursor(16, y + 16, kHi);
        /* Thumbnail at a third of its size: 42x37. */
        if (snes_savestate_slot_thumb(s, g_thumb)) {
            for (int j = 0; j < 37; j++)
                for (int i = 0; i < 42; i++)
                    Put(26 + i, y + j, g_thumb[(j * 3) * SNES_SAVESTATE_THUMB_W + i * 3]);
        } else {
            Fill(26, y, 42, 37, 0x10183A);
        }
        Frame(25, y - 1, 44, 39, s == g_save_slot ? kHi : 0x3952B5);
        snprintf(buf, sizeof(buf), T("Slot %02d"), s + 1);
        Text(76, y + 6, buf, s == g_save_slot ? kHi : kText);
        if (snes_savestate_slot_exists(s)) {
            snes_savestate_slot_label(s, buf, sizeof(buf));
            Text(76, y + 20, buf, kText);
        } else {
            Text(76, y + 20, T("Empty"), kDim);
        }
    }
    PageList();
    HintBox();
    if (g_live) {
        Text(HintX() + 1, 160, T(g_confirm == 0 ? "A again: LOAD" : "A: Load"), kText);
        Text(HintX() + 1, 172, T(g_confirm == 1 ? "X again: SAVE" : "X: Save"), kText);
        Text(HintX() + 1, 200, T("Touch to choose"), kTeal);
    } else if (g_confirm == 0) {
        Prompt(HintX(), kHintY[0], SNES_PAD_A, "Enter", "Yes, load", kHi, kActActivate);
        Prompt(HintX(), kHintY[1], SNES_PAD_B, "Esc", "Cancel", kText, kActBack);
    } else if (g_confirm == 1) {
        Prompt(HintX(), kHintY[0], SNES_PAD_X, "S", "Yes, save", kHi, kActSave);
        Prompt(HintX(), kHintY[1], SNES_PAD_B, "Esc", "Cancel", kText, kActBack);
    } else {
        /* Load and Save share a row when both fit the box (to x = 243). */
        int x = Prompt(HintX(), kHintY[0], SNES_PAD_A, "Enter", "Load", kText, kActActivate);
        const int wrap = x + 6 + PromptWidth(SNES_PAD_X, "S", "Save") > 243;
        Prompt(wrap ? HintX() : x + 6, kHintY[wrap ? 1 : 0], SNES_PAD_X, "S", "Save", kText, kActSave);
        PageBackPrompts();
    }
}

static void Notice(const char *l1, const char *l2, const char *l3)
{
    Backdrop();
    Box(8, 8, 242, 142);
    if (l1) Text(24, 24, T(l1), kHi);
    if (l2) Text(24, 44, T(l2), kText);
    if (l3) Text(24, 56, T(l3), kText);
}

static void DrawSettings(void)
{
    Notice("Settings", "Display and sound", "Language and text");
    Text(24, 68, T("Map and radar buttons"), kText);
    Text(24, 80, T("Cheats"), kText);
    Text(24, 92, T("Save states, reset, quit"), kText);
    PageList();
    HintBox();
    if (g_live) {
        Text(HintX() + 1, 160, T("A: Settings"), kText);
        Text(HintX() + 1, 200, T("Touch to choose"), kTeal);
        return;
    }
    Prompt(HintX(), kHintY[0], SNES_PAD_A, "Enter", "Open", kText, kActActivate);
    PageBackPrompts();
}

static int PanelScale(void)
{
    int w = 0, h = 0;
    IogMapHostOverlaySize(&w, &h);
    const int s = w / kW < h / kH ? w / kW : h / kH;
    return s < 1 ? 1 : s > kMaxScale ? kMaxScale : s;
}

static void Compose(void)
{
    g_prompt_count = 0;
    g_scale = g_live ? 2 : PanelScale();
    switch (Page()) {
    case kLiveItems: DrawItems(); break;
    case kLiveStatus: DrawStatus(); break;
    case kPageSaves: DrawSaves(); break;
    case kPageMap:           /* paused, only when this area has no map: else the map itself */
        if (g_live) { DrawLiveMap(); break; }
        Notice("Map", "No area map here", NULL);
        PageList(); HintBox(); PageBackPrompts(); break;
    case kPageAchievements:  /* only when the browser could not open */
        Notice("Achievements", "Achievements unavailable", NULL);
        PageList(); HintBox(); PageBackPrompts(); break;
    default: DrawSettings(); break;
    }
    if (g_live) return;
    const int S = g_scale, pw = kW * S;
    for (int y = 0; y < kH; y++) {
        uint32_t *row = g_panel + (size_t)(y * S) * pw;
        for (int x = 0; x < kW; x++) {
            const uint32_t c = g_canvas[y * kW + x] | 0xFF000000u;
            for (int i = 0; i < S; i++) row[x * S + i] = c;
        }
        for (int j = 1; j < S; j++) memcpy(row + (size_t)j * pw, row, (size_t)pw * 4);
    }
    const int k = GlyphK();
    for (int i = 0; i < g_prompt_count; i++) {
        const PromptAt *q = &g_prompts[i];
        if (q->glyph[0])
            IogMapUiGlyphDraw(g_panel, pw, kH * S, q->x * S, q->y * S + (8 * S - IOG_MAP_UI_GLYPH_HEIGHT * k) / 2,
                              q->glyph, q->color, k);
    }
}

/* ---- actions ---------------------------------------------------------------- */
static void Close(void) { IogAchievementUiClose();IogMapHostClose();g_open = 0; }

static void SetPage(int p)
{
    g_ptr_down=0;
    IogMapHostClose();
    IogAchievementUiClose();
    g_confirm = -1;
    if (g_live) { g_live_page = p; return; }
    g_page = p;
    if (g_page == kPageMap) IogMapHostOpen();
    else if (g_page == kPageAchievements) IogAchievementUiOpen(g_prev_nav);
    /* A page drawn here needs the menu's picture for its boxes and backdrop. */
    if (!IogMapHostIsOpen() && !IogAchievementUiIsOpen() && !g_have_inv) IogCompanionCaptureInventory();
}

static void StepPage(int d) { SetPage(Pages()[(PageIndex() + d + PageTotal()) % PageTotal()]); }

static void Equip(int slot)
{
    const uint8_t item = g_snes->ram[0x0AB4 + slot];
    if (!item) return;
    Wr(0x0AC4, (uint16_t)slot);
    Wr(0x0AC6, item);
}

static void Activate(void)
{
    switch (Page()) {
    case kLiveItems:
        Equip(g_slot);
        break;
    case kPageSaves:
        if (g_confirm == 0 || !snes_savestate_slot_exists(g_save_slot)) {
            g_confirm = -1;
            if (snes_savestate_load_slot(g_save_slot)) Close();
        } else {
            g_confirm = 0;
        }
        break;
    case kPageSettings:
        Close();
        snes_settings_menu_open();
        break;
    case kPageMap:
        if (g_live && IogMapHostAvailable()) g_live_far = !g_live_far;
        break;
    default:
        break;
    }
}

static void SaveHere(void)
{
    if (Page() != kPageSaves) return;
    /* Saving to an empty slot overwrites nothing: no question. */
    if (g_confirm == 1 || !snes_savestate_slot_exists(g_save_slot)) {
        g_confirm = -1;
        snes_savestate_save_slot(g_save_slot);
    } else {
        g_confirm = 1;
    }
}

static void Back(void)
{
    if (g_live) return;
    if (g_confirm >= 0) g_confirm = -1; else Close();
}

static void Move(int dx, int dy)
{
    if (Page() == kLiveItems) {
        int col = g_slot % 4 + dx, row = g_slot / 4 + dy;
        col = (col + 4) % 4;
        row = (row + 4) % 4;
        g_slot = row * 4 + col;
    } else if (Page() == kPageSaves && dy) {
        g_save_slot += dy;
        if (g_save_slot < 0) g_save_slot = 0;
        if (g_save_slot >= SNES_SAVESTATE_SLOTS) g_save_slot = SNES_SAVESTATE_SLOTS - 1;
        g_confirm = -1;
    }
}

/* ---- host hooks ------------------------------------------------------------- */
int IogCompanionOpen(void)
{
    g_map_requested=0;
    if (!g_snes || !Rd(0x09AA)) return 0;   /* not in play */
    const int eq = (int16_t)Rd(0x0AC4);
    g_slot = eq >= 0 && eq < 16 ? eq : 0;
    g_prev_nav = ~0u;
    g_open = 1;
    g_live = 0;
    IogMapHostNotePad(PadPresent() != 0);
    /* The map where this area has one, else the save states. */
    SetPage(IogMapHostAvailable() ? kPageMap : kPageSaves);
    if (g_page == kPageMap && !IogMapHostIsOpen()) SetPage(kPageSaves);
    return 1;
}

void IogCompanionNav(uint32_t in, uint32_t ticks)
{
    const uint32_t p = in & ~g_prev_nav;
    g_prev_nav = in;
    if (!g_open && !g_live_seen) return;
    g_live = !g_open;   /* beside the running game: the right stick */
    if (g_open) {
        if (p) IogMapHostNotePad(PadPresent() != 0);
        /* Start, which opened the screen, also returns to the game from any page. */
        if (p & SNES_PAD_START) { Close(); return; }
        if (g_page == kPageAchievements && IogAchievementUiIsOpen()) {
            if (p & SNES_PAD_B) { Close(); return; }
            if (p & SNES_PAD_L) { StepPage(-1); return; }
            if (p & SNES_PAD_R) { StepPage(1); return; }
            IogAchievementUiNav(in & ~(uint32_t)SNES_PAD_B, ticks);
            return;
        }
        if (g_page == kPageMap && IogMapHostIsOpen()) {
            /* L and R belong to the map (zoom by default): its Back leads to
             * the pages, Start to the game. */
            IogMapHostNav(in,ticks);
            if(!IogMapHostIsOpen())SetPage(kPageSaves);
            return;
        }
    }
    if (p & SNES_PAD_B) { Back(); return; }
    if (p & SNES_PAD_L) StepPage(-1);
    if (p & SNES_PAD_R) StepPage(1);
    if (p & SNES_PAD_A) Activate();
    if (p & SNES_PAD_X) SaveHere();
    if (p & SNES_PAD_LEFT) Move(-1, 0);
    if (p & SNES_PAD_RIGHT) Move(1, 0);
    if (p & SNES_PAD_UP) Move(0, -1);
    if (p & SNES_PAD_DOWN) Move(0, 1);
}

void IogCompanionKey(int key, int repeat)
{
    if(repeat&&(key=='m'||key=='i'||key==27||key=='q'||key=='e'))return;
    IogMapHostNotePad(false);   /* a key was pressed: name keys in the prompts */
    if (g_open && g_page == kPageAchievements && IogAchievementUiIsOpen()) {
        switch (key) {
        case 27: case 'i': Close(); return;
        case 'q': StepPage(-1); return;
        case 'e': StepPage(1); return;
        case 'm': SetPage(kPageMap); return;
        default: IogAchievementUiKey(key); return;
        }
    }
    if(g_open&&g_page==kPageMap&&IogMapHostIsOpen()&&key!='q'&&key!='e'&&key!='i'){
        IogMapHostKey(key,repeat);
        if((key==27||key=='m')&&!IogMapHostIsOpen())SetPage(kPageSaves);
        return;
    }
    /* SDL keycodes: Escape, I, arrows, Enter, Q/E pages, S save, M map. */
    switch (key) {
    case 27: case 'i': if (g_confirm >= 0) g_confirm = -1; else Close(); break;
    case 'q': StepPage(-1); break;
    case 'e': StepPage(1); break;
    case 'm': if (!g_live) SetPage(kPageMap); break;
    case '\r': case ' ': Activate(); break;
    case 's': SaveHere(); break;
    case 0x40000050: Move(-1, 0); break;   /* SDLK_LEFT  */
    case 0x4000004F: Move(1, 0); break;    /* SDLK_RIGHT */
    case 0x40000052: Move(0, -1); break;   /* SDLK_UP    */
    case 0x40000051: Move(0, 1); break;    /* SDLK_DOWN  */
    default: break;
    }
}

void IogCompanionPointer(int px, int py, int down)
{
    if (g_open && g_page == kPageAchievements && IogAchievementUiIsOpen()) {
        IogAchievementUiPointer(px, py, down);
        if (!IogAchievementUiIsOpen()) Close();
        return;
    }
    if(g_open&&g_page==kPageMap&&IogMapHostIsOpen()){
        IogMapHostPointer(px,py,down);
        if(!IogMapHostIsOpen())SetPage(kPageSaves);
        return;
    }
    g_live = !g_open;
    const int scale = g_live ? 2 : g_scale;   /* panel -> 1x */
    const int x = px / scale, y = py / scale;
    const int was = g_ptr_down;
    g_ptr_down = down;
    if (!down || was) return;            /* act on the press */
    /* Page list. */
    const int row0 = kPageRowY - (PageRowPitch() - 8) / 2;   /* a row's band is centred on its text */
    if (x >= 10 && x < 8 + ListW() - 6 && y >= row0 && y < row0 + PageRowPitch() * PageTotal()) {
        const int p = Pages()[(y - row0) / PageRowPitch()];
        if (p == Page() && p == kPageSettings) Activate();
        else SetPage(p);
        return;
    }
    /* A prompt is a button. */
    if (!g_live)
        for (int i = 0; i < g_prompt_count; i++) {
            const PromptAt *q = &g_prompts[i];
            if (x < q->x - 2 || x >= q->x1 + 2 || y < q->y - 3 || y >= q->y + 11) continue;
            switch (q->action) {
            case kActActivate: Activate(); break;
            case kActSave: SaveHere(); break;
            case kActBack: Back(); break;
            case kActPrev: StepPage(-1); break;
            case kActNext: StepPage(1); break;
            default: break;
            }
            return;
        }
    if (Page() == kLiveItems) {
        for (int i = 0; i < 16; i++) {
            int sx, sy;
            SlotPos(i, &sx, &sy);
            if (x >= sx - 11 && x < sx + 11 && y >= sy - 14 && y < sy + 4) {
                if (g_slot == i) Equip(i);
                g_slot = i;
                return;
            }
        }
    } else if (Page() == kPageSaves) {
        const int first = g_save_slot - 1 < 0 ? 0 : g_save_slot - 1 > SNES_SAVESTATE_SLOTS - 3
                          ? SNES_SAVESTATE_SLOTS - 3 : g_save_slot - 1;
        if (x >= 16 && x < 248 && y >= 14 && y < 14 + 3 * 42) {
            const int s = first + (y - 14) / 42;
            if (s == g_save_slot) Activate(); else { g_save_slot = s; g_confirm = -1; }
            return;
        }
        if (g_live && y >= 156 && x >= 90) {          /* hint box: top half load, bottom save */
            if (y < 178) Activate(); else SaveHere();
        }
    } else if (g_live && Page() == kPageSettings && y >= 156 && x >= 90) {
        Activate();
    } else if (g_live && Page() == kPageMap && (y >= 156 ? x >= 90 : y >= kMapY && y < kMapY + kMapH)) {
        Activate();                                   /* the map or its hint box: zoom */
    }
}

int IogCompanionImage(const uint32_t **px, int *w, int *h)
{
    if (!g_open) return 0;
    if (g_page == kPageAchievements && IogAchievementUiImage(px, w, h)) return 1;
    if(g_page==kPageMap&&IogMapHostImage(px,w,h))return 1;
    g_live = 0;
    Compose();
    *px = g_panel;
    *w = kW * g_scale;
    *h = kH * g_scale;
    return 1;
}

int IogCompanionAchievementQuiet(void)
{
    return !g_open && InPlayQuiet();
}

/* The live picture, at 1x. Before the first capture (or outside play)
 * nothing: the host then shows the game alone. */
int IogCompanionLive(const uint32_t **px, int *w, int *h)
{
    g_live_seen = 1;
    if (!g_snes || !Rd(0x09AA) || g_open) return 0;   /* no capture yet: plain boxes */
    g_live = 1;
    Compose();
    g_live = 0;
    *px = g_canvas;
    *w = kW;
    *h = kH;
    return 1;
}

/* After every real frame (the host's after_run_frame hook). */
void IogCompanionAfterFrame(void)
{
    /* Live layout: the first picture of the menu art (later ones come from
     * the player's own pause menu, IogCompanionGrabMenu). */
    if (g_live_seen) {
        extern int snes_frame_counter;
        /* A capture fails where the game will not open its menu (some
         * scenes, cutscenes); then wait longer each time, up to half a
         * minute, starting over when the map changes. */
        static int last_try = -100000, fails;
        static uint16_t last_map = 0xFFFF;
        const uint16_t map = Rd(0x0644);
        if (map != last_map) {
            last_map = map;
            fails = 0;
        }
        const int wait = 60 << (fails < 5 ? fails : 5);
        /* Only the first picture is captured: later ones come for free from
         * the player's own pause menu (IogCompanionGrabMenu). A capture
         * runs ~24 frames of the game at once -- a hitch in play. */
        const int changed = !g_have_inv;
        if (changed && !g_open && snes_frame_counter - last_try >= wait && InPlayQuiet()) {
            last_try = snes_frame_counter;
            const int before = g_have_inv;
            g_have_inv = 0;
            if (IogCompanionCaptureInventory()) {
                fails = 0;
            } else {
                g_have_inv = before;
                fails++;
            }
        }
    }
    /* IOG_COMPANION_LIVE_NAV=<steps>: test only. One step every half second
     * on the live panel, through the pad and touch paths: R L pages, A, X,
     * U D < > the cursor, 0-4 a touch on that row of the page list, T a touch
     * on the content box; anything else waits. "RRA" is the Map page, zoomed. */
    if (g_live_seen && !g_open && g_snes && Rd(0x09AA)) {
        static const char *nav;
        static int tick = -1;
        if (tick < 0) nav = getenv("IOG_COMPANION_LIVE_NAV");
        if (++tick % 30 == 29 && nav && *nav) {
            static const char keys[] = "RLAXUD<>";
            static const uint32_t bits[] = {SNES_PAD_R, SNES_PAD_L, SNES_PAD_A, SNES_PAD_X,
                                            SNES_PAD_UP, SNES_PAD_DOWN, SNES_PAD_LEFT, SNES_PAD_RIGHT};
            const char c = *nav++, *k = strchr(keys, c);
            g_prev_nav = 0;
            g_live = 1;
            if (k) {
                IogCompanionNav(bits[k - keys], 0);
            } else if (c == 'T' || (c >= '0' && c <= '4')) {   /* panel pixels are 2x */
                const int x = c == 'T' ? 128 : 40, y = c == 'T' ? 80 : kPageRowY + (c - '0') * PageRowPitch() + 4;
                IogCompanionPointer(x * 2, y * 2, 1);
                IogCompanionPointer(x * 2, y * 2, 0);
            }
        }
    }
    /* IOG_COMPANION_TEST=<frame>: open the companion there on paused page
     * IOG_COMPANION_PAGE (0 Saves, 3 Config) and write companion.ppm. */
    static long test_at = -2;
    if (test_at == -2) {
        const char *v = getenv("IOG_COMPANION_TEST");
        test_at = v ? strtol(v, NULL, 0) : -1;
    }
    extern int snes_frame_counter;
    if (test_at < 0 || snes_frame_counter < test_at || !InPlayQuiet())
        return;
    test_at = -1;
    const char *pg = getenv("IOG_COMPANION_PAGE");
    if (!IogCompanionOpen()) return;
    SetPage(pg && atoi(pg) % kPageCount == kPageSettings ? kPageSettings : kPageSaves);
    Compose();
    FILE *f = fopen("companion.ppm", "wb");
    if (f) {
        fprintf(f, "P6\n%d %d\n255\n", kW * g_scale, kH * g_scale);
        for (int i = 0; i < kW * g_scale * kH * g_scale; i++) {
            const uint32_t p = g_panel[i];
            fputc(p >> 16 & 255, f); fputc(p >> 8 & 255, f); fputc(p & 255, f);
        }
        fclose(f);
    }
    fprintf(stderr, "[companion] test page %d written (inv=%d scale=%d)\n", g_page, g_have_inv, g_scale);
    Close();
}
