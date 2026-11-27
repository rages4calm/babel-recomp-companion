/* ROM-free fixture: the runner's own input-binding parsers, as the Companion
 * launcher's Input editor writes their files.
 *
 * Built by scripts/test_input_bindings.py against the vendored
 * snesrecomp/runner/src/keybinds.c, desktop/mmx_config.c and util.c with SDL3,
 * so every name is resolved by the same SDL the game links.
 *
 *   test_input_bindings                      built-in cases (defaults, pad
 *                                            remaps, triggers, chords, seat 2,
 *                                            pad hotkey overrides)
 *   test_input_bindings --names <tsv>        every key name the launcher offers
 *   test_input_bindings --files <dir> <exp>  parse <dir>/config.ini and
 *                                            <dir>/keybinds.ini and compare with
 *                                            the expectations file <exp>
 */
#include "config.h"
#include "keybinds.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void Die(const char *error) {
  fprintf(stderr, "FAIL: Die(%s)\n", error ? error : "(null)");
  exit(1);
}

static int g_failures, g_checks;
#define CHECK(cond, ...)                                                  \
  do {                                                                    \
    g_checks++;                                                           \
    if (!(cond)) {                                                        \
      fprintf(stderr, "FAIL %s:%d: ", __FILE__, __LINE__);                \
      fprintf(stderr, __VA_ARGS__);                                       \
      fprintf(stderr, "\n");                                              \
      g_failures++;                                                       \
    }                                                                     \
  } while (0)

/* [GamepadMap] Controls order (kKeys_Controls + i). */
enum { cUp, cDown, cLeft, cRight, cSelect, cStart, cA, cB, cX, cY, cL, cR };
/* The host's HandleCommand remap: Controls index -> guest seat bit. */
static const unsigned char kKbdRemap[] = {4, 5, 6, 7, 2, 3, 8, 0, 9, 1, 10, 11};

/* The host's gamepad path (host_main.c HandleGamepadInput +
 * SetPadButtonOrFallthrough), on a synthetic pad: buttons are pressed in the
 * order given, each press resolving against the buttons already held, and the
 * guest word of `seat` is what the held commands produce. Returns the word;
 * *hotkey gets the first non-controller command a press resolved to. */
static unsigned PadWord(int seat, const int *buttons, int count, int *hotkey) {
  unsigned modifiers = 0, word = 0;
  *hotkey = 0;
  for (int i = 0; i < count; i++) {
    modifiers |= 1u << buttons[i];
    int cmd = FindCmdForGamepadButton(buttons[i] + seat * kGamepadBtn_Count, modifiers);
    if (!cmd) continue;
    if (ConfigSeatForControl(cmd) == seat) word |= 1u << kKbdRemap[(cmd - ConfigSeatControlsBase(seat)) % 12];
    else if (!*hotkey) *hotkey = cmd;
  }
  return word;
}

static char kPath[64];
static void Parse(const char *body) {
  FILE *f = fopen(kPath, "wb");
  if (!f) Die("cannot write fixture");
  fputs(body, f);
  fclose(f);
  memset(&g_config, 0, sizeof(g_config));
  ParseConfigFile(kPath);
}

/* ParseConfigFile only adds to the binding tables, so each case runs in a
 * process of its own (main re-runs this program with --case N). */
static void Case(int which) {
  int hk;
  snprintf(kPath, sizeof(kPath), "test_input_bindings_case%d.ini", which);
  if (which == 0) {
  /* Nothing set: today's mapping, position-faithful (south = SNES B). */
  Parse("[GamepadMap]\nEnableGamepad1 = true\n");
  CHECK(PadWord(0, (int[]){kGamepadBtn_A}, 1, &hk) == 1u << 0, "default south pad button is SNES B");
  CHECK(PadWord(0, (int[]){kGamepadBtn_B}, 1, &hk) == 1u << 8, "default east is SNES A");
  CHECK(PadWord(0, (int[]){kGamepadBtn_Y}, 1, &hk) == 1u << 9, "default north is SNES X");
  CHECK(PadWord(0, (int[]){kGamepadBtn_X}, 1, &hk) == 1u << 1, "default west is SNES Y");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L1}, 1, &hk) == 1u << 10, "default L1 is SNES L");
  CHECK(PadWord(0, (int[]){kGamepadBtn_Back}, 1, &hk) == 1u << 2, "default Back is Select");
  CHECK(PadWord(0, (int[]){kGamepadBtn_DpadLeft}, 1, &hk) == 1u << 6, "default d-pad left");
  CHECK(PadWord(1, (int[]){kGamepadBtn_Start}, 1, &hk) == 1u << 3, "player 2 default Start");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L2}, 1, &hk) == 0 && hk == 0, "L2 alone does nothing by default");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L2, kGamepadBtn_R3}, 2, &hk) == 0 && hk == kKeys_SettingsMenu,
        "built-in ZL+R3 opens settings");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L2, kGamepadBtn_R1}, 2, &hk) == 0 && hk == kKeys_Save,
        "built-in ZL+R quick save");

  } else if (which == 1) {
  /* Every SNES button remapped, triggers and a chord included, per seat. */
  Parse("[GamepadMap]\n"
        "Controls = DpadUp, DpadDown, DpadLeft, DpadRight, Back, Start, A, B, X, Y, L2, R2\n"
        "ControlsP2 = Y, A, X, B, L3, R3, DpadRight, DpadLeft, Lb, Rb, Start, L1+Back\n");
  CHECK(PadWord(0, (int[]){kGamepadBtn_A}, 1, &hk) == 1u << 8, "remapped south to SNES A");
  CHECK(PadWord(0, (int[]){kGamepadBtn_B}, 1, &hk) == 1u << 0, "remapped east to SNES B");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L2}, 1, &hk) == 1u << 10, "left trigger is SNES L");
  CHECK(PadWord(0, (int[]){kGamepadBtn_R2}, 1, &hk) == 1u << 11, "right trigger is SNES R");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L1}, 1, &hk) == 0, "old L1 binding released");
  CHECK(PadWord(1, (int[]){kGamepadBtn_Y}, 1, &hk) == 1u << 4, "player 2 north is Up");
  CHECK(PadWord(1, (int[]){kGamepadBtn_DpadRight}, 1, &hk) == 1u << 8, "player 2 d-pad right is A");
  CHECK(PadWord(1, (int[]){kGamepadBtn_L1, kGamepadBtn_Back}, 2, &hk) == ((1u << 9) | (1u << 11)),
        "player 2 L1 (X) held, then Back: the L1+Back chord adds SNES R");
  CHECK(PadWord(1, (int[]){kGamepadBtn_Back}, 1, &hk) == 0, "chord member alone is not R");
  CHECK(PadWord(0, (int[]){kGamepadBtn_Y}, 1, &hk) == 1u << 1, "player 1 unaffected by player 2's line");

  } else if (which == 2) {
  /* Pad hotkeys: a named one replaces its ZL default; an empty one clears it;
   * the rest keep theirs. */
  Parse("[GamepadMap]\nSettingsMenu = R3\nSaveStateMenu =\n");
  CHECK(PadWord(0, (int[]){kGamepadBtn_R3}, 1, &hk) == 0 && hk == kKeys_SettingsMenu, "R3 opens settings");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L2, kGamepadBtn_R3}, 2, &hk) == 0 && hk == kKeys_SettingsMenu,
        "ZL+R3 still resolves (R3 alone is a subset)");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L2, kGamepadBtn_Start}, 2, &hk) == 1u << 3 && hk == 0,
        "cleared SaveStateMenu: ZL+Start is plain Start");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L2, kGamepadBtn_Back}, 2, &hk) == 0 && hk == kKeys_Rewind,
        "untouched Rewind keeps ZL+Select");
  } else if (which == 3) {
  Parse("[GamepadMap]\nSettingsMenu = L2+Y\n");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L2, kGamepadBtn_R3}, 2, &hk) == 0 && hk == 0,
        "moved SettingsMenu no longer on ZL+R3");
  CHECK(PadWord(0, (int[]){kGamepadBtn_L2, kGamepadBtn_Y}, 2, &hk) == 0 && hk == kKeys_SettingsMenu,
        "SettingsMenu on ZL+North");

  } else if (which == 4) {
  /* Keyboard hotkeys: several keys for one command, slots, modifiers, None. */
  Parse("[KeyMap]\nPause = l, Pause\nLoad = F1,F2,F3,F4,F5,F6,F12,F8,F9,F10\nRewind = F7\n"
        "Turbo = None\nSettingsMenu = Ctrl+Escape\n");
  CHECK(FindCmdForSdlKey(SDLK_L, 0) == kKeys_Pause, "Pause on L");
  CHECK(FindCmdForSdlKey(SDLK_PAUSE, 0) == kKeys_Pause, "Pause also on the Pause key");
  CHECK(FindCmdForSdlKey(SDLK_F7, 0) == kKeys_Rewind, "Rewind took F7");
  CHECK(FindCmdForSdlKey(SDLK_F12, 0) == kKeys_Load + 6, "slot 7 moved to F12");
  CHECK(FindCmdForSdlKey(SDLK_TAB, 0) == 0, "Turbo cleared");
  CHECK(FindCmdForSdlKey(SDLK_ESCAPE, KMOD_CTRL) == kKeys_SettingsMenu, "Ctrl+Escape settings");
  CHECK(FindCmdForSdlKey(SDLK_ESCAPE, 0) != kKeys_SettingsMenu, "plain Escape freed");
  CHECK(FindCmdForSdlKey(SDLK_F1, KMOD_SHIFT) == kKeys_Save, "untouched Save keeps Shift+F1");
  char name[64];
  CHECK(!strcmp(ConfigCommandName(kKeys_Load + 6, name, sizeof(name)), "Load[6]"), "command name %s", name);
  CHECK(!strcmp(ConfigCommandName(kKeys_ControlsP2 + 11, name, sizeof(name)), "ControlsP2[11]"), "command name %s", name);
  }
  remove(kPath);
}
enum { kCaseCount = 5 };

/* Each TSV line: <scancode number> TAB <keybinds.ini name> TAB <[KeyMap] name or empty>. */
static void Names(const char *path) {
  FILE *f = fopen(path, "rb");
  if (!f) Die("cannot read names");
  char line[256];
  while (fgets(line, sizeof(line), f)) {
    line[strcspn(line, "\r\n")] = 0;
    char *a = strtok(line, "\t"), *b = strtok(NULL, "\t"), *c = strtok(NULL, "\t");
    if (!a || !b) continue;
    const int sc = atoi(a);
    CHECK((int)SDL_GetScancodeFromName(b) == sc, "keybinds name '%s' -> %d, want %d", b,
          (int)SDL_GetScancodeFromName(b), sc);
    CHECK(!strcmp(SDL_GetScancodeName((SDL_Scancode)sc), b), "SDL spells scancode %d '%s', launcher '%s'", sc,
          SDL_GetScancodeName((SDL_Scancode)sc), b);
    if (c && *c) {
      const SDL_Keycode key = SDL_GetKeyFromName(c);
      CHECK(key != SDLK_UNKNOWN, "[KeyMap] name '%s' unknown to SDL", c);
      CHECK((int)SDL_GetScancodeFromKey(key, NULL) == sc, "[KeyMap] name '%s' is scancode %d, want %d (US layout)", c,
            (int)SDL_GetScancodeFromKey(key, NULL), sc);
    }
  }
  fclose(f);
}

/* Expectations, one per line:
 *   key <player> <button> <SDL scancode name|None>        keybinds.ini
 *   hotkey <command name> <key> [Shift|Ctrl|Alt]          FindCmdForSdlKey
 *   pad <seat> <guest bit 0..11|-> <hotkey|-> <buttons...> synthetic pad
 *   source <seat> <0|1|2>                                 [Controller]
 */
static int ButtonId(const char *s) {
  static const char *const k[] = {"A", "B", "X", "Y", "Back", "Guide", "Start", "L3", "R3",
                                  "L1", "R1", "DpadUp", "DpadDown", "DpadLeft", "DpadRight", "L2", "R2"};
  for (int i = 0; i < (int)(sizeof(k) / sizeof(k[0])); i++) if (!strcmp(s, k[i])) return i;
  Die(s);
  return -1;
}
static int CommandId(const char *want) {
  char name[64];
  for (int cmd = 1; cmd < kKeys_Total; cmd++)
    if (!strcmp(ConfigCommandName(cmd, name, sizeof(name)), want)) return cmd;
  Die(want);
  return 0;
}
static void Files(const char *dir, const char *expect) {
  char path[1024];
  snprintf(path, sizeof(path), "%s/config.ini", dir);
  memset(&g_config, 0, sizeof(g_config));
  ParseConfigFile(path);
  snprintf(path, sizeof(path), "%s/babel-recomp.exe", dir);
  keybinds_init(path);   /* reads <dir>/keybinds.ini; never generates when present */
  FILE *f = fopen(expect, "rb");
  if (!f) Die("cannot read expectations");
  char line[512];
  while (fgets(line, sizeof(line), f)) {
    line[strcspn(line, "\r\n")] = 0;
    char *kind = strtok(line, " ");
    if (!kind || *kind == '#') continue;
    if (!strcmp(kind, "key")) {
      int player = atoi(strtok(NULL, " ")), button = -1;
      const char *bname = strtok(NULL, " "), *want = strtok(NULL, "");
      for (int b = 0; b < keybinds_button_count(); b++) if (!strcmp(keybinds_button_name(b), bname)) button = b;
      const SDL_Scancode sc = keybinds_get_button(player, button);
      const char *got = sc == SDL_SCANCODE_UNKNOWN ? "None" : SDL_GetScancodeName(sc);
      CHECK(button >= 0 && !strcmp(got, want), "keybinds player%d %s = '%s', want '%s'", player, bname, got, want);
    } else if (!strcmp(kind, "hotkey")) {
      const char *cmd = strtok(NULL, " "), *key = strtok(NULL, " "), *mod = strtok(NULL, " ");
      SDL_Keymod m = !mod ? 0 : !strcmp(mod, "Shift") ? KMOD_SHIFT : !strcmp(mod, "Ctrl") ? KMOD_CTRL : KMOD_ALT;
      const int got = FindCmdForSdlKey(SDL_GetKeyFromName(key), m);
      char name[64];
      CHECK(got == CommandId(cmd), "hotkey %s%s%s resolves to %s, want %s", mod ? mod : "", mod ? "+" : "", key,
            ConfigCommandName(got, name, sizeof(name)), cmd);
    } else if (!strcmp(kind, "pad")) {
      int seat = atoi(strtok(NULL, " "));
      const char *bit = strtok(NULL, " "), *hot = strtok(NULL, " ");
      int buttons[8], n = 0, hk;
      for (char *b; n < 8 && (b = strtok(NULL, " ")) != NULL;) buttons[n++] = ButtonId(b);
      const unsigned word = PadWord(seat, buttons, n, &hk);
      const unsigned want = !strcmp(bit, "-") ? 0 : 1u << atoi(bit);
      const int want_hk = !strcmp(hot, "-") ? 0 : CommandId(hot);
      CHECK(word == want && hk == want_hk, "pad seat %d %s: guest 0x%03x hotkey %d, want 0x%03x %d", seat,
            n ? "" : "(none)", word, hk, want, want_hk);
    } else if (!strcmp(kind, "source")) {
      int seat = atoi(strtok(NULL, " ")), want = atoi(strtok(NULL, " "));
      CHECK(g_config.player_src[seat] == want, "SourceP%d = %d, want %d", seat + 1, g_config.player_src[seat], want);
    }
  }
  fclose(f);
}

int main(int argc, char **argv) {
  if (argc == 3 && !strcmp(argv[1], "--names")) Names(argv[2]);
  else if (argc == 4 && !strcmp(argv[1], "--files")) Files(argv[2], argv[3]);
  else if (argc == 3 && !strcmp(argv[1], "--case")) Case(atoi(argv[2]));
  else {
    for (int i = 0; i < kCaseCount; i++) {
      char cmd[1200];
      snprintf(cmd, sizeof(cmd), "\"\"%s\" --case %d\"", argv[0], i);
      g_checks++;
      if (system(cmd) != 0) { fprintf(stderr, "FAIL: case %d\n", i); g_failures++; }
    }
  }
  printf("{\"passed\": %s, \"checks\": %d, \"failures\": %d}\n", g_failures ? "false" : "true", g_checks, g_failures);
  return g_failures ? 1 : 0;
}
