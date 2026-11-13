"""Restrictive owner policies never broaden native instruction admission."""
import json,os,shutil,subprocess
import pytest
from v2.native_effects import emit
from test_native_frame_continuation import bridge_source,CORE,REPO


def test_owner_scope_generation_is_explicit_and_compatible():
    row=dict(pc24=0x838000,m=0,x=0,e=0,bytes=b'\xea',mnemonic='NOP',immediate=False);key=(0x838000,0,0,0);source=CORE.read_text()
    assert emit(source,[row])==emit(source,[row],scope_limits=[])
    for limits in ([((0x838001,0,0,0),1)],[(key,0)],[(key,4)],[(key,True)],[(key,1),(key,1)]):
        with pytest.raises(ValueError):emit(source,[row],scope_limits=limits)
    with pytest.raises(ValueError):emit(source,[row],scope_limits=[(key,1)],nmi_owner_pc24=0x8500,nmi_keys=[key])
    generated,receipt=emit(source,[row],scope_limits=[(key,2)],nmi_owner_pc24=0x8500,nmi_keys=[key])
    assert receipt['native_owner_scope_limits']==1
    assert generated.index('if (!interp_bridge_restrict_native_instructions')<generated.index('return interp_bridge_allow_native_nmi_instructions')


@pytest.fixture(scope='module',params=[(False,1),(False,2),(True,2),(True,3)])
def scoped_binary(tmp_path_factory,request):
    nmi,scope=request.param;out=tmp_path_factory.mktemp(f'scope-{nmi}-{scope}');text,receipt=bridge_source(nmi)
    marker='    interp_bridge_set_native_frame_effects_enabled(frame_mode!=1);'
    checks=f'''
    InterpNativeInstruction invalid[2]={{ni_entries[0],ni_entries[1]}};invalid[1].step=NULL;
    CHECK(!interp_bridge_restrict_native_instructions(invalid,2,{scope}u),"late invalid restriction is atomic");
    CHECK(!interp_bridge_restrict_native_instructions(ni_entries,n,0),"empty owner scope refused");
    CHECK(!interp_bridge_restrict_native_instructions(ni_entries,n,4),"unknown owner scope refused");
    CHECK(interp_bridge_restrict_native_instructions(ni_entries,n,{scope}u),"explicit restrictive owner policy");
    CHECK(interp_bridge_restrict_native_instructions(ni_entries,n,{scope}u),"identical owner restriction idempotent");
    CHECK(!interp_bridge_restrict_native_instructions(ni_entries,n,{3 if scope!=3 else 1}u),"restriction cannot be changed or broadened");
'''
    assert marker in text;text=text.replace(marker,checks+marker)
    if not nmi and scope==2:
        # The ordinary scheduler must fall back even with frame permission
        # and its launch switch enabled. Effects/state still match reference.
        text=text.replace('&&after.ni>0,"host IRQ control and actually accepted guest COP effects"',
                          '&&!after.ni,"NMI-only descriptors refused in ordinary scheduler"')
        text=text.replace('if(budget>=8000&&!frame_mode)CHECK(frame_site_count()>0,',
                          'if(0)CHECK(frame_site_count()>0,')
        text=text.replace('else if(frame_mode) CHECK(!frame_site_count(),',
                          'else CHECK(!frame_site_count(),')
    active='static void nmi_active_hook(CpuState *cpu,uint32_t pc){'if nmi else'static void cop_interrupt(CpuState *cpu,uint32_t pc){'
    assert active in text
    text=text.replace(active,active+'\n CHECK(!interp_bridge_restrict_native_instructions(ni_entries,sizeof ni_entries/sizeof *ni_entries,1),"active frame cannot change owner restrictions");')
    src=out/'scope.c';src.write_text(text);exe=out/('scope.exe'if os.name=='nt'else'scope')
    cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    files=['interp816.c','interp_bridge.c','snes.c','apu.c','spc.c','dsp.c','dsp_clock.c','dma.c','cx4.c','sdd1.c','tier2_capture.c']
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),str(src),*[str(REPO/'runner/src/snes'/f)for f in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    p=subprocess.run(command,capture_output=True,text=True,timeout=90);(out/'compile.json').write_text(json.dumps(dict(command=command,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,emission=receipt)));assert p.returncode==0,p.stdout+p.stderr
    return out,exe,nmi,scope


@pytest.mark.parametrize('lookup',['0','1'])
def test_existing_owners_only_and_restriction_survives_registry_rebuild(scoped_binary,lookup):
    out,exe,nmi,scope=scoped_binary
    for variant in(range(4)if nmi else[0]):
        p=subprocess.run([str(exe),str(variant),*(['0']if nmi else[])],capture_output=True,text=True,timeout=45,cwd=out,env=dict(os.environ,SNESRECOMP_NATIVE_INSTRUCTION_INDEX=lookup))
        (out/f'run-{lookup}-{variant}.json').write_text(json.dumps(dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,scope=scope)))
        assert p.returncode==0,p.stdout+p.stderr
