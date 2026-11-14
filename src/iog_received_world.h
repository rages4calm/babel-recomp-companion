#ifndef IOG_RECEIVED_WORLD_H
#define IOG_RECEIVED_WORLD_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
bool IogReceivedWorldEnabled(void);
void IogReceivedWorldGeometry(int dw, int dh, int *w, int *h);
void IogReceivedWorldBeginRaster(void);
void IogReceivedWorldCaptureLine(int line);
void IogReceivedWorldEndRaster(void);
int IogReceivedWorldDraw(uint8_t *dst, size_t pitch, const uint8_t *field,
                         int width, int height, double alpha);
#endif
