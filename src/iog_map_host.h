#ifndef IOG_MAP_HOST_H
#define IOG_MAP_HOST_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Actual-frame adapter; only a verified profile can publish a map. */
void IogMapHostFrame(bool verified,const char *content_sha256);
void IogMapHostReset(void);
void IogMapHostShutdown(void);
/* Inventory art captures must not replace the real exploration journal. */
void IogMapHostSuspend(bool suspended);
bool IogMapHostAvailable(void);
void IogMapHostRadarToggle(void);
void IogMapHostDrawRadar(uint8_t *dst,size_t pitch,int width,int height);
int IogMapHostOpen(void);
void IogMapHostNav(uint32_t inputs,uint32_t ticks);
void IogMapHostKey(int key,int repeat);
void IogMapHostPointer(int x,int y,int down);
bool IogMapHostIsOpen(void);
int IogMapHostImage(const uint32_t **pixels,int *width,int *height);
void IogMapHostClose(void);
#endif
