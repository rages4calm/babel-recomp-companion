#ifndef IOG_VISUAL_OBJECTS_H
#define IOG_VISUAL_OBJECTS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

struct Ppu;

enum { kIogVisualMaxActors = 84, kIogVisualMaxParts = 512,
       kIogVisualPartPixels = 16 * 16 };

typedef enum IogVisualStatus {
    kIogVisualReady = 0,
    kIogVisualInvalidInput,
    kIogVisualUnsupportedScene,
    kIogVisualUnsupportedFormat,
    kIogVisualMalformedSource,
    kIogVisualCapacity
} IogVisualStatus;

typedef struct IogVisualSource {
    const uint8_t *ram;
    size_t ram_size;
    const uint8_t *rom;
    size_t rom_size;
    const struct Ppu *ppu;
    /* The caller verifies exact stock-USA ROM identity before enabling this
     * adapter. Patched/GaiaLabs/randomizer formats need their own contract. */
    bool stock_identity_verified;
} IogVisualSource;

typedef struct IogVisualViewport {
    int32_t world_x, world_y;
    uint16_t width, height;
} IogVisualViewport;

typedef struct IogVisualPart {
    int32_t world_x, world_y, x, y;
    /* Independent visual order, NOT a guessed hardware OAM owner/slot. Lower
     * order wins an OBJ overlap. Source sequence and repetitions are kept. */
    uint32_t order;
    uint16_t actor, animation, source_index, tile_attributes;
    uint8_t width, height, palette, priority, math, hflip, vflip, manual;
    /* Player pixels come from the current form's original ROM characters,
     * not an assumed resident dynamic VRAM tile or guessed OAM binding. */
    uint8_t player;
    /* RGB15, bit15 opaque (including black); transparent entries are zero.
     * Pixels include the flips already; metadata retains their source flags. */
    uint16_t pixels[kIogVisualPartPixels];
    /* Live CGRAM address for opaque pixels, zero for transparency. A host
     * replay can recolor from a later scanline palette epoch without touching
     * geometry or re-decoding characters. Opacity remains explicit above. */
    uint8_t indices[kIogVisualPartPixels];
} IogVisualPart;

typedef struct IogVisualFrame {
    IogVisualStatus status;
    uint16_t scene, actor_count, part_count, hidden_actors, outside_parts;
    IogVisualViewport viewport;
    IogVisualPart parts[kIogVisualMaxParts];
} IogVisualFrame;

/* Finite stock room-format selection for the independent world adapter.
 * This does not expand the older guest-culling preview's scene policy. */
bool IogVisualObjectsSupportsScene(uint16_t scene);

/* Read at the real original sprite-composition boundary. No simulation,
 * stack, ROM/RAM/PPU writes, callbacks or retained input pointers. Output is
 * caller-owned and immutable until rebuilt. Valid disjoint output gets zero
 * part_count on source/format/capacity failure; no partial list is accepted.
 * Null/overlapping arguments return InvalidInput without accessing output.
 * Inputs/output must not overlap. */
IogVisualStatus IogVisualObjectsBuild(const IogVisualSource *source,
    const IogVisualViewport *viewport, IogVisualFrame *out);

#endif
