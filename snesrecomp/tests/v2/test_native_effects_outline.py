"""Optional exact-key outlining keeps guarded callbacks and real retirement.

All byte programs are synthetic. The CPU/bus oracle is the actual opcode
engine; owner/COP/NMI cases reuse real bridge/device fixtures.
"""
from pathlib import Path
import functools,hashlib,json,os,re,shutil,subprocess
import pytest
import snes65816 as decoder
from v2.native_effects import emit
from test_native_effects import CORE,REPO,HARNESS,entries
from test_region_pacing import _c_function


def key(row):return row['pc24'],row['m'],row['x'],row['e']


def frame_rows():
    return [dict(pc24=(bank<<16)|pc,m=m,x=x,e=0,bytes=code,
                 mnemonic=name,immediate=decoder.opcode_table()[code[0]][1]==decoder.IMM)
            for bank in (0x03,0x43,0x83,0xC3)
            for pc,code,name in ((0xE800,b'\x02\x00','COP'),(0xE810,b'\x40','RTI'))
            for m in range(2)for x in range(2)]


def test_exact_groups_keep_literal_wrappers_and_policy_tables():
    rows=frame_rows()+[dict(pc24=(bank<<16)|0xE820,m=0,x=x,e=0,
                         bytes=b'\xA9\x99\x99',mnemonic='LDA',immediate=True)
                         for bank in (0x03,0x43,0x83,0xC3)for x in range(2)]
    kwargs=dict(frame_keys=[key(r)for r in rows if r['mnemonic']in('COP','RTI')],
                nmi_owner_pc24=0x00800B,nmi_keys=[key(r)for r in rows],
                scope_limits=[(key(r),3)for r in rows])
    source=CORE.read_text();legacy,old=emit(source,rows,**kwargs)
    outlined,receipt=emit(source,rows,outline_effects=True,**kwargs)
    marker='static const InterpNativeInstruction ni_entries[] = {'
    assert legacy[legacy.index(marker):]==outlined[outlined.index(marker):]
    groups={(r['bytes'],r['m'],r['x'],r['e'],r['immediate'])for r in rows}
    assert receipt['outlined_effect_bodies']==len(groups)==10
    assert receipt['outlined_effect_wrappers']==len(rows)==40
    assert receipt['native_nmi_grants']==old['native_nmi_grants']==40
    assert receipt['native_frame_grants']==old['native_frame_grants']==32
    assert 'NI_NOINLINE'not in legacy
    assert outlined.count('static NI_NOINLINE int ni_effect_')==len(groups)
    for row in rows:
        symbol=f"ni_at_{row['pc24']:06X}_{row['m']}{row['x']}"
        a=_c_function(legacy,symbol);b=_c_function(outlined,symbol)
        assert a.split('return 0;',1)[0]==b.split('return 0;',1)[0]
        assert re.search(r'return ni_effect_\d+\(cpu, 0x'+f"{row['pc24']:06X}"+r'u\);',b)
        assert 'cpu->cyclesUsed ='not in b


@pytest.mark.parametrize('invalid',[0,1,None,'true'])
def test_outlining_requires_explicit_bool(invalid):
    with pytest.raises(ValueError,match='explicit bool'):
        emit(CORE.read_text(),frame_rows(),frame_keys=[key(r)for r in frame_rows()],outline_effects=invalid)


def compiler():
    cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    return cc


def compile_run(out,source,files,args=(),defines=(),expected_failure=False):
    src=out/'outline.c';src.write_text(source,encoding='utf-8');exe=out/('outline.exe'if os.name=='nt'else'outline')
    command=[compiler(),'-std=c11','-O1',*defines,'-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),
             '-I',str(REPO/'tests/dma'),str(src),*[str(p)for p in files],'-lm','-o',str(exe)]
    p=subprocess.run(command,capture_output=True,text=True,timeout=120)
    (out/'compile.json').write_text(json.dumps(dict(command=command,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
    assert p.returncode==0,p.stdout+p.stderr
    for index,(parameters,environment)in enumerate(args or[((),{})]):
        p=subprocess.run([str(exe),*parameters],env=dict(os.environ,**environment),capture_output=True,text=True,timeout=120,cwd=out)
        (out/f'run-{index}.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),args=parameters,environment=environment,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
        assert p.returncode==0,p.stdout+p.stderr
        if expected_failure:assert re.search(r'failures=[1-9]',p.stdout),p.stdout
        else:assert 'failures=0'in p.stdout,p.stdout


POLICY=r'''
static bool same_policy_callback(const InterpNativeInstruction *items,size_t n){
 for(size_t i=0;i<n;i++){
  bool found=false;
  for(size_t j=0;j<count;j++)if(items[i].pc24==registered[j].pc24&&items[i].m==registered[j].m&&items[i].x==registered[j].x&&items[i].e==registered[j].e){
   if(items[i].step!=registered[j].step||items[i].length!=registered[j].length||memcmp(items[i].bytes,registered[j].bytes,4))return false;
   found=true;break;
  }if(!found)return false;
 }return true;
}
bool interp_bridge_restrict_native_instructions(const InterpNativeInstruction *p,size_t n,unsigned flags){return flags==3&&same_policy_callback(p,n);}
bool interp_bridge_allow_native_frame_instructions(const InterpNativeInstruction *p,size_t n){return same_policy_callback(p,n);}
bool interp_bridge_allow_native_nmi_instructions(uint32_t owner,const InterpNativeInstruction *p,size_t n){return owner==0x00800B&&same_policy_callback(p,n);}
'''


@pytest.mark.parametrize('mutant',[False,True])
def test_outlined_all_effects_real_opcode_bus_and_physical_keys(tmp_path,mutant):
    rows=[r for bank in(0x03,0x43,0x83,0xC3)for r in entries(bank)]+frame_rows()
    generated,receipt=emit(CORE.read_text(),rows,registration_name='RegisterEffects',outline_effects=True,
        frame_keys=[key(r)for r in frame_rows()],nmi_owner_pc24=0x00800B,
        nmi_keys=[key(r)for r in rows if r['bytes'][0]!=0x7C],scope_limits=[(key(r),3)for r in rows])
    if mutant:
        generated,n=re.subn(r'(return ni_effect_\d+\(cpu, )0x03',r'\g<1>0x43',generated,count=1)
        assert n==1
    harness=HARNESS.replace('int interp816_opcode_hook',POLICY+'\nint interp816_opcode_hook')
    harness=harness.replace('CHECK(wordclaims>0,',r'''
 for(size_t i=0;i<count;i++){
  const InterpNativeInstruction*d=&registered[i];Bus b={0};b.code=d;Interp816 c=initial_cpu(&b,d,0,0,0);b.cpu=&c;
  CHECK(d->step(NULL)==0,"NULL callback pure decline");c.read=NULL;Interp816 before=c;
  CHECK(d->step(&c)==0&&cpu_equal(c,before)&&!b.n,"NULL reader pure decline");
  for(size_t j=i+1;j<count;j++)CHECK(d->step!=registered[j].step,"different physical/mode key retains distinct guarded callback");
 }
 CHECK(wordclaims>0,''')
    if mutant:harness='#define EXPECT_FETCH_MUTANT 1\n'+harness
    (tmp_path/'emission.json').write_text(json.dumps(receipt,indent=2))
    compile_run(tmp_path,generated+harness,[CORE],expected_failure=mutant)


def test_outlined_indexed_indirect_jump_bus_and_live_pointer(tmp_path):
    rows=[dict(pc24=(bank<<16)|0xE840,m=m,x=x,e=0,bytes=b'\x7C\xFF\xFF',
               mnemonic='JMP',immediate=False)
          for bank in(0x03,0x43,0x83,0xC3)for m in range(2)for x in range(2)]
    # Keep a real claimed hardware-word read as an active bus-oracle control.
    rows.append(dict(pc24=0x838100,m=0,x=0,e=0,bytes=b'\xAD\x40\x21',mnemonic='LDA',immediate=False))
    generated,_=emit(CORE.read_text(),rows,registration_name='RegisterEffects',outline_effects=True)
    compile_run(tmp_path,generated+HARNESS,[CORE])


@pytest.mark.parametrize('kind',['branch','call','frame','nmi-frame'])
def test_outlined_actual_bridge_owners_frames_devices_and_deadlines(tmp_path,monkeypatch,kind):
    outlined=functools.partial(emit,outline_effects=True)
    if kind=='branch':
        import test_native_branch_continuation as fixture
        monkeypatch.setattr(fixture,'emit',outlined);source,_=fixture._source();parameters=[('0',)]
    elif kind=='call':
        import test_native_call_continuation as fixture
        monkeypatch.setattr(fixture,'emit',outlined);source,_=fixture._source();parameters=[('0',),('99',)]
    else:
        import test_native_frame_continuation as fixture
        monkeypatch.setattr(fixture,'emit',outlined);source,_=fixture.bridge_source(kind=='nmi-frame')
        parameters=[(str(mode),)for mode in range(3)]if kind=='frame'else[(str(owner),str(mode))for owner in(0,3)for mode in range(3)]
    common=['interp816.c','interp_bridge.c','tier2_capture.c','cx4.c','dma.c','sdd1.c']
    if kind in('branch','call'):
        core=tmp_path/'snes_core.c';core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n')
        files=[core,*[REPO/'runner/src/snes'/n for n in common],REPO/'runner/src/sha256.c']
    else:
        files=[*[REPO/'runner/src/snes'/n for n in common+['snes.c','apu.c','spc.c','dsp.c','dsp_clock.c']],REPO/'runner/src/sha256.c']
    args=[(values,dict(SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup))for lookup in('0','1')for values in parameters]
    compile_run(tmp_path,source,files,args,defines=('-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0'))
