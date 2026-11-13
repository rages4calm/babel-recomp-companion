"""Executed, ROM-free single-instruction continuations under real retirement."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from snes65816 import opcode_table
from test_region_poll_fallback import _source as fallback_source, REPO
from test_region_pacing import _c_function

PROGRAM = r'''
extern unsigned long long g_interp_bridge_steps;
static uint32 code_base;
static unsigned variant,visits,hook_kind,nested,handler_entries;
static uint8 fetch(Interp816 *in){return in->read(in->mem,((uint32)in->k<<16)|in->pc++);}
static void zn(Interp816 *in,uint16 value,int byte){in->z=(value&(byte?255:65535))==0;in->n=(value&(byte?128:32768))!=0;}
/* Fixed compiled effects for separately registered instruction sites. No
 * opcode decoder/switch or runOpcode call occurs on accepted paths. */
static int native_ldx(Interp816 *in){
  (void)fetch(in);uint16 value=fetch(in);if(!in->xf)value|=(uint16)fetch(in)<<8;
  in->x=value;zn(in,value,in->xf);return in->cyclesUsed=2+!in->xf;
}
static int native_lda(Interp816 *in){
  (void)fetch(in);uint16 value=fetch(in);if(!in->mf)value|=(uint16)fetch(in)<<8;
  in->a=in->mf?((in->a&0xff00)|value):value;zn(in,value,in->mf);return in->cyclesUsed=2+!in->mf;
}
static int native_sta(Interp816 *in){
  (void)fetch(in);(void)fetch(in);(void)fetch(in);(void)fetch(in);
  in->write(in->mem,0x7e0200,(uint8)in->a);
  if(!in->mf)in->write(in->mem,0x7e0201,(uint8)(in->a>>8));
  return in->cyclesUsed=5+!in->mf;
}
static int native_inc(Interp816 *in){
  (void)fetch(in);uint16 value=(in->a+1)&(in->mf?255:65535);
  in->a=in->mf?((in->a&0xff00)|value):value;zn(in,value,in->mf);return in->cyclesUsed=2;
}
static int native_dex(Interp816 *in){
  (void)fetch(in);in->x=(in->x-1)&(in->xf?255:65535);zn(in,in->x,in->xf);return in->cyclesUsed=2;
}
static int native_bne(Interp816 *in){
  (void)fetch(in);int8_t delta=(int8_t)fetch(in);in->cyclesUsed=2;
  if(!in->z){in->pc=(uint16)(in->pc+delta);++in->cyclesUsed;}return in->cyclesUsed;
}
static int native_rep(Interp816 *in){(void)fetch(in);uint8 mask=fetch(in);interp816_setFlags(in,interp816_getFlags(in)&~mask);return in->cyclesUsed=3;}
static int native_sep(Interp816 *in){(void)fetch(in);uint8 mask=fetch(in);interp816_setFlags(in,interp816_getFlags(in)|mask);return in->cyclesUsed=3;}
static int forbidden_handler(Interp816 *in){(void)in;++handler_entries;return 0;}
static int pure_decline(Interp816 *in){(void)in;return 0;}
static int native_capacity_nop(Interp816 *in){(void)fetch(in);return in->cyclesUsed=2;}
static InterpNativeInstruction descriptor(uint32 pc,int m,int x,int length,InterpNativeInstructionStep step){
  InterpNativeInstruction out={0};out.pc24=pc;out.m=m;out.x=x;out.length=length;out.step=step;
  memcpy(out.bytes,RAM+pc,length);return out;
}
static void hook(CpuState *cpu,uint32 pc){
  ++visits;
  if(hook_kind==1&&visits==2)RAM[pc+1]^=1;
  if(hook_kind==2&&visits==2){cpu->m_flag=!cpu->m_flag;cpu_mirrors_to_p(cpu);}
  if(hook_kind==3&&visits==2)interp_bridge_pre_opcode_redirect((pc&0xff0000)|0x8110);
  if(hook_kind==4&&visits==2){
    uint64 ni=interp_bridge_native_continuation_insns_total();uint16 sp=cpu->S;
    cpu_push_interrupt_frame_at(cpu,pc);
    CHECK(interp_bridge_run_interrupt(cpu,0x008300)==1,"nested actual RTI");
    CHECK(cpu->S==sp,"nested frame restores original SP");
    CHECK(interp_bridge_native_continuation_insns_total()==ni,"interrupt handler stays interpreted");
    ++nested;
  }
  if(hook_kind==5){
    size_t count=interp_bridge_native_instruction_stats(NULL,0);
    CHECK(!interp_bridge_add_native_instructions(NULL,0),"active registration refused");
    interp_bridge_clear_native_instructions();
    CHECK(interp_bridge_native_instruction_stats(NULL,0)==count,"active clear preserves registry");
  }
  if(hook_kind==6&&visits==2)cpu->PB=3;
}
typedef struct Outcome {
  CpuState cpu;Snes snes;uint32 resume,ipc;uint64 bus,reads,writes,logical,ii,ic,ni,nc;
  unsigned visits,nested,handler_entries,overlay_probes;int quiescent,wai;
} Outcome;
static void setup(int native,int bank,int fast,int m,int x,int count,int irq,int hk){
  memset(RAM,0,MEMSZ);init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);memset(&g_test_cart,0,sizeof g_test_cart);
  static Dma dma;memset(&dma,0,sizeof dma);g_test_snes.dma=&dma;g_test_snes.hdmaBeamOff=true;
  g_test_snes.cart=&g_test_cart;g_test_snes.ram=RAM;g_test_cart.type=CART_HIROM;
  g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
  snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(true);
  g_test_snes.hPos=0;g_test_snes.vPos=224;g_test_snes.beamMasterLast=0;
  if(irq){g_test_snes.hIrqEnabled=true;g_test_snes.hTimer=20;}
  g_c.emulation=0;g_c.m_flag=m;g_c.x_flag=x;g_c.A=0x1234;g_c.X=0x1234;g_c.Y=0x5678;g_c.DB=0x7e;
  g_c._flag_I=!irq;cpu_mirrors_to_p(&g_c);g_memsel=fast;
  g_push_count=g_interp_push_count=g_push_depth=g_pop_underflow=g_recomp_stack_top=0;g_abandon_called=0;
  unexpected_dispatch=rdnmi_reads=0;visits=nested=handler_entries=0;hook_kind=hk;
  interp_bridge_set_interpret_all(!native);interp_bridge_reset_dynamic_cache();
  interp_bridge_clear_native_rdnmi_polls();interp_bridge_clear_idle_polls();interp_bridge_clear_native_instructions();
  interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_set_lle_bounce_exclusions(NULL,0);
  (void)interp_bridge_lle_took_quiescent();(void)interp_bridge_lle_took_wai();
  code_base=((uint32)bank<<16)|0x8100;
  uint8 program[]={0xa2,(uint8)count,(uint8)(count>>8),0xea,0xa9,0x12,0x34,0xea,0x8f,0x00,0x02,0x7e,0x1a,0xca,0xd0,0xf8,0x6b};
  if(x)program[2]=0xea;if(m)program[6]=0xea;
  const uint8 owner[]={0x22,0x00,0x81,(uint8)bank,0x85,0x40,0x80,0xfe};
  const uint8 handler[]={0xe6,0x70,0x40};
  load(code_base,program,sizeof program);load(0x838000,owner,sizeof owner);load(0x008300,handler,sizeof handler);
  InterpNativeInstruction descriptors[]={descriptor(code_base,m,x,2+!x,native_ldx),descriptor(code_base+4,m,x,2+!m,native_lda),
    descriptor(code_base+8,m,x,4,native_sta),descriptor(code_base+12,m,x,1,native_inc),
    descriptor(code_base+13,m,x,1,native_dex),descriptor(code_base+14,m,x,2,native_bne),descriptor(0x008300,m,x,2,forbidden_handler)};
  if(variant==1)descriptors[2].step=pure_decline;
  if(variant==2)for(unsigned i=0;i<7;i++)descriptors[i].m=!m;
  /* Keep wrong-mode metadata internally valid; the load width then differs
   * too, so use an otherwise valid STA-only wrong-mode descriptor. */
  if(variant==2){descriptors[0]=descriptor(code_base+8,!m,x,4,native_sta);CHECK(interp_bridge_add_native_instructions(descriptors,1),"register wrong live mode");}
  else CHECK(interp_bridge_add_native_instructions(descriptors,7),"register exact instruction boundaries");
  if(variant==3)RAM[code_base+9]^=1;
  if(variant==4)interp_bridge_clear_native_instructions();
  if(variant==5)g_test_cart.type=CART_SA1;
  if(variant==6)g_test_cart.rom=NULL;
  if(variant==7){uint32 excluded=code_base+8;interp_bridge_set_lle_bounce_exclusions(&excluded,1);}
  if(variant==8){interp_bridge_clear_native_instructions();for(unsigned i=0;i<7;i++)descriptors[i].pc24^=0x400000;
    CHECK(interp_bridge_add_native_instructions(descriptors,7),"register different exact PB only");}
  if(variant==9){g_c.emulation=1;cpu_mirrors_to_p(&g_c);}
  interrupt_scope=variant==10;
  if(variant==11)g_test_snes.cart=NULL;
  if(variant==12)g_test_cart.romSize=1;
  if(variant==13)g_test_cart.overlayBank[(bank&0x7f)-0x20]=RAM;
  if(variant==14||variant==15){
    uint8 transition[]={0xc2,0x20,0xa9,0x12,0x34,0xe2,0x20,0x8f,0x00,0x02,0x7e,0x6b};
    if(variant==15){transition[1]=transition[6]=0x10;transition[2]=0xa2;}
    load(code_base,transition,sizeof transition);interp_bridge_clear_native_instructions();
    InterpNativeInstruction modes[]={descriptor(code_base,m,x,2,native_rep),
      descriptor(code_base+2,variant==14?0:m,variant==15?0:x,3,variant==14?native_lda:native_ldx),
      descriptor(code_base+5,variant==14?0:m,variant==15?0:x,2,native_sep),descriptor(code_base+7,m,x,4,native_sta)};
    CHECK(interp_bridge_add_native_instructions(modes,4),"register native mode transition chain");
  }
  if(hk)interp_bridge_add_pre_opcode_hook(code_base+8,hook);
  bus_hash=1469598103934665603ULL;bus_reads=bus_writes=0;last_data_ipc=overlay_probes=0;
}
static Outcome run(int native,int bank,int fast,int m,int x,int count,uint64 budget,int irq,int hk,int interrupt){
  Outcome out={0};setup(native,bank,fast,m,x,count,irq,hk);
  uint64 ii=interp816_insns_total(),ic=interp816_cycles_total(),ni=interp_bridge_native_continuation_insns_total(),nc=interp_bridge_native_continuation_cycles_total(),logical=g_interp_bridge_steps;
  interp_bridge_set_master_deadline(budget);
  CHECK(interp_bridge_run_until_quiescent(&g_c,0x838000)==1,"owning continuation yields");
  out.resume=interp_bridge_lle_resume_pc();
  if(interrupt){
    CHECK(g_c.S==0x1fc,"deadline inherits suspended real JSL frame");
    uint16 before=g_c.S;cpu_push_interrupt_frame_at(&g_c,out.resume);
    CHECK(interp_bridge_run_interrupt(&g_c,0x008300)==1,"actual deferred NMI/IRQ handler RTI");
    CHECK(g_c.S==before,"RTI restores continuation guest frame");
    g_test_snes.inIrq=false;
    for(unsigned n=0;n<4&&g_c.S!=0x1ff;n++){
      interp_bridge_set_master_deadline(g_c.master_cycles+10000);
      CHECK(interp_bridge_run_until_quiescent(&g_c,out.resume)==1,"resume exact inherited continuation");
      out.resume=interp_bridge_lle_resume_pc();
    }
    CHECK(g_c.S==0x1ff&&RAM[0x70]==1,"RTL interpreted after island and owner continues");
  }
  out.cpu=g_c;out.snes=g_test_snes;out.ipc=last_data_ipc;out.bus=bus_hash;out.reads=bus_reads;out.writes=bus_writes;
  out.ii=interp816_insns_total()-ii;out.ic=interp816_cycles_total()-ic;
  out.ni=interp_bridge_native_continuation_insns_total()-ni;out.nc=interp_bridge_native_continuation_cycles_total()-nc;out.logical=g_interp_bridge_steps-logical;
  out.visits=visits;out.nested=nested;out.handler_entries=handler_entries;
  out.overlay_probes=overlay_probes;
  out.quiescent=interp_bridge_lle_took_quiescent();out.wai=interp_bridge_lle_took_wai();
  InterpNativeInstructionStats stats[32];size_t n=interp_bridge_native_instruction_stats(stats,32);uint64 si=0,sc=0;
  CHECK(n<=32,"bounded per-site statistics");for(size_t i=0;i<n&&i<32;i++){si+=stats[i].insns;sc+=stats[i].cycles;}
  CHECK(si==out.ni&&sc==out.nc,"per-instruction attribution equals accepted totals");
  CHECK(!g_recomp_stack_top&&!g_pop_underflow&&!unexpected_dispatch&&!g_abandon_called,"host and guest control ownership clean");
  CHECK(!handler_entries,"native continuation refused in actual interrupt scope");
  interp_bridge_set_master_deadline(0);return out;
}
static uint8 *expected_memory;static unsigned pairs;
static void pair(int bank,int fast,int m,int x,int count,uint64 budget,int irq,int hook,int interrupt,int admission){
  Outcome a=run(0,bank,fast,m,x,count,budget,irq,hook,interrupt);memcpy(expected_memory,RAM,MEMSZ);
  Outcome b=run(1,bank,fast,m,x,count,budget,irq,hook,interrupt);
  CHECK(!memcmp(expected_memory,RAM,MEMSZ),"complete memory and inherited guest stack exact");
  CHECK(a.cpu.S==b.cpu.S,"inherited guest frame/watermark exact");
  CHECK(!memcmp(&a.cpu,&b.cpu,sizeof a.cpu),"full CPU/openbus/CPU+master clocks exact");
  CHECK(!memcmp(&a.snes,&b.snes,sizeof a.snes),"real core beam/IRQ/latch state exact");
  CHECK(a.resume==b.resume&&a.quiescent==b.quiescent&&a.wai==b.wai,"same deadline/quiescent continuation");
  CHECK(a.bus==b.bus&&a.reads==b.reads&&a.writes==b.writes,"every actual bus read/write/value/order exact");
  CHECK(a.ipc==b.ipc,"native memory writes have architectural IPC");
  CHECK(a.logical==b.logical,"shared logical retirement step indices exact");
  CHECK(a.ii==b.ii+b.ni&&a.ic==b.ic+b.nc,"native instructions and cycles never interpreted/relabelled");
  CHECK(!a.ni&&!a.nc,"forced reference disables registered continuations");
  CHECK(a.visits==b.visits&&a.nested==b.nested,"prehook/redirect/nesting phases exact");
  CHECK(a.overlay_probes==b.overlay_probes,"admission adds no overlay diagnostics");
  if(admission>=0)CHECK(admission?b.ni>0:b.ni==0,"admission or fallback measured");
  ++pairs;
}
/* METADATA_CHECKS */
int main(void){
  RAM=malloc(MEMSZ);expected_memory=malloc(MEMSZ);if(!RAM||!expected_memory)return 2;
  metadata_checks();
#ifndef PROTOCOL_NEGATIVE
  int banks[]={0x02,0x42,0x82,0xc2};
  for(unsigned b=0;b<4;b++)for(int fast=0;fast<2;fast++)for(int m=0;m<2;m++)for(int x=0;x<2;x++){
    pair(banks[b],fast,m,x,7,10000,0,0,0,1);
    pair(banks[b],fast,m,x,7,10000,1,0,0,1);
    pair(banks[b],fast,m,x,7,100,0,0,1,1);
    for(uint64 deadline=1;deadline<=120;deadline++)pair(banks[b],fast,m,x,7,deadline,0,0,0,-1);
  }
  for(unsigned h=1;h<=6;h++)pair(0x82,1,1,0,7,10000,0,h,0,1);
  for(variant=1;variant<=7;variant++)pair(0x82,1,1,0,7,10000,0,0,0,(variant==2||variant>=4&&variant<=6)?0:1);
  for(variant=8;variant<=12;variant++)pair(0x82,1,1,1,7,10000,0,0,0,0);
  variant=13;pair(0x22,1,1,0,7,10000,0,0,0,0);
  for(unsigned b=0;b<4;b++)for(int fast=0;fast<2;fast++){
    variant=14;for(int x=0;x<2;x++)pair(banks[b],fast,1,x,7,10000,0,0,0,1);
    variant=15;pair(banks[b],fast,1,1,7,10000,0,0,0,1);
  }
  variant=0;
#else
  pair(0x82,1,1,0,7,140,0,0,0,1);
#endif
  InterpExecutionShare report;g_cpu=g_c;InterpExecutionShareGet(&report);
  CHECK(report.native_continuation_insns==interp_bridge_native_continuation_insns_total(),"report continuation instruction counter");
  CHECK(report.native_continuation_cycles==interp_bridge_native_continuation_cycles_total(),"report continuation cycle counter");
  FILE *report_file=tmpfile();CHECK(report_file!=NULL,"JSON report tempfile");
  if(report_file){char text[2048]={0};InterpExecutionShareDumpJson(report_file);rewind(report_file);
    CHECK(fread(text,1,sizeof text-1,report_file)>0,"JSON report read");printf("SHARE %s",text);fclose(report_file);}
  printf("pairs=%u checks=%d failures=%d native=%llu cycles=%llu\n",pairs,g_check,fixture_fail,
    (unsigned long long)report.native_continuation_insns,(unsigned long long)report.native_continuation_cycles);
  free(RAM);free(expected_memory);return fixture_fail?1:0;
}
'''

BLOCKED = {0x00,0x44,0x6C,0xCB,0xDB,0xDC,
           0x1B,0x9A,0xFB}


def _metadata_source():
    lines = ["static void metadata_checks(void){", "InterpNativeInstruction d={0};d.pc24=0x828000;d.step=pure_decline;"]
    for opcode, (_, _, spec) in sorted(opcode_table().items()):
        for m in range(2):
            for x in range(2):
                length = spec(m, x) if callable(spec) else spec
                lines += ["interp_bridge_clear_native_instructions();memset(d.bytes,0,4);",
                          f"d.m={m};d.x={x};d.length={length};d.bytes[0]={opcode};",
                          f'CHECK(interp_bridge_add_native_instructions(&d,1)=={int(opcode not in BLOCKED)},"canonical length/control admission");',
                          'CHECK(!interp_bridge_native_frame_grants(),"canonical registration alone never grants frame effects");',
                          f'd.length={length % 4 + 1};CHECK(!interp_bridge_add_native_instructions(&d,1),"wrong canonical length refused");']
    lines += [r'''
    interp_bridge_clear_native_instructions();memset(&d,0,sizeof d);d.pc24=0x828000;d.m=1;d.length=2;d.bytes[0]=0xa9;d.step=pure_decline;
    CHECK(interp_bridge_add_native_instructions(&d,1),"valid descriptor");
    CHECK(interp_bridge_add_native_instructions(&d,1),"identical descriptor idempotent");
    CHECK(interp_bridge_native_instruction_stats(NULL,0)==1,"idempotent count");
    InterpNativeInstruction bad[2]={d,d};bad[0].pc24++;bad[1].bytes[1]=1;
    CHECK(!interp_bridge_add_native_instructions(bad,2),"atomic conflicting batch rejected");
    CHECK(interp_bridge_native_instruction_stats(NULL,0)==1,"no partial registry mutation");
    d.e=1;CHECK(!interp_bridge_add_native_instructions(&d,1),"E1 metadata refused");d.e=0;
    d.pc24=0x82ffff;CHECK(!interp_bridge_add_native_instructions(&d,1),"bank wrap metadata refused");
    d.pc24=0x827fff;CHECK(!interp_bridge_add_native_instructions(&d,1),"low code metadata refused");
    d.pc24=0x1828000;CHECK(!interp_bridge_add_native_instructions(&d,1),"invalid PC bits refused");
    CHECK(!interp_bridge_add_native_instructions(NULL,1),"NULL batch refused");
    interp_bridge_clear_native_instructions();
    setup(1,0x82,1,1,0,7,0,0);interp_bridge_clear_native_instructions();
    InterpNativeInstruction *full=calloc(131072,sizeof *full);CHECK(full!=NULL,"registry capacity allocation");
    if(full){
      const unsigned banks[]={0x02,0x42,0x82,0xc2};
      for(unsigned i=0;i<131072;i++){
        full[i]=d;full[i].pc24=(banks[i/32768]<<16)| (0x8000u+i%32768);
        full[i].length=1;full[i].step=native_capacity_nop;memset(full[i].bytes,0,4);full[i].bytes[0]=0xea;RAM[full[i].pc24]=0xea;
      }
      CHECK(full[131071].pc24==0xc2ffff,"full capacity ends on valid upper-bank opcode");
      CHECK(interp_bridge_add_native_instructions(full,131072),"full registry accepted");
      CHECK(interp_bridge_native_instruction_stats(NULL,0)==131072,"all page buckets retained");
      InterpNativeInstructionStats *stats=calloc(131072,sizeof *stats);CHECK(stats!=NULL,"full registry stats allocation");
      uint64 ni=interp_bridge_native_continuation_insns_total(),nc=interp_bridge_native_continuation_cycles_total();
      uint64 ii=interp816_insns_total(),ic=interp816_cycles_total();uint16 sp=g_c.S;
      interp_bridge_set_master_deadline(g_c.master_cycles+1);
      CHECK(interp_bridge_run_until_quiescent(&g_c,full[131071].pc24)==1,"owning bridge executes descriptor ID131072");
      interp_bridge_set_master_deadline(0);
      CHECK(interp_bridge_native_continuation_insns_total()==ni+1&&interp_bridge_native_continuation_cycles_total()==nc+2,"last descriptor exact native attribution");
      CHECK(interp816_insns_total()==ii&&interp816_cycles_total()==ic&&g_c.S==sp,"last descriptor neither interpreted nor changes owner stack");
      if(stats){CHECK(interp_bridge_native_instruction_stats(stats,131072)==131072&&stats[131071].pc24==0xc2ffff&&stats[131071].insns==1&&stats[131071].cycles==2,"last descriptor ID and per-site counters retained");}
      CHECK(interp_bridge_add_native_instructions(full,131072),"full registry idempotent batch");
      d=full[0];d.pc24=0x838000;
      CHECK(!interp_bridge_add_native_instructions(&d,1),"unique capacity overflow atomic refusal");
      InterpNativeInstruction conflict=full[131071];conflict.step=pure_decline;
      CHECK(!interp_bridge_add_native_instructions(&conflict,1),"full registry conflicting callback refusal");
      CHECK(!interp_bridge_add_native_instructions(full,131073),"oversized batch refused before input traversal");
      CHECK(interp_bridge_native_instruction_stats(NULL,0)==131072,"capacity refusal preserves registry");
      if(stats){CHECK(interp_bridge_native_instruction_stats(stats,131072)==131072&&stats[131071].pc24==0xc2ffff&&stats[131071].insns==1&&stats[131071].cycles==2,"idempotence and all refusals preserve used last descriptor");free(stats);}
      CHECK(interp_bridge_native_continuation_insns_total()==ni+1&&interp_bridge_native_continuation_cycles_total()==nc+2,"idempotence and refusals preserve global counters");free(full);
    }
    interp_bridge_clear_native_instructions();
    ''', "}"]
    return "\n".join(lines)


def _source(negative=None):
    source = fallback_source()
    source = source[:source.index("    int main(void){")]
    source = source.replace("\n    uint8 cpu_read8(", "\nuint8 cpu_read8(")
    source = source.replace(_c_function(source,"cpu_dispatch_has_entry"),
        "int cpu_dispatch_has_entry(CpuState *cpu,uint32 pc){(void)cpu;(void)pc;return 0;}\n")
    source = source.replace(_c_function(source,"cpu_interrupt_context_active"),
        "int cpu_interrupt_context_active(void){return interrupt_scope;}\n")
    mapping=_c_function(source,"cart_getRomPtr")
    source=source.replace(mapping,mapping.replace("(void)cart;",
        "if((bank&0x7f)>=0x20&&(bank&0x7f)<0x30&&cart->overlayBank[(bank&0x7f)-0x20])++overlay_probes;"))
    source = source.replace(_c_function(source,"cpu_read8"), r'''
uint8 cpu_read8(CpuState *cpu,uint8 bank,uint16 addr){
  uint32 pc=((uint32)bank<<16)|addr;uint8 value;
  if((bank&0x7f)<0x40&&addr==0x4210){++rdnmi_reads;value=snes_readReg(g_snes,addr);}else value=RAM[pc];
  bus_hash^=((uint64)pc<<8)|value;bus_hash*=1099511628211ULL;++bus_reads;return cpu->open_bus=value;
}''')
    source = source.replace(_c_function(source,"cpu_write8"), r'''
void cpu_write8(CpuState *cpu,uint8 bank,uint16 addr,uint8 value){
  uint32 pc=((uint32)bank<<16)|addr;RAM[pc]=value;cpu->open_bus=value;
  bus_hash^=((uint64)pc<<8)|value|((uint64)1<<40);bus_hash*=1099511628211ULL;++bus_writes;
  if(pc==0x7e0200||pc==0x7e0201)last_data_ipc=g_interp816_cur_pc;
}''')
    body = PROGRAM.replace("/* METADATA_CHECKS */", _metadata_source())
    if negative:
        body = "#define PROTOCOL_NEGATIVE 1\n" + body
        original = _c_function(body, "native_sta")
        if negative == "relabel": replacement = "static int native_sta(Interp816 *in){return interp816_runOpcode(in);}\n"
        elif negative == "clock": replacement = original.replace("5+!in->mf", "6+!in->mf")
        elif negative == "frame": replacement = original.replace("return in->cyclesUsed", "in->sp+=3;return in->cyclesUsed")
        else: raise AssertionError(negative)
        body = body.replace(original, replacement)
    return '#include "cpu_state.h"\n#include "snes/interp816.h"\nstatic uint64_t bus_hash,bus_reads,bus_writes;static uint32_t last_data_ipc;static int interrupt_scope;static unsigned overlay_probes;\n'+source+body


def _run(tmp_path, negative=None, lookup=None):
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc") or shutil.which("gcc")
    if not cc: pytest.skip("C11 compiler required")
    source=tmp_path/"continuation.c";source.write_text(_source(negative),encoding="utf-8")
    core=tmp_path/"snes_core.c";core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n',encoding="utf-8")
    exe=tmp_path/("continuation.exe" if os.name=="nt" else "continuation")
    command=[cc,"-std=c11","-O1","-DSNESRECOMP_TIER2_TEST=1","-DSNESRECOMP_REVERSE_DEBUG=0",
      "-I",str(REPO/"runner/src"),"-I",str(REPO/"runner/src/snes"),"-I",str(REPO/"tests/dma"),str(source),str(core),
      *[str(REPO/f)for f in ("runner/src/snes/interp816.c","runner/src/sha256.c","runner/src/snes/tier2_capture.c",
         "runner/src/snes/interp_bridge.c","runner/src/snes/cx4.c","runner/src/snes/dma.c","runner/src/snes/sdd1.c")],"-lm","-o",str(exe)]
    compiled=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (tmp_path/"compile.json").write_text(json.dumps(dict(command=command,exit_code=compiled.returncode,stdout=compiled.stdout,stderr=compiled.stderr),indent=2),encoding="utf-8")
    assert compiled.returncode==0,compiled.stdout+compiled.stderr
    environment=os.environ.copy()
    if lookup is not None: environment['SNESRECOMP_NATIVE_INSTRUCTION_INDEX']=lookup
    result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60,cwd=tmp_path,env=environment)
    (tmp_path/"execution.json").write_text(json.dumps(dict(exit_code=result.returncode,lookup=lookup,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
      binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),stdout=result.stdout,stderr=result.stderr),indent=2),encoding="utf-8")
    return result


@pytest.mark.parametrize("lookup",["0","1"])
def test_native_continuations_share_actual_core_retirement(tmp_path,lookup):
    result=_run(tmp_path,lookup=lookup)
    assert result.returncode==0,result.stdout+result.stderr
    assert "failures=0" in result.stdout
    line=next(s.removeprefix("SHARE ").strip().removesuffix(",")for s in result.stdout.splitlines()if s.startswith("SHARE "))
    share=json.loads("{"+line+"}")["execution_share"]
    assert share["native_continuation_insns"]>0 and share["native_continuation_cycles"]>0


@pytest.mark.parametrize("negative",["relabel","clock","frame"])
def test_continuation_counter_clock_and_frame_corruption_are_rejected(tmp_path,negative):
    result=_run(tmp_path,negative)
    assert result.returncode!=0
    expected={"relabel":"never interpreted/relabelled","clock":"CPU+master clocks exact","frame":"inherited guest frame/watermark exact"}[negative]
    assert expected in result.stdout+result.stderr
