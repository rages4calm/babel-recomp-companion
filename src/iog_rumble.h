/* Controller rumble (iog.enhancements/rumble): host-side, reads WRAM only.
 *
 * Sources, from the game's own code (gaia-sources baserom, ram_map /
 * wram-memory-map, functions-game-over, player_character.asm):
 *   $0ACE current HP, $0ACA max HP            a drop in play is a hit
 *   $09AE playerFlags bit $0200               set by CheckPlayerDeath (HP 0)
 *   $06F8/$06F9 SFX queue (ch1 / ch2)         sound #15 is the quake sound every
 *                                             CameraShakeActor tick queues
 *   $09AA player actor (0: title, file select, no player)
 *
 * IogRumbleStep is pure: no RAM, SDL, file or clock access. */
#ifndef IOG_RUMBLE_H
#define IOG_RUMBLE_H
#include <stdbool.h>
#include <stdint.h>

enum { kIogRumbleOff, kIogRumbleLow, kIogRumbleNormal, kIogRumbleStrong };
enum { kIogRumbleNone, kIogRumbleHit, kIogRumbleDeath, kIogRumbleShake, kIogRumbleStop };

typedef struct IogRumbleSample {
    uint64_t generation;   /* RtlStateGeneration: loads, rewinds, resets change it */
    uint16_t player, hp, max_hp, flags, sfx;
} IogRumbleSample;

typedef struct IogRumbleRequest {
    uint8_t kind;
    uint16_t low, high;    /* SDL_RumbleGamepad motor strengths */
    uint32_t ms;
    uint16_t damage;       /* hit: HP lost */
} IogRumbleRequest;

typedef struct IogRumbleTracker {
    IogRumbleSample previous;
    uint16_t pending;      /* HP lost on consecutive frames, not yet felt */
    uint16_t busy;         /* frames left of the last hit / death pulse */
    uint8_t shake_wait;    /* frames before another shake pulse */
    bool baseline, dead;
} IogRumbleTracker;

void IogRumbleTrackerInvalidate(IogRumbleTracker *tracker);
/* One REAL completed frame (never a speculative run-ahead one). */
IogRumbleRequest IogRumbleStep(IogRumbleTracker *tracker, const IogRumbleSample *sample, int level);

/* Runtime (iog_rumble.c). */
int IogRumbleGet(void);          /* 0 off, 1 low, 2 normal, 3 strong */
void IogRumbleSet(int level);    /* live; persists iog.enhancements/rumble */
#endif
