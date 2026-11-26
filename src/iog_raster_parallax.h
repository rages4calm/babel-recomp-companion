#ifndef IOG_RASTER_PARALLAX_H
#define IOG_RASTER_PARALLAX_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum { kIogRasterParallaxLines=225, kIogRasterParallaxBands=32 };
typedef struct IogRasterParallaxBand {
    uint16_t first_row,end_row,factor,fixed_phase;
} IogRasterParallaxBand;
typedef struct IogRasterParallax {
    uint16_t scene,source_camera_x,width,height;
    uint8_t band_count,delta_scale,previous_buffer,valid;
    IogRasterParallaxBand bands[kIogRasterParallaxBands];
} IogRasterParallax;

/* Original-USA Itory horizon producer only (15/1A/1C). Caller supplies its
 * already-verified Original identity, the actual SAME picture epoch's 64KB
 * RAM and all225 captured BG2 H-scroll words AFTER each raster service.
 * Actor-composition active RAM can be a frame older: do not substitute it.
 * Reads the original ROM's type01 descriptor; no table/asset is bundled here.
 * All captured rows must match one consistent current/previous buffer phase.
 * A failed calibration leaves output unchanged. No guest state is modified. */
bool IogRasterParallaxPrepare(const uint8_t *rom,size_t rom_bytes,
    bool original_usa_verified,const uint8_t *epoch_ram,size_t ram_bytes,
    const uint16_t *captured_hscroll,size_t captured_lines,
    IogRasterParallax *output);

/* Original Great Wall82/83/85--88/8A/8B, types1E/1F/21. These proportional
 * bands follow the secondary plane's actual vertical coordinate. All225
 * source rows must calibrate before expanded pixels can use the model.
 * Unlike the finite horizon, the wall texture is256 pixels wide and768 or
 * 1024 or2048 high; only X repeats. Output is unchanged on failure. */
bool IogRasterParallaxPrepareWall(const uint8_t *rom,size_t rom_bytes,
    bool original_usa_verified,const uint8_t *epoch_ram,size_t ram_bytes,
    const uint16_t *captured_hscroll,size_t captured_lines,
    IogRasterParallax *output);

/* Original second planes that the band thinker scrolls and that are exactly
 * one hardware tilemap wide, so the plane repeats in X on the console too:
 * Edward's Castle 0A, type00, seven bands down a 256x1024 plane (five
 * proportional to the camera, two that drift), and the Gold Ship 2B/2C,
 * type05, twenty-nine drifting bands of sky and sea on a 512x512 plane.
 * Bands are read from the ROM descriptor and the current accumulators of the
 * same picture epoch. Nothing is calibrated here: the caller keeps the
 * captured scroll on every row the raster described and uses this model for
 * the rows it did not. Output is unchanged on failure. */
bool IogRasterParallaxPrepareBands(const uint8_t *rom,size_t rom_bytes,
    bool original_usa_verified,const uint8_t *epoch_ram,size_t ram_bytes,
    IogRasterParallax *output);

/* The plane rows [first,end) of the band that holds plane_y. */
bool IogRasterParallaxBandRows(const IogRasterParallax *model,int plane_y,
    int *first,int *end);

/* Sample the finite horizon's own row, not foreground native_y. X repeats
 * through the caller's normal background map sampler; Y is finite to height.
 * host_camera_x is the host view origin. Fractional phase remains12.4 until
 * the final divide, including negative-camera continuation. Return the real
 * hardware10-bit scroll phase. Native-camera sampling reproduces calibration.
 * Invalid requests leave output unchanged. This is not a general HDMA model. */
bool IogRasterParallaxSample(const IogRasterParallax *model,int plane_y,
    int host_camera_x,uint16_t *hscroll);
#endif
