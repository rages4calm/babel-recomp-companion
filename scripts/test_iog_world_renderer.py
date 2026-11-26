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
/* No presenter here: the status plane is composed into the frame. */
int snes_ovl_frame_layer_available(void) { return 0; }
int snesrecomp_exe_dir_path(const char *leaf, char *out, size_t max_len) { (void)leaf;(void)out;(void)max_len; return 0; }
void snes_ovl_frame_layer_set(const uint32_t *pixels, int w, int h, int x, int y, int rect_w, int rect_h) {
  (void)pixels; (void)w; (void)h; (void)x; (void)y; (void)rect_w; (void)rect_h;
}
#include "iog_ips.c"
/* Exercise the real SDK digest over synthetic bytes; count title identity
 * checks without replacing the SHA-256 algorithm with a permissive stub. */
#define sha256_compute fixture_real_sha256_compute
#include "sha256.c"
#undef sha256_compute
static Snes machine;static Cart cart;static Ppu original,before_ppu;
static uint8_t ram[131072],rom[2097152],before_ram[131072];
CpuState g_cpu;Snes *g_snes=&machine;Ppu *g_ppu=&original;
uint8_t g_snesrecomp_last_hdmaen;
static unsigned checks,detached_lines,visual_builds;static bool randomizer,scene_ready=true;
static unsigned identity_hashes,interpret_all_calls;static int interpreted;
static const char *ips_path;
static SNESModActivationCallback ips_activation;
static uint8_t source_field[256*224*4];
static bool background_probe,static_plane_probe,stream_plane_probe,source_row_probe;
static bool water_wave_probe;
static unsigned water_wave_lines, water_wave_layer;
static bool cloud_probe,wall_probe;static unsigned wall_calls;
static bool bottom_edge_object_probe;
static bool horizon_probe,horizon_expected_valid,horizon_flat_expected;
static unsigned horizon_main_calls,horizon_background_calls;
static int expected_background_x,expected_background_y;
static unsigned background_probe_calls,background_probe_first_row;
#define CHECK(c) do{checks++;if(!(c)){fprintf(stderr,"line%d: %s\n",__LINE__,#c);exit(1);}}while(0)
static void word(unsigned at,unsigned value){ram[at]=(uint8_t)value;ram[at+1]=(uint8_t)(value>>8);}
bool IogRandomizerActive(void){return randomizer;}
void sha256_compute(const uint8_t*p,size_t n,uint8_t hash[32]){
 CHECK(p==rom&&n==sizeof(rom));identity_hashes++;fixture_real_sha256_compute(p,n,hash);
}
void interp_bridge_set_interpret_all(int enabled){interpreted=enabled;interpret_all_calls++;}
int snes_mod_register_activation_plugin(const char*id,SNESModActivationCallback callback){
 CHECK(!strcmp(id,"iog.apocalypse"));ips_activation=callback;return 1;
}
int snes_mod_runtime_feature_resource_path_c(const char*package,const char*feature,const char*resource,char*out,uint32_t cap){
 CHECK(!strcmp(package,"iog.apocalypse")&&!strcmp(feature,"apocalypse_gaia")&&!strcmp(resource,"patch"));
 if(!ips_path||strlen(ips_path)>=cap)return 0;strcpy(out,ips_path);return 1;
}
int snes_mod_runtime_package_root_c(const char*package,const char*version,char*out,uint32_t cap){
 (void)package;(void)version;(void)out;(void)cap;return 0;
}
bool IogSceneViewAbsentPyramidSecondary(const uint8_t*r,const Ppu*p){(void)r;(void)p;return false;}
bool IogSceneViewReadWorldSource(const uint8_t*r,size_t n,const Ppu*p,bool random,IogSceneViewSource*out){
 CHECK(r==ram&&n==sizeof(ram)&&p==g_ppu&&!random);memset(out,0,sizeof(*out));
 out->scene=(uint16_t)Word(r,0x644);out->gate=scene_ready?kIogSceneViewReady:kIogSceneViewUnsupportedScene;return true;
}
IogVisualStatus IogVisualObjectsBuild(const IogVisualSource*in,const IogVisualViewport*v,IogVisualFrame*out){
 CHECK(in->ram==s.active_ram&&in->rom==rom&&in->stock_identity_verified&&v->height<=512);
 visual_builds++;memset(out,0,sizeof(*out));out->status=kIogVisualReady;out->viewport=*v;out->scene=(uint16_t)Word(in->ram,0x644);
 out->part_count=1;IogVisualPart*p=&out->parts[0];p->x=4;p->y=4;p->width=p->height=8;p->order=1;
 for(unsigned n=0;n<64;n++){p->indices[n]=193;p->pixels[n]=0x8001;}
 if(bottom_edge_object_probe){
  p->x=s.view.native_x-3;p->y=s.view.native_y+223;
  for(unsigned n=1;n<3;n++){out->parts[n]=*p;out->parts[n].x+=16*n;}
  out->parts[1].manual=1;
  out->parts[2].y--;
  out->part_count=3;
 }
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
void IogSparkleDraw(uint8_t*d,size_t pitch,int w,int h,int x,int y){(void)d;(void)pitch;(void)w;(void)h;(void)x;(void)y;}
int IogEdgeHudGet(void){return 0;}
void PpuDrawDetachedLine(Ppu*p,int line){
 CHECK(p!=g_ppu&&(line==0||line==1));if(!line)return;detached_lines++;
 CHECK(p->renderPitch==1024&&!p->renderVram&&!p->hdFrame&&!p->overlayRenderBuffer[2]);
 for(unsigned n=0;n<256;n+=2)CHECK(p->oam[n]==0xf000);
 if((p->bgmode&7)==7){
  uint32_t*row=(uint32_t*)p->renderBuffer;
  for(int x=0;x<256;x++){
   unsigned index=IogMode7PlaneIndex(p,x,1);
   CHECK(index==(unsigned)x); /* palette strip must retain ALL256 indices */
   row[x]=0xff000000u|index*0x010101u;
  }
  return; /* palette transport stub, not a real PPU color-math claim */
 }
 if(background_probe){
  unsigned row=background_probe_calls/3,start=(background_probe_calls%3)*224;
  if(row>=background_probe_first_row)
   CHECK(p->hScroll[1]==((expected_background_x+(int)start)&1023));
  CHECK(p->vScroll[1]==((expected_background_y+(int)row)&1023));
  if(source_row_probe&&row==112&&start==224){
   /* The foreground's original field starts here, but a fixed backdrop
    * has already advanced112 rows. Its uploaded left256 columns and the
    * independently decoded right columns must sample the SAME row14. */
   const unsigned columns[]={248,256};
   for(unsigned n=0;n<2;n++){
    unsigned tx=columns[n]>>3;
    unsigned address=PPU_bgTilemapAdr(p,1)+(14u<<5)+(tx&31);
    if(tx&32)address+=0x400;
    CHECK(p->vram[address]==0x600e);
   }
  }
  if(Word(s.active_ram,0x644)==0x85&&row==40&&start==448){
   /* The third chunk is entirely beyond the256px secondary allocation.
    * Its first cell is still real repeated scenery, not transparent fill. */
   unsigned tx=p->hScroll[1]>>3,ty=(p->vScroll[1]+1)>>3;
   unsigned address=PPU_bgTilemapAdr(p,1)+((ty&31)<<5)+(tx&31);
   if(tx&32)address+=0x400;
   CHECK(p->vram[address]==0x789a);
  }
  if(static_plane_probe)for(unsigned n=0x1800;n<0x2000;n++)CHECK(p->vram[n]==0x5555);
  if(stream_plane_probe&&!background_probe_calls){
   bool changed=false;for(unsigned n=0x1800;n<0x2000;n++)changed|=p->vram[n]!=0x5555;
   CHECK(changed); /* A missing streaming patch cannot pass the static test. */
  }
  background_probe_calls++;
 }
 if(water_wave_probe){
  unsigned row=water_wave_lines/3,start=(water_wave_lines%3)*224;
  int native=(int)row-56,phase=(native%8+8)%8;
  CHECK(p->hScroll[water_wave_layer]==((256+(phase&3)-2-171+(int)start)&1023));
  CHECK(p->vScroll[water_wave_layer]==((256+((phase*3)&7)-4+native)&1023));
  water_wave_lines++;
 }
 uint32_t*row=(uint32_t*)p->renderBuffer;
 if(PPU_mosaicSize(p)>1){
  unsigned size=PPU_mosaicSize(p);
  CHECK(p->mosaicStartLine==0);
  for(unsigned x=0;x<256;x++)
   row[x]=0xff000000u|((p->hScroll[0]+x-x%size)&1023)|
     ((p->vScroll[0]&1023)<<10);
  return;
 }
 if(wall_probe){
  unsigned y=wall_calls/3,start=(wall_calls%3)*224;wall_calls++;
  int wy=s.view.world_y+(int)y;
  unsigned sample=(unsigned)(wy+1),rate=(sample<96||(sample>=256&&sample<336)||(sample>=512&&sample<592))?2:1;
  CHECK(p->hScroll[1]==(((unsigned)s.view.world_x/rate+start)&1023));
  CHECK(p->vScroll[1]==((unsigned)wy&1023));
 }
 if(horizon_probe){
  bool foreground=(p->screenEnabled[0]&1)!=0;
  unsigned call=foreground?horizon_main_calls++:horizon_main_calls-1;
  unsigned y=call/3,start=(call%3)*224;
  if(!foreground){horizon_background_calls++;CHECK(!p->extraObjectCount&&!(p->screenEnabled[0]&16));}
  CHECK(y<336);
  if(horizon_expected_valid){
   CHECK(p->vScroll[1]==(horizon_flat_expected&&y>=255?254:y));
   if(y+1<256){
    /* Native camera160 and168 both clamp to hostX-43. Auto bands keep
     * their fractional drift; the proportional last band uses3/8, not the
     * zero horizontal ratio of the vertical-only camera actor. */
    unsigned phase=y+1<32?((0x1a3f-203)>>4):y+1<64?((0x2237-203)>>4):y+1<96?((0x0ff9-203)>>4):1010;
    CHECK(p->hScroll[1]==((phase+start)&1023));
   }else{
    unsigned tx=p->hScroll[1]>>3,ty=(p->vScroll[1]+1)>>3;
    unsigned address=PPU_bgTilemapAdr(p,1)+((ty&31)<<5)+(tx&31);
    if(tx&32)address+=0x400;
    CHECK(p->vram[address]==(horizon_flat_expected?1:0)); /* finiteY or verified flat terminal row */
   }
  }
  for(unsigned x=0;x<256;x++)row[x]=foreground?0xffcc2211u:
   (y+1<256?(0xff000000u|((p->hScroll[1]+x)&1023)|((y+1)<<10)):(horizon_flat_expected?0xff101010u:0));
  return;
 }
 if(cloud_probe){
  bool foreground=(p->screenEnabled[0]&1)!=0;
  if(!foreground)CHECK(!p->extraObjectCount&&!(p->screenEnabled[0]&16));
  for(unsigned x=0;x<256;x++)row[x]=foreground?0xffcc2211u:0xff3366eeu;
  return;
 }
 for(unsigned x=0;x<256;x++)row[x]=0xff000000u|((p->hScroll[0]+x)&1023)|(((p->vScroll[0]+1)&1023)<<10);
 if(bottom_edge_object_probe){
  for(size_t n=0;n<p->extraObjectCount;n++){
   const PpuExtraObject*object=&p->extraObjects[n];
   for(int x=0;x<object->width;x++){
    int col=object->x+x;
    if(col>=0&&col<256&&object->pixels[x])row[col]=0xfff00df0u;
   }
  }
 }
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
 identity_hashes=interpret_all_calls=0;interpreted=0;ips_path=NULL;
 background_probe=static_plane_probe=stream_plane_probe=false;background_probe_calls=0;
 background_probe_first_row=0;
 source_row_probe=false;
 cloud_probe=wall_probe=false;wall_calls=0;
 bottom_edge_object_probe=false;
 horizon_probe=false;horizon_expected_valid=false;horizon_flat_expected=false;horizon_main_calls=horizon_background_calls=0;
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
static void stock_arrival_wave(void){
 static Dma dma;
 enum { CameraX=112, CameraY=48, Start=0x8a1e };
 fixture();
 word(0x644,0x0b);word(0x68a,CameraX);word(0x68c,CameraX);
 word(0x68e,CameraY);word(0x690,CameraY);word(0x6ee,0x0185);
 word(0x692,512);word(0x694,512);word(0x696,768);word(0x698,768);
 g_snes->dma=&dma;g_snesrecomp_last_hdmaen=0xc0;
 for(unsigned i=6;i<=7;i++)
  dma.channel[i]=(DmaChannel){.mode=2,.indirect=true,.bAdr=13+2*(i-6),
   .aBank=0x7e,.aAdr=0x8800,.indBank=0x7e};
 ram[0x8800]=0xff;word(0x8801,Start);
 ram[0x8803]=0xe0;word(0x8804,Start+254);
 for(unsigned sample=0;sample<512;sample++)
  word(0x8900+2*sample,CameraX+2+(sample%128)%19);
 g_ppu->vScroll[0]=g_ppu->vScroll[1]=CameraY;
 publication();IogWorldBeginRaster();
 for(int line=0;line<=224;line++){
  g_ppu->hScroll[0]=g_ppu->hScroll[1]=(uint16_t)Word(ram,Start+2*Clamp(line,0,222));
  IogWorldCaptureLine(line);
 }
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_stock_transition_wave"));
 const int x=s.view.native_x,row=s.view.native_y;
 unsigned top=Word(ram,Start+2*((unsigned)(1-row)&127));
 unsigned tail=Word(ram,Start+2*(223&127));
 CHECK((s.output[x]&1023)==top);
 CHECK((s.output[(row+224)*s.width+x]&1023)==tail);
 /* A disagreement anywhere in either raster channel retains fallback. */
 unsigned h=offsetof(Ppu,hScroll);
 s.lines[101].registers[h]^=1;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 s.lines[101].registers[h]^=1;
 /* Even authentic samples may only extend this scene after proving the
  * repeat. Simulate a live writer that changed a streamed table sample. */
 s.epochs[0].ram[Start+2*150]^=1;
 s.lines[150].registers[h]^=1;
 s.lines[150].registers[h+2]^=1;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 s.epochs[0].ram[Start+2*150]^=1;
 s.lines[150].registers[h]^=1;
 s.lines[150].registers[h+2]^=1;
 dma.channel[7].bAdr=16;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 g_snesrecomp_last_hdmaen=0;
}
static void epochs_and_read_only(void){
 stock_arrival_wave();
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
 unsigned left=(w-256)/2,top=(h-224)/2;
 for(int y=0;y<h;y++){
  for(int x=0;x<w;x++){
   const uint8_t*p=dst+y*pitch+x*4;
   if(x>=(int)left&&x<(int)(left+256)&&y>=(int)top&&y<(int)(top+224))CHECK(!memcmp(p,source_field+((y-top)*256+x-left)*4,4));
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
static void fallback_constant_pixel_scale(void){
 const unsigned extents[]={4,5,6};
 for(unsigned n=0;n<3;n++){
  fixture();s.extent_quarters=extents[n];int w=0,h=0;IogWorldGeometry(1920,1080,&w,&h);
  size_t pitch=(size_t)w*4,bytes=pitch*h;uint8_t*dst=malloc(bytes);CHECK(dst);
  CHECK(IogWorldDraw(dst,pitch,source_field,w,h,0)==1);
  int left=(w-256)/2,top=(h-224)/2;
  for(int y=0;y<h;y++)for(int x=0;x<w;x++){
   const uint8_t*p=dst+y*pitch+x*4;
   if(x>=left&&x<left+256&&y>=top&&y<top+224)
    CHECK(!memcmp(p,source_field+((y-top)*256+x-left)*4,4));
   else CHECK(!p[0]&&!p[1]&&!p[2]&&!p[3]);
  }
  free(dst);
 }
}
static void stock_modal_plate_scale(void){
 fixture();
 word(0x644,0xff);word(0x6ee,0x85);
 g_ppu->bgmode=9;g_ppu->inidisp=15;g_ppu->bgTileAdr=0x622;
 g_ppu->bgXsc[0]=4;g_ppu->bgXsc[1]=0x0c;g_ppu->bgXsc[2]=0x78;
 g_ppu->screenEnabled[0]=0x17;g_ppu->screenEnabled[1]=0;
 g_ppu->cgwsel=0x80;g_ppu->cgadsub=0;g_snesrecomp_last_hdmaen=6;
 IogWorldBeginRaster();IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&s.fixed_plate&&!strcmp(s.reason,"ready_stock_modal_plate"));
 const unsigned extents[]={4,5,6};
 for(unsigned n=0;n<3;n++){
  int w=0,h=0;s.extent_quarters=extents[n];IogWorldGeometry(1920,1080,&w,&h);
  int plate=256*h/224,left=(w-plate)/2;size_t pitch=(size_t)w*4+16;
  uint8_t*dst=malloc(pitch*h);CHECK(dst);memset(dst,0xa5,pitch*h);
  CHECK(IogWorldDraw(dst,pitch,source_field,w,h,0)==1);
  for(int y=0;y<h;y++){
   for(int x=0;x<w;x++){
    const uint8_t*p=dst+y*pitch+x*4;
    if(x>=left&&x<left+plate)
     CHECK(!memcmp(p,source_field+((y*224/h)*256+(x-left)*256/plate)*4,4));
    else CHECK(!p[0]&&!p[1]&&!p[2]&&!p[3]);
   }
   for(size_t b=(size_t)w*4;b<pitch;b++)CHECK(dst[y*pitch+b]==0xa5);
  }
  free(dst);
 }
 word(0x644,0xfd);IogWorldBeginRaster();CHECK(!s.fixed_plate&&!s.complete);
 g_ppu->bgXsc[0]=8;g_ppu->screenEnabled[0]=0x13;g_ppu->screenEnabled[1]=0x11;
 g_ppu->cgwsel=0x82;g_ppu->cgadsub=2;g_snesrecomp_last_hdmaen=2;
 IogWorldBeginRaster();IogWorldEndRaster(0,225,0);CHECK(s.fixed_plate&&s.complete);
 g_ppu->mosaic=0xc3;IogWorldBeginRaster();IogWorldEndRaster(0,225,0);CHECK(s.fixed_plate&&s.complete);
 g_ppu->mosaic=0xc1;IogWorldBeginRaster();CHECK(!s.fixed_plate);
 g_ppu->mosaic=0;
 g_ppu->inidisp=0x80;IogWorldBeginRaster();CHECK(!s.fixed_plate&&!s.complete);
 g_ppu->inidisp=15;g_ppu->bgXsc[1]=8;IogWorldBeginRaster();CHECK(!s.fixed_plate);
 g_ppu->bgXsc[1]=0x0c;word(0x644,0x8a);IogWorldBeginRaster();CHECK(!s.fixed_plate);
 word(0x644,0xfd);IogWorldBeginRaster();CHECK(s.fixed_plate);
 IogWorldReset();CHECK(!s.fixed_plate&&!s.complete);
 s.stock=false;IogWorldBeginRaster();CHECK(!s.fixed_plate);
}
static void stock_ending_plate(void){
 fixture();word(0x644,0x90);word(0x6ee,1);
 g_ppu->bgmode=9;g_ppu->inidisp=9;g_ppu->bgTileAdr=0x622;
 g_ppu->bgXsc[0]=0x11;g_ppu->bgXsc[1]=0x18;g_ppu->bgXsc[2]=0x78;
 g_ppu->screenEnabled[0]=0x17;g_ppu->screenEnabled[1]=2;
 g_ppu->cgwsel=2;g_ppu->cgadsub=0x41;
 IogWorldBeginRaster();IogWorldEndRaster(0,225,0);
 CHECK(s.fixed_plate&&s.complete&&!strcmp(s.reason,"ready_stock_ending_plate"));
 word(0x644,0x89);word(0x6ee,5);
 g_ppu->bgXsc[1]=0x19;g_ppu->screenEnabled[0]=0x11;g_ppu->screenEnabled[1]=4;
 g_ppu->cgwsel=0x82;g_ppu->cgadsub=1;
 CHECK(StockEndingPlate(g_ppu,ram));
 word(0x644,0xf7);word(0x6ee,0x0401);
 g_ppu->bgXsc[1]=0x18;g_ppu->bgXsc[2]=0x7a;g_ppu->windowsel=0x33;
 g_ppu->screenEnabled[0]=0x14;g_ppu->screenEnabled[1]=0;
 g_ppu->cgwsel=2;g_ppu->cgadsub=0x83;
 CHECK(StockEndingPlate(g_ppu,ram));
 g_ppu->bgXsc[2]=0x7b;CHECK(!StockEndingPlate(g_ppu,ram));g_ppu->bgXsc[2]=0x7a;
 g_ppu->bgmode=7;CHECK(!StockEndingPlate(g_ppu,ram));g_ppu->bgmode=9;
 g_ppu->inidisp=0x80;CHECK(!StockEndingPlate(g_ppu,ram));
}
static void stock_opening_plate(void){
 fixture();word(0x644,0xfc);word(0x6ee,0x80);
 g_ppu->inidisp=15;g_ppu->bgmode=9;g_ppu->bgTileAdr=0x622;
 g_ppu->bgXsc[0]=0x18;g_ppu->bgXsc[1]=0x10;g_ppu->bgXsc[2]=0x78;
 g_ppu->screenEnabled[0]=0x16;g_ppu->screenEnabled[1]=0;
 g_ppu->cgwsel=0x80;g_ppu->cgadsub=3;
 IogWorldBeginRaster();IogWorldEndRaster(0,225,0);
 CHECK(s.fixed_plate&&s.complete&&!strcmp(s.reason,"ready_stock_opening_plate"));
 word(0x644,0xfb);word(0x6ee,0x85);
 g_ppu->bgXsc[0]=0x19;g_ppu->bgXsc[1]=0x11;g_ppu->screenEnabled[0]=0x10;g_ppu->cgadsub=0;
 CHECK(StockOpeningPlate(g_ppu,ram));
 word(0x644,0xfa);word(0x6ee,5);
 g_ppu->bgXsc[0]=0x11;g_ppu->bgXsc[1]=0x19;g_ppu->windowsel=0x228800;
 g_ppu->screenEnabled[0]=1;g_ppu->screenEnabled[1]=4;
 g_ppu->cgwsel=0x82;g_ppu->cgadsub=0x41;g_snesrecomp_last_hdmaen=0x0e;
 CHECK(StockOpeningPlate(g_ppu,ram));
 g_ppu->windowsel=0;CHECK(!StockOpeningPlate(g_ppu,ram));
 g_snesrecomp_last_hdmaen=0;
 word(0x644,0x8e);word(0x6ee,0x1005);
 g_ppu->screenEnabled[0]=0x13;g_ppu->screenEnabled[1]=3;
 g_ppu->cgwsel=0x80;g_ppu->cgadsub=0x81;CHECK(StockOpeningPlate(g_ppu,ram));
 g_ppu->cgwsel=0x82;g_ppu->cgadsub=0x10;CHECK(StockOpeningPlate(g_ppu,ram));
 word(0x644,0x8f);g_ppu->screenEnabled[0]=0x11;g_ppu->screenEnabled[1]=1;
 CHECK(StockOpeningPlate(g_ppu,ram));
 g_ppu->bgmode=7;CHECK(!StockOpeningPlate(g_ppu,ram));
}
static void effect_camera_actor(unsigned at,unsigned entry,unsigned x,unsigned y){
 word(at,entry);ram[at+2]=0x80;word(at+0x12,0x1000);word(at+0x14,x);word(at+0x16,y);
}
static void live_effect_camera_models(void){
 EffectCamera camera;
 fixture();CHECK(!ReadEffectCamera(ram,&camera));
 word(0x56,0x1060);word(0x58,0x1060);effect_camera_actor(0x1060,0xEAA3,0x0401,0x0201);
 memcpy(before_ram,ram,sizeof(ram));CHECK(ReadEffectCamera(ram,&camera));
 CHECK(camera.ratio[0]==0x0401&&camera.ratio[1]==0x0201&&!camera.uploaded_ring);
 CHECK(!memcmp(before_ram,ram,sizeof(ram)));
 CHECK(ProjectEffect(camera.ratio[0],8)==2&&ProjectEffect(camera.ratio[1],12)==6);
 CHECK(ProjectEffect(0x0401,-1)==-1&&ProjectEffect(0x0401,-5)==-2);
 CHECK(ProjectEffect(0x0101,-17)==-17&&ProjectEffect(0,45)==0);
 word(0x1060,0xEAD7);CHECK(ReadEffectCamera(ram,&camera));CHECK(camera.ratio[0]==0x0401&&camera.ratio[1]==0x0201);
 word(0x1060,0xEAB4);CHECK(ReadEffectCamera(ram,&camera));CHECK(camera.ratio[0]==0&&camera.ratio[1]==0x0201);
 word(0x1060,0xEA26);ram[0x6EF]=4;CHECK(ReadEffectCamera(ram,&camera));
 CHECK(camera.ratio[0]==0x0101&&camera.ratio[1]==0x0101&&camera.uploaded_ring);
 ram[0x6EF]=0;CHECK(ReadEffectCamera(ram,&camera));CHECK(!camera.uploaded_ring);
 word(0x1060,0xEAA3);word(0x1074,1);CHECK(!ReadEffectCamera(ram,&camera)); /* divisor0 */
 word(0x1074,0x0401);ram[0x1062]=0x81;CHECK(!ReadEffectCamera(ram,&camera));
 ram[0x1062]=0x80;word(0x1072,0);CHECK(!ReadEffectCamera(ram,&camera));
 word(0x1072,0x1000);word(0x1066,0x1090);word(0x1094,0x1060);word(0x58,0x1090);
 effect_camera_actor(0x1090,0xEAA3,0x0101,0x0101);CHECK(!ReadEffectCamera(ram,&camera)); /* ambiguous */
 ram[0x1092]=0x81;CHECK(ReadEffectCamera(ram,&camera)); /* unrelated bank not a camera */
 word(0x1096,0x1090);CHECK(!ReadEffectCamera(ram,&camera)); /* cycle */
 word(0x1096,0);word(0x1094,0);CHECK(!ReadEffectCamera(ram,&camera)); /* bad backreference */
 word(0x1094,0x1060);word(0x58,0x1060);CHECK(!ReadEffectCamera(ram,&camera)); /* bad tail */
 word(0x58,0x1090);word(0x1066,0x1091);CHECK(!ReadEffectCamera(ram,&camera)); /* unaligned */
 word(0x1066,0x1FC0);CHECK(!ReadEffectCamera(ram,&camera)); /* outside actor arena */
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
 /* Dao's captured mask may move into, across or entirely past a chunk. */
 fixture();word(0x644,0xc3);word(0x6ee,0x80);
 word(0x692,768);word(0x696,512);word(0x694,512);word(0x698,512);
 g_ppu->windowsel=2;g_ppu->screenWindowed[0]=1;
 publication();IogWorldBeginRaster();CHECK(s.valid);
 for(int line=0;line<=224;line++){
  g_ppu->hScroll[0]=(uint16_t)(256+((line+63)%64)/4);
  IogWorldCaptureLine(line);
 }
 CHECK(s.valid&&DaoHeatWave(&s.epochs[0],g_ppu));
 s.lines[100].registers[offsetof(Ppu,hScroll)]^=1;
 CHECK(!DaoHeatWave(&s.epochs[0],g_ppu));
 g_ppu->window1left=0;g_ppu->window1right=120;
 RebaseWindow1(g_ppu,-50);CHECK(g_ppu->window1left==0&&g_ppu->window1right==70);
 RebaseWindow1(g_ppu,250);CHECK(g_ppu->window1left==250&&g_ppu->window1right==255);
 RebaseWindow1(g_ppu,80);CHECK(g_ppu->window1left==255&&g_ppu->window1right==0);
 RebaseWindow1(g_ppu,-255);CHECK(g_ppu->window1left==255&&g_ppu->window1right==0);
 g_ppu->windowsel=10;CHECK(!DaoWorldWindow(g_ppu,ram));
 fixture();word(0x644,0x2A);word(0x692,256);word(0x696,1280);
 word(0x694,512);word(0x698,512);
 g_ppu->windowsel=0x030033;g_ppu->cgwsel=0x80;
 g_ppu->screenEnabled[1]=0;g_ppu->screenWindowed[0]=23;
 publication();IogWorldBeginRaster();CHECK(s.valid);
 IogWorldCaptureLine(0);CHECK(s.valid&&DreamWorldWindow(g_ppu,ram));
 g_ppu->windowsel|=8;IogWorldCaptureLine(1);
 CHECK(!s.valid&&!strcmp(s.reason,"unsupported_line_effect"));
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
static void signed_camera_shake(void){
 fixture();word(0x68e,0xffff);g_ppu->vScroll[0]=1023;g_ppu->vScroll[1]=256;
 publication();IogWorldBeginRaster();CHECK(s.valid);
 for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0x828051,225,0);
 CHECK(s.complete&&s.view.world_y==-1&&s.view.native_y==0&&s.view.padding_top==1);
 /* The synthetic original row is not black. Keep it across the full native
  * rect rather than discarding its real hardware-wrapped first row; new
  * outside-map columns on that same row stay explicit empty padding. */
 CHECK(s.output[s.view.native_x]==(0xff000000u|256u));
 CHECK(s.output[0]==0);
 CHECK(s.output[223*s.width+s.view.native_x]==(0xff000000u|256u|(223u<<10)));
 CHECK(!s.view.padding_left&&!s.view.padding_right);
 fixture();word(0x68e,0xff7f);g_ppu->vScroll[0]=895;
 publication();IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0x828051,225,0);CHECK(!s.complete&&!strcmp(s.reason,"invalid_world_view"));
}
static void repeating_secondary_samples(void){
 fixture();PictureEpoch*e=&s.epochs[0];memset(e,0,sizeof(*e));
 memcpy(e->ram,ram,sizeof(e->ram));
 e->ram[0x694]=0;e->ram[0x695]=1; /* 256 by 768, not a power-of-two height */
 e->ram[0x698]=0;e->ram[0x699]=3;
 e->ram[0xc000]=1;e->ram[0xc2ff]=2;e->ram[0xc100]=3;
 for(unsigned n=0;n<4;n++){
  e->ram[0x2808+n*2]=(uint8_t)(0x10+n);e->ram[0x2809+n*2]=0x11;
  e->ram[0x2810+n*2]=(uint8_t)(0x20+n);e->ram[0x2811+n*2]=0x22;
  e->ram[0x2818+n*2]=(uint8_t)(0x30+n);e->ram[0x2819+n*2]=0x33;
 }
 uint8_t*before=malloc(sizeof(e->ram));CHECK(before);memcpy(before,e->ram,sizeof(e->ram));
 CHECK(MapTile(e,1,0,0,true)==0x1110);
 CHECK(MapTile(e,1,-1,-1,true)==0x2223);
 CHECK(MapTile(e,1,256,768,true)==0x1110);
 CHECK(MapTile(e,1,512,1024,true)==0x3330);
 CHECK(MapTile(e,1,-1,0,false)==0xffffffffu);
 CHECK(MapTile(e,1,256,0,false)==0xffffffffu);
 CHECK(MapTile(e,1,0,768,false)==0xffffffffu);
 CHECK(MapTile(e,0,-1,0,false)==0xffffffffu);
 CHECK(MapTile(e,0,768,0,false)==0xffffffffu);
 CHECK(!memcmp(before,e->ram,sizeof(e->ram)));free(before);
 e->ram[0x695]=2;e->ram[0x699]=2;e->ram[0xc3ff]=2; /* 512 by 512 */
 CHECK(MapTile(e,1,512,512,true)==0x1110);
 CHECK(MapTile(e,1,-1,-1,true)==0x2223);
 CHECK(MapTile(e,1,1536,1536,true)==0x1110);
 CHECK(!EffectPlaneScene(1)&&!EffectPlaneScene(8)&&!EffectPlaneScene(0xe5));
 CHECK(EffectProjection(0x4f,false,-1)==-1&&EffectProjection(0x4f,true,-5)==-2);
 CHECK(EffectProjection(0x4f,false,7)==1&&EffectProjection(0x4f,true,8)==2);
}
static void background_picture(unsigned scene,unsigned camera_x,unsigned camera_y,
 unsigned effect_x,unsigned effect_y,int expected_x,int expected_y,bool static_plane){
 fixture();word(0x644,scene);word(0x68a,camera_x);word(0x68e,camera_y);
 word(0x68c,effect_x);word(0x690,effect_y);
 if(scene==0x4f||scene==0xcc){word(0x692,1024);word(0x696,1024);word(0x694,512);word(0x698,512);}
 if(scene==0x4d){
  word(0x692,1024);word(0x696,1024);word(0x694,512);word(0x698,512);
  word(0x56,0x1060);word(0x58,0x1060);effect_camera_actor(0x1060,0xEAA3,0x0401,0x0401);
 }
 if(scene==0x85){
  word(0x692,2048);word(0x696,768);word(0x694,256);word(0x698,768);
  word(0x6D6,0);word(0x6D8,0);word(0x6DA,2048);word(0x6DE,256);
 }
 if(scene==0x55){word(0x692,512);word(0x696,512);word(0x694,512);word(0x698,512);}
 if(scene==0x43){
  word(0x692,1536);word(0x696,1024);word(0x694,1024);word(0x698,768);
  word(0x56,0x1060);word(0x58,0x1060);effect_camera_actor(0x1060,0xEAA3,0x0201,0x0201);
 }
 if(scene==0xea){
  word(0x692,256);word(0x696,256);word(0x694,512);word(0x698,256);
  word(0x6ee,static_plane?0x400:0);
  for(unsigned n=0x1800;n<0x2000;n++)g_ppu->vram[n]=0x5555;
 }
 g_ppu->hScroll[0]=(uint16_t)camera_x;g_ppu->vScroll[0]=(uint16_t)camera_y;
 /* Nonzero live raster offsets exercise preservation of drift/HDMA; their
  * values deliberately differ from the logical secondary camera. */
 g_ppu->hScroll[1]=(uint16_t)(effect_x+5);g_ppu->vScroll[1]=(uint16_t)(effect_y+7);
 publication();memcpy(before_ram,ram,sizeof(ram));before_ppu=*g_ppu;CpuState cpu=g_cpu;
 IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 background_probe=true;static_plane_probe=static_plane;stream_plane_probe=scene==0xea&&!static_plane;
 expected_background_x=expected_x;expected_background_y=expected_y;
 IogWorldEndRaster(0,225,0);CHECK(s.complete&&background_probe_calls==3*336);
 CHECK(!memcmp(before_ram,ram,sizeof(ram))&&!memcmp(&cpu,&g_cpu,sizeof(cpu)));
 CHECK(!memcmp(before_ppu.vram,g_ppu->vram,sizeof(before_ppu.vram)));
 CHECK(!memcmp(s.detached.vram,s.epochs[0].vram,sizeof(s.detached.vram)));
}
static void parallax_host_camera_and_static_upload(void){
 /* Both quarter-speed cases clamp the host view at origin0. The original
  * camera moves 8/12 ->12/16, but the backdrop must stay at phase5/7. The
  * obsolete full-rate recentering yields -1/-2 instead of this fixed phase. */
 background_picture(0x4f,8,12,2,3,5,7,false);
 background_picture(0x4f,12,16,3,4,5,7,false);
 background_picture(0x85,8,16,0,16,5,-33,false); /* vertical-only; bounded floor adds40px padding */
 background_picture(0xcc,760,592,0,0,5,7,false); /* fixed wall plate */
 background_picture(0x55,128,128,0,0,-166,-49,false); /* sky aligned to native viewport */
 background_picture(0x4d,512,384,128,96,-38,47,false); /* top-side quarter-rate backdrop */
 /* Mine BG2 keeps the actual 271+5,149+7 phase at native offset171,56. */
 background_picture(0x43,543,299,271,149,105,100,false);
 /* SceneEA's finite256 world is centered at (-171,-40). Its uploaded512
  * ring is authoritative in position-bypass mode; the otherwise identical
  * streamed control MUST modify detached map cells, then restore them. */
 background_picture(0xea,0,0,320,81,154,48,true);
 background_picture(0xea,0,0,320,81,154,48,false);
}
static void water_wave(void){
 for(unsigned layer=0;layer<=1;layer++){
  fixture();word(0x644,layer?0x5c:0x5f);word(0x692,1024);
  word(0x694,layer?768:1024);word(0x698,layer?512:1024);
  word(0x68c,256);word(0x690,256);word(0x6ee,layer?5:0x185);
  word(0x56,0x1060);word(0x58,0x1060);effect_camera_actor(0x1060,0xEAA3,0x0101,0x0101);
  publication();IogWorldBeginRaster();
  for(int line=0;line<=224;line++){
   int phase=(line+7)%8;
   g_ppu->hScroll[layer]=(uint16_t)(256+(phase&3)-2);
   g_ppu->vScroll[layer]=(uint16_t)(256+((phase*3)&7)-4);
   if(layer&&line==110)g_ppu->cgram[1]=0x1234; /* coffin room's palette IRQ */
   IogWorldCaptureLine(line);
  }
  water_wave_lines=0;water_wave_layer=layer;water_wave_probe=true;
  IogWorldEndRaster(0,225,0);water_wave_probe=false;
  CHECK(s.complete&&!strcmp(s.reason,"ready_water_wave")&&water_wave_lines==3*336);
  CHECK(s.view.native_x==171&&s.view.native_y==56);
  Ppu probe=s.base;memcpy(&probe,s.lines[1].registers,PPU_SAVESTATE_REGS_SIZE);
  CHECK(s.epoch_count==1+(int)layer);
  if(layer){
   s.epochs[1].ram[0x68c]^=1;
   CHECK(!WaterWave(&s.epochs[0],&probe));
   s.epochs[1].ram[0x68c]^=1;
  }
  s.lines[99].registers[offsetof(Ppu,vScroll)+layer*2]^=1;
  CHECK(!WaterWave(&s.epochs[0],&probe));
 }
}
static void babel_starfield(void){
 for(unsigned sub=0;sub<2;sub++){
  fixture();word(0x644,sub?0xf6:0xf2);word(0x6ee,0x0405);
  word(0x692,512);word(0x694,512);word(0x696,512);word(0x698,512);
  word(0x6d8,256);word(0x6da,256);word(0x6de,512);
  word(0x68a,0);word(0x68e,256);word(0x68c,1022);word(0x690,20);
  g_ppu->hScroll[0]=0;g_ppu->vScroll[0]=256;
  g_ppu->hScroll[1]=1022;g_ppu->vScroll[1]=20;
  g_ppu->cgwsel=2;g_ppu->cgadsub=0x31;
  g_ppu->screenEnabled[0]=sub?17:19;g_ppu->screenEnabled[1]=sub?2:0;
  publication();IogWorldBeginRaster();
  for(int line=0;line<=224;line++){
   unsigned phase=(unsigned)(line+63)%64;
   g_ppu->hScroll[1]=(uint16_t)((1022+phase/8)&1023);
   IogWorldCaptureLine(line);
  }
  cloud_probe=true;IogWorldEndRaster(0,225,0);cloud_probe=false;
  CHECK(s.complete&&!strcmp(s.reason,"ready_babel_starfield"));
  CHECK(s.output[0]==0xff3366eeu);
  CHECK(s.output[s.view.native_y*598+s.view.native_x]==0xffcc2211u);
  CHECK(!memcmp(s.detached.vram,s.epochs[0].vram,sizeof(s.detached.vram)));
  s.lines[99].registers[offsetof(Ppu,hScroll)+2]^=1;
  CHECK(!RenderWorld()&&!strcmp(s.reason,"unsupported_babel_starfield"));
  s.lines[99].registers[offsetof(Ppu,hScroll)+2]^=1;
  s.lines[99].registers[offsetof(Ppu,cgadsub)]^=1;
  CHECK(!RenderWorld()&&!strcmp(s.reason,"unsupported_babel_starfield"));
 }
 /* The rematches' normal star producer shares the two-plane victory
  * table. Its alternate phase can exceed the arrival-wave bound.
  * A nonperiodic raster must retain the captured edge phases. */
 static Dma victory_dma;
 fixture();word(0x644,0xf2);word(0x6ee,0x0405);
 word(0x68e,0);word(0x694,512);word(0x698,512);word(0x6d8,0);word(0x6da,512);word(0x6de,256);
 g_ppu->screenEnabled[0]=19;
 g_ppu->vScroll[0]=24;g_ppu->cgwsel=2;g_ppu->cgadsub=0x31;
 g_snes->dma=&victory_dma;g_snesrecomp_last_hdmaen=0xc2;
 for(unsigned i=6;i<=7;i++)victory_dma.channel[i]=(DmaChannel){
  .mode=2,.indirect=true,.bAdr=(uint8_t)(13+2*(i-6)),.aBank=0x7e,.aAdr=0x8800,.indBank=0x7e};
 victory_dma.channel[1]=victory_dma.channel[7];
 victory_dma.channel[1].aAdr=0x8a00;
 const uint8_t table[]={0xff,0,0x89,0xe0,0xfe,0x89,0};memcpy(ram+0x8800,table,sizeof table);
 for(unsigned line=0;line<223;line++)
  word(0x8900+2*line,256+(line<128?line%21:160+line%19));
 publication();IogWorldBeginRaster();
 for(unsigned line=0;line<=224;line++){
  uint16_t sample=Word(ram,0x8900+2*(line<223?line:222));
  g_ppu->hScroll[0]=g_ppu->hScroll[1]=sample;
  IogWorldCaptureLine((int)line);
 }
 cloud_probe=true;IogWorldEndRaster(0,225,0);cloud_probe=false;
 CHECK(s.complete&&!strcmp(s.reason,"ready_stock_transition_wave"));
 CHECK(s.output[s.width-1]==0xff3366eeu);
 victory_dma.channel[1].aAdr=0x8800;
 CHECK(RenderWorld()&&!strcmp(s.reason,"ready_stock_transition_wave"));
 victory_dma.channel[1].aAdr=0x8a00;
 victory_dma.channel[1].bAdr=16;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 victory_dma.channel[1].bAdr=15;
 s.lines[99].registers[offsetof(Ppu,hScroll)+2]^=1;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 s.lines[99].registers[offsetof(Ppu,hScroll)+2]^=1;
 s.active_ram[0x644]=s.epochs[0].ram[0x644]=0xf5;
 const size_t bg2_hofs=offsetof(Ppu,hScroll)+2;
 memset(s.lines[223].registers+bg2_hofs,0,2);
 memset(s.lines[224].registers+bg2_hofs,0,2);
 CHECK(RenderWorld()&&!strcmp(s.reason,"ready_stock_transition_wave"));
 /* Sand Fanger's channel-1 source can leave any value on the final two
  * lines. Only that scene and source may differ, and only after sample 222. */
 s.lines[224].registers[bg2_hofs]=1;
 CHECK(RenderWorld()&&!strcmp(s.reason,"ready_stock_transition_wave"));
 victory_dma.channel[1].aAdr=0x8800;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 victory_dma.channel[1].aAdr=0x8a00;
 s.active_ram[0x644]=s.epochs[0].ram[0x644]=0xf4;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 s.active_ram[0x644]=s.epochs[0].ram[0x644]=0xf5;
 s.lines[222].registers[bg2_hofs]^=1;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 s.lines[222].registers[bg2_hofs]^=1;
 g_snesrecomp_last_hdmaen=0;g_snes->dma=NULL;

 /* The channel-1 handover keeps BG1 fixed. F3 can instead hold its
  * first BG2 value after the other wave data overwrites its table. */
 for(unsigned held=0;held<2;held++){
  fixture();word(0x644,held?0xf3:0xf2);word(0x6ee,0x0405);
  word(0x68e,0);word(0x694,512);word(0x698,512);
  word(0x6d8,0);word(0x6da,512);word(0x6de,256);
  g_ppu->screenEnabled[0]=19;g_ppu->vScroll[0]=0;
  g_ppu->cgwsel=2;g_ppu->cgadsub=0x31;
  g_snes->dma=&victory_dma;g_snesrecomp_last_hdmaen=2;
  const unsigned table_base=held?0x8a00:0x8800;
  victory_dma.channel[1].aAdr=(uint16_t)table_base;
  for(unsigned offset=0;offset<12;offset+=3){
   ram[table_base+offset]=0xc0;
   word(table_base+offset+1,table_base+0x100);
  }
  publication();
  memcpy(ram+0x8800,table,sizeof table);
  for(unsigned line=0;line<223;line++)
   word(0x8900+2*line,256+(line<64?line%21:0));
  if(held){
   ram[table_base]=0x5a;word(table_base+1,0x5a00);ram[table_base+3]=0;
   word(0x5a00,0x2050);
  }
  IogWorldBeginRaster();
  for(unsigned line=0;line<=224;line++){
   g_ppu->hScroll[1]=held?80:Word(ram,0x8900+2*(line<223?line:222));
   IogWorldCaptureLine((int)line);
  }
  IogWorldEndRaster(0,225,0);
  CHECK(s.complete&&!strcmp(s.reason,"ready_babel_victory_setup"));
  s.epochs[0].ram[held?0x5a00:0x8900]^=1;
  CHECK(!RenderWorld()&&!strcmp(s.reason,"unsupported_babel_starfield"));
  s.epochs[0].ram[held?0x5a00:0x8900]^=1;
  s.active_ram[table_base]^=1;
  CHECK(!RenderWorld()&&!strcmp(s.reason,"unsupported_babel_starfield"));
  s.active_ram[table_base]^=1;
  s.lines[99].registers[offsetof(Ppu,hScroll)]^=1;
  CHECK(!RenderWorld()&&!strcmp(s.reason,"unsupported_babel_starfield"));
  g_snesrecomp_last_hdmaen=0;g_snes->dma=NULL;
 }

 fixture();word(0x644,0xf6);word(0x6ee,0x0405);
 word(0x692,512);word(0x694,512);word(0x696,512);word(0x698,512);
 word(0x6d8,256);word(0x6da,512);word(0x6de,512);
 word(0x68a,56);word(0x68c,100);word(0x690,406);
 g_ppu->bgmode=9;g_ppu->mosaic=0x63;g_ppu->mosaicStartLine=1;
 g_ppu->hScroll[0]=56;g_ppu->hScroll[1]=100;g_ppu->vScroll[1]=406;
 g_ppu->screenEnabled[0]=21;g_ppu->screenEnabled[1]=2;
 g_ppu->cgwsel=2;g_ppu->cgadsub=0x31;g_snesrecomp_last_hdmaen=2;
 publication();IogWorldBeginRaster();CHECK(s.valid);
 for(int line=0;line<=224;line++){
  g_ppu->hScroll[1]=(uint16_t)(100+((line+63)%64)/8);
  IogWorldCaptureLine(line);
 }
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_babel_starfield"));
 IogWorldBeginRaster();CHECK(s.valid);IogWorldCaptureLine(0);
 g_ppu->screenEnabled[1]=0;IogWorldCaptureLine(1);CHECK(!s.valid);
 g_snesrecomp_last_hdmaen=0;
}
static void mansion_fog(void){
 fixture();word(0x644,0xe9);
 word(0x692,1024);word(0x694,512);word(0x696,1024);word(0x698,256);
 word(0x68c,144);word(0x690,9);word(0x6ee,0x0485);
 word(0x56,0x1060);word(0x58,0x1060);
 effect_camera_actor(0x1060,0xea26,0,0);
 g_ppu->hScroll[1]=g_ppu->vScroll[1]=256;
 g_ppu->hScroll[0]=144;g_ppu->vScroll[0]=777;
 g_ppu->bgXsc[0]=0x19;g_ppu->bgXsc[1]=0x11;
 g_ppu->cgwsel=2;g_ppu->cgadsub=0x21;
 publication();IogWorldBeginRaster();
 for(int line=0;line<=224;line++){
  unsigned phase=(unsigned)(line+63)%64;
  g_ppu->hScroll[0]=(uint16_t)(144+(phase/8));
  IogWorldCaptureLine(line);
 }
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_mansion_fog"));
 CHECK(!memcmp(s.detached.vram,s.epochs[0].vram,sizeof(s.detached.vram)));
 s.lines[99].registers[offsetof(Ppu,hScroll)]^=1;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"unsupported_mansion_fog"));
 s.lines[99].registers[offsetof(Ppu,hScroll)]^=1;
 s.lines[99].registers[offsetof(Ppu,cgadsub)]^=1;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"unsupported_mansion_fog"));
}
static void village_heat(void){
 fixture();word(0x644,0xac);
 word(0x692,512);word(0x694,512);word(0x696,512);word(0x698,512);
 word(0x68a,64);word(0x68c,64);word(0x68e,128);word(0x690,128);
 publication();
 word(0x68a,66);word(0x68c,66);word(0x68e,130);word(0x690,130);
 g_ppu->hScroll[0]=g_ppu->hScroll[1]=64;
 IogWorldBeginRaster();
 for(int line=0;line<=224;line++){
  unsigned phase=(unsigned)(line+31)%32;
  g_ppu->vScroll[0]=g_ppu->vScroll[1]=(uint16_t)(128+phase/8);
  IogWorldCaptureLine(line);
 }
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_village_heat"));
 Ppu probe=s.base;memcpy(&probe,s.lines[1].registers,PPU_SAVESTATE_REGS_SIZE);
 CHECK(VillageHeat(&s.epochs[0],&probe));
 s.lines[99].registers[offsetof(Ppu,vScroll)]^=1;
 CHECK(!VillageHeat(&s.epochs[0],&probe)); /* The two layers must share their phase. */
 s.lines[99].registers[offsetof(Ppu,vScroll)+2]^=1;
 CHECK(!VillageHeat(&s.epochs[0],&probe)); /* A shared but aperiodic row still fails. */
 s.lines[99].registers[offsetof(Ppu,vScroll)]^=1;
 s.lines[99].registers[offsetof(Ppu,vScroll)+2]^=1;
 s.epochs[0].ram[0x68a]++;s.epochs[0].ram[0x68c]++;
 CHECK(!VillageHeat(&s.epochs[0],&probe)); /* A three-pixel camera disagreement fails. */
}
static void larai_mist(void){
 fixture();word(0x644,0x1d);word(0x6ee,0x85);
 word(0x692,768);word(0x694,512);word(0x696,1536);word(0x698,1536);
 word(0x56,0x1060);word(0x58,0x1060);effect_camera_actor(0x1060,0xeab4,0,0x0101);
 g_ppu->bgmode=9;g_ppu->bgXsc[0]=0x19;g_ppu->bgXsc[1]=0x11;
 g_ppu->screenEnabled[0]=0x17;g_ppu->screenEnabled[1]=0x12;
 g_ppu->cgwsel=0x82;g_ppu->cgadsub=0x41;
 g_ppu->hScroll[1]=(uint16_t)Word(ram,0x68a);
 g_ppu->vScroll[1]=(uint16_t)Word(ram,0x68e);
 publication();IogWorldBeginRaster();
 for(int line=0;line<=224;line++){
  g_ppu->hScroll[0]=(uint16_t)(176+((line+15)%16)/4);
  IogWorldCaptureLine(line);
 }
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_larai_mist"));
 s.lines[99].registers[offsetof(Ppu,hScroll)]^=1;
 CHECK(RenderWorld()&&!strcmp(s.reason,"ready_legacy_raster_effect"));
 s.lines[99].registers[offsetof(Ppu,hScroll)]^=1;
 s.lines[99].registers[offsetof(Ppu,cgadsub)]^=1;
 CHECK(RenderWorld()&&!strcmp(s.reason,"ready_legacy_raster_effect"));
}
static void great_wall_authored_courses(void){
 /* One allocation stores three256px courses. Observe the active original
  * camera window, never show the other courses as zoomed-out scenery. */
 for(unsigned course=0;course<3;course++){
  fixture();word(0x644,0x85);word(0x692,2048);word(0x696,768);
  word(0x694,256);word(0x698,768);word(0x68A,0);word(0x68E,course*256);
  word(0x68C,0);word(0x690,course*256);
  word(0x6D6,0);word(0x6D8,course*256);word(0x6DA,2048);word(0x6DE,(course+1)*256);
  g_ppu->hScroll[0]=g_ppu->hScroll[1]=0;
  g_ppu->vScroll[0]=g_ppu->vScroll[1]=(uint16_t)(course*256);
  publication();memcpy(before_ram,ram,sizeof(ram));before_ppu=*g_ppu;
  IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
  IogWorldEndRaster(0,225,0);CHECK(s.complete);
  CHECK(s.width==598&&s.height==336&&s.view.world_y==(int)course*256-40);
  CHECK(s.view.native_y==40&&s.view.padding_top==40&&s.view.padding_bottom==40);
  for(int y=0;y<336;y++)for(int x=0;x<598;x++){
   unsigned actual=s.output[y*598+x];
   if(y<40||y>=296)CHECK(actual==0);
   else CHECK(actual==(0xff000000u|(unsigned)x|(((course*256+(unsigned)y-39)&1023)<<10)));
  }
  /* Horizontal sky repetition remains available despite bounded courseY. */
  CHECK(MapTile(&s.epochs[0],1,256,course*256,true)==MapTile(&s.epochs[0],1,0,course*256,true));
  CHECK(!memcmp(before_ram,ram,sizeof(ram))&&!memcmp(before_ppu.vram,g_ppu->vram,sizeof(before_ppu.vram)));
 }
}
static void clouds_outside_terrain_not_objects(void){
 fixture();word(0x644,0x55);word(0x692,512);word(0x696,512);
 word(0x694,512);word(0x698,512);word(0x68a,128);word(0x68e,128);
 g_ppu->hScroll[0]=128;g_ppu->vScroll[0]=128;g_ppu->screenEnabled[0]=19;
 publication();before_ppu=*g_ppu;memcpy(before_ram,ram,sizeof(ram));
 IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 cloud_probe=true;IogWorldEndRaster(0,225,0);cloud_probe=false;CHECK(s.complete);
 for(int y=0;y<336;y++)for(int x=0;x<598;x++){
  int wx=s.view.world_x+x,wy=s.view.world_y+y;
  bool native=x>=s.view.native_x&&x<s.view.native_x+256&&y>=s.view.native_y&&y<s.view.native_y+224;
  bool inside=native||(wx>=0&&wx<512&&wy>=0&&wy<512);
  CHECK(s.output[y*598+x]==(inside?0xffcc2211u:0xff3366eeu));
 }
 CHECK(!memcmp(before_ram,ram,sizeof(ram))&&!memcmp(before_ppu.vram,g_ppu->vram,sizeof(before_ppu.vram)));
 /* An unrelated room must not gain an unbounded background. */
 word(0x644,0x54);IogWorldReset();publication();IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 cloud_probe=true;IogWorldEndRaster(0,225,0);cloud_probe=false;CHECK(s.complete);
 CHECK(s.output[0]==0);
}
static void raster_rom_word(unsigned at,unsigned value){rom[at]=(uint8_t)value;rom[at+1]=(uint8_t)(value>>8);}
static void horizon_picture(unsigned scene,unsigned camera,bool fault,unsigned tail){
 fixture();word(0x644,scene);word(0x692,512);word(0x696,512);word(0x694,512);word(0x698,256);
 word(0x68a,camera);word(0x68e,64);word(0x68c,0);word(0x690,0);word(0x6e4,0);
 word(0x56,0x1060);word(0x58,0x1060);effect_camera_actor(0x1060,0xEAB4,0x0101,0);
 word(0x6d6,0);word(0x6d8,0);word(0x6da,512);word(0x6de,512);
 g_ppu->hScroll[0]=(uint16_t)camera;g_ppu->vScroll[0]=64;g_ppu->vScroll[1]=0;
 g_ppu->screenEnabled[0]=19;
 if(tail){
  word(0x2804,1);word(0x2806,1);
  unsigned at=PPU_bgTileAdr(g_ppu,1)+16+7;
  g_ppu->vram[at]=tail==1?0x00ff:0x80ff;
  g_ppu->cgram[1]=0x0842;g_ppu->cgram[3]=0x7fff;
 }
 raster_rom_word(0x1cc02,0x8000);raster_rom_word(0x18000,0x7800);rom[0x18002]=0x7e;rom[0x18003]=0x0f;rom[0x18004]=8;
 const unsigned heights[]={32,32,32,200},addresses[]={0x720,0x722,0x724,0x726},speeds[]={24,32,40,45};
 unsigned phase[]={0x1a3f+camera-160,0x2237+camera-160,0x0ff9+camera-160,camera*6+45};
 for(unsigned i=0;i<4;i++){
  unsigned at=0x18005+i*8;raster_rom_word(at,65536-heights[i]);raster_rom_word(at+2,addresses[i]);
  raster_rom_word(at+4,i==3?0x020c:0);raster_rom_word(at+6,speeds[i]);word(addresses[i],phase[i]);
 }
 g_ppu->hScroll[1]=(uint16_t)(phase[0]>>4);
 publication();memcpy(before_ram,ram,sizeof ram);CpuState cpu=g_cpu;
 IogWorldBeginRaster();
 for(unsigned line=0;line<=224;line++){
  unsigned band=line<32?0:line<64?1:line<96?2:3;
  g_ppu->hScroll[1]=(uint16_t)((phase[band]>>4)&1023);
  if(fault&&line==100)g_ppu->hScroll[1]^=1;
  IogWorldCaptureLine((int)line);
 }
 before_ppu=*g_ppu;horizon_probe=true;horizon_expected_valid=!fault;horizon_flat_expected=tail==1&&!fault;
 IogWorldEndRaster(0,225,0);horizon_probe=false;
 CHECK(s.complete&&s.width==598&&s.height==336&&s.view.world_x==-43&&s.view.world_y==8);
 CHECK(s.view.native_y==56); /* background row is independent of this offset */
 CHECK(horizon_main_calls==3*336);
 CHECK(horizon_background_calls==(fault?0:3*336));
 CHECK(!strcmp(s.reason,fault?"ready_legacy_raster_effect":"ready"));
 for(unsigned y=0;y<336;y++)for(unsigned x=0;x<598;x++){
  bool foreground=x>=43&&x<555;
  unsigned phase_x=y+1<32?((0x1a3f-203)>>4):y+1<64?((0x2237-203)>>4):y+1<96?((0x0ff9-203)>>4):1010;
  uint32_t want=foreground?0xffcc2211u:(!fault&&y+1<256?
   0xff000000u|((phase_x+x)&1023)|((y+1)<<10):horizon_flat_expected?0xff101010u:0);
  CHECK(s.output[y*598+x]==want);
 }
 CHECK(!memcmp(before_ram,ram,sizeof ram)&&!memcmp(&cpu,&g_cpu,sizeof cpu)&&!memcmp(&before_ppu,g_ppu,sizeof before_ppu));
}
static void calibrated_wall_picture(void){
 fixture();word(0x644,0x86);word(0x692,768);word(0x696,1536);word(0x694,256);word(0x698,2048);
 word(0x68a,400);word(0x68e,100);word(0x68c,0);word(0x690,100);word(0x6e4,0);
 word(0x56,0x1060);word(0x58,0x1060);effect_camera_actor(0x1060,0xEAB4,0,0x0101);
 word(0x6d6,0);word(0x6d8,0);word(0x6da,768);word(0x6de,1536);
 g_ppu->hScroll[0]=400;g_ppu->hScroll[1]=400;g_ppu->vScroll[0]=g_ppu->vScroll[1]=100;
 g_ppu->screenEnabled[0]=19;
 raster_rom_word(0x1cc00+0x1e*2,0x8000);raster_rom_word(0x18000,0x7800);rom[0x18002]=0x7e;rom[0x18003]=0x0f;rom[0x18004]=8;
 const unsigned heights[]={96,160,80,176,80,2048};
 for(unsigned i=0;i<6;i++){
  unsigned at=0x18005+i*8;raster_rom_word(at,65536-heights[i]);raster_rom_word(at+2,0x720+i*2);
  raster_rom_word(at+4,i%2?0x0110:0x0108);
 }
 publication();memcpy(before_ram,ram,sizeof ram);CpuState cpu=g_cpu;
 IogWorldBeginRaster();
 for(unsigned line=0;line<=224;line++){
  unsigned y=100+line;g_ppu->hScroll[1]=(uint16_t)(y<256?400:200);
  IogWorldCaptureLine((int)line);
 }
 before_ppu=*g_ppu;wall_probe=true;IogWorldEndRaster(0,225,0);wall_probe=false;
 CHECK(s.complete&&s.width==598&&s.height==336&&s.view.world_x==170&&s.view.world_y==44);
 CHECK(wall_calls==3*336&&!strcmp(s.reason,"ready"));
 CHECK(!memcmp(before_ram,ram,sizeof ram)&&!memcmp(&cpu,&g_cpu,sizeof cpu)&&!memcmp(&before_ppu,g_ppu,sizeof before_ppu));
}
static void anchored_wall_passages(void){
 const unsigned scenes[]={0x8a,0x8b,0x88,0x82,0x82};
 for(unsigned n=0;n<sizeof scenes/sizeof scenes[0];n++){
  bool lower_entry=n==4,upper_entry=scenes[n]==0x82&&!lower_entry,upper_approach=scenes[n]==0x88;
  bool upper_floor=upper_entry||upper_approach;
  unsigned x=lower_entry?1490:upper_entry?618:upper_approach?768:400;
  unsigned y=lower_entry?512:upper_floor?0:100;
  unsigned width=scenes[n]==0x82?2048:1024;
  fixture();word(0x644,scenes[n]);word(0x692,width);word(0x696,upper_approach?768:1024);
  word(0x694,256);word(0x698,upper_approach?2048:n?1024:768);
  word(0x68a,x);word(0x68e,y);word(0x68c,0);word(0x690,y);
  if(upper_floor){word(0x6de,256);word(0x6da,width);}
  if(lower_entry){word(0x6d8,256);word(0x6de,1024);word(0x6da,width);}
  word(0x56,0x1060);word(0x58,0x1060);effect_camera_actor(0x1060,0xEAB4,0,0x0101);
  g_ppu->hScroll[0]=(uint16_t)x;g_ppu->hScroll[1]=(uint16_t)(x/2);
  g_ppu->vScroll[0]=g_ppu->vScroll[1]=(uint16_t)y;
  g_ppu->screenEnabled[0]=19;
  raster_rom_word(0x1cc00+(n?0x1e:0x1f)*2,0x8000);
  raster_rom_word(0x18000,0x7800);rom[0x18002]=0x7e;rom[0x18003]=0x0f;rom[0x18004]=8;
  raster_rom_word(0x18005,65536-2048);raster_rom_word(0x18007,0x720);
  raster_rom_word(0x18009,0x0108);
  publication();
  if(n==1){ /* BG2 captured a different camera publication from BG1. */
   word(0x68a,398);g_ppu->hScroll[1]=199;
  }
  IogWorldBeginRaster();
  for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
  /* Keep the captured phase at the native screen offset, even at the
   * right-hand approach door. Check both margins and chunk seams. */
  expected_background_x=lower_entry?574:upper_entry?138:upper_approach?42:n?28:29;
  expected_background_y=lower_entry?456:upper_floor?-40:44;background_probe=true;
  /* Rows above the authored field have no calibrated producer band. */
  background_probe_first_row=upper_floor?39:0;
  IogWorldEndRaster(0,225,0);background_probe=false;
  CHECK(s.complete&&s.view.native_x==(upper_approach?342:171)&&
   s.view.native_y==(upper_floor?40:56)&&background_probe_calls==3*336);
 }
}
static void flat_horizon_tail_guards(void){
 fixture();PictureEpoch e;memset(&e,0,sizeof e);
 e.ram[0x694]=0;e.ram[0x695]=2;e.ram[0x698]=0;e.ram[0x699]=1;
 e.ram[0x6a0]=0;e.ram[0x6a1]=0xc0;e.ram[0x6b0]=0;e.ram[0x6b1]=0x28;
 e.ram[0x2804]=e.ram[0x2806]=1;
 unsigned at=PPU_bgTileAdr(g_ppu,1)+16;
 e.vram[at+7]=0x00ff;e.cgram[1]=0x0842;
 CHECK(HorizonFlatTail(&e,g_ppu));
 /* One transparent texel, even with the same zero palette color, refuses. */
 e.vram[at+7]=0x00fe;CHECK(!HorizonFlatTail(&e,g_ppu));e.vram[at+7]=0x00ff;
 /* A reflected patterned tile remains nonuniform; no endpoint-only test. */
 e.vram[at+7]=0x80ff;e.cgram[3]=0x7fff;
 CHECK(!HorizonFlatTail(&e,g_ppu));e.ram[0x2805]=e.ram[0x2807]=0x40;
 CHECK(!HorizonFlatTail(&e,g_ppu));
 /* Palette aliases are visually uniform; distinct colors are not. */
 e.cgram[3]=e.cgram[1];CHECK(HorizonFlatTail(&e,g_ppu));e.cgram[3]=0x7fff;
 /* Vertical flip samples row0, not the opaque row7. */
 e.ram[0x2805]=e.ram[0x2807]=0x80;CHECK(!HorizonFlatTail(&e,g_ppu));
 e.vram[at]=0x00ff;CHECK(HorizonFlatTail(&e,g_ppu));
 /* Only one far-half metatile differs; checking the left edge is insufficient. */
 e.ram[0x2805]=e.ram[0x2807]=0;e.vram[at+7]=0x00ff;
 e.ram[0xc1ff]=1;e.ram[0x280c]=e.ram[0x280e]=2;
 e.vram[at+16+7]=0x00fe;CHECK(!HorizonFlatTail(&e,g_ppu));
 e.vram[at+16+7]=0x00ff;CHECK(HorizonFlatTail(&e,g_ppu));
 e.ram[0x280d]=e.ram[0x280f]=4;e.cgram[17]=0x7fff;
 CHECK(!HorizonFlatTail(&e,g_ppu));e.cgram[17]=e.cgram[1];CHECK(HorizonFlatTail(&e,g_ppu));
 e.ram[0xc1ff]=0;e.ram[0x695]=1;CHECK(!HorizonFlatTail(&e,g_ppu));
}
static void calibrated_finite_horizon(void){
 calibrated_wall_picture();anchored_wall_passages();flat_horizon_tail_guards();
 horizon_picture(0x1a,160,false,1);horizon_picture(0x1c,168,false,1);
 horizon_picture(0x1a,160,false,2);horizon_picture(0x1c,168,false,2);
 horizon_picture(0x1a,160,false,0);horizon_picture(0x1a,168,false,0);
 horizon_picture(0x1c,160,false,0);horizon_picture(0x1c,168,false,0);
 horizon_picture(0x1a,160,true,0);horizon_picture(0x1c,168,true,0);
}
static void bounded_rooftop_and_hieroglyph(void){
 fixture();word(0x644,0xE4);word(0x692,512);word(0x696,512);
 word(0x694,512);word(0x698,512);
 publication();IogWorldBeginRaster();
 for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&s.view.native_x==171&&s.view.native_y==56);
 for(int y=0;y<336;y++)for(int x=0;x<598;x++){
  bool inside=x>=171&&x<427&&y>=56&&y<280;
  CHECK(!!s.output[y*598+x]==inside);
 }
 PictureBounds bounds;
 PictureEpoch *e=&s.epochs[0];
 e->ram[0x695]=1;
 CHECK(!RoomPictureBounds(e,256,256,&bounds));
 fixture();word(0x644,0xDA);word(0x692,1536);word(0x696,256);
 word(0x6D6,256);word(0x6DA,512);word(0x6DE,256);
 word(0x68e,0);g_ppu->vScroll[0]=0;
 publication();IogWorldBeginRaster();
 for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&s.view.native_x==171&&s.view.native_y==56);
 CHECK(RoomPictureBounds(&s.epochs[0],256,0,&bounds)&&bounds.bottom==224);
 for(int y=0;y<336;y++)for(int x=0;x<598;x++){
  bool inside=x>=171&&x<427&&y>=56&&y<280;
  CHECK(!!s.output[y*598+x]==inside);
 }
 s.epochs[0].ram[0x6DB]=3;
 CHECK(!RoomPictureBounds(&s.epochs[0],256,0,&bounds));
 fixture();word(0x644,0x49);word(0x692,256);word(0x696,256);
 word(0x6D6,0);word(0x6D8,0);word(0x6DA,256);word(0x6DE,256);
 publication();IogWorldBeginRaster();IogWorldCaptureLine(1);
 CHECK(RoomPictureBounds(&s.epochs[0],0,0,&bounds)&&bounds.bottom==224);
 fixture();word(0x644,0x0B);word(0x692,512);word(0x696,768);
 word(0xA5EE,0xFFFE);word(0xA5FE,0xFDFC);
 publication();IogWorldBeginRaster();IogWorldCaptureLine(1);
 CHECK(CastleMapMarker(&s.epochs[0]));
 s.epochs[0].ram[0xA5EE]=0;
 CHECK(!CastleMapMarker(&s.epochs[0]));
 fixture();word(0x644,0xF0);word(0x692,256);word(0x696,256);
 word(0x694,256);word(0x698,256);
 publication();IogWorldBeginRaster();IogWorldCaptureLine(1);
 CHECK(RoomPictureBounds(&s.epochs[0],0,0,&bounds)&&bounds.right==256&&bounds.bottom==224);
 /* A stale second-map size only matters while BG2 is shown. */
 s.epochs[0].ram[0x699]=2;
 s.base.screenEnabled[0]|=2;
 CHECK(!RoomPictureBounds(&s.epochs[0],0,0,&bounds));
 s.base.screenEnabled[0]&=(uint8_t)~2;s.base.screenEnabled[1]&=(uint8_t)~2;
 CHECK(RoomPictureBounds(&s.epochs[0],0,0,&bounds)&&bounds.right==256&&bounds.bottom==224);
 s.base.screenEnabled[1]|=2;
 CHECK(!RoomPictureBounds(&s.epochs[0],0,0,&bounds));
}
static void pyramid_puzzle_storage_tail(void){
 fixture();word(0x644,0xCD);word(0x692,256);word(0x696,256);
 word(0x6d6,0);word(0x6d8,0);word(0x6da,256);word(0x6de,256);
 word(0x68a,0);word(0x68e,0);word(0x6ee,5);
 g_ppu->hScroll[0]=0;g_ppu->vScroll[0]=0;
 publication();IogWorldBeginRaster();
 for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&s.view.native_x==171&&s.view.native_y==56);
 for(int y=0;y<336;y++)for(int x=0;x<598;x++){
  bool inside=x>=171&&x<427&&y>=56&&y<280;
  CHECK(!!s.output[y*598+x]==inside);
 }
 PictureBounds bounds;PictureEpoch *e=&s.epochs[0];
 CHECK(RoomPictureBounds(e,0,0,&bounds)&&bounds.bottom==224);
 CHECK(!RoomPictureBounds(e,0,8,&bounds));
 e->ram[0x6ee]=0x85;
 CHECK(!RoomPictureBounds(e,0,0,&bounds));
}
static void angel_entrance_storage_tail(void){
 const struct {unsigned width,height;bool matching;} layouts[]={
  {1280,1024,true},{512,512,true},{512,256,true},
  {1280,512,false},{512,1024,false}
 };
 for(unsigned i=0;i<sizeof(layouts)/sizeof(layouts[0]);i++){
  bool matching=layouts[i].matching;
  fixture();word(0x644,0x69);word(0x692,768);word(0x696,256);
  word(0x694,layouts[i].width);word(0x698,layouts[i].height);
  word(0x6D6,0);word(0x6D8,0);word(0x6DA,768);word(0x6DE,256);
  word(0x6EE,5);word(0x68A,512);word(0x68E,0);
  g_ppu->hScroll[0]=512;g_ppu->vScroll[0]=0;
  publication();IogWorldBeginRaster();
  for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
  IogWorldEndRaster(0,225,0);
  CHECK(s.complete&&s.view.native_y==40&&s.view.native_x==342);
  CHECK(AngelEntranceHasStorageTail(&s.epochs[0])==matching);
  CHECK(s.output[263*598+s.view.native_x]&&s.output[263*598]);
  /* Row 295 would fetch the row after the map; it is padding. */
  for(int y=264;y<296;y++)for(int x=0;x<598;x++)
   CHECK(!!s.output[y*598+x]==(!matching&&y<295));
 }
}
static void generic_authored_window(void){
 bounded_rooftop_and_hieroglyph();
 pyramid_puzzle_storage_tail();
 angel_entrance_storage_tail();
 fixture();word(0x644,0x0D);word(0x692,1024);word(0x696,1024);
 word(0x694,1024);word(0x698,1024);
 word(0x6D6,256);word(0x6D8,256);word(0x6DA,768);word(0x6DE,512);
 publication();memcpy(before_ram,ram,sizeof(ram));before_ppu=*g_ppu;
 CHECK(!BoundedRoomScene(0x0D));
 IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);CHECK(s.complete);
 CHECK(s.view.world_x==213&&s.view.world_y==216);
 CHECK(s.view.native_x==43&&s.view.native_y==40);
 CHECK(s.view.padding_left==43&&s.view.padding_right==43);
 CHECK(s.view.padding_top==40&&s.view.padding_bottom==40);
 for(int y=0;y<336;y++)for(int x=0;x<598;x++){
  uint32_t expected=x>=43&&x<555&&y>=40&&y<295?
   0xff000000u|((213u+x)&1023)|(((217u+y)&1023)<<10):0;
  CHECK(s.output[y*598+x]==expected);
 }
 CHECK(!memcmp(before_ram,ram,sizeof(ram))&&!memcmp(before_ppu.vram,g_ppu->vram,sizeof(before_ppu.vram)));
 /* A stair changes the floor bounds early, with no remembered floor to
  * slide from (a door entered mid-pan, a loaded state). The rows the
  * original camera shows continue across the room's width ([256,768),
  * so from the field's left edge to the picture's right); nothing above or
  * below them, so no peek at the next floor. (Beta 12: black blocks beside
  * the field on Seaside Palace stairs.) */
 IogWorldReset();word(0x6D8,0);word(0x6DE,256);publication();
 IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_authored_window_pan"));
 CHECK(s.view.native_x==171&&s.view.native_y==56);
 for(int y=0;y<336;y++)for(int x=0;x<598;x++){
  uint32_t expected=x>=171&&y>=56&&y<280?
   0xff000000u|((85u+x)&1023)|(((201u+y)&1023)<<10):0;
  CHECK(s.output[y*598+x]==expected);
 }
}
static void republication(void){
 IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 for(unsigned n=0;n<544;n++)ram[0x422+n]=(uint8_t)(n*7+11+s.compose_sequence);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 IogWorldBeforeNmi();for(unsigned n=0;n<256;n++)g_ppu->oam[n]=(uint16_t)Word(ram,0x422+n*2);
 memcpy(g_ppu->highOam,ram+0x622,32);g_ppu->oamWriteCount++;IogWorldAfterNmi();
 CHECK(s.active&&s.publish_sequence==s.compose_sequence);
}
static void picture_at(unsigned camera_x,unsigned camera_y){
 word(0x68a,camera_x);word(0x68e,camera_y);
 g_ppu->hScroll[0]=g_ppu->hScroll[1]=(uint16_t)camera_x;g_ppu->vScroll[0]=g_ppu->vScroll[1]=(uint16_t)camera_y;
 if(s.publish_sequence)republication();else publication();
 IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);CHECK(s.complete);
}
/* The stock camera stops a 256-row frame on the window's edge and shows 224
 * rows of it: the last 32 rows of a window are never on its screen. */
static void stock_camera_bottom_rows(void){
 /* No camera words (other fixtures): the whole map, as before. */
 CHECK(StockBottomRow(ram,0)==INT32_MAX);
 fixture();word(0x6DA,768);word(0x6DC,1024);word(0x6DE,1024);
 CHECK(StockBottomRow(ram,256)==992&&StockBottomRow(ram,768)==992);
 /* A camera a script has taken lower has shown those rows itself. */
 CHECK(StockBottomRow(ram,780)==1004&&StockBottomRow(ram,900)==1124);
 picture_at(256,768);
 CHECK(!strcmp(s.reason,"ready")&&s.view.world_y==656&&s.view.native_y==112&&!s.view.padding_bottom);
 for(int y=0;y<336;y++)CHECK(s.output[y*598+5]==(0xff000000u|((85u+5)&1023)|(((657u+y)&1023)<<10)));
 /* A scene whose visible height is 224 keeps every row of its window. */
 fixture();word(0x6DA,768);word(0x6DC,1056);word(0x6DE,1024);
 CHECK(StockBottomRow(ram,256)==1024);
 picture_at(256,800);CHECK(s.view.world_y==688&&s.view.native_y==112);
 /* A room of one screen: the picture is the stock 224 rows, centred. */
 fixture();word(0x692,256);word(0x696,256);word(0x694,256);word(0x698,256);
 word(0x6DA,256);word(0x6DC,256);word(0x6DE,256);
 picture_at(0,0);
 CHECK(s.view.world_y==-56&&s.view.native_y==56&&s.view.padding_top==56&&s.view.padding_bottom==56);
 for(int y=0;y<336;y++){
  uint32_t expected=y>=56&&y<280?0xff000000u|((unsigned)(y-55)<<10):0;
  CHECK(s.output[y*598+171]==expected);
 }
}
/* A stair names the next floor at once and pans to it. The wide picture
 * slides from one floor to the other and shows both on the way. */
static void stair_pan_between_floors(void){
 fixture();word(0x644,0x0D);word(0x692,1024);word(0x696,1024);word(0x694,1024);word(0x698,1024);
 word(0x6D6,0);word(0x6DA,1024);word(0x6D8,512);word(0x6DC,768);word(0x6DE,768);
 picture_at(256,512);
 CHECK(!strcmp(s.reason,"ready")&&s.view.world_x==85&&s.view.world_y==456&&s.view.native_y==56);
 CHECK(s.pan.valid&&s.pan.top==512&&s.pan.bottom==736&&s.pan.view_y==456);
 CHECK(s.output[55*598+5]==0&&s.output[56*598+5]&&s.output[279*598+5]&&s.output[280*598+5]==0);
 /* The floor above is announced; the camera has not moved yet. */
 word(0x6D8,256);word(0x6DC,512);word(0x6DE,512);
 picture_at(256,512);
 CHECK(!strcmp(s.reason,"ready_authored_window_pan"));
 CHECK(s.view.world_x==85&&s.view.world_y==456&&s.view.native_x==171&&s.view.native_y==56);
 CHECK(s.pan.top==512&&s.pan.view_y==456); /* still the floor it left */
 for(int y=0;y<336;y++)for(int x=0;x<598;x+=13){
  /* The old floor to the bottom of its picture. The floor above appears
   * only as far as the camera has reached it (beta 11: its window opens
   * with filler rows that otherwise sat at the picture's top edge). */
  uint32_t expected=y>=56&&y<280?0xff000000u|((85u+x)&1023)|(((457u+y)&1023)<<10):0;
  CHECK(s.output[y*598+x]==expected);
 }
 /* Half way. The old floor leaves by the bottom of the original field. */
 picture_at(256,384);
 CHECK(s.view.world_y==328&&s.view.native_y==56&&s.view.padding_top==0);
 for(int y=0;y<336;y++)for(int x=0;x<598;x+=13){
  uint32_t expected=y<280?0xff000000u|((85u+x)&1023)|(((329u+y)&1023)<<10):0;
  CHECK(s.output[y*598+x]==expected);
 }
 /* Near the end the usual view could frame the room, and would jump. */
 picture_at(256,272);
 CHECK(!strcmp(s.reason,"ready")&&s.view.world_y==216&&s.view.native_y==56);
 /* Arrived: the new floor alone, at the same place in the frame. */
 picture_at(256,256);
 CHECK(!strcmp(s.reason,"ready")&&s.view.world_y==200&&s.view.native_y==56);
 CHECK(s.pan.top==256&&s.pan.bottom==480&&s.pan.view_y==200);
 CHECK(s.output[55*598+5]==0&&s.output[56*598+5]&&s.output[279*598+5]&&s.output[280*598+5]==0);
 /* Without a remembered floor (a state loaded during the pan) the rows
  * the original camera shows continue across the room (beta 12); rows
  * above and below them stay padding. */
 IogWorldReset();s.publish_sequence=0;word(0x6D8,512);word(0x6DC,768);word(0x6DE,768);
 picture_at(256,256);
 CHECK(!strcmp(s.reason,"ready_authored_window_pan")&&s.view.native_x==171&&s.view.native_y==56);
 CHECK(s.output[100*598+5]&&s.output[100*598+300]&&s.output[20*598+5]==0&&s.output[300*598+5]==0);
}
/* Dark Space keeps its star ring while no HDMA runs: every row then has
 * one scroll. Any row that differs is not that state. */
static void held_star_ring_rows(void){
 fixture();Ppu held=*g_ppu;held.hScroll[1]=300;held.vScroll[1]=40;held.cgwsel=2;held.cgadsub=0x31;
 for(int line=0;line<=224;line++)memcpy(s.lines[line].registers,&held,PPU_SAVESTATE_REGS_SIZE);
 CHECK(CapturedHeldScroll(&held,1));
 Ppu moved=held;moved.hScroll[1]=301;memcpy(s.lines[100].registers,&moved,PPU_SAVESTATE_REGS_SIZE);
 CHECK(!CapturedHeldScroll(&held,1));
 moved=held;moved.vScroll[1]=41;memcpy(s.lines[100].registers,&moved,PPU_SAVESTATE_REGS_SIZE);
 CHECK(!CapturedHeldScroll(&held,1));
 moved=held;moved.cgadsub=0x21;memcpy(s.lines[100].registers,&moved,PPU_SAVESTATE_REGS_SIZE);
 CHECK(!CapturedHeldScroll(&held,1));
 moved=held;moved.bgXsc[1]=0x11;memcpy(s.lines[224].registers,&moved,PPU_SAVESTATE_REGS_SIZE);
 memcpy(s.lines[100].registers,&held,PPU_SAVESTATE_REGS_SIZE);
 CHECK(!CapturedHeldScroll(&held,1));
 memcpy(s.lines[224].registers,&held,PPU_SAVESTATE_REGS_SIZE);
 /* The other background may do what it likes. */
 moved=held;moved.hScroll[0]=77;memcpy(s.lines[50].registers,&moved,PPU_SAVESTATE_REGS_SIZE);
 CHECK(CapturedHeldScroll(&held,1));
}
static void mode7_fixture(void){
 fixture();g_ppu->bgmode=7;g_ppu->inidisp=15;g_ppu->screenEnabled[0]=21;
 g_ppu->screenEnabled[1]=1;g_ppu->cgwsel=0x82;g_ppu->cgadsub=1;
 CHECK(Mode7PlaneLayout(g_ppu,0x59)&&!Mode7PlaneLayout(g_ppu,0x58));
 g_ppu->screenWindowed[1]=1;CHECK(!Mode7PlaneLayout(g_ppu,0x59));
 g_ppu->screenWindowed[1]=0;g_ppu->cgadsub=0;CHECK(!Mode7PlaneLayout(g_ppu,0x59));
 g_ppu->screenEnabled[0]=0x11;g_ppu->cgadsub=0x10;
 CHECK(Mode7PlaneLayout(g_ppu,0x8C)&&Mode7PlaneLayout(g_ppu,0x8D));
 CHECK(!Mode7PlaneLayout(g_ppu,0x8E)&&!Mode7PlaneLayout(g_ppu,0x59));
 g_ppu->windowsel=0x20;CHECK(!Mode7PlaneLayout(g_ppu,0x8C));
 g_ppu->windowsel=0;g_ppu->screenEnabled[0]=21;g_ppu->cgadsub=0;
 g_ppu->screenEnabled[1]=0;g_ppu->cgwsel=0;
 g_ppu->screenEnabled[1]=0;memset(g_ppu->m7matrix,0,sizeof(g_ppu->m7matrix));
 g_ppu->m7matrix[0]=g_ppu->m7matrix[3]=256;
 /* A synthetic two-byte VRAM bus: tilemap low bytes and character high
  * bytes are intentionally unrelated and cover all palette indices. */
 for(unsigned n=0;n<32768;n++)g_ppu->vram[n]=(uint16_t)(((n*29u+11u)&255u)<<8)|((n*13u+7u)&255u);
 CHECK(!s.active&&!s.pending&&!s.composed); /* no actor/OAM publication */
}
static void mode7_menu_dismissal(void){
 static Dma dma;
 mode7_fixture();word(0x644,0xFE);g_ppu->bgmode=9;
 g_snes->dma=&dma;g_snesrecomp_last_hdmaen=0x40;
 dma.channel[6]=(DmaChannel){.bAdr=5,.aBank=0x7E,.aAdr=0x8800};
 uint8_t table[]={127,7,96,7,1,9,0};memcpy(ram+0x8800,table,sizeof(table));
 IogWorldBeginRaster();CHECK(s.valid&&s.mode7&&s.mode7_split==223);
 /* On dismissal the split is at line 225. Admit Mode 7 before HDMA
  * writes BGMODE on line zero, then apply the per-line checks. */
 ram[0x8802]=98;IogWorldBeginRaster();CHECK(s.valid&&s.mode7&&!s.mode7_split);
 g_ppu->bgmode=7;
 for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_mode7_plane"));
 CHECK(s.output[0]!=0&&s.output[335*598]!=0);
 g_ppu->bgmode=9;IogWorldBeginRaster();CHECK(s.valid);
 g_ppu->bgmode=7;IogWorldCaptureLine(0);
 g_ppu->bgmode=9;IogWorldCaptureLine(1);CHECK(!s.valid);
 /* A repeat bit or a different channel target isn't the menu producer. */
 ram[0x8802]=0xE2;IogWorldBeginRaster();CHECK(!s.valid&&!s.mode7);
 ram[0x8802]=98;dma.channel[6].bAdr=6;
 IogWorldBeginRaster();CHECK(!s.valid&&!s.mode7);
 g_snesrecomp_last_hdmaen=0;
}
static void mode7_menu_panel_scale(void){
 static Dma dma;
 mode7_fixture();word(0x644,0xfe);g_ppu->bgmode=9;
 g_snes->dma=&dma;g_snesrecomp_last_hdmaen=0x40;
 dma.channel[6]=(DmaChannel){.bAdr=5,.aBank=0x7e,.aAdr=0x8800};
 const uint8_t table[]={127,7,24,7,1,9,0};memcpy(ram+0x8800,table,sizeof(table));
 const int map_rows=150;
 g_ppu->bgXsc[2]=0x78;
 const unsigned extents[]={4,5,6};
 for(unsigned n=0;n<3;n++){
  s.extent_quarters=extents[n];int w=0,h=0;IogWorldGeometry(1920,1080,&w,&h);
  g_ppu->bgmode=9;IogWorldBeginRaster();CHECK(s.mode7_split==map_rows+1);
  for(int y=0;y<=224;y++){
   g_ppu->bgmode=y<=map_rows?7:9;
   IogWorldCaptureLine(y);
  }
  IogWorldEndRaster(0,225,0);
  CHECK(s.complete&&!strcmp(s.reason,"ready_mode7_destination_menu"));
  for(int i=map_rows*256;i<224*256;i++){
   uint32_t color=0;
   memcpy(&color,source_field+4*i,3);
   s.hud[i]=0xff000000|color;
  }
  int native_left=(w-256)/2,top=(h-224)/2,panel_top=top+map_rows;
  int panel_width=256*h/224,panel_rows=(224-map_rows)*h/224;
  int panel_left=(w-panel_width)/2;
  size_t pitch=(size_t)w*4+16;uint8_t*dst=malloc(pitch*h);
  CHECK(dst);memset(dst,0xa5,pitch*h);
  CHECK(Mode7DestinationPanel(source_field,map_rows));
  CHECK(IogWorldDraw(dst,pitch,source_field,w,h,1)==1);
  for(int y=0;y<h;y++){
   for(int x=0;x<w;x++){
    const uint8_t*out=dst+y*pitch+4*x;
    if(y>=panel_top && y<panel_top+panel_rows && x>=panel_left && x<panel_left+panel_width)
     CHECK(!memcmp(out,source_field+4*((map_rows+(y-panel_top)*(224-map_rows)/panel_rows)*256+
                    (x-panel_left)*256/panel_width),4));
    else if(y>=top && y<panel_top && x>=native_left && x<native_left+256)
     CHECK(!memcmp(out,source_field+4*((y-top)*256+x-native_left),4));
    else if(y>=panel_top) CHECK(!out[0]&&!out[1]&&!out[2]&&!out[3]);
    else CHECK(!memcmp(out,&s.output[y*w+x],4));
   }
   for(size_t b=(size_t)w*4;b<pitch;b++)CHECK(dst[y*pitch+b]==0xa5);
  }
  s.hud[map_rows*256]^=1;
  CHECK(!Mode7DestinationPanel(source_field,map_rows));
  CHECK(IogWorldDraw(dst,pitch,source_field,w,h,1)==1);
  CHECK(!memcmp(dst+panel_top*pitch+native_left*4,source_field+map_rows*256*4,256*4));
  free(dst);
 }
 g_snesrecomp_last_hdmaen=0;
}
static void ship_dream_mosaic(void){
 fixture();word(0x644,0x2A);word(0x692,256);word(0x696,1280);
 word(0x694,512);word(0x698,512);word(0x6ee,5);
 g_ppu->bgmode=9;g_ppu->mosaic=0x63;g_ppu->screenEnabled[0]=23;
 g_ppu->screenEnabled[1]=0;g_ppu->windowsel=0x030033;
 g_ppu->cgwsel=0x80;g_ppu->cgadsub=0xa3;g_snesrecomp_last_hdmaen=6;
 CHECK(StockMosaicLayout(g_ppu,ram));
 g_ppu->cgadsub=0xa2;CHECK(!StockMosaicLayout(g_ppu,ram));
 word(0x644,0x2D);word(0x692,768);word(0x696,512);word(0x6ee,1);
 g_ppu->windowsel=0;g_ppu->cgadsub=0x22;g_snesrecomp_last_hdmaen=0x1e;
 CHECK(StockMosaicLayout(g_ppu,ram));
 g_ppu->cgadsub=0xa1;CHECK(StockMosaicLayout(g_ppu,ram));
 g_ppu->cgadsub=0x21;CHECK(!StockMosaicLayout(g_ppu,ram));
 g_ppu->cgadsub=0x22;
 g_snesrecomp_last_hdmaen=0x1f;CHECK(!StockMosaicLayout(g_ppu,ram));
 word(0x644,0x2E);
 g_ppu->screenEnabled[0]=21;g_ppu->cgadsub=0xa3;g_snesrecomp_last_hdmaen=6;
 CHECK(StockMosaicLayout(g_ppu,ram));
 g_ppu->screenEnabled[0]=23;CHECK(!StockMosaicLayout(g_ppu,ram));
 g_snesrecomp_last_hdmaen=0;
}
static void mode7_angkor_neighbor_mosaic(void){
 fixture();word(0x644,0xBF);word(0x692,512);word(0x696,512);
 word(0x68a,128);word(0x68e,64);
 g_ppu->bgmode=9;g_ppu->mosaic=0x63;g_ppu->screenEnabled[0]=21;
 g_ppu->hScroll[0]=128;g_ppu->vScroll[0]=64;
 g_ppu->mosaicStartLine=1;g_ppu->renderFlags=kPpuRenderFlags_NewRenderer;
 publication();IogWorldBeginRaster();CHECK(s.valid&&!s.mode7);
 for(int y=0;y<=224;y++)IogWorldCaptureLine(y);
 IogWorldEndRaster(0,225,0);CHECK(s.complete);
 /* The first visible chunk seam is deliberately unaligned with size seven. */
 for(int y=0;y<336;y++)for(int x=218;x<231;x++){
  int sx=x-s.view.native_x,sy=y-s.view.native_y+1;
  int mx=((sx%7)+7)%7,my=((sy%7)+7)%7;
  CHECK(s.output[y*598+x]==(0xff000000u|(unsigned)(128+sx-mx)|
      ((unsigned)(64+sy-my)<<10)));
 }
 /* Changed block phase or an unrelated room must keep source fallback. */
 IogWorldBeginRaster();CHECK(s.valid);IogWorldCaptureLine(0);
 g_ppu->mosaic=0x53;IogWorldCaptureLine(1);CHECK(!s.valid);
 word(0x644,0xBE);CHECK(!AngkorVisionMosaic(g_ppu,ram));
}
static void late_story_mosaics(void){
 fixture();word(0x644,0xC3);word(0x6EE,0x0485);
 word(0x692,768);word(0x694,512);word(0x696,512);word(0x698,512);
 g_ppu->bgmode=9;g_ppu->mosaic=0x83;g_ppu->mosaicStartLine=1;
 g_ppu->windowsel=2;g_ppu->screenWindowed[0]=0x17;
 g_ppu->screenEnabled[0]=0x17;g_ppu->screenEnabled[1]=0x12;
 g_ppu->cgwsel=0x82;g_ppu->cgadsub=0x41;g_snesrecomp_last_hdmaen=6;
 publication();IogWorldBeginRaster();CHECK(s.valid&&!s.mode7);
 IogWorldCaptureLine(0);IogWorldCaptureLine(1);CHECK(s.valid);
 g_ppu->cgadsub=0x43;IogWorldCaptureLine(2);CHECK(!s.valid);
 g_ppu->cgadsub=0x41;g_snesrecomp_last_hdmaen=2;
 IogWorldBeginRaster();CHECK(!s.valid);

 fixture();word(0x644,0xEA);word(0x6EE,0x0485);
 word(0x692,256);word(0x694,512);word(0x696,256);word(0x698,256);
 g_ppu->bgmode=9;g_ppu->mosaic=0x93;g_ppu->mosaicStartLine=1;
 g_ppu->screenEnabled[0]=0x15;g_ppu->screenEnabled[1]=0x16;
 g_ppu->cgwsel=0x02;g_ppu->cgadsub=0x21;g_snesrecomp_last_hdmaen=2;
 publication();IogWorldBeginRaster();CHECK(s.valid&&!s.mode7);
 IogWorldCaptureLine(0);IogWorldCaptureLine(1);CHECK(s.valid);
 g_ppu->mosaic=0x91;IogWorldCaptureLine(2);CHECK(!s.valid);
 g_ppu->mosaic=0x93;word(0x696,512);
 IogWorldBeginRaster();CHECK(!s.valid);

 IogWorldReset();
 word(0x644,0xE9);word(0x692,1024);word(0x696,1024);
 publication();IogWorldBeginRaster();CHECK(s.valid&&!s.mode7);
 IogWorldCaptureLine(0);IogWorldCaptureLine(1);CHECK(s.valid);
 g_ppu->cgadsub=0x20;IogWorldCaptureLine(2);CHECK(!s.valid);
 g_ppu->cgadsub=0x21;word(0x698,512);
 IogWorldBeginRaster();CHECK(!s.valid);

 IogWorldReset();
 word(0x644,0xE3);word(0x6EE,1);word(0x694,256);word(0x698,1024);
 g_ppu->screenEnabled[0]=0x17;g_ppu->screenEnabled[1]=0;
 g_ppu->cgwsel=0x80;g_ppu->cgadsub=0xA3;g_snesrecomp_last_hdmaen=6;
 publication();IogWorldBeginRaster();CHECK(s.valid&&!s.mode7);
 IogWorldCaptureLine(0);IogWorldCaptureLine(1);CHECK(s.valid);
 word(0x694,512);IogWorldCaptureLine(2);CHECK(!s.valid);
 g_snesrecomp_last_hdmaen=0;
}
static void story_sky_after_unpaired_upload(void){
 fixture();
 word(0x644,0x58);word(0x6ee,0x85);
 word(0x68a,0);word(0x68e,0);
 word(0x692,512);word(0x694,512);word(0x696,512);word(0x698,512);
 word(0x6da,256);word(0x6de,256);
 g_ppu->bgmode=9;g_ppu->inidisp=15;
 g_ppu->screenEnabled[0]=21;g_ppu->screenEnabled[1]=17;
 g_ppu->hScroll[0]=g_ppu->hScroll[1]=0;
 g_ppu->vScroll[0]=g_ppu->vScroll[1]=0;
 IogWorldBeginRaster();CHECK(!s.valid&&!s.sky_field);
 publication();
 IogWorldBeforeNmi();g_ppu->oamWriteCount++;g_ppu->oam[17]^=1;IogWorldAfterNmi();
 CHECK(!s.active);
 IogWorldBeginRaster();CHECK(s.valid&&s.sky_field&&!s.mode7);
 for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_story_sky_field")&&!visual_builds);
 CHECK(s.view.native_x==171&&s.view.native_y==40);
 static uint8_t dst[598*336*4];
 CHECK(IogWorldDraw(dst,598*4,source_field,598,336,0));
 for(int y=0;y<224;y++)
  CHECK(!memcmp(dst+((y+40)*598+171)*4,source_field+y*256*4,256*4));
 CHECK(!memcmp(dst,s.output,171*4));
 int hud_source=(11*256+8)*4;
 int hud_aperture=((11+40)*598+171+8)*4;
 int hud_display=(17*598+119)*4;
 s.hud[11*256+8]=0xff000000u|source_field[hud_source]|
     ((uint32_t)source_field[hud_source+1]<<8)|((uint32_t)source_field[hud_source+2]<<16);
 s.hud[11*256+9]=s.hud[11*256+8]; /* Different native RGB can be an intervening OBJ. */
 CHECK(IogWorldDraw(dst,598*4,source_field,598,336,0));
 CHECK(!memcmp(dst+hud_display,&s.hud[11*256+8],4));
 CHECK(!memcmp(dst+hud_aperture,(uint8_t *)s.output+hud_aperture,4));
 CHECK(!memcmp(dst+hud_aperture+4,source_field+hud_source+4,4));
 IogWorldBeginRaster();CHECK(s.valid);IogWorldCaptureLine(0);
 g_ppu->windowsel=0x20;IogWorldCaptureLine(1);CHECK(!s.valid);
 IogWorldBeginRaster();CHECK(!s.valid&&!s.sky_field);
 g_ppu->windowsel=0;word(0x644,0x59);
 IogWorldBeginRaster();CHECK(!s.valid&&!s.sky_field);
}
static void stock_actor_field_after_unpaired_upload(void){
 static uint8_t dst[598*336*4];
 const unsigned scene[]={0x0b,0xdf,0x46};
 const unsigned flags[]={0x0185,1,5},math[]={0x83,0xa3,0xa1};
 const unsigned w[]={512,2048,512},bw[]={512,256,256};
 const unsigned h[]={768,512,512},bh[]={768,1024,256};
 for(unsigned test=0;test<3;test++){
  fixture();
  word(0x644,scene[test]);word(0x6ee,flags[test]);
  word(0x68c,256);word(0x690,256);
  word(0x692,w[test]);word(0x694,bw[test]);
  word(0x696,h[test]);word(0x698,bh[test]);
  word(0x6da,w[test]);word(0x6de,h[test]);
  g_ppu->bgmode=9;g_ppu->inidisp=15;g_ppu->screenEnabled[0]=test==2?0x15:0x17;
  g_ppu->cgwsel=0x80;g_ppu->cgadsub=math[test];
  g_snesrecomp_last_hdmaen=test==1?6:0;
  IogWorldBeginRaster();CHECK(!s.valid&&!s.stock_actor_field);
  publication();
  IogWorldBeforeNmi();g_ppu->oamWriteCount++;g_ppu->oam[17]^=1;IogWorldAfterNmi();
  CHECK(!s.active);
  IogWorldBeginRaster();CHECK(s.valid&&s.stock_actor_field&&!s.mode7&&!s.sky_field);
  for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
  IogWorldEndRaster(0,225,0);
  CHECK(s.complete&&!strcmp(s.reason,"ready_stock_actor_field")&&!visual_builds);
  CHECK(IogWorldDraw(dst,598*4,source_field,598,336,0));
  for(int y=0;y<224;y++)
   CHECK(!memcmp(dst+((y+s.view.native_y)*598+s.view.native_x)*4,source_field+y*256*4,256*4));
  CHECK(!memcmp(dst,s.output,s.view.native_x*4));
  word(0x642,1);IogWorldBeginRaster();CHECK(!s.valid&&!s.stock_actor_field);
  word(0x642,0);word(0x68a,258);IogWorldBeginRaster();CHECK(!s.valid);
  word(0x68a,256);IogWorldBeginRaster();CHECK(s.valid);IogWorldCaptureLine(0);
  word(0x6bc,0x1c00);IogWorldCaptureLine(1);CHECK(!s.valid);
  g_snesrecomp_last_hdmaen=0;
 }
}
static void field_window_rebase(void){
 /* An unmeasured window stays on the original field's columns and rows. */
 Ppu p;memset(&p,0,sizeof(p));
 p.window1left=0;p.window1right=0;p.window2left=100;p.window2right=140;
 RebaseFieldWindows(&p,171,true);
 CHECK(p.window1left==171&&p.window1right==171&&p.window2left==255&&p.window2right==0);
 p.window1left=0;p.window1right=0;p.window2left=100;p.window2right=140;
 RebaseFieldWindows(&p,171-224,true);
 CHECK(p.window1left==255&&p.window1right==0&&p.window2left==47&&p.window2right==87);
 p.window1left=250;p.window1right=255;p.window2left=0;p.window2right=255;
 RebaseFieldWindows(&p,171-448,true);
 CHECK(p.window1left==255&&p.window1right==0&&p.window2left==255&&p.window2right==0);
 p.window2left=0;p.window2right=255;
 RebaseFieldWindows(&p,-100,true);
 CHECK(p.window2left==0&&p.window2right==155);
 p.window1left=120;p.window1right=136;p.window2left=0;p.window2right=255;
 RebaseFieldWindows(&p,0,false);
 CHECK(p.window1left==255&&p.window1right==0&&p.window2left==255&&p.window2right==0);
}
static void restored_actor_field_before_first_upload(void){
 static uint8_t dst[598*336*4];
 fixture();g_ppu->inidisp=15;g_ppu->screenEnabled[0]=0x17;
 IogWorldReset();
 IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 IogWorldBeginRaster();CHECK(s.valid&&s.stock_actor_field&&s.restored_actor_field&&!s.active);
 for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_restored_actor_field")&&!visual_builds);
 CHECK(IogWorldDraw(dst,598*4,source_field,598,336,0));
 for(int y=0;y<224;y++)
  CHECK(!memcmp(dst+((y+s.view.native_y)*598+s.view.native_x)*4,source_field+y*256*4,256*4));
 IogWorldBeginRaster();CHECK(!s.valid&&!s.restored_actor_field);
 IogWorldReset();IogWorldBeginRaster();CHECK(!s.valid);
 IogWorldReset();IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 word(0x68a,258);IogWorldBeginRaster();CHECK(!s.valid);
 word(0x68a,256);IogWorldReset();IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 IogWorldBeginRaster();CHECK(s.valid);
 IogWorldCaptureLine(0);word(0x6bc,0x1c00);IogWorldCaptureLine(1);CHECK(!s.valid);
 static const uint8_t additional_rooms[]={
  0x08,0x0a,0x0c,0x0d,0x15,0x29,0x32,0x43,0x46,0x47,0x4f,0x55,0x69,0x6b,
  0x74,0x78,0x79,0x85,0xa2,0xc8,0xe0,0xe1,0xe3,0xea
 };
 for(unsigned i=0;i<sizeof(additional_rooms);i++){
  word(0x644,additional_rooms[i]);word(0x6bc,0);
  IogWorldReset();IogWorldCaptureAtCompose(&g_cpu,0x83c714);
  IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
  CHECK(RestoredActorFieldLayout(g_ppu,ram));
  g_ppu->mosaic=0x11;CHECK(!RestoredActorFieldLayout(g_ppu,ram));
  /* Layer bits with a one-pixel block draw nothing (a mosaic-revealed room). */
  g_ppu->mosaic=3;CHECK(RestoredActorFieldLayout(g_ppu,ram));g_ppu->mosaic=0;
  word(0x642,1);CHECK(!RestoredActorFieldLayout(g_ppu,ram));word(0x642,0);
 }
 word(0x644,0xa2);IogWorldReset();IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 g_ppu->frameInterlace=true;CHECK(!RestoredActorFieldLayout(g_ppu,ram));g_ppu->frameInterlace=false;
 g_ppu->windowsel=2;CHECK(!RestoredActorFieldLayout(g_ppu,ram));g_ppu->windowsel=0;
 CHECK(RestoredActorFieldLayout(g_ppu,ram));
 scene_ready=false;IogWorldBeginRaster();CHECK(!s.valid&&!s.restored_actor_field);
 fixture();word(0x644,0xc3);word(0x6ee,0x0485);
 word(0x692,768);word(0x694,512);word(0x696,512);word(0x698,512);
 g_ppu->windowsel=2;
 IogWorldReset();IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 CHECK(RestoredActorFieldLayout(g_ppu,ram));
 g_ppu->windowsel=3;CHECK(!RestoredActorFieldLayout(g_ppu,ram));
 fixture();word(0x644,0xe8);word(0x6ee,5);
 word(0x692,256);word(0x694,256);word(0x696,512);word(0x698,256);
 g_ppu->inidisp=15;g_ppu->bgmode=9;g_ppu->windowsel=0x300000;
 g_ppu->bgXsc[0]=0x10;g_ppu->bgXsc[1]=0x18;g_ppu->screenEnabled[0]=0x17;
 g_ppu->cgwsel=0x22;g_ppu->cgadsub=3;g_snesrecomp_last_hdmaen=0x0e;
 IogWorldReset();IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 CHECK(RestoredActorFieldLayout(g_ppu,ram));
 g_ppu->cgwsel=0x02;CHECK(!RestoredActorFieldLayout(g_ppu,ram));
 fixture();word(0x644,0xe9);word(0x6ee,0x0485);
 word(0x692,1024);word(0x694,512);word(0x696,1024);word(0x698,256);
 g_ppu->inidisp=9;g_ppu->bgmode=9;g_ppu->mosaic=0x63;
 g_ppu->screenEnabled[0]=0x15;g_ppu->screenEnabled[1]=0x16;
 g_ppu->cgwsel=2;g_ppu->cgadsub=0x21;g_snesrecomp_last_hdmaen=2;
 IogWorldReset();IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 CHECK(RestoredActorFieldLayout(g_ppu,ram));
 g_ppu->mosaic=0x61;CHECK(!RestoredActorFieldLayout(g_ppu,ram));
 g_ppu->mosaic=0x63;g_ppu->cgadsub=0x20;CHECK(!RestoredActorFieldLayout(g_ppu,ram));
 fixture();word(0x644,0xe6);word(0x6ee,0x0405);
 word(0x692,256);word(0x694,512);word(0x696,512);word(0x698,512);
 g_ppu->bgXsc[0]=0x11;g_ppu->bgXsc[1]=0x19;
 g_ppu->inidisp=15;g_ppu->bgmode=9;g_ppu->mosaic=3;
 g_ppu->screenEnabled[0]=0x15;g_ppu->screenEnabled[1]=2;
 g_ppu->cgwsel=2;g_ppu->cgadsub=0x31;g_snesrecomp_last_hdmaen=2;
 IogWorldReset();IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 CHECK(RestoredActorFieldLayout(g_ppu,ram));
 g_ppu->mosaic=0x13;CHECK(!RestoredActorFieldLayout(g_ppu,ram));
 g_snesrecomp_last_hdmaen=0;
}
static void south_cape_house_mosaic(void){
 fixture();
 word(0x644,6);word(0x6ee,5);word(0x68a,0);word(0x68e,0);
 word(0x692,256);word(0x694,512);word(0x696,1280);word(0x698,512);
 word(0x6da,256);word(0x6de,256);
 g_ppu->bgmode=9;g_ppu->mosaic=0x83;g_ppu->mosaicStartLine=1;
 g_ppu->screenEnabled[0]=0x17;g_ppu->cgwsel=0x80;g_ppu->cgadsub=0xa3;
 g_snesrecomp_last_hdmaen=2;
 publication();IogWorldBeginRaster();CHECK(s.valid&&!s.mode7);
 IogWorldCaptureLine(0);IogWorldCaptureLine(1);CHECK(s.valid);
 word(0x6de,512);IogWorldCaptureLine(2);CHECK(!s.valid);
 g_snesrecomp_last_hdmaen=0;
}
static void dark_space_and_coast_mosaics(void){
 const unsigned scenes[]={0xe6,0x2f,0x31};
 const unsigned blend[]={0x31,0x22,0xa3};
 const unsigned hdma[]={2,6,2};
 for(unsigned i=0;i<sizeof(scenes)/sizeof(scenes[0]);i++){
  const bool dark=scenes[i]==0xe6;
  fixture();word(0x644,scenes[i]);word(0x6ee,dark?0x0405:5);
  word(0x692,256);word(0x694,512);word(0x696,dark?512:256);word(0x698,512);
  g_ppu->bgmode=9;g_ppu->mosaic=0x83;g_ppu->mosaicStartLine=1;
  g_ppu->bgXsc[0]=0x11;g_ppu->bgXsc[1]=0x19;
  g_ppu->screenEnabled[0]=dark?0x15:0x17;g_ppu->screenEnabled[1]=dark?2:0;
  g_ppu->cgwsel=dark?2:0x80;g_ppu->cgadsub=blend[i];
  g_snesrecomp_last_hdmaen=hdma[i];
  publication();IogWorldBeginRaster();CHECK(s.valid&&!s.mode7);
  IogWorldCaptureLine(0);IogWorldCaptureLine(1);CHECK(s.valid);
  g_ppu->mosaicStartLine=2;IogWorldCaptureLine(2);CHECK(!s.valid);
  g_ppu->mosaicStartLine=1;g_ppu->cgadsub^=1;
  IogWorldBeginRaster();CHECK(!s.valid);
  g_ppu->cgadsub=blend[i];word(0x698,256);
  IogWorldBeginRaster();CHECK(!s.valid);
 }
 g_snesrecomp_last_hdmaen=0;
}
static void itory_restore_camera(void){
 fixture();word(0x644,0x15);word(0x6ee,5);
 word(0x68a,614);word(0x68e,512);word(0x692,1280);word(0x694,512);
 word(0x696,1024);word(0x698,256);
 g_ppu->bgmode=9;g_ppu->screenEnabled[0]=0x17;g_ppu->screenEnabled[1]=3;
 g_ppu->hScroll[0]=598;g_ppu->vScroll[0]=512;g_ppu->cgwsel=0x82;
 g_snesrecomp_last_hdmaen=2;
 IogWorldReset();IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 IogWorldBeginRaster();CHECK(s.valid&&s.restored_actor_field);
 for(int line=0;line<=224;line++) IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_restored_actor_field"));
 CHECK(s.view.world_x+s.view.native_x==598&&s.view.world_y+s.view.native_y==512);
 s.lines[120].registers[offsetof(Ppu,hScroll)]^=1;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 s.lines[120].registers[offsetof(Ppu,hScroll)]^=1;
 s.restored_actor_field=false;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 g_snesrecomp_last_hdmaen=0;
}
static void watermia_restore_camera(void){
 fixture();word(0x644,0x78);word(0x6ee,0x0085);
 word(0x68a,512);word(0x68e,778);word(0x692,1280);word(0x694,1280);
 word(0x696,1024);word(0x698,1024);
 g_ppu->bgmode=9;g_ppu->bgXsc[0]=0x19;g_ppu->bgXsc[1]=0x11;
 g_ppu->screenEnabled[0]=0x17;g_ppu->screenEnabled[1]=0x12;
 g_ppu->hScroll[1]=512;g_ppu->vScroll[1]=779;
 g_ppu->cgwsel=0x82;g_ppu->cgadsub=0x41;
 IogWorldReset();IogWorldCaptureAtCompose(&g_cpu,0x83c714);
 IogWorldCaptureAfterCompose(&g_cpu,0x83c789);
 IogWorldBeginRaster();CHECK(s.valid&&s.restored_actor_field);
 for(int line=0;line<=224;line++) IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_restored_actor_field"));
 CHECK(s.view.world_x+s.view.native_x==512&&s.view.world_y+s.view.native_y==779);
 s.lines[120].registers[offsetof(Ppu,vScroll)+2]^=1;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
 s.lines[120].registers[offsetof(Ppu,vScroll)+2]^=1;
 s.lines[1].registers[offsetof(Ppu,cgadsub)]^=1;
 CHECK(!RenderWorld()&&!strcmp(s.reason,"camera_publication_mismatch"));
}
static void finite_room_backdrop(void){
 for(unsigned annex=0;annex<2;annex++){
  fixture();
  unsigned scene=annex?0x74:0x47, width=annex?768:256, height=annex?256:768;
  word(0x644,scene);word(0x6ee,5);word(0x68a,0);word(0x68e,0);
  word(0x692,width);word(0x694,width);word(0x696,height);word(0x698,annex?1024:256);
  word(0x6da,256);word(0x6de,height);
  g_ppu->bgmode=9;g_ppu->bgXsc[0]=0x11;g_ppu->bgXsc[1]=0x19;
  g_ppu->hScroll[0]=g_ppu->hScroll[1]=g_ppu->vScroll[0]=g_ppu->vScroll[1]=0;
  g_ppu->screenEnabled[0]=0x15;g_ppu->screenEnabled[1]=0;
  g_ppu->cgwsel=annex?0:0x80;g_ppu->cgadsub=annex?0x21:0xa1;
  g_ppu->inidisp=15;g_ppu->cgram[0]=annex?0x1062:0x0842;
  publication();IogWorldBeginRaster();CHECK(s.valid);
  for(int line=0;line<=224;line++) {
   if(annex&&line==223) g_ppu->screenEnabled[0]=0;
   IogWorldCaptureLine(line);
  }
  IogWorldEndRaster(0,225,0);CHECK(s.complete);
  uint32_t full=annex?0x101821:0x101010;
  CHECK(s.output[0]==full&&s.output[s.width-1]==full);
  CHECK(s.output[(s.height-1)*s.width]==full);
  CHECK(s.output[s.view.native_y*s.width+s.view.native_x]!=full);
  if(annex) {
   CHECK(!FiniteRoomBackdrop(&s.epochs[0],g_ppu,scene,222));
   CHECK(FiniteRoomBackdrop(&s.epochs[0],g_ppu,scene,223)==full);
   g_ppu->cgwsel=0x80;g_ppu->cgadsub=0xa1;
   CHECK(FiniteRoomBackdrop(&s.epochs[0],g_ppu,scene,223)==full);
   g_ppu->screenEnabled[0]=0x15;g_ppu->screenEnabled[1]=0;
   CHECK(FiniteRoomBackdrop(&s.epochs[0],g_ppu,scene,1)==full);
   g_ppu->cgadsub=0x61;
   CHECK(!FiniteRoomBackdrop(&s.epochs[0],g_ppu,scene,1));
   g_ppu->cgadsub=0xa1;
  }
  g_ppu->inidisp=7;
  CHECK(FiniteRoomBackdrop(&s.epochs[0],g_ppu,scene,1)==(annex?0x080810:0x080808));
  g_ppu->inidisp=15;g_ppu->fixedColor=1;
  CHECK(!FiniteRoomBackdrop(&s.epochs[0],g_ppu,scene,1));
  g_ppu->fixedColor=0;g_ppu->windowsel=1;
  CHECK(!FiniteRoomBackdrop(&s.epochs[0],g_ppu,scene,1));
 }
}
static void mode7_lifecycle_and_packet(const char*base){
 ship_dream_mosaic();
 late_story_mosaics();
 story_sky_after_unpaired_upload();
 stock_actor_field_after_unpaired_upload();
 restored_actor_field_before_first_upload();
 itory_restore_camera();
 watermia_restore_camera();
 finite_room_backdrop();
 IogWorldReset();
 south_cape_house_mosaic();
 dark_space_and_coast_mosaics();
 mode7_angkor_neighbor_mosaic();
 mode7_menu_dismissal();
 mode7_menu_panel_scale();
 mode7_fixture();memcpy(before_ram,ram,sizeof(ram));CpuState cpu=g_cpu;
 IogWorldBeginRaster();CHECK(s.mode7&&s.valid&&!s.active);before_ppu=*g_ppu;
 for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 IogWorldEndRaster(0,225,0);CHECK(s.complete&&!strcmp(s.reason,"ready_mode7_plane"));
 CHECK(s.epoch_count==1&&!s.publish_sequence&&!s.compose_sequence);
 CHECK(s.view.native_x==171&&s.view.native_y==56);
 CHECK(!memcmp(before_ram,ram,sizeof(ram))&&!memcmp(&cpu,&g_cpu,sizeof(cpu)));
 CHECK(!memcmp(&before_ppu,g_ppu,sizeof(before_ppu)));
 size_t bytes=(size_t)s.width*s.height*4;uint8_t*dst=malloc(bytes);CHECK(dst);
 CHECK(IogWorldDraw(dst,s.width*4,source_field,s.width,s.height,0)==1);
 for(int y=0;y<s.height;y++)for(int x=0;x<s.width;x++){
  const uint8_t*p=dst+(y*s.width+x)*4;
  if(x>=171&&x<427&&y>=56&&y<280)
   CHECK(!memcmp(p,source_field+((y-56)*256+x-171)*4,4));
  else {
   unsigned index=IogMode7PlaneIndex(&before_ppu,x-171,y-56+1);
   CHECK(*(const uint32_t*)p==(0xff000000u|index*0x010101u));
  }
 }
 free(dst);char path[4096];CHECK(snprintf(path,sizeof(path),"%s.mode7-test",base)>0);
 CHECK(ExportSourcePacket(path,source_field));
 /* Real raster matrices/control extend horizontally at their actual row.
  * No authored transforms exist above/below the224-row perspective band. */
 mode7_fixture();Ppu uniform=*g_ppu;memcpy(before_ram,ram,sizeof(ram));cpu=g_cpu;
 IogWorldBeginRaster();CHECK(s.mode7&&!s.active);
 for(int line=0;line<=224;line++){
  if(line==112)g_ppu->m7matrix[0]=300;
  if(line==160)g_ppu->m7sel=1;
  IogWorldCaptureLine(line);
 }
 before_ppu=*g_ppu;IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&!strcmp(s.reason,"ready_mode7_raster_band"));
 CHECK(!memcmp(before_ram,ram,sizeof(ram))&&!memcmp(&cpu,&g_cpu,sizeof(cpu)));
 CHECK(!memcmp(&before_ppu,g_ppu,sizeof(before_ppu))&&!s.publish_sequence&&!s.compose_sequence);
 uint8_t*band=calloc((size_t)s.width*s.height,4);CHECK(band);
 CHECK(IogWorldDraw(band,s.width*4,source_field,s.width,s.height,0)==1);
 unsigned projected_changes=0;Ppu raster=uniform;
 for(int y=0;y<s.height;y++)for(int x=0;x<s.width;x++){
  const uint8_t*p=band+(y*s.width+x)*4;
  if(y<56||y>=280)CHECK(*(const uint32_t*)p==0);
  else if(x>=171&&x<427)
   CHECK(!memcmp(p,source_field+((y-56)*256+x-171)*4,4));
  else {
   int native_y=y-56+1;
   memcpy(&raster,s.lines[native_y].registers,PPU_SAVESTATE_REGS_SIZE);
   unsigned index=IogMode7PlaneIndex(&raster,x-171,native_y);
   CHECK(*(const uint32_t*)p==(0xff000000u|index*0x010101u));
   projected_changes+=index!=IogMode7PlaneIndex(&uniform,x-171,native_y);
  }
 }
 CHECK(projected_changes>0);free(band);
 CHECK(snprintf(path,sizeof(path),"%s.mode7-raster-test",base)>0);
 CHECK(ExportSourcePacket(path,source_field));
 for(unsigned refusal=0;refusal<6;refusal++){
  mode7_fixture();
  switch(refusal){
   case 0:g_ppu->setini=0x40;break; /* EXTBG */
   case 1:g_ppu->screenEnabled[1]=1;break;
   case 2:g_ppu->mosaic=0x10;break;
   case 3:g_ppu->screenWindowed[0]=1;g_ppu->windowsel=2;break;
   case 4:g_ppu->windowsel=0x200000;break; /* color window */
   case 5:g_ppu->screenEnabled[0]|=2;break; /* unsupported extra BG */
  }
  IogWorldBeginRaster();CHECK(!s.valid&&!s.mode7);
 }
 /* A layout change midway through raster also refuses instead of publishing
  * a partially supported expanded frame. */
 mode7_fixture();IogWorldBeginRaster();IogWorldCaptureLine(0);
 g_ppu->screenEnabled[1]=1;IogWorldCaptureLine(1);
 CHECK(!s.valid&&!strcmp(s.reason,"unsupported_line_effect"));
}
static void calibrated_mode7_capture(unsigned fault){
 mode7_fixture();word(0xB6,1019);word(0xB8,177);word(0xBC,0);
 /* Synthetic source table words only: no ROM graphics or extracted table. */
 rom[0x1C695]=0x30;rom[0x1C696]=0x75; /* cos30000 */
 rom[0x1C595]=0x88;rom[0x1C596]=0x13; /* sin5000 */
 const IogMode7PerspectiveParameters p={177,1019,30000,5000};
 IogWorldBeginRaster();CHECK(s.mode7&&s.valid&&!s.active);
 for(int line=0;line<=224;line++){
  CHECK(IogMode7PerspectiveSample(&p,line<224?line:223,g_ppu->m7matrix)==kIogMode7PerspectiveMatrix);
  if(fault==1&&line==100)g_ppu->m7matrix[0]^=1;
  if(fault==2&&line==112)word(0xB8,178); /* native matrices still match */
  if(fault==3&&line==224)g_ppu->m7matrix[0]^=1; /* wrong terminal hold */
  IogWorldCaptureLine(line);
 }
 memcpy(before_ram,ram,sizeof(ram));before_ppu=*g_ppu;CpuState cpu=g_cpu;
 IogWorldEndRaster(0,225,0);CHECK(s.complete&&!s.active);
 CHECK(!memcmp(before_ram,ram,sizeof(ram))&&!memcmp(&before_ppu,g_ppu,sizeof(before_ppu)));
 CHECK(!memcmp(&cpu,&g_cpu,sizeof(cpu)));
 if(fault){CHECK(!s.mode7_perspective&&!strcmp(s.reason,"ready_mode7_raster_band"));}
 else CHECK(s.mode7_perspective&&!strcmp(s.reason,"ready_mode7_perspective"));
}
static void mode7_producer_validated_extension(const char*base){
 calibrated_mode7_capture(0);
 CHECK(s.mode7_parameters.initial_divisor==177&&s.mode7_parameters.increment==1019);
 CHECK(s.mode7_parameters.cosine==30000&&s.mode7_parameters.sine==5000);
 const IogMode7PerspectiveParameters p={177,1019,30000,5000};
 Ppu sample=before_ppu;unsigned sky_rows=0,upper_ground_rows=0,lower_rows=0;
 uint8_t*dst=malloc((size_t)s.width*s.height*4);CHECK(dst);
 CHECK(IogWorldDraw(dst,s.width*4,source_field,s.width,s.height,0)==1);
 for(int row=0;row<s.height;row++){
  int y=row-56+1,index=y>224?y-1:y;
  IogMode7PerspectiveStatus status;
  if(y>=1&&y<=224){index=y<224?y:223;}
  status=IogMode7PerspectiveSample(&p,index,sample.m7matrix);
  if(y<1){if(status==kIogMode7PerspectiveSky)sky_rows++;else upper_ground_rows++;}
  if(y>224)lower_rows++;
  for(int x=0;x<s.width;x++){
   uint32_t plane=status==kIogMode7PerspectiveSky?0xff000000u:
    0xff000000u|IogMode7PlaneIndex(&sample,x-171,y)*0x010101u;
   CHECK(s.output[row*s.width+x]==plane);
   const uint8_t*pixel=dst+(row*s.width+x)*4;
   if(x>=171&&x<427&&row>=56&&row<280)
    CHECK(!memcmp(pixel,source_field+((row-56)*256+x-171)*4,4));
   else CHECK(*(const uint32_t*)pixel==plane);
  }
 }
 CHECK(sky_rows>0&&upper_ground_rows>0&&lower_rows==56);free(dst);
 char path[4096];CHECK(snprintf(path,sizeof(path),"%s.mode7-perspective-test",base)>0);
 CHECK(ExportSourcePacket(path,source_field));
 /* Reject fitted-looking but unbound inputs. Each fault leaves native
  * center pixels available, but must not publish invented vertical rows. */
 for(unsigned fault=1;fault<=3;fault++){
  calibrated_mode7_capture(fault);
  for(int y=0;y<336;y++)if(y<56||y>=280)
   for(int x=0;x<598;x++)CHECK(s.output[y*598+x]==0);
 }
}
static void preserve_stock_bottom_object_edge(void){
 const unsigned scenes[]={0x54,0x67,1};
 for(unsigned n=0;n<sizeof scenes/sizeof scenes[0];n++){
  fixture();word(0x644,scenes[n]);bottom_edge_object_probe=true;
  publication();IogWorldBeginRaster();
  for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
  IogWorldEndRaster(0,225,0);CHECK(s.complete);
  const uint32_t*bottom=s.output+(s.view.native_y+223)*s.width+s.view.native_x;
  CHECK(bottom[-1]==0xfff00df0u);
  CHECK((bottom[0]==0xfff00df0u)==(scenes[n]==1));
  CHECK(bottom[13]==0xfff00df0u&&bottom[29]==0xfff00df0u);
  CHECK(bottom[s.width]==0xfff00df0u);
 }
}
static void projected_source_row_seam(void){
 fixture();word(0x644,0xcc);word(0x692,512);word(0x696,512);
 word(0x694,512);word(0x698,512);word(0x68a,0);word(0x68e,288);
 word(0x68c,0);word(0x690,0);
 g_ppu->hScroll[0]=g_ppu->hScroll[1]=0;
 g_ppu->vScroll[0]=288;g_ppu->vScroll[1]=0;
 /* Synthetic streamed background: every8px row has its own tile value,
  * shared across all columns. The uploaded ring agrees with map rows0..31.
  * This makes a source-row mismatch visible without using game assets. */
 for(unsigned py=0;py<2;py++)for(unsigned px=0;px<2;px++)
  for(unsigned y=0;y<16;y++)for(unsigned x=0;x<16;x++)
   ram[0xc000+((py*2+px)<<8)+(y<<4)+x]=(uint8_t)(py*16+y);
 for(unsigned n=0;n<32;n++)for(unsigned q=0;q<4;q++)word(0x2800+n*8+q*2,0x6000+n*2+q/2);
 for(unsigned y=0;y<32;y++)for(unsigned x=0;x<64;x++)
  g_ppu->vram[0x1800+(y<<5)+(x&31)+(x&32?0x400:0)]=(uint16_t)(0x6000+y);
 publication();memcpy(before_ram,ram,sizeof(ram));before_ppu=*g_ppu;CpuState cpu=g_cpu;
 IogWorldBeginRaster();for(int line=0;line<=224;line++)IogWorldCaptureLine(line);
 background_probe=source_row_probe=true;expected_background_x=expected_background_y=0;
 IogWorldEndRaster(0,225,0);
 CHECK(s.complete&&s.view.world_y==176&&s.view.native_y==112&&background_probe_calls==3*336);
 CHECK(!memcmp(before_ram,ram,sizeof(ram))&&!memcmp(&cpu,&g_cpu,sizeof(cpu)));
 CHECK(!memcmp(before_ppu.vram,g_ppu->vram,sizeof(before_ppu.vram)));
 CHECK(!memcmp(s.detached.vram,s.epochs[0].vram,sizeof(s.detached.vram)));
}
static void late_ips_identity(const char*base){
 char path[4096];CHECK(snprintf(path,sizeof(path),"%s.synthetic.ips",base)>0);
 const uint8_t valid[]={'P','A','T','C','H',0,0,0,0,1,1,'E','O','F'};
 const uint8_t invalid[]={'P','A','T','C','H',0,0,0,0,1,1,0x20,0,0,0,1,2,'E','O','F'};
 FILE*f=fopen(path,"wb");CHECK(f&&fwrite(valid,1,sizeof(valid),f)==sizeof(valid));fclose(f);
 fixture();IogWorldInitialize();CHECK(s.stock&&identity_hashes==1);publication();CHECK(s.active&&s.pending&&s.composed);
 CHECK(ips_activation!=NULL);ips_path=path;ips_activation();
 CHECK(rom[0]==1&&interpreted==1&&interpret_all_calls==1);
 CHECK(!s.stock&&identity_hashes==2); /* causal: pre-plugin hash cannot survive */
 CHECK(!s.active&&!s.pending&&!s.composed&&!s.valid&&!s.complete&&!s.epoch_count);
 IogWorldCaptureAtCompose(&g_cpu,0x83c714);CHECK(!s.pending);
 /* First valid record followed by an out-of-bounds second record must fail
  * pass0 before ANY bytes change; it must not invalidate stock eligibility. */
 f=fopen(path,"wb");CHECK(f&&fwrite(invalid,1,sizeof(invalid),f)==sizeof(invalid));fclose(f);
 fixture();IogWorldInitialize();publication();ips_path=path;
 uint8_t*before=malloc(sizeof(rom));CHECK(before);memcpy(before,rom,sizeof(rom));ips_activation();
 CHECK(!memcmp(before,rom,sizeof(rom)));free(before);
 CHECK(s.stock&&s.active&&s.pending&&s.composed&&identity_hashes==1&&!interpret_all_calls);
 CHECK(remove(path)==0);
}
static void identity_and_source_packet(const char*path){
 CHECK(ExportSourcePacket(path,source_field));
 fixture();publication();CHECK(s.stock&&s.active);cart.romSize=100;
 IogWorldInitialize();CHECK(!s.stock&&!s.active&&!s.pending&&!s.complete);
 IogWorldCaptureAtCompose(&g_cpu,0x83c714);CHECK(!s.pending);
}
int main(int argc,char**argv){CHECK(argc==2);
 /* These fixtures are the point-sampled hardware reference. The filtered
  * world-map presentation is covered by test_iog_mode7_plane.py and
  * test_iog_mode7_perspective.py. */
 putenv("IOG_WORLD_MAP_FILTER=0");
 phase_queue();epochs_and_read_only();field_window_rebase();geometry_and_canaries();fallback_constant_pixel_scale();stock_modal_plate_scale();stock_ending_plate();stock_opening_plate();live_effect_camera_models();actual_window_enable_gates();late_ips_identity(argv[1]);signed_camera_shake();repeating_secondary_samples();parallax_host_camera_and_static_upload();water_wave();babel_starfield();mansion_fog();village_heat();larai_mist();great_wall_authored_courses();clouds_outside_terrain_not_objects();calibrated_finite_horizon();generic_authored_window();stock_camera_bottom_rows();stair_pan_between_floors();held_star_ring_rows();preserve_stock_bottom_object_edge();projected_source_row_seam();mode7_lifecycle_and_packet(argv[1]);mode7_producer_validated_extension(argv[1]);real_map_edge_framing();identity_and_source_packet(argv[1]);printf("%u world-renderer assertions passed\n",checks);return 0;}
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
    synthetic_digest=hashlib.sha256(bytes(2097152)).hexdigest()
    (out/'snesrecomp_rom_identity.h').write_text('#define SNESRECOMP_ROM_EXPECTED_SHA256 "'+synthetic_digest+'"\n')
    source = out/'world_renderer.c';source.write_text(HARNESS, encoding='utf-8')
    exe = out/'world_renderer.exe'
    command = [args.compiler,'-std=c11','-O1','-Wall','-Wextra','-Werror',
               '-I'+str(out),'-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),
               str(source),str(ROOT/'src/iog_world_view.c'),str(ROOT/'src/iog_world_pixels.c'),str(ROOT/'src/iog_raster_parallax.c'),'-o',str(exe)]
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
    mode7_prefix=str(packet)+'.mode7-test'
    mode7=json.loads(Path(mode7_prefix+'.mode7.json').read_text())
    assert mode7['schema']=='iog-mode7-plane-source-v1' and mode7['composition_paired'] is False
    assert mode7['ready'] and mode7['complete'] and mode7['epoch_bytes']==66048
    assert mode7['native_x']==171 and mode7['native_y']==56 and len(mode7['lines'])==225
    assert Path(mode7_prefix+'.mode7.epochs.bin').stat().st_size==mode7['epochs']*66048
    assert Path(mode7_prefix+'.mode7.field.bgra').read_bytes()==bytes((i*13+7)&255 for i in range(256*224*4))
    assert not Path(mode7_prefix+'.source.json').exists()
    raster_prefix=str(packet)+'.mode7-raster-test'
    raster=json.loads(Path(raster_prefix+'.mode7.json').read_text())
    assert raster['schema']=='iog-mode7-plane-source-v1' and raster['composition_paired'] is False
    assert raster['ready'] and raster['complete'] and raster['native_y']==56
    assert len(set(row['regs'] for row in raster['lines'][1:]))==3
    assert Path(raster_prefix+'.mode7.epochs.bin').stat().st_size==raster['epochs']*66048
    assert Path(raster_prefix+'.mode7.field.bgra').read_bytes()==bytes((i*13+7)&255 for i in range(256*224*4))
    perspective_prefix=str(packet)+'.mode7-perspective-test'
    perspective=json.loads(Path(perspective_prefix+'.mode7.json').read_text())
    assert perspective['perspective_validated'] and perspective['ready'] and perspective['complete']
    assert [perspective[k] for k in ('initial_divisor','increment','cosine','sine')]==[177,1019,30000,5000]
    parameters=Path(perspective_prefix+'.mode7.parameters.bin').read_bytes()
    assert len(parameters)==32 and int.from_bytes(parameters[6:8],'little')==1019
    assert int.from_bytes(parameters[8:10],'little')==177
    assert Path(perspective_prefix+'.mode7.plane.bgrx').stat().st_size==598*336*4
    assert Path(perspective_prefix+'.mode7.field.bgra').read_bytes()==bytes((i*13+7)&255 for i in range(256*224*4))


    # Removing only the late-patch identity refresh must reproduce the stale
    # stock-eligibility failure with the very same synthetic patch and input.
    ips=ROOT/'src/iog_ips.c';text=ips.read_text();needle='    IogWorldInitialize();\n'
    assert text.count(needle)==1
    mutant=out/'ips_without_identity_refresh.c';mutant.write_text(text.replace(needle,''),encoding='utf-8')
    causal=out/'late_patch_causal.c';causal.write_text(HARNESS.replace('#include "iog_ips.c"','#include "'+mutant.as_posix()+'"'),encoding='utf-8')
    causal_exe=out/'late_patch_causal.exe';causal_command=command.copy();causal_command[causal_command.index(str(source))]=str(causal);causal_command[-1]=str(causal_exe)
    causal_build=subprocess.run(causal_command,capture_output=True,text=True)
    (out/'causal-build.log').write_text(causal_build.stdout+causal_build.stderr);causal_build.check_returncode()
    causal_run=subprocess.run([str(causal_exe),str(out/'causal-packet')],env=env,capture_output=True,text=True)
    (out/'causal-run.log').write_text(causal_run.stdout+causal_run.stderr)
    assert causal_run.returncode!=0 and '!s.stock&&identity_hashes==2' in causal_run.stderr
    renderer=ROOT/'src/iog_world_renderer.c';renderer_text=renderer.read_text()
    wrap_needle='if(repeat && w && h) {'
    assert renderer_text.count(wrap_needle)==1
    wrap_mutant=out/'world_without_secondary_repeat.c'
    wrap_mutant.write_text(renderer_text.replace(wrap_needle,'if(false && repeat && w && h) {'),encoding='utf-8')
    wrap_source=out/'secondary_repeat_causal.c'
    wrap_source.write_text(HARNESS.replace('#include "iog_world_renderer.c"','#include "'+wrap_mutant.as_posix()+'"'),encoding='utf-8')
    wrap_exe=out/'secondary_repeat_causal.exe';wrap_command=command.copy()
    wrap_command[wrap_command.index(str(source))]=str(wrap_source);wrap_command[-1]=str(wrap_exe)
    wrap_build=subprocess.run(wrap_command,capture_output=True,text=True)
    (out/'repeat-causal-build.log').write_text(wrap_build.stdout+wrap_build.stderr);wrap_build.check_returncode()
    wrap_run=subprocess.run([str(wrap_exe),str(out/'repeat-causal-packet')],env=env,capture_output=True,text=True)
    (out/'repeat-causal-run.log').write_text(wrap_run.stdout+wrap_run.stderr)
    assert wrap_run.returncode!=0 and 'MapTile(e,1,-1,-1,true)==0x2223' in wrap_run.stderr
    row_needle='int source_y=wy-camy;'
    assert renderer_text.count(row_needle)==1
    row_mutant=out/'world_with_foreground_source_row.c'
    row_mutant.write_text(renderer_text.replace(row_needle,'int source_y=native_y;'),encoding='utf-8')
    row_source=out/'source_row_causal.c'
    row_source.write_text(HARNESS.replace('#include "iog_world_renderer.c"','#include "'+row_mutant.as_posix()+'"'),encoding='utf-8')
    row_exe=out/'source_row_causal.exe';row_command=command.copy()
    row_command[row_command.index(str(source))]=str(row_source);row_command[-1]=str(row_exe)
    row_build=subprocess.run(row_command,capture_output=True,text=True)
    (out/'row-causal-build.log').write_text(row_build.stdout+row_build.stderr);row_build.check_returncode()
    row_run=subprocess.run([str(row_exe),str(out/'row-causal-packet')],env=env,capture_output=True,text=True)
    (out/'row-causal-run.log').write_text(row_run.stdout+row_run.stderr)
    assert row_run.returncode!=0 and 'p->vram[address]==0x600e' in row_run.stderr
    wall_needle='wall_bands=IogRasterParallaxPrepareWall'
    assert renderer_text.count(wall_needle)==1
    wall_mutant=out/'world_without_wall_bands.c'
    wall_mutant.write_text(renderer_text.replace(wall_needle,'wall_bands=false&&IogRasterParallaxPrepareWall'),encoding='utf-8')
    wall_source=out/'wall_bands_causal.c'
    wall_source.write_text(HARNESS.replace('#include "iog_world_renderer.c"','#include "'+wall_mutant.as_posix()+'"'),encoding='utf-8')
    wall_exe=out/'wall_bands_causal.exe';wall_command=command.copy()
    wall_command[wall_command.index(str(source))]=str(wall_source);wall_command[-1]=str(wall_exe)
    wall_build=subprocess.run(wall_command,capture_output=True,text=True)
    (out/'wall-causal-build.log').write_text(wall_build.stdout+wall_build.stderr);wall_build.check_returncode()
    wall_run=subprocess.run([str(wall_exe),str(out/'wall-causal-packet')],env=env,capture_output=True,text=True)
    (out/'wall-causal-run.log').write_text(wall_run.stdout+wall_run.stderr)
    assert wall_run.returncode!=0 and 'p->hScroll[1]' in wall_run.stderr
    inputs = [ROOT/'src/iog_raster_parallax.c',ROOT/'src/iog_raster_parallax.h',ROOT/'src/iog_mode7_perspective.h',ROOT/'src/iog_mode7_plane.h',ROOT/'src/iog_world_renderer.c',ROOT/'src/iog_world_renderer.h',ROOT/'src/iog_visual_objects.h',ROOT/'src/iog_world_view.c',ROOT/'src/iog_world_view.h',ROOT/'src/iog_world_pixels.c',ROOT/'src/iog_world_pixels.h',ips,ROOT/'snesrecomp/runner/src/sha256.c',ROOT/'snesrecomp/runner/src/sha256.h']
    result = dict(passed=run.returncode==0,command=command,
        scope='Actual world module/SDKheaders; stubbed scene/visual/detachedpixels, no real game/APU/PPU parity or GPU',
        sources={str(s.relative_to(ROOT)):hashlib.sha256(s.read_bytes()).hexdigest()for s in inputs},
        stdout=run.stdout,stderr=run.stderr,source_packet_format_and_payload_passed=True,
        actual_SHA256_over_synthetic_ROM=True,synthetic_ROM_digest=synthetic_digest,
        late_IPS_refresh_and_failed_patch_preservation_passed=True,removed_refresh_causal_mutant_rejected=True,
        repeating_secondary_samples_and_clipped_foreground_passed=True,
        actual_detached_parallax_phases_and_static_upload_passed=True,
        projected_uploaded_and_decoded_source_rows_agree_passed=True,
        live_linked_camera_ratios_and_refusals_passed=True,
        uniform_mode7_lifecycle_unpaired_packet_and_same_scale_fallback_passed=True,
        mode7_palette_strip_transport_stub_not_real_PPU_colormath=True,
        calibrated_mode7_full_extent_horizon_and_parameter_matrix_phase_refusals=True,
        nonuniform_mode7_raster_rows_expand_horizontally_with_vertical_padding=True,
        camera_model_read_does_not_mutate_guest_RAM=True,
        calibrated_finite_horizon_per_band_scroll_and_fixed_Y_passed=True,
        finite_horizon_does_not_repeat_vertical_sky_or_unmask_foreground_OBJ=True,
        finite_horizon_flat_tail_opaque_uniform_palette_flip_and_full_extent_guards_passed=True,
        corrupted_horizon_capture_retains_legacy_raster_policy=True,
        calibrated_wall_bands_select_expanded_world_rows_and_fractional_horizontal_rates=True,
        removed_wall_bands_causal_mutant_rejected=True,wall_bands_causal_exit_code=wall_run.returncode,
        fallback_world_pixel_scale_preserved_at_all_three_extents=True,
        great_wall_three_authored_courses_do_not_expose_spare_pages=True,
        foreground_source_row_causal_mutant_rejected=True,
        source_row_causal_exit_code=row_run.returncode,
        removed_secondary_repeat_causal_mutant_rejected=True,
        secondary_repeat_causal_exit_code=wrap_run.returncode,
        causal_exit_code=causal_run.returncode,causal_command=causal_command)
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    run.check_returncode();print(run.stdout.strip())


if __name__=='__main__': main()
