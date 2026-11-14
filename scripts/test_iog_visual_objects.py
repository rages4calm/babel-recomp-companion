#!/usr/bin/env python3
"""ROM-free execution of the read-only stock visual-record decoder.

Synthetic sources test format/order/coordinate/pixel rules and refusal. Private
stock captures separately qualify original producer records; no game data is
embedded here and this is not full room/combat or GPU acceptance.
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
#include "iog_visual_objects.h"
#include "snes/ppu.h"
static uint8_t ram[0x20000],rom[0x200000],oldram[0x20000],oldrom[0x200000];
static Ppu ppu,oldppu;
static IogVisualFrame frame;
static unsigned checks;
#define CHECK(c) do {checks++;if(!(c)){fprintf(stderr,"line%d: %s\n",__LINE__,#c);exit(1);}}while(0)
static void wr(unsigned at,unsigned v){ram[at]=(uint8_t)v;ram[at+1]=(uint8_t)(v>>8);}
static void actor(unsigned a,unsigned prev,unsigned next,unsigned x,unsigned y,unsigned flags,unsigned meta){
    wr(a+4,prev);wr(a+6,next);wr(a+0x14,x);wr(a+0x16,y);wr(a+0x10,flags);
    ram[0x10000+a+8]=0x7e;wr(0x10000+a+0xc,meta);wr(a+0x28,42);
}
static void record(unsigned meta,unsigned n,unsigned size,unsigned x0,unsigned x1,unsigned y0,unsigned y1,unsigned attr){
    unsigned at=meta+9+n*7;ram[at]=size;ram[at+1]=x0;ram[at+2]=x1;
    ram[at+3]=y0;ram[at+4]=y1;wr(at+5,attr);
}
static void fixture(void){
    memset(ram,0,sizeof(ram));memset(rom,0,sizeof(rom));memset(&ppu,0,sizeof(ppu));
    ppu.bgmode=1;ppu.obsel=2;wr(0x644,1);wr(0x56,0x1000);wr(0x58,0x1000);wr(0x13100,0xffff);
    actor(0x1000,0,0,600,400,0,0x4000);ram[0x4008]=1;record(0x4000,0,0,0,0,0,0,0x3802);
    for(unsigned i=0;i<256;i++)ppu.cgram[i]=(uint16_t)i;
    for(unsigned y=0;y<8;y++){ppu.vram[0x4020+y]=0x0080;ppu.vram[0x4028+y]=0;}
}
static IogVisualSource src(void){IogVisualSource s={ram,sizeof(ram),rom,sizeof(rom),&ppu,true};return s;}
static IogVisualStatus run(IogVisualViewport v){
    IogVisualSource s=src();memcpy(oldram,ram,sizeof(ram));memcpy(oldrom,rom,sizeof(rom));memcpy(&oldppu,&ppu,sizeof(ppu));
    IogVisualStatus z=IogVisualObjectsBuild(&s,&v,&frame);
    CHECK(!memcmp(oldram,ram,sizeof(ram))&&!memcmp(oldrom,rom,sizeof(rom))&&!memcmp(&oldppu,&ppu,sizeof(ppu)));
    CHECK(frame.status==z);if(z!=kIogVisualReady)CHECK(frame.part_count==0);return z;
}
static void geometry_and_pixels(void){
    fixture();IogVisualViewport v={500,300,600,336};
    CHECK(run(v)==kIogVisualReady&&frame.actor_count==1&&frame.part_count==1);
    IogVisualPart p=frame.parts[0];CHECK(p.world_x==600&&p.world_y==399&&p.x==100&&p.y==99);
    CHECK(p.actor==0x1000&&p.animation==42&&p.order==1&&p.width==8&&p.height==8);
    CHECK(p.palette==4&&p.math==1&&p.priority==3&&!p.manual&&!p.player);
    CHECK(p.pixels[0]==(0x8000|193)&&p.pixels[1]==0&&p.pixels[56]==(0x8000|193));
    CHECK(p.indices[0]==193&&p.indices[1]==0&&p.indices[56]==193);
    wr(0x1018,2);wr(0x101a,3);wr(0x100e,0xc000);record(0x4000,0,0,1,5,2,6,0x3802);
    CHECK(run(v)==kIogVisualReady);p=frame.parts[0];
    CHECK(p.world_x==603&&p.world_y==402&&p.hflip&&p.vflip);
    CHECK(p.pixels[7]==(0x8000|193)&&p.pixels[0]==0);
    wr(0x1010,0x80);wr(0x11028,1);CHECK(run(v)==kIogVisualReady&&frame.parts[0].palette==7);
    wr(0x1010,0x90);CHECK(run(v)==kIogVisualReady&&frame.parts[0].palette==4);
    fixture();wr(0x1014,0xfffc);v.world_x=-10;v.world_y=300;
    CHECK(run(v)==kIogVisualReady&&frame.parts[0].world_x==-4&&frame.parts[0].x==6);
    fixture();wr(0x68a,0xffff);wr(0x68e,0xffff);wr(0x1014,1);wr(0x1016,1);
    v=(IogVisualViewport){-1,-1,256,224};
    CHECK(run(v)==kIogVisualReady&&frame.part_count==1);
    CHECK(frame.parts[0].world_x==1&&frame.parts[0].world_y==0);
    CHECK(frame.parts[0].x==2&&frame.parts[0].y==1);
    wr(0x13100,10);wr(0x13102,0xffff);wr(0x13104,0x3802);wr(0x13106,0xffff);
    CHECK(run(v)==kIogVisualReady&&frame.part_count==2);
    CHECK(frame.parts[0].manual&&frame.parts[0].world_y==-1&&frame.parts[0].y==0);
    fixture();wr(0x1014,0xfffc);v=(IogVisualViewport){-10,300,600,336};
    v.world_x=INT32_MIN;CHECK(run(v)==kIogVisualReady&&frame.part_count==0&&frame.outside_parts==1);
    v.world_x=500;v.width=4096;v.height=512;CHECK(run(v)==kIogVisualReady);
    v.width=4097;CHECK(run(v)==kIogVisualInvalidInput);v.width=600;v.height=513;CHECK(run(v)==kIogVisualInvalidInput);
    fixture();v=(IogVisualViewport){500,300,600,336};
    /* A16x16 generic object wraps horizontal character index within its row. */
    record(0x4000,0,1,0,0,0,0,0x380f);
    ppu.vram[0x40f0]=0x0080;ppu.vram[0x4000]=0x8000;ppu.vram[0x41f0]=0x0080;
    CHECK(run(v)==kIogVisualReady&&frame.parts[0].width==16);
    CHECK(frame.parts[0].pixels[0]==(0x8000|193));
    CHECK(frame.parts[0].pixels[8]==(0x8000|194));
    CHECK(frame.parts[0].pixels[128]==(0x8000|193));
    ppu.cgram[193]=0;CHECK(run(v)==kIogVisualReady&&frame.parts[0].pixels[0]==0x8000);
}
static void orders_and_manual(void){
    fixture();IogVisualViewport v={0,0,1000,512};
    actor(0x1030,0x1000,0,600,400,0,0x4000);wr(0x1006,0x1030);wr(0x58,0x1030);
    CHECK(run(v)==kIogVisualReady&&frame.part_count==2);
    CHECK(frame.parts[0].actor==0x1000&&frame.parts[1].actor==0x1030); /* equal-key tie */
    wr(0x1030+0x16,200);CHECK(run(v)==kIogVisualReady&&frame.parts[0].actor==0x1000); /*400 clamps front*/
    wr(0x1016,100);CHECK(run(v)==kIogVisualReady&&frame.parts[0].actor==0x1030);
    wr(0x1010,3);CHECK(run(v)==kIogVisualReady&&frame.parts[0].actor==0x1000); /*front wins*/
    wr(0x1010,1);CHECK(run(v)==kIogVisualReady&&frame.parts[0].actor==0x1030);
    wr(0x1030+0x10,0x2000);CHECK(run(v)==kIogVisualReady&&frame.part_count==1&&frame.hidden_actors==1);
    wr(0x13100,610);wr(0x13102,410);wr(0x13104,0x3802);wr(0x13106,0xffff);
    wr(0xd8,0);CHECK(run(v)==kIogVisualReady&&frame.part_count==2&&frame.parts[0].manual);
    CHECK(frame.parts[0].world_y==410&&frame.parts[1].order==2); /* noactorY-1manual */
    for(unsigned n=0;n<128;n++){wr(0x13100+n*6,0);wr(0x13102+n*6,600);}
    CHECK(run(v)==kIogVisualCapacity); /* no terminator, even if every record clipped */
}
static void all_planar_colors(void){
    fixture();IogVisualViewport v={500,300,600,336};
    for(unsigned bank=0;bank<2;bank++)for(unsigned tile=0;tile<32;tile++)for(unsigned y=0;y<8;y++){
        unsigned planes[4]={0,0,0,0};
        for(unsigned x=0;x<8;x++){
            unsigned color=(tile+3*y+5*x)&15;
            for(unsigned b=0;b<4;b++)planes[b]|=((color>>b)&1)<<(7-x);
        }
        unsigned at=(bank?0x5000:0x4000)+tile*16+y;
        ppu.vram[at]=(uint16_t)(planes[0]|planes[1]<<8);
        ppu.vram[at+8]=(uint16_t)(planes[2]|planes[3]<<8);
    }
    for(unsigned size=8;size<=16;size+=8)for(unsigned bank=0;bank<2;bank++)
    for(unsigned flip=0;flip<4;flip++)for(unsigned pal=0;pal<8;pal++){
        unsigned attr=0x3002|bank*256|pal*512|((flip&1)?0x4000:0)|((flip&2)?0x8000:0);
        record(0x4000,0,size==16,0,0,0,0,attr);
        CHECK(run(v)==kIogVisualReady&&frame.part_count==1);
        IogVisualPart *p=&frame.parts[0];
        for(unsigned y=0;y<size;y++)for(unsigned x=0;x<size;x++){
            unsigned sx=flip&1?size-1-x:x,sy=flip&2?size-1-y:y;
            unsigned tile=2+(sy/8)*16+sx/8;
            unsigned color=(tile+3*(sy%8)+5*(sx%8))&15;
            unsigned index=color?128+pal*16+color:0;
            CHECK(p->indices[y*size+x]==index);
            CHECK(p->pixels[y*size+x]==(color?(0x8000|index):0));
        }
    }
}
static void player_rom_pixels(void){
    fixture();IogVisualViewport v={500,300,600,336};wr(0x1010,0x8000);
    for(unsigned form=0;form<9;form++){
        unsigned base=0x1d974+form*6;rom[base]=0;rom[base+1]=0x80;rom[base+2]=0x9a;
    }
    record(0x4000,0,1,0,0,0,0,0x3802);
    rom[0x1a8040]=0x80;rom[0x1a8061]=0x80;rom[0x1a8240]=0x80;
    memset(ppu.vram,0,sizeof(ppu.vram)); /* notresident: mustreadrealROMcharacters */
    for(unsigned form=0;form<3;form++){
        wr(0xad4,form);CHECK(run(v)==kIogVisualReady&&frame.parts[0].player);
        CHECK(frame.parts[0].pixels[0]==(0x8000|193)&&frame.parts[0].pixels[8]==(0x8000|194));
        CHECK(frame.parts[0].pixels[128]==(0x8000|193));
    }
    wr(0xad4,3);CHECK(run(v)==kIogVisualUnsupportedFormat);
    wr(0x9ae,0x8000);
    for(unsigned body=0;body<9;body++){
        wr(0x1100e,body*6);CHECK(run(v)==kIogVisualReady&&frame.parts[0].player);
        CHECK(frame.parts[0].pixels[0]==(0x8000|193)&&frame.parts[0].pixels[8]==(0x8000|194));
    }
    wr(0x1100e,54);CHECK(run(v)==kIogVisualUnsupportedFormat);
    wr(0x1100e,0xffff);CHECK(run(v)==kIogVisualUnsupportedFormat);
    wr(0x1100e,7);CHECK(run(v)==kIogVisualUnsupportedFormat);
    /* Fixedsourcebank with16bitDMAaddresswrap, notbankcarry. */
    wr(0x1100e,0);rom[0x1d974]=0xf0;rom[0x1d975]=0xff;
    rom[0x1a0030]=0x80;record(0x4000,0,0,0,0,0,0,0x3802);
    CHECK(run(v)==kIogVisualMalformedSource); /* mirror9A:0030 isnotROM */
}
static void refusals_and_capacity(void){
    fixture();IogVisualViewport v={0,0,1000,512};IogVisualSource s=src();
    CHECK(IogVisualObjectsBuild(NULL,&v,&frame)==kIogVisualInvalidInput);
    CHECK(IogVisualObjectsBuild(&s,NULL,&frame)==kIogVisualInvalidInput);
    CHECK(IogVisualObjectsBuild(&s,&v,NULL)==kIogVisualInvalidInput);
    s.stock_identity_verified=false;CHECK(IogVisualObjectsBuild(&s,&v,&frame)==kIogVisualUnsupportedFormat);
    s=src();s.ram_size--;CHECK(IogVisualObjectsBuild(&s,&v,&frame)==kIogVisualInvalidInput);
    s=src();s.rom_size--;CHECK(IogVisualObjectsBuild(&s,&v,&frame)==kIogVisualInvalidInput);
    s=src();CHECK(IogVisualObjectsBuild(&s,&v,(IogVisualFrame*)ram)==kIogVisualInvalidInput);
    wr(0x644,9);CHECK(run(v)==kIogVisualUnsupportedScene);wr(0x644,12);CHECK(run(v)==kIogVisualReady);
    ppu.obsel|=0x20;CHECK(run(v)==kIogVisualUnsupportedFormat);ppu.obsel=2;
    ppu.setini=2;CHECK(run(v)==kIogVisualUnsupportedFormat);ppu.setini=0;
    wr(0x6ee,0x1000);CHECK(run(v)==kIogVisualUnsupportedFormat);wr(0x6ee,0);
    wr(0x58,0x1030);CHECK(run(v)==kIogVisualMalformedSource);wr(0x58,0x1000);
    wr(0x1006,0x1000);CHECK(run(v)==kIogVisualMalformedSource);wr(0x1006,0);
    wr(0x1004,0x1030);CHECK(run(v)==kIogVisualMalformedSource);wr(0x1004,0);
    ram[0x11008]=0;CHECK(run(v)==kIogVisualMalformedSource);ram[0x11008]=0x7e;
    ram[0x4008]=0;CHECK(run(v)==kIogVisualMalformedSource);
    fixture();ram[0x4008]=7;for(unsigned n=0;n<7;n++)record(0x4000,n,1,0,0,0,0,0);
    for(unsigned n=0;n<84;n++)actor(0x1000+n*0x30,n?0x1000+(n-1)*0x30:0,n<83?0x1000+(n+1)*0x30:0,600,400,0,0x4000);
    wr(0x58,0x1f90);CHECK(run(v)==kIogVisualCapacity); /*588visibleparts, noacceptedpartial*/
    fixture();wr(0x56,0);wr(0x58,0);CHECK(run(v)==kIogVisualReady&&!frame.actor_count&&!frame.part_count);
}
static void exact_room_selection(void){
    for(unsigned room=0;room<65536;room++){
        bool expected=false;
        const unsigned allowed[]={0x02,0x03,0x04,0x05,0x06,0x08,0x0d,0x31,0x4c,0x61,0x83,0xe5,0xe6,0xe7,0xe8,0x01,0x0c,0x0e,0x0f,0x12,0x15,0x1a,0x1c,0x1e,0x23,0x25,0x26,
            0x27,0x28,0x29,0x2d,0x3d,0x3e,0x3f,0x40,0x41,0x42,0x45,0x46,0x4f,0x51,0x53,
            0x55,0x61,0x62,0x64,0x67,0x6d,0x6f,0x85,0x86,0x8a,0x8b,0xa7,0xb6,0xb8,0xcc,
            0xcd,0xce,0xdd,0xde,0xdf,0xe0,0xe1,0xe2,0xe3,0xea};
        for(unsigned i=0;i<sizeof(allowed)/sizeof(allowed[0]);i++)if(room==allowed[i])expected=true;
        CHECK(IogVisualObjectsSupportsScene((uint16_t)room)==expected);
    }
}
int main(void){geometry_and_pixels();orders_and_manual();all_planar_colors();player_rom_pixels();refusals_and_capacity();exact_room_selection();printf("%u visual-object assertions passed\n",checks);return 0;}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', default='cc')
    p.add_argument('--out', type=Path, default=ROOT/'.local/visual-object-tests')
    args = p.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT/'.local').resolve()):
        p.error('test output must stay under ignored .local/')
    out.mkdir(parents=True, exist_ok=True)
    source = out/'visual_objects.c';source.write_text(HARNESS, encoding='utf-8')
    inputs = [ROOT/'src/iog_visual_objects.c']
    exe = out/'visual_objects.exe'
    command = [args.compiler,'-std=c11','-O1','-Wall','-Wextra','-Werror',
               '-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),
               str(source),*[str(s) for s in inputs],str(ROOT/'snesrecomp/runner/src/sha256.c'),'-o',str(exe)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr, encoding='utf-8')
    build.check_returncode()
    env = {k:v for k,v in os.environ.items() if not k.startswith(('SNESRECOMP_','IOG_'))}
    run = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
    (out/'run.log').write_text(run.stdout+run.stderr, encoding='utf-8')
    result = dict(passed=run.returncode==0,command=command,
        scope='ROM-free visual data decoder/order/coordinates/pixels/refusal; no game/GPU or campaign proof',
        sources={str(s.relative_to(ROOT)):hashlib.sha256(s.read_bytes()).hexdigest()
                 for s in inputs+[ROOT/'src/iog_visual_objects.h']},
        stdout=run.stdout,stderr=run.stderr)
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    run.check_returncode();print(run.stdout.strip())


if __name__=='__main__': main()
