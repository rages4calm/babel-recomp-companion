"""ROM-free actual owning-bridge WRAM copy effects and real peripheral parity.

The only normalized observer field is IPC on the one actual first opcode
fetch, armed by the bridge's instruction hook. Prepeek, operand, data, stack
and write IPC, addresses, values, ordering and phases remain strict.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess

import pytest
from test_native_mmio_continuation import _source as mmio_source, BUS as OLD_BUS

REPO=Path(__file__).resolve().parents[2]

BUS=r'''
typedef struct {uint32_t adr,ipc,lead;uint64_t master;uint8_t value,write;} MmioEvent;
static MmioEvent events[8192];static unsigned event_count;
static unsigned opcode_fetch_armed;static uint32_t opcode_fetch_pc;
static void arm_opcode_fetch(uint32_t pc,int m,int x){
 (void)m;(void)x;opcode_fetch_pc=pc;opcode_fetch_armed=1;
}
static void mmio_note(CpuState *cpu,uint32_t adr,uint8_t value,int write){
 CHECK(event_count<8192,"ordered bus log bounded");
 if(event_count<8192){MmioEvent *e=&events[event_count++];memset(e,0,sizeof *e);
  e->adr=adr;e->ipc=g_interp816_cur_pc;
  if(!write&&opcode_fetch_armed&&adr==opcode_fetch_pc){e->ipc=0;opcode_fetch_armed=0;}
  e->lead=interp_bridge_access_lead((uint16_t)adr,0);
  e->master=cpu->master_cycles;e->value=value;e->write=write;}
}
static int mapped_ram(uint8_t bank,uint16_t addr){
 return bank==0x7e||bank==0x7f||(((bank&0x7f)<0x40)&&addr<0x2000);
}
uint8 cpu_read8(CpuState *cpu,uint8 bank,uint16 addr){
 uint32_t adr=((uint32_t)bank<<16)|addr;uint8_t value;
 if(mapped_ram(bank,addr)||((bank&0x7f)<0x40&&addr>=0x2100&&addr<0x4380))value=snes_read(g_snes,adr);
 else value=RAM[adr];
 mmio_note(cpu,adr,value,0);return cpu->open_bus=value;
}
void cpu_write8(CpuState *cpu,uint8 bank,uint16 addr,uint8 value){
 uint32_t adr=((uint32_t)bank<<16)|addr;mmio_note(cpu,adr,value,1);
 if(mapped_ram(bank,addr)||((bank&0x7f)<0x40&&addr>=0x2100&&addr<0x4380))snes_write(g_snes,adr,value);
 else RAM[adr]=value;
 cpu->open_bus=value;
}
'''

SUPPORT=r'''
static unsigned wc_bank=0x83,wc_mode,wc_variant,wc_visits,wc_pairs,wc_mutant,wc_hooked;
static uint16_t wc_count=2,wc_x=0x1000,wc_y=0x1800,wc_stack=0x1ff;
static unsigned wc_dest=0x7f,wc_src=0x7e;
static uint64_t wc_deadline;
static InterpNativeInstructionStep actual_mvn[256][4];
static int broken_mvn(Interp816 *in){
 unsigned mode=(in->mf<<1)|in->xf;
 if(wc_mutant==1){int cycles=0;do{cycles+=actual_mvn[in->k][mode](in);}while(in->a!=0xffff);return in->cyclesUsed=cycles;}
 /* A wrong cached-operand callback overwrites the live operand before its
  * original fetch. The bus and final RAM must detect this, not just totals. */
 uint8_t old=g_test_snes.ram[0x404];g_test_snes.ram[0x404]=0x7f;
 int cycles=actual_mvn[in->k][mode](in);g_test_snes.ram[0x404]=old;return cycles;
}
static void wc_hook(CpuState *cpu,uint32 pc){
 ++wc_visits;
 if(wc_variant==1&&wc_visits==2){g_test_snes.ram[0x404]=0x7e;g_test_snes.ram[0x405]=0x7f;}
 if(wc_variant==2&&wc_visits==2){g_test_snes.ram[0x403]=0x80;g_test_snes.ram[0x404]=1;}
 if(wc_variant==3&&wc_visits==2){cpu->x_flag=!cpu->x_flag;cpu_mirrors_to_p(cpu);}
 if(wc_variant==4&&!wc_hooked++){
  uint16_t sp=cpu->S;uint64_t ni=interp_bridge_native_continuation_insns_total();
  cpu_push_interrupt_frame_at(cpu,pc);
  CHECK(interp_bridge_run_interrupt(cpu,0x008800)==1,"foreign nested interrupt completes");
  CHECK(cpu->S==sp,"nested frame balanced");
  CHECK(interp_bridge_native_continuation_insns_total()==ni,"foreign nested owner refuses WRAM native effects");
 }
}
typedef struct {
 CpuState cpu;Snes snes;Apu apu;Spc spc;Dsp dsp;Dma dma;
 MmioEvent events[8192];unsigned count;uint8_t wram[0x20000];
 uint64_t dma_clocks,ni,nc,ii,ic,logical,wi,wc,nmi;uint32_t resume;
} WramOutcome;
static WramOutcome before,after;
static void wc_register(int policy){
 InterpNativeWramCopyInstruction items[128];size_t n=sizeof wc_entries/sizeof *wc_entries;
 CHECK(n<=128,"bounded synthetic WRAM entries");memcpy(items,wc_entries,sizeof wc_entries);
 if(wc_mutant)for(size_t i=0;i<n;i++)if((items[i].pc24&65535)==0x403){
  actual_mvn[items[i].pc24>>16][(items[i].m<<1)|items[i].x]=items[i].step;items[i].step=broken_mvn;
 }
 if(policy==3){size_t used=0;for(size_t i=0;i<n;i++)if(items[i].m!=((wc_mode>>1)&1))items[used++]=items[i];n=used;}
 if(policy==6)for(size_t i=0;i<n;i++)if(items[i].scopes&2)items[i].nmi_owner_pc24=0x8900;
 if(policy==7)for(size_t i=0;i<n;i++){items[i].scopes=1;items[i].nmi_owner_pc24=0;}
 CHECK(interp_bridge_add_native_wram_copy_instructions(items,n),"actual generated copy registration");
 if(policy!=1)interp_bridge_set_native_wram_copy_enabled(true);
 if(policy==2)interp_bridge_clear_native_instructions();
 if(policy==4){uint32 excluded=(wc_bank<<16)|0x403;interp_bridge_set_lle_bounce_exclusions(&excluded,1);}
}
static void wc_run(WramOutcome *out,int native,unsigned budget,int policy,int nmi){
 memset(RAM,0,MEMSZ);init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);memset(&g_test_cart,0,sizeof g_test_cart);
 static Dma dma;memset(&dma,0,sizeof dma);dma.snes=&g_test_snes;
 g_test_snes.dma=&dma;g_test_snes.ram=RAM+0x7e0000;g_test_snes.cart=&g_test_cart;g_test_snes.hdmaBeamOff=true;
 g_test_cart.type=policy==5?CART_SA1:CART_HIROM;g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
 g_test_snes.apu=apu_init();CHECK(g_test_snes.apu!=NULL,"real APU allocation");apu_reset(g_test_snes.apu);
 Apu *a=g_test_snes.apu;a->romReadable=false;a->spc->pc=0x200;a->cpuCyclesLeft=0;
 const uint8_t echo[]={0xe4,0xf4,0xc4,0xf4,0x2f,0xfa};memcpy(a->ram+0x200,echo,sizeof echo);
 CHECK(apu_enqueuePortWriteAt(a,0,0x5a,12),"real queued SPC input");
 s_apu_spc_offset=0;s_apu_access_adr=0;s_apu_access_write=false;g_apu_last_sync_master=0;
 g_cpu.A=wc_count;g_cpu.X=wc_x;g_cpu.Y=wc_y;g_cpu.S=wc_stack;g_cpu.D=0x0123;g_cpu.DB=0x81;
 g_cpu.m_flag=(wc_mode>>1)&1;g_cpu.x_flag=wc_mode&1;g_cpu.emulation=0;g_cpu._flag_I=1;cpu_mirrors_to_p(&g_cpu);
 g_memsel=1;snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(false);
 snes_set_master_clock_charge_hook(mmio_dma_charge);g_snes_dma_charged=0;
 for(unsigned i=0;i<0x20000;i++)g_test_snes.ram[i]=(uint8_t)(i*7+(i>>16)*13);
 const uint8_t stub[]={0x8b,0x54,(uint8_t)wc_dest,(uint8_t)wc_src,0xab,0x60};
 memcpy(g_test_snes.ram+0x402,stub,sizeof stub);
 const uint8_t program[]={0x20,0x02,0x04,0x80,0xfe};
 memcpy(RAM+(wc_bank<<16)+0x9000,program,sizeof program);
 /* IRQ/NMI handler JSRs the same physical00 RAM stub then acknowledges4211. */
 const uint8_t handler[]={0xc2,0x20,0xa9,0,0,0x20,0x02,0x04,0xad,0x11,0x42,0x40};memcpy(RAM+0x8800,handler,sizeof handler);
 g_test_snes.ramAdr=0x1a00;dma.channel[0].aBank=0x7e;dma.channel[0].aAdr=0x1000;dma.channel[0].bAdr=0x80;dma.channel[0].size=8;
 if(wc_variant==5){g_test_snes.ram[0x404]=0;g_cpu.Y=0x420b;g_test_snes.ram[wc_x]=1;}
 if(wc_variant==6){g_test_snes.ram[0x405]=0;g_cpu.X=0x2140;}
 if(wc_variant==7){const uint8_t safe[]={0xea,0xea,0xea,0xea,0xea,0x60};memcpy(g_test_snes.ram+0x402,safe,sizeof safe);}
 if(wc_variant==8){g_test_snes.ram[0x404]=0x7e;g_test_snes.ram[0x405]=0x7f;
  g_cpu.Y=0x404;g_test_snes.ram[0x10000+wc_x]=0x7f;}
 if(wc_variant==9){snes_set_raster_irq_beam_enabled(true);g_test_snes.vPos=224;g_test_snes.hPos=0;
  g_test_snes.hIrqEnabled=true;g_test_snes.hTimer=20;g_cpu._flag_I=0;cpu_mirrors_to_p(&g_cpu);}
 interp_bridge_set_interpret_all(!native);interp_bridge_clear_native_instructions();interp_bridge_clear_native_rdnmi_polls();
 interp_bridge_clear_idle_polls();interp_bridge_reset_dynamic_cache();interp_bridge_set_pre_opcode_hook(0,NULL);
 interp_bridge_set_lle_bounce_exclusions(NULL,0);wc_visits=wc_hooked=0;wc_register(policy);
 if(wc_variant>=1&&wc_variant<=4)interp_bridge_add_pre_opcode_hook((wc_bank<<16)|0x403,wc_hook);
 g_interp_bridge_pc_hook=arm_opcode_fetch;opcode_fetch_armed=0;g_interp816_cur_pc=0;
 event_count=0;memset(events,0,sizeof events);memset(out,0,sizeof *out);
 uint64_t ni=interp_bridge_native_continuation_insns_total(),nc=interp_bridge_native_continuation_cycles_total();
 uint64_t wi=interp_bridge_native_wram_copy_insns_total(),wc=interp_bridge_native_wram_copy_cycles_total();
 uint64_t nmic=interp_bridge_native_nmi_insns_total();
 uint64_t ii=interp816_insns_total(),ic=interp816_cycles_total(),logical=g_interp_bridge_steps;
 wc_deadline=budget;interp_bridge_set_master_deadline(budget);
 if(nmi){
  g_cpu.PB=0x83;cpu_push_interrupt_frame_at(&g_cpu,0x839000);
  g_test_snes.inNmi=g_test_snes.rdnmiPending=g_test_snes.nmiEnabled=true;
  int result=nmi==2?interp_bridge_run_interrupt(&g_cpu,0x008800):interp_bridge_run_native_nmi(&g_cpu,0x008800);
  CHECK(result==1,"finite original interrupt owner");
 }else CHECK(interp_bridge_run_until_quiescent(&g_cpu,(wc_bank<<16)|0x9000)==1,"same actual scheduler bridge");
 if(wc_variant==9){unsigned delivered=0;while(g_test_snes.inIrq&&!g_cpu._flag_I&&g_cpu.master_cycles<budget){
  CHECK(++delivered<8,"bounded actual comparator IRQ deliveries");if(delivered>=8)break;
  uint32_t resume=interp_bridge_lle_resume_pc();uint16_t sp=g_cpu.S;
  uint64_t n=interp_bridge_native_continuation_insns_total();cpu_push_interrupt_frame_at(&g_cpu,resume);
  CHECK(interp_bridge_run_interrupt(&g_cpu,0x008800)==1,"actual comparator IRQ uses original foreign owner");
  CHECK(g_cpu.S==sp&&interp_bridge_native_continuation_insns_total()==n,"IRQ frame balances and cannot inherit WRAM grants");
  CHECK(interp_bridge_run_until_quiescent(&g_cpu,resume)==1,"actual pending IRQ resumes exact scheduler PC");
 }}
 interp_bridge_set_master_deadline(0);out->cpu=g_cpu;out->snes=g_test_snes;
 out->snes.ram=NULL;out->snes.cart=NULL;out->snes.apu=NULL;out->snes.dma=NULL;
 out->apu=*a;out->apu.spc=NULL;out->apu.dsp=NULL;out->spc=*a->spc;out->spc.apu=NULL;
 out->dsp=*a->dsp;out->dsp.apu_ram=NULL;out->dsp.shadow=NULL;out->dsp.output_filter=NULL;
 out->dma=dma;out->dma.snes=NULL;out->count=event_count;memcpy(out->events,events,event_count*sizeof *events);
 memcpy(out->wram,g_test_snes.ram,sizeof out->wram);out->dma_clocks=g_snes_dma_charged;
 out->ni=interp_bridge_native_continuation_insns_total()-ni;out->nc=interp_bridge_native_continuation_cycles_total()-nc;
 out->wi=interp_bridge_native_wram_copy_insns_total()-wi;out->wc=interp_bridge_native_wram_copy_cycles_total()-wc;
 out->nmi=interp_bridge_native_nmi_insns_total()-nmic;
 out->ii=interp816_insns_total()-ii;out->ic=interp816_cycles_total()-ic;out->logical=g_interp_bridge_steps-logical;
 out->resume=interp_bridge_lle_resume_pc();apu_free(a);g_test_snes.apu=NULL;g_interp_bridge_pc_hook=NULL;
}
static void wc_pair(unsigned budget,int policy,int nmi){
 wc_run(&before,0,budget,policy,nmi);wc_run(&after,1,budget,policy,nmi);++wc_pairs;
 CHECK(!memcmp(&before.cpu,&after.cpu,sizeof before.cpu),"WRAM fullCPU/PBR/flags/width/stack/master/openbus parity");
 CHECK(!memcmp(&before.snes,&after.snes,sizeof before.snes),"WRAM actual Snes/beam/IRQ/WRAM port state parity");
 CHECK(!memcmp(&before.apu,&after.apu,sizeof before.apu)&&!memcmp(&before.spc,&after.spc,sizeof before.spc)&&!memcmp(&before.dsp,&after.dsp,sizeof before.dsp),"real complete APU/SPC/DSP scheduler parity");
 if(before.count!=after.count||memcmp(before.events,after.events,before.count*sizeof *events)){
  static unsigned reports;if(reports++<4){fprintf(stdout,"BUSDIFF bank=%02X mode=%u variant=%u policy=%d nmi=%d budget=%u counts=%u/%u\n",wc_bank,wc_mode,wc_variant,policy,nmi,budget,before.count,after.count);
   unsigned n=before.count<after.count?before.count:after.count;
   for(unsigned i=0;i<n;i++)if(memcmp(&before.events[i],&after.events[i],sizeof *events)){
    MmioEvent *a=&before.events[i],*z=&after.events[i];fprintf(stdout,"event%u adr=%06X/%06X ipc=%06X/%06X lead=%u/%u master=%llu/%llu value=%02X/%02X write=%u/%u\n",i,a->adr,z->adr,a->ipc,z->ipc,a->lead,z->lead,(unsigned long long)a->master,(unsigned long long)z->master,a->value,z->value,a->write,z->write);break;
   }
  }
 }
 CHECK(before.count==after.count&&!memcmp(before.events,after.events,before.count*sizeof *events),"strict actual bus address/value/order/lead/master/data-stack-write IPC parity");
 CHECK(!memcmp(&before.dma,&after.dma,sizeof before.dma)&&!memcmp(before.wram,after.wram,sizeof before.wram)&&before.dma_clocks==after.dma_clocks,"WRAM and DMA payload/state/clock parity");
 CHECK(before.logical==after.logical&&before.resume==after.resume,"same owning opcode retirement/deadline resume");
 CHECK(!before.ni&&before.ii==after.ii+after.ni&&before.ic==after.ic+after.nc,"actual native callback effects conserve decoder/CPU counts");
 CHECK(after.wi==after.ni&&after.wc==after.nc&&after.nmi<=after.ni,"WRAM/NMI are NI subsets, not extra work");
 if(policy==1||policy==2||policy==3||policy==5||wc_variant==7)CHECK(!after.wi,"default-disabled/clear/mode/mapper/shape refusal remains interpreted");
 if(policy==4){InterpNativeInstructionStats stats[128];size_t n=interp_bridge_native_instruction_stats(stats,128);
  CHECK(n<=128,"bounded exclusion stats");for(size_t i=0;i<n&&i<128;i++)if(stats[i].pc24==((wc_bank<<16)|0x403))CHECK(!stats[i].insns,"per-PC exclusion refuses every MVN mode");}
 if(nmi&&(nmi==2||policy==6||policy==7))CHECK(!after.wi,"foreign/IRQ/ungranted finite owner refuses copy");
 if(!policy&&!wc_variant&&budget>=2000&&nmi!=2)CHECK(after.wi>0,"source-shaped copy actually executes native");
 if(nmi==1&&!policy)CHECK(after.wi>0&&after.nmi==after.wi,"exact finite NMI executes copy as NI subset");
}
static void registry_tests(void){
 interp_bridge_set_interpret_all(0);interp_bridge_clear_native_instructions();
 InterpNativeWramCopyInstruction d=wc_entries[0],bad=d;
 CHECK(interp_bridge_add_native_wram_copy_instructions(&d,1),"register one copy");
 CHECK(interp_bridge_native_wram_copy_grants()==1,"exact physical grant count");
 CHECK(interp_bridge_add_native_wram_copy_instructions(&d,1)&&interp_bridge_native_wram_copy_grants()==1,"identical duplicate idempotent");
 bad.scopes=bad.scopes==1?3:1;bad.nmi_owner_pc24=bad.scopes==3?0x8800:0;
 CHECK(!interp_bridge_add_native_wram_copy_instructions(&bad,1)&&interp_bridge_native_wram_copy_grants()==1,"conflicting owner-scope duplicate atomic");
 const uint32_t forbidden[]={0x400402,0xc00402,0x7f0402,0x1000402};
 for(unsigned i=0;i<4;i++){bad=d;bad.pc24=forbidden[i];CHECK(!interp_bridge_add_native_wram_copy_instructions(&bad,1),"non-WRAM physical bank refused");}
 bad=d;bad.stub_pc=0x1ffb;bad.pc24=(d.pc24&0xff0000)|0x1ffb;CHECK(!interp_bridge_add_native_wram_copy_instructions(&bad,1),"whole stub must fit low8KiB");
 bad=d;bad.pc24=(d.pc24&0xff0000)|0x404;CHECK(!interp_bridge_add_native_wram_copy_instructions(&bad,1),"operand is not an instruction boundary");
 bad=d;bad.e=1;CHECK(!interp_bridge_add_native_wram_copy_instructions(&bad,1),"E1 refused");
 bad=d;bad.scopes=0;CHECK(!interp_bridge_add_native_wram_copy_instructions(&bad,1),"implicit scope refused");
 bad=d;bad.step=NULL;CHECK(!interp_bridge_add_native_wram_copy_instructions(&bad,1),"missing callback refused");
 bad=d;bad.scopes=2;bad.nmi_owner_pc24=0x0402;CHECK(!interp_bridge_add_native_wram_copy_instructions(&bad,1),"invalid NMI owner refused");
 InterpNativeWramCopyInstruction batch[]={d,d};batch[0].pc24=(d.pc24&0xff0000)|0x406;batch[1].e=1;
 CHECK(!interp_bridge_add_native_wram_copy_instructions(batch,2)&&interp_bridge_native_wram_copy_grants()==1,"late invalid batch leaves no prefix grants");
 CHECK(!interp_bridge_add_native_wram_copy_instructions(&d,131073),"over-capacity count refuses before dereference");
 InterpNativeInstruction rom={0};rom.pc24=d.pc24;rom.length=1;rom.bytes[0]=0x8b;rom.step=d.step;
 CHECK(!interp_bridge_add_native_instructions(&rom,1),"ordinary ROM API still refuses low WRAM");
 rom.pc24=0x838000;rom.length=3;rom.bytes[0]=0x54;
 CHECK(interp_bridge_add_native_instructions(&rom,1),"ordinary ROM API accepts canonical MVN descriptor");
 CHECK(interp_bridge_native_wram_copy_grants()==1,"ordinary ROM MVN adds no mutable WRAM grant");
 interp_bridge_clear_native_instructions();CHECK(!interp_bridge_native_wram_copy_grants(),"clear registrations clears copy grants");
 InterpNativeWramCopyInstruction *full=calloc(65535,sizeof *full);CHECK(full!=NULL,"bounded full-capacity fixture allocation");
 if(full){for(unsigned i=0;i<65535;i++){
   uint16_t base=(uint16_t)((i/4)%0x1ffa+1);full[i]=d;
   full[i].pc24=((0x80u+(i/4)/0x1ffau)<<16)|base;full[i].stub_pc=base;
   full[i].m=(i>>1)&1;full[i].x=i&1;full[i].scopes=1;full[i].nmi_owner_pc24=0;
  }
  CHECK(interp_bridge_add_native_wram_copy_instructions(full,65535)&&interp_bridge_native_wram_copy_grants()==65535,"actual copy registry reaches65535 exact physical/mode entries");
  d.pc24=0x830402;d.scopes=1;d.nmi_owner_pc24=0;
  CHECK(interp_bridge_add_native_wram_copy_instructions(&d,1)&&interp_bridge_native_wram_copy_grants()==65536,"legacy65535 boundary now admits one additional exact WRAM key");
  free(full);interp_bridge_clear_native_instructions();
 }
}
int main(int argc,char **argv){
 RAM=malloc(MEMSZ);if(!RAM)return 2;wc_mutant=argc>1?(unsigned)atoi(argv[1]):0;
 if(wc_mutant){wc_variant=1;wc_count=2;wc_pair(2000,0,0);}
 else{
  for(unsigned b=0;b<5;b++)for(wc_mode=0;wc_mode<4;wc_mode++){
   wc_bank=(unsigned[]){0,0x80,0x82,0x83,0x7e}[b];wc_variant=0;wc_count=2;wc_x=0x1000;wc_y=0x1800;
   for(unsigned budget=1;budget<230;budget+=11)wc_pair(budget,0,0);wc_pair(2000,0,0);
  }
  wc_bank=0x83;wc_mode=0;
  for(unsigned count=0;count<3;count++)for(unsigned wrap=0;wrap<2;wrap++){
   wc_count=(uint16_t[]){0,1,0xffff}[count];wc_x=wrap?0xffff:0xff;wc_y=wrap?0xffff:0xff;
   for(unsigned budget=28;budget<150;budget+=13)wc_pair(budget,0,0);
  }
  wc_count=2;wc_x=0x1000;wc_y=0x1800;
  for(wc_variant=1;wc_variant<=8;wc_variant++)wc_pair(2000,0,0);
  wc_variant=9;wc_pair(2000,0,0);
  wc_variant=0;wc_dest=0x7f;wc_src=0x7e;
  for(unsigned s=0;s<3;s++){wc_stack=(uint16_t[]){0,1,0xffff}[s];wc_pair(2000,0,0);}wc_stack=0x1ff;
  for(unsigned p=1;p<=5;p++)wc_pair(2000,p,0);
  wc_bank=0;for(wc_mode=0;wc_mode<4;wc_mode++){
   wc_pair(2000,0,1);wc_pair(2000,0,2);wc_pair(2000,6,1);wc_pair(2000,7,1);
  }
  registry_tests();
 }
 printf("wram_pairs=%u checks=%d failures=%d\n",wc_pairs,g_check,fixture_fail);free(RAM);return fixture_fail?1:0;
}
'''


def _source():
    # Import lazily: preparing this test must not race the emitter's author.
    from v2.native_wram_effects import emit
    text,_=mmio_source()
    start=text.index('/* PRIVATE ROM-derived continuations;')
    text=text[:start]
    assert OLD_BUS in text
    text=text.replace(OLD_BUS,BUS)
    entries=[]
    for bank in (0,0x80,0x82,0x83,0x7e):
        for offset in (0,1,4,5):
            for m in range(2):
                for x in range(2):
                    entries.append(dict(pc24=(bank<<16)|0x402,stub_pc=0x402,m=m,x=x,e=0,
                                        scopes=3 if bank==0 else 1,nmi_owner_pc24=0x8800 if bank==0 else 0))
                    entries[-1]['pc24']=(bank<<16)|(0x402+offset)
    generated,receipt=emit((REPO/'runner/src/snes/interp816.c').read_text(encoding='utf-8'),entries,
                           registration_name='RegisterWram')
    assert not re.search(r'\b(?:interp816_|wc_\w+_)(?:runOpcode|doOpcode)\s*\(',generated)
    return text+generated+SUPPORT,receipt


@pytest.mark.parametrize('lookup',['0','1'])
@pytest.mark.parametrize('mutant',[0,1,2])
def test_native_wram_actual_owner_bus_and_peripherals(tmp_path,lookup,mutant):
    cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    text,receipt=_source();source=tmp_path/'wram.c';source.write_text(text,encoding='utf-8')
    exe=tmp_path/('wram.exe'if os.name=='nt'else'wram')
    files=['interp816.c','interp_bridge.c','snes.c','apu.c','spc.c','dsp.c','dsp_clock.c','dma.c','cx4.c','sdd1.c','tier2_capture.c']
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0',
             '-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),
             str(source),*[str(REPO/'runner/src/snes'/f)for f in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    built=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (tmp_path/'compile.json').write_text(json.dumps(dict(command=command,exit_code=built.returncode,stdout=built.stdout,stderr=built.stderr),indent=2))
    assert built.returncode==0,built.stdout+built.stderr
    env={k:v for k,v in os.environ.items()if not k.startswith(('IOG_','SNESRECOMP_'))}
    env['SNESRECOMP_NATIVE_INSTRUCTION_INDEX']=lookup
    run=subprocess.run([str(exe),str(mutant)],capture_output=True,text=True,timeout=90,env=env,cwd=tmp_path)
    (tmp_path/'execution.json').write_text(json.dumps(dict(lookup=lookup,mutant=mutant,emission=receipt,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr),indent=2))
    if mutant:
        assert run.returncode!=0,run.stdout+run.stderr
        assert 'wram_pairs=1' in run.stdout and ('parity' in run.stderr or 'parity' in run.stdout),run.stdout+run.stderr
    else:assert run.returncode==0,run.stdout+run.stderr
