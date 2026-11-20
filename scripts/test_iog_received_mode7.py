"""ROM-free received Mode7 lifecycle with actual detached PPU color rendering."""
from pathlib import Path
import argparse,hashlib,json,runpy,subprocess
ROOT=Path(__file__).resolve().parents[1]
BODY=r'''
#include "iog_received_mode7.c"
static uint8_t romdata[0x320000],wram[131072],saved_ram[131072];
static uint32_t host[600*336],field[384*224];
static bool accept_identity=true;
IogVisualStatus IogVisualReceivedVerify(const uint8_t *r,size_t size,IogVisualReceivedIdentity *id){
 memset(id,0,sizeof *id);if(!accept_identity||size!=sizeof romdata)return kIogVisualIdentityMismatch;
 id->rom=r;id->rom_size=size;return kIogVisualReady;
}
static void word(uint8_t *r,unsigned at,unsigned v){r[at]=(uint8_t)v;r[at+1]=(uint8_t)(v>>8);}
static void setup(void){
 memset(&m,0,sizeof m);memset(&source,0,sizeof source);ppu_reset(&source);
 source.bgmode=7;source.inidisp=15;source.lastBrightnessMult=255;source.mosaic=0;source.m7sel=0x80;
 source.screenEnabled[0]=0x15;source.screenWindowed[0]=0x15;
 source.m7matrix[0]=source.m7matrix[3]=256;
 for(unsigned n=0;n<32768;n++)source.vram[n]=(uint16_t)((n%255+1)<<8);
 for(unsigned n=0;n<256;n++)source.cgram[n]=(uint16_t)(n*113)&32767;
 memset(wram,0,sizeof wram);word(wram,0xB6,1019);word(wram,0xB8,177);
 word(romdata,0x1D835,23900);word(romdata,0x1D735,3217);
 for(unsigned n=0;n<384*224;n++)field[n]=0x123456u^(n*13);
 live_before=source;memcpy(saved_ram,wram,sizeof wram);
}
static void capture(bool perspective,int fault){
 CHECK(IogReceivedMode7Begin(&source,wram,romdata,sizeof romdata,598,336));
 for(int line=0;line<=224;line++){
  if(perspective){int16_t v[4];CHECK(IogMode7PerspectiveSample(&m.producer,line>223?223:line,v)==kIogMode7PerspectiveMatrix);memcpy(source.m7matrix,v,sizeof v);}
  if(fault==1&&line==100)source.m7matrix[0]++;
  IogReceivedMode7Capture(&source,wram,line);
 }
 CHECK(IogReceivedMode7End());
}
static void drawcheck(void){
 memset(host,0xa5,sizeof host);CHECK(IogReceivedMode7Draw((uint8_t*)host,600*4,(uint8_t*)field,598,336));
 for(unsigned y=0;y<224;y++)for(unsigned x=0;x<384;x++)CHECK(host[(y+56)*600+x+107]==field[y*384+x]);
 for(unsigned y=0;y<336;y++){CHECK(host[y*600+598]==0xa5a5a5a5);CHECK(host[y*600+599]==0xa5a5a5a5);}
 CHECK(!IogReceivedMode7Draw((uint8_t*)host,1,(uint8_t*)field,598,336));
 CHECK(!IogReceivedMode7Draw((uint8_t*)host,SIZE_MAX,(uint8_t*)field,598,336));
 CHECK(!IogReceivedMode7Draw(NULL,600*4,(uint8_t*)field,598,336));
 CHECK(!memcmp(wram,saved_ram,sizeof wram));
}
int main(void){
 setup();capture(false,0);CHECK(!m.perspective);CHECK(!memcmp(&source,&live_before,sizeof source));drawcheck();
 CHECK(m.output[56*598+171]!=0);setup();capture(true,0);CHECK(m.perspective);drawcheck();
 setup();source.inidisp=7;capture(true,0);CHECK(m.perspective);drawcheck();
 setup();capture(true,1);CHECK(!m.perspective);for(int x=0;x<598;x++)CHECK(m.output[x]==0);drawcheck();
 setup();source.windowsel=2;CHECK(!IogReceivedMode7Begin(&source,wram,romdata,sizeof romdata,598,336));
 setup();source.windowsel=0x20000;CHECK(!IogReceivedMode7Begin(&source,wram,romdata,sizeof romdata,598,336));
 setup();source.screenEnabled[1]=1;CHECK(!IogReceivedMode7Begin(&source,wram,romdata,sizeof romdata,598,336));
 setup();accept_identity=false;CHECK(!IogReceivedMode7Begin(&source,wram,romdata,sizeof romdata,598,336));accept_identity=true;
 setup();CHECK(IogReceivedMode7Begin(&source,wram,romdata,sizeof romdata,598,336));IogReceivedMode7Capture(&source,wram,0);CHECK(!IogReceivedMode7End());
 setup();CHECK(IogReceivedMode7Begin(&source,wram,romdata,sizeof romdata,598,336));source.vramWriteCount++;IogReceivedMode7Capture(&source,wram,0);CHECK(!m.valid);
 setup();CHECK(IogReceivedMode7Begin(&source,wram,romdata,sizeof romdata,598,336));wram[0xB6]++;IogReceivedMode7Capture(&source,wram,0);CHECK(!m.valid);
 setup();CHECK(IogReceivedMode7Begin(&source,wram,romdata,sizeof romdata,598,336));IogReceivedMode7Capture(&source,wram,1);CHECK(!m.valid);
 printf("%u received Mode7 assertions passed\n",checks);return 0;
}
'''

def main():
 p=argparse.ArgumentParser();p.add_argument('--compiler',default='clang');p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();assert out.is_relative_to((ROOT/'.local').resolve());out.mkdir(parents=True,exist_ok=False)
 base=runpy.run_path(str(ROOT/'scripts/test_iog_world_pixels.py'))['HARNESS'].split('static void fixture(unsigned n)')[0]
 src=out/'received-mode7.c';src.write_text(base+BODY);exe=out/'received-mode7.exe'
 inputs=[ROOT/'src/iog_world_pixels.c',*[ROOT/'snesrecomp/runner/src/snes'/n for n in ('ppu.c','ppu_legacy.c','hd_jobs.c')]]
 files=[ROOT/'src/iog_received_mode7.c',ROOT/'src/iog_received_mode7.h',ROOT/'src/iog_mode7_plane.h',ROOT/'src/iog_mode7_perspective.h',*inputs]
 before={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in files}
 cmd=[a.compiler,'-std=c11','-O1','-pthread','-DSNESRECOMP_TRACE=1','-DSNESRECOMP_INTERP_PROFILE=1','-DSNESRECOMP_REVERSE_DEBUG=0','-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),str(src),*map(str,inputs),'-o',str(exe)]
 r=subprocess.run(cmd,capture_output=True,text=True);(out/'build.log').write_text(r.stdout+r.stderr);r.check_returncode()
 r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=45);(out/'run.log').write_text(r.stdout+r.stderr);r.check_returncode()
 assert before=={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in files}
 (out/'receipt.json').write_text(json.dumps(dict(passed=True,stdout=r.stdout,sources=before,command=cmd,scope='Synthetic identity seam, actual PPU palette rendering, lifecycle/calibration/canaries/readonly. Runtime full-ROM identity and actual worldmap qualification are separate.'),indent=2));print(r.stdout)
if __name__=='__main__':main()
