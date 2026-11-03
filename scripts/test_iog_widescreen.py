#!/usr/bin/env python3
"""ROM-free map/phase/restore checks through the actual adapter and WsShadow.

PPU presentation setters, randomizer query and a failing allocator are stubs. This
does not execute the game or replace the required full-frame visual replay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "common_cpu_infra.h"
#include "snes/snes.h"
#include "snes/ws_shadow.h"
#include "iog_widescreen.h"

Snes *g_snes;
Ppu *g_ppu;
int snes_frame_counter;
static bool randomizer;
static bool fail_shadow_alloc;
void *IogTestCalloc(size_t count, size_t size) {
    return fail_shadow_alloc ? NULL : calloc(count,size);
}
bool IogRandomizerActive(void) { return randomizer; }
void PpuSetExtraSideSpace(Ppu *p, int left, int right, int bottom) {
    (void)bottom; p->extraLeftCur=left; p->extraRightCur=right;
}
void PpuSetWidescreenHudSplit(Ppu *p, uint8_t h, uint8_t l, uint8_t r) {
    (void)p; (void)h; (void)l; (void)r;
}
void PpuSetWidescreenHudAlwaysVisible(Ppu *p, bool on) { (void)p; (void)on; }
static unsigned assertions;
#define CHECK(x) do { assertions++; assert(x); } while (0)
static void word(unsigned at, unsigned value) {
    g_snes->ram[at]=value; g_snes->ram[at+1]=value>>8;
}
static unsigned readword(unsigned at) {
    return g_snes->ram[at] | (unsigned)g_snes->ram[at+1]<<8;
}
static void setup(bool swapped) {
    memset(g_snes->ram,0,0x20000); memset(g_ppu,0,sizeof(*g_ppu));
    g_ppu->extraLeftRight=43; g_ppu->bgmode=9;
    g_ppu->screenEnabled[0]=3;
    word(0x644,1); word(0x6ee,swapped?0x85:5);
    for (int i=0;i<2;i++) {
        int off=i*2, physical=i^swapped;
        word(0x692 + off,768); word(0x696 + off,1024);
        word(0x69a + off,3072); word(0x69e + off,0xa000 + i*0x2000);
        word(0x6ae + off,0x2000 + i*0x800); word(0x6ba + off,0x1000 + i*0x800);
        word(0x68a + off,104); word(0x68e + off,64);
        g_ppu->hScroll[physical]=104; g_ppu->vScroll[physical]=64;
        g_ppu->bgXsc[physical]=i?0x19:0x11;
        for (int n=0;n<3072;n++) g_snes->ram[0xa000 + i*0x2000 + n]=(n+i*31)&255;
        for (int n=0;n<256;n++) for (int q=0;q<4;q++)
            word(0x2000 + i*0x800 + n*8+q*2,(n*4+q)&0x3ff);
    }
}
static void check_layers(bool swapped) {
    setup(swapped);
    unsigned char memory[0x20000]; memcpy(memory,g_snes->ram,sizeof(memory));
    uint16_t vram[0x8000]; memcpy(vram,g_ppu->vram,sizeof(vram));
    uint8_t registers[PPU_SAVESTATE_REGS_SIZE]; memcpy(registers,g_ppu,sizeof(registers));
    IogWidescreenBeginFrame(); IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(64);
    CHECK(g_ppu->extraLeftCur==43 && g_ppu->extraRightCur==43);
    for (int i=0;i<2;i++) {
        int physical=i^swapped; uint16_t entry;
        CHECK(WsShadowLayerActive(physical));
        /* world (64,128): arrangement page0, row8,col4 -> byte132. */
        CHECK(WsShadowLookupWorldTile(physical,8,16,&entry));
        CHECK(entry==readword(0x2000 + i*0x800 + ((132+i*31)&255)*8));
        /* Authentic pixels always keep the supplied real VRAM entry. */
        CHECK(WsShadowTile(physical,16,128,104,0x1000,0xcafe)==0xcafe);
        /* Per-line horizontal/vertical phase, including a >1024 origin. */
        word(0x68a + i*2,1128); word(0x68e + i*2,1088);
        g_ppu->hScroll[physical]=1129; g_ppu->vScroll[physical]=1090;
        IogWidescreenBeforeLine(65);
        CHECK(WsShadowWorldX(physical)==1129 && WsShadowWorldY(physical)==1090);
        CHECK(WsShadowScrollX(physical)==1129 && WsShadowScrollY(physical)==1090);
        word(0x68a + i*2,104); word(0x68e + i*2,64);
        g_ppu->hScroll[physical]=104; g_ppu->vScroll[physical]=64;
    }
    CHECK(!memcmp(vram,g_ppu->vram,sizeof(vram)));
    /* Restore the deliberately varied scroll registers before comparison. */
    CHECK(!memcmp(registers,g_ppu,sizeof(registers)));
    CHECK(!memcmp(memory,g_snes->ram,sizeof(memory)));
    /* A restored/rearranged map must replace prior margin keys immediately. */
    uint16_t old; CHECK(WsShadowLookupWorldTile(swapped,8,16,&old));
    g_snes->ram[0xa000 + 132]^=1;
    IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(64);
    uint16_t fresh; CHECK(WsShadowLookupWorldTile(swapped,8,16,&fresh));
    CHECK(fresh!=old);
    /* World bounds refuse wrapped tiles; verified transparent char wins. */
    word(0x68a,0); word(0x68e,0);
    g_ppu->hScroll[swapped]=0; g_ppu->vScroll[swapped]=0;
    IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(1);
    CHECK(g_ppu->extraLeftCur==0);
    CHECK(WsShadowTile(swapped,-8,1,0,0x1000,0xbeef)==0);
}
static void check_native_edges(void) {
    for (unsigned swapped=0;swapped<2;swapped++) for (unsigned phase=0;phase<8;phase++) {
        setup(swapped);
        for (int i=0;i<2;i++) {
            int physical=i^swapped;
            word(0x68a+i*2,104+phase); g_ppu->hScroll[physical]=104+phase;
            unsigned base=PPU_bgTilemapAdr(g_ppu,physical);
            unsigned first=base+16*32+((104+phase)>>3);
            unsigned tx=(104+phase+255)>>3;
            unsigned last=base+16*32+(tx&31)+((tx&32)?0x400:0);
            g_ppu->vram[first]=0x6123+i; g_ppu->vram[last]=0x6456+i;
        }
        IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(64);
        for (int i=0;i<2;i++) {
            int physical=i^swapped; unsigned wx=104+phase; uint16_t entry;
            CHECK(WsShadowLookupWorldTile(physical,wx>>3,16,&entry) && entry==0x6123+i);
            CHECK(WsShadowLookupWorldTile(physical,(wx+255)>>3,16,&entry) && entry==0x6456+i);
            int start=(int)((wx+255)&~7u)-(int)wx;
            CHECK(WsShadowTile(physical,-(int)phase,128,wx,0x1000,0x6123+i)==0x6123+i);
            CHECK(WsShadowTile(physical,start,128,wx,0x1000,0x6456+i)==0x6456+i);
        }
    }
}
int main(void) {
    g_snes=calloc(1,sizeof(*g_snes)); g_ppu=calloc(1,sizeof(*g_ppu));
    g_snes->ram=calloc(1,0x20000);
    setup(false); fail_shadow_alloc=true;
    IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(1);
    CHECK(!WsShadowLayerActive(0) && !WsShadowLayerActive(1));
    CHECK(!g_ppu->extraLeftCur && !g_ppu->extraRightCur);
    fail_shadow_alloc=false;
    check_layers(false); check_layers(true);
    check_native_edges();
    setup(false); g_ppu->extraLeftRight=0;
    IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(12);
    CHECK(!WsShadowLayerActive(0) && !WsShadowLayerActive(1));
    setup(false); randomizer=true; IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(12);
    CHECK(!WsShadowLayerActive(0) && !g_ppu->extraLeftCur && !g_ppu->extraRightCur);
    randomizer=false;
    setup(false); word(0x644,0xfc); IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(12);
    CHECK(!WsShadowLayerActive(0) && !g_ppu->extraLeftCur && !g_ppu->extraRightCur);
    /* Known classroom storage is not a safe extra-room visibility extent. */
    setup(false); word(0x644,0x08); IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(12);
    CHECK(!WsShadowLayerActive(0) && !g_ppu->extraLeftCur && !g_ppu->extraRightCur);
    setup(false); word(0x69a,0xffff); IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(12);
    CHECK(!WsShadowLayerActive(0) && !g_ppu->extraLeftCur && !g_ppu->extraRightCur);
    setup(false); IogWidescreenBeforeDraw(); g_ppu->hScroll[0]=1023;
    word(0x68a,0); IogWidescreenBeforeLine(12);
    CHECK(!WsShadowLayerActive(0) && !g_ppu->extraLeftCur && !g_ppu->extraRightCur);
    setup(false); IogWidescreenBeforeDraw(); word(0x644,0xfc); IogWidescreenBeforeLine(12);
    CHECK(!WsShadowLayerActive(0) && !g_ppu->extraLeftCur && !g_ppu->extraRightCur);
    setup(false); g_ppu->bgmode=7; IogWidescreenBeforeDraw(); IogWidescreenBeforeLine(12);
    CHECK(!WsShadowLayerActive(0) && g_ppu->extraLeftCur==43 && g_ppu->extraRightCur==43);
    /* Clearing margins never touches the central256 pixel columns. */
    setup(false); g_ppu->renderPitch=342*4;
    uint32_t *pixels=malloc(240*g_ppu->renderPitch);
    g_ppu->renderBuffer=(uint8_t*)pixels;
    for(int n=0;n<240*342;n++) pixels[n]=0x12345678;
    IogWidescreenBeforeDraw();
    for(int y=0;y<240;y++) for(int x=0;x<342;x++)
        CHECK(pixels[y*342+x]==((x<43||x>=299)?0:0x12345678));
    printf("%u widescreen assertions passed\n",assertions);
    free(pixels); free(g_snes->ram); free(g_snes); free(g_ppu);
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="gcc")
    parser.add_argument("--out", type=Path,
                        default=ROOT / ".local/batch-001/wide-005/research/tests")
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT / ".local").resolve()):
        parser.error("fixture output must stay under .local/")
    out.mkdir(parents=True, exist_ok=True)
    source = out / "widescreen.c"
    source.write_text(HARNESS, encoding="utf-8")
    exe = out / "widescreen.exe"
    inputs = [ROOT / "src/iog_widescreen.c",
              ROOT / "snesrecomp/runner/src/snes/ws_shadow.c"]
    common = [args.compiler, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
               "-I", str(ROOT / "src"), "-I", str(ROOT / "snesrecomp/runner/src"),
               ]
    shadow = out / "ws_shadow.o"
    allocation_command = common + ["-Dcalloc=IogTestCalloc", "-c", str(inputs[1]), "-o", str(shadow)]
    allocation = subprocess.run(allocation_command, capture_output=True, text=True)
    (out / "allocator-build.log").write_text(allocation.stdout + allocation.stderr, encoding="utf-8")
    allocation.check_returncode()
    command = common + [str(source), str(inputs[0]), str(shadow), "-o", str(exe)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out / "build.log").write_text(build.stdout + build.stderr, encoding="utf-8")
    build.check_returncode()
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    (out / "run.log").write_text(run.stdout + run.stderr, encoding="utf-8")
    receipt = {"passed": run.returncode == 0, "commands": [allocation_command, command],
               "scope": "synthetic adapter/shared-shadow execution; no game ROM or engine run",
               "sources": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in inputs}, "stdout": run.stdout, "stderr": run.stderr}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    run.check_returncode()
    print(run.stdout.strip())


if __name__ == "__main__":
    main()
