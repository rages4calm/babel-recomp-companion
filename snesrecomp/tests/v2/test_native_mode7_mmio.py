"""ROM-free M0 Mode7 division-register words on real Snes/APU/IRQ core.

Device semantics are production snes.c; host bus routing is the established
MMIO fixture. Word-leaf instrumentation observes claims that bypass byte hooks.
No ROM, game assets, renderer or hardware timing claim is involved.
"""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
import pytest
from v2.native_effects import emit
from test_native_mmio_continuation import _source as peripheral_source, BUS, REPO
from test_region_pacing import _c_function

WORD_BUS=r'''
int mode7_force_scalar;
static unsigned word_reads,word_writes;
uint16 cpu_read16(CpuState *cpu,uint8 bank,uint16 addr){
 ++word_reads;uint32_t p=((uint32_t)bank<<16)|addr;
 uint8_t lo=snes_read(g_snes,p);mmio_note(cpu,p,lo,0);cpu->open_bus=lo;
 uint8_t hi=snes_read(g_snes,p+1);mmio_note(cpu,p+1,hi,0);cpu->open_bus=hi;
 return lo|((uint16_t)hi<<8);
}
void cpu_write16(CpuState *cpu,uint8 bank,uint16 addr,uint16 value){
 ++word_writes;uint32_t p=((uint32_t)bank<<16)|addr;
 mmio_note(cpu,p,(uint8_t)value,1);snes_write(g_snes,p,(uint8_t)value);
 mmio_note(cpu,p+1,(uint8_t)(value>>8),1);snes_write(g_snes,p+1,(uint8_t)(value>>8));cpu->open_bus=(uint8_t)value;
}
'''

MAIN=r'''
typedef struct {CpuState cpu;Snes snes;Apu apu;Spc spc;Dsp dsp;Dma dma;
 MmioEvent events[8192];unsigned count,wr,ww;uint8_t ram[0x20000];
 uint64_t ni,nc,ii,ic,logical;uint32_t resume;} WordOutcome;
static WordOutcome ref,native;static unsigned pairs,full_claims,scalar_controls,irq_controls;
static void run_word(WordOutcome *out,int is_native,unsigned deadline,int scalar,unsigned divisor,unsigned timer_hi){
 memset(RAM,0,MEMSZ);init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);memset(&g_test_cart,0,sizeof g_test_cart);
 static Dma dma;memset(&dma,0,sizeof dma);dma.snes=&g_test_snes;g_test_snes.dma=&dma;
 g_test_snes.ram=RAM+0x7e0000;g_test_snes.cart=&g_test_cart;g_test_snes.hdmaBeamOff=true;
 g_test_cart.type=CART_HIROM;g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
 g_test_snes.apu=apu_init();CHECK(g_test_snes.apu!=NULL,"real APU allocation");apu_reset(g_test_snes.apu);
 Apu *a=g_test_snes.apu;a->romReadable=false;a->spc->pc=0x200;a->cpuCyclesLeft=0;
 const uint8_t echo[]={0xe4,0xf4,0xc4,0xf4,0x2f,0xfa};memcpy(a->ram+0x200,echo,sizeof echo);
 CHECK(apu_enqueuePortWriteAt(a,0,0x5a,40),"future actual SPC input event");
 s_apu_spc_offset=0;s_apu_access_adr=0;s_apu_access_write=false;g_apu_last_sync_master=0;
 g_cpu.A=0x1234;g_cpu.Y=(0x20u<<8)|divisor;g_cpu.DB=0x80;g_cpu.m_flag=0;g_cpu.x_flag=0;g_cpu.emulation=0;g_cpu._flag_I=1;cpu_mirrors_to_p(&g_cpu);
 g_memsel=1;snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(true);
 g_test_snes.hPos=0;g_test_snes.vPos=224;g_test_snes.beamMasterLast=0;
 g_test_snes.hIrqEnabled=true;g_test_snes.hTimer=timer_hi?0x1ff:0xff;
 g_test_snes.divideA=0xa5a5;g_test_snes.divideResult=0xdead;g_test_snes.multiplyResult=0xbeef;
 snes_set_master_clock_charge_hook(mmio_dma_charge);g_snes_dma_charged=0;
 const uint8_t program[]={0x8d,0x04,0x42,0x8c,0x06,0x42,0xad,0x14,0x42,0x80,0xfe};memcpy(RAM+0x829000,program,sizeof program);
 mode7_force_scalar=scalar;interp_bridge_set_interpret_all(!is_native);interp_bridge_clear_native_instructions();interp_bridge_clear_native_rdnmi_polls();interp_bridge_clear_idle_polls();interp_bridge_reset_dynamic_cache();interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_set_lle_bounce_exclusions(NULL,0);
 CHECK(RegisterMode7Words(),"exact three production-generated M0 descriptors registered");
 event_count=word_reads=word_writes=0;memset(events,0,sizeof events);memset(out,0,sizeof *out);
 uint64_t ni=interp_bridge_native_continuation_insns_total(),nc=interp_bridge_native_continuation_cycles_total(),ii=interp816_insns_total(),ic=interp816_cycles_total(),logical=g_interp_bridge_steps;
 interp_bridge_set_master_deadline(deadline);CHECK(interp_bridge_run_until_quiescent(&g_cpu,0x829000)==1,"real owning bridge bounded deadline");interp_bridge_set_master_deadline(0);
 out->cpu=g_cpu;out->snes=g_test_snes;out->snes.cpu=NULL;out->snes.apu=NULL;out->snes.ppu=NULL;out->snes.dma=NULL;out->snes.cart=NULL;out->snes.ram=NULL;
 out->apu=*a;out->apu.spc=NULL;out->apu.dsp=NULL;out->spc=*a->spc;out->spc.apu=NULL;out->dsp=*a->dsp;out->dsp.apu_ram=NULL;out->dsp.shadow=NULL;out->dsp.output_filter=NULL;
 out->dma=dma;out->dma.snes=NULL;out->count=event_count;out->wr=word_reads;out->ww=word_writes;memcpy(out->events,events,event_count*sizeof *events);memcpy(out->ram,g_test_snes.ram,sizeof out->ram);
 out->ni=interp_bridge_native_continuation_insns_total()-ni;out->nc=interp_bridge_native_continuation_cycles_total()-nc;out->ii=interp816_insns_total()-ii;out->ic=interp816_cycles_total()-ic;out->logical=g_interp_bridge_steps-logical;out->resume=interp_bridge_lle_resume_pc();apu_free(a);g_test_snes.apu=NULL;
}
static void pair_word(unsigned deadline,int scalar,unsigned divisor,unsigned timer_hi){
 run_word(&ref,0,deadline,scalar,divisor,timer_hi);run_word(&native,1,deadline,scalar,divisor,timer_hi);++pairs;
 CHECK(!memcmp(&ref.cpu,&native.cpu,sizeof ref.cpu),"CPU/register/openbus/master parity");
 CHECK(!memcmp(&ref.snes,&native.snes,sizeof ref.snes),"actual complete Snes divider/comparator/pending beam parity");
 CHECK(!memcmp(&ref.apu,&native.apu,sizeof ref.apu)&&!memcmp(&ref.spc,&native.spc,sizeof ref.spc)&&!memcmp(&ref.dsp,&native.dsp,sizeof ref.dsp),"real complete APU/SPC/DSP/scheduler parity");
 CHECK(!memcmp(&ref.dma,&native.dma,sizeof ref.dma)&&!memcmp(ref.ram,native.ram,sizeof ref.ram),"actual DMA and WRAM unchanged parity");
 CHECK(ref.count==native.count&&!memcmp(ref.events,native.events,ref.count*sizeof *ref.events),"every original bus address/value/order/master/accesslead/dataIPC equal");
 CHECK(ref.wr==native.wr&&ref.ww==native.ww,"real word-leaf claims independently counted");
 CHECK(ref.logical==native.logical&&ref.resume==native.resume,"same retirement/resume");
 CHECK(ref.ni==0&&ref.ii==native.ii+native.ni&&ref.ic==native.ic+native.nc,"native work exactly replaces interpreted work");
 if(deadline==2200){
  uint16_t quotient=divisor?0x1234/divisor:0xffff,remainder=divisor?0x1234%divisor:0x1234;
  CHECK(native.cpu.A==quotient&&native.snes.divideA==0x1234&&native.snes.divideResult==quotient&&native.snes.multiplyResult==remainder,"actual divider result and remainder including zero-divisor control");
  CHECK(native.snes.hTimer==(timer_hi?0x120:0x20),"STY high byte really reaches H-IRQ low register4207");
  CHECK(native.snes.inIrq&&native.snes.dbgIrqLatches>0,"programmed real H-IRQ comparator asserts pending event with I mask");++irq_controls;
  CHECK(native.ni==3,"all three word instructions actually native");
  if(scalar){CHECK(native.wr==0&&native.ww==0,"scalar word refusal takes real byte bus");++scalar_controls;}
  else{CHECK(native.wr==1&&native.ww==2,"claimed4214read and4204/4206writes exercised");++full_claims;}
  MmioEvent actual[6];unsigned count=0;
  for(unsigned j=0;j<native.count;j++)if((native.events[j].adr&0xffffu)>=0x4204&&(native.events[j].adr&0xffffu)<=0x4215){CHECK(count<6,"exact six divider/IRQ accesses");if(count<6)actual[count++]=native.events[j];}
  CHECK(count==6,"six real MMIO bytes visible even when byte callbacks bypassed");
  const uint32_t adr[]={0x804204,0x804205,0x804206,0x804207,0x804214,0x804215};
  const uint8_t value[]={0x34,0x12,(uint8_t)divisor,0x20,(uint8_t)quotient,(uint8_t)(quotient>>8)};
  for(unsigned j=0;j<count&&j<6;j++)CHECK(actual[j].adr==adr[j]&&actual[j].value==value[j]&&actual[j].write==(j<4),"literal word byte order/value device oracle");
 }
}
int main(void){RAM=malloc(MEMSZ);CHECK(RAM!=NULL,"RAM allocation");
 for(unsigned scalar=0;scalar<2;scalar++)for(unsigned zero=0;zero<2;zero++)for(unsigned hi=0;hi<2;hi++){
  for(unsigned deadline=1;deadline<=110;deadline++)pair_word(deadline,scalar,zero?0:0x12,hi);
  pair_word(2200,scalar,zero?0:0x12,hi);
 }
 printf("mode7_word_pairs=%u claimed_controls=%u scalar_controls=%u irq_controls=%u checks=%d failures=%d\n",pairs,full_claims,scalar_controls,irq_controls,g_check,fixture_fail);free(RAM);return fixture_fail?1:0;}
'''

def _source(outlined,mutant):
    source=peripheral_source()[0].split(BUS)[0]
    for name in ('cpu_read16','cpu_write16'):
        source=source.replace(_c_function(source,name).rstrip(),'')
    entries=[dict(pc24=0x829000,m=0,x=0,e=0,bytes=bytes.fromhex('8d0442'),mnemonic='STA',immediate=False),dict(pc24=0x829003,m=0,x=0,e=0,bytes=bytes.fromhex('8c0642'),mnemonic='STY',immediate=False),dict(pc24=0x829006,m=0,x=0,e=0,bytes=bytes.fromhex('ad1442'),mnemonic='LDA',immediate=False)]
    generated,receipt=emit((REPO/'runner/src/snes/interp816.c').read_text(),entries,registration_name='RegisterMode7Words',outline_effects=outlined)
    if mutant:
        needle='cpu->write_word(cpu->mem, adrl, adrh, value, reversed)'
        assert needle in generated
        generated=generated.replace(needle,'cpu->write_word(cpu->mem, adrl, adrh, value & 0xffu, reversed)')
    return source+BUS+WORD_BUS+generated+MAIN,receipt

@pytest.mark.parametrize('lookup',['0','1'])
@pytest.mark.parametrize('outlined',[False,True])
@pytest.mark.parametrize('mutant',[False,True])
def test_mode7_real_divider_claimed_words(tmp_path,lookup,outlined,mutant):
    cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    text,receipt=_source(outlined,mutant);source=tmp_path/'mode7.c';source.write_text(text)
    # Private diagnostic selector changes only claim eligibility, not device/clock logic.
    bridge=(REPO/'runner/src/snes/interp_bridge.c').read_text();needle='static int bridge_hw_word(uint32_t adrl, uint32_t adrh) {';assert needle in bridge
    bridge=bridge.replace(needle,needle+'\n    extern int mode7_force_scalar; if(mode7_force_scalar)return 0;')
    private_bridge=tmp_path/'interp_bridge.c';private_bridge.write_text(bridge)
    exe=tmp_path/('mode7.exe'if os.name=='nt'else'mode7')
    files=['interp816.c','snes.c','apu.c','spc.c','dsp.c','dsp_clock.c','dma.c','cx4.c','sdd1.c','tier2_capture.c']
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(source),str(private_bridge),*[str(REPO/'runner/src/snes'/f)for f in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    built=subprocess.run(command,capture_output=True,text=True,timeout=90);(tmp_path/'compile.json').write_text(json.dumps(dict(command=command,exit_code=built.returncode,stdout=built.stdout,stderr=built.stderr),indent=2));assert built.returncode==0,built.stdout+built.stderr
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60,env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup),cwd=tmp_path)
    (tmp_path/'execution.json').write_text(json.dumps(dict(lookup=lookup,outlined=outlined,mutant=mutant,emission=receipt,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),private_claim_selector_sha256=hashlib.sha256(private_bridge.read_bytes()).hexdigest(),exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr),indent=2))
    if mutant:assert run.returncode!=0 and 'failures=0'not in run.stdout,run.stdout+run.stderr
    else:assert run.returncode==0,run.stdout+run.stderr
