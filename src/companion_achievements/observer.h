/* SPDX-License-Identifier: MIT */
#ifndef COMPANION_GAIA_OBSERVER_H
#define COMPANION_GAIA_OBSERVER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* An observation adapter, not a live-game integration. No storage, guest
 * mutation, clock access, allocation or native/RA dependency. The host must
 * invalidate at EVERY save/state load, rewind, reset and ROM/profile change. */
typedef bool (*companion_gaia_event)(void *, const char *, uint32_t);
typedef struct {
    const uint8_t *ram, *rom;
    size_t ram_size, rom_size;
    uint64_t generation;
    bool verified_stock_rom; /* false for Apocalypse, IoGR, unknown ROMs */
    bool cheats_used;        /* sticky for the whole session, not current toggle */
    bool diagnostic;         /* assisted fixtures/replays never award live progress */
    bool new_game_plus;      /* separate edition not yet defined */
} companion_gaia_frame;
/* Why the last observation was refused, so the host can say so instead of
 * stopping silently. Everything except EVENT_LOST clears on the next valid
 * observation, which rebaselines silently (nothing seen while refused is ever
 * awarded); EVENT_LOST is latched with `failed`. */
typedef enum {
    COMPANION_GAIA_OK,
    COMPANION_GAIA_BAD_FRAME,        /* RAM/ROM missing or too small */
    COMPANION_GAIA_BAD_JEWEL_DIGITS, /* $0AB0 is not BCD 00-59 */
    COMPANION_GAIA_TOO_MANY_JEWELS,  /* more than 50 Red Jewels in total */
    COMPANION_GAIA_EVENT_LOST,       /* an event could not be delivered */
} companion_gaia_problem;
/* Optional content with no story route through it: each event flag below is
 * set by exactly one game script, the one that rewards that secret (writers
 * checked in the disassembly; see docs/ACHIEVEMENTS-INTEGRATION.md). Flag n
 * is bit n&7 of $0A00 + n/8. The event fires once when the flag is seen
 * going from clear to set between two in-play observations of one
 * generation; a flag already set at a baseline never fires. */
typedef struct { const char *event; uint16_t flag; } companion_gaia_secret_flag;
extern const companion_gaia_secret_flag companion_gaia_secret_flags[];
extern const size_t companion_gaia_secret_flag_count;
/* Solid Arm sets no flag when beaten: his script warps from his lair ($EA)
 * to Babel's upper floors ($E3), the lair's only way out besides the
 * game-over return to the mansion. "secret.solid-arm" fires on that scene
 * change, armed only by an in-play lair observation with an enemy still
 * standing ($0AEC), so a state saved after the defeat never arms it. */
typedef struct {
    uint64_t generation;
    unsigned jewels, rooms;
    uint16_t scene;
    uint8_t clear_flags[32];
    uint32_t secrets;  /* companion_gaia_secret_flags seen set, by index */
    bool baseline, active, epilogue, finished, failed, solid_arm;
    companion_gaia_problem problem;
    companion_gaia_event event;
    void *context;
} companion_gaia_observer;
void companion_gaia_observer_init(companion_gaia_observer *, companion_gaia_event, void *);
void companion_gaia_observer_invalidate(companion_gaia_observer *);
/* false means invalid observation or failed event enqueue; `problem` says
 * which. A failed enqueue latches failure until reinitialization, so tracking
 * cannot silently recover after dropping a fact. Noneligible observations
 * reset the baseline silently and are not a problem. */
bool companion_gaia_observe(companion_gaia_observer *, const companion_gaia_frame *);
#endif
