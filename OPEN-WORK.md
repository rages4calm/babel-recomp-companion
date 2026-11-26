# Open work

What is still to do, and what was not fixed or not tested, as of November 26,
2026 (tester build `v0.2.0-beta.15`). Read `HANDOFF.md` for
how things are built and where the evidence lives; this file is only the list.

Each item says what is known, not what is assumed. "Not tested" means nobody
and no tool has looked. "Not played" means automated replays ran but no person
played it.

## From Gaia and Time (betas 13 to 15, November 26)

andrewclunn (Drewish), author of the *Gaia and Time* hack, gave permission
to use his features; the owner asked for the ones worth having. Rebuilt in C
from his patches as documentation (`gaia-iog-baserom`, branch
`drew/gaia-and-time`, `RunButtonCore` and `TextSpeedOption`), credited in
the README:

- **Auto-run** (`iog.enhancements/run`, option `style`, default `auto`; `hold`
  is the old behaviour). Checked on a Mu mark: walking reaches run speed after
  about two seconds, holding Y after about fifteen frames; native and the
  interpreter give the same positions. Not played; not tried on slopes, ice,
  ladders or in boss rooms.
- **Text speed** (`iog.enhancements/text_speed`, on by default at Normal):
  Normal, Cinematic, Instant; the run button hurries any line. Checked on the
  Rama Statue message: Normal and Instant show the line at once, Cinematic
  types it over about thirty frames, Cinematic with Y held at once; native and
  the interpreter give identical frames. It writes `$7E` only while a message
  is up; a state loaded mid-message can take the written value for the
  script's own pace until the next line.
- **Use key items on the spot** (beta 14, `iog.enhancements/auto_use`, on by
  default). Pressing A where a carried key item works hands the game a B
  press with the item equipped while A is held; the previous equipment is
  restored after the message. 28 spots for 17 items, taken from the handlers
  in the item-use table at `$03:843F` (room `$0644`, tile `$09A6`/`$09A8`;
  `COP 45` areas taken as end-exclusive, the explicit compares as written).
  Checked only at Rama's Statue on the owner's F1 state: A on the right
  pedestal raises it and opens the cemetery, identically in native and the
  interpreter; A away from it does nothing. **Not checked at the other 27
  spots**, nor with a button type other than the default (the item button
  is then not B). Melodies and hieroglyphs are left out on purpose.
- **Red Jewel sparkles** (beta 15, `iog.enhancements/jewel_sparkles`, on by
  default, `src/iog_sparkle.c`). Drawn by the host over the finished picture
  (wide view at presentation, 4:3 into the render buffer), not as actors.
  Hidden jewels: actor `$00:C672`, index actor+`$0E`, flag `$0280+index`.
  Givers: Lance `$79` (`$A5` set, `$E2` clear), Ann `$95` (`$D6`, `$E5`
  clear), stone girl `$AE` (`$E6`), snake game `$C6` (`$E7`), on the actor
  nearest the spawn tile. Seen on staged warps from the owner's F1 state:
  South Cape's jewel by the bell tower (wide and 4:3), and the Gorgon hut's
  stone girl and its jewel. **Not seen:** Lance, Ann, the snake game, and the
  other thirteen jewels. Left out: his fisherman's pot and trapped slave
  sparkles (tied to his script changes) and the new jewel sources he adds.
- **Not taken, by choice:** his four items, item placements, ability and
  control changes, options menu and HUD rewrite (they change game code and
  rebalance the game), and his script (still in QA, written around his
  items). **Worth doing next:** using key items automatically at their spot,
  and the hidden Red Jewel sparkles (both GaiaLabs work he carries).

## Owner playtest of beta 11 (November 26)

Eight bug marks (`.local/batch-001/owner-playtest-5`). Fixed in beta 12,
checked on the marks, not yet played. Every beta 10 mark gives the same wide
frames on beta 11 and beta 12 apart from the item counter.

- **Item counter still hard to read**: the digits were taken from the game's
  BG3 font in VRAM, whose colour indices are not an outline, so they came out
  garbled. The counter now uses its own bold 4x7 digits, white on a dark badge
  with a light rim.
- **The plane enters and leaves at the old 4:3 edges** (the flight from the
  Sky Garden, scene 58): the plane stands left of the scene's 256-pixel window
  as it flies in and right of it as it leaves, and the renderer's rule for
  actors on another floor of a map cut their pixels to the original field.
  The flight's sky has one floor, so that rule no longer applies there.
- **Black rectangles on Seaside Palace stairs**: when a floor was entered
  through a door while the camera was still panning (no remembered floor to
  slide from), only the old field and the window showed, with black beside
  the field. The rows the original camera shows now continue across the
  room's width. The floor-to-floor slide also accepts floors of different
  widths.
- **Dotted column and flashing strip in Mu**: under a per-line horizontal wave
  (Mu's water, village heat, room-transition waves) the field's edge tile
  columns, where the game streams the next strip, came from live VRAM and
  showed stale cells in the middle of the wide picture. Those columns now come
  from the map. The original 4:3 picture shows the same dots at its own edge.
- **A Mu stone face that blinks and seems unkillable**: native and the
  interpreter give the same result, and one face died after several hits. It is
  the game's normal hit flash. No change.
- **The owner's F1 save in Mu**: the room with two pedestals (scene 66) takes
  two Rama's Statues (item `13`, flags `80` and `81`); the save had `80` set
  and no statue. At the owner's request a Rama's Statue was put in the empty
  slot of his F1 state; the original is in
  `saves-backup-before-rama-statue`. Tested on beta 11: using it on the right
  pedestal raises the statue and opens the cemetery. The chest or event that
  gives the second statue was not looked up and is not flagged.

## Owner playtest of beta 10 (November 26)

Ten bug marks, each reloaded with the owner's own settings and fixed or
explained. Fixed in beta 11, checked on the marks, not yet played:

- **Status display at the edges fell back to the centre** during dialogue at
  the top of the screen (the text box starts on row 39, the check stopped at
  row 40) and in rooms as narrow as the original picture (Neil's cottage, small
  houses). It now stays at the screen edges in both.
- **Brief 4:3 flashes** (learning Dark Friar, talking to a prisoner): 26 and 38
  frames where the game uploaded objects outside its composer. A room whose
  display is set up as on its last plain wide frame now keeps the wide picture
  with the game's own actors in the middle. **Not reproduced**: both happened
  before the marks were taken; check that they are gone in play.
- **Grey strip on house stairs**: the next floor's window was shown below the
  room from the first frame of the stair, so its filler rows sat at the edge.
  It now appears only as far as the camera has reached it.
- **Yes/No with nothing asked** (the slave trader in Freejia and five other
  prompts): the converter turned GaiaLabs' `[WAI]` into a new page when the
  question was taller than the rows above the choices. Those now show the
  question, wait, and scroll the choices in under it. Three questions with one
  row above their choices were shortened to one row
  (`079922`, `09D462`, `04E6E6`). The scrolled rows lose the speaker's colour.
- **Item stacking counter and equipped frame on the Cond. page**: the page
  check took Will's portrait for an item icon. It now needs every held item's
  icon. The counter has a dark badge so it reads on the light platform.
- **Diamond Mine lift cables away from their baskets**: the 3/2-speed cable
  layer was drawn with the backdrop projection, 85 pixels off. Planes as fast
  as the camera or faster now stay aligned with the original picture. The
  cables themselves cross the whole room in the original too (also behind the
  status display, as in the interpreter's 4:3 picture).

Open:

- **Stuck after falling in the Sky Garden** (scene 53 to 54, landing at
  496,640). The player's walk animation runs but the position never changes in
  any direction: the landing spot is solid on every side. The interpreter is
  stuck the same from the mark, so it happened during the fall. Not
  reproduced: the owner's F1 state is in the hub (4C) and the route and the
  place he stepped off are unknown. The owner then gave a state from just
  before the jump (slot 7, scene 53 at 532,594) and the same jump worked for
  them in play. Eight replays from it (straight down, down-left, down-right,
  at two distances, and sideways first) all landed in 54 at 496,540 to 576
  or stayed in 53, and Will could then walk in every direction. Native
  matched the interpreter on every replay. Still open: the landing spot
  that fails was not found.

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
- **Basement floor (scene `0A`):** fixed November 26 from the owner's bug
  mark (`.local/batch-001/owner-playtest-2`). The floor is on the band-scrolled
  plane. The game writes the wall layer's scroll in vertical blank and reads
  the bands from memory at the top of the frame; this runner has finished the
  frame's logic by then, so the bands ran one camera step ahead and the floor
  slid 2 pixels under the walls while walking. The wide renderer now registers
  each band to the camera the walls are shown at
  (`IogRasterParallaxBandShift`). A standing and a moving frame now differ
  only in the player and the minimap. Not done: the **Original 4:3 picture**
  comes straight from the PPU and still has the slide; scenes `2B`/`2C` use the
  same code and were not looked at; the castle sky scene was compared before
  and after and only its sky bands move, by under a pixel of camera.
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

## Diagnostics in the owner's install (November 26)

Three passive logs, on only where a file `diagnostics/on.txt` sits beside the
executable. The owner's beta 8 folder has it and runs a build of the same
source with these (`cb-diag`; the released executable is kept beside it as
`babel-recomp.beta8-release.exe`). The public download has the code but not
the file. All output goes to `diagnostics/`:

- `interpreter-<time>.txt`: what the interpreter itself ran, summed per
  session (`PC e m x rti sched count`), rewritten every half minute and at
  exit. Input for `sdk-update/extend.py` and `grant.py` once converted to
  their `PC:emx:rs` keys.
- `renderer-<time>.txt`: one line whenever the scene or the way the picture
  is presented changes (`frame scene reason width height player_x player_y
  camera_x camera_y`). Any reason not starting with `ready` is a fallback.
- **The B key marks a bug**: `mark-<id>.sav` (a save state of that moment), a
  screenshot, a `MARK <id>` line in the renderer log and "MARKED" on screen
  for two seconds. Play is not paused.

Checked in one hidden run (mark, state, log lines, confirmation). Not
checked: a long session, the screenshot file itself, and the exit write
after a crash (the half-minute rewrite is the fallback).

## Soundtrack (November 26)

- **MSU-1 is now off by default** (`iog.enhancements/msu1`
  `default_enabled = false`). Before beta 10 a fresh download showed
  "Active: MSU-1 soundtrack" on the launcher while the game, with no pack,
  played SNES music. Importing a pack turns it on.
- Checked from a clean unzipped folder: no pack means original audio in the
  launcher and the game; importing the owner's JUD6MENT zip verifies 28
  tracks, recognizes the catalog, turns it on, and the game plays from it.
  The launcher's own soundtrack tests pass (47 + 9 checks).
- **The launcher lists only packs inside the current game folder.** The
  owner's pack lived in the beta 2 folder after later betas were unzipped
  beside it, so his dropdown was empty although the game played the pack.
  Testers who update by unzipping a new folder hit the same thing;
  `START HERE.txt` now says which folders to copy. Not fixed in code: the
  launcher could find a pack in a sibling version folder, or store the pack
  path relative to the game folder.

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
  1,779,645 down to 598,348; scene `3E` 6,207 down to 31.
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
  - **Interrupt permission (same day, in beta 8).** The profile now also says
    whether an instruction ran inside an interrupt handler. All of the
    roughly 192,000 declining instructions did: steps registered for normal
    game code only, mostly the routine that sets the scroll registers on
    Mode 7 scenes. `sdk-update/grant.py` gave 263 of them the NMI grant
    (`sdk-update/ext4`). Scenes and routes are again identical with the same
    CPU cycles; interpreted instructions are now 924 over the survey and
    30,313 over the routes (92,710 cycles of 10.1 billion).
  - **What is left on the routes:** 29,500 at the sprite-culling
    instructions the wide view patches while the game runs (excluded on
    purpose), 484 at an indirect jump the generator forbids inside an
    interrupt (`808482`), 117 at the protected interrupt acknowledgement
    (`828195`), and a few stack and reset operations.
  - **Code the replays never reached is still interpreted.** Coverage is
    what 198 scenes and 142 routes executed; a real playthrough reaches
    more. Profile a played session with `SNESRECOMP_INTERP_RESIDUAL` and run
    `extend.py` and `grant.py` on it.
  - **Not played by a person** on the extended build, and no speed
    measurement was taken.
  - **The four declarations are assertions.** They rest on the older
    analyzer's proof and on the identical survey and routes.
  - **Reported upstream** as RetroPortingToolKit/snesrecomp#323 with a
    game-free test. No reply yet; a PR was offered, not sent.

## The tester build (`v0.2.0-beta.15`)

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
- **Native since beta 7.** The owner decided on November 26 to publish the
  compiled game code in the download (`package_release.py --native`, from
  `.local/batch-001/sdk-update/build`). The package was run from a clean
  folder: a cold boot to the title and the Inca room from his save, with 12
  and 0 interpreted instructions. It differs from the earlier downloads in
  two build options that came with the native build directory and were not
  compared in play: `SNESRECOMP_DSP_MIX_IMPL` is LLE (was NATIVE) and
  `SNESRECOMP_EXECUTION_DEFAULT` is off (was on). The executable's identity
  string still says `rom-derived-code=private`.
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
- **Classic 16:9 picture** (wide view off, `Widescreen = 1`): at the Great Wall
  (route `fanger`, frame 1462) a solid green strip fills the right edge.
  Seen in a capture on November 26; not investigated.
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

## Scratch cleanup (November 26)

At the owner's request the old private scratch under `.local` was cut from
141 GB to 5 GB. **Most `.local/batch-001/native-0xx` and
`visual-fullgame-0xx` paths named in `HANDOFF.md` and the `docs/` batch
notes no longer exist.** They were evidence archives; nothing current used
them. What was kept is exactly what these still need, checked by regenerating
the native graph byte-identically and rebuilding from what remained:

- `sdk-update/` (graph, native build directory, `ext4`/`ext5` native step
  sets, `mk.py`, `extend.py`, `grant.py`, `declare.py`, `prune.py`),
  `release/` (public build directory, GaiaLabs data, `rt.py`, release notes);
- the profile manifests the graph is generated from (inside `native-002` to
  `native-014`, `native-016/graph-world-v1`, `native-023`), the bundled Python
  (`native-007/tool-versions/python-current`), the GaiaLabs sources
  (`native-006`), `native-021/wram-effects-v1`;
- `visual-fullgame-041/`: `wsline` (the 142 routes), `sdk-survey`,
  `sdk-routes`, `playtest1-ui`, the baseline builds `cb-wsl2`, `cb-sdk0`,
  `cb-wsfix11`, and the save states the routes start from (spread over the
  remaining `visual-fullgame-0xx` folders);
- `owner-playtest-*` (the owner's saves, bug marks and session logs),
  `codex-history`, `manual-test-slots-025`.

`sdk-update/prune.py` is the script that worked out the keep list. After
each round of work delete the `cb-*` builds, `ui-*` and `travel-*` runs it
made; they are rebuildable.

## Housekeeping

- **`wsurvey/survey.py` overwrites `survey.json` on every run**, including a
  partial run. That destroyed the baseline once. Copy the baseline first, or
  give the script an output argument.
- **The GitHub contributors box** was to be rechecked. Not done.
- **`image-1795635901917.png`** in the repository root is the owner's pasted
  screenshot. Leave it; never commit it.
