/* Received-content Mode7 presentation, host-only and read-only. Preserve Babel,
 * GaiaLabs and existing license/attribution notices. No game assets embedded. */
#include "iog_received_mode7.h"
#include "iog_visual_objects.h"
#include "iog_mode7_plane.h"
#include "iog_mode7_perspective.h"
#include "iog_world_pixels.h"
#include <string.h>

enum { MaxWidth=598,MaxHeight=336 };
static struct {
    bool valid,complete,perspective;
    unsigned lines,vram_writes;
    int width,height;
    const char *reason;
    const uint8_t *rom;
    size_t rom_size;
    IogVisualReceivedIdentity identity;
    Ppu base,source,palette;
    uint8_t parameters[8];
    uint8_t registers[225][PPU_SAVESTATE_REGS_SIZE];
    uint16_t colors[225][256];
    uint32_t output[MaxWidth*MaxHeight],row[256];
    IogMode7PerspectiveParameters producer;
} m;
static unsigned Word(const uint8_t *p,unsigned n)
{return p[n]|(unsigned)p[n+1]<<8;}
static bool Layout(const Ppu *p)
{
    return p && (p->bgmode&7)==7 && !PPU_forcedBlank(p) &&
        !PPU_m7extBg(p) && !p->frameInterlace &&
        !PPU_objInterlace(p) && !(p->mosaic>>4) &&
        (p->screenEnabled[0]&1) && !(p->screenEnabled[0]&~21u) &&
        !p->screenEnabled[1] &&
        !((p->screenWindowed[0]&1)&&(p->windowsel&0xAu)) &&
        !((p->screenWindowed[0]&16)&&(p->windowsel&0xA0000u)) &&
        !(p->windowsel&0xA00000u);
}
static void Detach(Ppu *p)
{
    p->renderBuffer=(uint8_t *)m.row;p->renderPitch=sizeof m.row;
    p->renderVram=NULL;p->hdLookup=NULL;p->hdCtx=NULL;p->hdFrame=NULL;
    p->hdCapture=NULL;p->m7hdBuffer=NULL;p->hdEmissive=NULL;
    p->widescreenLineEnhancer=NULL;p->widescreenLineEnhancerContext=NULL;
    p->extraObjects=NULL;p->extraObjectCount=0;p->renderFlags=0;
    PpuClearOverlayBindings(p);PpuClearOverlayCaptures(p);
    PpuSetExtraSpace(p,0);PpuSetWidescreenHudSplit(p,0,0,0);
    for(unsigned n=0;n<256;n+=2)p->oam[n]=0xf000;
    memset(p->highOam,0,32);p->wsOamFullXOn=p->wsOamMotionGraceOn=0;
}
bool IogReceivedMode7Begin(const Ppu *p,const uint8_t *ram,
    const uint8_t *rom,size_t size,int width,int height)
{
    m.valid=m.complete=m.perspective=false;m.lines=0;
    m.reason="received_mode7_layout";
    if(!ram||!rom||width<384||width>MaxWidth||height<224||height>MaxHeight||!Layout(p))return false;
    if(m.rom!=rom||m.rom_size!=size||!m.identity.rom){
        m.rom=rom;m.rom_size=size;
        if(IogVisualReceivedVerify(rom,size,&m.identity)!=kIogVisualReady){
            m.reason="received_mode7_identity";return false;
        }
    }
    m.base=*p;m.vram_writes=p->vramWriteCount;m.width=width;m.height=height;
    memcpy(m.parameters,ram+0xB6,8);
    /* Exact received producer at physical3F4CD: DB81 indexed trig tables,
     * B8 divisor / B6 increment / BC angle. Full received ROM is identity-bound;
     * all224 generated words and the terminal hold are checked below. */
    unsigned angle=Word(ram,0xBC)&511u;
    m.producer=(IogMode7PerspectiveParameters){(uint16_t)Word(ram,0xB8),
        (uint16_t)Word(ram,0xB6),
        IogMode7PerspectiveSigned(Word(rom,0x1D835+angle*2)),
        IogMode7PerspectiveSigned(Word(rom,0x1D735+angle*2))};
    m.valid=true;m.reason="received_mode7_awaiting_raster";return true;
}
void IogReceivedMode7Capture(const Ppu *p,const uint8_t *ram,int line)
{
    if(!m.valid)return;
    if(line<0||line>224||line!=(int)m.lines||!ram||!Layout(p)||
        p->vramWriteCount!=m.vram_writes||memcmp(m.parameters,ram+0xB6,8)){
        m.valid=false;m.reason="received_mode7_raster_change";return;
    }
    memcpy(m.registers[line],p,PPU_SAVESTATE_REGS_SIZE);
    memcpy(m.colors[line],p->cgram,512);m.lines++;
}
bool IogReceivedMode7End(void)
{
    if(!m.valid||m.lines!=225){m.reason="received_mode7_incomplete";return false;}
    Ppu *source=&m.source,*palette=&m.palette;
    *source=m.base;memcpy(source,m.registers[1],PPU_SAVESTATE_REGS_SIZE);
    int16_t matrix[8];memcpy(matrix,source->m7matrix,sizeof matrix);
    unsigned control=source->m7sel;bool uniform=true,stable=true;
    int16_t captured[224][4];
    for(unsigned line=0;line<=224;line++){
        memcpy(source,m.registers[line],PPU_SAVESTATE_REGS_SIZE);
        if(line<224)memcpy(captured[line],source->m7matrix,sizeof captured[line]);
        if(memcmp(source->m7matrix+4,matrix+4,8)||source->m7sel!=control)stable=false;
        if(line&&(source->m7sel!=control||memcmp(source->m7matrix,matrix,sizeof matrix)))uniform=false;
    }
    m.perspective=stable&&!memcmp(source->m7matrix,captured[223],sizeof captured[223])&&
        IogMode7PerspectiveMatches(&m.producer,captured);
    *palette=m.base;Detach(palette);memset(palette->vram,0,sizeof palette->vram);
    for(unsigned tile=0;tile<32;tile++)palette->vram[tile]=(uint16_t)tile;
    for(unsigned tile=0;tile<32;tile++)for(unsigned x=0;x<8;x++){
        unsigned at=tile*64+8+x;
        palette->vram[at]=(palette->vram[at]&255)|((tile*8+x)<<8);
    }
    int left=(m.width-256)/2,top=(m.height-224)/2;
    uint32_t colors[256];
    for(int row=0;row<m.height;row++){
        int y=row-top+1,line=y<1?1:y>224?224:y;
        if(!uniform&&!m.perspective&&(y<1||y>224)){
            memset(m.output+row*m.width,0,(size_t)m.width*4);continue;
        }
        memcpy(source,m.registers[line],PPU_SAVESTATE_REGS_SIZE);
        memcpy(palette,m.registers[line],PPU_SAVESTATE_REGS_SIZE);
        memcpy(palette->cgram,m.colors[line],512);
        palette->screenEnabled[0]=1;palette->screenEnabled[1]=0;
        palette->screenWindowed[0]=palette->screenWindowed[1]=0;
        memset(palette->m7matrix,0,sizeof palette->m7matrix);
        palette->m7matrix[0]=palette->m7matrix[3]=256;palette->m7sel=0;
        IogWorldPixelsDrawLine(palette,0);IogWorldPixelsDrawLine(palette,1);
        memcpy(colors,m.row,sizeof colors);
        if(m.perspective&&(y<1||y>224)){
            IogMode7PerspectiveStatus status=IogMode7PerspectiveSample(
                &m.producer,y>224?y-1:y,source->m7matrix);
            if(status!=kIogMode7PerspectiveMatrix){
                uint32_t color=status==kIogMode7PerspectiveSky?colors[0]:0;
                for(int x=0;x<m.width;x++)m.output[row*m.width+x]=color;
                continue;
            }
        }
        for(int x=0;x<m.width;x++)
            m.output[row*m.width+x]=colors[IogMode7PlaneIndex(source,x-left,y)];
    }
    m.complete=true;m.reason=m.perspective?"received_mode7_perspective_ready":
        uniform?"received_mode7_plane_ready":"received_mode7_band_ready";
    return true;
}
int IogReceivedMode7Draw(uint8_t *dst,size_t pitch,const uint8_t *field,int w,int h)
{
    if(!m.complete||!dst||!field||w!=m.width||h!=m.height||pitch<(size_t)w*4||
        pitch>SIZE_MAX/(size_t)h)return 0;
    for(int y=0;y<h;y++)memcpy(dst+y*pitch,m.output+y*w,(size_t)w*4);
    /* Keep the actual384 field, including OBJ, UI and exact color composition,
     * at the same pixel scale. Only the surrounding plane is reconstructed. */
    int left=(w-384)/2,top=(h-224)/2;
    for(int y=0;y<224;y++)memcpy(dst+(y+top)*pitch+left*4,
        field+(size_t)y*384*4,384*4);
    return 1;
}
const char *IogReceivedMode7Reason(void){return m.reason;}
bool IogReceivedMode7Perspective(void){return m.complete&&m.perspective;}
