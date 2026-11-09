"""Direct fixed call/return effects retain the actual owning bridge protocol."""
from pathlib import Path
import hashlib,json,os,re,shutil,subprocess
import pytest
import snes65816 as decoder
from v2.native_effects import emit
from v2.emit_function import emit_function
from test_native_continuation import _source as base_source
from test_region_pacing import _c_function

REPO=Path(__file__).resolve().parents[2]
BANKS=(0x02,0x42,0x82,0xc2)

SUPPORT=r'''
static unsigned call_fault,aot_mode;static uint16_t call_sp=0x1ff;
static InterpNativeInstructionStep call_actual;
static int call_corrupt(Interp816 *in){
 if(call_fault==1)return interp816_runOpcode(in);
 uint16_t before=in->sp;int cycles=call_actual(in);
 if(call_fault==2)++cycles;if(call_fault==3)--in->sp;
 if(call_fault==4)in->k&=0x7f;if(call_fault==5)in->sp=before;
 return cycles;
}
static void call_hook(CpuState *cpu,uint32_t pc){
 ++visits;
 if(hook_kind==1)RAM[pc+1]^=1;
 if(hook_kind==2){cpu->m_flag=!cpu->m_flag;cpu->x_flag=!cpu->x_flag;cpu_mirrors_to_p(cpu);}
 if(hook_kind==3)interp_bridge_pre_opcode_redirect(pc+3);
 if(hook_kind==4){uint16_t s=cpu->S;uint64_t n=interp_bridge_native_continuation_insns_total();
  cpu_push_interrupt_frame_at(cpu,pc);CHECK(interp_bridge_run_interrupt(cpu,0x008300)==1,"real nested IRQ/NMI call handler RTI");
  CHECK(cpu->S==s&&interp_bridge_native_continuation_insns_total()==n,"interrupt call frames restore and native ISR remains refused");++nested;}
}
'''

SETUP=r'''
static void setup(int native,int bank,int fast,int m,int x,int unused,int irq,int hk){
 (void)unused;memset(RAM,0,MEMSZ);init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);memset(&g_test_cart,0,sizeof g_test_cart);
 static Dma dma;memset(&dma,0,sizeof dma);g_test_snes.dma=&dma;g_test_snes.hdmaBeamOff=true;
 g_test_snes.cart=&g_test_cart;g_test_snes.ram=RAM;g_test_cart.type=CART_HIROM;g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
 snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(true);g_test_snes.vPos=224;
 if(irq){g_test_snes.hIrqEnabled=true;g_test_snes.hTimer=20;}
 g_c.emulation=0;g_c.m_flag=m;g_c.x_flag=x;g_c.A=0x1234;g_c.X=x?0x34:0x1234;g_c.Y=x?0x78:0x5678;g_c.DB=0x7e;g_c.S=call_sp;
 g_c._flag_I=!irq;cpu_mirrors_to_p(&g_c);g_memsel=fast;
 g_push_count=g_interp_push_count=g_push_depth=g_pop_underflow=g_recomp_stack_top=0;g_abandon_called=0;
 unexpected_dispatch=rdnmi_reads=0;visits=nested=handler_entries=0;hook_kind=hk;
 /* Keep AOT policy equal in both sides; only fixed-instruction registration differs. */
 interp_bridge_set_interpret_all(0);interp_bridge_reset_dynamic_cache();interp_bridge_clear_native_rdnmi_polls();interp_bridge_clear_idle_polls();interp_bridge_clear_native_instructions();
 interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_set_lle_bounce_exclusions(NULL,0);
 code_base=((uint32_t)bank<<16)|0x8100;
 const uint8_t owner[]={0x22,0,0x81,(uint8_t)bank,0x85,0x40,0x80,0xfe};
 const uint8_t body[]={0x20,0x40,0x81,0x22,0x80,0x81,0x83,0x6b};const uint8_t near[]={0x1a,0x60};
 const uint8_t far[]={0x20,0xa0,0x81,0x1a,0x6b};const uint8_t simple_far[]={0x1a,0x6b};
 const uint8_t irqbody[]={0x20,0x08,0x83,0xe6,0x70,0x40};const uint8_t irqnear[]={0x1a,0x60};
 load(0x838000,owner,sizeof owner);load(code_base,body,sizeof body);load(((uint32_t)bank<<16)|0x8140,near,sizeof near);
 load(0x838180,aot_mode==1?simple_far:far,aot_mode==1?sizeof simple_far:sizeof far);load(0x8381a0,near,sizeof near);
 load(0x008300,irqbody,sizeof irqbody);load(0x008308,irqnear,sizeof irqnear);
 if(native){InterpNativeInstruction items[1024];size_t count=sizeof ni_entries/sizeof*ni_entries;CHECK(count<=1024,"bounded generated call descriptors");memcpy(items,ni_entries,sizeof ni_entries);
  if(call_fault)for(size_t i=0;i<count;i++)if(items[i].pc24==0x838000&&items[i].m==m&&items[i].x==x){call_actual=items[i].step;items[i].step=call_corrupt;break;}
  CHECK(interp_bridge_add_native_instructions(items,count),"production generated direct call/return descriptors");}
 if(variant==1)g_test_cart.type=CART_SA1;if(variant==2)g_test_cart.rom=NULL;
 if(variant==3)interp_bridge_set_lle_bounce_exclusions(&code_base,1);
 if(hk)interp_bridge_add_pre_opcode_hook(code_base,call_hook);
 bus_hash=1469598103934665603ULL;bus_reads=bus_writes=0;last_data_ipc=overlay_probes=0;
}
'''

MAIN=r'''
/* These dispatch sentinels model host control, while every guest call/return
 * in the surrounding owner is still the production-emitted effect. */
static void sentinel_checks(void){
 for(unsigned mode=4;mode<=7;mode++)for(int native=0;native<=1;native++){
  aot_mode=mode;setup(native,0x82,1,1,0,0,0,0);
  uint64 ni=interp_bridge_native_continuation_insns_total();interp_bridge_set_master_deadline(mode==6?1000:10000);
  int result=interp_bridge_run_until_quiescent(&g_c,0x838000);
  if(mode==7)CHECK(!result,"ancestor SKIP2 contained rather than resuming wrong owner");
  else CHECK(result,"bounded same-owner sentinel handled");
  if(mode==4||mode==5)CHECK(g_c.S==call_sp,"SKIP1/yield leaves exact restored owner stack");
  if(mode==6){CHECK(interp_bridge_lle_resume_pc()==0x838180&&g_c.S==(uint16_t)(call_sp-6),"deadline preserves suspended nested JSL and exact callee PC");
   aot_mode=0;interp_bridge_set_master_deadline(g_c.master_cycles+10000);
   CHECK(interp_bridge_run_until_quiescent(&g_c,0x838180)&&g_c.S==call_sp,"deadline continuation resumes real nested body and returns both frames");}
  CHECK((interp_bridge_native_continuation_insns_total()>ni)==native,"sentinel surrounds actually accepted native calls");interp_bridge_set_master_deadline(0);
 }
 aot_mode=8;setup(1,0x83,1,1,0,0,0,0);
 const unsigned at=0x83fffc;RAM[at]=0x20;RAM[at+1]=0x80;RAM[at+2]=0x81;
 RAM[0x830001]=0x80;RAM[0x830002]=0xfe;
 const uint8_t inline_body[]={0xc2,0x20,0xa3,1,0x18,0x69,2,0,0x83,1,0x60};load(0x838180,inline_body,sizeof inline_body);
 uint64 ni=interp_bridge_native_continuation_insns_total();interp_bridge_set_master_deadline(1000);
 CHECK(interp_bridge_run_until_quiescent(&g_c,at),"actual AOT inline-return owner yields");
 CHECK(interp_bridge_lle_resume_pc()==0x830001&&g_c.S==call_sp,"two inline bytes wrap PC16 after actual generated stack return rewrite");
 CHECK(interp_bridge_native_continuation_insns_total()>ni,"inline boundary call really native");interp_bridge_set_master_deadline(0);
}
static void boundaries(void){
 const unsigned ops[]={0x20,0x22};
 for(unsigned b=0;b<4;b++)for(unsigned o=0;o<2;o++){
  unsigned bank=(unsigned[]){2,0x42,0x82,0xc2}[b],op=ops[o],at=(bank<<16)|(op==0x20?0xfffd:0xfffc);
  aot_mode=3;setup(1,bank,0,1,1,0,0,0);RAM[at]=op;RAM[at+1]=0x80;RAM[at+2]=0x81;if(op==0x22)RAM[at+3]=0x83;
  RAM[(bank<<16)|0x8180]=0x1a;RAM[(bank<<16)|0x8181]=0x60;RAM[0x838180]=0x1a;RAM[0x838181]=0x6b;
  interp_bridge_set_master_deadline(100);CHECK(interp_bridge_run_until_quiescent(&g_c,at)==1,"paired boundary owner returns");
  CHECK(interp_bridge_lle_resume_pc()==(bank<<16),"architectural PC16 wrap preserves callerPB after actual AOT RTS/RTL");
  CHECK(g_c.S==call_sp,"paired boundary pops exact two/three-byte frame");interp_bridge_set_master_deadline(0);
 }
}
int main(int argc,char **argv){
 RAM=malloc(MEMSZ);expected_memory=malloc(MEMSZ);if(!RAM||!expected_memory)return 2;call_fault=argc>1?(unsigned)atoi(argv[1]):0;
 if(call_fault==99){call_fault=0;boundaries();}
 else if(call_fault){aot_mode=0;pair(0x82,1,1,0,0,10000,0,0,0,1);}
 else {
  unsigned banks[]={2,0x42,0x82,0xc2};uint16_t stacks[]={0x1ff,0xbff,0,0xffff};
  for(unsigned b=0;b<4;b++)for(unsigned f=0;f<2;f++)for(unsigned m=0;m<2;m++)for(unsigned x=0;x<2;x++)for(aot_mode=0;aot_mode<3;aot_mode++)for(unsigned s=0;s<4;s++){
   call_sp=stacks[s];pair(banks[b],f,m,x,0,10000,0,0,0,1);}
  call_sp=0x1ff;
  for(aot_mode=0;aot_mode<3;aot_mode++)for(unsigned m=0;m<2;m++)for(unsigned x=0;x<2;x++)for(unsigned d=1;d<=200;d++)pair(0x82,1,m,x,0,d,0,0,0,-1);
  for(aot_mode=0;aot_mode<3;aot_mode++)for(unsigned h=1;h<=4;h++)pair(0x82,1,1,0,0,10000,0,h,0,1);
  aot_mode=0;for(unsigned m=0;m<2;m++)for(unsigned x=0;x<2;x++){pair(0x82,1,m,x,0,10000,1,0,0,-1);pair(0x82,1,m,x,0,70,0,0,1,-1);}
  for(variant=1;variant<=3;variant++)pair(0x82,1,1,0,0,10000,0,0,0,-1);variant=0;boundaries();sentinel_checks();
 }
 printf("call_pairs=%u checks=%d failures=%d\n",pairs,g_check,fixture_fail);free(RAM);free(expected_memory);return fixture_fail?1:0;
}
'''


def _source():
    base=base_source();base=base[:base.index('static void metadata_checks(')]
    records={0x838000:bytes.fromhex('22008182'),0x008300:bytes.fromhex('200883'),0x008309:b'\x60',0x838180:bytes.fromhex('20a081'),0x838184:b'\x6b',0x838181:b'\x6b',0x8381a1:b'\x60',0x83fffc:bytes.fromhex('208081')}
    for bank in BANKS:
        records.update({bank<<16|0x8100:bytes.fromhex('204081'),bank<<16|0x8103:bytes.fromhex('22808183'),bank<<16|0x8107:b'\x6b',bank<<16|0x8141:b'\x60'})
    entries=[]
    # Owner JSL's bank operand differs per flow. Register its fixed target only
    # for82; other aliases deliberately retain the reference opcode there.
    for pc,code in records.items():
        name,mode,_=decoder.opcode_table()[code[0]]
        for m in range(2):
            for x in range(2):entries.append(dict(pc24=pc,m=m,x=x,e=0,bytes=code,mnemonic=name,immediate=False))
    generated,receipt=emit((REPO/'runner/src/snes/interp816.c').read_text(encoding='utf-8'),entries,registration_name='RegisterCalls')
    assert not re.search(r'\b(?:interp816_|ni_\d\d_)(?:runOpcode|doOpcode)\s*\(',generated)
    # Three actual generated AOT callees; Outer enters an explicit missing-body
    # wrapper that uses the production interpreter call-frame bridge.
    old=decoder.get_rom_mapping();decoder.set_rom_mapping('hirom');aot=[]
    try:
        for name,raw in [('CpNear',bytes.fromhex('1a60')),('CpFar',bytes.fromhex('1a6b')),('CpOuter',bytes.fromhex('20a0811a6b')),('CpInline',bytes.fromhex('c220a30118690200830160'))]:
            for m in range(2):
                for x in range(2):
                    rom=bytearray(0x40000);rom[0x38180:0x38180+len(raw)]=raw
                    aot.append(emit_function(bytes(rom),0x83,0x8180,m,x,end=0x8180+len(raw),func_name=name,instruction_blocks=True,region_paced=True,inline_arg_map={0x838180:2}if name=='CpInline'else None))
    finally:decoder.set_rom_mapping(old)
    declarations='\n'.join(f'RecompReturn {n}_M{m}X{x}(CpuState*);'for n in ['CpNear','CpFar','CpOuter','CpInline']for m in range(2)for x in range(2))
    wrappers='\n'.join(f'RecompReturn bank_83_81A0_M{m}X{x}(CpuState*cpu){{return interp_tier_run_call_frame(cpu,((uint32_t)cpu->PB<<16)|0x81a0,0x838180,2,NULL);}}'for m in range(2)for x in range(2))
    dispatch='int cpu_dispatch_has_entry(CpuState*cpu,uint32 pc){(void)cpu;return aot_mode&&((pc&0xffff)==0x8180);}\n'
    dispatch+='RecompReturn cpu_dispatch_pc_paired(CpuState*cpu,uint32 pc,uint8 frame){(void)pc;cpu->host_return_valid=frame;'
    dispatch+='if(aot_mode==4){cpu->S=(uint16)(cpu->S+frame);return RECOMP_RETURN_SKIP_1;}if(aot_mode==5)return interp_bridge_lle_yield_unwind(cpu,pc);if(aot_mode==6){cpu->master_cycles=2000;if(interp_bridge_lle_master_deadline_reached(cpu))return interp_bridge_lle_yield_unwind(cpu,pc);++unexpected_dispatch;}if(aot_mode==7)return RECOMP_RETURN_SKIP_2;'
    dispatch+='unsigned k=(cpu->m_flag<<1)|cpu->x_flag;switch(aot_mode==8?3:aot_mode==3?(frame==2?0:1):aot_mode==1?1:2){'
    for flow,name in enumerate(['CpNear','CpFar','CpOuter','CpInline']):
        dispatch+=f'case {flow}:switch(k){{'+''.join(f'case {(m<<1)|x}:return {name}_M{m}X{x}(cpu);'for m in range(2)for x in range(2))+'}break;'
    dispatch+='}++unexpected_dispatch;return RECOMP_RETURN_NORMAL;}\n'
    for name in ('cpu_dispatch_has_entry','cpu_dispatch_pc_paired','cpu_dispatch_inline_arg_bytes'):
        base=base.replace(_c_function(base,name).rstrip(),'')
    dispatch+='uint8 cpu_dispatch_inline_arg_bytes(uint32 pc){(void)pc;return aot_mode==8?2:0;}\n'
    start=base.index('static void setup(')
    base=base[:start]+SUPPORT+generated+'\n'+declarations+wrappers+'\n'+'\n'.join(aot)+dispatch+base[start:]
    base=base.replace(_c_function(base,'setup').rstrip(),SETUP)
    base=base.replace('CHECK(g_c.S==0x1fc,"deadline inherits suspended real JSL frame");','')
    base=base.replace('g_c.S!=0x1ff','g_c.S!=call_sp').replace('g_c.S==0x1ff&&RAM[0x70]==1','g_c.S==call_sp&&RAM[0x70]==1')
    base=base.replace('stats[32]','stats[1024]').replace('stats(stats,32)','stats(stats,1024)').replace('n<=32','n<=1024').replace('i<32','i<1024')
    return base+MAIN,receipt


@pytest.fixture(scope='module')
def call_binary(tmp_path_factory):
    out=tmp_path_factory.mktemp('native-call-core');cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    text,receipt=_source();src=out/'calls.c';src.write_text(text,encoding='utf-8');(out/'emission.json').write_text(json.dumps(receipt,indent=2))
    core=out/'snes_core.c';core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n')
    exe=out/('calls.exe'if os.name=='nt'else'calls')
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(src),str(core),*[str(REPO/'runner/src'/p)for p in ['snes/interp816.c','snes/interp_bridge.c','snes/tier2_capture.c','sha256.c','snes/cx4.c','snes/dma.c','snes/sdd1.c']],'-lm','-o',str(exe)]
    built=subprocess.run(command,capture_output=True,text=True,timeout=90);(out/'compile.json').write_text(json.dumps(dict(command=command,exit_code=built.returncode,stdout=built.stdout,stderr=built.stderr),indent=2));assert built.returncode==0,built.stdout+built.stderr
    return out,exe


@pytest.mark.parametrize('lookup',['0','1'])
@pytest.mark.parametrize('fault',[0,1,2,3,4,5,99])
def test_native_call_owner_protocol(call_binary,lookup,fault):
    out,exe=call_binary;env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup)
    p=subprocess.run([str(exe),str(fault)],capture_output=True,text=True,env=env,timeout=90,cwd=out)
    (out/f'run-{lookup}-{fault}.json').write_text(json.dumps(dict(exit_code=p.returncode,lookup=lookup,fault=fault,stdout=p.stdout,stderr=p.stderr),indent=2))
    if fault not in (0,99):assert p.returncode==1 and'FAIL:'in p.stdout
    else:assert p.returncode==0,p.stdout+p.stderr
