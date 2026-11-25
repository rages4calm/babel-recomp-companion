/* SPDX-License-Identifier: MIT */
#include "presentation.h"
#include "audit.h"
#include "catalog.generated.h"
#include "toolkit/companion_achievement_presentation.h"
#include "desktop/config.h"
#include "desktop/sdl_compat.h"
#include "snes_overlay_draw.h"
#include "iog_map_host.h"
#include "iog_map_ui.h"

#include <stdio.h>
#include <string.h>

static ca_ui ui;
static const ca_ui_metadata metadata[GAIA_ACHIEVEMENT_COUNT] = {
    [GAIA_ACHIEVEMENT_COUNT - 1] = {true, "Hidden achievement", "Keep exploring to learn more."},
};
static const char *status;
static bool initialized, pointer_down;
/* The browser is laid out on a 598x336 grid (narrower windows: down to 448)
 * and drawn at twice that when the host's overlay is at least 672 high, so
 * its 8-pixel font is not small on a 1080p screen. */
enum { GridW = 598, GridMinW = 448, GridH = 336, MaxScale = 2 };
static uint32_t browser[GridW * MaxScale * GridH * MaxScale];
static int grid_w = GridW, grid_scale = 1;
int IogCompletionPercent(void);
static uint32_t toast[CA_TOAST_WIDTH * CA_TOAST_HEIGHT];
static int16_t chime[CA_CHIME_FRAMES];
enum { Rows = 5, ListX = 16, ListY = 62, RowHeight = 38, PagerY = 254, FooterY = 302 };
static int ListW(void) { return (grid_w - 44) / 2; }
static int CardX(void) { return ListX + ListW() + 12; }
static void Layout(void) {
    int w = 0, h = 0;
    IogMapHostOverlaySize(&w, &h);
    grid_scale = h >= GridH * 2 && w >= GridMinW * 2 ? 2 : 1;
    grid_w = w / grid_scale;
    if (grid_w > GridW) grid_w = GridW;
    if (grid_w < GridMinW) grid_w = GridMinW;
}
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
    x /= grid_scale;
    y /= grid_scale;
    if (!ui.open || !edge || x < ListX || x >= grid_w - 16) return;
    if (x >= grid_w - 96 && y >= FooterY - 2 && y < FooterY + 22) { ca_ui_close(&ui); return; }
    if (x >= ListX + ListW()) return;
    if (y >= ListY && y < ListY + Rows * RowHeight) {
        const size_t index = ui.selected / Rows * Rows + (size_t)(y - ListY) / RowHeight;
        if (index < ui.count) ui.selected = index;
    }
    if (y >= PagerY && y < PagerY + 22) {
        if (x < ListX + 32) ca_ui_command_apply(&ui, CA_UI_PREVIOUS_PAGE);
        else if (x >= ListX + ListW() - 32) ca_ui_command_apply(&ui, CA_UI_NEXT_PAGE);
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

/* Browser drawing on the grid: every coordinate times grid_scale. */
static void Box(int x, int y, int w, int h, uint32_t color) {
    const int k = grid_scale;
    snes_ovl_fill_rect(browser, grid_w * k, GridH * k, x * k, y * k, w * k, h * k, color);
}
static void Label(int x, int y, int w, const char *text, uint32_t color, int size) {
    const int k = grid_scale;
    char line[96];
    const size_t max = (size_t)(w / (8 * size));
    size_t len = strlen(text), copy = len > max ? max : len;
    if (!max || max >= sizeof(line)) return;
    memcpy(line, text, copy);
    if (len > max && copy >= 3) memcpy(line + copy - 3, "...", 3);
    line[copy] = '\0';
    snes_ovl_draw_text(browser, grid_w * k, GridH * k, x * k, y * k, line, color, size * k);
}
static void Outline(int x, int y, int w, int h, uint32_t color) {
    const int k = grid_scale;
    for (int n = 0; n < k; ++n)
        snes_ovl_stroke_rect(browser, grid_w * k, GridH * k, x * k + n, y * k + n, w * k - 2 * n, h * k - 2 * n, color);
}
static void Gem(int x, int y, int scale, bool earned) {
    const uint32_t edge = earned ? 0xffffbc72 : 0xff7f8094;
    for (int i = 0; i < 5; ++i) {
        const int w = 2 * i + 2;
        Box(x + (4 - i) * scale, y + i * scale, w * scale, scale, edge);
        Box(x + (4 - i) * scale, y + (9 - i) * scale, w * scale, scale, edge);
    }
    if (earned) Box(x + 4 * scale, y + 2 * scale, 2 * scale, 5 * scale, 0xffffe4ad);
    else Box(x + 3 * scale, y + 3 * scale, 4 * scale, 4 * scale, 0xff36364d);
}

static void Wrap(int x, int y, int columns, int rows, const char *source, uint32_t color) {
    if (columns > 47) columns = 47;
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
        Label(x, y + row * 15, 8 * columns, line, color, 1);
    }
}

/* A footer prompt: the control under the current bindings, then its action.
 * An empty action joins the glyph to the next one. Returns the next x. */
static int Prompt(int x, uint32_t pad, const char *key, const char *action, uint32_t color) {
    const int k = grid_scale;
    char glyph[8];
    uint32_t tint;
    IogMapHostPrompt(pad, key, NULL, glyph, &tint, NULL);
    if (glyph[0]) {
        IogMapUiGlyphDraw(browser, grid_w * k, GridH * k, x * k, FooterY * k, glyph, tint, k);
        x += IogMapUiGlyphWidth(glyph, tint, 1) + (action[0] ? 4 : 2);
    }
    if (action[0]) {
        Label(x, FooterY + 5, 8 * (int)strlen(action), action, color, 1);
        x += 8 * (int)strlen(action) + 14;
    }
    return x;
}

bool IogAchievementUiImage(const uint32_t **pixels, int *width, int *height) {
    if (!ui.open) return false;
    Layout();
    const int W = grid_w, list_w = ListW(), card_x = CardX(), card_w = W - 16 - card_x;
    const uint32_t bg = 0xff171828, card = 0xff25263b, line = 0xff41435d;
    const uint32_t fg = 0xfffff1d9, dim = 0xffb8b8cb, jade = 0xff78e1c3, gold = 0xffffbc72;
    Box(0, 0, W, GridH, bg);
    Label(16, 12, W - 200, "ACHIEVEMENTS", fg, 2);
    char label[48];
    size_t earned = 0;
    for (size_t i = 0; i < ui.count; ++i) earned += ui.states[i].unlocked_at != 0;
    snprintf(label, sizeof(label), "%zu / %zu EARNED", earned, ui.count);
    Label(W - 16 - (int)strlen(label) * 8, 16, 192, label, gold, 1);
    Box(16, 36, W - 32, 1, line);
    Label(16, 45, W - 32 - 160, status ? status : "Local progress", dim, 1);
    const int percent = IogCompletionPercent();
    if (percent >= 0) {
        snprintf(label, sizeof(label), "GAME COMPLETED %d%%", percent);
        Label(W - 16 - (int)strlen(label) * 8, 45, 192, label, dim, 1);
    }

    const size_t first = ui.selected / Rows * Rows;
    for (size_t i = first; i < ui.count && i < first + Rows; ++i) {
        const bool unlocked = ui.states[i].unlocked_at != 0;
        const char *title = metadata[i].secret && !unlocked ? metadata[i].locked_title : ui.definitions[i].title;
        const int y = ListY + (int)(i - first) * RowHeight;
        Box(ListX, y, list_w, RowHeight - 4, i == ui.selected ? 0xff39354e : card);
        if (i == ui.selected) {
            Outline(ListX, y, list_w, RowHeight - 4, jade);
            Box(ListX, y + 4, 4, RowHeight - 12, jade);
        }
        Gem(ListX + 13, y + 12, 1, unlocked);
        Label(ListX + 33, y + 6, list_w - 41, title, fg, 1);
        Label(ListX + 33, y + 20, list_w - 41, unlocked ? "EARNED" : "LOCKED", unlocked ? gold : dim, 1);
    }
    Box(ListX, PagerY, 32, 22, card);
    Box(ListX + list_w - 32, PagerY, 32, 22, card);
    Label(ListX + 12, PagerY + 7, 10, "<", jade, 1);
    Label(ListX + list_w - 20, PagerY + 7, 10, ">", jade, 1);
    snprintf(label, sizeof(label), "PAGE %zu / %zu", first / Rows + 1, (ui.count + Rows - 1) / Rows);
    Label(ListX + list_w / 2 - (int)strlen(label) * 4, PagerY + 7, 150, label, dim, 1);

    Box(card_x, ListY, card_w, PagerY + 22 - ListY, card);
    const size_t selected = ui.selected;
    const ca_definition *def = &ui.definitions[selected];
    const ca_state selected_state = ui.states[selected];
    const bool unlocked = selected_state.unlocked_at != 0;
    const bool hidden = metadata[selected].secret && !unlocked;
    const int columns = (card_w - 32) / 8;
    Gem(card_x + 16, ListY + 14, 3, unlocked);
    Label(card_x + 60, ListY + 26, card_w - 76, unlocked ? "EARNED" : "LOCKED", unlocked ? gold : dim, 1);
    Wrap(card_x + 16, ListY + 60, columns, 2, hidden ? metadata[selected].locked_title : def->title, fg);
    Wrap(card_x + 16, ListY + 98, columns, 4, hidden ? metadata[selected].locked_description : def->description, dim);
    if (def->target > 1) {
        snprintf(label, sizeof(label), "%u / %u", selected_state.progress, def->target);
        Label(card_x + 16, ListY + 172, card_w - 32, label, fg, 1);
        Box(card_x + 16, ListY + 190, card_w - 32, 5, line);
        Box(card_x + 16, ListY + 190, (int)((uint64_t)(card_w - 32) * selected_state.progress / def->target), 5, jade);
    }
    /* Footer: what to press, under the current bindings (or keyboard keys). */
    int x = Prompt(ListX, 0, IogMapHostUsingPad() ? "PAD" : "ARROWS", "Browse", dim);
    x = Prompt(x, SNES_PAD_L, "Q", "", dim);
    x = Prompt(x, SNES_PAD_R, "E", "Screen", dim);
    char glyph[8];
    uint32_t tint;
    IogMapHostPrompt(SNES_PAD_B, "ESC", NULL, glyph, &tint, NULL);
    Prompt(W - 16 - IogMapUiGlyphWidth(glyph, tint, 1) - 4 - 32, SNES_PAD_B, "ESC", "Back", fg);
    *pixels = browser;
    *width = W * grid_scale;
    *height = GridH * grid_scale;
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
