"""Existing bounded effects inside real nested COP frames and mapped math MMIO.

COP/RTI/calls/data-stack opcodes are not registered here. SNES arithmetic is
the actual current core's immediate-result model, not silicon latency proof.
"""
import hashlib,json,os,shutil,subprocess
import pytest
import snes65816 as decoder
from v2.native_effects import emit
from test_native_mmio_continuation import _source as mmio_source,REPO
from test_region_pacing import _c_function


def _program():
    code=bytearray();entries=[];m=x=1
    excluded={0x02,0x40,0x08,0x28,0x20,0x60}
    def add(raw):
        nonlocal m,x
        raw=bytes.fromhex(raw);pc=0x008100+len(code);name,mode,size=decoder.opcode_table()[raw[0]]
        if raw[0]not in excluded:
            modes=[(a,b)for a in range(2)for b in range(2)]if pc==0x008101 else[(m,x)]
            for a,b in modes:entries.append(dict(pc24=pc,m=a,x=b,e=0,bytes=raw,mnemonic=name,immediate=mode==decoder.IMM))
        code.extend(raw)
        if raw[0]==0xc2:
            if raw[1]&0x20:m=0
            if raw[1]&0x10:x=0
        if raw[0]==0xe2:
            if raw[1]&0x20:m=1
            if raw[1]&0x10:x=1
    for raw in ['08','c230','ee1003','ad1003','c90100','d002','0200','e220','a912','8d0242','a907','8d0342']:
        add(raw)
    for _ in range(8):add('ea')
    for raw in ['c220','ad1642','8d0003','a93412','8d0442','e220','a907','8d0642']:add(raw)
    for _ in range(16):add('ea')
    for raw in ['c220','ad1442','8d0203','ad1642','8d0403','200082','28','40']:add(raw)
    for pc,raw in [(0x008200,bytes.fromhex('ee0603')),(0x008500,bytes.fromhex('ee2003'))]:
        for a,b in ([(0,0)]if pc==0x008200 else[(a,b)for a in range(2)for b in range(2)]):
            entries.append(dict(pc24=pc,m=a,x=b,e=0,bytes=raw,mnemonic='INC',immediate=False))
    return bytes(code),entries


SUPPORT=r'''
static unsigned cop_fault,cop_fired;static InterpNativeInstructionStep cop_actual;
static int cop_corrupt(Interp816 *in){if(cop_fault==1)return interp816_runOpcode(in);int c=cop_actual(in);if(cop_fault==2)++in->sp;return c;}
static void cop_interrupt(CpuState *cpu,uint32_t pc){
 if(cop_fired++)return;uint16_t before=cpu->S;uint64_t n=interp_bridge_native_continuation_insns_total();
 cpu_push_interrupt_frame_at(cpu,pc);CHECK(interp_bridge_run_interrupt(cpu,0x008500)==1,"actual host interrupt within guest COP returns by RTI");
 CHECK(cpu->S==before&&interp_bridge_native_continuation_insns_total()==n,"host ISR native effects refused and COP frame restored");
}
'''

PAIR=r'''
static void mmio_pair(unsigned budget,unsigned mode,int interrupt){
 mmio_run(&before,0,budget,mode,interrupt);mmio_run(&after,1,budget,mode,interrupt);++mmio_pairs;
 CHECK(!memcmp(&before.cpu,&after.cpu,sizeof before.cpu),"COP CPU/P/PB/PC/S and clock parity");
 CHECK(!memcmp(&before.snes,&after.snes,sizeof before.snes),"actual mapped multiplier/divider and beam state parity");
 CHECK(!memcmp(&before.apu,&after.apu,sizeof before.apu)&&!memcmp(&before.spc,&after.spc,sizeof before.spc)&&!memcmp(&before.dsp,&after.dsp,sizeof before.dsp),"complete real APU/SPC/DSP and pending scheduler parity");
 CHECK(before.count==after.count&&!memcmp(before.events,after.events,before.count*sizeof *events),"ordered actual COP stack/MMIO accesses and sample leads");
 CHECK(!memcmp(before.wram,after.wram,sizeof before.wram),"complete real WRAM and nested COP/IRQ frames exact");
 CHECK(before.resume==after.resume&&before.logical==after.logical,"COP deadlines and shared retirement exact");
 CHECK(!before.ni&&before.ii==after.ii+after.ni&&before.ic==after.ic+after.nc,"COP body native effects never decoded/relabelled");
 if(budget>=8000){
  CHECK(after.cpu.S==0x1ff&&after.cpu.PB==0x82,"both guest COP frames RTI to original main owner");
  CHECK(after.cpu.m_flag==((mode>>1)&1)&&after.cpu.x_flag==(mode&1),"RTI restores original M/X");
  CHECK(after.wram[0x310]==2&&after.wram[0x306]==2,"two actual COP entries and JSR helpers completed");
  CHECK((after.wram[0x300]|after.wram[0x301]<<8)==0x7e,"actual mapped MUL18x7 result after original NOPs");
  CHECK((after.wram[0x302]|after.wram[0x303]<<8)==0x299&&(after.wram[0x304]|after.wram[0x305]<<8)==5,"actual mapped DIV1234by7 quotient/remainder after original NOPs");
  CHECK(after.wram[0x320]==(interrupt?1:0)&&after.ni>0,"host IRQ control and actually accepted guest COP effects");
 }
}
'''


def _source():
    text,_=mmio_source();begin=text.index('/* PRIVATE ROM-derived continuations;');end=text.index('typedef struct {\n CpuState cpu;Apu apu;Spc spc;Dsp dsp;Dma dma;')
    raw,entries=_program();generated,receipt=emit((REPO/'runner/src/snes/interp816.c').read_text(),entries,registration_name='RegisterMmio')
    text=text[:begin]+generated+SUPPORT+text[end:]
    text=text.replace('CpuState cpu;Apu apu;','CpuState cpu;Snes snes;Apu apu;')
    text=text.replace('if((bank&0x7f)<0x40&&addr>=0x2100&&addr<0x4380)',
        'if(bank==0x7e||bank==0x7f||((bank&0x7f)<0x40&&(addr<0x2000||(addr>=0x2100&&addr<0x4380))))')
    run=_c_function(text,'mmio_run').rstrip()
    text=text.replace(run,run.replace('g_cpu.m_flag=1;g_cpu.x_flag=0;','g_cpu.m_flag=(ack>>1)&1;g_cpu.x_flag=ack&1;'))
    start=text.index(' const uint8_t program[]=');stop=text.index(' interp_bridge_set_interpret_all',start)
    text=text[:start]+(' static const uint8_t cop_code[]={'+','.join(str(v)for v in raw)+'};\n'
        ' const uint8_t maincode[]={2,0,0xea,0x80,0xfe};memcpy(RAM+0x829000,maincode,sizeof maincode);memcpy(RAM+0x8100,cop_code,sizeof cop_code);\n'
        ' RAM[0xffe4]=0;RAM[0xffe5]=0x81;RAM[0x8200]=0xee;RAM[0x8201]=6;RAM[0x8202]=3;RAM[0x8203]=0x60;\n'
        ' RAM[0x8500]=0xee;RAM[0x8501]=0x20;RAM[0x8502]=3;RAM[0x8503]=0x40;\n')+text[stop:]
    text=text.replace('CHECK(RegisterMmio(),"production generated registration");',r'''
    InterpNativeInstruction items[256];size_t n=sizeof ni_entries/sizeof *ni_entries;CHECK(n<=256,"bounded COP cohort");memcpy(items,ni_entries,sizeof ni_entries);
    if(cop_fault)for(size_t i=0;i<n;i++)if(items[i].pc24==0x8101&&items[i].m==g_cpu.m_flag&&items[i].x==g_cpu.x_flag){cop_actual=items[i].step;items[i].step=cop_corrupt;break;}
    CHECK(interp_bridge_add_native_instructions(items,n),"source-qualified ordinary COP effects only");cop_fired=0;
    if(dma_enabled)interp_bridge_add_pre_opcode_hook(0x008100,cop_interrupt);
''')
    text=text.replace('out->cpu=g_cpu;out->apu=*a;',
        'out->cpu=g_cpu;out->snes=g_test_snes;out->snes.apu=NULL;out->snes.cpu=NULL;out->snes.ppu=NULL;out->snes.dma=NULL;out->snes.cart=NULL;out->snes.ram=NULL;out->apu=*a;')
    text=text.replace(_c_function(text,'mmio_pair').rstrip(),PAIR)
    text=text[:text.index('int main(void){')]+r'''
int main(int argc,char **argv){RAM=malloc(MEMSZ);if(!RAM)return 2;cop_fault=argc>1?atoi(argv[1]):0;
 if(cop_fault)mmio_pair(8000,3,1);
 else for(unsigned mode=0;mode<4;mode++)for(unsigned irq=0;irq<2;irq++){
  for(unsigned d=1;d<=160;d++)mmio_pair(d,mode,irq);
  for(unsigned d=700;d<=4200;d+=53)mmio_pair(d,mode,irq);mmio_pair(8000,mode,irq);
 }
 printf("cop_pairs=%u checks=%d failures=%d\n",mmio_pairs,g_check,fixture_fail);free(RAM);return fixture_fail?1:0;}
'''
    return text,receipt


@pytest.fixture(scope='module')
def cop_binary(tmp_path_factory):
    out=tmp_path_factory.mktemp('native-cop-core');cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    text,receipt=_source();src=out/'cop.c';src.write_text(text,encoding='utf-8');(out/'emission.json').write_text(json.dumps(receipt,indent=2))
    exe=out/('cop.exe'if os.name=='nt'else'cop');files=['interp816.c','interp_bridge.c','snes.c','apu.c','spc.c','dsp.c','dsp_clock.c','dma.c','cx4.c','sdd1.c','tier2_capture.c']
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(src),*[str(REPO/'runner/src/snes'/p)for p in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    p=subprocess.run(command,capture_output=True,text=True,timeout=90);(out/'compile.json').write_text(json.dumps(dict(command=command,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2));assert p.returncode==0,p.stdout+p.stderr
    return out,exe


@pytest.mark.parametrize('lookup',['0','1'])
@pytest.mark.parametrize('fault',[0,1,2])
def test_guest_cop_ordinary_effects_keep_frames_and_mmio(cop_binary,lookup,fault):
    out,exe=cop_binary;p=subprocess.run([str(exe),str(fault)],capture_output=True,text=True,timeout=90,cwd=out,env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup))
    (out/f'run-{lookup}-{fault}.json').write_text(json.dumps(dict(exit_code=p.returncode,lookup=lookup,fault=fault,stdout=p.stdout,stderr=p.stderr),indent=2))
    if fault:assert p.returncode==1 and'FAIL:'in p.stdout
    else:assert p.returncode==0,p.stdout+p.stderr
