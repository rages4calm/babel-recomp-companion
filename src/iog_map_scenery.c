#include "iog_map_scenery.h"
#include <limits.h>

static unsigned Word(const uint8_t *p,size_t n)
{ return p[n]|((unsigned)p[n+1]<<8); }

static bool Overlap(const void *a,size_t an,const void *b,size_t bn)
{
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return an && bn && (x<=y ? y-x<an : x-y<bn);
}

static bool Tile(const IogMapScenerySource *s,unsigned x,unsigned y,unsigned *tile)
{
    size_t page=(size_t)(y>>8)*(s->width>>8)+(x>>8);
    size_t cell=(size_t)s->map_address+page*256+((y>>4)&15)*16+((x>>4)&15);
    if(cell>=s->ram_bytes) return false;
    size_t at=(size_t)s->definitions_address+(size_t)s->ram[cell]*8+
        ((y>>3)&1)*4+((x>>3)&1)*2;
    if(at>=s->ram_bytes || s->ram_bytes-at<2) return false;
    *tile=Word(s->ram,at);return true;
}

bool IogMapSceneryRender(const IogMapScenerySource *s,
    unsigned x,unsigned y,unsigned width,unsigned height,unsigned step,
    uint32_t *output,size_t capacity,size_t pitch)
{
    if(!s || !s->ram || !s->vram || !s->cgram || !output ||
       !s->width || !s->height || s->width>4096 || s->height>4096 ||
       (s->width&255) || (s->height&255) || s->ram_bytes>65536 ||
       s->vram_words!=32768 || s->cgram_words!=256 ||
       s->character_address>=32768 ||
       (step!=1 && step!=2 && step!=4 && step!=8) ||
       !width || !height || x>=s->width || y>=s->height ||
       width>s->width-x || height>s->height-y) return false;
    size_t w=(width+step-1)/step,h=(height+step-1)/step;
    if(pitch<w*4 || pitch%4 || pitch>SIZE_MAX/h || capacity<pitch*h ||
       Overlap(output,pitch*h,s,sizeof(*s)) ||
       Overlap(output,pitch*h,s->ram,s->ram_bytes) ||
       Overlap(output,pitch*h,s->vram,s->vram_words*2) ||
       Overlap(output,pitch*h,s->cgram,s->cgram_words*2)) return false;
    /* Validate every sampled cell before touching caller storage. */
    for(size_t row=0;row<h;row++) for(size_t col=0;col<w;col++) {
        unsigned tile;
        if(!Tile(s,x+(unsigned)col*step,y+(unsigned)row*step,&tile)) return false;
    }
    for(size_t row=0;row<h;row++) {
        uint32_t *dst=(uint32_t*)((uint8_t*)output+row*pitch);
        unsigned wy=y+(unsigned)row*step;
        for(size_t col=0;col<w;col++) {
            unsigned wx=x+(unsigned)col*step,tile=0;
            (void)Tile(s,wx,wy,&tile);
            unsigned px=wx&7,py=wy&7;
            if(tile&0x4000) px=7-px;
            if(tile&0x8000) py=7-py;
            unsigned at=(s->character_address+(tile&1023)*16+py)&32767;
            unsigned a=s->vram[at],b=s->vram[(at+8)&32767],bit=7-px;
            unsigned index=((a>>bit)&1)|(((a>>(bit+8))&1)<<1)|
                (((b>>bit)&1)<<2)|(((b>>(bit+8))&1)<<3);
            if(!index) {dst[col]=0;continue;}
            unsigned color=s->cgram[((tile>>10)&7)*16+index];
            unsigned r=color&31,g=(color>>5)&31,blue=(color>>10)&31;
            r=(r<<3)|(r>>2);g=(g<<3)|(g>>2);blue=(blue<<3)|(blue>>2);
            dst[col]=0xFF000000u|(r<<16)|(g<<8)|blue;
        }
    }
    return true;
}
