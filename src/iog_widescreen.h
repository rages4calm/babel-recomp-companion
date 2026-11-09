#ifndef IOG_WIDESCREEN_H
#define IOG_WIDESCREEN_H
#include <stdbool.h>

/* Drop prior presentation keys before simulation; also safe after restore. */
void IogWidescreenBeginFrame(void);
/* Resolve current decoded map state after simulation, before rasterization. */
void IogWidescreenBeforeDraw(void);
/* Follow the actual line's HDMA/IRQ scroll, before ppu_runLine. */
void IogWidescreenBeforeLine(int line);
/* Before the guest frame runs: widen the actor culling window. */
void IogWidescreenBeforeFrame(void);
/* Finite opt-in scene preview only; false preserves the existing HUD policy. */
void IogWidescreenSetPreviewCenteredHud(bool enabled);

#endif
