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
static const char *last_event;
static bool commit(void *p, const ca_state *s, size_t n)
{ (void)p; (void)s; (void)n; commits++; return commit_ok; }
static void notify(void *p, const ca_definition *d, const ca_state *s)
{
    (void)p; (void)s; notices++;
    CHECK(ca_ui_snapshot(&ui,engine.states,engine.count));
    CHECK(ca_ui_notice(&ui,(size_t)(d-gaia_definitions)));
}
static bool event(void *p,const char *name,uint32_t amount)
{ (void)p; events++; last_event=name; return ca_event(&engine,name,amount,1700000000); }
static void word(unsigned a,unsigned v) { ram[a]=(uint8_t)v;ram[a+1]=(uint8_t)(v>>8); }
static void flag(unsigned n,bool on)
{ if(on) ram[0x0A00+n/8]|=(uint8_t)(1u<<(n&7)); else ram[0x0A00+n/8]&=(uint8_t)~(1u<<(n&7)); }
static bool earned(const char *event)
{
    for(size_t i=0;i<engine.count;i++)
        if(!strcmp(gaia_definitions[i].event,event)) return engine.states[i].unlocked_at!=0;
    return false;
}
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
    CHECK(o.problem==COMPANION_GAIA_EVENT_LOST);
    ram[0x0AB0]=0xFA;CHECK(!companion_gaia_observe(&o,&f));CHECK(o.problem==COMPANION_GAIA_EVENT_LOST);
    /* Refusals say why, and recovery rebaselines from the current valid
     * observation: what happened while refused is never awarded. */
    setup(&o,&f);ram[0x0B56]=3;CHECK(companion_gaia_observe(&o,&f));CHECK(o.problem==COMPANION_GAIA_OK);
    ram[0x0B56]=51;CHECK(!companion_gaia_observe(&o,&f));
    CHECK(o.problem==COMPANION_GAIA_TOO_MANY_JEWELS && !o.baseline);
    ram[0x0B56]=52;ram[0x0A61]=1;CHECK(!companion_gaia_observe(&o,&f));CHECK(!events);
    CHECK(o.problem==COMPANION_GAIA_TOO_MANY_JEWELS);
    ram[0x0B56]=49;CHECK(companion_gaia_observe(&o,&f));
    CHECK(o.problem==COMPANION_GAIA_OK && !events && o.jewels==49 && o.rooms==1 && !ca_unlocked(&engine));
    CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    ram[0x0B56]=50;CHECK(companion_gaia_observe(&o,&f));CHECK(events==1 && ca_unlocked(&engine)==4);
    /* Exactly 50 is valid; 50 given plus one carried is not. */
    setup(&o,&f);ram[0x0AB0]=0x50;CHECK(companion_gaia_observe(&o,&f));CHECK(o.problem==COMPANION_GAIA_OK);
    ram[0x0AB4]=1;CHECK(!companion_gaia_observe(&o,&f));CHECK(o.problem==COMPANION_GAIA_TOO_MANY_JEWELS);
    /* Every malformed BCD byte is refused with its own reason. */
    setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));
    static const uint8_t bad_digits[]={0x0A,0x0F,0x1A,0x60,0x99,0xFF};
    for(unsigned i=0;i<sizeof bad_digits;i++){
        ram[0x0AB0]=bad_digits[i];CHECK(!companion_gaia_observe(&o,&f));
        CHECK(o.problem==COMPANION_GAIA_BAD_JEWEL_DIGITS && !o.baseline);
    }
    ram[0x0AB0]=0x59;CHECK(!companion_gaia_observe(&o,&f));CHECK(o.problem==COMPANION_GAIA_TOO_MANY_JEWELS);
    ram[0x0AB0]=0x12;CHECK(companion_gaia_observe(&o,&f));
    CHECK(o.problem==COMPANION_GAIA_OK && o.jewels==12 && !events && !ca_unlocked(&engine));
    ram[0x0AB0]=0x13;CHECK(companion_gaia_observe(&o,&f));CHECK(events==1 && ca_unlocked(&engine)==2);
    /* A frame without memory, and a noneligible mode, replace a stale reason. */
    setup(&o,&f);f.ram_size=10;CHECK(!companion_gaia_observe(&o,&f));CHECK(o.problem==COMPANION_GAIA_BAD_FRAME);
    f.ram_size=sizeof ram;CHECK(companion_gaia_observe(&o,&f));CHECK(o.problem==COMPANION_GAIA_OK);
    ram[0x0B56]=60;CHECK(!companion_gaia_observe(&o,&f));CHECK(o.problem==COMPANION_GAIA_TOO_MANY_JEWELS);
    f.cheats_used=true;CHECK(companion_gaia_observe(&o,&f));CHECK(o.problem==COMPANION_GAIA_OK && !events);
    /* Secrets: every table flag fires exactly once on 0->1 during play, and
     * every one has a catalog definition listening for its event. */
    CHECK(companion_gaia_secret_flag_count==8);
    for(size_t k=0;k<companion_gaia_secret_flag_count;k++){
        const companion_gaia_secret_flag *s=&companion_gaia_secret_flags[k];
        setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
        CHECK(!earned(s->event));
        flag(s->flag,true);memcpy(untouched,ram,sizeof ram);
        CHECK(companion_gaia_observe(&o,&f));CHECK(events==1 && !strcmp(last_event,s->event));
        CHECK(!memcmp(untouched,ram,sizeof ram));
        CHECK(earned(s->event) && ca_unlocked(&engine)==1 && notices==1);
        CHECK(companion_gaia_observe(&o,&f));CHECK(events==1);
        /* No other table flag shares this flag's bit. */
        for(size_t j=0;j<companion_gaia_secret_flag_count;j++)
            CHECK(j==k || companion_gaia_secret_flags[j].flag!=s->flag);
        /* Already set when a save or state is loaded: silent. */
        setup(&o,&f);flag(s->flag,true);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
        f.generation++;CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
        f.generation++;flag(s->flag,false);CHECK(companion_gaia_observe(&o,&f));
        flag(s->flag,true);f.generation++;CHECK(companion_gaia_observe(&o,&f));CHECK(!events && !earned(s->event));
        /* Set while not in play ($09AA clear): not awarded, then stays silent. */
        setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));word(0x09AA,0);flag(s->flag,true);
        CHECK(companion_gaia_observe(&o,&f));word(0x09AA,1);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
        /* Every unsupported or assisted mode: set meanwhile, never awarded. */
        for(unsigned mode=0;mode<4;mode++){
            setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));
            if(mode==0)f.verified_stock_rom=false;
            if(mode==1)f.cheats_used=true;
            if(mode==2)f.diagnostic=true;
            if(mode==3)f.new_game_plus=true;
            CHECK(companion_gaia_observe(&o,&f));flag(s->flag,true);
            CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
            f.verified_stock_rom=true;f.cheats_used=f.diagnostic=f.new_game_plus=false;
            CHECK(companion_gaia_observe(&o,&f));CHECK(companion_gaia_observe(&o,&f));CHECK(!events && !earned(s->event));
        }
        /* A rewind clearing the flag rebaselines silently (a jewel found in
         * the same frame is not awarded either); setting it again in play
         * reports it again, but the achievement is not earned twice. */
        setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));flag(s->flag,true);
        CHECK(companion_gaia_observe(&o,&f));CHECK(events==1 && notices==1);
        flag(s->flag,false);ram[0x0AB4]=1;CHECK(companion_gaia_observe(&o,&f));CHECK(events==1);
        CHECK(companion_gaia_observe(&o,&f));CHECK(events==1 && !earned("jewels.collected"));
        flag(s->flag,true);CHECK(companion_gaia_observe(&o,&f));CHECK(events==2 && notices==1 && ca_unlocked(&engine)==1);
        /* Refused observations in between award nothing seen meanwhile. */
        setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));ram[0x0B56]=60;
        CHECK(!companion_gaia_observe(&o,&f));flag(s->flag,true);CHECK(!companion_gaia_observe(&o,&f));
        ram[0x0B56]=0;CHECK(companion_gaia_observe(&o,&f));CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    }
    /* Two secrets in one observation: both, once each. */
    setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));
    flag(0xD7,true);flag(0xE7,true);CHECK(companion_gaia_observe(&o,&f));
    CHECK(events==2 && earned("secret.teapot") && earned("secret.snakes"));
    /* Neighbouring bits in the same bytes do not count. */
    setup(&o,&f);CHECK(companion_gaia_observe(&o,&f));
    flag(0xD6,true);flag(0xD8,true);flag(0xE3,true);flag(0xE4,true);flag(0xE8,true);flag(0xF1,true);
    CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    /* Solid Arm: armed in his lair ($EA) with an enemy standing ($0AEC),
     * awarded on the scene change to Babel ($E3) once he falls. */
    setup(&o,&f);word(0x0644,0xE9);CHECK(companion_gaia_observe(&o,&f));
    word(0x0644,0xEA);word(0x0AEC,1);CHECK(companion_gaia_observe(&o,&f));CHECK(companion_gaia_observe(&o,&f));
    word(0x0AEC,0);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    word(0x09AA,0);word(0x0644,0xE3);CHECK(companion_gaia_observe(&o,&f));
    CHECK(events==1 && !strcmp(last_event,"secret.solid-arm") && earned("secret.solid-arm"));
    word(0x09AA,1);CHECK(companion_gaia_observe(&o,&f));word(0x0644,0xEA);CHECK(companion_gaia_observe(&o,&f));
    word(0x0644,0xE3);CHECK(companion_gaia_observe(&o,&f));CHECK(events==1);
    /* A state loaded in the lair after his defeat ($0AEC 0) never arms. */
    setup(&o,&f);word(0x0644,0xEA);word(0x0AEC,1);CHECK(companion_gaia_observe(&o,&f));
    CHECK(companion_gaia_observe(&o,&f));word(0x0AEC,0);f.generation++;CHECK(companion_gaia_observe(&o,&f));
    CHECK(companion_gaia_observe(&o,&f));word(0x0644,0xE3);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    /* Loaded straight into the lair: the baseline itself does not arm. */
    setup(&o,&f);word(0x0644,0xEA);word(0x0AEC,1);CHECK(companion_gaia_observe(&o,&f));
    word(0x0AEC,0);CHECK(companion_gaia_observe(&o,&f));word(0x0644,0xE3);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    /* Game over: the lair's other exit (back to the mansion) disarms. */
    setup(&o,&f);word(0x0644,0xEA);word(0x0AEC,1);CHECK(companion_gaia_observe(&o,&f));CHECK(companion_gaia_observe(&o,&f));
    word(0x0644,0xE9);CHECK(companion_gaia_observe(&o,&f));word(0x0644,0xE3);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    /* Babel reached from anywhere else is the story, not the secret. */
    setup(&o,&f);word(0x0644,0xDF);word(0x0AEC,1);CHECK(companion_gaia_observe(&o,&f));CHECK(companion_gaia_observe(&o,&f));
    word(0x0644,0xE3);CHECK(companion_gaia_observe(&o,&f));CHECK(!events);
    /* Cheats or a new generation while armed: nothing. */
    for(unsigned mode=0;mode<3;mode++){
        setup(&o,&f);word(0x0644,0xEA);word(0x0AEC,1);CHECK(companion_gaia_observe(&o,&f));CHECK(companion_gaia_observe(&o,&f));
        if(mode==0)f.cheats_used=true;
        if(mode==1)f.generation++;
        if(mode==2)companion_gaia_observer_invalidate(&o);
        word(0x0AEC,0);CHECK(companion_gaia_observe(&o,&f));word(0x0644,0xE3);
        CHECK(companion_gaia_observe(&o,&f));CHECK(!events && !earned("secret.solid-arm"));
    }
    /* Every title fits the unlock toast whole: its title line is 132 px of
     * the 8-px font (toolkit ca_ui_draw_toast; presentation.c Text()). */
    for(size_t i=0;i<GAIA_ACHIEVEMENT_COUNT;i++){
        CHECK(strlen(gaia_definitions[i].title)<=(CA_TOAST_WIDTH-12)/8);
    }
    /* Every catalog event is one the observer can emit. */
    for(size_t i=0;i<GAIA_ACHIEVEMENT_COUNT;i++){
        const char *e=gaia_definitions[i].event;bool known=!strcmp(e,"rooms.cleared")||!strcmp(e,"jewels.collected")||
            !strcmp(e,"story.finished")||!strcmp(e,"secret.solid-arm");
        for(size_t k=0;k<companion_gaia_secret_flag_count;k++) known|=!strcmp(e,companion_gaia_secret_flags[k].event);
        CHECK(known);
    }
    /* A saved earned achievement restores silently through the actual core/UI. */
    setup(&o,&f);CHECK(ca_restore(&engine,"gaia.first-jewel",1,1700000000));
    CHECK(ca_ui_snapshot(&ui,engine.states,engine.count));CHECK(!notices && !commits);
    CHECK(!ca_ui_tick(&ui,0,10,false));
    printf("PASS %u checks: synthetic Gaia observations through shared core/presentation; no game playback\n",checks);
    return 0;
}
