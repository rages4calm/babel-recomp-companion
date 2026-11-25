#ifndef IOG_MAP_HOST_H
#define IOG_MAP_HOST_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Actual-frame adapter; only a verified profile can publish a map. */
void IogMapHostFrame(bool verified,const char *content_sha256);
void IogMapHostReset(void);
void IogMapHostShutdown(void);
/* Inventory art captures must not replace the real exploration journal. */
void IogMapHostSuspend(bool suspended);
bool IogMapHostAvailable(void);
void IogMapHostRadarToggle(void);
bool IogMapHostRadarEnabled(void);
void IogMapHostRadarSet(bool enabled);
/* Map controls use the shared host's remappable SNES logical buttons. D-pad
 * and left stick keep their shared directional mapping. Changing an occupied
 * action button swaps the actions, so Back is never lost to a conflict. */
enum { IOG_MAP_ZOOM_IN, IOG_MAP_ZOOM_OUT, IOG_MAP_CENTER,
       IOG_MAP_RADAR, IOG_MAP_BACK, IOG_MAP_CONTROL_COUNT };
enum { IOG_MAP_BUTTON_COUNT = 6 };
int IogMapHostControlGet(int action);
void IogMapHostControlSet(int action,int button);
const char *IogMapHostControlName(int button);
void IogMapHostDrawRadar(uint8_t *dst,size_t pitch,int width,int height);
int IogMapHostOpen(void);
/* Received-profile local-human input adapter. Source/hash guarded; never
 * intercepts world travel, original pause/debug modes or unknown profiles. */
int IogMapHostInput(uint32_t *human);
void IogMapHostNav(uint32_t inputs,uint32_t ticks);
void IogMapHostKey(int key,int repeat);
void IogMapHostPointer(int x,int y,int down);
bool IogMapHostIsOpen(void);
int IogMapHostImage(const uint32_t **pixels,int *width,int *height);
void IogMapHostClose(void);
/* The host's paused-overlay size in pixels (twice the presented frame). */
void IogMapHostOverlaySize(int *w,int *h);
/* The control the player presses for an SNES pad bit under the current
 * bindings, as a glyph (colour nonzero: ringed letter) or, with no controller
 * in use, the given keyboard key name. */
void IogMapHostPrompt(uint32_t snes_bit,const char *key,const char *text,
    char glyph[8],uint32_t *color,char out_text[16]);
bool IogMapHostUsingPad(void);
void IogMapHostNotePad(bool pad);
#endif
