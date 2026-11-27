#!/usr/bin/env python3
"""ROM-free title controller routing, conflict swaps and persisted preferences.

Runs the actual host adapter and map UI with a synthetic map-runtime and mod
selection store. This verifies logical controller inputs, not a physical pad,
SDL device enumeration, game frames or a complete campaign.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "iog_map_host.c"
#include "iog_companion.c"
#include <stdlib.h>
Snes *g_snes;
Ppu *g_ppu;
CpuState g_cpu;
static unsigned checks,persisted;
static unsigned capture_requests;
static bool ready=true,speculative,custom_enabled=true;
static char stored[IOG_MAP_CONTROL_COUNT+1][16];
#define C(x) do{checks++;if(!(x)){fprintf(stderr,"line %u: %s\n",__LINE__,#x);exit(1);}}while(0)
bool RtlSpeculativeFrame(void){return speculative;}
int snes_mod_runtime_feature_enabled_c(const char*p,const char*f){C(!strcmp(p,"iog.enhancements")&&!strcmp(f,"map_controls"));return custom_enabled;}
int IogInventoryPageShown(void){return 0;}
/* A connected Xbox-layout pad under the default map: SNES B is its A. */
static bool pad_present=true,snes_style;static bool achievements_open,achievements_fail;
/* The default [GamepadMap]: SNES B south, A east, Y west, X north. */
int IogHostPadLabel(uint32_t bit,char label[8],uint32_t *color){
 if(!pad_present)return 0;
 int position=bit==SNES_PAD_B?IOG_PAD_SOUTH:bit==SNES_PAD_A?IOG_PAD_EAST:bit==SNES_PAD_Y?IOG_PAD_WEST:
  bit==SNES_PAD_X?IOG_PAD_NORTH:bit==SNES_PAD_L?IOG_PAD_L1:bit==SNES_PAD_R?IOG_PAD_R1:
  bit==SNES_PAD_SELECT?IOG_PAD_SELECT:bit==SNES_PAD_START?IOG_PAD_START:-1;
 return IogMapUiPadGlyph(position,snes_style,label,color);
}
void IogAchievementUiOpen(uint32_t held){(void)held;achievements_open=!achievements_fail;}
void IogAchievementUiClose(void){achievements_open=false;}
bool IogAchievementUiIsOpen(void){return achievements_open;}
void IogAchievementUiNav(uint32_t buttons,uint32_t ticks){(void)buttons;(void)ticks;}
void IogAchievementUiKey(int key){(void)key;}
void IogAchievementUiPointer(int x,int y,int pressed){(void)x;(void)y;(void)pressed;}
bool IogAchievementUiImage(const uint32_t **pixels,int *width,int *height){(void)pixels;(void)width;(void)height;return false;}
int IogCompletionPercent(void){return 0;}
const char *IogI18nLanguage(void){return "original";}
int snes_frame_counter;
static unsigned settings_opened;
void snes_settings_menu_open(void){settings_opened++;}
void snes_host_speculative_set_grab(SnesSpecGrabFn grab){(void)grab;}
int snes_host_speculative_capture(SnesSpecInputFn input,SnesSpecStopFn stop,void *ud,int frames,int flags,uint32_t*out,int cap,int*w,int*h){
 (void)input;(void)stop;(void)ud;(void)frames;(void)flags;(void)out;(void)cap;(void)w;(void)h;capture_requests++;return 0;
}
int snes_savestate_slot_exists(int slot){(void)slot;return 0;}
int snes_savestate_slot_thumb(int slot,uint32_t*out){(void)slot;(void)out;return 0;}
void snes_savestate_slot_label(int slot,char*out,int cap){(void)slot;if(cap)out[0]=0;}
int snes_savestate_save_slot(int slot){(void)slot;return 0;}
int snes_savestate_load_slot(int slot){(void)slot;return 0;}
IogMapRuntime *IogMapRuntimeCreate(const char *path){C(!strcmp(path,"saves"));return (IogMapRuntime*)(uintptr_t)1;}
void IogMapRuntimeDestroy(IogMapRuntime *r){C(r!=NULL);}
bool IogMapRuntimeFlush(IogMapRuntime *r){return r!=NULL;}
bool IogMapRuntimeUpdate(IogMapRuntime *r,const IogMapRuntimeFrame *f){(void)r;(void)f;return false;}
void IogMapRuntimeGetStatus(const IogMapRuntime *r,IogMapRuntimeStatus *s){C(r!=NULL);memset(s,0,sizeof(*s));s->frame_valid=ready;}
bool IogMapRuntimeGetViewSource(IogMapRuntime *r,IogMapViewSource *s){(void)r;(void)s;return false;}
bool IogMapRuntimeGetRadarSource(IogMapRuntime *r,IogMapViewSource *s){(void)r;(void)s;return false;}
int snes_mod_runtime_feature_option_value_c(const char*p,const char*f,const char*o,char*out,uint32_t cap){
 C(!strcmp(p,"iog.enhancements")&&!strcmp(f,"map_controls"));int n=IOG_MAP_CONTROL_COUNT;
 for(int i=0;i<IOG_MAP_CONTROL_COUNT;i++)if(!strcmp(o,control_options[i]))n=i;
 if(!stored[n][0])return 0;snprintf(out,cap,"%s",stored[n]);return 1;
}
int snes_mod_runtime_persist_feature_c(const char*p,const char*f,int enabled,const char*o,const char*v){
 C(!strcmp(p,"iog.enhancements")&&!strcmp(f,"map_controls")&&enabled==1);int n=IOG_MAP_CONTROL_COUNT;
 for(int i=0;i<IOG_MAP_CONTROL_COUNT;i++)if(!strcmp(o,control_options[i]))n=i;
 snprintf(stored[n],sizeof(stored[n]),"%s",v);persisted++;return 1;
}
static void unique(void){unsigned used=0;for(int a=0;a<IOG_MAP_CONTROL_COUNT;a++){int b=IogMapHostControlGet(a);C(b>=0&&b<IOG_MAP_BUTTON_COUNT);C(!(used&(1u<<b)));used|=1u<<b;}}
static unsigned tick=100;
static void press(uint32_t button){IogMapHostNav(0,tick+=16);IogMapHostNav(button,tick+=16);}
static void reopen(void){C(IogMapHostOpen());IogMapHostNav(0,tick+=16);C(ui.full&&opened);}
static void doorway_markers(void){
 static uint8_t rom[2097152],ram[131072],visibility[16*16];
 Cart cart={0};cart.rom=rom;cart.romImageSize=sizeof(rom);
 IogMapDiscoveryIdentity identity={0};
 IogMapDiscovery map;
 IogMapViewMarker markers[StockDoorwayLimit];
 C(IogMapDiscoveryInit(&map,16,16,&identity));
 ram[0x644]=1;ram[0x646]=2;
 ram[0xd4]=0x32;ram[0xd5]=0x84;
 ram[0xd6]=0x4b;ram[0xd7]=0x84;
 ram[0x6d7]=1;
 rom[0x18236]=0x32;rom[0x18237]=0x84;
 rom[0x18432]=17;rom[0x18433]=3;rom[0x18434]=2;rom[0x18435]=1;
 rom[0x1843e]=2;rom[0x1843f]=3;rom[0x18440]=1;rom[0x18441]=1;
 rom[0x1844a]=0xff;
 C(StockDoorwayMarkers(ram,&cart,&map,markers)==0);
 visibility[3*16+2]=1;
 C(IogMapDiscoveryReveal(&map,2,3,1,visibility,sizeof(visibility),16,NULL));
 C(StockDoorwayMarkers(ram,&cart,&map,markers)==1);
 C(markers[0].cell_x==2&&markers[0].cell_y==3);
 ram[0xd4]^=1;
 C(StockDoorwayMarkers(ram,&cart,&map,markers)==0);
 ram[0xd4]^=1;rom[0x18440]=0;
 C(StockDoorwayMarkers(ram,&cart,&map,markers)==0);
}
static void chest_markers(void){
 static uint8_t rom[2097152],ram[131072],visibility[16*16];
 Cart cart={0};cart.rom=rom;cart.romImageSize=sizeof(rom);
 IogMapDiscoveryIdentity identity={0};
 IogMapDiscovery map;
 IogMapViewMarker markers[StockChestLimit];
 C(IogMapDiscoveryInit(&map,16,16,&identity));
 ram[0x644]=0x0E;ram[0x646]=0x1C;
 ram[0x693]=2;ram[0x697]=2;
 ram[0x69f]=0xA0;ram[0x6d7]=1;ram[0x6d9]=1;
 rom[0x1adc4]=0xa7;rom[0x1adc5]=0xaf;
 rom[0x1afa7]=17;rom[0x1afa8]=20;rom[0x1afa9]=6;rom[0x1afaa]=0x81;
 rom[0x1afab]=0xff;
 ram[0xA331]=0xfa;ram[0xA332]=0xfb;
 ram[0xA341]=0xf8;ram[0xA342]=0xf9;
 C(StockChestMarkers(ram,&cart,&map,markers)==0);
 visibility[3*16+2]=1;
 C(IogMapDiscoveryReveal(&map,2,3,1,visibility,sizeof(visibility),16,NULL));
 C(StockChestMarkers(ram,&cart,&map,markers)==1);
 C(markers[0].cell_x==2&&markers[0].cell_y==3&&markers[0].color.r==255);
 ram[0xA40]=2;
 C(StockChestMarkers(ram,&cart,&map,markers)==0);
 ram[0xA40]=0;ram[0xA341]=0xfc;
 C(StockChestMarkers(ram,&cart,&map,markers)==0);
 ram[0xA341]=0xf8;rom[0x1afab]=0x80;
 C(StockChestMarkers(ram,&cart,&map,markers)==0);
 rom[0x1afab]=0xff;rom[0x1adc5]=0xae;
 C(StockChestMarkers(ram,&cart,&map,markers)==0);
}
int main(void){
 doorway_markers();
 chest_markers();
 g_cpu.master_cycles=123456;
 for(int a=0;a<IOG_MAP_CONTROL_COUNT;a++)C(IogMapHostControlGet(a)==control_defaults[a]);
 C(gamepad&&IogMapHostRadarEnabled());unique();
 C(!strcmp(IogMapHostControlName(5),"R"));C(!strcmp(IogMapHostControlName(-1),"?"));
 C(IogMapHostControlGet(-1)==-1);C(IogMapHostControlGet(IOG_MAP_CONTROL_COUNT)==-1);
 unsigned writes=persisted;IogMapHostControlSet(-1,0);IogMapHostControlSet(0,99);C(writes==persisted);
 reopen();ui.zoom_index=3;press(SNES_PAD_R);C(ui.zoom_index==4);
 IogMapHostNav(SNES_PAD_R,tick+=16);C(ui.zoom_index==4);press(SNES_PAD_L);C(ui.zoom_index==3);
 ui.center_pending=false;press(SNES_PAD_Y);C(ui.center_pending);
 ui.center_x_q8=ui.center_y_q8=500;press(SNES_PAD_DOWN|SNES_PAD_RIGHT);C(ui.center_x_q8>500&&ui.center_x_q8==ui.center_y_q8);
 press(SNES_PAD_LEFT|SNES_PAD_UP);C(ui.center_x_q8==500&&ui.center_y_q8==500);
 press(SNES_PAD_X);C(!ui.radar&&!strcmp(stored[IOG_MAP_CONTROL_COUNT],"off"));
 IogMapHostNav(SNES_PAD_X,tick+=16);C(!ui.radar);press(SNES_PAD_X);C(ui.radar);
 press(SNES_PAD_B);C(!opened&&!ui.full);C(g_cpu.master_cycles==123456);
 /* Swapping Back with zoom-in must leave both independently reachable. */
 IogMapHostControlSet(IOG_MAP_BACK,5);C(controls[IOG_MAP_BACK]==5&&controls[IOG_MAP_ZOOM_IN]==1);unique();
 reopen();ui.zoom_index=3;press(SNES_PAD_B);C(opened&&ui.zoom_index==4);press(SNES_PAD_R);C(!opened);
 int before[IOG_MAP_CONTROL_COUNT];memcpy(before,controls,sizeof(before));
 IogMapHostRadarSet(false);IogMapHostShutdown();C(!initialized);
 for(int a=0;a<IOG_MAP_CONTROL_COUNT;a++)C(IogMapHostControlGet(a)==before[a]);C(!IogMapHostRadarEnabled());
 for(int a=0;a<IOG_MAP_CONTROL_COUNT;a++)for(int b=0;b<IOG_MAP_BUTTON_COUNT;b++){
  IogMapHostControlSet(a,b);unique();C(controls[a]==b);
  for(int k=0;k<IOG_MAP_CONTROL_COUNT;k++)C(!strcmp(stored[k],control_names[controls[k]]));
 }
 IogMapHostShutdown();for(int a=0;a<IOG_MAP_CONTROL_COUNT;a++)strcpy(stored[a],"A");
 (void)IogMapHostControlGet(0);unique();
 ready=false;C(!IogMapHostOpen());ready=true;
 reopen();speculative=true;IogMapHostReset();C(opened);speculative=false;IogMapHostReset();C(!opened);
 writes=persisted;IogMapHostRadarSet(IogMapHostRadarEnabled());C(persisted==writes);
 /* Dynamic labels are bounded copies; UI remains separate from guest state. */
 char long_hint[240];memset(long_hint,'R',sizeof(long_hint)-1);long_hint[sizeof(long_hint)-1]=0;
 IogMapUiControllerHints(&ui,long_hint,long_hint);C(strlen(ui.controller_hint)==95&&strlen(ui.controller_back)==23);
 IogMapUiControllerHints(&ui,NULL,NULL);C(!ui.controller_hint[0]&&!ui.controller_back[0]);
 /* Disabling custom controls restores safe built-in defaults, even when
  * custom options remain stored. It does not remove the built-in map. */
 IogMapHostShutdown();custom_enabled=false;
 for(int a=0;a<IOG_MAP_CONTROL_COUNT;a++)C(IogMapHostControlGet(a)==control_defaults[a]);
 C(IogMapHostRadarEnabled());custom_enabled=true;
 /* Controls pane is fully navigable without a pointer. Its fixed B returns
  * to the map; only the configured map Back then closes that map. */
 reopen();press(SNES_PAD_SELECT);C(controls_open&&opened);
 press(SNES_PAD_RIGHT);C(!ui.radar&&controls_open);
 press(SNES_PAD_DOWN);C(controls_row==1);
 press(SNES_PAD_RIGHT);C(controls[IOG_MAP_ZOOM_IN]==0);unique();
 IogMapHostNav(SNES_PAD_RIGHT,tick+=16);C(controls[IOG_MAP_ZOOM_IN]==0);
 const uint32_t *image=NULL;int width=0,height=0;
 /* The pane is the host's overlay size: twice the presented frame, with
  * doubled text once that is 672 high (the 1.5x wide view at any window). */
 frame_w=299;frame_h=168;C(IogMapHostImage(&image,&width,&height)&&image&&width==598&&height==336&&canvas_scale==1);
 frame_w=598;frame_h=336;C(IogMapHostImage(&image,&width,&height)&&width==1196&&height==672&&canvas_scale==2);
 frame_w=448;frame_h=336;C(IogMapHostImage(&image,&width,&height)&&width==896&&height==672&&canvas_scale==2);
 frame_w=256;frame_h=224;C(IogMapHostImage(&image,&width,&height)&&width==512&&height==448&&canvas_scale==1);
 press(SNES_PAD_B);C(!controls_open&&opened);
 press(control_bits[controls[IOG_MAP_BACK]]);C(!opened);
 /* Source-backed Start interception: safe radar mode only, held consumption,
  * no global Start replacement in towns, fades, world map or speculative work. */
 static Snes machine;static uint8_t ram[131072];machine.ram=ram;g_snes=&machine;
 ram[0x9aa]=1;uint32_t human=0;C(!IogCompanionInput(&human));
 human=SNES_PAD_START|SNES_PAD_RIGHT;C(IogCompanionInput(&human));
 C(human==SNES_PAD_RIGHT&&g_map_requested);
 C(IogCompanionOpen()&&g_page==kPageMap&&opened&&!capture_requests);
 g_have_inv=1;IogCompanionNav(0,tick+=16);
 IogCompanionNav(control_bits[controls[IOG_MAP_BACK]],tick+=16);
 /* Since 650c757 there is no paused page menu: the map's Back returns to
  * the game, and nothing is left on view. */
 const uint32_t *panel=NULL;int pw=0,ph=0;
 C(!opened&&!g_open&&!IogCompanionImage(&panel,&pw,&ph)&&kPageCount==4);
 /* The one paused page drawn in the menu's art is the notice shown when the
  * achievement browser cannot open (asked for by the settings menu's row). */
 achievements_fail=true;IogCompanionRequestAchievements();
 human=0;C(IogCompanionInput(&human));
 C(IogCompanionOpen()&&g_page==kPageAchievements&&g_open&&!achievements_open&&!opened&&!capture_requests);
 /* The page fills the overlay at the largest whole scale: 2x of 512x448,
  * 3x (768x672) of the 1.5x wide view's 1196x672, and never less than 1x. */
 frame_w=598;frame_h=336;C(IogCompanionImage(&panel,&pw,&ph)&&pw==768&&ph==672&&g_scale==3);
 frame_w=640;frame_h=360;C(IogCompanionImage(&panel,&pw,&ph)&&pw==768&&ph==672);
 frame_w=448;frame_h=336;C(IogCompanionImage(&panel,&pw,&ph)&&pw==768&&ph==672);
 frame_w=256;frame_h=224;C(IogCompanionImage(&panel,&pw,&ph)&&pw==512&&ph==448&&g_scale==2);
 /* Its one prompt names the pad's own button: Back is SNES B, the pad's A. */
 C(g_prompt_count==1&&!strcmp(g_prompts[0].glyph,"A")&&g_prompts[0].action==kActBack);
 /* SNES style prints the pad's own letter at the same position: B in yellow. */
 snes_style=true;C(IogCompanionImage(&panel,&pw,&ph)&&g_prompt_count==1);
 C(!strcmp(g_prompts[0].glyph,"B")&&g_prompts[0].color==IOG_MAP_UI_GLYPH_FILLED(0xf2c94c)&&g_prompts[0].action==kActBack);
 snes_style=false;
 /* Without a controller the same prompt names the keyboard key. */
 pad_present=false;IogMapHostNotePad(false);C(IogCompanionImage(&panel,&pw,&ph)&&!strcmp(g_prompts[0].glyph,"Esc")&&!g_prompts[0].color);
 pad_present=true;IogMapHostNotePad(true);C(IogCompanionImage(&panel,&pw,&ph)&&!strcmp(g_prompts[0].glyph,"A"));
 /* The prompt stays inside its box (x 8..249, rows 159..209). */
 C(g_prompts[0].x>=9&&g_prompts[0].x1<=249&&g_prompts[0].y>=159&&g_prompts[0].y+8<=210);
 /* A pointer press on the prompt acts at the panel's scale; Back returns to
  * the settings menu the notice came from. */
 IogCompanionPointer(g_prompts[0].x*g_scale+4,g_prompts[0].y*g_scale+4,1);
 C(!g_open&&settings_opened==1);IogCompanionPointer(0,0,0);
 /* Either style, the same SNES button acts: B leaves to the settings menu. */
 IogCompanionRequestAchievements();C(IogCompanionOpen()&&g_open);
 IogCompanionNav(0,tick+=16);IogCompanionNav(SNES_PAD_B,tick+=16);C(!g_open&&settings_opened==2);
 /* Start, which opened the screen, returns to the game, not to the settings. */
 IogCompanionRequestAchievements();C(IogCompanionOpen()&&g_open);
 IogCompanionNav(0,tick+=16);IogCompanionNav(SNES_PAD_START,tick+=16);C(!g_open&&settings_opened==2);
 achievements_fail=false;IogCompanionNav(0,tick+=16);
 /* Start opens the map; Start (the screen's own button) and the map's Back
  * both return to the game, and a held Start stays consumed. */
 human=0;IogCompanionInput(&human);
 human=SNES_PAD_START;C(IogCompanionInput(&human)&&human==0&&IogCompanionOpen()&&g_page==kPageMap&&opened);
 IogCompanionNav(0,tick+=16);IogCompanionNav(SNES_PAD_START,tick+=16);C(!g_open&&!opened);
 human=SNES_PAD_START;C(!IogCompanionInput(&human)&&human==0);human=0;IogCompanionInput(&human);
 human=SNES_PAD_START;C(IogCompanionInput(&human)&&IogCompanionOpen()&&g_page==kPageMap);
 IogCompanionNav(0,tick+=16);IogCompanionNav(control_bits[controls[IOG_MAP_BACK]],tick+=16);C(!g_open&&!opened);
 human=SNES_PAD_START;C(!IogCompanionInput(&human)&&human==0);
 human=0;C(!IogCompanionInput(&human));
 /* Since 650c757 Start is the map button wherever the area has a map: the
  * combat lock (0x9AE bit 3) no longer keeps the original Start. */
 ram[0x9ae]=8;human=SNES_PAD_START;C(IogCompanionInput(&human)&&human==0&&g_map_requested);
 C(IogCompanionOpen()&&opened);IogCompanionNav(0,tick+=16);IogCompanionNav(SNES_PAD_START,tick+=16);C(!g_open&&!opened);
 human=0;IogCompanionInput(&human);ram[0x9ae]=0;ready=false;
 human=SNES_PAD_START;C(!IogCompanionInput(&human)&&human==SNES_PAD_START);
 human=0;IogCompanionInput(&human);ready=true;ram[0x9ed]=0x20;
 human=SNES_PAD_START;C(!IogCompanionInput(&human)&&human==SNES_PAD_START);
 human=0;IogCompanionInput(&human);ram[0x9ed]=0;speculative=true;
 human=SNES_PAD_START;C(!IogCompanionInput(&human)&&human==SNES_PAD_START);
 speculative=false;human=0;IogCompanionInput(&human);
 putenv("IOG_ORIGINAL_AREA_MAP=1");human=SNES_PAD_START;
 C(!IogCompanionInput(&human)&&human==SNES_PAD_START);putenv("IOG_ORIGINAL_AREA_MAP=0");
 human=0;IogCompanionInput(&human);
 /* The page list lives on the Dual / Flip Grip screen beside the running
  * game. Shoulders walk Items, Status, Map, Saves, Config; the map there is
  * the live box, never the paused map host; Back has nothing to leave. */
 /* (IogCompanionLive would compose the menu art from the game's PPU, which
  * this ROM-free harness has none of; the host has called it once.) */
 g_live_seen=1;C(!g_open);
 C(g_live_page==kLiveItems);
 IogCompanionNav(SNES_PAD_R,tick+=16);C(g_live_page==kLiveStatus);IogCompanionNav(0,tick+=16);
 IogCompanionNav(SNES_PAD_R,tick+=16);C(g_live_page==kPageMap&&!opened);IogCompanionNav(0,tick+=16);
 IogCompanionNav(SNES_PAD_R,tick+=16);C(g_live_page==kPageSaves);IogCompanionNav(0,tick+=16);
 IogCompanionNav(SNES_PAD_R,tick+=16);C(g_live_page==kPageSettings);IogCompanionNav(0,tick+=16);
 IogCompanionNav(SNES_PAD_R,tick+=16);C(g_live_page==kLiveItems);IogCompanionNav(0,tick+=16);
 IogCompanionNav(SNES_PAD_L,tick+=16);C(g_live_page==kPageSettings);IogCompanionNav(0,tick+=16);
 IogCompanionNav(SNES_PAD_B,tick+=16);C(!g_open&&g_live_page==kPageSettings);IogCompanionNav(0,tick+=16);
 /* Live Saves: X on an empty slot saves without a question. */
 IogCompanionNav(SNES_PAD_L,tick+=16);C(g_live_page==kPageSaves);IogCompanionNav(0,tick+=16);
 IogCompanionNav(SNES_PAD_X,tick+=16);C(g_confirm==-1&&!g_open);IogCompanionNav(0,tick+=16);
 /* Every page-list row, the last one ("Config") included, lies inside the
  * list box's interior (rows 159..209 of the 151..215 box); a press on a row
  * selects that page and a press on the selected Config row opens settings. */
 C(kPageRowY>=159&&kPageRowY+(kLiveCount-1)*PageRowPitch()+8<=210&&PageRowPitch()>=9);
 IogCompanionPointer(2*40,2*(kPageRowY+4),1);C(g_live_page==kLiveItems);IogCompanionPointer(0,0,0);
 IogCompanionPointer(2*40,2*(kPageRowY+(kLiveCount-1)*PageRowPitch()+4),1);
 C(g_live_page==kPageSettings&&settings_opened==2);IogCompanionPointer(0,0,0);
 IogCompanionPointer(2*40,2*(kPageRowY+(kLiveCount-1)*PageRowPitch()+4),1);
 C(settings_opened==3&&!g_open);IogCompanionPointer(0,0,0);
 g_snes=NULL;human=0;IogCompanionInput(&human);
 IogMapHostShutdown();printf("%u map controller assertions passed; %u preference writes\n",checks,persisted);return 0;
}
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='cc')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    assert out.is_relative_to((ROOT / '.local').resolve())
    out.mkdir(parents=True, exist_ok=False)
    source = out / 'controller.c'
    source.write_text(HARNESS)
    exe = out / 'controller.exe'
    inputs = [ROOT / n for n in ('src/iog_map_host.c', 'src/iog_map_host.h',
        'src/iog_companion.c','src/iog_companion.h',
        'src/iog_map_ui.c', 'src/iog_map_ui.h', 'src/iog_map_view.c',
        'src/iog_map_discovery.c', 'snesrecomp/runner/src/snes_overlay_draw.c',
        'snesrecomp/runner/src/sha256.c')]
    cmd = [args.compiler, '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
        '-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DSNESRECOMP_ENABLE_MODS=1',
        '-I' + str(ROOT / 'src'), '-I' + str(ROOT / 'snesrecomp/runner/src'),
        '-I' + str(ROOT / 'snesrecomp/runner/src/desktop'),
        str(source), *[str(p) for p in inputs if p.suffix == '.c' and p.name not in ('iog_map_host.c','iog_companion.c')],
        '-o', str(exe)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    (out / 'build.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True, timeout=30)
    (out / 'run.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    # The private received reference links no mod runtime. Compile its actual
    # adapter separately and inspect undefined symbols instead of supplying a
    # test stub that could hide an accidental mod dependency.
    reference = out / 'reference-map-host.obj'
    reference_cmd = [args.compiler, '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
        '-DSNESRECOMP_ENABLE_MODS=0', '-DIOG_RECEIVED_REFERENCE=1',
        '-I' + str(ROOT / 'src'), '-I' + str(ROOT / 'snesrecomp/runner/src'),
        '-c', str(ROOT / 'src/iog_map_host.c'), '-o', str(reference)]
    check = subprocess.run(reference_cmd, capture_output=True, text=True)
    (out / 'reference-build.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    sibling = Path(args.compiler).parent / ('llvm-nm.exe' if Path(args.compiler).suffix == '.exe' else 'llvm-nm')
    nm = str(sibling) if sibling.is_file() else shutil.which('llvm-nm') or shutil.which('nm')
    assert nm, 'llvm-nm or nm is required for the mods-off dependency check'
    check = subprocess.run([nm, '-u', str(reference)], capture_output=True, text=True)
    check.check_returncode()
    (out / 'reference-undefined.txt').write_text(check.stdout)
    assert 'snes_mod_runtime_' not in check.stdout
    (out / 'receipt.json').write_text(json.dumps({
        'passed': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr,
        'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in inputs + [Path(__file__)]},
        'reference_mods_off_has_no_mod_runtime_dependencies': True,
        'scope': 'Actual title host/Companion/controller/UI with synthetic runtime and preference store. Logical pad edges, both-axis pan, actions, conflict swaps, preference reload, disabled defaults, Start radar replacement/held consumption and speculative guards. Actual received adapter object has no undefined mod-runtime symbols. No physical pad, SDL input-route or game/campaign qualification.'
    }, indent=2) + '\n')
    result.check_returncode()
    print(result.stdout.strip())

if __name__ == '__main__':
    main()
