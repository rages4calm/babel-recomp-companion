#!/usr/bin/env python3
"""Opt-in received-ROM input guard test; never runs guest instructions.

The caller supplies the private pinned ROM. The actual title adapter is linked
with a synthetic already-qualified map runtime. This tests input/hash/flag
guards, not campaign readiness or live controller operation. No inputs copied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "iog_map_host.c"
Snes *g_snes;Ppu *g_ppu;CpuState g_cpu;
static bool ready=true,speculative;static unsigned checks;
#define C(x)do{checks++;if(!(x)){fprintf(stderr,"line %u: %s\n",__LINE__,#x);exit(1);}}while(0)
bool RtlSpeculativeFrame(void){return speculative;}
IogMapRuntime *IogMapRuntimeCreate(const char *path){(void)path;return (IogMapRuntime*)(uintptr_t)1;}
void IogMapRuntimeDestroy(IogMapRuntime *r){(void)r;}
bool IogMapRuntimeFlush(IogMapRuntime *r){(void)r;return true;}
bool IogMapRuntimeUpdate(IogMapRuntime*r,const IogMapRuntimeFrame*f){(void)r;(void)f;return false;}
void IogMapRuntimeGetStatus(const IogMapRuntime*r,IogMapRuntimeStatus*s){(void)r;memset(s,0,sizeof(*s));s->frame_valid=ready;}
bool IogMapRuntimeGetViewSource(IogMapRuntime*r,IogMapViewSource*s){(void)r;(void)s;return false;}
static void word(uint8_t*r,unsigned at,unsigned value){r[at]=(uint8_t)value;r[at+1]=(uint8_t)(value>>8);}
static void request(bool expected){uint32_t pad=0;C(!IogMapHostInput(&pad));pad=SNES_PAD_START|SNES_PAD_RIGHT;C(!!IogMapHostInput(&pad)==expected);C(pad==(expected?SNES_PAD_RIGHT:SNES_PAD_START|SNES_PAD_RIGHT));}
int main(int argc,char**argv){
 C(argc==2);FILE*f=fopen(argv[1],"rb");C(f!=NULL);C(!fseek(f,0,SEEK_END));long size=ftell(f);C(size==3276800);rewind(f);
 uint8_t *rom=malloc((size_t)size);C(rom!=NULL);C(fread(rom,1,(size_t)size,f)==(size_t)size);fclose(f);
 uint8_t hash[32],pin[32];sha256_compute(rom,(size_t)size,hash);C(Digest("dded02334752a7122d4db8da4df4aa56d6997c078065e69183865dc23202973f",pin)&&!memcmp(hash,pin,32));
 static Snes machine;static Cart cart;static uint8_t ram[131072];machine.ram=ram;machine.cart=&cart;g_snes=&machine;
 cart.rom=rom;cart.type=CART_HIROM;cart.romImageSize=cart.romSize=(uint32_t)size;
 word(ram,0x9aa,1);word(ram,0x644,0x85);g_cpu.master_cycles=123456;
 (void)IogMapHostControlGet(0);uint8_t before[32],after[32];sha256_compute(ram,sizeof(ram),before);
 request(true);uint32_t pad=SNES_PAD_START;C(!IogMapHostInput(&pad)&&!pad);
 sha256_compute(ram,sizeof(ram),after);C(!memcmp(before,after,32)&&g_cpu.master_cycles==123456);
 const unsigned guards[][2]={{0x9ae,8},{0x9ae,0x200},{0x6fa,1},{0x9ec,0x80},{0x9ec,0x2000},{0x9ec,0x4000},{0x642,1},{0x644,0xfe},{0x9aa,0}};
 for(unsigned n=0;n<sizeof(guards)/sizeof(guards[0]);n++){
  unsigned at=guards[n][0],old=Word(ram,at);word(ram,at,guards[n][1]);request(false);word(ram,at,old);
 }
 ready=false;request(false);ready=true;speculative=true;request(false);speculative=false;
 unsigned oldtype=cart.type;cart.type=0;request(false);cart.type=oldtype;
 cart.romImageSize--;request(false);cart.romImageSize++;
 rom[0x3ec66]^=1;request(false);rom[0x3ec66]^=1;
 rom[0x2f8f7]^=1;request(false);rom[0x2f8f7]^=1;
 putenv("IOG_ORIGINAL_AREA_MAP=1");request(false);putenv("IOG_ORIGINAL_AREA_MAP=0");
 request(true);
 /* A mods-off received profile still has controller-only configuration and
  * native host persistence, without admitting any Original title plugin. */
 C(IogMapHostOpen());IogMapHostNav(0,100);IogMapHostNav(SNES_PAD_SELECT,116);C(controls_open);
 IogMapHostNav(0,132);IogMapHostNav(SNES_PAD_RIGHT,148);C(!ui.radar&&preferences_saved);
 IogMapHostControlSet(IOG_MAP_BACK,5);C(controls[IOG_MAP_BACK]==5&&preferences_saved);
 const uint32_t *image=NULL;int width=0,height=0;
 C(IogMapHostImage(&image,&width,&height)&&image&&width==598&&height==336);
 IogMapHostShutdown();C(IogMapHostControlGet(IOG_MAP_BACK)==5&&!IogMapHostRadarEnabled());
 sha256_compute(ram,sizeof(ram),after);C(!memcmp(before,after,32)&&g_cpu.master_cycles==123456);
 IogMapHostShutdown();free(rom);g_snes=NULL;
 printf("%u received-map input assertions passed\n",checks);return 0;
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',default='cc');p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 assert hashlib.sha256(a.rom.read_bytes()).hexdigest()=='dded02334752a7122d4db8da4df4aa56d6997c078065e69183865dc23202973f'
 out=a.out.resolve();assert out.is_relative_to((ROOT/'.local').resolve());out.mkdir(parents=True,exist_ok=False);(out/'saves/maps').mkdir(parents=True)
 source=out/'received-input.c';source.write_text(HARNESS);exe=out/'received-input.exe'
 inputs=[ROOT/'src'/n for n in ('iog_map_host.c','iog_map_host.h','iog_map_preferences.c','iog_map_preferences.h','iog_map_ui.c','iog_map_ui.h','iog_map_view.c','iog_map_discovery.c')]+[ROOT/'snesrecomp/runner/src/snes_overlay_draw.c',ROOT/'snesrecomp/runner/src/sha256.c']
 cmd=[a.compiler,'-std=c11','-O1','-Wall','-Wextra','-Werror','-DSNESRECOMP_ENABLE_MODS=0','-DIOG_RECEIVED_REFERENCE=1','-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),str(source),*[str(x)for x in inputs if x.suffix=='.c'and x.name!='iog_map_host.c'],'-o',str(exe)]
 r=subprocess.run(cmd,capture_output=True,text=True);(out/'build.log').write_text(r.stdout+r.stderr);r.check_returncode()
 r=subprocess.run([str(exe),str(a.rom.resolve())],cwd=out,capture_output=True,text=True,timeout=30);(out/'run.log').write_text(r.stdout+r.stderr);r.check_returncode()
 receipt=dict(passed=True,stdout=r.stdout,sources={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in inputs+[Path(__file__)]},scope='Pinned received ROM and actual input adapter with synthetic qualified-ready runtime; source/hash/menu/music/world/pause guards, held consumption and unchanged RAM/cycles. No guest execution, physical controller or campaign qualification.')
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(r.stdout.strip())
if __name__=='__main__':main()
