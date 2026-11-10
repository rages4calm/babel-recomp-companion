#!/usr/bin/env python3
"""ROM-free execution of Gaia's finite preview geometry and frame lifecycle.

This does not qualify live sprites, room composition, graphics drivers or latency.
Private captured-picture replay separately exercises the actual PPU/HDMA pixels.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "iog_scene_view.h"
#include "snes/ppu.h"

int snes_frame_counter;
static unsigned checks;
#define CHECK(c) do { checks++; if (!(c)) { \
    fprintf(stderr,"line%d: %s\n",__LINE__,#c); exit(1); } } while(0)
static uint8_t ram[0x20000], before_ram[0x20000];
static Ppu ppu, before_ppu;
static void word(unsigned at,unsigned value) { ram[at]=(uint8_t)value;ram[at+1]=(uint8_t)(value>>8); }
static void fixture(void) {
    memset(ram,0,sizeof(ram));memset(&ppu,0,sizeof(ppu));
    word(0x644,1); word(0x68a,64);word(0x68e,64);
    ppu.bgmode=9;ppu.bgTileAdr=0x622;
    for(unsigned i=0;i<2;i++) {
        word(0x692+i*2,768);word(0x696+i*2,1024);
        word(0x69a+i*2,3072);word(0x69e + i*2,0xa000+i*0x2000);
        word(0x6ae + i*2,0x2000+i*0x800);word(0x6ba+i*2,0x1000+i*0x800);
        ppu.bgXsc[i]=(uint8_t)(0x11+i*8);
    }
}
static IogSceneViewSource source(void) {
    IogSceneViewSource s;
    memcpy(before_ram,ram,sizeof(ram));memcpy(&before_ppu,&ppu,sizeof(ppu));
    CHECK(IogSceneViewReadSource(ram,sizeof(ram),&ppu,false,&s));
    CHECK(!memcmp(before_ram,ram,sizeof(ram))&&!memcmp(&before_ppu,&ppu,sizeof(ppu)));
    return s;
}
static void gates(void) {
    IogSceneViewSource s;
    CHECK(!IogSceneViewReadSource(NULL,sizeof(ram),&ppu,false,&s)&&s.gate==kIogSceneViewNoSource);
    CHECK(!IogSceneViewReadSource(ram,sizeof(ram)-1,&ppu,false,&s));
    CHECK(!IogSceneViewReadSource(ram,sizeof(ram),NULL,false,&s));
    CHECK(!IogSceneViewReadSource(ram,sizeof(ram),&ppu,false,NULL));
    fixture();s=source();CHECK(s.gate==kIogSceneViewReady&&s.scene==1&&s.world_width==768&&s.camera_x==64);
    word(0x644,12);s=source();CHECK(s.gate==kIogSceneViewReady);
    word(0x644,8);s=source();CHECK(s.gate==kIogSceneViewUnsupportedScene);
    word(0x644,255);s=source();CHECK(s.gate==kIogSceneViewUnsupportedScene);
    fixture();CHECK(IogSceneViewReadSource(ram,sizeof(ram),&ppu,true,&s)&&s.gate==kIogSceneViewRandomizer);
    fixture();ppu.bgmode=7;s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();ppu.bgmode|=16;s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();ppu.bgXsc[0]|=2;s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();word(0x69a,3071);s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();word(0x69e,0xa001);s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();word(0x6ae,0x2800);s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();word(0x692,767);s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();word(0x696,0x2100);s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();word(0x68a,513);s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();word(0x68e,801);s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();ram[0x6ef]=8;s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    fixture();ram[0x6ee]=0x80;ppu.bgXsc[0]=0x19;ppu.bgXsc[1]=0x11;s=source();CHECK(s.gate==kIogSceneViewReady);
    /* World eligibility must not silently widen the legacy guest-culling
     * preview, even when the underlying live map layout is identical. */
    const unsigned rooms[]={0x01,0x0c,0x0e,0x0f,0x12,0x15,0x1e,0x23,0x25,0x26,
        0x27,0x28,0x29,0x2d,0x3d,0x3e,0x3f,0x40,0x41,0x42,0x45,0x46,0x4f,0x51,0x53,
        0x55,0x61,0x62,0x64,0x67,0x6d,0x6f,0x85,0x86,0x8a,0x8b,0xa7,0xb6,0xb8,0xcc,
        0xcd,0xce,0xdd,0xde,0xdf,0xe0,0xe1,0xe2,0xe3,0xea};
    for(unsigned i=0;i<sizeof(rooms)/sizeof(rooms[0]);i++) {
        fixture();word(0x644,rooms[i]);
        CHECK(IogSceneViewReadWorldSource(ram,sizeof(ram),&ppu,false,&s)&&s.gate==kIogSceneViewReady);
        CHECK(IogSceneViewReadSource(ram,sizeof(ram),&ppu,false,&s));
        CHECK(s.gate==((rooms[i]==1||rooms[i]==12)?kIogSceneViewReady:kIogSceneViewUnsupportedScene));
    }
    const unsigned rejected[]={0,2,3,6,8,0x31,255,256,65535};
    for(unsigned i=0;i<sizeof(rejected)/sizeof(rejected[0]);i++) {
        fixture();word(0x644,rejected[i]);
        CHECK(IogSceneViewReadWorldSource(ram,sizeof(ram),&ppu,false,&s)&&s.gate==kIogSceneViewUnsupportedScene);
    }
    fixture();word(0x644,0xdd);ppu.bgmode=7;
    CHECK(IogSceneViewReadWorldSource(ram,sizeof(ram),&ppu,false,&s)&&s.gate==kIogSceneViewUnsupportedLayout);
    fixture();word(0x644,0xb6);
    CHECK(IogSceneViewReadWorldSource(ram,sizeof(ram),&ppu,true,&s)&&s.gate==kIogSceneViewRandomizer);
    /* Signed camera shake is a separate world contract; the old guest-
     * culling preview remains strict and never treats FFFF as a huge map. */
    fixture();word(0x68e,0xffff);
    CHECK(IogSceneViewReadWorldSource(ram,sizeof(ram),&ppu,false,&s)&&s.gate==kIogSceneViewReady);
    s=source();CHECK(s.gate==kIogSceneViewUnsupportedLayout);
    const unsigned good[]={0xfff0,0xffff,0,1,512,528};
    for(unsigned i=0;i<sizeof(good)/sizeof(good[0]);i++){
        fixture();word(0x68a,good[i]);
        CHECK(IogSceneViewReadWorldSource(ram,sizeof(ram),&ppu,false,&s)&&s.gate==kIogSceneViewReady);
    }
    const unsigned bad[]={0xffef,529,0x7fff,0x8000};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++){
        fixture();word(0x68a,bad[i]);
        CHECK(IogSceneViewReadWorldSource(ram,sizeof(ram),&ppu,false,&s)&&s.gate==kIogSceneViewUnsupportedLayout);
    }
}
static void lifecycle_and_pixels(void) {
    IogSceneView view; IogSceneViewGeometry g={777,888,9,true}, old=g;
    IogSceneViewSnapshot snap, frozen;
    fixture();IogSceneViewSource s=source();
    const char *off[]={NULL,"","0","true","01","1 ","-1"};
    for(unsigned i=0;i<sizeof(off)/sizeof(off[0]);i++) {
        IogSceneViewInit(&view,off[i]);CHECK(!view.enabled);
        CHECK(!IogSceneViewPrepare(&view,&s,1920,1080,0,true,&g));CHECK(!memcmp(&g,&old,sizeof(g)));
        IogSceneViewBeginFrame(&view);IogSceneViewEndFrame(&view,99);
        CHECK(!IogSceneViewGetSnapshot(&view,&snap));
    }
    IogSceneViewInit(&view,"1");CHECK(view.enabled&&sizeof(view)<512);
    CHECK(IogSceneViewPrepare(&view,&s,1920,1080,0,true,&g)&&g.width==342&&g.extra==43&&g.centered_hud);
    CHECK(!IogSceneViewGetSnapshot(&view,&snap));IogSceneViewBeginFrame(&view);IogSceneViewEndFrame(&view,7);
    CHECK(IogSceneViewGetSnapshot(&view,&snap)&&snap.frame==7&&snap.source.camera_x==64);frozen=snap;
    uint64_t generation=snap.generation;
    s.camera_x=72;
    CHECK(IogSceneViewPrepare(&view,&s,1920,1080,0,true,&g));
    CHECK(IogSceneViewGetSnapshot(&view,&snap)&&!memcmp(&snap,&frozen,sizeof(snap)));
    IogSceneViewBeginFrame(&view);CHECK(!IogSceneViewGetSnapshot(&view,&snap));IogSceneViewEndFrame(&view,8);
    CHECK(IogSceneViewGetSnapshot(&view,&snap)&&snap.source.camera_x==72&&snap.generation==generation);
    /* Host prepare runs again before present; it must not erase completion. */
    CHECK(IogSceneViewPrepare(&view,&s,1920,1080,0,true,&g));CHECK(IogSceneViewGetSnapshot(&view,&snap)&&snap.frame==8);
    size_t row=(size_t)g.width*4,pitch=row+13,bytes=pitch*224;
    uint8_t *pixels=malloc(row*224),*dst=malloc(bytes);CHECK(pixels&&dst);
    for(size_t i=0;i<row*224;i++)pixels[i]=(uint8_t)(i*17+i/row);
    for(int a=0;a<=4;a++) {
        memset(dst,0xa5,bytes);CHECK(IogSceneViewDraw(&view,dst,pitch,pixels,g.width,224,a/4.));
        for(int y=0;y<224;y++) {
            CHECK(!memcmp(dst+(size_t)y*pitch,pixels+(size_t)y*row,row));
            for(size_t x=row;x<pitch;x++)CHECK(dst[(size_t)y*pitch+x]==0xa5);
        }
    }
    memset(dst,0xa5,bytes);
    CHECK(!IogSceneViewDraw(&view,dst,pitch,pixels,g.width,224,NAN));
    CHECK(!IogSceneViewDraw(&view,dst,pitch,pixels,g.width,224,INFINITY));
    CHECK(!IogSceneViewDraw(&view,dst,pitch,pixels,g.width,224,-.1));
    CHECK(!IogSceneViewDraw(&view,dst,pitch,pixels,g.width,224,1.1));
    CHECK(!IogSceneViewDraw(&view,dst,row-1,pixels,g.width,224,1));
    CHECK(!IogSceneViewDraw(&view,dst,pitch,pixels,g.width-2,224,1));
    CHECK(!IogSceneViewDraw(&view,dst,pitch,pixels,g.width,223,1));
    for(size_t i=0;i<bytes;i++)CHECK(dst[i]==0xa5);
    CHECK(IogSceneViewPrepare(&view,&s,2520,1080,0,true,&g)&&g.width==448&&g.extra==96);
    CHECK(!IogSceneViewGetSnapshot(&view,&snap));
    CHECK(IogSceneViewPrepare(&view,&s,3840,1080,0,true,&g)&&g.width==448); /* 32:9 letterbox */
    CHECK(IogSceneViewPrepare(&view,&s,1440,1080,0,true,&g)&&g.width==256&&!g.centered_hud);
    CHECK(IogSceneViewPrepare(&view,&s,1920,1080,1,true,&g)&&g.width==398);
    CHECK(IogSceneViewPrepare(&view,&s,1920,1080,2,true,&g)&&g.width==448);
    CHECK(IogSceneViewPrepare(&view,&s,1920,1080,0,false,&g)&&g.width==256);
    s.gate=kIogSceneViewUnsupportedScene;s.scene=8;
    CHECK(IogSceneViewPrepare(&view,&s,2520,1080,0,true,&g)&&g.width==256&&!g.centered_hud);
    s.scene=255;CHECK(IogSceneViewPrepare(&view,&s,2520,1080,0,true,&g)&&g.width==256);
    CHECK(!IogSceneViewPrepare(&view,&s,0,1080,0,true,&g));
    IogSceneViewEndFrame(&view,9);CHECK(!IogSceneViewGetSnapshot(&view,&snap));
    CHECK(!IogSceneViewPrepare(&view,&s,1920,-1,0,true,&g));
    CHECK(!IogSceneViewPrepare(&view,&s,1920,1080,-1,true,&g));
    CHECK(!IogSceneViewPrepare(&view,&s,1920,1080,3,true,&g));
    generation=view.generation;IogSceneViewReset(&view);
    CHECK(view.enabled&&!view.prepared&&!view.complete&&view.generation==generation+1);
    CHECK(!IogSceneViewDraw(&view,dst,pitch,pixels,342,224,1));
    CHECK(!IogSceneViewGetSnapshot(&view,&snap));
    IogSceneViewInit(&view,"0");CHECK(!IogSceneViewDraw(&view,dst,pitch,pixels,342,224,1));
    free(pixels);free(dst);
}
int main(void) { gates();lifecycle_and_pixels();printf("%u scene-view assertions passed\n",checks);return 0; }
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', default='cc')
    p.add_argument('--out', type=Path, default=ROOT/'.local/scene-view-tests')
    args = p.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT/'.local').resolve()):
        p.error('test output must stay under ignored .local/')
    out.mkdir(parents=True, exist_ok=True)
    source = out/'scene_view.c'
    source.write_text(HARNESS, encoding='utf-8')
    inputs = [ROOT/'src/iog_scene_view.c', ROOT/'src/iog_visual_objects.c',
              ROOT/'snesrecomp/runner/src/widescreen.c']
    exe = out/'scene_view.exe'
    command = [args.compiler,'-std=c11','-O1','-Wall','-Wextra','-Werror',
               '-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),
               str(source),*[str(s) for s in inputs],'-o',str(exe)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr, encoding='utf-8')
    build.check_returncode()
    env = {k:v for k,v in os.environ.items() if not k.startswith(('SNESRECOMP_','IOG_'))}
    run = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
    (out/'run.log').write_text(run.stdout+run.stderr, encoding='utf-8')
    result = dict(passed=run.returncode==0,command=command,
        scope='ROM-free scene gate, geometry, completed-frame snapshot/reset and original presenter execution; no game/GPU',
        sources={str(s.relative_to(ROOT)):hashlib.sha256(s.read_bytes()).hexdigest()
                 for s in inputs+[ROOT/'src/iog_scene_view.h']},
        stdout=run.stdout,stderr=run.stderr)
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    run.check_returncode()
    print(run.stdout.strip())


if __name__=='__main__': main()
