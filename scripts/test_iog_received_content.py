#!/usr/bin/env python3
"""Test exact received-content warp guards using caller's private ROM.

Links the actual adapter, with synthetic CPU contexts and registration only.
Does not execute guest instructions or claim gameplay/visual qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PIN='dded02334752a7122d4db8da4df4aa56d6997c078065e69183865dc23202973f'
HARNESS=r'''
#include "iog_received_content.c"
Snes *g_snes;
static unsigned checks,registered;static uint32_t hook_pc[8],redirect;
#define C(x)do{checks++;if(!(x)){fprintf(stderr,"line %u: %s\n",__LINE__,#x);exit(1);}}while(0)
bool interp_bridge_add_pre_opcode_hook(uint32_t pc,InterpPreOpcodeHook hook)
{C(registered<8);C(hook==(registered<4?Destination:ClassroomDoors));hook_pc[registered++]=pc;return true;}
void interp_bridge_pre_opcode_redirect(uint32_t pc){redirect=pc;}
static void word(uint8_t*r,unsigned at,unsigned v){r[at]=(uint8_t)v;r[at+1]=(uint8_t)(v>>8);}
static CpuState seed(uint8_t *ram){
 memset(ram,0,131072);word(ram,0x100A,0xB56E);ram[0x100C]=0x83;word(ram,0x644,0xFE);word(ram,0x642,1);
 CpuState c;memset(&c,0,sizeof(c));c.ram=ram;c.A=0x178;c.X=0x1234;c.Y=0x5678;c.S=0x1ef;c.P=0xCF;
 c.D=0x1000;c.DB=0x81;c.cycles=123456;c.master_cycles=987654;c.PB=0x80;c.open_bus=0x4c;c._flag_N=1;c._flag_C=1;return c;
}
static void check(CpuState *cpu,uint32_t pc,bool fix){
 CpuState before=*cpu;uint8_t old[131072];memcpy(old,cpu->ram,sizeof(old));
 unsigned long long count=content.fixes;Destination(cpu,pc);
 C(cpu->A==(fix?0x278:before.A));C(content.fixes==count+(fix?1:0));
 before.A=cpu->A;C(!memcmp(&before,cpu,sizeof(before)));C(!memcmp(old,cpu->ram,sizeof(old)));
}
static void check_door(CpuState *cpu,uint32_t pc,unsigned warp,unsigned target){
 CpuState before=*cpu;uint8_t old[131072];memcpy(old,cpu->ram,sizeof(old));
 redirect=0;ClassroomDoors(cpu,pc);C(redirect==target);
 C(cpu->X==(warp?warp:before.X));before.X=cpu->X;
 C(!memcmp(&before,cpu,sizeof(before)));C(!memcmp(old,cpu->ram,sizeof(old)));
}
int main(int argc,char **argv){
 C(argc==2);FILE*f=fopen(argv[1],"rb");C(f!=NULL);uint8_t*rom=malloc(3276800);C(rom!=NULL);
 C(fread(rom,1,3276800,f)==3276800);fclose(f);static uint8_t ram[131072];static Cart cart;static Snes machine;
 cart.rom=rom;cart.romSize=cart.romImageSize=3276800;cart.type=CART_HIROM;machine.cart=&cart;g_snes=&machine;
 C(IogReceivedContentInitialize());C(registered==8);C(content.enabled&&content.classroom);
 C(IogReceivedContentInitialize()&&registered==8);
 CpuState c;
 for(unsigned i=0;i<4;i++)for(unsigned j=0;j<4;j++){
  c=seed(ram);ram[0x100C]=(uint8_t)(3+0x40*j);check(&c,hook_pc[i],true);
 }
 c=seed(ram);check(&c,0x80A351,true);
 for(unsigned i=0;i<14;i++){
  c=seed(ram);switch(i){
   case 0:c.D=1;break;case 1:c.DB=1;break;case 2:c.emulation=1;break;
   case 3:c.m_flag=1;break;case 4:c.x_flag=1;break;case 5:c.P|=0x20;break;case 6:c.P|=0x10;break;
   case 7:c.A=0x278;break;case 8:word(ram,0x644,1);break;case 9:word(ram,0x642,0xa);break;
   case 10:word(ram,0x100A,0xC4C4);break;case 11:word(ram,0x100A,0xC4F4);break;
   case 12:ram[0x100C]=0x7e;break;case 13:word(ram,0x100A,0xb56d);break;
  }check(&c,0x80A351,false);
 }
 c=seed(ram);check(&c,0x80A350,false);check(&c,0x81A351,false);
 for(unsigned i=0;i<2;i++){
  unsigned at=i?0x3B56C:0xA351;rom[at]^=1;c=seed(ram);check(&c,0x80A351,false);rom[at]^=1;
 }
 cart.romImageSize--;c=seed(ram);check(&c,0x80A351,false);cart.romImageSize++;
 unsigned type=cart.type;cart.type=0;check(&c,0x80A351,false);cart.type=type;
 c=seed(ram);c.D=0;word(ram,0x644,8);word(ram,0x642,0);
 word(ram,0xd4,ClassroomWestWarp);word(ram,0xd6,ClassroomExtendedWarps);
 for(unsigned i=4;i<8;i++){
  unsigned bank=hook_pc[i]&0xff0000;
  word(ram,0x9a2,128);word(ram,0x9a4,96);
  check_door(&c,hook_pc[i],ClassroomWestWarp,bank|ExecuteStandardWarp);
  word(ram,0x9a2,512);word(ram,0x9a4,144);
  check_door(&c,hook_pc[i],ClassroomEastWarp,bank|ExecuteStandardWarp);
  word(ram,0x9a2,568);check_door(&c,hook_pc[i],0,bank|CheckExtendedWarps);
  word(ram,0x9a2,192);word(ram,0x9a4,96);
  check_door(&c,hook_pc[i],0,bank|CheckExtendedWarps);
  word(ram,0x9a2,512);word(ram,0x9a4,142);
  check_door(&c,hook_pc[i],0,bank|CheckExtendedWarps);
 }
 word(ram,0x9a2,512);word(ram,0x9a4,144);
 word(ram,0xd6,0);check_door(&c,hook_pc[6],0,0);
 word(ram,0xd6,ClassroomExtendedWarps);word(ram,0x642,1);check_door(&c,hook_pc[6],0,0);
 word(ram,0x642,0);word(ram,0x644,1);check_door(&c,hook_pc[6],0,0);
 word(ram,0x644,8);content.classroom=false;check_door(&c,hook_pc[6],0,0);
 /* Initialization refuses unsupported identity/layout, before registration. */
 content.enabled=false;registered=0;rom[0x100]^=1;C(!IogReceivedContentInitialize()&&!registered);rom[0x100]^=1;
 cart.romImageSize--;C(!IogReceivedContentInitialize()&&!registered);cart.romImageSize++;
 cart.type=0;C(!IogReceivedContentInitialize()&&!registered);cart.type=type;
 g_snes=NULL;C(!IogReceivedContentInitialize()&&!registered);g_snes=&machine;
 C(Matches(rom,3276800,RECEIVED_ROM));free(rom);
 printf("%u received-content assertions passed; destination and door guards, CPU/RAM/flags/cycles preserved outside selected registers\n",checks);return 0;
}
'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler',default='clang');p.add_argument('--rom',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    assert hashlib.sha256(a.rom.read_bytes()).hexdigest()==PIN
    out=a.out.resolve();assert out.is_relative_to((ROOT/'.local').resolve())
    out.mkdir(parents=True,exist_ok=False)
    source=out/'received-content-test.c';source.write_text(HARNESS);exe=out/'received-content-test.exe'
    inputs=[ROOT/'src/iog_received_content.c',ROOT/'src/iog_received_content.h',Path(__file__).resolve()]
    before={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in inputs}
    cmd=[a.compiler,'-std=c11','-O1','-Wall','-Wextra','-Werror',f'-DIOG_RECEIVED_REFERENCE_SHA256="{PIN}"',
         '-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),str(source),str(ROOT/'snesrecomp/runner/src/sha256.c'),'-o',str(exe)]
    r=subprocess.run(cmd,capture_output=True,text=True);(out/'build.log').write_text(r.stdout+r.stderr);r.check_returncode()
    env={k:v for k,v in os.environ.items() if k not in ('IOG_RECEIVED_CLASSROOM_DOORS','IOG_RECEIVED_CONTENT_AUDIT')}
    r=subprocess.run([str(exe),str(a.rom.resolve())],capture_output=True,text=True,timeout=30,env=env)
    (out/'run.log').write_text(r.stdout+r.stderr);r.check_returncode()
    assert before=={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in inputs}
    receipt=dict(passed=True,stdout=r.stdout,source_sha256=before,rom_sha256=PIN,command=cmd,
                 scope='Actual source adapter; synthetic preopcode contexts, exact private ROM, four handler/pointer aliases, refusal guards, unchanged other CPU state/flags/cycles/RAM/ROM. No guest execution or visual/campaign approval.')
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(r.stdout.strip())
if __name__=='__main__':main()
