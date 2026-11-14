"""Synthetic host runtime, conservative exploration and persistence tests."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "iog_map_runtime.h"
static uint8_t ram[131072],saved_ram[131072];static Ppu ppu,saved_ppu;static unsigned checks;
#define CHECK(x)do{checks++;if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static void word(unsigned at,unsigned value){ram[at]=(uint8_t)value;ram[at+1]=(uint8_t)(value>>8);}
static IogMapRuntimeFrame fixture(void){
 memset(ram,0,sizeof(ram));memset(&ppu,0,sizeof(ppu));
 word(0x644,1);word(0x692,256);word(0x696,256);word(0x69a,256);word(0x69e,0xa000);word(0x6ae,0x2000);
 word(0x80,0xc000);ram[0x82]=0x7f;
 for(unsigned y=0;y<16;y++)ram[0xa000+y*16+8]=1;
 ram[0x10001]=0x0f;memset(ram+0x1c000,0xf0,256); /* actor-occupied live grid is NOT our static geometry */
 for(unsigned i=0;i<4;i++){word(0x2000+i*2,1);word(0x2008+i*2,2);}
 ppu.bgmode=1;ppu.bgTileAdr=0x622;
 for(unsigned y=0;y<8;y++){ppu.vram[0x2000+16+y]=0x00ff;ppu.vram[0x2000+32+y]=0xff00;ppu.vram[0x3000+16+y]=0xff00;}
 ppu.cgram[1]=31;ppu.cgram[2]=31<<5;
 IogMapRuntimeFrame f={0};f.ram=ram;f.ram_bytes=sizeof(ram);f.ppu=&ppu;
 memset(f.content_sha256,0x41,32);f.scene=1;f.authored=(IogMapRuntimeRect){0,0,256,256};
 f.player_x=72;f.player_y=104;f.profile_verified=true;return f;
}
static void update(IogMapRuntime*r,const IogMapRuntimeFrame*f){
 memcpy(saved_ram,ram,sizeof(ram));saved_ppu=ppu;CHECK(IogMapRuntimeUpdate(r,f));
 CHECK(!memcmp(saved_ram,ram,sizeof(ram))&&!memcmp(&saved_ppu,&ppu,sizeof(ppu)));
}
int main(int argc,char**argv){
 CHECK(argc==3);IogMapRuntimeFrame f=fixture();IogMapRuntime*r=IogMapRuntimeCreate(argv[1]);CHECK(r);
 IogMapViewSource view;IogMapRuntimeStatus status;
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));IogMapRuntimeGetStatus(r,&status);
 CHECK(status.frame_valid&&status.grid_width==16&&status.grid_height==16&&status.cell_world_pixels==16&&status.atlas_cell_pixels==8);
 CHECK(view.walkable[6*16+4]&&ram[0x1c000+6*16+4]==0xf0);
 CHECK(IogMapDiscoveryIsRevealed(view.discovery,8,6)&&!IogMapDiscoveryIsRevealed(view.discovery,9,6));
 CHECK(!IogMapDiscoveryIsRevealed(view.discovery,4,14)); /* outside authentic224-line camera */
 CHECK(view.scenery_rgba[0]==255&&view.scenery_rgba[1]==0&&view.scenery_rgba[2]==0&&view.scenery_rgba[3]==255);
 CHECK(view.scenery_rgba[64*4]==0&&view.scenery_rgba[64*4+1]==255); /* real decoded wall art */
 if(!strcmp(argv[2],"corruption")){
  CHECK(status.persistent_loads==0&&!IogMapDiscoveryIsRevealed(view.discovery,11,6));
  IogMapRuntimeDestroy(r);printf("corrupt state rejected; %u checks\n",checks);return 0;
 }
 for(unsigned i=0;i<120;i++)update(r,&f);
 IogMapRuntimeGetStatus(r,&status);CHECK(status.persistent_writes==0);
 /* A new character bank changes art even if NO VRAM or palette bytes change.
  * It must rebuild immediately rather than displaying the previous bank. */
 ppu.bgTileAdr=0x633;update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));CHECK(view.scenery_rgba[0]==0&&view.scenery_rgba[1]==255);
 ppu.bgTileAdr=0x622;update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));CHECK(view.scenery_rgba[0]==255&&view.scenery_rgba[1]==0);
 /* A real new player anchor on the far side can reveal that area; rewinding
  * back keeps the host journal, without pretending a path crossed the wall. */
 f.player_x=184;update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));CHECK(IogMapDiscoveryIsRevealed(view.discovery,11,6));
 f.player_x=72;update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));CHECK(IogMapDiscoveryIsRevealed(view.discovery,11,6));
 IogMapRuntimeGetStatus(r,&status);CHECK(status.persistent_writes==0);
 while(status.accepted_frames<300){update(r,&f);IogMapRuntimeGetStatus(r,&status);}
 CHECK(status.persistent_writes==1); /* one periodic dirty flush, not per-frame */
 for(unsigned i=0;i<60;i++)update(r,&f);
 IogMapRuntimeGetStatus(r,&status);CHECK(status.persistent_writes==1);
 CHECK(IogMapRuntimeFlush(r));IogMapRuntimeGetStatus(r,&status);CHECK(status.persistent_writes==1);
 CHECK(IogMapRuntimeFlush(r));IogMapRuntimeGetStatus(r,&status);CHECK(status.persistent_writes==1);
 CHECK(!IogMapRuntimeUpdate(r,NULL));memset(&view,0xab,sizeof(view));CHECK(!IogMapRuntimeGetViewSource(r,&view)&&!view.discovery);
 IogMapRuntimeGetStatus(r,&status);CHECK(!status.frame_valid);
 ppu.bgmode=7;CHECK(!IogMapRuntimeUpdate(r,&f));CHECK(!IogMapRuntimeGetViewSource(r,&view));ppu.bgmode=1;
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view)&&IogMapDiscoveryIsRevealed(view.discovery,11,6));
 ram[0x1c000+6*16+4]=0x0f;CHECK(!IogMapRuntimeUpdate(r,&f));CHECK(!IogMapRuntimeGetViewSource(r,&view));ram[0x1c000+6*16+4]=0xf0;
 /* Occupancy may preserve a partial-collision nibble (F1 over static01).
  * It must keep that barrier, and cannot excuse a mismatching low nibble. */
 ram[0x10001]=1;ram[0x1c000+6*16+8]=0xf1;update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));
 CHECK(!view.walkable[6*16+8]&&IogMapDiscoveryIsRevealed(view.discovery,8,6));
 /* Far-side cell already remembered above; fresh content proves no new spill. */
 f.content_sha256[0]=0x59;update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));
 CHECK(!IogMapDiscoveryIsRevealed(view.discovery,9,6)&&!view.walkable[6*16+8]);
 ram[0x1c000+6*16+8]=0xf0;update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));
 CHECK(!view.walkable[6*16+8]&&!IogMapDiscoveryIsRevealed(view.discovery,9,6));
 ram[0x1c000+6*16+4]=0xf1;CHECK(!IogMapRuntimeUpdate(r,&f)); /* static00 != low01 */
 ram[0x1c000+6*16+4]=0xe0;CHECK(!IogMapRuntimeUpdate(r,&f)); /* unknown high nibble */
 ram[0x1c000+6*16+4]=0xf0;ram[0x10001]=0x0f;f.content_sha256[0]=0x41;
 ram[0x82]=0;CHECK(!IogMapRuntimeUpdate(r,&f));ram[0x82]=0x7f;update(r,&f);
 f.profile_verified=false;CHECK(!IogMapRuntimeUpdate(r,&f));f.profile_verified=true;
 f.static_flags_address=131000;CHECK(!IogMapRuntimeUpdate(r,&f));f.static_flags_address=0;
 f.content_sha256[0]^=1;update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view)&&!IogMapDiscoveryIsRevealed(view.discovery,11,6));
 f.content_sha256[0]^=1;update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view)&&IogMapDiscoveryIsRevealed(view.discovery,11,6));
 uint8_t previous_layout[32];IogMapRuntimeGetStatus(r,&status);memcpy(previous_layout,status.layout_sha256,32);
 ram[0xa000]=1;update(r,&f);IogMapRuntimeGetStatus(r,&status);CHECK(memcmp(previous_layout,status.layout_sha256,32));
 CHECK(IogMapRuntimeGetViewSource(r,&view)&&!IogMapDiscoveryIsRevealed(view.discovery,11,6));ram[0xa000]=0;update(r,&f);
 f.authored=(IogMapRuntimeRect){0,128,256,128};f.player_y=152;f.camera_y=128;update(r,&f);IogMapRuntimeGetStatus(r,&status);
 CHECK(status.floor_id==(8u<<16)&&status.grid_height==8&&status.player_cell_y==1);
 CHECK(IogMapRuntimeGetViewSource(r,&view)&&view.scenery_bytes==128*64*4);
 f.authored=(IogMapRuntimeRect){0,0,256,256};f.player_y=104;f.camera_y=0;update(r,&f);
 /* Dual collision uses LINEAR layer1 indices even when its authored width
  * differs. Secondary worldYpage1 overlays primary worldXpage1 here. */
 f=fixture();word(0x692,512);word(0x69a,512);word(0x694,256);word(0x698,512);word(0x69c,512);
 word(0x6a0,0xc000);word(0x6b0,0x2800);word(0x6ac,0x100);ram[0x6ef]=1;ram[0x10102]=0x0f;
 memset(ram+0xc000,0,512);for(unsigned y=0;y<16;y++)ram[0xc000+256+y*16+6]=2;
 f.authored=(IogMapRuntimeRect){0,0,512,256};f.camera_x=256;f.player_x=328;
 for(unsigned i=0;i<512;i++){
  unsigned value=ram[0x10000+ram[0xa000+i]],overlay=ram[0x10100+ram[0xc000+i]];
  ram[0x1c000+i]=(uint8_t)(overlay?overlay:value);
 }
 ram[0x1c000+256+6*16+4]=0xf0; /* proven occupancy exempt, not all flags ignored */
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));
 CHECK(!view.walkable[6*32+22]&&view.walkable[6*32+23]);
 CHECK(IogMapDiscoveryIsRevealed(view.discovery,22,6)&&!IogMapDiscoveryIsRevealed(view.discovery,23,6));
 IogMapRuntimeGetStatus(r,&status);uint8_t overlay_layout[32];memcpy(overlay_layout,status.layout_sha256,32);
 /* Removing the source barrier and rebuilding live collision yields a new
  * identity and newly reachable cells; old fog is not borrowed across it. */
 for(unsigned y=0;y<16;y++){ram[0xc000+256+y*16+6]=0;ram[0x1c000+256+y*16+6]=0;}
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));CHECK(IogMapDiscoveryIsRevealed(view.discovery,23,6));
 IogMapRuntimeGetStatus(r,&status);CHECK(memcmp(overlay_layout,status.layout_sha256,32));
 word(0x69c,513);CHECK(!IogMapRuntimeUpdate(r,&f));word(0x69c,512);
 word(0x6ac,0xffff);CHECK(!IogMapRuntimeUpdate(r,&f));word(0x6ac,0x100);
 /* Qualified scene-cache identity follows authored sources, not mutable COP
  * door tiles. Current collision still controls reachability on EVERY frame. */
 f=fixture();f.stable_source_identity=true;
 word(0x678,0x8000);ram[0x67a]=0xc1;word(0x67e,0x9000);ram[0x680]=0xc1;
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));IogMapRuntimeGetStatus(r,&status);
 uint8_t stable_layout[32];memcpy(stable_layout,status.layout_sha256,32);
 CHECK(!IogMapDiscoveryIsRevealed(view.discovery,9,6));
 for(unsigned y=0;y<16;y++)ram[0xa000+y*16+8]=0;
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));IogMapRuntimeGetStatus(r,&status);
 CHECK(!memcmp(stable_layout,status.layout_sha256,32)&&view.walkable[6*16+8]);
 CHECK(IogMapDiscoveryIsRevealed(view.discovery,11,6));
 CHECK(view.scenery_rgba[64*4]==255&&view.scenery_rgba[64*4+1]==0); /* immediate door art */
 for(unsigned y=0;y<16;y++)ram[0xa000+y*16+8]=1;
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));IogMapRuntimeGetStatus(r,&status);
 CHECK(!memcmp(stable_layout,status.layout_sha256,32)&&!view.walkable[6*16+8]);
 CHECK(IogMapDiscoveryIsRevealed(view.discovery,11,6)); /* closed door does not erase memory */
 CHECK(view.scenery_rgba[64*4]==0&&view.scenery_rgba[64*4+1]==255);
 /* Definitions can be edited without map/VRAM writes: refresh immediately. */
 for(unsigned i=0;i<4;i++)word(0x2000+i*2,2);
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));IogMapRuntimeGetStatus(r,&status);
 CHECK(!memcmp(stable_layout,status.layout_sha256,32)&&view.scenery_rgba[0]==0&&view.scenery_rgba[1]==255);
 ram[0x67b]=123;ram[0x681]=45;word(0x6a4,321); /* inactive L1 history irrelevant */
 update(r,&f);IogMapRuntimeGetStatus(r,&status);CHECK(!memcmp(stable_layout,status.layout_sha256,32));
 ram[0x678]^=1;update(r,&f);IogMapRuntimeGetStatus(r,&status);
 CHECK(memcmp(stable_layout,status.layout_sha256,32));CHECK(IogMapRuntimeGetViewSource(r,&view));
 CHECK(!IogMapDiscoveryIsRevealed(view.discovery,11,6)); /* different authored asset */
 /* Opt-in aligned scenery is independent from dual COLLISION overlay. The
  * real second artwork plane supplies classroom floor under transparent BG1. */
 f=fixture();memset(f.content_sha256,0x71,32);f.stable_source_identity=true;f.aligned_secondary_source=true;
 word(0x678,0x8000);ram[0x67a]=0xc1;word(0x67e,0x9000);ram[0x680]=0xc1;
 word(0x67b,0xa000);ram[0x67d]=0xc1;word(0x681,0xb000);ram[0x683]=0xc1;
 word(0x694,256);word(0x698,256);word(0x69c,256);word(0x6a0,0xc000);word(0x6b0,0x2800);
 for(unsigned i=0;i<4;i++){word(0x2000+i*2,0);word(0x2008+i*2,1);word(0x2800+i*2,2);}
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));IogMapRuntimeGetStatus(r,&status);
 uint8_t aligned_layout[32];memcpy(aligned_layout,status.layout_sha256,32);
 CHECK(view.scenery_rgba[0]==0&&view.scenery_rgba[1]==255&&view.scenery_rgba[3]==255);
 CHECK(view.scenery_rgba[64*4]==255&&view.scenery_rgba[64*4+1]==0); /* BG1low above BG2low */
 CHECK(!view.walkable[6*16+8]); /* secondary art is not secondary collision */
 for(unsigned i=0;i<4;i++)word(0x2800+i*2,2|0x2000);
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));IogMapRuntimeGetStatus(r,&status);
 CHECK(!memcmp(aligned_layout,status.layout_sha256,32)&&view.scenery_rgba[64*4]==0&&view.scenery_rgba[64*4+1]==255);
 for(unsigned i=0;i<4;i++)word(0x2008+i*2,1|0x2000);
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));CHECK(view.scenery_rgba[64*4]==255&&view.scenery_rgba[64*4+1]==0);
 /* Secondary character-bank-only and secondary map-only edits invalidate
  * art immediately, independently of journal persistence and VRAM contents. */
 ppu.vram[0x3000+32]=0x00ff;for(unsigned y=1;y<8;y++)ppu.vram[0x3000+32+y]=0x00ff;
 ppu.bgTileAdr=0x632;update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));CHECK(view.scenery_rgba[0]==255&&view.scenery_rgba[1]==0);
 ppu.bgTileAdr=0x622;word(0x2808,0);word(0x280a,0);word(0x280c,0);word(0x280e,0);ram[0xc000]=1;ppu.cgram[0]=31<<10;
 update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));CHECK(view.scenery_rgba[0]==0&&view.scenery_rgba[1]==0&&view.scenery_rgba[2]==255&&view.scenery_rgba[3]==255);
 IogMapRuntimeGetStatus(r,&status);CHECK(!memcmp(aligned_layout,status.layout_sha256,32));
 ram[0x67b]^=1;update(r,&f);IogMapRuntimeGetStatus(r,&status);CHECK(memcmp(aligned_layout,status.layout_sha256,32));
 word(0x69c,257);CHECK(!IogMapRuntimeUpdate(r,&f));CHECK(!IogMapRuntimeGetViewSource(r,&view));word(0x69c,256);
 word(0x6b0,0xff00);CHECK(!IogMapRuntimeUpdate(r,&f));word(0x6b0,0x2800);
 f=fixture();update(r,&f);
 /* More than8 identities forces dirty eviction; returning reloads the
  * persisted identity rather than borrowing a different room's fog. */
 for(unsigned scene=2;scene<=12;scene++){f.scene=(uint16_t)scene;word(0x644,scene);update(r,&f);}
 f.scene=1;word(0x644,1);update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));IogMapRuntimeGetStatus(r,&status);
 CHECK(status.persistent_loads>0&&IogMapDiscoveryIsRevealed(view.discovery,11,6));
 IogMapViewSettings settings={0};settings.mode=kIogMapViewRadar;settings.transform=(IogMapViewTransform){0,0,1,1,1};settings.fog=(IogMapViewColor){1,2,3,255};
 uint8_t pixels[16*16*4];CHECK(IogMapRuntimeDraw(r,pixels,sizeof(pixels),16*4,16,16,&settings));
 CHECK(IogMapRuntimeFlush(r));printf("ACTIVE_LAYOUT ");for(unsigned i=0;i<32;i++)printf("%02x",status.layout_sha256[i]);printf("\n");
 IogMapRuntimeDestroy(r);
 r=IogMapRuntimeCreate(argv[1]);CHECK(r);update(r,&f);CHECK(IogMapRuntimeGetViewSource(r,&view));CHECK(IogMapDiscoveryIsRevealed(view.discovery,11,6));IogMapRuntimeDestroy(r);
 char missing[4096];CHECK(snprintf(missing,sizeof(missing),"%s-missing",argv[1])>0);CHECK(!IogMapRuntimeCreate(missing));
 printf("%u map-runtime assertions passed\n",checks);return 0;
}
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--compiler',default='cc');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();assert out.is_relative_to(ROOT/'.local');out.mkdir(parents=True,exist_ok=False);saves=out/'saves';saves.mkdir();sentinel=saves/'owner-sentinel.bin';sentinel.write_bytes(b'owner data stays intact')
    source=out/'runtime.c';source.write_text(HARNESS);exe=out/'runtime.exe'
    inputs=[ROOT/'src'/name for name in ('iog_map_runtime.c','iog_map_runtime.h','iog_map_scenery.c','iog_map_scenery.h','iog_map_discovery.c','iog_map_discovery.h','iog_map_view.c','iog_map_view.h')]+[ROOT/'snesrecomp/runner/src/sha256.c']
    cmd=[a.compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),str(source),*[str(x)for x in inputs if x.suffix=='.c'],'-o',str(exe)]
    b=subprocess.run(cmd,capture_output=True,text=True);(out/'build.log').write_text(b.stdout+b.stderr);b.check_returncode()
    runs=[]
    for phase in ('normal','corruption'):
        r=subprocess.run([str(exe),str(saves),phase],capture_output=True,text=True,timeout=60);(out/(phase+'.log')).write_text(r.stdout+r.stderr);r.check_returncode();runs.append(r.stdout)
        if phase=='normal':
            layout=bytes.fromhex(next(x.split()[1]for x in r.stdout.splitlines()if x.startswith('ACTIVE_LAYOUT ')))
            candidates=[x for x in (saves/'maps').glob('*.iogmap')if x.read_bytes()[52:84]==layout and x.read_bytes()[20:52]==bytes([0x41])*32]
            assert len(candidates)==1;candidates[0].write_bytes(candidates[0].read_bytes()[:-1]+bytes([candidates[0].read_bytes()[-1]^1]))
    assert sentinel.read_bytes()==b'owner data stays intact'and not Path(str(saves)+'-missing').exists()
    assert not list((saves/'maps').glob('*.tmp-*'))
    (out/'receipt.json').write_text(json.dumps({'passed':True,'command':cmd,'runs':runs,'corrupt_state_rejected_and_replaced':True,'owner_sentinel_preserved':True,'no_recursive_parent_creation':True,'no_leftover_atomic_temp_files':True,'sources':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in inputs+[Path(__file__)]},'scope':'Synthetic Mode1 native runtime+artwork+conservative static-collision discovery+bounded LRU+persistence. No game/GUI/campaign or optical LOS qualification.'},indent=2)+'\n');print('\n'.join(runs))
if __name__=='__main__':main()
