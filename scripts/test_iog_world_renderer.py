#!/usr/bin/env python3
"""ROM-free world-renderer publication, epoch, geometry and output checks.

Includes the real title module and actual framework types. Bounded scene,
visual-source and detached-pixel stubs isolate lifecycle and memory contracts;
private gameplay/captured-PPU tests qualify the real pixel and CPU paths.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "iog_world_renderer.c"
static Snes machine;static Cart cart;static Ppu original,before_ppu;
static uint8_t ram[131072],rom[2097152],before_ram[131072];
CpuState g_cpu;Snes *g_snes=&machine;Ppu *g_ppu=&original;
static unsigned checks,detached_lines,visual_builds;static bool randomizer,scene_ready=true;
static uint8_t source_field[256*224*4];
#define CHECK(c) do{checks++;if(!(c)){fprintf(stderr,"line%d: %s\n",__LINE__,#c);exit(1);}}while(0)
static void word(unsigned at,unsigned value){ram[at]=(uint8_t)value;ram[at+1]=(uint8_t)(value>>8);}
bool IogRandomizerActive(void){return randomizer;}
void sha256_compute(const uint8_t*p,size_t n,uint8_t hash[32]){CHECK(p==rom&&n==sizeof(rom));memset(hash,0,32);}
bool IogSceneViewReadWorldSource(const uint8_t*r,size_t n,const Ppu*p,bool random,IogSceneViewSource*out){
 CHECK(r==ram&&n==sizeof(ram)&&p==g_ppu&&!random);memset(out,0,sizeof(*out));
 out->scene=(uint16_t)Word(r,0x644);out->gate=scene_ready?kIogSceneViewReady:kIogSceneViewUnsupportedScene;return true;
}
IogVisualStatus IogVisualObjectsBuild(const IogVisualSource*in,const IogVisualViewport*v,IogVisualFrame*out){
 CHECK(in->ram==s.active_ram&&in->rom==rom&&in->stock_identity_verified&&v->height<=512);
 visual_builds++;memset(out,0,sizeof(*out));out->status=kIogVisualReady;out->viewport=*v;out->scene=(uint16_t)Word(in->ram,0x644);
 out->part_count=1;IogVisualPart*p=&out->parts[0];p->x=4;p->y=4;p->width=p->height=8;p->order=1;
 for(unsigned n=0;n<64;n++){p->indices[n]=193;p->pixels[n]=0x8001;}
 return kIogVisualReady;
}
bool PpuBindOverlaySurface(Ppu*p,PpuOverlaySource source,uint8_t*pixels,size_t pitch){
 CHECK(p==g_ppu&&source==kPpuOverlaySource_Bg3&&pitch==256*4);
 p->overlayRenderBuffer[source]=pixels;p->overlayRenderPitch[source]=(uint32_t)pitch;return true;
}
bool PpuSetOverlayCapture(Ppu*p,PpuOverlaySource source,int x,int y,int w,int h,uint8_t flags){
 CHECK(p==g_ppu&&source==kPpuOverlaySource_Bg3&&x==0&&y==0&&w==256&&h==224&&!flags);return true;
}
void PpuClearOverlayBindings(Ppu*p){memset(p->overlayRenderBuffer,0,sizeof(p->overlayRenderBuffer));}
void PpuClearOverlayCaptures(Ppu*p){memset(p->overlayCaptures,0,sizeof(p->overlayCaptures));}
void PpuSetExtraSpace(Ppu*p,uint16_t n){CHECK(p!=g_ppu&&!n);p->extraLeftRight=0;}
void PpuSetWidescreenHudSplit(Ppu*p,uint8_t h,uint8_t l,uint8_t r){CHECK(p!=g_ppu&&!h&&!l&&!r);}
void PpuSetExtraObjects(Ppu*p,const PpuExtraObject*objects,size_t count){p->extraObjects=objects;p->extraObjectCount=count;}
void PpuDrawDetachedLine(Ppu*p,int line){
 CHECK(p!=g_ppu&&(line==0||line==1));if(!line)return;detached_lines++;
 CHECK(p->renderPitch==1024&&!p->renderVram&&!p->hdFrame&&!p->overlayRenderBuffer[2]);
 for(unsigned n=0;n<256;n+=2)CHECK(p->oam[n]==0xf000);
 uint32_t*row=(uint32_t*)p->renderBuffer;
 for(unsigned x=0;x<256;x++)row[x]=0xff000000u|((p->hScroll[0]+x)&1023)|(((p->vScroll[0]+1)&1023)<<10);
}
static void fixture(void){
 if(s.audit)fclose(s.audit);memset(&s,0,sizeof(s));memset(ram,0,sizeof(ram));memset(rom,0,sizeof(rom));
 memset(g_ppu,0,sizeof(*g_ppu));memset(g_snes,0,sizeof(*g_snes));memset(&cart,0,sizeof(cart));memset(&g_cpu,0,sizeof(g_cpu));
 g_cpu.ram=ram;g_snes->ram=ram;g_snes->ppu=g_ppu;g_snes->cart=&cart;
 cart.rom=rom;cart.type=CART_HIROM;cart.romImageSize=cart.romSize=sizeof(rom);
 s.initialized=s.enabled=s.stock=true;s.extent_quarters=6;randomizer=false;scene_ready=true;
 word(0x644,1);word(0x68a,256);word(0x68e,256);word(0x692,768);word(0x694,768);word(0x696,1024);word(0x698,1024);
 word(0x69e,0xa000);word(0x6a0,0xc000);word(0x6ae,0x2000);word(0x6b0,0x2800);
 word(0x2000,0x1234);word(0x2002,0x2345);word(0x2004,0x3456);word(0x2006,0x4567);
 word(0x2800,0x5678);word(0x2802,0x6789);word(0x2804,0x789a);word(0x2806,0x89ab);
 g_ppu->bgmode=1;g_ppu->hScroll[0]=g_ppu->hScroll[1]=256;g_ppu->vScroll[0]=g_ppu->vScroll[1]=256;
 g_ppu->bgTileAdr=0x622;g_ppu->bgXsc[0]=0x11;g_ppu->bgXsc[1]=0x19;
    int width=0,height=0;IogWorldGeometry(1280,720,&width,&height);CHECK(width==598&&height==336);
 for(unsigned i=0;i<sizeof(source_field);i++)source_field[i]=(uint8_t)(i*13+7);
 detached_lines=visual_builds=0;
}
static void publication(void){
 IogWorldCaptureAtCompose(&g_cpu,0x83c714);CHECK(s.pending&&!s.composed&&!s.active);
 for(unsigned n=0;n<544;n++)ram[0x422+n]=(uint8_t)(n*7+11);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);CHECK(s.composed&&!s.active);
 IogWorldBeforeNmi();for(unsigned n=0;n<256;n++)g_ppu->oam[n]=(uint16_t)Word(ram,0x422+n*2);
 memcpy(g_ppu->highOam,ram+0x622,32);g_ppu->oamWriteCount++;IogWorldAfterNmi();
 CHECK(s.active&&s.publish_sequence==s.compose_sequence);
}
static void phase_queue(void){
 fixture();memcpy(before_ram,ram,sizeof(ram));
 IogWorldBeforeNmi();g_ppu->oamWriteCount++;IogWorldAfterNmi();CHECK(!s.active);
 publication();CHECK(!memcmp(s.active_ram,before_ram,0x422));
 /* High-table bytes are part of the publication contract, not just512bytes. */
 IogWorldBeforeNmi();g_ppu->oamWriteCount++;g_ppu->highOam[31]^=1;IogWorldAfterNmi();CHECK(!s.active);
 publication();IogWorldBeforeNmi();g_ppu->oam[17]^=1;g_ppu->oamWriteCount++;IogWorldAfterNmi();CHECK(!s.active);
 fixture();IogWorldCaptureAtCompose(&g_cpu,0xc3c714);CHECK(s.pending);IogWorldReset();
 CHECK(!s.pending&&!s.composed&&!s.active&&!s.complete&&!s.valid&&!s.epoch_count);
 fixture();randomizer=true;IogWorldCaptureAtCompose(&g_cpu,0x03c714);CHECK(!s.pending);
}
static void epochs_and_read_only(void){
 fixture();publication();int w=0,h=0;IogWorldGeometry(1280,720,&w,&h);CHECK(w==598&&h==336);
 memcpy(before_ram,ram,sizeof(ram));before_ppu=*g_ppu;CpuState before_cpu=g_cpu;IogWorldBeginRaster();CHECK(s.valid);
 for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 CHECK(s.epoch_count==1);unsigned ticks=s.simulation_ticks;
 IogWorldEndRaster(0x828051,225,0);CHECK(s.complete&&detached_lines&&visual_builds==1);
 CHECK(!memcmp(s.detached.vram,s.epochs[0].vram,sizeof(s.detached.vram)));
 uint32_t*expected=malloc((size_t)s.width*s.height*4);CHECK(expected);
 memcpy(expected,s.output,(size_t)s.width*s.height*4);s.copy_reference=true;
 CHECK(RenderWorld()&&!memcmp(expected,s.output,(size_t)s.width*s.height*4));
 CHECK(!memcmp(s.detached.vram,s.epochs[0].vram,sizeof(s.detached.vram)));free(expected);
 CHECK(ticks==s.simulation_ticks&&!memcmp(before_ram,ram,sizeof(ram))&&!memcmp(&before_cpu,&g_cpu,sizeof(g_cpu)));
 CHECK(!memcmp(&before_ppu,g_ppu,PPU_SAVESTATE_REGS_SIZE));
 CHECK(!memcmp(before_ppu.vram,g_ppu->vram,sizeof(before_ppu.vram)));
 CHECK(!memcmp(before_ppu.cgram,g_ppu->cgram,sizeof(before_ppu.cgram)));
 CHECK(!memcmp(before_ppu.oam,g_ppu->oam,sizeof(before_ppu.oam))&&!memcmp(before_ppu.highOam,g_ppu->highOam,sizeof(before_ppu.highOam)));
 fixture();publication();IogWorldBeginRaster();IogWorldCaptureLine(0);
 g_ppu->oamWriteCount++;IogWorldCaptureLine(1);CHECK(!s.valid&&!strcmp(s.reason,"mid_raster_oam_upload"));
 fixture();publication();IogWorldBeginRaster();IogWorldCaptureLine(0);
 g_ppu->vram[0]=1;g_ppu->vramWriteCount++;IogWorldCaptureLine(1);
 CHECK(s.epoch_count==2);IogWorldEndRaster(0,225,0);CHECK(!s.complete&&!strcmp(s.reason,"mid_raster_character_upload"));
 fixture();publication();IogWorldBeginRaster();
 for(int line=0;line<=Epochs;line++){g_ppu->cgram[1]=(uint16_t)line;IogWorldCaptureLine(line);}
 CHECK(!s.valid&&!strcmp(s.reason,"picture_epoch_capacity"));
 fixture();publication();scene_ready=false;IogWorldBeginRaster();CHECK(!s.valid);
 fixture();publication();g_ppu->hScroll[0]++;IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);CHECK(!s.complete&&!strcmp(s.reason,"camera_publication_mismatch"));
}
static void geometry_and_canaries(void){
 fixture();int w=0,h=0;s.extent_quarters=4;IogWorldGeometry(1280,720,&w,&h);CHECK(w==398&&h==224);
 s.extent_quarters=5;IogWorldGeometry(1280,720,&w,&h);CHECK(w==498&&h==280);
 s.extent_quarters=6;IogWorldGeometry(1280,720,&w,&h);CHECK(w==598&&h==336);
 IogWorldGeometry(3840,1080,&w,&h);CHECK(w==1194&&h==336);
 IogWorldGeometry(200,1080,&w,&h);CHECK(w==384&&h==336);
 IogWorldGeometry(1280,720,&w,&h);
 const size_t pitch=(size_t)w*4+28,bytes=pitch*h;uint8_t*dst=malloc(bytes+64);CHECK(dst);
 memset(dst,0xa5,bytes+64);CpuState old=g_cpu;unsigned ticks=s.simulation_ticks;
 CHECK(IogWorldDraw(dst,pitch,source_field,w,h,0)==1);
 CHECK(IogWorldDraw(dst,pitch,source_field,w,h,1)==1);
 CHECK(!memcmp(&old,&g_cpu,sizeof(old))&&s.simulation_ticks==ticks);
 unsigned scaledw=256*h/224,left=(w-scaledw)/2;
 for(int y=0;y<h;y++){
  for(int x=0;x<w;x++){
   const uint8_t*p=dst+y*pitch+x*4;
   if(x>=(int)left&&x<(int)(left+scaledw))CHECK(!memcmp(p,source_field+((y*224/h)*256+(x-left)*256/scaledw)*4,4));
   else CHECK(!p[0]&&!p[1]&&!p[2]&&!p[3]);
  }
  for(size_t b=(size_t)w*4;b<pitch;b++)CHECK(dst[y*pitch+b]==0xa5);
 }
 for(size_t b=bytes;b<bytes+64;b++)CHECK(dst[b]==0xa5);
 CHECK(!IogWorldDraw(dst,pitch-29,source_field,w,h,0));
 CHECK(!IogWorldDraw(dst,pitch,source_field,w,h,NAN));
 CHECK(!IogWorldDraw(dst,pitch,source_field,w,h,1.1));
 CHECK(!IogWorldDraw(dst,pitch,NULL,w,h,0));free(dst);
}
static void actual_window_enable_gates(void){
 /* Aqueduct enables window participation(TMW21) while W12/WOBJSEL has no
  * enabled window. Participation alone must not reject an authentic scene. */
 fixture();publication();g_ppu->screenWindowed[0]=21;g_ppu->windowsel=0;
 IogWorldBeginRaster();CHECK(s.valid);
 for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 CHECK(s.valid);IogWorldEndRaster(0,225,0);CHECK(s.complete);
 /* Inversion without either enable bit is likewise an inactive window. */
 fixture();publication();g_ppu->screenWindowed[0]=21;g_ppu->windowsel=0x50005;
 IogWorldBeginRaster();CHECK(s.valid);IogWorldCaptureLine(0);CHECK(s.valid);
 const unsigned layers[]={0,1,4};
 for(unsigned side=0;side<2;side++)for(unsigned k=0;k<3;k++)for(unsigned window=0;window<2;window++){
  unsigned layer=layers[k],enable=(window?8u:2u)<<(layer*4);
  fixture();publication();g_ppu->screenWindowed[side]=(uint8_t)(1u<<layer);g_ppu->windowsel=enable;
  IogWorldBeginRaster();CHECK(!s.valid); /* actual activeworld window unsupported */
  fixture();publication();g_ppu->screenWindowed[side]=(uint8_t)(1u<<layer);
  IogWorldBeginRaster();CHECK(s.valid);IogWorldCaptureLine(0);
  g_ppu->windowsel=enable;IogWorldCaptureLine(1);
  CHECK(!s.valid&&!strcmp(s.reason,"unsupported_line_effect"));
 }
 fixture();publication();g_ppu->windowsel=2; /* no main/sub participation */
 IogWorldBeginRaster();CHECK(s.valid);
 fixture();publication();g_ppu->screenWindowed[0]=4;g_ppu->windowsel=2u<<8;
 IogWorldBeginRaster();CHECK(s.valid); /* BG3 is separately captured HUD */
}
static void real_map_edge_framing(void){
 fixture();word(0x68a,152);word(0x68e,484);word(0x696,768);word(0x698,768);
 g_ppu->hScroll[0]=g_ppu->hScroll[1]=152;g_ppu->vScroll[0]=g_ppu->vScroll[1]=484;
 publication();IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0x828051,225,0);CHECK(s.complete&&s.view.world_x==0&&s.view.world_y==428);
 CHECK(s.visual.viewport.world_x==0&&s.visual.viewport.world_y==428);
 CHECK(!s.view.padding_left&&!s.view.padding_right&&!s.view.padding_top&&!s.view.padding_bottom);
 /* Stub pixels encode actual sampled coordinates. The full left column is
  * real source worldX0; the old implementation left19columns unrendered. */
 for(int y=0;y<s.height;y++)CHECK(s.output[y*s.width]==(0xff000000u|((unsigned)(429+y)&1023)<<10));
 CHECK(s.output[100*s.width+300]==(0xff000000u|300u|(529u<<10)));
 /* The original field is offset152/56 inside the host view, not forced to
  * its symmetric171/56 position or stretched to fill an invented edge. */
 CHECK(s.view.native_x==152&&s.view.native_y==56);
}
static void identity_and_source_packet(const char*path){
 CHECK(ExportSourcePacket(path,source_field));
 fixture();publication();CHECK(s.stock&&s.active);cart.romSize=100;
 IogWorldInitialize();CHECK(!s.stock&&!s.active&&!s.pending&&!s.complete);
 IogWorldCaptureAtCompose(&g_cpu,0x83c714);CHECK(!s.pending);
}
int main(int argc,char**argv){CHECK(argc==2);phase_queue();epochs_and_read_only();geometry_and_canaries();actual_window_enable_gates();real_map_edge_framing();identity_and_source_packet(argv[1]);printf("%u world-renderer assertions passed\n",checks);return 0;}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', default='cc')
    p.add_argument('--out', type=Path, default=ROOT/'.local/world-renderer-tests')
    args = p.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT/'.local').resolve()):
        p.error('test output must stay under ignored .local/')
    out.mkdir(parents=True, exist_ok=True)
    (out/'snesrecomp_rom_identity.h').write_text('#define SNESRECOMP_ROM_EXPECTED_SHA256 "'+'0'*64+'"\n')
    source = out/'world_renderer.c';source.write_text(HARNESS, encoding='utf-8')
    exe = out/'world_renderer.exe'
    command = [args.compiler,'-std=c11','-O1','-Wall','-Wextra','-Werror',
               '-I'+str(out),'-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),
               str(source),str(ROOT/'src/iog_world_view.c'),str(ROOT/'src/iog_world_pixels.c'),'-o',str(exe)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr, encoding='utf-8');build.check_returncode()
    env = {k:v for k,v in os.environ.items() if not k.startswith(('SNESRECOMP_','IOG_'))}
    packet = out/'packet'
    run = subprocess.run([str(exe),str(packet)], env=env, capture_output=True, text=True)
    (out/'run.log').write_text(run.stdout+run.stderr, encoding='utf-8')
    run.check_returncode()
    meta=json.loads(Path(str(packet)+'.source.json').read_text())
    assert meta['schema']=='iog-world-source-v1' and meta['complete'] and meta['scene']==1
    assert (meta['world_x'],meta['world_y'],meta['native_x'],meta['native_y'])==(0,428,152,56)
    assert len(meta['lines'])==225 and all(len(bytes.fromhex(row['regs']))==64 and 0<=row['epoch']<meta['epochs'] for row in meta['lines'])
    assert Path(str(packet)+'.active.wram.bin').stat().st_size==131072
    assert Path(str(packet)+'.published.oam.bin').stat().st_size==544
    assert Path(str(packet)+'.epochs.bin').stat().st_size==meta['epochs']*meta['epoch_bytes']==131584
    assert Path(str(packet)+'.hud.bgra').read_bytes()==bytes(256*224*4)
    assert Path(str(packet)+'.field.bgra').read_bytes()==bytes((i*13+7)&255 for i in range(256*224*4))
    inputs = [ROOT/'src/iog_world_renderer.c',ROOT/'src/iog_world_renderer.h',ROOT/'src/iog_visual_objects.h',ROOT/'src/iog_world_view.c',ROOT/'src/iog_world_view.h',ROOT/'src/iog_world_pixels.c',ROOT/'src/iog_world_pixels.h']
    result = dict(passed=run.returncode==0,command=command,
        scope='Actual world module/SDKheaders; stubbed scene/visual/detachedpixels, no real game/APU/PPU parity or GPU',
        sources={str(s.relative_to(ROOT)):hashlib.sha256(s.read_bytes()).hexdigest()for s in inputs},
        stdout=run.stdout,stderr=run.stderr,source_packet_format_and_payload_passed=True)
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    run.check_returncode();print(run.stdout.strip())


if __name__=='__main__': main()
