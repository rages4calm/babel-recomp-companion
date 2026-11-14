#!/usr/bin/env python3
"""Offline pinned received-layout replay. All game inputs/exports stay private.

No game launch, ROM patch or native-dispatch activation. ROM-free refusals run
without --rom; exact classroom packets separately qualify bounded geometry.
"""
import argparse, hashlib, json, os, struct, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "iog_visual_objects.h"
#include "snes/ppu.h"
static unsigned char rom[0x320000],packet[200032],ram[131072],stage[544];
static IogVisualReceivedFrame out;
static Ppu ppu;
static void readfile(const char *path,void *dst,size_t n){FILE*f=fopen(path,"rb");if(!f||fread(dst,1,n,f)!=n||fgetc(f)!=EOF)exit(3);fclose(f);}
static void wr(unsigned a,unsigned v){ram[a]=v;ram[a+1]=v>>8;}
static void printpart(int screen,unsigned actor,unsigned order,int x,int y,unsigned w,unsigned attr,unsigned player,const uint8_t *indices){
 printf("{\"screen\":%d,\"actor\":%u,\"order\":%u,\"x\":%d,\"y\":%d,\"size\":%u,\"attr\":%u,\"player\":%u,\"indices\":\"",screen,actor,order,x,y,w,attr,player);
 for(unsigned i=0;i<w*w;i++)printf("%02x",indices[i]);puts("\"}");
}
#define CHECK(c)do{if(!(c)){fprintf(stderr,"line %d failed %s\n",__LINE__,#c);exit(4);}}while(0)
static void refusals(void){
 IogVisualReceivedIdentity id;memset(&id,0xa5,sizeof(id));
 CHECK(IogVisualReceivedVerify(rom,sizeof(rom),&id)==kIogVisualIdentityMismatch);
 CHECK(!id.rom&&!id.rom_size);
 CHECK(IogVisualReceivedVerify(rom,10,&id)==kIogVisualIdentityMismatch);
 CHECK(IogVisualReceivedVerify(NULL,10,&id)==kIogVisualInvalidInput);
 IogVisualReceivedSource s={ram,sizeof(ram),&ppu,&id,stage,stage,544,544,1,1,0};
 IogVisualViewport v={0,0,384,224};
 CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualIdentityMismatch&&!out.screen_count&&!out.world.part_count);
 CHECK(IogVisualReceivedBuild(NULL,&v,&out)==kIogVisualInvalidInput);
 /* Parser-only fixtures manufacture a cached identity; Verify above rejects
  * this zero ROM. They do not qualify/enable synthetic ROMs at runtime. */
 const char *pins[]={"dded02334752a7122d4db8da4df4aa56d6997c078065e69183865dc23202973f","70485bc087dd11937ebd8794a39b3c76638f135ea873b63bfda0639a943697ad","dec96c815acd857455134a3ce2210678cc98285a62b196d912ae7c352756faa6"};
 id.rom=rom;id.rom_size=sizeof(rom);
 for(unsigned i=0;i<3;i++)for(unsigned n=0;n<32;n++){unsigned byte;CHECK(sscanf(pins[i]+2*n,"%2x",&byte)==1);id.digests[i][n]=(uint8_t)byte;}
 wr(0x644,8);wr(0x6ee,0x1000);wr(0x13100,0xffff);wr(0xda,4);s.observed_direct_bytes=4;stage[512]=2;ppu.bgmode=1;
 CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualReady&&out.screen_count==1&&!out.world.part_count);
 wr(0xda,3);CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualMalformedSource&&!out.screen_count&&!out.world.part_count);
 wr(0xda,516);CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualMalformedSource);wr(0xda,4);
 stage[512]=3;CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualMalformedSource);stage[512]=2;
 stage[0]=1;CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualPublicationMismatch);stage[0]=0;
 s.observed_direct_bytes=0;CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualMalformedSource);s.observed_direct_bytes=4;
 wr(0x644,0xfe);CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualSourceUnqualified);
 puts("ROM-free received identity, direct count/highbits/prefix, source qualification and refusal checks passed");
}
int main(int argc,char**argv){
 if(argc==1){refusals();return 0;}
 if(argc!=3)return 2;
 readfile(argv[1],rom,sizeof(rom));readfile(argv[2],packet,sizeof(packet));
 CHECK(packet[4]==3);
 memcpy(ppu.vram,packet+133976,65536);memcpy(ppu.cgram,packet+199512,512);
 ppu.obsel=packet[200024];ppu.bgmode=packet[200025];ppu.setini=packet[200026];
 memcpy(ram,packet+24,sizeof(ram));memcpy(stage,packet+131096,544);
 IogVisualReceivedIdentity id;CHECK(IogVisualReceivedVerify(rom,sizeof(rom),&id)==kIogVisualReady);
 unsigned char oldram[131072];Ppu oldppu;memcpy(oldram,ram,sizeof(ram));memcpy(&oldppu,&ppu,sizeof(ppu));
 IogVisualReceivedSource s={ram,sizeof(ram),&ppu,&id,stage,packet+133432,544,544,1,1,(uint16_t)(ram[0xda]|ram[0xdb]<<8)};
 IogVisualViewport v={(int16_t)(ram[0x68a]|ram[0x68b]<<8)-64,(int16_t)(ram[0x68e]|ram[0x68f]<<8),384,224};
 CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualReady);
 CHECK(!memcmp(oldram,ram,sizeof(ram))&&!memcmp(&oldppu,&ppu,sizeof(ppu)));
 for(unsigned i=0;i<out.screen_count;i++){IogVisualScreenPart*p=&out.screen[i];printpart(1,0,p->order,p->x,p->y,p->width,p->tile_attributes,0,p->indices);}
 for(unsigned i=0;i<out.world.part_count;i++){IogVisualPart*p=&out.world.parts[i];printpart(0,p->actor,p->order,p->x-64,p->y,p->width,p->tile_attributes,p->player,p->indices);}
 /* Faults must refuse without accepting a partial screen/world list. */
 uint8_t old=stage[543];stage[543]^=1;CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualPublicationMismatch);stage[543]=old;
 s.publication_epoch=2;CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualPublicationMismatch);s.publication_epoch=1;
 id.digests[1][0]^=1;CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualIdentityMismatch);id.digests[1][0]^=1;
 id.digests[2][31]^=1;CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualIdentityMismatch);id.digests[2][31]^=1;
 s.observed_direct_bytes+=4;CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualMalformedSource);s.observed_direct_bytes-=4;
 wr(0xda,3);CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualMalformedSource);wr(0xda,s.observed_direct_bytes);
 uint8_t h=stage[512];stage[512]^=1;unsigned char pub[544];memcpy(pub,stage,544);s.published=pub;
 CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualMalformedSource);stage[512]=h;s.published=packet+133432;
 wr(0x644,0xfe);CHECK(IogVisualReceivedBuild(&s,&v,&out)==kIogVisualSourceUnqualified);
 return 0;
}
'''

def planar(vram,obsel,x,y,tile,size,attr):
    """Decode published hardware OAM independently of the host data adapter."""
    words=struct.unpack('<32768H',vram);result=[]
    base=(obsel&7)*8192+(((obsel&24)+8)*512 if tile&256 else 0)
    palette=128+((attr>>1)&7)*16
    for dy in range(size):
        for dx in range(size):
            u=size-1-dx if attr&64 else dx;v=size-1-dy if attr&128 else dy
            character=(((tile&255)//16+v//8)*16+((tile%16+u//8)%16))
            at=(base+character*16+v%8)&32767;lo=words[at];hi=words[(at+8)&32767];bit=7-u%8
            color=sum(((p>>bit)&1)<<k for k,p in enumerate((lo&255,lo>>8,hi&255,hi>>8)))
            result.append(palette+color if color else 0)
    return bytes(result)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',default='cc');p.add_argument('--out',type=Path,default=ROOT/'.local/received-visual-tests');p.add_argument('--rom',type=Path);p.add_argument('--captures',type=Path,action='append',default=[]);a=p.parse_args()
    out=a.out.resolve()
    if not out.is_relative_to((ROOT/'.local').resolve()):p.error('output must stay under ignored .local')
    out.mkdir(parents=True,exist_ok=True);c=out/'probe.c';c.write_text(HARNESS);exe=out/'probe.exe'
    cmd=[a.compiler,'-std=c11','-O1','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),str(c),str(ROOT/'src/iog_visual_objects.c'),str(ROOT/'snesrecomp/runner/src/sha256.c'),'-o',str(exe)]
    build=subprocess.run(cmd,capture_output=True,text=True);(out/'build.log').write_text(build.stdout+build.stderr);build.check_returncode()
    env={k:v for k,v in os.environ.items()if not k.startswith(('IOG_','SNESRECOMP_'))}
    run=subprocess.run([str(exe)],env=env,capture_output=True,text=True);(out/'unit.log').write_text(run.stdout+run.stderr);run.check_returncode()
    results=[]
    for cap in a.captures:
        assert a.rom and cap.resolve().is_relative_to((ROOT/'.local').resolve())
        phase=cap/'phase'
        for packet in sorted(phase.glob('received-packet-*.bin')):
            r=subprocess.run([str(exe),str(a.rom.resolve()),str(packet.resolve())],env=env,capture_output=True,text=True)
            target=out/(cap.name+'-'+packet.stem+'.jsonl');target.write_text(r.stdout);(target.with_suffix('.log')).write_text(r.stderr);r.check_returncode()
            parts=[json.loads(s)for s in r.stdout.splitlines()];data=packet.read_bytes();assert len(data)==200032 and struct.unpack_from('<I',data,4)[0]==3;vram=data[133976:199512];cgram=struct.unpack('<256H',data[199512:200024]);obsel=data[200024];oam=data[133432:133976];actual=[]
            for n in range(128):
                x,y,t,attr=oam[n*4:n*4+4];high=(oam[512+n//4]>>(n%4*2))&3;x-=512 if high&1 else 0;size=16 if high&2 else 8
                if y>=224:continue
                actual.append(dict(slot=n,x=x,y=y,size=size,attr=attr,tile=t+(attr&1)*256,indices=planar(vram,obsel,x,y,t+(attr&1)*256,size,attr)))
            predicted=[q for q in parts if q['x']+q['size']>0 and q['x']<256 and q['y']+q['size']>0 and q['y']<224]
            rows=[]
            for got,want in zip(predicted,actual):
                geometry=(got['x'],got['y'],got['size'])==(want['x'],want['y'],want['size']);attrs=(got['attr']>>9)==(want['attr']>>1)
                indices=bytes.fromhex(got['indices']);index_match=indices==want['indices']
                colors=lambda idx:[(0x8000|(cgram[i]&32767))if i else 0 for i in idx]
                rows.append(dict(actor=got['actor'],slot=want['slot'],geometry=geometry,attributes=attrs,indices_match=index_match,nmi_palette_colors_match=colors(indices)==colors(want['indices']),player=got['player']))
            result=dict(capture=cap.name,packet=packet.name,parts=len(parts),native_predicted=len(predicted),published_visible=len(actual),count_match=len(predicted)==len(actual),rows=rows)
            results.append(result)
    passed=all(r['count_match'] and all(x['geometry'] and x['attributes'] and x['indices_match'] and x['nmi_palette_colors_match'] for x in r['rows'])for r in results)
    receipt=dict(passed=passed,rom_free_passed=True,packets=results,scope='bounded offline scene08 adapter; exact same-NMI post-publication VRAM/CGRAM, not raster palette or campaign proof',sources={x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest()for x in ['src/iog_visual_objects.c','src/iog_visual_objects.h','scripts/test_iog_received_visual.py']})
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(rom_free_passed=True,packets=len(results),counts_passed=sum(r['count_match']for r in results),geometry_bad=sum(not x['geometry']for r in results for x in r['rows']),attrs_bad=sum(not x['attributes']for r in results for x in r['rows']),pixels_bad=sum(not x['indices_match']for r in results for x in r['rows']))))
    assert passed,'Published geometry/order/attributes/graphics mismatch; inspect failed receipt'
if __name__=='__main__':main()
