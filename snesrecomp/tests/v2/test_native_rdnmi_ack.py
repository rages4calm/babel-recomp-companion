"""ROM-free fixed RDNMI acknowledgement effects on real Snes/APU devices.

Only three physical M1X0/E0 descriptors have scheduler scopes. The original
poll island, CPU retirement, device read-clear and interrupt owner stay intact.
"""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
import pytest
from v2.native_effects import emit
from test_native_mmio_continuation import _source as peripheral_source, BUS, REPO

MAIN=r'''
typedef struct {CpuState cpu;Snes snes;Apu apu;Spc spc;Dsp dsp;Dma dma;
 MmioEvent events[8192];unsigned count,hooks,acks;int inNmi_at_read,pending_at_read;uint8_t wram[0x20000],low[0x10000];
 uint64_t ni,nc,ii,ic,logical;uint32_t resume;} AckOutcome;
static AckOutcome ref,native;static unsigned pairs,accepted,nmi_controls,refusals;
static uint32_t ack_pc;static unsigned ack_variant,hook_calls;
static void ack_hook(CpuState *cpu,uint32_t pc){
 (void)cpu;++hook_calls;
 if(ack_variant==5)RAM[pc+1]=0x11;
 if(ack_variant==12)interp_bridge_pre_opcode_redirect(0x839100);
}
static void run_ack(AckOutcome *out,int is_native,uint32_t pc,unsigned deadline,
                    unsigned edge,int beam,int fast,unsigned variant,int nmi){
 memset(RAM,0,MEMSZ);init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);memset(&g_test_cart,0,sizeof g_test_cart);
 static Dma dma;memset(&dma,0,sizeof dma);dma.snes=&g_test_snes;
 g_test_snes.dma=&dma;g_test_snes.ram=RAM+0x7e0000;g_test_snes.cart=&g_test_cart;g_test_snes.hdmaBeamOff=true;
 g_test_cart.type=CART_HIROM;g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
 g_test_snes.apu=apu_init();CHECK(g_test_snes.apu!=NULL,"real APU allocation");apu_reset(g_test_snes.apu);
 Apu *a=g_test_snes.apu;a->romReadable=false;a->spc->pc=0x200;a->cpuCyclesLeft=0;
 const uint8_t echo[]={0xe4,0xf4,0xc4,0xf4,0x2f,0xfa};memcpy(a->ram+0x200,echo,sizeof echo);
 CHECK(apu_enqueuePortWriteAt(a,0,0x5a,40),"queued real SPC input");
 s_apu_spc_offset=0;s_apu_access_adr=0;s_apu_access_write=false;g_apu_last_sync_master=0;
 g_cpu.A=0xaa55;g_cpu.DB=0x7f;g_cpu.D=0x120;g_cpu.m_flag=1;g_cpu.x_flag=0;g_cpu.emulation=0;g_cpu._flag_I=1;cpu_mirrors_to_p(&g_cpu);
 g_memsel=fast;snes_set_rdnmi_beam_enabled(beam);snes_set_raster_irq_beam_enabled(false);
 g_test_snes.hPos=0;g_test_snes.vPos=224;g_test_snes.beamMasterLast=0;
 g_test_snes.inNmi=(edge&1)!=0;g_test_snes.rdnmiPending=(edge&2)!=0;g_test_snes.inIrq=true;
 snes_set_master_clock_charge_hook(mmio_dma_charge);g_snes_dma_charged=0;
 interp_bridge_set_interpret_all(!is_native);interp_bridge_clear_native_instructions();interp_bridge_clear_native_rdnmi_polls();
 interp_bridge_clear_idle_polls();interp_bridge_reset_dynamic_cache();interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_set_lle_bounce_exclusions(NULL,0);
 interrupt_scope=0;ack_pc=pc;ack_variant=variant;hook_calls=0;
 CHECK(RegisterAcks(),"production generated exact acknowledgements with scheduler scopes");
 CHECK(interp_bridge_native_nmi_grants()==0&&interp_bridge_native_frame_grants()==0,"ack registration adds no NMI or frame grants");
 const uint8_t code[]={0xaf,0x10,0x42,0x80,0x80,0xfe};memcpy(RAM+pc,code,sizeof code);memcpy(RAM+0x839100,code,sizeof code);
 if(variant==1)interp_bridge_clear_native_instructions();
 if(variant==2){g_cpu.m_flag=0;cpu_mirrors_to_p(&g_cpu);}
 if(variant==3){g_cpu.x_flag=1;cpu_mirrors_to_p(&g_cpu);}
 if(variant==4){g_cpu.emulation=1;g_cpu.x_flag=1;cpu_mirrors_to_p(&g_cpu);}
 if(variant==5||variant==12)interp_bridge_add_pre_opcode_hook(pc,ack_hook);
 if(variant==6)interrupt_scope=1;
 if(variant==7)g_test_cart.type=CART_SA1;
 if(variant==8)interp_bridge_set_lle_bounce_exclusions(&pc,1);
 if(variant==9)g_test_cart.rom=NULL;
 if(variant==10){pc=(pc&0xffffu)|0xc20000;memcpy(RAM+pc,code,sizeof code);}
 if(variant==11)g_test_cart.romSize=1;
 if(nmi){
  RAM[pc+4]=0x40;const uint8_t jump[]={0x5c,(uint8_t)pc,(uint8_t)(pc>>8),(uint8_t)(pc>>16)};
  memcpy(RAM+0x829100,jump,sizeof jump);cpu_push_interrupt_frame_at(&g_cpu,0x839000);
 }
 event_count=ack_reads=0;ack_inNmi_at_read=ack_pending_at_read=-1;memset(events,0,sizeof events);memset(out,0,sizeof *out);
 uint64_t ni=interp_bridge_native_continuation_insns_total(),nc=interp_bridge_native_continuation_cycles_total();
 uint64_t ii=interp816_insns_total(),ic=interp816_cycles_total(),logical=g_interp_bridge_steps;
 interp_bridge_set_master_deadline(nmi?0:deadline);
 int ok=nmi?(nmi==2?interp_bridge_run_native_nmi(&g_cpu,0x829100):interp_bridge_run_interrupt(&g_cpu,0x829100)):interp_bridge_run_until_quiescent(&g_cpu,pc);
 CHECK(ok==1,"same actual owning bridge completes bounded execution");interp_bridge_set_master_deadline(0);
 out->cpu=g_cpu;out->snes=g_test_snes;out->snes.cpu=NULL;out->snes.apu=NULL;out->snes.ppu=NULL;out->snes.dma=NULL;out->snes.cart=NULL;out->snes.ram=NULL;
 out->apu=*a;out->apu.spc=NULL;out->apu.dsp=NULL;out->spc=*a->spc;out->spc.apu=NULL;out->dsp=*a->dsp;out->dsp.apu_ram=NULL;out->dsp.shadow=NULL;out->dsp.output_filter=NULL;
 out->dma=dma;out->dma.snes=NULL;out->count=event_count;out->hooks=hook_calls;out->acks=ack_reads;out->inNmi_at_read=ack_inNmi_at_read;out->pending_at_read=ack_pending_at_read;memcpy(out->events,events,event_count*sizeof *events);
 memcpy(out->wram,g_test_snes.ram,sizeof out->wram);memcpy(out->low,RAM,sizeof out->low);
 out->ni=interp_bridge_native_continuation_insns_total()-ni;out->nc=interp_bridge_native_continuation_cycles_total()-nc;
 out->ii=interp816_insns_total()-ii;out->ic=interp816_cycles_total()-ic;out->logical=g_interp_bridge_steps-logical;out->resume=interp_bridge_lle_resume_pc();
 apu_free(a);g_test_snes.apu=NULL;interrupt_scope=0;
}
static void pair_ack(uint32_t pc,unsigned deadline,unsigned edge,int beam,int fast,unsigned variant,int nmi){
 run_ack(&ref,0,pc,deadline,edge,beam,fast,variant,nmi);run_ack(&native,1,pc,deadline,edge,beam,fast,variant,nmi);++pairs;
 CHECK(!memcmp(&ref.cpu,&native.cpu,sizeof ref.cpu),"full CPU/openbus/master/stack parity");
 CHECK(!memcmp(&ref.snes,&native.snes,sizeof ref.snes),"full real Snes NMI/IRQ/readclear parity");
 CHECK(!memcmp(&ref.apu,&native.apu,sizeof ref.apu)&&!memcmp(&ref.spc,&native.spc,sizeof ref.spc)&&!memcmp(&ref.dsp,&native.dsp,sizeof ref.dsp),"complete actual APU/SPC/DSP timeline parity");
 CHECK(!memcmp(&ref.dma,&native.dma,sizeof ref.dma)&&!memcmp(ref.wram,native.wram,sizeof ref.wram)&&!memcmp(ref.low,native.low,sizeof ref.low),"full DMA/WRAM/low-memory stack parity");
 CHECK(ref.count==native.count&&!memcmp(ref.events,native.events,ref.count*sizeof *ref.events),"every bus address/value/order/master/accesslead/dataIPC");
 CHECK(ref.logical==native.logical&&ref.resume==native.resume&&ref.hooks==native.hooks,"same retirement/resume/prehook effects");
 CHECK(ref.acks==native.acks&&ref.inNmi_at_read==native.inNmi_at_read&&ref.pending_at_read==native.pending_at_read,"immediate post-read latch state parity");
 CHECK(ref.ni==0&&ref.ii==native.ii+native.ni&&ref.ic==native.ic+native.nc,"native work exactly replaces interpreted work");
 if(variant||nmi){CHECK(native.ni==0,"wrong shape/mode/mapper/owner/exclusion/refusal remains interpreted");++refusals;}
 else{CHECK(native.ni==1&&native.nc==5,"one actual native LDA with original five cycles");++accepted;}
 if(!variant&&!nmi&&deadline==2200){
  unsigned expected=2|(((edge&1)||(beam&&(edge&2)))?0x80:0);
  CHECK(native.cpu.A==(0xaa00|expected),"literal CPU-version/latch value in A.low with A.high preserved");
  CHECK(native.acks==1&&!native.inNmi_at_read&&!native.pending_at_read,"both actual NMI latches consumed at the architectural read");
  /* A later beam edge may relatch RDNMI while the bounded trailing branch
   * retires. Full final Snes parity above includes that new edge. */
  if(!beam)CHECK(!native.snes.inNmi&&!native.snes.rdnmiPending,"no new host-driven NMI edge invented");
  CHECK(native.snes.inIrq,"RDNMI does not acknowledge TIMEUP");
  unsigned reads=0;for(unsigned i=0;i<native.count;i++)if(native.events[i].adr==0x804210){++reads;CHECK(native.events[i].value==expected&&!native.events[i].write,"exact acknowledged byte from authoritative bus");}
  CHECK(reads==1,"one architectural RDNMI read, no skipped or duplicated read");
 }
 if(nmi){CHECK(native.cpu.S==0x1ff,"real pushed interrupt frame restored by RTI");++nmi_controls;}
}
int main(void){
 RAM=malloc(MEMSZ);CHECK(RAM!=NULL,"RAM allocation");const uint32_t sites[]={0x828049,0x828053,0x828195};
 for(unsigned p=0;p<3;p++){
  for(int fast=0;fast<2;fast++)for(unsigned edge=0;edge<4;edge++)for(int beam=0;beam<2;beam++){
   for(unsigned deadline=1;deadline<=48;deadline++)pair_ack(sites[p],deadline,edge,beam,fast,0,0);
   pair_ack(sites[p],2200,edge,beam,fast,0,0);
  }
  for(unsigned variant=1;variant<=12;variant++)pair_ack(sites[p],2200,1,0,1,variant,0);
  for(int nmi=1;nmi<=2;nmi++)pair_ack(sites[p],2200,1,0,1,0,nmi);
 }
 printf("ack_pairs=%u accepted=%u refusals=%u nmi_controls=%u checks=%d failures=%d\n",pairs,accepted,refusals,nmi_controls,g_check,fixture_fail);free(RAM);return fixture_fail?1:0;
}
'''

def _source(outlined,mutant):
    source=peripheral_source()[0].split(BUS)[0]
    entries=[dict(pc24=pc,m=1,x=0,e=0,bytes=bytes.fromhex('af104280'),mnemonic='LDA',immediate=False)for pc in (0x828049,0x828053,0x828195)]
    generated,receipt=emit((REPO/'runner/src/snes/interp816.c').read_text(),entries,registration_name='RegisterAcks',scope_limits=[((e['pc24'],1,0,0),1)for e in entries],outline_effects=outlined)
    if mutant:
        needle='uint8_t value = cpu->read(cpu->mem, adr);'
        assert needle in generated
        generated=generated.replace(needle,'uint8_t value = adr == 0x804210u ? 2 : cpu->read(cpu->mem, adr);')
    bus=BUS.replace('value=snes_read(g_snes,adr);','{value=snes_read(g_snes,adr);if(adr==0x804210u){++ack_reads;ack_inNmi_at_read=g_snes->inNmi;ack_pending_at_read=g_snes->rdnmiPending;}}')
    assert bus!=BUS
    observation='static unsigned ack_reads;static int ack_inNmi_at_read,ack_pending_at_read;\n'
    return source+observation+bus+generated+MAIN,receipt

@pytest.mark.parametrize('lookup',['0','1'])
@pytest.mark.parametrize('outlined',[False,True])
@pytest.mark.parametrize('mutant',[False,True])
def test_rdnmi_ack_actual_devices_and_owners(tmp_path,lookup,outlined,mutant):
    cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    text,receipt=_source(outlined,mutant);source=tmp_path/'ack.c';source.write_text(text)
    exe=tmp_path/('ack.exe'if os.name=='nt'else'ack')
    files=['interp816.c','interp_bridge.c','snes.c','apu.c','spc.c','dsp.c','dsp_clock.c','dma.c','cx4.c','sdd1.c','tier2_capture.c']
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(source),*[str(REPO/'runner/src/snes'/f)for f in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    built=subprocess.run(command,capture_output=True,text=True,timeout=90);(tmp_path/'compile.json').write_text(json.dumps(dict(command=command,exit_code=built.returncode,stdout=built.stdout,stderr=built.stderr),indent=2));assert built.returncode==0,built.stdout+built.stderr
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=90,env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup),cwd=tmp_path)
    (tmp_path/'execution.json').write_text(json.dumps(dict(lookup=lookup,outlined=outlined,mutant=mutant,emission=receipt,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr),indent=2))
    if mutant:assert run.returncode!=0 and 'failures=0'not in run.stdout,run.stdout+run.stderr
    else:assert run.returncode==0,run.stdout+run.stderr
