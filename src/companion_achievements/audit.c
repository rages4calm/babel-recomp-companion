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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern Snes *g_snes;

static companion_gaia_observer observer;
static const uint8_t *verified_rom;
static uint64_t generation;
static unsigned observed_frame;

static bool Report(void *context, const char *event, uint32_t amount)
{
    (void)context;
    fprintf(stderr, "[iog_achievement_audit] frame=%u generation=%llu event=%s amount=%u\n",
            observed_frame, (unsigned long long)generation, event, amount);
    return true;
}

void IogAchievementAuditBind(void)
{
    verified_rom = NULL;
    const char *enabled = getenv("IOG_ACHIEVEMENT_AUDIT");
    const Cart *cart = g_snes ? g_snes->cart : NULL;
    if (!enabled || strcmp(enabled, "1") || !cart || !cart->rom ||
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
    fputs("[iog_achievement_audit] observing stock signals in read-only mode\n", stderr);
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
    (void)companion_gaia_observe(&observer, &sample);
}
