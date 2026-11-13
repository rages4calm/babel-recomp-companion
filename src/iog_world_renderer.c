/* Original-USA host picture reconstruction. The original 256x224 guest
 * simulation, visibility flags, candidate lists and camera remain authoritative.
 * This adapter observes composition and actual OAM publication, then draws
 * independent, bounded pictures. It never runs CPU/HDMA/IRQ a second time.
 * Unsupported formats keep the authentic field available. */
#include "iog_world_renderer.h"
#include "iog_visual_objects.h"
#include "iog_world_view.h"
#include "iog_world_pixels.h"
#include "iog_scene_view.h"
#include "iog_randomizer.h"
#include "common_cpu_infra.h"
#include "common_rtl.h"
#include "snes/cart.h"
#include "snes/snes.h"
#include "snes/ppu.h"
#include "snes/interp_bridge.h"
#include "sha256.h"
#include "snesrecomp_rom_identity.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { MaxWidth=2048, MaxHeight=512, Epochs=16, Chunk=224 };
typedef struct PictureEpoch {
    uint16_t vram[32768], cgram[256];
    uint8_t ram[65536];
    uint32_t vram_writes, oam_writes;
} PictureEpoch;
typedef struct PictureLine {
    uint8_t registers[PPU_SAVESTATE_REGS_SIZE];
    uint8_t epoch;
} PictureLine;
static struct {
    bool initialized, enabled, stock, pending, composed, active, complete, valid;
    bool copy_reference;
    bool source_packet;
    int width, height, extent_quarters, epoch_count;
    unsigned frame;
    unsigned simulation_ticks, presentation_calls;
    uint64_t compose_sequence, publish_sequence;
    uint32_t nmi_oam_writes;
    uint8_t pending_ram[131072], active_ram[131072], staging[544];
    Ppu base, detached;
    PictureEpoch epochs[Epochs];
    PictureLine lines[225];
    IogVisualFrame visual;
    IogWorldView view;
    PpuExtraObject objects[kIogVisualMaxParts];
    uint16_t object_rows[kIogVisualMaxParts][16];
    uint32_t output[MaxWidth*MaxHeight], row[256], hud[256*224];
    FILE *audit;
    bool output_written;
    const char *reason;
} s;

static unsigned Word(const uint8_t *ram, unsigned at)
{ return ram[at] | ((unsigned)ram[at+1] << 8); }
static int Clamp(int v,int low,int high) { return v<low?low:v>high?high:v; }
static bool ActiveWorldWindow(const Ppu *p)
{
    const unsigned layers[]={0,1,4};
    for(unsigned i=0;i<sizeof(layers)/sizeof(layers[0]);i++) {
        unsigned layer=layers[i];
        if(((p->screenWindowed[0]|p->screenWindowed[1])&(1u<<layer)) &&
           ((p->windowsel>>(layer*4))&10u)) return true;
    }
    return false;
}
static int ScrollWorld(const uint8_t *ram,unsigned at,unsigned scroll)
{
    int base=(int16_t)Word(ram,at), result=(base&~1023)|(int)(scroll&1023);
    if(result-base>512) result-=1024;
    if(base-result>512) result+=1024;
    return result;
}

bool IogWorldEnabled(void)
{
    if(!s.initialized) {
        s.initialized=true;
        const char *mode=getenv("IOG_WORLD_RENDERER");
        s.enabled=mode && !strcmp(mode,"1");
        const char *reference=getenv("IOG_WORLD_REFERENCE_PIXELS");
        s.copy_reference=reference && !strcmp(reference,"1");
        const char *packet=getenv("IOG_WORLD_SOURCE_PACKET");
        s.source_packet=packet && !strcmp(packet,"1");
        s.extent_quarters=6;
        const char *extent=getenv("IOG_WORLD_VIEW_EXTENT");
        if(extent && !strcmp(extent,"1")) s.extent_quarters=4;
        else if(extent && !strcmp(extent,"1.25")) s.extent_quarters=5;
        const char *path=getenv("IOG_RENDERER_AUDIT");
        if(path && *path) s.audit=fopen(path,"wb");
    }
    return s.enabled;
}

void IogWorldSimulationTick(void) { ++s.simulation_ticks; }

void IogWorldInitialize(void)
{
    if(!IogWorldEnabled()) return;
    s.stock=false;
    IogWorldReset();
    const Cart *cart=g_snes?g_snes->cart:NULL;
    if(!cart || cart->type!=CART_HIROM || cart->romImageSize!=2097152 ||
       cart->romSize<cart->romImageSize) return;
    uint8_t digest[32]; char hex[65];
    sha256_compute(cart->rom,cart->romImageSize,digest);
    for(unsigned i=0;i<32;i++) snprintf(hex+i*2,3,"%02x",digest[i]);
    s.stock=!strcmp(hex,SNESRECOMP_ROM_EXPECTED_SHA256);
}

void IogWorldReset(void)
{
    s.pending=s.composed=s.active=s.complete=s.valid=false;
    s.reason="reset_or_unpaired_upload";
    s.epoch_count=0;
    memset(&s.view,0,sizeof(s.view));
}

void IogWorldGeometry(int dw,int dh,int *w,int *h)
{
    if(!IogWorldEnabled() || !w || !h) return;
    int height=224*s.extent_quarters/4;
    double aspect=dw>0&&dh>0?(double)dw/dh:16.0/9;
    /* Finite output budget; use letterboxing, never unequal pixel scaling. */
    if(aspect<256.0/224) aspect=256.0/224;
    if(aspect>32.0/9) aspect=32.0/9;
    int width=(int)(height*aspect/2+0.5)*2;
    s.width=*w=Clamp(width,256,MaxWidth);
    s.height=*h=Clamp(height,224,MaxHeight);
}

void IogWorldCaptureAtCompose(const CpuState *cpu,uint32_t pc)
{
    (void)pc;
    if(!s.enabled || !s.stock || !cpu || !cpu->ram || IogRandomizerActive()) return;
    memcpy(s.pending_ram,cpu->ram,sizeof(s.pending_ram));
    s.pending=true; s.composed=false;
    ++s.compose_sequence;
}
void IogWorldCaptureAfterCompose(const CpuState *cpu,uint32_t pc)
{
    (void)pc;
    if(!s.enabled || !s.pending || !cpu || !cpu->ram) return;
    memcpy(s.staging,cpu->ram+0x422,sizeof(s.staging));
    s.composed=true;
}
void IogWorldBeforeNmi(void)
{ if(s.enabled && g_ppu) s.nmi_oam_writes=g_ppu->oamWriteCount; }
void IogWorldAfterNmi(void)
{
    if(!s.enabled || !g_ppu || g_ppu->oamWriteCount==s.nmi_oam_writes) return;
    bool match=s.composed && s.pending;
    for(unsigned i=0;i<256 && match;i++)
        match=g_ppu->oam[i]==Word(s.staging,i*2);
    if(match) match=!memcmp(g_ppu->highOam,s.staging+512,32);
    if(match) {
        memcpy(s.active_ram,s.pending_ram,sizeof(s.active_ram));
        s.active=true; s.publish_sequence=s.compose_sequence;
    } else {
        s.active=false; s.reason="unpaired_oam_upload";
    }
}

void IogWorldBeginRaster(void)
{
    if(!s.enabled || !g_ppu || !g_snes) return;
    s.complete=false; s.valid=false; s.epoch_count=0;
    memset(&s.view,0,sizeof(s.view));
    s.reason="unsupported_scene_or_layout";
    memset(s.hud,0,sizeof(s.hud));
    /* The live field is unchanged. Extraction records the real BG3 pixels. */
    PpuBindOverlaySurface(g_ppu,kPpuOverlaySource_Bg3,(uint8_t*)s.hud,256*4);
    PpuSetOverlayCapture(g_ppu,kPpuOverlaySource_Bg3,0,0,256,224,0);
    if(!s.stock || IogRandomizerActive() || !s.active) return;
    IogSceneViewSource source;
    IogSceneViewReadWorldSource(g_snes->ram,131072,g_ppu,false,&source);
    if(source.gate!=kIogSceneViewReady || source.scene!=Word(s.active_ram,0x644)) return;
    if(PPU_objInterlace(g_ppu) || g_ppu->frameInterlace ||
       (g_ppu->mosaic>>4)!=0 || ActiveWorldWindow(g_ppu)) return;
    s.base=*g_ppu;
    s.valid=true; s.reason="awaiting_picture";
}

void IogWorldCaptureLine(int line)
{
    if(!s.enabled || !s.valid || line<0 || line>224) return;
    if((g_ppu->bgmode&7)!=1 || g_ppu->frameInterlace || (g_ppu->mosaic>>4)!=0 ||
       ActiveWorldWindow(g_ppu)) {
        s.valid=false; s.reason="unsupported_line_effect"; return;
    }
    PictureEpoch *prior=s.epoch_count?&s.epochs[s.epoch_count-1]:NULL;
    if(prior && prior->oam_writes!=g_ppu->oamWriteCount) {
        s.valid=false; s.reason="mid_raster_oam_upload"; return;
    }
    /* Metadata, definitions and maps can change at a real raster IRQ. Record
     * only changed epochs; line register input is always captured separately. */
    bool changed=!prior || prior->vram_writes!=g_ppu->vramWriteCount ||
        memcmp(prior->cgram,g_ppu->cgram,sizeof(prior->cgram)) ||
        memcmp(prior->ram+0x644,g_snes->ram+0x644,0xBE) ||
        memcmp(prior->ram+0x2000,g_snes->ram+0x2000,0x1000) ||
        memcmp(prior->ram+0xA000,g_snes->ram+0xA000,0x6000);
    if(changed) {
        if(s.epoch_count==Epochs) {s.valid=false;s.reason="picture_epoch_capacity";return;}
        PictureEpoch *next=&s.epochs[s.epoch_count++];
        memcpy(next->vram,g_ppu->vram,sizeof(next->vram));
        memcpy(next->cgram,g_ppu->cgram,sizeof(next->cgram));
        memcpy(next->ram,g_snes->ram,sizeof(next->ram));
        next->vram_writes=g_ppu->vramWriteCount; next->oam_writes=g_ppu->oamWriteCount;
    }
    memcpy(s.lines[line].registers,g_ppu,PPU_SAVESTATE_REGS_SIZE);
    s.lines[line].epoch=(uint8_t)(s.epoch_count-1);
}

static unsigned MapTile(const PictureEpoch *e,int logical,int x,int y)
{
    const uint8_t *ram=e->ram; unsigned off=logical*2;
    unsigned w=Word(ram,0x692+off),h=Word(ram,0x696+off);
    if(x<0 || y<0 || x>=(int)w || y>=(int)h) return 0xFFFFFFFFu;
    unsigned map=Word(ram,0x69E + off),defs=Word(ram,0x6AE + off);
    unsigned address=map+(((y>>8)*(w>>8)+(x>>8))<<8)+(((y>>4)&15)<<4)+((x>>4)&15);
    if(address>=65536 || defs+ram[address]*8+7>=65536) return 0xFFFFFFFFu;
    return Word(ram,defs+ram[address]*8+((y>>3)&1)*4+((x>>3)&1)*2);
}

/* Original scene08 contains a real 512x256 room, including the east hall and
 * town stairs. Its second 512x512 layer also contains spare material below
 * that room; those cells are not additional scenery. Stock primary metatile
 * 6E is the uniform gray void outside its walls. Admit only the captured
 * layout/definition, then make that void black without moving a wall, seat,
 * actor, collision rectangle or native door. Unknown layouts keep fallback. */
static bool OriginalClassroomLayout(const PictureEpoch *e)
{
    const uint8_t *ram=e->ram;
    if(Word(ram,0x692)!=512 || Word(ram,0x696)!=256 ||
       Word(ram,0x694)!=512 || Word(ram,0x698)!=512 ||
       Word(ram,0x69E)!=0xA000 || Word(ram,0x6AE)!=0x2000) return false;
    for(unsigned n=0;n<4;n++)
        if(Word(ram,0x2000+0x6E*8+n*2)!=0x1C01) return false;
    return true;
}

static bool OriginalClassroomPixel(const PictureEpoch *e,int x,int y)
{
    if(x<0 || x>=512 || y<0 || y>=256) return false;
    /* Match the hardware BG sampling line: output world row0 samples row1.
     * This masks only original void cells, not any pixels of adjacent walls. */
    unsigned sy=(unsigned)y+1;
    if(sy>=256) return false;
    unsigned address=0xA000+(((unsigned)x>>8)<<8)+
        ((sy>>4)<<4)+(((unsigned)x>>4)&15);
    return e->ram[address]!=0x6E;
}

static void Detach(Ppu *p)
{
    p->renderBuffer=(uint8_t*)s.row; p->renderPitch=256*4;
    p->renderVram=NULL; p->hdLookup=NULL;p->hdCtx=NULL;p->hdFrame=NULL;
    p->hdCapture=NULL;p->hiresBuffer=NULL;p->hdEmissive=NULL;
    p->widescreenLineEnhancer=NULL;p->widescreenLineEnhancerContext=NULL;
    p->extraObjects=NULL;p->extraObjectCount=0;
    p->renderFlags=0;
    PpuClearOverlayBindings(p);PpuClearOverlayCaptures(p);
    PpuSetExtraSpace(p,0);
    PpuSetWidescreenHudSplit(p,0,0,0);
    for(unsigned i=0;i<256;i+=2) p->oam[i]=0xF000;
    memset(p->highOam,0,sizeof(p->highOam));
    p->wsOamFullXOn=0;p->wsOamMotionGraceOn=0;
}

static bool RenderWorld(void)
{
    if(!s.valid || !s.epoch_count || s.width<256 || s.height<224) return false;
    PictureEpoch *first=&s.epochs[s.lines[1].epoch];
    bool classroom=Word(s.active_ram,0x644)==0x08;
    if(classroom) for(int n=0;n<s.epoch_count;n++)
        if(!OriginalClassroomLayout(&s.epochs[n])) {
            s.reason="unsupported_classroom_layout";return false;
        }
    for(int n=0;n<s.epoch_count;n++) if(memcmp(first->vram,s.epochs[n].vram,sizeof(first->vram))) {
        s.reason="mid_raster_character_upload";return false;
    }
    Ppu *p=&s.detached;
    *p=s.base;memcpy(p,s.lines[1].registers,PPU_SAVESTATE_REGS_SIZE);
    int physical=(s.active_ram[0x6EE]>>7)&1;
    int camera_x=ScrollWorld(s.active_ram,0x68A,p->hScroll[physical]);
    int camera_y=ScrollWorld(s.active_ram,0x68E,p->vScroll[physical]);
    if(camera_x!=(int16_t)Word(s.active_ram,0x68A) ||
       camera_y!=(int16_t)Word(s.active_ram,0x68E)) {
        s.reason="camera_publication_mismatch";return false;
    }
    if(!IogWorldViewCompute(camera_x,camera_y,Word(first->ram,0x692),
            Word(first->ram,0x696),(uint16_t)s.width,(uint16_t)s.height,&s.view)) {
        s.reason="invalid_world_view";return false;
    }
    int left=s.view.native_x,top=s.view.native_y;
    IogVisualViewport viewport={s.view.world_x,s.view.world_y,
        s.view.width,s.view.height};
    s.detached=s.base;
    memcpy(s.detached.vram,first->vram,sizeof(first->vram));
    memcpy(s.detached.cgram,first->cgram,sizeof(first->cgram));
    IogVisualSource source={s.active_ram,sizeof(s.active_ram),g_snes->cart->rom,
        g_snes->cart->romImageSize,&s.detached,true};
    if(IogVisualObjectsBuild(&source,&viewport,&s.visual)!=kIogVisualReady) {
        s.reason="unsupported_visual_object";return false;
    }
    *p=s.base;Detach(p);
    memcpy(p->vram,first->vram,sizeof(p->vram));
    int blank[2]={-1,-1};
    for(int logical=0;logical<2;logical++) {
        int physical=logical^((first->ram[0x6EE]>>7)&1);
        unsigned base=PPU_bgTileAdr(p,physical);
        for(unsigned tile=0;tile<1024;tile++) {
            unsigned n=0;for(;n<16;n++) if(first->vram[(base+tile*16+n)&32767]) break;
            if(n==16) {blank[logical]=(int)tile;break;}
        }
        if(blank[logical]<0) {s.reason="no_verified_transparent_character";return false;}
    }
    memset(s.output,0,(size_t)s.width*s.height*4);
    for(int row=0;row<s.height;row++) {
        int native_y=row-top;
        PictureLine *line=&s.lines[Clamp(native_y,0,223)+1];
        PictureEpoch *e=&s.epochs[line->epoch];
        /* Objects were decoded from the exact composition/OAM publication
         * pair. Recolor the one visible row with this raster's palette. */
        size_t count=0;
        for(unsigned i=0;i<s.visual.part_count;i++) {
            const IogVisualPart *part=&s.visual.parts[i];
            int py=row-part->y;
            if(py<0 || py>=part->height) continue;
            uint16_t *pixels=s.object_rows[count];
            for(int x=0;x<part->width;x++) {
                unsigned index=part->indices[py*part->width+x];
                pixels[x]=index?(uint16_t)(0x8000|e->cgram[index]):0;
            }
            s.objects[count++]=(PpuExtraObject){part->x,0,part->width,1,
                part->width,part->priority,part->math,0,part->order+1,pixels};
        }
        for(int start=0;start<s.width;start+=Chunk) {
            int width=Clamp(s.width-start,0,Chunk);
            unsigned dirty[64],dirty_count=0;
            memcpy(p,line->registers,PPU_SAVESTATE_REGS_SIZE);
            uint16_t source_hscroll[2]={p->hScroll[0],p->hScroll[1]};
            uint16_t source_vscroll[2]={p->vScroll[0],p->vScroll[1]};
            if(s.copy_reference) memcpy(p->vram,e->vram,sizeof(p->vram));
            memcpy(p->cgram,e->cgram,sizeof(p->cgram));
            p->screenEnabled[0]&=~4;p->screenEnabled[1]&=~4;
            for(int logical=0;logical<2;logical++) {
                int physical=logical^((e->ram[0x6EE]>>7)&1);
                int camx=ScrollWorld(e->ram,0x68A+logical*2,p->hScroll[physical]);
                int camy=ScrollWorld(e->ram,0x68E + logical*2,p->vScroll[physical]);
                int wx=camx-left+start,wy=camy+native_y;
                p->hScroll[physical]=(uint16_t)wx&1023;
                p->vScroll[physical]=(uint16_t)wy&1023;
                for(int x=wx&~7;x<wx+width;x+=8) {
                    /* BG sampling uses hardware line1 while OBJ evaluation
                     * uses line0 for the same first output row. */
                    unsigned tile=MapTile(e,logical,x,wy+1);
                    if(tile==0xFFFFFFFFu) tile=(unsigned)blank[logical];
                    /* Overlapping authentic cells use the actual uploaded
                     * VRAM entry, including partially updated scroll strips. */
                    if(native_y>=0&&native_y<224 && x+8>camx && x<camx+256) {
                        unsigned tx=((unsigned)source_hscroll[physical]+(x-camx))>>3;
                        unsigned ty=((unsigned)source_vscroll[physical]+native_y+1)>>3;
                        unsigned address=PPU_bgTilemapAdr(p,physical)+((ty&31)<<5)+(tx&31);
                        if(PPU_bgTilemapWider(p,physical)&&(tx&32)) address+=0x400;
                        tile=e->vram[address&32767];
                    }
                    unsigned tx=((unsigned)x&1023)>>3,ty=((unsigned)(wy+1)&1023)>>3;
                    unsigned address=PPU_bgTilemapAdr(p,physical)+((ty&31)<<5)+(tx&31);
                    if(PPU_bgTilemapWider(p,physical)&&(tx&32)) address+=0x400;
                    address&=32767;
                    if(dirty_count==sizeof(dirty)/sizeof(dirty[0])) {
                        s.reason="tile_patch_capacity";return false;
                    }
                    dirty[dirty_count++]=address;
                    p->vram[address]=(uint16_t)tile;
                }
            }
            for(size_t i=0;i<count;i++) s.objects[i].x-=start;
            PpuSetExtraObjects(p,s.objects,count);
            IogWorldPixelsDrawLine(p,0);IogWorldPixelsDrawLine(p,1);
            /* Only tilemap entries were changed on the owned picture. All
             * epochs have identical VRAM (checked above), so restoring these
             * bounded cells replaces a full64KB copy for every chunk/row. */
            for(unsigned n=0;n<dirty_count;n++)
                p->vram[dirty[n]]=first->vram[dirty[n]];
            for(size_t i=0;i<count;i++) s.objects[i].x+=start;
            for(int x=0;x<width;x++) {
                int worldx=viewport.world_x+start+x,worldy=viewport.world_y+row;
                bool native_pixel=native_y>=0&&native_y<224&&
                    start+x>=left&&start+x<left+256;
                /* Preserve the actual uploaded tilemap cells across the
                 * whole authoritative field during shake. This may include
                 * a hardware-wrapped edge; expanded outside-map space is
                 * still padding, never guessed or repeated terrain. */
                if(classroom?OriginalClassroomPixel(e,worldx,worldy):
                   (native_pixel||(worldx>=0&&worldx<(int)Word(e->ram,0x692)&&
                   worldy>=0&&worldy<(int)Word(e->ram,0x696))))
                    s.output[row*s.width+start+x]=s.row[x];
            }
        }
    }
    /* Keep HUD physical size while the world camera shows a larger extent.
     * It is an independently extracted original UI plane, not world terrain. */
    int hudw=256*s.height/224,hudx=(s.width-hudw)/2;
    for(int y=0;y<s.height;y++) for(int x=0;x<hudw;x++) {
        uint32_t color=s.hud[(y*224/s.height)*256+x*256/hudw];
        if((color>>24) && x+hudx>=0 && x+hudx<s.width)
            s.output[y*s.width+x+hudx]=color;
    }
    s.reason="ready";return true;
}

void IogWorldEndRaster(uint32_t resume_pc,unsigned hdma_lines,unsigned irq_count)
{
    if(!s.enabled && !s.audit) return;
    ++s.frame;s.complete=s.enabled && RenderWorld();
    if(!s.enabled) {s.reason="reference_renderer";s.width=256;s.height=224;}
    if(s.audit) {
        const CpuState *c=&g_cpu;
        fprintf(s.audit,"{\"frame\":%u,\"resume_pc\":%u,\"A\":%u,\"X\":%u,\"Y\":%u,\"S\":%u,\"D\":%u,\"DB\":%u,\"PB\":%u,\"P\":%u,\"E\":%u,\"M\":%u,\"IX\":%u,\"N\":%u,\"V\":%u,\"Z\":%u,\"C\":%u,\"I\":%u,\"DF\":%u,\"cycles\":%llu,\"master_cycles\":%llu,\"hdma_lines\":%u,\"irq_count\":%u,\"simulation_width\":256,\"simulation_height\":224,\"width\":%d,\"height\":%d,\"compose\":%llu,\"publish\":%llu,\"epochs\":%d,\"parts\":%u,\"ready\":%s,\"reason\":\"%s\"}\n",
            s.frame,resume_pc,c->A,c->X,c->Y,c->S,c->D,c->DB,c->PB,c->P,
            c->emulation,c->m_flag,c->x_flag,c->_flag_N,c->_flag_V,c->_flag_Z,
            c->_flag_C,c->_flag_I,c->_flag_D,(unsigned long long)c->cycles,
            (unsigned long long)c->master_cycles,hdma_lines,irq_count,s.width,s.height,
            (unsigned long long)s.compose_sequence,(unsigned long long)s.publish_sequence,
            s.epoch_count,s.complete?s.visual.part_count:0,s.complete?"true":"false",s.reason?s.reason:"uninitialized");
        /* Raw operand values make accidental widened gameplay policy visible
         * in every frame, instead of trusting a configuration label. */
        static const unsigned sites[]={0x3C617,0x3C61A,0x3C62A,0x3C62D,0x3C729,
            0x3C8E5,0x3C8EA,0x3C9C2,0x3C9C7,0x3C7BE};
        /* A second JSON record is explicitly typed and shares frame identity. */
        fprintf(s.audit,"{\"kind\":\"policy\",\"frame\":%u,\"simulation_ticks\":%u,\"draw_calls\":%u,\"presentation_calls\":%u,\"cull_operands\":[",s.frame,s.simulation_ticks,s.frame,s.presentation_calls);
        for(unsigned i=0;i<sizeof(sites)/sizeof(sites[0]);i++)
            fprintf(s.audit,"%s%u",i?",":"",Word(g_snes->cart->rom,sites[i]));
        fprintf(s.audit,"],\"world_view\":[%d,%d,%u,%u,%u,%u,%u,%u,%u,%u]}\n",
            s.view.world_x,s.view.world_y,s.view.width,s.view.height,
            s.view.native_x,s.view.native_y,s.view.padding_left,
            s.view.padding_right,s.view.padding_top,s.view.padding_bottom);
        fflush(s.audit);
    }
}

/* Explicit private diagnostic export at the same completed picture boundary.
 * No guest code runs and no live picture input is reread. The bounded packet
 * lets independent tools inspect the actual published actor phase, HUD and
 * per-line memory epochs instead of joining an unrelated end-of-logic dump. */
static bool PacketFile(const char *base,const char *suffix,const void *data,size_t size)
{
    char path[4096];int n=snprintf(path,sizeof(path),"%s%s",base,suffix);
    if(n<0 || (size_t)n>=sizeof(path)) return false;
    FILE *file=fopen(path,"wb");if(!file) return false;
    bool ok=fwrite(data,1,size,file)==size;if(fclose(file)) ok=false;
    return ok;
}

static bool ExportSourcePacket(const char *base,const uint8_t *field)
{
    const uint16_t endian=1;
    if(!s.valid || !s.active || !s.epoch_count || *(const uint8_t*)&endian!=1) return false;
    bool ok=PacketFile(base,".active.wram.bin",s.active_ram,sizeof(s.active_ram));
    ok=PacketFile(base,".hud.bgra",s.hud,sizeof(s.hud)) && ok;
    ok=PacketFile(base,".field.bgra",field,256*224*4) && ok;
    uint8_t oam[544];memcpy(oam,s.base.oam,512);memcpy(oam+512,s.base.highOam,32);
    ok=PacketFile(base,".published.oam.bin",oam,sizeof(oam)) && ok;
    char path[4096];int length=snprintf(path,sizeof(path),"%s.epochs.bin",base);
    if(length<0 || (size_t)length>=sizeof(path)) return false;
    FILE *file=fopen(path,"wb");if(!file) return false;
    for(int n=0;n<s.epoch_count;n++) {
        const PictureEpoch *e=&s.epochs[n];
        if(fwrite(e->vram,1,sizeof(e->vram),file)!=sizeof(e->vram) ||
           fwrite(e->cgram,1,sizeof(e->cgram),file)!=sizeof(e->cgram) ||
           fwrite(e->ram,1,sizeof(e->ram),file)!=sizeof(e->ram)) {ok=false;break;}
    }
    if(fclose(file)) ok=false;
    length=snprintf(path,sizeof(path),"%s.source.json",base);
    if(length<0 || (size_t)length>=sizeof(path)) return false;
    file=fopen(path,"wb");if(!file) return false;
    if(fprintf(file,"{\"schema\":\"iog-world-source-v1\",\"frame\":%u,\"scene\":%u,\"ready\":%s,\"reason\":\"%s\",\"width\":%d,\"height\":%d,\"world_x\":%d,\"world_y\":%d,\"native_x\":%u,\"native_y\":%u,\"compose\":%llu,\"publish\":%llu,\"epochs\":%d,\"epoch_bytes\":131584,\"epoch_layout\":\"VRAM65536-CGRAM512-WRAM65536-LE\",\"even_frame\":%s,\"mosaic_start_line\":%u,\"frame_interlace\":%s,\"lines\":[",
        s.frame,Word(s.active_ram,0x644),s.complete?"true":"false",s.reason?s.reason:"unknown",s.width,s.height,s.view.world_x,s.view.world_y,
        s.view.native_x,s.view.native_y,(unsigned long long)s.compose_sequence,
        (unsigned long long)s.publish_sequence,s.epoch_count,s.base.evenFrame?"true":"false",
        s.base.mosaicStartLine,s.base.frameInterlace?"true":"false")<0) ok=false;
    for(int line=0;line<=224;line++) {
        if(fprintf(file,"%s{\"epoch\":%u,\"regs\":\"",line?",":"",s.lines[line].epoch)<0) ok=false;
        for(unsigned n=0;n<PPU_SAVESTATE_REGS_SIZE;n++)
            if(fprintf(file,"%02x",s.lines[line].registers[n])<0) ok=false;
        if(fprintf(file,"\"}")<0) ok=false;
    }
    if(fprintf(file,"],\"complete\":%s}\n",ok?"true":"false")<0) ok=false;
    if(fclose(file)) ok=false;
    return ok;
}

int IogWorldDraw(uint8_t *dst,size_t pitch,const uint8_t *field,int width,int height,double alpha)
{
    if(!s.enabled) return 0;
    ++s.presentation_calls;
    if(!dst||!field||width<256||width>MaxWidth||height<224||height>MaxHeight||
       pitch<(size_t)width*4||!isfinite(alpha)||alpha<0||alpha>1) return 0;
    if(s.complete && width==s.width && height==s.height) {
        for(int y=0;y<height;y++) memcpy(dst+y*pitch,s.output+y*width,width*4);
    } else {
        for(int y=0;y<height;y++) memset(dst+y*pitch,0,width*4);
        /* Unsupported scenes preserve the original field at a uniform scale. */
        int scaledw=256*height/224,left=(width-scaledw)/2;
        for(int y=0;y<height;y++) for(int x=0;x<scaledw;x++) {
            if(x+left>=0&&x+left<width) memcpy(dst+y*pitch+(x+left)*4,
                field+((y*224/height)*256+x*256/scaledw)*4,4);
        }
    }
    const char *output=getenv("IOG_WORLD_OUTPUT");
    const char *frame=getenv("IOG_WORLD_OUTPUT_FRAME");
    if(!s.output_written && output && *output && frame && *frame) {
        char *end=NULL;unsigned long wanted=strtoul(frame,&end,10);
        if(end && !*end && wanted==s.frame) {
            FILE *file=fopen(output,"wb");
            if(file) {
                bool ok=fprintf(file,"P6\n%d %d\n255\n",width,height)>0;
                for(int y=0;y<height && ok;y++) for(int x=0;x<width;x++) {
                    const uint8_t *color=dst+y*pitch+x*4;
                    const uint8_t rgb[3]={color[2],color[1],color[0]};
                    if(fwrite(rgb,1,3,file)!=3) {ok=false;break;}
                }
                if(fclose(file)) ok=false;
                s.output_written=ok;
                if(ok && s.source_packet) {
                    bool packet=ExportSourcePacket(output,field);
                    if(s.audit) fprintf(s.audit,"{\"kind\":\"source_packet\",\"frame\":%u,\"written\":%s}\n",s.frame,packet?"true":"false");
                }
                if(s.audit) {fprintf(s.audit,"{\"kind\":\"picture\",\"frame\":%u,\"width\":%d,\"height\":%d,\"ready\":%s,\"written\":%s}\n",s.frame,width,height,s.complete?"true":"false",ok?"true":"false");fflush(s.audit);}
            }
        }
    }
    return 1;
}
