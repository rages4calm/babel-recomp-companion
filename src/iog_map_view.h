#ifndef IOG_MAP_VIEW_H
#define IOG_MAP_VIEW_H
#include "iog_map_discovery.h"

typedef struct IogMapViewColor {uint8_t r,g,b,a;} IogMapViewColor;
typedef enum IogMapViewMode {kIogMapViewScenery,kIogMapViewRadar} IogMapViewMode;
typedef struct IogMapViewTransform {
    /* World-cell origin = origin_numerator/origin_denominator. Scale is
     * destination pixels per world cell = scale_numerator/scale_denominator. */
    int32_t origin_x_numerator,origin_y_numerator;
    uint16_t origin_denominator,scale_numerator,scale_denominator;
} IogMapViewTransform;
typedef struct IogMapViewMarker {
    int16_t cell_x,cell_y;
    uint8_t radius_pixels;
    IogMapViewColor color;
} IogMapViewMarker;
typedef struct IogMapViewSource {
    const IogMapDiscovery *discovery;
    /* Atlas is gridWidth*cellPixels by gridHeight*cellPixels, RGBA8. */
    const uint8_t *scenery_rgba;
    size_t scenery_bytes,scenery_stride;
    uint8_t scenery_cell_pixels;
    const uint8_t *walkable;
    size_t walkable_bytes,walkable_stride;
    const IogMapViewMarker *markers;
    size_t marker_count;
    bool player_present;
    int16_t player_x,player_y;
} IogMapViewSource;
typedef struct IogMapViewSettings {
    IogMapViewMode mode;
    IogMapViewTransform transform;
    IogMapViewColor fog,floor,wall,player;
    uint8_t player_radius_pixels;
} IogMapViewSettings;

/* Pure nearest-sampled host compositor, no text/art generation or guest writes.
 * Bounded to2048x2048 destination,256x256 world cells,16 atlas pixels/cell,
 * 256 markers,radius8. Fog/outside-map pixels are opaque, regardless of input
 * fog alpha. Scenery alpha blends onto that opaque color. Markers appear only
 * on explored pixels; an in-bounds player is intentionally visible through fog.
 * Failure leaves destination unchanged. Output/source buffers must not overlap.
 */
bool IogMapViewRender(uint8_t *destination,size_t bytes,size_t stride,
    unsigned width,unsigned height,const IogMapViewSource *source,
    const IogMapViewSettings *settings);
#endif
