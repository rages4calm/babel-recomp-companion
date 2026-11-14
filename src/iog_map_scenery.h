#ifndef IOG_MAP_SCENERY_H
#define IOG_MAP_SCENERY_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* A passive snapshot of one actual Mode 1 4bpp scenery layer. No sprites,
 * HUD, guest execution, visibility changes or extracted art is bundled here.
 * The caller validates the content identity and chooses the authored crop.
 * Map cells are 16x16, page packed in 256x256 pages, as in the game. */
typedef struct IogMapScenerySource {
    const uint8_t *ram;
    size_t ram_bytes;
    const uint16_t *vram, *cgram;
    size_t vram_words, cgram_words;
    unsigned width, height, map_address, definitions_address, character_address;
} IogMapScenerySource;

/* Native integer pixel sampling: step=1,2,4,8. Crop and step never stretch
 * either axis. Output is opaque full-brightness BGRX for nonzero character
 * pixels and transparent zero for index0; compose layers in the caller.
 * Failure leaves the entire output unchanged. Source and output may not alias.
 * Exact destination width/height = ceil(crop_width/step), ceil(height/step). */
bool IogMapSceneryRender(const IogMapScenerySource *source,
    unsigned x, unsigned y, unsigned crop_width, unsigned crop_height,
    unsigned step, uint32_t *output, size_t output_bytes, size_t pitch_bytes);
/* Two aligned, finite Mode1 layers in the same world coordinate system.
 * physical_primary is0 for BG1 or1 for BG2; secondary is the other plane.
 * Exact priority: BG1 high > BG2 high > BG1 low > BG2 low (tile bit13).
 * Crop must fit primary. Outside secondary's own extent is transparent;
 * no wrapping, scrolling offsets, color math, sprites or HUD are applied.
 * Both index0 returns transparent0; an opaque atlas caller may fill CGRAM0.
 * All source/output validation completes before any output is written. */
bool IogMapSceneryRenderMode1Composite(const IogMapScenerySource *primary,
    const IogMapScenerySource *secondary, unsigned physical_primary,
    unsigned x, unsigned y, unsigned crop_width, unsigned crop_height,
    unsigned step, uint32_t *output, size_t output_bytes, size_t pitch_bytes);
#endif
