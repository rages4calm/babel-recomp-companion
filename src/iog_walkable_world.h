#ifndef IOG_WALKABLE_WORLD_H
#define IOG_WALKABLE_WORLD_H

#include <stdbool.h>

bool IogWalkableWorldInitialize(void);
void IogWalkableWorldTick(void);
bool IogWalkableWorldActive(void);
const char *IogWalkableWorldLocation(void);

#endif
