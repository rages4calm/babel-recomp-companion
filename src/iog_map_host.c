/* Title-owned bindings for the shared paused Companion and native map helpers.
 * This observes actual frames only; it never changes game flags or inputs. */
#include "iog_map_host.h"
#include "iog_map_runtime.h"
#include "iog_map_ui.h"
#include "common_rtl.h"
#include "common_cpu_infra.h"
#include "cpu_state.h"
#include "sha256.h"
#include "snes/snes.h"
#include "snes/cart.h"
#include "snes_overlay_draw.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#ifdef _WIN32
#include <direct.h>
#else
#include <sys/stat.h>
#endif
extern Snes *g_snes;

static IogMapRuntime *runtime;
static IogMapUi ui;
static bool initialized,opened,gamepad;
static unsigned suspended;
static uint32_t previous_pad,last_ticks;
static uint32_t canvas[598*336];
static unsigned frame_number;
static FILE *audit;

static unsigned Word(const uint8_t *r,unsigned n)
{return r[n]|(unsigned)r[n+1]<<8;}
static void AuditEvent(const char *event)
{
    if(!audit||!g_snes||!g_snes->ram)return;
    uint8_t digest[32];char hex[65];sha256_compute(g_snes->ram,131072,digest);
    for(unsigned n=0;n<32;n++)snprintf(hex+n*2,3,"%02x",digest[n]);
    fprintf(audit,"{\"event\":\"%s\",\"frame\":%u,\"master_cycles\":%llu,\"wram_sha256\":\"%s\"}\n",
        event,frame_number,(unsigned long long)g_cpu.master_cycles,hex);
    fflush(audit);
}
static void Initialize(void)
{
    if(initialized)return;
    initialized=true;IogMapUiInit(&ui);
    /* Match this title's SRAM directory on a fresh portable installation.
     * Runtime creates only its own guarded maps child. */
#ifdef _WIN32
    (void)_mkdir("saves");
#else
    (void)mkdir("saves",0700);
#endif
    runtime=IogMapRuntimeCreate("saves");
    const char *path=getenv("IOG_MAP_AUDIT");
    if(path&&*path)audit=fopen(path,"wb");
}
void IogMapHostSuspend(bool pause)
{if(pause)suspended++;else if(suspended)suspended--;}
void IogMapHostReset(void)
{
    if(suspended||RtlSpeculativeFrame())return;
    IogMapHostClose();
    if(runtime){IogMapRuntimeFlush(runtime);IogMapRuntimeUpdate(runtime,NULL);}
}
void IogMapHostShutdown(void)
{
    if(runtime)IogMapRuntimeDestroy(runtime);
    runtime=NULL;
    if(audit)fclose(audit);
    audit=NULL;initialized=false;opened=false;
}
static bool Digest(const char *hex,uint8_t out[32])
{
    if(!hex||strlen(hex)!=64)return false;
    for(unsigned n=0;n<32;n++){
        unsigned value=0;
        for(unsigned k=0;k<2;k++){
            char c=hex[n*2+k];
            if(c>='0'&&c<='9')value=value*16+(unsigned)(c-'0');
            else if(c>='a'&&c<='f')value=value*16+(unsigned)(c-'a'+10);
            else return false;
        }
        out[n]=(uint8_t)value;
    }
    return true;
}
#ifndef IOG_RECEIVED_REFERENCE
static bool StableAssets(const uint8_t *ram)
{
    const Cart *cart=g_snes?g_snes->cart:NULL;
    if(!cart||!cart->rom||cart->romImageSize!=2097152)return false;
    const unsigned slots[]={0x678,0x67e,0x67b,0x681};
    unsigned count=((ram[0x6ef]&1)||Word(ram,0x644)==8)?4:2;
    for(unsigned n=0;n<count;n++){
        unsigned at=slots[n],bank=ram[at+2],address=Word(ram,at);
        if(bank<0x80||((bank&0x3fu)<<16)+address>=cart->romImageSize)return false;
    }
    return true;
}
#endif
void IogMapHostFrame(bool verified,const char *content)
{
    if(suspended||RtlSpeculativeFrame())return;
    Initialize();++frame_number;
    if(!runtime)return;
    IogMapRuntimeFrame f;memset(&f,0,sizeof(f));
    const uint8_t *r=g_snes?g_snes->ram:NULL;
    bool valid=verified&&r&&g_ppu&&Digest(content,f.content_sha256)&&
        Word(r,0x9aa)&&Word(r,0x654)==15&&!Word(r,0x642)&&
        !(Word(r,0x9ec)&0x6000)&&(Word(r,0x644)<0xe5||Word(r,0x644)==0xea)&&
        (g_ppu->bgmode&7)==1&&(g_ppu->inidisp&0x8f)==15&&!(r[0x6ef]&8);
    if(valid){
        unsigned w=Word(r,0x692),h=Word(r,0x696);
        unsigned x=Word(r,0x6d6),y=Word(r,0x6d8),right=Word(r,0x6da),bottom=Word(r,0x6de);
        unsigned physical=(r[0x6ee]>>7)&1;
        valid=w>=256&&h>=256&&w<=4096&&h<=4096&&!(w&255)&&!(h&255)&&
            x<right&&y<bottom&&right<=w&&bottom<=h&&
            !((x|y|right|bottom)&15)&&right-x>=256&&bottom-y>=224&&
            Word(r,0x69e)==0xa000&&Word(r,0x6ae)==0x2000&&
            Word(r,0x69a)==(w>>8)*(h>>8)*256&&
            0xa000u+Word(r,0x69a)<=65536&&
            !PPU_bigTiles(g_ppu,physical)&&!PPU_bgTilemapHigher(g_ppu,physical)&&
            PPU_bgTilemapAdr(g_ppu,physical)==Word(r,0x6ba);
        f.ram=r;f.ram_bytes=131072;f.ppu=g_ppu;f.scene=(uint16_t)Word(r,0x644);
        f.authored=(IogMapRuntimeRect){x,y,right-x,bottom-y};
        f.camera_x=(int16_t)Word(r,0x68a);f.camera_y=(int16_t)Word(r,0x68e);
        f.player_x=(int16_t)Word(r,0x9a2);f.player_y=(int16_t)Word(r,0x9a4);
        f.profile_verified=valid;
        /* Both qualified classroom adapters use aligned scenery planes. The
         * floor is real secondary artwork, not an independently moving sky. */
        f.aligned_secondary_source=f.scene==8&&Word(r,0x68a)==Word(r,0x68c)&&
            Word(r,0x68e)==Word(r,0x690)&&(g_ppu->screenEnabled[0]&3)==3&&
            (g_ppu->hScroll[physical]&1023)==(Word(r,0x68a)&1023)&&
            (g_ppu->hScroll[physical^1]&1023)==(Word(r,0x68c)&1023)&&
            (g_ppu->vScroll[physical]&1023)==(Word(r,0x68e)&1023)&&
            (g_ppu->vScroll[physical^1]&1023)==(Word(r,0x690)&1023);
        if(f.scene==8&&!f.aligned_secondary_source)valid=false;
#ifndef IOG_RECEIVED_REFERENCE
        /* These are the actual scene loader's source-cache slots, not a hash
         * of mutable door tiles. A changed authored source still gets its own
         * journal while normal scripted map edits retain discovery. */
        valid=valid&&StableAssets(r);
        f.stable_source_identity=valid;
        f.profile_verified=valid;
#endif
    }
    bool ready=IogMapRuntimeUpdate(runtime,valid?&f:NULL);
    if(!ready)IogMapHostClose();
    if(audit){
        IogMapRuntimeStatus status;IogMapRuntimeGetStatus(runtime,&status);
        char layout[65];for(unsigned n=0;n<32;n++)snprintf(layout+n*2,3,"%02x",status.layout_sha256[n]);
        fprintf(audit,"{\"frame\":%u,\"ready\":%s,\"scene\":%u,\"player\":[%d,%d],\"explored\":%zu,\"writes\":%llu,\"loads\":%llu,\"layout\":\"%s\",\"reason\":\"%s\"}\n",
            frame_number,ready?"true":"false",status.scene,status.player_cell_x,status.player_cell_y,
            status.explored_cells,(unsigned long long)status.persistent_writes,
            (unsigned long long)status.persistent_loads,layout,status.reason?status.reason:"unsupported_host_frame");
        fflush(audit);
    }
}
bool IogMapHostAvailable(void)
{
    IogMapRuntimeStatus status;
    if(!runtime)return false;
    IogMapRuntimeGetStatus(runtime,&status);return status.frame_valid;
}
void IogMapHostRadarToggle(void)
{
    Initialize();IogMapUiInput input={0};input.toggle_radar=true;
    IogMapUiHandleInput(&ui,&input);
}
static bool Draw(uint8_t *dst,size_t bytes,size_t pitch,int w,int h)
{
    IogMapViewSource source;
    if(!runtime||!IogMapRuntimeGetViewSource(runtime,&source))return false;
    IogMapUiMetadata metadata={true,false,gamepad,0};
    return IogMapUiDraw(&ui,dst,bytes,pitch,(unsigned)w,(unsigned)h,&source,&metadata);
}
void IogMapHostDrawRadar(uint8_t *dst,size_t pitch,int w,int h)
{
    if(opened||ui.full||w<256||h<160||pitch>SIZE_MAX/(size_t)h)return;
    (void)Draw(dst,pitch*(size_t)h,pitch,w,h);
}
int IogMapHostOpen(void)
{
    if(!IogMapHostAvailable())return 0;
    if(!ui.full){IogMapUiInput in={0};in.toggle_full=true;IogMapUiHandleInput(&ui,&in);}
    opened=true;previous_pad=~0u;last_ticks=0;AuditEvent("map_open");return 1;
}
void IogMapHostClose(void)
{
    if(opened)AuditEvent("map_close");
    IogMapUiInput in={0};in.close=true;IogMapUiHandleInput(&ui,&in);opened=false;
}
bool IogMapHostIsOpen(void){return opened;}
void IogMapHostPointer(int x,int y,int down)
{
    if(!opened)return;
    gamepad=false;IogMapUiPointer(&ui,x,y,down!=0,598,336);
    AuditEvent("map_pointer");
    if(!ui.full)opened=false;
}
void IogMapHostNav(uint32_t pad,uint32_t ticks)
{
    if(!opened)return;
    uint32_t pressed=pad&~previous_pad;previous_pad=pad;
    unsigned delta=last_ticks?ticks-last_ticks:16;last_ticks=ticks;
    IogMapUiInput in={0};in.dt_ms=delta;
    in.pan_x=(!!(pad&SNES_PAD_RIGHT))-(!!(pad&SNES_PAD_LEFT));
    in.pan_y=(!!(pad&SNES_PAD_DOWN))-(!!(pad&SNES_PAD_UP));
    in.zoom_out=!!(pressed&SNES_PAD_L);in.zoom_in=!!(pressed&SNES_PAD_R);
    in.recenter=!!(pressed&SNES_PAD_Y);in.close=!!(pressed&SNES_PAD_B);
    if(pad)gamepad=true;
    if(pad)AuditEvent("map_pad");
    IogMapUiHandleInput(&ui,&in);if(in.close)opened=false;
}
void IogMapHostKey(int key,int repeat)
{
    if(!opened)return;
    AuditEvent("map_key");
    gamepad=false;IogMapUiInput in={0};in.dt_ms=100;
    switch(key){
    case 27:case 'm':if(!repeat)in.close=true;break;
    case '+':case '=':in.zoom_in=true;break;
    case '-':in.zoom_out=true;break;
    case 0x4000004a:case 'c':in.recenter=true;break;
    case 0x40000050:in.pan_x=-1;break;
    case 0x4000004f:in.pan_x=1;break;
    case 0x40000052:in.pan_y=-1;break;
    case 0x40000051:in.pan_y=1;break;
    default:break;
    }
    IogMapUiHandleInput(&ui,&in);if(in.close)opened=false;
}
int IogMapHostImage(const uint32_t **pixels,int *w,int *h)
{
    if(!opened||!pixels||!w||!h)return 0;
    memset(canvas,0,sizeof(canvas));
    if(!Draw((uint8_t*)canvas,sizeof(canvas),598*4,598,336))return 0;
    *pixels=canvas;*w=598;*h=336;
    /* One diagnostic picture of the real paused map, never a separate fake UI. */
    static bool written;
    const char *output=getenv("IOG_MAP_OUTPUT");
    if(!written&&output&&*output){
        FILE *file=fopen(output,"wb");
        if(file){
            bool ok=fprintf(file,"P6\n598 336\n255\n")>0;
            for(unsigned n=0;n<598*336&&ok;n++){
                uint32_t p=canvas[n];uint8_t rgb[3]={(uint8_t)(p>>16),(uint8_t)(p>>8),(uint8_t)p};
                ok=fwrite(rgb,1,3,file)==3;
            }
            if(fclose(file))ok=false;written=ok;
        }
    }
    return 1;
}
