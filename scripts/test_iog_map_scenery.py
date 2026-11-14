"""ROM-free packed-map scenery oracle and actual SDK PPU comparisons."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BODY = r'''
#include "iog_map_scenery.h"
#include <limits.h>
static uint8_t mapram[65536],oldram[65536],cellids[32][48],ink[1024][64];
static uint16_t characters[32768],oldcharacters[32768],palette[256],oldpalette[256],definitions[256][4];
static uint32_t canvas[800*520],oldcanvas[800*520];
static IogMapScenerySource map;
static unsigned shade(unsigned n){return n*8+n/4;}
static uint32_t color(unsigned n){unsigned c=palette[n];return 0xff000000u|(shade(c&31)<<16)|(shade((c>>5)&31)<<8)|shade((c>>10)&31);}
static unsigned oracle_tile(unsigned x,unsigned y){return definitions[cellids[y/16][x/16]][(y%16/8)*2+x%16/8];}
static uint32_t oracle(unsigned x,unsigned y){
 unsigned t=oracle_tile(x,y),cx=x%8,cy=y%8;
 if(t&0x4000)cx=7-cx;if(t&0x8000)cy=7-cy;
 unsigned n=ink[t&1023][cy*8+cx];return n?color(((t>>10)&7)*16+n):0;
}
static void setup(unsigned seed){
 memset(mapram,0,sizeof mapram);memset(characters,0,sizeof characters);
 for(unsigned n=0;n<256;n++)palette[n]=(uint16_t)((n*131+seed*109)&32767);palette[0]=0;
 for(unsigned t=0;t<1024;t++)for(unsigned y=0;y<8;y++)for(unsigned x=0;x<8;x++){
  unsigned n=(t*3+y*5+x+seed)&15;ink[t][y*8+x]=(uint8_t)n;
  for(unsigned bit=0;bit<4;bit++)if(n&(1u<<bit))characters[t*16+y+(bit/2)*8]|=(uint16_t)(1u<<(7-x+(bit%2)*8));
 }
 for(unsigned i=0;i<256;i++)for(unsigned q=0;q<4;q++){
  unsigned t=((i*17+q*97+seed)&1023)|(((i+q+seed)&7)<<10)|(((i^q)&1)?0x4000:0)|(((i+q)&2)?0x8000:0);
  definitions[i][q]=(uint16_t)t;unsigned at=0x2000+i*8+q*2;mapram[at]=(uint8_t)t;mapram[at+1]=(uint8_t)(t>>8);
 }
 for(unsigned my=0;my<32;my++)for(unsigned mx=0;mx<48;mx++){
  unsigned id=(my*13+mx*7+(my/16)*43+(mx/16)*61+seed)&255;cellids[my][mx]=(uint8_t)id;
  unsigned page=(my/16)*3+mx/16,at=0xa000+page*256+(my%16)*16+mx%16;mapram[at]=(uint8_t)id;
 }
 map=(IogMapScenerySource){mapram,sizeof mapram,characters,palette,32768,256,768,512,0xa000,0x2000,0};
 memcpy(oldram,mapram,sizeof mapram);memcpy(oldcharacters,characters,sizeof characters);memcpy(oldpalette,palette,sizeof palette);
}
static void immutable(void){CHECK(!memcmp(oldram,mapram,sizeof mapram));CHECK(!memcmp(oldcharacters,characters,sizeof characters));CHECK(!memcmp(oldpalette,palette,sizeof palette));}
static void relocate_characters(unsigned base){
 for(unsigned i=0;i<32768;i++)characters[(base+i)&32767]=oldcharacters[i];
 memcpy(oldcharacters,characters,sizeof characters);map.character_address=base;
}
static void crops(void){
 const unsigned crops[][4]={{0,0,35,23},{247,249,27,31},{503,7,265,255},{0,0,768,512}};
 for(unsigned seed=0;seed<4;seed++){
  setup(seed);
  for(unsigned c=0;c<4;c++)for(unsigned step=1;step<=8;step*=2){
   unsigned x=crops[c][0],y=crops[c][1],w=crops[c][2],h=crops[c][3],dw=(w+step-1)/step,dh=(h+step-1)/step,pitch=dw+7;
   memset(canvas,0xa5,sizeof canvas);IogMapScenerySource before=map;
   CHECK(IogMapSceneryRender(&map,x,y,w,h,step,canvas,sizeof canvas,pitch*4));
   for(unsigned row=0;row<dh;row++){
    for(unsigned col=0;col<dw;col++)CHECK(canvas[row*pitch+col]==oracle(x+col*step,y+row*step));
    for(unsigned col=dw;col<pitch;col++)CHECK(canvas[row*pitch+col]==0xa5a5a5a5u);
   }
   for(unsigned n=dh*pitch;n<sizeof canvas/sizeof canvas[0];n++)CHECK(canvas[n]==0xa5a5a5a5u);
   CHECK(!memcmp(&map,&before,sizeof map));immutable();
  }
 }
 /* Character sheets can straddle the last VRAM word. Address wrapping must
  * preserve the same known planar pixels, independent of character base. */
 const unsigned bases[]={0x2000,0x7000,0x7fff};
 for(unsigned n=0;n<3;n++){
  setup(11);relocate_characters(bases[n]);
  CHECK(IogMapSceneryRender(&map,243,247,33,31,1,canvas,sizeof canvas,40*4));
  for(unsigned y=0;y<31;y++)for(unsigned x=0;x<33;x++)CHECK(canvas[y*40+x]==oracle(243+x,247+y));
  immutable();
 }
}
static void failures(void){
 setup(7);memset(canvas,0xa5,sizeof canvas);memcpy(oldcanvas,canvas,sizeof canvas);
 #define FAIL(s,x,y,w,h,step,buf,cap,pitch) do{CHECK(!IogMapSceneryRender(s,x,y,w,h,step,buf,cap,pitch));CHECK(!memcmp(canvas,oldcanvas,sizeof canvas));immutable();}while(0)
 FAIL(NULL,0,0,8,8,1,canvas,sizeof canvas,32);
 FAIL(&map,0,0,8,8,3,canvas,sizeof canvas,32);
 FAIL(&map,0,0,0,8,1,canvas,sizeof canvas,32);
 FAIL(&map,768,0,1,1,1,canvas,sizeof canvas,4);
 FAIL(&map,767,0,2,1,1,canvas,sizeof canvas,8);
 FAIL(&map,0,511,1,2,1,canvas,sizeof canvas,4);
 FAIL(&map,UINT_MAX,0,8,8,1,canvas,sizeof canvas,32);
 FAIL(&map,0,0,8,8,1,canvas,255,32);
 FAIL(&map,0,0,8,8,1,canvas,sizeof canvas,31);
 FAIL(&map,0,0,8,8,1,canvas,sizeof canvas,SIZE_MAX-3);
 FAIL(&map,0,0,8,8,1,NULL,sizeof canvas,32);
 IogMapScenerySource good=map;
 map.ram_bytes=0xa100;FAIL(&map,0,0,264,8,1,canvas,sizeof canvas,264*4);map=good; /* late invalid page */
 map.definitions_address=65535;FAIL(&map,0,0,8,8,1,canvas,sizeof canvas,32);map=good;
 map.map_address=UINT_MAX;FAIL(&map,0,0,8,8,1,canvas,sizeof canvas,32);map=good;
 map.width=767;FAIL(&map,0,0,8,8,1,canvas,sizeof canvas,32);map=good;
 map.height=4352;FAIL(&map,0,0,8,8,1,canvas,sizeof canvas,32);map=good;
 map.vram_words--;FAIL(&map,0,0,8,8,1,canvas,sizeof canvas,32);map=good;
 map.cgram_words--;FAIL(&map,0,0,8,8,1,canvas,sizeof canvas,32);map=good;
 map.character_address=32768;FAIL(&map,0,0,8,8,1,canvas,sizeof canvas,32);map=good;
 FAIL(&map,0,0,8,8,1,(uint32_t*)mapram,256,32);
 FAIL(&map,0,0,8,8,1,(uint32_t*)characters,256,32);
 FAIL(&map,0,0,8,8,1,(uint32_t*)palette,256,32);
 FAIL(&map,0,0,1,1,1,(uint32_t*)&map,sizeof map,4);CHECK(!memcmp(&map,&good,sizeof map));
 #undef FAIL
}
static void actual_ppu(void){
 g_snes=&machine;machine.ppu=&live;
 for(unsigned seed=0;seed<24;seed++){
  setup(seed);unsigned character_base=seed%2?0x7000:0;relocate_characters(character_base);
  memset(&source,0,sizeof source);ppu_reset(&source);
  memcpy(source.vram,characters,sizeof characters);memcpy(source.cgram,palette,sizeof palette);
  source.bgmode=1;source.screenEnabled[0]=1;source.inidisp=15;source.lastBrightnessMult=255;
  source.bgXsc[0]=0x61;source.bgTileAdr=(uint16_t)(character_base>>12);source.renderFlags=kPpuRenderFlags_NewRenderer;
  unsigned x=(seed*29)%512,y=(seed*11)%280;source.hScroll[0]=x&511;source.vScroll[0]=y&255;
  for(unsigned ty=y/8;ty<=(y+224)/8;ty++)for(unsigned tx=x/8;tx<=(x+255)/8;tx++){
   unsigned address=0x6000+(ty%32)*32+tx%32+(tx%64>=32?0x400:0);
   source.vram[address]=(uint16_t)oracle_tile(tx*8,ty*8);
  }
  memset(actual,0xa5,sizeof actual);source.renderBuffer=(uint8_t*)actual;source.renderPitch=256*4;
  const unsigned lines[]={1,8,16,112,224};
  for(unsigned n=0;n<5;n++){
   unsigned line=lines[n];PpuDrawDetachedLine(&source,(int)line);
   CHECK(IogMapSceneryRender(&map,x,y+line,256,1,1,canvas,sizeof canvas,256*4));
   for(unsigned col=0;col<256;col++){
    uint32_t want=actual[(line-1)*256+col]&0xffffff;
    if((canvas[col]&0xffffff)!=want){fprintf(stderr,"PPU seed=%u x=%u y=%u got=%08x want=%08x\n",seed,x+col,y+line,canvas[col],want);exit(2);}
    CHECK((canvas[col]&0xffffff)==want);
   }
  }
  immutable();cases++;
 }
}

static uint8_t secondary_ram[65536],secondary_before[65536];
static IogMapScenerySource second;
static void composite_setup(unsigned priority0,unsigned priority1,unsigned alpha){
 memset(mapram,0,sizeof mapram);memset(secondary_ram,0,sizeof secondary_ram);
 memset(characters,0,sizeof characters);memset(palette,0,sizeof palette);
 palette[17]=31;palette[33]=31<<5;
 unsigned tile0=1|(1<<10)|(priority0<<13),tile1=1|(2<<10)|(priority1<<13);
 for(unsigned n=0;n<4;n++){
  mapram[0x2000+n*2]=(uint8_t)tile0;mapram[0x2001+n*2]=(uint8_t)(tile0>>8);
  secondary_ram[0x2000+n*2]=(uint8_t)tile1;secondary_ram[0x2001+n*2]=(uint8_t)(tile1>>8);
 }
 for(unsigned y=0;y<8;y++){
  characters[16+y]=(alpha==1||alpha==3)?0:alpha==4?0xaa:0xff;
  characters[0x2000+16+y]=(alpha==2||alpha==3)?0:alpha==4?0x55:0xff;
 }
 map=(IogMapScenerySource){mapram,sizeof mapram,characters,palette,32768,256,256,256,0xa000,0x2000,0};
 second=(IogMapScenerySource){secondary_ram,sizeof secondary_ram,characters,palette,32768,256,256,256,0xa000,0x2000,0x2000};
 memcpy(oldram,mapram,sizeof mapram);memcpy(secondary_before,secondary_ram,sizeof secondary_ram);
 memcpy(oldcharacters,characters,sizeof characters);memcpy(oldpalette,palette,sizeof palette);
}
static void composite_immutable(void){immutable();CHECK(!memcmp(secondary_ram,secondary_before,sizeof secondary_ram));}
static void actual_composite_ppu(void){
 for(unsigned p0=0;p0<2;p0++)for(unsigned p1=0;p1<2;p1++)for(unsigned alpha=0;alpha<5;alpha++){
  composite_setup(p0,p1,alpha);memset(&source,0,sizeof source);ppu_reset(&source);
  memcpy(source.vram,characters,sizeof characters);memcpy(source.cgram,palette,sizeof palette);
  source.bgmode=1;source.screenEnabled[0]=3;source.inidisp=15;source.lastBrightnessMult=255;
  source.bgXsc[0]=0x60;source.bgXsc[1]=0x68;source.bgTileAdr=0x20;source.renderFlags=kPpuRenderFlags_NewRenderer;
  unsigned t0=1|(1<<10)|(p0<<13),t1=1|(2<<10)|(p1<<13);
  for(unsigned n=0;n<1024;n++){source.vram[0x6000+n]=(uint16_t)t0;source.vram[0x6800+n]=(uint16_t)t1;}
  memset(actual,0xa5,sizeof actual);source.renderBuffer=(uint8_t*)actual;source.renderPitch=256*4;
  for(unsigned physical=0;physical<2;physical++){
   const IogMapScenerySource *a=physical?&second:&map,*b=physical?&map:&second;
   const unsigned lines[]={1,8,16,112,224};
   for(unsigned n=0;n<5;n++){
    unsigned line=lines[n];PpuDrawDetachedLine(&source,(int)line);
    CHECK(IogMapSceneryRenderMode1Composite(a,b,physical,0,line,256,1,1,canvas,sizeof canvas,256*4));
    for(unsigned x=0;x<256;x++){
     uint32_t want=actual[(line-1)*256+x]&0xffffff;
     if((canvas[x]&0xffffff)!=want){fprintf(stderr,"composite PPU p0=%u p1=%u alpha=%u physical=%u x=%u got=%08x want=%08x\n",p0,p1,alpha,physical,x,canvas[x],want);exit(3);}
     CHECK((canvas[x]&0xffffff)==want);
     CHECK((canvas[x]>>24)==(alpha==3?0:255));
    }
   }
   composite_immutable();cases++;
  }
 }
}
static void composite_guards_and_finite(void){
 composite_setup(0,1,0);map.width=512;
 /* BG2 high wins inside its256px plate; beyond it only BG1 exists. */
 for(unsigned step=1;step<=8;step*=2){
  memset(canvas,0xa5,sizeof canvas);CHECK(IogMapSceneryRenderMode1Composite(&map,&second,0,250,250,20,6,step,canvas,sizeof canvas,128));
  unsigned w=(20+step-1)/step,h=(6+step-1)/step;
  for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++)CHECK(canvas[y*32+x]==(250+x*step<256?0xff00ff00u:0xffff0000u));
  for(unsigned y=0;y<h;y++)for(unsigned x=w;x<32;x++)CHECK(canvas[y*32+x]==0xa5a5a5a5u);
 }
 memset(canvas,0xa5,sizeof canvas);memcpy(oldcanvas,canvas,sizeof canvas);IogMapScenerySource good=second;
 #define CFAIL(a,b,physical,x,y,w,h,step,buf,cap,pitch) do{CHECK(!IogMapSceneryRenderMode1Composite(a,b,physical,x,y,w,h,step,buf,cap,pitch));CHECK(!memcmp(canvas,oldcanvas,sizeof canvas));composite_immutable();}while(0)
 CFAIL(&map,NULL,0,0,0,8,8,1,canvas,sizeof canvas,32);
 CFAIL(NULL,&second,0,0,0,8,8,1,canvas,sizeof canvas,32);
 CFAIL(&map,&second,2,0,0,8,8,1,canvas,sizeof canvas,32);
 CFAIL(&map,&second,0,UINT_MAX,0,8,8,1,canvas,sizeof canvas,32);
 CFAIL(&map,&second,0,0,0,8,8,3,canvas,sizeof canvas,32);
 CFAIL(&map,&second,0,0,0,8,8,1,canvas,255,32);
 CFAIL(&map,&second,0,0,0,8,8,1,canvas,sizeof canvas,SIZE_MAX-3);
 second.vram_words=0;CFAIL(&map,&second,0,300,0,8,8,1,canvas,sizeof canvas,32);second=good;
 second.width=512;second.ram_bytes=0xa100;CFAIL(&map,&second,0,0,0,264,8,1,canvas,sizeof canvas,264*4);second=good;
 second.definitions_address=65535;CFAIL(&map,&second,0,0,0,8,8,1,canvas,sizeof canvas,32);second=good;
 CFAIL(&map,&second,0,0,0,1,1,1,(uint32_t*)secondary_ram,sizeof secondary_ram,4);
 CFAIL(&map,&second,0,0,0,1,1,1,(uint32_t*)characters,sizeof characters,4);
 CFAIL(&map,&second,0,0,0,1,1,1,(uint32_t*)palette,sizeof palette,4);
 CFAIL(&map,&second,0,0,0,1,1,1,(uint32_t*)&second,sizeof second,4);
 #undef CFAIL
}
int main(void){crops();failures();actual_ppu();actual_composite_ppu();composite_guards_and_finite();printf("map scenery PASS %u assertions, %u actual PPU fixtures\n",checks,cases);return 0;}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='cc')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); out = args.out.resolve()
    if not out.is_relative_to((ROOT / '.local').resolve()):
        parser.error('Output must remain in ignored project .local/')
    out.mkdir(parents=True, exist_ok=True)
    inputs = [ROOT / 'src/iog_map_scenery.c', *[ROOT / 'snesrecomp/runner/src/snes' / name for name in ('ppu.c', 'ppu_legacy.c', 'hd_jobs.c')]]
    files = inputs + [ROOT/'src/iog_map_scenery.h', ROOT/'snesrecomp/runner/src/snes/ppu.h', ROOT/'scripts/test_iog_world_pixels.py', Path(__file__)]
    identities = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    base = runpy.run_path(str(ROOT / 'scripts/test_iog_world_pixels.py'))['HARNESS'].split('static void fixture(unsigned n)')[0]
    source = out / 'scenery.c'; source.write_text(base + BODY); exe = out / 'scenery.exe'
    command = [args.compiler, '-std=c11', '-O2', '-pthread', '-DSNESRECOMP_TRACE=1', '-DSNESRECOMP_REVERSE_DEBUG=0', '-DSNESRECOMP_INTERP_PROFILE=1', '-I'+str(ROOT/'src'), '-I'+str(ROOT/'snesrecomp/runner/src'), str(source), *map(str, inputs), '-o', str(exe)]
    build = subprocess.run(command, capture_output=True, text=True, timeout=120)
    (out/'build.log').write_text(build.stdout+build.stderr); build.check_returncode()
    env = {k:v for k,v in os.environ.items() if not k.startswith(('IOG_', 'SNESRECOMP_'))}
    result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=60)
    (out/'run.log').write_text(result.stdout+result.stderr); result.check_returncode()
    assert identities == {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, 'Test source changed during compilation/execution'
    (out/'receipt.json').write_text(json.dumps({'passed': True, 'command': command, 'stdout': result.stdout,
        'sources': identities, 'compiled_and_executed_source_identities_unchanged': True,
        'scope': 'Synthetic packed-map oracle and real SDK Mode1 4bpp PPU full-brightness single-layer and two-layer BG1hi/BG2hi/BG1lo/BG2lo priority pixels, both physical-primary orders. Crop/steps/alpha/flips/page boundaries/guards/immutability. No game, content integration, windows, color math, HDMA, sprites, animation, GPU or complete-zone qualification.'}, indent=2)+'\n')
    print(result.stdout.strip())


if __name__ == '__main__':
    main()
