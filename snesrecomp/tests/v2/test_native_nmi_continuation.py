"""Explicit finite NMI data continuations: actual bridge, SPC and WRAM DMA.

All guest bytes are synthetic. The reference owner still pushes/pops every
architectural/COP/subroutine frame and retires every instruction/device event.
"""
import hashlib,json,os,re,shutil,subprocess
import pytest
import snes65816 as decoder
from v2.native_effects import emit
from test_native_cop_continuation import _source as cop_source,_program as cop_program,REPO
from test_region_pacing import _c_function


SUPPORT=r'''
static unsigned nmi_variant,nmi_fault,nmi_held,nmi_hook_calls;
static int nmi_decline(Interp816 *in){(void)in;return 0;}
static void nmi_forbidden_grants(void){
 static const uint8_t ops[]={8,0x28,0x48,0x68,0xda,0xfa,0x5a,0x7a,0x0b,0x2b,0x8b,0xab,0x4b,0xf4,0x62,0xd4,0x20,0x22,0x60,0x6b,0x7c,2,0x40,0x1b,0x9a,0xfb,0x44,0x54};
 static const uint8_t lengths[]={1,1,1,1,1,1,1,1,1,1,1,1,1,3,3,2,3,4,1,1,3,2,1,1,1,1,3,3};
 for(unsigned i=0;i<sizeof ops;i++){
  InterpNativeInstruction d=ni_entries[0];d.pc24=0x839000+i*4;d.length=lengths[i];memset(d.bytes,0,4);d.bytes[0]=ops[i];
  (void)interp_bridge_add_native_instructions(&d,1);
  CHECK(!interp_bridge_allow_native_nmi_instructions(0x8500,&d,1)&&!interp_bridge_native_nmi_grants(),"stack/control/SP/emulation/block effects cannot acquire finite NMI grant");
 }
}
static void nmi_active_hook(CpuState *cpu,uint32_t pc){
 (void)cpu;(void)pc;if(nmi_hook_calls++)return;
 size_t count=interp_bridge_native_instruction_stats(NULL,0),grants=interp_bridge_native_nmi_grants();
 CHECK(!interp_bridge_allow_native_nmi_instructions(0x8500,ni_entries,1),"active owner cannot grant");
 CHECK(!interp_bridge_add_native_instructions(ni_entries,1),"active owner cannot replace callbacks");
 interp_bridge_clear_native_instructions();
 CHECK(count==interp_bridge_native_instruction_stats(NULL,0)&&grants==interp_bridge_native_nmi_grants(),"active clear preserves descriptors/grants");
 /* Re-enter the SAME granted vector, with a short synthetic body. The
  * outer core already passed its trampoline, so restore it after the nested
  * return. An active owner must not lend its grant to the nested core. */
 uint8_t saved[3];memcpy(saved,RAM+0x8501,3);
 RAM[0x8501]=0;RAM[0x8502]=0x86;RAM[0x8503]=0;
 uint16_t sp=cpu->S;uint64_t ni=interp_bridge_native_continuation_insns_total();
 cpu_push_interrupt_frame_at(cpu,pc);
 CHECK(interp_bridge_run_native_nmi(cpu,0x8500)==1,"nested same-vector NMI returns through original frame");
 CHECK(cpu->S==sp&&interp_bridge_native_continuation_insns_total()==ni,"same-vector nested owner cannot inherit grant");
 memcpy(RAM+0x8501,saved,3);
}
static int nmi_enter(CpuState *cpu){
 /* Identical host-entry provenance before the architectural frame push;
  * native guest accesses below still retain their real write IPC. */
 g_interp816_cur_pc=0;
 uint16_t original_s=cpu->S;cpu_push_interrupt_frame_at(cpu,0x828123);
 g_test_snes.inNmi=g_test_snes.rdnmiPending=g_test_snes.nmiEnabled=nmi_variant!=2;
 g_test_snes.inIrq=nmi_variant==2;
 int result=nmi_variant==1?interp_bridge_run_interrupt(cpu,0x8500):interp_bridge_run_native_nmi(cpu,0x8500);
 CHECK(cpu->S==original_s&&cpu->PB==0x82,"finite RTI alone consumes original four-byte frame");
 return result;
}
'''
PAIR=r'''
static void mmio_pair(unsigned budget,unsigned mode,int dma_enabled){
 uint64_t refni=interp_bridge_native_nmi_insns_total(),refnc=interp_bridge_native_nmi_cycles_total();
 mmio_run(&before,0,budget,mode,dma_enabled);
 CHECK(interp_bridge_native_nmi_insns_total()==refni&&interp_bridge_native_nmi_cycles_total()==refnc,"forced reference has zero NMI subset credit");
 uint64_t ni=interp_bridge_native_nmi_insns_total(),nc=interp_bridge_native_nmi_cycles_total();
 mmio_run(&after,1,budget,mode,dma_enabled);++mmio_pairs;
 CHECK(!memcmp(&before.cpu,&after.cpu,sizeof before.cpu),"full NMI CPU/flags/width/stack/openbus/clocks exact");
 CHECK(!memcmp(&before.snes,&after.snes,sizeof before.snes),"real NMI acknowledgment/beam/math state exact");
 CHECK(!memcmp(&before.apu,&after.apu,sizeof before.apu)&&!memcmp(&before.spc,&after.spc,sizeof before.spc)&&!memcmp(&before.dsp,&after.dsp,sizeof before.dsp),"complete real APU/SPC/DSP/scheduler exact");
 CHECK(before.count==after.count&&!memcmp(before.events,after.events,before.count*sizeof *events),"all ordered opcode/frame/device accesses and access leads exact");
 CHECK(!memcmp(&before.dma,&after.dma,sizeof before.dma)&&!memcmp(before.wram,after.wram,sizeof before.wram)&&before.dma_clocks==after.dma_clocks,"real DMA payload/channel/clock and full WRAM/frame exact");
 CHECK(before.logical==after.logical&&before.resume==after.resume,"same original retirement/resume");
 CHECK(!before.ni&&before.ii==after.ii+after.ni&&before.ic==after.ic+after.nc,"native NMI effects never decoded/relabelled");
 CHECK(after.cpu.S==0x1ff&&after.cpu.m_flag==((mode>>1)&1)&&after.cpu.x_flag==(mode&1),"original RTI restores original owner widths/S");
 CHECK(!after.snes.inNmi,"actual4210 read clears NMI while native grant remains latched");
 CHECK(after.apu.outPorts[0]==0x5a,"real SPC echo observed");
 CHECK(dma_enabled?after.dma_clocks>0&&after.wram[0x2000]==0x30&&after.wram[0x2007]==0x37:!after.dma_clocks&&after.wram[0x2000]==0,"real DMA or zero-channel negative");
 CHECK(after.wram[0x310]==2&&after.wram[0x306]==2,"nested real guest COP/RTI and JSR/RTS complete inside finite NMI");
 CHECK(after.wram[0x340]==1,"registered nested same-vector helper actually executed through fallback");
 if(nmi_variant){CHECK(!after.ni&&interp_bridge_native_nmi_insns_total()==ni&&interp_bridge_native_nmi_cycles_total()==nc,"legacy/IRQ/wrong-vector scopes keep reference fallback");}
 else {CHECK(after.ni>0&&interp_bridge_native_nmi_insns_total()-ni==after.ni&&interp_bridge_native_nmi_cycles_total()-nc==after.nc,"NMI counters are exact subset of continuation work");}
}
'''


def _source(mutant=None):
    text,_=cop_source();old,entries=cop_program();entries=[r for r in entries if r['pc24']!=0x8500]
    code=bytearray();m=x=0;dma_operand=None
    excluded={0x08,0x28,0x48,0x68,0xda,0xfa,0x5a,0x7a,0x0b,0x2b,0x8b,0xab,0x02,0x40,0x20,0x60}
    for raw in ('08','c230','48','da','5a','0b','8b','e220','ad1042','a95a','cd4021','d0fb','a901','8d0b42','c230','0200','ab','2b','7a','fa','68','28','40'):
        raw=bytes.fromhex(raw);pc=0x829000+len(code);name,mode,size=decoder.opcode_table()[raw[0]]
        if raw==bytes.fromhex('a901'):dma_operand=pc+1
        if raw[0]not in excluded:
            for a,b in ([(a,b)for a in range(2)for b in range(2)]if pc==0x829001 else[(m,x)]):
                entries.append(dict(pc24=pc,m=a,x=b,e=0,bytes=raw,mnemonic=name,immediate=mode==decoder.IMM))
        code.extend(raw)
        if raw[0]==0xc2:
            if raw[1]&0x20:m=0
            if raw[1]&0x10:x=0
        elif raw[0]==0xe2:
            if raw[1]&0x20:m=1
            if raw[1]&0x10:x=1
    for m in range(2):
        for x in range(2):
            entries.append(dict(pc24=0x8600,m=m,x=x,e=0,bytes=bytes.fromhex('ee4003'),mnemonic='INC',immediate=False))
    nmi_kwargs = dict(nmi_owner_pc24=0x8500,nmi_keys=[(e['pc24'],e['m'],e['x'],e['e'])for e in entries]) if mutant=='production_grant' else {}
    generated,receipt=emit((REPO/'runner/src/snes/interp816.c').read_text(),entries,registration_name='RegisterMmio',**nmi_kwargs)
    assert not re.search(r'\b(?:interp816_|ni_\w+_)(?:runOpcode|doOpcode)\s*\(',generated)
    if mutant=='skip_port':generated=generated.replace('uint8_t value = cpu->read(cpu->mem, adr);','uint8_t value = adr==0x802140?0x5a:cpu->read(cpu->mem, adr);')
    if mutant=='skip_dma':generated=generated.replace('cpu->write(cpu->mem, adr, val);','if(adr!=0x80420b)cpu->write(cpu->mem, adr, val);')
    if mutant=='relabel':
        start=generated.index('static int ni_at_829001_00(');end=generated.index('\n}',start)+2
        generated=generated[:start]+'static int ni_at_829001_00(Interp816 *cpu){return interp816_runOpcode(cpu); }'+generated[end:]
    begin=text.index('/* PRIVATE ROM-derived continuations;');end=text.index('static unsigned cop_fault,',begin)
    text=text[:begin]+generated+SUPPORT+text[end:]
    start=text.index(' const uint8_t maincode[]=');end=text.index(' interp_bridge_set_interpret_all',start)
    text=text[:start]+(' const uint8_t handler[]={'+','.join(str(v)for v in code)+'};memcpy(RAM+0x829000,handler,sizeof handler);\n'
      f' if(!dma_enabled)RAM[{dma_operand}]=0;\n'
      ' RAM[0x8500]=0x5c;RAM[0x8501]=0;RAM[0x8502]=0x90;RAM[0x8503]=0x82;\n'
      ' memcpy(RAM+0x8100,cop_code,sizeof cop_code);RAM[0xffe4]=0;RAM[0xffe5]=0x81;\n'
      ' RAM[0x8200]=0xee;RAM[0x8201]=6;RAM[0x8202]=3;RAM[0x8203]=0x60;\n')+text[end:]
    text=text.replace(' interp_bridge_set_interpret_all', ' RAM[0x8600]=0xee;RAM[0x8601]=0x40;RAM[0x8602]=3;RAM[0x8603]=0x40;\n interp_bridge_set_interpret_all')
    start=text.index('    InterpNativeInstruction items[256];');end=text.index(' event_count=0;',start)
    text=text[:start]+r'''
    CHECK(RegisterMmio(),"production-emitted exact finite NMI data registration");
    size_t n=sizeof ni_entries/sizeof *ni_entries;CHECK(n>2,"nonempty bounded cohort");
    InterpNativeInstruction bad[2]={ni_entries[0],ni_entries[1]};bad[1].step=nmi_decline;
    nmi_forbidden_grants();
    CHECK(!interp_bridge_allow_native_nmi_instructions(0x8500,bad,2)&&!interp_bridge_native_nmi_grants(),"late callback mismatch grants nothing");
    bad[1]=ni_entries[1];bad[1].bytes[1]^=1;
    CHECK(!interp_bridge_allow_native_nmi_instructions(0x8500,bad,2)&&!interp_bridge_native_nmi_grants(),"late immutable-byte mismatch grants nothing");
    CHECK(!interp_bridge_allow_native_nmi_instructions(0x7e8500,ni_entries,n)&&!interp_bridge_native_nmi_grants(),"WRAM owner refused");
    CHECK(interp_bridge_allow_native_nmi_instructions(nmi_variant==3?0x8501:0x8500,ni_entries,n),"explicit exact-owner data grant");
    CHECK(interp_bridge_native_nmi_grants()==n,"every exact descriptor granted once");
    CHECK(!interp_bridge_allow_native_nmi_instructions(0x8502,ni_entries,n)&&interp_bridge_native_nmi_grants()==n,"conflicting owner refuses entire update");
    CHECK(RegisterMmio()&&interp_bridge_native_nmi_grants()==n,"idempotent registry rebuild preserves grants");
    nmi_hook_calls=0;interp_bridge_add_pre_opcode_hook(0x829000,nmi_active_hook);
'''+text[end:]
    if mutant=='production_grant':
        a=text.index('    InterpNativeInstruction bad[2]');b=text.index('    nmi_hook_calls=0;',a)
        text=text[:a]+' CHECK(interp_bridge_native_nmi_grants()==n,"production emitter optional NMI grant actually registered");\n'+text[b:]
    text=text.replace('g_cpu.m_flag=(ack>>1)&1;g_cpu.x_flag=ack&1;','g_cpu.m_flag=(ack>>1)&1;g_cpu.x_flag=ack&1;')
    text=text.replace('CHECK(interp_bridge_run_until_quiescent(&g_cpu,0x829000)==1,"actual owning bridge deadline");','CHECK(nmi_enter(&g_cpu)==1,"finite NMI ignores scheduler deadline and reaches original RTI");')
    text=text.replace(_c_function(text,'mmio_pair').rstrip(),PAIR)
    text=text[:text.index('int main(int argc,char **argv){')]+r'''
int main(int argc,char **argv){RAM=malloc(MEMSZ);if(!RAM)return 2;nmi_variant=argc>1?atoi(argv[1]):0;
 for(unsigned mode=0;mode<4;mode++)for(unsigned dma=0;dma<2;dma++){
  for(unsigned budget=1;budget<200;budget+=19)mmio_pair(budget,mode,dma);mmio_pair(8000,mode,dma);
 }
 printf("nmi_pairs=%u checks=%d failures=%d\n",mmio_pairs,g_check,fixture_fail);free(RAM);return fixture_fail?1:0;}
'''
    return text,receipt


@pytest.fixture(scope='module',params=[None,'relabel','skip_port','skip_dma','production_grant'])
def nmi_binary(tmp_path_factory,request):
    out=tmp_path_factory.mktemp('native-nmi-'+str(request.param));cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    source,receipt=_source(request.param);src=out/'nmi.c';src.write_text(source,encoding='utf-8');(out/'emission.json').write_text(json.dumps(receipt,indent=2))
    exe=out/('nmi.exe'if os.name=='nt'else'nmi');files=['interp816.c','interp_bridge.c','snes.c','apu.c','spc.c','dsp.c','dsp_clock.c','dma.c','cx4.c','sdd1.c','tier2_capture.c']
    cmd=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(src),*[str(REPO/'runner/src/snes'/f)for f in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=90);(out/'compile.json').write_text(json.dumps(dict(command=cmd,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2));assert p.returncode==0,p.stdout+p.stderr
    return out,exe,request.param


@pytest.mark.parametrize('lookup',['0','1'])
def test_exact_finite_nmi_owner_real_devices_and_fallback(nmi_binary,lookup):
    out,exe,mutant=nmi_binary
    fault=mutant in ('relabel','skip_port','skip_dma')
    for variant in([0]if mutant else range(4)):
        p=subprocess.run([str(exe),str(variant)],capture_output=True,text=True,timeout=45,cwd=out,env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup))
        (out/f'run-{lookup}-{variant}.json').write_text(json.dumps(dict(exit_code=p.returncode,lookup=lookup,variant=variant,mutant=mutant,stdout=p.stdout,stderr=p.stderr),indent=2))
        if fault:assert p.returncode==1 and'FAIL:'in p.stdout,p.stdout+p.stderr
        else:assert p.returncode==0,p.stdout+p.stderr
