"""ROM-free generated effects, owning bridge, real SPC/DSP and WRAM DMA.

The fixture selects the production master-clock APU timeline. Unrelated host
presentation/dispatch surfaces remain the established bridge-fixture stubs.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess

import pytest
from v2.native_effects import emit
from test_native_continuation import _source as continuation_source
from test_region_pacing import _c_function

REPO = Path(__file__).resolve().parents[2]


def _functions(source):
    return set(re.findall(r"(?m)^(?:[A-Za-z_]\w*[ \t*]+)+([A-Za-z_]\w*)\([^;{}]*\)\s*\{", source))


BUS = r'''
typedef struct {uint32_t adr,ipc,lead;uint64_t master;uint8_t value,write;} MmioEvent;
static MmioEvent events[8192];static unsigned event_count;
static void mmio_note(CpuState *cpu,uint32_t adr,uint8_t value,int write){
  CHECK(event_count<8192,"ordered bus log bounded");
  if(event_count<8192){MmioEvent *e=&events[event_count++];memset(e,0,sizeof *e);
    /* Reference runOpcode publishes write IPC after its opcode fetch; the
     * native bridge publishes it before. It is architectural data/write
     * attribution, not a code-fetch observer contract. Keep all fetch bus
     * addresses/order/values/clocks, and compare IPC on actual data accesses. */
    e->adr=adr;e->ipc=(adr&0xffffu)<0x8000u?g_interp816_cur_pc:0;e->lead=interp_bridge_access_lead((uint16_t)adr,0);
    e->master=cpu->master_cycles;e->value=value;e->write=write;}
}
uint8 cpu_read8(CpuState *cpu,uint8 bank,uint16 addr){
  uint32_t adr=((uint32_t)bank<<16)|addr;uint8_t value;
  if((bank&0x7f)<0x40&&addr>=0x2100&&addr<0x4380)value=snes_read(g_snes,adr);
  else value=RAM[adr];
  mmio_note(cpu,adr,value,0);return cpu->open_bus=value;
}
void cpu_write8(CpuState *cpu,uint8 bank,uint16 addr,uint8 value){
  uint32_t adr=((uint32_t)bank<<16)|addr;mmio_note(cpu,adr,value,1);
  if((bank&0x7f)<0x40&&addr>=0x2100&&addr<0x4380)snes_write(g_snes,adr,value);
  else RAM[adr]=value;
  cpu->open_bus=value;
}
'''


CLOCK = r'''
#define RTL_SMP_HALF_PER_SEC 2050560ull
#define RTL_MASTER_PER_SEC 21477270ull
static uint32_t s_apu_lead;static int s_apu_kr,s_apu_kw;static int64_t s_apu_spc_offset;
static uint64_t (*s_cpu_access_clock)(uint64_t,uint32_t);
static uint16_t s_apu_access_adr;static bool s_apu_access_write;
uint32_t interp_bridge_access_lead(uint16_t adr,uint32_t fallback);
void rtl_sync_apu_to_cpu_locked(void);
/* Production's master-clock branch; non-master timelines are outside this fixture. */
bool rtl_apu_master_clock(void){return true;}
uint64_t rtl_cpu_master_now(void){return g_cpu.master_cycles;}
void rtl_sync_apu_to_cpu_locked(void){rtl_apu_master_sync_locked();}
static void mmio_dma_charge(Snes *snes,uint64_t clocks){g_cpu.master_cycles+=clocks;snes_sync_master_clock(snes,g_cpu.master_cycles);}
'''


MAIN = r'''
typedef struct {
 CpuState cpu;Apu apu;Spc spc;Dsp dsp;Dma dma;
 MmioEvent events[8192];unsigned count;uint8_t wram[0x20000];
 uint64_t dma_clocks,ni,nc,ii,ic,logical;uint32_t resume;
} MmioOutcome;
static MmioOutcome before,after;static unsigned mmio_pairs;
static void mmio_run(MmioOutcome *out,int native,unsigned budget,unsigned ack,int dma_enabled){
 memset(RAM,0,MEMSZ);init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);memset(&g_test_cart,0,sizeof g_test_cart);
 static Dma dma;memset(&dma,0,sizeof dma);dma.snes=&g_test_snes;
 g_test_snes.dma=&dma;g_test_snes.ram=RAM+0x7e0000;g_test_snes.cart=&g_test_cart;g_test_snes.hdmaBeamOff=true;
 g_test_cart.type=CART_HIROM;g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
 g_test_snes.apu=apu_init();CHECK(g_test_snes.apu!=NULL,"real APU allocation");apu_reset(g_test_snes.apu);
 Apu *a=g_test_snes.apu;a->romReadable=false;a->spc->pc=0x200;a->cpuCyclesLeft=0;
 const uint8_t echo[]={0xe4,0xf4,0xc4,0xf4,0x2f,0xfa};memcpy(a->ram+0x200,echo,sizeof echo);
 CHECK(apu_enqueuePortWriteAt(a,0,0x5a,ack),"future real SPC input event");
 s_apu_spc_offset=0;s_apu_access_adr=0;s_apu_access_write=false;g_apu_last_sync_master=0;
 g_cpu.A=0x5a;g_cpu.DB=0x80;g_cpu.m_flag=1;g_cpu.x_flag=0;g_cpu.emulation=0;g_cpu._flag_I=1;cpu_mirrors_to_p(&g_cpu);
 g_memsel=1;snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(false);
 snes_set_master_clock_charge_hook(mmio_dma_charge);g_snes_dma_charged=0;
 for(unsigned i=0;i<8;i++)g_test_snes.ram[0x1000+i]=(uint8_t)(0x30+i);
 g_test_snes.ramAdr=0x2000;dma.channel[0].aBank=0x7e;dma.channel[0].aAdr=0x1000;dma.channel[0].bAdr=0x80;dma.channel[0].size=8;
 const uint8_t program[]={0xcd,0x40,0x21,0xd0,0xfb,0xa9,0x01,0x8d,0x0b,0x42,0x80,0xfe};
 memcpy(RAM+0x829000,program,sizeof program);if(!dma_enabled)RAM[0x829006]=0;
 interp_bridge_set_interpret_all(!native);interp_bridge_clear_native_instructions();interp_bridge_clear_native_rdnmi_polls();
 interp_bridge_clear_idle_polls();interp_bridge_reset_dynamic_cache();interp_bridge_set_pre_opcode_hook(0,NULL);
 interp_bridge_set_lle_bounce_exclusions(NULL,0);CHECK(RegisterMmio(),"production generated registration");
 event_count=0;memset(events,0,sizeof events);memset(out,0,sizeof *out);
 uint64_t ni=interp_bridge_native_continuation_insns_total(),nc=interp_bridge_native_continuation_cycles_total();
 uint64_t ii=interp816_insns_total(),ic=interp816_cycles_total(),logical=g_interp_bridge_steps;
 interp_bridge_set_master_deadline(budget);CHECK(interp_bridge_run_until_quiescent(&g_cpu,0x829000)==1,"actual owning bridge deadline");
 interp_bridge_set_master_deadline(0);out->cpu=g_cpu;out->apu=*a;out->apu.spc=NULL;out->apu.dsp=NULL;
 out->spc=*a->spc;out->spc.apu=NULL;out->dsp=*a->dsp;out->dsp.apu_ram=NULL;out->dsp.shadow=NULL;out->dsp.output_filter=NULL;
 out->dma=dma;out->dma.snes=NULL;out->count=event_count;memcpy(out->events,events,event_count*sizeof *events);
 memcpy(out->wram,g_test_snes.ram,sizeof out->wram);out->dma_clocks=g_snes_dma_charged;
 out->ni=interp_bridge_native_continuation_insns_total()-ni;out->nc=interp_bridge_native_continuation_cycles_total()-nc;
 out->ii=interp816_insns_total()-ii;out->ic=interp816_cycles_total()-ic;out->logical=g_interp_bridge_steps-logical;
 out->resume=interp_bridge_lle_resume_pc();apu_free(a);g_test_snes.apu=NULL;
}
static void mmio_pair(unsigned budget,unsigned ack,int dma_enabled){
 mmio_run(&before,0,budget,ack,dma_enabled);mmio_run(&after,1,budget,ack,dma_enabled);++mmio_pairs;
 CHECK(!memcmp(&before.cpu,&after.cpu,sizeof before.cpu),"CPU/master/openbus/owner parity");
 CHECK(!memcmp(&before.apu,&after.apu,sizeof before.apu)&&!memcmp(&before.spc,&after.spc,sizeof before.spc)&&!memcmp(&before.dsp,&after.dsp,sizeof before.dsp),"real complete APU/SPC/DSP plus scheduler parity");
 CHECK(before.count==after.count&&!memcmp(before.events,after.events,before.count*sizeof *events),"ordered actual device bus/access phase parity");
 CHECK(!memcmp(&before.dma,&after.dma,sizeof before.dma)&&!memcmp(before.wram,after.wram,sizeof before.wram)&&before.dma_clocks==after.dma_clocks,"actual DMA payload/channel/clock parity");
 CHECK(before.logical==after.logical&&before.resume==after.resume,"same owning retirement/resume");
 CHECK(!before.ni&&before.ii==after.ii+after.ni&&before.ic==after.ic+after.nc,"native effects not decoder relabelling");
 if(budget>=4000){CHECK(after.apu.outPorts[0]==0x5a,"actual SPC echo acknowledged");
  CHECK(after.ni>0,"actual native device instructions executed");
  CHECK(dma_enabled?after.dma_clocks>0&&after.wram[0x2000]==0x30&&after.wram[0x2007]==0x37:!after.dma_clocks&&after.wram[0x2000]==0,"actual DMA or zero-channel control");}
}
int main(void){
 RAM=malloc(MEMSZ);CHECK(RAM!=NULL,"RAM allocation");
 for(unsigned ack=4;ack<=40;ack+=12){for(unsigned budget=1;budget<=180;budget++)mmio_pair(budget,ack,1);
  mmio_pair(4000,ack,1);mmio_pair(4000,ack,0);}
 printf("mmio_pairs=%u checks=%d failures=%d\n",mmio_pairs,g_check,fixture_fail);free(RAM);return fixture_fail?1:0;
}
'''


def _source(mutant=None):
    source = continuation_source()
    source = source[:source.index('static uint32 code_base;')]
    # Real production implementations replace only the old isolated peripheral stubs.
    for name in ('apu_init','apu_free','apu_reset','apu_cycle','apu_runCycles','apu_saveload',
                 'apu_notePortObserved','snes_catchupApu','rtl_sync_apu_to_cpu_locked',
                 'rtl_sync_apu_for_access_locked','rtl_apu_master_clock','rtl_cpu_master_now'):
        if name in _functions(source): source=source.replace(_c_function(source,name).rstrip(),'')
    for name in ('cpu_read8','cpu_write8'):source=source.replace(_c_function(source,name).rstrip(),'')
    source=source.replace('static CpuState g_c;','')
    source=re.sub(r'\bg_c\b','g_cpu',source)
    audio=(REPO/'tests/runtime_dispatch/apu_port_guest_time_test.c').read_text()
    audio=audio[:audio.index('int main(void)')]
    extra='\n#include "dsp_shadow.h"\nstatic unsigned applied_count;\n'
    known=_functions(source)
    extra+='\n'.join(_c_function(audio,n) for n in sorted(_functions(audio)-known) if n!='check')
    rtl=(REPO/'runner/src/common_rtl.c').read_text()
    clock= CLOCK[:CLOCK.index('void rtl_sync_apu_to_cpu_locked(void){')]
    clock+='\n'.join(_c_function(rtl,n) for n in ('rtl_apu_half_ticks','rtl_apu_spc_cycle','rtl_apu_read_last','rtl_apu_master_sync_locked','rtl_sync_apu_for_access_locked'))
    clock+=CLOCK[CLOCK.index('void rtl_sync_apu_to_cpu_locked(void){'):]
    entries=[dict(pc24=0x829000,m=1,x=0,e=0,bytes=bytes.fromhex('cd4021'),mnemonic='CMP',immediate=False),
             dict(pc24=0x829003,m=1,x=0,e=0,bytes=bytes.fromhex('d0fb'),mnemonic='BNE',immediate=False),
             dict(pc24=0x829007,m=1,x=0,e=0,bytes=bytes.fromhex('8d0b42'),mnemonic='STA',immediate=False)]
    generated,receipt=emit((REPO/'runner/src/snes/interp816.c').read_text(),entries,registration_name='RegisterMmio')
    if mutant=='skip_port':
        original='uint8_t value = cpu->read(cpu->mem, adr);'
        assert original in generated
        generated=generated.replace(original,'uint8_t value = adr == 0x802140 ? 0x5a : cpu->read(cpu->mem, adr);')
    elif mutant=='skip_dma':
        original='cpu->write(cpu->mem, adr, val);'
        assert original in generated
        generated=generated.replace(original,'if (adr != 0x80420b) cpu->write(cpu->mem, adr, val);')
    return source+extra+clock+BUS+generated+MAIN,receipt


@pytest.mark.parametrize('lookup',['0','1'])
@pytest.mark.parametrize('mutant',[None,'skip_port','skip_dma'])
def test_native_mmio_actual_spc_and_dma(tmp_path,lookup,mutant):
    cc=os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    text,receipt=_source(mutant);source=tmp_path/'mmio.c';source.write_text(text,encoding='utf-8')
    exe=tmp_path/('mmio.exe' if os.name=='nt' else 'mmio')
    files=['interp816.c','interp_bridge.c','snes.c','apu.c','spc.c','dsp.c','dsp_clock.c','dma.c','cx4.c','sdd1.c','tier2_capture.c']
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(source),*[str(REPO/'runner/src/snes'/f)for f in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    built=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (tmp_path/'compile.json').write_text(json.dumps(dict(command=command,exit_code=built.returncode,stdout=built.stdout,stderr=built.stderr),indent=2))
    assert built.returncode==0,built.stdout+built.stderr
    env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup)
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60,env=env,cwd=tmp_path)
    (tmp_path/'execution.json').write_text(json.dumps(dict(lookup=lookup,mutant=mutant,emission=receipt,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr),indent=2))
    if mutant:assert run.returncode!=0,run.stdout+run.stderr
    else:assert run.returncode==0,run.stdout+run.stderr
