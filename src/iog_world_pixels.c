/* Host-only pixel-algorithm selection for independently owned pictures.
 * Both implementations remain the framework's original PPU algorithms. */
#include "iog_world_pixels.h"
#include "snes/ppu.h"
#include "snes/snes.h"
#include <stdlib.h>
#include <string.h>

extern Snes *g_snes;

/* Detached drawing is allowed on independent host threads. Match the PPU's
 * private render scope without introducing shared lazy-initialization writes. */
#ifdef _MSC_VER
static __declspec(thread) unsigned s_pixel_mode;
#else
static _Thread_local unsigned s_pixel_mode;
#endif

static unsigned PixelMode(void)
{
    if (!s_pixel_mode) {
        const char *reference = getenv("IOG_WORLD_REFERENCE_PIXELS");
        const char *spans = getenv("IOG_WORLD_SPAN_PIXELS");
        s_pixel_mode = !spans || !strcmp(spans, "1") ? 2u : 1u;
        if (reference && !strcmp(reference, "1")) s_pixel_mode = 1u;
    }
    return s_pixel_mode;
}

void IogWorldPixelsDrawLine(Ppu *ppu, int line)
{
    if (!ppu || (g_snes && ppu == g_snes->ppu) || line < 0 || line > 240)
        return;
    const uint32_t flags = ppu->renderFlags;
    ppu->renderFlags = PixelMode() == 2u && PPU_mode(ppu) == 1
        ? flags | kPpuRenderFlags_NewRenderer
        : flags & ~(uint32_t)kPpuRenderFlags_NewRenderer;
    PpuDrawDetachedLine(ppu, line);
    ppu->renderFlags = flags;
}
