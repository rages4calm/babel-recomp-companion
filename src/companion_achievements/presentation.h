/* SPDX-License-Identifier: MIT */
#ifndef IOG_ACHIEVEMENT_PRESENTATION_H
#define IOG_ACHIEVEMENT_PRESENTATION_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

void IogAchievementUiOpen(uint32_t held);
void IogAchievementUiClose(void);
bool IogAchievementUiIsOpen(void);
void IogAchievementUiNav(uint32_t buttons, uint32_t ticks);
void IogAchievementUiKey(int key);
void IogAchievementUiPointer(int x, int y, int pressed);
bool IogAchievementUiImage(const uint32_t **pixels, int *width, int *height);
void IogAchievementUiFrame(unsigned frame, uint32_t ticks, bool quiet);
void IogAchievementUiToast(uint8_t *dst, size_t pitch, int width, int height);
void IogAchievementUiShutdown(void);

#endif
