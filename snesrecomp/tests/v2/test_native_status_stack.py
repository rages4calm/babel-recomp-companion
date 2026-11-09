"""Production status/data-stack effects under the actual owning bridge loop."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest
import snes65816 as decoder
from v2.native_effects import emit
from test_native_continuation import _source as continuation_source
from test_region_poll_fallback import REPO
from test_region_pacing import _c_function

BANKS = (0x02, 0x42, 0x82, 0xC2, 0x22)


def _program(flow):
    ordinary = [b'\x08', b'\xc2\x30', b'\x48', b'\xda', b'\x5a', b'\x8b', b'\x0b',
        b'\xe2\x30', b'\xa9\x5a', b'\xa2\xb6', b'\xa0\xc7', b'\x8f\x00\x02\x7e',
        b'\xc2\x30', b'\x2b', b'\xab', b'\x7a', b'\xfa', b'\x68', b'\x28', b'\x8f\x04\x02\x7e', b'\x6b']
    pointers = [b'\x08', b'\xc2\x30', b'\x0b', b'\xa9\x00\x1f', b'\x5b', b'\x4b', b'\xab',
        b'\x8b', b'\xab', b'\xf4\xae\xc2', b'\x68', b'\x8f\x00\x02\x7e',
        b'\x62\xff\x7f', b'\x68', b'\x8f\x02\x02\x7e', b'\xd4\xff', b'\x68',
        b'\x8f\x04\x02\x7e', b'\x2b', b'\x28', b'\x6b']
    result = bytearray()
    entries = []
    modes = [(0, 0), (0, 1), (1, 0), (1, 1)]
    for code in pointers if flow else ordinary:
        opcode = code[0]
        if opcode != 0x6B:  # The original interpreter still consumes every RTL.
            for m, x in modes:
                entries.append((len(result), code, m, x))
        result.extend(code)
        if opcode == 0xC2:
            modes = [(0, 0)]
        elif opcode == 0xE2:
            modes = [(1, 1)]
        elif opcode == 0x28:
            modes = [(0, 0), (0, 1), (1, 0), (1, 1)]
    return bytes(result), entries


SETUP = r'''
static void setup(int native,int bank,int fast,int m,int x,int flow,int irq,int hk){
  memset(RAM,0,MEMSZ);init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);memset(&g_test_cart,0,sizeof g_test_cart);
  static Dma dma;memset(&dma,0,sizeof dma);g_test_snes.dma=&dma;g_test_snes.hdmaBeamOff=true;
  g_test_snes.cart=&g_test_cart;g_test_snes.ram=RAM;g_test_cart.type=CART_HIROM;g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
  snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(true);
  g_test_snes.hPos=0;g_test_snes.vPos=224;g_test_snes.beamMasterLast=0;
  if(irq){g_test_snes.hIrqEnabled=true;g_test_snes.hTimer=20;}
  g_c.emulation=0;g_c.m_flag=m;g_c.x_flag=x;g_c.A=0xabcd;g_c.X=x?0x34:0x1234;g_c.Y=x?0x78:0x5678;
  g_c.DB=0x7e;g_c.D=0x117;g_c.S=ss_sp;g_c._flag_I=!irq;g_c._flag_C=1;g_c._flag_D=1;cpu_mirrors_to_p(&g_c);g_memsel=fast;
  g_push_count=g_interp_push_count=g_push_depth=g_pop_underflow=g_recomp_stack_top=0;g_abandon_called=0;
  unexpected_dispatch=rdnmi_reads=0;visits=nested=handler_entries=0;hook_kind=hk;
  interp_bridge_set_interpret_all(!native);interp_bridge_reset_dynamic_cache();interp_bridge_clear_native_rdnmi_polls();
  interp_bridge_clear_idle_polls();interp_bridge_clear_native_instructions();interp_bridge_set_pre_opcode_hook(0,NULL);
  interp_bridge_set_lle_bounce_exclusions(NULL,0);g_interp_bridge_pc_hook=NULL;interrupt_scope=variant==1;
  (void)interp_bridge_lle_took_quiescent();(void)interp_bridge_lle_took_wai();
  code_base=((uint32)bank<<16)|(flow?0x9100:0x8100);
  load(code_base,ss_programs[flow],ss_lengths[flow]);RAM[0x1fff]=0x34;RAM[0x2000]=0x12;
  uint8 owner[]={0x22,(uint8)code_base,(uint8)(code_base>>8),(uint8)bank,0x85,0x40,0x80,0xfe};
  const uint8 handler[]={0x20,0x10,0x83,0x40},sub[]={0x0b,0xf4,0,0,0x2b,0xe6,0x70,0x08,0xc2,0x30,0xe2,0x30,0x28,0x2b,0x60};
  load(0x838000,owner,sizeof owner);load(0x008300,handler,sizeof handler);load(0x008310,sub,sizeof sub);
  InterpNativeInstruction items[512];size_t total=sizeof ni_entries/sizeof *ni_entries;CHECK(total<=512,"bounded generated registry");
  memcpy(items,ni_entries,sizeof ni_entries);
  if(ss_fault){
    uint32 target=code_base+(ss_fault==6?3:1);int em=ss_fault==6?0:m,ex=ss_fault==6?0:x;int found=0;
    for(size_t i=0;i<total;i++)if(items[i].pc24==target&&items[i].m==em&&items[i].x==ex){ss_actual=items[i].step;items[i].step=ss_corrupt;found=1;break;}
    CHECK(found,"exact production effect selected for mutation");
  }
  CHECK(interp_bridge_add_native_instructions(items,total),"production status/data-stack descriptors admitted");
  if(variant==2)g_test_cart.type=CART_SA1;if(variant==3)g_test_cart.rom=NULL;
  if(variant==4){InterpNativeInstruction chosen={0};for(size_t i=0;i<total;i++)if(items[i].pc24==code_base&&items[i].m==m&&items[i].x==x)chosen=items[i];
    interp_bridge_clear_native_instructions();CHECK(interp_bridge_add_native_instructions(&chosen,1),"single policy-excluded production opcode");
    interp_bridge_set_lle_bounce_exclusions(&code_base,1);}
  if(variant==5)g_test_cart.overlayBank[(bank&0x7f)-0x20]=RAM;
  if(hk&&hk!=4)interp_bridge_add_pre_opcode_hook(code_base+1,ss_hook);
  if(hk==4)g_interp_bridge_pc_hook=ss_observe;
  bus_hash=1469598103934665603ULL;bus_reads=bus_writes=0;last_data_ipc=overlay_probes=0;
}
'''

SUPPORT = r'''
static unsigned ss_fault;static uint16 ss_sp=0x1ff;static InterpNativeInstructionStep ss_actual;
static int ss_corrupt(Interp816 *in){
  if(ss_fault==1)return interp816_runOpcode(in); /* accounting must reject relabelling */
  if(ss_fault==5)(void)in->read(in->mem,((uint32)in->k<<16)|in->pc);
  if(ss_fault==6)g_interp816_cur_pc^=1;
  int cycles=ss_actual(in);
  if(ss_fault==2)++cycles;if(ss_fault==3)in->mf=!in->mf;if(ss_fault==4)++in->sp;
  return cycles;
}
static void ss_hook(CpuState *cpu,uint32 pc){
  ++visits;
  if(hook_kind==1)RAM[pc+1]^=1; /* change carry mask, not program widths */
  if(hook_kind==2){cpu->m_flag=!cpu->m_flag;cpu->x_flag=!cpu->x_flag;cpu_mirrors_to_p(cpu);}
  if(hook_kind==3){uint16 sp=cpu->S;uint64 native=interp_bridge_native_continuation_insns_total();
    cpu_push_interrupt_frame_at(cpu,pc);CHECK(interp_bridge_run_interrupt(cpu,0x008300)==1,"real nested status/stack handler RTI");
    CHECK(cpu->S==sp,"nested interrupt restores live data-stack depth");
    CHECK(interp_bridge_native_continuation_insns_total()==native,"status/stack handler retains interpreter ownership");++nested;}
}
static void ss_observe(uint32 pc,int m,int x){(void)m;(void)x;if(pc==code_base+1){++visits;RAM[pc+1]^=1;}}
'''

MAIN = r'''
int main(int argc,char **argv){
  ss_fault=argc>1?(unsigned)atoi(argv[1]):0;RAM=malloc(MEMSZ);expected_memory=malloc(MEMSZ);if(!RAM||!expected_memory)return 2;
  int banks[]={0x02,0x42,0x82,0xc2};uint16 stacks[]={0x1ff,0xbff,0,0xffff};
  if(ss_fault)pair(0x82,1,1,0,0,160,0,0,0,-1);
  else{
    for(int flow=0;flow<2;flow++)for(unsigned b=0;b<4;b++)for(int fast=0;fast<2;fast++)for(int m=0;m<2;m++)for(int x=0;x<2;x++)for(unsigned s=0;s<4;s++){
      ss_sp=stacks[s];pair(banks[b],fast,m,x,flow,10000,0,0,0,1);
    }
    ss_sp=0x1ff;
    for(int flow=0;flow<2;flow++)for(int fast=0;fast<2;fast++)for(uint64 deadline=1;deadline<=240;deadline++)pair(0x82,fast,1,0,flow,deadline,0,0,0,-1);
    for(int flow=0;flow<2;flow++)for(int m=0;m<2;m++)for(int x=0;x<2;x++){
      pair(0x82,1,m,x,flow,10000,1,0,0,-1);
      for(unsigned h=1;h<=4;h++)pair(0x82,1,m,x,flow,10000,0,h,0,1);
      for(uint64 deadline=30;deadline<=180;deadline+=50)pair(0x82,1,m,x,flow,deadline,0,0,1,1);
    }
    for(variant=1;variant<=4;variant++)pair(0x82,1,1,0,0,10000,0,0,0,0);
    variant=5;pair(0x22,1,1,0,0,10000,0,0,0,0);variant=0;
  }
  printf("status_stack_pairs=%u checks=%d failures=%d\n",pairs,g_check,fixture_fail);
  free(RAM);free(expected_memory);return fixture_fail?1:0;
}
'''


def _source():
    base = continuation_source()
    base = base[:base.index('int main(void){')]
    # Attribute every stack/data write as well as its address/value/order.
    original = 'bus_hash^=((uint64)pc<<8)|value|((uint64)1<<40);'
    assert original in base
    base = base.replace(original, original + 'bus_hash^=(uint64)g_interp816_cur_pc<<17;')
    entries, programs = [], []
    for flow in range(2):
        raw, records = _program(flow)
        programs.append(raw)
        for bank in BANKS:
            start = (bank << 16) | (0x9100 if flow else 0x8100)
            for offset, code, m, x in records:
                name, mode, _ = decoder.opcode_table()[code[0]]
                entries.append(dict(pc24=start+offset,m=m,x=x,e=0,bytes=code,mnemonic=name,immediate=mode==decoder.IMM))
    for pc, code in [(0x008317,b'\x08'),(0x008318,b'\xc2\x30'),(0x00831A,b'\xe2\x30'),(0x00831C,b'\x28')]:
        name, mode, _ = decoder.opcode_table()[code[0]]
        for m in range(2):
            for x in range(2):
                entries.append(dict(pc24=pc,m=m,x=x,e=0,bytes=code,mnemonic=name,immediate=mode==decoder.IMM))
    generated, receipt = emit((REPO/'runner/src/snes/interp816.c').read_text(encoding='utf-8'),entries,registration_name='RegisterStatusStack')
    assert not re.search(r'\b(?:interp816_|ni_\d\d_)(?:runOpcode|doOpcode)\s*\(',generated)
    declarations = ''.join(f'static const uint8 ss_program{i}[]={{'+','.join(str(v) for v in raw)+'};\n' for i,raw in enumerate(programs))
    declarations += 'static const uint8 *ss_programs[]={ss_program0,ss_program1};\n'
    declarations += 'static const unsigned ss_lengths[]={sizeof ss_program0,sizeof ss_program1};\n'
    start = base.index('static void setup(')
    base = base[:start] + generated + '\n' + declarations + SUPPORT + '\n' + base[start:]
    base = base.replace(_c_function(base,'setup'), SETUP)
    # The interrupted instruction may have pushed data, so capture its actual
    # live S below; the real RTI must restore that value, not a fixed entry S.
    base = base.replace('CHECK(g_c.S==0x1fc,"deadline inherits suspended real JSL frame");','')
    base = base.replace('g_c.S!=0x1ff','g_c.S!=ss_sp').replace('g_c.S==0x1ff&&RAM[0x70]==1','g_c.S==ss_sp&&RAM[0x70]==1')
    base = base.replace('stats[32]', 'stats[512]').replace('stats(stats,32)', 'stats(stats,512)').replace('n<=32','n<=512').replace('i<32','i<512')
    # Native status/stack operations inside a real RTI handler remain refused.
    needle='CHECK(si==out.ni&&sc==out.nc,"per-instruction attribution equals accepted totals");'
    base=base.replace(needle,needle+'for(size_t i=0;i<n&&i<512;i++)if((stats[i].pc24>>16)==0)CHECK(!stats[i].insns,"interrupt handler native status/stack guard retained");')
    return base + MAIN, receipt


@pytest.fixture(scope='module')
def status_stack_binary(tmp_path_factory):
    out=tmp_path_factory.mktemp('status-stack-core')
    cc=os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
    if not cc:
        pytest.skip('C11 compiler required')
    source,receipt=_source();src=out/'status_stack.c';src.write_text(source,encoding='utf-8')
    (out/'emission.json').write_text(json.dumps(receipt,indent=2))
    core=out/'snes_core.c';core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n')
    exe=out/('status_stack.exe' if os.name=='nt' else 'status_stack')
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0',
        '-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(src),str(core),
        *[str(REPO/f) for f in ('runner/src/snes/interp816.c','runner/src/sha256.c','runner/src/snes/tier2_capture.c',
          'runner/src/snes/interp_bridge.c','runner/src/snes/cx4.c','runner/src/snes/dma.c','runner/src/snes/sdd1.c')],'-lm','-o',str(exe)]
    built=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (out/'compile.json').write_text(json.dumps(dict(command=command,exit_code=built.returncode,stdout=built.stdout,stderr=built.stderr),indent=2))
    assert built.returncode==0,built.stdout+built.stderr
    return out,exe


def _execute(binary, fault, lookup='1'):
    out,exe=binary
    env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup)
    result=subprocess.run([str(exe),str(fault)],capture_output=True,text=True,timeout=120,cwd=out,env=env)
    (out/f'execution-{fault}-index{lookup}.json').write_text(json.dumps(dict(exit_code=result.returncode,lookup=lookup,
        source_sha256=hashlib.sha256((out/'status_stack.c').read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        stdout=result.stdout,stderr=result.stderr),indent=2))
    return result


@pytest.mark.parametrize('lookup',['0','1'])
def test_production_status_stack_uses_actual_retirement(status_stack_binary,lookup):
    result=_execute(status_stack_binary,0,lookup)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'failures=0' in result.stdout


@pytest.mark.parametrize('fault,message',[(1,'never interpreted/relabelled'),(2,'CPU+master clocks exact'),
    (3,'complete memory and inherited guest stack exact'),(4,'inherited guest frame/watermark exact'),
    (5,'every actual bus read/write/value/order exact'),(6,'every actual bus read/write/value/order exact')])
def test_status_stack_negative_controls(status_stack_binary,fault,message):
    result=_execute(status_stack_binary,fault)
    assert result.returncode!=0
    assert message in result.stdout+result.stderr
