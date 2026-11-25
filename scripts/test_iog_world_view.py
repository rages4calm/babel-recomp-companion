#!/usr/bin/env python3
"""ROM-free camera-boundary properties and actual town framing regression."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "iog_world_view.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned checks;
#define CHECK(c) do{++checks;if(!(c)){fprintf(stderr,"line%d: %s\n",__LINE__,#c);exit(1);}}while(0)
static void properties(int x,int y,unsigned mw,unsigned mh,unsigned w,unsigned h){
 IogWorldView v;CHECK(IogWorldViewCompute(x,y,mw,mh,w,h,&v));
 CHECK(v.width==w&&v.height==h);
 CHECK(v.world_x+v.native_x==x&&v.world_y+v.native_y==y);
 /* All authentic source pixels remain inside the host view at every edge. */
 CHECK(v.native_x+256u<=w&&v.native_y+224u<=h);
 if(mw>=w){CHECK(v.world_x>=0&&v.world_x+(int)w<=(int)mw);CHECK(!v.padding_left&&!v.padding_right);}
 else{CHECK(v.world_x<=0&&v.world_x+(int)w>=(int)mw);CHECK(v.padding_left+mw+v.padding_right==w);CHECK(abs((int)v.padding_left-v.padding_right)<=1);}
 if(mh>=h){CHECK(v.world_y>=0&&v.world_y+(int)h<=(int)mh);CHECK(!v.padding_top&&!v.padding_bottom);}
 else{CHECK(v.world_y<=0&&v.world_y+(int)h>=(int)mh);CHECK(v.padding_top+mh+v.padding_bottom==h);CHECK(abs((int)v.padding_top-v.padding_bottom)<=1);}
 CHECK(v.padding_left<=w&&v.padding_right<=w&&v.padding_top<=h&&v.padding_bottom<=h);
}
static void shake_properties(int x,int y,unsigned mw,unsigned mh,unsigned w,unsigned h){
 struct {uint64_t before;IogWorldView view;uint64_t after;} guarded={0x123456789abcdef0ULL,{0},0xfedcba9876543210ULL};
 CHECK(IogWorldViewCompute(x,y,mw,mh,w,h,&guarded.view));
 CHECK(guarded.before==0x123456789abcdef0ULL&&guarded.after==0xfedcba9876543210ULL);
 IogWorldView v=guarded.view;
 CHECK(v.world_x+v.native_x==x&&v.world_y+v.native_y==y);
 CHECK(v.native_x+256u<=w&&v.native_y+224u<=h);
 CHECK(v.padding_left==(v.world_x<0?-v.world_x:0));
 CHECK(v.padding_top==(v.world_y<0?-v.world_y:0));
 CHECK(v.padding_right==(v.world_x+(int)w>(int)mw?v.world_x+(int)w-(int)mw:0));
 CHECK(v.padding_bottom==(v.world_y+(int)h>(int)mh?v.world_y+(int)h-(int)mh:0));
}
int main(void){
 IogWorldView v,zero={0};
 /* The reported 1.5x town shot previously started at worldX=-19. */
 CHECK(IogWorldViewCompute(152,484,768,768,598,336,&v));
 CHECK(v.world_x==0&&v.world_y==428&&v.native_x==152&&v.native_y==56);
 CHECK(!v.padding_left&&!v.padding_right&&!v.padding_top&&!v.padding_bottom);
 CHECK(IogWorldViewCompute(512,544,768,768,598,336,&v));
 CHECK(v.world_x==170&&v.world_y==432&&v.native_x==342&&v.native_y==112);
 CHECK(IogWorldViewCompute(152,0,512,256,598,336,&v));
 CHECK(v.world_x==-43&&v.world_y==-40&&v.padding_left==43&&v.padding_right==43&&v.padding_top==40&&v.padding_bottom==40);
 const unsigned maps[]={256,512,768,1024,65535},widths[]={256,398,498,598,2048},heights[]={224,280,336,512};
 for(unsigned a=0;a<5;a++)for(unsigned b=0;b<5;b++)for(unsigned c=0;c<5;c++)for(unsigned d=0;d<4;d++){
  unsigned mw=maps[a],mh=maps[b],xs[]={0,1,(mw-256)/2,mw-257,mw-256},ys[]={0,1,(mh-224)/2,mh-225,mh-224};
  for(unsigned e=0;e<5;e++)for(unsigned f=0;f<5;f++)if(xs[e]<=mw-256&&ys[f]<=mh-224)properties(xs[e],ys[f],mw,mh,widths[c],heights[d]);
 }
 int previous=-1;
 for(int x=0;x<=512;x++){CHECK(IogWorldViewCompute(x,484,768,768,598,336,&v));CHECK(v.world_x>=previous&&(previous<0||v.world_x-previous<=1));previous=v.world_x;}
 CHECK(IogWorldViewCompute(-1,0,768,768,256,224,&v)&&v.world_x==-1&&v.native_x==0&&v.padding_left==1);
 CHECK(IogWorldViewCompute(-1,0,768,768,598,336,&v)&&v.world_x==-1&&v.native_x==0&&v.padding_left==1);
 CHECK(IogWorldViewCompute(513,545,768,768,256,224,&v)&&v.world_x==513&&v.world_y==545&&v.padding_right==1&&v.padding_bottom==1);
 for(unsigned a=0;a<4;a++)for(unsigned b=0;b<4;b++)for(unsigned c=0;c<5;c++)for(unsigned d=0;d<4;d++){
  unsigned mw=maps[a],mh=maps[b];int xs[]={-16,-1,0,(int)mw-256,(int)mw-255,(int)mw-240};
  int ys[]={-16,-1,0,(int)mh-224,(int)mh-223,(int)mh-208};
  for(unsigned e=0;e<6;e++)for(unsigned f=0;f<6;f++)shake_properties(xs[e],ys[f],mw,mh,widths[c],heights[d]);
 }
 const int invalid[][6]={{-17,0,768,768,598,336},{0,-17,768,768,598,336},{529,0,768,768,598,336},{0,561,768,768,598,336},{0,0,255,768,598,336},{0,0,768,223,598,336},{0,0,65536,768,598,336},{0,0,768,65536,598,336},{0,0,768,768,255,336},{0,0,768,768,2049,336},{0,0,768,768,598,223},{0,0,768,768,598,513},{INT32_MIN,0,768,768,598,336},{INT32_MAX,0,768,768,598,336}};
 for(unsigned n=0;n<sizeof(invalid)/sizeof(invalid[0]);n++){
  memset(&v,0xA5,sizeof(v));CHECK(!IogWorldViewCompute(invalid[n][0],invalid[n][1],invalid[n][2],invalid[n][3],invalid[n][4],invalid[n][5],&v));CHECK(!memcmp(&v,&zero,sizeof(v)));
 }
 CHECK(!IogWorldViewCompute(0,0,768,768,598,336,NULL));
 /* The original depth-sort edge test with the window as parameters: the
  * stock 256/224 spans, then a wide span that contains the original one. */
 CHECK(IogWorldViewAxisOnscreen(100,0,16,100,256));CHECK(IogWorldViewAxisOnscreen(355,0,16,100,256));
 CHECK(!IogWorldViewAxisOnscreen(356,0,16,100,256));CHECK(IogWorldViewAxisOnscreen(363,8,16,100,256));
 CHECK(IogWorldViewAxisOnscreen(90,8,16,100,256));CHECK(IogWorldViewAxisOnscreen(84,8,16,100,256));CHECK(!IogWorldViewAxisOnscreen(83,8,16,100,256));
 CHECK(!IogWorldViewAxisOnscreen(84,8,0,100,256));CHECK(IogWorldViewAxisOnscreen(3,8,16,0,256));
 CHECK(!IogWorldViewAxisOnscreen(500,0,16,100,256));CHECK(IogWorldViewAxisOnscreen(500,0,16,-71,598));
 CHECK(!IogWorldViewAxisOnscreen(527,0,16,-71,598));CHECK(IogWorldViewAxisOnscreen(526,0,16,-71,598));
 for(int cam=0;cam<2048;cam+=37)for(int pos=cam-400;pos<cam+700;pos+=3)for(int org=0;org<48;org+=15)for(int ext=0;ext<64;ext+=21){
  bool narrow=IogWorldViewAxisOnscreen((uint16_t)pos,(uint16_t)org,(uint16_t)ext,cam,256);
  bool wide=IogWorldViewAxisOnscreen((uint16_t)pos,(uint16_t)org,(uint16_t)ext,cam-171,598);
  int edge=pos-org-cam;bool model=(edge>=0&&edge<256)||(edge<0&&pos+ext-cam>=0&&pos+ext-cam<256);
  CHECK(narrow==model);CHECK(!narrow||wide);
 }
 printf("%u world-view assertions passed\n",checks);return 0;
}
'''

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',default='cc');p.add_argument('--out',type=Path,default=ROOT/'.local/world-view-tests');a=p.parse_args()
 out=a.out.resolve()
 if not out.is_relative_to((ROOT/'.local').resolve()):p.error('test output must stay under ignored .local/')
 out.mkdir(parents=True,exist_ok=True);c=out/'view.c';c.write_text(HARNESS);exe=out/'view.exe'
 command=[a.compiler,'-std=c11','-O1','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),str(c),str(ROOT/'src/iog_world_view.c'),'-o',str(exe)]
 b=subprocess.run(command,capture_output=True,text=True);(out/'build.log').write_text(b.stdout+b.stderr);b.check_returncode()
 r=subprocess.run([str(exe)],capture_output=True,text=True);(out/'run.log').write_text(r.stdout+r.stderr)
 inputs=[ROOT/'src/iog_world_view.c',ROOT/'src/iog_world_view.h']
 (out/'receipt.json').write_text(json.dumps(dict(passed=r.returncode==0,command=command,source_hashes={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in inputs},stdout=r.stdout,scope='Pure host framing only; actual scenery/CPU/PPU/camera movement qualified separately.'),indent=2)+'\n')
 r.check_returncode();print(r.stdout.strip())
if __name__=='__main__':main()
