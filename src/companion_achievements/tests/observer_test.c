/* SPDX-License-Identifier: MIT */
#include "observer.h"
#include "catalog.generated.h"
#include "companion_achievement_presentation.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static unsigned checks;
static uint8_t ram[0x20000], rom[0x200000], untouched[0x20000];
static ca_engine engine;
static ca_ui ui;
static unsigned commits, notices, events;
static bool commit_ok=true;
static bool commit(void *p, const ca_state *s, size_t n)
{ (void)p; (void)s; (void)n; commits++; return commit_ok; }
static void notify(void *p, const ca_definition *d, const ca_state *s)
{
    (void)p; (void)s; notices++;
    CHECK(ca_ui_snapshot(&ui,engine.states,engine.count));
    CHECK(ca_ui_notice(&ui,(size_t)(d-gaia_definitions)));
}
static bool event(void *p,const char *name,uint32_t amount)
{ (void)p; events++; return ca_event(&engine,name,amount,1700000000); }
static void word(unsigned a,unsigned v) { ram[a]=(uint8_t)v;ram[a+1]=(uint8_t)(v>>8); }
static void setup(companion_gaia_observer *o,companion_gaia_frame *f)
{
    memset(ram,0,sizeof ram); memset(rom,0,sizeof rom); rom[0x01AADE + 8]=1;
    word(0x09AA,1); word(0x0644,8);
    CHECK(ca_init(&engine,gaia_definitions,GAIA_ACHIEVEMENT_COUNT,commit,notify,NULL));
    CHECK(ca_ui_init(&ui,gaia_definitions,NULL,GAIA_ACHIEVEMENT_COUNT));
    companion_gaia_observer_init(o,event,NULL);
    *f=(companion_gaia_frame){ram,rom,sizeof ram,sizeof rom,1,true,false,false,false};
    commits=notices=events=0; commit_ok=true;
}
int main(void)
{
    companion_gaia_observer o; companion_gaia_frame f;
    setup(&o,&f);
    CHECK(companion_gaia_observe(&o,&f)); CHECK(!events);
    ram[0x0A61]=1;ram[0x0AB4]=1;
    memcpy(untouched,ram,sizeof ram);
    CHECK(companion_gaia_observe(&o,&f)); CHECK(events==2 && notices==2);
    CHECK(!memcmp(untouched,ram,sizeof ram)); CHECK(ca_unlocked(&engine)==2);
    CHECK(companion_gaia_observe(&o,&f)); CHECK(events==2 && notices==2);
    ram[0x0B56]=9; CHECK(companion_gaia_observe(&o,&f)); CHECK(ca_unlocked(&engine)==3);
    ram[0x0B56]=29; CHECK(companion_gaia_observe(&o,&f)); CHECK(ca_unlocked(&engine)==4);
    ram[0x0B56]=49; CHECK(companion_gaia_observe(&o,&f)); CHECK(ca_unlocked(&engine)==5);
    /* Handing over all jewels preserves the count and creates no new fact. */
    unsigned before=events;ram[0x0AB0]=0x50;ram[0x0AB4]=0;ram[0x0B56]=0;
    CHECK(companion_gaia_observe(&o,&f));CHECK(events==before);
    /* Epilogue then END even though the terminal screen is not in-play. */
    word(0x0644,0xE5);CHECK(companion_gaia_observe(&o,&f));
    word(0x09AA,0);word(0x0644,0xF0);CHECK(companion_gaia_observe(&o,&f));
    CHECK(ca_unlocked(&engine)==6);before=events;
    CHECK(companion_gaia_observe(&o,&f));CHECK(events==before);
    CHECK(ca_ui_tick(&ui,0,10,false)); CHECK(!ca_ui_tick(&ui,0,11,false));
    /* Baseline snapshots and loads are silent, including an epilogue load. */
    setup(&o,&f);ram[0x0AB0]=0x50;ram[0x0A61]=1;word(0x0644,0xE5);
    CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    word(0x0644,0xF0);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    word(0x0644,8);f.generation++;CHECK(companion_gaia_observe(&o,&f));
    word(0x0644,0xE5);CHECK(companion_gaia_observe(&o,&f));
    f.generation++;word(0x0644,0xF0);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    /* Explicit invalidation and backward observations also seed silently. */
    companion_gaia_observer_invalidate(&o);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    ram[0x0AB0]=0;CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    /* Every unsupported/assisted mode is read-only. */
    for(unsigned mode=0;mode<4;mode++){
        setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));
        if(mode==0)f.verified_stock_rom=false;
        if(mode==1)f.cheats_used=true;
        if(mode==2)f.diagnostic=true;
        if(mode==3)f.new_game_plus=true;
        ram[0x0AB4]=1;ram[0x0A61]=1;
        CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
        f.verified_stock_rom=true;f.cheats_used=f.diagnostic=f.new_game_plus=false;
        CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    }
    setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));
    f.ram_size=10;CHECK(!companion_gaia_observe(&o,&f));f.ram_size=sizeof ram;
    CHECK(companion_gaia_observe(&o,&f));ram[0x0AB0]=0xFA;
    CHECK(!companion_gaia_observe(&o,&f));CHECK(!events);
    setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));commit_ok=false;ram[0x0AB4]=1;
    CHECK(!companion_gaia_observe(&o,&f));CHECK(o.failed);
    CHECK(!notices && ca_unlocked(&engine)==0 && commits==1);
    commit_ok=true;CHECK(!companion_gaia_observe(&o,&f));CHECK(commits==1);
    /* A saved earned achievement restores silently through the actual core/UI. */
    setup(&o,&f);CHECK(ca_restore(&engine,"gaia.first-jewel",1,1700000000));
    CHECK(ca_ui_snapshot(&ui,engine.states,engine.count));CHECK(!notices && !commits);
    CHECK(!ca_ui_tick(&ui,0,10,false));
    printf("PASS %u checks: synthetic Gaia observations through shared core/presentation; no game playback\n",checks);
    return 0;
}
