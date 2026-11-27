/* SPDX-License-Identifier: MIT */
/* The game's audit glue (audit.c) with the real observer and progress store,
 * against stubbed game memory (tests/stubs). Checks the status text the
 * achievements browser shows for every unavailable or error state, and that
 * recovery from a refused observation rebaselines without awarding anything. */
#include "audit.h"
#include "snes/snes.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <direct.h>
#include <process.h>
#include <windows.h>
#define getpid _getpid
static void nap(void) { Sleep(10); }
#else
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
static void nap(void) { struct timespec t = {0, 10000000}; nanosleep(&t, NULL); }
#endif

#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); exit(1); } } while (0)
static unsigned checks;

Snes *g_snes;
static uint8_t ram[0x20000], rom[0x200000];
static Cart cart = {rom, sizeof rom, CART_HIROM, sizeof rom};
static Snes snes = {&cart, ram};
static bool cheats, randomizer, apocalypse, path_fails;
static char profile[1024];

bool RtlSpeculativeFrame(void) { return false; }
bool IogCheatsSessionTainted(void) { return cheats; }
bool IogRandomizerActive(void) { return randomizer; }
int snes_mod_runtime_feature_enabled_c(const char *package, const char *feature)
{ (void)package; (void)feature; return apocalypse ? 1 : 0; }
void sha256_compute(const uint8_t *data, size_t len, uint8_t out[32])
{ (void)data; (void)len; memset(out, 0, 32); }
int snesrecomp_exe_dir_path(const char *leaf, char *out, size_t max)
{
    (void)leaf;
    if (path_fails) return 0;
    return snprintf(out, max, "%s", profile) < (int)max;
}

static ca_state states[CA_MAX_ACHIEVEMENTS];
static unsigned frame;
static const char *Status(void)
{
    uint64_t notices;
    const char *text = IogAchievementAuditSnapshot(states, &notices);
    /* The browser's status line holds 40 columns in a 4:3 picture. */
    CHECK(text && strlen(text) <= 40);
    return text;
}
/* One emulated frame, then the status (the store answers on its own thread). */
static const char *Step(void) { IogAchievementAuditFrame(++frame); return Status(); }
static bool Await(const char *expected)
{
    for (int i = 0; i < 500; ++i) {
        if (!strcmp(Status(), expected)) return true;
        nap();
    }
    fprintf(stderr, "status is \"%s\", expected \"%s\"\n", Status(), expected);
    return false;
}
static unsigned Unlocked(void)
{
    unsigned n = 0;
    Status();
    for (unsigned i = 0; i < CA_MAX_ACHIEVEMENTS; ++i) n += states[i].unlocked_at != 0;
    return n;
}
static bool AwaitUnlocked(unsigned n)
{
    for (int i = 0; i < 500 && Unlocked() != n; ++i) nap();
    return Unlocked() == n;
}
static void Settle(void) { for (int i = 0; i < 20; ++i) nap(); }
static void Session(const char *directory)
{
    IogAchievementAuditShutdown();
    snprintf(profile, sizeof profile, "%s", directory);
    memset(ram, 0, sizeof ram);
    ram[0x0644] = 8;
    IogAchievementAuditBind();
}
static void Write(const char *path, const char *text)
{
    FILE *f = fopen(path, "wb");
    CHECK(f && fputs(text, f) >= 0 && !fclose(f));
}
static char *Read(const char *path)
{
    static char buffer[8192];
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    size_t n = fread(buffer, 1, sizeof buffer - 1, f);
    fclose(f);
    buffer[n] = 0;
    return buffer;
}

int main(void)
{
    static const char *const owned[] = {"IOG_ACHIEVEMENT_AUDIT", "IOG_ACHIEVEMENT_PROGRESS",
        "SNESRECOMP_RUN_FRAMES", "SNESRECOMP_CAPTURE_OUT"};
    for (size_t i = 0; i < sizeof owned / sizeof *owned; ++i) CHECK(!getenv(owned[i]));
    /* Developer test options exist only in IOG_ACHIEVEMENT_TEST_INPUT builds. */
#ifdef _WIN32
    CHECK(!_putenv("IOG_ACHIEVEMENT_TEST_REFUSE_BROWSER=1"));
#else
    CHECK(!setenv("IOG_ACHIEVEMENT_TEST_REFUSE_BROWSER", "1", 1));
#endif
#ifdef IOG_ACHIEVEMENT_TEST_INPUT
    CHECK(IogAchievementAuditTestOption("IOG_ACHIEVEMENT_TEST_REFUSE_BROWSER"));
#else
    CHECK(!IogAchievementAuditTestOption("IOG_ACHIEVEMENT_TEST_REFUSE_BROWSER"));
#endif
    char base[512], dir[600], file[700];
    snprintf(base, sizeof base, "test-audit-%d", (int)getpid());
    char *argv[] = {"game", NULL};
    IogAchievementAuditStart(1, argv);
    g_snes = &snes;

    /* Before a verified ROM, and at the title screen. */
    CHECK(!strcmp(Status(), "Progress unavailable"));
    snprintf(dir, sizeof dir, "%s/ok", base);
    Session(dir);
    CHECK(!strcmp(Status(), "Starts when a game is loaded"));
    CHECK(!strcmp(Step(), "Starts when a game is loaded"));
    ram[0x09AA] = 1;
    ram[0x0B56] = 3;
    Step();
    CHECK(Await("Local progress"));
    ram[0x0B56] = 4;
    Step();
    CHECK(AwaitUnlocked(1) && states[1].unlocked_at);

    /* More than 50 jewels: said at once, nothing recorded while it lasts. */
    ram[0x0B56] = 51;
    CHECK(!strcmp(Step(), "Paused: save shows over 50 Red Jewels"));
    ram[0x0B56] = 52;
    ram[0x0A61] = 1;
    CHECK(!strcmp(Step(), "Paused: save shows over 50 Red Jewels"));
    Settle();
    CHECK(Unlocked() == 1);
    /* Recovery: the current valid values become the baseline, silently. */
    ram[0x0B56] = 49;
    CHECK(!strcmp(Step(), "Local progress"));
    Step(); Step();
    Settle();
    CHECK(Unlocked() == 1);
    ram[0x0B56] = 50;   /* a real pickup after recovery counts */
    Step();
    CHECK(AwaitUnlocked(4));
    CHECK(!states[0].unlocked_at);   /* the room seen while paused is not awarded */

    /* Invalid BCD in $0AB0, then recovery. */
    ram[0x0B56] = 10;
    Step();
    CHECK(!strcmp(Status(), "Local progress"));
    ram[0x0AB0] = 0x0A;
    CHECK(!strcmp(Step(), "Paused: Red Jewel count unreadable"));
    ram[0x0AB0] = 0x6F;
    CHECK(!strcmp(Step(), "Paused: Red Jewel count unreadable"));
    ram[0x0AB0] = 0x20;   /* 20 given + 10 carried: rebaseline at 30 */
    CHECK(!strcmp(Step(), "Local progress"));
    Settle();
    CHECK(Unlocked() == 4 && !states[0].unlocked_at);

    /* Session and save conditions name themselves, and clear again. */
    cheats = true;
    CHECK(!strcmp(Step(), "Not recorded: cheats used this session"));
    cheats = false;
    ram[0x0B54] = 1;
    CHECK(!strcmp(Step(), "Not recorded in New Game+"));
    ram[0x0B54] = 0;
    randomizer = true;
    CHECK(!strcmp(Step(), "Not recorded with the Randomizer"));
    randomizer = false;
    apocalypse = true;
    CHECK(!strcmp(Step(), "Not recorded with Apocalypse Gaia"));
    apocalypse = false;
    CHECK(!strcmp(Step(), "Local progress"));
    /* A refusal under a condition reappears once the condition clears. */
    ram[0x0B56] = 60;
    cheats = true;
    CHECK(!strcmp(Step(), "Not recorded: cheats used this session"));
    cheats = false;
    CHECK(!strcmp(Step(), "Paused: save shows over 50 Red Jewels"));
    ram[0x0B56] = 10;
    CHECK(!strcmp(Step(), "Local progress"));
    IogAchievementAuditShutdown();
    snprintf(file, sizeof file, "%s/progress.json", dir);
    const char *json = Read(file);
    CHECK(json && strstr(json, "\"gaia.fifty-jewels\",\"progress\":50,\"unlockedAt\":") &&
          strstr(json, "{\"id\":\"gaia.first-room\",\"progress\":0,\"unlockedAt\":0}"));

    /* Corrupt progress.json: the storage reason wins over a jewel problem,
     * and the file is left as it was. */
    snprintf(dir, sizeof dir, "%s/corrupt", base);
    Session(dir);
#ifdef _WIN32
    _mkdir(dir);
#else
    mkdir(dir, 0700);
#endif
    snprintf(file, sizeof file, "%s/progress.json", dir);
    Write(file, "{\"schemaVersion\":1,");
    ram[0x09AA] = 1;
    Step();
    CHECK(Await("Profile could not be read"));
    ram[0x0B56] = 51;
    CHECK(!strcmp(Step(), "Profile could not be read"));
    ram[0x0B56] = 5;
    CHECK(!strcmp(Step(), "Profile could not be read"));
    ram[0x0B56] = 6;
    CHECK(!strcmp(Step(), "Profile could not be read"));
    IogAchievementAuditShutdown();
    CHECK(!strcmp(Read(file), "{\"schemaVersion\":1,"));

    /* Unwritable profile: its folder's parent is a file. */
    snprintf(file, sizeof file, "%s/blocker", base);
    Write(file, "x");
    snprintf(dir, sizeof dir, "%s/blocker/profile", base);
    Session(dir);
    ram[0x09AA] = 1;
    Step();
    CHECK(Await("Unable to save progress"));
    ram[0x0B56] = 1;
    CHECK(!strcmp(Step(), "Unable to save progress"));

    /* Profile open in another game window. */
    snprintf(dir, sizeof dir, "%s/ok", base);
    IogAchievementStore *other = IogAchievementStoreOpen(dir);
    CHECK(other);
    Settle();
    Session(dir);
    ram[0x09AA] = 1;
    Step();
    CHECK(Await("Profile open in another game window"));
    IogAchievementAuditShutdown();
    IogAchievementStoreClose(other);

    /* No folder for the profile at all. */
    path_fails = true;
    Session(dir);
    ram[0x09AA] = 1;
    CHECK(!strcmp(Step(), "Progress folder unavailable"));
    path_fails = false;

    /* An unverified ROM. */
    Session(dir);
    cart.type = 1;
    IogAchievementAuditBind();
    CHECK(!strcmp(Step(), "Not recorded: ROM not verified"));
    cart.type = CART_HIROM;

    static const char *const leftovers[] = {"ok/progress.json", "ok/progress.lock",
        "corrupt/progress.json", "corrupt/progress.lock", "blocker", "ok", "corrupt", ""};
    for (size_t i = 0; i < sizeof leftovers / sizeof *leftovers; ++i) {
        snprintf(file, sizeof file, "%s/%s", base, leftovers[i]);
        if (remove(file)) {
#ifdef _WIN32
            CHECK(!_rmdir(file));
#else
            CHECK(!rmdir(file));
#endif
        }
    }
    printf("PASS %u checks: audit status text for refused observations, recovery and storage failures\n", checks);
    return 0;
}
