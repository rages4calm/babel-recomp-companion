#ifndef IOG_SPARKLE_H
#define IOG_SPARKLE_H
#include <stddef.h>
#include <stdint.h>

/* Red Jewel sparkles: draw over a finished picture whose pixel (0,0) is
 * world position (origin_x, origin_y), BGRA bytes. */
void IogSparkleDraw(uint8_t *dst, size_t pitch, int width, int height, int origin_x, int origin_y);
/* The 4:3 picture (wide view off): draw into the PPU render buffer. */
void IogSparkleNative(void);
int IogSparkleGet(void);
void IogSparkleSet(int on);

#endif
