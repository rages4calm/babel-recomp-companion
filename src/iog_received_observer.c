/* Opt-in private observation of one pinned received build. No guest writes,
 * generated dispatch, patches, sprite reconstruction or gameplay hooks. */
#include "iog_received_observer.h"
#include "common_cpu_infra.h"
#include "common_rtl.h"
#include "snes/snes.h"
#include "snes/cart.h"
#include "snes/ppu.h"
#include "snes/interp_bridge.h"
#include "sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#ifdef _WIN32
/* SDK types.h defines FORCEINLINE as plain C inline. Let WinNT supply its
 * own force-inline spelling inside the system-header boundary, then restore
 * the SDK macro. Otherwise MinGW emits duplicate WinNT helpers at -O0. */
#pragma push_macro("FORCEINLINE")
#undef FORCEINLINE
#include <windows.h>
#pragma pop_macro("FORCEINLINE")
#else
#include <sys/stat.h>
#include <unistd.h>
#endif

#define RECEIVED_ROM "dded02334752a7122d4db8da4df4aa56d6997c078065e69183865dc23202973f"
#define COMPOSE_HASH "70485bc087dd11937ebd8794a39b3c76638f135ea873b63bfda0639a943697ad"
#define BODY_HASH "dec96c815acd857455134a3ce2210678cc98285a62b196d912ae7c352756faa6"
enum { Budget=4*1024*1024, RamBytes=131072, StagingBytes=544,
       DirectBytes=512, ManualBytes=768, PacketBytes=24+RamBytes+2*StagingBytes+2*DirectBytes+ManualBytes+65536+512+8 };
static IogVisualReceivedIdentity live_identity;
static struct {
    int requested,ready;
    uint64_t epoch;
    uint8_t ram[131072],staging[544],published[544];
    Ppu ppu;
} live;
static struct {
    int enabled,pending,after,limit,captures;
    unsigned frame,entry_frame,start_frame,write_count,entry_pc,exit_pc;
    uint64_t entries,exits,pairs,mismatches,wrong_phase,unpublished,load_resets,unobserved_uploads,budget_refusals;
    size_t written;
    char directory[4096];
    FILE *journal;
    CpuState cpu;
    uint8_t ram[RamBytes],staging[StagingBytes],direct[DirectBytes],manual[ManualBytes],selected_direct[DirectBytes];
} s;

static unsigned Word(const uint8_t *p,unsigned a) {return p[a]|((unsigned)p[a+1]<<8);}
static unsigned DirectSource(unsigned scene)
{return scene==0xFE||(scene>=0x8C&&scene<0x90)?0x10600:0x11FC0;}
static void Hash(const void *p,size_t n,char out[65])
{
    uint8_t digest[32];sha256_compute(p,n,digest);
    for(unsigned i=0;i<32;i++)snprintf(out+2*i,3,"%02x",digest[i]);out[64]=0;
}
static int Matches(const void *p,size_t n,const char *pin)
{char hash[65];Hash(p,n,hash);return !strcmp(hash,pin);}

static int PrivateDirectory(const char *value)
{
    char root[4096],path[4096];
#ifdef _WIN32
    if(!_fullpath(root,IOG_RECEIVED_DIAGNOSTICS_ROOT,sizeof(root)) ||
       !_fullpath(path,value,sizeof(path)))return 0;
    size_t n=strlen(root);
    if(_strnicmp(path,root,n)||path[n]!='\\')return 0;
    for(char *p=path+3;;p++)if(*p=='\\'||!*p) {
        char saved=*p;*p=0;DWORD a=GetFileAttributesA(path);*p=saved;
        if(a==INVALID_FILE_ATTRIBUTES||(a&FILE_ATTRIBUTE_REPARSE_POINT))return 0;
        if(!saved) {if(!(a&FILE_ATTRIBUTE_DIRECTORY))return 0;break;}
    }
#else
    if(!realpath(IOG_RECEIVED_DIAGNOSTICS_ROOT,root)||!realpath(value,path))return 0;
    size_t n=strlen(root);if(strncmp(path,root,n)||path[n]!='/')return 0;
    /* Refuse aliases in the supplied path, not just in its resolved target. */
    if(value[0]!='/')return 0;
    char check[4096];if(strlen(value)>=sizeof(check))return 0;strcpy(check,value);
    for(char *p=check+1;;p++)if(*p=='/'||!*p) {
        char saved=*p;*p=0;struct stat st;int ok=lstat(check,&st);*p=saved;
        if(ok||S_ISLNK(st.st_mode))return 0;
        if(!saved) {if(!S_ISDIR(st.st_mode))return 0;break;}
    }
#endif
    if(strlen(path)>=sizeof(s.directory))return 0;strcpy(s.directory,path);return 1;
}

static void Finish(void)
{
    if(!s.journal)return;
    char line[1200];int n=snprintf(line,sizeof(line),
        "{\"kind\":\"summary\",\"frames\":%u,\"entries\":%llu,\"exits\":%llu,\"pairs\":%llu,\"captures\":%d,\"mismatches\":%llu,\"wrong_phase\":%llu,\"unpublished\":%llu,\"load_resets\":%llu,\"unobserved_uploads\":%llu,\"budget_refusals\":%llu,\"payload_bytes\":%zu,\"budget\":%u}\n",
        s.frame,(unsigned long long)s.entries,(unsigned long long)s.exits,
        (unsigned long long)s.pairs,s.captures,(unsigned long long)s.mismatches,
        (unsigned long long)s.wrong_phase,(unsigned long long)s.unpublished,
        (unsigned long long)s.load_resets,(unsigned long long)s.unobserved_uploads,
        (unsigned long long)s.budget_refusals,s.written,Budget);
    if(n>0&&(size_t)n<sizeof(line)&&s.written+(size_t)n<=Budget)fwrite(line,1,(size_t)n,s.journal);
    fclose(s.journal);s.journal=NULL;
}

static void Entry(CpuState *cpu,uint32_t pc)
{
    if(!s.enabled)return;s.entries++;
    if(s.pending)s.unpublished++;
    memcpy(s.ram,cpu->ram,sizeof(s.ram));s.cpu=*cpu;
    s.entry_frame=s.frame;s.entry_pc=pc;s.pending=1;s.after=0;
}
static void Exit(CpuState *cpu,uint32_t pc)
{
    if(!s.enabled)return;s.exits++;
    if(!s.pending||s.after){s.wrong_phase++;s.pending=s.after=0;return;}
    memcpy(s.staging,cpu->ram+0x422,sizeof(s.staging));
    memcpy(s.direct,cpu->ram+0x10600,sizeof(s.direct));
    memcpy(s.manual,cpu->ram+0x13100,sizeof(s.manual));s.after=1;
    memcpy(s.selected_direct,cpu->ram+DirectSource(Word(s.ram,0x644)),512);s.exit_pc=pc;
}

void IogReceivedObserverInitialize(void)
{
    const char *world=getenv("IOG_RECEIVED_WORLD_RENDERER");live.requested=world&&!strcmp(world,"1");
    const char *path=getenv("IOG_RECEIVED_OBSERVER_DIR");
    if(path && !*path)path=NULL;
    if(!path&&!live.requested)return;
    if(s.journal)return;
    const Cart *cart=g_snes?g_snes->cart:NULL;
    const uint16_t endian=1;
    if(*(const uint8_t*)&endian!=1 || !cart || cart->type!=CART_HIROM ||
       cart->romImageSize!=3276800 || cart->romSize<cart->romImageSize ||
       strcmp(IOG_RECEIVED_REFERENCE_SHA256,RECEIVED_ROM) ||
       !Matches(cart->rom,cart->romImageSize,RECEIVED_ROM) ||
       !Matches(cart->rom+0x3DAFE,118,COMPOSE_HASH) ||
       !Matches(cart->rom+0x1F179,54,BODY_HASH) || (path && !PrivateDirectory(path))) {
        fprintf(stderr,"[received-observer] refused identity, phase or private-directory binding\n");return;
    }
    if(live.requested && IogVisualReceivedVerify(cart->rom,cart->romImageSize,&live_identity)!=kIogVisualReady)return;
    s.limit=16;const char *cap=getenv("IOG_RECEIVED_OBSERVER_LIMIT");
    if(cap&&*cap){char *end;long v=strtol(cap,&end,10);if(*end||v<1||v>32)return;s.limit=(int)v;}
    const char *start=getenv("IOG_RECEIVED_OBSERVER_START_FRAME");
    if(start&&*start){char *end;unsigned long v=strtoul(start,&end,10);if(*end||v>1000000000ul)return;s.start_frame=(unsigned)v;}
    if(path) {
    char file[4200];snprintf(file,sizeof(file),"%s/received-observer.jsonl",s.directory);
    s.journal=fopen(file,"wx");if(!s.journal)return;
    const char *header="{\"kind\":\"identity\",\"schema\":\"received-oam-observation-v3\",\"rom_sha256\":\"" RECEIVED_ROM "\",\"compose_sha256\":\"" COMPOSE_HASH "\",\"body_lookup_sha256\":\"" BODY_HASH "\",\"read_only\":true}\n";
    size_t header_size=strlen(header);
    if(fwrite(header,1,header_size,s.journal)!=header_size){Finish();return;}
    s.written=header_size;
    } else s.limit=0;
    static const uint32_t banks[]={0x030000,0x430000,0x830000,0xC30000};
    for(unsigned i=0;i<4;i++)if(!interp_bridge_add_pre_opcode_hook(banks[i]|0xDAFE,Entry)||
        !interp_bridge_add_pre_opcode_hook(banks[i]|0xDB73,Exit)) {
        s.wrong_phase++;Finish();return;
    }
    s.enabled=1;atexit(Finish);
    fprintf(stderr,"[received-observer] pinned read-only phase capture enabled; max=%d budget=%u\n",s.limit,Budget);
}
void IogReceivedObserverFrame(void){if(s.enabled)s.frame++;}
void IogReceivedObserverReset(void)
{live.ready=0;if(s.enabled){s.pending=s.after=0;s.load_resets++;}}
void IogReceivedObserverBeforeNmi(void)
{if(s.enabled&&g_ppu)s.write_count=g_ppu->oamWriteCount;}

void IogReceivedObserverAfterNmi(void)
{
    if(!s.enabled||!g_ppu||g_ppu->oamWriteCount==s.write_count)return;
    if(live.requested)live.ready=0;
    if(!s.pending){s.unobserved_uploads++;return;}
    if(!s.after){s.wrong_phase++;s.pending=s.after=0;return;}
    uint8_t published[544];memcpy(published,g_ppu->oam,512);memcpy(published+512,g_ppu->highOam,32);
    if(memcmp(published,s.staging,544)){s.mismatches++;s.pending=s.after=0;return;}
    s.pairs++;
    if(live.requested) {
        memcpy(live.ram,s.ram,sizeof(live.ram));memcpy(live.staging,s.staging,544);
        memcpy(live.published,published,544);live.ppu=*g_ppu;live.epoch=s.pairs;live.ready=1;
    }
    if(s.entry_frame<s.start_frame||s.captures>=s.limit){s.pending=s.after=0;return;}
    unsigned scene=Word(s.ram,0x644),raw_count=Word(s.ram,0xDA);
    unsigned count=raw_count>512?512:raw_count,source=DirectSource(scene);
    unsigned direct_mode=!!(Word(s.ram,0x6EE)&0x1000),high_bits=scene==0xFF?0:2;
    int direct_shape=!(count&3),direct_prefix=0,hi_match=1;
    if(direct_shape)direct_prefix=!memcmp(s.ram+source,s.staging,count);
    for(unsigned i=0;direct_shape&&i<count/4;i++)
        if(((published[512+i/4]>>((i&3)*2))&3)!=high_bits)hi_match=0;
    char ramhash[65],stagehash[65],directhash[65];Hash(s.ram,sizeof(s.ram),ramhash);
    Hash(s.staging,sizeof(s.staging),stagehash);Hash(s.ram+source,512,directhash);
    char vramhash[65],cgramhash[65];Hash(g_ppu->vram,65536,vramhash);Hash(g_ppu->cgram,512,cgramhash);
    uint8_t ppu_regs[8]={g_ppu->obsel,g_ppu->bgmode,g_ppu->setini,g_ppu->cgadsub,g_ppu->cgwsel,0,0,0};
    char line[3000];int n=snprintf(line,sizeof(line),
        "{\"kind\":\"paired\",\"packet\":%d,\"epoch\":%llu,\"entry_calls\":%llu,\"exit_calls\":%llu,\"publication_pairs\":%llu,\"compose_frame\":%u,\"nmi_frame\":%u,\"scene\":%u,\"entry_pc\":%u,\"exit_pc\":%u,\"cpu\":{\"A\":%u,\"X\":%u,\"Y\":%u,\"S\":%u,\"D\":%u,\"DB\":%u,\"PB\":%u},\"all544_oam_match\":true,\"ram_sha256\":\"%s\",\"staging_sha256\":\"%s\",\"direct_before_sha256\":\"%s\",\"direct_mode\":%s,\"direct_source_ram_offset\":%u,\"direct_raw_bytes\":%u,\"direct_bytes\":%u,\"direct_shape_valid\":%s,\"direct_prefix_matches_staging\":%s,\"direct_high_bits_match\":%s,\"direct_full512_unchanged\":%s,\"manual_full768_unchanged\":%s,\"layout\":\"header24-RAM131072-staging544-direct0600After512-manualAfter768-selectedDirectAfter512-published544-vram65536-cgram512-ppuRegs8\",\"vram_sha256\":\"%s\",\"cgram_sha256\":\"%s\",\"graphics_phase\":\"same-NMI-post-OAM-publication-not-raster-palette\"}\n",
        s.captures,(unsigned long long)s.load_resets,(unsigned long long)s.entries,
        (unsigned long long)s.exits,(unsigned long long)s.pairs,
        s.entry_frame,s.frame,scene,s.entry_pc,s.exit_pc,s.cpu.A,s.cpu.X,s.cpu.Y,s.cpu.S,s.cpu.D,s.cpu.DB,s.cpu.PB,
        ramhash,stagehash,directhash,direct_mode?"true":"false",source,raw_count,count,direct_shape?"true":"false",
        direct_prefix?"true":"false",hi_match?"true":"false",
        !memcmp(s.ram+source,s.selected_direct,512)?"true":"false",
        !memcmp(s.ram+0x13100,s.manual,768)?"true":"false",vramhash,cgramhash);
    if(n<=0||(size_t)n>=sizeof(line)||s.written+PacketBytes+(size_t)n+4096>Budget){s.budget_refusals++;s.pending=s.after=0;return;}
    char path[4200];snprintf(path,sizeof(path),"%s/received-packet-%02d.bin",s.directory,s.captures);
    FILE *file=fopen(path,"wbx");if(!file){s.wrong_phase++;s.pending=s.after=0;return;}
    uint32_t header[6]={0x314F4752,3,s.entry_frame,s.frame,Word(s.ram,0x644),PacketBytes};
    int ok=fwrite(header,1,24,file)==24 && fwrite(s.ram,1,sizeof(s.ram),file)==sizeof(s.ram) &&
        fwrite(s.staging,1,sizeof(s.staging),file)==sizeof(s.staging) &&
        fwrite(s.direct,1,sizeof(s.direct),file)==sizeof(s.direct) &&
        fwrite(s.manual,1,sizeof(s.manual),file)==sizeof(s.manual) &&
        fwrite(s.selected_direct,1,sizeof(s.selected_direct),file)==sizeof(s.selected_direct) &&
        fwrite(published,1,sizeof(published),file)==sizeof(published) &&
        fwrite(g_ppu->vram,1,65536,file)==65536 && fwrite(g_ppu->cgram,1,512,file)==512 &&
        fwrite(ppu_regs,1,sizeof(ppu_regs),file)==sizeof(ppu_regs);
    if(fclose(file))ok=0;
    if(!ok){s.wrong_phase++;s.enabled=0;return;}
    if(fwrite(line,1,(size_t)n,s.journal)!=(size_t)n){s.enabled=0;return;}fflush(s.journal);
    s.written+=PacketBytes+(size_t)n;s.captures++;s.pending=s.after=0;
}

bool IogReceivedObserverPicture(IogVisualReceivedSource *out)
{
    if(!out || !live.requested || !live.ready)return false;
    *out=(IogVisualReceivedSource){live.ram,sizeof(live.ram),&live.ppu,&live_identity,
        live.staging,live.published,544,544,live.epoch,live.epoch,
        (uint16_t)((Word(live.ram,0x6ee)&0x1000)?Word(live.ram,0xda):0)};
    return true;
}
