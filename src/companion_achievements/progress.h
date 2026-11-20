/* SPDX-License-Identifier: MIT */
#ifndef IOG_ACHIEVEMENT_PROGRESS_H
#define IOG_ACHIEVEMENT_PROGRESS_H

#ifdef __cplusplus
extern "C" {
#endif
#include "toolkit/companion_achievements.h"

typedef struct IogAchievementStore IogAchievementStore;
typedef enum IogAchievementStatus {
    kIogAchievementLoading,
    kIogAchievementReady,
    kIogAchievementInUse,
    kIogAchievementInvalidProfile,
    kIogAchievementWriteFailure,
} IogAchievementStatus;

/* The worker owns the profile lock and all I/O. Destroy drains accepted events. */
IogAchievementStore *IogAchievementStoreOpen(const char *profile_directory);
void IogAchievementStoreClose(IogAchievementStore *store);
bool IogAchievementStoreEvent(IogAchievementStore *store, const char *event, uint32_t value);
/* Consume notices without replaying old unlocks when the profile opens. */
IogAchievementStatus IogAchievementStoreSnapshot(IogAchievementStore *store,
    ca_state states[CA_MAX_ACHIEVEMENTS], uint64_t *notices);

#ifdef __cplusplus
}
#endif
#endif
