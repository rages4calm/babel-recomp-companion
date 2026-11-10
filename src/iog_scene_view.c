#include "iog_scene_view.h"
#include "iog_visual_objects.h"

#include <math.h>
#include <string.h>

#include "desktop/display_aspect.h"
#include "snes/ppu.h"
#include "widescreen.h"

static uint16_t Word(const uint8_t *ram, unsigned at)
{
    return (uint16_t)(ram[at] | (uint16_t)ram[at + 1] << 8);
}

void IogSceneViewInit(IogSceneView *view, const char *token)
{
    if (!view) return;
    memset(view, 0, sizeof(*view));
    view->enabled = token && strcmp(token, "1") == 0;
    view->generation = 1;
}

void IogSceneViewReset(IogSceneView *view)
{
    if (!view) return;
    bool enabled = view->enabled;
    uint64_t generation = view->generation + 1;
    memset(view, 0, sizeof(*view));
    view->enabled = enabled;
    view->generation = generation;
}

static bool ReadSource(const uint8_t *ram, size_t size, const Ppu *ppu,
                       bool randomizer, bool independent_world,
                       IogSceneViewSource *out)
{
    if (!out) return false;
    memset(out, 0, sizeof(*out));
    if (!ram || size < 0x20000 || !ppu) return false;
    out->scene = Word(ram, 0x0644);
    out->form = Word(ram, 0x0AD4);
    out->camera_x = Word(ram, 0x068A);
    out->camera_y = Word(ram, 0x068E);
    out->world_width = Word(ram, 0x0692);
    out->world_height = Word(ram, 0x0696);
    out->gate = kIogSceneViewUnsupportedScene;
    /* Keep the older expanded-guest-culling preview at its original two
     * scenes. Independent world composition has its own source-qualified
     * finite room selection; neither admits the spare classroom storage. */
    if (independent_world ? !IogVisualObjectsSupportsScene(out->scene) :
        (out->scene != 0x0001 && out->scene != 0x000C)) return true;
    out->gate = kIogSceneViewRandomizer;
    if (randomizer) return true;
    out->gate = kIogSceneViewUnsupportedLayout;
    if ((ppu->bgmode & 7) != 1 || (ram[0x06EF] & 8)) return true;
    uint32_t signature = 2166136261u;
    for (unsigned i = 0; i < 2; i++) {
        unsigned off = i * 2;
        unsigned physical = i ^ ((ram[0x06EE] >> 7) & 1);
        uint16_t width = Word(ram, 0x0692 + off);
        uint16_t height = Word(ram, 0x0696 + off);
        uint16_t map = Word(ram, 0x069E + off);
        uint16_t definitions = Word(ram, 0x06AE + off);
        uint32_t bytes = (uint32_t)(width >> 8) * (height >> 8) * 256u;
        if (width < 256 || height < 256 || (width & 255) || (height & 255) ||
            width > 32768 || height > 8192 ||
            map != (i ? 0xC000 : 0xA000) ||
            definitions != (i ? 0x2800 : 0x2000) ||
            bytes != Word(ram, 0x069A + off) || map + bytes > 0x10000u ||
            PPU_bigTiles(ppu, physical) || PPU_bgTilemapHigher(ppu, physical) ||
            PPU_bgTilemapAdr(ppu, physical) != Word(ram, 0x06BA + off)) return true;
        const uint16_t fields[] = {width, height, map, definitions,
            Word(ram, 0x06BA + off), (uint16_t)physical,
            (uint16_t)PPU_bgTileAdr(ppu, physical)};
        for (unsigned n = 0; n < sizeof(fields) / sizeof(fields[0]); n++)
            signature = (signature ^ fields[n]) * 16777619u;
    }
    if (out->camera_x > out->world_width - 256u ||
        out->camera_y > out->world_height - 224u) return true;
    out->layout_signature = signature;
    out->gate = kIogSceneViewReady;
    return true;
}

bool IogSceneViewReadSource(const uint8_t *ram, size_t size, const Ppu *ppu,
                          bool randomizer, IogSceneViewSource *out)
{
    return ReadSource(ram, size, ppu, randomizer, false, out);
}

bool IogSceneViewReadWorldSource(const uint8_t *ram, size_t size, const Ppu *ppu,
                               bool randomizer, IogSceneViewSource *out)
{
    return ReadSource(ram, size, ppu, randomizer, true, out);
}

bool IogSceneViewPrepare(IogSceneView *view, const IogSceneViewSource *source,
                         int dw, int dh, int aspect, bool widescreen,
                         IogSceneViewGeometry *out)
{
    if (!view || !view->enabled || !source || !out) return false;
    if (dw <= 0 || dh <= 0 || aspect < 0 || aspect >= kSnesDisplayAspect_Count) {
        view->prepared = false;
        view->complete = false;
        return false;
    }
    IogSceneViewGeometry geometry = {256, kIogSceneViewHeight, 0, false};
    if (widescreen && source->gate == kIogSceneViewReady) {
        SnesDisplayFrame frame = SnesDisplayAspect_ComputeAdaptiveFrame(256,
            kIogSceneViewHeight, kIogSceneViewMaxWidth, (double)dw / dh,
            (SnesDisplayAspect)aspect);
        geometry.width = frame.width;
        geometry.extra = frame.extra;
        geometry.centered_hud = geometry.extra != 0;
    }
    IogSceneViewSnapshot *snapshot = &view->pending;
    if (!view->prepared || snapshot->source.scene != source->scene ||
        snapshot->source.form != source->form ||
        snapshot->source.layout_signature != source->layout_signature ||
        snapshot->source.gate != source->gate ||
        snapshot->geometry.width != geometry.width) {
        view->generation++;
        view->complete = false;
    }
    snapshot->generation = view->generation;
    snapshot->source = *source;
    snapshot->geometry = geometry;
    snapshot->frame = 0;
    view->prepared = true;
    *out = geometry;
    return true;
}

void IogSceneViewBeginFrame(IogSceneView *view)
{
    if (view && view->enabled) view->complete = false;
}

void IogSceneViewEndFrame(IogSceneView *view, unsigned frame)
{
    if (!view || !view->enabled || !view->prepared) return;
    view->snapshot = view->pending;
    view->snapshot.frame = frame;
    view->complete = true;
}

bool IogSceneViewGetSnapshot(const IogSceneView *view, IogSceneViewSnapshot *out)
{
    if (!view || !view->enabled || !view->complete || !out) return false;
    *out = view->snapshot;
    return true;
}

int IogSceneViewDraw(const IogSceneView *view, uint8_t *dst, size_t pitch,
                     const uint8_t *field, int width, int height, double alpha)
{
    if (!view || !view->enabled || !view->complete || !dst || !field ||
        width != view->snapshot.geometry.width || height != kIogSceneViewHeight ||
        pitch < (size_t)width * 4 || !isfinite(alpha) || alpha < 0 || alpha > 1)
        return 0;
    RtlWidescreenPresent(dst, pitch, field, width, height);
    return 1;
}
