"""Execute live-immediate refusal through the real owning-interpreter bridge.

The synthetic cartridge and bus come from the ROM-free bridge fixture. The
native bodies are actual region-paced emission; only dispatch/bus/platform
surfaces are fakes. This is not a game, mapper or complete APU qualification.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

import pytest

from snes65816 import get_rom_mapping, set_rom_mapping
from v2.emit_function import emit_function
from test_region_pacing import _c_function


REPO = Path(__file__).resolve().parents[2]
BANKS = (0x03, 0x43, 0x83, 0xC3)


def _program(opcode, narrow):
    prefix = [0xA9, 0x20] + ([] if narrow else [0x01])
    immediate = [opcode, 0x10] + ([] if narrow else [0x01])
    # BCC reaches the other ordinary instruction stream, not a host callback.
    arm = [0xA9, 0x22] + ([] if narrow else [0]) + [0x85, 0x44, 0x60]
    other = [0xA9, 0x11] + ([] if narrow else [0]) + [0x85, 0x44, 0x60]
    return bytes(prefix + immediate + [0x90, len(arm)] + arm + other), len(prefix)


def _generated(opcode, narrow):
    code, site = _program(opcode, narrow)
    rom = bytearray(0x40000)
    rom[0x38100:0x38100 + len(code)] = code
    rom[0x38200:0x38202] = bytes([0xE8, 0x60])  # a later genuine native JSR
    old = get_rom_mapping()
    try:
        set_rom_mapping("hirom")
        result, declarations, dispatch = [], [], []
        for bank in BANKS:
            for frozen in (False, True):
                name = f"{'Frozen' if frozen else 'Live'}{bank:02X}"
                result.append(emit_function(
                    bytes(rom), bank, 0x8100, narrow, 0,
                    end=0x8100 + len(code), func_name=name,
                    instruction_blocks=True, region_paced=True,
                    live_operand_sites=None if frozen else {(bank << 16) | (0x8100 + site)}))
                declarations.append(f"RecompReturn {name}_M{narrow}X0(CpuState *);")
            name = f"Leaf{bank:02X}"
            result.append(emit_function(bytes(rom), bank, 0x8200, narrow, 0,
                                        end=0x8202, func_name=name,
                                        instruction_blocks=True, region_paced=True))
            declarations.append(f"RecompReturn {name}_M{narrow}X0(CpuState *);")
            dispatch.append(f'''case 0x{bank:02X}:
  if (low == 0x8100) {{ ++root_entries; return frozen_mode ?
    Frozen{bank:02X}_M{narrow}X0(cpu) : Live{bank:02X}_M{narrow}X0(cpu); }}
  if (low == 0x8200) {{ ++leaf_entries; return Leaf{bank:02X}_M{narrow}X0(cpu); }}
  break;''')
        return code, site, "\n".join(result), "\n".join(declarations), "\n".join(dispatch)
    finally:
        set_rom_mapping(old)


_EXTRA = r'''
#include "common_cpu_infra.h"
#include "cpu_trace.h"
static unsigned root_entries, leaf_entries, unexpected_dispatch;
static int frozen_mode;
void WatchdogCheck(void) {}
void RecompStackPopYield(void) { RecompStackPop(); }
void cpu_dbg_funcname(const char *name) { (void)name; }
void cpu_tailcall_inherit_return_context(uint16_t s, uint8_t hrv) {
  (void)s; (void)hrv; ++unexpected_dispatch;
}
int cpu_resolve_ancestor_skip(uint16_t s) { (void)s; ++unexpected_dispatch; return -1; }
RecompReturn cpu_dispatch_pc_from(CpuState *cpu, uint32 pc, uint16 restore, uint32 site) {
  (void)cpu; (void)pc; (void)restore; (void)site; ++unexpected_dispatch; return 0;
}
/* GENERATED_DECLARATIONS */
static RecompReturn dispatch_generated(CpuState *cpu, uint32 pc24) {
  unsigned low = pc24 & 0xffff;
  switch (pc24 >> 16) { /* GENERATED_DISPATCH */ }
  ++unexpected_dispatch;
  return RECOMP_RETURN_NORMAL;
}
'''


_MAIN = r'''
static const uint8_t body[] = { BODY_BYTES };
static const uint8_t banks[] = {3, 0x43, 0x83, 0xc3};
static unsigned mutable_reads, reads_at_hook, hook_count;
static uint32_t current_site;
typedef struct Snap {
  uint16_t a,x,y,s,d; uint8_t db,pb,p,m,xflag,e,bus;
  uint64_t cycles,master;
} Snap;
static Snap checkpoint, transfer_checkpoint;
static uint8_t checkpoint_stack[0x200], transfer_stack[0x200];
static unsigned transfer_count, transfer_reads, transfer_opcode_reads, hook_opcode_reads;
static Snap state(CpuState *c) {
  Snap s; memset(&s,0,sizeof s); cpu_mirrors_to_p(c);
  s.a=c->A; s.x=c->X; s.y=c->Y; s.s=c->S; s.d=c->D; s.db=c->DB;
  s.pb=c->PB; s.p=c->P; s.m=c->m_flag; s.xflag=c->x_flag; s.e=c->emulation;
  s.bus=c->open_bus; s.cycles=c->cycles; s.master=c->master_cycles;
  return s;
}
static void before_mutable(CpuState *cpu, uint32_t pc) {
  CHECK(pc == current_site, "wrong live landing bank: %06x/%06x", pc,current_site);
  checkpoint=state(cpu); reads_at_hook=mutable_reads; ++hook_count;
  hook_opcode_reads=opcode_reads;
  memcpy(checkpoint_stack,RAM,sizeof checkpoint_stack);
}
/* Observe the emitted refusal immediately before the real production helper.
 * No bus read or timing/stack mutation is introduced by this observation. */
static RecompReturn observe_tail(CpuState *cpu, uint32 target, uint32 site,
                                uint16 entry_s, uint8 hrv) {
  if (target==current_site) {
    CHECK(site==current_site,"refusal site alias %06x/%06x",site,current_site);
    transfer_checkpoint=state(cpu); transfer_reads=mutable_reads; ++transfer_count;
    transfer_opcode_reads=opcode_reads;
    memcpy(transfer_stack,RAM,sizeof transfer_stack);
  }
  return interp_tier_dispatch_tail(cpu,target,site,entry_s,hrv);
}
/* GENERATED_BODIES */
typedef struct Result {
  int rc; Snap before,after; unsigned hooks,reads_before,roots,leaves,arms,consumes;
  Snap transfer; unsigned transfers,reads_at_transfer,opcode_at_transfer,opcode_at_hook,opcodes;
  uint8_t stack[0x200],transfer_stack[0x200];
  int depth,underflow,bad; uint8_t value;
} Result;
static uint8_t *expected_memory;
static Result execute(unsigned bank, unsigned edited, unsigned fast, int native, int frozen) {
  Result r={0}; memset(RAM,0,MEMSZ); init_cpu();
  interp_bridge_reset_dynamic_cache(); interp_bridge_set_pre_opcode_hook(0,NULL);
  interp_bridge_set_interpret_all(!native);
  g_c.emulation=0; g_c.m_flag=NARROW; g_c.x_flag=0; g_c._flag_C=1;
  g_c._flag_I=1; g_c.A=0xabcd; g_c.X=0x0101; g_c.Y=0x2345; g_c.DB=0x7e;
  cpu_mirrors_to_p(&g_c); g_memsel=fast;
  root_entries=leaf_entries=unexpected_dispatch=0; frozen_mode=frozen;
  hook_count=mutable_reads=reads_at_hook=0; memset(&checkpoint,0,sizeof checkpoint);
  transfer_count=transfer_reads=0; memset(&transfer_checkpoint,0,sizeof transfer_checkpoint);
  transfer_opcode_reads=hook_opcode_reads=opcode_reads=0;
  g_push_count=g_interp_push_count=g_push_depth=g_pop_underflow=g_recomp_stack_top=0;
  g_abandon_called=0;
  const uint8_t owner[]={0x20,0x00,0x81,0x20,0x00,0x82,0x85,0x42,0x60};
  const uint8_t leaf[]={0xe8,0x60};
  for(unsigned i=0;i<sizeof banks;i++) {
    unsigned base=(unsigned)banks[i]<<16;
    load(base|0x8000,owner,sizeof owner); load(base|0x8100,body,sizeof body);
    load(base|0x8200,leaf,sizeof leaf);
    RAM[base|MUTABLE_LOW]=edited ? (NARROW ? 0x30 : 0x00) : 0x10;
    if(!NARROW) RAM[base|(MUTABLE_LOW+1)]=edited ? 0x02 : 0x01;
  }
  current_site=(bank<<16)|MUTABLE_PC;
  interp_bridge_set_pre_opcode_hook(current_site,before_mutable);
  cpu_push_jsr_return_frame(&g_c); g_c.open_bus=0x5a;
  const uint64_t start=interp_bridge_resume_total();
  r.rc=interp_bridge_run(&g_c,(bank<<16)|0x8000);
  r.before=checkpoint; r.after=state(&g_c); r.hooks=hook_count; r.reads_before=reads_at_hook;
  r.transfer=transfer_checkpoint; r.transfers=transfer_count; r.reads_at_transfer=transfer_reads;
  r.opcode_at_transfer=transfer_opcode_reads; r.opcode_at_hook=hook_opcode_reads; r.opcodes=opcode_reads;
  memcpy(r.stack,checkpoint_stack,sizeof r.stack);
  memcpy(r.transfer_stack,transfer_stack,sizeof r.transfer_stack);
  r.roots=root_entries; r.leaves=leaf_entries;
  r.depth=g_recomp_stack_top; r.underflow=g_pop_underflow;
  r.bad=unexpected_dispatch+g_abandon_called; r.value=RAM[0x44];
  for(uint64_t q=start;q<interp_bridge_resume_total();q++) {
    InterpResumeEvent e;
    if(interp_bridge_resume_get(q,&e) && e.new_pc24==current_site) {
      if(e.kind==INTERP_RESUME_KIND_UNWIND_ARM) r.arms++;
      if(e.kind==INTERP_RESUME_KIND_UNWIND_CONSUME) r.consumes++;
    }
  }
  return r;
}
int main(void) {
  RAM=malloc(MEMSZ); expected_memory=malloc(MEMSZ);
  if(!RAM||!expected_memory) return 2;
  g_test_cart.type=CART_HIROM; g_test_snes.cart=&g_test_cart;
  unsigned scenarios=0, negative_controls=0;
  for(unsigned b=0;b<sizeof banks;b++) for(unsigned fast=0;fast<2;fast++) {
    for(unsigned toggle=0;toggle<3;toggle++) {
      const unsigned edited=toggle==1;
      Result ref=execute(banks[b],edited,fast,0,0);
      memcpy(expected_memory,RAM,MEMSZ);
      Result got=execute(banks[b],edited,fast,1,0);
      ++scenarios;
      CHECK(ref.rc==1&&got.rc==1,"bridge return bank%02x",banks[b]);
      CHECK(!memcmp(&ref.before,&got.before,sizeof(Snap)),"pre-effect CPU/clocks/bus bank%02x",banks[b]);
      CHECK(got.transfers==1&&!got.reads_at_transfer,"one pre-operand transfer bank%02x",banks[b]);
      CHECK(!got.opcode_at_transfer&&!got.opcode_at_hook&&!ref.opcode_at_hook&&
            got.opcodes>0&&got.opcodes==ref.opcodes,"opcode observations bank%02x transfer/hook/refhook/final/ref %u/%u/%u/%u/%u",
            banks[b],got.opcode_at_transfer,got.opcode_at_hook,ref.opcode_at_hook,got.opcodes,ref.opcodes);
      CHECK(!memcmp(&ref.before,&got.transfer,sizeof(Snap)),"CPU/clocks/bus before helper bank%02x",banks[b]);
      CHECK(!memcmp(ref.stack,got.transfer_stack,sizeof ref.stack)&&
            !memcmp(ref.stack,got.stack,sizeof ref.stack),"guest stack before/after transfer bank%02x",banks[b]);
      CHECK(!memcmp(&ref.after,&got.after,sizeof(Snap)),"final CPU/clocks/bus bank%02x",banks[b]);
      CHECK(!memcmp(expected_memory,RAM,MEMSZ),"complete memory/stack bank%02x",banks[b]);
      CHECK(ref.hooks==1&&got.hooks==1,"instruction interpreted once bank%02x %u/%u",banks[b],ref.hooks,got.hooks);
      CHECK(ref.reads_before==0&&got.reads_before==0,"operand read before refusal bank%02x",banks[b]);
      CHECK(ref.roots==0&&ref.leaves==0&&got.roots==1&&got.leaves==1,"actual native entries bank%02x",banks[b]);
      CHECK(got.arms==1&&got.consumes==1,"real owner unwind bank%02x %u/%u",banks[b],got.arms,got.consumes);
      CHECK(got.depth==0&&!got.underflow&&!got.bad,"host owner/depth bank%02x",banks[b]);
      CHECK(got.after.s==0x01ff&&got.after.x==0x0102,"guest return/later native leaf bank%02x",banks[b]);
      CHECK(got.value==(edited?0x11:0x22),"patched immediate changes branch bank%02x",banks[b]);
    }
    /* A compiled frozen immediate must be detected as stale by this oracle. */
    Result ref=execute(banks[b],1,fast,0,0);
    Result frozen=execute(banks[b],1,fast,1,1);
    CHECK(ref.value==0x11&&frozen.value==0x22&&frozen.roots==1&&frozen.hooks==0,
          "negative stale-constant control bank%02x",banks[b]);
    ++negative_controls;
  }
  interp_bridge_set_pre_opcode_hook(0,NULL); interp_bridge_set_interpret_all(0);
  printf("live refusal: %u scenarios, %u stale controls, %d checks, %d failures\n",
         scenarios,negative_controls,g_check,g_fail);
  free(expected_memory);free(RAM);return g_fail ? 1 : 0;
}
'''


def _fixture(opcode, narrow):
    code, site, generated, declarations, dispatch = _generated(opcode, narrow)
    fixture = (REPO / "tests/interp816/bridge_test.c").read_text(encoding="utf-8")
    fixture = fixture[:fixture.index("int main(void) {")]
    # common_cpu_infra declares the production bool g_fail; the borrowed
    # fixture's independent assertion counter must not shadow that symbol.
    fixture = fixture.replace("g_fail", "fixture_fail")
    # Keep the original bus fixture but make its last-byte latch observable.
    fixture = fixture.replace("(void)cpu; return RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF];",
        "if (addr >= MUTABLE_LOW && addr < MUTABLE_LOW + (NARROW ? 1 : 2)) ++mutable_reads;\n"
        "    if (addr == MUTABLE_PC) ++opcode_reads;\n"
        "    return cpu->open_bus = RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF];")
    fixture = fixture.replace("(void)cpu; RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF] = v;",
                              "RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF] = v; cpu->open_bus=v;")
    fixture = fixture.replace(_c_function(fixture, "cpu_dispatch_has_entry"),
        "int cpu_dispatch_has_entry(CpuState *cpu,uint32 pc) { (void)cpu;\n"
        " return (pc&0xffff)==0x8100 || (pc&0xffff)==0x8200; }\n")
    fixture = fixture.replace(_c_function(fixture, "cpu_dispatch_pc"),
        "RecompReturn cpu_dispatch_pc(CpuState *cpu,uint32 pc,uint16 restore) {\n"
        " (void)restore; return dispatch_generated(cpu,pc); }\n")
    fixture = fixture.replace(_c_function(fixture, "cpu_dispatch_pc_paired"),
        "RecompReturn cpu_dispatch_pc_paired(CpuState *cpu,uint32 pc,uint8 frame) {\n"
        " cpu->host_return_valid=frame; return dispatch_generated(cpu,pc); }\n")
    # Put declarations before the fixture dispatch and the bodies after its fakes.
    preamble = (f"#define NARROW {narrow}\n#define MUTABLE_PC 0x{0x8100+site:04x}\n"
                f"#define MUTABLE_LOW 0x{0x8101+site:04x}\n"
                "static unsigned mutable_reads, opcode_reads;\n"
                '#include "cpu_state.h"\nstatic RecompReturn dispatch_generated(CpuState *,uint32);\n')
    extra = _EXTRA.replace("/* GENERATED_DECLARATIONS */", declarations).replace(
        "/* GENERATED_DISPATCH */", dispatch)
    runtime = (REPO / "runner/src/cpu_state.c").read_text(encoding="utf-8")
    master = "\n".join(_c_function(runtime, name) for name in (
        "is_hw_reg", "cpu_add_aot_master_cycles", "cpu_read8_paced", "cpu_read16_paced",
        "cpu_write8_paced", "cpu_write16_paced"))
    # Observe only the call site; the wrapper delegates to the real linked bridge.
    main = _MAIN.replace("/* GENERATED_BODIES */", generated.replace(
        "interp_tier_dispatch_tail(", "observe_tail(")).replace(
        "BODY_BYTES", ",".join(f"0x{x:02x}" for x in code))
    main = main.replace("g_fail", "fixture_fail")
    main = main.replace("static unsigned mutable_reads, reads_at_hook, hook_count;",
                        "static unsigned reads_at_hook, hook_count;")
    return preamble + fixture + extra + master + main


@pytest.mark.parametrize("opcode", [0xC9, 0xE9], ids=["cmp", "sbc"])
@pytest.mark.parametrize("narrow", [0, 1], ids=["m0", "m1-control"])
def test_live_immediate_refusal_preserves_owner_and_later_native_entry(tmp_path, opcode, narrow):
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("C11 compiler required")
    source = tmp_path / "live_owner.c"
    source.write_text(_fixture(opcode, narrow), encoding="utf-8")
    exe = tmp_path / ("live_owner.exe" if os.name == "nt" else "live_owner")
    command = [cc, "-std=c11", "-O1", "-DSNESRECOMP_TIER2_TEST=1",
               "-I", str(REPO / "runner/src"), "-I", str(REPO / "runner/src/snes"),
               str(source), *[str(REPO / p) for p in (
                   "runner/src/snes/interp816.c", "runner/src/sha256.c",
                   "runner/src/snes/tier2_capture.c", "runner/src/snes/interp_bridge.c",
                   "runner/src/snes/cx4.c")], "-lm", "-o", str(exe)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (tmp_path / "compile.json").write_text(json.dumps({
        "command": command, "exit_code": compiled.returncode,
        "stdout": compiled.stdout, "stderr": compiled.stderr}, indent=2), encoding="utf-8")
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    (tmp_path / "execution.json").write_text(json.dumps({
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "binary_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
        "exit_code": result.returncode, "stdout": result.stdout,
        "stderr": result.stderr}, indent=2), encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "24 scenarios, 8 stale controls" in result.stdout
