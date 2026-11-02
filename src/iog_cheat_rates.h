/* Host-side optional cheats. No guest instruction implementation is copied. */
#ifndef IOG_CHEAT_RATES_H
#define IOG_CHEAT_RATES_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct IogCheatRateSample {
    uint64_t generation;
    uint16_t scene, player, hp;
    uint16_t stats[3]; /* maximum HP, strength, defense */
    uint8_t cleared[32], reward_kind; /* stock table: 1 HP, 2 STR, 3 DEF */
    bool supported, blocked;
} IogCheatRateSample;
typedef struct IogCheatRateTracker {
    IogCheatRateSample previous;
    uint16_t armed_stats[3];
    uint8_t pending_kind, pending_frames;
    bool baseline;
} IogCheatRateTracker;
typedef struct IogCheatRateAward { uint8_t kind; uint16_t extra; } IogCheatRateAward;

int IogCheatRateClampMultiplier(int value);
bool IogCheatRateSourceSupported(const uint8_t *rom, size_t size);
void IogCheatRateTrackerInvalidate(IogCheatRateTracker *tracker);
/* Real completed frames only. Returns a bounded EXTRA award after an exact
 * source-derived original reward. No RAM, CPU, file or clock access here. */
IogCheatRateAward IogCheatRateStep(IogCheatRateTracker *, const IogCheatRateSample *, int multiplier);

/* Runtime integration in iog_mods.c. Load/reset invalidates pending observations
 * but NEVER clears session taint. A fresh process starts a fresh taint flag. */
void IogCheatRatesInvalidate(void);
int IogRoomRewardMultiplierGet(void);
void IogRoomRewardMultiplierSet(int multiplier);
void IogCheatsMarkUsed(void);
bool IogCheatsSessionTainted(void);
#endif
