"""Production-emitted static branches inside the actual owning bridge loop."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from v2.native_effects import emit
from test_native_continuation import _source as base_source
from test_region_poll_fallback import REPO
from test_region_pacing import _c_function

OPS = [(0x10,"BPL"),(0x30,"BMI"),(0x50,"BVC"),(0x70,"BVS"),
       (0x90,"BCC"),(0xB0,"BCS"),(0xD0,"BNE"),(0xF0,"BEQ"),
       (0x80,"BRA"),(0x82,"BRL"),(0x4C,"JMP"),(0x5C,"JMP")]
BANKS = (0x02,0x42,0x82,0xC2,0x22)


def _spec(opcode, bank, variant):
    length=3 if opcode in (0x82,0x4C) else 4 if opcode==0x5C else 2
    pc=(0x9000,0x9100,0x90FE,0x10000-length,0x9200)[variant]
    delta=(14,-16,-128,-32,-length)[variant]
    fall=(bank<<16)|((pc+length)&65535)
    if opcode==0x4C:
        target=(pc+length+delta)&65535
        code=bytes((opcode,target&255,target>>8))
    elif opcode==0x5C:
        target=(pc+length+delta)&65535
        pb=bank if variant==4 else 0x85
        code=bytes((opcode,target&255,target>>8,pb))
    elif opcode==0x82:
        code=bytes((opcode,delta&255,(delta>>8)&255));target=(pc+length+delta)&65535
    else:
        code=bytes((opcode,delta&255));target=(pc+length+delta)&65535
    target=((code[3]if opcode==0x5C else bank)<<16)|target
    return (bank<<16)|pc,code,target,fall


C_MAIN=r'''
typedef struct BranchSpec {uint32 pc,target,fall;uint8 length,bytes[4];} BranchSpec;
/* SPECS */
static unsigned fault,hook_type,hook_visits,observer_visits,nmi_calls;
static uint32 branch_pc,target_pc,fall_pc,alternate_pc;
static unsigned branch_op,current_m;
static InterpNativeInstructionStep actual_step;
static int corrupt_step(Interp816 *in){
  if(fault==1)return interp816_runOpcode(in); /* deliberate false-native control */
  if(fault==4)(void)in->read(in->mem,((uint32)in->k<<16)|in->pc);
  int cycles=actual_step(in);
  if(fault==2)++cycles;
  if(fault==3)in->pc^=1;
  if(fault==5)in->sp+=3;
  return cycles;
}
static void payload(uint32 pc,unsigned marker,int m){
  uint8 code[]={0xa9,(uint8)marker,0,0x8f,0,3,0x7e,0x6b};
  if(m){memmove(code+2,code+3,5);load(pc,code,7);}else load(pc,code,8);
}
static void edit_operand(void){
  uint16 target=(uint16)alternate_pc;
  if(branch_op==0x4c||branch_op==0x5c){RAM[branch_pc+1]=(uint8)target;RAM[branch_pc+2]=(uint8)(target>>8);}
  else {int16_t delta=(int16_t)(target-(uint16)(branch_pc+(branch_op==0x82?3:2)));
    RAM[branch_pc+1]=(uint8)delta;if(branch_op==0x82)RAM[branch_pc+2]=(uint8)(delta>>8);}
}
static void observe_branch(uint32 pc,int m,int x){
  (void)m;(void)x;if(pc==branch_pc&&!observer_visits++){edit_operand();}
}
static void branch_hook(CpuState *cpu,uint32 pc){
  ++hook_visits;
  if(hook_visits!=1)return;
  if(hook_type==1)edit_operand();
  if(hook_type==2)interp_bridge_pre_opcode_redirect(alternate_pc);
  if(hook_type==3)cpu->PB=4;
  if(hook_type==4){cpu->m_flag=!cpu->m_flag;cpu_mirrors_to_p(cpu);
    payload(fall_pc,0x22,cpu->m_flag);if(target_pc!=branch_pc)payload(target_pc,0x33,cpu->m_flag);payload(alternate_pc,0x44,cpu->m_flag);}
  if(hook_type==5){cpu->emulation=cpu->m_flag=cpu->x_flag=1;cpu_mirrors_to_p(cpu);
    payload(fall_pc,0x22,1);if(target_pc!=branch_pc)payload(target_pc,0x33,1);payload(alternate_pc,0x44,1);}
  if(hook_type==6){
    uint64 ni=interp_bridge_native_continuation_insns_total(),deadline=10000;uint16 sp=cpu->S;
    g_test_snes.inNmi=g_test_snes.rdnmiPending=g_test_snes.nmiEnabled=true;
    cpu_push_interrupt_frame_at(cpu,pc);interp_bridge_set_master_deadline(cpu->master_cycles-1);
    CHECK(interp_bridge_run_interrupt(cpu,0x008300)==1,"real NMI nested JSR/RTS/RTI");
    CHECK(cpu->S==sp,"NMI restores real suspended owner frame");
    CHECK(interp_bridge_native_continuation_insns_total()==ni,"NMI branch remains interpreted");
    interp_bridge_set_master_deadline(deadline);++nmi_calls;
  }
}
typedef struct BranchResult {
  CpuState cpu;Snes snes;uint32 resume,ipc;
  uint64 bus,reads,writes,ii,ic,ni,nc,logical;unsigned hooks,observations,nmis;
  int quiescent,wai;
} BranchResult;
static BranchResult execute_branch(int native,unsigned opindex,unsigned bankindex,unsigned which,
                                  int m,int x,int fast,int take,uint64 deadline,int irq,unsigned hook,unsigned refusal){
  BranchResult out={0};const BranchSpec *s=&specs[opindex][bankindex][which];
  memset(RAM,0,MEMSZ);init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);memset(&g_test_cart,0,sizeof g_test_cart);
  static Dma dma;memset(&dma,0,sizeof dma);g_test_snes.cart=&g_test_cart;g_test_snes.ram=RAM;
  g_test_snes.dma=&dma;g_test_snes.hdmaBeamOff=true;g_test_cart.type=CART_HIROM;g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
  snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(true);
  g_test_snes.hPos=0;g_test_snes.vPos=224;g_test_snes.beamMasterLast=0;
  if(irq){g_test_snes.hIrqEnabled=true;g_test_snes.hTimer=20;}
  branch_pc=s->pc;target_pc=s->target;fall_pc=s->fall;branch_op=s->bytes[0];current_m=m;
  alternate_pc=((branch_op==0x5c?0x85:(branch_pc>>16))<<16)|0x9020;
  g_c.emulation=0;g_c.m_flag=m;g_c.x_flag=x;g_c.A=0x1234;g_c.X=0x0123;g_c.Y=0x4567;g_c.DB=0x7e;
  g_c._flag_C=1;g_c._flag_Z=0;g_c._flag_V=1;g_c._flag_N=0;g_c._flag_D=1;g_c._flag_I=!irq;
  if(branch_op==0x10)g_c._flag_N=!take;if(branch_op==0x30)g_c._flag_N=take;
  if(branch_op==0x50)g_c._flag_V=!take;if(branch_op==0x70)g_c._flag_V=take;
  if(branch_op==0x90)g_c._flag_C=!take;if(branch_op==0xb0)g_c._flag_C=take;
  if(branch_op==0xd0)g_c._flag_Z=!take;if(branch_op==0xf0)g_c._flag_Z=take;
  cpu_mirrors_to_p(&g_c);g_memsel=fast;
  g_push_count=g_interp_push_count=g_push_depth=g_pop_underflow=g_recomp_stack_top=0;g_abandon_called=unexpected_dispatch=rdnmi_reads=0;
  hook_visits=observer_visits=nmi_calls=0;hook_type=hook;interrupt_scope=refusal==5;
  interp_bridge_set_interpret_all(!native);interp_bridge_reset_dynamic_cache();interp_bridge_clear_idle_polls();
  interp_bridge_clear_native_rdnmi_polls();interp_bridge_clear_native_instructions();interp_bridge_set_pre_opcode_hook(0,NULL);
  interp_bridge_set_lle_bounce_exclusions(NULL,0);g_interp_bridge_pc_hook=NULL;
  (void)interp_bridge_lle_took_quiescent();(void)interp_bridge_lle_took_wai();
  payload(fall_pc,0x22,m);if(target_pc!=branch_pc)payload(target_pc,0x33,m);payload(alternate_pc,0x44,m);
  /* Foreign-PB hook lands on an ordinary NOP plus interpreted payload. */
  RAM[0x040000|(branch_pc&65535)]=0xea;payload(0x040000|((branch_pc+1)&65535),0x55,m);
  load(branch_pc,s->bytes,s->length);
  const uint8 owner[]={0x22,(uint8)branch_pc,(uint8)(branch_pc>>8),(uint8)(branch_pc>>16),0x85,0x40,0x80,0xfe};
  const uint8 handler[]={0x20,0x10,0x83,0x40},sub[]={0xe6,0x70,0xd0,0,0x60};
  load(0x838000,owner,sizeof owner);load(0x008300,handler,sizeof handler);load(0x008310,sub,sizeof sub);
  CHECK(registrations[opindex](),"production emitted branch registry");CHECK(RegisterNmiBranch(),"production NMI branch descriptor");
  if(fault||refusal==2){
    InterpNativeInstructionStats stats[128];size_t count=interp_bridge_native_instruction_stats(stats,128);
    CHECK(count<=128,"bounded branch registry");
    /* ENTRIES_SELECT */
    interp_bridge_clear_native_instructions();CHECK(interp_bridge_add_native_instructions(&chosen,1),"single selected branch descriptor");
  }
  if(refusal==1)interp_bridge_clear_native_instructions();
  if(refusal==3)g_test_cart.type=CART_SA1;if(refusal==4)g_test_cart.rom=NULL;
  if(refusal==6)g_test_cart.romSize=1;if(refusal==7)g_test_snes.cart=NULL;
  if(refusal==8)g_test_cart.overlayBank[(branch_pc>>16&0x7f)-0x20]=RAM;
  if(hook&&hook!=7)interp_bridge_add_pre_opcode_hook(branch_pc,branch_hook);
  if(hook==7)g_interp_bridge_pc_hook=observe_branch;
  bus_hash=1469598103934665603ULL;bus_reads=bus_writes=0;last_data_ipc=overlay_probes=0;
  uint64 ii=interp816_insns_total(),ic=interp816_cycles_total(),ni=interp_bridge_native_continuation_insns_total(),nc=interp_bridge_native_continuation_cycles_total(),logical=g_interp_bridge_steps;
  interp_bridge_set_master_deadline(deadline);
  CHECK(interp_bridge_run_until_quiescent(&g_c,0x838000)==1,"actual owning bridge branch yield/return");
  out.cpu=g_c;out.snes=g_test_snes;out.resume=interp_bridge_lle_resume_pc();out.ipc=last_data_ipc;
  out.bus=bus_hash;out.reads=bus_reads;out.writes=bus_writes;
  out.ii=interp816_insns_total()-ii;out.ic=interp816_cycles_total()-ic;
  out.ni=interp_bridge_native_continuation_insns_total()-ni;out.nc=interp_bridge_native_continuation_cycles_total()-nc;
  out.logical=g_interp_bridge_steps-logical;out.hooks=hook_visits;out.observations=observer_visits;out.nmis=nmi_calls;
  out.quiescent=interp_bridge_lle_took_quiescent();out.wai=interp_bridge_lle_took_wai();
  InterpNativeInstructionStats sites[128];size_t count=interp_bridge_native_instruction_stats(sites,128);uint64 si=0,sc=0;
  CHECK(count<=128,"branch stats bound");for(size_t i=0;i<count&&i<128;i++){si+=sites[i].insns;sc+=sites[i].cycles;
    if(sites[i].pc24==0x008312)CHECK(sites[i].insns==0,"host RTI native branch guard retained");}
  CHECK(si==out.ni&&sc==out.nc,"every native branch attributed per instruction");
  CHECK(!g_recomp_stack_top&&!g_pop_underflow&&!g_abandon_called&&!unexpected_dispatch,"no fabricated or leaked owner frames");
  interp_bridge_set_master_deadline(0);g_interp_bridge_pc_hook=NULL;return out;
}
static unsigned branch_pairs;static uint8 *reference_memory;
static void branch_pair(unsigned op,unsigned bank,unsigned which,int m,int x,int fast,int take,uint64 deadline,int irq,unsigned hook,unsigned refusal,int admission){
  BranchResult a=execute_branch(0,op,bank,which,m,x,fast,take,deadline,irq,hook,refusal);memcpy(reference_memory,RAM,MEMSZ);
  BranchResult b=execute_branch(1,op,bank,which,m,x,fast,take,deadline,irq,hook,refusal);
  CHECK(!memcmp(reference_memory,RAM,MEMSZ),"full memory and guest stack exact");
  CHECK(a.cpu.S==b.cpu.S,"inherited owner SP/watermark exact");
  CHECK(!memcmp(&a.cpu,&b.cpu,sizeof a.cpu),"full CPU/openbus/CPU+master clocks exact");
  CHECK(!memcmp(&a.snes,&b.snes,sizeof a.snes),"real comparator IRQ/NMI/core state exact");
  CHECK(a.resume==b.resume&&a.quiescent==b.quiescent&&a.wai==b.wai,"precise branch continuation/yield phase exact");
  CHECK(a.bus==b.bus&&a.reads==b.reads&&a.writes==b.writes,"every bus fetch/data/write/value/order exact");
  CHECK(a.ipc==b.ipc,"postbranch writes retain exact architectural IPC");
  CHECK(a.logical==b.logical,"per instruction logical retirement exact");
  CHECK(a.ii==b.ii+b.ni&&a.ic==b.ic+b.nc,"native branch never decoder relabelled");
  CHECK(!a.ni&&!a.nc,"forced reference never native");
  CHECK(a.hooks==b.hooks&&a.observations==b.observations&&a.nmis==b.nmis,"observer/prehook/NMI phases exact");
  if(admission>=0)CHECK(admission?b.ni>0:b.ni==0,"explicit branch admission/refusal");
  ++branch_pairs;
}
int main(int argc,char **argv){
  fault=argc>1?(unsigned)atoi(argv[1]):0;RAM=malloc(MEMSZ);reference_memory=malloc(MEMSZ);if(!RAM||!reference_memory)return 2;
  if(fault){branch_pair(6,2,0,1,0,1,1,1200,0,0,0,1);}
  else {
    for(unsigned op=0;op<12;op++)for(unsigned b=0;b<4;b++)for(unsigned v=0;v<5;v++)
      for(int m=0;m<2;m++)for(int x=0;x<2;x++)for(int fast=0;fast<2;fast++)for(int take=0;take<2;take++)
        branch_pair(op,b,v,m,x,fast,take,10000,0,0,0,1);
    for(unsigned op=0;op<12;op++)for(int fast=0;fast<2;fast++)for(int take=0;take<2;take++)
      for(uint64 d=1;d<=160;d++)branch_pair(op,2,0,1,0,fast,take,d,0,0,0,-1);
    for(unsigned op=0;op<12;op++)for(int take=0;take<2;take++){
      branch_pair(op,2,0,1,0,1,take,10000,1,0,0,-1);
      branch_pair(op,2,0,1,0,1,take,10000,0,6,0,1);
    }
    for(unsigned h=1;h<=7;h++)branch_pair(6,2,0,1,0,1,1,10000,0,h,0,(h==1||h==2||h==3||h==5||h==7)?0:1);
    for(unsigned r=1;r<=7;r++)branch_pair(6,2,0,1,0,1,1,10000,0,0,r,0);
    branch_pair(6,4,0,1,0,1,1,10000,0,0,8,0);
  }
  printf("pairs=%u checks=%d failures=%d native=%llu cycles=%llu\n",branch_pairs,g_check,fixture_fail,
    (unsigned long long)interp_bridge_native_continuation_insns_total(),(unsigned long long)interp_bridge_native_continuation_cycles_total());
  free(reference_memory);free(RAM);return fixture_fail?1:0;
}
'''


def _source():
    base=base_source();base=base[:base.index("int main(void){")]
    # Observe the payload write at its real architectural PC after a branch.
    base=base.replace("pc==0x7e0200||pc==0x7e0201","pc==0x7e0300||pc==0x7e0301")
    core=(REPO/"runner/src/snes/interp816.c").read_text()
    generated=[];receipts=[];spec_rows=[];entry_arrays=[];registrations=[]
    for opcode,mnemonic in OPS:
        entries=[];banks=[]
        for bank in BANKS:
            variants=[]
            for v in range(5):
                pc,code,target,fall=_spec(opcode,bank,v)
                variants.append('{'+f'0x{pc:06X},0x{target:06X},0x{fall:06X},{len(code)},'+
                                '{'+','.join(str(b)for b in code)+'}}')
                for m in range(2):
                    for x in range(2):entries.append(dict(pc24=pc,m=m,x=x,e=0,bytes=code,mnemonic=mnemonic,immediate=False))
            banks.append('{'+','.join(variants)+'}')
        spec_rows.append('{'+','.join(banks)+'}')
        name=f'RegisterBR{opcode:02X}'
        code,receipt=emit(core,entries,registration_name=name)
        assert not re.search(r'\binterp816_(?:runOpcode|doOpcode)\b',code)
        code=code.replace('NiOperands',f'Br{opcode:02X}Operands').replace('ni_',f'br{opcode:02X}_')
        generated.append(code);receipts.append(receipt);entry_arrays.append(f'br{opcode:02X}_entries');registrations.append(name)
    nmi=[dict(pc24=0x008312,m=m,x=x,e=0,bytes=b'\xd0\x00',mnemonic='BNE',immediate=False)for m in range(2)for x in range(2)]
    code,receipt=emit(core,nmi,registration_name='RegisterNmiBranch')
    generated.append(code.replace('NiOperands','NmiOperands').replace('ni_','nmi_'));receipts.append(receipt)
    spec='static const BranchSpec specs[12][5][5]={'+','.join(spec_rows)+'};\n'
    spec+='static bool (*registrations[])(void)={'+','.join(registrations)+'};\n'
    spec+='static const InterpNativeInstruction *entry_arrays[]={'+','.join(entry_arrays)+'};\n'
    choose=r'''
    InterpNativeInstruction chosen={0};int found=0;
    for(unsigned j=0;j<100;j++){const InterpNativeInstruction *d=&entry_arrays[opindex][j];
      if(d->pc24==branch_pc&&d->m==(refusal==2?!m:m)&&d->x==x){chosen=*d;found=1;break;}}
    CHECK(found,"exact production callback selected");actual_step=chosen.step;if(fault)chosen.step=corrupt_step;
    '''
    return base+'\n'+'\n'.join(generated)+C_MAIN.replace('/* SPECS */',spec).replace('/* ENTRIES_SELECT */',choose),receipts


@pytest.fixture(scope="module")
def branch_binary(tmp_path_factory):
    out=tmp_path_factory.mktemp("static-branch-core")
    cc=os.environ.get("CC")or shutil.which("clang")or shutil.which("cc")or shutil.which("gcc")
    if not cc:pytest.skip("C11 compiler required")
    source,receipts=_source();src=out/"branch.c";src.write_text(source,encoding="utf-8")
    (out/"emission.json").write_text(json.dumps(receipts,indent=2),encoding="utf-8")
    core=out/"snes_core.c";core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n',encoding="utf-8")
    exe=out/("branch.exe"if os.name=="nt"else"branch")
    command=[cc,"-std=c11","-O1","-DSNESRECOMP_TIER2_TEST=1","-DSNESRECOMP_REVERSE_DEBUG=0",
      "-I",str(REPO/"runner/src"),"-I",str(REPO/"runner/src/snes"),"-I",str(REPO/"tests/dma"),str(src),str(core),
      *[str(REPO/f)for f in ("runner/src/snes/interp816.c","runner/src/sha256.c","runner/src/snes/tier2_capture.c",
        "runner/src/snes/interp_bridge.c","runner/src/snes/cx4.c","runner/src/snes/dma.c","runner/src/snes/sdd1.c")],"-lm","-o",str(exe)]
    built=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (out/"compile.json").write_text(json.dumps(dict(command=command,exit_code=built.returncode,stdout=built.stdout,stderr=built.stderr),indent=2),encoding="utf-8")
    assert built.returncode==0,built.stdout+built.stderr
    return out,exe


def _execute(binary,fault):
    out,exe=binary;result=subprocess.run([str(exe),str(fault)],capture_output=True,text=True,timeout=120,cwd=out)
    (out/f"execution-{fault}.json").write_text(json.dumps(dict(exit_code=result.returncode,
      source_sha256=hashlib.sha256((out/"branch.c").read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
      stdout=result.stdout,stderr=result.stderr),indent=2),encoding="utf-8")
    return result


def test_production_static_branch_effects_share_actual_retirement(branch_binary):
    result=_execute(branch_binary,0)
    assert result.returncode==0,result.stdout+result.stderr
    assert "failures=0"in result.stdout


@pytest.mark.parametrize("fault,message",[(1,"never decoder relabelled"),(2,"CPU+master clocks exact"),
    (3,"full memory and guest stack exact"),(4,"every bus fetch"),(5,"owner SP/watermark exact")])
def test_static_branch_negative_controls_are_detected(branch_binary,fault,message):
    result=_execute(branch_binary,fault)
    assert result.returncode!=0
    assert message in result.stdout+result.stderr
