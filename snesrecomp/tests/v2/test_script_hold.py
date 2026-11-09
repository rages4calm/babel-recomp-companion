"""Actual desktop script parser/ticker: continuous input and legacy releases."""
import os
import subprocess

from test_region_pacing import REPO, _c_function


def test_continuous_segments_and_legacy_press_timeline(tmp_path):
    import test_hle_func_seam as seam
    compiler = seam._compiler()
    if not compiler:
        import pytest
        pytest.skip("C compiler required")
    host = (REPO / "runner/src/desktop/host_main.c").read_text()
    start = host.index("// --- Scripted input ---")
    end = host.index("static uint32 ParseButtonMask", start)
    source = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t uint32; typedef uint16_t uint16; typedef uint8_t uint8;
enum {kKeys_ToggleRenderer=1,kKeys_ToggleWidescreen=2,kSaveLoad_Save=1,kSaveLoad_Load=0};
static uint8 g_ram[0x20000]; static int g_turbo, snes_frame_counter;
static unsigned dump_count;
static struct {int widescreen;} g_config;
static const char *g_active_config_file;
static unsigned config_writes;
static void WriteConfigFile(const char *path) {
  if(!path || path!=g_active_config_file) abort();
  FILE *f=fopen(path,"w"); if(!f) abort();
  fprintf(f,"widescreen=%d\n",g_config.widescreen); fclose(f); config_writes++;
}
static void RtlSaveLoad(int mode, int slot) {(void)mode;(void)slot;}
static void GameReset(void) {} static void ConsoleReset(void) {}
static void HandleCommand(uint32 command,bool pressed) {(void)command;(void)pressed;}
static int snesrecomp_desktop_new_renderer(void) {return 0;}
static void ScriptDump(const char *tag,unsigned frame) {(void)tag;(void)frame;dump_count++;}
'''
    source += host[start:end]
    for name in ("snesrecomp_desktop_set_widescreen", "HexNibble", "ParseButtonMask", "ParseHexByte", "ParseHexBytes",
                 "AddScriptForcePoke", "ApplyScriptForcePokes", "NewScriptEntry",
                 "LoadScript", "ScriptCondHolds", "TickScript"):
        source += _c_function(host, name)
    source += r'''
int main(int argc,char **argv) {
  if(argc<3) return 2;
  LoadScript(argv[1]);
  if(!strcmp(argv[2],"invalid")) return g_script_failed && g_script_quit && !config_writes ? 0 : 3;
  if(g_script_failed) return 4;
  if(!strcmp(argv[2],"aspect")) {
    if(argc!=4) return 7;
    g_active_config_file=argv[3];
    const unsigned masks[]={0x100,0x100,0,0x100,0};
    const unsigned writes[]={1,2,2,3,3};
    const int wide[]={0,1,1,0,0};
    for(unsigned i=0;i<5;i++,snes_frame_counter++) {
      if(TickScript()!=masks[i] || config_writes!=writes[i] || g_config.widescreen!=wide[i]) return 8;
    }
    if(!g_script_quit || g_script_failed || !g_turbo) return 9;
    FILE *f=fopen(g_active_config_file,"r"); char line[64];
    if(!f || !fgets(line,sizeof(line),f)) return 10;
    fclose(f); if(strcmp(line,"widescreen=0\n")) return 11;
    return 0;
  }
  for(int i=3;i<argc;i++) {
    unsigned expected=(unsigned)strtoul(argv[i],NULL,16), got=TickScript();
    if(got!=expected) {fprintf(stderr,"frame%d got%x expected%x\n",i-3,got,expected);return 5;}
    snes_frame_counter++;
  }
  if(dump_count!=(unsigned)strtoul(argv[2],NULL,10)) return 6;
  return 0;
}
'''
    c = tmp_path / "hold.c"
    c.write_text(source)
    exe = tmp_path / ("hold.exe" if os.name == "nt" else "hold")
    built = subprocess.run([compiler, "-std=c11", "-D_POSIX_C_SOURCE=200809L",
                            "-O1", str(c), "-o", str(exe)], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    cases = [
        ("press a 2\npress l 2\n", [0x100, 0x100, 0, 0x400, 0x400, 0, 0], 0),
        ("hold a 2\nhold a+l+r 2\nhold none 1\n", [0x100, 0x100, 0xD00, 0xD00, 0, 0], 0),
        ("hold a 2\ndump charged\nhold a+r 1\n", [0x100, 0x100, 0x900, 0], 1),
        ("hold p2:a+a 1\nwait 2\nhold p2:a+l 1\n", [0x100100, 0, 0, 0x100400, 0], 0),
        ("hold a\npress r 1\n", [0x100, 0x800, 0, 0], 0),
    ]
    for index, (script, timeline, dumps) in enumerate(cases):
        path = tmp_path / f"case{index}.txt"
        path.write_text(script)
        run = subprocess.run([str(exe), str(path), str(dumps), *[f"{x:x}" for x in timeline]],
                             capture_output=True, text=True)
        assert run.returncode == 0, script + run.stdout + run.stderr
    aspect = tmp_path / "aspect.txt"
    aspect.write_text("widescreen 0 # start narrow\nhold a 1\n"
                      "widescreen 1\nturbo on\nrenderer toggle\nhold a 1\n"
                      "wait 1\nwidescreen 0\nhold a 1\nquit\n")
    config = tmp_path / "private-config.ini"
    run = subprocess.run([str(exe), str(aspect), "aspect", str(config)],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert config.read_text() == "widescreen=0\n"
    assert "script f=0 widescreen=0" in run.stderr
    assert "script f=1 widescreen=1" in run.stderr
    assert "script f=3 widescreen=0" in run.stderr
    for text in ("hold a 0", "hold a -1", "hold a 10001", "hold a nonsense",
                 "hold a 9999999999999999999999999999999999999", "hold a 2 extra", "hold"):
        path = tmp_path / "bad.txt"
        path.write_text(text + "\n")
        run = subprocess.run([str(exe), str(path), "invalid"], capture_output=True, text=True)
        assert run.returncode == 0, text + run.stdout + run.stderr
    for text in ("widescreen", "widescreen -1", "widescreen 2", "widescreen on",
                 "widescreen 01", "widescreen +1", "widescreen 1x", "widescreen 1 extra",
                 "widescreen 0 1", "widescreen " + "1" * 300):
        path = tmp_path / "bad-aspect.txt"
        path.write_text(text + "\nhold a 1\n")
        run = subprocess.run([str(exe), str(path), "invalid"], capture_output=True, text=True)
        assert run.returncode == 0, text + run.stdout + run.stderr
        assert "script: expected 'widescreen 0' or 'widescreen 1'" in run.stderr
