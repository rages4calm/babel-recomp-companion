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
int IogCompletionPercent(void){return 0;}
const char *IogI18nLanguage(void){return "original";}
int snes_frame_counter;
void snes_settings_menu_open(void){}
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
int main(void){
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
 C(IogMapHostImage(&image,&width,&height)&&image&&width==598&&height==336);
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
 C(g_page==kPageItems&&!opened&&g_open);
 human=SNES_PAD_START;C(!IogCompanionInput(&human)&&human==0);
 human=0;C(!IogCompanionInput(&human));
 ram[0x9ae]=8;human=SNES_PAD_START;C(!IogCompanionInput(&human)&&human==SNES_PAD_START);
 human=0;IogCompanionInput(&human);ram[0x9ae]=0;ready=false;
 human=SNES_PAD_START;C(!IogCompanionInput(&human)&&human==SNES_PAD_START);
 human=0;IogCompanionInput(&human);ready=true;ram[0x9ed]=0x20;
 human=SNES_PAD_START;C(!IogCompanionInput(&human)&&human==SNES_PAD_START);
 human=0;IogCompanionInput(&human);ram[0x9ed]=0;speculative=true;
 human=SNES_PAD_START;C(!IogCompanionInput(&human)&&human==SNES_PAD_START);
 speculative=false;human=0;IogCompanionInput(&human);
 putenv("IOG_ORIGINAL_AREA_MAP=1");human=SNES_PAD_START;
 C(!IogCompanionInput(&human)&&human==SNES_PAD_START);putenv("IOG_ORIGINAL_AREA_MAP=0");
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
