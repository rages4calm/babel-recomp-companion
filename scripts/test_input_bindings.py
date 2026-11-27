#!/usr/bin/env python3
"""ROM-free fixture: the runner's own keybinds.ini / config.ini input parsers.

Compiles scripts/test_input_bindings.c against the vendored
snesrecomp/runner/src/keybinds.c, desktop/mmx_config.c and util.c with the
SDL3 the game links (headers from build/_deps/sdl3-src, the static library
from --sdl-lib), then runs the built-in cases. With --names it also checks
every key name the launcher's Input editor offers (the TSV the Companion
tests write with --input-names), and with --files DIR EXPECT it parses the
config.ini and keybinds.ini in DIR and checks them against EXPECT.

Usage:
  test_input_bindings.py --sdl-lib <dir with libSDL3.a> --out <scratch dir>
        [--names names.tsv] [--files DIR EXPECT]
"""
from pathlib import Path
import argparse, json, os, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "snesrecomp" / "runner" / "src"
LIBS = ["-lkernel32", "-luser32", "-lgdi32", "-lwinmm", "-limm32", "-lole32", "-loleaut32", "-lversion",
        "-luuid", "-ladvapi32", "-lsetupapi", "-lshell32", "-ldinput8"]

ap = argparse.ArgumentParser()
ap.add_argument("--sdl-lib", required=True, type=Path)
ap.add_argument("--sdl-include", type=Path, default=ROOT / "build" / "_deps" / "sdl3-src" / "include")
ap.add_argument("--out", required=True, type=Path)
ap.add_argument("--cc", default=os.environ.get("CC", "clang"))
ap.add_argument("--names", type=Path)
ap.add_argument("--files", nargs=2, type=Path)
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
exe = a.out / "test_input_bindings.exe"
cmd = [a.cc, "-std=c11", "-O1", "-Wall", "-DSDL_MAIN_HANDLED", "-DSNESRECOMP_SDL3=1", "-DSNESRECOMP_NO_DEFAULT_PAD_TURBO=1",
       "-I", str(a.sdl_include), "-I", str(a.sdl_lib / "include-revision"),
       "-I", str(RUNNER), "-I", str(RUNNER / "desktop"),
       str(ROOT / "scripts" / "test_input_bindings.c"), str(RUNNER / "keybinds.c"),
       str(RUNNER / "desktop" / "mmx_config.c"), str(RUNNER / "util.c"),
       str(a.sdl_lib / "libSDL3.a"), *LIBS, "-o", str(exe)]
subprocess.run(cmd, check=True)
results = {}
runs = [("built-in", [])]
if a.names: runs.append(("names", ["--names", str(a.names)]))
if a.files: runs.append(("files", ["--files", str(a.files[0]), str(a.files[1])]))
ok = True
for label, extra in runs:
    p = subprocess.run([str(exe), *extra], cwd=a.out, capture_output=True, text=True)
    sys.stderr.write(p.stderr)
    results[label] = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {"passed": False}
    ok &= p.returncode == 0
print(json.dumps({"passed": ok, **results}))
sys.exit(0 if ok else 1)
