"""ROM-free RGBA scenery/radar compositor, fog privacy and transform checks."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include "iog_map_view.h"
static unsigned checks;
#define CHECK(x)do{checks++;if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static IogMapDiscovery map,before;
static uint8_t atlas[6*40],walk[3*6],mask[12],destination[72*12+16],unchanged[sizeof(destination)];
static const uint8_t fog[4]={3,5,7,255};
static void render(const IogMapViewSource*s,const IogMapViewSettings*v){
 memset(destination,0xc3,sizeof(destination));before=map;
 CHECK(IogMapViewRender(destination+8,72*12,72,16,12,s,v));CHECK(!memcmp(&map,&before,sizeof(map)));
 for(unsigned n=0;n<8;n++)CHECK(destination[n]==0xc3&&destination[sizeof(destination)-1-n]==0xc3);
 for(unsigned y=0;y<12;y++)for(unsigned n=64;n<72;n++)CHECK(destination[8+y*72+n]==0xc3);
}
int main(void){
 IogMapDiscoveryIdentity id={{0},{0},1};CHECK(IogMapDiscoveryInit(&map,4,3,&id));
 mask[0]=mask[1]=mask[4]=1;size_t changed;CHECK(IogMapDiscoveryReveal(&map,0,0,8,mask,12,4,&changed)&&changed==3);
 memset(atlas,0xab,sizeof(atlas));for(unsigned y=0;y<6;y++)for(unsigned x=0;x<8;x++){
  uint8_t*p=atlas+y*40+x*4;p[0]=(uint8_t)x;p[1]=(uint8_t)y;p[2]=60;p[3]=255;
 }
 for(unsigned y=0;y<3;y++)for(unsigned x=0;x<4;x++)walk[y*6+x]=(uint8_t)((x+y)&1);
 IogMapViewSource source={0};source.discovery=&map;source.scenery_rgba=atlas;source.scenery_bytes=sizeof(atlas);source.scenery_stride=40;source.scenery_cell_pixels=2;
 source.walkable=walk;source.walkable_bytes=sizeof(walk);source.walkable_stride=6;
 IogMapViewSettings settings={0};settings.mode=kIogMapViewScenery;settings.transform=(IogMapViewTransform){0,0,1,4,1};
 settings.fog=(IogMapViewColor){3,5,7,0};settings.floor=(IogMapViewColor){10,11,12,255};settings.wall=(IogMapViewColor){20,21,22,255};settings.player=(IogMapViewColor){0,255,0,255};settings.player_radius_pixels=1;
 render(&source,&settings);
 for(unsigned y=0;y<12;y++)for(unsigned x=0;x<16;x++){
  uint8_t*p=destination+8+y*72+x*4;
  if(mask[(y/4)*4+x/4])CHECK(p[0]==x/2&&p[1]==y/2&&p[2]==60&&p[3]==255);
  else CHECK(!memcmp(p,fog,4));
 }
 settings.mode=kIogMapViewRadar;render(&source,&settings);
 for(unsigned y=0;y<12;y++)for(unsigned x=0;x<16;x++){
  uint8_t*p=destination+8+y*72+x*4;
  if(mask[(y/4)*4+x/4]){unsigned value=walk[(y/4)*6+x/4]?10:20;CHECK(p[0]==value&&p[1]==value+1&&p[2]==value+2&&p[3]==255);}
  else CHECK(!memcmp(p,fog,4));
 }
 IogMapViewMarker markers[2]={{0,0,3,{255,0,0,255}},{3,2,2,{255,0,255,255}}};
 source.markers=markers;source.marker_count=2;source.player_present=true;source.player_x=3;source.player_y=2;
 render(&source,&settings);CHECK(destination[8+10*72+14*4+1]==255);
 CHECK(!memcmp(destination+8+4*72+4*4,fog,4)); /* visible marker cannot bleed into hidden cell */
 for(unsigned y=0;y<12;y++)for(unsigned x=0;x<16;x++){
  uint8_t*p=destination+8+y*72+x*4;CHECK(!(p[0]==255&&p[1]==0&&p[2]==255)); /* undiscovered marker */
 }
 source.player_present=false;render(&source,&settings);CHECK(!memcmp(destination+8+10*72+14*4,fog,4));
 source.player_present=true;source.player_x=4;render(&source,&settings);CHECK(!memcmp(destination+8+10*72+14*4,fog,4));
 source.player_present=false;source.marker_count=0;source.markers=NULL;settings.mode=kIogMapViewScenery;
 settings.transform=(IogMapViewTransform){1,0,2,4,1};render(&source,&settings);
 for(unsigned y=0;y<12;y++)for(unsigned x=0;x<16;x++){
  unsigned gx=(2*x+5)/8,gy=y/4;uint8_t*p=destination+8+y*72+x*4;
  if(gx<4&&mask[gy*4+gx])CHECK(p[0]==(2*x+5)/4&&p[1]==y/2&&p[2]==60&&p[3]==255);
  else CHECK(!memcmp(p,fog,4));
 }
 settings.transform=(IogMapViewTransform){-1,0,1,4,1};render(&source,&settings);CHECK(!memcmp(destination+8,fog,4));CHECK(destination[8+4*4+2]==60);
 memset(mask,1,sizeof(mask));CHECK(IogMapDiscoveryReveal(&map,0,0,8,mask,12,4,&changed));
 settings.transform=(IogMapViewTransform){0,0,1,1,2};render(&source,&settings);
 CHECK(destination[8]==2&&destination[9]==2);CHECK(destination[8+4]==6);CHECK(!memcmp(destination+8+8,fog,4));
 settings.transform=(IogMapViewTransform){0,0,1,4,1};atlas[0]=100;atlas[1]=110;atlas[2]=120;atlas[3]=128;render(&source,&settings);
 CHECK(destination[8]==52&&destination[9]==58&&destination[10]==64&&destination[11]==255);
 memcpy(unchanged,destination,sizeof(destination));
 CHECK(!IogMapViewRender(destination+8,71,72,16,12,&source,&settings));
 CHECK(!IogMapViewRender(destination+8,72*12,SIZE_MAX,16,12,&source,&settings));
 CHECK(!IogMapViewRender(destination+8,72*12,72,2049,12,&source,&settings));
 IogMapViewSettings invalid=settings;invalid.transform.scale_numerator=0;CHECK(!IogMapViewRender(destination+8,72*12,72,16,12,&source,&invalid));
 invalid=settings;invalid.transform.origin_denominator=0;CHECK(!IogMapViewRender(destination+8,72*12,72,16,12,&source,&invalid));
 invalid=settings;invalid.transform.origin_x_numerator=INT_MIN;CHECK(!IogMapViewRender(destination+8,72*12,72,16,12,&source,&invalid));
 invalid=settings;invalid.mode=(IogMapViewMode)99;CHECK(!IogMapViewRender(destination+8,72*12,72,16,12,&source,&invalid));
 IogMapViewSource bad=source;bad.scenery_bytes=3;CHECK(!IogMapViewRender(destination+8,72*12,72,16,12,&bad,&settings));
 bad=source;bad.scenery_cell_pixels=17;CHECK(!IogMapViewRender(destination+8,72*12,72,16,12,&bad,&settings));
 bad=source;bad.marker_count=257;CHECK(!IogMapViewRender(destination+8,72*12,72,16,12,&bad,&settings));
 bad=source;bad.markers=markers;bad.marker_count=1;markers[0].radius_pixels=9;CHECK(!IogMapViewRender(destination+8,72*12,72,16,12,&bad,&settings));
 CHECK(!memcmp(destination,unchanged,sizeof(destination)));
 CHECK(!IogMapViewRender(atlas,sizeof(atlas),40,4,3,&source,&settings));
 printf("%u map-view assertions passed\n",checks);return 0;
}
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--compiler',default='cc');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();assert out.is_relative_to(ROOT/'.local');out.mkdir(parents=True,exist_ok=True)
    source=out/'view.c';source.write_text(HARNESS);exe=out/'view.exe'
    inputs=[ROOT/'src/iog_map_view.c',ROOT/'src/iog_map_view.h',ROOT/'src/iog_map_discovery.c',ROOT/'src/iog_map_discovery.h']
    command=[a.compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),str(source),str(inputs[0]),str(inputs[2]),'-o',str(exe)]
    b=subprocess.run(command,capture_output=True,text=True);(out/'build.log').write_text(b.stdout+b.stderr);b.check_returncode()
    r=subprocess.run([str(exe)],capture_output=True,text=True);(out/'run.log').write_text(r.stdout+r.stderr);r.check_returncode()
    (out/'receipt.json').write_text(json.dumps({'passed':True,'stdout':r.stdout,'command':command,'sources':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in inputs+[Path(__file__)]},'scope':'Pure RGBA scenery/radar, exploration privacy, player marker and rational pan/zoom compositor; synthetic atlas only. No game/UI wiring or extracted scenery.'},indent=2)+'\n');print(r.stdout)
if __name__=='__main__':main()
