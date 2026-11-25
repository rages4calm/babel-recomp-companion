#ifndef IOG_MAP_UI_H
#define IOG_MAP_UI_H
#include "iog_map_view.h"

typedef struct IogMapUiInput {
  bool toggle_full, toggle_radar, close, zoom_in, zoom_out, recenter;
  int8_t pan_x, pan_y;
  uint32_t dt_ms;
} IogMapUiInput;
typedef struct IogMapUiMetadata {
  bool valid, hidden, gamepad;
  /* A known user-facing floor number, or0 to omit an unknown floor. */
  unsigned floor_number;
  /* Nonzero alpha indicates that the corresponding marker is available. */
  IogMapViewColor exit_legend, chest_legend;
} IogMapUiMetadata;
/* A button prompt: the physical control the player presses, then its action.
 * A nonzero colour draws the one-letter glyph in a coloured ring (the overlay
 * button style); zero draws the label in a plain key cap. */
typedef struct IogMapUiPrompt {
  char glyph[8];
  uint32_t color;
  char text[16];
} IogMapUiPrompt;
enum { IOG_MAP_UI_PROMPTS = 6, IOG_MAP_UI_GLYPH_HEIGHT = 18 };
typedef struct IogMapUi {
  uint32_t magic;
  /* Chrome and text multiplier, 1 or 2; zoom steps scale with it. */
  unsigned scale;
  IogMapUiPrompt prompts[IOG_MAP_UI_PROMPTS], back_prompt;
  unsigned prompt_count;
  bool radar, full, visible, center_pending, identity_valid;
  bool pointer_down, dragging;
  int pointer_x, pointer_y;
  unsigned draw_width, draw_height;
  char controller_hint[96], controller_back[24];
  int zoom_index;
  int32_t center_x_q8, center_y_q8;
  IogMapDiscoveryIdentity identity;
} IogMapUi;
void IogMapUiInit(IogMapUi *ui);
/* Host supplies current remappable logical button labels. NULL resets defaults. */
void IogMapUiControllerHints(IogMapUi *ui,const char *hint,const char *back);
/* 1 or 2. The host picks 2 when the canvas is the doubled 1080p-class frame. */
void IogMapUiSetScale(IogMapUi *ui, unsigned scale);
/* Bottom-row prompts and the title-row Back prompt for the active controller.
 * A zero count returns to the text hints above. Strings are bounded copies. */
void IogMapUiSetPrompts(IogMapUi *ui, const IogMapUiPrompt *prompts,
                        unsigned count, const IogMapUiPrompt *back);
/* Shared glyph drawing for the other overlay pages: width in pixels, and a
 * glyph in an 18*scale-high slot whose top-left corner is (x, y). */
int IogMapUiGlyphWidth(const char *glyph, uint32_t color, int scale);
void IogMapUiGlyphDraw(uint32_t *pixels, int stride, int height, int x, int y,
                       const char *glyph, uint32_t color, int scale);
/* Paused controller-first bindings pane. Row0 is radar, rows1..5 are actions.
 * Input bindings contain distinct A/B/X/Y/L/R indices0..5. */
bool IogMapUiDrawControls(uint8_t *bgra,size_t bytes,size_t pitch,
    unsigned width,unsigned height,const uint8_t bindings[5],
    unsigned selected,bool radar,bool persistent);
/* Edges are supplied by the host. Full-map activation belongs to its paused
 * Companion page, never an unpaused guest hotkey. No guest input or time is
 * consumed here; the host owns modal capture and speculative-frame guards. */
void IogMapUiHandleInput(IogMapUi *ui, const IogMapUiInput *input);
/* Pointer coordinates are in the most recently drawn full-map canvas. Only a
 * press starting inside its viewport can drag; header buttons are
 * edge-triggered. Release is delivered even outside the canvas. True means the
 * map consumed it. No wheel semantics are implied. Closing Back clears ui->full
 * for the host. */
bool IogMapUiPointer(IogMapUi *ui, int x, int y, bool down, unsigned width,
                     unsigned height);
/* Quiet stone/gold BGRA presentation over a caller-owned frame. MapView does
 * fog/marker filtering; radar follows the player, fullmap supports uniform
 * pan/zoom/recenter. Invalid/hidden sources draw nothing and close stale maps.
 * Dimensions are256..2048 x160..2048. Rejected buffer/source leaves pixels
 * unchanged. Buffers/state/source must not alias; arbitrary row pitch allowed
 * when four-byte aligned. No graphics, game data or native fonts are bundled.
 */
bool IogMapUiDraw(IogMapUi *ui, uint8_t *bgra, size_t bytes, size_t pitch,
                  unsigned width, unsigned height,
                  const IogMapViewSource *source,
                  const IogMapUiMetadata *metadata);
#endif
