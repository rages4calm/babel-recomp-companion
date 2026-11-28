#!/usr/bin/env python3
"""ROM-free fixture: controller rumble (src/iog_rumble.c).

Compiles scripts/test_rumble.c, which includes the actual src/iog_rumble.c,
against stub host headers (mod runtime, state generation, run-ahead's
speculative flag, config, SDL) and runs every case. SDL_RumbleGamepad calls
are recorded; nothing touches a real controller. It models WRAM as the
frame callback reads it; a real-game check (the harness and IOG_RUMBLE_LOG)
covers the game itself.
"""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from test_iog_mods_runtime import STUBS as MOD_STUBS  # noqa: E402

STUBS = dict(MOD_STUBS)
STUBS["common_rtl.h"] = '''#pragma once
#include <stdbool.h>
#include <stdint.h>
uint64_t RtlStateGeneration(void);
bool RtlSpeculativeFrame(void);
extern int snes_frame_counter;
'''
STUBS["desktop/config.h"] = '''#pragma once
#include <stdbool.h>
typedef struct Config { bool enable_gamepad[5]; } Config;
extern Config g_config;
'''
STUBS["desktop/sdl_compat.h"] = '''#pragma once
#include <stdbool.h>
#include <stdint.h>
#define SNESRECOMP_SDL3 1
typedef uint32_t SDL_JoystickID;
typedef struct SDL_Gamepad SDL_Gamepad;
SDL_JoystickID *SDL_GetGamepads(int *count);
void SDL_free(void *p);
SDL_Gamepad *SDL_GetGamepadFromID(SDL_JoystickID id);
int SDL_GetGamepadPlayerIndex(SDL_Gamepad *pad);
bool SDL_RumbleGamepad(SDL_Gamepad *pad, uint16_t low, uint16_t high, uint32_t ms);
'''

CASES = ["hit", "gain", "load-rewind-reset", "rollback", "death", "off", "no-pad", "shake", "log"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--compiler", default="clang")
    p.add_argument("--out", type=Path, default=ROOT / ".local/batch-001/rumble-fixture")
    args = p.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT / ".local").resolve()):
        p.error("fixture output must remain under .local/")
    include = out / "include"
    for name, text in STUBS.items():
        path = include / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    exe = out / "test_rumble.exe"
    subprocess.run([args.compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-I", str(include), "-I", str(ROOT / "src"),
                    str(ROOT / "scripts/test_rumble.c"), "-o", str(exe)], check=True)
    results = []
    for case in CASES:
        extra = []
        if case == "log":
            log = out / "rumble.log"
            log.unlink(missing_ok=True)
            extra = [str(log)]
        env = None
        if case == "log":
            import os
            env = dict(os.environ, IOG_RUMBLE_LOG=str(out / "rumble.log"))
        r = subprocess.run([str(exe), case, *extra], capture_output=True, text=True, env=env)
        passed = r.returncode == 0
        print(("ok   " if passed else "FAIL ") + case)
        for line in (r.stdout + r.stderr).strip().splitlines():
            if not line.startswith("PASS "):
                print("     " + line)
        m = re.search(r"(\d+) assertions", r.stdout)
        results.append({"case": case, "passed": passed, "assertions": int(m.group(1)) if m else 0})
    report = {"passed": all(c["passed"] for c in results), "cases": results}
    (out / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "assertions": sum(c["assertions"] for c in results),
                      "failed": [c["case"] for c in results if not c["passed"]]}))
    if not report["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
