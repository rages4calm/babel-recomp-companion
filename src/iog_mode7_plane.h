#ifndef IOG_MODE7_PLANE_H
#define IOG_MODE7_PLANE_H
#include "snes/ppu.h"
#include "snes/mode7_hd.h"
#include "snes/ppu_brightness.h"
#include <stdint.h>

static inline int64_t IogMode7Floor(int64_t value,int64_t divisor)
{
    return value>=0?value/divisor:-((-value+divisor-1)/divisor);
}

/* Read-only affine BG1 sample: 0x00RRGGBB (B,G,R,zero bytes on LE).
 * Screen Y is the hardware raster line (native visible rows are 1..224).
 * This retains the original six-bit intermediate truncation, unlike the HD
 * fractional sampler. Palette index zero resolves to the backdrop color.
 * The caller admits only plain, nonmosaic Mode7 without windows/color math
 * or EXTBG; this is not an OBJ/UI/compositor replacement. */
static inline uint8_t IogMode7PlaneIndex(const Ppu *p,int screen_x,int screen_y)
{
    if(!p || screen_x < -2048 || screen_x > 2048 ||
       screen_y < -512 || screen_y > 512 || PPU_forcedBlank(p)) return 0;
    int cx=SnesMode7HdSign13(p->m7matrix[4]);
    int cy=SnesMode7HdSign13(p->m7matrix[5]);
    int h=SnesMode7HdSign13(p->m7matrix[6])-cx;
    int v=SnesMode7HdSign13(p->m7matrix[7])-cy;
    h=(h&0x2000)?(h|~1023):(h&1023);
    v=(v&0x2000)?(v|~1023):(v&1023);
    int64_t x=PPU_m7xFlip(p)?255-(int64_t)screen_x:screen_x;
    int64_t y=PPU_m7yFlip(p)?255-(int64_t)screen_y:screen_y;
    int64_t a=p->m7matrix[0],b=p->m7matrix[1];
    int64_t c=p->m7matrix[2],d=p->m7matrix[3];
    int64_t u=IogMode7Floor(a*h,64)*64+IogMode7Floor(b*y,64)*64+
        IogMode7Floor(b*v,64)*64+(int64_t)cx*256+a*x;
    int64_t w=IogMode7Floor(c*h,64)*64+IogMode7Floor(d*y,64)*64+
        IogMode7Floor(d*v,64)*64+(int64_t)cy*256+c*x;
    return SnesMode7HdFetchInt(p->m7sel,p->vram,
        (int)IogMode7Floor(u,256),(int)IogMode7Floor(w,256),-1);
}

static inline uint32_t IogMode7PlanePixel(const Ppu *p,int screen_x,int screen_y)
{
    if(!p || screen_x < -2048 || screen_x > 2048 ||
       screen_y < -512 || screen_y > 512 || PPU_forcedBlank(p)) return 0;
    uint8_t index=IogMode7PlaneIndex(p,screen_x,screen_y);
    unsigned color=p->cgram[index],brightness=PPU_brightness(p);
    return (uint32_t)ppu_brightness_level(color&31,brightness)<<16 |
        (uint32_t)ppu_brightness_level((color>>5)&31,brightness)<<8 |
        ppu_brightness_level((color>>10)&31,brightness);
}
#endif
