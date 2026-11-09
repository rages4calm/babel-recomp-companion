"""ROM-free live data immediates through actual interp816/owning bridge.

Only cartridge/platform/dispatch surfaces are synthetic. The emitted bodies,
paced bus helpers, interpreter and owning bridge are production code. This is
not a game, mapper, PPU/APU, interrupt-latency or campaign qualification.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

import pytest

from snes65816 import get_rom_mapping, set_rom_mapping
from v2.emit_function import LIVE_OPERAND_MNEMONICS, emit_function
from test_region_pacing import _c_function
from test_region_live_operand_refusal import _EXTRA

REPO = Path(__file__).resolve().parents[2]
OPS = {"LDA": 0xA9, "LDX": 0xA2, "LDY": 0xA0, "ADC": 0x69,
       "SBC": 0xE9, "AND": 0x29, "ORA": 0x09, "EOR": 0x49,
       "CMP": 0xC9, "CPX": 0xE0, "CPY": 0xC0, "BIT": 0x89}
BANKS = (3, 0x43, 0x83, 0xC3)


def _generated(mnemonic, m, x, wrap=False, partial=False):
    narrow = x if mnemonic in {"LDX", "LDY", "CPX", "CPY"} else m
    site = 0xFFFE if wrap else 0x8101
    entry = site - 1
    code = bytes([OPS[mnemonic], 0x12] + ([] if narrow else [0x01]))
    # At a wrapped partial-bank continuation the code is WRAM, not trusted
    # ROM. Do not manufacture a native continuation there.
    banks = (0x43, 0xC3) if wrap else BANKS
    rom = bytearray(0x50000)
    rom[0x30000 + entry] = 0xEA  # settle native prologue's return-frame bus peek
    rom[0x30000 + site:0x30000 + site + len(code)] = code
    if wrap:
        rom[0x30000] = 0x60 if narrow else 0x01
        if not narrow:
            rom[0x30001] = 0x60
    else:
        rom[0x30000 + site + len(code):0x30000 + site + len(code) + 7] = bytes([0x85, 0x44, 0x86, 0x46, 0x84, 0x48, 0x60])
    old = get_rom_mapping()
    try:
        set_rom_mapping("hirom")
        bodies, declarations, dispatch = [], [], []
        for bank in banks:
            for frozen in (False, True):
                name = f"{'Frozen' if frozen else 'Live'}{bank:02X}"
                bodies.append(emit_function(
                    bytes(rom), bank, entry, m, x, end=0x10000 if wrap else site + len(code) + 7,
                    func_name=name, instruction_blocks=True, region_paced=True,
                    region_live_immediates=not frozen,
                    live_operand_sites=None if frozen else {(bank << 16) | site},
                    entry_hooks=None if partial else {(bank << 16) | site: "live_observer"}))
                declarations.append(f"RecompReturn {name}_M{m}X{x}(CpuState *);")
            runtime_bank = (3 if bank == 0x43 else 0x83) if partial else bank
            dispatch.append(f"case 0x{runtime_bank:02X}: ++root_entries; return frozen_mode ? Frozen{bank:02X}_M{m}X{x}(cpu) : Live{bank:02X}_M{m}X{x}(cpu);")
        runtime_banks = (3, 0x83) if partial else banks
        return code, site, narrow, runtime_banks, "\n".join(bodies), "\n".join(declarations), "\n".join(dispatch)
    finally:
        set_rom_mapping(old)


_MAIN = r'''
static const uint8_t instruction[] = { INSTRUCTION };
static const uint8_t banks[] = { BANKS };
static unsigned hooks, reads_before_hook, hook_after_nmi, live_tails;
static int patch_at_hook;
typedef struct Snap {
  uint16_t a,x,y,s,d; uint8_t db,pb,p,m,xf,e,bus;
  uint64_t cycles,master;
} Snap;
static Snap before;
static Snap state(CpuState *c) {
  Snap s; memset(&s,0,sizeof s);cpu_mirrors_to_p(c);
  s.a=c->A;s.x=c->X;s.y=c->Y;s.s=c->S;s.d=c->D;s.db=c->DB;s.pb=c->PB;
  s.p=c->P;s.m=c->m_flag;s.xf=c->x_flag;s.e=c->emulation;
  s.bus=c->open_bus;s.cycles=c->cycles;s.master=c->master_cycles;return s;
}
static void patch_operand(unsigned edited) {
  RAM[(current_bank<<16)|(uint16_t)(SITE+1)]=edited?0x34:0x12;
  if(!NARROW)RAM[(current_bank<<16)|(uint16_t)(SITE+2)]=edited?0x02:0x01;
}
static void observe(CpuState *cpu,uint32_t pc) {
  CHECK(pc==((current_bank<<16)|SITE),"live hook alias %06x",pc);
  before=state(cpu);reads_before_hook=operand_reads;hooks++;
  hook_after_nmi=RAM[0x60]==0x66;
  if(patch_at_hook)patch_operand(1);
}
void live_observer(const CpuState *cpu,uint32 pc) { observe((CpuState *)cpu,pc); }
static void interpreter_observer(CpuState *cpu,uint32 pc) { observe(cpu,pc); }
static RecompReturn observe_tail(CpuState *cpu,uint32 target,uint32 site,uint16 entry_s,uint8 hrv) {
  if(target==((current_bank<<16)|SITE)) {
    live_tails++;
    CHECK(!operand_reads,"partial-bank refusal before operand fetch");
  }
  return interp_tier_dispatch_tail(cpu,target,site,entry_s,hrv);
}
/* GENERATED_BODIES */
typedef struct Result {
  Snap before,after,yield;unsigned hooks,reads,low_reads,high_reads,pre_reads,roots;
  unsigned after_nmi,tails;int rc,depth,underflow,bad;uint32_t resume;
} Result;
static uint8_t *expected_memory;
static Result execute(unsigned bank,unsigned edited,unsigned fast,unsigned carry,
                      unsigned decimal,int native,int frozen,int double_clock,
                      int mutate_hook,uint64_t deadline,int interrupt) {
  Result r={0};memset(RAM,0,MEMSZ);init_cpu();
  interp_bridge_reset_dynamic_cache();interp_bridge_set_master_deadline(0);
  interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_set_interpret_all(!native);
  current_bank=bank;operand_reads=operand_low_reads=operand_high_reads=0;
  double_clock_reads=double_clock;hooks=reads_before_hook=hook_after_nmi=0;
  patch_at_hook=mutate_hook;root_entries=leaf_entries=unexpected_dispatch=0;frozen_mode=frozen;
  live_tails=0;
  memset(&before,0,sizeof before);
  g_c.emulation=0;g_c.m_flag=MFLAG;g_c.x_flag=XFLAG;
  g_c.A=0x0220;g_c.X=XFLAG?0x20:0x0220;g_c.Y=XFLAG?0x20:0x0220;
  g_c.DB=0x7e;g_c._flag_C=carry;g_c._flag_D=decimal;g_c._flag_I=1;
  cpu_mirrors_to_p(&g_c);g_memsel=fast;g_c.master_cycles=1000;
  g_push_count=g_interp_push_count=g_push_depth=g_pop_underflow=g_recomp_stack_top=0;
  g_abandon_called=0;
  const uint8_t owner[]={0x20,ENTRY&255,ENTRY>>8,0x60};
  const uint8_t loop[]={0x20,ENTRY&255,ENTRY>>8,0x80,0xfe};
  const uint8_t stores[]={0x85,0x44,0x86,0x46,0x84,0x48,0x60};
  for(unsigned k=0;k<sizeof banks;k++) {
    unsigned base=(unsigned)banks[k]<<16;
    load(base|0x8000,deadline?loop:owner,deadline?sizeof loop:sizeof owner);
    RAM[base|ENTRY]=0xea;
    for(unsigned i=0;i<sizeof instruction;i++)RAM[base|(uint16_t)(SITE+i)]=instruction[i];
    if(WRAP)RAM[base|(uint16_t)(SITE+sizeof instruction)]=0x60;
    else load(base|(SITE+sizeof instruction),stores,sizeof stores);
  }
  patch_operand(edited);
  interp_bridge_set_pre_opcode_hook((bank<<16)|SITE,interpreter_observer);
  if(!deadline)cpu_push_jsr_return_frame(&g_c);
  g_c.open_bus=0x5a;
  if(deadline) {
    interp_bridge_set_master_deadline(deadline);
    r.rc=interp_bridge_run_until_quiescent(&g_c,(bank<<16)|0x8000);
    r.yield=state(&g_c);r.resume=interp_bridge_lle_resume_pc();
    CHECK(hooks==0&&operand_reads==0,"deadline must precede hook/operand");
    CHECK(r.resume==((bank<<16)|SITE),"deadline resume PC %06x",r.resume);
    CHECK(g_c.S==0x1fd,"deadline retains JSR frame %04x",g_c.S);
    interp_bridge_set_master_deadline(0);
    if(interrupt) {
      const uint8_t handler[]={0x48,0xa9,0x66, MFLAG?0x85:0x00,
                              MFLAG?0x60:0x85,MFLAG?0x68:0x60,MFLAG?0x40:0x68,0x40};
      load(0x008300,handler,MFLAG?7:8);
      cpu_push_interrupt_frame_at(&g_c,r.resume);
      CHECK(interp_bridge_run_interrupt(&g_c,0x008300)==1,"real RTI interrupt bridge");
      CHECK(RAM[0x60]==0x66,"interrupt handler before live operand");
    }
    r.rc=interp_bridge_run_until_quiescent(&g_c,r.resume);
  } else r.rc=interp_bridge_run(&g_c,(bank<<16)|0x8000);
  r.before=before;r.after=state(&g_c);r.hooks=hooks;r.pre_reads=reads_before_hook;
  r.reads=operand_reads;r.low_reads=operand_low_reads;r.high_reads=operand_high_reads;
  r.roots=root_entries;r.after_nmi=hook_after_nmi;r.tails=live_tails;
  r.depth=g_recomp_stack_top;r.underflow=g_pop_underflow;r.bad=unexpected_dispatch+g_abandon_called;
  return r;
}
int main(void) {
  RAM=malloc(MEMSZ);expected_memory=malloc(MEMSZ);if(!RAM||!expected_memory)return 2;
  g_test_cart.type=CART_HIROM;g_test_snes.cart=&g_test_cart;
  unsigned scenarios=0,negative=0,interrupts=0;
  for(unsigned b=0;b<sizeof banks;b++)for(unsigned fast=0;fast<2;fast++)
    for(unsigned decimal=0;decimal<DECIMAL_CASES;decimal++)for(unsigned carry=0;carry<2;carry++) {
      for(unsigned phase=0;phase<4;phase++) {
        unsigned edited=phase==1;int mutate=phase==3;
        Result ref=execute(banks[b],edited,fast,carry,decimal,0,0,0,mutate,0,0);
        memcpy(expected_memory,RAM,MEMSZ);
        Result got=execute(banks[b],edited,fast,carry,decimal,1,0,0,mutate,0,0);scenarios++;
        CHECK(ref.rc==1&&got.rc==1,"owner return");
        CHECK(!memcmp(&ref.before,&got.before,sizeof(Snap)),"pre-effect state");
        CHECK(!memcmp(&ref.after,&got.after,sizeof(Snap)),"final CPU/flags/bus/cycles/master");
        CHECK(!memcmp(expected_memory,RAM,MEMSZ),"complete bus memory/WRAM/stack");
        CHECK(got.hooks==1&&ref.hooks==1&&!got.pre_reads&&!ref.pre_reads,"hook precedes live fetch exactly once");
        CHECK(got.reads==(NARROW?1:2)&&ref.reads==got.reads&&got.low_reads==1&&got.high_reads==!NARROW,"operand bytes fetched exactly once");
        CHECK(got.roots==1&&!ref.roots,"actual emitted native body entered");
        CHECK(got.tails==PARTIAL,"only partial-bank live site refuses to owning interpreter");
        CHECK(got.after.s==0x1ff&&!got.depth&&!got.underflow&&!got.bad,"guest/host owner stack balanced");
      }
      Result ref=execute(banks[b],1,fast,carry,decimal,0,0,0,0,0,0);
      Result stale=execute(banks[b],1,fast,carry,decimal,1,1,0,0,0,0);
      CHECK(memcmp(&ref.after,&stale.after,sizeof(Snap))!=0,"oracle detects stale compiled operand");negative++;
      Result doubled=execute(banks[b],1,fast,carry,decimal,1,0,1,0,0,0);
      CHECK(ref.after.master!=doubled.after.master&&ref.after.cycles==doubled.after.cycles,
            "oracle detects doubled operand fetch clocks");negative++;
      if(!WRAP&&carry==1&&decimal==0) {
        uint64_t deadline=ref.before.master;
        Result yr=execute(banks[b],0,fast,carry,decimal,0,0,0,1,deadline,1);
        memcpy(expected_memory,RAM,MEMSZ);
        Result yn=execute(banks[b],0,fast,carry,decimal,1,0,0,1,deadline,1);interrupts++;
        CHECK(!memcmp(&yr.yield,&yn.yield,sizeof(Snap)),"pre-opcode deadline state and retained frame");
        CHECK(!memcmp(&yr.after,&yn.after,sizeof(Snap))&&!memcmp(expected_memory,RAM,MEMSZ),"NMI-frame/RTI/resume CPU memory timing");
        CHECK(yr.after_nmi&&yn.after_nmi,"NMI handler precedes live hook/fetch");
        CHECK(yn.after.s==0x1ff&&!yn.depth&&!yn.underflow&&!yn.bad,"interrupt continuation owns stack");
      }
    }
  interp_bridge_set_master_deadline(0);interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_set_interpret_all(0);
  printf("live immediate: %u scenarios, %u negative controls, %u interrupt boundaries, %d checks, %d failures\n",scenarios,negative,interrupts,g_check,fixture_fail);
  free(expected_memory);free(RAM);return fixture_fail?1:0;
}
'''


def _fixture(mnemonic, m, x, wrap=False, partial=False):
    code, site, narrow, banks, bodies, declarations, dispatch = _generated(mnemonic, m, x, wrap, partial)
    fixture = (REPO / "tests/interp816/bridge_test.c").read_text(encoding="utf-8")
    fixture = fixture[:fixture.index("int main(void) {")].replace("g_fail", "fixture_fail")
    fixture = fixture.replace("(void)cpu; return RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF];", r'''
    if(bank==current_bank && (addr==(uint16_t)(SITE+1)||(!NARROW&&addr==(uint16_t)(SITE+2)))) {
      operand_reads++;if(addr==(uint16_t)(SITE+1))operand_low_reads++;else operand_high_reads++;
      if(double_clock_reads)cpu->master_cycles+=cpu_region_speed(((uint32)bank<<16)|addr);
    }
    return cpu->open_bus=RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF];''')
    fixture = fixture.replace("(void)cpu; RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF] = v;",
                              "RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF]=v;cpu->open_bus=v;")
    fixture = fixture.replace(_c_function(fixture, "cpu_dispatch_has_entry"),
        "int cpu_dispatch_has_entry(CpuState *cpu,uint32 pc){(void)cpu;return (pc&0xffff)==ENTRY;}\n")
    fixture = fixture.replace(_c_function(fixture, "cpu_dispatch_pc"),
        "RecompReturn cpu_dispatch_pc(CpuState *cpu,uint32 pc,uint16 restore){(void)restore;return dispatch_generated(cpu,pc);}\n")
    fixture = fixture.replace(_c_function(fixture, "cpu_dispatch_pc_paired"),
        "RecompReturn cpu_dispatch_pc_paired(CpuState *cpu,uint32 pc,uint8 frame){cpu->host_return_valid=frame;return dispatch_generated(cpu,pc);}\n")
    extra = _EXTRA.replace("/* GENERATED_DECLARATIONS */", declarations)
    # The old helper dispatches only8100/8200. Replace that small fake surface;
    # the actual interpreter, bridge, native instruction body and bus are real.
    extra = extra[:extra.index("static RecompReturn dispatch_generated")]+(
        "static RecompReturn dispatch_generated(CpuState *cpu,uint32 pc24){switch(pc24>>16){"+dispatch+
        "}++unexpected_dispatch;return RECOMP_RETURN_NORMAL;}\n")
    runtime = (REPO / "runner/src/cpu_state.c").read_text(encoding="utf-8")
    paced = "\n".join(_c_function(runtime, name) for name in (
        "is_hw_reg", "cpu_add_aot_master_cycles", "cpu_read8_paced", "cpu_read16_paced",
        "cpu_write8_paced", "cpu_write16_paced"))
    main = _MAIN.replace("/* GENERATED_BODIES */", bodies.replace("interp_tier_dispatch_tail(", "observe_tail(")).replace("INSTRUCTION", ",".join(map(str, code)))
    main = main.replace("BANKS", ",".join(map(str, banks)))
    preamble = (f"#define SITE 0x{site:04x}\n#define ENTRY 0x{site-1:04x}\n#define NARROW {narrow}\n#define MFLAG {m}\n#define XFLAG {x}\n"
                f"#define WRAP {int(wrap)}\n#define PARTIAL {int(partial)}\n#define DECIMAL_CASES {2 if mnemonic in {'ADC','SBC'}else 1}\n"
                "static unsigned current_bank,operand_reads,operand_low_reads,operand_high_reads;\n"
                "static int double_clock_reads;\n#include \"cpu_state.h\"\n"
                "static RecompReturn dispatch_generated(CpuState *,uint32);\n")
    return preamble + fixture + extra + paced + main


def _run(tmp_path, mnemonic, m, x, wrap=False, partial=False):
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("C11 compiler required")
    source = tmp_path / "live_immediate.c"
    source.write_text(_fixture(mnemonic, m, x, wrap, partial), encoding="utf-8")
    exe = tmp_path / ("live_immediate.exe" if os.name == "nt" else "live_immediate")
    command = [cc, "-std=c11", "-O1", "-DSNESRECOMP_TIER2_TEST=1", "-I", str(REPO / "runner/src"),
               "-I", str(REPO / "runner/src/snes"), str(source), *[str(REPO / p) for p in (
                   "runner/src/snes/interp816.c", "runner/src/sha256.c", "runner/src/snes/tier2_capture.c",
                   "runner/src/snes/interp_bridge.c", "runner/src/snes/cx4.c")], "-lm", "-o", str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (tmp_path / "compile.json").write_text(json.dumps({"command": command, "exit_code": compiled.returncode,
        "stdout": compiled.stdout, "stderr": compiled.stderr}, indent=2), encoding="utf-8")
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    (tmp_path / "execution.json").write_text(json.dumps({"source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "binary_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(), "exit_code": result.returncode,
        "stdout": result.stdout, "stderr": result.stderr}, indent=2), encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 failures" in result.stdout


def test_complete_supported_data_immediate_set():
    assert set(OPS) == LIVE_OPERAND_MNEMONICS


@pytest.mark.parametrize("mnemonic", OPS)
@pytest.mark.parametrize("m,x", [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_live_immediate_real_owner_parity(tmp_path, mnemonic, m, x):
    _run(tmp_path, mnemonic, m, x)


@pytest.mark.parametrize("mnemonic", ["CMP", "SBC"])
@pytest.mark.parametrize("narrow", [0, 1])
def test_full_rom_bank_wrap_keeps_program_bank(tmp_path, mnemonic, narrow):
    _run(tmp_path, mnemonic, narrow, 0, wrap=True)


@pytest.mark.parametrize("mnemonic", ["CMP", "SBC"])
def test_partial_bank_wrap_refuses_before_effects(tmp_path, mnemonic):
    # Defensive runtime-PB check: the synthetic dispatcher deliberately selects
    # a full-bank body with a partial live PB. Production dispatch need not
    # permit this alias; its lower continuation is not trusted cartridge ROM.
    _run(tmp_path, mnemonic, 0, 0, wrap=True, partial=True)


@pytest.mark.parametrize("code", [bytes.fromhex(s)for s in ("ED 00 10 60", "C2 20 60", "E2 20 60", "02 00 60")])
def test_non_data_or_non_immediate_annotations_are_rejected(code):
    old = get_rom_mapping()
    try:
        set_rom_mapping("hirom")
        rom = bytearray(0x40000);rom[0x38100:0x38100+len(code)] = code
        with pytest.raises(ValueError, match="live_operand"):
            emit_function(bytes(rom), 0x83, 0x8100, 0, 0, func_name="Unsupported",
                          instruction_blocks=True, region_paced=True, region_live_immediates=True,
                          live_operand_sites={0x838100})
    finally:
        set_rom_mapping(old)
