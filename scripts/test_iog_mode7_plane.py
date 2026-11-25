"""ROM-free Mode7 plane versus the actual SDK PPU and integer extension oracle."""
from pathlib import Path
import argparse,hashlib,json,os,runpy,subprocess
R=Path(__file__).resolve().parents[1]
BODY=r'''
#include "iog_mode7_plane.h"
#undef IOG_MODE7_PLANE_H
#define IogMode7PlanePixel WrongFlip
#define IogMode7PlaneIndex WrongFlipIndex
#define IogMode7Floor WrongFlipFloor
#define IogMode7PlaneTexel WrongFlipTexel
#define IogMode7PlaneSamples WrongFlipSamples
#define IogMode7PlaneFilteredRow WrongFlipFilteredRow
#include "wrong-flip.h"
#undef IogMode7PlanePixel
#undef IogMode7PlaneIndex
#undef IogMode7Floor
#undef IogMode7PlaneTexel
#undef IogMode7PlaneSamples
#undef IogMode7PlaneFilteredRow
#undef IOG_MODE7_PLANE_H
#define IogMode7PlanePixel WrongTruncation
#define IogMode7PlaneIndex WrongTruncationIndex
#define IogMode7Floor WrongTruncationFloor
#define IogMode7PlaneTexel WrongTruncationTexel
#define IogMode7PlaneSamples WrongTruncationSamples
#define IogMode7PlaneFilteredRow WrongTruncationFilteredRow
#include "wrong-truncation.h"
#undef IogMode7PlanePixel
#undef IogMode7PlaneIndex
#undef IogMode7Floor
#undef IogMode7PlaneTexel
#undef IogMode7PlaneSamples
#undef IogMode7PlaneFilteredRow
static uint32_t expanded_reference(Ppu*p,int x,int y){
 if(PPU_forcedBlank(p))return 0;
 int cx=SnesMode7HdSign13(p->m7matrix[4]),cy=SnesMode7HdSign13(p->m7matrix[5]);
 int h=SnesMode7HdSign13(p->m7matrix[6])-cx,v=SnesMode7HdSign13(p->m7matrix[7])-cy;
 h=(h&0x2000)?(h|~1023):(h&1023);v=(v&0x2000)?(v|~1023):(v&1023);
 int64_t ry=PPU_m7yFlip(p)?255-(int64_t)y:y,rx=PPU_m7xFlip(p)?255-(int64_t)x:x;
 uint32_t u=((uint32_t)((int64_t)p->m7matrix[0]*h)&~63u)+((uint32_t)((int64_t)p->m7matrix[1]*ry)&~63u)+((uint32_t)((int64_t)p->m7matrix[1]*v)&~63u)+(uint32_t)(cx*256)+(uint32_t)(p->m7matrix[0]*rx);
 uint32_t w=((uint32_t)((int64_t)p->m7matrix[2]*h)&~63u)+((uint32_t)((int64_t)p->m7matrix[3]*ry)&~63u)+((uint32_t)((int64_t)p->m7matrix[3]*v)&~63u)+(uint32_t)(cy*256)+(uint32_t)(p->m7matrix[2]*rx);
 unsigned index=0;
 if(!PPU_m7largeField(p)||(u|w)<=0x3ffffu||PPU_m7charFill(p)){
  unsigned tile=((u|w)>0x3ffffu&&PPU_m7largeField(p))?0:p->vram[((w>>11)&127)*128+((u>>11)&127)]&255;
  index=p->vram[tile*64+((w>>8)&7)*8+((u>>8)&7)]>>8;
 }
 unsigned col=p->cgram[index],l=p->inidisp&15;
 unsigned r=(((col&31)*l*2+15)/30),g=((((col>>5)&31)*l*2+15)/30),b=((((col>>10)&31)*l*2+15)/30);
 return ((r*8+r/4)<<16)|((g*8+g/4)<<8)|(b*8+b/4);
}
int main(void){
 unsigned flip_differences=0,truncation_differences=0;g_snes=&machine;machine.ppu=&live;
 for(unsigned n=0;n<768;n++){
  memset(&source,0,sizeof(source));ppu_reset(&source);source.bgmode=7;source.inidisp=(n%16)|(n%97==0?128:0);
  source.screenEnabled[0]=1;source.lastBrightnessMult=255;source.renderFlags=kPpuRenderFlags_NewRenderer;
  source.m7sel=(n&3)|((n>>2)&3)*64;
  for(unsigned i=0;i<32768;i++)source.vram[i]=(uint16_t)next();
  for(unsigned i=0;i<256;i++)source.cgram[i]=(uint16_t)next()&32767;
  for(unsigned i=0;i<8;i++)source.m7matrix[i]=(int16_t)next();
  if(n<64){source.m7matrix[0]=256;source.m7matrix[1]=0;source.m7matrix[2]=0;source.m7matrix[3]=256;for(unsigned i=4;i<8;i++)source.m7matrix[i]=0;}
  if(n%13==0)for(unsigned i=0;i<32768;i++)source.vram[i]&=255; /* index0/backdrop */
  before_ppu=source;unsigned line=1+(n*17)%224;source.renderBuffer=(uint8_t*)actual;source.renderPitch=256*4;
  PpuDrawDetachedLine(&source,(int)line);
  for(unsigned x=0;x<256;x++){
   uint32_t got=IogMode7PlanePixel(&before_ppu,(int)x,(int)line);uint32_t want=actual[(line-1)*256+x]&0xffffff;
   if(got!=want){fprintf(stderr,"mode7 mismatch n=%u x=%u y=%u got=%x want=%x\n",n,x,line,got,want);return 2;}
   checks++;flip_differences+=WrongFlip(&before_ppu,(int)x,(int)line)!=want;truncation_differences+=WrongTruncation(&before_ppu,(int)x,(int)line)!=want;
  }
  for(int y=-300;y<=400;y+=71)for(int x=-1024;x<=1024;x+=73){CHECK(IogMode7PlanePixel(&before_ppu,x,y)==expanded_reference(&before_ppu,x,y));}
  Ppu immutable=before_ppu;for(int x=-20;x<280;x++)(void)IogMode7PlanePixel(&before_ppu,x,(int)line);CHECK(!memcmp(&immutable,&before_ppu,sizeof(immutable)));
  cases++;
 }
 /* Host-filtered presentation row: exact at whole positive scales, a plain
  * texel average when minified, and never a new color on a uniform plane. */
 unsigned before_filtered=checks;
 for(unsigned n=0;n<192;n++){
  memset(&source,0,sizeof(source));ppu_reset(&source);source.bgmode=7;source.inidisp=15;source.screenEnabled[0]=1;
  int scale=1+(int)(n%3);source.m7sel=scale==1?(uint8_t)(((n/3)&3)|(((n/12)&3)*64)):0;
  for(unsigned i=0;i<32768;i++)source.vram[i]=(uint16_t)next();
  uint32_t colors[256],row[300];for(unsigned i=0;i<256;i++)colors[i]=(uint32_t)next()&0xffffffu;
  for(unsigned i=4;i<8;i++)source.m7matrix[i]=(int16_t)next();
  source.m7matrix[0]=source.m7matrix[3]=(int16_t)(256*scale);source.m7matrix[1]=source.m7matrix[2]=0;
  int32_t m[4]={65536*scale,0,0,65536*scale};int y=(int)((n*29)%300)-40;
  before_ppu=source;IogMode7PlaneFilteredRow(&source,m,m,y,-20,300,colors,row);CHECK(!memcmp(&before_ppu,&source,sizeof(source)));
  const Ppu *sp=&source;int fx=PPU_m7xFlip(sp)?1:0,fy=PPU_m7yFlip(sp)?1:0;
  int cx=SnesMode7HdSign13(source.m7matrix[4]),cy=SnesMode7HdSign13(source.m7matrix[5]);
  int h=SnesMode7HdSign13(source.m7matrix[6])-cx,v=SnesMode7HdSign13(source.m7matrix[7])-cy;
  h=(h&0x2000)?(h|~1023):(h&1023);v=(v&0x2000)?(v|~1023):(v&1023);
  for(int i=0;i<300;i++){
   int x=i-20;
   /* A flipped cell [x,x+1) ends on the texel the next point sample reads. */
   if(scale==1){CHECK(row[i]==colors[IogMode7PlaneIndex(&source,x+fx,y+fy)]);continue;}
   int sum[3]={0,0,0};
   for(int dv=0;dv<scale;dv++)for(int du=0;du<scale;du++){
    uint32_t c=colors[SnesMode7HdFetchInt(source.m7sel,source.vram,scale*(h+x)+cx+du,scale*(v+y)+cy+dv,-1)];
    sum[0]+=(int)((c>>16)&255);sum[1]+=(int)((c>>8)&255);sum[2]+=(int)(c&255);
   }
   for(int k=0;k<3;k++){int got=(int)((row[i]>>(16-8*k))&255)*scale*scale;CHECK(abs(got-sum[k])<=scale*scale);}
  }
 }
 for(unsigned n=0;n<64;n++){
  memset(&source,0,sizeof(source));ppu_reset(&source);source.bgmode=7;source.inidisp=15;source.screenEnabled[0]=1;source.m7sel=(uint8_t)(n&3);
  for(unsigned i=0;i<32768;i++)source.vram[i]=(uint16_t)(0x5a00u|(next()&255u));
  uint32_t colors[256],wide[598];for(unsigned i=0;i<256;i++)colors[i]=(uint32_t)next()&0xffffffu;
  for(unsigned i=4;i<8;i++)source.m7matrix[i]=(int16_t)next();
  int32_t from[4],to[4];
  for(unsigned i=0;i<4;i++){from[i]=(int32_t)(next()%2000001u)-1000000;to[i]=from[i]+(int32_t)(next()%4001u)-2000;}
  IogMode7PlaneFilteredRow(&source,from,to,(int)(n*7)-100,-171,598,colors,wide);
  for(unsigned i=0;i<598;i++)CHECK(wide[i]==colors[0x5a]);
  source.inidisp=0x80;IogMode7PlaneFilteredRow(&source,from,to,0,0,598,colors,wide);
  for(unsigned i=0;i<598;i++)CHECK(wide[i]==colors[0]);
  uint32_t guard=0x12345678u;
  IogMode7PlaneFilteredRow(NULL,from,to,0,0,1,colors,&guard);IogMode7PlaneFilteredRow(&source,NULL,to,0,0,1,colors,&guard);
  IogMode7PlaneFilteredRow(&source,from,to,0,0,0,colors,&guard);IogMode7PlaneFilteredRow(&source,from,to,513,0,1,colors,&guard);
  IogMode7PlaneFilteredRow(&source,from,to,0,2049,1,colors,&guard);IogMode7PlaneFilteredRow(&source,from,to,0,0,1,NULL,&guard);
  CHECK(guard==0x12345678u);
 }
 CHECK(IogMode7PlaneSamples(1)==3&&IogMode7PlaneSamples(65536)==3&&IogMode7PlaneSamples(65537)==4&&IogMode7PlaneSamples(131072)==4);
 CHECK(IogMode7PlaneSamples(131073)==6&&IogMode7PlaneSamples(1<<20)==8&&IogMode7PlaneTexel(-1)==-1&&IogMode7PlaneTexel(16777216)==1);
 CHECK(checks-before_filtered>200000);
 CHECK(flip_differences>0&&truncation_differences>0);CHECK(!IogMode7PlanePixel(NULL,0,0));CHECK(!IogMode7PlanePixel(&source,2049,0));CHECK(!IogMode7PlanePixel(&source,0,-513));
 printf("%u checks, %u real-PPU cases; rejected flip=%u truncation=%u\n",checks,cases,flip_differences,truncation_differences);return 0;
}
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--compiler',default='cc');p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();assert out.is_relative_to(R/'.local');out.mkdir(parents=True,exist_ok=True)
 base=runpy.run_path(str(R/'scripts/test_iog_world_pixels.py'))['HARNESS'].split('static void fixture(unsigned n)')[0]
 # The real PPU harness already supplies all callback/bus stubs; this oracle
 # replaces only its test cases, not PPU implementation or palette logic.
 base=base.replace('static Ppu live, live_before, source, reference, candidate;','static Ppu live, live_before, source, reference, candidate, before_ppu;')
 header=(R/'src/iog_mode7_plane.h').read_text();(out/'wrong-flip.h').write_text(header.replace('255-(int64_t)screen_x','(int64_t)screen_x'))
 (out/'wrong-truncation.h').write_text(header.replace('IogMode7Floor(a*h,64)*64','a*h').replace('IogMode7Floor(b*y,64)*64','b*y').replace('IogMode7Floor(b*v,64)*64','b*v'))
 source=out/'plane.c';source.write_text(base+BODY);exe=out/'plane.exe';inputs=[R/'snesrecomp/runner/src/snes'/f for f in ['ppu.c','ppu_legacy.c','hd_jobs.c']]
 cmd=[a.compiler,'-std=c11','-O2','-pthread','-DSNESRECOMP_TRACE=1','-DSNESRECOMP_REVERSE_DEBUG=0','-DSNESRECOMP_INTERP_PROFILE=1','-I'+str(out),'-I'+str(R/'src'),'-I'+str(R/'snesrecomp/runner/src'),str(source),*[str(x)for x in inputs],'-o',str(exe)]
 build=subprocess.run(cmd,capture_output=True,text=True,timeout=120);(out/'build.log').write_text(build.stdout+build.stderr);build.check_returncode()
 env={k:v for k,v in os.environ.items()if not k.startswith(('IOG_','SNESRECOMP_'))};res=subprocess.run([str(exe)],env=env,capture_output=True,text=True,timeout=60);(out/'run.log').write_text(res.stdout+res.stderr);res.check_returncode()
 (out/'receipt.json').write_text(json.dumps({'passed':True,'command':cmd,'stdout':res.stdout,'sources':{str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest()for f in inputs+[R/'src/iog_mode7_plane.h',Path(__file__)]},'scope':'Plain Mode7 BG1 sampling versus actual stock SDK PPU inside field and independent uint32 reference outside. No OBJ/UI/windows/mosaic/color math/HDMA/game/GPU qualification.'},indent=2)+'\n');print(res.stdout)
if __name__=='__main__':main()
