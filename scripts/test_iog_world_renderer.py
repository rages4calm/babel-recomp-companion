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
#include "iog_ips.c"
/* Exercise the real SDK digest over synthetic bytes; count title identity
 * checks without replacing the SHA-256 algorithm with a permissive stub. */
#define sha256_compute fixture_real_sha256_compute
#include "sha256.c"
#undef sha256_compute
static Snes machine;static Cart cart;static Ppu original,before_ppu;
static uint8_t ram[131072],rom[2097152],before_ram[131072];
CpuState g_cpu;Snes *g_snes=&machine;Ppu *g_ppu=&original;
static unsigned checks,detached_lines,visual_builds;static bool randomizer,scene_ready=true;
static unsigned identity_hashes,interpret_all_calls;static int interpreted;
static const char *ips_path;
static SNESModActivationCallback ips_activation;
static uint8_t source_field[256*224*4];
static bool background_probe,static_plane_probe,stream_plane_probe,source_row_probe;
static int expected_background_x,expected_background_y;
static unsigned background_probe_calls;
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
 if(background_probe){
  unsigned row=background_probe_calls/3,start=(background_probe_calls%3)*224;
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
  if(Word(s.active_ram,0x644)==0x85&&!row&&start==448){
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
 identity_hashes=interpret_all_calls=0;interpreted=0;ips_path=NULL;
 background_probe=static_plane_probe=stream_plane_probe=false;background_probe_calls=0;
 source_row_probe=false;
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
 fixture();word(0x68e,0xffef);g_ppu->vScroll[0]=1007;
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
 if(scene==0x85){word(0x692,2048);word(0x696,768);word(0x694,256);word(0x698,768);}
 if(scene==0x55){word(0x692,512);word(0x696,512);word(0x694,512);word(0x698,512);}
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
 background_picture(0x85,8,16,0,16,5,7,false); /* vertical-only, X is fixed */
 background_picture(0xcc,760,592,0,0,5,7,false); /* fixed wall plate */
 background_picture(0x55,128,128,0,0,5,7,false); /* independent sky */
 /* SceneEA's finite256 world is centered at (-171,-40). Its uploaded512
  * ring is authoritative in position-bypass mode; the otherwise identical
  * streamed control MUST modify detached map cells, then restore them. */
 background_picture(0xea,0,0,320,81,154,48,true);
 background_picture(0xea,0,0,320,81,154,48,false);
}
static void projected_source_row_seam(void){
 fixture();word(0x644,0x55);word(0x692,512);word(0x696,512);
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
int main(int argc,char**argv){CHECK(argc==2);phase_queue();epochs_and_read_only();geometry_and_canaries();actual_window_enable_gates();late_ips_identity(argv[1]);signed_camera_shake();repeating_secondary_samples();parallax_host_camera_and_static_upload();projected_source_row_seam();real_map_edge_framing();identity_and_source_packet(argv[1]);printf("%u world-renderer assertions passed\n",checks);return 0;}
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
    inputs = [ROOT/'src/iog_world_renderer.c',ROOT/'src/iog_world_renderer.h',ROOT/'src/iog_visual_objects.h',ROOT/'src/iog_world_view.c',ROOT/'src/iog_world_view.h',ROOT/'src/iog_world_pixels.c',ROOT/'src/iog_world_pixels.h',ips,ROOT/'snesrecomp/runner/src/sha256.c',ROOT/'snesrecomp/runner/src/sha256.h']
    result = dict(passed=run.returncode==0,command=command,
        scope='Actual world module/SDKheaders; stubbed scene/visual/detachedpixels, no real game/APU/PPU parity or GPU',
        sources={str(s.relative_to(ROOT)):hashlib.sha256(s.read_bytes()).hexdigest()for s in inputs},
        stdout=run.stdout,stderr=run.stderr,source_packet_format_and_payload_passed=True,
        actual_SHA256_over_synthetic_ROM=True,synthetic_ROM_digest=synthetic_digest,
        late_IPS_refresh_and_failed_patch_preservation_passed=True,removed_refresh_causal_mutant_rejected=True,
        repeating_secondary_samples_and_clipped_foreground_passed=True,
        actual_detached_parallax_phases_and_static_upload_passed=True,
        projected_uploaded_and_decoded_source_rows_agree_passed=True,
        foreground_source_row_causal_mutant_rejected=True,
        source_row_causal_exit_code=row_run.returncode,
        removed_secondary_repeat_causal_mutant_rejected=True,
        secondary_repeat_causal_exit_code=wrap_run.returncode,
        causal_exit_code=causal_run.returncode,causal_command=causal_command)
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    run.check_returncode();print(run.stdout.strip())


if __name__=='__main__': main()
