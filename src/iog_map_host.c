/* Title-owned bindings for the shared paused Companion and native map helpers.
 * This observes actual frames only; it never changes game flags or inputs. */
#include "iog_map_host.h"
#include "iog_map_runtime.h"
#include "iog_map_ui.h"
#include "iog_map_preferences.h"
#include "common_rtl.h"
#include "common_cpu_infra.h"
#include "cpu_state.h"
#include "sha256.h"
#include "snes/snes.h"
#include "snes/cart.h"
#include "snes_overlay_draw.h"
#include "mod_runtime.h"
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
static bool initialized,opened,gamepad=true;
static bool controls_open,preferences_saved=true,input_held,input_consumed;
static unsigned controls_row;
static unsigned suspended;
static uint32_t previous_pad,last_ticks;
static uint32_t canvas[598*336];
static unsigned frame_number;
static FILE *audit;
static const char *const control_names[IOG_MAP_BUTTON_COUNT]={"A","B","X","Y","L","R"};
static const uint32_t control_bits[IOG_MAP_BUTTON_COUNT]={SNES_PAD_A,SNES_PAD_B,
    SNES_PAD_X,SNES_PAD_Y,SNES_PAD_L,SNES_PAD_R};
#if SNESRECOMP_ENABLE_MODS
static const char *const control_options[IOG_MAP_CONTROL_COUNT]={
    "zoom_in","zoom_out","center","radar_button","back"};
#endif
static const int control_defaults[IOG_MAP_CONTROL_COUNT]={5,4,3,2,1};
static int controls[IOG_MAP_CONTROL_COUNT];
static void LoadControls(void)
{
    memcpy(controls,control_defaults,sizeof(controls));
#if SNESRECOMP_ENABLE_MODS
    if(snes_mod_runtime_feature_enabled_c("iog.enhancements","map_controls")<=0)return;
    unsigned used=0;
    for(int a=0;a<IOG_MAP_CONTROL_COUNT;a++){
        char value[16]={0};int button=control_defaults[a];
        if(snes_mod_runtime_feature_option_value_c("iog.enhancements","map_controls",
            control_options[a],value,sizeof(value))>0)
            for(int b=0;b<IOG_MAP_BUTTON_COUNT;b++)
                if(!strcmp(value,control_names[b]))button=b;
        if(used&(1u<<button)){
            button=control_defaults[a];
            if(used&(1u<<button))for(button=0;used&(1u<<button);button++){}
        }
        controls[a]=button;used|=1u<<button;
    }
    char value[16]={0};
    if(snes_mod_runtime_feature_option_value_c("iog.enhancements","map_controls",
        "radar",value,sizeof(value))>0&&!strcmp(value,"off"))ui.radar=false;
#endif
}

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
    initialized=true;IogMapUiInit(&ui);LoadControls();
    /* Match this title's SRAM directory on a fresh portable installation.
     * Runtime creates only its own guarded maps child. */
#ifdef _WIN32
    (void)_mkdir("saves");
#else
    (void)mkdir("saves",0700);
#endif
    runtime=IogMapRuntimeCreate("saves");
#if !SNESRECOMP_ENABLE_MODS
    IogMapPreferences preferences;
    if(runtime&&IogMapPreferencesLoad(&preferences)){
        ui.radar=preferences.radar;
        for(unsigned n=0;n<IOG_MAP_CONTROL_COUNT;n++)controls[n]=preferences.bindings[n];
    }
#endif
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
    audit=NULL;initialized=false;opened=false;controls_open=false;
    input_held=input_consumed=false;preferences_saved=true;
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
            (unsigned)PPU_bgTilemapAdr(g_ppu,physical)==Word(r,0x6ba);
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
    Initialize();IogMapHostRadarSet(!ui.radar);
}
bool IogMapHostRadarEnabled(void){Initialize();return ui.radar;}
#if !SNESRECOMP_ENABLE_MODS
static void SaveNativePreferences(void)
{
    IogMapPreferences p;p.radar=ui.radar;
    for(unsigned n=0;n<IOG_MAP_CONTROL_COUNT;n++)p.bindings[n]=(uint8_t)controls[n];
    preferences_saved=runtime&&IogMapPreferencesSave(&p);
}
#endif
void IogMapHostRadarSet(bool enabled)
{
    Initialize();if(ui.radar==enabled)return;
    ui.radar=enabled;
#if SNESRECOMP_ENABLE_MODS
    preferences_saved=snes_mod_runtime_persist_feature_c("iog.enhancements","map_controls",1,"radar",
        enabled?"on":"off")!=0;
#else
    SaveNativePreferences();
#endif
}
const char *IogMapHostControlName(int button)
{return button>=0&&button<IOG_MAP_BUTTON_COUNT?control_names[button]:"?";}
int IogMapHostControlGet(int action)
{Initialize();return action>=0&&action<IOG_MAP_CONTROL_COUNT?controls[action]:-1;}
void IogMapHostControlSet(int action,int button)
{
    Initialize();
    if(action<0||action>=IOG_MAP_CONTROL_COUNT||button<0||button>=IOG_MAP_BUTTON_COUNT||
        controls[action]==button)return;
    int old=controls[action];
    for(int a=0;a<IOG_MAP_CONTROL_COUNT;a++)
        if(a!=action&&controls[a]==button)controls[a]=old;
    controls[action]=button;
    /* Persist the complete conflict-free assignment; a swapped Back binding
     * must survive restart along with the action the player changed. */
#if SNESRECOMP_ENABLE_MODS
    preferences_saved=true;
    for(int a=0;a<IOG_MAP_CONTROL_COUNT;a++)
        if(!snes_mod_runtime_persist_feature_c("iog.enhancements","map_controls",1,
            control_options[a],control_names[controls[a]]))preferences_saved=false;
#else
    SaveNativePreferences();
#endif
    previous_pad=~0u;
}
static bool Draw(uint8_t *dst,size_t bytes,size_t pitch,int w,int h)
{
    IogMapViewSource source;
    bool ready=ui.full?IogMapRuntimeGetViewSource(runtime,&source):
        IogMapRuntimeGetRadarSource(runtime,&source);
    if(!ready)return false;
    IogMapUiMetadata metadata={true,false,gamepad,0};
    char hint[96],back[24];
    snprintf(hint,sizeof(hint),"SNES: Pad Move  %s/%s Zoom  %s Center  %s Radar %s  Select Controls",
        control_names[controls[IOG_MAP_ZOOM_OUT]],control_names[controls[IOG_MAP_ZOOM_IN]],
        control_names[controls[IOG_MAP_CENTER]],control_names[controls[IOG_MAP_RADAR]],
        ui.radar?"ON":"OFF");
    snprintf(back,sizeof(back),"%s Back",control_names[controls[IOG_MAP_BACK]]);
    IogMapUiControllerHints(&ui,hint,back);
    return IogMapUiDraw(&ui,dst,bytes,pitch,(unsigned)w,(unsigned)h,&source,&metadata);
}
void IogMapHostDrawRadar(uint8_t *dst,size_t pitch,int w,int h)
{
    if(opened||ui.full||!ui.radar||w<256||h<160||pitch>SIZE_MAX/(size_t)h)return;
    (void)Draw(dst,pitch*(size_t)h,pitch,w,h);
}
int IogMapHostOpen(void)
{
    if(!IogMapHostAvailable())return 0;
    if(!ui.full){IogMapUiInput in={0};in.toggle_full=true;IogMapUiHandleInput(&ui,&in);}
    opened=true;controls_open=false;previous_pad=~0u;last_ticks=0;AuditEvent("map_open");return 1;
}
int IogMapHostInput(uint32_t *human)
{
#ifdef IOG_RECEIVED_REFERENCE
    if(!human||RtlSpeculativeFrame())return 0;
    bool held=!!(*human&SNES_PAD_START);
    if(!held){input_held=input_consumed=false;return 0;}
    bool pressed=!input_held;input_held=true;
    if(input_consumed){*human&=~SNES_PAD_START;return 0;}
    const char *fallback=getenv("IOG_ORIGINAL_AREA_MAP");
    const uint8_t *ram=g_snes?g_snes->ram:NULL;
    if(!pressed||(fallback&&*fallback=='1')||!IogMapHostAvailable()||!ram||
        !Word(ram,0x9aa)||Word(ram,0x642)||Word(ram,0x644)==0xfe||
        (Word(ram,0x9ec)&0x6080)||(Word(ram,0x9ae)&0x0208)||Word(ram,0x6fa))return 0;
    const Cart *cart=g_snes->cart;uint8_t digest[32],expected[32];
    /* Exact received GlobalInputHandler Start dispatch and IsMusicPlaying
     * helper. Hashes bind the source-derived RAM meanings, without embedding
     * extracted instructions or applying a guest patch. The observer already
     * verifies the full received content identity before a map can be ready. */
    if(!cart||cart->type!=CART_HIROM||!cart->rom||cart->romImageSize!=3276800||cart->romSize<3276800)return 0;
    sha256_compute(cart->rom+0x3ec66,0x81,digest);
    if(!Digest("7694aa045fdb90c4eb3174b4cbb9673ce9fb4bfb578158a13fc020a9e018c6e3",expected)||
        memcmp(digest,expected,32))return 0;
    sha256_compute(cart->rom+0x2f8f7,17,digest);
    if(!Digest("a8a84ace3e866f05caee8fb43824c829e72aeb664bcc768e2fc9ab12a7bf0150",expected)||
        memcmp(digest,expected,32))return 0;
    *human&=~SNES_PAD_START;input_consumed=true;gamepad=true;
    AuditEvent("map_request");return 1;
#else
    (void)human;return 0;
#endif
}
void IogMapHostClose(void)
{
    if(opened)AuditEvent("map_close");
    IogMapUiInput in={0};in.close=true;IogMapUiHandleInput(&ui,&in);opened=false;controls_open=false;
}
bool IogMapHostIsOpen(void){return opened;}
void IogMapHostPointer(int x,int y,int down)
{
    if(!opened)return;
    if(controls_open)return;
    gamepad=false;IogMapUiPointer(&ui,x,y,down!=0,598,336);
    AuditEvent("map_pointer");
    if(!ui.full)opened=false;
}
void IogMapHostNav(uint32_t pad,uint32_t ticks)
{
    if(!opened)return;
    uint32_t pressed=pad&~previous_pad;previous_pad=pad;
    unsigned delta=last_ticks?ticks-last_ticks:16;last_ticks=ticks;
    if(pad)gamepad=true;
    if(pad)AuditEvent("map_pad");
    if(pressed&SNES_PAD_SELECT){controls_open=!controls_open;return;}
    if(controls_open){
        if(pressed&SNES_PAD_B){controls_open=false;return;}
        if(pressed&SNES_PAD_UP)controls_row=(controls_row+5)%6;
        if(pressed&SNES_PAD_DOWN)controls_row=(controls_row+1)%6;
        int direction=(!!(pressed&(SNES_PAD_RIGHT|SNES_PAD_A)))-!!(pressed&SNES_PAD_LEFT);
        if(direction){
            if(!controls_row)IogMapHostRadarToggle();
            else IogMapHostControlSet((int)controls_row-1,
                (controls[controls_row-1]+IOG_MAP_BUTTON_COUNT+direction)%IOG_MAP_BUTTON_COUNT);
        }
        return;
    }
    IogMapUiInput in={0};in.dt_ms=delta;
    in.pan_x=(!!(pad&SNES_PAD_RIGHT))-(!!(pad&SNES_PAD_LEFT));
    in.pan_y=(!!(pad&SNES_PAD_DOWN))-(!!(pad&SNES_PAD_UP));
    in.zoom_out=!!(pressed&control_bits[controls[IOG_MAP_ZOOM_OUT]]);
    in.zoom_in=!!(pressed&control_bits[controls[IOG_MAP_ZOOM_IN]]);
    in.recenter=!!(pressed&control_bits[controls[IOG_MAP_CENTER]]);
    in.close=!!(pressed&control_bits[controls[IOG_MAP_BACK]]);
    if(pressed&control_bits[controls[IOG_MAP_RADAR]])IogMapHostRadarToggle();
    IogMapUiHandleInput(&ui,&in);if(in.close)opened=false;
}
void IogMapHostKey(int key,int repeat)
{
    if(!opened)return;
    AuditEvent("map_key");
    gamepad=false;IogMapUiInput in={0};in.dt_ms=100;
    if(key==9&&!repeat){controls_open=!controls_open;return;}
    if(controls_open){
        if((key==27||key=='m')&&!repeat){controls_open=false;return;}
        uint32_t pad=key==0x40000052?SNES_PAD_UP:key==0x40000051?SNES_PAD_DOWN:
            key==0x40000050?SNES_PAD_LEFT:key==0x4000004f||key=='\r'?SNES_PAD_RIGHT:0;
        if(pad){previous_pad=0;IogMapHostNav(pad,last_ticks+16);gamepad=false;}
        return;
    }
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
    bool drawn;
    if(controls_open){
        uint8_t bindings[5];for(unsigned n=0;n<5;n++)bindings[n]=(uint8_t)controls[n];
        drawn=IogMapUiDrawControls((uint8_t*)canvas,sizeof(canvas),598*4,598,336,
            bindings,controls_row,ui.radar,preferences_saved);
    }else drawn=Draw((uint8_t*)canvas,sizeof(canvas),598*4,598,336);
    if(!drawn)return 0;
    *pixels=canvas;*w=598;*h=336;
    /* One diagnostic picture of the real paused map, never a separate fake UI. */
    static bool written,written_controls;
    bool *done=controls_open?&written_controls:&written;
    const char *output=getenv(controls_open?"IOG_MAP_CONTROLS_OUTPUT":"IOG_MAP_OUTPUT");
    if(!*done&&output&&*output){
        FILE *file=fopen(output,"wb");
        if(file){
            bool ok=fprintf(file,"P6\n598 336\n255\n")>0;
            for(unsigned n=0;n<598*336&&ok;n++){
                uint32_t p=canvas[n];uint8_t rgb[3]={(uint8_t)(p>>16),(uint8_t)(p>>8),(uint8_t)p};
                ok=fwrite(rgb,1,3,file)==3;
            }
            if(fclose(file))ok=false;*done=ok;
        }
    }
    return 1;
}
