/*
 * Red Jewel sparkles (trusted plugin "iog.jewel_sparkles").
 *
 * After andrewclunn's Gaia and Time (red-jewels/*.patch.asm, the GaiaLabs
 * line of work), done differently: his hack spawns a sparkle actor beside
 * each hidden jewel. Here nothing is added to the game. The host reads which
 * jewels are still to be found and draws a twinkle of light over them in the
 * finished picture, in the wide view, in its margins and in the 4:3 picture.
 *
 *  - The sixteen hidden jewels are one invisible actor ($00:C672). Each keeps
 *    its index in actor+$0E; its pickup sets event flag $0280 + index, bit
 *    (index & 7) of $0A50/$0A51. The game never removes the actor, so a
 *    sparkle shows exactly while that flag is clear.
 *  - Four people give a jewel: Lance at the party (scene $79, flags $A5 set,
 *    $E2 clear), Ann's trade in Euro ($95, $D6 and $E5 clear), the stone girl
 *    in the Gorgon hut ($AE, $E6 clear) and the snake game in Dao ($C6, $E7
 *    clear). The sparkle follows the actor nearest that person's place.
 *
 * Flags: event flag n is bit (n & 7) of $0A00 + (n >> 3).
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "common_cpu_infra.h"
#include "mod_runtime.h"
#include "snes/ppu.h"
#include "snes/snes.h"

#include "iog_sparkle.h"

extern Ppu *g_ppu;

static bool g_on;

static uint16_t Rd(const uint8_t *ram, unsigned a) { return (uint16_t)(ram[a] | ram[a + 1] << 8); }
static bool Flag(const uint8_t *ram, unsigned n) { return (ram[0x0A00 + (n >> 3)] >> (n & 7)) & 1; }

typedef struct Giver { uint8_t scene, tile_x, tile_y; uint8_t need_set, need_clear1, need_clear2; } Giver;
/* need_set 0: no condition. Tiles are the spawn places (16 pixels). */
static const Giver kGivers[] = {
    {0x79, 0x07, 0x09, 0xA5, 0xE2, 0xE2},   /* Lance, after the party */
    {0x95, 0x0B, 0x0A, 0x00, 0xD6, 0xE5},   /* Ann, the Gorgon Flower trade */
    {0xAE, 0x08, 0x07, 0x00, 0xE6, 0xE6},   /* the stone girl */
    {0xC6, 0x07, 0x09, 0x00, 0xE7, 0xE7},   /* the snake game */
};

enum { kMaxSparkles = 8 };
typedef struct Sparkle { int x, y; unsigned phase; } Sparkle;

static bool ActorOk(unsigned a) { return a >= 0x1000 && a < 0x1FC0 && !((a - 0x1000) % 0x30); }

static int Collect(const uint8_t *ram, Sparkle *out)
{
    int n = 0;
    const unsigned scene = Rd(ram, 0x0644);
    if (!Rd(ram, 0x09AA) || scene == 0xFF || scene >= 0xF0)
        return 0;
    const unsigned tick = ram[0x36];
    /* Hidden jewels. */
    unsigned a = Rd(ram, 0x56), guard = 0;
    while (ActorOk(a) && guard++ < 84 && n < kMaxSparkles) {
        const unsigned pc = Rd(ram, a), bank = ram[a + 2];
        if ((bank & 0x3F) == 0x00 && pc >= 0xC672 && pc < 0xC6A6) {
            const unsigned index = ram[a + 0x0E] & 0x0F;
            if (!Flag(ram, 0x0280 + index)) {
                out[n].x = (int16_t)Rd(ram, a + 0x14);
                out[n].y = (int16_t)Rd(ram, a + 0x16) - 4;
                out[n].phase = tick + index * 11;
                n++;
            }
        }
        a = Rd(ram, a + 6);
    }
    /* People who give a jewel. */
    for (size_t g = 0; g < sizeof(kGivers) / sizeof(kGivers[0]) && n < kMaxSparkles; g++) {
        const Giver *v = &kGivers[g];
        if (v->scene != scene || (v->need_set && !Flag(ram, v->need_set)) ||
            Flag(ram, v->need_clear1) || Flag(ram, v->need_clear2))
            continue;
        const int px = v->tile_x * 16 + 8, py = v->tile_y * 16 + 8;
        unsigned best = 0; int best_d = 40 * 40;
        a = Rd(ram, 0x56); guard = 0;
        while (ActorOk(a) && guard++ < 84) {
            const uint16_t flags = Rd(ram, a + 0x10);
            if (a != Rd(ram, 0x09AA) && !(flags & 0x8000) && !(flags & 0x2000)) {
                const int dx = (int16_t)Rd(ram, a + 0x14) - px, dy = (int16_t)Rd(ram, a + 0x16) - py;
                if (dx * dx + dy * dy < best_d) { best_d = dx * dx + dy * dy; best = a; }
            }
            a = Rd(ram, a + 6);
        }
        if (best) {
            out[n].x = (int16_t)Rd(ram, best + 0x14) + 6;
            out[n].y = (int16_t)Rd(ram, best + 0x16) - 26;
            out[n].phase = tick + (unsigned)g * 17;
            n++;
        }
    }
    return n;
}

/* Light added to one pixel (BGRA bytes), scaled by the screen brightness. */
static void Add(uint8_t *p, int r, int g, int b, int a)
{
    const int m = g_ppu ? g_ppu->brightnessMult[31] : 255;
    a = a * m / 255;
    int v;
    v = p[2] + r * a / 255; p[2] = (uint8_t)(v > 255 ? 255 : v);
    v = p[1] + g * a / 255; p[1] = (uint8_t)(v > 255 ? 255 : v);
    v = p[0] + b * a / 255; p[0] = (uint8_t)(v > 255 ? 255 : v);
}

/* A twinkle: a four-pointed star that swells and fades over 64 ticks, with
 * a soft halo and a warm red heart; quiet for part of the cycle so it reads
 * as a glint rather than a marker. (cx, cy) is in dst pixels. */
static void Twinkle(uint8_t *dst, size_t pitch, int width, int height, int cx, int cy, unsigned phase)
{
    const unsigned t = phase & 63;
    if (t >= 40)
        return;   /* rest */
    const int ramp = t < 20 ? (int)t : 40 - (int)t;     /* 0..20 */
    const int arm = 1 + ramp / 4;                        /* 1..6 pixels */
    const int peak = 90 + ramp * 8;                      /* brightness */
    for (int dy = -arm - 1; dy <= arm + 1; dy++)
        for (int dx = -arm - 1; dx <= arm + 1; dx++) {
            const int x = cx + dx, y = cy + dy;
            if (x < 0 || y < 0 || x >= width || y >= height)
                continue;
            const int ax = abs(dx), ay = abs(dy);
            int a = 0;
            if (!dx && !dy) a = peak;
            else if (!dy && ax <= arm) a = peak * (arm + 1 - ax) / (arm + 1);
            else if (!dx && ay <= arm) a = peak * (arm + 1 - ay) / (arm + 1);
            else if (ax == 1 && ay == 1) a = peak / 3;
            else if (ax + ay <= 2) a = peak / 6;
            if (a <= 0)
                continue;
            uint8_t *p = dst + (size_t)y * pitch + (size_t)x * 4;
            if (!dx && !dy)
                Add(p, 255, 150, 150, a);   /* red-tinged heart */
            else
                Add(p, 255, 245, 210, a);   /* warm white light */
        }
}

void IogSparkleDraw(uint8_t *dst, size_t pitch, int width, int height, int origin_x, int origin_y)
{
    if (!g_on || !g_snes || !dst)
        return;
    Sparkle s[kMaxSparkles];
    const int n = Collect(g_snes->ram, s);
    for (int i = 0; i < n; i++)
        Twinkle(dst, pitch, width, height, s[i].x - origin_x, s[i].y - origin_y, s[i].phase);
}

void IogSparkleNative(void)
{
    if (!g_on || !g_snes || !g_ppu || !g_ppu->renderBuffer)
        return;
    const int extra = g_ppu->extraLeftRight;
    const int cam_x = (int16_t)Rd(g_snes->ram, 0x068A), cam_y = (int16_t)Rd(g_snes->ram, 0x068E);
    IogSparkleDraw(g_ppu->renderBuffer, g_ppu->renderPitch, 256 + 2 * extra, 224,
                   cam_x - extra, cam_y);
}

static void Activate(void) { g_on = true; }
static void Reset(void) { g_on = false; }
int IogSparkleGet(void) { return g_on; }
void IogSparkleSet(int on)
{
    g_on = on != 0;
    snes_mod_runtime_persist_feature_c("iog.enhancements", "jewel_sparkles", on != 0, NULL, NULL);
}

SNES_MOD_CONSTRUCTOR(register_iog_sparkle)
{
    snes_mod_register_reset_callback(Reset);
    snes_mod_register_activation_plugin("iog.jewel_sparkles", Activate);
}
