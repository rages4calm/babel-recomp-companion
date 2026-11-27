/* SPDX-License-Identifier: MIT */
#include "observer.h"
#include <string.h>

/* Existing Babel references: IogCompletionPercent in src/iog_ngplus.c,
 * inventory kStacks in src/iog_inventory.c, and the NG+ epilogue/END route.
 * These addresses still require real-route qualification before enabling the
 * adapter in a public game build. No boss or per-jewel location is inferred. */
enum { REWARD_TABLE=0x01AADE, CLEAR_FLAGS=0x0A60, SCENE=0x0644,
       GAME_LOADED=0x09AA, GIVEN_JEWELS=0x0AB0, INVENTORY=0x0AB4,
       EXTRA_JEWELS=0x0B56, EPILOGUE=0xE5, END=0xF0, EVENT_FLAGS=0x0A00,
       ENEMIES_LEFT=0x0AEC, SOLID_ARM_LAIR=0xEA, BABEL_UPPER=0xE3 };
/* Writer of each flag (extracted/ in the USA disassembly), the only one:
 *   $D7 south_cape/sc01_fisherman  teapot pot (fisherman's 1-in-16 spot)
 *   $E1 freejia/fr32_creep         the man hidden in the hedges
 *   $D9 diamond_mine/dm40_trapped_slave  the laborer buried by a cave-in
 *   $E5 euro/eu95_ann              Ann's third Red Apple
 *   $A6 euro/eu93_found            hidden house's Strength
 *   $F0 euro/eu97_life_medicine    Life Medicine at the end of the line
 *   $E6 native_village/nvAE_stone_girl2  the restored girl's thanks
 *   $E7 dao/daC6_snake_panic       snake game won (51 or more)
 * None is cleared by any script. The only other writer in this project is
 * the All Red Jewels cheat ($D7 $E1 $E5 $E6 $E7), which taints the session. */
const companion_gaia_secret_flag companion_gaia_secret_flags[] = {
    {"secret.teapot", 0xD7}, {"secret.hedge", 0xE1}, {"secret.buried", 0xD9},
    {"secret.apples", 0xE5}, {"secret.hidden-house", 0xA6},
    {"secret.life-medicine", 0xF0}, {"secret.stone-girls", 0xE6},
    {"secret.snakes", 0xE7},
};
const size_t companion_gaia_secret_flag_count =
    sizeof companion_gaia_secret_flags / sizeof *companion_gaia_secret_flags;
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
    o->solid_arm=false;
}
static bool refuse(companion_gaia_observer *o, companion_gaia_problem why)
{
    companion_gaia_observer_invalidate(o); o->problem=why; return false;
}
static bool emit(companion_gaia_observer *o, const char *event, unsigned amount)
{
    if (!o->event || !o->event(o->context,event,amount)) {
        o->failed=true; o->problem=COMPANION_GAIA_EVENT_LOST; return false;
    }
    return true;
}
bool companion_gaia_observe(companion_gaia_observer *o, const companion_gaia_frame *f)
{
    if (!o || !f || o->failed) return false;
    if (!f->ram || !f->rom || f->ram_size<=EXTRA_JEWELS ||
        f->rom_size<REWARD_TABLE+256)
        return refuse(o,COMPANION_GAIA_BAD_FRAME);
    if (!f->verified_stock_rom || f->cheats_used || f->diagnostic || f->new_game_plus) {
        companion_gaia_observer_invalidate(o); o->problem=COMPANION_GAIA_OK; return true;
    }
    const uint8_t *r=f->ram;
    unsigned scene=word(r+SCENE), bcd=r[GIVEN_JEWELS];
    if ((bcd&15)>9 || (bcd>>4)>5) return refuse(o,COMPANION_GAIA_BAD_JEWEL_DIGITS);
    unsigned jewels=(bcd>>4)*10+(bcd&15)+r[EXTRA_JEWELS], rooms=0;
    for (unsigned i=0;i<16;i++) jewels+=r[INVENTORY+i]==1;
    if (jewels>50) return refuse(o,COMPANION_GAIA_TOO_MANY_JEWELS);
    for (unsigned i=0;i<256;i++)
        if (f->rom[REWARD_TABLE+i] && (r[CLEAR_FLAGS+i/8]&(1u<<(i&7)))) rooms++;
    bool active=word(r+GAME_LOADED)!=0;
    uint32_t secrets=0;
    for (size_t i=0;i<companion_gaia_secret_flag_count;i++) {
        unsigned n=companion_gaia_secret_flags[i].flag;
        if (r[EVENT_FLAGS+n/8]&(1u<<(n&7))) secrets|=UINT32_C(1)<<i;
    }
    bool reset=!o->baseline || o->generation!=f->generation;
    /* Backward flags/counts are a second defence against unannounced restores;
     * they cannot replace an explicit generation change for a forward load. */
    if (!reset) {
        if (jewels<o->jewels) reset=true;
        for (unsigned i=0;i<32;i++) if (o->clear_flags[i] & ~r[CLEAR_FLAGS+i]) reset=true;
        if (o->secrets & ~secrets) reset=true;
    }
    /* After a refusal `baseline` is false, so recovery lands here: the
     * current valid observation becomes the new baseline and emits nothing. */
    if (reset) {
        o->epilogue=false; o->finished=false; o->solid_arm=false;
    } else {
        if (active && o->active) {
            if (rooms>o->rooms && !emit(o,"rooms.cleared",rooms)) return false;
            if (jewels>o->jewels && !emit(o,"jewels.collected",jewels)) return false;
            for (size_t i=0;i<companion_gaia_secret_flag_count;i++)
                if ((secrets & ~o->secrets) & (UINT32_C(1)<<i) &&
                    !emit(o,companion_gaia_secret_flags[i].event,1)) return false;
        }
        /* Leaving the lair any other way (the game-over return) disarms. */
        if (scene!=o->scene && scene!=SOLID_ARM_LAIR) {
            bool beaten=o->solid_arm && scene==BABEL_UPPER;
            o->solid_arm=false;
            if (beaten && !emit(o,"secret.solid-arm",1)) return false;
        }
        if (scene==SOLID_ARM_LAIR && active && o->active && word(r+ENEMIES_LEFT))
            o->solid_arm=true;
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
    o->secrets=secrets;
    o->problem=COMPANION_GAIA_OK;
    memcpy(o->clear_flags,r+CLEAR_FLAGS,32);
    return true;
}
