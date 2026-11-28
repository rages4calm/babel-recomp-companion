/* ROM-free fixture for controller rumble. Includes the ACTUAL src/iog_rumble.c
 * (tracker and runtime: the frame callback, the plugin, the settings get/set,
 * the player-1 pad choice and the IOG_RUMBLE_LOG writer); only host services
 * and SDL are stubbed. SDL_RumbleGamepad calls are recorded.
 *
 * The game is modelled as the callback sees it: WRAM words $09AA (player),
 * $0ACE/$0ACA (HP / max), $09AE (playerFlags), $06F8 (SFX latch), the state
 * generation and run-ahead's speculative flag. A save state is a copy of the
 * modelled WRAM; a real load, rewind or reset changes the generation, a
 * rollback restores the copy and keeps it (common_rtl.c). */
#include "iog_rumble.c"

static uint8_t test_ram[0x20000];
static Snes test_snes = {test_ram, 0, 0};
Snes *g_snes = &test_snes;
Config g_config;
int snes_frame_counter;
static uint64_t generation = 1;
static bool speculative;
uint64_t RtlStateGeneration(void) { return generation; }
bool RtlSpeculativeFrame(void) { return speculative; }

static SNESModFrameCallback observer;
void IogModsSetHpObserver(SNESModFrameCallback cb) { observer = cb; }
static SNESModActivationCallback reset_cb, plugin_cb;
static const char *plugin_id;
int snes_mod_register_reset_callback(SNESModActivationCallback fn) { reset_cb = fn; return 1; }
int snes_mod_register_activation_plugin(const char *id, SNESModActivationCallback fn) { plugin_id = id; plugin_cb = fn; return 1; }
int snes_mod_register_presentation_plugin(const char *id, SNESModActivationCallback fn) { (void)id; (void)fn; return 1; }
int snes_mod_register_frame_callback(SNESModFrameCallback fn) { (void)fn; return 1; }
int snes_mod_register_input_filter(SNESModInputFilter fn) { (void)fn; return 1; }
int snes_mod_runtime_feature_enabled_c(const char *p, const char *f) { (void)p; (void)f; return 1; }
static const char *option_strength = "normal";
int snes_mod_runtime_feature_option_value_c(const char *p, const char *f, const char *o, char *out, size_t cap)
{
    (void)p; (void)f; (void)o;
    snprintf(out, cap, "%s", option_strength);
    return (int)strlen(out);
}
static char persisted[64];
int snes_mod_runtime_persist_feature_c(const char *p, const char *f, int e, const char *o, const char *v)
{ snprintf(persisted, sizeof persisted, "%s/%s:%d:%s=%s", p, f, e, o ? o : "-", v ? v : "-"); return 1; }

/* SDL: one or two pads, recorded rumble calls. */
struct SDL_Gamepad { SDL_JoystickID id; int player_index; };
static SDL_Gamepad pads[2] = {{11, 1}, {12, 0}};
static int pad_count = 1;
typedef struct Call { SDL_Gamepad *pad; uint16_t low, high; uint32_t ms; int frame; } Call;
static Call calls[256];
static int ncalls;
SDL_JoystickID *SDL_GetGamepads(int *count)
{
    *count = pad_count;
    SDL_JoystickID *ids = malloc(sizeof *ids * 2);
    for (int i = 0; i < pad_count; i++) ids[i] = pads[i].id;
    return ids;
}
void SDL_free(void *p) { free(p); }
SDL_Gamepad *SDL_GetGamepadFromID(SDL_JoystickID id)
{
    for (int i = 0; i < pad_count; i++) if (pads[i].id == id) return &pads[i];
    return NULL;
}
int SDL_GetGamepadPlayerIndex(SDL_Gamepad *p) { return p->player_index; }
static int seated_id = -1;   /* the host's seat 0, -1 unknown */
int snesrecomp_host_seat_gamepad_id(int seat) { return seat == 0 ? seated_id : -1; }
bool SDL_RumbleGamepad(SDL_Gamepad *p, uint16_t low, uint16_t high, uint32_t ms)
{
    if (ncalls < 256) calls[ncalls++] = (Call){p, low, high, ms, snes_frame_counter};
    return true;
}

static unsigned assertions, failures;
static const char *current_case;
#define CHECK(v) do { assertions++; if (!(v)) { failures++; \
    fprintf(stderr, "FAIL %s %s:%d: %s\n", current_case, __FILE__, __LINE__, #v); } } while (0)

static void W(uint32_t a, uint16_t v) { test_ram[a] = (uint8_t)v; test_ram[a + 1] = (uint8_t)(v >> 8); }
static uint16_t R(uint32_t a) { return (uint16_t)(test_ram[a] | test_ram[a + 1] << 8); }
static void Play(uint16_t hp, uint16_t max)
{ W(0x09AA, 0x1000); W(0x0ACE, hp); W(0x0ACA, max); W(0x09AE, 0); W(0x06F8, 0); }
/* One real frame: the game changes RAM (already done by the caller), the
 * framework runs the mod frame callbacks (never on a speculative frame). */
static void Frame(void) { snes_frame_counter++; if (!speculative) observer(); }
static void Frames(int n) { while (n-- > 0) Frame(); }
static void Boot(int pads_connected, bool p1_gamepad)
{
    memset(test_ram, 0, sizeof test_ram);
    generation = 1; speculative = false; ncalls = 0; snes_frame_counter = 0;
    pad_count = pads_connected;
    g_config.enable_gamepad[0] = p1_gamepad;
    register_iog_rumble();
    reset_cb();
    plugin_cb();     /* the feature is on (manifest default) */
}
static int Pulses(void) { int n = 0; for (int i = 0; i < ncalls; i++) n += calls[i].low != 0; return n; }

static void CaseHit(void)
{
    Boot(1, true);
    CHECK(observer == RumbleFrame && plugin_id && !strcmp(plugin_id, "iog.rumble"));
    CHECK(IogRumbleGet() == kIogRumbleNormal);
    Play(20, 30); Frames(5);
    CHECK(ncalls == 0);
    W(0x0ACE, 19); Frame();          /* a 1-HP hit: felt once HP stops falling */
    CHECK(ncalls == 0);
    Frame();
    CHECK(ncalls == 1);
    Frames(30);
    CHECK(ncalls == 1);
    const Call small = calls[0];
    W(0x0ACE, 13); Frame(); Frames(30);   /* a 6-HP hit */
    CHECK(ncalls == 2);
    CHECK(calls[1].low > small.low && calls[1].high > small.high && calls[1].ms > small.ms);
    CHECK(small.low > 0 && small.ms >= 100 && calls[1].ms <= 240);
    /* New Game+: the game takes 2, the multiplier 2 more a callback later. */
    W(0x0ACE, 11); Frame(); W(0x0ACE, 9); Frame(); Frame(); Frames(20);
    CHECK(ncalls == 3);
    CHECK(calls[2].low > small.low);
    /* The HP refill cheat puts HP back right after the hit: still one pulse. */
    W(0x0ACE, 6); Frame(); W(0x0ACE, 30); Frame(); Frames(20);
    CHECK(ncalls == 4);
    CHECK(calls[0].pad == &pads[0]);
}
static void CaseGain(void)
{
    Boot(1, true);
    Play(10, 30); Frames(3);
    W(0x0ACE, 14); Frames(3);        /* herb */
    W(0x0ACE, 30); Frames(3);
    W(0x0ACA, 31); W(0x0ACE, 31); Frames(3);   /* max HP reward */
    CHECK(ncalls == 0);
}
static void CaseLoadRewindReset(void)
{
    Boot(1, true);
    Play(30, 30); Frames(5);
    W(0x0ACE, 5); generation++; Frames(5);     /* state load with less HP */
    CHECK(ncalls == 0);
    W(0x0ACE, 2); generation++; Frames(5);     /* rewind */
    CHECK(ncalls == 0);
    generation++; memset(test_ram, 0, 0x2000); Frames(30);   /* reset: title, no player */
    Play(17, 17); Frames(3);                    /* a file continued: first frames are a baseline */
    W(0x0ACE, 12); W(0x0ACA, 12); Frames(3);   /* another file's block */
    CHECK(ncalls == 0);
    /* A load during a hit pulse stops it, and starts nothing. */
    W(0x0ACE, 4); Frame(); Frame();
    CHECK(Pulses() == 1);
    W(0x0ACE, 1); generation++; Frame(); Frames(5);
    CHECK(Pulses() == 1 && ncalls == 2 && calls[1].low == 0 && calls[1].ms == 0);
    /* Back in play after the jump, hits count again. */
    W(0x0ACE, 0); Frame();
    CHECK(Pulses() == 2);
}
static void CaseRollback(void)
{
    Boot(1, true);
    Play(25, 30); Frames(5);
    uint8_t snapshot[0x2000];
    for (int f = 0; f < 20; f++) {
        /* Run-ahead: one real frame, then speculation that takes a hit,
         * then the rollback restores the real frame's RAM, generation kept. */
        Frame();
        memcpy(snapshot, test_ram, sizeof snapshot);
        const int saved = snes_frame_counter;
        speculative = true;
        W(0x0ACE, 20); Frame(); Frame();
        observer();                 /* even a callback run on one refuses it */
        speculative = false;
        memcpy(test_ram, snapshot, sizeof snapshot);
        snes_frame_counter = saved;
    }
    CHECK(ncalls == 0);
    W(0x0ACE, 20); Frame(); Frame();   /* the real frame reaches the hit */
    Frames(10);
    CHECK(ncalls == 1 && calls[0].low > 0);
}
static void CaseDeath(void)
{
    Boot(1, true);
    Play(3, 30); Frames(3);
    W(0x0ACE, 0); Frame();                  /* the lethal hit */
    W(0x09AE, 0x0200); Frames(60);          /* CheckPlayerDeath, the death sequence */
    CHECK(ncalls == 1 && calls[0].ms == 700 && calls[0].low == Motor(100, kIogRumbleNormal));
    W(0x0ACE, 30); Frames(5);               /* game over: HP refilled */
    W(0x09AE, 0); Frames(5);                /* the respawn */
    CHECK(ncalls == 1);
    W(0x0ACE, 28); Frame(); Frame();        /* hits after the respawn */
    CHECK(ncalls == 2 && calls[1].ms < 700);
    W(0x09AE, 0x0200); Frames(3);           /* a death by the flag alone (scripted) */
    CHECK(ncalls == 3 && calls[2].ms == 700);
    /* The hit pulse is bigger than every shake and smaller than death. */
    CHECK(calls[1].low < calls[2].low);
}
static void CaseOff(void)
{
    Boot(1, true);
    Play(30, 30); Frames(3);
    IogRumbleSet(kIogRumbleOff);
    CHECK(!strcmp(persisted, "iog.enhancements/rumble:0:-=normal"));
    CHECK(ncalls == 1 && calls[0].low == 0);   /* stops what plays */
    W(0x0ACE, 10); Frames(5); W(0x0ACE, 0); Frames(5); W(0x06F8, 0x1500); Frames(30);
    CHECK(Pulses() == 0);
    /* Live back on at Strong: stronger than Low for the same hit. */
    Play(30, 30);
    IogRumbleSet(kIogRumbleStrong);
    CHECK(!strcmp(persisted, "iog.enhancements/rumble:1:strength=strong"));
    Frames(2); W(0x0ACE, 27); Frame(); Frame(); Frames(20);
    IogRumbleSet(kIogRumbleLow); Frames(2);
    W(0x0ACE, 24); Frame(); Frame();
    CHECK(Pulses() == 2 && calls[ncalls - 1].low < calls[ncalls - 2].low);
    /* Disabled at launch: the plugin never runs, nothing rumbles. */
    reset_cb();
    CHECK(IogRumbleGet() == kIogRumbleOff);
    const int before = ncalls;
    W(0x0ACE, 10); Frames(5);
    CHECK(ncalls == before);
    option_strength = "strong"; plugin_cb(); option_strength = "normal";
    CHECK(IogRumbleGet() == kIogRumbleStrong);
}
static void CaseNoPad(void)
{
    Boot(0, true);                  /* gamepad play, nothing connected */
    Play(30, 30); Frames(3); W(0x0ACE, 20); Frames(3);
    CHECK(ncalls == 0);
    Boot(1, false);                 /* keyboard play, a pad connected */
    Play(30, 30); Frames(3); W(0x0ACE, 20); Frames(3); W(0x0ACE, 0); Frames(3);
    CHECK(ncalls == 0);
    Boot(2, true);                  /* two pads: SDL's player index 0 */
    Play(30, 30); Frames(3); W(0x0ACE, 20); Frames(3);
    CHECK(ncalls == 1 && calls[0].pad == &pads[1]);
    Boot(2, true); seated_id = 11;  /* the host seated the other pad as player 1 */
    Play(30, 30); Frames(3); W(0x0ACE, 20); Frames(3);
    CHECK(ncalls == 1 && calls[0].pad == &pads[0]);
    Boot(2, true); seated_id = 99;  /* a seat id SDL no longer knows: the fallback */
    Play(30, 30); Frames(3); W(0x0ACE, 20); Frames(3);
    CHECK(ncalls == 1 && calls[0].pad == &pads[1]);
    seated_id = -1;
}
static void CaseShake(void)
{
    Boot(1, true);
    Play(30, 30); Frames(3);
    for (int i = 0; i < 61; i++) { W(0x06F8, (i & 1) ? 0 : 0x1500); Frame(); }   /* NMI clears even frames */
    const int shakes = ncalls;
    CHECK(shakes >= 7 && shakes <= 9);
    for (int i = 0; i < ncalls; i++) CHECK(calls[i].low == Motor(30, kIogRumbleNormal) && calls[i].high == 0);
    W(0x06F8, 0); Frames(20);
    CHECK(ncalls == shakes);
    W(0x06F8, 0x0015); Frame(); W(0x06F8, 0); Frames(10);   /* one debris impact, channel 1 */
    CHECK(ncalls == shakes + 1);
    W(0x06F8, 0x0505); Frames(20);                        /* another sound */
    CHECK(ncalls == shakes + 1);
    /* A hit while shaking is not covered by the next shake pulse. */
    W(0x0ACE, 22); Frame(); W(0x06F8, 0x1500); Frames(12);
    CHECK(calls[shakes + 1].low > Motor(30, kIogRumbleNormal));
    CHECK(ncalls == shakes + 2);
}
static void CaseLog(const char *path)
{
    Boot(0, false);               /* the harness has no pad */
    g_log_checked = false; g_log = NULL;
    Play(30, 30); Frames(3); W(0x0ACE, 26); Frame(); Frame(); W(0x0ACE, 0); Frames(3);
    if (g_log) { fclose(g_log); g_log = NULL; }
    FILE *f = fopen(path, "r");
    CHECK(f != NULL);
    char line[256]; int n = 0, hit = 0, death = 0;
    while (f && fgets(line, sizeof line, f)) {
        n++;
        hit += strstr(line, "frame=5 kind=hit damage=4 ") != NULL;
        death += strstr(line, "kind=death damage=0 ") != NULL && strstr(line, "ms=700") != NULL;
    }
    if (f) fclose(f);
    CHECK(n == 2 && hit == 1 && death == 1);
    CHECK(ncalls == 0);
    /* Log-only even with player 1 on a connected gamepad: no motor call. */
    Boot(1, true);
    Play(30, 30); Frames(3); W(0x0ACE, 26); Frame(); Frame(); W(0x0ACE, 0); Frames(3);
    CHECK(ncalls == 0);
}

int main(int argc, char **argv)
{
    if (argc < 2) return 2;
    current_case = argv[1];
    if (!strcmp(argv[1], "hit")) CaseHit();
    else if (!strcmp(argv[1], "gain")) CaseGain();
    else if (!strcmp(argv[1], "load-rewind-reset")) CaseLoadRewindReset();
    else if (!strcmp(argv[1], "rollback")) CaseRollback();
    else if (!strcmp(argv[1], "death")) CaseDeath();
    else if (!strcmp(argv[1], "off")) CaseOff();
    else if (!strcmp(argv[1], "no-pad")) CaseNoPad();
    else if (!strcmp(argv[1], "shake")) CaseShake();
    else if (!strcmp(argv[1], "log") && argc > 2) CaseLog(argv[2]);
    else return 2;
    (void)R;
    printf("%s %s: %u assertions\n", failures ? "FAIL" : "PASS", argv[1], assertions);
    return failures ? 1 : 0;
}
