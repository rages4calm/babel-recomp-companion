#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include "iog_map_runtime.h"
#include "iog_map_scenery.h"
#include "sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#pragma push_macro("FORCEINLINE")
#undef FORCEINLINE
#include <windows.h>
#pragma pop_macro("FORCEINLINE")
#else
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#endif

enum { CacheRooms=8,PathCapacity=4096,SaveCapacity=8290,Cells=65536 };
typedef struct MapRoom {
    bool used,dirty;
    uint64_t age;
    uint8_t key[32];
    IogMapDiscovery map;
    size_t count;
} MapRoom;
typedef struct CollisionLayers {
    bool secondary,art_secondary;
    unsigned map1,definitions1,flags1,size1,width1,height1;
} CollisionLayers;
struct IogMapRuntime {
    MapRoom rooms[CacheRooms];
    int current;
    bool visible,atlas_dirty;
    uint64_t clock,last_flush,last_atlas,writes,loads;
    unsigned nonce;
    char directory[PathCapacity];
    const char *reason;
    uint16_t scene;
    IogMapRuntimeRect rect;
    int player_x,player_y;
    unsigned source_width,source_height,map_address,definitions,characters;
    bool art_secondary;
    unsigned physical_primary;
    unsigned secondary_width,secondary_height,secondary_map,secondary_definitions,secondary_characters;
    uint8_t ram[65536],walkable[Cells],visibility[Cells],seen[Cells];
    uint16_t vram[32768],cgram[256],queue[Cells];
    uint8_t hash_input[2*65536+2*2304+128];
    uint8_t *atlas;
    size_t atlas_capacity;
};
static unsigned Word(const uint8_t*p,unsigned a){return p[a]|(unsigned)p[a+1]<<8;}
static void Put32(uint8_t*p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(i*8));}
static size_t Count(const IogMapDiscovery*m)
{
    size_t n=0,bytes=((size_t)m->width*m->height+7)/8;
    for(size_t i=0;i<bytes;i++){unsigned x=m->explored[i];while(x){n+=x&1;x>>=1;}}
    return n;
}
#ifdef _WIN32
static bool Wide(const char*path,wchar_t output[PathCapacity])
{
    wchar_t input[PathCapacity],full[PathCapacity];
    if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,input,PathCapacity))return false;
    if(!wcsncmp(input,L"\\\\?\\",4)){wcscpy(output,input);return true;}
    DWORD n=GetFullPathNameW(input,PathCapacity-8,full,NULL);
    if(!n||n>=PathCapacity-8)return false;
    if(full[0]==L'\\'&&full[1]==L'\\'){
        wcscpy(output,L"\\\\?\\UNC\\");wcscat(output,full+2);
    }else{wcscpy(output,L"\\\\?\\");wcscat(output,full);}
    return true;
}
static bool Directory(const char*path,bool reject_link)
{
    wchar_t wide[PathCapacity];if(!Wide(path,wide))return false;
    DWORD a=GetFileAttributesW(wide);
    return a!=INVALID_FILE_ATTRIBUTES&&(a&FILE_ATTRIBUTE_DIRECTORY)&&
        (!reject_link||!(a&FILE_ATTRIBUTE_REPARSE_POINT));
}
static bool MakeDirectory(const char*path)
{
    wchar_t wide[PathCapacity];return Wide(path,wide)&&
        (CreateDirectoryW(wide,NULL)||GetLastError()==ERROR_ALREADY_EXISTS)&&Directory(path,true);
}
static bool ReadFileBytes(const char*path,uint8_t*out,size_t capacity,size_t*bytes)
{
    wchar_t wide[PathCapacity];if(!Wide(path,wide))return false;
    DWORD attrs=GetFileAttributesW(wide);
    if(attrs==INVALID_FILE_ATTRIBUTES||(attrs&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)))return false;
    HANDLE h=CreateFileW(wide,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(h==INVALID_HANDLE_VALUE)return false;
    LARGE_INTEGER size;DWORD read=0;
    bool ok=GetFileSizeEx(h,&size)&&size.QuadPart>=0&&(uint64_t)size.QuadPart<=capacity&&
        ReadFile(h,out,(DWORD)size.QuadPart,&read,NULL)&&read==(uint64_t)size.QuadPart;
    CloseHandle(h);if(ok)*bytes=read;return ok;
}
static bool AtomicWrite(IogMapRuntime*r,const char*path,const uint8_t*data,size_t bytes)
{
    if(!Directory(r->directory,true))return false;
    wchar_t target[PathCapacity],temporary[PathCapacity];char temp[PathCapacity];
    if(!Wide(path,target))return false;
    HANDLE h=INVALID_HANDLE_VALUE;
    for(unsigned i=0;i<16;i++){
        int n=snprintf(temp,sizeof(temp),"%s.tmp-%lu-%u",path,(unsigned long)GetCurrentProcessId(),++r->nonce);
        if(n<0||(size_t)n>=sizeof(temp)||!Wide(temp,temporary))return false;
        h=CreateFileW(temporary,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
        if(h!=INVALID_HANDLE_VALUE)break;
        if(GetLastError()!=ERROR_FILE_EXISTS&&GetLastError()!=ERROR_ALREADY_EXISTS)return false;
    }
    if(h==INVALID_HANDLE_VALUE)return false;
    DWORD written=0;bool ok=WriteFile(h,data,(DWORD)bytes,&written,NULL)&&written==bytes&&FlushFileBuffers(h);
    if(!CloseHandle(h))ok=false;
    if(ok)ok=MoveFileExW(temporary,target,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=0;
    if(!ok)DeleteFileW(temporary);
    return ok;
}
#else
static bool Directory(const char*path,bool reject_link)
{
    struct stat s;int result=reject_link?lstat(path,&s):stat(path,&s);
    return result==0&&S_ISDIR(s.st_mode)&&(!reject_link||!S_ISLNK(s.st_mode));
}
static bool MakeDirectory(const char*path){return (mkdir(path,0700)==0||errno==EEXIST)&&Directory(path,true);}
static bool ReadFileBytes(const char*path,uint8_t*out,size_t capacity,size_t*bytes)
{
    struct stat s;if(lstat(path,&s)||!S_ISREG(s.st_mode)||s.st_size<0||(uint64_t)s.st_size>capacity)return false;
    FILE*f=fopen(path,"rb");if(!f)return false;
    size_t n=fread(out,1,capacity,f);bool ok=!ferror(f);if(fclose(f))ok=false;if(ok)*bytes=n;return ok;
}
static bool AtomicWrite(IogMapRuntime*r,const char*path,const uint8_t*data,size_t bytes)
{
    if(!Directory(r->directory,true))return false;
    char temp[PathCapacity];int fd=-1;
    for(unsigned i=0;i<16;i++){
        int n=snprintf(temp,sizeof(temp),"%s.tmp-%ld-%u",path,(long)getpid(),++r->nonce);
        if(n<0||(size_t)n>=sizeof(temp))return false;
        fd=open(temp,O_WRONLY|O_CREAT|O_EXCL,0600);if(fd>=0)break;if(errno!=EEXIST)return false;
    }
    if(fd<0)return false;
    bool ok=true;size_t n=0;
    while(n<bytes){ssize_t done=write(fd,data+n,bytes-n);if(done<0&&errno==EINTR)continue;if(done<=0){ok=false;break;}n+=(size_t)done;}
    if(ok&&fsync(fd))ok=false;if(close(fd))ok=false;
    if(ok&&rename(temp,path))ok=false;if(!ok)unlink(temp);return ok;
}
#endif
static bool Filename(const IogMapRuntime*r,const MapRoom*room,char path[PathCapacity])
{
    char hex[65];for(unsigned i=0;i<32;i++)snprintf(hex+i*2,3,"%02x",room->key[i]);
    int n=snprintf(path,PathCapacity,"%s/%s.iogmap",r->directory,hex);
    return n>=0&&(unsigned)n<PathCapacity;
}
static bool Load(const IogMapRuntime*r,const MapRoom*room,IogMapDiscovery*out)
{
    char path[PathCapacity];uint8_t bytes[SaveCapacity];size_t used=0;
    return Directory(r->directory,true)&&Filename(r,room,path)&&ReadFileBytes(path,bytes,sizeof(bytes),&used)&&
        IogMapDiscoveryDeserialize(out,bytes,used,&room->map.identity,room->map.width,room->map.height);
}
static bool Save(IogMapRuntime*r,MapRoom*room)
{
    if(!room->used||!room->dirty)return true;
    IogMapDiscovery disk;
    if(Load(r,room,&disk))for(unsigned i=0;i<kIogMapDiscoveryBytes;i++)room->map.explored[i]|=disk.explored[i];
    room->count=Count(&room->map);uint8_t bytes[SaveCapacity];size_t size=0;char path[PathCapacity];
    if(!Filename(r,room,path)||!IogMapDiscoverySerialize(&room->map,bytes,sizeof(bytes),&size)||!AtomicWrite(r,path,bytes,size))return false;
    room->dirty=false;r->writes++;return true;
}
IogMapRuntime *IogMapRuntimeCreate(const char*parent)
{
    if(!parent||!*parent||strlen(parent)>PathCapacity-128||!Directory(parent,false))return NULL;
    IogMapRuntime*r=calloc(1,sizeof(*r));if(!r)return NULL;
    int n=snprintf(r->directory,sizeof(r->directory),"%s/maps",parent);
    if(n<0||(size_t)n>=sizeof(r->directory)||!MakeDirectory(r->directory)){free(r);return NULL;}
    r->current=-1;r->reason="no_supported_frame";return r;
}
bool IogMapRuntimeFlush(IogMapRuntime*r)
{
    if(!r)return false;bool ok=true;
    for(unsigned i=0;i<CacheRooms;i++)if(!Save(r,&r->rooms[i]))ok=false;
    if(ok)r->last_flush=r->clock;return ok;
}
void IogMapRuntimeDestroy(IogMapRuntime*r)
{if(r){(void)IogMapRuntimeFlush(r);free(r->atlas);free(r);}}
static unsigned StaticCollision(const IogMapRuntimeFrame*f,unsigned flags,
    const CollisionLayers*l,unsigned index)
{
    unsigned value=f->ram[flags+f->ram[Word(f->ram,0x69e)+index]];
    if(l->secondary&&index<l->size1){
        unsigned overlay=f->ram[l->flags1+f->ram[l->map1+index]];
        if(overlay)value=overlay; /* original replacement, not flag OR */
    }
    return value;
}
static bool FrameShape(const IogMapRuntimeFrame*f,unsigned*w,unsigned*h,unsigned*flags,CollisionLayers*l)
{
    if(!f||!f->profile_verified||!f->ram||f->ram_bytes!=131072||!f->ppu||
       (f->ppu->bgmode&7)!=1||(f->ram[0x6ef]&8)||Word(f->ram,0x644)!=f->scene)return false;
    *w=Word(f->ram,0x692);*h=Word(f->ram,0x696);
    *flags=f->static_flags_address?f->static_flags_address:0x10000+Word(f->ram,0x6aa);
    memset(l,0,sizeof(*l));
    IogMapRuntimeRect a=f->authored;unsigned physical=(f->ram[0x6ee]>>7)&1;
    if(!*w||!*h||*w>4096||*h>4096||((*w|*h)&255)||
       !a.width||!a.height||((a.x|a.y|a.width|a.height)&15)||
       a.x>=*w||a.y>=*h||a.width>*w-a.x||a.height>*h-a.y||a.width/16>256||a.height/16>256||
       *flags<65536||*flags>131072-256||(*flags&255)||PPU_bigTiles(f->ppu,physical)||
       f->player_x<(int)a.x||f->player_y<(int)a.y||
       f->player_x>=(int)(a.x+a.width)||f->player_y>=(int)(a.y+a.height)||
       f->camera_x < -16||f->camera_y < -16||f->camera_x>(int)*w+16||f->camera_y>(int)*h+16)return false;
    unsigned size=(*w>>8)*(*h>>8)*256,map=Word(f->ram,0x69e),defs=Word(f->ram,0x6ae);
    if(size!=Word(f->ram,0x69a)||map+size>65536||defs+2048>65536)return false;
    l->secondary=(f->ram[0x6ef]&1)!=0;l->art_secondary=f->aligned_secondary_source;
    if(l->secondary||l->art_secondary){
        l->map1=Word(f->ram,0x6a0);l->definitions1=Word(f->ram,0x6b0);
        l->width1=Word(f->ram,0x694);l->height1=Word(f->ram,0x698);l->size1=Word(f->ram,0x69c);
        l->flags1=0x10000+Word(f->ram,0x6ac);
        if(!l->width1||!l->height1||l->width1>4096||l->height1>4096||
           ((l->width1|l->height1)&255)||l->size1!=(l->width1>>8)*(l->height1>>8)*256||
           l->map1+l->size1>65536||l->definitions1+2048>65536||
           l->flags1>131072-256||(l->flags1&255))return false;
        if(l->art_secondary&&PPU_bigTiles(f->ppu,(1-physical)))return false;
    }
    /* Bind reconstructed static geometry to the current live collision grid.
     * Proven F0 occupancy can overwrite the cell or preserve its static low
     * nibble (F1, etc.). Neither form removes the underlying static barrier.
     * Any other
     * unexplained script/dynamic difference hides the map, rather than letting
     * exploration spill through a barrier whose producer is not qualified. */
    unsigned bank=f->ram[0x82];if(bank!=0x7e&&bank!=0x7f)return false;
    unsigned live=(bank-0x7e)*65536+Word(f->ram,0x80);
    if(live>131072||size>131072-live)return false;
    for(unsigned y=a.y/16;y<(a.y+a.height)/16;y++)for(unsigned x=a.x/16;x<(a.x+a.width)/16;x++){
        unsigned index=(((y>>4)*(*w>>8)+(x>>4))<<8)+((y&15)<<4)+(x&15);
        unsigned actual=f->ram[live+index];
        unsigned expected=StaticCollision(f,*flags,l,index);
        if(actual!=expected&&actual!=0xf0&&
           !((actual&0xf0)==0xf0&&(actual&0x0f)==expected))return false;
    }
    return true;
}
static void IdentityFor(IogMapRuntime*r,const IogMapRuntimeFrame*f,unsigned w,unsigned h,unsigned flags,
    const CollisionLayers*l,IogMapDiscoveryIdentity*id,uint8_t key[32])
{
    unsigned map=Word(f->ram,0x69e),defs=Word(f->ram,0x6ae),size=Word(f->ram,0x69a);
    const unsigned values[24]={w,h,map,defs,size,flags,f->scene,f->authored.x,f->authored.y,
        f->authored.width,f->authored.height,16,8,3,l->secondary,l->width1,l->height1,
        l->map1,l->definitions1,l->size1,l->flags1,f->stable_source_identity,
        f->ram[0x6ee]&128,l->art_secondary};
    for(unsigned i=0;i<24;i++)Put32(r->hash_input+i*4,values[i]);
    size_t at=96;
    if(f->stable_source_identity){
        /* These are the scene loader's source-pointer cache slots, not the
         * mutable decompressed tile maps. The verified content ROM and these
         * asset sources bind the authored coordinate space while COP tile edits
         * change current art/collision without erasing remembered exploration. */
        memcpy(r->hash_input+at,f->ram+0x678,3);at+=3;
        memcpy(r->hash_input+at,f->ram+0x67e,3);at+=3;
        if(l->secondary||l->art_secondary){
            memcpy(r->hash_input+at,f->ram+0x67b,3);at+=3;
            memcpy(r->hash_input+at,f->ram+0x681,3);at+=3;
        }
        Put32(r->hash_input+at,Word(f->ram,0x6a2));at+=4;
        if(l->secondary||l->art_secondary){Put32(r->hash_input+at,Word(f->ram,0x6a4));at+=4;}
    }else{
    memcpy(r->hash_input+at,f->ram+map,size);at+=size;
    memcpy(r->hash_input+at,f->ram+defs,2048);at+=2048;
    memcpy(r->hash_input+at,f->ram+flags,256);at+=256;
    if(l->secondary||l->art_secondary){
        memcpy(r->hash_input+at,f->ram+l->map1,l->size1);at+=l->size1;
        memcpy(r->hash_input+at,f->ram+l->definitions1,2048);at+=2048;
        memcpy(r->hash_input+at,f->ram+l->flags1,256);at+=256;
    }
    }
    memcpy(id->content_sha256,f->content_sha256,32);sha256_compute(r->hash_input,at,id->layout_sha256);
    id->floor_id=(f->authored.y/16<<16)|(f->authored.x/16);
    memcpy(r->hash_input,id->content_sha256,32);memcpy(r->hash_input+32,id->layout_sha256,32);
    Put32(r->hash_input+64,id->floor_id);Put32(r->hash_input+68,f->authored.width/16);Put32(r->hash_input+72,f->authored.height/16);
    sha256_compute(r->hash_input,76,key);
}
static bool Eligible(const IogMapRuntimeFrame*f,unsigned x,unsigned y,int px,int py)
{
    int wx=(int)f->authored.x+(int)x*16,wy=(int)f->authored.y+(int)y*16;
    int dx=(int)x-px,dy=(int)y-py;
    return dx*dx+dy*dy<=64&&wx>=f->camera_x&&wy>=f->camera_y&&
        wx+16<=f->camera_x+256&&wy+16<=f->camera_y+224;
}
static void Reveal(IogMapRuntime*r,const IogMapRuntimeFrame*f,MapRoom*room)
{
    unsigned w=room->map.width,h=room->map.height;size_t cells=(size_t)w*h;
    memset(r->visibility,0,cells);memset(r->seen,0,cells);
    int px=(f->player_x-(int)f->authored.x)/16,py=(f->player_y-(int)f->authored.y)/16;
    r->player_x=px;r->player_y=py;
    unsigned head=0,tail=0,start=(unsigned)py*w+(unsigned)px;
    if(Eligible(f,(unsigned)px,(unsigned)py,px,py)){
        r->visibility[start]=1;r->seen[start]=1;
        if(r->walkable[start])r->queue[tail++]=(uint16_t)start;
    }
    while(head<tail){
        unsigned at=r->queue[head++],x=at%w,y=at/w;
        const int dx[4]={-1,1,0,0},dy[4]={0,0,-1,1};
        for(unsigned i=0;i<4;i++){
            int nx=(int)x+dx[i],ny=(int)y+dy[i];
            if(nx<0||ny<0||nx>=(int)w||ny>=(int)h||!Eligible(f,(unsigned)nx,(unsigned)ny,px,py))continue;
            unsigned n=(unsigned)ny*w+(unsigned)nx;if(r->seen[n])continue;
            r->seen[n]=r->visibility[n]=1;
            if(r->walkable[n])r->queue[tail++]=(uint16_t)n;
        }
    }
    size_t changed=0;
    if(IogMapDiscoveryReveal(&room->map,px,py,8,r->visibility,cells,w,&changed)&&changed){room->count+=changed;room->dirty=true;}
}
bool IogMapRuntimeUpdate(IogMapRuntime*r,const IogMapRuntimeFrame*f)
{
    if(!r)return false;r->visible=false;r->reason="unsupported_frame";
    unsigned w,h,flags;CollisionLayers layers;if(!FrameShape(f,&w,&h,&flags,&layers))return false;
    IogMapDiscoveryIdentity id;uint8_t key[32];IdentityFor(r,f,w,h,flags,&layers,&id,key);
    int found=-1,free_slot=-1,lru=0;
    for(int i=0;i<CacheRooms;i++){
        if(r->rooms[i].used&&!memcmp(key,r->rooms[i].key,32))found=i;
        if(!r->rooms[i].used)free_slot=i;
        if(r->rooms[i].age<r->rooms[lru].age)lru=i;
    }
    bool changed=found!=r->current;
    if(changed&&r->current>=0&&!Save(r,&r->rooms[r->current])){r->reason="storage_write_failed";return false;}
    if(found<0){
        found=free_slot>=0?free_slot:lru;
        if(!Save(r,&r->rooms[found])){r->reason="storage_write_failed";return false;}
        MapRoom*room=&r->rooms[found];memset(room,0,sizeof(*room));room->used=true;memcpy(room->key,key,32);
        if(!IogMapDiscoveryInit(&room->map,f->authored.width/16,f->authored.height/16,&id))return false;
        IogMapDiscovery disk;if(Load(r,room,&disk)){room->map=disk;room->count=Count(&disk);r->loads++;}
        changed=true;
    }
    r->current=found;r->clock++;MapRoom*room=&r->rooms[found];room->age=r->clock;
    unsigned characters=PPU_bgTileAdr(f->ppu,(f->ram[0x6ee]>>7)&1);
    unsigned map=Word(f->ram,0x69e),defs=Word(f->ram,0x6ae),size=Word(f->ram,0x69a);
    bool data_changed=memcmp(r->ram+map,f->ram+map,size)||memcmp(r->ram+defs,f->ram+defs,2048);
    unsigned secondary_characters=PPU_bgTileAdr(f->ppu,1-((f->ram[0x6ee]>>7)&1));
    if(layers.art_secondary)data_changed|=memcmp(r->ram+layers.map1,f->ram+layers.map1,layers.size1)||
        memcmp(r->ram+layers.definitions1,f->ram+layers.definitions1,2048);
    bool bank_changed=r->characters!=characters||r->art_secondary!=layers.art_secondary||
        (layers.art_secondary&&r->secondary_characters!=secondary_characters);
    bool pixels_changed=bank_changed||memcmp(r->vram,f->ppu->vram,sizeof(r->vram))||memcmp(r->cgram,f->ppu->cgram,sizeof(r->cgram));
    memcpy(r->ram,f->ram,sizeof(r->ram));memcpy(r->vram,f->ppu->vram,sizeof(r->vram));memcpy(r->cgram,f->ppu->cgram,sizeof(r->cgram));
    r->rect=f->authored;r->scene=f->scene;r->source_width=w;r->source_height=h;
    r->map_address=Word(f->ram,0x69e);r->definitions=Word(f->ram,0x6ae);r->characters=characters;
    r->art_secondary=layers.art_secondary;r->secondary_width=layers.width1;r->secondary_height=layers.height1;
    r->physical_primary=(f->ram[0x6ee]>>7)&1;
    r->secondary_map=layers.map1;r->secondary_definitions=layers.definitions1;r->secondary_characters=secondary_characters;
    for(unsigned y=0;y<room->map.height;y++)for(unsigned x=0;x<room->map.width;x++){
        unsigned tx=f->authored.x/16+x,ty=f->authored.y/16+y;
        unsigned at=r->map_address+(((ty>>4)*(w>>8)+(tx>>4))<<8)+((ty&15)<<4)+(tx&15);
        unsigned collision=StaticCollision(f,flags,&layers,at-r->map_address);
        r->walkable[y*room->map.width+x]=(uint8_t)(collision==0);
    }
    Reveal(r,f,room);r->atlas_dirty|=pixels_changed||changed||data_changed;
    if(changed||bank_changed||data_changed)r->last_atlas=0;
    r->visible=true;r->reason="ready_conservative_reachability";
    if(r->clock-r->last_flush>=300&&!IogMapRuntimeFlush(r))r->reason="ready_storage_write_failed";
    return true;
}
void IogMapRuntimeGetStatus(const IogMapRuntime*r,IogMapRuntimeStatus*out)
{
    if(!out)return;memset(out,0,sizeof(*out));if(!r){out->reason="no_runtime";return;}
    out->frame_valid=r->visible;out->storage_available=Directory(r->directory,true);out->reason=r->reason;
    out->accepted_frames=r->clock;out->persistent_writes=r->writes;out->persistent_loads=r->loads;
    if(!r->visible||r->current<0)return;
    const MapRoom*room=&r->rooms[r->current];out->scene=r->scene;out->authored=r->rect;
    out->player_cell_x=r->player_x;out->player_cell_y=r->player_y;out->grid_width=room->map.width;out->grid_height=room->map.height;
    out->cell_world_pixels=16;out->atlas_cell_pixels=8;out->explored_cells=room->count;
    memcpy(out->layout_sha256,room->map.identity.layout_sha256,32);out->floor_id=room->map.identity.floor_id;
}
bool IogMapRuntimeGetViewSource(IogMapRuntime*r,IogMapViewSource*out)
{
    if(!out)return false;memset(out,0,sizeof(*out));if(!r||!r->visible||r->current<0)return false;
    MapRoom*room=&r->rooms[r->current];size_t width=r->rect.width/2,height=r->rect.height/2,bytes=width*height*4;
    if(!r->atlas||r->atlas_capacity<bytes){
        uint8_t*next=realloc(r->atlas,bytes);if(!next){r->reason="atlas_allocation_failed";return false;}
        r->atlas=next;r->atlas_capacity=bytes;r->last_atlas=0;
    }
    if(!r->last_atlas||(r->atlas_dirty&&r->clock-r->last_atlas>=30)){
        IogMapScenerySource source={r->ram,sizeof(r->ram),r->vram,r->cgram,32768,256,
            r->source_width,r->source_height,r->map_address,r->definitions,r->characters};
        IogMapScenerySource secondary={r->ram,sizeof(r->ram),r->vram,r->cgram,32768,256,
            r->secondary_width,r->secondary_height,r->secondary_map,r->secondary_definitions,r->secondary_characters};
        bool rendered=r->art_secondary?
            IogMapSceneryRenderMode1Composite(&source,&secondary,r->physical_primary,r->rect.x,r->rect.y,
                r->rect.width,r->rect.height,2,(uint32_t*)r->atlas,bytes,width*4):
            IogMapSceneryRender(&source,r->rect.x,r->rect.y,r->rect.width,r->rect.height,2,(uint32_t*)r->atlas,bytes,width*4);
        if(!rendered){
            r->reason="atlas_decode_failed";return false;
        }
        unsigned backdrop=r->cgram[0],red=backdrop&31,green=(backdrop>>5)&31,blue=(backdrop>>10)&31;
        for(size_t i=0;i<bytes;i+=4){
            if(!r->atlas[i+3]){
                r->atlas[i]=(uint8_t)((blue<<3)|(blue>>2));r->atlas[i+1]=(uint8_t)((green<<3)|(green>>2));
                r->atlas[i+2]=(uint8_t)((red<<3)|(red>>2));r->atlas[i+3]=255;
            }
            uint8_t b=r->atlas[i];r->atlas[i]=r->atlas[i+2];r->atlas[i+2]=b;
        }
        r->last_atlas=r->clock;r->atlas_dirty=false;
    }
    *out=(IogMapViewSource){.discovery=&room->map,.scenery_rgba=r->atlas,.scenery_bytes=bytes,.scenery_stride=width*4,
        .scenery_cell_pixels=8,.walkable=r->walkable,.walkable_bytes=(size_t)room->map.width*room->map.height,
        .walkable_stride=room->map.width,.player_present=true,.player_x=(int16_t)r->player_x,.player_y=(int16_t)r->player_y};
    return true;
}
bool IogMapRuntimeDraw(IogMapRuntime*r,uint8_t*dst,size_t bytes,size_t stride,unsigned w,unsigned h,const IogMapViewSettings*v)
{IogMapViewSource source;return IogMapRuntimeGetViewSource(r,&source)&&IogMapViewRender(dst,bytes,stride,w,h,&source,v);}
