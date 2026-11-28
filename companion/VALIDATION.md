# Launcher batch 001 — 2026-11-02

- Windows .NET Release build: passed, no warnings/errors.
- Locked restore: Core and Windows CompanionLauncher 0.2.0 package hashes verified.
- Adapter fixtures: 30 checks passed using disposable synthetic configs and files,
  including rejection of partial first-run config creation, shared Mode 7 controls
  preserving quality/legacy settings, and Adaptive/legacy VSync parsing.
- Read-only local owner-ROM option: 5 additional checks passed (35 total), covering
  supported USA digest, header normalization and structured direct/Babel launch plans.
- Shared shell smoke: five pages rendered at 1120×800 client size and visually
  reviewed. Draft edits survive navigation, unapplied edits disable Play, and Revert
  restores saved options. Only one profile exists, so profile-switch testing is skipped.
- Actual adapter launch: passed against a copy of the locally built interpreter-only
  engine in a fresh scratch folder. The real launch plan ran 60 frames with dummy
  SDL video/audio, captured `frame.ppm` and exited successfully at the frame cap.
  Original engine and owner-ROM hashes remained unchanged. This checks process
  handoff and bounded boot only; the graphical launcher was not used to click Play.
  The probe now records nonblack pixel count separately; a captured black frame
  does not qualify visible output. The original receipt predates this extra field.
- No controller hardware, audible output, in-game Apply, save loading, natural
  progression, alternate modes or other platforms are qualified by these checks.

Private smoke images and the shared-shell receipt are retained in the current bounded
scratch batch at `.local/batch-001/launcher-smoke/`; no gameplay images are committed.
The graphics-parity five-page smoke is in `.local/batch-001/launcher-parity-smoke/`.
The real adapter/engine receipt is in `.local/batch-001/launcher-engine-smoke/`.
Native/runtime baseline qualification is recorded separately in the project handoff.

# Launcher window tests — 2026-11-27

`tests/ui/Gaia.Companion.UiTests.csproj` (not part of `build.ps1 -Test`: every mode opens
real windows, so run it on a hidden desktop, e.g. through
`.local/batch-001/visual-fullgame-041/hidden_run.py` with its own desktop name; on a desktop
shared with game runs, their windows take the posted clicks):

- `--pad <folder with config.ini and keybinds.ini>`: mock XInput source (`XInputPad.Source`)
  — 97 checks: every XInput button, both triggers at the 37% threshold, every LT chord, a
  button held when capture opens, the second slot, Esc/Delete/B, keys by scan code, the
  10-second capture timeout, then the whole Controls window (Swap/Replace/Cancel conflicts,
  presets, devices, live tester, controller page/edit/clear navigation, Save read back).
- `--dpi <babel-recomp.exe> <out>`: the Controls window and its dialogs at 96/144/192 DPI by
  WM_GETDPISCALEDSIZE + WM_DPICHANGED, the method of dotnet/winforms' own DPI tests
  (`DpiMessageHelper`); fonts, clipping, overlap and the screen's working area are checked.
  The window's real DPI stays the monitor's (96 here): no per-monitor DPI hardware was used.
- `--click <installed launcher.exe> <rom> <report.json>`: UI Automation click-through of the
  real launcher process with `COMPANION_DATA_ROOT` and `GAIA_UPDATE_FEED` pointing at scratch
  data. Buttons that open a modal window are clicked with posted mouse messages: a UIA Invoke
  runs the handler inside an input-synchronous COM call and every later UIA call times out.

Physical controller (needs a person, about two minutes): plug in an Xbox-compatible pad,
open Controls, press each face button, both bumpers, both triggers, Start, View, both stick
clicks and the d-pad on the "Try it" pad (each lights its SNES button); click Player 1's A
controller cell and press RB (captures "RB"), then hold LT and press A (captures "LT + A");
press B in a key capture (cancels); RB/LB switch pages; Close without saving.

# Controller rumble — 2026-11-27

Automated: `scripts/test_rumble.py` compiles the real `src/iog_rumble.c` with stubbed host
and SDL calls (hit scaled by damage, HP gain, load/rewind/reset, run-ahead rollback, death,
Off/Low/Normal/Strong, keyboard play, no pad, two pads, quake sound, the log writer); the
launcher's `--mods-tests` round-trip the Off/Low/Normal/Strong choice. A Great Wall fight
in the harness logs every request (`IOG_RUMBLE_LOG`) identically native, interpreter and
native with run-ahead 2, and a Mummy Queen fight logs 57 hits and 27 quake-sound shake
pulses identically native and interpreter. With `IOG_RUMBLE_LOG` set the game only logs and
never calls the controller, and harness runs hide every pad from SDL.

Physical controller (needs a person, about one minute, any rumble pad as player 1, HP
Refill off): in a room with enemies, take a small hit (one short buzz) and a big one (a
stronger, longer buzz); a herb gives none; walk into a lethal hit (one long rumble, nothing
more through the game-over fade); in the in-game settings set CONTROLLER RUMBLE to LOW,
then STRONG (the same hit feels weaker / stronger), then OFF (nothing at all); load a save
state with less HP and rewind (no buzz); Freedan's Earthquaker landing or the Mummy Queen's
roar gives a light rumble while the ground shakes; switch Player 1 to keyboard in the
launcher (no rumble). Report any buzz that comes late, twice, or with no hit.

# Game language (Spanish, French, German) — 2026-11-27

Launcher: **Language** in the left column opens the Language tab of Cheats and Mods
(`LanguageRoms.cs`, `CheatsModsForm.cs`). The ROM is identified by the game's own test
(`IogTextRomLanguage`: copier header skipped, title `ILLUSION OF TIME ` + SPN/FRA/GRM at
$FFC0); only the header is read and only the path is stored, as the iog.languages package
reads it (feature `language`, value `code`, `[[resource]]` `rom_es`/`rom_fr`/`rom_de`).

Automated: `build.ps1 -Test` runs `--language-tests` (38 checks on synthetic 64 KiB files
with only a title: each release, copier header, USA/Italian/other/misplaced/tiny/text
files refused, refusal writes nothing, game quoting without `\u` escapes for paths with an
apostrophe and a plus, switching, English drops a European `language.txt`, a moved ROM,
`languages/` one folder deep, a game-written selection updated in place).
`tests/ui --language <fresh folder>` drives the tab (9 checks; with `GAIA_UI_SHOW=1` only
on a hidden desktop, it also draws the tab to `language-tab.png`). A game run with the
launcher-written state found the synthetic Spanish header (`[i18n] language available: es`)
and its settings row read ENGLISH; without a European ROM the row reads
ENGLISH (ADD ROM IN LAUNCHER).

Not tested: playing in a European language from a real Illusion of Time ROM through the
launcher (no European ROM on the test machine). Owner check, about two minutes: Language →
Choose Illusion of Time ROM… → your ROM (the status names its language) → choose it →
Apply changes → Play; the title screen and first dialogue are in that language; Ctrl+L
cycles languages; back in the launcher choose English and Apply, and the game starts in
English.
