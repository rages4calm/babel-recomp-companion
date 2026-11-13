"""ROM-free fixed-case effects versus the actual interp816 opcode engine.

The sparse bus defines every24-bit byte and records every access/word claim.
Only CPU-local effect semantics are tested here. Registry admission, ownership,
IRQ/NMI/deadlines and shared retirement have separate real-bridge proofs.
"""
from pathlib import Path
import hashlib,json,os,re,shutil,subprocess,sys
import pytest
import snes65816 as d
from v2.native_effects import (emit,SAFE_NAMES,STATIC_CONTROL_NAMES,STATIC_CONTROL_OPCODES,
    DIRECT_CALL_RETURN_NAMES,DIRECT_CALL_RETURN_OPCODES)

REPO=Path(__file__).resolve().parents[2]
CORE=REPO/'runner/src/snes/interp816.c'


def entries(bank,small=False):
    result=[];slot=0
    for opcode,(name,mode,size)in sorted(d.opcode_table().items()):
        if name not in SAFE_NAMES or(small and opcode not in(0xA9,0xAD,0xBD,0xB2,0xA7,0xED,0xE9,0x85,0xE6,0xEE,0xEB,0x5B)):
            continue
        if name in STATIC_CONTROL_NAMES and opcode not in STATIC_CONTROL_OPCODES:
            continue
        if name in DIRECT_CALL_RETURN_NAMES and opcode not in DIRECT_CALL_RETURN_OPCODES:
            continue
        for m,x in((0,0),(0,1),(1,0),(1,1)):
            length=size(m,x)if callable(size)else size
            for variant in range(1 if length==1 else 2):
                operand=({2:0x99,3:0x9999,4:0xFFFFFF}.get(length,0)if mode==d.IMM else
                    {2:0xFF,3:0xFFFF,4:0xFFFFFF}.get(length,0))if not variant else(
                    {2:0x01,3:0xFFFF}.get(length,0)if mode==d.IMM else{2:0x74,3:0x2140,4:0x804210}.get(length,0))
                code=bytes([opcode])+operand.to_bytes(length-1,'little')
                result.append(dict(pc24=bank<<16|0x8000+slot*4,m=m,x=x,e=0,bytes=code,mnemonic=name,immediate=mode==d.IMM))
                slot+=1
    for m,x in((0,0),(0,1),(1,0),(1,1)):
        for opcode,pc,operand in((0xA9,0xFFFD,0x9999),(0xAF,0xFFFC,0xFFFFFF),(0x0A,0xFFFF,0)):
            name,mode,size=d.opcode_table()[opcode];length=size(m,x)if callable(size)else size
            result.append(dict(pc24=bank<<16|pc,m=m,x=x,e=0,bytes=bytes([opcode])+(operand&((1<<(8*(length-1)))-1)).to_bytes(length-1,'little'),mnemonic=name,immediate=mode==d.IMM))
    return result


HARNESS=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "snes/snes_cycles.h"
static const InterpNativeInstruction *registered;static size_t count;
bool interp_bridge_add_native_instructions(const InterpNativeInstruction *items,size_t n){registered=items;count=n;return true;}
int interp816_opcode_hook(uint32_t pc){(void)pc;return 0;}
typedef struct {uint32_t adr;uint16_t value,pc,sp,dp;uint8_t kind,db,m,x,cycles;} Event;
typedef struct {uint32_t adr;uint8_t value;} Byte;
typedef struct {
 const InterpNativeInstruction *code;Interp816 *cpu;unsigned seed,fast,hook;
 Event events[40];unsigned n;Byte writes[8];unsigned nw;
 uint64_t master;unsigned accesses,read_hooks,write_hooks,claims;uint8_t openbus;
} Bus;
static int failures;static unsigned long long scenarios,checks,negatives,wordclaims;
#define CHECK(ok,...) do{checks++;if(!(ok)){if(failures++<12){printf("FAIL ");printf(__VA_ARGS__);puts("");}}}while(0)
static uint8_t initial(Bus *b,uint32_t a){
 for(unsigned i=b->nw;i;i--)if(b->writes[i-1].adr==a)return b->writes[i-1].value;
 if(a>=b->code->pc24&&a-b->code->pc24<b->code->length)return b->code->bytes[a-b->code->pc24];
 return(uint8_t)((a*1337u)^(a>>8)^(a>>17)^(b->seed*0x91919191u));
}
static void note(Bus *b,uint8_t kind,uint32_t a,uint16_t v){
 if(b->n>=40){puts("event overflow");exit(2);}Event *e=&b->events[b->n++];memset(e,0,sizeof *e);
 e->kind=kind;e->adr=a;e->value=v;e->pc=b->cpu->pc;e->sp=b->cpu->sp;e->dp=b->cpu->dp;e->db=b->cpu->db;
 e->m=b->cpu->mf;e->x=b->cpu->xf;e->cycles=b->cpu->cyclesUsed;
}
static uint8_t read8(void *mem,uint32_t a){Bus*b=mem;a&=0xFFFFFF;uint8_t v=initial(b,a);note(b,'r',a,v);b->openbus=v;b->accesses++;b->master+=snes_region_speed(a,b->fast);return v;}
static void write8(void *mem,uint32_t a,uint8_t v){Bus*b=mem;a&=0xFFFFFF;note(b,'w',a,v);b->openbus=v;b->accesses++;b->master+=snes_region_speed(a,b->fast);
 if(b->nw>=8){puts("write overflow");exit(2);}Byte*w=&b->writes[b->nw++];w->adr=a;w->value=v;}
static bool hw(uint32_t lo,uint32_t hi){return((lo>>16)&0x7F)<0x40&&(lo&65535)>=0x2000&&(lo&65535)+1<0x6000&&hi==lo+1;}
static bool readword(void *mem,uint32_t lo,uint32_t hi,uint16_t *out){Bus*b=mem;b->read_hooks++;
 if(b->hook!=2||!hw(lo,hi))return false;b->claims++;note(b,'R',lo,0);uint8_t a=read8(mem,lo);*out=a|((uint16_t)read8(mem,hi)<<8);return true;}
static bool writeword(void *mem,uint32_t lo,uint32_t hi,uint16_t value,bool reversed){Bus*b=mem;b->write_hooks++;
 if(b->hook!=2||reversed||!hw(lo,hi))return false;b->claims++;note(b,'W',lo,value);write8(mem,lo,value);write8(mem,hi,value>>8);return true;}
static Interp816 initial_cpu(Bus *b,const InterpNativeInstruction *desc,unsigned seed,unsigned carry,unsigned decimal){
 static const uint16_t values[]={0,1,0x99,0x7FFF,0x8000,0x9999,0xFF00,0xFFFF};
 static const uint16_t dps[]={0,1,0x1000,0x1FB0,0x1FFF,0xFF80,0xFFF0,0xFFFF};
 static const uint16_t sps[]={0x1FF,0x1F9,0x201,0xBFF,0x1FFF,0xFFFC,0,0xFFFF};
 static const uint8_t dbs[]={0,0x3F,0x7E,0x7F,0x80,0xBF,0xFE,0xFF};
 Interp816 c={0};c.mem=b;c.read=read8;c.write=write8;if(b->hook){c.read_word=readword;c.write_word=writeword;}
 c.a=values[seed];c.x=values[(seed+1)&7];c.y=values[(seed+3)&7];if(desc->x){c.x&=255;c.y&=255;}
 c.pc=desc->pc24;c.k=desc->pc24>>16;c.db=dbs[seed];c.dp=dps[seed];c.sp=sps[seed];c.mf=desc->m;c.xf=desc->x;
 c.c=carry;c.d=decimal;c.n=seed&1;c.z=seed&2;c.v=seed&4;c.i=seed&1;c.cyclesUsed=0xCC;return c;
}
static int cpu_equal(Interp816 a,Interp816 b){a.mem=b.mem=NULL;return!memcmp(&a,&b,sizeof a);}
static int bus_equal(const Bus*a,const Bus*b){
 return a->n==b->n&&a->nw==b->nw&&!memcmp(a->events,b->events,a->n*sizeof(Event))&&
 !memcmp(a->writes,b->writes,a->nw*sizeof(Byte))&&a->openbus==b->openbus&&a->master==b->master&&
 a->accesses==b->accesses&&a->read_hooks==b->read_hooks&&a->write_hooks==b->write_hooks&&a->claims==b->claims;
}
int main(void){
 CHECK(RegisterEffects(),"registration");CHECK(count>0,"descriptors");
 for(size_t i=0;i<count;i++)for(unsigned seed=0;seed<8;seed++)for(unsigned carry=0;carry<2;carry++)for(unsigned decimal=0;decimal<2;decimal++)for(unsigned fast=0;fast<2;fast++)for(unsigned hook=0;hook<3;hook++){
  const InterpNativeInstruction*d=&registered[i];Bus a={0},b={0};a.code=b.code=d;a.seed=b.seed=seed;a.fast=b.fast=fast;a.hook=b.hook=hook;
  Interp816 ref=initial_cpu(&a,d,seed,carry,decimal),got=initial_cpu(&b,d,seed,carry,decimal);a.cpu=&ref;b.cpu=&got;
  int rc=interp816_runOpcode(&ref);uint64_t before_i=interp816_insns_total(),before_c=interp816_cycles_total();int nc=d->step(&got);scenarios++;
  wordclaims+=b.claims;
  a.master+=(unsigned)rc>a.accesses?((unsigned)rc-a.accesses)*6u:0;b.master+=(unsigned)nc>b.accesses?((unsigned)nc-b.accesses)*6u:0;
  CHECK(rc==nc&&cpu_equal(ref,got),"CPU op%02x M%uX%u seed%u C%uD%u hook%u pc%04x/%04x cycles%d/%d",d->bytes[0],d->m,d->x,seed,carry,decimal,hook,ref.pc,got.pc,rc,nc);
  CHECK(bus_equal(&a,&b),"bus/order/virtual memory/master op%02x M%uX%u seed%u hook%u events%u/%u",d->bytes[0],d->m,d->x,seed,hook,a.n,b.n);
  CHECK(before_i==interp816_insns_total()&&before_c==interp816_cycles_total(),"native must never execute decoder");
 }
 /* Negative control: substituting the real opcode engine preserves effects
  * but MUST be detected as interpreted work by the accounting oracle. */
 {const InterpNativeInstruction*d=&registered[0];Bus b={0};b.code=d;Interp816 c=initial_cpu(&b,d,0,0,0);b.cpu=&c;
  uint64_t before=interp816_insns_total();(void)interp816_runOpcode(&c);CHECK(interp816_insns_total()==before+1,"decoder relabel negative detects instruction");negatives++;}
 for(size_t i=0;i<count;i++){
  const InterpNativeInstruction*d=&registered[i];Bus b={0};b.code=d;Interp816 c=initial_cpu(&b,d,0,0,0);b.cpu=&c;
  c.mf=!d->m;Interp816 before=c;CHECK(d->step(&c)==0&&cpu_equal(c,before)&&!b.n,"wrongM pure decline");
  c.mf=d->m;c.xf=!d->x;before=c;CHECK(d->step(&c)==0&&cpu_equal(c,before)&&!b.n,"wrongX pure decline");
  c.xf=d->x;c.e=1;before=c;CHECK(d->step(&c)==0&&cpu_equal(c,before)&&!b.n,"E1 pure decline");
  c.e=0;c.k^=0x80;before=c;CHECK(d->step(&c)==0&&cpu_equal(c,before)&&!b.n,"wrongPB pure decline");
  c.k=d->pc24>>16;c.pc++;before=c;CHECK(d->step(&c)==0&&cpu_equal(c,before)&&!b.n,"wrongPC pure decline");
 }
 CHECK(wordclaims>0,"claimed hardware word paths executed");
 printf("descriptors=%zu scenarios=%llu negatives=%llu wordclaims=%llu checks=%llu failures=%d\n",count,scenarios,negatives,wordclaims,checks,failures);
#ifdef EXPECT_FETCH_MUTANT
 return failures?0:1;
#else
 return failures?1:0;
#endif
}
'''


def run_fixture(tmp_path,bank,small=False,mutant=None,extra_entries=()):
    compiler=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not compiler:pytest.skip('C11 compiler required')
    generated,receipt=emit(CORE.read_text(),entries(bank,small)+list(extra_entries),registration_name='RegisterEffects')
    assert not re.search(r'\b(?:interp816_|ni_\d\d_)(?:runOpcode|doOpcode)\s*\(',generated)
    fetch='(void)cpu->read(cpu->mem, _ni->base + n);'
    if mutant=='skip_fetch':
        assert fetch in generated
        generated=generated.replace(fetch,'(void)0; /* deliberate missing bus fetch */')
    elif mutant=='double_fetch':
        assert fetch in generated
        generated=generated.replace(fetch,fetch+'\n  '+fetch)
    elif mutant=='stale_operand':
        pattern=r'(static const uint8_t code\[\] = \{0xA9,)0x99'
        generated,n=re.subn(pattern,r'\g<1>0x98',generated,count=1)
        assert n==1
    elif mutant=='stale_branch_operand':
        pattern=r'(static const uint8_t code\[\] = \{0xD0,)0x7F'
        generated,n=re.subn(pattern,r'\g<1>0x7E',generated,count=1)
        assert n==1
    elif mutant=='stale_status_width':
        assignment='cpu->mf = val & 0x20;'
        assert assignment in generated
        generated=generated.replace(assignment,'(void)val; /* deliberate stale M */')
    elif mutant=='stale_index_high':
        assert 'cpu->x &= 0xff;' in generated and 'cpu->y &= 0xff;' in generated
        generated=generated.replace('cpu->x &= 0xff;','(void)0; /* deliberate stale X high */')
        generated=generated.replace('cpu->y &= 0xff;','(void)0; /* deliberate stale Y high */')
    elif mutant=='bad_stack_order':
        pattern=r'(ni_\d\d_pushByte\(cpu, _ni, )value >> 8'
        generated,n=re.subn(pattern,r'\g<1>value & 0xff',generated)
        assert n
    elif mutant is not None:raise AssertionError(mutant)
    if mutant:generated='#define EXPECT_FETCH_MUTANT 1\n'+generated
    source=tmp_path/'effects.c';source.write_text(generated+HARNESS)
    exe=tmp_path/('effects.exe'if os.name=='nt'else'effects')
    command=[compiler,'-std=c11','-O1','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),str(source),str(CORE),'-o',str(exe)]
    compiled=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (tmp_path/'compile.json').write_text(json.dumps(dict(command=command,exit_code=compiled.returncode,stdout=compiled.stdout,stderr=compiled.stderr),indent=2))
    assert compiled.returncode==0,compiled.stdout+compiled.stderr
    result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=45)
    (tmp_path/'execution.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),emission=receipt,expected_negative_mutant=mutant,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2))
    assert result.returncode==0,result.stdout+result.stderr
    failures=int(re.search(r'failures=(\d+)',result.stdout)[1])
    assert failures>0 if mutant else failures==0


def test_first_generated_effects_real_core(tmp_path):
    run_fixture(tmp_path,0x83,True)


@pytest.mark.parametrize('bank',[0x03,0x43,0x83,0xC3])
def test_all_safe_effects_real_core(tmp_path,bank):
    run_fixture(tmp_path,bank)


@pytest.mark.parametrize('bank',[0x03,0x43,0x83,0xC3])
def test_static_control_targets_flags_and_pc_wrap(tmp_path,bank):
    # Full SAFE matrix already covers every static-control opcode. This extra
    # cohort concentrates on BNE/BRA/BRL and directJMP/JML boundary targets.
    extras=[]
    for index,opcode in enumerate((0xD0,0x80,0x82,0x4C,0x5C)):
        name,mode,size=d.opcode_table()[opcode];length=size(0,0)if callable(size)else size
        for m,x in((0,0),(0,1),(1,0),(1,1)):
            position=0xE000+index*0x100
            operand={2:0x80,3:0x8000,4:0x7EFFFF}[length]
            extras.append(dict(pc24=bank<<16|position,m=m,x=x,e=0,bytes=bytes([opcode])+operand.to_bytes(length-1,'little'),mnemonic=name,immediate=False))
    # Separate boundary position per width/opcode so no duplicate keys.
    # BNE atFFFE wraps sequentialPC to0, then signed+127; BRL atFFFA
    # has positive displacement wrapping through0; JML changes livePB.
    for opcode,position,operand in((0xD0,0xFFFE,0x7F),(0x82,0xFFFA,0x7FFF),(0x4C,0xFFF6,0xFFFF),(0x5C,0xFFF2,0xC30001)):
        name,mode,size=d.opcode_table()[opcode];length=size(0,0)if callable(size)else size
        for m,x in((0,0),(0,1),(1,0),(1,1)):
            extras.append(dict(pc24=bank<<16|position,m=m,x=x,e=0,bytes=bytes([opcode])+operand.to_bytes(length-1,'little'),mnemonic=name,immediate=False))
    run_fixture(tmp_path,bank,True,extra_entries=extras)


def test_oracle_rejects_stale_branch_target(tmp_path):
    extra=dict(pc24=0x83FFFE,m=0,x=0,e=0,bytes=b'\xD0\x7F',mnemonic='BNE',immediate=False)
    run_fixture(tmp_path,0x83,True,'stale_branch_operand',[extra])


@pytest.mark.parametrize('mutant',['skip_fetch','double_fetch','stale_operand'])
def test_oracle_rejects_missing_duplicate_fetch_and_stale_operand(tmp_path,mutant):
    run_fixture(tmp_path,0x83,True,mutant)


def test_repeatable_across_process_hash_randomization(tmp_path):
    script='''import sys,hashlib,json;from pathlib import Path
sys.path.insert(0,sys.argv[1]);import snes65816 as d
from v2.native_effects import emit
e=[dict(pc24=0x838100,m=0,x=0,e=0,bytes=bytes.fromhex("6D FF FF"),mnemonic="ADC",immediate=False),dict(pc24=0x838200,m=1,x=0,e=0,bytes=bytes.fromhex("A7 74"),mnemonic="LDA",immediate=False)]
s,r=emit(Path(sys.argv[2]).read_text(),e);print(json.dumps(dict(hash=hashlib.sha256(s.encode()).hexdigest(),salt=hash("native effects"))))'''
    results=[]
    for seed in('13','37','91'):
        env=dict(os.environ,PYTHONHASHSEED=seed)
        p=subprocess.run([sys.executable,'-X','utf8','-c',script,str(REPO/'recompiler'),str(CORE)],env=env,capture_output=True,text=True,timeout=20)
        assert p.returncode==0,p.stderr
        results.append(json.loads(p.stdout))
    (tmp_path/'repeatability.json').write_text(json.dumps(results,indent=2))
    assert len({x['hash']for x in results})==1


@pytest.mark.parametrize('change',[{'mnemonic':'NOP'},{'bytes':b'\xA9'},{'immediate':False},{'e':1},{'m':True},{'bytes':[0xA9,0x99,0x99]}])
def test_invalid_descriptor_refused(change):
    entry=dict(pc24=0x838100,m=0,x=0,e=0,bytes=b'\xA9\x99\x99',mnemonic='LDA',immediate=True)
    entry.update(change)
    with pytest.raises(ValueError):emit(CORE.read_text(),[entry])


@pytest.mark.parametrize('opcode',[0x6C,0xDC])
def test_indirect_jump_descriptors_refused(opcode):
    name,mode,size=d.opcode_table()[opcode]
    entry=dict(pc24=0x838100,m=0,x=0,e=0,bytes=bytes([opcode,0x00,0x80]),mnemonic=name,immediate=False)
    with pytest.raises(ValueError,match='static or indexed-indirect jump'):
        emit(CORE.read_text(),[entry])


def test_indirect_jsr_descriptor_refused():
    entry=dict(pc24=0x838000,m=0,x=0,e=0,bytes=bytes.fromhex('fc0090'),mnemonic='JSR',immediate=False)
    with pytest.raises(ValueError,match='direct call/return'):
        emit(CORE.read_text(),[entry])


def test_full_uint16_descriptor_range_and_overflow():
    entries=[dict(pc24=0x808000+i//4,m=(i>>1)&1,x=i&1,e=0,
                  bytes=b'\xea',mnemonic='NOP',immediate=False)for i in range(65535)]
    generated,receipt=emit(CORE.read_text(),entries)
    assert receipt['entries']==65535
    assert generated.count('static int ni_at_')==65535
    assert 'ni_at_80BFFF_10}'in generated
    with pytest.raises(ValueError,match='bounded nonempty'):
        emit(CORE.read_text(),entries+[dict(entries[-1],pc24=0x80c000)])


def test_optional_nmi_scope_is_explicit_and_fail_closed():
    entry=dict(pc24=0x838100,m=0,x=0,e=0,bytes=b'\xea',mnemonic='NOP',immediate=False)
    key=(entry['pc24'],0,0,0);source=CORE.read_text()
    assert emit(source,[entry])==emit(source,[entry],nmi_owner_pc24=None,nmi_keys=[])
    for owner,keys in ((None,[key]),(True,[key]),(0x7e8500,[key]),(0x8500,[]),
                       (0x8500,[key,key]),(0x8500,[(0x838101,0,0,0)]),
                       (0x8500,[(entry['pc24'],False,0,0)])):
        with pytest.raises(ValueError):emit(source,[entry],nmi_owner_pc24=owner,nmi_keys=keys)
    for opcode in (0x08,0x28,0x48,0x68,0xda,0xfa,0x5a,0x7a,0x0b,0x2b,0x8b,0xab,0x4b,0xf4,0x62,0xd4,0x20,0x22,0x60,0x6b):
        name,mode,size=d.opcode_table()[opcode];length=size(0,0)if callable(size)else size
        row=dict(entry,bytes=bytes([opcode])+bytes(length-1),mnemonic=name)
        generated,_=emit(source,[row],nmi_owner_pc24=0x8500,nmi_keys=[key])
        assert 'interp_bridge_allow_native_nmi_instructions' in generated
    row=dict(entry,bytes=bytes.fromhex('7c0090'),mnemonic='JMP')
    with pytest.raises(ValueError,match='NMI data site'):
        emit(source,[row],nmi_owner_pc24=0x8500,nmi_keys=[key])


def test_jsr_afc7_diagnostic_preserves_environment_presence(tmp_path):
    """Babel's optional trace is part of the extracted JSR behavior too."""
    row=dict(pc24=0x838000,m=1,x=1,e=0,bytes=bytes.fromhex('20c7af'),mnemonic='JSR',immediate=False)
    generated,receipt=emit(CORE.read_text(),[row],registration_name='RegisterEffects')
    harness=HARNESS[:HARNESS.index('int main(void){')]+r'''
int main(void){
 CHECK(RegisterEffects(),"registration");Bus a={0},b={0};a.code=b.code=&registered[0];
 Interp816 ref=initial_cpu(&a,a.code,3,1,0),got=initial_cpu(&b,b.code,3,1,0);a.cpu=&ref;b.cpu=&got;
 int rc=interp816_runOpcode(&ref);uint64_t n=interp816_insns_total();int nc=registered[0].step(&got);
 CHECK(rc==nc&&cpu_equal(ref,got)&&bus_equal(&a,&b),"trace retains actual JSR effects and ordered stack accesses");
 CHECK(interp816_insns_total()==n,"trace does not decode native instruction");return failures?1:0;
}
'''
    source=tmp_path/'trace.c';source.write_text(generated+harness,encoding='utf-8')
    cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    exe=tmp_path/('trace.exe'if os.name=='nt'else'trace')
    command=[cc,'-std=c11','-O1','-I',str(REPO/'runner/src'),str(source),str(CORE),'-o',str(exe)]
    p=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (tmp_path/'compile.json').write_text(json.dumps(dict(command=command,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
    assert p.returncode==0,p.stdout+p.stderr
    results=[]
    for value in (None,'','0','1'):
        env=dict(os.environ);env.pop('SNESRECOMP_JSR_AFC7_TRACE',None)
        if value is not None:env['SNESRECOMP_JSR_AFC7_TRACE']=value
        p=subprocess.run([str(exe)],capture_output=True,text=True,env=env,timeout=10)
        results.append(dict(value=value,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        assert p.returncode==0,p.stdout+p.stderr
        lines=p.stderr.splitlines()
        assert len(lines)==(0 if value is None else 2)
        if lines:assert lines[0]==lines[1]and lines[0].startswith('[jsr_afc7] from=83:8000')
    (tmp_path/'diagnostic-presence.json').write_text(json.dumps(dict(emission=receipt,runs=results),indent=2))


def test_code_operand_bank_wrap_remains_refused():
    entry=dict(pc24=0x83FFFF,m=0,x=0,e=0,bytes=b'\xD0\x7F',mnemonic='BNE',immediate=False)
    with pytest.raises(ValueError):emit(CORE.read_text(),[entry])


def status_stack_entries(bank, all_masks=False):
    """Fixed masks exercise live status writes and every data-stack opcode."""
    result=[];slot=0
    for opcode in (0xC2,0xE2):
        for m,x in ((0,0),(0,1),(1,0),(1,1)):
            for mask in range(256) if all_masks else (0,4,8,0x10,0x20,0x30,0xCF,0xFF):
                result.append(dict(pc24=bank<<16|0xC000+slot*4,m=m,x=x,e=0,
                    bytes=bytes((opcode,mask)),mnemonic='REP' if opcode==0xC2 else 'SEP',immediate=True))
                slot+=1
    # Use disjoint addresses even in the full2048-mask cohort.
    for opcode in (0x08,0x28,0x48,0x68,0xDA,0xFA,0x5A,0x7A,0x0B,0x2B,0x4B,0x8B,0xAB,0x62,0xD4,0xF4):
        name,mode,size=d.opcode_table()[opcode]
        for m,x in ((0,0),(0,1),(1,0),(1,1)):
            length=size(m,x) if callable(size) else size
            for operand in ((0xC2AE,0xC2AF,0xFFFF) if opcode==0xF4 else (0xFF,)):
                result.append(dict(pc24=bank<<16|0xE400+(slot-2048 if all_masks else slot)*4,m=m,x=x,e=0,
                    bytes=bytes((opcode,))+(operand&((1<<(8*(length-1)))-1)).to_bytes(length-1,'little'),
                    mnemonic=name,immediate=mode==d.IMM))
                slot+=1
    return result


def test_all_status_masks_and_data_stack_actual_core(tmp_path):
    # Source PEA has a Babel-specific C2AE→Y0 rule; preserve it and its C2AF
    # control rather than claiming this fixture independently proves hardwareISA.
    run_fixture(tmp_path,0x83,True,extra_entries=status_stack_entries(0x83,True))


@pytest.mark.parametrize('mutant',['stale_status_width','stale_index_high','bad_stack_order'])
def test_status_stack_oracle_rejects_mutated_effects(tmp_path,mutant):
    run_fixture(tmp_path,0x83,True,mutant,status_stack_entries(0x83))
