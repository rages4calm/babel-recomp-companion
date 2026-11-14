"""Pure source-driven raster parallax tests and optional captured-packet calibration."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BODY=r'''
#include "iog_raster_parallax.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned checks;
static uint8_t rom[2097152],ram[65536],before_rom[2097152],before_ram[65536];
static uint16_t captured[225],before_captured[225];
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);exit(2);}}while(0)
static void word(uint8_t*p,unsigned at,unsigned v){p[at]=(uint8_t)v;p[at+1]=(uint8_t)(v>>8);}
static void snapshot(void){memcpy(before_rom,rom,sizeof rom);memcpy(before_ram,ram,sizeof ram);memcpy(before_captured,captured,sizeof captured);}
static void immutable(void){CHECK(!memcmp(before_rom,rom,sizeof rom));CHECK(!memcmp(before_ram,ram,sizeof ram));CHECK(!memcmp(before_captured,captured,sizeof captured));}
static void fixture(unsigned previous){
 memset(rom,0,sizeof rom);memset(ram,0,sizeof ram);
 word(rom,0x1cc02,0x8000);word(rom,0x18000,0x7800);rom[0x18002]=0x7e;rom[0x18003]=0x0f;rom[0x18004]=8;
 word(ram,0x644,0x1a);word(ram,0x694,512);word(ram,0x698,256);word(ram,0x68a,160);word(ram,0x6e4,8);
 const unsigned heights[]={32,32,32,200},addresses[]={0x720,0x722,0x724,0x726},speeds[]={24,32,40,45},phases[]={0x1a3f,0x2237,0x0ff9,1005};
 for(unsigned i=0;i<4;i++){
  unsigned at=0x18005+i*8;word(rom,at,65536-heights[i]);word(rom,at+2,addresses[i]);word(rom,at+4,i==3?0x020c:0);word(rom,at+6,speeds[i]);
  word(ram,addresses[i],phases[i]);
 }
 for(unsigned line=0;line<225;line++){
  unsigned i=line<32?0:line<64?1:line<96?2:3;
  unsigned phase=phases[i];if(previous)phase-=i==3?48:speeds[i]+8;
  captured[line]=(uint16_t)(((phase&65535)>>4)&1023);
 }
 snapshot();
}
static void current_and_previous(void){
 for(unsigned previous=0;previous<2;previous++){
  fixture(previous);IogRasterParallax model;
  CHECK(IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,&model));
  CHECK(model.previous_buffer==previous&&model.band_count==4&&model.source_camera_x==160);
  for(unsigned row=0;row<225;row++){
   uint16_t h=777;CHECK(IogRasterParallaxSample(&model,(int)row,160,&h));CHECK(h==captured[row]);
  }
  uint16_t h=777;
  CHECK(IogRasterParallaxSample(&model,0,161,&h));CHECK(h==(previous?418:420)); /* fraction F carries */
  CHECK(IogRasterParallaxSample(&model,100,161,&h));CHECK(h==(previous?60:63));
  CHECK(IogRasterParallaxSample(&model,100,-1,&h));CHECK(h==(previous?1023:2));
  CHECK(IogRasterParallaxSample(&model,255,0,&h));
  h=777;CHECK(!IogRasterParallaxSample(&model,256,160,&h)&&h==777);
  CHECK(!IogRasterParallaxSample(&model,-1,160,&h)&&h==777);
  CHECK(!IogRasterParallaxSample(&model,0,-2049,&h)&&h==777);
  CHECK(!IogRasterParallaxSample(&model,0,4097,&h)&&h==777);
  CHECK(!IogRasterParallaxSample(&model,0,160,NULL));
  immutable();
 }
}
static void fail_prepare(void){
 fixture(0);IogRasterParallax out,before;memset(&out,0xa5,sizeof out);before=out;
 CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,false,ram,sizeof ram,captured,225,&out));CHECK(!memcmp(&out,&before,sizeof out));
 captured[78]^=1;CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,&out));CHECK(!memcmp(&out,&before,sizeof out));captured[78]^=1;
 CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,224,&out));
 CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,65535,captured,225,&out));
 CHECK(!IogRasterParallaxPrepare(rom,sizeof rom-1,true,ram,sizeof ram,captured,225,&out));
 CHECK(!IogRasterParallaxPrepare(NULL,sizeof rom,true,ram,sizeof ram,captured,225,&out));
 CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,NULL));
 CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,(IogRasterParallax*)ram));
 CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,(IogRasterParallax*)rom));
 CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,(IogRasterParallax*)captured));
 const unsigned locations[]={0x644,0x694,0x698,0x690,0x6ee,0x6ef};
 for(unsigned i=0;i<6;i++){
  fixture(0);word(ram,locations[i],i==4?128:i==5?8:1);snapshot();
  CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,&out));CHECK(!memcmp(&out,&before,sizeof out));immutable();
 }
 fixture(0);rom[0x18003]|=128;snapshot();CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,&out));immutable();
 fixture(0);word(rom,0x18005+4,0x000c);snapshot();CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,&out));immutable();
 fixture(0);word(rom,0x18005+2,0x7fff);snapshot();CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,&out));immutable();
 fixture(0);word(ram,0x726,1006);snapshot();CHECK(!IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,&out));immutable();
}
static void fixed_wrap(void){
 fixture(0);word(ram,0x720,0xfff8);for(unsigned i=0;i<32;i++)captured[i]=1023;snapshot();
 IogRasterParallax model;CHECK(IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,&model));
 uint16_t h;CHECK(IogRasterParallaxSample(&model,0,160,&h)&&h==1023);
 CHECK(IogRasterParallaxSample(&model,0,168,&h)&&h==0);immutable();
}
static void load(const char*name,void*out,size_t n){FILE*f=fopen(name,"rb");CHECK(f);CHECK(fread(out,1,n,f)==n);CHECK(fgetc(f)==EOF);CHECK(!fclose(f));}
int main(int argc,char**argv){
 if(argc==5){
  load(argv[1],rom,sizeof rom);load(argv[2],ram,sizeof ram);load(argv[3],captured,sizeof captured);snapshot();
  IogRasterParallax model;bool ok=IogRasterParallaxPrepare(rom,sizeof rom,true,ram,sizeof ram,captured,225,&model);
  FILE*f=fopen(argv[4],"wb");CHECK(f);fprintf(f,"{\"passed\":%s",ok?"true":"false");
  if(ok)fprintf(f,",\"scene\":%u,\"source_camera_x\":%u,\"bands\":%u,\"previous_buffer\":%u",model.scene,model.source_camera_x,model.band_count,model.previous_buffer);
  fprintf(f,"}\n");CHECK(!fclose(f));immutable();return ok?0:3;
 }
 CHECK(argc==1);current_and_previous();fail_prepare();fixed_wrap();printf("raster parallax PASS %u assertions\n",checks);return 0;
}
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler',default='cc');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--packet',type=Path,action='append',default=[])
    p.add_argument('--rom',type=Path)
    a=p.parse_args();out=a.out.resolve()
    if not out.is_relative_to((ROOT/'.local').resolve()):p.error('Output must remain private under .local/')
    out.mkdir(parents=True,exist_ok=True)
    files=[ROOT/'src/iog_raster_parallax.c',ROOT/'src/iog_raster_parallax.h',Path(__file__)]
    sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
    before={str(f.relative_to(ROOT)):sha(f)for f in files}
    source=out/'raster.c';source.write_text(BODY);exe=out/'raster.exe'
    cmd=[a.compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),str(source),str(files[0]),'-o',str(exe)]
    build=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/'build.log').write_text(build.stdout+build.stderr);build.check_returncode()
    env={k:v for k,v in os.environ.items()if not k.startswith(('IOG_','SNESRECOMP_'))}
    run=subprocess.run([str(exe)],env=env,capture_output=True,text=True,timeout=60);(out/'run.log').write_text(run.stdout+run.stderr);run.check_returncode()
    # The fault preserves native integer scroll but discards the fractional
    # phase before host-camera correction; the targeted carry test must fail.
    mutant=out/'without-fraction.c';text=files[0].read_text();needle='unsigned phase=b->fixed_phase;';assert text.count(needle)==1
    mutant.write_text(text.replace(needle,'unsigned phase=b->fixed_phase&~15u;'))
    mutant_exe=out/'without-fraction.exe';mutant_cmd=cmd.copy();mutant_cmd[mutant_cmd.index(str(files[0]))]=str(mutant);mutant_cmd[-1]=str(mutant_exe)
    fault_build=subprocess.run(mutant_cmd,capture_output=True,text=True,timeout=60);(out/'fraction-fault-build.log').write_text(fault_build.stdout+fault_build.stderr);fault_build.check_returncode()
    fault=subprocess.run([str(mutant_exe)],env=env,capture_output=True,text=True,timeout=60);(out/'fraction-fault-run.log').write_text(fault.stdout+fault.stderr)
    assert fault.returncode!=0 and 'previous?418:420' in fault.stderr
    packet_results=[]
    if a.packet:
        if not a.rom or sha(a.rom)!='32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd':p.error('Verified bare Original-USA ROM required for captured calibration')
    for n,prefix in enumerate(a.packet):
        prefix=prefix.resolve();meta=json.loads(Path(str(prefix)+'.source.json').read_text());epochs=Path(str(prefix)+'.epochs.bin').read_bytes()
        first=meta['lines'][1]['epoch'];ram=epochs[first*131584+66048:(first+1)*131584];assert len(ram)==65536
        scroll=b''.join(bytes.fromhex(row['regs'])[16:18]for row in meta['lines']);assert len(scroll)==450
        rp=out/f'packet{n}-epoch-ram.bin';hp=out/f'packet{n}-scroll.bin';jp=out/f'packet{n}.json';rp.write_bytes(ram);hp.write_bytes(scroll)
        actual=subprocess.run([str(exe),str(a.rom.resolve()),str(rp),str(hp),str(jp)],env=env,capture_output=True,text=True,timeout=30)
        (out/f'packet{n}.log').write_text(actual.stdout+actual.stderr);result=json.loads(jp.read_text());result.update(packet=str(prefix),exit_code=actual.returncode,source_sha256=sha(Path(str(prefix)+'.source.json')));packet_results.append(result)
    assert before=={str(f.relative_to(ROOT)):sha(f)for f in files}
    packets_passed=all(row['passed']for row in packet_results)
    receipt={'passed':packets_passed,'synthetic_tests_passed':True,'fraction_discard_fault_rejected':True,'command':cmd,'stdout':run.stdout,'sources':before,'packet_calibrations':packet_results,'all_requested_packet_calibrations_passed':packets_passed,'scope':'Pure ROM-driven producer calibration and synthetic fraction/phase/guards/read-only tests. Optional captured rows are readonly bounded calibration, not game motion, GPU or full-zone approval.'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(run.stdout.strip());print(json.dumps(packet_results,indent=2))
    if not packets_passed:raise SystemExit(1)


if __name__=='__main__':main()
