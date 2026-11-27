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
#include "iog_map_host.h"
#include "iog_randomizer.h"
#include "iog_inventory.h"
#include "iog_i18n.h"
#include "iog_build_info.h"
#include "iog_walkable_world.h"
#include "snes_osd.h"
#include "snes_overlay_draw.h"
#include <stdio.h>
#include <stdlib.h>
#include "common_rtl.h"
#include "snes/snes.h"
#include "snes/hd_jobs.h"
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

static void IogPollRadarHotkey(void)
{
    if(RtlSpeculativeFrame())return;
    static bool was_down;
    const uint8_t *keys=snesrecomp_sdl_get_keyboard_state();
    bool down=keys&&keys[SDL_SCANCODE_M]&&
        (keys[SDL_SCANCODE_LCTRL]||keys[SDL_SCANCODE_RCTRL]);
    if(down&&!was_down)IogMapHostRadarToggle();
    was_down=down;
}

#ifdef IOG_RECEIVED_REFERENCE
#include "iog_received_world.h"
#include "iog_received_observer.h"
static void IogReferenceAfterFrame(const SnesDesktopHostFrameStats *stats)
{
    (void)stats;
    IogVisualReceivedSource source;
    bool verified=IogReceivedWorldEnabled()&&IogReceivedObserverPicture(&source);
    IogMapHostFrame(verified,IOG_RECEIVED_REFERENCE_SHA256);
}
static int IogReferenceDraw(uint8_t *dst,size_t pitch,const uint8_t *field,int w,int h,double alpha)
{
    int drawn=IogReceivedWorldDraw(dst,pitch,field,w,h,alpha);
    if(drawn)IogMapHostDrawRadar(dst,pitch,w,h);
    return drawn;
}
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
#ifdef IOG_RECEIVED_MAIN_CONTENT
    .display_name = "GaiaLabs main-content integration preview (interpreted guest CPU)",
    .window_title = "Illusion of Gaia - GaiaLabs integration preview",
#else
    .display_name = "GaiaLabs received-content reference (interpreted)",
    .window_title = "GaiaLabs reference - not native qualification",
#endif
    .region = SNESRECOMP_ROM_REGION,
    .rom_file = IOG_RECEIVED_REFERENCE_ROM_FILE,
    .expected_sha256_hex = IOG_RECEIVED_REFERENCE_SHA256,
    .expected_crc32_hex = NULL,
#ifdef IOG_RECEIVED_MAIN_CONTENT
    .game_id = "iog-gaialabs-main-preview-" IOG_RECEIVED_REFERENCE_SHA256,
    .build_version = "main-content-preview-dev",
#else
    .game_id = "iog-gaialabs-reference-" IOG_RECEIVED_REFERENCE_SHA256,
    .build_version = "received-reference-dev",
#endif
    .game_info = &kGameInfo,
    .num_players = 1,
#ifdef IOG_RECEIVED_MAIN_CONTENT
    .sram_path = "saves/gaialabs-main-preview.srm",
#else
    .sram_path = "saves/received-reference.srm",
#endif
    .native_widescreen = 1,
    .prepare_frame = IogReferenceFrame,
    .presentation_geometry = IogReceivedWorldGeometry,
    .draw_frame = IogReferenceDraw,
    .compute_viewport = IogReceivedViewport,
    .after_run_frame = IogReferenceAfterFrame,
    .before_run_frame = IogPollRadarHotkey,
    .on_reset = IogMapHostReset,
    .on_shutdown = IogMapHostShutdown,
    .companion_open = IogMapHostOpen,
    .companion_input = IogMapHostInput,
    .companion_nav = IogMapHostNav,
    .companion_key = IogMapHostKey,
    .companion_image = IogMapHostImage,
    .companion_pointer = IogMapHostPointer,
};
#else
#include "companion_achievements/audit.h"
#include "companion_achievements/presentation.h"
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
    IogPollRadarHotkey();
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
#include "iog_sparkle.h"
/* After a frame is rasterised: presentation added by mods. */
static void IogEndSimFrame(const uint8_t *field, unsigned number)
{
    (void)field;
    (void)number;
    IogCompanionGrabMenu();
    IogInventoryOverlay();
    if (!IogWorldEnabled())
        IogSparkleNative();   /* the wide view draws its own at presentation */
    if (field) IogSceneViewEndFrame(&s_scene_view, number);
}

static void IogDrawWorldHint(uint8_t *dst,size_t pitch,int width,int height,
                             int y,const char *text)
{
    int x=(width-8*snes_ovl_text_len(text))/2;
    int stride=(int)(pitch/sizeof(uint32_t));
    snes_ovl_draw_text((uint32_t *)dst,stride,height,x+1,y+1,text,0xff34270du,1);
    snes_ovl_draw_text((uint32_t *)dst,stride,height,x,y,text,0xfff2dda4u,1);
}

/* GPU ground for the Enhanced walking map: hand its ground rows to the
 * runner's GPU Mode 7 presenter, which samples the plane at the window's
 * resolution. IogMapGpuSamples decides, before a frame is built, whether the
 * presenter will take it; the renderer then skips its own filtered plane.
 * IogWorldHdPublish is called with the finished host picture: whatever the
 * software picture's ground does not explain (objects, pins, minimap,
 * plates) stays a software pixel. NULL withdraws the rows. */
#if SNESRECOMP_HAS_GL_PRESENTER && !SNESRECOMP_SDL_GLES2_ONLY
bool snesrecomp_opengl_hd_refused(void);   /* desktop/opengl.c */
#define IOG_MAP_GPU_PRESENTER 1
#else
#define IOG_MAP_GPU_PRESENTER 0
#endif
/* Samples per axis for the next frame; 0: the software plane.
 * IOG_WORLD_MAP_GPU=0 forces the software plane, 1..4 a sample count. */
static int IogMapGpuSamples(int dw, int dh, int width, int height)
{
    static int forced = -2;
    static bool refused;
    if (forced == -2) {
        const char *value = getenv("IOG_WORLD_MAP_GPU");
        forced = value && *value >= '0' && *value <= '4' && !value[1] ? *value - '0' : -1;
    }
    if (!IOG_MAP_GPU_PRESENTER || !forced || refused || dw <= 0 || dh <= 0 ||
        width <= 0 || height <= 0 || width > kSnesHdMaxWidth || height > kSnesHdMaxHeight) return 0;
#if IOG_MAP_GPU_PRESENTER
    /* A frame the presenter turned down: the software plane from here on. */
    if (snesrecomp_opengl_hd_refused()) { refused = true; return 0; }
#endif
    /* The presenter draws game-published rows only on OpenGL, on the plain
     * nearest path, in the single-screen layout and without frame blending.
     * Shader presets and linear filtering take the software picture. */
    if (g_config.output_method != kOutputMethod_OpenGL || (g_config.shader && *g_config.shader) ||
        g_config.linear_filtering || g_config.frame_blend || g_config.companion_layout > 0 ||
        !IogWalkableWorldEnhanced()) return 0;
    SnesDisplayViewport view = SnesDisplayAspect_FitViewport((double)width / height, dw, dh);
    /* Its raster is the frame times the configured Mode 7 scale; below the
     * window's size it would be coarser than the software plane. */
    if ((long long)width * g_config.mode7.scale < view.width || view.width <= 0 || view.height <= 0) return 0;
    int samples = forced > 0 ? forced : 2;
    /* The presenter's own memory rule (opengl.c: 128 MB), else it halves the picture. */
    while (samples > 1 && (unsigned long long)view.width * view.height * 4 * (1 + samples * samples) +
           (unsigned long long)(width + 1) * view.height * samples * 16 > 128ull * 1024 * 1024) samples--;
    return samples;
}
static SnesHdFrame *s_map_hd;
static int s_map_gpu;   /* IogMapGpuSamples at this present */
static const struct SnesHdFrame *IogWorldHdFrame(void) { return s_map_hd; }
static void IogWorldHdPublish(const uint8_t *dst, size_t pitch, int width, int height)
{
    SnesHdFrameDestroy(s_map_hd); s_map_hd = NULL;
    IogWorldHdRow r;
    if (!dst || !s_map_gpu || width > kSnesHdMaxWidth || height > kSnesHdMaxHeight ||
        !IogWorldHdQuery(0, width, height, &r)) return;
    SnesHdFrame *frame = SnesHdFrameCreate((unsigned)width, (unsigned)height);
    static SnesHdLine line;
    const uint16_t *picture = NULL;
    int left = (width - 256) / 2, source = -1;
    bool ok = frame && SnesHdFrameSetSampling(frame, (unsigned)r.samples);
    for (int row = 0; row < height && ok; row++) {
        ok = IogWorldHdQuery(row, width, height, &r);
        memset(&line, 0, sizeof(line));
        memcpy(line.native, dst + row * pitch, (size_t)width * 4);
        line.kind = kSnesHdNative; line.brightness = 15;
        if (ok && r.kind) {
            if (picture != r.vram) { source = SnesHdFrameAddPicture(frame, r.vram); picture = r.vram; }
            if (source < 0) { ok = false; break; }
            line.kind = kSnesHdAffine; line.source = (uint16_t)source;
            line.control = r.control; line.brightness = r.light;
            line.cgwsel = r.cgwsel; line.cgadsub = r.cgadsub; line.fixed_color = r.fixed;
            memcpy(line.palette, r.cgram, sizeof(line.palette));
            /* Past the map edge the software plane shows the open sea (the
             * map's commonest texel); index 0 inside the map stays the
             * backdrop, as the original field shows it (the black columns at
             * the east edge, Angel Village). Recolouring palette entry 0 also
             * turned those into sea on the GPU ground. */
            if (r.edge >= 0) line.outside = (uint16_t)(r.edge + 1);
            line.screen_left = line.active_left = (int16_t)-left;
            line.active_right = (int16_t)(width - left);
            memcpy(line.affine, r.affine, sizeof(line.affine));
            unsigned alpha = r.haze * 255u / 256u;
            for (int x = 0; x < width; x++) {
                line.visibility[x] = 1;
                line.native_mask[x] = ((line.native[x] ^ r.soft[x]) & 0xffffffu) != 0;
                if (alpha) {
                    uint32_t sky = IogWorldHdHaze(x, r.light);
                    line.overlay[x] = alpha << 24 | (((sky >> 16) & 255) * alpha / 255) << 16 |
                        (((sky >> 8) & 255) * alpha / 255) << 8 | (sky & 255) * alpha / 255;
                }
            }
        }
        ok = ok && SnesHdFrameSetLine(frame, (unsigned)row, &line);
    }
    if (ok && SnesHdFrameSeal(frame)) s_map_hd = frame;
    else SnesHdFrameDestroy(frame);
}

/* The status display and dialogue are a layer the presenter draws over the
 * scaled frame (snes_ovl_frame_layer_set), so an achievement toast drawn into
 * the frame came out underneath them. Clear the layer where the toast is,
 * and the toast shows through, above the status display. */
static void IogToastAboveStatus(int width, int height)
{
    int toast[4], rect[4], lw = 0, lh = 0;
    uint32_t *layer = NULL;
    static int below = -1;   /* IOG_TOAST_BELOW_STATUS=1: the old picture, for comparison */
    if (below < 0) { const char *v = getenv("IOG_TOAST_BELOW_STATUS"); below = v && *v == '1'; }
    if (below) return;
    if (!IogAchievementUiToastRect(width, height, toast) ||
        !snes_ovl_frame_layer_peek(&layer, &lw, &lh, rect) || !layer ||
        rect[2] <= 0 || rect[3] <= 0 || lw <= 0 || lh <= 0) return;
    int x0 = (toast[0] - rect[0]) * lw / rect[2];
    int x1 = ((toast[0] + toast[2] - rect[0]) * lw + rect[2] - 1) / rect[2];
    int y0 = (toast[1] - rect[1]) * lh / rect[3];
    int y1 = ((toast[1] + toast[3] - rect[1]) * lh + rect[3] - 1) / rect[3];
    if (toast[0] < rect[0]) x0 = 0;
    if (toast[1] < rect[1]) y0 = 0;
    if (x1 > lw) x1 = lw;
    if (y1 > lh) y1 = lh;
    for (int y = y0; y < y1 && x0 < x1; y++)
        memset(layer + (size_t)y * lw + x0, 0, (size_t)(x1 - x0) * sizeof(*layer));
}

static int IogDrawSceneView(uint8_t *dst, size_t pitch, const uint8_t *field,
                           int width, int height, double alpha)
{
    IogWorldHdPublish(NULL,0,0,0);
    int drawn=IogWorldEnabled()?IogWorldDraw(dst,pitch,field,width,height,alpha):
        IogSceneViewDraw(&s_scene_view,dst,pitch,field,width,height,alpha);
    if(drawn) {
        IogMapHostDrawRadar(dst,pitch,width,height);
        IogAchievementUiToast(dst,pitch,width,height);
        {   /* Diagnostics: confirm a bug mark for two seconds. */
            extern unsigned g_snesrecomp_diag_mark;
            static unsigned shown;static int frames;
            if(g_snesrecomp_diag_mark!=shown) {shown=g_snesrecomp_diag_mark;frames=120;}
            if(frames>0) {frames--;IogDrawWorldHint(dst,pitch,width,height,height-22,"MARKED");}
        }
        IogToastAboveStatus(width,height);
        if(IogWalkableWorldActive() && IogWalkableWorldEnhanced()) {
            IogWalkableWorldDrawOverlay(dst,pitch,width,height);
        } else if(IogWalkableWorldActive()) {
            const char *location=IogWalkableWorldLocation();
            char direction[64];
            if(location) {
                IogDrawWorldHint(dst,pitch,width,height,height/2-46,location);
                IogDrawWorldHint(dst,pitch,width,height,height-22,"B (SNES): Enter");
            } else {
                if(IogWalkableWorldDirection(direction,sizeof(direction)))
                    IogDrawWorldHint(dst,pitch,width,height,height/2-46,direction);
                IogDrawWorldHint(dst,pitch,width,height,height-22,"Up/Down: Walk  Left/Right: Turn");
            }
        }
        if(IogWorldEnabled()) IogWorldHdPublish(dst,pitch,width,height);
    }
    return drawn;
}

static void IogResetSceneView(void)
{
    IogWorldReset();
    IogAchievementAuditInvalidate();
    IogMapHostReset();
    IogInitSceneView();
    IogSceneViewReset(&s_scene_view);
    IogWidescreenSetPreviewCenteredHud(false);
}

static void IogPresentationGeometry(int dw, int dh, int *w, int *h)
{
    IogWorldGeometry(dw, dh, w, h);
    if (IogWorldEnabled() && w && h) IogWorldSetMapGpu(s_map_gpu = IogMapGpuSamples(dw, dh, *w, *h));
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
static void IogAfterRunFrame(const SnesDesktopHostFrameStats *st)
{
    IogAchievementAuditFrame(st->frame);
    IogAchievementUiFrame(st->frame, (uint32_t)SDL_GetTicks(), IogCompanionAchievementQuiet() && !IogWalkableWorldActive());
    IogMapHostFrame(IogWorldStockVerified()&&!IogRandomizerActive(),SNESRECOMP_ROM_EXPECTED_SHA256);
    IogCompanionAfterFrame();
}

static void IogShutdown(void)
{
    IogAchievementUiShutdown();
    IogMapHostShutdown();
}

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
    .on_shutdown         = IogShutdown,
    .after_config        = IogSettingsInstall,
    .after_run_frame     = IogAfterRunFrame,
    .companion_open      = IogCompanionOpen,
    .companion_input     = IogCompanionInput,
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
    IogAchievementAuditStart(argc, argv);
#endif
#ifndef IOG_RECEIVED_REFERENCE
    /* The wide world view publishes the walking map's ground to the GPU
     * presenter. The classic view keeps the host's own Mode 7 capture, which
     * a game-published frame would replace. */
    static SnesDesktopHostGame world_host;
    if (IogWorldEnabled()) {
        world_host = kGameHost; world_host.hd_frame = IogWorldHdFrame;
        const int world_result = snesrecomp_desktop_main(&world_host, argc, argv);
        IogAchievementAuditShutdown();
        return world_result;
    }
#endif
    const int result = snesrecomp_desktop_main(&kGameHost, argc, argv);
#ifndef IOG_RECEIVED_REFERENCE
    IogAchievementAuditShutdown();
#endif
    return result;
}
