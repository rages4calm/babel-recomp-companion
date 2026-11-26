# Open work

What is still to do, and what was not fixed or not tested, as of November 25,
2026 (tester build `v0.2.0-beta.6`). Read `HANDOFF.md` for
how things are built and where the evidence lives; this file is only the list.

Each item says what is known, not what is assumed. "Not tested" means nobody
and no tool has looked. "Not played" means automated replays ran but no person
played it.

## Owner playtest of beta 2 (November 26)

The owner played from the start to Freejia on the interpreter build. His save
states are in `.local/batch-001/owner-playtest-1/saves` (`save0.sav` is his
"slot 1", and so on; `save.srm` is the battery save). Fixed in beta 4 and seen
fixed in pictures by the agents (evidence in
`visual-fullgame-041/playtest1-render` and `playtest1-ui`): the castle sky
and red streak, the basement floor, the gold ship, the clubhouse bottom strip,
castle stair pans, the battery save lost after a state load and Reset, Reset
itself, confirmations for load and save state, SNES button prompts in the
settings footer and save browser, the achievement toast behind the status
display, the classroom area map, and the launcher's "settings changed"
refusal. None of it has been replayed by the owner yet. What is left:

- **Psycho Dash drop to 4:3:** not reproduced; the pickup would not start in
  five staged attempts. A related change keeps the Dark Space star ring on
  frames with no HDMA; whether that was his drop is unknown.
- **Stairs in South Cape houses:** the pan fix was seen in the castle only;
  the house stair could not be triggered by placing the player.
- **Inca room (slot 4):** one pixel row of green remains at the bottom left;
  it is in the original field too.
- **Basement floor:** a 2-pixel lag remains while the camera moves, inside
  the original field as this runner draws it. Not compared with hardware.
- **The bottom-row rule changes the framing of nearly every room.** The
  survey compares presentation reasons, not pictures, so earlier approvals of
  bottom edges need a second look. The scene-specific bottom cuts in
  `RoomPictureBounds` are now special cases of it and could go.
- **Gold ship at night:** only reached by a late warp that was too dark to
  judge.
- **Auto prompts cannot detect his 8BitDo:** in X-input mode it identifies as
  an Xbox 360 controller. He has to choose SNES by hand.
- **Not looked at after the prompt change:** achievement footer, walkable
  world prompt, rewind strip. With Xbox style the settings footer now reads
  (B) SELECT / (A) BACK, which is true to the default mapping.
- **The pending-save flush before a state load** is not exercised by any
  test; an in-game save could not be driven in the harness.
- **Reset now boots through the reset vector**, which also changes the
  end-of-game return to title (`iog_ngplus.c`). Not tested.
- **No setting turns the confirmations off.**
- **Toast text is cut short** ("A LITTLE STRO...").
- Seen in his files, not investigated: `radar = "off"` in his mod state;
  `SourceP1 = 1` (keyboard) in his config although the pad plays; d-pad Up on
  the settings menu's top row does not wrap.

## Companion redesign (done November 26, not played)

The paused Companion menu is gone. Start opens the area map wherever the area
has one (in towns too, where the game itself only pauses) and the map's Back
returns to the game. Achievements open from an **Achievements** row in the
in-game settings and Back returns there; **I** / **LT+L3** open them directly.
Save and load state keep their own keys (Shift+F1-F10 / F1-F10, LT+R / LT+L
for slot 1, F11 / LT+Start for the browser). Seen in pictures in Freejia
(`visual-fullgame-041/playtest1-ui/ui-rd3`, `ui-rd4`). Not checked:

- **Not played by the owner.**
- **Start no longer shows the game's PAUSE in towns** that have a map. Where
  there is no map, and on the world map, Start is unchanged. Whether Start
  can now open the map at a moment the game would have refused it (mid
  cutscene) was not hunted for; the map freezes the game and changes nothing.
- **The "Achievements unavailable" notice** (browser failed to open) was not
  seen; the browser opened every time.
- **Achievements from the settings on the title screen** (not in play) were
  not run.
- **Pointer and touch** on the map and achievements after the change: not run.
- **The Dual / Flip Grip second screen** still has its five pages and was not
  rerun after the code around it was cut.
- **Spanish strings** for the removed pages are still in `iog_companion.c`'s
  table; harmless.

## Status display at the screen edges (done November 26, not played)

An option, off by default: `iog.graphics/edge_hud`, the **Status display** row
in the in-game settings (wide view only) and a toggle under Cheats and Mods in
the launcher. It moves the game's own pixels and redraws nothing: PLAYER, the
player's life and the left bracket go to the left edge of the room picture,
ENEMY, its life and the right bracket to the right edge, the DP ornament stays
in the centre, dialogue stays centred. The cuts are at the gaps in the art
(`HudPart` in `src/iog_world_renderer.c`). In a room with black sides the
groups sit at the room picture's edges. Seen in pictures in the Inca room,
Edward's Castle, the lookout and the gold ship
(`visual-fullgame-041/playtest1-ui/hud-check2.png`). Not checked:

- **Not played by the owner.**
- **Enemy life was never on screen** in a checked picture. Its columns
  (x 160 to 239) are taken from the status tilemap's layout, not seen.
- **Scenes at the original width** (fixed plates, Mode 7, fallbacks) keep the
  one-block display, because it is baked into their picture.
- **Whether the groups move** while the camera scrolls past a map edge, during
  screen shake or during fades: not looked at.
- **The software path** (`CompositeHud`, presenters without the frame layer)
  uses the same layout and was not run.
- **The achievement toast** clears the layer under it by rectangle; not rerun
  with the wide layer.
- Two smaller ideas were not built: hide the ENEMY label while there is no
  enemy, and a faint shadow behind the display over bright scenes.

## Decided, not built

- **Native coverage.** The interpreter rise after the SDK update is explained
  and fixed (November 26). The analyzer of SNESRecomp `627b2f27` rejects a
  return that follows a pull whose push is in an earlier fragment of the same
  routine, so four sprite helpers lost their return proof and all 33 routines
  calling them, the per-frame sprite composer `83C714` included, were cut at
  the call and left to the interpreter bridge. Four `exit_mx_variant` lines in
  `recomp/bank03.cfg` declare the widths the older analyzer had proven. The
  regenerated graph (`.local/batch-001/sdk-update/graph`; the one before is
  `graph-pre-declare`) has 1,262 AOT-eligible variants (1,229 after the
  update, 1,248 before it). Same source, old graph against new, over the
  198-scene survey: every renderer log identical, interpreted instructions
  1,779,645 down to 598,348; scene `3E` 6,207 down to 31. Still open:
  The 142 route replays are also identical between the two graphs, with the
  same total CPU cycles.
- **Native steps extended (November 26).** The interpreter's residual was
  profiled with `SNESRECOMP_INTERP_RESIDUAL=<file>` (new, in the runner's
  `interp_bridge.c`; one line per instruction the interpreter itself ran:
  `PC e m x frame`) over the 198 scenes and the 142 routes. It was almost all
  enemy, script and credits code never selected for native steps.
  `sdk-update/extend.py` appended 8,494 contexts the effect generator
  supports to the 35,098 already selected (`sdk-update/ext3/contexts.json`,
  effects in `sdk-update/ext3/effects`; the native build directory now uses
  them). Against the build before it, all 198 scenes and all 142 routes have
  identical renderer logs and the routes the same total CPU cycles.
  Interpreted instructions: survey 598,348 down to 17,063; routes 18,187,963
  down to 221,564 (845,414 cycles of 10.1 billion, 0.008 percent). On the
  morning's build the same two totals were 1,779,645 and 21,656,871.
  Still open:
  - **The new contexts skipped the older process's extra checks:** no
    independent RomAtlas decode and no per-case witness, only the generator's
    own policy and the identical replays.
  - **What is left:** about 191,000 instructions at registered sites that
    decline at run time (cause not captured), about 30,000 that touch bytes
    the game patches while running, and a few stack-pointer and reset
    operations. `sdk-routes/residual-routes-ext3.json` has the list.
  - **Not played by a person** on the extended build, and no speed
    measurement was taken.
  - **The four declarations are assertions.** They rest on the older
    analyzer's proof and on the identical survey and routes.
  - **Reported upstream** as RetroPortingToolKit/snesrecomp#323 with a
    game-free test. No reply yet; a PR was offered, not sent.
  - The public download is interpreter-only and is not affected either way.

## The tester build (`v0.2.0-beta.6`)

- **Not played by a person.** It was checked from a clean unzipped folder
  with no developer variables: a room, the walkable world map and a cold boot
  to the prologue. Nothing else.
- **The launcher was not clicked through.** It starts and its adapter tests
  pass (57 + 47 + 9 + 26 checks). No page was opened by hand, including the
  new Wide view toggle under Cheats and Mods.
- **Achievement unlocking was not seen end to end.** Recording is now on by
  default and the module tests pass (observer 100 checks, progress store).
  The store only opens once play begins, and every way of driving input
  automatically also switches recording off by design, so no unlock, toast or
  saved `progress.json` has been observed in a real session.
- **Interpreter only.** The download has no ROM-derived native code, so
  testers run the slower path. The 198-scene survey and the route replays
  were run on the native build, not on the interpreter build.
- **Wide view off was not tested** on the public build (the setting
  `iog.graphics/wide_view` disabled). The setting needs a restart and has no
  in-game row yet.
- **"Babel 16:9 widescreen"** in the launcher does nothing while the wide view
  is on. It should be hidden or explained.
- **Windows x64 only.** The tag also started the workflow builds for Linux,
  macOS, Android, 3DS and Vita; their results were not looked at and nothing
  from them was published.
- **GaiaLabs has not been told** that the dialogue pack and map data ship in a
  public build. They are generated from the public GPL-3.0 repository and
  carry the notice and license; telling them is a courtesy the owner may want
  to do himself.
- **`docs/ROMATLAS-PLAN.md`** contains a local user path. It is already
  public in the repository and no longer ships in the zip.

## Cheats and conveniences

All eleven launcher options were run in the game on and off, against their
help text (evidence in `visual-fullgame-041/cheatcheck`). Nine work as
described. Two faults were fixed afterwards and not rerun: the run button's L
and R choices never ran (they are the game's guard) and were removed; the
game now caps minimum stats, max HP and DP itself instead of trusting the
launcher. Still open or untested:

- **Hold to advance with nothing equipped:** holding the item button keeps
  dismissing and reopening "You're not equipped." Not fixed.
- **Hold to advance** when a question arrives during held paging: not covered.
- **Room rewards** on boss clears, and the New Game+, randomizer and
  Apocalypse blocks: not run. The tested clears had the enemy counter set to 1
  before a real kill.
- **Stacking** for jewels handed to Gem and crystals in use: only herbs were
  consumed for real.
- **Enhanced world map:** "control sooner after leaving a town" not measured.
- **Quick item selection** with a menu open, past the ends of the list, and
  the Y and Select modifier choices: not run.
- **Changing cheats from the in-game settings** during play, and "switching
  off does not lower stats": not run.
- **Wide view off with `Widescreen = 0`** in the config: not run.
- **Launcher Input page:** Button prompts round-trips in tests and the page
  was rendered and looked at; it was not clicked by hand.

## Widescreen and renderer

- **Dark Gaia's defeat white-out:** for about 74 frames the player sprite is
  olive in the wide picture and blue in the original. Not fixed.
- **Vampires' circle window:** it uses the same code as the Dark Gaia entrance
  fix (`RebaseFieldWindows`) but was never seen, because the kill could not be
  staged.
- **Not staged at all:** the kills of Castoth and Sand Fanger; the pause
  menu's status page; state loads in the mosaic-revealed rooms other than
  Luke's house (`5A`, `7D`, the Gem rooms), which the fix covers by inference.
- **Diamond Mine:** a line at world x of about 438. Open.
- **Walkable world map with Enhanced off:** streaks in the picture. Open.
- **Euro arrival:** black corners. Open.
- **Prison entry** is still a fallback to the original picture in the audit.
- **Single lit fallback frames** once reported in scenes `58`, `06`, `68` and
  `FE` did not reproduce in the 413,000-frame census. Not explained.
- **Walkable world map on the GPU path has no before/after pixel comparison.**
  The older test builds never used that path; the new picture was checked by
  eye only.
- **Not checked by a person:** the GPU presentation in general, the OpenGL ES
  path, and the Dual and Flip Grip layouts.
- **Other Mode 7 scenes** still use the software plane; only the walkable map
  ground is on the runner's GPU path.
- **Narrow rooms** keep black sides. This is the owner's decision, not a gap.
- **Scenes that stay at the original width by design** (logos, title, file
  select, inventory, statue ceremony, ending, credits, and `2A E4 E5 E7 E8 F0
  DC`) have no art beyond the edges. Leave them unless new art exists.
- **Console CPU cost** (span planning, render workers) has not been started.
  Measured on PC only: about 3 ms a frame original, 5 to 6 ms wide, 7 to 9 ms
  on the world map.

## Retranslation

- **1,098 of 1,133 rows use the authored layout.** The other 35 use the older
  reflowed layout.
- **About 166 strings have no GaiaLabs text** and stay in the original
  English. The owner decided to leave them; do not write replacements.
- **Round 3 of the scene sweep saw 364 of 772 authored rows in their scenes.**
  The remaining 408 were checked by the engine-level page check, not in their
  own scenes.
- **The page check tool reads a stale pack** (`recheck64/v53.tsv`), so 4 of
  27 sampled strings fail in it on both old and new builds. The tool needs to
  be pointed at the current pack (`v71.tsv`) before its failures mean
  anything.
- **Kara's five-row pages and a continuous campaign** were left to
  playtesters.
- **`04EA77`** is a typo found after the upstream comment on
  Azarem/IOGRetranslation#35; it is corrected locally only.

## SNESRecomp update (to `627b2f27`)

- **Nine of 142 route replays shift a scene load by one or two frames.**
  States, scene changes and end positions match. I attribute this to
  upstream's timing corrections but did not trace any of the nine to a commit.
- **`test_native_continuations` and `test_iog_map_controller` fail**, the
  same way before the update. Not investigated.
- **Four tests were not run** because they need a ROM or a build directory:
  `test_iog_received_content`, `test_iog_received_map_input`,
  `test_iog_virtual_controller`, `test_received_reference`.
- **Two of upstream's own tests fail against this tree**
  (`test_host_overlay_keys`, `test_host_deadline_wait`) because their stubs do
  not know two older local changes (`SnesRa_Idle` in the rewind loop,
  `frame_skip`). Not merge errors; not fixed.
- **Upstream's new hi-res (512-dot) surface is unused here.** The game owns
  `draw_frame` and does not provide `draw_hires_frame`.
- **`build-tree.py` and `build-play.py`** still exist and link against the
  pre-update graph. Use `sdk-update/mk.py`. They were not deleted.
- **The settings-menu point** once considered for an upstream SNESRecomp issue
  was never rechecked against the updated code.

## Housekeeping

- **`wsurvey/survey.py` overwrites `survey.json` on every run**, including a
  partial run. That destroyed the baseline once. Copy the baseline first, or
  give the script an output argument.
- **The GitHub contributors box** was to be rechecked. Not done.
- **`image-1795635901917.png`** in the repository root is the owner's pasted
  screenshot. Leave it; never commit it.
