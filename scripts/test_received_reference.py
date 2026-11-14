"""ROM-free configure/preprocessor checks for the private received reference.

Requires an already configured private reference build for actual include paths;
does not run a game, qualify native execution, or modify that build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import struct

ROOT = Path(__file__).resolve().parents[1]

OBSERVER_PHASE_HARNESS = r'''
#include <assert.h>
#include "iog_received_observer.c"
static Snes machine;static Ppu picture;static uint8_t fixture_ram[131072];
Snes *g_snes=&machine;Ppu *g_ppu=&picture;CpuState g_cpu;
static unsigned registered;
bool interp_bridge_add_pre_opcode_hook(uint32_t pc,InterpPreOpcodeHook hook)
{(void)pc;(void)hook;registered++;return true;}
int main(void){
    memset(&s,0,sizeof(s));memset(&g_cpu,0,sizeof(g_cpu));
    g_cpu.ram=fixture_ram;CpuState before=g_cpu;
    uint8_t original[131072];memcpy(original,fixture_ram,sizeof(original));
    IogReceivedObserverInitialize();assert(!s.enabled&&!registered);
    s.enabled=1;s.limit=0;
    s.pending=1;s.after=0;picture.oamWriteCount=1;
    IogReceivedObserverAfterNmi();assert(s.wrong_phase==1&&!s.pending&&!s.pairs);
    s.pending=s.after=1;picture.highOam[31]=1;
    IogReceivedObserverAfterNmi();assert(s.mismatches==1&&!s.pending&&!s.pairs);
    memcpy(s.staging,picture.oam,512);memcpy(s.staging+512,picture.highOam,32);
    s.pending=s.after=1;IogReceivedObserverAfterNmi();assert(s.pairs==1&&!s.pending);
    s.pending=s.after=1;IogReceivedObserverReset();assert(!s.pending&&!s.after&&s.load_resets==1);
    assert(!memcmp(&g_cpu,&before,sizeof(g_cpu))&&!memcmp(original,fixture_ram,sizeof(original)));
    assert(DirectSource(8)==0x11fc0&&DirectSource(0xff)==0x11fc0);
    assert(DirectSource(0xfe)==0x10600&&DirectSource(0x8c)==0x10600&&DirectSource(0x8f)==0x10600);
    assert(DirectSource(0x90)==0x11fc0);
    puts("Actual observer phase refusals, last high-table mismatch and readonly checks pass");return 0;
}
'''


def validate_observation(directory):
    """Independently check complete exported packets, including published OAM."""
    directory = Path(directory)
    rows = [json.loads(s) for s in (directory / "received-observer.jsonl").read_text().splitlines()]
    assert rows[0]["schema"] in ("received-oam-observation-v2", "received-oam-observation-v3")
    summary = rows[-1]
    assert summary["kind"] == "summary" and summary["mismatches"] == summary["wrong_phase"] == 0
    packets = [r for r in rows if r["kind"] == "paired"]
    assert 0 < len(packets) == summary["captures"] <= 32
    assert sum(p.stat().st_size for p in directory.iterdir() if p.is_file()) <= 4*1024*1024

    def packet_checks(data, row):
        head = struct.unpack_from("<6I", data)
        version=3 if rows[0]["schema"].endswith("v3") else 2
        assert head == (0x314F4752, version, row["compose_frame"], row["nmi_frame"], row["scene"], 200032 if version==3 else 133976)
        assert len(data) == head[-1]
        ram = data[24:131096]; staging = data[131096:131640]
        selected_after = data[132920:133432]; published = data[133432:133976]
        assert len(staging) == len(published) == 544 and staging == published
        if version==3:
            assert hashlib.sha256(data[133976:199512]).hexdigest()==row["vram_sha256"]
            assert hashlib.sha256(data[199512:200024]).hexdigest()==row["cgram_sha256"]
            assert row["graphics_phase"]=="same-NMI-post-OAM-publication-not-raster-palette"
        assert hashlib.sha256(ram).hexdigest() == row["ram_sha256"]
        assert hashlib.sha256(staging).hexdigest() == row["staging_sha256"]
        source = row["direct_source_ram_offset"]
        assert source in (0x10600, 0x11FC0)
        assert ram[source:source+512] == selected_after
        assert ram[0x13100:0x13400] == data[132152:132920]
        assert hashlib.sha256(selected_after).hexdigest() == row["direct_before_sha256"]
        count = min(int.from_bytes(ram[0xDA:0xDC], "little"), 512)
        assert count % 4 == 0 and count == row["direct_bytes"]
        if row["direct_mode"]:
            assert staging[:count] == selected_after[:count]
            for slot in range(count//4):
                assert ((published[512+slot//4] >> ((slot%4)*2)) & 3) == (0 if row["scene"] == 255 else 2)
        assert row["all544_oam_match"] and row["direct_prefix_matches_staging"]

    for row in packets:
        data = (directory / f"received-packet-{row['packet']:02d}.bin").read_bytes()
        packet_checks(data, row)
    # The last high-table byte is part of the contract, not just the512-byte
    # low table. Corrupting only that byte must fail the independent reader.
    first = packets[0]; data = bytearray((directory / "received-packet-00.bin").read_bytes())
    data[133975] ^= 1
    try:
        packet_checks(data, first)
    except AssertionError:
        pass
    else:
        raise AssertionError("Published high-table mutation was accepted")
    return {"passed": True, "packets": len(packets), "summary": summary,
            "independent_full544_and_full_source_buffer_checks": True,
            "published_high_table_fault_rejected": True}


def body(source, marker):
    match = re.search(re.escape(marker) + r"\s*(?:=\s*)?\{", source)
    assert match, marker
    start = match.end() - 1
    depth = 1; end = start + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}"); end += 1
    return source[start:end]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--compiler", required=True)
    p.add_argument("--cmake", required=True)
    p.add_argument("--ninja", required=True)
    a = p.parse_args(); out = a.out.resolve(); build = a.build.resolve()
    assert out.is_relative_to((ROOT / ".local").resolve()) and not out.exists()
    assert build.is_relative_to((ROOT / ".local").resolve())
    out.mkdir(parents=True)
    ninja = (build / "build.ninja").read_text()
    includes = shlex.split(re.search(r"(?m)^  INCLUDES = (.*)$", ninja)[1])
    common = [a.compiler, "-E", "-P", *includes, "-DSNESRECOMP_SDL3=1",
              "-DSNESRECOMP_ENABLE_MODS=0", "-DSNESRECOMP_INTERPRETER_ONLY=1"]
    checks = {}
    outputs = {}
    for profile in ("reference", "original"):
        flags = ["-DIOG_RECEIVED_REFERENCE=1", '-DIOG_RECEIVED_REFERENCE_SHA256="' + "a"*64 + '"',
                 '-DIOG_RECEIVED_REFERENCE_ROM_FILE="synthetic.smc"'] if profile == "reference" else []
        for file in ("main", "game_rtl"):
            result = subprocess.run([*common, *flags, str(ROOT / f"src/{file}.c")], capture_output=True, text=True)
            (out / f"{profile}-{file}.log").write_text(result.stderr)
            result.check_returncode(); outputs[profile, file] = result.stdout
    host = body(outputs["reference", "main"], "static const SnesDesktopHostGame kGameHost")
    for token in ("IogCompanion", "IogI18n", "IogInventory", "IogWorld", "IogWidescreen", "IogBeforeRunFrame"):
        assert token not in host
    assert ".prepare_frame = IogReferenceFrame" in host
    assert ".native_widescreen = 1" in host
    # Map host callbacks are title-neutral host UI/data observers. They do not
    # admit stock Companion/inventory/i18n or generated guest dispatch.
    for callback, function in (("companion_open", "IogMapHostOpen"),
        ("companion_nav", "IogMapHostNav"), ("companion_key", "IogMapHostKey"),
        ("companion_image", "IogMapHostImage"), ("companion_pointer", "IogMapHostPointer")):
        assert re.search(r"\." + callback + r"\s*=\s*" + function + r"\b", host)
    assert ".on_reset = IogMapHostReset" in host
    assert ".on_shutdown = IogMapHostShutdown" in host
    frame = body(outputs["reference", "main"], "static void IogReferenceFrame(int dw,int dh,int *w,int *h)")
    assert "*w=384;*h=224;" in re.sub(r"\s+", "", frame)
    assert "PpuSetWidescreenBg3Widen(g_ppu,1)" in re.sub(r"\s+", "", frame)
    assert ".expected_crc32_hex=((void*)0)" in re.sub(r"\s+", "", host)
    original = body(outputs["original", "main"], "static const SnesDesktopHostGame kGameHost")
    assert "IogCompanionOpen" in original and "IogBeforeRunFrame" in original
    init = body(outputs["reference", "game_rtl"], "static void GameInitialize(void)")
    assert "interp_bridge_set_interpret_all(1)" in init
    assert "interp_bridge_clear_native_instructions()" in init
    assert "add_pre_opcode_hook" not in init and "IogNative" not in init
    draw = body(outputs["reference", "game_rtl"], "void GameDrawPpuFrame(void)")
    observed_draw=re.sub(r"IogReceivedWorld(?:BeginRaster|CaptureLine|EndRaster)\([^;]*\);", "", draw)
    assert "Iog" not in observed_draw and "ppu_runLine" in draw and "SimpleHdma_DoLine" in draw
    run = body(outputs["reference", "game_rtl"], "void GameRunOneFrame(void)")
    observed_run = re.sub(r"IogReceivedObserver(?:Frame|BeforeNmi|AfterNmi)\(\);", "", run)
    assert "Iog" not in observed_run and "reset_vector()" in run and "nmi_vector()" in run
    checks["actual_preprocessor_removes_stock_callbacks_and_retains_original_profile"] = True
    cache = (build / "CMakeCache.txt").read_text()
    for definition in ("SNESRECOMP_INTERPRETER_ONLY:BOOL=ON", "SNESRECOMP_ENABLE_MODS:BOOL=OFF"):
        assert definition in cache
    title_objects = re.findall(r"(?m)^build .*?/src/(iog_[^ :]+)\.obj:", ninja)
    allowed_reference_objects = [
        "iog_received_observer.c", "iog_received_world.c", "iog_visual_objects.c",
        "iog_world_pixels.c", "iog_world_view.c", "iog_map_discovery.c",
        "iog_map_view.c", "iog_map_scenery.c", "iog_map_runtime.c",
        "iog_map_ui.c", "iog_map_host.c",
    ]
    assert sorted(title_objects) == sorted(allowed_reference_objects), title_objects
    assert not re.search(r"(?m)^build .*src/gen/", ninja)
    checks["configured_reference_has_no_stock_plugins_or_generated_objects"] = True
    unit = out / "observer-phase.c"; unit.write_text(OBSERVER_PHASE_HARNESS)
    unit_exe = out / "observer-phase.exe"
    unit_command = [a.compiler, "-std=c11", "-O1", *includes,
                    '-DIOG_RECEIVED_REFERENCE_SHA256="' + "a"*64 + '"',
                    '-DIOG_RECEIVED_DIAGNOSTICS_ROOT="' + (ROOT/".local").as_posix() + '"',
                    str(unit), str(ROOT/"src/iog_visual_objects.c"), str(ROOT/"snesrecomp/runner/src/sha256.c"), "-o", str(unit_exe)]
    result = subprocess.run(unit_command, capture_output=True, text=True)
    (out/"observer-phase-build.log").write_text(result.stdout+result.stderr);result.check_returncode()
    import os
    clean_env = {k:v for k,v in os.environ.items() if not k.startswith(("IOG_", "SNESRECOMP_"))}
    result = subprocess.run([str(unit_exe)], env=clean_env, capture_output=True, text=True)
    (out/"observer-phase-run.log").write_text(result.stdout+result.stderr);result.check_returncode()
    checks["actual_observer_rejects_wrong_phase_and_last_high_table_mismatch_readonly"] = True
    failures = [(["-DSNESRECOMP_INTERPRETER_ONLY=OFF"], "interpreter-only"),
                (["-DIOG_NATIVE_EFFECTS_SOURCE=forbidden.c"], "refuses generated/native"),
                (["-DIOG_RECEIVED_REFERENCE_SHA256=bad"], "exact lowercase ROM SHA-256")]
    for i, (flags, expected) in enumerate(failures):
        cmd = [a.cmake, "-S", str(ROOT), "-B", str(out / f"refused{i}"), "-G", "Ninja",
               "-DCMAKE_C_COMPILER="+a.compiler, "-DCMAKE_CXX_COMPILER="+a.compiler,
               "-DCMAKE_MAKE_PROGRAM="+a.ninja, "-DIOG_RECEIVED_REFERENCE=ON",
               "-DIOG_RECEIVED_REFERENCE_SHA256="+"a"*64,
               "-DIOG_RECEIVED_REFERENCE_ROM_FILE=synthetic.smc", *flags]
        result = subprocess.run(cmd, capture_output=True, text=True)
        (out / f"refused{i}.log").write_text(result.stdout + result.stderr)
        assert result.returncode and expected in result.stdout + result.stderr
    checks["actual_configure_rejects_native_inputs_and_missing_identity"] = True
    (out / "receipt.json").write_text(json.dumps({"passed": True, "checks": checks,
        "scope": "ROM-free actual C preprocessing/configure guards; no game execution or native qualification"}, indent=2)+"\n")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
