"""Isolated, bounded Windows/desktop smoke route. Never touches owner saves.

This establishes execution/rendering evidence, not a campaign qualification.
Pass --compare TRACE to reject the first differing CPU/WRAM trace row.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def run(binary: Path, rom: Path, output: Path, frames: int, wide: bool,
        compare: Path | None = None, settings_smoke: bool = False) -> dict:
    if not 360 <= frames <= 3600:
        raise ValueError("Frames must be 360..3600")
    payload = rom.read_bytes()
    if len(payload) == 2097664:
        payload = payload[512:]
    identity = (ROOT / "rom_identity.txt").read_text()
    expected = re.search(r"^expected_sha256\s*=\s*(\w+)", identity, re.M)[1]
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected:
        raise ValueError("ROM does not match the supported USA revision")
    # A fresh output directory makes state contamination explicit instead of
    # quietly running over a prior save/config. The caller owns this directory.
    output.mkdir(parents=True, exist_ok=False)
    # The host also resolves keybinds, logs and mods beside the executable.
    # A --config path alone cannot isolate an installed MSU/mod selection.
    local_binary = output / binary.name
    shutil.copy2(binary, local_binary)
    for name in ("assets", "i18n"):
        if (binary.parent / name).is_dir():
            shutil.copytree(binary.parent / name, output / name)
    shutil.copytree(ROOT / "mods/preloaded", output / "mods/preloaded")
    config = output / "test.ini"
    config.write_text("[Graphics]\nOutputMethod = SDL-Software\nNewRenderer = 1\n"
                      f"Widescreen = {int(wide)}\nDisplayAspect = 4:3\n"
                      "[General]\nDisableFrameDelay = 1\nRetroAchievements = 0\n"
                      "[Sound]\nEnableAudio = 0\n"
                      "[GamepadMap]\nEnableGamepad1 = false\nEnableGamepad2 = false\n", encoding="utf-8")
    script = output / "route.txt"
    script.write_text("# Start/confirm pulses; no cheats, memory writes or imported saves.\n"
                      "wait 450\npress start 2\nwait 90\npress start 2\n"
                      "wait 90\npress a 2\nwait 90\npress start 2\n"
                      "wait 90\npress a 2\n", encoding="utf-8")
    env = dict(os.environ)
    # Do not inherit arbitrary debug/load/mod switches from the caller.
    for name in list(env):
        if name.startswith(("SNESRECOMP_", "IOG_", "IOGR_")):
            del env[name]
    env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
               SNESRECOMP_RUN_FRAMES=str(frames), SNESRECOMP_HOST_PROFILE="1",
               SNESRECOMP_SCREENSHOT=str(output / "frame.ppm"),
               SNESRECOMP_SCREENSHOT_FRAME=str(frames - 10),
               SNESRECOMP_STATE_TRACE=str(output / "trace.csv"))
    if settings_smoke:
        env.update(SNESRECOMP_SETTINGS_OPEN_AT="400", SNESRECOMP_SETTINGS_SCRIPT="D,A,B",
                   SNESRECOMP_OVERLAY_DUMP=str(output / "settings.ppm"))
    command = [str(local_binary), "--no-launcher", "--config", str(config),
               "--script", str(script), "--rom", str(rom)]
    start = time.monotonic()
    result = subprocess.run(command, cwd=output, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=90)
    elapsed = time.monotonic() - start
    log = result.stdout.decode("utf-8", errors="replace")
    (output / "run.log").write_text(log, encoding="utf-8")
    trace_path = output / "trace.csv"
    rows = trace_path.read_text().splitlines() if trace_path.exists() else []
    shot = output / "frame.ppm"
    receipt = {"schema": "iog-baseline-v1", "rom_sha256": digest,
               "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
               "execution_id": next((line for line in log.splitlines() if line.startswith("IOG_EXECUTION=")), "upstream-unstamped"),
               "frames_requested": frames, "frames_traced": len(rows),
               "widescreen": wide, "exit_code": result.returncode,
               "elapsed_seconds": round(elapsed, 4),
               "trace_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest() if rows else None,
               "rendered": shot.is_file(), "comparison": None,
               "evidence_scope": "dummy video/audio; boot plus start/confirm input pulses; no verified prologue/gameplay, campaign or input-latency proof"}
    report = output / "last_run_report.json"
    if report.is_file():
        diagnostics = json.loads(report.read_text(encoding="utf-8"))
        receipt["execution_share"] = diagnostics.get("execution_share")
    if shot.is_file():
        with shot.open("rb") as image:
            receipt["ppm_header"] = [image.readline().decode().strip() for _ in range(3)]
            pixels = image.read()
        width, height = (int(value) for value in receipt["ppm_header"][1].split())
        receipt["valid_ppm"] = (receipt["ppm_header"][0] == "P6" and receipt["ppm_header"][2] == "255"
                                 and len(pixels) == width * height * 3)
        receipt["nonblack_pixels"] = sum(any(pixels[i:i+3]) for i in range(0, len(pixels), 3))
        receipt["visual_qualified"] = receipt["valid_ppm"] and receipt["nonblack_pixels"] > 0
    if compare:
        reference = compare.read_text().splitlines()
        first = next((i + 1 for i, (a, b) in enumerate(zip(reference, rows)) if a != b), None)
        if first is None and len(reference) != len(rows):
            first = min(len(reference), len(rows)) + 1
        receipt["comparison"] = {"equal": first is None, "first_differing_row": first,
                                 "reference_frames": len(reference)}
    receipt["execution_passed"] = (result.returncode == 0 and len(rows) == frames and shot.is_file()
                         and f"RUN_FRAMES reached after {frames} frames" in log
                         and "script: unknown" not in log and "script: cannot open" not in log
                         and "Can't parse" not in log
                         and (not compare or receipt["comparison"]["equal"]))
    receipt["passed"] = receipt["execution_passed"] and receipt.get("visual_qualified", False)
    if settings_smoke:
        saved = config.read_text(encoding="utf-8")
        receipt["mode7_setting_saved_off"] = bool(re.search(r"^Mode7Enabled\s*=\s*0\s*$", saved, re.M))
        receipt["settings_overlay_captured"] = (output / "settings.ppm").is_file()
        receipt["passed"] = receipt["passed"] and receipt["mode7_setting_saved_off"] and receipt["settings_overlay_captured"]
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=1200)
    parser.add_argument("--wide", action="store_true")
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--settings-smoke", action="store_true", help="Open in-game settings and toggle HD Mode 7 off (Windows layout)")
    args = parser.parse_args()
    receipt = run(args.binary.resolve(), args.rom.resolve(), args.output.resolve(),
                  args.frames, args.wide, args.compare, args.settings_smoke)
    print(json.dumps(receipt, indent=2))
    raise SystemExit(0 if receipt["passed"] else 1)
