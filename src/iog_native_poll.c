/* Stock-USA native poll island. No guest iteration is skipped or replayed.
 * Unlike a generated call body, this owns no guest return frame: the active
 * bridge retains its per-opcode IRQ/deadline/quiescence/retirement protocol. */
#include "iog_native_poll.h"

#include <stdlib.h>
#include <string.h>

#include "common_cpu_infra.h"
#include "snes/cart.h"
#include "snes/interp_bridge.h"
#include "snes/snes.h"
#include "sha256.h"
#include "snesrecomp_rom_identity.h"

int IogNativePollStep(Interp816 *in)
{
    if (!in || !in->read || in->e || !in->mf ||
        (in->k & 0x3Fu) != 2u)
        return 0;
    const uint32_t bank = (uint32_t)in->k << 16;
    if (in->pc == 0x804Du) {
        /* The bridge verified immutable AF 10 42 80 bytes before effects.
         * Still perform each architectural fetch, in order, through the
         * authoritative bus. The load changes only A.low, N and Z. */
        (void)in->read(in->mem, bank | in->pc++);
        (void)in->read(in->mem, bank | in->pc++);
        (void)in->read(in->mem, bank | in->pc++);
        (void)in->read(in->mem, bank | in->pc++);
        const uint8_t value = in->read(in->mem, 0x804210u);
        in->a = (in->a & 0xFF00u) | value;
        in->z = value == 0;
        in->n = (value & 0x80u) != 0;
        in->cyclesUsed = 5;
        return 5;
    }
    if (in->pc == 0x8051u) {
        /* BPL -6. The displacement fetch is real; its verified value is
         * compiled into this branch, with no opcode decoder call. */
        (void)in->read(in->mem, bank | in->pc++);
        (void)in->read(in->mem, bank | in->pc++);
        in->cyclesUsed = 2;
        if (!in->n) {
            in->pc = 0x804Du;
            in->cyclesUsed = 3;
        }
        return in->cyclesUsed;
    }
    return 0;
}

void IogNativePollInitialize(void)
{
    interp_bridge_clear_native_rdnmi_polls();
#ifndef SNESRECOMP_INTERPRETER_ONLY
    const char *setting = getenv("IOG_NATIVE_RDNMI_POLL");
    if (!setting || strcmp(setting, "1") != 0 || !g_snes || !g_snes->cart)
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
    if (strcmp(actual, SNESRECOMP_ROM_EXPECTED_SHA256) != 0)
        return;
    static const uint8_t banks[] = {0x02, 0x42, 0x82, 0xC2};
    for (unsigned i = 0; i < sizeof banks; ++i) {
        if (!interp_bridge_add_native_rdnmi_poll(
                ((uint32_t)banks[i] << 16) | 0x804Du, IogNativePollStep)) {
            interp_bridge_clear_native_rdnmi_polls();
            return;
        }
    }
#endif
}
