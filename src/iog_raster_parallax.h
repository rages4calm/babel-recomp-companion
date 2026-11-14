#ifndef IOG_RASTER_PARALLAX_H
#define IOG_RASTER_PARALLAX_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum { kIogRasterParallaxLines=225, kIogRasterParallaxBands=8 };
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

/* Sample the finite horizon's own row, not foreground native_y. X repeats
 * through the caller's normal background map sampler; Y is limited to0..255.
 * host_camera_x is the host view origin. Fractional phase remains12.4 until
 * the final divide, including negative-camera continuation. Return the real
 * hardware10-bit scroll phase. Native-camera sampling reproduces calibration.
 * Invalid requests leave output unchanged. This is not a general HDMA model. */
bool IogRasterParallaxSample(const IogRasterParallax *model,int plane_y,
    int host_camera_x,uint16_t *hscroll);
#endif
