#include "iog_cheat_rates.h"
#include <string.h>

int IogCheatRateClampMultiplier(int value)
{ return value<1?1:value>8?8:value; }

static uint32_t fingerprint(const uint8_t *p,size_t size)
{
    uint32_t value=2166136261u;
    for(size_t i=0;i<size;i++) value=(value^p[i])*16777619u;
    return value;
}
bool IogCheatRateSourceSupported(const uint8_t *rom,size_t size)
{
    /* ROM-free fingerprints of stock USA award stores, common room-flag
     * setter and table. See docs/CHEAT-RATES.md for independently traced
     * source order. These are guards, not authentication or copied game code. */
    static const struct {uint32_t offset,size,hash;} ranges[]={
        {0x00E03C,22,0xB2F53129u},{0x00E08A,15,0x1C8A78B0u},
        {0x00E0D5,15,0x7CA0F920u},{0x00E14C,9,0x02ADC62Au},
        {0x00B4A1,11,0x9A41208Du},{0x01AADE,256,0xCB027393u}
    };
    if(!rom||size!=0x200000) return false;
    for(size_t i=0;i<sizeof ranges/sizeof *ranges;i++)
        if(fingerprint(rom+ranges[i].offset,ranges[i].size)!=ranges[i].hash) return false;
    return true;
}
void IogCheatRateTrackerInvalidate(IogCheatRateTracker *tracker)
{
    if(tracker) memset(tracker,0,sizeof *tracker);
}
static bool ready(const IogCheatRateSample *s)
{
    return s->supported&&!s->blocked&&s->scene<256&&s->player&&s->hp&&
        s->stats[0]&&s->hp<=s->stats[0];
}
IogCheatRateAward IogCheatRateStep(IogCheatRateTracker *t,
                                const IogCheatRateSample *s,int multiplier)
{
    IogCheatRateAward award={0,0};
    if(!t||!s) return award;
    multiplier=IogCheatRateClampMultiplier(multiplier);
    if(!ready(s)||multiplier==1) {
        IogCheatRateTrackerInvalidate(t);return award;
    }
    if(!t->baseline||s->generation!=t->previous.generation||
       s->scene!=t->previous.scene||s->player!=t->previous.player) {
        t->previous=*s;t->baseline=true;t->pending_kind=t->pending_frames=0;
        return award;
    }
    unsigned added=0;bool backward=false;
    for(unsigned i=0;i<32;i++) {
        uint8_t new_bits=s->cleared[i]&~t->previous.cleared[i];
        backward|=(t->previous.cleared[i]&~s->cleared[i])!=0;
        for(unsigned bit=0;bit<8;bit++) added+=(new_bits>>bit)&1u;
    }
    unsigned room=s->scene,mask=1u<<(room&7);
    bool current_new=(s->cleared[room/8]&mask)&&!(t->previous.cleared[room/8]&mask);
    if(backward||added>1||(added&&!current_new)) {
        t->pending_kind=t->pending_frames=0;t->previous=*s;return award;
    }
    if(added==1&&current_new&&s->reward_kind>=1&&s->reward_kind<=3) {
        /* The stock common actor sets this flag before returning to the
         * +1 stat store. Keep only a tiny two-real-frame continuation window;
         * unrelated stat edits, scene/source/generation changes cancel it. */
        memcpy(t->armed_stats,t->previous.stats,sizeof t->armed_stats);
        t->pending_kind=s->reward_kind;t->pending_frames=3;
    }
    if(t->pending_kind) {
        unsigned kind=t->pending_kind-1;bool unchanged=true,matched=true;
        if(s->reward_kind!=t->pending_kind) matched=unchanged=false;
        for(unsigned i=0;i<3;i++) {
            unchanged&=s->stats[i]==t->armed_stats[i];
            unsigned expected=(unsigned)t->armed_stats[i]+(i==kind);
            matched&=expected<=65535u&&s->stats[i]==expected;
        }
        if(matched) {
            static const uint16_t cap[]={40,99,99};
            unsigned amount=(unsigned)multiplier-1;
            if(s->stats[kind]<cap[kind]) {
                unsigned room_left=cap[kind]-s->stats[kind];
                if(amount>room_left) amount=room_left;
                award.kind=(uint8_t)(kind+1);award.extra=(uint16_t)amount;
            }
            t->pending_kind=t->pending_frames=0;
        } else if(!unchanged||!--t->pending_frames) {
            t->pending_kind=t->pending_frames=0;
        }
    }
    t->previous=*s;
    if(award.extra) {
        t->previous.stats[award.kind-1]+=award.extra;
        if(award.kind==1) {
            unsigned hp=(unsigned)t->previous.hp+award.extra;
            t->previous.hp=(uint16_t)(hp>t->previous.stats[0]?t->previous.stats[0]:hp);
        }
    }
    return award;
}
