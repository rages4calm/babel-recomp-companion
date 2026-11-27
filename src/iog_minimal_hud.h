#ifndef IOG_MINIMAL_HUD_H
#define IOG_MINIMAL_HUD_H

/* GaiaLabs "Minimal HUD" (iog_minimal_hud.c, plugin iog.gaialabs.minimal_hud).
 * Presentation only: around one frame's raster, the status display's BG3
 * tilemap rows are drawn blank while the player is in a non-combat area.
 * Begin and End must be paired inside the same frame draw. */
void IogMinimalHudBeginDraw(void);
void IogMinimalHudEndDraw(void);

#endif
