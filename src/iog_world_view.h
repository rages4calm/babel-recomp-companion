#ifndef IOG_WORLD_VIEW_H
#define IOG_WORLD_VIEW_H
#include <stdbool.h>
#include <stdint.h>

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
 * balanced padding. Guest camera/viewport and pixel proportions never change.
 * Invalid input zeros a valid output and returns false. */
bool IogWorldViewCompute(int32_t camera_x,int32_t camera_y,
    uint32_t map_width,uint32_t map_height,uint16_t width,uint16_t height,
    IogWorldView *out);
#endif
