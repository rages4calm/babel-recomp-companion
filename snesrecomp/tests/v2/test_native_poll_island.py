"""ROM-free native opcode effects under the real owning interpreter protocol."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from test_region_poll_fallback import _source as fallback_source, REPO
from test_region_pacing import _c_function


NATIVE = r'''
extern unsigned long long g_interp_bridge_steps;
static unsigned admission_variant;
static int decline_poll(Interp816 *in){(void)in;return 0;}
/* Compiled effects, deliberately independent of interp816_runOpcode. */
static int compiled_poll(Interp816 *in) {
  uint32 bank=(uint32)in->k<<16;
  uint8 op=in->read(in->mem,bank|in->pc++);
  if(op==0xaf){
    uint32 a=in->read(in->mem,bank|in->pc++);
    a|=(uint32)in->read(in->mem,bank|in->pc++)<<8;
    a|=(uint32)in->read(in->mem,bank|in->pc++)<<16;
    uint8 value=in->read(in->mem,a);
    in->a=(in->a&0xff00)|value;in->z=value==0;in->n=(value&0x80)!=0;
    in->cyclesUsed=5;
  }else{
    int8_t displacement=(int8_t)in->read(in->mem,bank|in->pc++);
    in->cyclesUsed=2;
    if(!in->n){in->pc=(uint16)(in->pc+displacement);++in->cyclesUsed;}
  }
  return in->cyclesUsed;
}
static unsigned visits,hook_mode,nested_calls,redirects,mutations;
static uint32 poll_pc;
static void observer(CpuState *cpu,uint32 pc){
  ++visits;
  if(hook_mode==1&&visits==7){g_test_snes.inNmi=true;g_test_snes.rdnmiPending=true;}
  if(hook_mode==2&&visits==5){++redirects;interp_bridge_pre_opcode_redirect((pc&0xff0000)|0x805d);}
  if(hook_mode==3&&visits==4){++mutations;RAM[poll_pc+5]=0;}
  if(hook_mode==4&&visits==2){
    uint64 count=interp_bridge_native_poll_insns_total();
    g_test_snes.inNmi=true;g_test_snes.rdnmiPending=true;
    uint16 old_s=cpu->S;
    cpu_push_interrupt_frame_at(cpu,pc);
    CHECK(interp_bridge_run_interrupt(cpu,0x008300)==1,"nested real interrupt RTI");
    CHECK(cpu->S==old_s,"nested RTI owner SP");
    CHECK(interp_bridge_native_poll_insns_total()==count,"host interrupt refuses island");
    ++nested_calls;
  }
  if(hook_mode==5&&visits==4){cpu->m_flag=0;cpu_mirrors_to_p(cpu);++mutations;}
}
typedef struct IslandResult {
  CpuState cpu;
  Snes snes;
  uint32 resume;
  uint64 reads_hash,reads_count,interp_insns,interp_cycles,native_insns,native_cycles,logical;
  unsigned reads,visits,nested,redirected,mutated,overlay_probes;
  int quiescent,wai;
} IslandResult;
static IslandResult island(int native,int bank,int fast,int mx,int emulation,
                           uint64 budget,int irq,int edge,int hook,int bad_shape,int mapper,int ordinary){
  IslandResult out={0};
  memset(RAM,0,MEMSZ);init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);
  static Dma dma;memset(&dma,0,sizeof dma);
  memset(&g_test_cart,0,sizeof g_test_cart);
  g_test_cart.type=mapper;g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
  g_test_snes.cart=&g_test_cart;g_test_snes.ram=RAM;g_test_snes.dma=&dma;
  g_test_snes.hdmaBeamOff=true;
  snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(true);
  g_c.emulation=emulation;g_c.m_flag=mx>>1;g_c.x_flag=mx&1;
  g_c.A=0x1234;g_c.X=0x12;g_c.Y=0x34;g_c._flag_I=!irq;cpu_mirrors_to_p(&g_c);
  g_test_snes.hPos=0;g_test_snes.vPos=224;g_test_snes.beamMasterLast=0;
  g_test_snes.inNmi=edge;g_test_snes.rdnmiPending=edge;
  if(irq){g_test_snes.hIrqEnabled=true;g_test_snes.hTimer=20;}
  interp_bridge_reset_dynamic_cache();interp_bridge_set_interpret_all(!native);
  interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_clear_idle_polls();
  interp_bridge_clear_native_rdnmi_polls();
  poll_pc=((uint32)bank<<16)|0x804d;
  /* Register even in forced-interpreter runs: policy must override it. */
  InterpNativePollStep callback=admission_variant==1?decline_poll:compiled_poll;
  CHECK(interp_bridge_add_native_rdnmi_poll(poll_pc,callback),"register exact poll PC");
  CHECK(interp_bridge_add_native_rdnmi_poll(poll_pc,callback),"idempotent registration");
  if(admission_variant==2)interp_bridge_clear_native_rdnmi_polls();
  if(admission_variant==3)g_test_cart.rom=NULL;
  if(admission_variant==4)g_test_cart.romSize=1;
  interp_bridge_set_lle_bounce_exclusions(NULL,0);
  if(admission_variant==5)interp_bridge_set_lle_bounce_exclusions(&poll_pc,1);
  test_interrupt_scope=admission_variant==6;
  if(admission_variant==7)g_test_cart.overlayBank[(bank&0x7f)-0x20]=RAM;
  if(hook){interp_bridge_add_pre_opcode_hook(poll_pc,observer);}
  visits=nested_calls=redirects=mutations=0;hook_mode=hook;
  (void)interp_bridge_lle_took_quiescent();(void)interp_bridge_lle_took_wai();
  rdnmi_reads=root_entries=unexpected_dispatch=0;g_memsel=fast;
  g_push_count=g_interp_push_count=g_push_depth=g_pop_underflow=g_recomp_stack_top=0;g_abandon_called=0;
  const uint8_t owner[]={0x22,0x4d,0x80,(uint8)bank,0x85,0x40,0x80,0xfe};
  const uint8_t poll[]={0xaf,0x10,0x42,0x80,0x10,0xfa,0x6b};
  const uint8_t escape[]={0xa9,0x55,0x6b};
  const uint8_t handler[]={0x22,0x4d,0x80,(uint8)bank,0xe6,0x70,0x40};
  load(0x838000,owner,sizeof owner);load(poll_pc,poll,sizeof poll);
  load(((uint32)bank<<16)|0x805d,escape,sizeof escape);load(0x008300,handler,sizeof handler);
  if(bad_shape)RAM[poll_pc+bad_shape-1]^=1;
  uint64 before_i=interp816_insns_total(),before_c=interp816_cycles_total();
  uint64 before_ni=interp_bridge_native_poll_insns_total(),before_nc=interp_bridge_native_poll_cycles_total();
  uint64 before_l=g_interp_bridge_steps;
  bus_hash=1469598103934665603ULL;bus_reads=0;overlay_probes=0;
  interp_bridge_set_master_deadline(budget);
  CHECK((ordinary?interp_bridge_run(&g_c,poll_pc):interp_bridge_run_until_quiescent(&g_c,0x838000))==1,"island owning return/yield");
  out.resume=interp_bridge_lle_resume_pc();out.reads=rdnmi_reads;
  out.quiescent=interp_bridge_lle_took_quiescent();out.wai=interp_bridge_lle_took_wai();
  out.cpu=g_c;out.snes=g_test_snes;out.reads_hash=bus_hash;out.reads_count=bus_reads;
  out.interp_insns=interp816_insns_total()-before_i;out.interp_cycles=interp816_cycles_total()-before_c;
  out.native_insns=interp_bridge_native_poll_insns_total()-before_ni;out.native_cycles=interp_bridge_native_poll_cycles_total()-before_nc;
  out.logical=g_interp_bridge_steps-before_l;out.visits=visits;out.nested=nested_calls;out.redirected=redirects;out.mutated=mutations;
  out.overlay_probes=overlay_probes;
  CHECK(!g_recomp_stack_top&&!g_pop_underflow&&!unexpected_dispatch&&!g_abandon_called,"no owner stack/control leaks");
  interp_bridge_set_master_deadline(0);return out;
}
static void equal(IslandResult a,IslandResult b,int accepted){
  CHECK(!memcmp(&a.cpu,&b.cpu,sizeof a.cpu),"complete CPU/cycles/openbus exact");
  CHECK(!memcmp(&a.snes,&b.snes,sizeof a.snes),"complete core beam/IRQ/RDNMI state exact");
  CHECK(a.resume==b.resume&&a.quiescent==b.quiescent&&a.wai==b.wai,"same cooperative continuation/reason");
  CHECK(a.reads==b.reads&&a.reads_hash==b.reads_hash&&a.reads_count==b.reads_count,"every bus read/value/order exact");
  CHECK(a.logical==b.logical,"logical instruction steps exact");
  CHECK(a.interp_insns==b.interp_insns+b.native_insns,"native not counted as interpreted instructions");
  CHECK(a.interp_cycles==b.interp_cycles+b.native_cycles,"native not counted as interpreted cycles");
  CHECK(a.visits==b.visits&&a.nested==b.nested&&a.redirected==b.redirected&&a.mutated==b.mutated,"prehook order/effects exact");
  CHECK(a.overlay_probes==b.overlay_probes,"admission adds no overlay probe effects");
  CHECK(!a.native_insns&&!a.native_cycles,"force interpreter disables registered island");
  CHECK((accepted==2?a.reads>0:accepted)?b.native_insns>0:b.native_insns==0,"native admission/refusal measured");
}
static uint8 *expected_memory;
static unsigned pairs;
static IslandResult deferred(int native,int enabled){
  IslandResult out=island(native,0x82,1,2,0,10000,0,0,0,0,CART_HIROM,0);
  CHECK(out.quiescent&&g_c.S==0x1fc,"manual NMI starts from real suspended JSL");
  uint64 bi=interp816_insns_total(),bc=interp816_cycles_total();
  uint64 bn=interp_bridge_native_poll_insns_total(),bcy=interp_bridge_native_poll_cycles_total(),bl=g_interp_bridge_steps;
  g_test_snes.nmiEnabled=enabled;g_test_snes.inNmi=true;g_test_snes.rdnmiPending=true;
  if(enabled){
    const uint8_t handler[]={0xe6,0x70,0x40};load(0x008300,handler,sizeof handler);
    uint16 before=g_c.S;cpu_push_interrupt_frame_at(&g_c,out.resume);
    CHECK(g_c.S==(uint16)(before-4),"deferred real architectural frame");
    CHECK(interp_bridge_run_interrupt(&g_c,0x008300)==1,"deferred real handler RTI");
    CHECK(g_c.S==before,"deferred RTI resumes suspended owner");
  }
  for(unsigned t=0;t<4&&RAM[0x40]!=0x82;t++){
    interp_bridge_set_master_deadline(g_c.master_cycles+10000);
    CHECK(interp_bridge_run_until_quiescent(&g_c,out.resume)==1,"manual edge resumes owning poll");
    out.resume=interp_bridge_lle_resume_pc();
  }
  CHECK(RAM[0x40]==0x82&&g_c.S==0x1ff,"real latch exits poll and RTL returns to owner");
  CHECK(RAM[0x70]==enabled,"NMITIMEN gates actual handler");
  CHECK(!g_test_snes.inNmi&&!g_test_snes.rdnmiPending,"both real RDNMI latches consumed");
  CHECK(snes_readReg(&g_test_snes,0x4210)==2,"no duplicate manual NMI edge");
  out.cpu=g_c;out.snes=g_test_snes;out.reads=rdnmi_reads;
  out.reads_hash=bus_hash;out.reads_count=bus_reads;
  out.interp_insns+=interp816_insns_total()-bi;out.interp_cycles+=interp816_cycles_total()-bc;
  out.native_insns+=interp_bridge_native_poll_insns_total()-bn;out.native_cycles+=interp_bridge_native_poll_cycles_total()-bcy;
  out.logical+=g_interp_bridge_steps-bl;out.quiescent=interp_bridge_lle_took_quiescent();out.wai=interp_bridge_lle_took_wai();
  CHECK(!g_recomp_stack_top&&!g_pop_underflow,"deferred owner stack balanced");
  interp_bridge_set_master_deadline(0);return out;
}
static void pair(int bank,int fast,int mx,int emulation,uint64 budget,int irq,int edge,int hook,int bad,int mapper,int ordinary,int accepted){
  IslandResult a=island(0,bank,fast,mx,emulation,budget,irq,edge,hook,bad,mapper,ordinary);
  memcpy(expected_memory,RAM,MEMSZ);
  IslandResult b=island(1,bank,fast,mx,emulation,budget,irq,edge,hook,bad,mapper,ordinary);
  CHECK(!memcmp(expected_memory,RAM,MEMSZ),"complete synthetic memory/guest stack exact");
  equal(a,b,accepted);++pairs;
}
int main(void){
  RAM=malloc(MEMSZ);expected_memory=malloc(MEMSZ);if(!RAM||!expected_memory)return 2;
  int banks[]={0x02,0x42,0x82,0xc2};
  for(unsigned b=0;b<4;b++)for(int fast=0;fast<2;fast++)for(int x=0;x<2;x++){
    pair(banks[b],fast,2+x,0,10000,0,0,0,0,CART_HIROM,0,1);
    pair(banks[b],fast,2+x,0,10000,1,0,0,0,CART_HIROM,0,1);
    pair(banks[b],fast,2+x,0,10000,0,1,0,0,CART_HIROM,0,1);
    for(uint64 deadline=1;deadline<=160;deadline++)
      pair(banks[b],fast,2+x,0,deadline,0,0,0,0,CART_HIROM,0,2);
  }
  for(int hook=1;hook<=5;hook++)pair(0x82,1,2,0,10000,0,0,hook,0,CART_HIROM,0,1);
  for(admission_variant=1;admission_variant<=6;admission_variant++)
    pair(0x82,1,2,0,10000,0,1,0,0,CART_HIROM,0,0);
  admission_variant=7;pair(0x22,1,2,0,10000,0,1,0,0,CART_HIROM,0,0);
  admission_variant=0;
  interp_bridge_set_lle_bounce_exclusions(NULL,0);
  for(int enabled=0;enabled<2;enabled++){
    IslandResult a=deferred(0,enabled);memcpy(expected_memory,RAM,MEMSZ);
    IslandResult b=deferred(1,enabled);
    CHECK(!memcmp(expected_memory,RAM,MEMSZ),"deferred complete memory/guest stack");
    equal(a,b,1);++pairs;
  }
  for(int bad=1;bad<=6;bad++)pair(0x82,1,2,0,10000,0,0,0,bad,CART_HIROM,0,0);
  for(int mx=0;mx<2;mx++)pair(0x82,1,mx,0,10000,0,1,0,0,CART_HIROM,0,0);
  pair(0x82,1,3,1,10000,0,1,0,0,CART_HIROM,0,0);
  pair(0x82,1,2,0,10000,0,1,0,0,CART_LOROM,0,0);
  /* No scheduler owner: execute a balanced ordinary call only, no spin. */
  pair(0x82,1,2,0,0,0,1,0,0,CART_HIROM,1,0);
  CHECK(!interp_bridge_add_native_rdnmi_poll(0x828100,NULL),"null callback refused");
  CHECK(!interp_bridge_add_native_rdnmi_poll(0x827fff,compiled_poll),"low-code address refused");
  CHECK(!interp_bridge_add_native_rdnmi_poll(0x82fffb,compiled_poll),"PBR wrap refused");
  CHECK(!interp_bridge_add_native_rdnmi_poll(0x7e8100,compiled_poll),"WRAM refused");
  CHECK(!interp_bridge_add_native_rdnmi_poll(0x1828100,compiled_poll),"highbits refused");
  InterpExecutionShare report;g_cpu=g_c;InterpExecutionShareGet(&report);
  CHECK(report.native_poll_insns==interp_bridge_native_poll_insns_total(),"report native instruction counter");
  CHECK(report.native_poll_cycles==interp_bridge_native_poll_cycles_total(),"report native cycle counter");
  FILE *report_file=tmpfile();CHECK(report_file!=NULL,"report tempfile");
  if(report_file){char text[2048]={0};InterpExecutionShareDumpJson(report_file);rewind(report_file);
    CHECK(fread(text,1,sizeof text-1,report_file)>0,"read report JSON");printf("SHARE %s",text);fclose(report_file);}
  printf("pairs=%u checks=%d failures=%d native_total=%llu cycles=%llu\n",pairs,g_check,fixture_fail,
    (unsigned long long)interp_bridge_native_poll_insns_total(),(unsigned long long)interp_bridge_native_poll_cycles_total());
  free(expected_memory);free(RAM);return fixture_fail?1:0;
}
'''


def _source(relabel=False):
    source = fallback_source()
    # Keep the production core/peripheral harness and old negative-control
    # bodies intact, replacing only its main and flat-bus instrumentation.
    main = source.index("    int main(void){")
    source = source[:main]
    source = source.replace("\n    uint8 cpu_read8(", "\nuint8 cpu_read8(")
    source = source.replace(_c_function(source, "cpu_dispatch_has_entry"),
        "int cpu_dispatch_has_entry(CpuState *cpu,uint32 pc){(void)cpu;(void)pc;return 0;}\n")
    source = source.replace(_c_function(source, "cpu_interrupt_context_active"),
        "int cpu_interrupt_context_active(void){return test_interrupt_scope;}\n")
    old_mapping = _c_function(source, "cart_getRomPtr")
    source = source.replace(old_mapping, old_mapping.replace("(void)cart;",
        "if((bank&0x7f)>=0x20&&(bank&0x7f)<0x30&&cart->overlayBank[(bank&0x7f)-0x20])++overlay_probes;"))
    source = source.replace(_c_function(source, "cpu_read8"), r'''
    uint8 cpu_read8(CpuState *cpu,uint8 bank,uint16 addr){
      uint32 pc=((uint32)bank<<16)|addr;uint8 value;
      if((bank&0x7f)<0x40&&addr==0x4210){++rdnmi_reads;value=snes_readReg(g_snes,addr);}
      else value=RAM[pc&0xffffff];
      bus_hash^=((uint64)pc<<8)|value;bus_hash*=1099511628211ULL;++bus_reads;
      return cpu->open_bus=value;
    }
    ''')
    native = NATIVE.replace(_c_function(NATIVE, "compiled_poll"),
        _c_function((REPO.parent / "src/iog_native_poll.c").read_text(encoding="utf-8"),
                    "IogNativePollStep").replace("IogNativePollStep", "compiled_poll"))
    if relabel:
        native = native.replace(_c_function(native, "compiled_poll"),
            "int compiled_poll(Interp816 *in){return interp816_runOpcode(in);}\n")
    return '#include "snes/interp816.h"\nstatic uint64_t bus_hash,bus_reads;\nstatic int test_interrupt_scope;static unsigned overlay_probes;\n' + source + native


def _compile_run(tmp_path, *, relabel=False):
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("C11 compiler required")
    source = tmp_path / "island.c"
    source.write_text(_source(relabel), encoding="utf-8")
    core = tmp_path / "snes_core.c"
    core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n', encoding="utf-8")
    exe = tmp_path / ("island.exe" if os.name == "nt" else "island")
    command = [cc,"-std=c11","-O1","-DSNESRECOMP_TIER2_TEST=1","-DSNESRECOMP_REVERSE_DEBUG=0",
        "-I",str(REPO/"runner/src"),"-I",str(REPO/"runner/src/snes"),"-I",str(REPO/"tests/dma"),
        str(source),str(core),*[str(REPO/f) for f in ("runner/src/snes/interp816.c","runner/src/sha256.c",
        "runner/src/snes/tier2_capture.c","runner/src/snes/interp_bridge.c","runner/src/snes/cx4.c",
        "runner/src/snes/dma.c","runner/src/snes/sdd1.c")],"-lm","-o",str(exe)]
    result = subprocess.run(command,capture_output=True,text=True,timeout=60)
    (tmp_path/"compile.json").write_text(json.dumps(dict(command=command,exit_code=result.returncode,
        stdout=result.stdout,stderr=result.stderr),indent=2),encoding="utf-8")
    assert result.returncode==0,result.stdout+result.stderr
    result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
    (tmp_path/"execution.json").write_text(json.dumps(dict(exit_code=result.returncode,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        stdout=result.stdout,stderr=result.stderr),indent=2),encoding="utf-8")
    return result


def test_native_poll_effects_share_real_interpreter_retirement(tmp_path):
    result = _compile_run(tmp_path)
    assert result.returncode==0,result.stdout+result.stderr
    assert "failures=0" in result.stdout
    share_line = next(line.removeprefix("SHARE ").strip().removesuffix(",")
                      for line in result.stdout.splitlines() if line.startswith("SHARE "))
    share = json.loads("{" + share_line + "}")["execution_share"]
    assert share["native_poll_insns"] > 0 and share["native_poll_cycles"] > 0


def test_counter_partition_rejects_interpreter_relabelled_as_native(tmp_path):
    result = _compile_run(tmp_path, relabel=True)
    assert result.returncode != 0
    assert "native not counted as interpreted instructions" in result.stdout + result.stderr
    assert "native not counted as interpreted cycles" in result.stdout + result.stderr
