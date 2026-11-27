#!/usr/bin/env python3
"""ROM-free fixture: Minimal HUD blanking and restoring around one raster.

Compiles scripts/test_iog_minimal_hud.c against the actual
src/iog_minimal_hud.c (or --source, e.g. an older revision for a before run)
with stub headers for the PPU, cartridge, Snes and mod runtime, and runs
every case. It models the runner's VRAM write paths (byte port, word store,
host-only counter bump) and the VRAM write log hook; it does not run the
CPU, the PPU raster or the wide renderer (a real-game check does that).
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

CASES = ["no-writes", "host-bump", "nonzero-writes", "blank-writes", "mixed-writes", "elsewhere",
         "option-off", "lock-clear", "fixed-overwritten", "not-mode1", "ornament-fallback",
         "next-frames", "begin-twice"]

STUBS = {
"snes/cart.h": '''#pragma once
#include <stdint.h>
typedef struct Cart {uint8_t *rom;unsigned romSize;} Cart;
''',
"snes/snes.h": '''#pragma once
#include <stdint.h>
#include "cart.h"
typedef struct Snes {uint8_t *ram;Cart *cart;} Snes;
''',
"snes/ppu.h": '''#pragma once
#include <stdint.h>
typedef struct Ppu {uint16_t vram[0x8000];uint8_t bgmode;uint8_t bgXsc[4];uint32_t vramWriteCount;} Ppu;
#define PPU_bgTilemapAdr(ppu, layer) ((ppu->bgXsc[layer] & 0xfc) << 8)
typedef void (*PpuVramWriteLogHook)(uint32_t byte_addr, uint8_t value);
void ppu_set_vram_write_log_hook(PpuVramWriteLogHook hook);
''',
"mod_runtime.h": '''#pragma once
typedef void (*SNESModActivationCallback)(void);
#define SNES_MOD_CONSTRUCTOR(name) void name(void)
int snes_mod_register_reset_callback(SNESModActivationCallback);
int snes_mod_register_activation_plugin(const char *,SNESModActivationCallback);
''',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--compiler", default="clang")
    p.add_argument("--source", type=Path, default=ROOT / "src/iog_minimal_hud.c")
    p.add_argument("--out", type=Path, default=ROOT / ".local/batch-001/minimal-hud-fixture")
    p.add_argument("--report-only", action="store_true", help="print failures without failing (before runs)")
    args = p.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT / ".local").resolve()):
        p.error("fixture output must remain under .local/")
    include = out / "include"
    for name, text in STUBS.items():
        path = include / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    exe = out / "test_iog_minimal_hud.exe"
    source = args.source.resolve()
    subprocess.run([args.compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Wno-unused-function",
                    "-I", str(include), "-I", str(ROOT / "src"),
                    f'-DIOG_MINIMAL_HUD_SOURCE="{source.as_posix()}"',
                    str(ROOT / "scripts/test_iog_minimal_hud.c"), "-o", str(exe)], check=True)
    results = []
    for case in CASES:
        r = subprocess.run([str(exe), case], capture_output=True, text=True)
        passed = r.returncode == 0
        print(("ok   " if passed else "FAIL ") + case)
        for line in (r.stdout + r.stderr).strip().splitlines():
            if line.startswith("FAIL "):
                print("     " + line)
        m = re.search(r"(\d+) assertions", r.stdout)
        results.append({"case": case, "passed": passed, "assertions": int(m.group(1)) if m else 0})
    report = {"schema": "iog minimal hud fixture v1", "rom_free": True,
              "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "passed": all(c["passed"] for c in results), "cases": results}
    (out / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "failed": [c["case"] for c in results if not c["passed"]]}))
    if not report["passed"] and not args.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
