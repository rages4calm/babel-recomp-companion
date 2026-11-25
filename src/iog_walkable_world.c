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
#include "iog_map_ui.h"
#include "iog_world_renderer.h"
#include "sha256.h"
#include "snes/cart.h"
#include "snes/interp_bridge.h"
#include "snes/mode7_hd.h"
#include "snes/ppu.h"
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
    /* Stock camera words (divisor at the top line, growth per line) and the
     * pair the tilt leaves them at. The enhanced view keeps the same ratio,
     * so the horizon stays where it was while the camera sits twice as high. */
    kCameraDivisor = 0xB8,
    kCameraIncrement = 0xB6,
    kStockDivisor = 177,
    kStockIncrement = 1019,
    kHighDivisor = 25,
    kHighIncrement = 650,
};
int IogWorldMapEnhancedGet(void); /* iog_mods.c */
int IogHostPadLabel(uint32_t snes_bit,char label[8],uint32_t *color); /* iog_settings.c */
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
bool IogWalkableWorldEnhanced(void)
{
    /* IOG_WORLD_MAP_ENHANCED=0/1 overrides the setting for tests. */
    static int forced=-2;
    if(forced==-2) {
        const char *value=getenv("IOG_WORLD_MAP_ENHANCED");
        forced=value && *value?strcmp(value,"0")!=0:-1;
    }
    return forced>=0?forced!=0:IogWorldMapEnhancedGet()!=0;
}
static unsigned help_ticks; /* frames walked since arriving on the map */
static void BeginWalking(uint8_t *ram,unsigned slot)
{
    help_ticks=0;
    Put(ram,kLeader,slot);
    Put(ram,slot+0x10,Word(ram,slot+0x10)&~0x2000);
    Put(ram,slot+0x24,0x7080);
    Put(ram,slot+0x28,Word(ram,0x0d60));
    Put(ram,0xda,0);
    Put(ram,kWalking,1);
    SyncView(ram);
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
        if(IogWalkableWorldEnhanced()) {
            /* The stock tilt holds the player for 93 ticks. Start walking
             * now and let the tick ease the camera down instead; the tilt
             * loop's per-tick delta is cleared as its own exit does. */
            Put(ram,0x1002e + slot,0);
            BeginWalking(ram,slot);
            interp_bridge_pre_opcode_redirect(bank|kLeaderAnimate);
            return;
        }
        /* Bypass the Mode 1 menu and the automatic route's name actor.
         * Retain the original 93-tick tilt and original sprite. */
        interp_bridge_pre_opcode_redirect(bank|kTiltWithoutTitle);
    } else if(Marked(ram) && Word(ram,kLeader) && !Word(ram,kWalking) &&
              site==kAfterTilt) {
        BeginWalking(ram,slot);
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
    /* Eight 45-degree sectors: 53/128 is the tangent of 22.5 degrees. A
     * four-way hint kept saying Ahead while the road ran 45 degrees off. */
    static const char *const sectors[3][3]={
        {"Behind left","Behind","Behind right"},
        {"Left","Ahead","Right"},
        {"Ahead left","Ahead","Ahead right"}};
    int along=abs(left)*128<=abs(forward)*53,across=abs(forward)*128<=abs(left)*53;
    const char *direction=sectors[across?1:forward>=0?2:0][along?1:left>=0?0:2];
    int written=snprintf(text,capacity,"%s: %s",target->name,direction);
    return written>=0 && (size_t)written<capacity;
}
static int CameraStep(int delta)
{
    int step=delta/8;
    return step?step:(delta>0)-(delta<0);
}
static void EaseCamera(uint8_t *ram)
{
    /* With the setting off the tilt already ended on the stock pair and
     * nothing is written. A save made with the other setting eases across. */
    bool high=IogWalkableWorldEnhanced();
    int divisor=(int)Word(ram,kCameraDivisor),increment=(int)Word(ram,kCameraIncrement);
    int want_divisor=high?kHighDivisor:kStockDivisor;
    int want_increment=high?kHighIncrement:kStockIncrement;
    if(divisor==want_divisor && increment==want_increment)return;
    Put(ram,kCameraDivisor,(unsigned)(divisor+CameraStep(want_divisor-divisor)));
    Put(ram,kCameraIncrement,(unsigned)(increment+CameraStep(want_increment-increment)));
}
void IogWalkableWorldTick(void)
{
    IogWorldSetMapEnhanced(IogWalkableWorldEnhanced());
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
    EaseCamera(ram);
    if(help_ticks<0xffff)help_ticks++;
    if(input&SNES_PAD_UP)Move(ram,angle,1);
    if(input&SNES_PAD_DOWN)Move(ram,angle,-1);
    SyncView(ram);
    if(input&SNES_PAD_B) {
        const WorldDestination *destination=Nearby(ram);
        if(destination)Enter(ram,destination);
    }
}

/* ---- Enhanced view: markers, minimap and prompt plate --------------------
 * Host presentation only. Drawn in the widescreen frame with the overlay
 * font and plain shapes, in the cream-on-umber of the game's own boxes. */
enum {
    kInk = 0xff1c140a, kCream = 0xfff2dda4, kGold = 0xffffc64a,
    kShut = 0xff8f8672, kPlate = 0x241a0e, kMini = 56
};
static void Shade(uint32_t *dst,int stride,int width,int height,
    int x0,int y0,int w,int h,uint32_t rgb,unsigned part)
{
    for(int y=y0<0?0:y0;y<y0+h && y<height;y++)
        for(int x=x0<0?0:x0;x<x0+w && x<width;x++) {
            uint32_t under=dst[y*stride+x],out=0xff000000u;
            for(unsigned shift=0;shift<24;shift+=8) {
                unsigned a=(under>>shift)&255,b=(rgb>>shift)&255;
                out|=((a*(256-part)+b*part)>>8)<<shift;
            }
            dst[y*stride+x]=out;
        }
}
static void Label(uint32_t *dst,int stride,int height,int x,int y,
    const char *text,uint32_t color,int scale)
{
    for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++)
        if(dx||dy)snes_ovl_draw_text(dst,stride,height,x+dx*scale,y+dy*scale,text,kInk,scale);
    snes_ovl_draw_text(dst,stride,height,x,y,text,color,scale);
}
/* Where a map point lands in the native 256x224 field under the current
 * camera: the inverse of the perspective producer about its pivot (128,112). */
static bool Project(const uint8_t *ram,int map_x,int map_y,double *x,double *y)
{
    unsigned angle=Word(ram,kCameraAngle)&511;
    double c=(int16_t)Word(world.rom,0x1c695+angle*2)/32768.0;
    double s=(int16_t)Word(world.rom,0x1c595+angle*2)/32768.0;
    double u=map_x-(int)Word(ram,kMapX),w=map_y-(int)Word(ram,kMapY);
    double across=c*u-s*w,down=s*u+c*w;
    double divisor=Word(ram,kCameraDivisor),increment=Word(ram,kCameraIncrement);
    double reach=128.0-down*increment/256.0;
    if(reach<8.0)return false; /* at or past the horizon */
    *y=(down*divisor+14336.0)/reach;
    double scale=128.0/(divisor+increment**y/256.0);
    if(scale<=0)return false;
    *x=128.0+across/scale;
    return true;
}
static void Marker(uint32_t *dst,int stride,int height,int x,int y,
    const char *name,bool open)
{
    uint32_t color=open?kGold:kShut;
    /* A pin: stem from the ground point, diamond head, name above. */
    snes_ovl_fill_rect(dst,stride,height,x-1,y-13,3,13,kInk);
    snes_ovl_fill_rect(dst,stride,height,x,y-12,1,12,color);
    for(int r=-5;r<=5;r++) {
        int half=5-abs(r);
        snes_ovl_fill_rect(dst,stride,height,x-half,y-18+r,half*2+1,1,kInk);
    }
    for(int r=-3;r<=3;r++) {
        int half=3-abs(r);
        snes_ovl_fill_rect(dst,stride,height,x-half,y-18+r,half*2+1,1,color);
    }
    Label(dst,stride,height,x-4*snes_ovl_text_len(name),y-35,name,open?kCream:kShut,1);
}
static void Minimap(uint32_t *dst,int stride,int width,int height,const uint8_t *ram)
{
    static uint32_t picture[kMini*kMini];
    static unsigned age;
    const Ppu *ppu=g_snes->ppu;
    if(!ppu)return;
    if(age++%60==0) {
        /* The flat map itself, four texels averaged per pixel. */
        for(int j=0;j<kMini;j++)for(int i=0;i<kMini;i++) {
            unsigned red=0,green=0,blue=0;
            for(int n=0;n<4;n++) {
                int u=(i*2+(n&1))*1024/(kMini*2)+4,v=(j*2+(n>>1))*1024/(kMini*2)+4;
                unsigned color=ppu->cgram[SnesMode7HdFetchInt(0,ppu->vram,u,v,-1)];
                red+=color&31;green+=(color>>5)&31;blue+=(color>>10)&31;
            }
            picture[j*kMini+i]=0xff000000u|(red*2+red/16)<<16|(green*2+green/16)<<8|(blue*2+blue/16);
        }
    }
    int x0=width-kMini-14,y0=14;
    snes_ovl_fill_rect(dst,stride,height,x0-3,y0-3,kMini+6,kMini+6,kInk);
    snes_ovl_stroke_rect(dst,stride,height,x0-2,y0-2,kMini+4,kMini+4,kCream);
    for(int j=0;j<kMini;j++)for(int i=0;i<kMini;i++)dst[(y0+j)*stride+x0+i]=picture[j*kMini+i];
    unsigned choice=Word(ram,kMapChoice);
    for(unsigned i=0;i<sizeof(destinations)/sizeof(destinations[0]);i++) {
        if(!(allowed[choice]&(1u<<i)))continue;
        int x=x0+destinations[i].x*kMini/1024,y=y0+destinations[i].y*kMini/1024;
        snes_ovl_fill_rect(dst,stride,height,x-2,y-2,5,5,kInk);
        snes_ovl_fill_rect(dst,stride,height,x-1,y-1,3,3,
            DestinationAllowed(ram,choice,i)?kGold:kShut);
    }
    /* The player: a dot with a tail pointing the way the camera faces. */
    unsigned angle=Word(ram,kCameraAngle)&511;
    int x=x0+(int)Word(ram,kMapX)*kMini/1024,y=y0+(int)Word(ram,kMapY)*kMini/1024;
    int vx=Velocity(0x1c595,angle),vy=Velocity(0x1c695,angle);
    for(int n=2;n<=6;n++) {
        int px=x+vx*n/512,py=y+vy*n/512;
        if(px>=x0 && px<x0+kMini && py>=y0 && py<y0+kMini)
            snes_ovl_fill_rect(dst,stride,height,px,py,1,1,0xffffffffu);
    }
    snes_ovl_fill_rect(dst,stride,height,x-2,y-2,5,5,kInk);
    snes_ovl_fill_rect(dst,stride,height,x-1,y-1,3,3,0xffff5a3cu);
}
void IogWalkableWorldDrawOverlay(uint8_t *pixels,size_t pitch,int width,int height)
{
    if(!pixels || width<256 || height<224 || pitch<(size_t)width*4 ||
       !IogWalkableWorldActive())return;
    const uint8_t *ram=g_snes->ram;
    uint32_t *dst=(uint32_t *)pixels;
    int stride=(int)(pitch/sizeof(uint32_t));
    int left=(width-256)/2,top=(height-224)/2;
    unsigned choice=Word(ram,kMapChoice);
    const WorldDestination *here=Nearby(ram);
    for(unsigned i=0;i<sizeof(destinations)/sizeof(destinations[0]);i++) {
        /* Every place this stage's stock menu lists. One the story still
         * holds shut (the road to South Cape from Itory) is drawn dim. */
        if(!(allowed[choice]&(1u<<i)) || &destinations[i]==here)continue;
        double x,y;
        if(!Project(ram,destinations[i].x,destinations[i].y,&x,&y))continue;
        int sx=left+(int)x,sy=top+(int)y-1;
        if(sx<40 || sx>=width-40 || sy<44 || sy>=height-40)continue;
        /* Never over the player, who stands at the pivot. */
        if(abs(sx-(left+128))<28 && sy>top+84 && sy<top+150)continue;
        /* Nor under the minimap in the top right corner. */
        if(sx>width-kMini-70 && sy<kMini+60)continue;
        Marker(dst,stride,height,sx,sy,destinations[i].name,
            DestinationAllowed(ram,choice,i));
    }
    Minimap(dst,stride,width,height,ram);
    /* Prompt plate along the bottom, clear of the player. */
    char text[72],label[8]={0};
    uint32_t tint=0;
    int glyph=0,scale=1;
    if(here) {
        /* The pad's own name for the button, in the chosen prompt style. */
        if(!IogHostPadLabel(SNES_PAD_B,label,&tint) || !label[0]) {
            label[0]='B';label[1]=0;tint=SNES_OVL_COL_B;
        }
        glyph=IogMapUiGlyphWidth(label,tint,1)+6;scale=2;
        snprintf(text,sizeof(text),"Enter %s",here->name);
    } else if(!IogWalkableWorldDirection(text,sizeof(text))) text[0]=0;
    int text_width=8*scale*snes_ovl_text_len(text);
    int plate_width=text_width+glyph+20,plate_height=scale==2?28:18;
    int x=(width-plate_width)/2,y=height-plate_height-12;
    if(text[0]) {
        Shade(dst,stride,width,height,x,y,plate_width,plate_height,kPlate,200);
        snes_ovl_stroke_rect(dst,stride,height,x,y,plate_width,plate_height,kCream);
        if(glyph)IogMapUiGlyphDraw(dst,stride,height,x+8,y+(plate_height-IOG_MAP_UI_GLYPH_HEIGHT)/2,label,tint,1);
        Label(dst,stride,height,x+10+glyph,y+(plate_height-8*scale)/2+1,text,kCream,scale);
    }
    /* The controls, for the first few seconds of each visit to the map. */
    if(help_ticks<300) {
        const char *help="Up/Down: Walk  Left/Right: Turn";
        int help_width=8*snes_ovl_text_len(help);
        Label(dst,stride,height,(width-help_width)/2,y-14,help,kCream,1);
    }
}
