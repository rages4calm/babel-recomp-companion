/* Original-USA host picture reconstruction. The original 256x224 guest
 * simulation, visibility flags, candidate lists and camera remain authoritative.
 * This adapter observes composition and actual OAM publication, then draws
 * independent, bounded pictures. It never runs CPU/HDMA/IRQ a second time.
 * Unsupported formats keep the authentic field available. */
#include "iog_world_renderer.h"
#include "iog_visual_objects.h"
#include "iog_world_view.h"
#include "iog_world_pixels.h"
#include "iog_mode7_plane.h"
#include "iog_mode7_perspective.h"
#include "iog_raster_parallax.h"
#include "iog_scene_view.h"
#include "iog_randomizer.h"
#include "snes_overlay_draw.h"
#include "common_cpu_infra.h"
#include "common_rtl.h"
#include "snes/cart.h"
#include "snes/dma.h"
#include "snes/snes.h"
#include "snes/ppu.h"
#include "snes/ppu_brightness.h"
#include "snes/interp_bridge.h"
#include "sha256.h"
#include "snesrecomp_rom_identity.h"
#include <math.h>
#include <stddef.h>
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
    bool source_packet,mode7,mode7_perspective,absent_secondary,sky_field,stock_actor_field;
    bool hud_layered; /* the status plane was left out of `output` for the presenter */
    bool awaiting_restore,restored_actor_field,fixed_plate;
    int mode7_split;
    IogMode7PerspectiveParameters mode7_parameters;
    int width, height, extent_quarters, epoch_count;
    unsigned frame;
    unsigned simulation_ticks, presentation_calls;
    uint64_t compose_sequence, publish_sequence;
    uint32_t nmi_oam_writes;
    uint8_t pending_ram[131072], active_ram[131072], staging[544];
    /* The last paired upload. A lagging frame can send it again while the
     * next composition is still being built. */
    uint8_t published[544];
    bool published_valid, repeated;
    struct { uint16_t staging, previous; uint8_t composed, pending; } unpaired;
    Ppu base, detached, mode7_source;
    bool mode7_filtered;
    uint32_t mode7_exact[256*224];
    PictureEpoch epochs[Epochs];
    PictureLine lines[225];
    IogVisualFrame visual;
    IogWorldView view;
    /* Part of the last completed wide picture that shows real map, relative
     * to the simulation camera. Zero spans: the stock 256x224 rule applies. */
    struct { int16_t left, top; uint16_t width, height; } wake;
    bool stock_wake;
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

/* Dao's heat effect uses only the first hardware window on BG1. The
 * captured bounds are in native screen coordinates, not map coordinates. */
static bool DaoWorldWindow(const Ppu *p,const uint8_t *ram)
{
    return Word(ram,0x644)==0xc3 && (ram[0x6ee]&0x80) &&
        Word(ram,0x692)==768 && Word(ram,0x696)==512 &&
        Word(ram,0x694)==512 && Word(ram,0x698)==512 && p->windowsel==2;
}

static bool DreamWorldWindow(const Ppu *p,const uint8_t *ram)
{
    return Word(ram,0x644)==0x2A && Word(ram,0x692)==256 &&
        Word(ram,0x696)==1280 && Word(ram,0x694)==512 &&
        Word(ram,0x698)==512 && p->windowsel==0x030033 &&
        p->cgwsel==0x80 && !p->screenEnabled[1];
}

static bool KnownWorldWindow(const Ppu *p,const uint8_t *ram)
{
    return DaoWorldWindow(p,ram) || DreamWorldWindow(p,ram);
}

static bool StockModalPlate(const Ppu *p,const uint8_t *ram)
{
    unsigned scene=Word(ram,0x644);
    if((scene!=0xFD && scene!=0xFF) || Word(ram,0x6EE)!=0x85 ||
       p->bgmode!=9 || p->windowsel || p->frameInterlace ||
       PPU_objInterlace(p) || PPU_forcedBlank(p) || p->bgTileAdr!=0x622 ||
       p->bgXsc[1]!=0x0C || p->bgXsc[2]!=0x78) return false;
    /* Both layouts switch to dedicated source art and a screen-space UI.
     * Reframe the live plate, including its objects and color effects. */
    /* A room that was revealed through a mosaic leaves its two layer bits
     * set with a block size of one pixel, which draws nothing. */
    /* The item page keeps its BG1 map at $0400; the status ("Cond.") page
     * shows the map at $0000 with every other register unchanged. */
    if(scene==0xFF)
        return (!p->mosaic || p->mosaic==3) && (p->bgXsc[0]==0x04 || !p->bgXsc[0]) &&
            p->screenEnabled[0]==0x17 &&
            !p->screenEnabled[1] && p->cgwsel==0x80 && !p->cgadsub &&
            g_snesrecomp_last_hdmaen==6;
    /* The ceremony's exit mosaics both scenery backgrounds before return. */
    return (!p->mosaic || (p->mosaic&15)==3) &&
        p->bgXsc[0]==0x08 && p->screenEnabled[0]==0x13 &&
        p->screenEnabled[1]==0x11 && p->cgwsel==0x82 && p->cgadsub==2 &&
        g_snesrecomp_last_hdmaen==2;
}

static bool StockEndingPlate(const Ppu *p,const uint8_t *ram)
{
    unsigned scene=Word(ram,0x644);
    if(p->bgmode!=9 || p->mosaic || p->frameInterlace || PPU_objInterlace(p) ||
       PPU_forcedBlank(p) || p->bgTileAdr!=0x622 || p->bgXsc[0]!=0x11)
        return false;
    switch(scene) {
    case 0x89: /* New Babel skyline */
        return Word(ram,0x6EE)==5 && !p->windowsel && p->bgXsc[1]==0x19 &&
            p->bgXsc[2]==0x78 && p->screenEnabled[0]==0x11 &&
            p->screenEnabled[1]==4 && p->cgwsel==0x82 && p->cgadsub==1;
    case 0x90: /* Changed World map and its subtitle */
        return Word(ram,0x6EE)==1 && !p->windowsel && p->bgXsc[1]==0x18 &&
            p->bgXsc[2]==0x78 && p->screenEnabled[0]==0x17 &&
            p->screenEnabled[1]==2 && p->cgwsel==2 && p->cgadsub==0x41;
    case 0xF7:
        /* The credits script changes the BG3 size, masks and color math as
         * the staff panels, characters and scenery enter. The live PPU
         * already combines those layers within a fixed screen-space plate. */
        return Word(ram,0x6EE)==0x0401 && p->windowsel==0x33 &&
            p->bgXsc[1]==0x18 && p->bgXsc[2]>=0x78 && p->bgXsc[2]<=0x7A &&
            !(p->screenEnabled[0]&~0x17u) && !(p->screenEnabled[1]&~2u) &&
            p->cgwsel==2 && (p->cgadsub==0x83 || p->cgadsub==0x41 || p->cgadsub==1);
    default:
        return false;
    }
}

static bool StockOpeningPlate(const Ppu *p,const uint8_t *ram)
{
    unsigned scene=Word(ram,0x644);
    if(p->bgmode!=9 || p->mosaic || p->frameInterlace || PPU_objInterlace(p) ||
       PPU_forcedBlank(p) || p->bgTileAdr!=0x622 || p->bgXsc[2]!=0x78)
        return false;
    const unsigned main=p->screenEnabled[0],sub=p->screenEnabled[1];
    switch(scene) {
    case 0xFB:
        return Word(ram,0x6EE)==0x85 && p->bgXsc[0]==0x19 && p->bgXsc[1]==0x11 &&
            !p->windowsel && main==0x10 && !sub && p->cgwsel==0x80 && !p->cgadsub;
    case 0xFC:
        return Word(ram,0x6EE)==0x80 && p->bgXsc[0]==0x18 && p->bgXsc[1]==0x10 &&
            !p->windowsel && (main==0x10 || main==0x16) && !sub &&
            p->cgwsel==0x80 && p->cgadsub==3;
    case 0xFA:
        return Word(ram,0x6EE)==5 && p->bgXsc[0]==0x11 && p->bgXsc[1]==0x19 &&
            p->windowsel==0x228800 && main==1 && sub==4 &&
            p->cgwsel==0x82 && p->cgadsub==0x41 && g_snesrecomp_last_hdmaen==0x0E;
    case 0x8E:
        return Word(ram,0x6EE)==0x1005 && p->bgXsc[0]==0x11 && p->bgXsc[1]==0x19 &&
            !p->windowsel && main==0x13 && sub==3 &&
            ((p->cgwsel==0x80 && p->cgadsub==0x81) || (p->cgwsel==0x82 && p->cgadsub==0x10));
    case 0x8F:
        return Word(ram,0x6EE)==0x1005 && p->bgXsc[0]==0x11 && p->bgXsc[1]==0x19 &&
            !p->windowsel && main==0x11 && sub==1 && p->cgwsel==0x82 && p->cgadsub==0x10;
    default:
        return false;
    }
}

static void RebaseWindow1(Ppu *p,int offset)
{
    int left=p->window1left+offset,right=p->window1right+offset;
    if(left>right || right<0 || left>255) {
        p->window1left=255;
        p->window1right=0;
    } else {
        p->window1left=(uint8_t)Clamp(left,0,255);
        p->window1right=(uint8_t)Clamp(right,0,255);
    }
}

/* A window is written in the coordinates of the original 256x224 field.
 * In a wide picture it stays on that field: both windows move with it, and
 * the rows above and below the field, which no raster line described,
 * have none. Used for every enabled window without a measured layout of
 * its own; what remains after the frame gates is the colour window (the
 * Vampires' circle, Dark Gaia's entrance). */
static void RebaseFieldWindows(Ppu *p,int offset,bool field_row)
{
    if(!field_row) {
        p->window1left=p->window2left=255;
        p->window1right=p->window2right=0;
        return;
    }
    RebaseWindow1(p,offset);
    int left=p->window2left+offset,right=p->window2right+offset;
    if(left>right || right<0 || left>255) {
        p->window2left=255;
        p->window2right=0;
    } else {
        p->window2left=(uint8_t)Clamp(left,0,255);
        p->window2right=(uint8_t)Clamp(right,0,255);
    }
}

enum { DaoHeatPeriod=64 };

static bool DaoHeatWave(const PictureEpoch *e,const Ppu *p)
{
    if(!DaoWorldWindow(p,e->ram) || s.epoch_count!=1) return false;
    bool varied=false;
    size_t offset=offsetof(Ppu,hScroll);
    for(unsigned line=1;line<=224;line++) {
        const uint8_t *regs=s.lines[line].registers;
        const uint8_t *phase=s.lines[(line-1)%DaoHeatPeriod+1].registers;
        unsigned scroll=Word(regs,offset)&1023;
        if(scroll!=(Word(phase,offset)&1023) ||
           regs[offsetof(Ppu,bgXsc)]!=p->bgXsc[0] ||
           Word(regs,offsetof(Ppu,bgTileAdr))!=p->bgTileAdr) return false;
        varied|=scroll!=(p->hScroll[0]&1023);
    }
    return varied;
}

static bool Mode7PlaneLayout(const Ppu *p,unsigned scene)
{
    /* The Sky Garden crash adds its Mode 7 plane to itself on the
     * subscreen. The same texel feeds both inputs of the real color math. */
    bool crash_color_math=scene==0x59 && p->screenEnabled[1]==1 &&
        p->cgwsel==0x82 && p->cgadsub==1 && !p->screenWindowed[1];
    /* The prologue composes text and figures over its Mode 7 plane.
     * Extend only the captured BG1 plane under this stock color layout. */
    bool prologue_color_math=(scene==0x8C || scene==0x8D) &&
        p->screenEnabled[0]==0x11 && p->screenEnabled[1]==1 &&
        p->cgwsel==0x82 && p->cgadsub==0x10 && !p->windowsel;
    return (p->bgmode&7)==7 && !PPU_m7extBg(p) && !p->frameInterlace &&
        !PPU_objInterlace(p) && !(p->mosaic>>4) &&
        (p->screenEnabled[0]&1) && !(p->screenEnabled[0]&~21u) &&
        (!p->screenEnabled[1] || crash_color_math || prologue_color_math) && !ActiveWorldWindow(p) &&
        !(p->windowsel&0xA00000u);
}
static int WorldMapMode7Lines(void)
{
    if(Word(g_snes->ram,0x644)!=0xfe || !(g_snesrecomp_last_hdmaen&0x40))
        return 0;
    const DmaChannel *channel=&g_snes->dma->channel[6];
    if(channel->mode || channel->indirect || channel->fromB ||
       channel->bAdr!=5 || channel->aBank!=0x7e ||
       (channel->aAdr!=0x8800 && channel->aAdr!=0x8900))
        return 0;
    const uint8_t *table=g_snes->ram+channel->aAdr;
    if(table[0]!=127 || table[1]!=7 || table[2]<24 || table[2]>127 ||
       table[3]!=7 || table[4]!=1 || table[5]!=9 || table[6]!=0)
        return 0;
    const char *enable=getenv("IOG_WORLD_MAP_SPLIT");
    /* HDMA selects Mode 7 at line zero. As the menu closes, the Mode 1
     * write moves below line 224 while the PPU still starts in Mode 1. */
    return enable && !strcmp(enable,"0") ? 0 : Clamp(126+table[2],0,224);
}
static int ScrollWorld(const uint8_t *ram,unsigned at,unsigned scroll)
{
    int base=(int16_t)Word(ram,at), result=(base&~1023)|(int)(scroll&1023);
    if(result-base>512) result-=1024;
    if(base-result>512) result+=1024;
    return result;
}

static bool AngkorVisionMosaic(const Ppu *p,const uint8_t *ram)
{
    /* The Spirit Guide's transition into the Mode 7 vision mosaics the
     * ordinary temple picture. Only the known stock background grid is
     * supported; unrelated effects retain their normal fallback. */
    return Word(ram,0x644)==0xBF && p->bgmode==9 && (p->mosaic&15)==3 &&
        !p->windowsel && p->screenEnabled[0]==21 && !p->screenEnabled[1] &&
        Word(ram,0x692)==512 && Word(ram,0x696)==512 &&
        Word(ram,0x694)==768 && Word(ram,0x698)==1024;
}

static bool DaoVillageMosaic(const Ppu *p,const uint8_t *ram)
{
    /* The Spirit Guide's trip to Dao combines the village's regular heat
     * window and color math with the stock two-background reveal. */
    return DaoWorldWindow(p,ram) && Word(ram,0x6EE)==0x0485 &&
        p->bgmode==9 && (p->mosaic&15)==3 &&
        p->screenEnabled[0]==0x17 && p->screenEnabled[1]==0x12 &&
        p->cgwsel==0x82 && p->cgadsub==0x41 && g_snesrecomp_last_hdmaen==0x06;
}

static bool MansionAndSolidArmMosaic(const Ppu *p,const uint8_t *ram)
{
    /* The Mansion reveal and Solid Arm exit share the same two-plane
     * effect but have different authored foreground widths. */
    unsigned scene=Word(ram,0x644);
    unsigned width=scene==0xE9?1024:256;
    return (scene==0xE9 || scene==0xEA) && Word(ram,0x6EE)==0x0485 &&
        p->bgmode==9 && (p->mosaic&15)==3 && !p->windowsel &&
        p->screenEnabled[0]==0x15 && p->screenEnabled[1]==0x16 &&
        p->cgwsel==0x02 && p->cgadsub==0x21 && g_snesrecomp_last_hdmaen==0x02 &&
        Word(ram,0x692)==width && Word(ram,0x696)==width &&
        Word(ram,0x694)==512 && Word(ram,0x698)==256;
}

static bool DarkSpaceMosaic(const Ppu *p,const uint8_t *ram)
{
    return Word(ram,0x644)==0xE6 && Word(ram,0x6EE)==0x0405 &&
        Word(ram,0x692)==256 && Word(ram,0x694)==512 &&
        Word(ram,0x696)==512 && Word(ram,0x698)==512 &&
        p->bgmode==9 && (p->mosaic&15)==3 && !p->windowsel &&
        p->bgXsc[0]==0x11 && p->bgXsc[1]==0x19 &&
        p->screenEnabled[0]==0x15 && p->screenEnabled[1]==2 &&
        p->cgwsel==2 && p->cgadsub==0x31 && g_snesrecomp_last_hdmaen==2;
}

static bool AdriftCoastMosaic(const Ppu *p,const uint8_t *ram)
{
    if(Word(ram,0x6EE)!=5 || Word(ram,0x692)!=256 || Word(ram,0x694)!=512 ||
       Word(ram,0x696)!=256 || Word(ram,0x698)!=512 ||
       p->bgmode!=9 || (p->mosaic&15)!=3 || p->windowsel ||
       p->bgXsc[0]!=0x11 || p->bgXsc[1]!=0x19 ||
       p->screenEnabled[0]!=0x17 || p->screenEnabled[1] || p->cgwsel!=0x80)
        return false;
    /* The outgoing raft keeps its ocean wave. The coast reveal uses the
     * ordinary camera and a different stock blend in the same map layout. */
    switch(Word(ram,0x644)) {
    case 0x2F: return p->cgadsub==0x22 && g_snesrecomp_last_hdmaen==6;
    case 0x31: return p->cgadsub==0xA3 && g_snesrecomp_last_hdmaen==2;
    default: return false;
    }
}

static bool StorySkyLayout(const uint8_t *ram)
{
    return Word(ram,0x644)==0x58 && (ram[0x6EE]&0x80) &&
        Word(ram,0x692)==512 && Word(ram,0x694)==512 &&
        Word(ram,0x696)==512 && Word(ram,0x698)==512 &&
        !Word(ram,0x6D6) && !Word(ram,0x6D8) &&
        Word(ram,0x6DA)==256 && Word(ram,0x6DE)==256;
}

static bool StorySkyFieldLayout(const Ppu *p,const uint8_t *ram)
{
    return StorySkyLayout(ram) && Word(ram,0x6EE)==0x0085 &&
        !Word(ram,0x68A) && !Word(ram,0x68E) && p->bgmode==9 &&
        p->screenEnabled[0]==21 && p->screenEnabled[1]==17 &&
        !p->windowsel && !p->cgwsel && !p->cgadsub;
}

/* Neil's flight to the Great Wall holds its camera on one 256x224 sky.
 * The 256-pixel window below it ends in rows the stock picture never shows. */
static bool NeilFlightField(const uint8_t *ram)
{
    return Word(ram,0x644)==0xDC && Word(ram,0x6EE)==0x0085 &&
        Word(ram,0x692)==512 && Word(ram,0x694)==512 &&
        Word(ram,0x696)==512 && Word(ram,0x698)==512 &&
        !Word(ram,0x6D6) && !Word(ram,0x6D8) &&
        Word(ram,0x6DA)==256 && Word(ram,0x6DE)==256 &&
        !Word(ram,0x68A) && !Word(ram,0x68E);
}

static bool SameActorFieldRoom(const uint8_t *ram,const uint8_t *compose)
{
    return !Word(ram,0x642) && Word(ram,0x644)==Word(compose,0x644) &&
        !memcmp(ram+0x68A,compose+0x68A,0x6C0-0x68A) &&
        !memcmp(ram+0x6D6,compose+0x6D6,0x6F0-0x6D6);
}

static bool RestoredActorFieldLayout(const Ppu *p,const uint8_t *ram)
{
    /* A loaded frame has the original actors already in live OAM. The next
     * composition has started, but its OAM upload will arrive one frame later.
     * The regular scene/layout gate still validates terrain before capture.
     * Only trust the first live field while its room and camera agree with
     * the incoming composition and its display is supported. */
    unsigned scene=Word(ram,0x644);
    bool dark_gaia_window=scene==0xE8 && p->bgmode==9 && p->windowsel==0x300000 &&
        Word(ram,0x6EE)==5 && Word(ram,0x692)==256 && Word(ram,0x694)==256 &&
        Word(ram,0x696)==512 && Word(ram,0x698)==256 &&
        p->bgXsc[0]==0x10 && p->bgXsc[1]==0x18 && p->screenEnabled[0]==0x17 &&
        !p->screenEnabled[1] && p->cgwsel==0x22 && p->cgadsub==3 &&
        g_snesrecomp_last_hdmaen==0x0E;
    if((p->bgmode&7)!=1 || (p->windowsel && !DaoWorldWindow(p,ram) && !dark_gaia_window) || PPU_forcedBlank(p) ||
       p->frameInterlace || PPU_objInterlace(p) || !SameActorFieldRoom(ram,s.pending_ram))
        return false;
    /* A room that was revealed through a mosaic keeps its layer bits set
     * with a block size of one pixel (Luke's house, the Gem rooms, Dark
     * Space). That register value draws nothing. */
    if(!(p->mosaic>>4)) return true;
    return scene==0xE9 && MansionAndSolidArmMosaic(p,ram);
}

static bool StockActorFieldLayout(const Ppu *p,const uint8_t *ram)
{
    /* These dialogue and reward scripts can publish OAM outside the observed
     * composer. Keep their live actors in the native field and extend only
     * the verified room scenery. */
    unsigned scene=Word(ram,0x644);
    if(p->bgmode!=9 || p->mosaic || p->windowsel ||
       p->screenEnabled[0]!=(scene==0x46?0x15:0x17) || p->screenEnabled[1] ||
       p->cgwsel!=0x80 || !SameActorFieldRoom(ram,s.active_ram))
        return false;
    switch(scene) {
    case 0x0B:
        return Word(ram,0x6EE)==0x0185 && p->cgadsub==0x83 && !g_snesrecomp_last_hdmaen &&
            Word(ram,0x692)==512 && Word(ram,0x694)==512 &&
            Word(ram,0x696)==768 && Word(ram,0x698)==768;
    case 0x46:
        return Word(ram,0x6EE)==5 && p->cgadsub==0xA1 && !g_snesrecomp_last_hdmaen &&
            Word(ram,0x692)==512 && Word(ram,0x694)==256 &&
            Word(ram,0x696)==512 && Word(ram,0x698)==256;
    case 0xDF:
        return Word(ram,0x6EE)==1 && p->cgadsub==0xA3 && g_snesrecomp_last_hdmaen==6 &&
            Word(ram,0x692)==2048 && Word(ram,0x694)==256 &&
            Word(ram,0x696)==512 && Word(ram,0x698)==1024;
    default:
        return false;
    }
}

static bool RestoredLiveCamera(const Ppu *p,const uint8_t *ram,int physical,
                               int camera_x,int camera_y,int live_x,int live_y)
{
    /* The saved raster can still be at the previous camera for the first
     * restored frame. Use its position only for verified stock layouts
     * with an unchanged camera throughout the raster. */
    if(!s.restored_actor_field || s.epoch_count!=1 || Word(ram,0x692)!=1280 ||
       Word(ram,0x696)!=1024 || p->bgmode!=9 || p->mosaic ||
       p->screenEnabled[0]!=0x17 || p->cgwsel!=0x82)
        return false;
    switch(Word(ram,0x644)) {
    case 0x15: /* Itory departure, one tile column behind. */
        if(Word(ram,0x6EE)!=5 || Word(ram,0x694)!=512 || Word(ram,0x698)!=256 ||
           p->bgXsc[0]!=0x11 || p->bgXsc[1]!=0x19 || p->screenEnabled[1]!=3 ||
           p->cgadsub || g_snesrecomp_last_hdmaen!=2 ||
           live_x!=camera_x-16 || live_y!=camera_y) return false;
        break;
    case 0x78: /* Watermia's entrance camera is one row ahead. */
        if(Word(ram,0x6EE)!=0x0085 || Word(ram,0x694)!=1280 || Word(ram,0x698)!=1024 ||
           p->bgXsc[0]!=0x19 || p->bgXsc[1]!=0x11 || p->screenEnabled[1]!=0x12 ||
           p->cgadsub!=0x41 || g_snesrecomp_last_hdmaen ||
           live_x!=camera_x || live_y!=camera_y+1) return false;
        break;
    default:
        return false;
    }
    for(unsigned line=0;line<=224;line++) {
        const uint8_t *registers=s.lines[line].registers;
        if((Word(registers,offsetof(Ppu,hScroll)+physical*2)&1023)!=(p->hScroll[physical]&1023) ||
           (Word(registers,offsetof(Ppu,vScroll)+physical*2)&1023)!=(p->vScroll[physical]&1023))
            return false;
    }
    return true;
}

static bool SouthCapeHouseMosaic(const Ppu *p,const uint8_t *ram)
{
    /* The dinner sequence returns from the upper map page to the living
     * room. The normal authored bounds still hide all other house floors. */
    return Word(ram,0x644)==0x06 && Word(ram,0x6EE)==5 &&
        p->bgmode==9 && (p->mosaic&15)==3 && !p->windowsel &&
        p->screenEnabled[0]==0x17 && !p->screenEnabled[1] &&
        p->cgwsel==0x80 && p->cgadsub==0xA3 && g_snesrecomp_last_hdmaen==2 &&
        !Word(ram,0x68A) && !Word(ram,0x68E) &&
        Word(ram,0x692)==256 && Word(ram,0x696)==1280 &&
        Word(ram,0x694)==512 && Word(ram,0x698)==512 &&
        !Word(ram,0x6D6) && !Word(ram,0x6D8) &&
        Word(ram,0x6DA)==256 && Word(ram,0x6DE)==256;
}

static bool BabelQueenMosaic(const Ppu *p,const uint8_t *ram)
{
    /* The Queen's exit mosaics the stock starfield and foreground on the
     * same grid, while the regular channel-1 BG2 wave keeps running. */
    return Word(ram,0x644)==0xF6 && Word(ram,0x6EE)==0x0405 &&
        p->bgmode==9 && (p->mosaic&15)==3 && !p->windowsel &&
        p->screenEnabled[0]==21 && p->screenEnabled[1]==2 &&
        p->cgwsel==0x02 && p->cgadsub==0x31 && g_snesrecomp_last_hdmaen==0x02 &&
        Word(ram,0x692)==512 && Word(ram,0x696)==512 &&
        Word(ram,0x694)==512 && Word(ram,0x698)==512;
}

static bool BabelLandingMosaic(const Ppu *p,const uint8_t *ram)
{
    /* Solid Arm's exit hands off to the landing with a different color
     * math configuration and a foreground bounded to the upper floor. */
    return Word(ram,0x644)==0xE3 && Word(ram,0x6EE)==1 &&
        p->bgmode==9 && (p->mosaic&15)==3 && !p->windowsel &&
        p->screenEnabled[0]==0x17 && !p->screenEnabled[1] &&
        p->cgwsel==0x80 && p->cgadsub==0xA3 && g_snesrecomp_last_hdmaen==6 &&
        Word(ram,0x692)==1024 && Word(ram,0x696)==1024 &&
        Word(ram,0x694)==256 && Word(ram,0x698)==1024;
}

static bool ShipDreamMosaic(const Ppu *p,const uint8_t *ram)
{
    if(p->bgmode!=9 || (p->mosaic&15)!=3 ||
       p->screenEnabled[1] || p->cgwsel!=0x80 ||
       Word(ram,0x694)!=512 || Word(ram,0x698)!=512)
        return false;
    if(p->cgadsub==0xA3 && g_snesrecomp_last_hdmaen==6) {
        if(DreamWorldWindow(p,ram))
            return p->screenEnabled[0]==23 && Word(ram,0x6EE)==5;
        /* The lower deck starts the dream with the same color math
         * but a fixed main screen and its own camera plane. */
        if(Word(ram,0x644)==0x2E)
            return p->screenEnabled[0]==21 && !p->windowsel && Word(ram,0x6EE)==1 &&
                Word(ram,0x692)==768 && Word(ram,0x696)==512;
    }
    /* The cabin's existing HDMA swaps the sunset color math below the sky. */
    return Word(ram,0x644)==0x2D && p->screenEnabled[0]==23 &&
        Word(ram,0x692)==768 && Word(ram,0x696)==512 &&
        Word(ram,0x6EE)==1 && !p->windowsel && (p->cgadsub==0xA1 || p->cgadsub==0x22) &&
        g_snesrecomp_last_hdmaen==0x1E;
}

/* The trip to the Jeweler's Mansion leaves each Gem room through a mosaic,
 * and three story arrivals reveal an ordinary room the same way. Both run
 * over the room's regular picture. Each row is one measured stock layout;
 * any other room or display state keeps the fallback. */
static bool RoomTransitionMosaic(const Ppu *p,const uint8_t *ram)
{
    static const struct {
        uint8_t scene,maps[2],main,sub,cgwsel,cgadsub,hdma;
        uint16_t layout,width,height,bg_width,bg_height;
    } rooms[]={
        {0x01,{0x11,0x19},0x17,0x02,0x82,0x01,0x00,0x0005,768,1024,768,1024},
        {0x32,{0x18,0x11},0x17,0x16,0x82,0x01,0x02,0x0484,1280,1024,256,256},
        {0x5A,{0x11,0x19},0x17,0x00,0x80,0xA2,0x06,0x0005,1024,1536,768,512},
        {0x6B,{0x19,0x11},0x17,0x12,0x82,0x01,0x02,0x0085,1024,1024,1024,768},
        {0x79,{0x11,0x19},0x17,0x00,0x80,0xA3,0x02,0x0005,256,256,256,256},
        {0x7B,{0x11,0x19},0x17,0x00,0x80,0xA3,0x02,0x0005,512,256,512,256},
        {0x7D,{0x11,0x19},0x17,0x00,0x80,0xA3,0x02,0x0005,256,256,256,256},
        {0x9B,{0x11,0x19},0x17,0x00,0x80,0xA3,0x02,0x0005,256,256,256,256},
    };
    if(p->bgmode!=9 || (p->mosaic&15)!=3 || p->windowsel) return false;
    for(unsigned i=0;i<sizeof(rooms)/sizeof(rooms[0]);i++) {
        if(Word(ram,0x644)!=rooms[i].scene) continue;
        return Word(ram,0x6EE)==rooms[i].layout &&
            Word(ram,0x692)==rooms[i].width && Word(ram,0x696)==rooms[i].height &&
            Word(ram,0x694)==rooms[i].bg_width && Word(ram,0x698)==rooms[i].bg_height &&
            p->bgXsc[0]==rooms[i].maps[0] && p->bgXsc[1]==rooms[i].maps[1] &&
            p->screenEnabled[0]==rooms[i].main && p->screenEnabled[1]==rooms[i].sub &&
            p->cgwsel==rooms[i].cgwsel && p->cgadsub==rooms[i].cgadsub &&
            g_snesrecomp_last_hdmaen==rooms[i].hdma;
    }
    return false;
}

static bool StockMosaicLayout(const Ppu *p,const uint8_t *ram)
{
    return AngkorVisionMosaic(p,ram) || DaoVillageMosaic(p,ram) ||
        MansionAndSolidArmMosaic(p,ram) || BabelQueenMosaic(p,ram) ||
        BabelLandingMosaic(p,ram) || ShipDreamMosaic(p,ram) || SouthCapeHouseMosaic(p,ram) ||
        DarkSpaceMosaic(p,ram) || AdriftCoastMosaic(p,ram) ||
        RoomTransitionMosaic(p,ram);
}

static int PositiveMod(int value,int divisor)
{
    int remainder=value%divisor;
    return remainder<0?remainder+divisor:remainder;
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
        const char *wake=getenv("IOG_WORLD_STOCK_ACTIVATION");
        s.stock_wake=wake && !strcmp(wake,"1");
    }
    return s.enabled;
}

void IogWorldSimulationTick(void) { ++s.simulation_ticks; }
bool IogWorldStockVerified(void) { return s.stock; }

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
    s.published_valid=s.repeated=false;
    s.fixed_plate=false;
    s.awaiting_restore=true;
    s.publish_sequence=0;
    s.reason="reset_or_unpaired_upload";
    memset(&s.wake,0,sizeof(s.wake));
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
/* Boss lairs (and their Babel rematches) keep the original 256x224 actor
 * activation: their scripts time attacks and phases on the off-screen flag. */
static bool StockWakeScene(unsigned scene)
{
    return scene==0x29 || scene==0x55 || scene==0x67 || scene==0x8A ||
        scene==0xDD || scene==0xE8 || scene==0xEA || scene>=0xF0;
}

/* The original depth sort has just set or cleared every actor's off-screen
 * flag (actor+$10 bit $4000) from its 256x224 window; scripts read it on
 * their next tick to wake, keep moving or retire. While the wide picture is
 * what the player sees, an actor inside that picture counts as on screen by
 * the same edge test. The wide window always contains the original one, so
 * this only ever clears the flag; the sort's draw list, OAM and every other
 * guest byte stay stock, and the wide picture's own object list is built
 * from actor positions, not from this flag. */
static void WakeVisibleActors(uint8_t *ram)
{
    if(s.stock_wake || !s.wake.width || !s.wake.height ||
       StockWakeScene(Word(ram,0x644))) return;
    int32_t left=(int16_t)Word(ram,0x68A)-s.wake.left;
    int32_t top=(int16_t)Word(ram,0x68E)-s.wake.top;
    unsigned actor=Word(ram,0x56),count=0;
    while(actor>=0x1000 && actor<0x1FC0 && !((actor-0x1000)%0x30) &&
          count++<kIogVisualMaxActors) {
        if((ram[actor+0x11]&0x40) &&
           IogWorldViewAxisOnscreen((uint16_t)Word(ram,actor+0x14),(uint16_t)Word(ram,actor+0x18),
               (uint16_t)Word(ram,actor+0x1C),left,s.wake.width) &&
           IogWorldViewAxisOnscreen((uint16_t)Word(ram,actor+0x16),(uint16_t)Word(ram,actor+0x1A),
               (uint16_t)Word(ram,actor+0x1E),top,s.wake.height))
            ram[actor+0x11]&=(uint8_t)~0x40;
        actor=Word(ram,actor+6);
    }
}

void IogWorldCaptureAfterCompose(const CpuState *cpu,uint32_t pc)
{
    (void)pc;
    if(!s.enabled || !s.pending || !cpu || !cpu->ram) return;
    memcpy(s.staging,cpu->ram+0x422,sizeof(s.staging));
    s.composed=true;
    WakeVisibleActors(cpu->ram);
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
        memcpy(s.published,s.staging,sizeof(s.published));
        s.published_valid=true; s.repeated=false;
        s.active=true; s.publish_sequence=s.compose_sequence;
    } else {
        /* The same objects as the last paired frame are on screen again:
         * active_ram still describes exactly what was uploaded. */
        s.repeated=s.published_valid && (s.active || s.repeated);
        for(unsigned i=0;i<256 && s.repeated;i++)
            s.repeated=g_ppu->oam[i]==Word(s.published,i*2);
        if(s.repeated) s.repeated=!memcmp(g_ppu->highOam,s.published+512,32);
        if(!s.repeated) s.published_valid=false;
        s.active=false; s.reason="unpaired_oam_upload";
        if(s.audit) {
            unsigned staging=0,previous=0;
            for(unsigned i=0;i<256;i++) {
                staging+=g_ppu->oam[i]!=Word(s.staging,i*2);
                previous+=g_ppu->oam[i]!=Word(s.published,i*2);
            }
            s.unpaired.staging=(uint16_t)staging;s.unpaired.previous=(uint16_t)previous;
            s.unpaired.composed=s.composed;s.unpaired.pending=s.pending;
        }
    }
}

void IogWorldBeginRaster(void)
{
    if(!s.enabled || !g_ppu || !g_snes) return;
    bool awaiting_restore=s.awaiting_restore;
    s.awaiting_restore=false;
    s.complete=false; s.valid=false; s.epoch_count=0;
    s.mode7=s.mode7_perspective=false;
    s.absent_secondary=false;
    s.sky_field=s.stock_actor_field=s.restored_actor_field=false;s.hud_layered=false;
    s.fixed_plate=false;
    s.mode7_split=0;
    memset(&s.view,0,sizeof(s.view));
    s.reason="unsupported_scene_or_layout";
    memset(s.hud,0,sizeof(s.hud));
    /* The live field is unchanged. Extraction records the real BG3 pixels. */
    PpuBindOverlaySurface(g_ppu,kPpuOverlaySource_Bg3,(uint8_t*)s.hud,256*4);
    PpuSetOverlayCapture(g_ppu,kPpuOverlaySource_Bg3,0,0,256,224,0);
    if(!s.stock || IogRandomizerActive()) return;
    if(StockModalPlate(g_ppu,g_snes->ram)) {
        s.fixed_plate=true;
        s.reason="ready_stock_modal_plate";
        return;
    }
    if(StockEndingPlate(g_ppu,g_snes->ram)) {
        s.fixed_plate=true;
        s.reason="ready_stock_ending_plate";
        return;
    }
    if(StockOpeningPlate(g_ppu,g_snes->ram)) {
        s.fixed_plate=true;
        s.reason="ready_stock_opening_plate";
        return;
    }
    int map_lines=WorldMapMode7Lines();
    if(map_lines && map_lines<224) s.mode7_split=map_lines+1;
    if(map_lines || Mode7PlaneLayout(g_ppu,Word(g_snes->ram,0x644))) {
        s.base=*g_ppu;s.mode7=s.valid=true;s.reason="awaiting_mode7_plane";
        return;
    }
    /* During Neil's flight, some OAM uploads do not match the observed
     * composer. Keep the hardware picture for the actors, and extend only
     * the known repeating sky after a paired frame has established the room. */
    bool sky_field=!s.active && s.publish_sequence && StorySkyLayout(s.active_ram) &&
        StorySkyFieldLayout(g_ppu,g_snes->ram);
    bool actor_field=!s.active && s.publish_sequence && StockActorFieldLayout(g_ppu,g_snes->ram);
    bool restored_field=awaiting_restore && !s.publish_sequence && s.composed &&
        RestoredActorFieldLayout(g_ppu,g_snes->ram);
    /* The refusals below name their own cause in the audit. */
    /* A repeated upload keeps the composition it was paired with. The
     * rooms above keep their own live-field handling. */
    bool repeated=!s.active && s.repeated && !sky_field && !actor_field && !restored_field;
    if(!s.active && !repeated && !sky_field && !actor_field && !restored_field) {
        s.reason="unpaired_object_publication";return;
    }
    IogSceneViewSource source;
    IogSceneViewReadWorldSource(g_snes->ram,131072,g_ppu,false,&source);
    if(source.gate!=kIogSceneViewReady) {
        s.reason=source.gate==kIogSceneViewUnsupportedScene?"unsupported_scene":
            "unsupported_map_layout";
        return;
    }
    if(source.scene!=Word(restored_field?s.pending_ram:s.active_ram,0x644)) {
        s.reason="scene_ahead_of_publication";return;
    }
    if(PPU_objInterlace(g_ppu) || g_ppu->frameInterlace) {
        s.reason="unsupported_interlace";return;
    }
    if((g_ppu->mosaic>>4)!=0 && !StockMosaicLayout(g_ppu,g_snes->ram)) {
        s.reason="unsupported_mosaic";return;
    }
    if(ActiveWorldWindow(g_ppu) && !KnownWorldWindow(g_ppu,g_snes->ram)) {
        s.reason="unsupported_window";return;
    }
    s.base=*g_ppu;
    s.sky_field=sky_field;
    s.stock_actor_field=actor_field || restored_field;
    s.restored_actor_field=restored_field;
    if(restored_field) {
        memcpy(s.active_ram,s.pending_ram,sizeof(s.active_ram));
        s.published_valid=s.repeated=false;
    }
    s.absent_secondary=source.absent_secondary;
    s.valid=true; s.reason="awaiting_picture";
}

void IogWorldCaptureLine(int line)
{
    if(!s.enabled || !s.valid || line<0 || line>224) return;
    if(s.sky_field && !StorySkyFieldLayout(g_ppu,g_snes->ram)) {
        s.valid=false; s.reason="unsupported_story_sky"; return;
    }
    if(s.stock_actor_field && !(s.restored_actor_field?
       RestoredActorFieldLayout(g_ppu,g_snes->ram):StockActorFieldLayout(g_ppu,g_snes->ram))) {
        s.valid=false; s.reason="unsupported_stock_actor_field"; return;
    }
    if(s.absent_secondary && (Word(g_snes->ram,0x644)!=Word(s.active_ram,0x644) ||
       !IogSceneViewAbsentPyramidSecondary(g_snes->ram,g_ppu))) {
        s.valid=false; s.reason="unexpected_secondary_background"; return;
    }
    bool mode7_line=s.mode7 && (!s.mode7_split || line<s.mode7_split);
    if((mode7_line?!Mode7PlaneLayout(g_ppu,Word(g_snes->ram,0x644)):(g_ppu->bgmode&7)!=1) ||
       g_ppu->frameInterlace ||
       (((g_ppu->mosaic|s.base.mosaic)>>4)!=0 &&
          (!StockMosaicLayout(g_ppu,g_snes->ram) || g_ppu->mosaic!=s.base.mosaic ||
           (line>0 && g_ppu->mosaicStartLine!=1))) ||
       (ActiveWorldWindow(g_ppu) && !KnownWorldWindow(g_ppu,g_snes->ram))) {
        s.valid=false; s.reason="unsupported_line_effect"; return;
    }
    PictureEpoch *prior=s.epoch_count?&s.epochs[s.epoch_count-1]:NULL;
    if(prior && prior->oam_writes!=g_ppu->oamWriteCount) {
        s.valid=false; s.reason="mid_raster_oam_upload"; return;
    }
    /* Metadata, definitions and maps can change at a real raster IRQ. Record
     * only changed epochs; line register input is always captured separately. */
    bool changed=!prior || prior->vram_writes!=g_ppu->vramWriteCount ||
        (s.mode7 && memcmp(prior->ram+0xB0,g_snes->ram+0xB0,0x20)) ||
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

static unsigned MapTile(const PictureEpoch *e,int logical,int x,int y,bool repeat)
{
    const uint8_t *ram=e->ram; unsigned off=logical*2;
    unsigned w=Word(ram,0x692+off),h=Word(ram,0x696+off);
    /* The secondary scenery is a scrolling plane, not another finite world.
     * CameraFullRefresh/WrapMapIndex repeat its small map into the hardware
     * ring. Keep that period beyond the original field too (including the
     * negative side of the host view). Never repeat foreground terrain or
     * the separate floors/material stored in bounded interior maps. */
    if(repeat && w && h) {
        x%= (int)w;if(x<0)x+=(int)w;
        y%= (int)h;if(y<0)y+=(int)h;
    }
    if(x<0 || y<0 || x>=(int)w || y>=(int)h) return 0xFFFFFFFFu;
    unsigned map=Word(ram,0x69E + off),defs=Word(ram,0x6AE + off);
    unsigned address=map+(((y>>8)*(w>>8)+(x>>8))<<8)+(((y>>4)&15)<<4)+((x>>4)&15);
    if(address>=65536 || defs+ram[address]*8+7>=65536) return 0xFFFFFFFFu;
    return Word(ram,defs+ram[address]*8+((y>>3)&1)*4+((x>>3)&1)*2);
}

/* A finite horizon may end in an opaque, completely flat border. Continue
 * that verified border below the image instead of switching to a different
 * backdrop color. This never repeats mountains/sky or invents map geometry.
 * Nonuniform or transparent terminal rows retain explicit finite padding. */
static bool HorizonFlatTail(const PictureEpoch *e,const Ppu *p)
{
    unsigned physical=1u^((e->ram[0x6EE]>>7)&1u),expected=0;
    for(unsigned x=0;x<512;x++) {
        unsigned tile=MapTile(e,1,(int)x,255,false);
        if(tile==0xffffffffu)return false;
        unsigned px=x&7,py=7;
        if(tile&0x4000)px=7-px;
        if(tile&0x8000)py=0;
        unsigned at=(PPU_bgTileAdr(p,physical)+(tile&1023)*16+py)&32767;
        unsigned a=e->vram[at],b=e->vram[(at+8)&32767],bit=7-px;
        unsigned index=((a>>bit)&1)|(((a>>(bit+8))&1)<<1)|
            (((b>>bit)&1)<<2)|(((b>>(bit+8))&1)<<3);
        if(!index)return false;
        unsigned color=e->cgram[((tile>>10)&7)*16+index]&32767;
        if(x&&color!=expected)return false;
        expected=color;
    }
    return true;
}

/* The same for the first row of a backdrop that keeps its own camera: a
 * sky that starts as one opaque colour may continue upward in that colour.
 * A top row with any detail or transparency keeps the plane's finite edge. */
static bool BackdropFlatHead(const PictureEpoch *e,const Ppu *p)
{
    unsigned physical=1u^((e->ram[0x6EE]>>7)&1u),expected=0;
    unsigned width=Word(e->ram,0x694);
    if(width<256 || Word(e->ram,0x698)<256) return false;
    for(unsigned x=0;x<width;x++) {
        unsigned tile=MapTile(e,1,(int)x,0,false);
        if(tile==0xffffffffu)return false;
        unsigned px=x&7,py=0;
        if(tile&0x4000)px=7-px;
        if(tile&0x8000)py=7;
        unsigned at=(PPU_bgTileAdr(p,physical)+(tile&1023)*16+py)&32767;
        unsigned a=e->vram[at],b=e->vram[(at+8)&32767],bit=7-px;
        unsigned index=((a>>bit)&1)|(((a>>(bit+8))&1)<<1)|
            (((b>>bit)&1)<<2)|(((b>>(bit+8))&1)<<3);
        if(!index)return false;
        unsigned color=e->cgram[((tile>>10)&7)*16+index]&32767;
        if(x&&color!=expected)return false;
        expected=color;
    }
    return true;
}

/* These are the five scenery models exercised by the manual F4--F8 saves.
 * Do not infer the camera rate from allocation sizes: the original actors
 * choose it. Other rooms retain their existing sampling pending a visual
 * qualification of their own. This changes the host picture only. */
static bool EffectPlaneScene(unsigned scene)
{
    return scene==0x85 || scene==0x4F || scene==0x55 || scene==0xEA || scene==0xCC;
}

static int EffectProjection(unsigned scene,bool vertical,int position)
{
    switch(scene) {
    case 0x85: return vertical?position:0; /* ScrollCameraVertical, 1:1 Y */
    case 0x4F: /* ScrollCameraTrack, packed ratio $0401 on both axes */
        return position>=0?position/4:-((-position+3)/4);
    case 0x55: case 0xCC: return 0; /* independent sky / fixed wall plate */
    default: return position; /* Solid Arm drift adds the camera delta */
    }
}

typedef struct EffectCamera { unsigned ratio[2]; bool uploaded_ring; } EffectCamera;

/* Observe the actual, composition-paired camera producer. Allocation sizes
 * cannot distinguish a fixed backdrop from quarter-speed scenery. Packed
 * actor parameters are multiplier/divisor bytes used by stock MulDivide. */
static bool ReadEffectCamera(const uint8_t *ram,EffectCamera *out)
{
    unsigned actor=Word(ram,0x56),count=0,previous=0;
    bool found=false;
    *out=(EffectCamera){{0,0},false};
    while(actor) {
        if(actor<0x1000 || actor>=0x1FC0 || (actor-0x1000)%0x30 || ++count>84 ||
           Word(ram,actor+4)!=previous)
            return false;
        if((ram[actor+2]&0x3F)==0 && (Word(ram,actor+0x12)&0x1000)) {
            EffectCamera next={{0,0},false};bool known=true;
            switch(Word(ram,actor)) {
            case 0xEAA3: case 0xEAD7: /* Track / Accumulate */
                next.ratio[0]=Word(ram,actor+0x14);
                next.ratio[1]=Word(ram,actor+0x16);break;
            case 0xEAB4: /* Vertical */
                next.ratio[1]=Word(ram,actor+0x16);break;
            case 0xEA26: /* Wrapped drift includes both camera deltas. */
                next.ratio[0]=next.ratio[1]=0x0101;
                next.uploaded_ring=(ram[0x6EF]&4)!=0;break;
            default:known=false;break;
            }
            if(known) {
                for(unsigned axis=0;axis<2;axis++) {
                    unsigned ratio=next.ratio[axis];
                    if(ratio && (!(ratio>>8) ||
                       (unsigned)Word(ram,0x692+axis*4)*(ratio&255)>65535u))
                        return false;
                }
                if(found) return false;
                *out=next;found=true;
            }
        }
        previous=actor;actor=Word(ram,actor+6);
    }
    return found && Word(ram,0x58)==previous;
}

/* These measured BG2 layouts stay registered to the original gameplay
 * rectangle. Extend the captured scroll instead of recentering the backdrop
 * at a second rate, which shifts rocks or clouds underneath stock objects. */
static bool RasterAnchoredBackdrop(unsigned scene,const uint8_t *ram,const EffectCamera *effect)
{
    unsigned width=Word(ram,0x692),height=Word(ram,0x696);
    unsigned bg_width=Word(ram,0x694),bg_height=Word(ram,0x698);
    if(scene==0x43)
        return width==1536 && height==1024 && bg_width==1024 && bg_height==768;
    if(bg_width!=512 || bg_height!=512) return false;
    switch(scene) {
    case 0x4c: case 0x4d: case 0x4f: case 0x51: case 0x53:
        return effect && effect->ratio[0]==0x0401 && effect->ratio[1]==0x0401;
    case 0x55:
        return width==512 && height==512;
    default:
        return false;
    }
}

static int ProjectEffect(unsigned ratio,int position)
{
    int denominator=(int)(ratio>>8),numerator=(int)(ratio&255);
    if(!denominator)return 0;
    int product=position*numerator;
    return product>=0?product/denominator:-((-product+denominator-1)/denominator);
}

enum { RingWavePeriod = 64, LaraiMistPeriod = 16 };

static bool CapturedHorizontalWave(const Ppu *p,unsigned layer,unsigned period,bool stable_color)
{
    size_t h=offsetof(Ppu,hScroll)+layer*2,v=offsetof(Ppu,vScroll)+layer*2;
    unsigned vscroll = Word(s.lines[1].registers,v) & 1023;
    bool varied = false;
    unsigned first = Word(s.lines[1].registers,h) & 1023;
    for (unsigned line = 1; line <= 224; line++) {
        const uint8_t *regs = s.lines[line].registers;
        unsigned hscroll = Word(regs,h) & 1023;
        unsigned phase = (line - 1) % period + 1;
        if ((Word(regs,v) & 1023) != vscroll ||
            hscroll != (Word(s.lines[phase].registers,h) & 1023) ||
            regs[offsetof(Ppu,bgXsc)+layer] != p->bgXsc[layer] ||
            Word(regs,offsetof(Ppu,bgTileAdr)) != p->bgTileAdr ||
            (stable_color && (regs[offsetof(Ppu,cgwsel)]!=p->cgwsel ||
             regs[offsetof(Ppu,cgadsub)]!=p->cgadsub)))
            return false;
        varied |= hscroll != first;
    }
    return varied;
}

/* Freejia's BG1 is the drifting secondary layer despite the PPU layer
 * numbering. Its slow-wave thinker repeats a single 64-line HDMA table.
 * Require agreement with the live raster and keep the uploaded tile ring. */
static bool FreejiaRingWave(const PictureEpoch *e, const Ppu *p,
                           const EffectCamera *camera)
{
    const uint8_t *ram = e->ram;
    if (Word(ram,0x644) != 0x32 || !(ram[0x6EE] & 128) ||
        Word(ram,0x694) != 256 || Word(ram,0x698) != 256 ||
        !camera->uploaded_ring || camera->ratio[0] != 0x0101 ||
        camera->ratio[1] != 0x0101 ||
        PPU_bigTiles(p,0) || PPU_bgTilemapWider(p,0) || PPU_bgTilemapHigher(p,0))
        return false;
    return CapturedHorizontalWave(p,0,RingWavePeriod,false);
}

static bool LaraiMist(const PictureEpoch *e,const Ppu *p,const EffectCamera *camera)
{
    const uint8_t *ram=e->ram;
    /* The cliff uses a vertically tracked finite map and a separate short
     * horizontal mist wave. Its expanded rows continue the measured HDMA
     * phase instead of repeating the first or last native scanline. */
    return Word(ram,0x644)==0x1D && Word(ram,0x6EE)==0x85 &&
        Word(ram,0x692)==768 && Word(ram,0x694)==512 &&
        Word(ram,0x696)==1536 && Word(ram,0x698)==1536 &&
        !camera->uploaded_ring && !camera->ratio[0] && camera->ratio[1]==0x0101 &&
        p->bgmode==9 && p->bgXsc[0]==0x19 && p->bgXsc[1]==0x11 &&
        p->screenEnabled[0]==0x17 && p->screenEnabled[1]==0x12 &&
        p->cgwsel==0x82 && p->cgadsub==0x41 &&
        CapturedHorizontalWave(p,0,LaraiMistPeriod,true);
}

/* The Mansion uses a two-page uploaded BG1 fog ring in display mode $22.
 * Leaving that ring for the finite map drops the color-math input at a
 * camera-dependent edge. Retain the live ring only for its witnessed phase. */
static bool MansionFog(const PictureEpoch *e,const Ppu *p,
                       const EffectCamera *camera)
{
    const uint8_t *ram=e->ram;
    return Word(ram,0x644)==0xE9 && (ram[0x6EE]&128) &&
        Word(ram,0x692)==1024 && Word(ram,0x696)==1024 &&
        Word(ram,0x694)==512 && Word(ram,0x698)==256 &&
        camera->uploaded_ring && camera->ratio[0]==0x0101 && camera->ratio[1]==0x0101 &&
        !PPU_bigTiles(p,0) && PPU_bgTilemapWider(p,0) && !PPU_bgTilemapHigher(p,0) &&
        p->cgwsel==0x02 && p->cgadsub==0x21 && CapturedHorizontalWave(p,0,RingWavePeriod,true);
}

/* All five rematches retain their stars in an uploaded BG2 ring under the
 * ending wave. The stars may be on either screen. Leave both enables and
 * backdrop math in the captured state rather than moving BG2 to main. */
static bool BabelStarfieldLayout(const PictureEpoch *e,const Ppu *p)
{
    const uint8_t *ram=e->ram;
    unsigned scene=Word(ram,0x644);
    return scene>=0xF2 && scene<=0xF6 && (Word(ram,0x6EE)&0x0480)==0x0400 &&
       Word(ram,0x694)==512 && Word(ram,0x698)==512 &&
       !PPU_bigTiles(p,1) && PPU_bgTilemapWider(p,1) && !PPU_bgTilemapHigher(p,1) &&
       ((p->screenEnabled[0]|p->screenEnabled[1])&2) &&
       p->cgwsel==0x02 && p->cgadsub==0x31;
}

/* Dark Space draws its stars from the same uploaded, repeating BG2 ring and
 * 64-line wave as the Babel rematches. Only that ring may continue past the
 * room. The floor, portal and actors keep their original field. */
static bool DarkSpaceStarfield(const PictureEpoch *e,const Ppu *p)
{
    const uint8_t *ram=e->ram;
    return Word(ram,0x644)==0xE6 && Word(ram,0x6EE)==0x0405 &&
        Word(ram,0x692)==256 && Word(ram,0x696)==512 &&
        Word(ram,0x694)==512 && Word(ram,0x698)==512 &&
        p->bgmode==9 && !p->windowsel &&
        p->bgXsc[0]==0x11 && p->bgXsc[1]==0x19 &&
        !PPU_bigTiles(p,1) && PPU_bgTilemapWider(p,1) && !PPU_bgTilemapHigher(p,1) &&
        p->screenEnabled[0]==0x15 && p->screenEnabled[1]==2 &&
        p->cgwsel==0x02 && p->cgadsub==0x31 && g_snesrecomp_last_hdmaen==2 &&
        CapturedHorizontalWave(p,1,RingWavePeriod,true);
}

enum { WaterWavePeriod = 8 };
enum { VillageHeatPeriod = 32 };
enum { StockWaveTable = 0x8800, StockWaveRing = 0x8900, StockWavePeriod = 128,
       StockWaveLastLine = 222, BabelAlternateTable = 0x8A00 };

static bool HorizontalScrollHdma(const DmaChannel *c,unsigned target)
{
    return c->mode==2 && c->indirect && !c->fromB && c->bAdr==target &&
        c->aBank==0x7E && c->indBank==0x7E;
}

static unsigned StockHorizontalWaveOrigin(const uint8_t *ram)
{
    const uint8_t *table=ram+StockWaveTable;
    unsigned origin=Word(table,1);
    enum { RingBytes=2*StockWavePeriod };
    if(table[0]!=0xFF || table[3]!=0xE0 || table[6] ||
       origin<StockWaveRing || origin+2*(StockWaveLastLine+1)>StockWaveRing+4*RingBytes ||
       (origin&1) || Word(table,4)!=origin+254)
        return 0;
    return origin;
}

/* The victory producer replaces the BG2 ring one frame before HDMA enables
 * the two new channels. Only BG2 can move in that picture. Some camera phases
 * overwrite the alternate descriptor with a single held scroll value. */
static bool BabelVictorySetup(const PictureEpoch *e)
{
    const uint8_t *ram=e->ram;
    const unsigned scene=Word(ram,0x644);
    if(scene>0xF5 || Word(ram,0x6EE)!=0x0405 ||
       g_snesrecomp_last_hdmaen!=0x02 || !g_snes->dma)
        return false;
    const DmaChannel *c=&g_snes->dma->channel[1];
    if(!HorizontalScrollHdma(c,15))
        return false;
    unsigned origin=StockHorizontalWaveOrigin(ram);
    if(!origin || (c->aAdr!=StockWaveTable && c->aAdr!=BabelAlternateTable))
        return false;

    /* The paired OAM was authored against the outgoing 64-row table. */
    const uint8_t *outgoing=s.active_ram+c->aAdr;
    for(unsigned offset=0;offset<12;offset+=3)
        if(outgoing[offset]!=0xC0 || Word(outgoing,offset+1)!=c->aAdr+0x100u)
            return false;

    bool held=c->aAdr==BabelAlternateTable;
    /* Sand Fanger's alternate descriptor is already covered by the new ring.
     * Admit that frame only when it leaves BG2 at one scroll value for the
     * whole picture, so the rows outside the field continue the same value. */
    bool fanger_hold=held && scene==0xF5 && ram[BabelAlternateTable]!=0xC0;
    if(held && !fanger_hold) {
        const uint8_t *table=ram+BabelAlternateTable;
        if(scene!=0xF3 || table[0]!=0x5A || Word(table,1)!=0x5A00 || table[3])
            return false;
        origin=Word(table,1);
    }
    const size_t h=offsetof(Ppu,hScroll)+2;
    const uint8_t *base=s.lines[0].registers;
    for(int line=0;line<=224;line++) {
        const uint8_t *regs=s.lines[line].registers;
        const unsigned sample=held?0u:(unsigned)Clamp(line,0,StockWaveLastLine);
        const unsigned expected=fanger_hold?Word(base,h):Word(ram,origin+2*sample);
        if((Word(regs,h)&1023)!=(expected&1023) ||
           memcmp(regs,base,h) ||
           memcmp(regs+h+2,base+h+2,PPU_SAVESTATE_REGS_SIZE-h-2))
            return false;
    }
    return true;
}

/* Validate the shared horizontal HDMA producer on both backgrounds and
 * every visible line before using its ring outside the original field. */
static unsigned StockHorizontalWave(const PictureEpoch *e,const Ppu *p,int camera_x,
                                   unsigned hdma_mask,bool *repeats)
{
    const uint8_t *ram=e->ram;
    if(s.epoch_count!=1 || g_snesrecomp_last_hdmaen!=hdma_mask || !g_snes->dma)
        return 0;

    const unsigned channels[]={6,7,1};
    for(unsigned i=0;i<sizeof(channels)/sizeof(channels[0]);i++) {
        unsigned ch=channels[i];
        if(!(hdma_mask&(1u<<ch))) continue;
        const DmaChannel *c=&g_snes->dma->channel[ch];
        /* The rematches' original BG2 wave uses a double buffer on ch1.
         * The verified ch7 write supplies the final BG2 value each line. */
        bool table_matches=c->aAdr==StockWaveTable || (ch==1 && c->aAdr==BabelAlternateTable);
        if(!HorizontalScrollHdma(c,ch==6?13:15) || !table_matches)
            return 0;
    }
    unsigned origin=StockHorizontalWaveOrigin(ram);
    if(!origin) return 0;
    bool varied=false,periodic=true;
    const size_t h=offsetof(Ppu,hScroll),v=offsetof(Ppu,vScroll);
    /* The higher channels end together after sample 222. Sand Fanger's
     * alternating channel-1 source then supplies its own BG2 values for the
     * final two lines. Those rows keep their captured scroll in the field,
     * and the rows below the field continue the wave table instead. */
    const bool bg2_free_tail=hdma_mask==0xC2 && Word(ram,0x644)==0xF5 &&
        g_snes->dma->channel[1].aAdr==BabelAlternateTable;
    for(int line=0;line<=224;line++) {
        const uint8_t *regs=s.lines[line].registers;
        unsigned sample=(unsigned)Clamp(line,0,StockWaveLastLine);
        unsigned shift=Word(ram,origin+2*sample)&1023;
        int distance=(int)((shift-(unsigned)camera_x+512)&1023)-512;
        /* Babel's alternating BG2 source data can carry its camera
         * displacement. Both final scroll registers must still match
         * the actual wave table. */
        if((hdma_mask==0xC0 && (distance < -64 || distance > 64)) ||
           (Word(regs,h)&1023)!=shift ||
           ((Word(regs,h+2)&1023)!=shift && !(bg2_free_tail && line>StockWaveLastLine)) ||
           (Word(regs,v)&1023)!=(p->vScroll[0]&1023) ||
           (Word(regs,v+2)&1023)!=(p->vScroll[1]&1023) ||
           regs[offsetof(Ppu,bgXsc)]!=p->bgXsc[0] ||
           regs[offsetof(Ppu,bgXsc)+1]!=p->bgXsc[1] ||
           Word(regs,offsetof(Ppu,bgTileAdr))!=p->bgTileAdr)
            return 0;
        periodic&=(Word(ram,origin+2*(sample%StockWavePeriod))&1023)==shift;
        varied|=distance!=0;
    }
    *repeats=periodic;
    return varied?origin:0;
}

static bool ArrivalWaveLayout(unsigned scene,const PictureEpoch *e,const Ppu *p,
                              int camera_x,int camera_y)
{
    const uint8_t *ram=e->ram;
    if(Word(ram,0x644)!=scene || Word(ram,0x692)!=512 ||
       (int16_t)Word(ram,0x68A)!=camera_x || (int16_t)Word(ram,0x68E)!=camera_y ||
       (p->vScroll[0]&1023)!=((unsigned)camera_y&1023) ||
       (p->vScroll[1]&1023)!=((unsigned)camera_y&1023))
        return false;
    if(scene==0x0B)
        return Word(ram,0x694)==512 && Word(ram,0x696)==768 &&
            Word(ram,0x698)==768 && Word(ram,0x6EE)==0x0185 &&
            Word(ram,0x68C)==Word(ram,0x68A) && Word(ram,0x690)==Word(ram,0x68E);
    return scene==0xDE && Word(ram,0x694)==256 && Word(ram,0x696)==256 &&
        Word(ram,0x698)==256 && Word(ram,0x6EE)==0x0001 &&
        Word(ram,0x6D6)==256 && !Word(ram,0x6D8) &&
        Word(ram,0x6DA)==512 && Word(ram,0x6DE)==256 &&
        !Word(ram,0x68C) && !Word(ram,0x690) && camera_x==256 && camera_y==0;
}

/* The Pyramid portals, the Mu altar and the Watermia glass game run the
 * same stock wave over the room's ordinary picture. The producer writes the
 * terrain scroll to both registers. Most of these rooms show only their
 * terrain background. Those that show a second plane are admitted only
 * while both cameras share the same horizontal position. Each row is one
 * measured stock layout; any other room or display state keeps the fallback.
 * Watermia keeps bobbing during the wave, and its raster can be one row
 * ahead of the composed camera. The caller then uses the raster's row. */
static bool RoomTransitionWave(unsigned scene,const PictureEpoch *e,const Ppu *p,
                               int camera_x,int camera_y)
{
    static const struct {
        uint8_t scene,layout,main,sub,cgwsel,cgadsub;
        uint16_t width,height;
    } rooms[]={
        {0x66,0x05,0x15,0x00,0x80,0xA1,768,512},
        {0x78,0x85,0x17,0x12,0x82,0x41,1280,1024},
        {0xCC,0x05,0x15,0x00,0x80,0xA1,1024,1024},
        {0xCF,0x05,0x15,0x00,0x80,0xA1,1536,1024},
        {0xD1,0x05,0x15,0x00,0x80,0xA1,1280,1536},
        {0xD3,0x05,0x15,0x00,0x80,0xA1,2048,768},
        {0xD4,0x05,0x15,0x00,0x80,0xA1,1280,1280},
        {0xD5,0x05,0x15,0x00,0x80,0xA1,1280,1280},
        {0xD7,0x05,0x17,0x00,0x80,0xA3,1024,1536},
        {0xD8,0x05,0x15,0x00,0x80,0xA1,1280,1280},
        {0xDB,0x85,0x17,0x00,0x80,0xA3,2048,512},
        {0xDD,0x05,0x15,0x00,0x80,0xA1,512,512},
    };
    const uint8_t *ram=e->ram;
    if(Word(ram,0x644)!=scene || p->bgmode!=9 || p->mosaic || p->windowsel ||
       (int16_t)Word(ram,0x68A)!=camera_x)
        return false;
    for(unsigned i=0;i<sizeof(rooms)/sizeof(rooms[0]);i++) {
        if(scene!=rooms[i].scene) continue;
        unsigned physical=rooms[i].layout>>7;
        bool second_plane=((rooms[i].main|rooms[i].sub)&2)!=0;
        int ahead=ScrollWorld(ram,0x68E,p->vScroll[physical])-camera_y;
        if(ahead && (scene!=0x78 || ahead < -1 || ahead > 1)) return false;
        return Word(ram,0x6EE)==rooms[i].layout &&
            Word(ram,0x692)==rooms[i].width && Word(ram,0x696)==rooms[i].height &&
            p->bgXsc[physical]==0x11 && p->bgXsc[physical^1]==0x19 &&
            p->screenEnabled[0]==rooms[i].main && p->screenEnabled[1]==rooms[i].sub &&
            p->cgwsel==rooms[i].cgwsel && p->cgadsub==rooms[i].cgadsub &&
            (!second_plane || Word(ram,0x68C)==Word(ram,0x68A));
    }
    return false;
}

/* Scene AC binds one 32-line heat table to both vertical scroll registers.
 * Keep the actual raster across the native field. Extend it only when both
 * layers agree throughout the captured picture. */
static bool VillageHeat(const PictureEpoch *e,const Ppu *p)
{
    const uint8_t *ram=e->ram;
    if(s.epoch_count!=1 || Word(ram,0x644)!=0xAC ||
       Word(ram,0x692)!=512 || Word(ram,0x694)!=512 ||
       Word(ram,0x696)!=512 || Word(ram,0x698)!=512)
        return false;
    /* The raster can be one walking step ahead of the composed camera.
     * Horizontal scroll still follows composition. The sine table is
     * centered on the raster's vertical camera. */
    int camera_x=(int16_t)Word(s.active_ram,0x68A);
    int camera_y=(int16_t)Word(ram,0x68E);
    int delta_x=(int16_t)Word(ram,0x68A)-camera_x;
    int delta_y=camera_y-(int16_t)Word(s.active_ram,0x68E);
    if(delta_x < -2 || delta_x > 2 || delta_y < -2 || delta_y > 2 ||
       Word(ram,0x68C)!=Word(ram,0x68A) || Word(ram,0x690)!=Word(ram,0x68E))
        return false;
    bool varied=false;
    size_t h=offsetof(Ppu,hScroll),v=offsetof(Ppu,vScroll),maps=offsetof(Ppu,bgXsc);
    for(unsigned line=1;line<=224;line++) {
        const uint8_t *regs=s.lines[line].registers;
        const uint8_t *phase=s.lines[(line-1)%VillageHeatPeriod+1].registers;
        unsigned x=Word(regs,h)&1023,y=Word(regs,v)&1023;
        int drift=ScrollWorld(ram,0x68E,y)-camera_y;
        if(x!=((unsigned)camera_x&1023) || x!=(Word(regs,h+2)&1023) ||
           y!=(Word(regs,v+2)&1023) || y!=(Word(phase,v)&1023) ||
           drift < -4 || drift > 4 ||
           regs[maps]!=p->bgXsc[0] || regs[maps+1]!=p->bgXsc[1] ||
           Word(regs,offsetof(Ppu,bgTileAdr))!=p->bgTileAdr)
            return false;
        varied |= y!=(p->vScroll[0]&1023);
    }
    return varied;
}

/* Mu and Seaside Palace bind both secondary scroll registers to a repeating
 * sine table. Require the known layout and agreement across all published
 * rows before extending the wave beyond the recorded field. */
static bool WaterWave(const PictureEpoch *e, const Ppu *p)
{
    const uint8_t *ram = e->ram;
    unsigned scene = Word(ram, 0x644);
    unsigned physical = 1 ^ ((ram[0x6EE] >> 7) & 1);
    unsigned width = Word(ram, 0x692), height = Word(ram, 0x696);
    unsigned water_width = Word(ram, 0x694), water_height = Word(ram, 0x698);
    bool mu = ((scene >= 0x5F && scene <= 0x62) || scene == 0x64 || scene == 0x65) &&
        physical == 0 && width == water_width && height == water_height;
    bool palace = ((scene == 0x5A && width == 1024 && height == 1536) ||
                   (scene == 0x5B && width == 256 && height == 1024) ||
                   (scene == 0x5C && width == 1024 && height == 1024)) &&
        physical == 1 && water_width == 768 && water_height == 512;
    if (!mu && !palace)
        return false;
    /* The measured coffin room changes its palette during the raster.
     * RenderWorld has already matched every epoch's VRAM. Bind the two
     * palettes to their real raster rows and require identical room RAM. */
    if (s.epoch_count != 1 &&
        !(scene == 0x5C && s.epoch_count == 2 &&
          !memcmp(s.epochs[0].ram, s.epochs[1].ram, sizeof(e->ram)) &&
          memcmp(s.epochs[0].cgram, s.epochs[1].cgram, sizeof(e->cgram))))
        return false;
    size_t xoff = offsetof(Ppu, hScroll) + physical * 2;
    size_t yoff = offsetof(Ppu, vScroll) + physical * 2;
    unsigned first_x = p->hScroll[physical] & 1023, first_y = p->vScroll[physical] & 1023;
    bool varied = false;
    for (unsigned line = 1; line <= 224; line++) {
        const uint8_t *regs = s.lines[line].registers;
        const uint8_t *period = s.lines[(line - 1) % WaterWavePeriod + 1].registers;
        unsigned x = Word(regs, xoff) & 1023;
        unsigned y = Word(regs, yoff) & 1023;
        if (x != (Word(period, xoff) & 1023) || y != (Word(period, yoff) & 1023) ||
            regs[offsetof(Ppu, bgXsc) + physical] != p->bgXsc[physical] ||
            Word(regs, offsetof(Ppu, bgTileAdr)) != p->bgTileAdr)
            return false;
        varied |= x != first_x || y != first_y;
    }
    return varied;
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

typedef struct PictureBounds { int left,top,right,bottom; } PictureBounds;

static bool SourcePlateScene(unsigned scene)
{
    return scene==0x2A || (scene>=0xE4 && scene<=0xE8) || scene==0xF0;
}

static bool BoundedRoomScene(unsigned scene)
{
    switch(scene) {
    case 0x02: case 0x03: case 0x04: case 0x05: case 0x06: case 0x16:
    case 0x17: case 0x18: case 0x31:
    case 0x49: case 0x85: case 0xCD: case 0xDA: return true;
    default: return SourcePlateScene(scene);
    }
}

/* Allocated maps can hold several separate floors, story versions, or BG
 * animation material. For these measured stock rooms, the original live
 * InitCameraBounds window is the authored extent, not the allocation size.
 * Dark Space and flight also use composed BG2 material rather than a proved
 * offscreen terrain stream. Retain their authoritative field, as well as
 * Dark Gaia's original camera scroll between phase pages and the ending,
 * rather than exposing extra animation/other-phase material. */
static bool AuthoredWindow(const PictureEpoch *e,PictureBounds *out)
{
    const uint8_t *ram=e->ram;
    *out=(PictureBounds){Word(ram,0x6D6),Word(ram,0x6D8),
        Word(ram,0x6DA),Word(ram,0x6DE)};
    return out->right<=(int)Word(ram,0x692) && out->bottom<=(int)Word(ram,0x696) &&
        out->right-out->left>=256 && out->bottom-out->top>=224 &&
        !((out->left|out->top|out->right|out->bottom)&255);
}

static bool RoomPictureBounds(const PictureEpoch *e,int camera_x,int camera_y,
    PictureBounds *out)
{
    const uint8_t *ram=e->ram;
    unsigned scene=Word(ram,0x644),width=Word(ram,0x692),height=Word(ram,0x696);
    unsigned expected_width=scene==0x04?512:256,expected_height=256;
    /* Rampway storage contains three courses. Only the current authored
     * camera window is this visit's floor; the other pages are not scenery. */
    if(scene==0x85) {expected_width=2048;expected_height=768;}
    if(scene==0xDA) expected_width=1536;
    if(scene==0xE4) {expected_width=512;expected_height=512;}
    if(scene==0x03 || scene==0x04 || scene==0xE6 || scene==0xE8) expected_height=512;
    if(scene==0x06 || scene==0x2A) expected_height=1280;
    if(!BoundedRoomScene(scene) || width!=expected_width || height!=expected_height) return false;
    if(SourcePlateScene(scene)) {
        /* The Babel rooftop's blue vortex is cutscene art in its BG2
         * allocation. Showing the unused side tiles creates a water strip
         * suspended over the void. Keep the composed cutscene field. */
        if(scene==0xE4 && (Word(ram,0x694)!=512 || Word(ram,0x698)!=512))
            return false;
        /* The final school scene has a single composed street view and
         * moving cutscene actors. Its BG3 dialogue can use the host frame. */
        /* The scene loads no second map, so those two words keep the last
         * room's size. They describe nothing while BG2 is on neither screen. */
        if(scene==0xF0 && (Word(ram,0x694)!=256 || Word(ram,0x698)!=256) &&
           ((ram[0x6EE]&0x80) || ((s.base.screenEnabled[0]|s.base.screenEnabled[1])&2)))
            return false;
        /* The dream stores separate rooms in one tall map. Preserve its
         * original aperture and never expose adjacent floors. */
        if(scene==0x2A && (Word(ram,0x694)!=512 || Word(ram,0x698)!=512))
            return false;
        *out=(PictureBounds){camera_x,camera_y,camera_x+256,camera_y+224};
        return true;
    }
    /* 06DE is the uncorrected bottom edge; 06DC additionally contains the
     * original visible-height correction. Neither word is a player edit. */
    if(!AuthoredWindow(e,out)) return false;
    if(scene==0xCD) {
        /* The puzzle room stores glyph picker tiles below the fixed playfield. */
        if(camera_x || camera_y || Word(ram,0x6EE)!=5 ||
           out->left || out->top || out->right!=256 || out->bottom!=256)
            return false;
        out->bottom=224;
    }
    if(scene==0x49 || scene==0xDA) {
        /* These rooms store map material below the authored field. Each
         * Hieroglyph panel and Neil's cottage use one original-height view. */
        if(out->right-out->left!=256 || out->bottom-out->top!=256) return false;
        out->bottom=out->top+224;
    }
    if(scene==0x06 || (scene>=0x16 && scene<=0x18)) {
        /* Will's house and the Itory houses keep storage tiles in the last
         * row of a one-screen floor. The stock camera rests on the top of
         * that page and never shows them. Other floors keep their window. */
        if(out->right-out->left==256 && out->bottom-out->top==256 &&
           !camera_x && camera_y==out->top && Word(ram,0x6EE)==5)
            out->bottom=out->top+224;
    }
    return true;
}

static uint32_t FiniteRoomBackdrop(const PictureEpoch *e,const Ppu *p,unsigned scene,int line)
{
    const uint8_t *ram=e->ram;
    /* These finite rooms use a flat, dark CGRAM 0 outside their visible
     * scenery. Continue it through the padded pixels at the live brightness
     * without exposing another map page or changing the stock field. */
    if(Word(ram,0x644)!=scene || Word(ram,0x6EE)!=5 || p->bgmode!=9 ||
       p->mosaic || p->windowsel || PPU_forcedBlank(p) || p->fixedColor ||
       p->bgXsc[0]!=0x11 || p->bgXsc[1]!=0x19) return 0;
    bool main=p->screenEnabled[0]==0x15 && !p->screenEnabled[1];
    bool subtract_zero=p->cgwsel==0x80 && p->cgadsub==0xA1;
    if(scene==0x47) {
        if(!main || Word(ram,0x692)!=256 || Word(ram,0x694)!=256 ||
           Word(ram,0x696)!=768 || Word(ram,0x698)!=256 ||
           e->cgram[0]!=0x0842 || !subtract_zero) return 0;
    } else {
        /* The annex disables background layers for its last two lines.
         * With the same blend settings they still show the backdrop. */
        bool annex_tail=line>=223 && !p->screenEnabled[0] && !p->screenEnabled[1];
        if((!main && !annex_tail) || Word(ram,0x692)!=768 || Word(ram,0x694)!=768 ||
           Word(ram,0x696)!=256 || Word(ram,0x698)!=1024 ||
           Word(ram,0x6D6) || Word(ram,0x6D8) ||
           Word(ram,0x6DA)!=256 || Word(ram,0x6DE)!=256 ||
           e->cgram[0]!=0x1062 || (!subtract_zero && (p->cgwsel || p->cgadsub!=0x21))) return 0;
    }
    unsigned rgb=e->cgram[0],light=PPU_brightness(p);
    return (uint32_t)ppu_brightness_level(rgb&31,light)<<16 |
           (uint32_t)ppu_brightness_level((rgb>>5)&31,light)<<8 |
           ppu_brightness_level((rgb>>10)&31,light);
}

static bool CastleMapMarker(const PictureEpoch *e)
{
    const uint8_t *ram=e->ram;
    /* This disconnected 2×2 metatile marker is stored in the last corner of
     * the prison passage. It only becomes visible in the expanded margins. */
    return Word(ram,0x644)==0x0B && Word(ram,0x692)==512 &&
        Word(ram,0x696)==768 && Word(ram,0xA5EE)==0xFFFE &&
        Word(ram,0xA5FE)==0xFDFC;
}

static bool AngelEntranceHasStorageTail(const PictureEpoch *e)
{
    const uint8_t *ram=e->ram;
    PictureBounds bounds;
    unsigned secondary_width=Word(ram,0x694),secondary_height=Word(ram,0x698);
    bool secondary=(secondary_width==1280 && secondary_height==1024) ||
        (secondary_width==512 && (secondary_height==512 || secondary_height==256));
    return Word(ram,0x644)==0x69 && Word(ram,0x692)==768 &&
        Word(ram,0x696)==256 && secondary &&
        Word(ram,0x69E)==0xA000 && Word(ram,0x6AE)==0x2000 && Word(ram,0x6EE)==5 &&
        AuthoredWindow(e,&bounds) && !bounds.left && !bounds.top &&
        bounds.right==768 && bounds.bottom==256;
}

static bool RoomPictureView(int camera_x,int camera_y,const PictureBounds *bounds)
{
    IogWorldView view;
    if(IogWorldViewCompute(camera_x-bounds->left,camera_y-bounds->top,
            (unsigned)(bounds->right-bounds->left),(unsigned)(bounds->bottom-bounds->top),
            (uint16_t)s.width,(uint16_t)s.height,&view)) {
        view.world_x+=bounds->left;view.world_y+=bounds->top;s.view=view;
        return true;
    } else {
        /* Original forced-walk stairs can change the destination window
         * before their camera finishes panning. Keep the real source field
         * centered at the same extent, without a fallback zoom or invented
         * cells between floors. Its original pixels remain authoritative. */
        s.view.world_x=camera_x-(s.width-256)/2;
        s.view.world_y=camera_y-(s.height-224)/2;
        s.view.native_x=(uint16_t)(camera_x-s.view.world_x);
        s.view.native_y=(uint16_t)(camera_y-s.view.world_y);
        s.view.padding_left=(uint16_t)Clamp(bounds->left-s.view.world_x,0,s.width);
        s.view.padding_right=(uint16_t)Clamp(s.view.world_x+s.width-bounds->right,0,s.width);
        s.view.padding_top=(uint16_t)Clamp(bounds->top-s.view.world_y,0,s.height);
        s.view.padding_bottom=(uint16_t)Clamp(s.view.world_y+s.height-bounds->bottom,0,s.height);
        return false;
    }
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

/* A uniform affine plane can continue outside the original screen without
 * inventing perspective/HDMA rows. OBJ and interface pixels remain the real
 * original field, overlaid at identical world-pixel scale during presentation.
 * Other Mode7 compositions retain the same-scale reference fallback. */
/* The setting chooses; IOG_WORLD_MAP_FILTER=0 still forces the point-sampled
 * hardware picture for tests. */
static bool map_enhanced;
void IogWorldSetMapEnhanced(bool enhanced){map_enhanced=enhanced;}
static bool Mode7FilterWanted(void)
{
    static int wanted=-1;
    if(wanted<0) {
        const char *value=getenv("IOG_WORLD_MAP_FILTER");
        wanted=!(value && !strcmp(value,"0"));
    }
    return map_enhanced && wanted!=0;
}
static uint32_t Mode7Mix(uint32_t from,uint32_t to,unsigned part)
{
    /* part is 0..256 of `to`, per channel. */
    uint32_t out=0;
    for(unsigned shift=0;shift<24;shift+=8) {
        unsigned a=(from>>shift)&255,b=(to>>shift)&255;
        out|=((a*(256-part)+b*part+128)>>8)<<shift;
    }
    return out;
}

#include "iog_world_sky.inc"
/* The owner's sky painting above the walking map's horizon. The picture is
 * mirrored into a circle that one full turn of the camera crosses once, and
 * dims with the screen like the map under it. `above` counts rows up from
 * the horizon; row 0 is the glow the haze below fades into. */
static uint32_t WorldSkyPixel(int column,int above,unsigned light)
{
    int u=column%(2*kWorldSkyWidth);
    if(u<0) u+=2*kWorldSkyWidth;
    if(u>=kWorldSkyWidth) u=2*kWorldSkyWidth-1-u;
    int v=kWorldSkyHeight-1-above;
    uint32_t rgb=kWorldSkyPalette[kWorldSky[(v<0?0:v)*kWorldSkyWidth+u]];
    return light>=15?rgb:Mode7Mix(0,rgb,light*256u/15u);
}

/* GPU ground for the filtered walking map. When the host says the runner's
 * GPU Mode 7 presenter will take this frame (IogWorldSetMapGpu, decided in
 * main.c before the frame is built), each ground row is recorded as a
 * prepared affine row and the presenter samples the plane at the window's
 * resolution. The box filter is then skipped: the software picture keeps a
 * one-sample ground, which is what lies under objects and overlays and what
 * is shown if the presenter turns the frame down. Sky rows, objects and
 * every overlay stay software pixels. Samples 0: the software plane. */
static struct {
    int samples,used;
    bool ready;
    unsigned sea;
    int sky_turn;
    struct { uint8_t kind,haze,light,line,control,sea_edge,cgwsel,cgadsub; uint16_t fixed; double affine[8]; } rows[MaxHeight];
} hd;
void IogWorldSetMapGpu(int samples) { hd.samples=samples<0?0:samples>4?4:samples; }
static bool Mode7HdRecord(int row,const Ppu *p,const int32_t from[4],const int32_t to[4],
    int y,unsigned haze,int line,const uint32_t colors[256],const uint16_t *cgram,bool sea_edge)
{
    int cx=SnesMode7HdSign13(p->m7matrix[4]),cy=SnesMode7HdSign13(p->m7matrix[5]);
    int h=SnesMode7HdSign13(p->m7matrix[6])-cx,v=SnesMode7HdSign13(p->m7matrix[7])-cy;
    h=(h&0x2000)?(h|~1023):(h&1023);
    v=(v&0x2000)?(v|~1023):(v&1023);
    bool flip_x=PPU_m7xFlip(p),flip_y=PPU_m7yFlip(p);
    double edge[2][4];
    for(int e=0;e<2;e++) {
        const int32_t *m=e?to:from;
        double yy=(flip_y?255.0-(y+e):(double)(y+e))+v,hh=h+(flip_x?255:0);
        edge[e][0]=(m[0]*hh+m[1]*yy)/256.0+cx*256.0;
        edge[e][1]=(m[2]*hh+m[3]*yy)/256.0+cy*256.0;
        edge[e][2]=(flip_x?-m[0]:m[0])/256.0;
        edge[e][3]=(flip_x?-m[2]:m[2])/256.0;
    }
    unsigned light=PPU_brightness(p);
    hd.rows[row].kind=1;hd.rows[row].haze=(uint8_t)haze;hd.rows[row].light=(uint8_t)light;
    hd.rows[row].line=(uint8_t)line;hd.rows[row].control=p->m7sel;hd.rows[row].sea_edge=sea_edge;
    for(int c=0;c<4;c++) {
        hd.rows[row].affine[c]=edge[0][c];hd.rows[row].affine[c+4]=edge[1][c]-edge[0][c];
    }
    /* The GPU rows carry the palette, brightness and fixed-colour math the
     * shared shader implements; anything else keeps the software plane. */
    hd.rows[row].cgwsel=p->cgwsel;hd.rows[row].cgadsub=p->cgadsub;hd.rows[row].fixed=p->fixedColor;
    unsigned prevent=(p->cgwsel>>4)&3,clip=(p->cgwsel>>6)&3;
    if((p->cgwsel&3) || clip==3 || clip==1 ||
       (sea_edge && ((p->cgadsub&1)!=0)!=((p->cgadsub&32)!=0))) return false;
    for(unsigned c=0;c<8;c++) if(!isfinite(hd.rows[row].affine[c])) return false;
    for(unsigned i=0;i<256;i++) {
        unsigned color=cgram[i],layer=i?0:5;
        bool math=prevent!=3 && prevent!=1 && (p->cgadsub&(1u<<layer));
        uint32_t expected=0;
        for(unsigned c=0;c<3;c++) {
            int value=(color>>(5*c))&31;
            if(math) {
                int other=(p->fixedColor>>(5*c))&31;
                value+=p->cgadsub&128?-other:other;
                if(value<0)value=0;
                if(p->cgadsub&64)value/=2;
                if(value>31)value=31;
            }
            expected|=(uint32_t)ppu_brightness_level((unsigned)value,light)<<(16-8*c);
        }
        if((colors[i]&0xffffffu)!=expected) return false;
    }
    return true;
}
/* The one-sample ground of a recorded row: the same transform the presenter
 * uses, read at the middle of each pixel. */
static void Mode7HdSoftRow(int row,const Ppu *p,int first_x,int count,
    const uint32_t colors[256],uint32_t outside,uint32_t *out)
{
    const double *a=hd.rows[row].affine;
    double step_u=(a[2]+.5*a[6])/256.0,step_w=(a[3]+.5*a[7])/256.0;
    double u=(a[0]+.5*a[4])/256.0+(first_x+.5)*step_u,w=(a[1]+.5*a[5])/256.0+(first_x+.5)*step_w;
    for(int i=0;i<count;i++,u+=step_u,w+=step_w)
        out[i]=IogMode7PlaneColor(p,colors,outside,(int)floor(u),(int)floor(w))&0xffffffu;
}

static bool RenderMode7Plane(void)
{
    s.mode7_filtered=false;hd.ready=false;
    if(!s.valid || !s.epoch_count) return false;
    /* Mode7 observes its own raster epochs, not the prior Mode1 OAM pair. */
    s.visual.part_count=0;
    Ppu *source=&s.mode7_source,*palette=&s.detached;
    *source=s.base;memcpy(source,s.lines[1].registers,PPU_SAVESTATE_REGS_SIZE);
    int16_t matrix[8];memcpy(matrix,source->m7matrix,sizeof(matrix));
    unsigned control=source->m7sel;bool uniform=true;
    int map_end=s.mode7_split?s.mode7_split-1:224;
    for(int line=1;line<=map_end;line++) {
        memcpy(source,s.lines[line].registers,PPU_SAVESTATE_REGS_SIZE);
        const PictureEpoch *epoch=&s.epochs[s.lines[line].epoch];
        if(!Mode7PlaneLayout(source,Word(epoch->ram,0x644))) {
            s.reason="mode7_unsupported_raster";return false;
        }
        if(source->m7sel!=control || memcmp(source->m7matrix,matrix,sizeof(matrix)))
            uniform=false;
    }
    const PictureEpoch *initial=&s.epochs[s.lines[0].epoch];
    unsigned angle=Word(initial->ram,0xBC)&511u;
    const Cart *cart=g_snes?g_snes->cart:NULL;
    if(cart && cart->rom && cart->romImageSize==2097152) {
        unsigned sin_at=0x1C595+angle*2,cos_at=0x1C695+angle*2;
        s.mode7_parameters=(IogMode7PerspectiveParameters){
            (uint16_t)Word(initial->ram,0xB8),(uint16_t)Word(initial->ram,0xB6),
            IogMode7PerspectiveSigned(Word(cart->rom,cos_at)),
            IogMode7PerspectiveSigned(Word(cart->rom,sin_at))};
        int16_t captured[224][4];bool stable=true;
        for(int line=0;line<=map_end;line++) {
            memcpy(source,s.lines[line].registers,PPU_SAVESTATE_REGS_SIZE);
            if(line<224)memcpy(captured[line],source->m7matrix,sizeof(captured[line]));
            if(memcmp(source->m7matrix+4,matrix+4,4*sizeof(int16_t)) ||
               source->m7sel!=control)stable=false;
            const PictureEpoch *e=&s.epochs[s.lines[line].epoch];
            if(memcmp(e->ram+0xB6,initial->ram+0xB6,8))stable=false;
        }
        /* The stock destination menu switches to Mode 1 below map_end.
         * Verify every Mode 7 row, including the initialized raster row,
         * before continuing its projection above the visible map. The
         * terminal hold only applies when Mode 7 spans the full display. */
        int verified_rows=s.mode7_split?map_end+1:224;
        s.mode7_perspective=stable &&
            (s.mode7_split || !memcmp(source->m7matrix,captured[223],sizeof(captured[223]))) &&
            IogMode7PerspectiveMatchesPrefix(&s.mode7_parameters,captured,verified_rows);
    }
    *palette=s.base;Detach(palette);memset(palette->vram,0,sizeof(palette->vram));
    /* Ask the actual detached PPU for all256 palette results, including
     * backdrop, brightness, clipping and fixed-color math. This avoids a
     * second, approximate color compositor for the extended plane. */
    for(unsigned tile=0;tile<32;tile++) palette->vram[tile]=(uint16_t)tile;
    for(unsigned tile=0;tile<32;tile++) {
        for(unsigned x=0;x<8;x++) {
            unsigned address=tile*64+8+x;
            palette->vram[address]=(palette->vram[address]&255)|((tile*8+x)<<8);
        }
    }
    int left=(s.width-256)/2,top=(s.height-224)/2;
    s.view=(IogWorldView){0};s.view.width=(uint16_t)s.width;s.view.height=(uint16_t)s.height;
    s.view.world_x=-left;s.view.world_y=-top;
    s.view.native_x=(uint16_t)left;s.view.native_y=(uint16_t)top;
    uint32_t colors[256];int prior_epoch=-1;
    /* A validated full-screen camera is drawn from its producer at sub-row
     * precision and box-filtered. Objects are restored at presentation. */
    bool filtered=s.mode7_perspective && !s.mode7_split && Mode7FilterWanted();
    /* The map's own commonest texel is open sea. Use it, under each row's
     * palette, for what lies past the map edge and for the haze at the
     * horizon, so neither is a flat black cut. */
    enum { HazeRows=14 };
    unsigned sea=0;bool edge_is_sea=false;int horizon=1-top,sky_turn=0;
    if(filtered) {
        unsigned counts[256]={0};
        const uint16_t *map=s.epochs[s.lines[1].epoch].vram;
        for(int v=8;v<1024;v+=16) for(int u=8;u<1024;u+=16)
            counts[SnesMode7HdFetchInt(0,map,u,v,-1)]++;
        for(unsigned index=1;index<256;index++) if(counts[index]>counts[sea]) sea=index;
        edge_is_sea=sea!=0;
        /* One turn of the camera is one trip round the mirrored picture. */
        sky_turn=(int)lround(atan2((double)s.mode7_parameters.sine,(double)s.mode7_parameters.cosine)*
                             kWorldSkyWidth/3.14159265358979);
        int32_t probe[4];
        while(horizon<1 && IogMode7PerspectiveSmooth(&s.mode7_parameters,horizon,0,probe)!=
              kIogMode7PerspectiveMatrix) horizon++;
        hd.ready=hd.samples>0;hd.used=hd.samples;hd.sea=sea;hd.sky_turn=sky_turn;
        memset(hd.rows,0,sizeof(hd.rows));
    }
    uint8_t prior_registers[PPU_SAVESTATE_REGS_SIZE];
    memset(prior_registers,0,sizeof(prior_registers));
    int backdrop_shown=-1;
    for(int row=0;row<s.height;row++) {
        int y=row-top+1;
        /* Extend only a validated camera above the stock menu. Its
         * Mode 1 dialogue band and the padding below stay intact. */
        if((s.mode7_split && (y>map_end || (y<1 && !s.mode7_perspective))) ||
           (!uniform && !s.mode7_perspective && (y<1 || y>224))) {
            memset(s.output+row*s.width,0,s.width*4);continue;
        }
        PictureLine *line=&s.lines[Clamp(y,1,224)];
        PictureEpoch *epoch=&s.epochs[line->epoch];
        memcpy(source,line->registers,PPU_SAVESTATE_REGS_SIZE);
        if(prior_epoch!=(int)line->epoch ||
           memcmp(prior_registers,line->registers,sizeof(prior_registers))) {
            memcpy(source->vram,epoch->vram,sizeof(source->vram));
            memcpy(palette,line->registers,PPU_SAVESTATE_REGS_SIZE);
            memcpy(palette->cgram,epoch->cgram,sizeof(palette->cgram));
            palette->screenEnabled[0]=1;palette->screenEnabled[1]=source->screenEnabled[1];
            palette->screenWindowed[0]=palette->screenWindowed[1]=0;
            memset(palette->m7matrix,0,sizeof(palette->m7matrix));
            palette->m7matrix[0]=palette->m7matrix[3]=256;palette->m7sel=0;
            IogWorldPixelsDrawLine(palette,0);IogWorldPixelsDrawLine(palette,1);
            memcpy(colors,s.row,sizeof(colors));
            memcpy(prior_registers,line->registers,sizeof(prior_registers));
            prior_epoch=line->epoch;
        }
        if(filtered) {
            int32_t from[4],to[4];
            IogMode7PerspectiveStatus status=IogMode7PerspectiveSmooth(
                &s.mode7_parameters,y,0,from);
            if(y>=1 && y<=224) for(int x=0;x<256;x++)
                s.mode7_exact[(y-1)*256+x]=colors[IogMode7PlaneIndex(source,x,y)];
            uint32_t backdrop=colors[0],haze=edge_is_sea?colors[sea]:colors[0];
            uint32_t *out=s.output+row*s.width;
            unsigned light=PPU_brightness(source);
            if(status==kIogMode7PerspectiveMatrix) {
                if(IogMode7PerspectiveSmooth(&s.mode7_parameters,y+1,0,to)!=
                   kIogMode7PerspectiveMatrix) memcpy(to,from,sizeof(to));
                if(hd.ready && !Mode7HdRecord(row,source,from,to,y,
                    edge_is_sea && y-horizon<HazeRows?(unsigned)(HazeRows-(y-horizon))*208u/HazeRows:0,
                    Clamp(y,1,224),colors,epoch->cgram,edge_is_sea && (source->m7sel&0xC0)==0x80)) {
                    /* Not a row the presenter can draw: build this picture
                     * again from the top with the software plane. */
                    hd.ready=false;row=-1;prior_epoch=-1;
                    memset(prior_registers,0,sizeof(prior_registers));
                    continue;
                }
                if(hd.ready) Mode7HdSoftRow(row,source,-left,s.width,colors,haze,out);
                else IogMode7PlaneFilteredRowEdge(source,from,to,y,-left,s.width,colors,haze,out);
                if(edge_is_sea && y-horizon<HazeRows) {
                    unsigned part=(unsigned)(HazeRows-(y-horizon))*208u/HazeRows;
                    for(int x=0;x<s.width;x++)
                        out[x]=Mode7Mix(out[x],WorldSkyPixel(x+sky_turn,0,light),part);
                }
            } else {
                /* Above the horizon: the sky painting. */
                int above=horizon-y;
                for(int x=0;x<s.width;x++)
                    out[x]=edge_is_sea?WorldSkyPixel(x+sky_turn,above<0?0:above,light):backdrop;
            }
            continue;
        }
        if(s.mode7_perspective && (y<1 || y>224)) {
            int index=y>224?y-1:y;
            IogMode7PerspectiveStatus status=IogMode7PerspectiveSample(
                &s.mode7_parameters,index,source->m7matrix);
            if(status!=kIogMode7PerspectiveMatrix) {
                /* The backdrop colour is this scene's sky only where the
                 * original field shows it. A plane that fills every stock
                 * row (the prologue ocean) leaves that palette entry unused,
                 * and the rows past its horizon are padding. */
                if(backdrop_shown<0) {
                    backdrop_shown=0;
                    for(int line=1;line<=map_end && !backdrop_shown;line++) {
                        memcpy(source,s.lines[line].registers,PPU_SAVESTATE_REGS_SIZE);
                        for(int x=0;x<256;x++)
                            if(!IogMode7PlaneIndex(source,x,line)) {backdrop_shown=1;break;}
                    }
                }
                uint32_t color=status==kIogMode7PerspectiveSky && backdrop_shown?colors[0]:0;
                for(int x=0;x<s.width;x++)s.output[row*s.width+x]=color;
                continue;
            }
        }
        for(int x=0;x<s.width;x++)
            s.output[row*s.width+x]=colors[IogMode7PlaneIndex(source,x-left,y)];
    }
    s.mode7_filtered=filtered;
    s.reason=s.mode7_split?"ready_mode7_destination_menu":
        s.mode7_perspective?"ready_mode7_perspective":
        uniform?"ready_mode7_plane":"ready_mode7_raster_band";return true;
}

/* One recorded ground row for the publisher in main.c; kind 0 is a row the
 * software picture keeps (sky). False: nothing to publish this frame. */
bool IogWorldHdQuery(int row,int width,int height,IogWorldHdRow *out)
{
    if(!out || !hd.ready || !s.complete || !s.mode7 || !s.mode7_filtered || s.fixed_plate ||
       width!=s.width || height!=s.height || row<0 || row>=height) return false;
    *out=(IogWorldHdRow){0};
    out->samples=hd.used;out->soft=s.output+row*width;
    if(!hd.rows[row].kind) return true;
    const PictureEpoch *epoch=&s.epochs[s.lines[hd.rows[row].line].epoch];
    out->kind=1;out->haze=hd.rows[row].haze;out->light=hd.rows[row].light;
    out->control=hd.rows[row].control;out->cgwsel=hd.rows[row].cgwsel;
    out->cgadsub=hd.rows[row].cgadsub;out->fixed=hd.rows[row].fixed;
    out->edge=hd.rows[row].sea_edge?(int)hd.sea:-1;
    out->vram=epoch->vram;out->cgram=epoch->cgram;
    memcpy(out->affine,hd.rows[row].affine,sizeof(out->affine));
    return true;
}
uint32_t IogWorldHdHaze(int x,unsigned light) { return WorldSkyPixel(x+hd.sky_turn,0,light); }

static void CompositeHud(uint8_t *dst,size_t pitch)
{
    int hudw=256*s.height/224,hudx=(s.width-hudw)/2;
    for(int y=0;y<s.height;y++) for(int x=0;x<hudw;x++) {
        uint32_t color=s.hud[(y*224/s.height)*256+x*256/hudw];
        if((color>>24) && x+hudx>=0 && x+hudx<s.width)
            memcpy(dst+y*pitch+(x+hudx)*4,&color,sizeof(color));
    }
}

/* The status display and dialogue boxes are 1.5 times the world's pixel
 * size. Scaled into the frame by nearest pixel, every other column is drawn
 * twice and one-pixel strokes come out uneven. Where the presenter can draw
 * a layer over the scaled frame, hand it the plane instead: it is then
 * scaled once, to the window, with even pixel widths. */
static void PresentHud(uint8_t *dst,size_t pitch)
{
    static uint32_t layer[256*224];
    if(!snes_ovl_frame_layer_available()) {CompositeHud(dst,pitch);return;}
    for(int i=0;i<256*224;i++) layer[i]=(s.hud[i]>>24)?(s.hud[i]|0xff000000u):0;
    int hudw=256*s.height/224;
    snes_ovl_frame_layer_set(layer,256,224,(s.width-hudw)/2,0,hudw,s.height);
}

static void DrawCenteredField(uint8_t *dst,size_t pitch,const uint8_t *field,
                             int width,int plate_width,int source_rows,int rows)
{
    int left=(width-plate_width)/2;
    for(int y=0;y<rows;y++) {
        uint8_t *row=dst+y*pitch;
        memset(row,0,width*4);
        const uint8_t *source=field+(y*source_rows/rows)*256*4;
        for(int x=0;x<plate_width;x++)
            memcpy(row+(left+x)*4,source+(x*256/plate_width)*4,4);
    }
}

static bool Mode7DestinationPanel(const uint8_t *field,int map_rows)
{
    if(!s.mode7_split || !s.epoch_count) return false;
    /* Confirm the stock Mode 1 menu band and verify that every colored
     * pixel in it is the actual published BG3 panel. Any visible scenery
     * or object in an unknown split keeps its usual source framing. */
    for(int y=map_rows;y<224;y++) {
        const PictureLine *line=&s.lines[y+1];
        const uint8_t *regs=line->registers;
        if(Word(s.epochs[line->epoch].ram,0x644)!=0xFE ||
           regs[offsetof(Ppu,bgmode)]!=9 || regs[offsetof(Ppu,mosaic)] ||
           regs[offsetof(Ppu,bgXsc)+2]!=0x78 ||
           !(regs[offsetof(Ppu,screenEnabled)]&4)) return false;
        for(int x=0;x<256;x++) {
            int i=y*256+x;
            const uint8_t *rgb=field+4*i;
            uint32_t color=s.hud[i];
            if((rgb[0]||rgb[1]||rgb[2]) && ((color>>24)!=255 || memcmp(rgb,&color,3)))
                return false;
        }
    }
    return true;
}

static bool RenderWorld(void)
{
    if(s.mode7) return RenderMode7Plane();
    if(!s.valid || !s.epoch_count || s.width<256 || s.height<224) return false;
    PictureEpoch *first=&s.epochs[s.lines[1].epoch];
    bool live_actors=s.sky_field || s.stock_actor_field;
    const uint8_t *picture_ram=live_actors?first->ram:s.active_ram;
    unsigned scene=Word(picture_ram,0x644);
    bool classroom=scene==0x08;
    if(classroom) for(int n=0;n<s.epoch_count;n++)
        if(!OriginalClassroomLayout(&s.epochs[n])) {
            s.reason="unsupported_classroom_layout";return false;
        }
    for(int n=0;n<s.epoch_count;n++) if(memcmp(first->vram,s.epochs[n].vram,sizeof(first->vram))) {
        s.reason="mid_raster_character_upload";return false;
    }
    Ppu *p=&s.detached;
    *p=s.base;memcpy(p,s.lines[1].registers,PPU_SAVESTATE_REGS_SIZE);
    int physical=(picture_ram[0x6EE]>>7)&1;
    int camera_x=(int16_t)Word(picture_ram,0x68A);
    int camera_y=(int16_t)Word(picture_ram,0x68E);
    bool village_heat=scene==0xAC && VillageHeat(first,p);
    bool babel_starfield_layout=s.epoch_count==1 && BabelStarfieldLayout(first,p);
    bool transition_wave_repeats=false;
    bool room_wave=RoomTransitionWave(scene,first,p,camera_x,camera_y);
    unsigned transition_wave=(((scene==0x0B || scene==0xDE) &&
        ArrivalWaveLayout(scene,first,p,camera_x,camera_y)) || room_wave)?
            StockHorizontalWave(first,p,camera_x,0xC0,&transition_wave_repeats):0;
    if(!transition_wave_repeats) transition_wave=0;
    room_wave=room_wave && transition_wave;
    if(room_wave) camera_y=ScrollWorld(picture_ram,0x68E,p->vScroll[physical]);
    if(babel_starfield_layout && scene<=0xF5 && Word(first->ram,0x6EE)==0x0405)
        transition_wave=StockHorizontalWave(first,p,camera_x,0xC2,&transition_wave_repeats);
    bool babel_victory_wave=transition_wave && babel_starfield_layout;
    bool babel_victory_setup=babel_starfield_layout && BabelVictorySetup(first);
    bool source_plate=SourcePlateScene(scene);
    if(source_plate) {
        /* These verified compositions expose only their native field. Their
         * BG scroll can animate independently of the actor camera (E7 flight),
         * so retain that real raster scroll without treating it as more world.
         * Shape/scene refusal and composition/OAM publication gates still apply. */
        PictureBounds bounds;
        if(Word(first->ram,0x644)!=scene ||
           !RoomPictureBounds(first,camera_x,camera_y,&bounds)) {
            s.reason="unsupported_room_window";return false;
        }
    } else if(!village_heat && !transition_wave) {
        int live_x=ScrollWorld(picture_ram,0x68A,p->hScroll[physical]);
        int live_y=ScrollWorld(picture_ram,0x68E,p->vScroll[physical]);
        if(live_x!=camera_x || live_y!=camera_y) {
            if(!RestoredLiveCamera(p,picture_ram,physical,camera_x,camera_y,live_x,live_y)) {
                s.reason="camera_publication_mismatch";return false;
            }
            camera_x=live_x;
            camera_y=live_y;
        }
    }
    if(!IogWorldViewCompute(camera_x,camera_y,Word(first->ram,0x692),
            Word(first->ram,0x696),(uint16_t)s.width,(uint16_t)s.height,&s.view)) {
        s.reason="invalid_world_view";return false;
    }
    bool bounded=BoundedRoomScene(scene);
    PictureBounds authored_bounds;
    bool authored=!bounded && !classroom && AuthoredWindow(first,&authored_bounds) &&
        (authored_bounds.left || authored_bounds.top ||
         authored_bounds.right!=(int)Word(first->ram,0x692) ||
         authored_bounds.bottom!=(int)Word(first->ram,0x696));
    bool flight_field=authored && s.epoch_count==1 && !camera_x && !camera_y &&
        NeilFlightField(first->ram);
    if(flight_field) authored_bounds.bottom=224;
    EffectCamera effect_camera;
    bool tracked_effect=!s.sky_field && ReadEffectCamera(s.active_ram,&effect_camera);
    IogRasterParallax horizon_model={0};
    IogRasterParallax wall_model={0};
    bool horizon=false,wall_bands=false;
    if(tracked_effect && s.epoch_count==1) {
        uint16_t hscroll[225];Ppu probe=s.base;
        for(unsigned i=0;i<225;i++) {
            memcpy(&probe,s.lines[i].registers,PPU_SAVESTATE_REGS_SIZE);
            hscroll[i]=probe.hScroll[1];
        }
        const Cart *cart=g_snes?g_snes->cart:NULL;
        if(cart) {
            if(effect_camera.ratio[1]==0)
                horizon=IogRasterParallaxPrepare(cart->rom,cart->romImageSize,s.stock,
                    first->ram,sizeof(first->ram),hscroll,225,&horizon_model);
            if(effect_camera.ratio[0]==0 && effect_camera.ratio[1]==0x0101)
                wall_bands=IogRasterParallaxPrepareWall(cart->rom,cart->romImageSize,s.stock,
                    first->ram,sizeof(first->ram),hscroll,225,&wall_model);
        }
    }
    bool freejia_wave = tracked_effect && s.epoch_count == 1 &&
        FreejiaRingWave(first,p,&effect_camera);
    bool larai_mist=tracked_effect && s.epoch_count==1 && LaraiMist(first,p,&effect_camera);
    bool mansion_fog=tracked_effect && s.epoch_count==1 && MansionFog(first,p,&effect_camera);
    bool dark_space_stars=scene==0xE6 && s.epoch_count==1 && DarkSpaceStarfield(first,p);
    bool babel_stars=babel_victory_wave || babel_victory_setup || dark_space_stars ||
        (babel_starfield_layout && CapturedHorizontalWave(p,1,RingWavePeriod,true));
    bool water_wave = WaterWave(first,p);
    bool dao_heat=DaoHeatWave(first,p);
    if (scene == 0x32 && !freejia_wave) {
        s.reason = "unsupported_freejia_wave";
        return false;
    }
    if(scene==0xE9 && !mansion_fog) {
        s.reason="unsupported_mansion_fog";return false;
    }
    if(scene>=0xF2 && scene<=0xF6 && (!babel_stars || !AuthoredWindow(first,&authored_bounds))) {
        s.reason="unsupported_babel_starfield";return false;
    }
    bool deferred_raster_effect=false;
    /* A room transition wave moves both planes together. Keep the room's
     * ordinary camera projection so the margins do not shift as it begins. */
    if(tracked_effect && !horizon && !wall_bands && !freejia_wave && !mansion_fog && !babel_stars &&
       !room_wave) {
        /* A camera actor does not describe per-band HDMA derivatives.
         * Keep those on their prior sampling policy until their actual
         * raster producer is bound; a global ratio would be misleading. */
        Ppu *probe=&s.mode7_source;
        unsigned background=1u^((s.active_ram[0x6EE]>>7)&1u);
        for(int line=1;line<=224;line++) {
            memcpy(probe,s.lines[line].registers,PPU_SAVESTATE_REGS_SIZE);
            if(probe->hScroll[background]!=p->hScroll[background] ||
               probe->vScroll[background]!=p->vScroll[background]) {
                tracked_effect=false;deferred_raster_effect=true;break;
            }
        }
    }
    bool flat_horizon_tail=horizon&&HorizonFlatTail(first,p);
    bool raster_anchored=RasterAnchoredBackdrop(scene,first->ram,
        tracked_effect?&effect_camera:NULL);
    bool wall_approach=authored && !authored_bounds.left &&
        ((scene==0x82 && Word(first->ram,0x692)==2048 &&
          Word(first->ram,0x696)==1024 && authored_bounds.right==2048 &&
          ((!authored_bounds.top && authored_bounds.bottom==256) ||
           (authored_bounds.top==256 && authored_bounds.bottom==1024))) ||
         (scene==0x88 && Word(first->ram,0x692)==1024 &&
          Word(first->ram,0x696)==768 && authored_bounds.right==1024 &&
          !authored_bounds.top && authored_bounds.bottom==256));
    bool wall_field_phase=wall_bands && (wall_approach || scene==0x8A || scene==0x8B);
    /* The captured backdrop can be from the next camera publication. */
    int wall_source_camera=wall_field_phase?wall_model.source_camera_x:camera_x;
    /* On the underside of Sky Garden, the real BG2 ring wraps as the
     * clouds drift. Only that map repeats. The walkable floors stay finite. */
    bool underside_backdrop=(scene==0x4e || scene==0x50 || scene==0x52 || scene==0x54) &&
        Word(first->ram,0x694)==512 && Word(first->ram,0x698)==512;
    /* The flight cutscene stores two repeating cloud planes behind its
     * small camera window. Only the known stock sky may fill the margins. */
    bool story_sky=scene==0x58 && s.epoch_count==1 && StorySkyLayout(first->ram);
    if(scene==0x58 && !story_sky) {
        s.reason="unsupported_story_sky";return false;
    }
    /* The raft uses a finite 256-pixel field over a separate ocean map.
     * The lower rows of the first page repeat open water. The page below
     * that stores other authored material, including another horizon. */
    bool adrift_ocean=scene==0x2F && !physical && s.epoch_count==1 &&
        Word(first->ram,0x692)==256 && Word(first->ram,0x694)==512 &&
        Word(first->ram,0x696)==256 && Word(first->ram,0x698)==512;
    if(scene==0x2F && !adrift_ocean) {
        s.reason="unsupported_adrift_ocean";return false;
    }
    bool authored_window_pan=false;
    if(bounded) {
        PictureBounds bounds;
        if(!RoomPictureBounds(first,camera_x,camera_y,&bounds)) {
            s.reason="unsupported_room_window";return false;
        }
        RoomPictureView(camera_x,camera_y,&bounds);
    } else if(authored) {
        /* A stair can announce the new floor before the camera leaves the
         * old one. Preserve the visible field and HUD on that frame without
         * pulling cells from the destination floor into its margins. */
        authored_window_pan=!RoomPictureView(camera_x,camera_y,&authored_bounds);
    }
    int left=s.view.native_x,top=s.view.native_y;
    const int mosaic=PPU_mosaicSize((&s.base));
    const int stock_mosaic_origin=(s.base.renderFlags&kPpuRenderFlags_NewRenderer)?0:1;
    IogVisualViewport viewport={s.view.world_x,s.view.world_y,
        s.view.width,s.view.height};
    s.detached=s.base;
    memcpy(s.detached.vram,first->vram,sizeof(first->vram));
    memcpy(s.detached.cgram,first->cgram,sizeof(first->cgram));
    IogVisualSource source={s.active_ram,sizeof(s.active_ram),g_snes->cart->rom,
        g_snes->cart->romImageSize,&s.detached,true};
    s.visual.part_count=0;
    if(!live_actors && IogVisualObjectsBuild(&source,&viewport,&s.visual)!=kIogVisualReady) {
        s.reason="unsupported_visual_object";return false;
    }
    *p=s.base;Detach(p);
    memcpy(p->vram,first->vram,sizeof(p->vram));
    int blank[2]={-1,-1};
    int layers=s.absent_secondary?1:2;
    for(int logical=0;logical<layers;logical++) {
        int physical=logical^((first->ram[0x6EE]>>7)&1);
        unsigned base=PPU_bgTileAdr(p,physical);
        for(unsigned tile=0;tile<1024;tile++) {
            unsigned n=0;for(;n<16;n++) if(first->vram[(base+tile*16+n)&32767]) break;
            if(n==16) {blank[logical]=(int)tile;break;}
        }
        if(blank[logical]<0) {s.reason="no_verified_transparent_character";return false;}
    }
    memset(s.output,0,(size_t)s.width*s.height*4);
    bool finite_backdrop=scene==0x47 || scene==0x74;
    /* A plain finite backdrop with its own camera (the ship deck's sky)
     * has no model above its first row. */
    bool flat_head=layers==2 && s.epoch_count==1 && mosaic<=1 && !bounded && !classroom &&
        !tracked_effect && !deferred_raster_effect && !EffectPlaneScene(scene) &&
        !horizon && !wall_bands && !babel_stars && !story_sky && !adrift_ocean &&
        !underside_backdrop && !village_heat && !transition_wave && !water_wave &&
        (Word(first->ram,0x68C)!=Word(first->ram,0x68A) ||
         Word(first->ram,0x690)!=Word(first->ram,0x68E)) &&
        BackdropFlatHead(first,p);
    for(int row=0;row<s.height;row++) {
        int native_y=row-top;
        int scanline=Clamp(native_y,0,223)+1;
        PictureLine *line=&s.lines[scanline];
        PictureEpoch *e=&s.epochs[line->epoch];
        PictureBounds bounds={0,0,0,0};
        if(bounded && ((source_plate && Word(e->ram,0x644)!=scene) ||
           !RoomPictureBounds(e,camera_x,camera_y,&bounds))) {
            s.reason="unsupported_room_window";return false;
        }
        if(authored && !AuthoredWindow(e,&bounds)) {
            s.reason="unsupported_authored_window";return false;
        }
        if(flight_field) bounds.bottom=224;
        uint32_t padding=0;
        if(finite_backdrop) {
            memcpy(p,line->registers,PPU_SAVESTATE_REGS_SIZE);
            padding=FiniteRoomBackdrop(e,p,scene,scanline);
        }
        /* The fixed-height Angel entrance ends at the stock aperture.
         * The allocation below it exposes only the green clear backdrop. */
        if(native_y>=224 && !camera_y && AngelEntranceHasStorageTail(e))
            continue;
        bool castle_marker=CastleMapMarker(e);
        /* Objects were decoded from the exact composition/OAM publication
         * pair. Recolor the one visible row with this raster's palette. */
        const bool stock_bottom_edge = native_y == 223 && (scene == 0x54 || scene == 0x67);
        size_t count=0;
        for(unsigned i=0;i<s.visual.part_count;i++) {
            const IogVisualPart *part=&s.visual.parts[i];
            int py=row-part->y;
            if(py<0 || py>=part->height) continue;
            uint16_t *pixels=s.object_rows[count];
            /* The stock actor writer culls a metasprite part that starts on
             * the last displayed row. Keep that row clear in the stock
             * aperture while continuing to draw the part in the margins. */
            const bool culled_at_stock_edge = stock_bottom_edge && py == 0 && !part->manual;
            /* An actor that stands on another floor of the same map can
             * reach over the edge of this floor's window (bats hanging
             * from the ceiling of the floor below). The stock camera never
             * shows those rows; outside the original field they stay out. */
            bool other_floor=false;
            if(authored && !authored_window_pan && !part->manual && !part->player &&
               part->actor>=0x1000 && part->actor<0x1FC0) {
                int ax=(int16_t)Word(s.active_ram,part->actor+0x14);
                int ay=(int16_t)Word(s.active_ram,part->actor+0x16);
                other_floor=ax<bounds.left || ax>=bounds.right ||
                    ay<bounds.top || ay>=bounds.bottom;
            }
            const bool native_row=native_y>=0 && native_y<224;
            for(int x=0;x<part->width;x++) {
                unsigned index=part->indices[py*part->width+x];
                if(culled_at_stock_edge && part->x+x>=left && part->x+x<left+256)
                    index=0;
                if(other_floor && !(native_row && part->x+x>=left && part->x+x<left+256))
                    index=0;
                pixels[x]=index?(uint16_t)(0x8000|e->cgram[index]):0;
            }
            s.objects[count++]=(PpuExtraObject){part->x,0,part->width,1,
                part->width,part->priority,part->math,0,part->order+1,pixels};
        }
        for(int start=0;start<s.width;start+=Chunk) {
            int width=Clamp(s.width-start,0,Chunk);
            /* Each detached chunk must start on the stock mosaic grid.
             * Discard the prefix after drawing so seams never reset it. */
            int skip=mosaic>1?PositiveMod(start-left,mosaic):0;
            int chunk_x=start-skip;
            unsigned dirty[64],dirty_count=0;
            memcpy(p,line->registers,PPU_SAVESTATE_REGS_SIZE);
            if(KnownWorldWindow(p,e->ram))
                RebaseWindow1(p,left-chunk_x);
            else if(p->windowsel&0xAAAAAAu)
                RebaseFieldWindows(p,left-chunk_x,native_y>=0 && native_y<224);
            uint16_t source_hscroll[2]={p->hScroll[0],p->hScroll[1]};
            uint16_t source_vscroll[2]={p->vScroll[0],p->vScroll[1]};
            if(s.copy_reference) memcpy(p->vram,e->vram,sizeof(p->vram));
            memcpy(p->cgram,e->cgram,sizeof(p->cgram));
            p->screenEnabled[0]&=~4;p->screenEnabled[1]&=~4;
            for(int logical=0;logical<layers;logical++) {
                int physical=logical^((e->ram[0x6EE]>>7)&1);
                int camx=ScrollWorld(e->ram,0x68A+logical*2,p->hScroll[physical]);
                int camy=ScrollWorld(e->ram,0x68E + logical*2,p->vScroll[physical]);
                int wx=camx-left+chunk_x,wy=camy+native_y;
                bool star_plane=logical==1 && babel_stars;
                bool effect=logical==1 && (!bounded || scene==0x85) && !classroom &&
                    (tracked_effect || horizon || EffectPlaneScene(scene));
                if(effect && !raster_anchored && !star_plane) {
                    /* Reframe at this plane's rate. Subtracting the whole
                     * foreground offset makes a quarter-speed/fixed backdrop
                     * slide as the player moves inside a clamped host view.
                     * Live raster scroll still carries drift and HDMA. */
                    wx=camx+(tracked_effect?
                        ProjectEffect(effect_camera.ratio[0],s.view.world_x)-
                        ProjectEffect(effect_camera.ratio[0],camera_x):
                        EffectProjection(scene,false,s.view.world_x)-
                        EffectProjection(scene,false,camera_x))+chunk_x;
                    wy=camy+(tracked_effect?
                        ProjectEffect(effect_camera.ratio[1],s.view.world_y)-
                        ProjectEffect(effect_camera.ratio[1],camera_y):
                        EffectProjection(scene,true,s.view.world_y)-
                        EffectProjection(scene,true,camera_y))+row;
                }
                if(logical==1&&horizon) {
                    /* This finite sky/mountain plate has its own screen row.
                     * Use the actual producer's fractional phase and band,
                     * not the foreground's clamped native_y. */
                    wy=camy+row;
                    if(wy>=255&&flat_horizon_tail)wy=254;
                    uint16_t phase;
                    if(IogRasterParallaxSample(&horizon_model,wy+1,s.view.world_x,&phase))
                        wx=(int)phase+chunk_x;
                }
                if(logical==1&&wall_bands) {
                    /* Great Wall's sky/wall bands have different X rates at
                     * each background world height. The expanded top/bottom
                     * must select their own band, not clamp to a native row. */
                    uint16_t phase;
                    /* Keep the approach, lair and passage aligned with their
                     * captured field when the expanded view pulls back. */
                    if(IogRasterParallaxSample(&wall_model,wy+1,
                            wall_field_phase?wall_source_camera:s.view.world_x,&phase))
                        wx=(int)phase+chunk_x-(wall_field_phase?left:0);
                }
                if(logical==1&&(freejia_wave||mansion_fog||larai_mist||
                   (star_plane&&!babel_victory_wave&&!babel_victory_setup))&&
                   (native_y<0 || native_y>=224)) {
                    int period=larai_mist?LaraiMistPeriod:RingWavePeriod;
                    int phase=PositiveMod(native_y,period)+1;
                    unsigned scroll=Word(s.lines[phase].registers,offsetof(Ppu,hScroll)+physical*2);
                    int wave_x=ScrollWorld(e->ram,0x68C,scroll);
                    wx+=wave_x-camx;
                }
                if (logical == 1 && water_wave && (native_y < 0 || native_y >= 224)) {
                    int phase = (native_y % WaterWavePeriod + WaterWavePeriod) % WaterWavePeriod + 1;
                    const uint8_t *regs = s.lines[phase].registers;
                    int wave_x = ScrollWorld(e->ram, 0x68C, Word(regs, offsetof(Ppu, hScroll) + physical * 2));
                    int wave_y = ScrollWorld(e->ram, 0x690, Word(regs, offsetof(Ppu, vScroll) + physical * 2));
                    wx += wave_x - camx;
                    wy += wave_y - camy;
                }
                if(logical==1 && dao_heat && (native_y<0 || native_y>=224)) {
                    int phase=(native_y%DaoHeatPeriod+DaoHeatPeriod)%DaoHeatPeriod+1;
                    unsigned scroll=Word(s.lines[phase].registers,offsetof(Ppu,hScroll));
                    wx+=ScrollWorld(e->ram,0x68C,scroll)-camx;
                }
                if(village_heat && (native_y<0 || native_y>=224)) {
                    int phase=(native_y%VillageHeatPeriod+VillageHeatPeriod)%VillageHeatPeriod+1;
                    unsigned scroll=Word(s.lines[phase].registers,offsetof(Ppu,vScroll)+physical*2);
                    wy+=ScrollWorld(e->ram,0x68E + logical*2,scroll)-camy;
                }
                if(transition_wave && transition_wave_repeats && (native_y<0 || native_y>=224)) {
                    /* The final two hardware lines hold sample 222. Begin
                     * the lower extension at the next actual wave sample. */
                    int sample=native_y<0?native_y+1:native_y-1;
                    unsigned phase=(unsigned)sample&(StockWavePeriod-1);
                    unsigned scroll=Word(e->ram,transition_wave+2*phase);
                    wx+=ScrollWorld(e->ram,0x68A + logical*2,scroll)-camx;
                }
                bool mosaic_layer=mosaic>1 && PPU_mosaicEnabled(p,physical);
                if(mosaic_layer)
                    wy-=PositiveMod(native_y+1-stock_mosaic_origin,mosaic);
                /* Clamp after quantizing. Otherwise the expanded sky above
                 * the raster can wrap to ocean tiles during the mosaic. */
                if(logical==1 && adrift_ocean && native_y<0 && wy<0) wy=0;
                if(logical==1 && flat_head && native_y<0 && wy<-1) wy=-1;
                p->hScroll[physical]=(uint16_t)wx&1023;
                p->vScroll[physical]=(uint16_t)(wy+(mosaic_layer?1:0))&1023;
                if(star_plane) continue;
                /* Layer-1 position bypass deliberately performs no map
                 * streaming. Solid Arm's animated backdrop lives in the
                 * uploaded VRAM ring; rebuilding it from allocation data
                 * replaces the animation with unrelated map cells. */
                if(effect && ((tracked_effect && effect_camera.uploaded_ring) ||
                   (scene==0xEA && (e->ram[0x6EF]&4)))) continue;
                int sample_y=wy+1;
                if(logical==1 && adrift_ocean && sample_y>=256)
                    sample_y=160+((sample_y-160)%32);
                for(int x=wx&~7;x<wx+width+skip;x+=8) {
                    /* BG sampling uses hardware line1 while OBJ evaluation
                     * uses line0 for the same first output row. */
                    int sample_x=x;
                    bool finite_horizon=logical==1&&horizon;
                    bool finite_wall=logical==1&&wall_bands;
                    if(finite_horizon||finite_wall) {
                        int repeat_width=finite_wall?wall_model.width:512;
                        sample_x%=repeat_width;if(sample_x<0)sample_x+=repeat_width;
                    }
                    bool repeat=(adrift_ocean && logical==1) || story_sky || ((effect || (logical==1 && underside_backdrop)) &&
                        !finite_horizon && !finite_wall && (!bounded || scene==0x85) && !classroom);
                    unsigned tile=MapTile(e,logical,sample_x,sample_y,repeat);
                    if(tile==0xFFFFFFFFu) tile=(unsigned)blank[logical];
                    /* Overlapping authentic cells use the actual uploaded
                     * VRAM entry, including partially updated scroll strips. */
                    int source_y=wy-camy;
                    int source_x=camx;
                    if(finite_wall) {
                        uint16_t phase;
                        if(IogRasterParallaxSample(&wall_model,wy+1,wall_source_camera,&phase))source_x=phase;
                    }
                    if(source_y>=-(int)mosaic_layer&&source_y<224 && x+8>source_x && x<source_x+256) {
                        unsigned tx=((unsigned)source_hscroll[physical]+(x-source_x))>>3;
                        unsigned ty=((unsigned)source_vscroll[physical]+source_y+1)>>3;
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
            for(size_t i=0;i<count;i++) s.objects[i].x-=chunk_x;
            PpuSetExtraObjects(p,s.objects,count);
            IogWorldPixelsDrawLine(p,0);
            if(mosaic>1) p->mosaicStartLine=0;
            IogWorldPixelsDrawLine(p,1);
            uint32_t composite[Chunk];
            bool cloud_sky=((scene==0x55 && !bounded && !authored &&
                Word(e->ram,0x694)==512 && Word(e->ram,0x698)==512)||horizon||adrift_ocean) &&
                (p->screenEnabled[0]&(1u<<(1^((e->ram[0x6EE]>>7)&1))));
            bool backdrop_only=cloud_sky || babel_stars;
            if(backdrop_only) {
                /* These scenes have a separate cloud or star plane. Draw
                 * only that plane outside terrain bounds; unmasking the full
                 * composite would expose spare floor pages and off-map actors.
                 * Preserve the ordinary composite everywhere inside the room
                 * and across the complete authoritative native field. */
                memcpy(composite,s.row+skip,(size_t)width*4);
                unsigned terrain=(e->ram[0x6EE]>>7)&1;
                p->screenEnabled[0]&=(uint8_t)~((1u<<terrain)|16u);
                p->screenEnabled[1]&=(uint8_t)~((1u<<terrain)|16u);
                PpuSetExtraObjects(p,NULL,0);
                IogWorldPixelsDrawLine(p,0);
                if(mosaic>1) p->mosaicStartLine=0;
                IogWorldPixelsDrawLine(p,1);
            }
            /* Only tilemap entries were changed on the owned picture. All
             * epochs have identical VRAM (checked above), so restoring these
             * bounded cells replaces a full64KB copy for every chunk/row. */
            for(unsigned n=0;n<dirty_count;n++)
                p->vram[dirty[n]]=first->vram[dirty[n]];
            for(size_t i=0;i<count;i++) s.objects[i].x+=chunk_x;
            for(int x=0;x<width;x++) {
                int worldx=viewport.world_x+start+x,worldy=viewport.world_y+row;
                bool native_pixel=native_y>=0&&native_y<224&&
                    start+x>=left&&start+x<left+256;
                /* Preserve the actual uploaded tilemap cells across the
                 * whole authoritative field during shake. This may include
                 * a hardware-wrapped edge; expanded outside-map space is
                 * still padding, never guessed or repeated terrain. */
                /* The map fetch samples the following row. A final authored
                 * row at the edge must not expose the next page's tiles. */
                int picture_bottom=bounds.bottom-(authored?1:0);
                /* The same holds for a whole map that ends inside the view:
                 * its last row would fetch the row after the map and show
                 * the backdrop colour as a line above the padding. */
                int map_bottom=(int)Word(e->ram,0x696)-(s.view.padding_bottom?1:0);
                bool inside=(bounded||authored)?(native_pixel || (!authored_window_pan && worldx>=bounds.left && worldx<bounds.right &&
                   worldy>=bounds.top && worldy<picture_bottom)):
                   classroom?OriginalClassroomPixel(e,worldx,worldy):
                   (native_pixel||(worldx>=0&&worldx<(int)Word(e->ram,0x692)&&
                   worldy>=0&&worldy<map_bottom));
                if(castle_marker && !native_pixel && worldx>=480 && worldy>=735)
                    inside=false;
                if(inside || backdrop_only || story_sky)
                    s.output[row*s.width+start+x]=backdrop_only&&inside?composite[x]:s.row[x+skip];
                else if(padding)
                    s.output[row*s.width+start+x]=padding;
            }
        }
    }
    if(s.sky_field) {s.reason="ready_story_sky_field";return true;}
    if(s.stock_actor_field) {
        s.reason=s.restored_actor_field?"ready_restored_actor_field":"ready_stock_actor_field";
        return true;
    }
    /* Keep HUD physical size while the world camera shows a larger extent.
     * It is an independently extracted original UI plane, not world terrain. */
    s.hud_layered=snes_ovl_frame_layer_available()!=0;
    if(!s.hud_layered) CompositeHud((uint8_t *)s.output,s.width*4);
    s.reason=authored_window_pan?"ready_authored_window_pan":freejia_wave?"ready_freejia_wave":
        larai_mist?"ready_larai_mist":
        water_wave?"ready_water_wave":
        dao_heat?"ready_dao_heat":
        village_heat?"ready_village_heat":
        transition_wave?"ready_stock_transition_wave":
        babel_victory_setup?"ready_babel_victory_setup":
        mansion_fog?"ready_mansion_fog":
        dark_space_stars?"ready_dark_space_starfield":
        babel_stars?"ready_babel_starfield":
        deferred_raster_effect && !EffectPlaneScene(scene)?"ready_legacy_raster_effect":"ready";return true;
}

void IogWorldEndRaster(uint32_t resume_pc,unsigned hdma_lines,unsigned irq_count)
{
    if(!s.enabled && !s.audit) return;
    ++s.frame;s.complete=s.enabled && (s.fixed_plate || RenderWorld());
    memset(&s.wake,0,sizeof(s.wake));
    if(s.complete && !s.fixed_plate && !s.mode7 && !s.sky_field && !s.stock_actor_field &&
       s.view.width==s.width && s.view.height==s.height &&
       s.view.padding_left<=s.view.native_x && s.view.padding_top<=s.view.native_y &&
       s.view.padding_left+s.view.padding_right+256<=s.view.width &&
       s.view.padding_top+s.view.padding_bottom+224<=s.view.height) {
        /* Padding is outside the map: nothing there is shown as terrain. */
        s.wake.left=(int16_t)(s.view.native_x-s.view.padding_left);
        s.wake.top=(int16_t)(s.view.native_y-s.view.padding_top);
        s.wake.width=(uint16_t)(s.view.width-s.view.padding_left-s.view.padding_right);
        s.wake.height=(uint16_t)(s.view.height-s.view.padding_top-s.view.padding_bottom);
        if(s.wake.left+256>s.wake.width || s.wake.top+224>s.wake.height)
            memset(&s.wake,0,sizeof(s.wake));
    }
    if(!s.enabled) {s.reason="reference_renderer";s.width=256;s.height=224;}
    if(s.audit) {
        const CpuState *c=&g_cpu;
        fprintf(s.audit,"{\"frame\":%u,\"resume_pc\":%u,\"A\":%u,\"X\":%u,\"Y\":%u,\"S\":%u,\"D\":%u,\"DB\":%u,\"PB\":%u,\"P\":%u,\"E\":%u,\"M\":%u,\"IX\":%u,\"N\":%u,\"V\":%u,\"Z\":%u,\"C\":%u,\"I\":%u,\"DF\":%u,\"cycles\":%llu,\"master_cycles\":%llu,\"hdma_lines\":%u,\"irq_count\":%u,\"simulation_width\":256,\"simulation_height\":224,\"width\":%d,\"height\":%d,\"compose\":%llu,\"publish\":%llu,\"epochs\":%d,\"parts\":%u,\"ready\":%s,\"reason\":\"%s\"}\n",
            s.frame,resume_pc,c->A,c->X,c->Y,c->S,c->D,c->DB,c->PB,c->P,
            c->emulation,c->m_flag,c->x_flag,c->_flag_N,c->_flag_V,c->_flag_Z,
            c->_flag_C,c->_flag_I,c->_flag_D,(unsigned long long)c->cycles,
            (unsigned long long)c->master_cycles,hdma_lines,irq_count,s.width,s.height,
            (unsigned long long)s.compose_sequence,(unsigned long long)s.publish_sequence,
            s.epoch_count,s.complete&&!s.fixed_plate?s.visual.part_count:0,s.complete?"true":"false",s.reason?s.reason:"uninitialized");
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
        /* A refused frame records the display state its profile would need. */
        if(s.enabled && !s.complete && g_ppu && g_snes) {
            const Ppu *p=g_ppu;const uint8_t *ram=g_snes->ram;
            fprintf(s.audit,"{\"kind\":\"refused\",\"frame\":%u,\"scene\":%u,\"pending\":%u,\"layout\":%u,"
                "\"size\":[%u,%u,%u,%u],\"camera\":[%d,%d],\"bgmode\":%u,\"mosaic\":%u,\"windowsel\":%u,"
                "\"windowed\":[%u,%u],\"maps\":[%u,%u,%u],\"main\":%u,\"sub\":%u,\"cgwsel\":%u,"
                "\"cgadsub\":%u,\"hdma\":%u,\"blank\":%u,\"brightness\":%u,"
                "\"oam_differs\":[%u,%u,%u,%u],\"objects\":[%u,%u,%u]}\n",
                s.frame,Word(ram,0x644),Word(ram,0x642),Word(ram,0x6EE),
                Word(ram,0x692),Word(ram,0x696),Word(ram,0x694),Word(ram,0x698),
                (int16_t)Word(ram,0x68A),(int16_t)Word(ram,0x68E),p->bgmode,p->mosaic,
                (unsigned)p->windowsel,p->screenWindowed[0],p->screenWindowed[1],
                p->bgXsc[0],p->bgXsc[1],p->bgXsc[2],p->screenEnabled[0],p->screenEnabled[1],
                p->cgwsel,p->cgadsub,(unsigned)g_snesrecomp_last_hdmaen,
                PPU_forcedBlank(p)?1u:0u,(unsigned)p->inidisp&15u,
                s.unpaired.staging,s.unpaired.previous,s.unpaired.composed,s.unpaired.pending,
                (unsigned)s.visual.status,(unsigned)s.visual.actor_count,(unsigned)s.visual.hidden_actors);
        }
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
    if(s.complete && s.fixed_plate && *(const uint8_t*)&endian==1)
        return PacketFile(base,".field.bgra",field,256*224*4);
    if(s.complete && s.stock_actor_field && *(const uint8_t*)&endian==1)
        return PacketFile(base,".field.bgra",field,256*224*4) &&
            PacketFile(base,".hud.bgra",s.hud,sizeof(s.hud));
    if(s.mode7) {
        if(!s.valid || !s.epoch_count || *(const uint8_t*)&endian!=1) return false;
        bool ok=PacketFile(base,".mode7.field.bgra",field,256*224*4);
        ok=PacketFile(base,".mode7.parameters.bin",s.epochs[s.lines[0].epoch].ram+0xB0,0x20) && ok;
        if(s.complete) ok=PacketFile(base,".mode7.plane.bgrx",s.output,
            (size_t)s.width*s.height*4) && ok;
        char path[4096];int n=snprintf(path,sizeof(path),"%s.mode7.epochs.bin",base);
        if(n<0 || (size_t)n>=sizeof(path))return false;
        FILE *f=fopen(path,"wb");if(!f)return false;
        for(int i=0;i<s.epoch_count;i++)
            if(fwrite(s.epochs[i].vram,1,65536,f)!=65536 ||
               fwrite(s.epochs[i].cgram,1,512,f)!=512)ok=false;
        if(fclose(f))ok=false;
        n=snprintf(path,sizeof(path),"%s.mode7.json",base);
        if(n<0 || (size_t)n>=sizeof(path))return false;
        f=fopen(path,"wb");if(!f)return false;
        if(fprintf(f,"{\"schema\":\"iog-mode7-plane-source-v1\",\"frame\":%u,\"ready\":%s,\"composition_paired\":false,\"width\":%d,\"height\":%d,\"native_x\":%u,\"native_y\":%u,\"perspective_validated\":%s,\"initial_divisor\":%u,\"increment\":%u,\"cosine\":%d,\"sine\":%d,\"epoch_bytes\":66048,\"epochs\":%d,\"lines\":[",s.frame,s.complete?"true":"false",s.width,s.height,s.view.native_x,s.view.native_y,s.mode7_perspective?"true":"false",s.mode7_parameters.initial_divisor,s.mode7_parameters.increment,s.mode7_parameters.cosine,s.mode7_parameters.sine,s.epoch_count)<0)ok=false;
        for(int line=0;line<=224;line++) {
            if(fprintf(f,"%s{\"epoch\":%u,\"regs\":\"",line?",":"",s.lines[line].epoch)<0)ok=false;
            for(unsigned k=0;k<PPU_SAVESTATE_REGS_SIZE;k++)
                if(fprintf(f,"%02x",s.lines[line].registers[k])<0)ok=false;
            if(fprintf(f,"\"}")<0)ok=false;
        }
        if(fprintf(f,"],\"complete\":%s}\n",ok?"true":"false")<0)ok=false;
        if(fclose(f))ok=false;
        return ok;
    }
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
    if(s.complete && s.fixed_plate && 256*height/224<=width) {
        DrawCenteredField(dst,pitch,field,width,256*height/224,224,height);
    } else if(s.complete && !s.fixed_plate && width==s.width && height==s.height) {
        for(int y=0;y<height;y++) memcpy(dst+y*pitch,s.output+y*width,width*4);
        if(s.hud_layered && !s.sky_field && !s.stock_actor_field && !s.mode7) PresentHud(dst,pitch);
        if(s.sky_field || s.stock_actor_field) {
            /* Keep live objects but replace visible source HUD pixels with
             * verified scenery before drawing BG3 at its usual display scale.
             * A different source color can be an object over the HUD. */
            for(int y=0;y<224;y++) for(int x=0;x<256;x++) {
                int index=y*256+x;
                uint32_t hud=s.hud[index];
                if(!(hud>>24) || memcmp(field+index*4,&hud,3))
                    memcpy(dst+(y+s.view.native_y)*pitch+(x+s.view.native_x)*4,
                        field+index*4,4);
            }
            PresentHud(dst,pitch);
        } else if(s.mode7) {
            int left=(width-256)/2,top=(height-224)/2;
            int map_rows=s.mode7_split?s.mode7_split-1:224;
            int panel_rows=(224-map_rows)*height/224;
            int panel_top=top+map_rows;
            int panel_width=256*height/224;
            bool scale_panel=panel_width<=width && panel_top+panel_rows<=height &&
                Mode7DestinationPanel(field,map_rows);
            int source_rows=scale_panel?map_rows:224;
            if(s.mode7_filtered && !scale_panel) {
                /* The filtered plane already covers the field. Restore only
                 * what the point-sampled plane does not explain: objects. */
                for(int y=0;y<224;y++) for(int x=0;x<256;x++) {
                    int index=y*256+x;
                    if(memcmp(field+index*4,&s.mode7_exact[index],3))
                        memcpy(dst+(y+top)*pitch+(x+left)*4,field+index*4,4);
                }
            } else
            for(int y=0;y<source_rows;y++) memcpy(dst+(y+top)*pitch+left*4,field+y*256*4,256*4);
            if(scale_panel)
                DrawCenteredField(dst+panel_top*pitch,pitch,field+map_rows*256*4,width,
                                  panel_width,224-map_rows,panel_rows);
        }
    } else {
        for(int y=0;y<height;y++) memset(dst+y*pitch,0,width*4);
        /* A field that is one flat colour under its text (the blue screen
         * of the prison entry, a white flash) has no picture to frame.
         * Continue that colour over the whole view instead of showing a
         * coloured box; the field itself is still drawn unchanged below. */
        {
            const uint8_t *wash=NULL;bool flat=true;int plain=0;
            for(int i=0;i<256*224 && flat;i++) {
                if(s.hud[i]>>24) continue;
                if(!wash) wash=field+i*4;
                else flat=!memcmp(wash,field+i*4,3);
                plain++;
            }
            if(flat && wash && plain>=256*224/2 && (wash[0]|wash[1]|wash[2]))
                for(int y=0;y<height;y++) for(int x=0;x<width;x++)
                    memcpy(dst+y*pitch+x*4,wash,4);
        }
        /* Keep the same world-pixel scale across supported rooms, menus and
         * fallback effects. Filling the taller host frame magnifies the old
         * field and makes every unsupported doorway produce a zoom jump. */
        int left=(width-256)/2,top=(height-224)/2;
        for(int y=0;y<224;y++) memcpy(dst+(y+top)*pitch+left*4,
            field+y*256*4,256*4);
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
