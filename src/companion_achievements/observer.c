/* SPDX-License-Identifier: MIT */
#include "observer.h"
#include <string.h>

/* Existing Babel references: IogCompletionPercent in src/iog_ngplus.c,
 * inventory kStacks in src/iog_inventory.c, and the NG+ epilogue/END route.
 * These addresses still require real-route qualification before enabling the
 * adapter in a public game build. No boss or per-jewel location is inferred. */
enum { REWARD_TABLE=0x01AADE, CLEAR_FLAGS=0x0A60, SCENE=0x0644,
       GAME_LOADED=0x09AA, GIVEN_JEWELS=0x0AB0, INVENTORY=0x0AB4,
       EXTRA_JEWELS=0x0B56, EPILOGUE=0xE5, END=0xF0 };
static unsigned word(const uint8_t *p) { return p[0] | (unsigned)p[1]<<8; }
void companion_gaia_observer_init(companion_gaia_observer *o,
                                 companion_gaia_event event, void *context)
{
    if (!o) return;
    memset(o, 0, sizeof *o); o->event=event; o->context=context;
}
void companion_gaia_observer_invalidate(companion_gaia_observer *o)
{
    if (!o) return;
    o->baseline=false; o->active=false; o->epilogue=false; o->finished=false;
}
static bool emit(companion_gaia_observer *o, const char *event, unsigned amount)
{
    if (!o->event || !o->event(o->context,event,amount)) {
        o->failed=true; return false;
    }
    return true;
}
bool companion_gaia_observe(companion_gaia_observer *o, const companion_gaia_frame *f)
{
    if (!o || !f || o->failed) return false;
    if (!f->ram || !f->rom || f->ram_size<=EXTRA_JEWELS ||
        f->rom_size<REWARD_TABLE+256) {
        companion_gaia_observer_invalidate(o); return false;
    }
    if (!f->verified_stock_rom || f->cheats_used || f->diagnostic || f->new_game_plus) {
        companion_gaia_observer_invalidate(o); return true;
    }
    const uint8_t *r=f->ram;
    unsigned scene=word(r+SCENE), bcd=r[GIVEN_JEWELS];
    if ((bcd&15)>9 || (bcd>>4)>5) {
        companion_gaia_observer_invalidate(o); return false;
    }
    unsigned jewels=(bcd>>4)*10+(bcd&15)+r[EXTRA_JEWELS], rooms=0;
    for (unsigned i=0;i<16;i++) jewels+=r[INVENTORY+i]==1;
    if (jewels>50) { companion_gaia_observer_invalidate(o); return false; }
    for (unsigned i=0;i<256;i++)
        if (f->rom[REWARD_TABLE+i] && (r[CLEAR_FLAGS+i/8]&(1u<<(i&7)))) rooms++;
    bool active=word(r+GAME_LOADED)!=0;
    bool reset=!o->baseline || o->generation!=f->generation;
    /* Backward flags/counts are a second defence against unannounced restores;
     * they cannot replace an explicit generation change for a forward load. */
    if (!reset) {
        if (jewels<o->jewels) reset=true;
        for (unsigned i=0;i<32;i++) if (o->clear_flags[i] & ~r[CLEAR_FLAGS+i]) reset=true;
    }
    if (reset) {
        o->epilogue=false; o->finished=false;
    } else {
        if (active && o->active) {
            if (rooms>o->rooms && !emit(o,"rooms.cleared",rooms)) return false;
            if (jewels>o->jewels && !emit(o,"jewels.collected",jewels)) return false;
        }
        /* A loaded epilogue/END frame does not arm completion. Observe the
         * transition INTO epilogue and then END in the same generation. Do
         * not require ordinary gameplay readiness at the terminal scene. */
        if (scene==EPILOGUE && o->scene!=EPILOGUE && o->active) o->epilogue=true;
        if (scene==END && o->epilogue && !o->finished) {
            if (!emit(o,"story.finished",1)) return false;
            o->finished=true;
        }
    }
    o->generation=f->generation; o->scene=(uint16_t)scene;
    o->jewels=jewels; o->rooms=rooms; o->active=active; o->baseline=true;
    memcpy(o->clear_flags,r+CLEAR_FLAGS,32);
    return true;
}
