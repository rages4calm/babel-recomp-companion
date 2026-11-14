#include "iog_map_discovery.h"
#include <string.h>

enum { HeaderBytes=92, TrailerBytes=4 };
static const uint8_t magic[8]={'I','O','G','M','A','P','D',0};
static bool Dimensions(unsigned w,unsigned h)
{ return w&&h&&w<=kIogMapDiscoveryMaxSide&&h<=kIogMapDiscoveryMaxSide; }
static size_t Payload(unsigned w,unsigned h){return ((size_t)w*h+7)/8;}
static bool Overlap(const void*a,size_t an,const void*b,size_t bn)
{
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return an&&bn&&(x<=y?y-x<an:x-y<bn);
}
static unsigned Read16(const uint8_t*p){return p[0]|(unsigned)p[1]<<8;}
static uint32_t Read32(const uint8_t*p)
{return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void Write16(uint8_t*p,unsigned n){p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);}
static void Write32(uint8_t*p,uint32_t n)
{for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(i*8));}
static uint32_t Crc32(const uint8_t*p,size_t bytes)
{
    uint32_t crc=UINT32_MAX;
    for(size_t i=0;i<bytes;i++){
        crc^=p[i];
        for(unsigned bit=0;bit<8;bit++)crc=crc&1?(crc>>1)^0xedb88320u:crc>>1;
    }
    return ~crc;
}
static bool Canonical(const uint8_t*p,unsigned w,unsigned h)
{
    unsigned remainder=(w*h)&7;
    return !remainder || !(p[Payload(w,h)-1]&~((1u<<remainder)-1));
}
bool IogMapDiscoveryInit(IogMapDiscovery*m,unsigned w,unsigned h,
    const IogMapDiscoveryIdentity*id)
{
    if(!m||!id||!Dimensions(w,h))return false;
    IogMapDiscoveryIdentity copy=*id;
    memset(m,0,sizeof(*m));m->identity=copy;m->width=(uint16_t)w;m->height=(uint16_t)h;
    return true;
}
bool IogMapDiscoveryIsRevealed(const IogMapDiscovery*m,int x,int y)
{
    if(!m||!Dimensions(m->width,m->height)||x<0||y<0||x>=m->width||y>=m->height)return false;
    size_t i=(size_t)y*m->width+(unsigned)x;
    return (m->explored[i>>3]&(1u<<(i&7)))!=0;
}
bool IogMapDiscoveryReveal(IogMapDiscovery*m,int cx,int cy,unsigned radius,
    const uint8_t*mask,size_t bytes,size_t stride,size_t*new_cells)
{
    if(new_cells)*new_cells=0;
    if(!m||!mask||!Dimensions(m->width,m->height)||cx<0||cy<0||
       cx>=m->width||cy>=m->height||radius>512||stride<m->width)return false;
    if(m->height>1 && stride>(SIZE_MAX-m->width)/(m->height-1))return false;
    size_t required=(size_t)(m->height-1)*stride+m->width;
    if(bytes<required||Overlap(m,sizeof(*m),mask,required))return false;
    size_t changed=0;
    for(unsigned y=0;y<m->height;y++)for(unsigned x=0;x<m->width;x++){
        int dx=(int)x-cx,dy=(int)y-cy;
        if((unsigned)(dx*dx+dy*dy)>radius*radius||!mask[(size_t)y*stride+x])continue;
        size_t i=(size_t)y*m->width+x;uint8_t bit=(uint8_t)(1u<<(i&7));
        if(!(m->explored[i>>3]&bit)){m->explored[i>>3]|=bit;changed++;}
    }
    if(new_cells)*new_cells=changed;
    return true;
}
size_t IogMapDiscoveryEncodedSize(const IogMapDiscovery*m)
{
    return m&&Dimensions(m->width,m->height)?HeaderBytes+Payload(m->width,m->height)+TrailerBytes:0;
}
bool IogMapDiscoverySerialize(const IogMapDiscovery*m,uint8_t*out,size_t capacity,size_t*written)
{
    if(written)*written=0;
    size_t total=IogMapDiscoveryEncodedSize(m);
    if(!out||!total||capacity<total||Overlap(m,sizeof(*m),out,total)||
       !Canonical(m->explored,m->width,m->height))return false;
    memset(out,0,HeaderBytes);memcpy(out,magic,8);
    Write16(out+8,1);Write16(out+10,HeaderBytes);Write16(out+12,m->width);Write16(out+14,m->height);
    Write32(out+16,(uint32_t)Payload(m->width,m->height));
    memcpy(out+20,m->identity.content_sha256,32);memcpy(out+52,m->identity.layout_sha256,32);
    Write32(out+84,m->identity.floor_id);memcpy(out+HeaderBytes,m->explored,total-HeaderBytes-TrailerBytes);
    Write32(out+total-TrailerBytes,Crc32(out,total-TrailerBytes));
    if(written)*written=total;
    return true;
}
bool IogMapDiscoveryDeserialize(IogMapDiscovery*dst,const uint8_t*in,size_t bytes,
    const IogMapDiscoveryIdentity*id,unsigned w,unsigned h)
{
    if(!dst||!in||!id||!Dimensions(w,h)||bytes<HeaderBytes+TrailerBytes)return false;
    size_t payload=Payload(w,h),total=HeaderBytes+payload+TrailerBytes;
    if(bytes!=total||memcmp(in,magic,8)||Read16(in+8)!=1||Read16(in+10)!=HeaderBytes||
       Read16(in+12)!=w||Read16(in+14)!=h||Read32(in+16)!=payload||Read32(in+88)||
       memcmp(in+20,id->content_sha256,32)||memcmp(in+52,id->layout_sha256,32)||
       Read32(in+84)!=id->floor_id||Read32(in+total-4)!=Crc32(in,total-4)||
       !Canonical(in+HeaderBytes,w,h))return false;
    IogMapDiscovery decoded;
    if(!IogMapDiscoveryInit(&decoded,w,h,id))return false;
    memcpy(decoded.explored,in+HeaderBytes,payload);*dst=decoded;
    return true;
}
