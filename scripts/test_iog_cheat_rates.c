#include "iog_cheat_rates.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(v) do {checks++;if(!(v)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#v);return 1;}}while(0)
static IogCheatRateSample seed(unsigned kind)
{
    IogCheatRateSample s={0};s.generation=1;s.scene=0x10;s.player=0x1000;
    s.hp=8;s.stats[0]=8;s.stats[1]=4;s.stats[2]=3;s.reward_kind=(uint8_t)kind;s.supported=true;
    return s;
}
int main(int argc,char **argv)
{
    unsigned checks=0;
    for(unsigned kind=1;kind<=3;kind++)for(int mult=1;mult<=8;mult++){
        IogCheatRateTracker t={0};IogCheatRateSample s=seed(kind);IogCheatRateAward a;
        a=IogCheatRateStep(&t,&s,mult);CHECK(!a.extra);
        s.cleared[2]=1;s.stats[kind-1]++;
        a=IogCheatRateStep(&t,&s,mult);CHECK(a.extra==(unsigned)mult-1);
        CHECK(!a.extra||a.kind==kind);
        if(a.extra){s.stats[kind-1]+=a.extra;if(kind==1)s.hp+=a.extra;}
        a=IogCheatRateStep(&t,&s,mult);CHECK(!a.extra);
    }
    CHECK(IogCheatRateClampMultiplier(-1)==1);CHECK(IogCheatRateClampMultiplier(99)==8);
    IogCheatRateTracker t={0};IogCheatRateSample s=seed(2);IogCheatRateAward a;
    /* Already-earned flags/stats, explicit restores and generation changes. */
    s.cleared[2]=1;s.stats[1]=20;CHECK(!IogCheatRateStep(&t,&s,8).extra);
    IogCheatRateTrackerInvalidate(&t);CHECK(!IogCheatRateStep(&t,&s,8).extra);
    s.generation++;s.stats[1]++;CHECK(!IogCheatRateStep(&t,&s,8).extra);
    /* An original reward may follow the flag after a scheduling boundary. */
    t=(IogCheatRateTracker){0};s=seed(2);IogCheatRateStep(&t,&s,8);
    s.cleared[2]=1;CHECK(!IogCheatRateStep(&t,&s,8).extra);
    CHECK(!IogCheatRateStep(&t,&s,8).extra);s.stats[1]++;
    a=IogCheatRateStep(&t,&s,8);CHECK(a.extra==7&&a.kind==2);
    /* Window expires; an unrelated later stat change is not an award. */
    t=(IogCheatRateTracker){0};s=seed(2);IogCheatRateStep(&t,&s,8);s.cleared[2]=1;
    for(int i=0;i<4;i++)CHECK(!IogCheatRateStep(&t,&s,8).extra);
    s.stats[1]++;CHECK(!IogCheatRateStep(&t,&s,8).extra);
    /* Every failure cancels; none can be repaired by a later coincidental +1. */
    for(unsigned why=0;why<11;why++){
        t=(IogCheatRateTracker){0};s=seed(2);IogCheatRateStep(&t,&s,8);
        s.cleared[2]=1;s.stats[1]++;
        switch(why){
            case 0:s.generation++;break;
            case 1:s.scene++;break;
            case 2:s.player=0;break;
            case 3:s.hp=0;break;
            case 4:s.supported=false;break;
            case 5:s.blocked=true;break;
            case 6:s.stats[0]++;break;
            case 7:s.stats[1]++;break;
            case 8:s.cleared[2]=3;break;
            case 9:s.cleared[2]=0;s.cleared[3]=1;break;
            case 10:s.reward_kind=3;break;
        }
        CHECK(!IogCheatRateStep(&t,&s,8).extra);
    }
    /* Backward flags, spending/refunds and current-HP changes alone never arm. */
    t=(IogCheatRateTracker){0};s=seed(1);s.cleared[2]=1;IogCheatRateStep(&t,&s,8);
    s.cleared[2]=0;s.stats[0]++;CHECK(!IogCheatRateStep(&t,&s,8).extra);
    s.hp=4;CHECK(!IogCheatRateStep(&t,&s,8).extra);s.hp=8;CHECK(!IogCheatRateStep(&t,&s,8).extra);
    for(unsigned kind=1;kind<=3;kind++){
        t=(IogCheatRateTracker){0};s=seed(kind);s.stats[kind-1]=kind==1?38:97;
        IogCheatRateStep(&t,&s,8);s.cleared[2]=1;s.stats[kind-1]++;
        a=IogCheatRateStep(&t,&s,8);CHECK(a.extra==1);
        t=(IogCheatRateTracker){0};s=seed(kind);s.stats[kind-1]=kind==1?40:99;
        IogCheatRateStep(&t,&s,8);s.cleared[2]=1;s.stats[kind-1]++;
        CHECK(!IogCheatRateStep(&t,&s,8).extra);
    }
    CHECK(!IogCheatRateSourceSupported(NULL,0));
    if(argc>1){
        FILE*f=fopen(argv[1],"rb");CHECK(f!=NULL);uint8_t*rom=malloc(0x200000);CHECK(rom!=NULL);
        CHECK(fread(rom,1,0x200000,f)==0x200000);CHECK(fgetc(f)==EOF);fclose(f);
        CHECK(IogCheatRateSourceSupported(rom,0x200000));rom[0x00E048]^=1;
        CHECK(!IogCheatRateSourceSupported(rom,0x200000));free(rom);
    }
    printf("PASS %u room-reward checks; pure bounded fixtures, not natural reward playback\n",checks);
    return 0;
}
