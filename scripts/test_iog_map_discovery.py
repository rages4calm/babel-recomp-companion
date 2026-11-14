"""ROM-free discovery, caller-visibility and persistent-state validation."""
from pathlib import Path
import argparse, hashlib, json, subprocess
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "iog_map_discovery.h"
static unsigned checks;
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static IogMapDiscovery map,copy,before;
static uint8_t mask[65536],encoded[9000],altered[9000];
static uint32_t crc(const uint8_t*p,size_t size){uint32_t n=~0u;for(size_t i=0;i<size;i++){n^=p[i];for(int j=0;j<8;j++)n=n&1?(n>>1)^0xedb88320u:n>>1;}return ~n;}
static void fix_crc(uint8_t*p,size_t n){uint32_t c=crc(p,n-4);for(unsigned j=0;j<4;j++)p[n-4+j]=(uint8_t)(c>>(8*j));}
int main(void){
 IogMapDiscoveryIdentity id={{0},{0},5};memset(id.content_sha256,0x41,32);memset(id.layout_sha256,0x7c,32);
 CHECK(!IogMapDiscoveryInit(NULL,16,12,&id));CHECK(!IogMapDiscoveryInit(&map,0,12,&id));CHECK(!IogMapDiscoveryInit(&map,257,12,&id));
 CHECK(IogMapDiscoveryInit(&map,16,12,&id));
 memset(mask,0xff,sizeof(mask));for(unsigned y=0;y<12;y++)for(unsigned x=8;x<16;x++)mask[y*20+x]=0;
 size_t changed=999,expected=0;
 CHECK(IogMapDiscoveryReveal(&map,7,6,4,mask,240,20,&changed));
 for(int y=0;y<12;y++)for(int x=0;x<16;x++){
  bool want=x<8&&(x-7)*(x-7)+(y-6)*(y-6)<=16;expected+=want;
  CHECK(IogMapDiscoveryIsRevealed(&map,x,y)==want);
 }
 CHECK(changed==expected&&changed>0);CHECK(!IogMapDiscoveryIsRevealed(&map,8,6));CHECK(!IogMapDiscoveryIsRevealed(&map,9,6));
 CHECK(IogMapDiscoveryReveal(&map,7,6,4,mask,240,20,&changed)&&changed==0);
 before=map;CHECK(!IogMapDiscoveryReveal(&map,-1,6,4,mask,240,20,&changed));CHECK(changed==0&&!memcmp(&map,&before,sizeof(map)));
 CHECK(!IogMapDiscoveryReveal(&map,7,6,513,mask,240,20,&changed));CHECK(!IogMapDiscoveryReveal(&map,7,6,4,NULL,240,20,&changed));
 CHECK(!IogMapDiscoveryReveal(&map,7,6,4,mask,235,20,&changed));CHECK(!IogMapDiscoveryReveal(&map,7,6,4,mask,240,15,&changed));
 CHECK(!IogMapDiscoveryReveal(&map,7,6,4,mask,SIZE_MAX,SIZE_MAX,&changed));CHECK(!memcmp(&map,&before,sizeof(map)));
 CHECK(!IogMapDiscoveryIsRevealed(&map,16,0)&&!IogMapDiscoveryIsRevealed(&map,0,12));
 size_t size=IogMapDiscoveryEncodedSize(&map),written=999;CHECK(size==120);memset(encoded,0xab,sizeof(encoded));
 CHECK(!IogMapDiscoverySerialize(&map,encoded,size-1,&written)&&written==0);for(size_t i=0;i<size;i++)CHECK(encoded[i]==0xab);
 CHECK(IogMapDiscoverySerialize(&map,encoded,sizeof(encoded),&written)&&written==size);
 CHECK(IogMapDiscoveryDeserialize(&copy,encoded,size,&id,16,12));CHECK(!memcmp(&map,&copy,sizeof(map)));
 CHECK(IogMapDiscoverySerialize(&copy,altered,sizeof(altered),&written)&&!memcmp(encoded,altered,size));
 before=copy;IogMapDiscoveryIdentity wrong=id;wrong.floor_id++;
 CHECK(!IogMapDiscoveryDeserialize(&copy,encoded,size,&wrong,16,12));wrong=id;wrong.content_sha256[0]^=1;
 CHECK(!IogMapDiscoveryDeserialize(&copy,encoded,size,&wrong,16,12));wrong=id;wrong.layout_sha256[31]^=1;
 CHECK(!IogMapDiscoveryDeserialize(&copy,encoded,size,&wrong,16,12));
 CHECK(!IogMapDiscoveryDeserialize(&copy,encoded,size,&id,15,12));CHECK(!IogMapDiscoveryDeserialize(&copy,encoded,size+1,&id,16,12));
 for(size_t i=0;i<size;i++){
  memcpy(altered,encoded,size);altered[i]^=1;CHECK(!IogMapDiscoveryDeserialize(&copy,altered,size,&id,16,12));CHECK(!memcmp(&copy,&before,sizeof(copy)));
 }
 const unsigned fields[]={0,8,10,12,14,16,20,52,84,88};
 for(unsigned i=0;i<sizeof(fields)/sizeof(fields[0]);i++){
  memcpy(altered,encoded,size);altered[fields[i]]^=1;fix_crc(altered,size);
  CHECK(!IogMapDiscoveryDeserialize(&copy,altered,size,&id,16,12));CHECK(!memcmp(&copy,&before,sizeof(copy)));
 }
 CHECK(!IogMapDiscoverySerialize(&map,(uint8_t*)&map,sizeof(map),&written));CHECK(!memcmp(&map,&before,sizeof(map)));
 CHECK(IogMapDiscoveryInit(&map,13,11,&id));memset(mask,1,sizeof(mask));CHECK(IogMapDiscoveryReveal(&map,6,5,512,mask,143,13,&changed)&&changed==143);
 size=IogMapDiscoveryEncodedSize(&map);CHECK(IogMapDiscoverySerialize(&map,encoded,sizeof(encoded),&written));
 memcpy(altered,encoded,size);altered[92+17]|=128;fix_crc(altered,size);CHECK(!IogMapDiscoveryDeserialize(&copy,altered,size,&id,13,11));
 map.explored[17]|=128;CHECK(!IogMapDiscoverySerialize(&map,encoded,sizeof(encoded),&written));
 CHECK(IogMapDiscoveryInit(&map,256,256,&id));CHECK(IogMapDiscoveryReveal(&map,0,0,512,mask,sizeof(mask),256,&changed)&&changed==65536);
 CHECK(IogMapDiscoveryIsRevealed(&map,255,255));size=IogMapDiscoveryEncodedSize(&map);CHECK(size==8288);
 CHECK(IogMapDiscoverySerialize(&map,encoded,sizeof(encoded),&written));CHECK(IogMapDiscoveryDeserialize(&copy,encoded,size,&id,256,256));CHECK(!memcmp(&map,&copy,sizeof(map)));
 /* A hidden center is not automatically learned, even at radius0. */
 CHECK(IogMapDiscoveryInit(&map,8,8,&id));memset(mask,0,sizeof(mask));CHECK(IogMapDiscoveryReveal(&map,4,4,0,mask,64,8,&changed)&&changed==0);
 CHECK(!IogMapDiscoveryIsRevealed(&map,4,4));
 printf("%u discovery assertions passed\n",checks);return 0;
}
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--compiler',default='cc');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();assert out.is_relative_to(ROOT/'.local');out.mkdir(parents=True,exist_ok=True)
    source=out/'discovery.c';source.write_text(HARNESS);binary=out/'discovery.exe'
    inputs=[ROOT/'src/iog_map_discovery.c',ROOT/'src/iog_map_discovery.h']
    command=[a.compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),str(source),str(inputs[0]),'-o',str(binary)]
    result=subprocess.run(command,capture_output=True,text=True);(out/'build.log').write_text(result.stdout+result.stderr);result.check_returncode()
    result=subprocess.run([str(binary)],capture_output=True,text=True);(out/'run.log').write_text(result.stdout+result.stderr);result.check_returncode()
    (out/'receipt.json').write_text(json.dumps({'passed':True,'stdout':result.stdout,'command':command,'sources':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in inputs+[Path(__file__)]},'scope':'Pure host discovery and persistence foundation; visibility supplied by caller. No map UI, engine wiring, automatic LOS, guest writes or game qualification.'},indent=2)+'\n')
    print(result.stdout)
if __name__=='__main__':main()
