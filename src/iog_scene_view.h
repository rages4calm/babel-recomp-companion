#ifndef IOG_SCENE_VIEW_H
#define IOG_SCENE_VIEW_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

struct Ppu;

/* Finite development preview, not an all-room widescreen or interpolation
 * feature. No ROM pixels, tile arrays or user configuration live here. */
enum { kIogSceneViewMaxWidth = 448, kIogSceneViewHeight = 224 };
typedef enum IogSceneViewGate {
    kIogSceneViewNoSource,
    kIogSceneViewUnsupportedScene,
    kIogSceneViewRandomizer,
    kIogSceneViewUnsupportedLayout,
    kIogSceneViewReady
} IogSceneViewGate;

typedef struct IogSceneViewSource {
    uint16_t scene, form, camera_x, camera_y, world_width, world_height;
    uint32_t layout_signature;
    IogSceneViewGate gate;
} IogSceneViewSource;

typedef struct IogSceneViewGeometry {
    int width, height, extra;
    bool centered_hud;
} IogSceneViewGeometry;

typedef struct IogSceneViewSnapshot {
    uint64_t generation;
    unsigned frame;
    IogSceneViewSource source;
    IogSceneViewGeometry geometry;
} IogSceneViewSnapshot;

typedef struct IogSceneView {
    bool enabled, prepared, complete;
    uint64_t generation;
    IogSceneViewSnapshot pending, snapshot;
} IogSceneView;

/* Only the exact token "1" opts in. Called once by the host; no config write. */
void IogSceneViewInit(IogSceneView *view, const char *preview_token);
void IogSceneViewReset(IogSceneView *view);
bool IogSceneViewReadSource(const uint8_t *ram, size_t ram_size,
                           const struct Ppu *ppu, bool randomizer,
                           IogSceneViewSource *source);
/* Same live-layout contract, separate finite scene selection for the
 * independent world renderer. Legacy preview remains restricted to01/0C. */
bool IogSceneViewReadWorldSource(const uint8_t *ram, size_t ram_size,
                               const struct Ppu *ppu, bool randomizer,
                               IogSceneViewSource *source);
/* False leaves the caller's legacy geometry untouched. An enabled preview
 * contains unsupported rooms/menus in their authentic256-column field. */
bool IogSceneViewPrepare(IogSceneView *view, const IogSceneViewSource *source,
                         int drawable_width, int drawable_height,
                         int pixel_aspect, bool widescreen,
                         IogSceneViewGeometry *geometry);
void IogSceneViewBeginFrame(IogSceneView *view);
void IogSceneViewEndFrame(IogSceneView *view, unsigned frame);
bool IogSceneViewGetSnapshot(const IogSceneView *view,
                             IogSceneViewSnapshot *snapshot);
/* The host owns this completed field. This seam copies its pixels with their
 * real pitch; alpha does not invent object history or blend screenshots.
 * No persistent pixel copy, GPU readback, HD RGB packet or refresh override. */
int IogSceneViewDraw(const IogSceneView *view, uint8_t *dst, size_t pitch,
                     const uint8_t *field, int width, int height, double alpha);

#endif
