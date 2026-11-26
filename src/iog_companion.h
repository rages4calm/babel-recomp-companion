#ifndef IOG_COMPANION_H
#define IOG_COMPANION_H
#include <stdint.h>
int IogCompanionCaptureInventory(void);
const uint32_t *IogCompanionInventoryImage(int *w, int *h);
void IogCompanionAfterFrame(void);
void IogCompanionGrabMenu(void);
/* Host companion hooks (SnesDesktopHostGame.companion_*). */
int IogCompanionOpen(void);
int IogCompanionAchievementQuiet(void);
/* The settings menu's Achievements row: open them when it has closed. */
void IogCompanionRequestAchievements(void);
/* Optional local-human input hook: replace the Original local radar command
 * with the paused enhanced Map. Does not handle scripts/netplay/world travel. */
int IogCompanionInput(uint32_t *human);
void IogCompanionNav(uint32_t inputs, uint32_t ticks);
void IogCompanionKey(int key, int repeat);
void IogCompanionPointer(int x, int y, int down);
int IogCompanionImage(const uint32_t **px, int *w, int *h);
int IogCompanionLive(const uint32_t **px, int *w, int *h);
#endif
