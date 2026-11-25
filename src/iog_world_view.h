#ifndef IOG_WORLD_VIEW_H
#define IOG_WORLD_VIEW_H
#include <stdbool.h>
#include <stdint.h>

/* Camera shake can move the original field a small distance outside the
 * authored map, and a scripted pan can begin from an unclamped camera: the
 * Euro arrival starts 88 pixels past the right edge and shows the hardware
 * ring there. This is a finite presentation budget of half a field, not
 * additional map data or permission to sample outside the validated map
 * buffers: the original field keeps its uploaded cells and everything else
 * past the edge stays padding. */
enum { kIogWorldCameraExcursion = 128 };

typedef struct IogWorldView {
    int32_t world_x, world_y;
    uint16_t width, height;
    /* Position of the authoritative 256x224 field within this host view.
     * These offsets can be asymmetric near map edges. */
    uint16_t native_x, native_y;
    uint16_t padding_left, padding_right, padding_top, padding_bottom;
} IogWorldView;

/* Pure presentation geometry. Large maps clamp the host camera inside real
 * content; maps smaller than the requested canvas are centered with explicit
 * balanced padding. The complete original field stays inside the host view
 * during bounded camera shake, including its actual hardware edge pixels;
 * new outside-map space remains explicit padding. Coordinates are signed
 * world values, not an unsigned packed camera register. Guest camera/viewport
 * and pixel proportions never change.
 * Invalid input zeros a valid output and returns false. */
bool IogWorldViewCompute(int32_t camera_x,int32_t camera_y,
    uint32_t map_width,uint32_t map_height,uint16_t width,uint16_t height,
    IogWorldView *out);

/* The original depth sort's on-screen test for one axis, with the window as
 * parameters: the actor's left/top edge (position - origin) lies inside
 * [window, window+span), or it lies before the window and position + extent
 * reaches into it. window = camera and span = 256 (224 vertically) is exactly
 * the stock rule, including its 16-bit wrap. */
bool IogWorldViewAxisOnscreen(uint16_t position,uint16_t origin,uint16_t extent,
    int32_t window,uint16_t span);
#endif
