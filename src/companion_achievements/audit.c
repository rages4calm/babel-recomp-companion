/* SPDX-License-Identifier: MIT */
#include "audit.h"
#include "observer.h"

#include "common_rtl.h"
#include "iog_cheat_rates.h"
#include "iog_randomizer.h"
#include "mod_runtime.h"
#include "sha256.h"
#include "snes/cart.h"
#include "snes/snes.h"
#include "snesrecomp_rom_identity.h"
#ifdef IOG_ACHIEVEMENT_STORAGE
#include "host_paths.h"
#include "progress.h"
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern Snes *g_snes;

static companion_gaia_observer observer;
static const uint8_t *verified_rom;
static uint64_t generation;
static unsigned observed_frame;
static bool read_only;
#ifdef IOG_ACHIEVEMENT_STORAGE
static bool save_progress;
static IogAchievementStore *store;
static bool eligible;
#endif

void IogAchievementAuditStart(int argc, char **argv)
{
    const char *flag = getenv("IOG_ACHIEVEMENT_AUDIT");
    read_only = flag && !strcmp(flag, "1");
#if defined(IOG_ACHIEVEMENT_STORAGE) && !SNESRECOMP_TRACE
    flag = getenv("IOG_ACHIEVEMENT_PROGRESS");
    /* Local progress is recorded unless IOG_ACHIEVEMENT_PROGRESS=0. */
    if (read_only || (flag && !strcmp(flag, "0"))) return;
    static const char *const diagnostics[] = {
        "SNESRECOMP_RUN_FRAMES", "SNESRECOMP_DEBUG_PORT", "SNESRECOMP_OVERLAY_SELFTEST_PAD",
        "SNESRECOMP_COMPANION_SELFTEST_PAD", "SNESRECOMP_CLASSROOM_PAD_ROUTE",
        "SNES_NET_MENU_SELFTEST", "SNESRECOMP_CAPTURE_OUT",
    };
    for (size_t i = 0; i < sizeof(diagnostics) / sizeof(*diagnostics); ++i)
        if (getenv(diagnostics[i])) return;
    /* Anything that plays, pauses or records the session for the player
     * (host_args.c). Matched as prefixes so "--flag=value" counts too. */
    static const char *const automation[] = {
        "--script", "--paused", "--start-paused", "--resume-state", "--netplay",
        "--framedump", "--capture-",
#ifndef IOG_ACHIEVEMENT_TEST_INPUT
        /* A developer build configured with IOG_ACHIEVEMENT_TEST_INPUT=ON (off
         * by default, never set for releases) may drive a real unlock through
         * these, to test unlocks, saving and restarts end to end. */
        "--input-script", "--load-state", "--exit-at-frame",
#endif
    };
    for (int i = 1; i < argc; ++i)
        for (size_t k = 0; k < sizeof(automation) / sizeof(*automation); ++k)
            if (!strncmp(argv[i], automation[k], strlen(automation[k]))) return;
    save_progress = true;
#else
    (void)argc;
    (void)argv;
#endif
}

const char *IogAchievementAuditSnapshot(ca_state states[CA_MAX_ACHIEVEMENTS], uint64_t *notices)
{
    *notices = 0;
    memset(states, 0, CA_MAX_ACHIEVEMENTS * sizeof(*states));
    if (read_only) return "Read-only audit";
#ifdef IOG_ACHIEVEMENT_STORAGE
    if (!save_progress) return "Progress disabled in this session";
    if (!eligible) return "Progress unavailable for this game session";
    if (!store) return "Progress unavailable";
    switch (IogAchievementStoreSnapshot(store, states, notices)) {
    case kIogAchievementLoading: return "Loading local progress";
    case kIogAchievementReady: return "Local progress";
    case kIogAchievementInUse: return "Profile open in another game window";
    case kIogAchievementInvalidProfile: return "Profile could not be read";
    case kIogAchievementWriteFailure: return "Unable to save progress";
    }
#endif
    return "Progress unavailable";
}

void IogAchievementAuditShutdown(void)
{
#ifdef IOG_ACHIEVEMENT_STORAGE
    IogAchievementStoreClose(store);
    store = NULL;
#endif
}

static bool Report(void *context, const char *event, uint32_t amount)
{
    (void)context;
    if (read_only) {
        fprintf(stderr, "[iog_achievement_audit] frame=%u generation=%llu event=%s amount=%u\n",
            observed_frame, (unsigned long long)generation, event, amount);
        return true;
    }
#ifdef IOG_ACHIEVEMENT_STORAGE
    if (!IogAchievementStoreEvent(store, event, amount)) {
        fputs("[iog_achievements] progress cue could not be saved for this session\n", stderr);
        return false;
    }
    return true;
#else
    return false;
#endif
}

void IogAchievementAuditBind(void)
{
    verified_rom = NULL;
#ifdef IOG_ACHIEVEMENT_STORAGE
    eligible = false;
#endif
    const Cart *cart = g_snes ? g_snes->cart : NULL;
    bool enabled = read_only;
#ifdef IOG_ACHIEVEMENT_STORAGE
    enabled |= save_progress;
#endif
    if (!enabled || !cart || !cart->rom ||
        cart->type != CART_HIROM || cart->romImageSize != 0x200000 ||
        cart->romSize < cart->romImageSize)
        return;

    uint8_t bytes[32];
    char hash[65];
    sha256_compute(cart->rom, cart->romImageSize, bytes);
    for (unsigned i = 0; i < sizeof(bytes); ++i)
        snprintf(hash + i * 2, 3, "%02x", bytes[i]);
    if (strcmp(hash, SNESRECOMP_ROM_EXPECTED_SHA256))
        return;

    verified_rom = cart->rom;
    companion_gaia_observer_init(&observer, Report, NULL);
    ++generation;
    if (read_only) fputs("[iog_achievement_audit] observing stock signals in read-only mode\n", stderr);
}

void IogAchievementAuditInvalidate(void)
{
    if (!verified_rom || RtlSpeculativeFrame())
        return;
    ++generation;
    companion_gaia_observer_invalidate(&observer);
}

void IogAchievementAuditFrame(unsigned frame)
{
    if (!verified_rom || RtlSpeculativeFrame() || !g_snes || !g_snes->cart || !g_snes->ram)
        return;
    const Cart *cart = g_snes->cart;
    const uint8_t *ram = g_snes->ram;
    observed_frame = frame;
    const companion_gaia_frame sample = {
        .ram = ram, .rom = cart->rom,
        .ram_size = 0x20000, .rom_size = cart->romImageSize,
        .generation = generation,
        .verified_stock_rom = cart->rom == verified_rom && !IogRandomizerActive() &&
            snes_mod_runtime_feature_enabled_c("iog.apocalypse", "apocalypse_gaia") <= 0,
        .cheats_used = IogCheatsSessionTainted(),
        .new_game_plus = (ram[0x0b54] & 0x7f) != 0,
        /* Assisted routes may qualify signal timing. This sink has no
         * profile, progress engine or other way to award an achievement. */
        .diagnostic = false,
    };
#ifdef IOG_ACHIEVEMENT_STORAGE
    if (!read_only) {
        eligible = sample.verified_stock_rom && !sample.cheats_used && !sample.new_game_plus;
        if (!eligible) {
            IogAchievementAuditInvalidate();
            return;
        }
        if (!store) {
            /* Delay file access until the verified game has entered play. */
            if (!(ram[0x09aa] | ram[0x09ab])) return;
            char directory[4096];
            if (snesrecomp_exe_dir_path("UserData/Achievements/illusion-of-gaia/stock-companion/unseeded",
                                        directory, sizeof(directory)))
                store = IogAchievementStoreOpen(directory);
            if (!store) { verified_rom = NULL; return; }
        }
        const unsigned scene = ram[0x0644] | (unsigned)ram[0x0645] << 8;
        if (scene == 0xfa) { IogAchievementAuditInvalidate(); return; }
    }
#endif
    (void)companion_gaia_observe(&observer, &sample);
}
