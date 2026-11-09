"""Bounded stock-Gaia input routes with private state and explicit scene evidence.

All runtime files live in a fresh output directory. The owner ROM is read-only;
native saves/mod selections/music are never copied. Script WRAM writes or imported
states are reported as assisted coverage. A scene ID alone is not campaign proof.
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
# Existing Babel/GaiaLabs-derived contracts: src/iog_ngplus.c and
# src/iog_inventory.c. These are inspected evidence, not guessed scene labels.
WORDS = {"pending_scene": 0x0642, "scene": 0x0644, "player_actor": 0x09AA,
         "control_flags": 0x09AE, "camera_x": 0x068A, "map_width": 0x0692,
         "hp": 0x0ACE, "max_hp": 0x0ACA}
SCENE_NAMES = {0x01: "south-cape", 0x08: "classroom/church", 0xFA: "file-select", 0xFC: "name-entry", 0xFF: "inventory"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def snapshots(output: Path) -> list[dict]:
    records = []
    for path in (output / "snapshots").glob("*.wram.bin"):
        raw = path.read_bytes()
        tag = path.name.removesuffix(".wram.bin")
        reg_path = path.with_name(tag + ".regs.json")
        regs = json.loads(reg_path.read_text()) if reg_path.is_file() else {}
        words = {name: int.from_bytes(raw[addr:addr+2], "little") for name, addr in WORDS.items()}
        framebuffer = path.with_name(tag + ".fb.bgrx")
        pixels = framebuffer.read_bytes() if framebuffer.is_file() else b""
        nonblack = sum(any(pixels[i:i+3]) for i in range(0, len(pixels), 4))
        records.append({"tag": tag, "frame": regs.get("frame"), "wram_bytes": len(raw),
                        "wram_sha256": sha(path), **words,
                        "scene_name": SCENE_NAMES.get(words["scene"], "unclassified"),
                        "inidisp": regs.get("inidisp"), "nonblack_pixels": nonblack,
                        "framebuffer_sha256": sha(framebuffer) if pixels else None,
                        "in_play_candidate": words["player_actor"] != 0 and words["scene"] < 0xF0})
    return sorted(records, key=lambda value: (value["frame"] is None, value["frame"] or 0, value["tag"]))


def run(binary: Path, rom: Path, route_script: Path, output: Path, frames: int,
        expect_scene: int | None = None, expect_player: bool = False,
        compare: Path | None = None, wide: bool = False, timeout: int = 180, capture: bool = False,
        interpret_all: bool = False, native_poll: bool = False, native_continuations: bool = False) -> dict:
    if type(native_continuations) is not bool:
        raise ValueError("native_continuations must be a boolean")
    if type(native_poll) is not bool:
        raise ValueError("native_poll must be a boolean")
    if not 60 <= frames <= 60000:
        raise ValueError("frames must be 60..60000")
    if not 1 <= timeout <= 600:
        raise ValueError("timeout must be 1..600 seconds")
    script_text = route_script.read_text(encoding="utf-8")
    dump_tags = []
    for line in script_text.splitlines():
        line = line.split("#", 1)[0].strip()
        parts = line.split()
        if parts and parts[0] == "dump":
            if len(parts) != 2 or not re.fullmatch(r"[A-Za-z0-9_-]{1,63}", parts[1]):
                raise ValueError("Dump tags must be safe basenames")
            dump_tags.append(parts[1])
    if len(set(dump_tags)) != len(dump_tags):
        raise ValueError("Dump tags must be unique so earlier evidence is not overwritten")
    expected = re.search(r"^expected_sha256\s*=\s*(\w+)", (ROOT / "rom_identity.txt").read_text(), re.M)[1]
    payload = rom.read_bytes()
    if len(payload) == 2097664:
        payload = payload[512:]
    if len(payload) != 2097152 or hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("Unsupported ROM: choose the clean USA revision")
    input_hashes = {"binary": sha(binary), "rom": sha(rom), "route": sha(route_script)}
    output.mkdir(parents=True, exist_ok=False)
    (output / "snapshots").mkdir()
    local_binary = output / binary.name
    shutil.copy2(binary, local_binary)
    for dll in binary.parent.glob("*.dll"):
        shutil.copy2(dll, output / dll.name)
    for name in ("assets", "i18n"):
        source = binary.parent / name
        if source.is_dir():
            shutil.copytree(source, output / name)
    shutil.copytree(ROOT / "mods/preloaded", output / "mods/preloaded")
    config = output / "test.ini"
    config.write_text("[Graphics]\nOutputMethod = SDL-Software\nNewRenderer = 1\n"
                      f"Widescreen = {int(wide)}\nDisplayAspect = 4:3\nMode7Enabled = 0\n"
                      "[General]\nDisableFrameDelay = 1\nRetroAchievements = 0\n"
                      "[Sound]\nEnableAudio = 0\n"
                      "[GamepadMap]\nEnableGamepad1 = false\nEnableGamepad2 = false\n", encoding="utf-8")
    local_script = output / "route.txt"
    local_script.write_text(script_text, encoding="utf-8")
    env = dict(os.environ)
    for name in list(env):
        if name.startswith(("SNESRECOMP_", "IOG_", "IOGR_")):
            del env[name]
    env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", SNESRECOMP_RUN_FRAMES=str(frames),
               SNESRECOMP_HOST_PROFILE="1", SNESRECOMP_STATE_TRACE=str(output / "trace.csv"),
               SNESRECOMP_DUMP_DIR=str(output / "snapshots"),
               SNESRECOMP_SCREENSHOT=str(output / "final.ppm"), SNESRECOMP_SCREENSHOT_FRAME=str(frames-1))
    command = [str(local_binary), "--no-launcher", "--config", str(config), "--script", str(local_script), "--rom", str(rom)]
    if interpret_all:
        env["SNESRECOMP_INTERPRET_ALL"] = "1"
    if native_poll:
        env["IOG_NATIVE_RDNMI_POLL"] = "1"
    if native_continuations:
        env["IOG_NATIVE_CONTINUATIONS"] = "1"
        env["IOG_NATIVE_CONTINUATION_STATS"] = str(output / "native-continuations.json")
    if capture:
        env.update(SNESRECOMP_TIER2_MANIFEST=str(output / "tier2-manifest.json"),
                   SNESRECOMP_TIER2_JOURNAL=str(output / "tier2-journal.jsonl"))
        command.insert(1, "--coverage-capture=on")
    began = time.monotonic()
    try:
        result = subprocess.run(command, cwd=output, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout)
        code = result.returncode
        log = result.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as error:
        code = None
        log = (error.stdout or b"").decode("utf-8", errors="replace") + "\nRUNNER TIMEOUT\n"
    (output / "run.log").write_text(log, encoding="utf-8")
    trace = output / "trace.csv"
    rows = trace.read_text().splitlines() if trace.is_file() else []
    states = snapshots(output)
    comparison = None
    if compare:
        reference = compare.read_text().splitlines()
        first = next((n+1 for n, (left, right) in enumerate(zip(reference, rows)) if left != right), None)
        if first is None and len(reference) != len(rows):
            first = min(len(reference), len(rows)) + 1
        comparison = {"reference_frames": len(reference), "equal": first is None, "first_differing_row": first}
    last = states[-1] if states else {}
    assisted = bool(re.search(r"(?m)^\s*(?:poke|pokefor|forcepoke|loadstate)\s", script_text))
    observed = set(re.findall(r"(?m)^script f=\d+ dump ([\w-]+) ok", log))
    requested = set(re.findall(r"(?m)^\s*dump ([\w-]+)", script_text))
    checks = {"exit_zero": code == 0, "frame_count": len(rows) == frames,
              "frame_cap": f"RUN_FRAMES reached after {frames} frames" in log,
              "script_valid": not any(error in log for error in ("script: unknown", "script: cannot open", "script: bad", "Can't parse", "timed out")),
              "all_requested_dumps": requested <= observed and bool(requested),
              "complete_wram": bool(states) and all(s["wram_bytes"] == 131072 for s in states),
              "visible_last_snapshot": last.get("nonblack_pixels", 0) > 0,
              "owner_inputs_unchanged": input_hashes == {"binary": sha(binary), "rom": sha(rom), "route": sha(route_script)}}
    if expect_scene is not None:
        checks["expected_scene"] = last.get("scene") == expect_scene
    if expect_player:
        checks["player_actor_present"] = last.get("player_actor", 0) != 0
    if comparison:
        checks["matched_trace"] = comparison["equal"]
    coverage_summary = None
    if capture:
        manifest = output / "tier2-manifest.json"
        journal = output / "tier2-journal.jsonl"
        checks["coverage_files_written"] = manifest.is_file() and journal.is_file()
        if manifest.is_file():
            coverage = json.loads(manifest.read_text())
            coverage_summary = {key: coverage.get(key) for key in
                                ("schema", "capture_id", "sequence", "distinct_sites", "overflowed_tuples", "journal_write_failures")}
            coverage_summary["manifest_sha256"] = sha(manifest)
            checks["coverage_identity_matches"] = coverage.get("identity", {}).get("rom_sha256") == expected
            checks["coverage_not_truncated"] = coverage.get("overflowed_tuples") == 0 and coverage.get("journal_write_failures") == 0
    receipt = {"schema": "iog-native-route-v1", "passed": all(checks.values()), "checks": checks,
               "frames_requested": frames, "frames_traced": len(rows), "exit_code": code,
               "elapsed_seconds": round(time.monotonic()-began, 4), "input_sha256": input_hashes,
               "normalized_rom_sha256": expected, "route_assisted": assisted,
               "widescreen": wide, "capture_requested": capture, "interpret_all": interpret_all,
               "trace_sha256": sha(trace) if rows else None,
               "comparison": comparison, "coverage": coverage_summary, "snapshots": states,
               "evidence_scope": "isolated dummy video/audio; scripted stock-ROM route; scene/player/visual evidence only; no physical input, timing or campaign certification"}
    if native_poll:
        receipt["native_poll_requested"] = True
    if native_continuations:
        receipt["native_continuations_requested"] = True
    report = output / "last_run_report.json"
    if report.is_file():
        receipt["execution_share"] = json.loads(report.read_text()).get("execution_share")
    if native_continuations:
        stats = output / "native-continuations.json"
        checks["continuation_stats_present"] = stats.is_file()
        if stats.is_file():
            receipt["continuation_stats_sha256"] = sha(stats)
        receipt["passed"] = all(checks.values())
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("binary", "rom", "route-script", "output"):
        parser.add_argument("--"+flag, type=Path, required=True)
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--expect-scene", type=lambda value: int(value, 0))
    parser.add_argument("--expect-player", action="store_true")
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--wide", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--capture", action="store_true", help="Record interpreter residual manifest/journal in the isolated fixture")
    parser.add_argument("--interpret-all", action="store_true", help="Explicitly verify retained fallback in a mixed-code executable")
    parser.add_argument("--native-poll", action="store_true", help="Explicit private native RDNMI island request")
    parser.add_argument("--native-continuations", action="store_true")
    args = parser.parse_args()
    receipt = run(args.binary.resolve(), args.rom.resolve(), args.route_script.resolve(), args.output.resolve(),
                  args.frames, args.expect_scene, args.expect_player, args.compare, args.wide, args.timeout, args.capture,
                  args.interpret_all, args.native_poll, args.native_continuations)
    print(json.dumps(receipt, indent=2))
    raise SystemExit(0 if receipt["passed"] else 1)
