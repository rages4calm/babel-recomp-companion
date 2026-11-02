"""Paced, isolated MSU-1/absent-pack/original boot checks. PCM stays private."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import struct

ROOT = Path(__file__).resolve().parents[1]


def check(binary: Path, rom: Path, pack: Path, output: Path, case: str) -> dict:
    target = output / case
    target.mkdir(parents=True, exist_ok=False)
    executable = target / binary.name
    shutil.copy2(binary, executable)
    for name in ("assets", "i18n"):
        shutil.copytree(binary.parent / name, target / name)
    shutil.copytree(ROOT / "mods/preloaded", target / "mods/preloaded")
    selected = pack if case == "full" else target / "absent-pack"
    if case == "partial":
        selected = target / "partial-pack"
        selected.mkdir()
        # A format-valid synthetic track 2; title track 1 is deliberately absent.
        (selected / "fixture-2.pcm").write_bytes(b"MSU1" + struct.pack("<I", 0) + bytes(256))
    state = ('format_version = 1\n\n[[package]]\nid = "iog.enhancements"\nversion = "1.0.0"\n'
             '\n[[feature]]\npackage_id = "iog.enhancements"\nid = "msu1"\n'
             f'enabled = {str(case != "off").lower()}\n'
             '\n[[resource]]\npackage_id = "iog.enhancements"\nfeature_id = "msu1"\nid = "pack"\n'
             f'path = {json.dumps(str(selected))}\n')
    (target / "mods/preloaded/state.toml").write_text(state, encoding="utf-8")
    (target / "config.ini").write_text(
        "[Graphics]\nOutputMethod = SDL-Software\nNewRenderer = 1\nWindowScale = 3\nWidescreen = 0\n"
        "[General]\nDisableFrameDelay = 0\nRetroAchievements = 0\n"
        "[Sound]\nEnableAudio = 1\nVolume = 20\nAudioFreq = 32040\nAudioChannels = 2\nAudioSamples = 512\n"
        "[GamepadMap]\nEnableGamepad1 = false\nEnableGamepad2 = false\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SNESRECOMP_", "IOG_"))}
    env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", SNESRECOMP_RUN_FRAMES="900",
               SNESRECOMP_AUDIO_STATS=str(target / "audio-stats.txt"),
               SNESRECOMP_SCREENSHOT=str(target / "frame.ppm"), SNESRECOMP_SCREENSHOT_FRAME="890")
    result = subprocess.run([str(executable), "--no-launcher", "--rom", str(rom)], cwd=target,
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
    log = result.stdout.decode("utf-8", errors="replace")
    (target / "run.log").write_text(log, encoding="utf-8")
    stats = target / "audio-stats.txt"
    lines = [line for line in stats.read_text().splitlines() if line and not line.startswith("#")] if stats.exists() else []
    final = [int(value) for value in lines[-1].split()] if lines else []
    msu = [line for line in log.splitlines() if "[msu1]" in line.lower()]
    receipt = {"case": case, "exit_code": result.returncode, "frames": 900,
               "audio_stats_rows": len(lines), "audio_produced": final[1] if final else 0,
               "audio_consumed": final[2] if final else 0, "msu_log": msu,
               "captured_frame": (target / "frame.ppm").is_file(),
               "evidence_scope": "paced SDL dummy device; stream/activation evidence, no audible-device or campaign certification"}
    receipt["passed"] = (result.returncode == 0 and "RUN_FRAMES reached after 900 frames" in log
                         and receipt["audio_consumed"] > 0 and receipt["captured_frame"]
                         and (case not in ("full", "partial") or any("songs on MSU-1" in line for line in msu))
                         and (case != "partial" or not any("-> track 1 " in line for line in msu)))
    (target / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", choices=("full", "partial", "missing", "off"), default=["full", "partial", "missing", "off"])
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(lambda case: check(args.binary.resolve(), args.rom.resolve(), args.pack.resolve(), args.output, case),
                                 args.cases))
    print(json.dumps(receipts, indent=2))
    raise SystemExit(0 if all(r["passed"] for r in receipts) else 1)
