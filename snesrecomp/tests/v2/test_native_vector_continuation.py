"""Fixed vector jumps use real architectural/COP frames and existing owners."""
import json,os,re,shutil,subprocess
import pytest
import snes65816 as decoder
from v2.native_effects import emit
from test_native_frame_continuation import bridge_source,CORE,REPO,key
from test_region_pacing import _c_function


def descriptors(text,name):
    a=text.index(f'static const InterpNativeInstruction {name}[] = {{');b=text.index('\n};',a);rows=[]
    for pc,m,x,length,code in re.findall(r'\{0x([0-9A-F]+)u,([01]),([01]),0,(\d),\{([^}]+)\},ni_at_',text[a:b]):
        code=bytes(int(z,16)for z in code.split(','));mn,mode,_=decoder.opcode_table()[code[0]]
        rows.append(dict(pc24=int(pc,16),m=int(m),x=int(x),e=0,bytes=code,mnemonic=mn,immediate=mode==decoder.IMM))
    return rows


@pytest.fixture(scope='module',params=[False,True])
def vector_binary(tmp_path_factory,request):
    nmi=request.param;out=tmp_path_factory.mktemp('vector-'+str(nmi));text,_=bridge_source(nmi)
    rows=descriptors(text,'ni_entries');frames=[key(r)for r in descriptors(text,'ni_frame_entries')]
    pc=0x8500 if nmi else 0x8700;code=bytes.fromhex('5c009082'if nmi else'5c008100');scope=2 if nmi else 1
    vectors=[dict(pc24=pc,m=m,x=x,e=0,bytes=code,mnemonic=decoder.opcode_table()[0x5c][0],immediate=False)for m in range(2)for x in range(2)]
    generated,receipt=emit(CORE.read_text(),rows+vectors,registration_name='RegisterMmio',frame_keys=frames,scope_limits=[(key(r),scope)for r in vectors])
    a=text.index('/* PRIVATE ROM-derived continuations;');old=_c_function(text,'RegisterMmio');b=text.index(old)+len(old);text=text[:a]+generated+text[b:]
    marker='    interp_bridge_set_native_frame_effects_enabled(frame_mode!=1);'
    text=text.replace(marker,f'    CHECK(interp_bridge_restrict_native_instructions(ni_scope_{scope}_entries,4,{scope}),"vector fixed to existing eligible owner only");\n'+marker)
    if not nmi:
        text=text.replace('RAM[0xffe4]=0;RAM[0xffe5]=0x81;',
            'RAM[0xffe4]=0;RAM[0xffe5]=0x87;const uint8_t vector_jump[]={0x5c,0,0x81,0};memcpy(RAM+0x8700,vector_jump,4);')
    helper=f'''
static uint64_t vector_site_count(void){{
 InterpNativeInstructionStats rows[256];size_t n=interp_bridge_native_instruction_stats(rows,256);uint64_t count=0;
 CHECK(n<=256,"bounded vector stats");for(size_t i=0;i<n;i++)if(rows[i].pc24==0x{pc:06X})count+=rows[i].insns;return count;
}}
'''
    pos=text.index('static void mmio_pair(');text=text[:pos]+helper+text[pos:]
    pair=_c_function(text,'mmio_pair');condition='!nmi_variant'if nmi else'1'
    check=f'\n if(budget>=8000&&{condition})CHECK(vector_site_count()>0,"fixed vector jump actually native under original owner");'+('\n if(nmi_variant)CHECK(!vector_site_count(),"legacy IRQ and wrong vector retain reference trampoline");'if nmi else'')+'\n'
    text=text.replace(pair,pair.rstrip()[:-1]+check+'}')
    src=out/'vector.c';src.write_text(text);exe=out/('vector.exe'if os.name=='nt'else'vector');cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    files=['interp816.c','interp_bridge.c','snes.c','apu.c','spc.c','dsp.c','dsp_clock.c','dma.c','cx4.c','sdd1.c','tier2_capture.c']
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(src),*[str(REPO/'runner/src/snes'/f)for f in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    p=subprocess.run(command,capture_output=True,text=True,timeout=90);(out/'compile.json').write_text(json.dumps(dict(command=command,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,emission=receipt)));assert p.returncode==0,p.stdout+p.stderr
    return out,exe,nmi


@pytest.mark.parametrize('lookup',['0','1'])
def test_vector_jump_preserves_actual_frame_bus_devices_and_owner(vector_binary,lookup):
    out,exe,nmi=vector_binary
    for variant in(range(4)if nmi else[0]):
        p=subprocess.run([str(exe),str(variant),*(['0']if nmi else[])],capture_output=True,text=True,timeout=45,cwd=out,env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup))
        (out/f'run-{lookup}-{variant}.json').write_text(json.dumps(dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)))
        assert p.returncode==0,p.stdout+p.stderr
