"""Keep RDNMI polling interpreted until native retirement/ownership is exact.

ROM-free actual snes.c/dma.c + interp816/owning bridge. Only platform, audio
and cartridge/bus routing are peripheral fixtures; RDNMI and comparator state
are real core code. A deliberately guard-less native body is a negative
control, not an enabled optimization or hardware/APU/campaign qualification.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess

import pytest

from snes65816 import get_rom_mapping, set_rom_mapping
from v2.emit_function import emit_function
from test_region_pacing import _c_function

REPO = Path(__file__).resolve().parents[2]
_EXTRA = r'''
#include "common_cpu_infra.h"
#include "cpu_trace.h"
static unsigned root_entries,unexpected_dispatch;
void WatchdogCheck(void) {}
void RecompStackPopYield(void) { RecompStackPop(); }
void cpu_dbg_funcname(const char *name) { (void)name; }
void cpu_tailcall_inherit_return_context(uint16_t s,uint8_t hrv) {(void)s;(void)hrv;++unexpected_dispatch;}
int cpu_resolve_ancestor_skip(uint16_t s) {(void)s;++unexpected_dispatch;return -1;}
RecompReturn cpu_dispatch_pc_from(CpuState *cpu,uint32 pc,uint16 restore,uint32 site) {
  (void)cpu;(void)pc;(void)restore;(void)site;++unexpected_dispatch;return 0;
}
/* GENERATED_DECLARATIONS */
'''

def _source():
    S = REPO
    def functions(source):
        return set(re.findall(r"(?m)^(?:[A-Za-z_]\w*[ \t*]+)+([A-Za-z_]\w*)\([^;{}]*\)\s*\{", source))
    bridge = (S / "tests/interp816/bridge_test.c").read_text(encoding="utf-8")
    bridge = bridge[:bridge.index("int main(void) {")].replace("g_fail", "fixture_fail")
    for name in ("snes_sync_master_clock", "sdd1_read"):
        bridge = bridge.replace(_c_function(bridge, name), "")
    bridge = bridge.replace("int snes_frame_counter = 0;", "")
    bridge = bridge.replace(_c_function(bridge, "cpu_read8"), r'''
    uint8 cpu_read8(CpuState *cpu,uint8 bank,uint16 addr) {
      if ((bank & 0x7f)<0x40 && addr==0x4210) {
        ++rdnmi_reads;
        return cpu->open_bus=snes_readReg(g_snes,addr);
      }
      return cpu->open_bus=RAM[(((uint32)bank<<16)|addr)&0xffffff];
    }
    ''')
    bridge = bridge.replace("(void)cpu; RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF] = v;",
        "RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF]=v; cpu->open_bus=v;")
    bridge = bridge.replace(_c_function(bridge, "cpu_dispatch_has_entry"),
        "int cpu_dispatch_has_entry(CpuState *cpu,uint32 pc) {(void)cpu;return pc==0x828100;}\n")
    bridge = bridge.replace(_c_function(bridge, "cpu_dispatch_pc"),
        "RecompReturn cpu_dispatch_pc(CpuState *cpu,uint32 pc,uint16 restore) {(void)restore;return poll_dispatch(cpu,pc);}\n")
    bridge = bridge.replace(_c_function(bridge, "cpu_dispatch_pc_paired"),
        "RecompReturn cpu_dispatch_pc_paired(CpuState *cpu,uint32 pc,uint8 frame) {cpu->host_return_valid=frame;return poll_dispatch(cpu,pc);}\n")
    hdma = (S / "tests/dma/hdma_timing_test.c").read_text(encoding="utf-8")
    hdma = hdma[:hdma.index("int main(void) {")]
    already = functions(bridge)
    peripherals = '#include "snes/ppu.h"\n#include "snes/dma.h"\nPpu *g_ppu; uint8_t g_snesrecomp_last_hdmaen, g_ppu_wlog_src; bool g_fail;\nstatic uint8_t ppu_regs[0x40];\n'
    peripherals += "\n".join(_c_function(hdma, name) for name in sorted(functions(hdma) - already)
                             if name not in {"check"})
    rom = bytearray(0x40000)
    code = bytes((0xaf,0x10,0x42,0x80,0x10,0xfa,0x6b))
    rom[0x28100:0x28100+len(code)] = code
    previous = get_rom_mapping()
    try:
        set_rom_mapping("hirom")
        emitted = emit_function(bytes(rom), 0x82, 0x8100, 1, 0, end=0x8107,
            func_name="Poll", instruction_blocks=True, region_paced=True)
    finally:
        set_rom_mapping(previous)
    guard = re.compile(r"    if \([^\n]*0x804210[^\n]*\) \{ RecompStackPop\(\);\n"
                       r"      return interp_tier_dispatch_tail\([^\n]*MMIO remains authoritative LLE \*/")
    assert len(guard.findall(emitted)) == 1
    naive = guard.sub("    /* Negative control: only this RDNMI guard omitted. */", emitted)
    naive = naive.replace("Poll_M1X0", "NaivePoll_M1X0")
    extra = _EXTRA.replace("/* GENERATED_DECLARATIONS */", "RecompReturn Poll_M1X0(CpuState*);\nRecompReturn NaivePoll_M1X0(CpuState*);")
    extra += '''static RecompReturn poll_dispatch(CpuState *cpu,uint32 pc) {
      if(pc!=0x828100){++unexpected_dispatch;return 0;}
      ++root_entries;return naive_mode?NaivePoll_M1X0(cpu):Poll_M1X0(cpu);
    }\n'''
    runtime = (S / "runner/src/cpu_state.c").read_text(encoding="utf-8")
    paced = "\n".join(_c_function(runtime,name) for name in ("is_hw_reg", "cpu_add_aot_master_cycles",
        "cpu_read8_paced", "cpu_read16_paced", "cpu_write8_paced", "cpu_write16_paced"))
    main = r'''
    typedef struct Result {
      uint64_t cpu,master; uint32 resume; unsigned reads; int quiescent,wai,irq;
      uint16 s,a,x,y,d; uint8 p,bus,pb,db,m,xf,e;
    } Result;
    static void capture_cpu(Result *r) {
      r->a=g_c.A;r->x=g_c.X;r->y=g_c.Y;r->d=g_c.D;r->pb=g_c.PB;r->db=g_c.DB;
      r->m=g_c.m_flag;r->xf=g_c.x_flag;r->e=g_c.emulation;r->p=g_c.P;r->bus=g_c.open_bus;
    }
    static int same(Result a,Result b) {
      return a.cpu==b.cpu&&a.master==b.master&&a.resume==b.resume&&a.reads==b.reads&&
        a.quiescent==b.quiescent&&a.wai==b.wai&&a.irq==b.irq&&a.s==b.s&&a.a==b.a&&
        a.x==b.x&&a.y==b.y&&a.d==b.d&&a.p==b.p&&a.bus==b.bus&&a.pb==b.pb&&
        a.db==b.db&&a.m==b.m&&a.xf==b.xf&&a.e==b.e;
    }
    static Result execute(int native,int naive,int real_irq) {
      Result out={0}; memset(RAM,0,MEMSZ); init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);
      static Dma dma;memset(&dma,0,sizeof dma);g_test_snes.dma=&dma;g_test_snes.hdmaBeamOff=true;
      g_test_snes.ram=RAM;g_test_cart.type=CART_HIROM;g_test_snes.cart=&g_test_cart;
      snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(true);
      g_c.emulation=0;g_c.m_flag=1;g_c.x_flag=0;g_c.A=0x1234;g_c._flag_I=!real_irq;cpu_mirrors_to_p(&g_c);
      g_test_snes.hPos=0;g_test_snes.vPos=224;g_test_snes.beamMasterLast=0;
      if(real_irq){g_test_snes.hIrqEnabled=true;g_test_snes.hTimer=20;}
      interp_bridge_reset_dynamic_cache();interp_bridge_set_interpret_all(!native);
      interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_clear_idle_polls();
      (void)interp_bridge_lle_took_quiescent();(void)interp_bridge_lle_took_wai();
      naive_mode=naive;rdnmi_reads=root_entries=unexpected_dispatch=0;g_memsel=1;
      g_push_count=g_interp_push_count=g_push_depth=g_pop_underflow=g_recomp_stack_top=0;g_abandon_called=0;
      const uint8_t owner[]={0x22,0x00,0x81,0x82,0x85,0x40,0x80,0xfe};
      const uint8_t poll[]={0xaf,0x10,0x42,0x80,0x10,0xfa,0x6b};
      load(0x838000,owner,sizeof owner);load(0x828100,poll,sizeof poll);
      interp_bridge_set_master_deadline(10000);
      CHECK(interp_bridge_run_until_quiescent(&g_c,0x838000)==1,"owning bridge yield");
      out.cpu=g_c.cycles;out.master=g_c.master_cycles;out.resume=interp_bridge_lle_resume_pc();
      out.reads=rdnmi_reads;out.quiescent=interp_bridge_lle_took_quiescent();out.wai=interp_bridge_lle_took_wai();
      out.irq=g_test_snes.inIrq;out.s=g_c.S;capture_cpu(&out);
      CHECK(!g_recomp_stack_top&&!g_pop_underflow&&!unexpected_dispatch&&!g_abandon_called,"owner host stack");
      interp_bridge_set_master_deadline(0);return out;
    }
    static void print_result(const char *name,Result r){
      printf("%s cpu=%llu master=%llu resume=%06x reads=%u quiescent=%d irq=%d s=%04x a=%04x p=%02x bus=%02x\n",
        name,(unsigned long long)r.cpu,(unsigned long long)r.master,r.resume,r.reads,r.quiescent,r.irq,r.s,r.a,r.p,r.bus);
    }
    static Result deferred_edge(int native,int enabled) {
      Result result=execute(native,0,0);
      CHECK(result.quiescent&&result.s==0x1fc,"deferred NMI starts at suspended real JSL");
      g_test_snes.nmiEnabled=enabled;g_test_snes.inNmi=true;g_test_snes.rdnmiPending=true;
      if(enabled){
        const uint8_t handler[]={0xe6,0x70,0x40};load(0x008300,handler,sizeof handler);
        uint16 before_s=g_c.S;cpu_push_interrupt_frame_at(&g_c,result.resume);
        CHECK(g_c.S==(uint16)(before_s-4),"real native interrupt frame");
        CHECK(interp_bridge_run_interrupt(&g_c,0x008300)==1,"real deferred NMI handler RTI");
        CHECK(g_c.S==before_s,"RTI restores suspended call stack");
      }
      uint32 resume=result.resume;
      for(unsigned i=0;i<4&&RAM[0x40]!=0x82;i++){
        interp_bridge_set_master_deadline(g_c.master_cycles+10000);
        CHECK(interp_bridge_run_until_quiescent(&g_c,resume)==1,"resume after deferred host edge");
        resume=interp_bridge_lle_resume_pc();
      }
      CHECK(RAM[0x40]==0x82&&g_c.S==0x1ff,"one edge exits poll and real RTL/owner continues");
      CHECK(RAM[0x70]==enabled,"NMITIMEN gates handler, not readable host edge");
      CHECK(!g_test_snes.inNmi&&!g_test_snes.rdnmiPending,"poll consumes both actual latches");
      CHECK(snes_readReg(&g_test_snes,0x4210)==2,"no duplicate edge after host delivery");
      result.cpu=g_c.cycles;result.master=g_c.master_cycles;result.resume=resume;
      result.reads=rdnmi_reads;result.quiescent=interp_bridge_lle_took_quiescent();
      result.s=g_c.S;capture_cpu(&result);
      CHECK(!g_recomp_stack_top&&!g_pop_underflow,"deferred edge host stack balanced");
      interp_bridge_set_master_deadline(0);return result;
    }
    int main(void){
      RAM=malloc(MEMSZ);uint8 *expected_memory=malloc(MEMSZ);
      if(!RAM||!expected_memory)return 2;
      /* Exercise real read-clear and manual/beam ownership independently first. */
      snes_set_rdnmi_beam_enabled(false);g_test_snes.inNmi=true;g_test_snes.rdnmiPending=true;
      CHECK(snes_readReg(&g_test_snes,0x4210)==0x82,"real RDNMI pending read");
      CHECK(!g_test_snes.inNmi&&!g_test_snes.rdnmiPending&&snes_readReg(&g_test_snes,0x4210)==2,"both latches read-clear");
      for(int irq=0;irq<2;irq++){
        Result ref=execute(0,0,irq);memcpy(expected_memory,RAM,MEMSZ);
        Result current=execute(1,0,irq);
        CHECK(!memcmp(expected_memory,RAM,MEMSZ),"current fallback complete memory/guest stack");
        Result hypothesis=execute(1,1,irq);
        print_result(irq?"irq-reference":"wait-reference",ref);
        print_result(irq?"irq-current-fallback":"wait-current-fallback",current);
        print_result(irq?"irq-guard-only-hypothesis":"wait-guard-only-hypothesis",hypothesis);
        CHECK(same(ref,current),"unchanged MMIO fallback exact");
        CHECK(!same(ref,hypothesis),"guard-only hypothesis must fail reference parity");
        if(!irq){CHECK(ref.quiescent&&ref.master<10000,"reference cooperative wait before budget");
          CHECK(!hypothesis.quiescent&&hypothesis.master>=10000&&hypothesis.reads>ref.reads,"native budget-only over-executes");}
        else {CHECK(ref.irq&&ref.master<10000,"real comparator reference preemption");
          CHECK(hypothesis.master>ref.master&&hypothesis.reads>ref.reads,"native fails timely real IRQ preemption");}
      }
      for(int enabled=0;enabled<2;enabled++){
        Result ref=deferred_edge(0,enabled);memcpy(expected_memory,RAM,MEMSZ);
        Result current=deferred_edge(1,enabled);
        CHECK(!memcmp(expected_memory,RAM,MEMSZ),"deferred edge complete memory/guest stack");
        print_result(enabled?"nmi-enabled-reference":"nmi-disabled-reference",ref);
        print_result(enabled?"nmi-enabled-fallback":"nmi-disabled-fallback",current);
        CHECK(same(ref,current),"deferred host edge reference/fallback exact");
      }
      printf("checks=%d failures=%d\n",g_check,fixture_fail);
      free(expected_memory);free(RAM);return fixture_fail?1:0;
    }
    '''
    prefix = '#include "cpu_state.h"\nstatic unsigned rdnmi_reads;static int naive_mode;\nstatic RecompReturn poll_dispatch(CpuState*,uint32);\n'
    text = prefix + bridge + peripherals + extra + paced + emitted + naive + main
    return text


def test_default_rdnmi_fallback_matches_real_core_and_rejects_guard_only_poll(tmp_path):
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("C11 compiler required")
    source = tmp_path / "poll.c"
    source.write_text(_source(), encoding="utf-8")
    # Retain real register/beam code. Only unrelated audio catch-up remains
    # the bridge fixture's stub; these checks make no APU correctness claim.
    core = tmp_path / "snes_core.c"
    core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n', encoding="utf-8")
    exe = tmp_path / ("poll.exe" if os.name == "nt" else "poll")
    command = [cc, "-std=c11", "-O1", "-DSNESRECOMP_TIER2_TEST=1", "-DSNESRECOMP_REVERSE_DEBUG=0",
        "-I", str(REPO / "runner/src"), "-I", str(REPO / "runner/src/snes"),
        "-I", str(REPO / "tests/dma"), str(source), str(core),
        *[str(REPO / file) for file in ("runner/src/snes/interp816.c", "runner/src/sha256.c",
            "runner/src/snes/tier2_capture.c", "runner/src/snes/interp_bridge.c", "runner/src/snes/cx4.c",
            "runner/src/snes/dma.c", "runner/src/snes/sdd1.c")], "-lm", "-o", str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (tmp_path / "compile.json").write_text(json.dumps(dict(command=command, exit_code=compiled.returncode,
        stdout=compiled.stdout, stderr=compiled.stderr), indent=2), encoding="utf-8")
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
    (tmp_path / "execution.json").write_text(json.dumps(dict(exit_code=result.returncode,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), stdout=result.stdout,
        stderr=result.stderr), indent=2), encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "failures=0" in result.stdout
    assert "wait-guard-only-hypothesis" in result.stdout
    assert "irq-guard-only-hypothesis" in result.stdout
    assert "nmi-enabled-fallback" in result.stdout and "nmi-disabled-fallback" in result.stdout
