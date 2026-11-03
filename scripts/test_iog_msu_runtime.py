#!/usr/bin/env python3
"""ROM-free actual MSU callback/activation test with synthetic song metadata.

No game ROM, soundtrack or owner save is read. Host/MSU services are stubs;
actual first-frame generation handling and original upload state machine run.
Real engine/audio restore proof remains a separate paced fixture.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess
from test_iog_mods_runtime import STUBS
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "@SOURCE@"
#include <assert.h>
static unsigned assertions,writes,pumps,registered;
static uint64_t generation=40;
static bool pack=true,tracks=true;
static uint8_t ram[0x20000],rom[0x200000],original[0x200000];
static Cart cart={rom,sizeof rom};
static Snes machine={ram,&cart,0};
Snes *g_snes=&machine;
static SNESModFrameCallback callback;
#define CHECK(v) do { assertions++; if(!(v)){fprintf(stderr,"FAIL line%d: %s\n",__LINE__,#v);exit(1);} }while(0)
uint64_t RtlStateGeneration(void){return generation;}
bool IogRandomizerActive(void){return false;}
bool msu1_enabled(void){return pack;}
int msu1_track_present(uint16_t track){return tracks&&track==6;}
void msu1_write(uint32_t address,uint8_t value){(void)address;(void)value;writes++;}
void msu1_pump(void){pumps++;}
void cart_set_overlay_bank(Cart *target,int bank,const uint8_t *data){CHECK(target==&cart&&bank==15&&data);}
int snes_mod_register_activation_plugin(const char*id,SNESModActivationCallback fn){CHECK(!strcmp(id,"iog.msu1")&&fn==Activate);return 1;}
int snes_mod_register_frame_callback(SNESModFrameCallback fn){callback=fn;registered++;return 1;}
int snes_mod_register_apu_write_callback(SNESModApuWriteCallback fn){CHECK(fn==ApuWrite);return 1;}
static void prepare(void){
  memset(ram,0,sizeof ram);memset(rom,0,sizeof rom);
  for(unsigned id=1;id<=30;id++){
    unsigned p=0x1CBA6+3*(id-1);rom[p]=0;rom[p+1]=0;rom[p+2]=0x80;
  }
  unsigned p=0x1CBA6+3*(0x1B-1);rom[p+1]=0x90;
  memcpy(original,rom,sizeof rom);register_iog_msu1();
}
static void set_loaded_song(void){
  CHECK(g_ncopies>0);uint32_t ptr=g_copies[0].addr;
  ram[0x687]=(uint8_t)ptr;ram[0x688]=(uint8_t)(ptr>>8);ram[0x689]=(uint8_t)(ptr>>16);
  ram[0x3e]=ram[0x687];ram[0x3f]=ram[0x688];ram[0x40]=ram[0x689];ram[0x6f2]=1;
}
int main(int argc,char**argv){
  CHECK(argc==2);prepare();
  if(!strcmp(argv[1],"missing-pack")||!strcmp(argv[1],"missing-tracks")){
    if(!strcmp(argv[1],"missing-pack"))pack=false;else tracks=false;
    Activate();CHECK(!registered&&!writes&&!callback);CHECK(!memcmp(rom,original,sizeof rom));
  }else{
    Activate();CHECK(callback==Frame&&registered==1);CHECK(g_ncopies==1);set_loaded_song();
    if(!strcmp(argv[1],"first-load")){
      generation++;callback();CHECK(g_track==6&&writes==4&&pumps==1);
      callback();CHECK(writes==4&&pumps==2); /* no repeated restart */
      generation++;ram[0x687]=ram[0x688]=ram[0x689]=0;callback();CHECK(!g_track&&writes==5);
    }else if(!strcmp(argv[1],"cold-upload")){
      /* A boot's pending upload must survive its first frame unchanged. */
      g_loading=2;callback();CHECK(!g_track&&!writes&&g_loading==2&&g_quiet==1);
      callback();CHECK(g_loading==3&&!writes);
      ApuWrite(0x2140,1);CHECK(g_track==6&&writes==4);
    }else if(!strcmp(argv[1],"later-load")){
      callback();CHECK(!g_track&&!writes);generation++;callback();CHECK(g_track==6&&writes==4);
    }else CHECK(false);
  }
  printf("PASS %u actual MSU callback assertions: %s\n",assertions,argv[1]);return 0;
}
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'.local/batch-001/wide-005/mods/msu-callback-tests');p.add_argument('--compiler',default='clang')
    args=p.parse_args();out=args.out.resolve()
    if not out.is_relative_to((ROOT/'.local').resolve()):p.error('output must be private .local/')
    out.mkdir(parents=True,exist_ok=True);include=out/'include';stubs=dict(STUBS)
    stubs['mod_runtime.h']+='\ntypedef int (*SNESModApuWriteCallback)(uint16_t,uint8_t);\nint snes_mod_register_apu_write_callback(SNESModApuWriteCallback);\n'
    stubs['snes/cart.h']+='\nvoid cart_set_overlay_bank(Cart *,int,const uint8_t *);\n'
    stubs['snes/msu1.h']='#pragma once\n#include <stdint.h>\n#include <stdbool.h>\nbool msu1_enabled(void);\nint msu1_track_present(uint16_t);\nvoid msu1_write(uint32_t,uint8_t);\nvoid msu1_pump(void);\n'
    for name,text in stubs.items():
        path=include/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    source=out/'test.c';source.write_text(HARNESS.replace('@SOURCE@',(ROOT/'src/iog_msu.c').as_posix()))
    exe=out/'test.exe';command=[args.compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(include),'-I',str(ROOT/'src'),str(source),'-o',str(exe)]
    subprocess.run(command,check=True);rows=[]
    for name in ('first-load','later-load','cold-upload','missing-pack','missing-tracks'):
        result=subprocess.run([str(exe),name],capture_output=True,text=True,check=True);print(result.stdout.strip());rows.append(dict(case=name,passed=True,output=result.stdout.strip()))
    report=dict(passed=True,rom_free=True,synthetic_metadata=True,actual_source=True,framework_msu_services_stubbed=True,cases=rows,source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in (ROOT/'src/iog_msu.c',Path(__file__).resolve())})
    (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
