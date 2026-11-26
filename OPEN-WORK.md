# Open work

What is still to do, and what was not fixed or not tested, as of November 25,
2026 (commit `389e213`, tester build `v0.2.0-beta.2`). Read `HANDOFF.md` for
how things are built and where the evidence lives; this file is only the list.

Each item says what is known, not what is assumed. "Not tested" means nobody
and no tool has looked. "Not played" means automated replays ran but no person
played it.

## Decided, not built

- **Optional edge-anchored status display.** In the wide view the status
  display is still the original 256-pixel block in the middle of a wider
  picture. Proposal: PLAYER life at the top-left, ENEMY life at the top-right,
  the DP counter and ornament centred. The owner wants it as a choice, with
  the centred layout kept. Two smaller ideas went with it: hide the ENEMY
  label while there is no enemy, and a faint shadow behind the display so it
  reads over bright scenes. Nothing is designed or built. The status display
  is already its own layer (`PresentHud`, `s.hud` in
  `src/iog_world_renderer.c`; `DrawFrameLayer` in the runner's `opengl.c`),
  which is what makes this cheap. Use the Game UI/UX skill named in
  `AGENTS.md` when designing it.
- **Native coverage.** The owner's next priority after the tester build. On
  the updated SDK the private native build still carries about 99.9 percent of
  CPU cycles, but the interpreter share rose from 31 to about 6,200
  instructions per 620 frames in the one scene measured (`3E`). Start by
  finding out why before choosing targets. The regenerated graph has 1,229
  AOT-eligible variants; the old one had 1,248.

## The tester build (`v0.2.0-beta.2`)

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
