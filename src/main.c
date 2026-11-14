/*
 * Illusion Of Gaia Usa — desktop host shim.
 *
 * Identity and hooks, nothing else. The host itself is the framework's
 * (snesrecomp/runner/src/desktop/host_main.h): the pre-boot launcher, ROM
 * resolution and digest checks, config.ini and keybinds.ini, the window and
 * the SDL / OpenGL presenters, audio, gamepads, the in-game save-state
 * browser and rewind filmstrip, the OSD, the pacing clock, crash handlers and
 * the post-mortem report, mod packages, Generate & rebuild, and the netplay
 * barrier when the project is built with it. A fix there reaches this
 * project on a submodule pull; nothing in this file needs to change for it.
 *
 * This file used to BE the host -- a ~700-line copy made at scaffold time --
 * so every project scaffolded before a fix kept the bug. Two ports of the
 * same game, a week apart, had different hosts.
 *
 * Nothing here ever ships a ROM. The player supplies one; the host makes
 * that easy (launcher, then positional argument, then a copy beside the
 * executable, then the rom.cfg cache, then a file picker) and checks what it
 * is handed against the digests in rom_identity.txt.
 *
 * Grow this file only with what is specific to THIS title: a custom
 * presenter (prepare_frame / draw_frame), an SPC player, a pacing rule
 * (keep_pacing_debt), a Mods provider. See SnesDesktopHostGame for the
 * complete list of hooks and what each is for.
 */

#include "host_main.h"
#include "game_rtl.h"
#include "iog_widescreen.h"
#include "iog_scene_view.h"
#include "iog_world_renderer.h"
#include "iog_randomizer.h"
#include "iog_inventory.h"
#include "iog_i18n.h"
#include "iog_build_info.h"
#include "snes_osd.h"
#include <stdio.h>
#include <stdlib.h>
#include "common_rtl.h"
#include "snes/snes.h"
#include "snesrecomp_rom_identity.h"  /* generated from rom_identity.txt */
#include "desktop/config.h"
#include "desktop/display_aspect.h"

#ifndef __ANDROID__
#define SDL_MAIN_HANDLED 1
#endif
#include "desktop/sdl_compat.h"
#ifdef __ANDROID__
/* SDLActivity loads libmain.so and dlsyms its SDL_main. */
#define main SDL_main
#endif

#ifndef SNES_GAME_VERSION
#define SNES_GAME_VERSION "dev"
#endif

#ifdef IOG_RECEIVED_REFERENCE
#include "iog_received_world.h"
static void IogReferenceFrame(int dw,int dh,int *w,int *h)
{
    (void)dw;(void)dh;*w=384;*h=224;
    /* This received build authors its menus/dialogue across BG3 too. The
     * generic PPU otherwise deliberately clamps that layer to 256 columns. */
    if(g_ppu) PpuSetWidescreenBg3Widen(g_ppu,1);
}
static void IogReceivedViewport(int fw,int fh,int dw,int dh,SnesDisplayViewport *out)
{
    if(!out||fw<=0||fh<=0)return;
    int num=1,den=1;
    if(!IogReceivedWorldEnabled())SnesDisplayAspect_GetPixelAspect((SnesDisplayAspect)g_config.display_aspect,&num,&den);
    *out=SnesDisplayAspect_FitViewport((double)fw*num/((double)fh*den),dw,dh);
}
static const SnesDesktopHostGame kGameHost = {
    .display_name = "GaiaLabs received-content reference (interpreted)",
    .window_title = "GaiaLabs reference - not native qualification",
    .region = SNESRECOMP_ROM_REGION,
    .rom_file = IOG_RECEIVED_REFERENCE_ROM_FILE,
    .expected_sha256_hex = IOG_RECEIVED_REFERENCE_SHA256,
    .expected_crc32_hex = NULL,
    .game_id = "iog-gaialabs-reference-" IOG_RECEIVED_REFERENCE_SHA256,
    .build_version = "received-reference-dev",
    .game_info = &kGameInfo,
    .num_players = 1,
    .sram_path = "saves/received-reference.srm",
    .native_widescreen = 1,
    .prepare_frame = IogReferenceFrame,
    .presentation_geometry = IogReceivedWorldGeometry,
    .draw_frame = IogReceivedWorldDraw,
    .compute_viewport = IogReceivedViewport,
};
#else
static IogSceneView s_scene_view;
static bool s_scene_view_initialized;

static void IogInitSceneView(void)
{
    if (s_scene_view_initialized) return;
    s_scene_view_initialized = true;
    IogSceneViewInit(&s_scene_view, getenv("IOG_SCENE_VIEW_PREVIEW"));
    if (s_scene_view.enabled)
        fprintf(stderr, "[iog_scene_view] finite preview enabled; cap=%d, no interpolation\n",
                kIogSceneViewMaxWidth);
}

/* Default widescreen: the PPU rasterizes a field widened by 4/3 (342 px for the
 * default 4:3 pixel aspect, i.e. 16:9 on screen), centred on the authentic
 * 256 columns. Off, the field stays 256 wide and 4:3 is bit-identical. */
static void IogPrepareFrame(int drawable_w, int drawable_h, int *frame_w, int *frame_h)
{
    if (IogWorldEnabled()) {
        *frame_w = 256; *frame_h = 224;
        IogWidescreenSetPreviewCenteredHud(false);
        return;
    }
    IogInitSceneView();
    if (s_scene_view.enabled) {
        IogSceneViewSource source;
        IogSceneViewGeometry geometry;
        IogSceneViewReadSource(g_snes ? g_snes->ram : NULL, 0x20000,
                              g_ppu, IogRandomizerActive(), &source);
        uint64_t generation = s_scene_view.generation;
        if (IogSceneViewPrepare(&s_scene_view, &source, drawable_w, drawable_h,
                               g_config.display_aspect, g_config.widescreen,
                               &geometry)) {
            *frame_w = geometry.width;
            *frame_h = geometry.height;
            IogWidescreenSetPreviewCenteredHud(geometry.centered_hud);
            if (generation != s_scene_view.generation)
                fprintf(stderr, "[iog_scene_view] generation=%llu scene=%04X gate=%d width=%d drawable=%dx%d\n",
                        (unsigned long long)s_scene_view.generation, source.scene,
                        (int)source.gate, geometry.width, drawable_w, drawable_h);
        } else {
            *frame_w = 256; *frame_h = kIogSceneViewHeight;
            IogWidescreenSetPreviewCenteredHud(false);
        }
        return;
    }
    if (g_config.widescreen)
        *frame_w = SnesDisplayAspect_ComputeWideFrameWidth(256);
}

static void IogBeginSimFrame(unsigned number)
{
    (void)number;
    IogSceneViewBeginFrame(&s_scene_view);
    IogWidescreenBeginFrame();
}

/* Ctrl+L: next language. Polled here because the language is a title
 * feature, not a framework key binding. */
static void IogPollLanguageHotkey(void)
{
    static int was_down;
    const uint8_t *keys = snesrecomp_sdl_get_keyboard_state();
    if (!keys)
        return;
    int down = keys[SDL_SCANCODE_L] &&
               (keys[SDL_SCANCODE_LCTRL] || keys[SDL_SCANCODE_RCTRL]);
    if (down && !was_down) {
        char msg[96];
        snprintf(msg, sizeof(msg), "Language: %s", IogI18nCycle());
        snes_osd_push(msg, 2000);
    }
    was_down = down;
}

static void IogBeforeRunFrame(void)
{
    static int initialized;
    if (!initialized) {
        initialized = 1;
        IogI18nInit();
    }
    IogPollLanguageHotkey();
    IogI18nFrame();
    IogWidescreenBeforeFrame();
}

#include "iog_companion.h"
/* After a frame is rasterised: presentation added by mods. */
static void IogEndSimFrame(const uint8_t *field, unsigned number)
{
    (void)field;
    (void)number;
    IogCompanionGrabMenu();
    IogInventoryOverlay();
    if (field) IogSceneViewEndFrame(&s_scene_view, number);
}

static int IogDrawSceneView(uint8_t *dst, size_t pitch, const uint8_t *field,
                           int width, int height, double alpha)
{
    if (IogWorldEnabled())
        return IogWorldDraw(dst, pitch, field, width, height, alpha);
    return IogSceneViewDraw(&s_scene_view, dst, pitch, field, width, height, alpha);
}

static void IogResetSceneView(void)
{
    IogWorldReset();
    IogInitSceneView();
    IogSceneViewReset(&s_scene_view);
    IogWidescreenSetPreviewCenteredHud(false);
}

static void IogPresentationGeometry(int dw, int dh, int *w, int *h)
{
    IogWorldGeometry(dw, dh, w, h);
}

static void IogViewport(int fw, int fh, int dw, int dh, SnesDisplayViewport *out)
{
    if (!out || fw <= 0 || fh <= 0) return;
    int num = 1, den = 1;
    if (!IogWorldEnabled()) SnesDisplayAspect_GetPixelAspect(
        (SnesDisplayAspect)g_config.display_aspect, &num, &den);
    *out = SnesDisplayAspect_FitViewport((double)fw * num / ((double)fh * den), dw, dh);
}

void IogSettingsInstall(void);   /* iog_settings.c */
static void IogAfterRunFrame(const SnesDesktopHostFrameStats *st) { (void)st; IogCompanionAfterFrame(); }

static const SnesDesktopHostGame kGameHost = {
    .display_name        = "Illusion Of Gaia Usa",
    .window_title        = "Illusion of Gaia Companion - Babel Recomp",
    .region              = SNESRECOMP_ROM_REGION,
    .rom_file            = SNESRECOMP_ROM_FILE,
    .expected_sha256_hex = SNESRECOMP_ROM_EXPECTED_SHA256,
    .expected_crc32_hex  = SNESRECOMP_ROM_EXPECTED_CRC32,
    .game_id             = SNESRECOMP_ROM_GAME_ID,
    .build_version       = SNES_GAME_VERSION,
    .game_info           = &kGameInfo,
    .num_players         = 1,
    /* Battery-backed SRAM shows the launcher's SAVES panel. Leave NULL for a
     * title without one. The path is exe-relative. */
    .sram_path           = "saves/save.srm",
    .widescreen_supported = 1,
    .native_widescreen   = 1,
    /* RetroArch GLSL presets (.glslp/.glsl) on the OpenGL presenter. */
    .shader_supported    = 1,
    .prepare_frame       = IogPrepareFrame,
    .begin_sim_frame     = IogBeginSimFrame,
    .before_run_frame    = IogBeforeRunFrame,
    .end_sim_frame       = IogEndSimFrame,
    .draw_frame          = IogDrawSceneView,
    .presentation_geometry = IogPresentationGeometry,
    .compute_viewport    = IogViewport,
    .on_reset            = IogResetSceneView,
    .after_config        = IogSettingsInstall,
    .after_run_frame     = IogAfterRunFrame,
    .companion_open      = IogCompanionOpen,
    .companion_nav       = IogCompanionNav,
    .companion_key       = IogCompanionKey,
    .companion_pointer   = IogCompanionPointer,
    .companion_image     = IogCompanionImage,
    .companion_live      = IogCompanionLive,
};
#endif

#ifndef __ANDROID__
#undef main   /* desktop: keep plain main() even if SDL_main.h remapped it */
#endif
int main(int argc, char **argv)
{
#ifdef IOG_RECEIVED_REFERENCE
    fprintf(stderr,"[gaialabs] Received-content reference: interpreter only; stock hooks/plugins disabled\n");
#else
    fprintf(stderr, "%s\n", IOG_EXECUTION_ID);
#endif
    return snesrecomp_desktop_main(&kGameHost, argc, argv);
}
