"""Exercise the optional SPC700 timer effects against the stock interpreter."""

import argparse
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "snesrecomp/runner/src"
TIMER_SITES = """
SPC_NATIVE_TIMER_SITE(0x0240, 0xeb, 0xfd)
SPC_NATIVE_TIMER_SITE(0x0242, 0xf0, 0xfc)
SPC_NATIVE_TIMER_SITE(0x0270, 0xeb, 0xfe)
SPC_NATIVE_TIMER_SITE(0x0272, 0xf0, 0xfc)
"""
DRIVER_FIXTURES = (
    (0x0B, 0x42), (0x24, 0x42), (0x3D,), (0x3F, 0x30, 0x08),
    (0x48, 0xAA), (0x5D,), (0x5F, 0x12, 0x34), (0x69, 0x42, 0x43),
    (0x6F,), (0x8D, 0x79), (0x8F, 0xC3, 0x42), (0xAD, 0x80),
    (0xB0, 0xBE), (0xBB, 0x01), (0xC4, 0xF3), (0xCB, 0x42),
    (0xD0, 0xBE), (0xDA, 0x77), (0xE3, 0x42, 0x10), (0xE4, 0xF4),
    (0xE6,), (0xF2, 0x42), (0xF3, 0x42, 0xBE), (0xF4, 0x01),
    (0xF5, 0xFE, 0xFF), (0xF6, 0xFE, 0xFF), (0xFD,), (0xFE, 0xBE),
    (0x1C,), (0x2D,), (0x3A, 0x42), (0x4B, 0x42),
    (0x60,), (0x68, 0x80), (0x7A, 0x42), (0x7E, 0xF4),
    (0x84, 0x42), (0x90, 0x12), (0x9A, 0x42), (0x9B, 0x42),
    (0x9E,), (0xAE,), (0xC7, 0x42), (0xC8, 0x80),
    (0xCD, 0x10), (0xCF,), (0xD5, 0xFE, 0xFF), (0xDD,),
    (0xDE, 0x42, 0xF0), (0xE7, 0x42), (0xE8, 0x80), (0xFC,),
)
SOURCE = r"""
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "snes/apu.h"

uint64_t g_apu_timer0_total_ticks;
int snes_frame_counter;
void RtlApuLock(void) {}
void RtlApuUnlock(void) {}

static const unsigned sites[] = {0x0240, 0x0242, 0x0270, 0x0272};
static const uint8_t opcodes[] = {0xeb, 0xf0, 0xeb, 0xf0};
static const uint8_t operands[] = {0xfd, 0xfc, 0xfe, 0xfc};

typedef struct DriverOpcode {
  unsigned pc;
  unsigned length;
  uint8_t bytes[3];
} DriverOpcode;

static const DriverOpcode driverOpcodes[] = {
  DRIVER_FIXTURE_ROWS
};

typedef struct Snapshot {
  SaveLoadInfo io;
  bool loading;
  size_t size;
  uint8_t bytes[128 * 1024];
} Snapshot;

static void transfer(SaveLoadInfo *info, void *data, size_t size) {
  Snapshot *snapshot = (Snapshot *)info;
  assert(snapshot->size + size <= sizeof(snapshot->bytes));
  if (snapshot->loading)
    memcpy(data, snapshot->bytes + snapshot->size, size);
  else
    memcpy(snapshot->bytes + snapshot->size, data, size);
  snapshot->size += size;
}

static uint64_t appendHash(uint64_t hash, const void *data, size_t size) {
  const uint8_t *bytes = data;
  for (size_t i = 0; i < size; i++)
    hash = (hash ^ bytes[i]) * UINT64_C(1099511628211);
  return hash;
}

static void observe(Apu *apu, Snapshot *restore) {
  Snapshot snapshot = {.io = {.func = transfer}};
  apu_saveload(apu, &snapshot.io);
  uint64_t hash = appendHash(UINT64_C(14695981039346656037), snapshot.bytes, snapshot.size);
  hash = appendHash(hash, &apu->spc->a, sizeof(Spc) - offsetof(Spc, a));
  hash = appendHash(hash, apu->portQueue, sizeof(Apu) - offsetof(Apu, portQueue));
  printf("%016llx\n", (unsigned long long)hash);
  if (restore) {
    *restore = snapshot;
    restore->loading = true;
    restore->size = 0;
  }
}

static void setup(Apu *apu, unsigned site, unsigned counter, unsigned phase) {
  apu_reset(apu);
  apu->spc->pc = sites[site];
  apu->spc->a = 0xf1;
  apu->spc->y = 0xbb;
  apu->spc->x = 0x80;
  apu->spc->sp = 0x5d;
  apu->spc->c = true;
  apu->spc->i = true;
  apu->spc->v = true;
  apu->spc->h = true;
  apu->spc->b = true;
  apu->spc->n = (counter & 2) != 0;
  apu->spc->z = (counter & 1) != 0;
  apu->cpuCyclesLeft = 0;
  for (unsigned i = 0; i < 4; i++) {
    apu->ram[sites[i]] = opcodes[i];
    apu->ram[sites[i] + 1] = operands[i];
  }
  for (unsigned i = 0; i < 3; i++) {
    apu->timer[i].target = i + 1;
    apu->timer[i].divider = i;
    apu->timer[i].enabled = true;
    apu->timer[i].counter = counter;
    apu->timer[i].cycles = phase;
  }
}

int main(void) {
  Apu *apu = apu_init();
  assert(apu);
  for (unsigned site = 0; site < 4; site++) {
    for (unsigned counter = 0; counter < 16; counter++) {
      for (unsigned phase = 0; phase < 8; phase++) {
        setup(apu, site, counter, phase);
        int cycles = spc_runOpcode(apu->spc);
        if (opcodes[site] == 0xeb) {
          assert(cycles == 3 && apu->timer[operands[site] - 0xfd].counter == 0);
        } else {
          assert(cycles == ((counter & 1) ? 4 : 2));
          assert(apu->spc->pc == sites[site] + ((counter & 1) ? -2 : 2));
        }
        observe(apu, NULL);
      }
    }
    for (unsigned guard = 0; guard < 5; guard++) {
      setup(apu, site, 9, 5);
      switch (guard) {
        case 0: apu->ram[sites[site]] = 0; break;
        case 1: apu->ram[sites[site] + 1] = 0xff; break;
        case 2: apu->spc->p = true; break;
        case 3: apu->spc->stopped = true; break;
        case 4: apu->spc->pc = 0x1000; break;
      }
      spc_runOpcode(apu->spc);
      observe(apu, NULL);
    }
  }
  /* Independent synthetic addresses covering every added opcode family.
   * Vary registers enough to hit both outcomes of branches and index wrapping. */
  for (unsigned i = 0; i < sizeof(driverOpcodes) / sizeof(driverOpcodes[0]); i++) {
    const DriverOpcode *fixture = &driverOpcodes[i];
    for (unsigned sample = 0; sample < 34; sample++) {
      setup(apu, 0, sample & 15, sample & 7);
      Spc *spc = apu->spc;
      spc->a = (uint8_t)(sample * 137u);
      spc->x = (uint8_t)(sample * 29u);
      spc->y = (uint8_t)(sample * 7u);
      spc->c = (sample & 1) != 0;
      spc->pc = fixture->pc;
      apu->ram[0x0042] = (uint8_t)(sample * 17u);
      apu->ram[0x0043] = (uint8_t)((sample & 2) ? sample : sample * 17u);
      apu->ram[0x015e] = 0x44;
      apu->ram[0x015f] = 0x33;
      memcpy(apu->ram + fixture->pc, fixture->bytes, fixture->length);
      if (sample == 32)
        spc->p = true;
      if (sample == 33)
        apu->ram[fixture->pc + fixture->length - 1] ^= 0x01;
      spc_runOpcode(spc);
      observe(apu, NULL);
    }
  }
  for (unsigned site = 0; site < 4; site += 2) {
    setup(apu, site, 0, 3);
    assert(apu_schedulePortWrite(apu, 0, 0x62, 11));
    for (unsigned step = 0; step < 33; step++) {
      apu_runCycles(apu, 1 + (step % 5));
      if (step == 0) {
        Snapshot save;
        assert(apu->cpuCyclesLeft == 2);
        observe(apu, &save);
        apu->spc->x ^= 0xff;
        apu_saveload(apu, &save.io);
      }
      observe(apu, NULL);
    }
  }
  apu_reset(apu);
  apu_runCycles(apu, 116);
  observe(apu, NULL);
  apu_free(apu);
  return 0;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="clang")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / ".local"):
        parser.error("--out must be in this project's .local directory")
    out.mkdir(parents=True, exist_ok=True)
    fixture = out / "spc_timer_fixture.c"
    addresses = [0x0600 + index * 8 for index in range(len(DRIVER_FIXTURES))]
    fixture_rows = []
    header_rows = []
    for pc, code in zip(addresses, DRIVER_FIXTURES):
        padded = (*code, 0, 0)[:3]
        fixture_rows.append(
            f"{{0x{pc:04x}, {len(code)}, {{{', '.join(f'0x{x:02x}' for x in padded)}}}}}"
        )
        opcode, first, second = padded
        header_rows.append(
            f"SPC_NATIVE_SITE(0x{pc:04x}, 0x{opcode:02x}, {len(code)}, 0x{first:02x}, 0x{second:02x})"
        )
    fixture.write_text(SOURCE.replace("DRIVER_FIXTURE_ROWS", ",\n  ".join(fixture_rows)),
                       encoding="utf-8")
    header = out / "timer_sites.h"
    header.write_text(TIMER_SITES + "\n".join(header_rows) + "\n", encoding="utf-8")
    sources = [fixture, *(RUNNER / name for name in (
        "snes/spc.c", "snes/apu.c", "snes/dsp.c", "snes/dsp_clock.c",
        "snes/dsp_shadow.c", "snes/audio_shadow.c", "audio_trace.c",
    ))]
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("SNESRECOMP_", "IOG_"))}
    native_row = re.compile(r"\[spc-native\] pc=[0-9a-f]+ instructions=(\d+) cycles=(\d+)")
    for scheduler in (0, 1):
        executable = out / f"spc_timer_fixture_{scheduler}.exe"
        subprocess.run([
            args.compiler, "-std=c11", "-O2", "-UNDEBUG", "-DSNESRECOMP_TRACE=0",
            f"-DSNESRECOMP_APU_NATIVE={scheduler}",
            '-DIOG_NATIVE_SPC_EFFECTS_HEADER="timer_sites.h"',
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            f"-I{RUNNER}", f"-I{out}", *map(str, sources), "-lm", "-o", str(executable),
        ], check=True)
        for access_timing in ("0", "1"):
            runs = []
            for enabled, forced_reference in (("0", "0"), ("1", "0"), ("1", "1")):
                run = subprocess.run([str(executable)], check=True, capture_output=True,
                                     text=True, env={
                                         **env, "SNESRECOMP_SPC_ACCESS_CYCLES": access_timing,
                                         "SNESRECOMP_INTERPRET_ALL": forced_reference,
                                         "IOG_NATIVE_SPC_TIMER_OPCODES": enabled,
                                         "IOG_NATIVE_SPC_STATS": "1",
                                     })
                rows = [(int(insns), int(cycles)) for insns, cycles in native_row.findall(run.stderr)]
                assert len(rows) == 4 + len(DRIVER_FIXTURES), run.stderr
                assert [insns for insns, _ in rows] == (
                    [130] * 4 + [32] * len(DRIVER_FIXTURES)
                    if enabled == "1" and forced_reference == "0" else [0] * len(rows)
                ), rows
                runs.append(run.stdout)
            assert runs[0] == runs[1] == runs[2]
            print(f"Scheduler {scheduler}, access timing {access_timing}: {len(runs[0].splitlines())} matching states")


if __name__ == "__main__":
    main()
