/*
 * GaiaLabs Retranslation options (package "iog.gaialabs").
 *
 * GaiaLabs offers its options as modules for its own ROM rebuild. Here the
 * stock ROM keeps running with native code generated from it, so each option
 * is taken over in the form the game can use without new code:
 *
 *  - JP content (backgrounds, palettes, the red fountain): data the game
 *    loads itself. scripts/build_gaialabs_mods.py turns the modules into
 *    i18n/gaialabs-mods.bin, a list of writes over the stock spans (art
 *    recompressed with the game's QuintetLZ) and longer parallax tables. Each
 *    write carries the SHA-256 of the stock bytes it replaces; a mismatch
 *    refuses that option. Applied after the startup identity checks, undone
 *    on reset, so the ROM file is never touched. A changed background shows
 *    the next time its room loads.
 *  - Full HP herb and the Pyramid portal exit: the modules patch game code,
 *    so the host does what the patch does to the game's state instead.
 *
 * The world renderer reads parallax tables through the game's own pointer
 * table, so relocated JP tables reach the wide view as they do the 4:3 one.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common_cpu_infra.h"
#include "host_paths.h"
#include "iog_randomizer.h"
#include "mod_runtime.h"
#include "sha256.h"
#include "snes/cart.h"
#include "snes/ppu.h"
#include "snes/snes.h"

#include "iog_gaialabs.h"

extern Ppu *g_ppu;

enum {
    kParallaxTable = 0x1CC00,
    /* Free space for longer parallax tables: the end of bank $01 after the
     * dialogue pack's 24 bytes at $01:FF6C (iog_text.c GaiaShortTitle). */
    kBank1Free = 0x1FF8C, kBank1End = 0x20000,
    kMaxRecords = 128,
};

typedef struct {
    char kind;                  /* 'W' write, 'T' parallax table, 'S' resident swap */
    char feature[24];
    uint32_t offset, len;       /* W: ROM offset; T: pointer slot */
    uint8_t sha[32];
    const uint8_t *data;
} Record;

static const char *const kFeatures[] = {
    "jp_edward", "jp_itory", "jp_wall", "red_fountain", "jp_church", "jp_mines", "jp_prologue",
    "jp_viper", "crystal_ring",
};
enum { kNumFeatures = sizeof(kFeatures) / sizeof(kFeatures[0]) };

static uint8_t *g_file;
static Record g_rec[kMaxRecords];
static int g_nrec, g_loaded;
static bool g_wanted[kNumFeatures], g_usable[kNumFeatures];

/* What was applied, to undo it exactly. */
typedef struct { uint32_t offset, len; uint8_t *original; } Undo;
static Undo g_undo[kMaxRecords * 2];
static int g_nundo;

static bool g_full_herb, g_portal_exit;

/* Art the console may already hold (see SwapResident): both versions,
 * expanded. Built once from the stock ROM, before anything is applied. */
typedef struct { int feature; bool palette; uint8_t *stock, *mod; uint32_t len; } Resident;
static Resident g_res[32];
static int g_nres, g_res_built;
static unsigned g_last_scene = 0xFFFF, g_res_tick;

static int FeatureIndex(const char *id)
{
    for (int i = 0; i < kNumFeatures; i++)
        if (!strcmp(kFeatures[i], id))
            return i;
    return -1;
}

static void Load(void)
{
    if (g_loaded)
        return;
    g_loaded = 1;
    char path[1024];
    const char *override = getenv("IOG_GAIALABS_MODS");
    if (override && *override)
        snprintf(path, sizeof(path), "%s", override);
    else if (!snesrecomp_exe_dir_path("i18n/gaialabs-mods.bin", path, sizeof(path)))
        return;
    FILE *f = fopen(path, "rb");
    if (!f)
        return;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    g_file = n > 16 && n < (4 << 20) ? malloc((size_t)n) : NULL;
    if (!g_file || fread(g_file, 1, (size_t)n, f) != (size_t)n) {
        fclose(f);
        free(g_file);
        g_file = NULL;
        return;
    }
    fclose(f);
    const uint8_t *p = g_file, *end = g_file + n;
    if (memcmp(p, "IOGGLM01", 8))
        goto bad;
    p += 8;
    if (end - p < 2) goto bad;
    unsigned slen = p[0] | p[1] << 8;
    p += 2 + slen;
    if (end - p < 4) goto bad;
    uint32_t count = p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24;
    p += 4;
    for (uint32_t i = 0; i < count; i++) {
        if (g_nrec >= kMaxRecords || end - p < 2) goto bad;
        Record *r = &g_rec[g_nrec];
        r->kind = (char)p[0];
        unsigned fl = p[1];
        p += 2;
        if (fl >= sizeof(r->feature) || end - p < (long)fl + 8 + 32) goto bad;
        memcpy(r->feature, p, fl);
        r->feature[fl] = 0;
        p += fl;
        r->offset = p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24;
        r->len = p[4] | p[5] << 8 | p[6] << 16 | (uint32_t)p[7] << 24;
        p += 8;
        memcpy(r->sha, p, 32);
        p += 32;
        if ((uint32_t)(end - p) < r->len || (r->kind != 'W' && r->kind != 'T' && r->kind != 'S') ||
            FeatureIndex(r->feature) < 0) goto bad;
        r->data = p;
        p += r->len;
        g_nrec++;
    }
    fprintf(stderr, "[gaialabs] %d option records from %s\n", g_nrec, path);
    return;
bad:
    fprintf(stderr, "[gaialabs] %s: not a usable options pack\n", path);
    g_nrec = 0;
}

static bool StockMatches(const Cart *cart, uint32_t offset, uint32_t len, const uint8_t *sha)
{
    if (offset + len > cart->romImageSize)
        return false;
    uint8_t digest[32];
    sha256_compute(cart->rom + offset, len, digest);
    return !memcmp(digest, sha, 32);
}

static bool Save(Cart *cart, uint32_t offset, uint32_t len)
{
    if (g_nundo >= (int)(sizeof(g_undo) / sizeof(g_undo[0])))
        return false;
    Undo *u = &g_undo[g_nundo];
    u->original = malloc(len);
    if (!u->original)
        return false;
    memcpy(u->original, cart->rom + offset, len);
    u->offset = offset;
    u->len = len;
    g_nundo++;
    return true;
}

static void Put(Cart *cart, uint32_t offset, const uint8_t *data, uint32_t len)
{
    if (Save(cart, offset, len))
        memcpy(cart->rom + offset, data, len);
}

static void Unapply(void)
{
    Cart *cart = g_snes ? g_snes->cart : NULL;
    for (int i = g_nundo - 1; i >= 0; i--) {
        if (cart)
            memcpy(cart->rom + g_undo[i].offset, g_undo[i].original, g_undo[i].len);
        free(g_undo[i].original);
    }
    g_nundo = 0;
}

static uint16_t RomWord(const Cart *cart, uint32_t at) { return (uint16_t)(cart->rom[at] | cart->rom[at + 1] << 8); }

/* Stock size of the parallax table behind pointer slot `slot`: up to the
 * next table any slot points at. */
static uint32_t StockTableSize(const Cart *cart, uint32_t slot)
{
    unsigned at = RomWord(cart, slot), next = 0x10000;
    for (unsigned i = 0; i < 64; i++) {
        unsigned v = RomWord(cart, kParallaxTable + 2 * i);
        if (v > at && v < next)
            next = v;
    }
    return next - at;
}

typedef struct { uint32_t lo, hi; } Span;

static bool Take(Span *spans, int n, uint32_t len, uint32_t *at)
{
    for (int i = 0; i < n; i++)
        if (spans[i].hi - spans[i].lo >= len) {
            *at = spans[i].lo;
            spans[i].lo += len;
            return true;
        }
    return false;
}

/* QuintetLZ, the game's own compression (as iog_text.c QuintetExpand). */
static uint8_t *Expand(const uint8_t *src, size_t size, uint32_t *out_len)
{
    if (size < 2)
        return NULL;
    uint32_t len = src[0] | src[1] << 8;
    uint8_t *out = len ? malloc(len) : NULL, dict[256];
    if (!out)
        return NULL;
    memset(dict, 0x20, sizeof(dict));
    unsigned dp = 0xEF;
    uint64_t bit = 16;
    uint32_t n = 0;
#define BITS(k, v) do { v = 0; for (int _b = 0; _b < (k); _b++, bit++) { \
        if ((bit >> 3) >= size) { free(out); return NULL; } \
        v = v << 1 | (src[bit >> 3] >> (7 - (bit & 7)) & 1); } } while (0)
    while (n < len) {
        unsigned flag, v;
        BITS(1, flag);
        if (flag) {
            BITS(8, v);
            out[n++] = (uint8_t)v;
            dict[dp] = (uint8_t)v;
            dp = (dp + 1) & 0xFF;
        } else {
            unsigned idx, ln;
            BITS(8, idx);
            BITS(4, ln);
            for (ln += 2; ln--; ) {
                uint8_t b = dict[idx];
                idx = (idx + 1) & 0xFF;
                if (n < len)
                    out[n++] = b;
                dict[dp] = b;
                dp = (dp + 1) & 0xFF;
            }
        }
    }
#undef BITS
    *out_len = len;
    return out;
}

static void BuildResident(const Cart *cart)
{
    if (g_res_built)
        return;
    g_res_built = 1;
    for (int i = 0; i < g_nrec && g_nres < (int)(sizeof(g_res) / sizeof(g_res[0])); i++) {
        const Record *r = &g_rec[i];
        if (r->kind != 'S' || r->len < 2)
            continue;
        Resident *s = &g_res[g_nres];
        s->feature = FeatureIndex(r->feature);
        s->palette = r->data[0] == 'p';
        if (s->palette) {
            s->len = r->len - 1;
            if (r->offset + s->len > cart->romImageSize)
                continue;
            s->stock = malloc(s->len);
            s->mod = malloc(s->len);
            if (!s->stock || !s->mod) { free(s->stock); free(s->mod); continue; }
            memcpy(s->stock, cart->rom + r->offset, s->len);
            memcpy(s->mod, r->data + 1, s->len);
        } else {
            uint32_t a = 0, b = 0;
            if (r->offset >= cart->romImageSize)
                continue;
            s->stock = Expand(cart->rom + r->offset, cart->romImageSize - r->offset, &a);
            s->mod = Expand(r->data + 1, r->len - 1, &b);
            if (!s->stock || !s->mod || a != b) { free(s->stock); free(s->mod); continue; }
            s->len = a;
        }
        g_nres++;
    }
    fprintf(stderr, "[gaialabs] %d assets checked against save states\n", g_nres);
}

/* A save state keeps VRAM, WRAM and CGRAM as they were saved. Loaded with the
 * other setting, a room change inside the same area reloads only the palette
 * and the JP palette lands on stock art (or the reverse). So the version of
 * each asset that does not match the setting is looked for in memory and
 * swapped where it still matches byte for byte: found by a 32-byte window
 * where the two versions differ, accepted when most of it matches. */
static bool SwapIn(uint8_t *mem, size_t size, const uint8_t *have, const uint8_t *want, uint32_t len)
{
    uint32_t sig = 0;
    for (; sig + 32 <= len; sig += 16) {
        int differs = 0, distinct = 0;
        for (int k = 0; k < 32; k++) {
            differs += have[sig + k] != want[sig + k];
            distinct += have[sig + k] != have[sig];
        }
        if (differs >= 8 && distinct >= 8)
            break;
    }
    if (sig + 32 > len || len > size)
        return false;
    bool changed = false;
    for (size_t p = sig; p + len <= size + sig; p++) {
        if (mem[p] != have[sig] || memcmp(mem + p, have + sig, 32))
            continue;
        uint8_t *base = mem + p - sig;
        uint32_t same = 0;
        for (uint32_t k = 0; k < len; k++)
            same += base[k] == have[k];
        if (same < len - len / 8)
            continue;
        for (uint32_t k = 0; k < len; k++)
            if (base[k] == have[k])
                base[k] = want[k];
        changed = true;
        p += len - 1;
    }
    return changed;
}

static void SwapResident(void)
{
    if (!g_snes || !g_ppu || !g_nres)
        return;
    bool vram = false;
    for (int i = 0; i < g_nres; i++) {
        const Resident *s = &g_res[i];
        const bool on = s->feature >= 0 && g_usable[s->feature];
        const uint8_t *have = on ? s->stock : s->mod, *want = on ? s->mod : s->stock;
        if (s->palette) {
            /* CGRAM and the game's palette copy in WRAM, which it uploads
             * again (a fix to CGRAM alone is undone the next frame). */
            SwapIn((uint8_t *)g_ppu->cgram, sizeof(g_ppu->cgram), have, want, s->len);
            SwapIn(g_snes->ram, 0x20000, have, want, s->len);
            continue;
        }
        vram |= SwapIn((uint8_t *)g_ppu->vram, sizeof(g_ppu->vram), have, want, s->len);
        SwapIn(g_snes->ram, 0x20000, have, want, s->len);
    }
    if (vram) {
        g_ppu->vramWriteCount++;
        fprintf(stderr, "[gaialabs] art from a save state made with the other setting swapped\n");
    }
}

static void ResidentFrame(void)
{
    if (!g_snes || !g_nres)
        return;
    const unsigned scene = g_snes->ram[0x0644] | g_snes->ram[0x0645] << 8;
    /* At a room change and every half second (a state load changes nothing
     * the game announces). */
    if (scene != g_last_scene || ++g_res_tick >= 30) {
        g_last_scene = scene;
        g_res_tick = 0;
        SwapResident();
    }
}

static void Apply(void)
{
    Cart *cart = g_snes ? g_snes->cart : NULL;
    Unapply();
    if (!cart || !cart->rom || cart->type != CART_HIROM || cart->romImageSize != 0x200000 ||
        IogRandomizerActive())
        return;
    Load();
    BuildResident(cart);
    /* An option is usable only when every stock span it replaces is intact. */
    for (int f = 0; f < kNumFeatures; f++) {
        g_usable[f] = g_wanted[f];
        int any = 0;
        for (int i = 0; i < g_nrec && g_usable[f]; i++) {
            const Record *r = &g_rec[i];
            if (FeatureIndex(r->feature) != f)
                continue;
            any = 1;
            if (r->kind == 'W' && !StockMatches(cart, r->offset, r->len, r->sha))
                g_usable[f] = false;
            if (r->kind == 'T' && !StockMatches(cart, r->offset, 2, r->sha))
                g_usable[f] = false;
        }
        if (g_wanted[f] && !g_usable[f])
            fprintf(stderr, "[gaialabs] %s: ROM bytes differ from the stock USA ROM; left off\n", kFeatures[f]);
        if (!any)
            g_usable[f] = false;
    }
    for (int i = 0; i < g_nrec; i++) {
        const Record *r = &g_rec[i];
        if (r->kind == 'W' && g_usable[FeatureIndex(r->feature)])
            Put(cart, r->offset, r->data, r->len);
    }
    /* Parallax tables: free space is the end of bank $01 plus the stock slots
     * of the tables being moved (adjacent ones merge). Largest first. */
    Span spans[8];
    int nspans = 0;
    uint32_t lo = kBank1Free;
    while (lo < kBank1End && cart->rom[lo] != 0xFF) lo++;
    bool clean = true;
    for (uint32_t a = lo; a < kBank1End; a++) clean &= cart->rom[a] == 0xFF;
    if (clean && lo < kBank1End)
        spans[nspans++] = (Span){lo, kBank1End};
    int order[kMaxRecords], nt = 0;
    for (int i = 0; i < g_nrec; i++)
        if (g_rec[i].kind == 'T' && g_usable[FeatureIndex(g_rec[i].feature)])
            order[nt++] = i;
    for (int a = 0; a < nt; a++)
        for (int b = a + 1; b < nt; b++)
            if (g_rec[order[b]].len > g_rec[order[a]].len) { int t = order[a]; order[a] = order[b]; order[b] = t; }
    /* freed stock slots, sorted by address and merged */
    Span freed[8];
    int nfreed = 0;
    for (int k = 0; k < nt && nfreed < 8; k++) {
        const Record *r = &g_rec[order[k]];
        uint32_t at = 0x10000u + RomWord(cart, r->offset);
        freed[nfreed++] = (Span){at, at + StockTableSize(cart, r->offset)};
    }
    for (int a = 0; a < nfreed; a++)
        for (int b = a + 1; b < nfreed; b++)
            if (freed[b].lo < freed[a].lo) { Span t = freed[a]; freed[a] = freed[b]; freed[b] = t; }
    for (int a = 0; a < nfreed; a++) {
        if (nspans && spans[nspans - 1].hi == freed[a].lo && spans[nspans - 1].lo >= 0x10000 &&
            spans[nspans - 1].hi < kBank1Free)
            spans[nspans - 1].hi = freed[a].hi;
        else if (nspans < 8)
            spans[nspans++] = freed[a];
    }
    for (int k = 0; k < nt; k++) {
        const Record *r = &g_rec[order[k]];
        uint32_t at;
        if (!Take(spans, nspans, r->len, &at)) {
            fprintf(stderr, "[gaialabs] %s: no room for its parallax table; background stays stock\n", r->feature);
            continue;
        }
        Put(cart, at, r->data, r->len);
        const uint8_t pointer[2] = {(uint8_t)at, (uint8_t)(at >> 8)};
        Put(cart, r->offset, pointer, 2);
    }
}

/* ---- Full HP herb (full-health-herb/FullHealthHerb.patch.asm) -------------
 * A herb sets hpToHeal ($0B22), which UpdateHUD counts down one HP at a time
 * until Will's HP is full: the stock herb gives 8, the module 40, i.e. all of
 * it. Seen as the frame a herb is used up (the slots' herbs plus item
 * stacking's spare count at $0B55 drop by one) and hpToHeal becomes 8. */
static unsigned g_herbs = 0xFFFF, g_to_heal;

static unsigned Herbs(const uint8_t *ram)
{
    unsigned n = ram[0x0B55];
    for (int i = 0; i < 16; i++)
        n += ram[0x0AB4 + i] == 0x06;
    return n;
}

static void HerbFrame(void)
{
    if (!g_full_herb || !g_snes)
        return;
    uint8_t *ram = g_snes->ram;
    unsigned herbs = Herbs(ram), to_heal = ram[0x0B22] | ram[0x0B23] << 8;
    /* The HUD may already have counted the new 8 down by one this frame. */
    if (g_herbs != 0xFFFF && herbs + 1 == g_herbs && to_heal > g_to_heal && to_heal <= 8 && to_heal >= 7) {
        to_heal += 32;
        ram[0x0B22] = (uint8_t)to_heal;
        ram[0x0B23] = 0;
    }
    g_herbs = herbs;
    g_to_heal = to_heal;
}

/* ---- Pyramid portal exit (pyramid-portal-exit/PyramidPortalExit.patch.asm)
 * Every portal in a Pyramid room sends Will to the top of the entrance hall
 * ($CC at $01F8,$0130). The module sends him to the lower main area
 * ($01F8,$0380) instead; the portal in the hall itself keeps going to the
 * top. The destination waits in $064C (x) / $064E (y) while the screen fades,
 * so it is changed there, only for exactly that request from a Pyramid room. */
static void PortalFrame(void)
{
    if (!g_portal_exit || !g_snes)
        return;
    uint8_t *ram = g_snes->ram;
    const unsigned scene = ram[0x0644] | ram[0x0645] << 8;
    const unsigned want = ram[0x0642] | ram[0x0643] << 8;
    if (scene >= 0xCD && scene <= 0xDB && want == 0xCC &&
        (ram[0x064C] | ram[0x064D] << 8) == 0x01F8 && (ram[0x064E] | ram[0x064F] << 8) == 0x0130) {
        ram[0x064E] = 0x80;
        ram[0x064F] = 0x03;
    }
}

/* ---- Pyramid elevator 2x (pyramid-elevator-speed/PyramidElevatorSpeed.patch.asm)
 * The moving floors in the Pyramid (pyD7_sliding_wall, $08:C4ED) step the
 * layer offset at $1086 ($1060 + $26) by one per tick for the count in the
 * actor's own $26, resuming at $08:C555 (down) or $08:C566 (up). The module
 * takes two steps per tick and stops the moment the count runs out. Here the
 * host adds the second step right after a tick the game just took, only while
 * at least two remain, so the distance and the stop are the stock ones. */
static bool g_elevator;
static const uint8_t kElevatorStep[] = {   /* $08:C549..$08:C574, stock */
    0xbf, 0x10, 0x00, 0x7f, 0x85, 0x26, 0xa5, 0x24, 0x10, 0x11, 0x02, 0xc1, 0xa0, 0x60, 0x10,
    0xb9, 0x26, 0x00, 0x3a, 0x99, 0x26, 0x00, 0xc6, 0x26, 0xf0, 0x12, 0x6b, 0x02, 0xc1, 0xa0,
    0x60, 0x10, 0xb9, 0x26, 0x00, 0x1a, 0x99, 0x26, 0x00, 0xc6, 0x26, 0xf0, 0x01, 0x6b,
};
static struct { unsigned actor, count; } g_elev_last[8];

static void ElevatorFrame(void)
{
    if (!g_elevator || !g_snes || !g_snes->cart)
        return;
    uint8_t *ram = g_snes->ram;
    const Cart *cart = g_snes->cart;
    if (cart->romImageSize != 0x200000 ||
        memcmp(cart->rom + 0x08C549, kElevatorStep, sizeof(kElevatorStep)))
        return;
    unsigned seen[8], counts[8], n = 0;
    unsigned a = ram[0x56] | ram[0x57] << 8;
    for (int guard = 0; a >= 0x1000 && a < 0x1FC0 && guard < 96 && n < 8; guard++) {
        const unsigned pc = ram[a] | ram[a + 1] << 8;
        if ((ram[a + 2] & 0x3F) == 0x08 && (pc == 0xC555 || pc == 0xC566)) {
            unsigned count = ram[a + 0x26] | ram[a + 0x27] << 8;
            /* the game just took a step: its count dropped by one since last frame */
            for (int k = 0; k < 8; k++) {
                if (g_elev_last[k].actor != a || g_elev_last[k].count != count + 1 || count < 2)
                    continue;
                unsigned v = ram[0x1086] | ram[0x1087] << 8;
                v = (pc == 0xC566 ? v + 1 : v - 1) & 0xFFFF;
                ram[0x1086] = (uint8_t)v;
                ram[0x1087] = (uint8_t)(v >> 8);
                count--;
                ram[a + 0x26] = (uint8_t)count;
                ram[a + 0x27] = (uint8_t)(count >> 8);
                break;
            }
            seen[n] = a;
            counts[n++] = count;
        }
        a = ram[a + 6] | ram[a + 7] << 8;
    }
    memset(g_elev_last, 0, sizeof(g_elev_last));
    for (unsigned k = 0; k < n; k++) {
        g_elev_last[k].actor = seen[k];
        g_elev_last[k].count = counts[k];
    }
}

/* ---- activation ------------------------------------------------------------ */

static void ActivateData(const char *id)
{
    int f = FeatureIndex(id);
    if (f < 0)
        return;
    g_wanted[f] = true;
    Apply();
    fprintf(stderr, "[gaialabs] %s %s\n", id, g_usable[f] ? "on" : "unavailable");
}

#define DATA_PLUGIN(name) static void Activate_##name(void) { ActivateData(#name); }
DATA_PLUGIN(jp_edward)
DATA_PLUGIN(jp_itory)
DATA_PLUGIN(jp_wall)
DATA_PLUGIN(red_fountain)
DATA_PLUGIN(jp_church)
DATA_PLUGIN(jp_mines)
DATA_PLUGIN(jp_viper)
DATA_PLUGIN(crystal_ring)
DATA_PLUGIN(jp_prologue)

static void ActivateHerb(void) { g_full_herb = true; g_herbs = 0xFFFF; }
static void ActivatePortal(void) { g_portal_exit = true; }
static void ActivateElevator(void) { g_elevator = true; memset(g_elev_last, 0, sizeof(g_elev_last)); }

static void Reset(void)
{
    Unapply();
    memset(g_wanted, 0, sizeof(g_wanted));
    memset(g_usable, 0, sizeof(g_usable));
    g_last_scene = 0xFFFF;
    g_full_herb = g_portal_exit = g_elevator = false;
    memset(g_elev_last, 0, sizeof(g_elev_last));
    g_herbs = 0xFFFF;
    /* Plugin activation clears frame callbacks and then runs this: register
     * them here. The resident check runs with every option off too, to put
     * stock art back after a state saved with an option on. */
    Cart *cart = g_snes ? g_snes->cart : NULL;
    if (cart && cart->rom && cart->type == CART_HIROM && cart->romImageSize == 0x200000) {
        Load();
        BuildResident(cart);
    }
    snes_mod_register_frame_callback(HerbFrame);
    snes_mod_register_frame_callback(PortalFrame);
    snes_mod_register_frame_callback(ElevatorFrame);
    snes_mod_register_frame_callback(ResidentFrame);
}

bool IogGaiaLabsOn(const char *feature)
{
    int f = FeatureIndex(feature);
    if (f >= 0)
        return g_usable[f];
    if (!strcmp(feature, "full_herb"))
        return g_full_herb;
    if (!strcmp(feature, "portal_exit"))
        return g_portal_exit;
    if (!strcmp(feature, "elevator"))
        return g_elevator;
    return false;
}

SNES_MOD_CONSTRUCTOR(register_iog_gaialabs)
{
    snes_mod_register_reset_callback(Reset);
    snes_mod_register_activation_plugin("iog.gaialabs.jp_edward", Activate_jp_edward);
    snes_mod_register_activation_plugin("iog.gaialabs.jp_itory", Activate_jp_itory);
    snes_mod_register_activation_plugin("iog.gaialabs.jp_wall", Activate_jp_wall);
    snes_mod_register_activation_plugin("iog.gaialabs.red_fountain", Activate_red_fountain);
    snes_mod_register_activation_plugin("iog.gaialabs.jp_church", Activate_jp_church);
    snes_mod_register_activation_plugin("iog.gaialabs.jp_mines", Activate_jp_mines);
    snes_mod_register_activation_plugin("iog.gaialabs.jp_prologue", Activate_jp_prologue);
    snes_mod_register_activation_plugin("iog.gaialabs.jp_viper", Activate_jp_viper);
    snes_mod_register_activation_plugin("iog.gaialabs.crystal_ring", Activate_crystal_ring);
    snes_mod_register_activation_plugin("iog.gaialabs.full_herb", ActivateHerb);
    snes_mod_register_activation_plugin("iog.gaialabs.portal_exit", ActivatePortal);
    snes_mod_register_activation_plugin("iog.gaialabs.elevator", ActivateElevator);
}
