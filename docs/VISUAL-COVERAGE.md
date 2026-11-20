# Full-game visual coverage

The owner has expanded the presentation task beyond the eight manual test saves.
Every playable zone and its transitions needs correct widescreen, 1.5× framing,
background scrolling and Mode 1/7 effects. Native-gap work is secondary to this
visual pass. Approved GaiaLabs content integration is a separate content-identity
boundary; a stock renderer receipt does not qualify a modified ROM or new maps.

## Inventory, not a pass percentage

`scripts/inspect_visual_coverage.py` enumerates all 256 scene IDs without reading
a ROM, executing a game or changing renderer eligibility. It reads the actual
source admission, authored-window and secondary-camera predicates. An admitted
scene format can still render incorrectly; the manual-save bugs demonstrated
that directly. There are currently no complete scene/phase approvals in this
inventory. A known unused/default-record alias is not counted as a tested zone.

An optional external GaiaLabs scene index identifies shared default-record
aliases without copying extracted source or assets into this repository. Their
classification is source evidence, not proof that no runtime path can reach them.
Mode 7 is inventoried separately. The uniform-plane sampler has layout/raster
gates. The calibrated perspective path extends rows only when its parameters
match the captured original transforms. Other supported nonuniform rasters can
retain the captured original-height band with padding outside it. These are
separate structural capabilities, not proof of every Mode 7 scene or phase.
The generic widescreen Mode 7 margin path remains separate. Scene modes are not
guessed from IDs.
Likewise, five explicit legacy scene camera models are counted separately from
the new live producer reader for Track, Vertical, Accumulate and Drift behavior;
neither count is a full-game pass figure.
The generic authored-window reader conditionally frames live room bounds; it
does not establish that secondary scenery should stop at the floor boundary.
Per-line HDMA camera derivatives also cannot be inferred from a global actor
ratio. Deferred raster-camera paths remain explicit review work.

## Original ship and Freejia routes

The Original renderer now admits the Wrecked Ship and Gold Ship decks
(`2B`, `2C`), the Gold Ship cabin (`2E`), and the Freejia house and hotel
(`33`, `39`). The Wrecked Ship cabin (`2D`) already admitted the same stock
format and was retested with its deck. The original lighting and camera
windows govern the expanded picture.

The hotel stair pan previously showed parts of the next floor below the
active floor because its new camera bounds take effect before the camera
arrives. While the camera is outside the new bounds, the renderer preserves
the original field and HUD at the same scale. In settled authored rooms, the
expanded bottom edge respects the tile fetch's one-row lookahead. This
removes a one-pixel strip observed in the wreck's upstairs cabin.

The v10 controller runs traversed both ship door round trips, both cabin
stairs in both directions, both Freejia town-door round trips and both hotel
stair directions. They used separately assisted stock checkpoints followed
by SDL virtual controller events. The hotel pan retains all 57,344 native
viewport pixels while removing 22,204 leaked floor pixels. Matching guest
state and CPU results do not substitute for the 1080p square-pixel 1.5×
visual checks. Further rooms and story phases remain open.

The retained v7 travel build separately passed the story-gated Freejia to
Diamond Mine round trip with movement inside both areas and MSU-1 changes.
That test used three linked controller checkpoints. The locked mine and
stock-route recovery also passed.

## Diamond Mine

The elevator, foyer and rescue chamber (`43`, `44`, `47`) now use the
expanded renderer with their stock scene data. The elevator's two cave layers
keep the captured BG2 phase during the diagonal ride. The wider view extends
the actual cave without moving the rocks relative to the stock cable and
player. In one paired mid-ride frame, the previous projected composition
displaced 37,005 gameplay pixels in the sampled original rectangle below
the HUD. The corrected composition matches all those source pixels.

Final v12 SDL virtual controller replays verified the entrance and main-room
doors, both elevator directions and exits, and the foyer doors to the Morgue
and rescue chamber. An entrance combat check killed a Flayzer with a controller
attack using the retained boosted-stat fixture. The rescue route uses an assisted foyer
arrival and opens the stock two-key requirement in its starting state. The
same approach with the flags clear stayed in the foyer. The rescue route
walked the lower chamber and returned through its original door.

The full 1080p square-pixel 1.5× pictures were inspected with the original
cave layers, cable, actors and Companion radar. The rescue chamber is a
finite 256-pixel room and uses black space beyond its authored geometry.
These checks cover the tested routes and elevator phases. Collecting the
two keys and completing the Memory Melody rescue sequence remain separate
quest coverage.

## Nazca through Watermia

This batch adds expanded rendering to 35 Original scene IDs across five
regions. It increases structural admission from 78 to 113 scenes. The
controller checks below use separate source-validated arrivals and disclosed
story setup. They cover the routes and phases observed in those runs.

| Region | Newly admitted rooms | Verified gameplay and presentation |
| --- | --- | --- |
| Nazca and Sky Garden | `4B, 4D, 4E, 50, 52, 54, 56` | Nazca movement on both axes, Sky Garden door round trips and underside exits, and an active Viper phase with projectiles and rubble |
| Seaside Palace | `5A–5E` | Room and coffin door round trips, main stair both directions, passage toward Mu, and stock Purification Stone use |
| Mu | `5F, 60, 63, 65, 66` | Full, half and drained water phases, six natural transitions and a live Vampire combat phase |
| Angel Village and tunnels | `69, 6A–6C, 6E, 70–75` | Terrain and light shafts during movement, four village/tunnel door round trips and the statue-room round trip |
| Watermia | `78–7E` | Day and night docks, movement in six interiors and all six house door round trips |

Sky Garden's top-side backdrop now stays aligned with the stock raster.
The four underside scenes repeat only their verified drift layer, removing
the rectangular seam around the original field. Paired captures show that
the underside fix leaves the original rectangle byte-identical. Scene `54`
still has an inherited 28-pixel difference against stock on its last native
scanline in one tested pose.

Seaside Palace and Mu extend both scroll axes using the measured eight-line
cycle. The coffin hall's lower floor can use the same extension when its
two epochs change only the palette. Discontinuous layouts still use the
existing fallback. Expanded foreground geometry stays within the actual
room window.

V14 verifies the combined renderer, including full NVIDIA OpenGL 1080p
captures at square-pixel 1.5×. Some unaffected routes use the exact v13
candidate, and changed regions have v14 replay evidence. The 18 Angel
Village and Watermia movement captures and the separate night capture
match stock gameplay pixels outside the separately placed HUD. Both boss
checks cover active fights. Boss victories and Neil's Cottage remain open.

The optional manual visual receipt binds the eight historical samples to their
actual build and dependency hashes. A later source edit changes those samples
to historical evidence. Neither current nor historical samples are silently
promoted to a whole-scene approval.

```powershell
python scripts/inspect_visual_coverage.py `
  --scene-index .local/batch-001/native-006/gaia-sources/baserom/extracted/tables/scene_actors.asm `
  --visual-receipt .local/manual-test-slots-025/renderer-fix/COMPLETE-v2.json `
  --output .local/batch-001/visual-fullgame-001/inventory-initial.json
```

Detailed output remains ignored/private. Existing output files are refused;
produce a new receipt when policy changes. Do not commit private indexes,
captures, states, ROM-derived generated code or asset data.

## Euro through Pyramid

Batch 014 adds 52 Original scene IDs, bringing structural admission from
113 to 165. It also extends the existing Pyramid hub admission to its
one-background form. Arrivals use assisted, source-checked checkpoints.
Door checks use SDL virtual controller movement after setup. Scripted
quest and combat checks are identified separately.

| Region | New scene IDs | Verified route or behavior |
| --- | --- | --- |
| Watermia and Great Wall | `7F` | Watermia story exit to Luke's house. Sand Fanger defeated from an assisted combat setup, with the reward flag set. Separate earned defeat checkpoint reaches the Dark Space statue ceremony and returns with the statue recorded. |
| Euro | `91–9D` | All 13 rooms moved on both axes, 12 door round trips, and selected stairs and the shrine cellar. Visual checks use interiors entered through their normal doors so that stock graphics have loaded. |
| Mt. Temple and Native Village | `A0–A6, A8–A9, AC–AE` | Movement checks, 11 assisted door round trips including previously admitted `A7`, and one temple spider kill with the enemy counter decrement. |
| Angkor Wat | `B0–B5, B7, B9–BF` | Stable captures across all 16 scenes including previously admitted `B6/B8`, 12 door round trips, and stock Flower exchange driven by a scripted confirm sequence with a full starting inventory. The `B2` outbound door passed, with its return still open. |
| Dao | `C3–C9` | Square-pixel 1.5× town heat and six door round trips. |
| Pyramid | `D0, D2, D4, D6, D8` | Movement and branch returns into hub `CC`. Four branches and the hub return use a guarded layout with the secondary background absent. `D6` uses its normal two-background route. |

Dao's window bounds translate with each detached width segment. The
renderer checks the actual 64-line heat phase before extending it. Native
Village repeats its separately verified 32-line vertical pattern only
while its camera and raster agree within the guarded bounds. Transient
frames outside those bounds, the Great Wall Dark Space ceremony, and
unrecognized layouts retain the same-scale fallback. One sample during
the Native Village return had two differing pixels on the last stock row,
and one Great Wall ceremony return fade sample had lower-edge differences.

The broad movement and transition runs came from `originalv15`. The final
`originalv16` rechecks Native Village motion, all five Pyramid branch returns,
Euro door-entry visuals, and selected Dao and Angkor views. The final build
also passed controller map open/close and stock world travel fallback checks.
The checked player view uses square pixels and 1.5×, including selected
1920×1080 NVIDIA captures and comparisons of source gameplay pixels with
the separately composed HUD masked. These samples cover the listed paths
and phases. Uninspected story phases and the remaining scenery are open.

## Early rooms, Pyramid and late story

Batch 015 adds 40 Mode 1 scene IDs, bringing the structural list from 165
to 205. The separate Mode 7 extension now handles the crash's tested
same-plane color effect. Exact v17 routes begin from assisted checkpoints.
Controller routes use SDL virtual input, including stock doors and combat.
In the early rooms, 12 selected door routes completed a round trip and nine
others reached their neighboring scene in one direction. Tests covered the
actual composed screen, with original gameplay pixels compared separately
from the repositioned HUD.

| Area | Added scenes | Verified behavior |
| --- | --- | --- |
| South Cape, Castle and Itory | `07, 0A–0B, 10–11, 13, 16–19, 1B` | Town and Itory return doors, dungeon adjoining rooms, and castle prison dialogue and movement. A disconnected map marker stays outside the expanded picture. |
| Inca and Freejia | `1D, 1F–22, 24, 30, 34–38, 3A–3C` | Inca movement and Freejia room transitions. The cliff retains its captured raster effect. |
| Neil's Cottage, Sky Garden aftermath and Angel Village | `49, 58, 68` | The Hotel-to-Cottage story path, flight through the Mode 7 crash and descent, and tunnel/portrait story checks. The cottage stays within its original field. |
| Pyramid and Dao flight | `CF, D1, D3, D5, D7, D9–DC` | Eight branch exits, all six Hieroglyph Chamber panels, a stock first-stone reward from an assisted setup, and the flight into Babel. |
| Babel rooftop and Jeweler's Mansion | `E4, E9` | Rooftop dialogue retains its original cutscene framing at 1.5×. The Mansion preserves the uploaded fog through camera motion and active combat. |

Babel's rooftop blue strips came from showing cutscene background pixels
outside the authored camera. The composed field is now centered in the
widescreen presentation. The mansion's 64-line fog wave continues across
the full width using the live uploaded ring and original color math. The
renderer checks the phase before extending it and retains fallback for
other layouts. The Pyramid and cottage clip allocation rows beyond their
authored 224-line fields.

The Sky Garden crash uses the actual Mode 7 color math for both screen
inputs, and the bookending flight repeats the verified stock cloud
planes. The three final rechecks cover the flight, ocean and descent
phases. The next batch addresses the Babel boss rematch stars and the
Great Wall ceremony fade.

## Babel rematches, Great Wall ceremony and ending

Batch 016 adds seven Mode 1 scene IDs, bringing the structural list from
205 to 212. v18 keeps the same square-pixel 1.5× scale and stock fallback.
The verification uses assisted starts and SDL virtual controller input
where movement or combat is required.

| Area | Verification |
| --- | --- |
| Babel rematches `F2–F6` | Live fights use the original 64-line star wave, screen enables and color math. Only the star layer extends outside the arena. Sand Fanger was defeated with assisted player stats, and the stock script recorded the reward flag and returned to Babel. |
| Great Wall `8A`, statue ceremony `FD` | The wall parallax now accepts the stock terminal validation sample when its descriptor and phase agree. The drawable map remains finite. The return no longer misaligns sand during the tested fade. The statue inventory ceremony keeps the original framing and mosaic through fallback. |
| Adrift `2F` | Seven scripted raft phases, including dialogue, preserve the original horizon and moving sea. Only the background repeats past the raft. Controller dialogue from an assisted start also reaches Diamond Coast. |
| Credits `F7` and final school scene `F0` | The stock credits ran through their authored handoff into the school scene. The field stays centered with the original scenery and motion, and the dialogue uses the host frame. |

The Sand Fanger rematch return fade can still use fallback. Batch 017
addresses the next two prologue compositions, the dream and the upper
Great Wall sky.

## Opening, dream and Great Wall

v19 uses the original Mode 7 subscreen and color math for the opening
ocean and legend cards. The ocean extends into the sides and the original
ships, figures and text stay in their authored positions. The idle title
sequence and controller Start were checked from original cold-entry
checkpoints. The tower, spotlight and two ending scenes preserve their
centered original presentation.

The ship dream adds scene `2A` to the Mode 1 renderer. It translates the
original window coordinates for each drawn segment and keeps the dream's
rooms and iris within the authored field. The HUD and dialogue use the
same presentation scale as nearby rooms. Unknown window configurations
retain fallback. From an assisted ship setup, virtual controller input
reached the dream through the sleeping scene, walked the stair, completed
Shira's dialogue, and returned to the ship.

The upper Great Wall arena and adjoining room now extend from the
captured background phase. This preserves the original field during
movement even when the background and foreground publish different
camera positions. Checked the `8B → 8A → 8B` round trip and the v18
post-ceremony fade. Controller routes use SDL virtual input.

## Radar, inventory and connected routes

v20 feeds the small radar from the walkable grid, revealed cells and player
position. Scenery decoding is reserved for the full area map. Both still
use the same discovery journal. The radar pixel comparison used both source
paths. In game, the virtual controller opened and closed the full map, and
its output matched v19 byte for byte.

The virtual controller also opened and closed the original inventory from
the Ishtar studio. Two menu pictures and the settled room matched v19
exactly, as did all seven checked guest snapshot fields after the return.
The inventory keeps its centered stock framing at square-pixel 1.5×.

The Castle staircase and all four Larai Cliff links completed in both
directions from assisted entries. The routes used the original dialogue
and controller movement. Eight inspected views matched their sampled
original gameplay pixels, including the lower cliff mist.

The assisted Cottage route reached Nazca through the original world map.
The Seaside Tunnel route advanced through all three story phases into
Angel Village. Both tested Angkor routes from `B2` returned to that room.
The routes used the original transition scripts after setup.

The four remaining Babel rematches were won from assisted starts. Castoth
lost both hands before the head opened, and both Vampires fell. Viper,
the Vampires, Castoth and the Mummy Queen each returned to the tower
through the original victory script. Player-only setup included form,
stats and positioning. Sand Fanger's win and return were verified on v18.
The original Sky Garden Viper also reached its stock reward ceremony and
returned to the arena from an assisted combat checkpoint.

## Explored exits, travel and boss returns

The full area map now marks exit triggers in explored tiles. It checks the
loaded list against the verified Original cartridge and clips the search
to the active floor. The small radar and the town pause behavior keep
their existing controls. Three reviewed full-map captures show markers.
An Aqueduct capture with no qualifying exit is byte-identical to v20.
All four controller map sessions returned to the same guest snapshot.

The walkable world map reached and departed destinations on 11 distinct
routes on v20, with four routes replayed on exact v21. The route checks use
assisted story starts and stock controller entry and exit. Two paced MSU-1
routes on v20 reported no underflow after warmup with a dummy audio driver.
Speaker playback remains open.

The original Mu twins fell and the bomb and Erik sequence completed.
Solid Arm returned to Babel, Dark Gaia reached the epilogue after both
forms, Mummy Queen earned the statue, and Castoth returned control after
defeat. The test setups use player-only assistance and virtual controller
input. One Mu fight sample differs on 13 pixels of the bottom stock row.
The Mu rescue stops in the room after dialogue.

The Pyramid puzzle's original field ends before its glyph storage.
The renderer now clips those tiles from the lower margin in the witnessed
layout. Its center still matches the original field on the reward return
and other layouts retain fallback.

## World travel and connected story

The batch 020 test build replays 15 staged world-map entries and returns using
virtual controller input with the current retranslation and MSU-1 active.
The tested routes cover Angel Village, Watermia, Great Wall, Euro, Mt. Temple,
Native Village, Angkor Wat, Dao and the Pyramid. The samples use the full
square-pixel 1.5× field. Stock world-map recovery and the separate Companion
local map each matched seven saved guest fields against their controls.

A save already near South Cape can no longer bypass the Itory road gate.
The virtual controller stays on the map with the gate closed and enters
South Cape after the story flag has opened the road.

From assisted starts, ordered virtual-controller input defeated the Mu twins,
defused the bomb, rescued Erik, walked out and reached the reunion camp.
The widened combat capture's 13-pixel difference on the last stock row comes
from the reconstructed actor parts starting at that edge. The widened renderer
draws those parts into the expanded picture. The stock OAM publication culls
them at the edge of its own field.

The ending replay defeated both Dark Gaia forms, advanced into the epilogue and
reached the Changed World sequence. Reloading that earned checkpoint on the
current dialogue pack and advancing the stock cutscene returned to the epilogue.
The replays use an SDL virtual controller and keep their starting assistance
separate from ordinary movement, combat and dialogue after that setup.

## Bounded entry survey

`scripts/survey_iog_scenes.py` stages isolated copies of a private fixture's
settings/mod metadata and seed. `--plan` records the intended commands without
launching the game or reading a ROM. Execution requires the exact bare Original
USA image and a frozen private executable; it is not a GaiaLabs-ROM runner.

```powershell
python scripts/survey_iog_scenes.py `
  --binary .local/batch-001/visual-fullgame-001/babel-visual-v7.exe `
  --seed .local/manual-test-slots-025/play/saves/save1.sav `
  --fixture .local/manual-test-slots-025/play `
  --rom "Illusion of Gaia (USA).sfc" --scenes 33,2D,2E,39 `
  --incoming-catalog .local/batch-001/visual-fullgame-001/authentic-incoming-camera-repair-v1.json `
  --output .local/batch-001/visual-fullgame-001/entry-plan-example `
  --frames 600 --jobs 2 --plan
```

Remove `--plan` and select a new output directory only after the candidate is
ready. Each run accepts at most 32 explicit unique IDs below `F0`, 400–1000
frames per case and two workers. It requests scene entry through the original
pending request/return-context path, with source-validated destination X/Y,
facing and camera window from an actual Original inbound warp. Execution
refuses missing recipes; a plan without a catalog labels its scripts missing
and cannot execute. Catalogs bind the private source file hash, record line,
source scene and exact incoming tuple. Executed recipes must also match a
literal warp record in the verified Original ROM. This does not establish
story prerequisites or natural progression. It does not set every story flag
or overwrite enemy/reward outcomes. Captured player position, health,
allocation bounds, PPU mode and renderer refusal reasons must be reviewed.

Cases retain failures/timeouts, capped logs, source picture packets and command,
environment and input hashes. Entry checks are distinct from renderer readiness
and visual approval. A loaded room, a nonblack image or an opted-in survey scene
is not a shipping admission or completed visual test. Survey instrumentation
retains the stock identity, layout, object and publication guards.

The first 32-scene survey remains diagnostic evidence: its producer changed
during preparation and its early `settled` snapshots could retain old scene
dimensions. Do not rerun it merely to rewrite that status. Future plans freeze
the producer hash before launching, refuse later launches after a producer edit,
and record any end-of-run producer/input drift. The new delayed probe snapshot
is still not the picture's state: visual classification uses the composition-
paired active RAM exported with the actual source picture. Where that association
is absent (including packet formats without scene RAM), classification is marked
unavailable instead of silently substituting probe metadata. An off-map player
or a story-specific departure phase remains a fixture problem to investigate.

Both initial 32-scene surveys forced an invalid `$2200` camera window through
the last incoming byte. That selects a 512×512 window even for a 256-pixel room.
It can preserve wrapped edge strips or expose separate floors, so those images
cannot establish renderer defects without correcting the fixture. The original
surveys remain diagnostic, with their invalid setup disclosed. Targeted repeats
of `33`, `2D`, `2E` and `39` correct this identified fixture bug; they do not
rewrite the earlier results or qualify other rooms. There is no silent `$2200`
or allocation-window fallback in the current execution tool.

## Work groups

1. Preserve the eight bounded samples: Classroom `08`, South Cape `01`, Aqueduct
   `0E`, Great Wall `85`, Sky Garden `4F`, Viper `55`, Solid Arm `EA`, Pyramid `CC`.
2. Fix immediate exits that fell back in the manual-save build: Aqueduct `0D`,
   Sky Garden hub `4C`, Great Wall adjoining room `83`. A newly added source
   admission is still unqualified until exercised. Check both directions after fades settle;
   a correct source-sized fallback is not completed widescreen support.
3. Review all other admitted formats for their actual secondary-camera producer,
   repeating versus bounded layers, live VRAM animation, raster effects and
   authored camera window. Do not apply one parallax coefficient to every room.
4. Implement remaining scene formats, including cutscenes, Dark Space, flight,
   world map, inventory and Mode 7 compositions. Keep an explicit original-view
   reference until each replacement is visually qualified.
5. Re-run the same acceptance against the selected GaiaLabs content identity,
   including approved expanded maps and their actor, warp and collision changes.

## Acceptance per zone and phase

Use actual 1920×1080, widescreen, 1.5× extent and the player's selected filter;
retain an original-view comparison. Check movement in both axes and directions,
all expanded edges and camera clamps, secondary-plane phase, animated/raster
effects, actor placement and occlusion. Traverse entrances, exits, stairs and
story/ability transitions in both directions. Check menus, cutscenes and relevant
combat/boss phases. Teleports and prerequisite flags may set up fixtures, with
assistance disclosed; they do not establish natural progression.

Record each defect even if structural readiness, native CPU parity or the old
256-pixel field passes. Keep guest-state and foreground/object checks separate
from the intentionally reframed background. Visual review needs actual pictures
and motion evidence, not only screenshot existence, a list of admitted IDs or an
aggregate native coverage figure. Scope failures and untested phases explicitly.
