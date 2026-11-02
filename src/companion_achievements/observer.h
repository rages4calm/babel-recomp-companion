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
typedef struct {
    uint64_t generation;
    unsigned jewels, rooms;
    uint16_t scene;
    uint8_t clear_flags[32];
    bool baseline, active, epilogue, finished, failed;
    companion_gaia_event event;
    void *context;
} companion_gaia_observer;
void companion_gaia_observer_init(companion_gaia_observer *, companion_gaia_event, void *);
void companion_gaia_observer_invalidate(companion_gaia_observer *);
/* false means invalid observation or failed event enqueue. A failed enqueue
 * latches failure until reinitialization, so tracking cannot silently recover
 * after dropping a fact. Noneligible observations reset the baseline silently. */
bool companion_gaia_observe(companion_gaia_observer *, const companion_gaia_frame *);
#endif
