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

/* Whole texel of a 40.24 coordinate, rounded toward minus infinity. */
_Static_assert((-1>>1)==-1,"arithmetic right shift");
static inline int IogMode7PlaneTexel(int64_t coordinate)
{
    return (int)(coordinate>>24);
}

static inline unsigned IogMode7PlaneSamples(int64_t footprint_q16)
{
    /* A magnified texel only needs its edges softened. A minified one needs
     * an even number of samples per texel crossed, bounded for the horizon. */
    if(footprint_q16<=65536)return 3;
    int64_t texels=(footprint_q16+65535)/65536;
    return texels>=4?8u:(unsigned)texels*2u;
}

/* Host presentation only: one output row with each pixel box-filtered over
 * its cell [x,x+1) x [y,y+1). The matrices are in 1/256 of a hardware matrix
 * unit, `from` at the top of the row and `to` at the top of the next one, so a
 * perspective producer can continue between raster lines. Colors come from the
 * caller's composed palette for this line. Unlike IogMode7PlaneIndex this
 * deliberately has no six-bit truncation and is not a hardware reference; an
 * integer positive axis-aligned scale reproduces the point sample exactly. */
static inline uint32_t IogMode7PlaneColor(const Ppu *p,const uint32_t colors[256],
    uint32_t outside,int u,int w)
{
    /* The one case where the fetch reports the backdrop for a texel that is
     * not on the map at all. */
    if(((unsigned)u>=1024 || (unsigned)w>=1024) && (p->m7sel&0xC0)==0x80)return outside;
    return colors[SnesMode7HdFetchInt(p->m7sel,p->vram,u,w,-1)];
}

/* As IogMode7PlaneFilteredRow, with the color shown past the edge of a
 * non-repeating map chosen by the caller instead of palette entry 0. */
static inline void IogMode7PlaneFilteredRowEdge(const Ppu *p,const int32_t from[4],
    const int32_t to[4],int screen_y,int first_x,int count,
    const uint32_t colors[256],uint32_t outside,uint32_t *out)
{
    if(!p || !from || !to || !colors || !out || count<1 || count>4096 ||
       first_x < -2048 || first_x+count > 2049 ||
       screen_y < -512 || screen_y > 512) return;
    if(PPU_forcedBlank(p)) {
        for(int i=0;i<count;i++)out[i]=colors[0];
        return;
    }
    int cx=SnesMode7HdSign13(p->m7matrix[4]);
    int cy=SnesMode7HdSign13(p->m7matrix[5]);
    int h=SnesMode7HdSign13(p->m7matrix[6])-cx;
    int v=SnesMode7HdSign13(p->m7matrix[7])-cy;
    h=(h&0x2000)?(h|~1023):(h&1023);
    v=(v&0x2000)?(v|~1023):(v&1023);
    bool flip_x=PPU_m7xFlip(p),flip_y=PPU_m7yFlip(p);
    int64_t across=(from[0]<0?-(int64_t)from[0]:from[0])+(from[2]<0?-(int64_t)from[2]:from[2]);
    int64_t y0=flip_y?255-(int64_t)screen_y:screen_y,y1=flip_y?y0-1:y0+1;
    int64_t middle=(int64_t)first_x+count/2;
    middle=flip_x?255-middle:middle;
    int64_t du=((int64_t)to[0]-from[0])*(h+middle)+(int64_t)to[1]*(v+y1)-(int64_t)from[1]*(v+y0);
    int64_t dw=((int64_t)to[2]-from[2])*(h+middle)+(int64_t)to[3]*(v+y1)-(int64_t)from[3]*(v+y0);
    if(du<0)du=-du;
    if(dw<0)dw=-dw;
    unsigned nx=IogMode7PlaneSamples(across),ny=IogMode7PlaneSamples(du>dw?du:dw);
    int64_t a[8],c[8],base_u[8],base_w[8];
    for(unsigned j=0;j<ny;j++) {
        int64_t part=(int64_t)(2*j+1)*128/ny; /* 0..255 within the row */
        int64_t b=from[1]+((int64_t)to[1]-from[1])*part/256;
        int64_t d=from[3]+((int64_t)to[3]-from[3])*part/256;
        a[j]=from[0]+((int64_t)to[0]-from[0])*part/256;
        c[j]=from[2]+((int64_t)to[2]-from[2])*part/256;
        int64_t y=(int64_t)screen_y*256+part;
        if(flip_y)y=255*256-y;
        y+=(int64_t)v*256;
        base_u[j]=a[j]*h*256+b*y+(int64_t)cx*16777216;
        base_w[j]=c[j]*h*256+d*y+(int64_t)cy*16777216;
    }
    /* Sums are averaged with a rounded reciprocal: exact for a uniform cell. */
    unsigned total=nx*ny,reciprocal=(65536u+total/2)/total;
    int64_t offset[8];
    for(unsigned k=0;k<nx;k++)offset[k]=(int64_t)(2*k+1)*128/nx;
    /* Where the row is magnified in both axes most cells lie inside one
     * texel: the four cell corners then agree and one fetch is the average. */
    bool magnified=nx==3 && ny==3;
    int64_t edge_y[2]={(int64_t)screen_y*256,(int64_t)screen_y*256+256};
    int64_t edge_u[2],edge_w[2];
    for(unsigned e=0;e<2;e++) {
        const int32_t *m=e?to:from;
        int64_t y=(flip_y?255*256-edge_y[e]:edge_y[e])+(int64_t)v*256;
        edge_u[e]=(int64_t)m[0]*h*256+(int64_t)m[1]*y+(int64_t)cx*16777216;
        edge_w[e]=(int64_t)m[2]*h*256+(int64_t)m[3]*y+(int64_t)cy*16777216;
    }
    for(int i=0;i<count;i++) {
        int64_t left=((int64_t)first_x+i)*256;
        if(magnified) {
            int64_t x0=flip_x?255*256-left:left,x1=flip_x?x0-256:x0+256;
            int u=IogMode7PlaneTexel(edge_u[0]+from[0]*x0),w=IogMode7PlaneTexel(edge_w[0]+from[2]*x0);
            if(u==IogMode7PlaneTexel(edge_u[0]+from[0]*x1) && w==IogMode7PlaneTexel(edge_w[0]+from[2]*x1) &&
               u==IogMode7PlaneTexel(edge_u[1]+to[0]*x0) && w==IogMode7PlaneTexel(edge_w[1]+to[2]*x0) &&
               u==IogMode7PlaneTexel(edge_u[1]+to[0]*x1) && w==IogMode7PlaneTexel(edge_w[1]+to[2]*x1)) {
                out[i]=IogMode7PlaneColor(p,colors,outside,u,w)&0xffffffu;
                continue;
            }
        }
        uint32_t red_blue=0,green=0;
        for(unsigned k=0;k<nx;k++) {
            int64_t x=left+offset[k];
            if(flip_x)x=255*256-x;
            for(unsigned j=0;j<ny;j++) {
                uint32_t color=IogMode7PlaneColor(p,colors,outside,
                    IogMode7PlaneTexel(base_u[j]+a[j]*x),
                    IogMode7PlaneTexel(base_w[j]+c[j]*x));
                red_blue+=color&0xff00ffu;green+=color&0xff00u;
            }
        }
        out[i]=(((red_blue>>16)*reciprocal+32768u)>>16)<<16 |
            ((((green>>8)*reciprocal+32768u)>>16)<<8) |
            (((red_blue&0xffffu)*reciprocal+32768u)>>16);
    }
}

static inline void IogMode7PlaneFilteredRow(const Ppu *p,const int32_t from[4],
    const int32_t to[4],int screen_y,int first_x,int count,
    const uint32_t colors[256],uint32_t *out)
{
    if(colors)IogMode7PlaneFilteredRowEdge(p,from,to,screen_y,first_x,count,colors,colors[0],out);
}
#endif
