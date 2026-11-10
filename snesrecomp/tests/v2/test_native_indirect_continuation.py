"""Indexed-indirect JMP: production fixed effects, live pointers and owner loop."""
import hashlib,json,os,re,shutil,subprocess
import pytest
from v2.native_effects import emit
from test_native_branch_continuation import C_MAIN as BRANCH_MAIN,base_source,REPO
from test_region_pacing import _c_function

BANKS=(2,0x42,0x82,0xc2,0x22)

def _source():
    entries=[];banks=[]
    for bank in BANKS:
        variants=[]
        for v in range(5):
            pc=(0x9000,0x9100,0x90fe,0xfffd,0x9200)[v]
            operand=(0x9300,0xfe,0xfedc,0x9300,0x9340)[v]
            target=pc if v==4 else (pc+(16,-16,32,-32)[v])&65535
            raw=bytes((0x7c,operand&255,operand>>8));full=bank<<16|pc
            variants.append('{'+f'0x{full:06X},0x{bank<<16|target:06X},0x{bank<<16|((pc+3)&65535):06X},3,'+'{'+','.join(map(str,raw))+'}}')
            for m in range(2):
                for x in range(2):entries.append(dict(pc24=full,m=m,x=x,e=0,bytes=raw,mnemonic='JMP',immediate=False))
        banks.append('{'+','.join(variants)+'}')
    core=(REPO/'runner/src/snes/interp816.c').read_text();generated,receipt=emit(core,entries,registration_name='RegisterIndirect')
    nmi,other=emit(core,[dict(pc24=0x8312,m=m,x=x,e=0,bytes=bytes.fromhex('d000'),mnemonic='BNE',immediate=False)for m in range(2)for x in range(2)],registration_name='RegisterNmiBranch')
    nmi=nmi.replace('NiOperands','NmiOperands').replace('ni_','nmi_')
    text=BRANCH_MAIN
    spec='static const BranchSpec specs[1][5][5]={{'+','.join(banks)+'}};\nstatic bool (*registrations[])(void)={RegisterIndirect};\nstatic const InterpNativeInstruction *entry_arrays[]={ni_entries};\n'
    choose=r'''
    InterpNativeInstruction chosen={0};int found=0;
    for(unsigned j=0;j<100;j++){const InterpNativeInstruction *d=&entry_arrays[opindex][j];
      if(d->pc24==branch_pc&&d->m==(refusal==2?!m:m)&&d->x==x){chosen=*d;found=1;break;}}
    CHECK(found,"exact production indexed-jump callback selected");actual_step=chosen.step;if(fault)chosen.step=corrupt_step;
'''
    text=text.replace('/* SPECS */',spec).replace('/* ENTRIES_SELECT */',choose)
    pointer=r'''
static void point_to(uint32 target,uint16 index){
 uint16 adr=(uint16)(RAM[branch_pc+1]|RAM[branch_pc+2]<<8);
 uint32 bank=branch_pc&0xff0000;RAM[bank|(uint16)(adr+index)]=(uint8)target;
 RAM[bank|(uint16)(adr+index+1)]=(uint8)(target>>8);
}
'''
    text=text.replace('static void payload(',pointer+'\nstatic void payload(')
    edit=r'''
static void edit_operand(void){RAM[branch_pc+1]=0;RAM[branch_pc+2]=0x94;point_to(alternate_pc,g_c.X);}
'''
    text=text.replace(_c_function(text,'edit_operand').rstrip(),edit)
    hook=_c_function(text,'branch_hook').rstrip();text=text.replace(hook,hook[:-1]+r'''
  if(hook_type==8)point_to(alternate_pc,cpu->X);
  if(hook_type==9){cpu->X=(cpu->X+2)&(cpu->x_flag?255:65535);point_to(alternate_pc,cpu->X);}
}
''')
    text=text.replace('g_c.X=0x0123;','g_c.X=x?0x23:0x0123;')
    text=text.replace('load(branch_pc,s->bytes,s->length);','load(branch_pc,s->bytes,s->length);point_to(target_pc,g_c.X);')
    text=text.replace('branch_pair(6,','branch_pair(0,').replace('op<12','op<1').replace('for(int take=0;take<2;take++)','for(int take=1;take<2;take++)')
    text=text.replace('for(unsigned h=1;h<=7;h++)','for(unsigned h=1;h<=9;h++)')
    base=base_source();base=base[:base.index('int main(void){')];base=base.replace('pc==0x7e0200||pc==0x7e0201','pc==0x7e0300||pc==0x7e0301')
    return base+generated+nmi+text,[receipt,other]


@pytest.fixture(scope='module')
def indirect_binary(tmp_path_factory):
    out=tmp_path_factory.mktemp('indexed-indirect-core');cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    source,receipts=_source();src=out/'indirect.c';src.write_text(source,encoding='utf-8');(out/'emission.json').write_text(json.dumps(receipts,indent=2))
    core=out/'snes_core.c';core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n')
    exe=out/('indirect.exe'if os.name=='nt'else'indirect')
    cmd=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(src),str(core),*[str(REPO/f)for f in('runner/src/snes/interp816.c','runner/src/sha256.c','runner/src/snes/tier2_capture.c','runner/src/snes/interp_bridge.c','runner/src/snes/cx4.c','runner/src/snes/dma.c','runner/src/snes/sdd1.c')],'-lm','-o',str(exe)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=90);(out/'compile.json').write_text(json.dumps(dict(command=cmd,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2));assert p.returncode==0,p.stdout+p.stderr
    return out,exe


@pytest.mark.parametrize('lookup',['0','1'])
@pytest.mark.parametrize('fault',[0,1,2,3,4,5])
def test_live_indexed_pointer_under_original_owner(indirect_binary,lookup,fault):
    out,exe=indirect_binary;p=subprocess.run([str(exe),str(fault)],capture_output=True,text=True,timeout=90,cwd=out,env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup))
    (out/f'run-{lookup}-{fault}.json').write_text(json.dumps(dict(exit_code=p.returncode,fault=fault,lookup=lookup,stdout=p.stdout,stderr=p.stderr),indent=2))
    if fault:assert p.returncode==1 and'FAIL:'in p.stdout,p.stdout+p.stderr
    else:assert p.returncode==0,p.stdout+p.stderr
