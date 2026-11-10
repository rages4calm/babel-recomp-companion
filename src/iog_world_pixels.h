#ifndef IOG_WORLD_PIXELS_H
#define IOG_WORLD_PIXELS_H

typedef struct Ppu Ppu;

/* Draw one line of a caller-owned detached picture, never the live PPU.
 * The PPU, output and any optional picture inputs must belong to the caller;
 * this does not bind buffers or execute guest CPU/HDMA/IRQ work. Renderer
 * selection is restored before return. The existing Mode1 span renderer is
 * selected by default. Configure before the first draw on each thread:
 * IOG_WORLD_REFERENCE_PIXELS=1 forces the pixel reference. An explicit
 * IOG_WORLD_SPAN_PIXELS value selects spans only when exactly "1"; "0" or
 * an invalid value selects the reference. Unset retains the span default.
 * Other modes retain the pixel reference until separately qualified.
 * As in PpuDrawDetachedLine, line0 prepares caches and lines1..240 draw. */
void IogWorldPixelsDrawLine(Ppu *ppu, int line);

#endif
