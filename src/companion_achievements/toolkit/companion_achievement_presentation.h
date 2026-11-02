/* SPDX-License-Identifier: MIT */
#ifndef COMPANION_ACHIEVEMENT_PRESENTATION_H
#define COMPANION_ACHIEVEMENT_PRESENTATION_H
#include "companion_achievements.h"

#define CA_PRESENTATION_VERSION "0.3.0"
enum { CA_UI_WIDTH=640, CA_UI_HEIGHT=360, CA_TOAST_WIDTH=144, CA_TOAST_HEIGHT=32,
       CA_CHIME_RATE=48000, CA_CHIME_FRAMES=31200 };
enum { CA_UI_UP=1, CA_UI_DOWN=2, CA_UI_LEFT=4, CA_UI_RIGHT=8, CA_UI_CLOSE=16 };
typedef enum { CA_UI_FIRST, CA_UI_LAST, CA_UI_PREVIOUS_PAGE, CA_UI_NEXT_PAGE,
               CA_UI_PREVIOUS_ROW, CA_UI_NEXT_ROW, CA_UI_DISMISS } ca_ui_command;
/* Metadata is parallel to definitions; NULL entries use generic secret hints.
 * Strings and definitions must outlive the UI. No game artwork is required. */
typedef struct { bool secret; const char *locked_title, *locked_description; } ca_ui_metadata;
typedef struct {
    const ca_definition *definitions;
    const ca_ui_metadata *metadata;
    size_t count, selected, toast_index;
    ca_state states[CA_MAX_ACHIEVEMENTS];
    size_t queue[CA_MAX_ACHIEVEMENTS], queued;
    uint64_t announced;
    uint32_t previous_input, repeat_at, toast_started, pause_started;
    bool open, repeat_armed, toast_active, paused;
} ca_ui;
/* Renderer callbacks receive a fixed logical canvas, opaque ARGB colours and
 * UTF-8 strings valid only during the callback. Text must clip to the supplied
 * rectangle; use the host's readable font. The host owns GPU/font/audio state. */
typedef struct {
    void *context;
    void (*rectangle)(void *, int x, int y, int width, int height, uint32_t argb);
    void (*text)(void *, int x, int y, int width, int height, const char *, uint32_t argb);
} ca_ui_draw;
bool ca_ui_init(ca_ui *, const ca_definition *, const ca_ui_metadata *, size_t count);
/* Copy a committed read-only snapshot. Never queues notices on restore/load. */
bool ca_ui_snapshot(ca_ui *, const ca_state *, size_t count);
/* Feed ONLY post-commit notifications. Bounded, deduplicated, no allocation.
 * False means invalid/unearned index. Restored achievements are not notices. */
bool ca_ui_notice(ca_ui *, size_t index);
/* Opening primes held input; host must gate held buttons after closing until
 * release before resuming gameplay. No simulated input or guest writes here. */
void ca_ui_open(ca_ui *, uint32_t held_buttons);
void ca_ui_close(ca_ui *);
void ca_ui_command_apply(ca_ui *, ca_ui_command);
/* Tick with monotonic host milliseconds. Block toasts for other menus/dialogue.
 * Returns true ONCE when a queued toast starts: play the optional chime then.
 * Hidden time does not consume the 5.5 second toast duration. */
bool ca_ui_tick(ca_ui *, uint32_t buttons, uint32_t milliseconds, bool blocked);
bool ca_ui_draw_browser(const ca_ui *, const ca_ui_draw *, const char *heading, const char *status);
bool ca_ui_draw_toast(const ca_ui *, const ca_ui_draw *);
/* Place at top right of the game field, not the entire letterboxed window.
 * Scale with the field's pixel scale, never independently stretch the toast. */
bool ca_ui_toast_origin(int field_x, int field_y, int field_width, int field_height,
                        int pixel_scale, int *x, int *y);
/* Original, synthesized mono PCM16 notification; generate at startup, submit
 * through a separate host audio voice at unlock. No audio device dependency. */
bool ca_chime_generate(int16_t *samples, size_t capacity);
#endif
