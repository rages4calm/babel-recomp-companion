/* ROM-free fixture for hold to advance (iog_mods.c HoldAdvanceFilter) across
 * timeline jumps. Includes the ACTUAL iog_mods implementation (the path comes
 * from IOG_MODS_SOURCE, so an older revision can be compiled for a before
 * run); only host services are stubbed.
 *
 * The game is modelled as far as the filter can see it: each frame the NMI
 * counter $36 ticks, the filter runs on the physical pad word, and the game
 * acts on a NEW press of A, B or Y (the edge against its previous word, which
 * a save state carries). A message is up when $09AA != 0 and $09EC & $2000;
 * a choice is being asked when $065C != 0. In a message a new press turns a
 * page; in a question it answers; in play it acts.
 *
 * A save state is the model's guest state plus the game_rtl.c tail words,
 * saved and loaded through the same three calls game_rtl.c makes. A real
 * load, rewind or reset then calls IogHoldAdvanceTimelineJump (GameStateLoaded
 * on a non-rollback load, GameHardwareReset); a rollback load does not. */
#include IOG_MODS_SOURCE

static uint8_t test_ram[0x20000], test_rom[0x8000];
static Cart test_cart = {test_rom, sizeof test_rom};
static Snes test_snes = {test_ram, &test_cart, 0};
Snes *g_snes = &test_snes;
static unsigned assertions, failures;
static const char *current_case;
#define CHECK(v) do { assertions++; if (!(v)) { failures++; \
    fprintf(stderr, "FAIL %s %s:%d: %s\n", current_case, __FILE__, __LINE__, #v); } } while (0)

uint64_t RtlStateGeneration(void) { return 1; }
bool IogRandomizerActive(void) { return false; }
void PresentFilter_Set(int value) { (void)value; }
void SnesRa_SetBlocked(const char *why) { (void)why; }
int snes_mod_register_reset_callback(SNESModActivationCallback fn) { (void)fn; return 1; }
int snes_mod_register_activation_plugin(const char *id, SNESModActivationCallback fn) { (void)id; (void)fn; return 1; }
int snes_mod_register_presentation_plugin(const char *id, SNESModActivationCallback fn) { (void)id; (void)fn; return 1; }
int snes_mod_register_frame_callback(SNESModFrameCallback fn) { (void)fn; return 1; }
int snes_mod_register_input_filter(SNESModInputFilter fn) { (void)fn; return 1; }
int snes_mod_runtime_feature_enabled_c(const char *p, const char *f) { (void)p; (void)f; return 0; }
int snes_mod_runtime_feature_option_value_c(const char *p, const char *f, const char *o, char *out, size_t cap)
{ (void)p; (void)f; (void)o; if (cap) out[0] = 0; return 0; }
int snes_mod_runtime_persist_feature_c(const char *p, const char *f, int e, const char *o, const char *v)
{ (void)p; (void)f; (void)e; (void)o; (void)v; return 1; }
/* iog_cheat_rates.c is not linked: the cheat plugins are never activated here. */
int IogCheatRateClampMultiplier(int v) { return v; }
bool IogCheatRateSourceSupported(const uint8_t *rom, size_t size) { (void)rom; (void)size; return false; }
void IogCheatRateTrackerInvalidate(IogCheatRateTracker *t) { memset(t, 0, sizeof *t); }
IogCheatRateAward IogCheatRateStep(IogCheatRateTracker *t, const IogCheatRateSample *s, int m)
{ (void)t; (void)s; (void)m; IogCheatRateAward a = {0, 0}; return a; }

enum { kAdv = kPadA | kPadB | kPadY };
enum { kPlay, kMessage, kQuestion };

typedef struct Game { uint8_t clock; uint16_t prev; int mode; } Game;
typedef struct State { Game game; uint16_t tail_latched, tail_held; } State;
static Game g;
static unsigned pages, answers, actions;
static uint32_t log_out[512];
static int log_n;

static void SetMode(int mode)
{
    g.mode = mode;
    Wr(0x09AA, 0x1000);
    Wr(0x09EC, mode == kMessage || mode == kQuestion ? 0x2000 : 0);
    Wr(0x065C, mode == kQuestion ? 0x0F00 : 0);
}
static void Frame(uint32_t pad)
{
    test_ram[0x36] = ++g.clock;
    SetMode(g.mode);
    uint32_t out = HoldAdvanceFilter(pad);
    uint16_t edge = (uint16_t)(out & ~g.prev & kAdv);
    g.prev = (uint16_t)out;
    if (log_n < (int)(sizeof log_out / sizeof *log_out)) log_out[log_n++] = out;
    if (!edge) return;
    if (g.mode == kMessage) pages++;
    else if (g.mode == kQuestion) answers++;
    else actions++;
}
static void Run(uint32_t pad, int frames) { while (frames-- > 0) Frame(pad); }
static State Save(void)
{
    State s = {g, IogHoldAdvanceStateSave(), IogHoldAdvanceHeldSave()};
    return s;
}
/* game_rtl.c: GameStateLoad restores the tail, then GameStateLoaded marks a
 * jump unless the load is a rollback. */
static void Load(const State *s, bool rollback)
{
    g = s->game;
    IogHoldAdvanceStateLoad(s->tail_latched, s->tail_held);
    if (!rollback) IogHoldAdvanceTimelineJump();
}
static void Begin(const char *name)
{
    current_case = name;
    memset(test_ram, 0, sizeof test_ram);
    memset(&g, 0, sizeof g);
    g.clock = 0x40;
    IogHoldAdvanceSet(2);                 /* normal: a 16-frame period */
    HoldAdvanceFilter(0);                 /* settle the filter */
    IogHoldAdvanceStateLoad(0, 0);
    pages = answers = actions = 0;
    log_n = 0;
}
static void Counts(void) { pages = answers = actions = 0; }

/* A state made in a mode with nothing held (prev = 0, empty tail). */
static State QuietState(int mode)
{
    Begin(current_case);
    SetMode(mode);
    Run(0, 8);
    return Save();
}

/* --- timeline jumps with a button held across them ----------------------- */

static void CaseJump(const char *name, int mode, uint32_t button)
{
    current_case = name;
    State s = QuietState(mode);
    Run(button, 5);                       /* already holding in the old timeline */
    Load(&s, false);
    Counts();
    Run(button, 120);                     /* still held: nothing may happen */
    printf("%s held-across: pages=%u answers=%u actions=%u\n", name, pages, answers, actions);
    CHECK(pages == 0 && answers == 0 && actions == 0);
    Run(0, 4);                            /* released */
    Counts();
    Run(button, 3); Run(0, 4);            /* one deliberate tap */
    printf("%s tap-after-release: pages=%u answers=%u actions=%u\n", name, pages, answers, actions);
    CHECK(pages + answers + actions == 1);
}

/* Rewind: back to a moment in the middle of held paging (the tail carries a
 * latched A and the down time). The hands are still on A. */
static void CaseRewind(void)
{
    Begin("rewind");
    SetMode(kMessage);
    Run(0, 4);
    Run(kPadA, 40);                       /* holding: first page by the edge, then paging */
    CHECK(pages >= 2);
    State mid = Save();
    Run(kPadA, 30);
    Load(&mid, false);                    /* the rewind panel's last load */
    Counts();
    Run(kPadA, 120);
    printf("rewind held-across: pages=%u\n", pages);
    CHECK(pages == 0);
    Run(0, 2); Counts();
    Run(kPadA, 40);                       /* pressed again: paging resumes */
    printf("rewind re-pressed: pages=%u\n", pages);
    CHECK(pages >= 2);
}

/* Reset: the console reset is a jump too (GameHardwareReset). */
static void CaseReset(void)
{
    Begin("reset");
    SetMode(kMessage);
    Run(kPadB, 10);
    g.prev = 0;                           /* the machine restarts */
    IogHoldAdvanceTimelineJump();
    Counts();
    Run(kPadB, 100);
    printf("reset held-across: pages=%u\n", pages);
    CHECK(pages == 0);
}

/* A held button that was latched by paging stays hidden in play, and the jump
 * mask must not hide anything that was not held at the jump. */
static void CaseOtherButtons(void)
{
    current_case = "other-buttons";
    State s = QuietState(kMessage);
    Run(kPadA, 3);
    Load(&s, false);
    Counts();
    Run(kPadA, 20);
    Run(kPadA | kPadB, 1); Run(kPadA, 3); /* B tapped while A is still held */
    printf("other-buttons tap B while A held: pages=%u\n", pages);
    CHECK(pages == 1);
}

/* --- behaviour that must not change ------------------------------------ */

static void CaseHeldPaging(void)
{
    Begin("held-paging");
    SetMode(kMessage);
    Run(0, 4);
    Run(kPadA, 16 * 5 + 2);
    printf("held-paging 82 frames: pages=%u\n", pages);
    CHECK(pages == 6);                    /* the press itself, then one per period */
    SetMode(kPlay);                       /* the message closes while A is held */
    Counts();
    Run(kPadA, 40);
    CHECK(actions == 0);                  /* the generated press stays with the paging */
    Run(0, 2); Run(kPadA, 2);
    CHECK(actions == 1);
}

static void CaseTaps(void)
{
    Begin("taps");
    SetMode(kMessage);
    for (int i = 0; i < 6; i++) { Run(kPadB, 6); Run(0, 10); }
    printf("taps 6x6 frames: pages=%u\n", pages);
    CHECK(pages == 6);
}

static void CaseQuestionHeld(void)
{
    Begin("question-held");
    SetMode(kMessage);
    Run(kPadA, 40);                       /* paging with A held ... */
    SetMode(kQuestion);                   /* ... into a question */
    Counts();
    Run(kPadA, 80);
    CHECK(answers == 0);
    Run(0, 2); Run(kPadA, 2);
    CHECK(answers == 1);
}

/* --- rollback (run-ahead, netplay) is exact ----------------------------- */

/* Run a pad script twice: once straight, once with a two-frame run-ahead that
 * speculates and rolls back every frame. The filter's outputs must match. */
static void RollbackScript(bool runahead, uint32_t *outs, int *n, const State *start, bool jump)
{
    static const struct { int frames; uint32_t pad; int mode; } script[] = {
        {6, kPadA, kMessage}, {40, kPadA, kMessage}, {3, 0, kMessage}, {50, kPadA, kMessage},
        {20, kPadA, kQuestion}, {4, 0, kQuestion}, {2, kPadA, kQuestion}, {30, kPadB, kPlay},
    };
    Load(start, !jump);
    log_n = 0;
    int k = 0;
    for (size_t i = 0; i < sizeof script / sizeof *script; i++)
        for (int f = 0; f < script[i].frames; f++) {
            g.mode = script[i].mode;
            const int before = log_n;
            Frame(script[i].pad);         /* the real frame */
            outs[k++] = log_out[before];
            if (runahead) {
                State snap = Save();
                Frame(script[i].pad); Frame(script[i].pad);
                Load(&snap, true);        /* rollback: no jump */
            }
            log_n = before + 1;
        }
    *n = k;
}
static void CaseRollback(const char *name, bool jump)
{
    current_case = name;
    static uint32_t a[512], b[512];
    int na = 0, nb = 0;
    State s = QuietState(kMessage);
    Run(kPadA, 4);                        /* held before the load */
    State held_now = Save();
    held_now.game = s.game;               /* ... into the quiet state */
    Begin(name);
    RollbackScript(false, a, &na, &held_now, jump);
    Begin(name);
    RollbackScript(true, b, &nb, &held_now, jump);
    int diff = 0;
    for (int i = 0; i < na && i < nb; i++) diff += a[i] != b[i];
    printf("%s straight vs run-ahead: frames=%d/%d differing=%d\n", name, na, nb, diff);
    CHECK(na == nb && diff == 0);
}

/* Run-ahead right after a jump: the speculative frames release the button,
 * and the rollback must put the jump mask back exactly. */
static void CaseRollbackAfterJump(void)
{
    current_case = "rollback-after-jump";
    State s = QuietState(kMessage);
    Run(kPadA, 4);
    Load(&s, false);
    Frame(kPadA);                         /* the jump is taken on this frame */
    State snap = Save();
    Frame(0); Frame(0);                   /* speculation: released */
    Load(&snap, true);
    Counts();
    Run(kPadA, 60);                       /* the real input: still held */
    printf("rollback-after-jump held: pages=%u\n", pages);
    CHECK(pages == 0);
}

/* --- the state tail ------------------------------------------------------ */

static void CaseTail(void)
{
    Begin("tail");
    /* Beta 19 tails: {latched, 0}; beta 20: {latched, held}. Both load, and a
     * latched button still behaves as a paging latch. */
    SetMode(kPlay);
    IogHoldAdvanceStateLoad(kPadA, 0);
    Counts(); Run(kPadA, 30); CHECK(actions == 0);
    Run(0, 1); Run(kPadA, 1); CHECK(actions == 1);
    IogHoldAdvanceStateLoad(kPadB, (uint16_t)(0x8000 | 0x40));
    Counts(); Run(kPadB, 30); CHECK(actions == 0);
    /* Anything a newer build adds must stay out of the bits an older build
     * reads: beta 20 loads latched & (A|B|Y) and the held word as is. */
    State s = QuietState(kMessage);
    Run(kPadA | kPadY, 3);
    Load(&s, false);
    Frame(kPadA | kPadY);                 /* jump mask now A|Y */
    const uint16_t w0 = IogHoldAdvanceStateSave(), w1 = IogHoldAdvanceHeldSave();
    printf("tail after a jump: latched-word=0x%04x held-word=0x%04x\n", w0, w1);
    CHECK((w0 & kAdv) == 0);              /* nothing latched by paging */
    CHECK(w1 == 0);                       /* nothing the filter counts as down */
    /* and the word round-trips: a rollback restores the jump mask */
    IogHoldAdvanceStateLoad(0, 0);
    IogHoldAdvanceStateLoad(w0, w1);
    Counts(); Run(kPadA | kPadY, 40); CHECK(pages == 0);
}

int main(int argc, char **argv)
{
    const char *only = argc > 1 ? argv[1] : NULL;
#define RUN(name, call) if (!only || !strcmp(only, name)) { call; }
    RUN("play", CaseJump("play", kPlay, kPadA));
    RUN("play-b", CaseJump("play-b", kPlay, kPadB));
    RUN("message", CaseJump("message", kMessage, kPadA));
    RUN("message-b", CaseJump("message-b", kMessage, kPadB));
    RUN("message-y", CaseJump("message-y", kMessage, kPadY));
    RUN("question", CaseJump("question", kQuestion, kPadA));
    RUN("rewind", CaseRewind());
    RUN("reset", CaseReset());
    RUN("other-buttons", CaseOtherButtons());
    RUN("held-paging", CaseHeldPaging());
    RUN("taps", CaseTaps());
    RUN("question-held", CaseQuestionHeld());
    RUN("rollback", CaseRollback("rollback", false));
    RUN("rollback-jump", CaseRollback("rollback-jump", true));
    RUN("rollback-after-jump", CaseRollbackAfterJump());
    RUN("tail", CaseTail());
    printf("%s %u assertions, %u failed\n", failures ? "FAIL" : "PASS", assertions, failures);
    return failures ? 1 : 0;
}
