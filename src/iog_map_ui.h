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
} IogMapUiMetadata;
typedef struct IogMapUi {
  uint32_t magic;
  bool radar, full, visible, center_pending, identity_valid;
  bool pointer_down, dragging;
  int pointer_x, pointer_y;
  unsigned draw_width, draw_height;
  int zoom_index;
  int32_t center_x_q8, center_y_q8;
  IogMapDiscoveryIdentity identity;
} IogMapUi;
void IogMapUiInit(IogMapUi *ui);
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
