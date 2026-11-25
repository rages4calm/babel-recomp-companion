/*
 * Illusion of Gaia's items in the in-game settings menu
 * (snes_settings_menu.h). Each change applies at once where the game can
 * take it mid-session, and is written to the mod selection (state.toml) so
 * the launcher and the next launch agree.
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "mod_runtime.h"
#include "present_filter.h"
#include "snes_overlay_draw.h"
#include "snes_settings_menu.h"
#include "snes/msu1.h"

#include "iog_i18n.h"
#include "iog_randomizer.h"
#include "iog_cheat_rates.h"
#include "iog_map_host.h"
#include "desktop/config.h"
#include "desktop/sdl_compat.h"

/* ---- button prompts ----------------------------------------------------------
 * The physical controller button bound to an SNES pad bit for player 1, from
 * the live [GamepadMap], as the label an Xbox-layout pad prints on it. Returns
 * 0 when no controller is connected or nothing is bound (callers then name a
 * keyboard key). Face buttons take the overlay's button colours. */
int IogHostPadLabel(uint32_t snes_bit, char label[8], uint32_t *color)
{
    /* [GamepadMap] Controls order: Up Down Left Right Select Start A B X Y L R. */
    static const uint32_t kOrder[12] = {SNES_PAD_UP, SNES_PAD_DOWN, SNES_PAD_LEFT, SNES_PAD_RIGHT,
        SNES_PAD_SELECT, SNES_PAD_START, SNES_PAD_A, SNES_PAD_B, SNES_PAD_X, SNES_PAD_Y,
        SNES_PAD_L, SNES_PAD_R};
    static const struct { int button; const char *name; uint32_t color; } kNames[] = {
        {kGamepadBtn_A, "A", SNES_OVL_COL_A}, {kGamepadBtn_B, "B", SNES_OVL_COL_B},
        {kGamepadBtn_X, "X", SNES_OVL_COL_X}, {kGamepadBtn_Y, "Y", SNES_OVL_COL_Y},
        {kGamepadBtn_Back, "BACK", 0}, {kGamepadBtn_Start, "START", 0},
        {kGamepadBtn_L1, "LB", 0}, {kGamepadBtn_R1, "RB", 0}, {kGamepadBtn_L2, "LT", 0},
        {kGamepadBtn_R2, "RT", 0}, {kGamepadBtn_L3, "L3", 0}, {kGamepadBtn_R3, "R3", 0},
        {kGamepadBtn_DpadUp, "UP", 0}, {kGamepadBtn_DpadDown, "DOWN", 0},
        {kGamepadBtn_DpadLeft, "LEFT", 0}, {kGamepadBtn_DpadRight, "RIGHT", 0},
    };
    int pads = 0;
#if SNESRECOMP_SDL3
    SDL_JoystickID *ids = SDL_GetGamepads(&pads);
    if (ids) SDL_free(ids);
#else
    pads = SDL_NumJoysticks();
#endif
    if (pads <= 0 || !label || !color) return 0;
    for (int i = 0; i < 12; i++) {
        if (kOrder[i] != snes_bit) continue;
        for (size_t n = 0; n < sizeof(kNames) / sizeof(kNames[0]); n++)
            if (FindCmdForGamepadButton(kNames[n].button, 0) == kKeys_Controls + i) {
                snprintf(label, 8, "%s", kNames[n].name);
                *color = kNames[n].color;
                return 1;
            }
    }
    return 0;
}

int IogHoldAdvanceGet(void);
void IogHoldAdvanceSet(int v);

/* ---- HD scaling (iog.graphics/hd) ---------------------------------------- */
static const char *const kScaling[] = {"ORIGINAL", "SHARP PIXELS", "SMOOTH (XBR)"};

static int ScalingGet(void *ud) { (void)ud; return PresentFilter_Get(); }
static void ScalingSet(void *ud, int v)
{
    (void)ud;
    PresentFilter_Set(v);
    snes_mod_runtime_persist_feature_c("iog.graphics", "hd", v != 0, v ? "filter" : NULL,
                                       v == 2 ? "smooth" : "sharp");
}

/* ---- hold to advance (iog.enhancements/hold_advance) ---------------------- */
static const char *const kAdvance[] = {"OFF", "SLOW", "NORMAL", "FAST"};
static const char *const kAdvanceIds[] = {"normal", "slow", "normal", "fast"};

static int AdvanceGet(void *ud) { (void)ud; return IogHoldAdvanceGet(); }
static void AdvanceSet(void *ud, int v)
{
    (void)ud;
    IogHoldAdvanceSet(v);
    snes_mod_runtime_persist_feature_c("iog.enhancements", "hold_advance", v != 0,
                                       v ? "speed" : NULL, kAdvanceIds[v & 3]);
}

/* ---- language (iog.languages/language) ------------------------------------ */
static const char *const kLangNames[] = {"ENGLISH", "ESPAÑOL", "FRANÇAIS", "DEUTSCH"};
static const char *const kLangCodes[] = {"original", "es", "fr", "de"};
static int g_lang_choice = -1;

static int LangGet(void *ud)
{
    (void)ud;
    if (g_lang_choice >= 0)
        return g_lang_choice;
    const char *cur = IogI18nLanguage();
    for (int i = 0; i < 4; i++)
        if (!strcmp(cur, kLangCodes[i]))
            return i;
    return 0;
}
static void LangSet(void *ud, int v)
{
    (void)ud;
    /* Skip languages whose ROM is not in languages/ (or chosen on the Mods
     * page): Left/Right steps over them. */
    const int start = LangGet(NULL);
    const int dir = ((v - start + 4) % 4) == 3 ? -1 : 1;
    for (int n = 0; n < 4 && !IogI18nAvailable(kLangCodes[v]); n++)
        v = (v + dir + 4) % 4;
    if (!IogI18nAvailable(kLangCodes[v]) || IogRandomizerActive())
        return;
    g_lang_choice = v;
    IogI18nSetLanguage(kLangCodes[v]);
    snes_mod_runtime_persist_feature_c("iog.languages", "language", v != 0,
                                       v ? "code" : NULL, kLangCodes[v]);
}

/* ---- MSU-1 (iog.enhancements/msu1): next launch --------------------------- */
static int g_msu = -1;
static int MsuGet(void *ud)
{
    (void)ud;
    if (g_msu < 0)
        g_msu = snes_mod_runtime_feature_enabled_c("iog.enhancements", "msu1") > 0;
    return g_msu;
}
static void MsuSet(void *ud, int v)
{
    (void)ud;
    g_msu = v != 0;
    snes_mod_runtime_persist_feature_c("iog.enhancements", "msu1", g_msu, NULL, NULL);
}

/* ---- cheats (iog.cheats): live ---------------------------------------------- */
int IogCheatGet(int which);
void IogCheatSet(int which, int on);
static int CheatGet(void *ud) { return IogCheatGet((int)(intptr_t)ud); }
static void CheatSet(void *ud, int v) { IogCheatSet((int)(intptr_t)ud, v != 0); }
static const char *const kRewardRates[]={"ORIGINAL (1X)","2X","3X","4X","5X","6X","7X","8X"};
static int RewardRateGet(void *ud) { (void)ud;return IogRoomRewardMultiplierGet()-1; }
static void RewardRateSet(void *ud,int value) { (void)ud;IogRoomRewardMultiplierSet(value+1); }
static const char *const kMapButtons[]={"A","B","X","Y","L","R"};
static int MapRadarGet(void *ud){(void)ud;return IogMapHostRadarEnabled();}
static void MapRadarSet(void *ud,int value){(void)ud;IogMapHostRadarSet(value!=0);}
static int MapControlGet(void *ud){return IogMapHostControlGet((int)(intptr_t)ud);}
static void MapControlSet(void *ud,int value){IogMapHostControlSet((int)(intptr_t)ud,value);}

/* ---- the in-game menus in the game's language -------------------------------
 * English is the source; Spanish while the game runs in Spanish. */
static const char *const kEs[][2] = {
    {"SETTINGS", "AJUSTES"}, {"SELECT", "ELEGIR"}, {"LEFT/RIGHT CHANGE", "IZQ/DER CAMBIA"},
    {"BACK TO GAME", "VOLVER AL JUEGO"}, {"APPLIES ON THE NEXT LAUNCH", "SE APLICA AL REINICIAR"},
    {"PRESS A AGAIN", "PULSA A OTRA VEZ"}, {"ON", "SÍ"}, {"OFF", "NO"},
    {"DISPLAY", "PANTALLA"}, {"FULLSCREEN", "PANTALLA COMPLETA"}, {"FPS COUNTER", "CONTADOR DE FPS"}, {"HD MODE 7", "MODO 7 EN HD"},
    {"COMPANION SCREEN", "PANTALLA COMPAÑERA"}, {"DUAL", "DOBLE"}, {"FLIP GRIP", "FLIP GRIP"},
    {"FLIP GRIP R", "FLIP GRIP R"}, {"AUDIO", "SONIDO"}, {"VOLUME", "VOLUMEN"},
    {"RETROACHIEVEMENTS", "RETROACHIEVEMENTS"}, {"ACHIEVEMENTS", "LOGROS"},
    {"SYSTEM", "SISTEMA"}, {"SAVE STATES", "ESTADOS GUARDADOS"}, {"RESET GAME", "REINICIAR JUEGO"},
    {"QUIT GAME", "SALIR DEL JUEGO"}, {"HD SCALING", "ESCALADO HD"}, {"ORIGINAL", "ORIGINAL"},
    {"SHARP PIXELS", "PÍXELES NÍTIDOS"}, {"SMOOTH (XBR)", "SUAVE (XBR)"}, {"LANGUAGE", "IDIOMA"},
    {"HOLD TO ADVANCE TEXT", "MANTENER PARA AVANZAR"}, {"SLOW", "LENTO"}, {"NORMAL", "NORMAL"},
    {"FAST", "RÁPIDO"}, {"MSU-1 MUSIC (NEXT LAUNCH)", "MÚSICA MSU-1 (AL REINICIAR)"},
    {"MAP / RADAR (SNES BUTTONS)", "MAPA / RADAR (BOTONES SNES)"}, {"RADAR", "RADAR"},
    {"MAP ZOOM IN", "MAPA: ACERCAR"}, {"MAP ZOOM OUT", "MAPA: ALEJAR"}, {"MAP CENTER", "MAPA: CENTRAR"},
    {"MAP RADAR TOGGLE", "MAPA: RADAR"}, {"MAP BACK", "MAPA: VOLVER"},
    {"HP REFILL", "RECARGAR VIDA"}, {"MINIMUM DP", "DP MÍNIMO"}, {"MINIMUM STATS", "ESTADÍSTICAS MÍNIMAS"},
    {"CHEATS (ACHIEVEMENTS OFF)", "TRUCOS (SIN LOGROS)"}, {"INFINITE HP", "VIDA INFINITA"},
    {"DP 99", "DP 99"}, {"STATS BOOST", "MEJORA DE ESTADÍSTICAS"}, {"ALL 50 RED JEWELS", "LAS 50 JOYAS ROJAS"}, {"GAME COMPLETED", "JUEGO COMPLETADO"},
    {"ROOM-CLEAR REWARDS", "PREMIOS POR SALA"}, {"ORIGINAL (1X)", "ORIGINAL (1X)"},
};

static const char *Translate(const char *en)
{
    if (strcmp(IogI18nLanguage(), "es"))
        return NULL;
    for (size_t i = 0; i < sizeof(kEs) / sizeof(kEs[0]); i++)
        if (!strcmp(kEs[i][0], en))
            return kEs[i][1];
    return NULL;
}

#include "iog_inventory.h"
void SnesRa_SetBlocked(const char *why);
static void ActJewels(void *ud)
{
    (void)ud;
    if (IogInventoryAllRedJewels() >= 0) {
        IogCheatsMarkUsed();
        SnesRa_SetBlocked("cheats are on");
    }
}

int IogCompletionPercent(void);
static void CompletionText(void *ud, int v, char *out, size_t cap)
{
    (void)ud; (void)v;
    const int pct = IogCompletionPercent();
    if (pct < 0) snprintf(out, cap, "-");
    else snprintf(out, cap, "%d%%", pct);
}

void IogSettingsInstall(void)
{
    snes_ui_set_translator(Translate);
    SnesSettingItem it;
    memset(&it, 0, sizeof(it));
    it.kind = kSnesSetting_Header;
    it.label = "ILLUSION OF GAIA";
    snes_settings_menu_add(&it);

    memset(&it, 0, sizeof(it));
    it.kind = kSnesSetting_Info;
    it.label = "GAME COMPLETED";
    it.value_text = CompletionText;
    snes_settings_menu_add(&it);

    memset(&it, 0, sizeof(it));
    it.kind = kSnesSetting_Choice;
    it.label = "HD SCALING";
    it.choices = kScaling;
    it.count = 3;
    it.get = ScalingGet;
    it.set = ScalingSet;
    snes_settings_menu_add(&it);

    memset(&it, 0, sizeof(it));
    it.kind = kSnesSetting_Choice;
    it.label = "LANGUAGE";
    it.choices = kLangNames;
    it.count = 4;
    it.get = LangGet;
    it.set = LangSet;
    snes_settings_menu_add(&it);

    memset(&it, 0, sizeof(it));
    it.kind = kSnesSetting_Choice;
    it.label = "HOLD TO ADVANCE TEXT";
    it.choices = kAdvance;
    it.count = 4;
    it.get = AdvanceGet;
    it.set = AdvanceSet;
    snes_settings_menu_add(&it);

    if (msu1_available()) {
        memset(&it, 0, sizeof(it));
        it.kind = kSnesSetting_Toggle;
        /* The shared menu draws its "applies on the next launch" note over
         * the last visible row (here MAP ZOOM IN), so the label says it. */
        it.label = "MSU-1 MUSIC (NEXT LAUNCH)";
        it.get = MsuGet;
        it.set = MsuSet;
        snes_settings_menu_add(&it);
    }

    memset(&it,0,sizeof it);it.kind=kSnesSetting_Header;
    it.label="MAP / RADAR (SNES BUTTONS)";snes_settings_menu_add(&it);
    memset(&it,0,sizeof it);it.kind=kSnesSetting_Toggle;it.label="RADAR";
    it.get=MapRadarGet;it.set=MapRadarSet;snes_settings_menu_add(&it);
    static const char *const map_labels[]={"MAP ZOOM IN","MAP ZOOM OUT","MAP CENTER",
        "MAP RADAR TOGGLE","MAP BACK"};
    for(int action=0;action<IOG_MAP_CONTROL_COUNT;action++){
        memset(&it,0,sizeof it);it.kind=kSnesSetting_Choice;it.label=map_labels[action];
        it.choices=kMapButtons;it.count=IOG_MAP_BUTTON_COUNT;
        it.get=MapControlGet;it.set=MapControlSet;it.ud=(void*)(intptr_t)action;
        snes_settings_menu_add(&it);
    }

    static const char *const kCheatLabels[] = {"HP REFILL", "MINIMUM DP", "MINIMUM STATS"};
    memset(&it, 0, sizeof(it));
    it.kind = kSnesSetting_Header;
    it.label = "CHEATS (ACHIEVEMENTS OFF)";
    snes_settings_menu_add(&it);
    for (int i = 0; i < 3; i++) {
        memset(&it, 0, sizeof(it));
        it.kind = kSnesSetting_Toggle;
        it.label = kCheatLabels[i];
        it.get = CheatGet;
        it.set = CheatSet;
        it.ud = (void *)(intptr_t)i;
        snes_settings_menu_add(&it);
    }
    memset(&it,0,sizeof it);
    it.kind=kSnesSetting_Choice;
    it.label="ROOM-CLEAR REWARDS";
    it.choices=kRewardRates;it.count=8;
    it.get=RewardRateGet;it.set=RewardRateSet;
    snes_settings_menu_add(&it);
    memset(&it, 0, sizeof(it));
    it.kind = kSnesSetting_Action;
    it.label = "ALL 50 RED JEWELS";
    it.action = ActJewels;
    it.confirm = 1;
    snes_settings_menu_add(&it);
}
