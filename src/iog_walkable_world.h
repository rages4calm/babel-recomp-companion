#ifndef IOG_WALKABLE_WORLD_H
#define IOG_WALKABLE_WORLD_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

bool IogWalkableWorldInitialize(void);
void IogWalkableWorldTick(void);
bool IogWalkableWorldActive(void);
const char *IogWalkableWorldLocation(void);
bool IogWalkableWorldDirection(char *text,size_t capacity);
/* The "Enhanced world map" setting (iog.enhancements/world_map). */
bool IogWalkableWorldEnhanced(void);
/* Markers, minimap and prompt plate for the enhanced view, over the presented
 * picture (BGRA, the widescreen frame). Draws nothing unless walking. */
void IogWalkableWorldDrawOverlay(uint8_t *dst,size_t pitch,int width,int height);

#endif
