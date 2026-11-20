/* SPDX-License-Identifier: MIT */
#include "presentation.h"
#include "audit.h"
#include "catalog.generated.h"
#include "toolkit/companion_achievement_presentation.h"
#include "desktop/config.h"
#include "desktop/sdl_compat.h"
#include "snes_overlay_draw.h"

#include <stdio.h>
#include <string.h>

static ca_ui ui;
static const ca_ui_metadata metadata[GAIA_ACHIEVEMENT_COUNT] = {
    [GAIA_ACHIEVEMENT_COUNT - 1] = {true, "Hidden achievement", "Keep exploring to learn more."},
};
static const char *status;
static bool initialized, pointer_down;
static uint32_t browser[CA_UI_WIDTH * CA_UI_HEIGHT];
static uint32_t toast[CA_TOAST_WIDTH * CA_TOAST_HEIGHT];
static int16_t chime[CA_CHIME_FRAMES];
enum { Rows = 5, ListY = 88, RowHeight = 40 };
#if SNESRECOMP_SDL3
static SDL_AudioStream *audio;
#else
static SDL_AudioDeviceID audio;
#endif

static void Refresh(void) {
    ca_state states[CA_MAX_ACHIEVEMENTS];
    uint64_t notices;
    status = IogAchievementAuditSnapshot(states, &notices);
    if (!ca_ui_snapshot(&ui, states, GAIA_ACHIEVEMENT_COUNT)) return;
    for (size_t i = 0; i < GAIA_ACHIEVEMENT_COUNT; ++i)
        if (notices & (UINT64_C(1) << i)) ca_ui_notice(&ui, i);
}

static void Initialize(void) {
    if (initialized) return;
    initialized = ca_ui_init(&ui, gaia_definitions, metadata, GAIA_ACHIEVEMENT_COUNT);
    if (initialized) ca_chime_generate(chime, CA_CHIME_FRAMES);
}

static uint32_t Directions(uint32_t pad) {
    return ((pad & SNES_PAD_UP) ? CA_UI_UP : 0) |
           ((pad & SNES_PAD_DOWN) ? CA_UI_DOWN : 0) |
           ((pad & SNES_PAD_LEFT) ? CA_UI_LEFT : 0) |
           ((pad & SNES_PAD_RIGHT) ? CA_UI_RIGHT : 0) |
           ((pad & SNES_PAD_B) ? CA_UI_CLOSE : 0);
}

void IogAchievementUiOpen(uint32_t held) {
    Initialize();
    if (!initialized) return;
    Refresh();
    pointer_down = false;
    ca_ui_open(&ui, Directions(held));
}

void IogAchievementUiClose(void) { ca_ui_close(&ui); }
bool IogAchievementUiIsOpen(void) { return ui.open; }

void IogAchievementUiNav(uint32_t buttons, uint32_t ticks) {
    if (ui.open) ca_ui_tick(&ui, Directions(buttons), ticks, true);
}

void IogAchievementUiKey(int key) {
    if (!ui.open) return;
    switch (key) {
    case SDLK_ESCAPE: case SDLK_i: ca_ui_close(&ui); break;
    case SDLK_UP: ca_ui_command_apply(&ui, CA_UI_PREVIOUS_ROW); break;
    case SDLK_DOWN: ca_ui_command_apply(&ui, CA_UI_NEXT_ROW); break;
    case SDLK_LEFT: ca_ui_command_apply(&ui, CA_UI_PREVIOUS_PAGE); break;
    case SDLK_RIGHT: ca_ui_command_apply(&ui, CA_UI_NEXT_PAGE); break;
    case SDLK_HOME: ca_ui_command_apply(&ui, CA_UI_FIRST); break;
    case SDLK_END: ca_ui_command_apply(&ui, CA_UI_LAST); break;
    }
}

void IogAchievementUiPointer(int x, int y, int pressed) {
    const bool edge = pressed && !pointer_down;
    pointer_down = pressed != 0;
    if (!ui.open || !edge || x < 20 || x >= 620) return;
    if (x >= 504 && y >= 324 && y < 346) { ca_ui_close(&ui); return; }
    if (x >= 320) return;
    if (y >= ListY && y < ListY + Rows * RowHeight) {
        const size_t index = ui.selected / Rows * Rows + (size_t)(y - ListY) / RowHeight;
        if (index < ui.count) ui.selected = index;
    }
    if (y >= 290 && y < 314) {
        if (x < 52) ca_ui_command_apply(&ui, CA_UI_PREVIOUS_PAGE);
        else if (x >= 288) ca_ui_command_apply(&ui, CA_UI_NEXT_PAGE);
    }
}

typedef struct Surface { uint32_t *pixels; int width, height; } Surface;
static void Rectangle(void *context, int x, int y, int w, int h, uint32_t color) {
    Surface *surface = context;
    snes_ovl_fill_rect(surface->pixels, surface->width, surface->height, x, y, w, h, color);
}

static void Text(void *context, int x, int y, int w, int h, const char *text, uint32_t color) {
    Surface *surface = context;
    if (surface->width == CA_TOAST_WIDTH && y == 3) text = "NEW ACHIEVEMENT";
    const int scale = y == 20 && h >= 20 ? 2 : 1;
    char line[96];
    const size_t max = (size_t)(w / (8 * scale));
    if (!max || max >= sizeof(line) || h < 8 * scale) return;
    size_t len = strlen(text);
    size_t copy = len > max ? max : len;
    memcpy(line, text, copy);
    if (len > max && copy >= 3) memcpy(line + copy - 3, "...", 3);
    line[copy] = '\0';
    snes_ovl_draw_text(surface->pixels, surface->width, surface->height, x, y, line, color, scale);
}

static void Gem(Surface *s, int x, int y, int scale, bool earned) {
    const uint32_t edge = earned ? 0xffffbc72 : 0xff7f8094;
    for (int i = 0; i < 5; ++i) {
        const int w = 2 * i + 2;
        Rectangle(s, x + (4 - i) * scale, y + i * scale, w * scale, scale, edge);
        Rectangle(s, x + (4 - i) * scale, y + (9 - i) * scale, w * scale, scale, edge);
    }
    if (earned) {
        Rectangle(s, x + 4 * scale, y + 2 * scale, 2 * scale, 5 * scale, 0xffffe4ad);
    } else {
        Rectangle(s, x + 3 * scale, y + 3 * scale, 4 * scale, 4 * scale, 0xff36364d);
    }
}

static void Wrap(Surface *s, int x, int y, int columns, int rows, const char *source, uint32_t color) {
    for (int row = 0; row < rows && *source; ++row) {
        size_t length = strlen(source);
        if (length > (size_t)columns) {
            length = columns;
            while (length && source[length] != ' ') --length;
            if (!length) length = columns;
        }
        char line[48];
        memcpy(line, source, length);
        line[length] = '\0';
        source += length;
        while (*source == ' ') ++source;
        if (row == rows - 1 && *source && length >= 3) memcpy(line + length - 3, "...", 3);
        Text(s, x, y + row * 15, 8 * columns, 10, line, color);
    }
}

bool IogAchievementUiImage(const uint32_t **pixels, int *width, int *height) {
    if (!ui.open) return false;
    Surface s = {browser, CA_UI_WIDTH, CA_UI_HEIGHT};
    const uint32_t bg = 0xff171828, card = 0xff25263b, line = 0xff41435d;
    const uint32_t fg = 0xfffff1d9, dim = 0xffb8b8cb, jade = 0xff78e1c3, gold = 0xffffbc72;
    Rectangle(&s, 0, 0, s.width, s.height, bg);
    Rectangle(&s, 20, 55, 600, 1, line);
    Text(&s, 20, 20, 440, 24, "ACHIEVEMENTS", fg);
    char label[48];
    size_t earned = 0;
    for (size_t i = 0; i < ui.count; ++i) earned += ui.states[i].unlocked_at != 0;
    snprintf(label, sizeof(label), "%zu / %zu EARNED", earned, ui.count);
    Text(&s, 620 - (int)strlen(label) * 8, 26, 192, 12, label, gold);

    const size_t first = ui.selected / Rows * Rows;
    for (size_t i = first; i < ui.count && i < first + Rows; ++i) {
        const bool unlocked = ui.states[i].unlocked_at != 0;
        const char *title = metadata[i].secret && !unlocked ? metadata[i].locked_title : ui.definitions[i].title;
        const int y = ListY + (int)(i - first) * RowHeight;
        Rectangle(&s, 20, y, 300, 36, i == ui.selected ? 0xff39354e : card);
        if (i == ui.selected) {
            snes_ovl_stroke_rect(browser, s.width, s.height, 20, y, 300, 36, jade);
            Rectangle(&s, 20, y + 4, 4, 28, jade);
        }
        Gem(&s, 33, y + 12, 1, unlocked);
        Text(&s, 53, y + 6, 256, 12, title, fg);
        Text(&s, 53, y + 21, 240, 10, unlocked ? "EARNED" : "LOCKED", unlocked ? gold : dim);
    }
    Rectangle(&s, 20, 290, 32, 22, card);
    Rectangle(&s, 288, 290, 32, 22, card);
    Text(&s, 32, 297, 10, 8, "<", jade);
    Text(&s, 300, 297, 10, 8, ">", jade);
    snprintf(label, sizeof(label), "PAGE %zu / %zu", first / Rows + 1, (ui.count + Rows - 1) / Rows);
    Text(&s, 170 - (int)strlen(label) * 4, 297, 150, 8, label, dim);

    Rectangle(&s, 336, 72, 284, 240, card);
    const size_t selected = ui.selected;
    const ca_definition *def = &ui.definitions[selected];
    const ca_state selected_state = ui.states[selected];
    const bool unlocked = selected_state.unlocked_at != 0;
    const bool hidden = metadata[selected].secret && !unlocked;
    Gem(&s, 356, 90, 3, unlocked);
    Text(&s, 402, 102, 196, 11, unlocked ? "EARNED" : "LOCKED", unlocked ? gold : dim);
    Wrap(&s, 356, 142, 30, 2, hidden ? metadata[selected].locked_title : def->title, fg);
    Wrap(&s, 356, 180, 30, 4, hidden ? metadata[selected].locked_description : def->description, dim);
    if (def->target > 1) {
        snprintf(label, sizeof(label), "%u / %u", selected_state.progress, def->target);
        Text(&s, 356, 263, 240, 10, label, fg);
        Rectangle(&s, 356, 282, 244, 5, line);
        Rectangle(&s, 356, 282, (int)((uint64_t)244 * selected_state.progress / def->target), 5, jade);
    }
    Text(&s, 20, 70, 294, 10, status ? status : "Local progress", dim);
    Text(&s, 20, 332, 472, 12, "D-PAD / ARROWS: BROWSE", dim);
    Rectangle(&s, 504, 324, 116, 22, card);
    Text(&s, 514, 332, 104, 10, "B / ESC: BACK", fg);
    *pixels = browser;
    *width = s.width;
    *height = s.height;
    return true;
}

static void PlayChime(void) {
    const char *option = SDL_getenv("IOG_ACHIEVEMENT_CHIME");
    const int volume = g_config.volume > 100 ? 100 : g_config.volume;
    if (!g_config.enable_audio || volume <= 0 || (option && !strcmp(option, "0")) ||
        !(SDL_WasInit(SDL_INIT_AUDIO) & SDL_INIT_AUDIO)) return;
#if SNESRECOMP_SDL3
    SDL_AudioSpec spec = {.format = SDL_AUDIO_S16, .channels = 1, .freq = CA_CHIME_RATE};
    if (!audio) audio = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, NULL, NULL);
    if (!audio) return;
    if (!SDL_SetAudioStreamGain(audio, (float)volume / 100.0f) ||
        !SDL_PutAudioStreamData(audio, chime, sizeof(chime)) || !SDL_ResumeAudioStreamDevice(audio)) {
        SDL_DestroyAudioStream(audio);
        audio = NULL;
    }
#else
    SDL_AudioSpec spec = {.format = AUDIO_S16SYS, .channels = 1, .freq = CA_CHIME_RATE, .samples = 1024};
    if (!audio) audio = SDL_OpenAudioDevice(NULL, 0, &spec, NULL, 0);
    if (!audio) return;
    static int16_t scaled[CA_CHIME_FRAMES];
    for (size_t i = 0; i < CA_CHIME_FRAMES; ++i)
        scaled[i] = (int16_t)((int32_t)chime[i] * volume / 100);
    if (SDL_QueueAudio(audio, scaled, sizeof(scaled)) == 0) SDL_PauseAudioDevice(audio, 0);
    else { SDL_CloseAudioDevice(audio); audio = 0; }
#endif
}

void IogAchievementUiFrame(unsigned frame, uint32_t ticks, bool quiet) {
    if (!initialized && frame % 30) return;
    Initialize();
    if (frame % 30 == 0) Refresh();
    if (ca_ui_tick(&ui, 0, ticks, !quiet)) PlayChime();
}

void IogAchievementUiToast(uint8_t *dst, size_t pitch, int width, int height) {
    int x, y;
    if (!ui.toast_active || !ca_ui_toast_origin(0, 0, width, height, 1, &x, &y)) return;
    Surface surface = {toast, CA_TOAST_WIDTH, CA_TOAST_HEIGHT};
    ca_ui_draw draw = {&surface, Rectangle, Text};
    if (ca_ui_draw_toast(&ui, &draw))
        snes_ovl_blit_panel_rect(dst, (int)pitch, width, height, toast, surface.width, surface.height,
                               x, y, surface.width, surface.height);
}

void IogAchievementUiShutdown(void) {
#if SNESRECOMP_SDL3
    if (audio) SDL_DestroyAudioStream(audio);
    audio = NULL;
#else
    if (audio) SDL_CloseAudioDevice(audio);
    audio = 0;
#endif
    initialized = false;
}
