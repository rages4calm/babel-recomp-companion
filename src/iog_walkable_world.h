#ifndef IOG_WALKABLE_WORLD_H
#define IOG_WALKABLE_WORLD_H

#include <stdbool.h>
#include <stddef.h>

bool IogWalkableWorldInitialize(void);
void IogWalkableWorldTick(void);
bool IogWalkableWorldActive(void);
const char *IogWalkableWorldLocation(void);
bool IogWalkableWorldDirection(char *text,size_t capacity);

#endif
