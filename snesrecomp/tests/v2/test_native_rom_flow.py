"""ROM-free ROM MVN/indexed-JSR effects under actual owning-core retirement.

These tests reuse the existing canonical bridge/APU/DMA fixtures. No accepted
callback calls the decoder. Only the first actual opcode-fetch IPC observer is
normalized; operand, data, stack, write, clock and device observations stay exact.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
from unittest.mock import patch

import pytest
import snes65816 as decoder
from v2.native_effects import emit
from test_native_mmio_continuation import _source as mmio_source, BUS as OLD_BUS
from test_native_wram_copy import BUS, SUPPORT as WRAM_SUPPORT
from test_region_pacing import _c_function
import test_native_call_continuation as calls

REPO = Path(__file__).resolve().parents[2]
BANKS = (2, 0x42, 0x82, 0xC2)


def replace(text, old, new):
    assert old in text, "Fixture source seam changed"
    return text.replace(old, new)


FLOW_HELPERS = r'''
static unsigned flow_kind;
static unsigned flow_mutant_calls;
static uint8_t *flow_expected;
static uint32_t flow_pc(void){return (wc_bank<<16)|(flow_kind?0x9400u:0x9000u+wc_variant*16u);}
static void setup_byte(unsigned bank,uint16_t adr,uint8_t value){
 if(mapped_ram(bank,adr))g_test_snes.ram[((bank==0x7f)?0x10000:0)+adr]=value;
 else RAM[(bank<<16)|adr]=value;
}
static void pointer_at(unsigned bank,uint16_t table,uint16_t index,uint16_t target){
 setup_byte(bank,(uint16_t)(table+index),(uint8_t)target);
 setup_byte(bank,(uint16_t)(table+index+1),(uint8_t)(target>>8));
}
'''

FLOW_REGISTER = r'''
static void wc_register(int policy){
 InterpNativeInstruction items[256];size_t n=sizeof ni_entries/sizeof *ni_entries;
 CHECK(n<=256,"bounded ordinary ROM descriptors");memcpy(items,ni_entries,sizeof ni_entries);
 if(wc_mutant)for(size_t i=0;i<n;i++){
  unsigned op=items[i].bytes[0];
  if(items[i].pc24==flow_pc()&&((wc_mutant==1&&op==0x54)||(wc_mutant>=2&&op==0xfc))){
   actual_mvn[items[i].pc24>>16][(items[i].m<<1)|items[i].x]=items[i].step;items[i].step=broken_mvn;
  }
 }
 if(policy==3){size_t used=0;for(size_t i=0;i<n;i++)if(items[i].m!=((wc_mode>>1)&1))items[used++]=items[i];n=used;}
 CHECK(interp_bridge_add_native_instructions(items,n),"ordinary ROM MVN/indexed-call registration");
 CHECK(interp_bridge_restrict_native_instructions(items,n,INTERP_NATIVE_SCOPE_SCHEDULER),"new effects remain scheduler-only");
 if(policy==2)interp_bridge_clear_native_instructions();
 if(policy==4){uint32 excluded=flow_pc();interp_bridge_set_lle_bounce_exclusions(&excluded,1);}
}
'''

FLOW_HOOK = r'''
static void wc_hook(CpuState *cpu,uint32 pc){
 ++wc_visits;
 if(wc_variant==1){
  if(flow_kind)pointer_at(wc_bank,0x9540,cpu->X,0x9610);
  else if(wc_visits==2){RAM[pc+1]=0x7e;RAM[pc+2]=0x7f;}
 }
 if(wc_variant==2){
  if(flow_kind)RAM[pc+1]=0x60;
  else if(wc_visits==2){RAM[pc]=0x80;RAM[pc+1]=0xfe;}
 }
 if(wc_variant==3){cpu->x_flag=!cpu->x_flag;cpu_mirrors_to_p(cpu);if(flow_kind)cpu->X+=2;}
 if(wc_variant==4&&!wc_hooked++){
  uint16_t sp=cpu->S;uint64_t ni=interp_bridge_native_continuation_insns_total();
  cpu_push_interrupt_frame_at(cpu,pc);
  CHECK(interp_bridge_run_interrupt(cpu,0x008800)==1,"nested original interrupt finishes");
  CHECK(cpu->S==sp&&interp_bridge_native_continuation_insns_total()==ni,"nested foreign owner cannot inherit ROM flow grants");
 }
}
'''

FLOW_PROGRAM = r'''
 uint32_t pc=flow_pc();uint8_t dest=wc_variant==5?0:wc_variant==8?(uint8_t)wc_bank:0x7f;
 uint8_t src=wc_variant==6?0:0x7e;
 const uint8_t move[]={0x54,dest,src,0x80,0xfe};
 const uint8_t call[]={0xfc,0x40,0x95,0x80,0xfe};
 memcpy(RAM+pc,flow_kind?call:move,5);
 const uint8_t target[]={0x8d,0x40,0x21,0x60};const uint8_t alternate[]={0x1a,0x60};
 memcpy(RAM+(wc_bank<<16)+0x9600,target,sizeof target);memcpy(RAM+(wc_bank<<16)+0x9610,alternate,sizeof alternate);
 pointer_at(wc_bank,0x9540,g_cpu.X,0x9600);pointer_at(wc_bank,0x9560,g_cpu.X,0x9610);
 pointer_at(wc_bank,0x9540,(uint16_t)(g_cpu.X+2),0x9610);
 const uint8_t handler[]={0xc2,0x20,0xa9,0,0,flow_kind?0xfc:0x54,flow_kind?0x40:0x7f,flow_kind?0x95:0x7e,0xaf,0x11,0x42,0,0x40};
 memcpy(RAM+(flow_kind?0x8810:0x8800),handler,sizeof handler);memcpy(RAM+0x9600,target,sizeof target);pointer_at(0,0x9540,g_cpu.X,0x9600);
'''

FLOW_VARIANTS = r'''
 if(wc_variant==5){g_cpu.Y=0x420b;g_test_snes.ram[wc_x]=1;if(flow_kind){g_cpu.A=1;RAM[(wc_bank<<16)|0x9601]=0x0b;RAM[(wc_bank<<16)|0x9602]=0x42;}}
 if(wc_variant==6&&!flow_kind)g_cpu.X=0x2140;
 if(wc_variant==7){const uint8_t safe[]={0xea,0xea,0xea,0x80,0xfe};memcpy(RAM+pc,safe,sizeof safe);}
 if(wc_variant==8&&!flow_kind){g_cpu.Y=(uint16_t)(pc+1);g_test_snes.ram[wc_x]=0x7f;}
'''

FLOW_MAIN = r'''
static void registry_tests(void){
 interp_bridge_set_interpret_all(0);interp_bridge_clear_native_instructions();
 for(unsigned op=0;op<2;op++){
  InterpNativeInstruction d={0};d.pc24=0x828800;d.length=3;d.bytes[0]=op?0xfc:0x54;d.step=ni_entries[0].step;
  CHECK(interp_bridge_add_native_instructions(&d,1),"generic ROM API admits canonical flow shape");
  CHECK(!interp_bridge_allow_native_nmi_instructions(0x8800,&d,1)&&!interp_bridge_native_nmi_grants(),"unrestricted ROM MVN/FC cannot receive NMI grant");
  interp_bridge_clear_native_instructions();d.e=1;CHECK(!interp_bridge_add_native_instructions(&d,1),"new flow E1 remains refused");
 }
}
int main(int argc,char **argv){
 RAM=malloc(MEMSZ);flow_expected=malloc(MEMSZ);if(!RAM||!flow_expected)return 2;
 wc_mutant=argc>1?(unsigned)atoi(argv[1]):0;
 if(wc_mutant){wc_bank=0x82;flow_kind=wc_mutant==1?0:1;wc_variant=flow_kind?1:0;wc_count=2;wc_pair(2000,0,0);}
 else{
  for(flow_kind=0;flow_kind<2;flow_kind++){
   for(unsigned b=0;b<4;b++)for(wc_mode=0;wc_mode<4;wc_mode++){
    wc_bank=(unsigned[]){2,0x42,0x82,0xc2}[b];wc_variant=0;wc_count=2;wc_x=0x1000;wc_y=0x1800;
    for(unsigned budget=1;budget<180;budget+=13)wc_pair(budget,0,0);wc_pair(2000,0,0);
   }
   wc_bank=0x82;wc_mode=0;
   for(unsigned count=0;count<3;count++)for(unsigned wrap=0;wrap<2;wrap++){
    wc_count=(uint16_t[]){0,1,0xffff}[count];wc_x=flow_kind?(wrap?0x6abf:0xff):(wrap?0xffff:0xff);wc_y=wrap?0xffff:0xff;
    for(unsigned budget=28;budget<150;budget+=17)wc_pair(budget,0,0);
   }
   wc_count=2;wc_x=0x1000;wc_y=0x1800;
   for(wc_variant=1;wc_variant<=9;wc_variant++)wc_pair(2000,0,0);wc_variant=0;
   for(unsigned s=0;s<3;s++){wc_stack=(uint16_t[]){0,1,0xffff}[s];wc_pair(2000,0,0);}wc_stack=0x1ff;
   for(unsigned policy=1;policy<=6;policy++)wc_pair(2000,policy,0);
   for(wc_mode=0;wc_mode<4;wc_mode++){wc_pair(2000,0,1);wc_pair(2000,0,2);}
  }
  registry_tests();
 }
 printf("rom_flow_pairs=%u mutant_callbacks=%u checks=%d failures=%d\n",wc_pairs,flow_mutant_calls,g_check,fixture_fail);
 free(RAM);free(flow_expected);return fixture_fail?1:0;
}
'''


def peripheral_source(outline):
    text, _ = mmio_source()
    text = text[:text.index('/* PRIVATE ROM-derived continuations;')]
    text = replace(text, OLD_BUS, BUS)
    text = replace(text, 'CHECK(event_count<8192,"ordered bus log bounded");',
                   'if(event_count>=8192){fprintf(stderr,"FAIL: bounded ROM-flow bus fixture overflow\\n");exit(3);}')
    text += '\n#include "snes/interp_native_wram.h"\n'
    support = WRAM_SUPPORT[:WRAM_SUPPORT.index('static void registry_tests(')]
    support = replace(support, _c_function(support, 'wc_register').rstrip(), FLOW_REGISTER)
    support = replace(support, _c_function(support, 'wc_hook').rstrip(), FLOW_HOOK)
    support = replace(support, 'static WramOutcome before,after;', 'static WramOutcome before,after;')
    support = replace(support, 'static uint64_t wc_deadline;', 'static uint64_t wc_deadline;\n' + FLOW_HELPERS)
    support = replace(support, _c_function(support, 'broken_mvn').rstrip(), r'''
static int broken_mvn(Interp816 *in){
 ++flow_mutant_calls;
 unsigned mode=(in->mf<<1)|in->xf;InterpNativeInstructionStep step=actual_mvn[in->k][mode];
 if(wc_mutant==1){int cycles=0;unsigned transfers=0;do{
  if(++transfers>3){fprintf(stderr,"FAIL: bounded three-byte mutant fixture mapping\\n");exit(3);}
  cycles+=step(in);
 }while(in->a!=0xffff);return in->cyclesUsed=cycles;}
 int cycles=step(in);if(wc_mutant==2)in->pc=0x9600;if(wc_mutant==3)++in->k;return cycles;
}''')
    start = support.index(' const uint8_t stub[]=')
    end = support.index(' g_test_snes.ramAdr=', start)
    support = support[:start] + FLOW_PROGRAM + support[end:]
    start = support.index(' if(wc_variant==5){', support.index('static void wc_run('))
    end = support.index(' if(wc_variant==9){', start)
    support = support[:start] + FLOW_VARIANTS + support[end:]
    support = replace(support, 'g_cpu.DB=0x81;', 'g_cpu.DB=0;')
    support = replace(support, 'g_cpu.X=wc_x;g_cpu.Y=wc_y;',
                      'g_cpu.X=(wc_mode&1)?(wc_x&255):wc_x;g_cpu.Y=(wc_mode&1)?(wc_y&255):wc_y;')
    support = replace(support, 'g_test_cart.type=policy==5?CART_SA1:CART_HIROM;g_test_cart.rom=RAM;', 'g_test_cart.type=policy==5?CART_SA1:CART_HIROM;g_test_cart.rom=policy==6?NULL:RAM;')
    support = replace(support, 'interp_bridge_set_interpret_all(!native);', 'interp_bridge_set_interpret_all(!native||policy==1);')
    support = replace(support, '(wc_bank<<16)|0x403,wc_hook', 'flow_pc(),wc_hook')
    support = replace(support, '(wc_bank<<16)|0x9000)==1', 'flow_pc())==1')
    support = support.replace('0x008800', '(flow_kind?0x008810:0x008800)')
    support = replace(support, 'wc_run(&before,0,budget,policy,nmi);wc_run(&after,1,budget,policy,nmi);', 'wc_run(&before,0,budget,policy,nmi);memcpy(flow_expected,RAM,MEMSZ);wc_run(&after,1,budget,policy,nmi);CHECK(!memcmp(flow_expected,RAM,MEMSZ),"complete ROM data/pointer/stack memory parity");')
    tail = support.index(' CHECK(after.wi==after.ni')
    support = support[:tail] + r'''
 CHECK(!after.wi&&!after.wc,"generic ROM work never relabelled WRAM subset");
 if(policy==1||policy==2||policy==3||policy==5||policy==6||wc_variant==7||nmi)CHECK(!after.ni,"mode/mapper/clear/shape/interrupt refusal measured");
 if(!policy&&!wc_variant&&budget>=2000&&!nmi)CHECK(after.ni>0,"new ordinary ROM callback actually executes");
 if(wc_variant==5&&!policy&&!nmi)CHECK(after.dma_clocks>0,"payload triggers actual DMA clock service");
}
'''
    entries = []
    for bank in BANKS:
        for variant in range(10):
            raw = bytes((0x54, 0 if variant == 5 else bank if variant == 8 else 0x7F,
                         0 if variant == 6 else 0x7E))
            entries.extend(dict(pc24=bank << 16 | (0x9000 + variant * 16), m=m, x=x, e=0,
                                bytes=raw, mnemonic='MVN', immediate=True)
                           for m in range(2) for x in range(2))
        entries.extend(dict(pc24=bank << 16 | 0x9400, m=m, x=x, e=0,
                            bytes=bytes.fromhex('fc4095'), mnemonic='JSR', immediate=False)
                       for m in range(2) for x in range(2))
    # Both interrupt shapes are registered so fallback is measured, not absent.
    # They use separate sites; the runtime handler is selected accordingly.
    entries.extend(dict(pc24=0x008805, m=m, x=x, e=0,
                        bytes=bytes.fromhex('547f7e'), mnemonic='MVN', immediate=True)
                   for m in range(2) for x in range(2))
    entries.extend(dict(pc24=0x008815, m=m, x=x, e=0,
                        bytes=bytes.fromhex('fc4095'), mnemonic='JSR', immediate=False)
                   for m in range(2) for x in range(2))
    generated, receipt = emit((REPO/'runner/src/snes/interp816.c').read_text(), entries,
                              registration_name='RegisterRomFlow', outline_effects=outline)
    return text + generated + support + FLOW_MAIN, receipt


def indexed_owner_source(outline):
    def indexed_emit(source, entries, **kwargs):
        changed = []
        for row in entries:
            row = dict(row)
            if row['pc24'] & 0xFFFF == 0x8100:
                row['bytes'] = bytes.fromhex('fc0082')
            if row['pc24'] == 0x83FFFC:
                row['bytes'] = bytes.fromhex('fc8081')
            changed.append(row)
        for bank in BANKS:
            changed.extend(dict(pc24=bank << 16 | 0xFFFD, m=m, x=x, e=0,
                                bytes=bytes.fromhex('fc8081'), mnemonic='JSR', immediate=False)
                           for m in range(2) for x in range(2))
        return emit(source, changed, **kwargs, outline_effects=outline)
    with patch.object(calls, 'emit', indexed_emit):
        text, receipt = calls._source()
    text = replace(text, 'const uint8_t body[]={0x20,0x40,0x81,', 'const uint8_t body[]={0xfc,0,0x82,')
    pointer = r'''
static void call_pointer(unsigned bank,uint16 table,uint16 index,uint16 target){
 RAM[(bank<<16)|(uint16)(table+index)]=(uint8)target;RAM[(bank<<16)|(uint16)(table+index+1)]=(uint8)(target>>8);
}
'''
    text = replace(text, 'static unsigned call_fault,aot_mode;', pointer + '\nstatic unsigned call_fault,aot_mode;')
    text = replace(text, 'load(code_base,body,sizeof body);', 'load(code_base,body,sizeof body);call_pointer(bank,0x8200,g_c.X,0x8140);call_pointer(bank,0x8200,(uint16)(g_c.X&255),0x8140);call_pointer(bank,0x8200,(uint16)(g_c.X+2),0x8141);call_pointer(bank,0x8300,g_c.X,0x8141);call_pointer(0x83,0x8180,g_c.X,0x8180);')
    text = replace(text, 'if(hook_kind==1)RAM[pc+1]^=1;', 'if(hook_kind==1){RAM[pc+1]=0;RAM[pc+2]=0x83;}if(hook_kind==5)call_pointer(pc>>16,0x8200,cpu->X,0x8141);if(hook_kind==6)cpu->X+=2;')
    text = replace(text, 'items[i].pc24==0x838000', 'items[i].pc24==code_base')
    text = replace(text, 'if(call_fault==2)++cycles;', 'if(call_fault==6)in->pc=0x8140;if(call_fault==7)++in->k;if(call_fault==2)++cycles;')
    text = replace(text, 'static unsigned call_fault,aot_mode;', 'static unsigned call_mutant_calls;static unsigned call_fault,aot_mode;')
    text = replace(text, 'static int call_corrupt(Interp816 *in){', 'static int call_corrupt(Interp816 *in){++call_mutant_calls;')
    text = replace(text, 'printf("call_pairs=%u checks=%d failures=%d\\n",pairs,g_check,fixture_fail);', 'printf("call_pairs=%u mutant_callbacks=%u checks=%d failures=%d\\n",pairs,call_mutant_calls,g_check,fixture_fail);')
    text = replace(text, 'for(unsigned h=1;h<=4;h++)', 'for(unsigned h=1;h<=6;h++)')
    text = replace(text, 'else if(call_fault){aot_mode=0;pair(0x82,1,1,0,0,10000,0,0,0,1);}', 'else if(call_fault){aot_mode=0;pair(0x82,1,1,0,0,10000,0,call_fault==6?5:0,0,1);}')
    text = replace(text, 'RAM[at]=0x20;', 'RAM[at]=0xfc;call_pointer(0x83,0x8180,g_c.X,0x8180);')
    text = replace(text, 'const unsigned ops[]={0x20,0x22};', 'const unsigned ops[]={0xfc,0x22};')
    text = replace(text, 'op==0x20?0xfffd:0xfffc', 'op==0xfc?0xfffd:0xfffc')
    text = replace(text, 'RAM[at]=op;RAM[at+1]=0x80;', 'RAM[at]=op;if(op==0xfc)call_pointer(bank,0x8180,g_c.X,0x8180);RAM[at+1]=0x80;')
    return text, receipt


@pytest.fixture(scope='module', params=[False, True], ids=['flat', 'outlined'])
def flow_binaries(tmp_path_factory, request):
    cc = os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
    if not cc:
        pytest.skip('C11 compiler required')
    out = tmp_path_factory.mktemp('native-rom-flow-' + str(int(request.param)))
    built = {}
    for name, builder in [('peripheral', peripheral_source), ('indexed-owner', indexed_owner_source)]:
        text, receipt = builder(request.param)
        assert not re.search(r'\b(?:ni_\d\d_)(?:runOpcode|doOpcode)\s*\(', text)
        source = out/(name+'.c');source.write_text(text, encoding='utf-8')
        core = out/'snes_core.c'
        core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n')
        executable = out/(name+('.exe' if os.name == 'nt' else ''))
        files = ['interp816.c', 'interp_bridge.c', 'dma.c', 'cx4.c', 'sdd1.c', 'tier2_capture.c']
        if name == 'peripheral':
            files += ['snes.c', 'apu.c', 'spc.c', 'dsp.c', 'dsp_clock.c']
        command = [cc, '-std=c11', '-O1', '-DSNESRECOMP_TIER2_TEST=1', '-DSNESRECOMP_REVERSE_DEBUG=0',
                   '-I', str(REPO/'runner/src'), '-I', str(REPO/'runner/src/snes'), '-I', str(REPO/'tests/dma'),
                   str(source), *([] if name == 'peripheral' else [str(core)]),
                   *[str(REPO/'runner/src/snes'/f) for f in files], str(REPO/'runner/src/sha256.c'), '-lm', '-o', str(executable)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (out/(name+'-compile.json')).write_text(json.dumps(dict(command=command, exit_code=result.returncode,
            stdout=result.stdout, stderr=result.stderr, emission=receipt,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()), indent=2))
        assert result.returncode == 0, result.stdout + result.stderr
        built[name] = executable
    return out, built


def execute_case(fixture, name, lookup, mutant):
    out, binaries = fixture
    env = {k:v for k,v in os.environ.items() if not k.startswith(('IOG_', 'SNESRECOMP_'))}
    env['SNESRECOMP_NATIVE_INSTRUCTION_INDEX'] = lookup
    result = subprocess.run([str(binaries[name]), str(mutant)], capture_output=True, text=True,
                            timeout=120, cwd=out, env=env)
    (out/f'{name}-{lookup}-{mutant}.json').write_text(json.dumps(dict(lookup=lookup, mutant=mutant,
        exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr), indent=2))
    if mutant not in (0, 99):
        assert result.returncode == 1 and 'FAIL:' in result.stdout + result.stderr, result.stdout + result.stderr
        count = re.search(r'mutant_callbacks=(\d+)', result.stdout)
        assert count and int(count[1]) > 0, 'Mutant callback did not actually execute: ' + result.stdout
        if name == 'peripheral':
            assert 'parity' in result.stdout + result.stderr, result.stdout + result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('lookup', ['0', '1'])
@pytest.mark.parametrize('mutant', [0, 1, 2, 3])
def test_rom_flow_actual_bus_peripherals_and_deadlines(flow_binaries, lookup, mutant):
    execute_case(flow_binaries, 'peripheral', lookup, mutant)


@pytest.mark.parametrize('lookup', ['0', '1'])
@pytest.mark.parametrize('mutant', [0, 1, 2, 3, 4, 5, 6, 7, 99])
def test_indexed_jsr_actual_owner_and_return_protocol(flow_binaries, lookup, mutant):
    execute_case(flow_binaries, 'indexed-owner', lookup, mutant)


def test_rom_flow_generator_refuses_nmi_grants():
    source = (REPO/'runner/src/snes/interp816.c').read_text()
    for opcode, name in [(bytes.fromhex('547f7e'), 'MVN'), (bytes.fromhex('fc0082'), 'JSR')]:
        row = dict(pc24=0x828000, m=0, x=0, e=0, bytes=opcode, mnemonic=name,
                   immediate=decoder.opcode_table()[opcode[0]][1] == decoder.IMM)
        with pytest.raises(ValueError, match='Unsupported.*NMI'):
            emit(source, [row], nmi_owner_pc24=0x8800, nmi_keys=[(0x828000, 0, 0, 0)])
