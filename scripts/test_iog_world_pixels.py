#!/usr/bin/env python3
"""Compare the detached Mode1 span path with the actual pixel reference.

Default fixtures contain no ROM data. Optional private snapshot prefixes test
the same algorithms using immutable PPU register/VRAM/CGRAM/OAM captures; these
are snapshot picture tests, not replay of guest IRQs or campaign qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "iog_world_pixels.h"
#include "snes/ppu.h"
#include "snes/snes.h"
#include "snes/ws_shadow.h"
#include "debug_server.h"

Snes *g_snes; int snes_frame_counter; unsigned char g_snesrecomp_last_hdmaen;
static unsigned callbacks, checks, cases;
uint64_t snesrecomp_host_now_ns(void) { callbacks++; return callbacks; }
void debug_server_on_ppu_line(int l) {(void)l;callbacks++;}
void debug_server_on_ppu_line_drawn(int l,int r,unsigned m) {(void)l;(void)r;(void)m;callbacks++;}
void debug_server_on_oam_render(void) {callbacks++;}
void debug_server_on_ppu_window(int l,int z,const int16_t *e,unsigned n,uint8_t b) {(void)l;(void)z;(void)e;(void)n;(void)b;callbacks++;}
void debug_server_on_oam_write(int h,uint16_t i,uint16_t v) {(void)h;(void)i;(void)v;callbacks++;}
void debug_server_on_vram_write(uint32_t a,uint8_t v) {(void)a;(void)v;callbacks++;}
uint16_t WsShadowTile(int l,int x,uint32_t y,uint16_t s,uint16_t a,uint16_t t) {(void)l;(void)x;(void)y;(void)s;(void)a;callbacks++;return t;}
bool WsShadowLayerActive(int l) {(void)l;callbacks++;return false;}
uint32_t WsShadowWorldX(int l) {(void)l;callbacks++;return 0;}
uint32_t WsShadowPresentWorldY(int l,int x) {(void)l;(void)x;callbacks++;return 0;}
uint32_t WsShadowScrollY(int l) {(void)l;callbacks++;return 0;}
void WsShadowOnVramWrite(uint16_t a,uint16_t v) {(void)a;(void)v;callbacks++;}
static void external(Ppu *p,uint y,bool sub,void *context) {(void)p;(void)y;(void)sub;(void)context;callbacks++;}
#define CHECK(x) do {checks++;if(!(x)){fprintf(stderr,"FAIL %d: %s case=%u\n",__LINE__,#x,cases);exit(2);}}while(0)
static Snes machine;
static Ppu live, live_before, source, reference, candidate;
static uint32_t expected[256*240+32],actual[256*240+32];
static uint32_t random_state=0x5217bdea;
static uint32_t next(void){random_state^=random_state<<13;random_state^=random_state>>17;random_state^=random_state<<5;return random_state;}
static uint16_t object_pixels[4][16*16];
static PpuExtraObject objects[4];
static uint64_t hash=UINT64_C(1469598103934665603);
static void add_hash(const void *p,size_t n){const uint8_t*b=p;for(size_t i=0;i<n;i++)hash=(hash^b[i])*UINT64_C(1099511628211);}

static void fixture(unsigned n){
 memset(&source,0,sizeof source);ppu_reset(&source);
 source.bgmode=1|(n&1?8:0);source.inidisp=(n%17?0:0x80)|(n%16);
 source.lastBrightnessMult=255;source.obsel=2;source.bgTileAdr=0x0420;
 source.bgXsc[0]=0x61;source.bgXsc[1]=0x69;source.bgXsc[2]=0x71;
 source.screenEnabled[0]=(uint8_t)next()&31;source.screenEnabled[1]=(uint8_t)next()&31;
 source.screenWindowed[0]=(uint8_t)next()&31;source.screenWindowed[1]=(uint8_t)next()&31;
 source.windowsel=next()&0xffffff;source.wbgobjlog=(uint16_t)next();
 source.window1left=n&255;source.window1right=(n*7)&255;
 source.window2left=(n*3)&255;source.window2right=(n*11)&255;
 source.cgadsub=(uint8_t)n;source.cgwsel=(uint8_t)(n>>1);source.fixedColor=(uint16_t)next()&0x7fff;
 source.mosaic=0;source.widescreenLineEnhancer=external;source.widescreenLineEnhancerContext=&machine;
 for(unsigned i=0;i<4;i++){source.hScroll[i]=(uint16_t)next()&1023;source.vScroll[i]=(uint16_t)next()&1023;}
 for(unsigned i=0;i<32768;i++)source.vram[i]=(uint16_t)next();
 for(unsigned i=0;i<256;i++)source.cgram[i]=(uint16_t)next()&0x7fff;
 for(unsigned i=0;i<128;i++){source.oam[i*2]=0xf000;source.oam[i*2+1]=0;}
 for(unsigned i=0;i<4;i++){
  for(unsigned j=0;j<256;j++)object_pixels[i][j]=j%7?0x8000|(next()&0x7fff):0;
  objects[i]=(PpuExtraObject){(int32_t)(n*5+i*31)%290-16,0,16,16,16,(uint8_t)i,(uint8_t)(n&1),0,i+1,object_pixels[i]};
 }
 PpuSetExtraObjects(&source,objects,4);
}

static void pair(int line){
 reference=source;candidate=source;memset(expected,0xa5,sizeof expected);memset(actual,0xa5,sizeof actual);
 reference.renderBuffer=(uint8_t*)expected;candidate.renderBuffer=(uint8_t*)actual;
 reference.renderPitch=candidate.renderPitch=256*4;
 reference.renderFlags=source.renderFlags&~kPpuRenderFlags_NewRenderer;
 candidate.renderFlags=source.renderFlags;
 reference.timeOver=candidate.timeOver=true;reference.rangeOver=candidate.rangeOver=true;
 unsigned before=callbacks;
 PpuDrawDetachedLine(&reference,0);IogWorldPixelsDrawLine(&candidate,0);
 PpuDrawDetachedLine(&reference,line);IogWorldPixelsDrawLine(&candidate,line);
 if(memcmp(expected,actual,sizeof actual)){
  for(unsigned i=0;i<256*240+32;i++)if(expected[i]!=actual[i]){fprintf(stderr,"pixel mismatch line=%d x=%u expected=%08x actual=%08x\n",line,i%256,expected[i],actual[i]);break;}
  CHECK(0);
 }
 CHECK(callbacks==before);CHECK(candidate.renderFlags==source.renderFlags);
 CHECK(candidate.rangeOver&&candidate.timeOver);CHECK(candidate.evenFrame==source.evenFrame);
 CHECK(!memcmp(candidate.vram,source.vram,sizeof source.vram));CHECK(!memcmp(candidate.cgram,source.cgram,sizeof source.cgram));
 CHECK(!memcmp(candidate.oam,source.oam,sizeof source.oam));CHECK(!memcmp(candidate.highOam,source.highOam,sizeof source.highOam));
 CHECK(!memcmp(&candidate,&source,PPU_SAVESTATE_REGS_SIZE));CHECK(!memcmp(&live,&live_before,sizeof live));
 CHECK(candidate.widescreenLineEnhancer==external&&candidate.widescreenLineEnhancerContext==&machine);
 add_hash(actual+(line-1)*256,256*4);cases++;
}

static unsigned read32(FILE*f){unsigned v=0;for(unsigned i=0;i<4;i++){int b=fgetc(f);CHECK(b!=EOF);v|=(unsigned)b<<(8*i);}return v;}
static void snapshot(const char*path){
 FILE*f=fopen(path,"rb");CHECK(f);char magic[8];CHECK(fread(magic,1,8,f)==8&&!memcmp(magic,"IOGPIX01",8));
 fixture(31);unsigned a[40];for(unsigned i=0;i<40;i++)a[i]=read32(f);
 source.inidisp=a[0];source.obsel=a[1];source.bgmode=a[2];source.mosaic=a[3];source.bgTileAdr=a[4];source.m7sel=a[5];source.setini=a[6];source.fixedColor=a[7];source.windowsel=a[8];source.wbgobjlog=a[9];
 source.screenEnabled[0]=a[10];source.screenEnabled[1]=a[11];source.screenWindowed[0]=a[12];source.screenWindowed[1]=a[13];source.cgwsel=a[14];source.cgadsub=a[15];
 for(unsigned i=0;i<4;i++){source.bgXsc[i]=a[16+i];source.hScroll[i]=a[20+i];source.vScroll[i]=a[24+i];}
 source.window1left=a[28];source.window1right=a[29];source.window2left=a[30];source.window2right=a[31];
 for(unsigned i=0;i<8;i++)source.m7matrix[i]=(int16_t)a[32+i];
 CHECK(fread(source.vram,1,sizeof source.vram,f)==sizeof source.vram);CHECK(fread(source.cgram,1,sizeof source.cgram,f)==sizeof source.cgram);
 CHECK(fread(source.oam,1,sizeof source.oam,f)==sizeof source.oam);CHECK(fread(source.highOam,1,sizeof source.highOam,f)==sizeof source.highOam);CHECK(fgetc(f)==EOF);fclose(f);
 CHECK((source.bgmode&7)==1);PpuSetExtraObjects(&source,NULL,0);
 for(int line=1;line<=224;line++)pair(line);
 /* The private world path uses extraObjects, not the live actor OAM. Test
  * real captured palette/tile state with independently owned object rows. */
 for(unsigned i=0;i<128;i++)source.oam[i*2]=0xf000;
 PpuSetExtraObjects(&source,objects,4);
 for(unsigned i=0;i<4;i++)objects[i].y=0;
 for(int line=1;line<=16;line++)pair(line);
}

int main(int argc,char**argv){
 g_snes=&machine;machine.ppu=&live;ppu_reset(&live);live_before=live;
 const int lines[]={1,2,8,16,112,224,240};
 for(unsigned n=0;n<512;n++){
  fixture(n);source.renderFlags=(n&1?kPpuRenderFlags_NewRenderer:0)|(n&2?kPpuRenderFlags_NoSpriteLimits:0);
  for(unsigned j=0;j<sizeof lines/sizeof lines[0];j++)pair(lines[j]);
 }
 /* Captured-line effects can change between rows; every row is compared
  * after its own brightness/scroll/palette/math/window inputs are applied. */
 fixture(39);
 for(int line=1;line<=224;line++){
  source.inidisp=line&15;source.hScroll[0]=(line*7)&1023;source.vScroll[1]=(line*3)&1023;
  source.cgram[line&255]=(uint16_t)(line*139)&0x7fff;source.cgadsub=(uint8_t)line;source.cgwsel=(line>>2)&255;
  source.window1left=line&255;source.window1right=(line+48)&255;pair(line);
 }
 for(int i=1;i<argc;i++)snapshot(argv[i]);
 source.renderFlags=kPpuRenderFlags_NewRenderer|kPpuRenderFlags_NoSpriteLimits;candidate=source;
 IogWorldPixelsDrawLine(NULL,1);IogWorldPixelsDrawLine(&candidate,-1);IogWorldPixelsDrawLine(&candidate,241);IogWorldPixelsDrawLine(&live,1);
 CHECK(!memcmp(&candidate,&source,sizeof source));CHECK(!memcmp(&live,&live_before,sizeof live));
 printf("world pixels PASS cases=%u pixels=%u assertions=%u digest=%016llx\n",cases,cases*256,checks,(unsigned long long)hash);return 0;
}
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot_input(prefix, output):
    """Serialize only captured picture inputs, retaining every source hash."""
    paths = {name: Path(str(prefix)+'.'+name) for name in
             ('regs.json', 'vram.bin', 'cgram.bin', 'oam.bin')}
    regs = json.loads(paths['regs.json'].read_text(encoding='utf-8'))
    scalar = ('inidisp','obsel','bgmode','mosaic','bg_tile_adr','m7sel','setini',
              'fixed_color','windowsel','wbgobjlog','tm','ts','tmw','tsw','cgwsel','cgadsub')
    values = [regs[name] for name in scalar]
    for name in ('bgsc','hscroll','vscroll','window','m7matrix'):
        values.extend(regs[name])
    assert len(values) == 40
    payload = b'IOGPIX01'+struct.pack('<40I', *(n & 0xffffffff for n in values))
    for name, size in (('vram.bin',65536),('cgram.bin',512),('oam.bin',544)):
        data = paths[name].read_bytes()
        assert len(data) == size, (paths[name], len(data), size)
        payload += data
    output.write_bytes(payload)
    return dict(prefix=str(prefix), frame=regs['frame'],
                sources={str(p):sha(p) for p in paths.values()},
                serialized_sha256=sha(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='cc')
    parser.add_argument('--out', type=Path, default=ROOT/'.local/world-pixel-tests')
    parser.add_argument('--snapshot-prefix', type=Path, action='append', default=[])
    args = parser.parse_args()
    output = args.out.resolve()
    private = (ROOT/'.local').resolve()
    if not output.is_relative_to(private):
        parser.error('test outputs must remain under ignored .local/')
    output.mkdir(parents=True,exist_ok=True)
    snapshots = []
    for i,prefix in enumerate(args.snapshot_prefix):
        prefix = prefix.resolve()
        if not prefix.is_relative_to(private):
            parser.error('snapshot inputs must remain under ignored .local/')
        target = output/f'picture-{i:03}.bin'
        snapshots.append(snapshot_input(prefix,target))
    source = output/'world_pixels.c'
    source.write_text(HARNESS,encoding='utf-8',newline='\n')
    inputs = [ROOT/'src/iog_world_pixels.c',
              ROOT/'snesrecomp/runner/src/snes/ppu.c',
              ROOT/'snesrecomp/runner/src/snes/ppu_legacy.c',
              ROOT/'snesrecomp/runner/src/snes/hd_jobs.c']
    binary = output/'world_pixels.exe'
    command = [args.compiler,'-std=c11','-O2','-Wall','-Wextra','-pthread',
               '-DSNESRECOMP_TRACE=1','-DSNESRECOMP_REVERSE_DEBUG=0',
               '-DSNESRECOMP_INTERP_PROFILE=1',
               '-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),
               str(source),*[str(p) for p in inputs],'-o',str(binary)]
    build_env = {**os.environ, 'TMP':str(output), 'TEMP':str(output),
                 'TMPDIR':str(output)}
    build = subprocess.run(command,capture_output=True,text=True,env=build_env,
                           timeout=120)
    (output/'build.log').write_text(build.stdout+build.stderr,encoding='utf-8')
    build.check_returncode()
    env = {k:v for k,v in os.environ.items() if not k.startswith(('SNESRECOMP_','IOG_'))}
    results = []
    for name, extra in [('default-span',{}),
                        ('explicit-span',{'IOG_WORLD_SPAN_PIXELS':'1'}),
                        ('explicit-reference',{'IOG_WORLD_SPAN_PIXELS':'0'}),
                        ('forced-reference',{'IOG_WORLD_SPAN_PIXELS':'1',
                                             'IOG_WORLD_REFERENCE_PIXELS':'1'})]:
        run = subprocess.run([str(binary),*[str(output/f'picture-{i:03}.bin')
                              for i in range(len(snapshots))]],
                             env={**env,**extra},capture_output=True,text=True,
                             timeout=45)
        (output/(name+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
        results.append(dict(name=name,environment=extra,exit_code=run.returncode,
                            stdout=run.stdout,stderr=run.stderr))
    passed = all(r['exit_code']==0 for r in results)
    result = dict(passed=passed,command=command,cases=results,snapshots=snapshots,
                  sources={str(p.relative_to(ROOT)):sha(p) for p in inputs+
                           [ROOT/'src/iog_world_pixels.h',Path(__file__)]},
                  scope='Real PPU Mode1 detached span/pixel equality, immutable picture inputs, host/live-state isolation; no game replay/GPU/FPS/campaign claim')
    (output/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
