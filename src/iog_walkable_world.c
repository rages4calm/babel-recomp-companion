/* Original-compatible world travel, based on the GaiaLabs walkable-world-map
 * module by the GaiaLabs Team. The approved collision data is imported locally.
 * This adapter uses the Original actors, perspective producer and scene loader. */
#include "iog_walkable_world.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common_cpu_infra.h"
#include "cpu_state.h"
#include "iog_randomizer.h"
#include "iog_world_renderer.h"
#include "sha256.h"
#include "snes/cart.h"
#include "snes/interp_bridge.h"
#include "snes/snes.h"
#include "snes_overlay_draw.h"

enum {
    kWorldScene = 0xFE,
    kMapChoice = 0x0D58,
    kRoute = 0x0D5A,
    kCameraAngle = 0xBC,
    kMapX = 0xCA,
    kMapY = 0xCC,
    /* Scratch used by the diary only in scene FA. It belongs to this
     * controller while the exact scene FE actors are held. */
    kScratch = 0x0D76,
    kLeader = 0x0D78,
    kFracX = 0x0D7A,
    kFracY = 0x0D7C,
    kMarker = 0x0D7E,
    kMarkerCheck = 0x0D80,
    kWalking = 0x0D82,
    kMenuActor = 0xA31E,
    kCheckForMenu = 0xA38F,
    kTiltWithoutTitle = 0xA3BD,
    kAfterTilt = 0xA3D7,
    kIdleReturn = 0xA3A3,
    kLeaderAnimate = 0xA497,
    kCheckRoute = 0xA4BA,
    kContinueAnimation = 0xA4BF,
};
typedef struct WorldDestination {
    uint16_t x, y;
    uint16_t original_operands;
    const char *name;
} WorldDestination;

/* Positions from the approved map; transition operands from the Original
 * menu, whose stock payload also supplies revival when the flag requests it. */
static const WorldDestination destinations[] = {
    {0x0D4,0x3A8,0xB95B,"South Cape"}, {0x105,0x338,0xB96B,"Edward's Castle"},
    {0x0C6,0x2BA,0xB97B,"Itory Village"}, {0x134,0x284,0xB9AB,"Inca Ruins"},
    {0x254,0x2D4,0xB9CB,"Freejia"}, {0x334,0x334,0xB9BB,"Diamond Mine"},
    {0x384,0x164,0xB9EB,"Angel Village"}, {0x2D4,0x1A4,0xB9DB,"Watermia"},
    {0x2A4,0x124,0xB9FB,"Great Wall"}, {0x1D4,0x134,0xBA21,"City of Euro"},
    {0x214,0x0B4,0xBA47,"Mt. Temple"}, {0x124,0x1A4,0xBA67,"Natives' Village"},
    {0x134,0x154,0xBA87,"Angkor Wat"}, {0x094,0x114,0xBAC7,"Desert Village Dao"},
    {0x074,0x0B4,0xBAB7,"Pyramid"},
};
#define DEST(n) (1u << (n))
/* Preserve the stock visit choices for this story stage. Four destinations
 * outside the stock menu stay in their original story-driven routes. */
static const uint16_t allowed[] = {
    0, DEST(0)|DEST(1), DEST(0)|DEST(2), DEST(1)|DEST(0), DEST(2)|DEST(0),
    DEST(3)|DEST(2), DEST(2)|DEST(3), DEST(4)|DEST(5), DEST(5)|DEST(4), DEST(4),
    DEST(6)|DEST(7), DEST(7)|DEST(6), DEST(7)|DEST(6)|DEST(8), DEST(8)|DEST(7),
    DEST(7)|DEST(6)|DEST(8)|DEST(9), DEST(9)|DEST(7), DEST(9)|DEST(7)|DEST(10),
    DEST(10)|DEST(9), DEST(11)|DEST(9), DEST(11)|DEST(9)|DEST(12), DEST(12)|DEST(11),
    DEST(6), DEST(13)|DEST(11), DEST(13)|DEST(11)|DEST(14), DEST(14)|DEST(13),
    DEST(11)|DEST(9)|DEST(12)|DEST(13), DEST(9)|DEST(7)|DEST(10)|DEST(11), DEST(0)
};
#undef DEST
/* DialogueOptions dispatch index zero in each of the 27 stock menus.
 * Shared exits can use a different Quit scene from the physical origin. */
static const uint8_t quit[] = {
    0, 0, 0, 1, 2, 3, 2, 4, 5, 4, 6, 7, 7, 8,
    7, 9, 9, 10, 11, 11, 12, 6, 13, 13, 14, 11, 9, 0
};

static struct {
    const Cart *cart;
    const uint8_t *rom;
    bool configured;
    uint8_t collision[2048];
} world;
static const char stock_hash[] =
    "32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd";

static unsigned Word(const uint8_t *data, unsigned at)
{
    return data[at] | ((unsigned)data[at+1] << 8);
}
static void Put(uint8_t *ram, unsigned at, unsigned word)
{
    ram[at] = (uint8_t)word;
    ram[at+1] = (uint8_t)(word >> 8);
}
static bool HasIdentity(const uint8_t *data, size_t size, const char *pin)
{
    uint8_t hash[32];
    char hex[65];
    sha256_compute(data,size,hash);
    for(unsigned i=0;i<32;i++)snprintf(hex+i*2,3,"%02x",hash[i]);
    return !strcmp(hex,pin);
}
static bool LiveCart(void)
{
    return world.cart && g_snes && g_snes->cart == world.cart &&
        world.cart->rom == world.rom && world.cart->romImageSize == 0x200000 &&
        !IogRandomizerActive();
}
static bool StockCodeUsable(void)
{
    /* MSU and text overrides may change unrelated data after the full-image
     * boot check. Revalidate the stock actor, destinations and trigonometry
     * when entering this scene rather than requiring unmodified audio/text. */
    return
        HasIdentity(world.rom+0x3a2f1,531,
            "9a0a590d05de2085ada4b2bf43c6a3115f9d471014bb9d68cb1e3c2cf20c13ec") &&
        HasIdentity(world.rom+0x3b957,393,
            "768d073e42403be6b6cdfa67051fd40201eb1e41eb5c3eb57ed86e6377ebd3f5") &&
        HasIdentity(world.rom+0x1c595,1024,
            "9ec7f751200e5c3a178296675b1a38e4c8299c3315b57d3dd0f316f889573eed");
}
static bool RuntimeAllowed(void)
{
    return world.configured && (!IogWorldEnabled() || IogWorldStockVerified());
}
static bool Marked(const uint8_t *ram)
{
    return Word(ram,kMarker)==0x574d && Word(ram,kMarkerCheck)==0x4741;
}
static bool MenuChoice(const uint8_t *ram)
{
    unsigned choice=Word(ram,kMapChoice);
    return choice>0 && choice<sizeof(allowed)/sizeof(allowed[0]);
}
static bool ActorSlot(unsigned slot)
{
    return slot>=0x1000 && slot<0x1fc0 && (slot-0x1000)%0x30==0;
}
static void ClearMarker(uint8_t *ram)
{
    memset(ram+kScratch,0,kWalking+2-kScratch);
}
static void SyncView(uint8_t *ram)
{
    unsigned x=(Word(ram,kMapX)-128)&0xffff, y=(Word(ram,kMapY)-112)&0xffff;
    Put(ram,0x68a,x); Put(ram,0x68e,y);
    Put(ram,0x6be,x); Put(ram,0x6c2,y);
    Put(ram,0x6c6,0x8000|x); Put(ram,0x6ca,0x8000|y);
}
static void ObserveActors(CpuState *cpu,uint32_t pc)
{
    uint8_t *ram=cpu->ram;
    if(!LiveCart() || !RuntimeAllowed() || !ram ||
        Word(ram,0x644)!=kWorldScene || !MenuChoice(ram) || Word(ram,kRoute) ||
        !ActorSlot(cpu->D) || cpu->emulation || cpu->m_flag || cpu->x_flag)
        return;
    unsigned site=pc&0xffff, bank=pc&0xff0000;
    unsigned slot=cpu->D;
    if(site==kMenuActor) {
        if(!Marked(ram)) {
            /* First stock menu yield. Leave the actor re-entry unmodified so
             * it can run the original menu when walking is switched off. */
            if(Word(ram,0x642) || Word(ram,kMarker) || Word(ram,kMarkerCheck) ||
                !StockCodeUsable())return;
            ClearMarker(ram);
            Put(ram,kMarker,0x574d); Put(ram,kMarkerCheck,0x4741);
        }
        interp_bridge_pre_opcode_redirect(bank|kIdleReturn);
    } else if(Marked(ram) && site==kCheckForMenu) {
        Put(ram,kLeader,slot);
        /* Bypass the Mode 1 menu and the automatic route's name actor.
         * Retain the original 93-tick tilt and original sprite. */
        interp_bridge_pre_opcode_redirect(bank|kTiltWithoutTitle);
    } else if(Marked(ram) && Word(ram,kLeader) && !Word(ram,kWalking) &&
              site==kAfterTilt) {
        Put(ram,kLeader,slot);
        Put(ram,slot+0x10,Word(ram,slot+0x10)&~0x2000);
        Put(ram,slot+0x24,0x7080);
        Put(ram,slot+0x28,Word(ram,0x0d60));
        Put(ram,0xda,0);
        Put(ram,kWalking,1);
        SyncView(ram);
        interp_bridge_pre_opcode_redirect(bank|kLeaderAnimate);
    } else if(Marked(ram) && Word(ram,kWalking) && slot==Word(ram,kLeader) &&
              site==kCheckRoute) {
        /* Keep the stock animator and positioning loop. Its original route
         * test would remove the actor because there is no auto-route. */
        interp_bridge_pre_opcode_redirect(bank|kContinueAnimation);
    }
}

bool IogWalkableWorldInitialize(void)
{
    static const char collision_hash[] =
        "ef5d12e71f00725eecef1747a8093bed20f993b4c4c681921a9f2275251abcbb";
    const Cart *cart=g_snes?g_snes->cart:NULL;
    world.cart=NULL;
    world.rom=NULL;
    world.configured=false;
    if(!cart || cart->type!=CART_HIROM || cart->romImageSize!=0x200000 ||
        !cart->rom || !HasIdentity(cart->rom,cart->romImageSize,stock_hash))
        return false;
    world.cart=cart;
    world.rom=cart->rom;
    const char *path=getenv("IOG_WALKABLE_MAP_DATA");
    const char *enabled=getenv("IOG_WALKABLE_MAP");
    if(!path || !*path || (enabled && !strcmp(enabled,"0")))return false;
    FILE *file=fopen(path,"rb");
    if(!file)return false;
    bool read=fread(world.collision,1,sizeof(world.collision),file)==sizeof(world.collision)
        && fgetc(file)==EOF && !ferror(file);
    fclose(file);
    if(!read || !HasIdentity(world.collision,sizeof(world.collision),collision_hash))
        return false;
    const unsigned sites[]={kMenuActor,kCheckForMenu,kAfterTilt,kCheckRoute};
    const unsigned banks[]={0x030000,0x430000,0x830000,0xc30000};
    for(unsigned i=0;i<sizeof(sites)/sizeof(sites[0]);i++)
        for(unsigned j=0;j<sizeof(banks)/sizeof(banks[0]);j++)
            if(!interp_bridge_add_pre_opcode_hook(banks[j]|sites[i],ObserveActors))
                return false;
    return world.configured=true;
}

static bool EventFlag(const uint8_t *ram,unsigned flag)
{
    return (ram[0xa00+flag/8] & (1u<<(flag%8)))!=0;
}
static bool Blocked(const uint8_t *ram,int x,int y)
{
    if(x<32 || y<32 || x>=992 || y>=992)return true;
    unsigned column=(unsigned)x/16,row=(unsigned)y/16;
    if(!EventFlag(ram,0x26) &&
        ((row==0x2e && column>=0x0b && column<=0x0e) ||
         (EventFlag(ram,0x25) && row>=0x38 && row<=0x3a && column>=0x0a && column<=0x10)))
        return true;
    unsigned cell=world.collision[row*32+column/2];
    return ((cell>>(4*(column%2)))&15)!=0;
}
static int Velocity(unsigned table,unsigned angle)
{
    int sample=(int16_t)Word(world.rom,table+angle*2);
    /* Convert the Original Q15 sample to the module's signed Q8.8 speed. */
    return -(sample+(sample<0?-32:32))/64;
}
static void Move(uint8_t *ram,unsigned angle,int direction)
{
    int x=(int)Word(ram,kMapX), y=(int)Word(ram,kMapY);
    int fx=x*256+(int)Word(ram,kFracX)+direction*Velocity(0x1c595,angle);
    int fy=y*256+(int)Word(ram,kFracY)+direction*Velocity(0x1c695,angle);
    int next_x=fx/256,next_y=fy/256;
    Put(ram,kFracX,(unsigned)fx&255); Put(ram,kFracY,(unsigned)fy&255);
    if(!Blocked(ram,next_x,next_y)) {
        Put(ram,kMapX,(unsigned)next_x); Put(ram,kMapY,(unsigned)next_y);
    } else if(!Blocked(ram,next_x,y)) {
        Put(ram,kMapX,(unsigned)next_x);
    } else if(!Blocked(ram,x,next_y)) {
        Put(ram,kMapY,(unsigned)next_y);
    }
}
static bool DestinationAllowed(const uint8_t *ram, unsigned choice, unsigned index)
{
    if (!(allowed[choice] & (1u << index))) return false;
    /* From Itory, the event opens both the road and South Cape's entrance.
     * Saved positions can already be inside the entrance's radius. */
    return choice != 4 || index != 0 || EventFlag(ram, 0x26);
}
static const WorldDestination *Nearby(const uint8_t *ram)
{
    unsigned choice=Word(ram,kMapChoice);
    int x=(int)Word(ram,kMapX),y=(int)Word(ram,kMapY),best=48;
    if(!MenuChoice(ram))return NULL;
    const WorldDestination *selected=NULL;
    for(unsigned i=0;i<sizeof(destinations)/sizeof(destinations[0]);i++) {
        if(!DestinationAllowed(ram,choice,i))continue;
        const WorldDestination *destination=&destinations[i];
        int dx=abs((int)destination->x-x),dy=abs((int)destination->y-y);
        if(dx<24 && dy<24 && dx+dy<best) {
            best=dx+dy;
            selected=destination;
        }
    }
    return selected;
}
static void Enter(uint8_t *ram,const WorldDestination *destination)
{
    unsigned at=0x030000u|destination->original_operands;
    unsigned flags=world.rom[at+5];
    Put(ram,0x064c,Word(world.rom,at+1));
    Put(ram,0x064e,Word(world.rom,at+3));
    Put(ram,0x0650,flags&0x7f);
    Put(ram,0x0652,Word(world.rom,at+6));
    if(flags&0x80) {
        Put(ram,0x0af0,destination->original_operands);
        Put(ram,0x0af4,destination->original_operands);
        Put(ram,0x0af2,0x83); Put(ram,0x0af6,0x83);
    }
    Put(ram,0x064a,0x0400);
    /* Match WorldMapController.ClearWorldMapState before the loader
     * uses its next-scene payload. Leave the origin tag at $0D6F alone. */
    memset(ram+0x0d52,0,0x1c);
    ClearMarker(ram);
    /* Publish last: the main loop owns fades, scene actors and collision. */
    Put(ram,0x0642,world.rom[at]);
}
static void ReturnToOrigin(uint8_t *ram)
{
    if(!MenuChoice(ram) || Word(ram,0x642) || !StockCodeUsable())return;
    /* A walkable checkpoint can have already skipped the stock menu's
     * raster thinker. Use its original Quit destination via the ordinary
     * loader; the next normal map entry will open the stock menu. */
    Enter(ram,&destinations[quit[Word(ram,kMapChoice)]]);
}
bool IogWalkableWorldActive(void)
{
    const uint8_t *ram=LiveCart()?g_snes->ram:NULL;
    return RuntimeAllowed() && ram && Word(ram,0x644)==kWorldScene &&
        !Word(ram,0x642) && Marked(ram) && Word(ram,kWalking)==1;
}
const char *IogWalkableWorldLocation(void)
{
    if(!IogWalkableWorldActive())return NULL;
    const WorldDestination *destination=Nearby(g_snes->ram);
    return destination?destination->name:NULL;
}
bool IogWalkableWorldDirection(char *text,size_t capacity)
{
    if(!IogWalkableWorldActive() || !MenuChoice(g_snes->ram))return false;
    const uint8_t *ram=g_snes->ram;
    unsigned choice=Word(ram,kMapChoice),origin=ram[0x0d6f];
    int x=(int)Word(ram,kMapX),y=(int)Word(ram,kMapY);
    int best=INT32_MAX;
    const WorldDestination *target=NULL;
    for(unsigned i=0;i<sizeof(destinations)/sizeof(destinations[0]);i++) {
        if(!DestinationAllowed(ram,choice,i))continue;
        const WorldDestination *destination=&destinations[i];
        if(world.rom[0x030000u|destination->original_operands]==origin)continue;
        int dx=(int)destination->x-x,dy=(int)destination->y-y;
        int distance=abs(dx)+abs(dy);
        if(distance<best) {
            best=distance;
            target=destination;
        }
    }
    if(!target)return false;
    unsigned angle=Word(ram,kCameraAngle)&511;
    int vx=Velocity(0x1c595,angle),vy=Velocity(0x1c695,angle);
    int dx=(int)target->x-x,dy=(int)target->y-y;
    int forward=vx*dx+vy*dy,left=vy*dx-vx*dy;
    const char *direction=abs(forward)>=abs(left)
        ?(forward>=0?"Ahead":"Behind")
        :(left>=0?"Left":"Right");
    int written=snprintf(text,capacity,"%s: %s",target->name,direction);
    return written>=0 && (size_t)written<capacity;
}
void IogWalkableWorldTick(void)
{
    uint8_t *ram=LiveCart()?g_snes->ram:NULL;
    if(!ram || !Marked(ram))return;
    if(Word(ram,0x644)!=kWorldScene)return;
    if(!RuntimeAllowed()) {
        ReturnToOrigin(ram);
        return;
    }
    if(!IogWalkableWorldActive())return;
    unsigned input=g_snes->input1_currentState,angle=Word(ram,kCameraAngle)&511;
    if(input&SNES_PAD_LEFT)angle=(angle+4)&511;
    if(input&SNES_PAD_RIGHT)angle=(angle+508)&511;
    Put(ram,kCameraAngle,angle);
    if(input&SNES_PAD_UP)Move(ram,angle,1);
    if(input&SNES_PAD_DOWN)Move(ram,angle,-1);
    SyncView(ram);
    if(input&SNES_PAD_B) {
        const WorldDestination *destination=Nearby(ram);
        if(destination)Enter(ram,destination);
    }
}
