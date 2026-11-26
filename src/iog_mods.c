/*
 * Illusion of Gaia gameplay mods: trusted plugins selected by the packages in
 * mods/preloaded/packages (iog.enhancements, iog.cheats).
 *
 * Each one runs at the end of a guest frame (snes_mod_register_frame_callback)
 * and works on WRAM only, so the stock ROM and the recompiled code are
 * untouched and a disabled feature leaves the game exactly as shipped.
 *
 * WRAM layout used here (GaiaLabs' RAM map and patches, and the game's own
 * save routine at $0B:EDC2 for the stats):
 *   (buttons: the physical pad, g_snes->input1_currentState; during play the
 *   game rewrites its own copies at $0656/$0660 through the button type,
 *   so those do not name physical buttons)
 *   $09AA  player actor (0: none)       $09AE  player control flags
 *   $09B2  dash speed east/west         $09B4  dash speed north/south
 *   $09B8  dash brake counter
 *   $0ACE  HP   $0ACA  max HP   $0AD6  DP   $0ADC  DEF   $0ADE  STR
 *
 * The behaviour follows the GaiaLabs enhancement patches (RunButton.asm) as
 * documentation; the code is this project's own.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common_cpu_infra.h"
#include "common_rtl.h"
#include "mod_runtime.h"
#include "snes/snes.h"
#include "snes/cart.h"
#include "present_filter.h"
#include "snes_ra.h"
#include "iog_cheat_rates.h"
#include "iog_randomizer.h"

static uint16_t Rd(uint32_t a) { return g_snes->ram[a] | g_snes->ram[a + 1] << 8; }
static void Wr(uint32_t a, uint16_t v) { g_snes->ram[a] = (uint8_t)v; g_snes->ram[a + 1] = (uint8_t)(v >> 8); }

static long OptionInt(const char *pkg, const char *feature, const char *option, long fallback)
{
    char v[32];
    if (snes_mod_runtime_feature_option_value_c(pkg, feature, option, v, sizeof(v)) > 0 && v[0])
        return strtol(v, NULL, 0);
    return fallback;
}

/* ---- run button ---------------------------------------------------------- */

/* Physical pad, in the controller's serial order (bit 0 = B). */
enum {
    kPadB = 0x001, kPadY = 0x002, kPadSelect = 0x004, kPadStart = 0x008,
    kPadUp = 0x010, kPadDown = 0x020, kPadLeft = 0x040, kPadRight = 0x080,
    kPadA = 0x100, kPadX = 0x200, kPadL = 0x400, kPadR = 0x800,
};
static uint16_t Pad(void) { return g_snes->input1_currentState & 0x0FFF; }

static uint16_t g_run_mask = kPadY;
static bool g_run_on;     /* iog.enhancements/run */
static bool g_auto_run;   /* run style "auto": Drewish's build-up auto-run */

/* Auto-run, after Drewish's Gaia and Time (RunButtonCore.patch.asm, used as
 * documentation; the code is this project's own). Each frame Will actually
 * moves with a direction held earns 1 point, or 8 with the run button held.
 * At 120 he runs in that direction for as long as he keeps moving. A sideways
 * turn keeps the progress and redirects the run; reversing, stopping, a wall
 * or a lock resets it. Host-side state only: nothing is stored in the game. */
enum { kAutoRunFull = 120 };
static uint16_t g_ar_progress, g_ar_dir = 0xFFFF, g_ar_x, g_ar_y;
static bool g_ar_have_pos;

static void AutoRunReset(void) { g_ar_progress = 0; }

static void AutoRunTick(uint16_t pad)
{
    const uint16_t actor = Rd(0x09AA);
    const uint16_t dirs = pad & (kPadRight | kPadLeft | kPadDown | kPadUp);
    if (!actor || actor < 0x1000 || actor >= 0x1FC0) {
        g_ar_have_pos = false; AutoRunReset(); return;
    }
    const uint16_t x = Rd(actor + 0x14), y = Rd(actor + 0x16);
    const bool moved = g_ar_have_pos && (x != g_ar_x || y != g_ar_y);
    g_ar_x = x; g_ar_y = y; g_ar_have_pos = true;
    if (!dirs || !moved || (Rd(0x09AE) & 0x3A00)) {
        AutoRunReset(); return;
    }
    /* 0 east, 1 west, 2 south, 3 north: opposites differ in bit 0. The same
     * priority as the hold-to-run mode. */
    const uint16_t dir = (dirs & kPadRight) ? 0 : (dirs & kPadLeft) ? 1 : (dirs & kPadDown) ? 2 : 3;
    if (g_ar_dir != 0xFFFF && (dir ^ g_ar_dir) == 1) {
        if (g_ar_progress >= kAutoRunFull) {
            Wr(0x09B2, 0); Wr(0x09B4, 0); Wr(0x09B8, 0);
        }
        g_ar_progress = 0;
    }
    g_ar_dir = dir;
    if (g_ar_progress < kAutoRunFull) {
        g_ar_progress += (pad & g_run_mask) ? 8 : 1;
        if (g_ar_progress < kAutoRunFull)
            return;
    }
    g_ar_progress = kAutoRunFull;
    const uint16_t speed = (dir & 1) ? 0xFFFD : 3;
    if (dir & 2) { Wr(0x09B2, 0); Wr(0x09B4, speed); }
    else         { Wr(0x09B4, 0); Wr(0x09B2, speed); }
    Wr(0x09B8, 0);
}

/* Holding the run button with a direction starts the game's own dash (the
 * one Will uses after a charged step), in that direction, whenever the game
 * would let the player move. The dash ends by itself like any other. */
static void RunFrame(void)
{
    if (!g_snes || !g_run_on)
        return;
    const uint16_t pad = Pad();
    /* The host callback also runs in the inventory and during text.
     * Those paths can retain a player actor and unlocked09AE. Checking only
     * those fields is insufficient here. Never queue a dash to leak out
     * of a menu or let a held run button move the player during dialogue. */
    if (Rd(0x0644) == 0x00FF || (Rd(0x09EC) & 0x2000)) {
        AutoRunReset(); g_ar_have_pos = false;
        return;
    }
    if (g_auto_run) {
        AutoRunTick(pad);
        return;
    }
    if (!(pad & g_run_mask))
        return;
    if (!Rd(0x09AA) || Rd(0x09B2) || Rd(0x09B4) || (Rd(0x09AE) & 0x3800))
        return;   /* no player, dashing already, or movement locked/ladder */
    const uint16_t dir = pad;
    if (dir & kPadRight)
        Wr(0x09B2, 3);
    else if (dir & kPadLeft)
        Wr(0x09B2, 0xFFFD);
    else if (dir & kPadDown)
        Wr(0x09B4, 3);
    else if (dir & kPadUp)
        Wr(0x09B4, 0xFFFD);
    else
        return;
    Wr(0x09B8, 0);
}

static void ActivateRun(void)
{
    char v[16] = "Y";
    snes_mod_runtime_feature_option_value_c("iog.enhancements", "run", "button", v, sizeof(v));
    /* L and R are the game's guard, which locks the dash; they are not offered. */
    g_run_mask = !strcmp(v, "X") ? kPadX : kPadY;
    char style[16] = "auto";
    snes_mod_runtime_feature_option_value_c("iog.enhancements", "run", "style", style, sizeof(style));
    g_auto_run = strcmp(style, "hold") != 0;
    AutoRunReset(); g_ar_dir = 0xFFFF; g_ar_have_pos = false;
    g_run_on = true;
}

/* In-game settings: 0 off, 1 hold to run, 2 auto-run. */
int IogRunGet(void) { return !g_run_on ? 0 : g_auto_run ? 2 : 1; }
void IogRunSet(int v)
{
    g_run_on = v != 0;
    if (v) g_auto_run = v == 2;
    AutoRunReset(); g_ar_dir = 0xFFFF;
    snes_mod_runtime_persist_feature_c("iog.enhancements", "run", v != 0,
                                       v ? "style" : NULL, v == 2 ? "auto" : "hold");
}

/* ---- text speed ------------------------------------------------------------ */

/* After Drewish's Gaia and Time (TextSpeedOption.patch.asm, as documentation).
 * The game's per-letter wait ($03:E7BA) waits $7E frames for each letter;
 * scripts set $7E for paced lines and leave 0 for the usual instant text.
 * While a message is up this keeps what the script asked for and writes the
 * delay for the chosen speed instead, and puts the script's value back when
 * the message closes:
 *   normal     the script's pace; holding the run button halves it
 *   cinematic  one frame per letter where the script sets no pace (held run:
 *              none), the script's pace otherwise (held run: half)
 *   instant    no waits at all
 * Works the same in native code and the interpreter: it only touches $7E. */
enum { kTextNormal, kTextCinematic, kTextInstant };
static int g_text_speed = -1;   /* -1: feature off, the game's own pacing */
static bool g_text_active;
static uint8_t g_text_authored, g_text_written;

static void TextSpeedFrame(void)
{
    if (!g_snes)
        return;
    uint8_t *delay = &g_snes->ram[0x7E];
    const bool up = (Rd(0x09EC) & 0x2000) != 0;
    if (g_text_speed < 0 || !up) {
        if (g_text_active && *delay == g_text_written)
            *delay = g_text_authored;
        g_text_active = false;
        return;
    }
    if (!g_text_active || *delay != g_text_written)
        g_text_authored = *delay;   /* the script set a new pace */
    g_text_active = true;
    const bool hurry = (Pad() & g_run_mask) != 0;
    uint8_t want;
    if (g_text_speed == kTextInstant)
        want = 0;
    else if (g_text_speed == kTextCinematic && !g_text_authored)
        want = hurry ? 0 : 1;
    else
        want = hurry ? (uint8_t)((g_text_authored + 1) >> 1) : g_text_authored;
    *delay = want;
    g_text_written = want;
}

static int TextSpeedFromName(const char *v)
{
    return !strcmp(v, "cinematic") ? kTextCinematic : !strcmp(v, "instant") ? kTextInstant : kTextNormal;
}

static void ActivateTextSpeed(void)
{
    char v[16] = "normal";
    snes_mod_runtime_feature_option_value_c("iog.enhancements", "text_speed", "speed", v, sizeof(v));
    g_text_speed = TextSpeedFromName(v);
    /* The run button that hurries text is the run feature's choice. */
    char b[16] = "Y";
    snes_mod_runtime_feature_option_value_c("iog.enhancements", "run", "button", b, sizeof(b));
    g_run_mask = !strcmp(b, "X") ? kPadX : kPadY;
}

/* In-game settings: 0 off (the game's pacing), 1 normal, 2 cinematic, 3 instant. */
int IogTextSpeedGet(void) { return g_text_speed + 1; }
void IogTextSpeedSet(int v)
{
    static const char *const kNames[] = {"normal", "normal", "cinematic", "instant"};
    g_text_speed = (v & 3) - 1;
    snes_mod_runtime_persist_feature_c("iog.enhancements", "text_speed", v != 0,
                                       v ? "speed" : NULL, kNames[v & 3]);
}

/* ---- item hotswapping ---------------------------------------------------- */

/* Holding the modifier, L/R step the equipped item through the inventory
 * ($0AB4, 16 slots) in either direction; past either end nothing is
 * equipped. The game's item-select sound confirms it (COP 07 #$10 just
 * stores the effect in $06F8 for the next NMI). */
static uint16_t g_swap_mod = kPadX, g_swap_prev;

static void SwapFrame(void)
{
    if (!g_snes)
        return;
    const uint16_t pad = Pad(), pressed = pad & ~g_swap_prev;
    g_swap_prev = pad;
    if (!(pad & g_swap_mod) || !(pressed & (kPadL | kPadR)))
        return;
    if (!Rd(0x09AA) || (Rd(0x09EC) & 0x4000))
        return;   /* no player, or a menu/message is up */
    const uint8_t *slots = &g_snes->ram[0x0AB4];
    int slot = (int16_t)Rd(0x0AC4);
    if (pressed & kPadR) {
        do slot++; while (slot < 16 && !slots[slot]);
    } else {
        if (slot < 0) slot = 16;
        do slot--; while (slot >= 0 && !slots[slot]);
    }
    if (slot < 0 || slot >= 16) {
        Wr(0x0AC4, 0xFFFF);
        Wr(0x0AC6, 0);
    } else {
        Wr(0x0AC4, (uint16_t)slot);
        Wr(0x0AC6, slots[slot]);
    }
    g_snes->ram[0x06F8] = 0x10;
}

static void ActivateSwap(void)
{
    char v[16] = "X";
    snes_mod_runtime_feature_option_value_c("iog.enhancements", "hotswap", "modifier", v, sizeof(v));
    g_swap_mod = !strcmp(v, "Y") ? kPadY : !strcmp(v, "Select") ? kPadSelect : kPadX;
    g_swap_prev = 0;
    snes_mod_register_frame_callback(SwapFrame);
}

/* ---- cheats -------------------------------------------------------------- */

/* Live switches (the in-game settings): the frame callbacks are always
 * installed (ResetHd) and do nothing while off. */
static int g_cheat_hp, g_cheat_dp, g_cheat_stats;
static int g_room_reward_multiplier=1;
static bool g_cheat_session_tainted;
static IogCheatRateTracker g_room_reward_tracker;

void IogCheatsMarkUsed(void) { g_cheat_session_tainted=true; }
bool IogCheatsSessionTainted(void) { return g_cheat_session_tainted; }
void IogCheatRatesInvalidate(void)
{ IogCheatRateTrackerInvalidate(&g_room_reward_tracker); }
int IogRoomRewardMultiplierGet(void) { return g_room_reward_multiplier; }
void IogRoomRewardMultiplierSet(int value)
{
    char text[8];
    g_room_reward_multiplier=IogCheatRateClampMultiplier(value);
    IogCheatRatesInvalidate();
    if(g_room_reward_multiplier>1) IogCheatsMarkUsed();
    snprintf(text,sizeof text,"%d",g_room_reward_multiplier);
    snes_mod_runtime_persist_feature_c("iog.cheats","room_rewards",
        g_room_reward_multiplier>1,"multiplier",text);
}

/* The framework excludes speculative run-ahead frames from mod callbacks.
 * Only exact observed original stat awards may produce bounded extra points. */
static void RoomRewardFrame(void)
{
    IogCheatRateSample sample={0};
    if(g_room_reward_multiplier==1||!g_snes||!g_snes->cart) {
        IogCheatRatesInvalidate();return;
    }
    sample.generation=RtlStateGeneration();
    sample.scene=Rd(0x0644);sample.player=Rd(0x09AA);sample.hp=Rd(0x0ACE);
    sample.stats[0]=Rd(0x0ACA);sample.stats[1]=Rd(0x0ADE);sample.stats[2]=Rd(0x0ADC);
    memcpy(sample.cleared,g_snes->ram+0x0A60,sizeof sample.cleared);
    sample.supported=IogCheatRateSourceSupported(g_snes->cart->rom,g_snes->cart->romSize);
    sample.blocked=g_cheat_stats||IogRandomizerActive()||
        snes_mod_runtime_feature_enabled_c("iog.apocalypse","apocalypse_gaia")>0||
        (g_snes->ram[0x0B54]&0x7F)!=0;
    if(sample.scene<256&&sample.supported)
        sample.reward_kind=g_snes->cart->rom[0x01AADE + sample.scene];
    IogCheatRateAward award=IogCheatRateStep(&g_room_reward_tracker,&sample,g_room_reward_multiplier);
    if(!award.extra) return;
    static const uint16_t stat_at[]={0x0ACA,0x0ADE,0x0ADC};
    Wr(stat_at[award.kind-1],sample.stats[award.kind-1]+award.extra);
    if(award.kind==1) {
        unsigned hp=(unsigned)sample.hp+award.extra;
        unsigned maximum=(unsigned)sample.stats[0]+award.extra;
        Wr(0x0ACE,(uint16_t)(hp>maximum?maximum:hp));
    }
}

static void InfiniteHpFrame(void)
{
    if (!g_cheat_hp) return;
    /* $0ACE current HP, $0ACA max (the regen at $00:8206 compares them).
     * Zero is left alone so a death already under way is not undone. */
    if (g_snes && Rd(0x09AA) && Rd(0x0ACE) && Rd(0x0ACE) < Rd(0x0ACA))
        Wr(0x0ACE, Rd(0x0ACA));
}

static uint16_t g_min_dp;
static void DpFrame(void)
{
    if (!g_cheat_dp) return;
    if (g_snes && Rd(0x0AD6) < g_min_dp)
        Wr(0x0AD6, g_min_dp);
}

static uint16_t g_min_str, g_min_def, g_min_maxhp;
static void StatsFrame(void)
{
    if (!g_cheat_stats) return;
    if (!g_snes || !Rd(0x09AA))
        return;   /* only in play: the title and file select use the same RAM */
    if (Rd(0x0ADE) < g_min_str)
        Wr(0x0ADE, g_min_str);
    if (Rd(0x0ADC) < g_min_def)
        Wr(0x0ADC, g_min_def);
    if (Rd(0x0ACA) < g_min_maxhp) {   /* max HP; current HP follows */
        Wr(0x0ACA, g_min_maxhp);
        Wr(0x0ACE, g_min_maxhp);
    }
}

/* Cheats make a session unfair for RetroAchievements: not loaded then. */
static const char kRaCheats[] = "cheats are on";

static void ActivateInfiniteHp(void)
{
    IogCheatsMarkUsed();
    SnesRa_SetBlocked(kRaCheats);
    g_cheat_hp = 1;
}

static void ActivateDp(void)
{
    IogCheatsMarkUsed();
    SnesRa_SetBlocked(kRaCheats);
    g_min_dp = (uint16_t)OptionInt("iog.cheats", "dp", "amount", 99);
    if (g_min_dp > 999) g_min_dp = 999;   /* the game's own ceiling */
    g_cheat_dp = 1;
}

static void ActivateStats(void)
{
    IogCheatsMarkUsed();
    SnesRa_SetBlocked(kRaCheats);
    g_min_str = (uint16_t)OptionInt("iog.cheats", "stats", "strength", 0);
    if (g_min_str > 99) g_min_str = 99;   /* the game's own ceiling */
    g_min_def = (uint16_t)OptionInt("iog.cheats", "stats", "defense", 0);
    if (g_min_def > 99) g_min_def = 99;   /* the game's own ceiling */
    g_min_maxhp = (uint16_t)OptionInt("iog.cheats", "stats", "max_hp", 0);
    if (g_min_maxhp > 40) g_min_maxhp = 40;   /* the game's own ceiling */
    g_cheat_stats = 1;
}

static void ActivateRoomRewards(void)
{
    long value=OptionInt("iog.cheats","room_rewards","multiplier",1);
    g_room_reward_multiplier=value<1?1:value>8?8:(int)value;
    IogCheatRatesInvalidate();
    if(g_room_reward_multiplier>1) IogCheatsMarkUsed();
}

/* ---- hold to advance dialogue --------------------------------------------- */

/* Text waits ([FIN] / [WAI], $03:E6A4 / $03:E6D2) act on a NEW press: the
 * edge in $0656, so a held button counts once. While a message is up
 * ($09EC & $2000) and no choice is being asked (COP BE sets $065C = $0F00
 * for its menu and clears it after), the held confirm buttons are let go for
 * one frame in every `g_advance_period`, timed by the NMI counter $36: the
 * next frame is a fresh press and the page turns. A pure function of the
 * pad word and RAM, so run-ahead and netplay frames see the same thing. */
static uint8_t g_advance_period;   /* 0: off */

static uint32_t HoldAdvanceFilter(uint32_t in)
{
    if (!g_advance_period || !g_snes || !Rd(0x09AA))
        return in;
    const uint32_t adv = in & (kPadA | kPadB | kPadY);
    if (!adv || !(Rd(0x09EC) & 0x2000) || Rd(0x065C) != 0)
        return in;
    if ((g_snes->ram[0x36] % g_advance_period) == 0)
        in &= ~adv;
    return in;
}

static void ActivateHoldAdvance(void)
{
    char v[16] = "normal";
    snes_mod_runtime_feature_option_value_c("iog.enhancements", "hold_advance", "speed", v, sizeof(v));
    g_advance_period = !strcmp(v, "fast") ? 8 : !strcmp(v, "slow") ? 32 : 16;
}

/* In-game settings (iog_settings.c): 0 off, 1 slow, 2 normal, 3 fast. */
int IogHoldAdvanceGet(void)
{
    return g_advance_period == 0 ? 0 : g_advance_period == 32 ? 1 : g_advance_period == 16 ? 2 : 3;
}
void IogHoldAdvanceSet(int v)
{
    static const uint8_t kPeriods[] = {0, 32, 16, 8};
    g_advance_period = kPeriods[v & 3];
}

/* ---- Enhanced world map ---------------------------------------------------- */

/* One switch for everything added to the walkable world map: the filtered
 * plane, the higher camera, destination markers, the minimap, the horizon and
 * the prompt plate. Off is the stock walking view. iog_walkable_world.c reads
 * it every frame, so the in-game settings can change it mid-session. */
static int g_world_map_enhanced;
static int g_edge_hud;   /* iog.graphics/edge_hud, below */

static void ActivateWorldMap(void) { g_world_map_enhanced = 1; }
int IogWorldMapEnhancedGet(void) { return g_world_map_enhanced; }
void IogWorldMapEnhancedSet(int on)
{
    g_world_map_enhanced = on != 0;
    snes_mod_runtime_persist_feature_c("iog.enhancements", "world_map", on != 0, NULL, NULL);
}

/* ---- HD scaling (presentation only) -------------------------------------- */

/* How the picture is scaled up to the screen: crisp square pixels, or the
 * art's edges redrawn smooth (present_filter.h). Off: the [Graphics]
 * LinearFiltering setting, as without mods. */
static void ActivateHd(void)
{
    char v[16] = "";
    snes_mod_runtime_feature_option_value_c("iog.graphics", "hd", "filter", v, sizeof(v));
    PresentFilter_Set(strcmp(v, "smooth") == 0 ? kPresentFilter_Smooth : kPresentFilter_Sharp);
}

static void ResetHd(void)
{
    /* The filter is always installed; it does nothing while the period is 0,
     * so the in-game settings can turn it on mid-session. */
    g_advance_period = 0;
    g_run_on = g_auto_run = false;
    g_run_mask = kPadY;
    g_text_speed = -1;
    g_text_active = false;
    snes_mod_register_frame_callback(RunFrame);
    snes_mod_register_frame_callback(TextSpeedFrame);
    g_world_map_enhanced = 0;
    g_edge_hud = 0;
    snes_mod_register_input_filter(HoldAdvanceFilter);
    g_cheat_hp = g_cheat_dp = g_cheat_stats = 0;
    g_room_reward_multiplier=1;
    IogCheatRatesInvalidate();
    g_min_dp = 99;
    snes_mod_register_frame_callback(InfiniteHpFrame);
    snes_mod_register_frame_callback(DpFrame);
    snes_mod_register_frame_callback(StatsFrame);
    snes_mod_register_frame_callback(RoomRewardFrame);
    SnesRa_SetBlocked(NULL);   /* each launch decides again (plugins follow) */
    PresentFilter_Set(kPresentFilter_Config);
}

/* ---- status display at the screen edges (iog.graphics/edge_hud) ----------- */
static void ActivateEdgeHud(void) { g_edge_hud = 1; }
int IogEdgeHudGet(void) { return g_edge_hud; }
void IogEdgeHudSet(int on)
{
    g_edge_hud = on != 0;
    snes_mod_runtime_persist_feature_c("iog.graphics", "edge_hud", on != 0, NULL, NULL);
}

/* Read at start by the world renderer (IogWorldEnabled); nothing to switch here. */
static void ActivateWideView(void) {}

SNES_MOD_CONSTRUCTOR(register_iog_mods)
{
    snes_mod_register_reset_callback(ResetHd);
    snes_mod_register_presentation_plugin("iog.hd", ActivateHd);
    snes_mod_register_presentation_plugin("iog.wide_view", ActivateWideView);
    snes_mod_register_presentation_plugin("iog.edge_hud", ActivateEdgeHud);
    snes_mod_register_activation_plugin("iog.run", ActivateRun);
    snes_mod_register_activation_plugin("iog.hold_advance", ActivateHoldAdvance);
    snes_mod_register_activation_plugin("iog.text_speed", ActivateTextSpeed);
    snes_mod_register_activation_plugin("iog.hotswap", ActivateSwap);
    snes_mod_register_activation_plugin("iog.world_map", ActivateWorldMap);
    snes_mod_register_activation_plugin("iog.cheat.hp", ActivateInfiniteHp);
    snes_mod_register_activation_plugin("iog.cheat.dp", ActivateDp);
    snes_mod_register_activation_plugin("iog.cheat.stats", ActivateStats);
    snes_mod_register_activation_plugin("iog.cheat.room_rewards", ActivateRoomRewards);
}

/* In-game settings (iog_settings.c): 0 infinite HP, 1 DP, 2 stats. */
int IogCheatGet(int which)
{
    return which == 0 ? g_cheat_hp : which == 1 ? g_cheat_dp : g_cheat_stats;
}

void IogCheatSet(int which, int on)
{
    static const char *const kFeat[] = {"infinite_hp", "dp", "stats"};
    if (which < 0 || which > 2) return;
    /* A feature that was disabled at launch did not run its activation
     * plugin. Live enable must use the same authoritative option loading:
     * otherwise Stats silently retains zero minima and DP uses stale99. */
    if (on) {
        if (which == 0) ActivateInfiniteHp();
        else if (which == 1) ActivateDp();
        else ActivateStats();
    } else {
        if (which == 0) g_cheat_hp = 0;
        else if (which == 1) g_cheat_dp = 0;
        else g_cheat_stats = 0;
    }
    snes_mod_runtime_persist_feature_c("iog.cheats", kFeat[which], on != 0, NULL, NULL);
}
