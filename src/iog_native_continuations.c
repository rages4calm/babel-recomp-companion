/* Private per-instruction continuations; no guessed call/return frame. */
#include "iog_native_continuations.h"
#include "common_cpu_infra.h"
#include "snes/interp_bridge.h"
#include "snes/interp_native_wram.h"
#include "snes/cart.h"
#include "sha256.h"
#include "snesrecomp_rom_identity.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
static bool native_nmi_enabled;

bool IogNativeContinuationsNmiEnabled(void) { return native_nmi_enabled; }

#if defined(IOG_HAS_NATIVE_CONTINUATIONS) && !defined(SNESRECOMP_INTERPRETER_ONLY)
extern bool IogRegisterNativeContinuations(void);
#ifdef IOG_HAS_NATIVE_WRAM_CONTINUATIONS
extern bool IogRegisterNativeWramCopyContinuations(void);
#endif
static char stats_path[4096];
static int stats_exit_registered;
static void WriteNativeContinuationStats(void)
{
    size_t count = interp_bridge_native_instruction_stats(NULL, 0);
    InterpNativeInstructionStats *rows = count ? calloc(count, sizeof *rows) : NULL;
    if (count && !rows) return;
    if (count) interp_bridge_native_instruction_stats(rows, count);
    FILE *file = fopen(stats_path, "w");
    if (!file) { free(rows); return; }
    fprintf(file, "{\"schema\":\"iog native continuation stats v1\",\"lookup\":\"%s\",\"insns\":%llu,\"cycles\":%llu,\"wram_copy_insns\":%llu,\"wram_copy_cycles\":%llu,\"sites\":[",
            interp_bridge_native_instruction_index_enabled() ? "direct" : "legacy",
            (unsigned long long)interp_bridge_native_continuation_insns_total(),
            (unsigned long long)interp_bridge_native_continuation_cycles_total(),
            (unsigned long long)interp_bridge_native_wram_copy_insns_total(),
            (unsigned long long)interp_bridge_native_wram_copy_cycles_total());
    for (size_t i = 0; i < count; ++i) {
        const InterpNativeInstructionStats *s = &rows[i];
        fprintf(file, "%s{\"pc24\":\"%06X\",\"m\":%u,\"x\":%u,\"e\":%u,\"insns\":%llu,\"cycles\":%llu}",
                i ? "," : "", (unsigned)s->pc24, s->m, s->x, s->e,
                (unsigned long long)s->insns, (unsigned long long)s->cycles);
    }
    fputs("]}\n", file);
    fclose(file);
    free(rows);
}
#endif

void IogNativeContinuationsInitialize(void)
{
    native_nmi_enabled = false;
    interp_bridge_clear_native_instructions();
#if defined(IOG_HAS_NATIVE_CONTINUATIONS) && !defined(SNESRECOMP_INTERPRETER_ONLY)
    const char *setting = getenv("IOG_NATIVE_CONTINUATIONS");
    if (!setting || strcmp(setting, "1") || !g_snes || !g_snes->cart)
        return;
    const Cart *cart = g_snes->cart;
    if (cart->type != CART_HIROM || !cart->rom ||
        cart->romImageSize != 2097152u || cart->romSize < cart->romImageSize)
        return;
    uint8_t digest[32];
    char actual[65];
    static const char hex[] = "0123456789abcdef";
    sha256_compute(cart->rom, cart->romImageSize, digest);
    for (unsigned i = 0; i < 32; ++i) {
        actual[2 * i] = hex[digest[i] >> 4];
        actual[2 * i + 1] = hex[digest[i] & 15u];
    }
    actual[64] = 0;
    if (strcmp(actual, SNESRECOMP_ROM_EXPECTED_SHA256)) return;
    if (!IogRegisterNativeContinuations()) {
        interp_bridge_clear_native_instructions();
        return;
    }
#ifdef IOG_HAS_NATIVE_WRAM_CONTINUATIONS
    if (!IogRegisterNativeWramCopyContinuations()) {
        interp_bridge_clear_native_instructions();
        return;
    }
    const char *copy_setting = getenv("IOG_NATIVE_WRAM_COPY_CONTINUATIONS");
    interp_bridge_set_native_wram_copy_enabled(
        copy_setting && !strcmp(copy_setting, "1"));
#endif
    const char *frame_setting = getenv("IOG_NATIVE_FRAME_CONTINUATIONS");
    interp_bridge_set_native_frame_effects_enabled(
        frame_setting && !strcmp(frame_setting, "1"));
    const char *nmi_setting = getenv("IOG_NATIVE_NMI_CONTINUATIONS");
    native_nmi_enabled = nmi_setting && !strcmp(nmi_setting, "1") &&
        interp_bridge_native_nmi_grants() != 0;
    const char *path = getenv("IOG_NATIVE_CONTINUATION_STATS");
    if (path && path[0] && strlen(path) < sizeof stats_path) {
        strcpy(stats_path, path);
        if (!stats_exit_registered) {
            atexit(WriteNativeContinuationStats);
            stats_exit_registered = 1;
        }
    }
#endif
}
