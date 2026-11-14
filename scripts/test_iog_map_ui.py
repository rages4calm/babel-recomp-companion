#!/usr/bin/env python3
"""ROM-free actual map UI/controller, MapView fog and SDK font integration."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "iog_map_ui.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
static unsigned checks;
#define C(x)do{checks++;if(!(x)){fprintf(stderr,"line %u: %s\n",__LINE__,#x);exit(1);}}while(0)
static IogMapDiscovery map;
static unsigned char atlas[48*16*64*16*4],walk[48*64];
static IogMapViewMarker markers[2]={{1,1,2,{255,0,255,255}},{24,32,1,{198,173,107,255}}};
static IogMapViewSource src;
static IogMapUiMetadata meta={true,false,false,1};
static void fixture(void){
 IogMapDiscoveryIdentity id={{1},{2},3};C(IogMapDiscoveryInit(&map,48,64,&id));
 memset(walk,1,sizeof(walk));
 unsigned char mask[48*64];memset(mask,0,sizeof(mask));
 for(unsigned y=27;y<38;y++)for(unsigned x=19;x<30;x++)mask[y*48+x]=1;
 C(IogMapDiscoveryReveal(&map,24,32,12,mask,sizeof(mask),48,NULL));
 for(unsigned y=0;y<64*16;y++)for(unsigned x=0;x<48*16;x++){
  unsigned at=(y*48*16+x)*4;atlas[at]=IogMapDiscoveryIsRevealed(&map,x/16,y/16)?90:255;atlas[at+1]=IogMapDiscoveryIsRevealed(&map,x/16,y/16)?110:0;atlas[at+2]=IogMapDiscoveryIsRevealed(&map,x/16,y/16)?70:255;atlas[at+3]=255;
 }
 src=(IogMapViewSource){&map,atlas,sizeof(atlas),48*16*4,16,walk,sizeof(walk),48,markers,2,true,24,32};
}
static void ppm(const char*path,const unsigned char*p,unsigned w,unsigned h,size_t pitch){FILE*f=fopen(path,"wb");C(f!=NULL);fprintf(f,"P6\n%u %u\n255\n",w,h);for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){const unsigned char*q=p+y*pitch+x*4;unsigned char rgb[3]={q[2],q[1],q[0]};C(fwrite(rgb,1,3,f)==3);}fclose(f);}
static void dimensions(unsigned w,unsigned h,bool full,const char*image){
 size_t pitch=(w+13)*4,n=pitch*h;unsigned char*storage=malloc(n+64),*old=malloc(n),*dst=storage+32;C(storage&&old);memset(storage,0xa5,n+64);
 IogMapUi ui;IogMapUiInit(&ui);C(ui.radar&&!ui.full);if(full){IogMapUiInput in={0};in.toggle_full=true;IogMapUiHandleInput(&ui,&in);}
 C(IogMapUiDraw(&ui,dst,n,pitch,w,h,&src,&meta)&&ui.visible);
 for(unsigned i=0;i<32;i++)C(storage[i]==0xa5&&storage[n+32+i]==0xa5);
 for(unsigned y=0;y<h;y++)for(unsigned x=w*4;x<pitch;x++)C(dst[y*pitch+x]==0xa5);
 for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){unsigned char*q=dst+y*pitch+x*4;C(!(q[0]==255&&q[1]==0&&q[2]==255));}
 if(image)ppm(image,dst,w,h,pitch);
 memcpy(old,dst,n);IogMapUiMetadata hidden=meta;hidden.hidden=true;C(!IogMapUiDraw(&ui,dst,n,pitch,w,h,&src,&hidden)&&!ui.full&&!ui.visible&&!memcmp(dst,old,n));
 IogMapViewSource malformed=src;malformed.scenery_bytes=1;ui.full=true;C(!IogMapUiDraw(&ui,dst,n,pitch,w,h,&malformed,&meta)&&!memcmp(dst,old,n));
 C(!IogMapUiDraw(&ui,dst,n,pitch,w,h,&src,NULL));C(!IogMapUiDraw(&ui,dst,1,pitch,w,h,&src,&meta));C(!IogMapUiDraw(&ui,dst,(size_t)-1,(size_t)INT_MAX*4,w,h,&src,&meta));
 free(old);free(storage);
}
static void actions(void){
 IogMapUi ui;IogMapUiInit(&ui);IogMapUiInput in={0};in.toggle_full=true;IogMapUiHandleInput(&ui,&in);C(ui.full);
 in=(IogMapUiInput){0};in.zoom_in=true;for(unsigned n=0;n<20;n++)IogMapUiHandleInput(&ui,&in);C(ui.zoom_index==7);
 in.zoom_in=false;in.zoom_out=true;for(unsigned n=0;n<20;n++)IogMapUiHandleInput(&ui,&in);C(ui.zoom_index==0);
 in=(IogMapUiInput){0};in.pan_x=in.pan_y=1;in.dt_ms=1000;ui.center_x_q8=ui.center_y_q8=1000;IogMapUiHandleInput(&ui,&in);C(ui.center_x_q8==ui.center_y_q8&&ui.center_x_q8>1000&&ui.center_x_q8<3000);
 in=(IogMapUiInput){0};in.recenter=true;IogMapUiHandleInput(&ui,&in);C(ui.center_pending);
 in=(IogMapUiInput){0};in.close=true;IogMapUiHandleInput(&ui,&in);C(!ui.full&&ui.radar);
 in=(IogMapUiInput){0};in.toggle_radar=true;IogMapUiHandleInput(&ui,&in);C(!ui.radar);
}
static void fog_independence(void){
 unsigned w=598,h=336;size_t n=w*h*4;unsigned char*a=calloc(1,n),*b=calloc(1,n);C(a&&b);IogMapUi u,v;IogMapUiInit(&u);u.full=true;v=u;
 C(IogMapUiDraw(&u,a,n,w*4,w,h,&src,&meta));
 for(unsigned y=0;y<64*16;y++)for(unsigned x=0;x<48*16;x++)if(!IogMapDiscoveryIsRevealed(&map,x/16,y/16)){unsigned at=(y*48*16+x)*4;atlas[at]=0;atlas[at+1]=255;atlas[at+2]=0;}
 markers[0].color=(IogMapViewColor){0,255,0,255};C(IogMapUiDraw(&v,b,n,w*4,w,h,&src,&meta)&&!memcmp(a,b,n));
 IogMapUiInit(&u);u.full=true;C(IogMapUiDraw(&u,a,n,w*4,w,h,&src,&meta));map.identity.layout_sha256[0]^=1;u.center_x_q8=0;u.zoom_index=7;C(IogMapUiDraw(&u,b,n,w*4,w,h,&src,&meta));C(u.center_x_q8==24*256+128&&u.center_y_q8==32*256+128&&u.zoom_index!=7);
 free(a);free(b);
}
static void pointer_actions(void){
 unsigned w=598,h=336;size_t bytes=w*h*4;unsigned char*dst=calloc(1,bytes);C(dst!=NULL);
 IogMapUi u;IogMapUiInit(&u);u.full=true;C(IogMapUiDraw(&u,dst,bytes,w*4,w,h,&src,&meta));u.zoom_index=3;
 int x=u.center_x_q8,y=u.center_y_q8;
 C(IogMapUiPointer(&u,300,140,true,w,h));C(u.dragging);
 C(IogMapUiPointer(&u,316,156,true,w,h));C(u.center_x_q8==x-512&&u.center_y_q8==y-512);
 C(IogMapUiPointer(&u,-100,-100,false,w,h)&&!u.dragging&&!u.pointer_down);
 x=u.center_x_q8;y=u.center_y_q8;
 C(!IogMapUiPointer(&u,100,305,true,w,h));C(!IogMapUiPointer(&u,300,140,true,w,h));C(u.center_x_q8==x&&u.center_y_q8==y);C(IogMapUiPointer(&u,0,0,false,w,h));
 C(!IogMapUiPointer(&u,-1,140,true,w,h));C(!IogMapUiPointer(&u,300,140,true,w,h));C(!u.dragging);C(IogMapUiPointer(&u,0,0,false,w,h));
 C(IogMapUiPointer(&u,480,30,true,w,h));C(u.zoom_index==4);C(!IogMapUiPointer(&u,480,30,true,w,h));C(u.zoom_index==4);C(IogMapUiPointer(&u,480,30,false,w,h));
 C(IogMapUiPointer(&u,450,30,true,w,h));C(u.zoom_index==3);C(IogMapUiPointer(&u,450,30,false,w,h));
 u.center_pending=false;C(IogMapUiPointer(&u,390,30,true,w,h));C(u.center_pending);C(IogMapUiPointer(&u,390,30,false,w,h));C(IogMapUiDraw(&u,dst,bytes,w*4,w,h,&src,&meta));C(u.center_x_q8==src.player_x*256+128);
 C(IogMapUiPointer(&u,300,140,true,w,h));C(IogMapUiPointer(&u,INT_MAX,INT_MIN,true,w,h));C(u.center_x_q8==0&&u.center_y_q8==65536);C(IogMapUiPointer(&u,0,0,false,w,h));
 C(!IogMapUiPointer(&u,100,100,true,344,224));C(!u.pointer_down);
 C(IogMapUiPointer(&u,520,30,true,w,h));C(!u.full&&!u.visible&&!u.dragging);C(!IogMapUiPointer(&u,100,100,true,w,h));
 free(dst);
}
int main(int argc,char**argv){C(argc==3);fixture();actions();pointer_actions();dimensions(598,336,true,argv[1]);dimensions(598,336,false,argv[2]);dimensions(344,224,true,NULL);dimensions(784,336,true,NULL);dimensions(256,160,true,NULL);dimensions(2048,512,true,NULL);meta.gamepad=true;dimensions(344,224,true,NULL);fog_independence();printf("%u map UI assertions passed\n",checks);return 0;}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',default='cc');p.add_argument('--out',type=Path,default=ROOT/'.local/batch-001/visual-fullgame-002/map-ui-tests');a=p.parse_args();out=a.out.resolve();assert out.is_relative_to((ROOT/'.local').resolve());out.mkdir(parents=True,exist_ok=True);c=out/'ui.c';c.write_text(HARNESS);exe=out/'ui.exe'
 inputs=[ROOT/'src/iog_map_ui.c',ROOT/'src/iog_map_view.c',ROOT/'src/iog_map_discovery.c',ROOT/'snesrecomp/runner/src/snes_overlay_draw.c']
 cmd=[a.compiler,'-std=c11','-O1','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),str(c),*[str(x)for x in inputs],'-o',str(exe)];r=subprocess.run(cmd,capture_output=True,text=True);(out/'build.log').write_text(r.stdout+r.stderr);r.check_returncode();r=subprocess.run([str(exe),str(out/'full.ppm'),str(out/'radar.ppm')],capture_output=True,text=True);(out/'run.log').write_text(r.stdout+r.stderr);(out/'receipt.json').write_text(json.dumps({'passed':r.returncode==0,'stdout':r.stdout,'stderr':r.stderr,'sources':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in inputs+[ROOT/'src/iog_map_ui.h']},'scope':'ROM-free actual controller/chrome/MapView/SDKfont; canaries, dimensions, hidden-data independence, identity recenter, pointer drag/header controls and adversarial coordinates. No actual game/runtime integration qualification.'},indent=2)+'\n');r.check_returncode();print(r.stdout.strip())
if __name__=='__main__':main()
