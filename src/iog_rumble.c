/*
 * Controller rumble for player 1's gamepad (iog.enhancements/rumble).
 *
 * A hit is a drop of current HP ($0ACE) while the player actor exists. HP
 * lost on consecutive frames is one hit, felt on the first frame HP stops
 * falling: New Game+'s damage multiplier (iog_ngplus.c) lowers HP again
 * after the game has, and must not make a second pulse. Bigger hits are
 * stronger and longer. Death (HP 0, or CheckPlayerDeath's playerFlags
 * $0200) is one long pulse. The game's quake sound #15, queued in the SFX
 * latch $06F8/$06F9 on every tick of CameraShakeActor and by falling debris
 * and the other shaking scenes, is a light pulse, renewed while it lasts.
 *
 * Not a hit: anything across a timeline jump (save-state load, rewind,
 * reset; RtlStateGeneration changes), a change of maximum HP, HP rising,
 * and frames without a player (title, file select, a file being loaded).
 * The framework never runs mod frame callbacks on run-ahead's speculative
 * frames (common_rtl.c, RtlSetSpeculativeFrame), and a rollback load keeps
 * the generation, so a rolled-back hit is felt once, when the real frame
 * reaches it; the callback also refuses a speculative frame itself.
 *
 * Output: SDL_RumbleGamepad on player 1's gamepad when player 1 plays with
 * a gamepad ([Controller] SourceP1 = gamepad, g_config.enable_gamepad[0]).
 * Keyboard play has none. IOG_RUMBLE_LOG=path instead appends each request
 * (frame, kind, motors, duration) there and drives NO controller, pad or
 * not: test runs must never shake the owner's hardware.
 */
#include "iog_rumble.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- the pure tracker ------------------------------------------------------ */

void IogRumbleTrackerInvalidate(IogRumbleTracker *tracker)
{
    if (tracker) memset(tracker, 0, sizeof *tracker);
}

static uint16_t Motor(unsigned percent, int level)
{
    static const unsigned kScale[] = {0, 50, 75, 100};
    return (uint16_t)(65535u * percent * kScale[level] / 10000u);
}
static uint16_t MsToFrames(uint32_t ms) { return (uint16_t)((ms * 60u + 999u) / 1000u); }

IogRumbleRequest IogRumbleStep(IogRumbleTracker *t, const IogRumbleSample *s, int level)
{
    IogRumbleRequest r = {0};
    if (!t || !s) return r;
    if (level <= kIogRumbleOff || level > kIogRumbleStrong) {
        IogRumbleTrackerInvalidate(t);
        return r;
    }
    if (t->busy) t->busy--;
    if (t->shake_wait) t->shake_wait--;
    const bool in_play = s->player && s->max_hp && s->hp <= s->max_hp;
    const bool dead = in_play && (s->hp == 0 || (s->flags & 0x0200));
    if (!in_play || !t->baseline || s->generation != t->previous.generation ||
        s->max_hp != t->previous.max_hp) {
        /* A jump: whatever was rumbling belonged to the old timeline. */
        if (t->busy && t->baseline && s->generation != t->previous.generation)
            r.kind = kIogRumbleStop;
        const uint16_t keep_wait = t->shake_wait;
        IogRumbleTrackerInvalidate(t);
        if (in_play) {
            t->previous = *s;
            t->baseline = true;
            t->dead = dead;
            t->shake_wait = keep_wait;
        }
        return r;
    }
    if (dead) {
        if (!t->dead) {
            r.kind = kIogRumbleDeath;
            r.low = Motor(100, level);
            r.high = (uint16_t)(r.low * 70u / 100u);
            r.ms = 700;
            t->busy = MsToFrames(r.ms);
        }
        t->dead = true;
        t->pending = 0;
        t->previous = *s;
        return r;
    }
    t->dead = false;
    if (s->hp < t->previous.hp) {
        unsigned total = (unsigned)t->pending + (t->previous.hp - s->hp);
        t->pending = (uint16_t)(total > 0xFFFF ? 0xFFFF : total);
    } else if (t->pending) {
        const unsigned d = t->pending > 8 ? 8 : t->pending;
        r.kind = kIogRumbleHit;
        r.damage = t->pending;
        r.low = Motor(40 + 60 * (d - 1) / 7, level);
        r.high = (uint16_t)(r.low * 55u / 100u);
        r.ms = 100 + 20 * (d - 1);
        t->busy = MsToFrames(r.ms);
        t->pending = 0;
    }
    const bool quake = (s->sfx & 0xFF) == 0x15 || (s->sfx >> 8) == 0x15;
    if (!r.kind && quake && !t->busy && !t->shake_wait && !t->pending) {
        r.kind = kIogRumbleShake;
        r.low = Motor(30, level);
        r.ms = 150;
        t->shake_wait = 8;   /* renewed every 8 frames while the sound keeps coming */
    }
    t->previous = *s;
    return r;
}

/* ---- runtime ----------------------------------------------------------------- */
#ifndef IOG_RUMBLE_PURE
#include "common_cpu_infra.h"
#include "common_rtl.h"
#include "mod_runtime.h"
#include "snes/snes.h"
#include "desktop/config.h"
#include "desktop/sdl_compat.h"

static int g_level;
static IogRumbleTracker g_tracker;
static FILE *g_log;
static bool g_log_checked, g_log_only;

static uint16_t Rd(uint32_t a) { return (uint16_t)(g_snes->ram[a] | g_snes->ram[a + 1] << 8); }

/* Player 1's gamepad: none unless player 1 plays with a gamepad. The one the
 * host seated as player 1 (snesrecomp_host_seat_gamepad_id); when that is
 * unknown, SDL's player index 0, else the first opened pad, as the host
 * seats them (host_main.c OpenOneGamepad). */
int snesrecomp_host_seat_gamepad_id(int seat);   /* desktop/host_main.c */
static SDL_Gamepad *PlayerOnePad(void)
{
#if SNESRECOMP_SDL3
    if (!g_config.enable_gamepad[0]) return NULL;
    const int seated = snesrecomp_host_seat_gamepad_id(0);
    if (seated >= 0) {
        SDL_Gamepad *pad = SDL_GetGamepadFromID((SDL_JoystickID)seated);
        if (pad) return pad;
    }
    int count = 0;
    SDL_JoystickID *ids = SDL_GetGamepads(&count);
    SDL_Gamepad *first = NULL, *indexed = NULL;
    for (int i = 0; ids && i < count; i++) {
        SDL_Gamepad *pad = SDL_GetGamepadFromID(ids[i]);   /* opened by the host only */
        if (!pad) continue;
        if (!first) first = pad;
        if (!indexed && SDL_GetGamepadPlayerIndex(pad) == 0) indexed = pad;
    }
    if (ids) SDL_free(ids);
    return indexed ? indexed : first;
#else
    return NULL;
#endif
}

static void Output(const IogRumbleRequest *r)
{
    static const char *const kKinds[] = {"none", "hit", "death", "shake", "stop"};
    if (!g_log_checked) {
        g_log_checked = true;
        const char *path = getenv("IOG_RUMBLE_LOG");
        g_log_only = path && *path;
        if (g_log_only) g_log = fopen(path, "a");
    }
    if (g_log) {
        fprintf(g_log, "frame=%d kind=%s damage=%u low=%u high=%u ms=%u level=%d\n",
                snes_frame_counter, kKinds[r->kind], r->damage, r->low, r->high,
                (unsigned)r->ms, g_level);
        fflush(g_log);
    }
    if (g_log_only) return;   /* a test run: never the hardware */
#if SNESRECOMP_SDL3
    SDL_Gamepad *pad = PlayerOnePad();
    if (pad) SDL_RumbleGamepad(pad, r->low, r->high, r->ms);
#endif
}

static void RumbleFrame(void)
{
    if (!g_snes || !g_snes->ram || RtlSpeculativeFrame()) return;
    if (!g_level) { IogRumbleTrackerInvalidate(&g_tracker); return; }
    IogRumbleSample s;
    memset(&s, 0, sizeof s);
    s.generation = RtlStateGeneration();
    s.player = Rd(0x09AA);
    s.hp = Rd(0x0ACE);
    s.max_hp = Rd(0x0ACA);
    s.flags = Rd(0x09AE);
    s.sfx = Rd(0x06F8);
    const IogRumbleRequest r = IogRumbleStep(&g_tracker, &s, g_level);
    if (r.kind) Output(&r);
}

static void ActivateRumble(void)
{
    char v[16] = "normal";
    snes_mod_runtime_feature_option_value_c("iog.enhancements", "rumble", "strength", v, sizeof v);
    g_level = !strcmp(v, "low") ? kIogRumbleLow : !strcmp(v, "strong") ? kIogRumbleStrong : kIogRumbleNormal;
    IogRumbleTrackerInvalidate(&g_tracker);
}

/* Each activation: off until the plugin runs (the feature is on). The frame
 * callback itself is registered by iog_mods.c's reset, ahead of the HP
 * refill cheat, which would otherwise put a hit's HP back before it is seen. */
static void ResetRumble(void)
{
    g_level = kIogRumbleOff;
    IogRumbleTrackerInvalidate(&g_tracker);
}

int IogRumbleGet(void) { return g_level; }
void IogRumbleSet(int level)
{
    static const char *const kIds[] = {"normal", "low", "normal", "strong"};
    if (level < kIogRumbleOff || level > kIogRumbleStrong) return;
    if (!level && g_level) {   /* stop what is playing now */
        const IogRumbleRequest stop = {kIogRumbleStop, 0, 0, 0, 0};
        Output(&stop);
    }
    g_level = level;
    IogRumbleTrackerInvalidate(&g_tracker);
    snes_mod_runtime_persist_feature_c("iog.enhancements", "rumble", level != 0,
                                       level ? "strength" : NULL, kIds[level]);
}

void IogModsSetHpObserver(SNESModFrameCallback callback);   /* iog_mods.c */
SNES_MOD_CONSTRUCTOR(register_iog_rumble)
{
    IogModsSetHpObserver(RumbleFrame);
    snes_mod_register_reset_callback(ResetRumble);
    snes_mod_register_activation_plugin("iog.rumble", ActivateRumble);
}
#endif
