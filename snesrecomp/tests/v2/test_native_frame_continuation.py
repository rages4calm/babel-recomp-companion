"""Explicit COP/RTI fixed effects retain real frames and the owning bridge.

Synthetic programs only. No replacement scheduler, repaired frame or opcode
engine call inside a native effect. Actual devices/retirement are compared.
"""
import hashlib,json,os,re,shutil,subprocess
import pytest
import snes65816 as decoder
from v2.native_effects import emit
from test_native_effects import HARNESS,CORE,REPO as EFFECT_REPO
from test_native_cop_continuation import _source as cop_source,_program as cop_program,REPO
from test_native_nmi_continuation import _source as nmi_source
from test_region_pacing import _c_function


def frame_entry(pc,opcode,m,x):
    name,mode,size=decoder.opcode_table()[opcode]
    length=size(m,x)if callable(size)else size
    return dict(pc24=pc,m=m,x=x,e=0,bytes=bytes([opcode])+bytes(length-1),mnemonic=name,immediate=mode==decoder.IMM)


def key(row):return row['pc24'],row['m'],row['x'],row['e']


def test_frame_generation_requires_exact_opt_in():
    source=CORE.read_text();rows=[frame_entry(0x838100,2,0,0),frame_entry(0x838102,0x40,0,0)]
    for row in rows:
        with pytest.raises(ValueError,match='explicit frame-effect'):emit(source,[row])
    keys=[key(r)for r in rows]
    for invalid in (keys+[keys[0]],[(0x838100,False,0,0)],keys+[(0x838103,0,0,0)]):
        with pytest.raises(ValueError):emit(source,rows,frame_keys=invalid)
    generated,receipt=emit(source,rows,frame_keys=keys,nmi_owner_pc24=0x8500,nmi_keys=keys)
    assert receipt['native_frame_grants']==receipt['native_nmi_grants']==2
    assert generated.index('if (!interp_bridge_allow_native_frame_instructions')<generated.index('return interp_bridge_allow_native_nmi_instructions')
    assert not re.search(r'\b(?:interp816_|ni_\w+_)(?:runOpcode|doOpcode|doInterrupt)\s*\(',generated)


@pytest.mark.parametrize('mutant',[None,'bad_status','bad_cycle','missing_signature_fetch'])
def test_frame_effects_match_actual_opcode_cpu_bus_and_cycles(tmp_path,mutant):
    rows=[frame_entry(0x838100+i*8,op,m,x)for i,(op,m,x)in enumerate((o,m,x)for o in(2,0x40)for m in range(2)for x in range(2))]
    # The unchanged matrix also exercises a claimed hardware-word path.
    rows.append(dict(pc24=0x838200,m=0,x=0,e=0,bytes=bytes.fromhex('ad4021'),mnemonic='LDA',immediate=False))
    generated,receipt=emit(CORE.read_text(),rows,registration_name='RegisterEffects',frame_keys=[key(r)for r in rows[:-1]])
    if mutant=='bad_status':generated=generated.replace('cpu->i = true;','cpu->i = false;')
    if mutant=='bad_cycle':generated=generated.replace('cpu->cyclesUsed++; // native mode: 1 extra cycle','cpu->cyclesUsed += 2; // deliberately wrong')
    if mutant=='missing_signature_fetch':generated=re.sub(r'(?m)^\s*ni_\d\d_readOpcode\(cpu, _ni\);\s*$', '',generated)
    stub='bool interp_bridge_allow_native_frame_instructions(const InterpNativeInstruction *p,size_t n){return p&&n==8;}\n'
    harness=HARNESS.replace('int interp816_opcode_hook',stub+'int interp816_opcode_hook')
    if mutant:harness='#define EXPECT_FETCH_MUTANT 1\n'+harness
    cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    src=tmp_path/'frame.c';src.write_text(generated+harness);exe=tmp_path/('frame.exe'if os.name=='nt'else'frame')
    command=[cc,'-std=c11','-O1','-I',str(EFFECT_REPO/'runner/src'),str(src),str(CORE),'-o',str(exe)]
    p=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (tmp_path/'compile.json').write_text(json.dumps(dict(command=command,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)))
    assert p.returncode==0,p.stdout+p.stderr
    p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
    (tmp_path/'run.json').write_text(json.dumps(dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,emission=receipt)))
    assert p.returncode==0,p.stdout+p.stderr
    assert ('FAIL 'in p.stdout)==bool(mutant)


def bridge_source(nmi=False,mutant=None):
    text,_=nmi_source()if nmi else cop_source()
    raw,_=cop_program();frames=[]
    # Main COP and nested COP/RTI inside the actual synthetic handler.
    for m in range(2):
        for x in range(2):frames.append(frame_entry(0x829000,2,m,x))
    offset=0;m=x=1
    while offset<len(raw):
        opcode=raw[offset];name,mode,size=decoder.opcode_table()[opcode];length=size(m,x)if callable(size)else size
        if opcode in(2,0x40):
            modes=[(a,b)for a in range(2)for b in range(2)]if opcode==0x40 else[(m,x)]
            frames.extend(frame_entry(0x8100+offset,opcode,a,b)for a,b in modes)
        if opcode==0xc2:
            if raw[offset+1]&0x20:m=0
            if raw[offset+1]&0x10:x=0
        if opcode==0xe2:
            if raw[offset+1]&0x20:m=1
            if raw[offset+1]&0x10:x=1
        offset+=length
    # Read exact existing descriptors from the generated synthetic output.
    start=text.index('static const InterpNativeInstruction ni_entries[] = {');end=text.index('\n};',start)
    entries=[]
    for pc,m,x,length,code in re.findall(r'\{0x([0-9A-F]+)u,([01]),([01]),0,(\d),\{([^}]+)\},ni_at_',text[start:end]):
        code=bytes(int(z,16)for z in code.split(','));name,mode,_=decoder.opcode_table()[code[0]]
        entries.append(dict(pc24=int(pc,16),m=int(m),x=int(x),e=0,bytes=code,mnemonic=name,immediate=mode==decoder.IMM))
    if nmi:
        # The finite NMI's main program has its own COP and terminal RTI.
        # nmi_source publishes its synthetic instruction stream as memcpy data.
        code_match=re.search(r'const uint8_t handler\[\]=\{([^}]+)\}',text)
        assert code_match,'NMI synthetic code declaration changed'
        nraw=bytes(int(v.strip(),0)for v in code_match[1].split(','));offset=0;m=x=0
        # Main829000 is PHP rather than COP in this fixture.
        frames=[r for r in frames if r['pc24']!=0x829000]
        while offset<len(nraw):
            op=nraw[offset];_,_,size=decoder.opcode_table()[op];length=size(m,x)if callable(size)else size
            if op in(2,0x40):
                modes=[(a,b)for a in range(2)for b in range(2)]if op==0x40 else[(m,x)]
                frames.extend(frame_entry(0x829000+offset,op,a,b)for a,b in modes)
            if op==0xc2:
                if nraw[offset+1]&0x20:m=0
                if nraw[offset+1]&0x10:x=0
            if op==0xe2:
                if nraw[offset+1]&0x20:m=1
                if nraw[offset+1]&0x10:x=1
            offset+=length
    allrows=entries+frames;fkeys=[key(r)for r in frames]
    generated,receipt=emit(CORE.read_text(),allrows,registration_name='RegisterMmio',frame_keys=fkeys)
    if mutant=='frame_cycle':
        for row in frames:
            name=f'ni_at_{row["pc24"]:06X}_{row["m"]}{row["x"]}'
            body=_c_function(generated,name);assert 'cpu->cyclesUsed++;'in body
            generated=generated.replace(body,body.replace('cpu->cyclesUsed++;','cpu->cyclesUsed += 2;'))
    a=text.index('/* PRIVATE ROM-derived continuations;');function=_c_function(text,'RegisterMmio');b=text.index(function)+len(function)
    text=text[:a]+generated+text[b:]
    marker='static unsigned nmi_variant'if nmi else'static unsigned cop_fault'
    text=text.replace(marker,'static unsigned frame_mode;\n'+marker,1)
    a=text.index('    CHECK(RegisterMmio(),"production-emitted')if nmi else text.index('    InterpNativeInstruction items[256]')
    b=text.index(' event_count=0;',a)
    registration=r'''
    size_t n=sizeof ni_entries/sizeof *ni_entries;
    CHECK(interp_bridge_add_native_instructions(ni_entries,n),"fixed frame descriptors registered");
    CHECK(!interp_bridge_native_frame_grants(),"registration alone grants no frame execution");
    InterpNativeInstruction bad[2]={ni_frame_entries[0],ni_frame_entries[1]};bad[1].step=NULL;
    CHECK(!interp_bridge_allow_native_frame_instructions(bad,2)&&!interp_bridge_native_frame_grants(),"late invalid frame descriptor changes no grants");
    if(frame_mode!=2){CHECK(interp_bridge_allow_native_frame_instructions(ni_frame_entries,sizeof ni_frame_entries/sizeof *ni_frame_entries),"explicit fixed frame permission");}
    interp_bridge_set_native_frame_effects_enabled(frame_mode!=1);
    CHECK(interp_bridge_add_native_instructions(ni_entries,n),"idempotent rebuild preserves frame grants");
'''
    if nmi:
        registration+=r'''
    InterpNativeInstruction grants[256];size_t count=0;
    for(size_t i=0;i<n;i++)if(frame_mode!=2||(ni_entries[i].bytes[0]!=2&&ni_entries[i].bytes[0]!=0x40))grants[count++]=ni_entries[i];
    CHECK(interp_bridge_allow_native_nmi_instructions(nmi_variant==3?0x8501:0x8500,grants,count),"independent exact NMI owner grant");
    nmi_hook_calls=0;interp_bridge_add_pre_opcode_hook(0x829000,nmi_active_hook);
'''
    else:registration+='    cop_fired=0;if(dma_enabled)interp_bridge_add_pre_opcode_hook(0x008100,cop_interrupt);\n'
    text=text[:a]+registration+text[b:]
    # Active frames cannot toggle permission or the launch switch.
    if nmi:
        text=text.replace('size_t count=interp_bridge_native_instruction_stats(NULL,0),grants=',
            'CHECK(!interp_bridge_allow_native_frame_instructions(ni_frame_entries,1),"active frame grant refused");interp_bridge_set_native_frame_effects_enabled(false);\n size_t count=interp_bridge_native_instruction_stats(NULL,0),grants=')
    text=text.replace('cop_fault=argc>1?atoi(argv[1]):0;','cop_fault=0;frame_mode=argc>1?atoi(argv[1]):0;')
    if nmi:text=text.replace('nmi_variant=argc>1?atoi(argv[1]):0;','nmi_variant=argc>1?atoi(argv[1]):0;frame_mode=argc>2?atoi(argv[2]):0;')
    helper=r'''
static uint64_t frame_site_count(void){
 InterpNativeInstructionStats rows[256];size_t n=interp_bridge_native_instruction_stats(rows,256);uint64_t total=0;
 CHECK(n<=256,"bounded frame stats");
 for(size_t i=0;i<n;i++)for(size_t j=0;j<sizeof ni_frame_entries/sizeof *ni_frame_entries;j++)
  if(rows[i].pc24==ni_frame_entries[j].pc24&&rows[i].m==ni_frame_entries[j].m&&rows[i].x==ni_frame_entries[j].x)total+=rows[i].insns;
 return total;
}
'''
    pos=text.index('static void mmio_pair(');text=text[:pos]+helper+text[pos:]
    pair=_c_function(text,'mmio_pair')
    condition='(!nmi_variant&&!frame_mode)'if nmi else'!frame_mode'
    tail=f'\n if({condition})CHECK(frame_site_count()>0,"actual COP/RTI effects executed natively");else CHECK(!frame_site_count(),"disabled/ungranted/wrong-owner frame effects retain fallback");\n'
    # Short deadlines can end before a frame opcode; only require positive
    # execution in the full-program checkpoint.
    tail=tail.replace('if('+condition+')','if(budget>=8000&&'+condition+')').replace('else CHECK','else if(frame_mode'+('||nmi_variant'if nmi else'')+') CHECK')
    text=text.replace(pair,pair.rstrip()[:-1]+tail+'}')
    return text,receipt


@pytest.fixture(scope='module',params=[(False,None),(True,None),(False,'frame_cycle'),(True,'frame_cycle')])
def frame_bridge_binary(tmp_path_factory,request):
    nmi,mutant=request.param;out=tmp_path_factory.mktemp('frame-'+str(nmi)+'-'+str(mutant));source,receipt=bridge_source(nmi,mutant)
    src=out/'frame.c';src.write_text(source);exe=out/('frame.exe'if os.name=='nt'else'frame')
    cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    files=['interp816.c','interp_bridge.c','snes.c','apu.c','spc.c','dsp.c','dsp_clock.c','dma.c','cx4.c','sdd1.c','tier2_capture.c']
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(src),*[str(REPO/'runner/src/snes'/f)for f in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    p=subprocess.run(command,capture_output=True,text=True,timeout=90);(out/'compile.json').write_text(json.dumps(dict(command=command,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,emission=receipt)));assert p.returncode==0,p.stdout+p.stderr
    return out,exe,nmi,mutant


@pytest.mark.parametrize('lookup',['0','1'])
def test_real_frame_owner_nested_COP_NMI_devices_and_deadlines(frame_bridge_binary,lookup):
    out,exe,nmi,mutant=frame_bridge_binary
    combinations=[(0,0)]if mutant else([(variant,mode)for variant in range(4)for mode in range(3)]if nmi else[(0,mode)for mode in range(3)])
    for variant,mode in combinations:
        args=[str(variant),str(mode)]if nmi else[str(mode)]
        p=subprocess.run([str(exe),*args],capture_output=True,text=True,timeout=45,cwd=out,env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup))
        (out/f'run-{lookup}-{variant}-{mode}.json').write_text(json.dumps(dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,lookup=lookup,variant=variant,mode=mode)))
        if mutant:assert p.returncode==1 and'FAIL:'in p.stdout,p.stdout+p.stderr
        else:assert p.returncode==0,p.stdout+p.stderr
