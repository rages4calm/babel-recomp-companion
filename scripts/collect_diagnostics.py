"""Collect a played session's diagnostics and, once read, clear them.

  collect_diagnostics.py DIAGNOSTICS_DIR [--clear]

Copies every log and bug mark from the install's diagnostics folder into the
next .local/batch-001/owner-playtest-<n> folder, checks the copies, prints
what the session shows (bug marks, scenes where the wide view fell back, what
the interpreter still ran) and writes residual.json for
sdk-update/extend.py and grant.py. With --clear the originals are then
deleted (on.txt stays), so the folder never grows. Run it without --clear
first, read the summary, then run it again with --clear.
"""
import argparse, filecmp, json, shutil, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("diagnostics", type=Path); p.add_argument("--clear", action="store_true")
a = p.parse_args()
files = sorted(f for f in a.diagnostics.iterdir() if f.is_file() and f.name != "on.txt")
if not files: sys.exit("nothing to collect")
batch = ROOT / ".local/batch-001"
kept = {f.name: d / f.name for d in batch.glob("owner-playtest-*") for f in d.iterdir()}
new = [f for f in files if f.name not in kept or not filecmp.cmp(f, kept[f.name], shallow=False)]
if new:
    n = 1 + max([int(d.name.rsplit("-", 1)[1]) for d in batch.glob("owner-playtest-*") if d.name.rsplit("-", 1)[1].isdigit()] or [0])
    out = batch / f"owner-playtest-{n}"; out.mkdir()
    for f in new:
        shutil.copy2(f, out / f.name); kept[f.name] = out / f.name
    print("copied", len(new), "files to", out)
for f in files:
    if not filecmp.cmp(f, kept[f.name], shallow=False): sys.exit(f"copy of {f.name} does not match; nothing cleared")
marks, fallbacks, resid = [], Counter(), Counter()
for f in files:
    if f.name.startswith("renderer-"):
        for line in f.read_text().splitlines():
            t = line.split()
            if t and t[0] == "MARK": marks.append(line); t = t[2:]
            if len(t) > 2 and not t[2].startswith("ready"): fallbacks[(t[1], t[2])] += 1
    elif f.name.startswith("interpreter-"):
        for line in f.read_text().splitlines():
            pc, e, m, x, rti, sched, count = line.split(); resid[f"{pc}:{e}{m}{x}:{rti}{sched}"] += int(count)
print("bug marks:", len(marks)); [print("  ", m) for m in marks]
print("states:", [f.name for f in files if f.suffix == ".sav"])
print("times the picture was not the wide view, by scene and reason:")
for (scene, reason), n in fallbacks.most_common(30): print(f"  {n:4d}  scene {scene}  {reason}")
print("interpreted instructions:", sum(resid.values()), "at", len(resid), "sites")
if resid and new:
    (out / "residual.json").write_text(json.dumps({"total": resid})); print("wrote", out / "residual.json")
if a.clear:
    for f in files: f.unlink()
    print("cleared", len(files), "files; on.txt kept")
