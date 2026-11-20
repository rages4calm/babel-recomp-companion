/* Companion content corrections for the received GaiaLabs preview.
 * GaiaLabs/Babel authorship and licenses remain with their respective authors.
 * Hand-authored semantic adapter; no guest instruction block or artwork.
 * These adapters preserve guest scene loading and interpreter fallback.
 */
#include "iog_received_content.h"
#include "common_cpu_infra.h"
#include "cpu_state.h"
#include "snes/snes.h"
#include "snes/cart.h"
#include "snes/interp_bridge.h"
#include "sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RECEIVED_ROM "dded02334752a7122d4db8da4df4aa56d6997c078065e69183865dc23202973f"
#define QUEUE_HASH "a3a9b932f724f73bfae5f17f6a57a6641d07d447e587545523c58f17712f22e6"
#define SOUTH_CAPE_HASH "9b78bff92c88b401fe0ce9e553ab3ba24e203824055d61e4ad4f5d0e34d0291c"
#define CLASSROOM_WARPS_HASH "cf17aee31207cabe1c47cac51662bde32e582f8da343a62987473e391264d88d"
#define WARP_SCAN_HASH "57d25b8f34de044bea641415c2eca3e43bd4c7a412b5b45f2b80d3e8a3e54a5f"
enum {
    ClassroomWestWarp = 0x8328,
    ClassroomEastWarp = ClassroomWestWarp + 12,
    ClassroomExtendedWarps = ClassroomEastWarp + 13,
    CheckStandardWarps = 0xd32a,
    CheckExtendedWarps = 0xd378,
    ExecuteStandardWarp = 0xd409,
    ExecuteExtendedWarp = 0xd4a1,
};
static struct { bool enabled, classroom, audit; unsigned long long fixes, refused; } content;

static unsigned Word(const uint8_t *p, unsigned a)
{ return p[a] | ((unsigned)p[a+1] << 8); }
static bool Matches(const void *p, size_t n, const char *pin)
{
    uint8_t hash[32]; char hex[65]; sha256_compute(p,n,hash);
    for(unsigned i=0;i<32;i++)snprintf(hex+2*i,3,"%02x",hash[i]);
    return !strcmp(hex,pin);
}
static bool CartShape(const Cart *cart)
{
    return cart && cart->rom && cart->type==CART_HIROM &&
        cart->romImageSize==3276800 && cart->romSize>=cart->romImageSize;
}
static bool BlocksMatch(const Cart *cart)
{
    return Matches(cart->rom+0xA340,92,QUEUE_HASH) &&
        Matches(cart->rom+0x3B569,12,SOUTH_CAPE_HASH);
}
static void Destination(CpuState *cpu, uint32_t pc)
{
    if(!content.enabled || !cpu || !cpu->ram)return;
    const Cart *cart=g_snes?g_snes->cart:NULL;
    const uint8_t *ram=cpu->ram;
    unsigned dp=cpu->D;
    unsigned pointer=Word(ram,dp+0xA)|((unsigned)ram[dp+0xC]<<16);
    /* Public wmcEnter_SouthCape is the unique world-map leaf at 03:B569.
     * COP dispatch retains the player actor's D=1000 and DB=81; its $0A
     * pointer is actor-relative, not global scratch RAM. COP #26 reads
     * inline operands through that pointer. At QueueMapChange's STA
     * warpDestX, $0A has advanced to the Y word at B56E, A is the X word,
     * and sceneNext is already 01. The remaining original handler, scene
     * loader and player spawn run unchanged. The expanded SouthCape layout
     * places all original cells 16 tiles / 256 pixels further right.
     * INC $0A produced the live flags; STA does not use/change those flags.
     * Only A changes here; next original LDA replaces it normally.
     */
    bool valid=(pc&0x3FFFFF)==0xA351 && (pointer&0x3FFFFF)==0x3B56E &&
        cpu->D==0x1000 && cpu->DB==0x81 &&
        !cpu->emulation && !cpu->m_flag && !cpu->x_flag && !(cpu->P&0x30) &&
        cpu->A==0x0178 && Word(ram,0x644)==0xFE && Word(ram,0x642)==1 &&
        CartShape(cart) && BlocksMatch(cart);
    if(!valid) {
        content.refused++;
        if(content.audit && content.refused<=16)fprintf(stderr,
            "{\"kind\":\"received-content-refused\",\"pc\":%u,\"pointer\":%u,\"D\":%u,\"DB\":%u,\"A\":%u,\"P\":%u,\"m\":%u,\"x\":%u,\"emulation\":%u,\"scene\":%u,\"next\":%u}\n",
            pc,pointer,cpu->D,cpu->DB,cpu->A,cpu->P,cpu->m_flag,cpu->x_flag,
            cpu->emulation,Word(ram,0x644),Word(ram,0x642));
        return;
    }
    cpu->A=0x0278;
    content.fixes++;
    if(content.audit)fprintf(stderr,
        "{\"kind\":\"received-content-destination\",\"fix\":\"southcape-expanded-world-entry\",\"source_scene\":254,\"destination_scene\":1,\"x_before\":376,\"x_after\":632,\"y\":64,\"fixes\":%llu}\n",content.fixes);
}
static void ClassroomDoors(CpuState *cpu, uint32_t pc)
{
    if(!content.enabled || !content.classroom || !cpu || !cpu->ram ||
        (pc & 0x3fffff) != (0x20000 | CheckStandardWarps) ||
        cpu->D || (cpu->DB & 0x3f) != 1 || cpu->emulation ||
        cpu->m_flag || cpu->x_flag || (cpu->P & 0x30))
        return;
    const uint8_t *ram=cpu->ram;
    if(Word(ram,0x644)!=8 || Word(ram,0x642)!=0 ||
        Word(ram,0xd4)!=ClassroomWestWarp || Word(ram,0xd6)!=ClassroomExtendedWarps)
        return;

    /* Use the engine's adjusted player coordinates. The west doorway's
     * two rows and the east step retain the existing destination records.
     * Misses enter the original extended scan, bypassing the old positions. */
    unsigned x=Word(ram,0x9a2), y=Word(ram,0x9a4);
    unsigned warp=0;
    if(x>=128 && x<=144 && y>=80 && y<=96)
        warp=ClassroomWestWarp;
    else if(x>=496 && x<=512 && y==144)
        warp=ClassroomEastWarp;

    unsigned bank=pc & 0xff0000;
    if(!warp) {
        interp_bridge_pre_opcode_redirect(bank | CheckExtendedWarps);
        return;
    }
    cpu->X=(uint16_t)warp;
    interp_bridge_pre_opcode_redirect(bank | ExecuteStandardWarp);
    if(content.audit)
        fprintf(stderr,"{\"kind\":\"received-classroom-exit\",\"door\":\"%s\",\"x\":%u,\"y\":%u}\n",
                warp==ClassroomWestWarp?"west":"east",x,y);
}
static void Finish(void)
{
    if(content.audit)fprintf(stderr,
        "{\"kind\":\"received-content-summary\",\"fixes\":%llu,\"refused_contexts\":%llu}\n",
        content.fixes,content.refused);
}
bool IogReceivedContentInitialize(void)
{
    if(content.enabled)return true;
    const Cart *cart=g_snes?g_snes->cart:NULL;
    const uint16_t endian=1;
    if(*(const uint8_t*)&endian!=1 || !CartShape(cart) ||
        strcmp(IOG_RECEIVED_REFERENCE_SHA256,RECEIVED_ROM) ||
        !Matches(cart->rom,cart->romImageSize,RECEIVED_ROM) || !BlocksMatch(cart))return false;
    static const uint32_t banks[]={0,0x400000,0x800000,0xC00000};
    for(unsigned i=0;i<4;i++)
        if(!interp_bridge_add_pre_opcode_hook(banks[i]|0xA351,Destination))return false;
    const char *classroom=getenv("IOG_RECEIVED_CLASSROOM_DOORS");
    content.classroom=(!classroom || strcmp(classroom,"0")) &&
        Matches(cart->rom+0x10000+ClassroomWestWarp,26,CLASSROOM_WARPS_HASH) &&
        Matches(cart->rom+0x20000+CheckStandardWarps,
                ExecuteExtendedWarp-CheckStandardWarps,WARP_SCAN_HASH);
    if(content.classroom) {
        for(unsigned i=0;i<4;i++)
            if(!interp_bridge_add_pre_opcode_hook(banks[i]|0x20000|CheckStandardWarps,
                                                ClassroomDoors))return false;
    }
    const char *audit=getenv("IOG_RECEIVED_CONTENT_AUDIT");
    content.audit=audit&&!strcmp(audit,"1");
    content.enabled=true;
    atexit(Finish);
    return true;
}
