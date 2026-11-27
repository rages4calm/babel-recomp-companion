#!/usr/bin/env python3
"""ROM-free fixture: hold to advance across state loads, rewinds and resets.

Compiles scripts/test_hold_advance.c against the actual src/iog_mods.c (or
--source, e.g. an older revision for a before run) with the host stubs of
test_iog_mods_runtime.py, and runs every case. It models the game's new-press
edge, the message / question flags and the game_rtl.c state tail; it does not
run the CPU or the host's real load path (a real-game check does that).
"""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from test_iog_mods_runtime import STUBS  # noqa: E402

CASES = ["play", "play-b", "message", "message-b", "message-y", "question", "rewind", "reset",
         "other-buttons", "held-paging", "taps", "question-held", "rollback", "rollback-jump",
         "rollback-after-jump", "tail"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--compiler", default="clang")
    p.add_argument("--source", type=Path, default=ROOT / "src/iog_mods.c")
    p.add_argument("--out", type=Path, default=ROOT / ".local/batch-001/hold-advance-fixture")
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
    exe = out / "test_hold_advance.exe"
    source = args.source.resolve().as_posix()
    subprocess.run([args.compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Wno-unused-function",
                    "-I", str(include), "-I", str(ROOT / "src"), f'-DIOG_MODS_SOURCE="{source}"',
                    str(ROOT / "scripts/test_hold_advance.c"), "-o", str(exe)], check=True)
    results = []
    for case in CASES:
        r = subprocess.run([str(exe), case], capture_output=True, text=True)
        passed = r.returncode == 0
        print(("ok   " if passed else "FAIL ") + case)
        for line in (r.stdout + r.stderr).strip().splitlines():
            if not line.startswith(("PASS ", "FAIL ") ) or line.startswith("FAIL " + case):
                print("     " + line)
        results.append({"case": case, "passed": passed,
                        "assertions": int(re.search(r"(\d+) assertions", r.stdout).group(1))})
    report = {"source": source, "passed": all(c["passed"] for c in results), "cases": results}
    (out / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "failed": [c["case"] for c in results if not c["passed"]]}))
    if not report["passed"] and not args.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
