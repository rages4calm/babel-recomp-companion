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
#include <limits.h>
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
/* The paused map is drawn at the host's overlay size: twice the presented
 * frame (598x336 at the 1.5x wide view, so 1196x672), with doubled chrome
 * when that is at least 672 high. Frame size is noted at each radar call. */
enum { CanvasMaxW=1600, CanvasMaxH=896 };
static uint32_t canvas[CanvasMaxW*CanvasMaxH];
static uint32_t controls_canvas[(CanvasMaxW/2)*(CanvasMaxH/2)];
static int frame_w=256,frame_h=224,canvas_w=598,canvas_h=336,canvas_scale=1;
int IogHostPadLabel(uint32_t snes_bit,char label[8],uint32_t *color);
void IogMapHostOverlaySize(int *w,int *h)
{
    int ow=frame_w*2,oh=frame_h*2;
    if(ow>CanvasMaxW)ow=CanvasMaxW;
    if(oh>CanvasMaxH)oh=CanvasMaxH;
    if(w)*w=ow;
    if(h)*h=oh;
}
void IogMapHostPrompt(uint32_t snes_bit,const char *key,const char *text,
    char glyph[8],uint32_t *color,char out_text[16])
{
    char label[8]={0};uint32_t tint=0;
    if(!(snes_bit&&gamepad&&IogHostPadLabel(snes_bit,label,&tint))){
        snprintf(label,sizeof(label),"%.7s",key?key:"");tint=0;
    }
    memcpy(glyph,label,8);*color=tint;
    if(out_text)snprintf(out_text,16,"%.15s",text?text:"");
}
bool IogMapHostUsingPad(void){return gamepad;}
void IogMapHostNotePad(bool pad){gamepad=pad;}
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
#ifndef IOG_RECEIVED_REFERENCE
enum { StockDoorwayLimit=32, StockChestLimit=8 };
static const IogMapViewColor ExitMarkerColor={105,217,211,255};
static const IogMapViewColor ChestMarkerColor={255,190,96,255};

static size_t StockDoorwayMarkers(const uint8_t *ram,const Cart *cart,
    const IogMapDiscovery *map,IogMapViewMarker markers[StockDoorwayLimit])
{
    enum { WarpBank=0x10000, WarpPointers=0x18234, WarpLists=0x18432,
           WarpLimit=0x1A95E, WarpRecordSize=12 };
    if(!ram || !cart || !cart->rom || cart->romImageSize!=2097152 || !map)
        return 0;
    unsigned scene=Word(ram,0x644);
    if(scene>=0xFF || Word(ram,0x646)!=scene*2) return 0;

    /* Bind to the game's currently loaded transition list. The following
     * list contains in-room forced walks and does not describe exits. */
    const uint8_t *rom=cart->rom;
    unsigned list=WarpBank+Word(rom,WarpPointers+scene*2);
    unsigned end=WarpBank+Word(ram,0xD6)-1;
    if(list!=WarpBank+Word(ram,0xD4) || list<WarpLists || end<list ||
       end>=WarpLimit || (end-list)%WarpRecordSize ||
       (end-list)/WarpRecordSize>StockDoorwayLimit || rom[end]!=0xFF)
        return 0;

    int floor_x=(int)Word(ram,0x6D6)/16, floor_y=(int)Word(ram,0x6D8)/16;
    size_t count=0;
    for(unsigned at=list;at<end;at+=WarpRecordSize) {
        const uint8_t *entry=rom+at;
        if(entry[0]>=128 || !entry[2] || !entry[3]) return 0;
        int left=entry[0]-floor_x, top=entry[1]-floor_y;
        int right=left+entry[2], bottom=top+entry[3];
        int best=INT_MAX, marker_x=0, marker_y=0;
        for(int y=top<0?0:top;y<bottom && y<map->height;y++) {
            for(int x=left<0?0:left;x<right && x<map->width;x++) {
                if(!IogMapDiscoveryIsRevealed(map,x,y)) continue;
                int distance=abs(2*x+1-left-right)+abs(2*y+1-top-bottom);
                if(distance>=best) continue;
                best=distance;
                marker_x=x;
                marker_y=y;
            }
        }
        if(best!=INT_MAX)
            markers[count++]=(IogMapViewMarker){(int16_t)marker_x,(int16_t)marker_y,
                2,ExitMarkerColor};
    }
    return count;
}

static bool StockClosedChest(const uint8_t *ram, unsigned x, unsigned y)
{
    unsigned columns=Word(ram,0x692),rows=Word(ram,0x696);
    if(columns<256 || rows<256 || ((columns|rows)&255) ||
       columns>4096 || rows>4096 || !y || x+1>=columns/16 || y>=rows/16)
        return false;
    /* Check the live metatiles as well as the opened flag. A script can
     * remove or replace a chest while the source record still exists. */
    const uint8_t expected[2][2]={{0xFA,0xFB},{0xF8,0xF9}};
    for(unsigned row=0;row<2;row++) {
        unsigned cell_y=y+row-1;
        for(unsigned col=0;col<2;col++) {
            unsigned cell_x=x+col;
            unsigned offset=((cell_y/16)*(columns/256)+cell_x/16)*256+
                (cell_y%16)*16+cell_x%16;
            if(offset>=0x6000 || ram[0xA000+offset]!=expected[row][col])
                return false;
        }
    }
    return true;
}

static size_t StockChestMarkers(const uint8_t *ram,const Cart *cart,
    const IogMapDiscovery *map,IogMapViewMarker markers[StockChestLimit])
{
    enum { Bank=0x10000, Pointers=0x1ADA8, Lists=0x1AFA6, End=0x1B086, RecordSize=4 };
    if(!ram || !cart || !cart->rom || cart->romImageSize!=2097152 || !map ||
       Word(ram,0x69E)!=0xA000)
        return 0;
    unsigned scene=Word(ram,0x644);
    if(scene>=0xFF || Word(ram,0x646)!=scene*2) return 0;
    const uint8_t *rom=cart->rom;
    unsigned at=Bank+Word(rom,Pointers+scene*2);
    if(at<Lists || at>=End) return 0;
    int floor_x=(int)Word(ram,0x6D6)/16,floor_y=(int)Word(ram,0x6D8)/16;
    size_t count=0;
    for(unsigned n=0;n<=StockChestLimit && at<End;n++,at+=RecordSize) {
        if(rom[at]==0xFF) return count;
        if(n==StockChestLimit || at+RecordSize>End || (rom[at]&0x80)) return 0;
        unsigned x=rom[at],y=rom[at+1],flag=rom[at+3]&0x7Fu;
        if((ram[0xA40+flag/8]&(1u<<(flag%8))) || !StockClosedChest(ram,x,y))
            continue;
        int left=(int)x-floor_x,bottom=(int)y-floor_y;
        for(unsigned cell=0;cell<4;cell++) {
            int mx=left+(int)(cell%2),my=bottom-(int)(cell/2);
            if(!IogMapDiscoveryIsRevealed(map,mx,my)) continue;
            markers[count++]=(IogMapViewMarker){(int16_t)mx,(int16_t)my,2,ChestMarkerColor};
            break;
        }
    }
    return 0;
}
#endif

#ifndef IOG_RECEIVED_REFERENCE
/* Exits and unopened chests of the loaded scene, with their legend colours. */
static void StockMarkers(IogMapViewSource *source,
    IogMapViewMarker markers[StockDoorwayLimit+StockChestLimit],IogMapUiMetadata *metadata)
{
    if(!g_snes) return;
    size_t exits=StockDoorwayMarkers(g_snes->ram,g_snes->cart,source->discovery,markers);
    size_t chests=StockChestMarkers(g_snes->ram,g_snes->cart,source->discovery,markers+exits);
    source->marker_count=exits+chests;
    if(!(exits+chests)) return;
    source->markers=markers;
    if(exits) metadata->exit_legend=ExitMarkerColor;
    if(chests) metadata->chest_legend=ChestMarkerColor;
}
#endif

static bool Draw(uint8_t *dst,size_t bytes,size_t pitch,int w,int h)
{
    IogMapViewSource source;
    bool ready=ui.full?IogMapRuntimeGetViewSource(runtime,&source):
        IogMapRuntimeGetRadarSource(runtime,&source);
    if(!ready)return false;
    IogMapUiMetadata metadata={.valid=true,.gamepad=gamepad};
#ifndef IOG_RECEIVED_REFERENCE
    IogMapViewMarker markers[StockDoorwayLimit+StockChestLimit];
    if(ui.full) StockMarkers(&source,markers,&metadata);
#endif
    char hint[96],back[24];
    snprintf(hint,sizeof(hint),"SNES: Pad Move  %s/%s Zoom  %s Center  %s Radar %s  Select Controls",
        control_names[controls[IOG_MAP_ZOOM_OUT]],control_names[controls[IOG_MAP_ZOOM_IN]],
        control_names[controls[IOG_MAP_CENTER]],control_names[controls[IOG_MAP_RADAR]],
        ui.radar?"ON":"OFF");
    snprintf(back,sizeof(back),"%s Back",control_names[controls[IOG_MAP_BACK]]);
    IogMapUiControllerHints(&ui,hint,back);
    /* The physical buttons bound to those SNES buttons, as glyphs. Without a
     * bound controller the text hints above remain (keyboard names). */
    IogMapUiPrompt prompts[IOG_MAP_UI_PROMPTS],exit_prompt;unsigned count=0;
    memset(prompts,0,sizeof(prompts));memset(&exit_prompt,0,sizeof(exit_prompt));
    char probe[8];uint32_t tint;
    if(ui.full&&gamepad&&IogHostPadLabel(control_bits[controls[IOG_MAP_BACK]],probe,&tint)){
        snprintf(prompts[0].glyph,8,"PAD");snprintf(prompts[0].text,16,"Move");
        IogMapHostPrompt(control_bits[controls[IOG_MAP_ZOOM_OUT]],"-","",prompts[1].glyph,&prompts[1].color,prompts[1].text);
        IogMapHostPrompt(control_bits[controls[IOG_MAP_ZOOM_IN]],"+","Zoom",prompts[2].glyph,&prompts[2].color,prompts[2].text);
        IogMapHostPrompt(control_bits[controls[IOG_MAP_CENTER]],"Home","Center",prompts[3].glyph,&prompts[3].color,prompts[3].text);
        IogMapHostPrompt(control_bits[controls[IOG_MAP_RADAR]],"","",prompts[4].glyph,&prompts[4].color,NULL);
        snprintf(prompts[4].text,16,"Radar %s",ui.radar?"ON":"OFF");
        IogMapHostPrompt(SNES_PAD_SELECT,"Tab","Setup",prompts[5].glyph,&prompts[5].color,prompts[5].text);
        IogMapHostPrompt(control_bits[controls[IOG_MAP_BACK]],"Esc","Back",exit_prompt.glyph,&exit_prompt.color,exit_prompt.text);
        count=IOG_MAP_UI_PROMPTS;
    }
    IogMapUiSetPrompts(&ui,prompts,count,&exit_prompt);
    return IogMapUiDraw(&ui,dst,bytes,pitch,(unsigned)w,(unsigned)h,&source,&metadata);
}
void IogMapHostDrawRadar(uint8_t *dst,size_t pitch,int w,int h)
{
    if(w>=256&&h>=160){frame_w=w;frame_h=h;}
    if(opened||ui.full||!ui.radar||w<256||h<160||pitch>SIZE_MAX/(size_t)h)return;
    (void)Draw(dst,pitch*(size_t)h,pitch,w,h);
}
int IogMapHostDrawLive(uint32_t *dst,int stride,int w,int h,int cell_pixels)
{
    IogMapViewSource source;IogMapUiMetadata metadata={.valid=true};
    if(!dst||w<=0||h<=0||stride<w||cell_pixels<=0||!IogMapHostAvailable()||
        !IogMapRuntimeGetViewSource(runtime,&source))return 0;
#ifndef IOG_RECEIVED_REFERENCE
    IogMapViewMarker markers[StockDoorwayLimit+StockChestLimit];
    StockMarkers(&source,markers,&metadata);
#endif
    const size_t pitch=(size_t)stride*4;
    if(!IogMapUiDrawView((uint8_t*)dst,pitch*(size_t)(h-1)+(size_t)w*4,pitch,
        (unsigned)w,(unsigned)h,&source,(unsigned)cell_pixels))return 0;
    return IOG_MAP_LIVE_DRAWN|(metadata.exit_legend.a?IOG_MAP_LIVE_EXITS:0)|
        (metadata.chest_legend.a?IOG_MAP_LIVE_CHESTS:0);
}
int IogMapHostOpen(void)
{
    if(!IogMapHostAvailable())return 0;
    if(!ui.full){IogMapUiInput in={0};in.toggle_full=true;IogMapUiHandleInput(&ui,&in);}
    opened=true;controls_open=false;previous_pad=~0u;last_ticks=0;AuditEvent("map_open");
    char probe[8];uint32_t tint;gamepad=IogHostPadLabel(SNES_PAD_B,probe,&tint)!=0;return 1;
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
    gamepad=false;IogMapUiPointer(&ui,x,y,down!=0,(unsigned)canvas_w,(unsigned)canvas_h);
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
    IogMapHostOverlaySize(&canvas_w,&canvas_h);
    canvas_scale=canvas_h>=672&&canvas_w>=512?2:1;
    canvas_w-=canvas_w%canvas_scale;canvas_h-=canvas_h%canvas_scale;
    const size_t pitch=(size_t)canvas_w*4;
    memset(canvas,0,pitch*(size_t)canvas_h);
    bool drawn;
    if(controls_open){
        /* The bindings pane is text only: drawn once at 1x, then doubled. */
        const int lw=canvas_w/canvas_scale,lh=canvas_h/canvas_scale;
        uint8_t bindings[5];for(unsigned n=0;n<5;n++)bindings[n]=(uint8_t)controls[n];
        drawn=IogMapUiDrawControls((uint8_t*)controls_canvas,sizeof(controls_canvas),(size_t)lw*4,
            (unsigned)lw,(unsigned)lh,bindings,controls_row,ui.radar,preferences_saved);
        if(drawn)for(int y=0;y<canvas_h;y++)for(int x=0;x<canvas_w;x++)
            canvas[(size_t)y*canvas_w+x]=controls_canvas[(size_t)(y/canvas_scale)*lw+x/canvas_scale];
    }else{
        IogMapUiSetScale(&ui,(unsigned)canvas_scale);
        drawn=Draw((uint8_t*)canvas,pitch*(size_t)canvas_h,pitch,canvas_w,canvas_h);
    }
    if(!drawn)return 0;
    *pixels=canvas;*w=canvas_w;*h=canvas_h;
    /* One diagnostic picture of the real paused map, never a separate fake UI. */
    static bool written,written_controls;
    bool *done=controls_open?&written_controls:&written;
    const char *output=getenv(controls_open?"IOG_MAP_CONTROLS_OUTPUT":"IOG_MAP_OUTPUT");
    if(!*done&&output&&*output){
        FILE *file=fopen(output,"wb");
        if(file){
            bool ok=fprintf(file,"P6\n%d %d\n255\n",canvas_w,canvas_h)>0;
            for(unsigned n=0;n<(unsigned)(canvas_w*canvas_h)&&ok;n++){
                uint32_t p=canvas[n];uint8_t rgb[3]={(uint8_t)(p>>16),(uint8_t)(p>>8),(uint8_t)p};
                ok=fwrite(rgb,1,3,file)==3;
            }
            if(fclose(file))ok=false;*done=ok;
        }
    }
    return 1;
}
