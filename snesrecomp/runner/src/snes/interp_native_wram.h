#ifndef SNESRECOMP_INTERP_NATIVE_WRAM_H
#define SNESRECOMP_INTERP_NATIVE_WRAM_H
#include "interp_bridge.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Source-qualified, six-byte bank-copy stub: PHB; MVN dest,src; PLB; RTS.
 * This is a separate contract from immutable upper-ROM instructions. Register
 * exact physical PC/M/X/E entries; only dedicated 7E and the low-WRAM mirrors
 * in 00-3F/80-BF are supported under plain LoROM/HiROM. The entire stub must
 * lie in the first 8 KiB. 40/C0 and 7F are not aliases of this storage.
 *
 * The four opcode bytes are checked directly after pre-opcode hooks. Both MVN
 * bank operands remain live and are fetched through the original bus on EVERY
 * iteration. The callback executes one architectural opcode (one byte moved
 * for MVN), never a whole transfer, and retains all original accesses, cycles,
 * index-width wrapping and owner retirement. No interpreter decoder is called.
 *
 * Callers qualify source provenance and callback semantics; matching RAM is
 * not source identity. Existing exclusions, pending events and finite-owner
 * checks remain. NMI scope names the same exact existing owner; it creates no
 * new interrupt/IRQ/nested owner. Setup is atomic and host-idle only. The
 * launch enable defaults off and is cleared with ordinary registrations. */
typedef struct {
    uint32_t pc24;
    uint16_t stub_pc;
    uint8_t m, x, e, scopes;
    uint32_t nmi_owner_pc24;
    InterpNativeInstructionStep step;
} InterpNativeWramCopyInstruction;

bool interp_bridge_add_native_wram_copy_instructions(
    const InterpNativeWramCopyInstruction *items, size_t count);
void interp_bridge_set_native_wram_copy_enabled(bool enabled);
size_t interp_bridge_native_wram_copy_grants(void);
/* Subsets of NI totals, never additional CPU work. NMI can overlap them. */
uint64_t interp_bridge_native_wram_copy_insns_total(void);
uint64_t interp_bridge_native_wram_copy_cycles_total(void);

#ifdef __cplusplus
}
#endif
#endif
