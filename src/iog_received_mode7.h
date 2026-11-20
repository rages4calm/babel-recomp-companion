#ifndef IOG_RECEIVED_MODE7_H
#define IOG_RECEIVED_MODE7_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
struct Ppu;
bool IogReceivedMode7Begin(const struct Ppu *ppu,const uint8_t *ram,
    const uint8_t *rom,size_t rom_size,int width,int height);
void IogReceivedMode7Capture(const struct Ppu *ppu,const uint8_t *ram,int line);
bool IogReceivedMode7End(void);
int IogReceivedMode7Draw(uint8_t *dst,size_t pitch,const uint8_t *field,
    int width,int height);
const char *IogReceivedMode7Reason(void);
bool IogReceivedMode7Perspective(void);
#endif
