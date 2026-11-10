"""ROM-free COP data/frame ABI under the original owning retirement loop.

The synthetic dispatcher reads the actual COP-pushed PB/PC, resolves a live
signature table, changes a real saved return PC, balances saved registers,
and deliberately disposes a COP frame before RTL. COP/RTI/indirect JMP stay
interpreted. Production-emitted effects and real math/APU devices are used.
"""
import json,os,re,shutil,subprocess
import pytest
import snes65816 as decoder
from v2.native_effects import emit
from test_native_cop_continuation import _source as cop_source,_program as cop_program,REPO
from test_region_pacing import _c_function


def _programs():
    segments={};entries=[]
    def add(pc,code,modes=None):
        code=bytes.fromhex(code)if isinstance(code,str)else code
        name,mode,size=decoder.opcode_table()[code[0]]
        if code[0]not in(0x02,0x40,0x7c,0xdb):
            for m,x in modes or[(m,x)for m in range(2)for x in range(2)]:
                length=size(m,x)if callable(size)else size
                if length==len(code):entries.append(dict(pc24=pc,m=m,x=x,e=0,bytes=code,mnemonic=name,immediate=mode==decoder.IMM))
        return code
    # Synthetic addresses/table, with the real native COP-frame offsets.
    dispatch=bytearray()
    for code in('c220','9b','a304','850c','a302','3a','850a','a70a','e60a','29ff00','0a','aa','7c8080'):
        dispatch.extend(add(0x8000+len(dispatch),code))
    segments[0x8000]=bytes(dispatch);segments[0x8080]=bytes.fromhex('008100840083')
    # Temporary PHP/PHX shift the actual COP PB and PC by three bytes.
    # Only the outer nonzero-PB caller skips the following synthetic STP.
    prefix=bytearray()
    for code in('08','c230','da',
                '48','68','5a','7a','0b','2b','8b','4b','ab','ab',
                'f43412','68','620000','68','d420','68',
                'e220','48','68','c220','e210','da','fa','5a','7a','c210',
                'a307','29ff00','f005','a305','1a','8305','fa','28'):
        prefix.extend(add(0x8100+len(prefix),code))
    old,old_entries=cop_program();segments[0x8100]=bytes(prefix)+old
    for row in old_entries:
        if row['pc24']==0x8500:continue
        if 0x8100<=row['pc24']<0x8200:row=dict(row,pc24=row['pc24']+len(prefix))
        entries.append(row)
    # Previously omitted saved-status and helper call/return instructions.
    pc=0x8100+len(prefix);m=x=1
    while pc<0x8100+len(prefix)+len(old):
        at=pc-(0x8100+len(prefix));op=old[at];name,mode,size=decoder.opcode_table()[op]
        n=size(m,x)if callable(size)else size;raw=old[at:at+n]
        if op in(0x08,0x28,0x20,0x60):add(pc,raw)
        if op==0xc2:
            if raw[1]&0x20:m=0
            if raw[1]&0x10:x=0
        if op==0xe2:
            if raw[1]&0x20:m=1
            if raw[1]&0x10:x=1
        pc+=n
    segments[0x8200]=add(0x8200,'ee0603')+add(0x8203,'60')
    segments[0x8300]=b''.join(add(0x8300+offset,code)for offset,code in[(0,'08'),(1,'c230'),(3,'ee1203'),(6,'28'),(7,'40')])
    # Four-byte native COP frame is discarded by two M0 PLA effects; the
    # subsequent real RTL consumes its surrounding JSL's three-byte frame.
    segments[0x8400]=b''.join(add(0x8400+offset,code)for offset,code in[(0,'c230'),(2,'68'),(3,'68'),(4,'6b')])
    segments[0x8500]=bytes.fromhex('08e220ad1142c230ee200302022840')
    for offset,raw in[(0,'08'),(1,'e220'),(3,'ad1142'),(6,'c230'),(8,'ee2003'),(13,'28')]:add(0x8500+offset,raw)
    segments[0x838600]=bytes.fromhex('0201db')
    # Register both source variants only where bytes agree; the unused main
    # JSL and ordinary COP have separate starting PCs.
    for bank in(2,0x42,0x82,0xc2):
        add(bank<<16|0x9003,'80fe')
        add(bank<<16|0x9020,'22008683');add(bank<<16|0x9024,'ee0a03');add(bank<<16|0x9027,'80fe')
    unique={}
    for row in entries:
        k=row['pc24'],row['m'],row['x'],row['e']
        assert k not in unique or unique[k]==row
        unique[k]=row
    return segments,list(unique.values())


SUPPORT=r'''
static unsigned cop_fault,cop_fired,cop_case,cop_bank=0x82,cop_irq_fired,cop_hook,cop_drop_store;
static uint16_t cop_stack=0x1ff;static uint64_t cop_deadline;
static InterpNativeInstructionStep cop_actual[4];
static bool cop_drop_word(void *mem,uint32_t lo,uint32_t hi,uint16_t value,bool reversed){
 (void)mem;(void)lo;(void)hi;(void)value;(void)reversed;return true;
}
static int cop_corrupt(Interp816 *in){
 if(cop_fault==1)return interp816_runOpcode(in);
 Interp816WriteWordHandler word=in->write_word;
 if(cop_fault==3)in->write_word=cop_drop_word;
 cop_drop_store=cop_fault==3;int cycles=cop_actual[(in->mf<<1)|in->xf](in);cop_drop_store=0;in->write_word=word;
 CHECK(cycles>0,"mutant wraps an actually admitted live-mode callback");
 if(cop_fault==2)++in->sp;
 if(cop_fault==4)in->a^=0x80;
 return cycles;
}
static void cop_interrupt(CpuState *cpu,uint32_t pc){
 if(cop_fired++)return;
 uint16_t sp=cpu->S;uint64_t n=interp_bridge_native_continuation_insns_total();
 g_test_snes.inNmi=g_test_snes.rdnmiPending=g_test_snes.nmiEnabled=true;
 cpu_push_interrupt_frame_at(cpu,pc);
 /* The real finite NMI contains its own COP/RTI; an already-expired
  * scheduler deadline must not stop it on that inner RTI. */
 interp_bridge_set_master_deadline(cpu->master_cycles?cpu->master_cycles-1:1);
 CHECK(interp_bridge_run_interrupt(cpu,0x008500)==1,"actual host NMI with nested COP completes finite owner");
 CHECK(cpu->S==sp,"NMI and innerCOP restore suspended outerCOP stack");
 CHECK(interp_bridge_native_continuation_insns_total()==n,"foreign NMI scope refuses registered COP effects");
 interp_bridge_set_master_deadline(cop_deadline);
}
static void cop_irq_arrive(CpuState *cpu,uint32_t pc){
 (void)pc;if(cop_irq_fired++)return;
 snes_sync_master_clock(g_snes,cpu->master_cycles);
 CHECK(g_snes->inIrq,"real comparator crosses configured H target during original COP frame");
}
'''


PAIR=r'''
static void mmio_pair(unsigned budget,unsigned mode,int interrupt){
 mmio_run(&before,0,budget,mode,interrupt);mmio_run(&after,1,budget,mode,interrupt);++mmio_pairs;
 CHECK(!memcmp(&before.cpu,&after.cpu,sizeof before.cpu),"COP fullCPU/width/PB/PC/S/master/openbus exact");
 CHECK(!memcmp(&before.snes,&after.snes,sizeof before.snes),"real math/IRQ/beam state exact");
 CHECK(!memcmp(&before.apu,&after.apu,sizeof before.apu)&&!memcmp(&before.spc,&after.spc,sizeof before.spc)&&!memcmp(&before.dsp,&after.dsp,sizeof before.dsp),"real full APU/SPC/DSP and scheduler exact");
 CHECK(before.count==after.count&&!memcmp(before.events,after.events,before.count*sizeof *events),"ordered COP frame/signature/pointer/MMIO bus/access leads exact");
 CHECK(!memcmp(before.wram,after.wram,sizeof before.wram),"all actual WRAM/stack/return-PC writes exact");
 CHECK(before.resume==after.resume&&before.logical==after.logical,"same original owning retirement and deadline resume");
 CHECK(!before.ni&&before.ii==after.ii+after.ni&&before.ic==after.ic+after.nc,"native effects executed without ISA decoder relabelling");
 if(budget>=8000){
  CHECK(after.cpu.S==cop_stack&&after.cpu.PB==cop_bank,"COP RTI or frame-discard RTL returns original owner PB/S");
  CHECK(after.cpu.m_flag==(cop_case?0:((mode>>1)&1))&&after.cpu.x_flag==(cop_case?0:(mode&1)),"RTI restores original widths; frame-discard RTL keeps live handler widths");
  CHECK(after.ni>0,"new dispatcher/frame data effects actually native");
  if(cop_case)CHECK(after.wram[0x30a]==1,"COP frame pop plus RTL reaches surrounding JSL continuation");
  else {
   CHECK(after.wram[0x310]==2&&after.wram[0x306]==2,"outer and nested guest COP execute and helpers return");
   CHECK((after.wram[0x300]|after.wram[0x301]<<8)==0x7e,"real mapped MUL result");
   CHECK((after.wram[0x302]|after.wram[0x303]<<8)==0x299&&(after.wram[0x304]|after.wram[0x305]<<8)==5,"real mapped DIV result/remainder");
  }
  CHECK(after.wram[0x312]==after.wram[0x320],"each actual IRQ/NMI also completes its nested COP");
  if(interrupt==2&&!cop_case)CHECK(after.wram[0x320]>0,"real comparator IRQ reaches acknowledged handler after COP RTI");
  else CHECK(after.wram[0x320]==((interrupt&1)?1:0),"NMI control or still-masked pending IRQ is exact");
 }
}
'''


def _source():
    text,_=cop_source();start=text.index('/* PRIVATE ROM-derived continuations;');end=text.index('typedef struct {\n CpuState cpu;Snes snes;Apu apu;')
    segments,entries=_programs();generated,receipt=emit((REPO/'runner/src/snes/interp816.c').read_text(),entries,registration_name='RegisterMmio')
    assert not re.search(r'\b(?:interp816_|ni_\w+_)(?:runOpcode|doOpcode)\s*\(',generated)
    text=text[:start]+generated+SUPPORT+text[end:]
    # The normal bus still logs the exact attempted native store. This mutant
    # drops only that store's actual forwarding, so frame memory/control checks
    # must detect it without relying on a changed event count.
    text=text.replace('uint8 cpu_read8(CpuState *cpu,uint8 bank,uint16 addr){','static unsigned cop_drop_store;\nuint8 cpu_read8(CpuState *cpu,uint8 bank,uint16 addr){')
    text=text.replace('cop_hook,cop_drop_store;','cop_hook;')
    text=text.replace('mmio_note(cpu,adr,value,1);','mmio_note(cpu,adr,value,1);if(cop_drop_store){cpu->open_bus=value;return;}')
    run=_c_function(text,'mmio_run').rstrip()
    run=run.replace('g_cpu.A=0x5a;','g_cpu.S=cop_stack;g_cpu.D=0x0123;g_cpu.A=0x5a;')
    run=run.replace('g_cpu._flag_I=1;', 'g_cpu._flag_I=(dma_enabled&2)?0:1;')
    run=run.replace('snes_set_raster_irq_beam_enabled(false);', 'snes_set_raster_irq_beam_enabled((dma_enabled&2)!=0);if(dma_enabled&2){g_test_snes.vPos=224;g_test_snes.hPos=0;g_test_snes.hIrqEnabled=true;g_test_snes.hTimer=20;}')
    run=run.replace('interp_bridge_set_master_deadline(budget);','cop_deadline=budget;interp_bridge_set_master_deadline(budget);')
    run=run.replace('interp_bridge_run_until_quiescent(&g_cpu,0x829000)','interp_bridge_run_until_quiescent(&g_cpu,(cop_bank<<16)|(cop_case?0x9020:0x9000))')
    run=run.replace(' interp_bridge_set_master_deadline(0);out->cpu=',r'''
 /* A scheduler bridge yields IRQ_PENDING; the owning host, not a native
  * callback, pushes/delivers the actual IRQ and resumes that exact PC. */
 if(dma_enabled&2){unsigned delivered=0;
  while(g_test_snes.inIrq&&!g_cpu._flag_I&&g_cpu.master_cycles<budget){
   CHECK(++delivered<16,"bounded owning IRQ deliveries");if(delivered>=16)break;
   uint32_t resume=interp_bridge_lle_resume_pc();uint16_t sp=g_cpu.S;unsigned bus_before=event_count;
   uint64_t native_before=interp_bridge_native_continuation_insns_total();
   cpu_push_interrupt_frame_at(&g_cpu,resume);
   CHECK(interp_bridge_run_interrupt(&g_cpu,0x008500)==1,"real comparator IRQ delivered by original owner");
   bool acknowledged=false;for(unsigned j=bus_before;j<event_count;j++)
    if(!events[j].write&&(events[j].adr&0xffff)==0x4211&&(events[j].value&0x80))acknowledged=true;
   CHECK(g_cpu.S==sp&&acknowledged,"IRQ nested COP/RTI restores S and real4211ack reads asserted latch");
   CHECK(native_before==interp_bridge_native_continuation_insns_total(),"finite IRQ scope refuses registered dispatcher effects");
   CHECK(interp_bridge_run_until_quiescent(&g_cpu,resume)==1,"original pendingIRQ continuation resumes at exact PC");
  }
 }
 interp_bridge_set_master_deadline(0);out->cpu=''')
    text=text.replace(_c_function(text,'mmio_run').rstrip(),run)
    start=text.index(' static const uint8_t cop_code[]=');end=text.index(' interp_bridge_set_interpret_all',start)
    code=[]
    for pc,data in segments.items():code.append(' {const uint8_t code[]={'+','.join(str(x)for x in data)+'};memcpy(RAM+'+hex(pc)+',code,sizeof code);}')
    code.append(' const uint8_t maincode[]={2,0,0xdb,0x80,0xfe};memcpy(RAM+(cop_bank<<16)+0x9000,maincode,sizeof maincode);')
    code.append(' RAM[((cop_bank^0x80)<<16)+0x9001]=2; /* Wrong PB must select a different live signature. */')
    code.append(' const uint8_t yieldcode[]={0x22,0,0x86,0x83,0xee,0x0a,3,0x80,0xfe};memcpy(RAM+(cop_bank<<16)+0x9020,yieldcode,sizeof yieldcode);')
    code.append(' RAM[0xffe4]=0;RAM[0xffe5]=0x80;RAM[0xffee]=0;RAM[0xffef]=0x85;')
    text=text[:start]+'\n'.join(code)+'\n'+text[end:]
    start=text.index('    InterpNativeInstruction items[256];');end=text.index(' event_count=0;',start)
    text=text[:start]+r'''
    InterpNativeInstruction items[1024];size_t n=sizeof ni_entries/sizeof *ni_entries;CHECK(n<=1024,"bounded synthetic COP cohort");memcpy(items,ni_entries,sizeof ni_entries);
    if(cop_fault)for(size_t i=0;i<n;i++){
      bool selected=cop_fault==3?(items[i].bytes[0]==0x83&&items[i].bytes[1]==5):items[i].pc24==0x8003;
      if(selected){cop_actual[(items[i].m<<1)|items[i].x]=items[i].step;items[i].step=cop_corrupt;}
    }
    CHECK(interp_bridge_add_native_instructions(items,n),"production dispatcher/saved-register/frame-addressed registration");cop_fired=cop_irq_fired=0;
    if(dma_enabled&1)interp_bridge_add_pre_opcode_hook(0x008000,cop_interrupt);
    if(dma_enabled&2)interp_bridge_add_pre_opcode_hook(0x008003,cop_irq_arrive);
'''+text[end:]
    text=text.replace(_c_function(text,'mmio_pair').rstrip(),PAIR)
    text=text[:text.index('int main(int argc,char **argv){')]+r'''
int main(int argc,char **argv){RAM=malloc(MEMSZ);if(!RAM)return 2;cop_fault=argc>1?atoi(argv[1]):0;
 if(cop_fault)mmio_pair(8000,3,1);
 else {
  for(cop_case=0;cop_case<2;cop_case++)for(unsigned mode=0;mode<4;mode++)for(unsigned irq=0;irq<2;irq++){
   for(unsigned budget=1;budget<=160;budget++)mmio_pair(budget,mode,irq);
   for(unsigned budget=700;budget<=2400;budget+=113)mmio_pair(budget,mode,irq);mmio_pair(8000,mode,irq);
  }
  for(cop_case=0;cop_case<2;cop_case++)for(unsigned b=0;b<4;b++)for(unsigned s=0;s<2;s++){
   cop_bank=(unsigned[]){2,0x42,0x82,0xc2}[b];cop_stack=s?0xbff:0x1ff;mmio_pair(8000,3,1);
  }
  cop_bank=0x82;cop_stack=0x1ff;
  for(cop_case=0;cop_case<2;cop_case++)for(unsigned mode=0;mode<4;mode++){
   for(unsigned budget=80;budget<800;budget+=103)mmio_pair(budget,mode,2);mmio_pair(8000,mode,2);
  }
 }
 printf("cop_dispatch_pairs=%u checks=%d failures=%d\n",mmio_pairs,g_check,fixture_fail);free(RAM);return fixture_fail?1:0;}
'''
    return text,receipt


@pytest.fixture(scope='module')
def dispatcher_binary(tmp_path_factory):
    out=tmp_path_factory.mktemp('native-cop-dispatcher');cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    source,receipt=_source();src=out/'dispatcher.c';src.write_text(source,encoding='utf-8');(out/'emission.json').write_text(json.dumps(receipt,indent=2))
    exe=out/('dispatcher.exe'if os.name=='nt'else'dispatcher')
    files=['interp816.c','interp_bridge.c','snes.c','apu.c','spc.c','dsp.c','dsp_clock.c','dma.c','cx4.c','sdd1.c','tier2_capture.c']
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(src),*[str(REPO/'runner/src/snes'/p)for p in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    result=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (out/'compile.json').write_text(json.dumps(dict(command=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2))
    assert result.returncode==0,result.stdout+result.stderr
    return out,exe


@pytest.mark.parametrize('lookup',['0','1'])
@pytest.mark.parametrize('fault',[0,1,2,3,4])
def test_cop_dispatcher_savedregs_and_live_frame_keep_owner(dispatcher_binary,lookup,fault):
    out,exe=dispatcher_binary
    result=subprocess.run([str(exe),str(fault)],capture_output=True,text=True,timeout=90,cwd=out,env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup))
    (out/f'run-{lookup}-{fault}.json').write_text(json.dumps(dict(exit_code=result.returncode,lookup=lookup,fault=fault,stdout=result.stdout,stderr=result.stderr),indent=2))
    if fault:assert result.returncode==1 and'FAIL:'in result.stdout
    else:assert result.returncode==0,result.stdout+result.stderr
