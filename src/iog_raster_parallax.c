#include "iog_raster_parallax.h"
#include <string.h>

static unsigned Word(const uint8_t *p,size_t at)
{ return p[at]|((unsigned)p[at+1]<<8); }
static int Signed(unsigned n)
{ return n&32768u?(int)n-65536:(int)n; }
static int64_t FloorDivide(int64_t n,int64_t d)
{ return n>=0?n/d:-((-n+d-1)/d); }
static bool Overlap(const void *a,size_t an,const void *b,size_t bn)
{
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return an && bn && (x<=y?y-x<an:x-y<bn);
}
static unsigned Project(unsigned factor,int x)
{
    return (unsigned)FloorDivide((int64_t)(factor&255u)*x,factor>>8);
}
static const IogRasterParallaxBand *Band(const IogRasterParallax *m,unsigned row)
{
    for(unsigned i=0;i<m->band_count;i++)
        if(row>=m->bands[i].first_row && row<m->bands[i].end_row)return &m->bands[i];
    return NULL;
}

bool IogRasterParallaxSample(const IogRasterParallax *m,int y,int x,uint16_t *out)
{
    if(!m || !out || !m->valid || !m->band_count ||
       m->band_count>kIogRasterParallaxBands || m->height!=256 || m->width!=512 ||
       y<0 || y>255 || x < -2048 || x>4096)return false;
    const IogRasterParallaxBand *b=Band(m,(unsigned)y);
    if(!b)return false;
    unsigned phase=b->fixed_phase;
    if(b->factor) {
        if(!(b->factor>>8))return false;
        phase+=(Project(b->factor,x)-Project(b->factor,m->source_camera_x));
    } else {
        phase+=(unsigned)((x-(int)m->source_camera_x)*m->delta_scale);
    }
    *out=(uint16_t)(((phase&65535u)>>4)&1023u);return true;
}

bool IogRasterParallaxPrepare(const uint8_t *rom,size_t size,bool verified,
    const uint8_t *ram,size_t ram_size,const uint16_t *captured,size_t lines,
    IogRasterParallax *out)
{
    if(!rom || size!=2097152 || !verified || !ram || ram_size<65536 ||
       !captured || lines!=kIogRasterParallaxLines || !out ||
       Overlap(out,sizeof(*out),rom,size) || Overlap(out,sizeof(*out),ram,ram_size) ||
       Overlap(out,sizeof(*out),captured,lines*sizeof(*captured)))return false;
    unsigned scene=Word(ram,0x644);
    if((scene!=0x15 && scene!=0x1A && scene!=0x1C) ||
       (ram[0x6EE]&128) || (ram[0x6EF]&8) ||
       Word(ram,0x694)!=512 || Word(ram,0x698)!=256 || Word(ram,0x690)!=0 ||
       Word(ram,0x68A)>2048)return false;
    /* Profile-qualified Original table address, index01. Values and band
     * records remain ROM inputs. Descriptor bank7E/registerBG2HOFS/stride8
     * establishes the producer contract; swapped sources are not handled. */
    unsigned pointer=Word(rom,0x1CC00+2);
    if(pointer<0x8000 || pointer>0xFFF0)return false;
    size_t at=0x10000u+pointer;
    unsigned config=rom[at+3],buffer=Word(rom,at);
    if(buffer>0xF800 || rom[at+2]!=0x7E || (config&63)!=0x0F ||
       (config&128) || rom[at+4]!=8)return false;
    IogRasterParallax base={0};
    base.scene=(uint16_t)scene;base.source_camera_x=(uint16_t)Word(ram,0x68A);
    base.width=512;base.height=256;base.delta_scale=(uint8_t)(config&64?16:1);
    unsigned rows=0;at+=5;
    uint16_t accumulators[kIogRasterParallaxBands],speeds[kIogRasterParallaxBands];
    for(unsigned i=0;i<kIogRasterParallaxBands;i++,at+=8) {
        if(at+8>0x20000u)return false;
        unsigned height=Word(rom,at);
        if(!height)break;
        if(!(height&32768u))return false;
        height=65536u-height;
        unsigned accumulator=Word(rom,at+2),factor=Word(rom,at+4),speed=Word(rom,at+6);
        if(!height || height>1024 || rows+height>2048 ||
           accumulator<0x720 || accumulator>0x75E || (accumulator&1) ||
           (factor && (!(factor>>8) ||
            (factor&255u)*base.source_camera_x>65535u)))return false;
        IogRasterParallaxBand *b=&base.bands[i];
        b->first_row=(uint16_t)rows;b->end_row=(uint16_t)(rows+height);
        b->factor=(uint16_t)factor;b->fixed_phase=(uint16_t)Word(ram,accumulator);
        if(factor && b->fixed_phase!=((Project(factor,base.source_camera_x)+speed)&65535u))return false;
        accumulators[i]=(uint16_t)accumulator;speeds[i]=(uint16_t)speed;
        rows+=height;base.band_count++;
        /* The original emitter stops when the visible budget is exhausted;
         * a sufficiently tall final record need not have a zero terminator.
         * Stop inside this finite256-row plane, not the next descriptor. */
        if(rows>=256)break;
    }
    if(rows<256 || !base.band_count)return false;
    /* Recover the previous accumulator BEFORE reducing its fractional bits.
     * The descriptor's auto velocity and the captured frame's camera delta
     * distinguish the double-buffer phase. Require all225 actual rows. */
    unsigned matches=0;IogRasterParallax chosen={0};
    for(unsigned previous=0;previous<2;previous++) {
        IogRasterParallax trial=base;trial.previous_buffer=(uint8_t)previous;trial.valid=1;
        int old_x=(int)base.source_camera_x-Signed(Word(ram,0x6E4));
        bool ok=true;
        for(unsigned i=0;i<trial.band_count;i++) {
            IogRasterParallaxBand *b=&trial.bands[i];
            if(previous) {
                if(b->factor) {
                    if(old_x<0 || (b->factor&255u)*(unsigned)old_x>65535u){ok=false;break;}
                    b->fixed_phase=(uint16_t)(Project(b->factor,old_x)+speeds[i]);
                } else {
                    unsigned delta=Word(ram,0x6E4)*base.delta_scale;
                    b->fixed_phase=(uint16_t)(Word(ram,accumulators[i])-speeds[i]-delta);
                }
            }
        }
        for(unsigned line=0;line<lines && ok;line++) {
            uint16_t h;
            if(!IogRasterParallaxSample(&trial,(int)(line<224?line:223),
                base.source_camera_x,&h) || h!=(captured[line]&1023u))ok=false;
        }
        if(ok){chosen=trial;matches++;}
    }
    if(matches!=1)return false;
    *out=chosen;return true;
}
