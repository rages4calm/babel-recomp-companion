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
These checks cover the tested routes and elevator phases. The later
[connected quest tests](#angel-village-and-linked-story-routes) also cover
both keys and the Memory Melody.

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
had an inherited 28-pixel difference against stock on its last native
scanline in one tested pose. [Batch 026 fixes that edge](#bottom-edges-lower-great-wall-and-map-dismissal).

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
defused the bomb, rescued Erik, walked out and reached the reunion camp in
Seaside Tunnel. The replay then walked around camp, opened the mushroom
dialogue and reached the second camp phase through the ordinary story
conditions. A separate test reached that phase with the dialogue open and
restored it in a new process. The v23 build loads the configured translation
before the restored dialogue reads from it. The replay closes the message
and stays in Seaside Tunnel. The following batch verifies the Angel Village
arrival through the rest of that conversation.
The widened combat capture's 13-pixel difference on the last stock row comes
from the reconstructed actor parts starting at that edge. The widened renderer
draws those parts into the expanded picture. The stock OAM publication culls
them at the edge of its own field.

The ending replay defeated both Dark Gaia forms, advanced into the epilogue and
reached the Changed World sequence. Earned checkpoints then linked the return
to the epilogue, the following cutscene, credits and final school scene. The
credits advanced on their original timer. The first segment used the previous
dialogue pack with this binary, and the later segments used the current pack.
The replays use an SDL virtual controller. Start-to-credits campaign coverage
and physical controller testing remain open.

## Angel Village and linked story routes

V25 clips the green storage rows below Angel Village's southern wall for
three witnessed stock layouts. Before-and-after frames cover entering from
Seaside Tunnel and the world map, returning from the annex, and walking
through the village. The original picture, expanded side scenery, HUD and
radar matched. The neighboring cave frames matched across the full output.

- **Angel Village and Watermia.** The translated Seaside Tunnel checkpoint
  now proceeds through the actual Angel Village arrival and cave doors.
  Separate assisted starts verify Ishtar's final answer and Kara's rescue.
  The linked party reunion and Neil dialogue lead to the original scripted
  trip, Watermia's opening narration and Luke's house. Controller routes
  also exercised free walking between the two world-map destinations.
- **Diamond Mine.** Stock interactions awarded both keys in the Morgue and
  Nest on v23. Preparations used a staged room arrival, nearby player
  positions and Freedan. On v25, the foyer script consumed both items,
  opened the lock and the controller passed into the rescue room. After a
  staged position near Sam, controller attacks cut his chain, dialogue
  awarded the Memory Melody and Will walked back into the foyer with it.
- **Pyramid to Babel.** An earned Mummy Queen win checkpoint carried into
  the statue ceremony, Kara's dialogue and Dao. The fixture supplied six
  earlier hieroglyph flags and the earlier Jackal event. A linked controller
  run took Neil's Mode 7 flight into Babel and reached its lower corridor.

These are bounded, checkpoint-linked replays with a virtual controller and
a 598×336 square-pixel 1.5× presentation. The stock world map fallback passed
on the same production build.

## Prison, Watermia and Babel continuation

Batch 022 extends three controller routes using original game interactions.
The replays retain the 757-entry dialogue pack and use the square-pixel
1.5× full picture, including the original framing during authored fades.

- **Edward's Prison.** From a staged prison arrival, Will examined the bars,
  moss and chain ball, then waited for the bread and the flute dialogue.
  The controller pulled the gem into reach before collecting it. The pig
  sequence awarded the Prison Key, and Will equipped it through the original
  inventory, opened the bars and walked through. Linked exit replays then
  reached both the Aqueduct entrance and the next room, where a controller
  attack reduced the room's enemy count. The starting fixture carried boosted
  player stats. A separate setup supplies the story prerequisite for the
  later Aqueduct portal. From there, controller input enters Dark Space,
  advances the statue dialogue, earns Freedan and exits into the Aqueduct
  in that form.
- **Watermia.** The route from Luke's house used ordinary doors, boards and
  the ladder to Lance's father. Talking to Lance, his father and then Lance
  set the party prerequisite. Following the real exit and raft back to
  Luke's house led to the birthday and earned Lance's Letter. A separate
  departure replay equipped and read the letter, left Watermia through the
  southern boardwalk and walked to the Great Wall entrance on the world
  map. The first Great Wall stair leads into the lower course with its own
  camera window and parallax.
- **Babel.** The linked lower-corridor route triggered the laser and picked up
  the Crystal Ring. After the stock fanfare finished, the controller equipped
  it and crossed the lasers, took the stairs and advanced the full Kara
  conversation. The adjacent room's door was tested in both directions.
  The route reaches the Dark Castoth rematch, with the live starfield visible.
  A replay from that earned checkpoint defeated both hands and the head
  with inherited player stats. The original victory script returned the
  player to Babel, where the controller verified movement.

## Sand Fanger, Babel and Solid Arm

V27 uses the captured band phase for the verified upper Great Wall
approach layout. On the west return from the Sand Fanger arena, the
farther-back camera previously shifted the sky against the original
field. Settled and moving captures dropped from 11,521 and 12,464
different gameplay pixels to zero. Five neighboring, fade and menu
captures stayed byte-identical.

- **Great Wall.** From an assisted original room arrival, controller input
  passed through the authored west door, took both drops and reached the
  active 40-HP Sand Fanger. A player-only combat setup then defeated it,
  earned the original power-up, advanced the Mystic Statue ceremony and
  climbed the revealed ladder to the east passage. A separate controller
  replay earned the first Necklace Stone. From an earned victory checkpoint,
  both upper exits and the inventory round trip passed. Lily and Lance's
  reunion led back to Watermia. That reunion checkpoint lacked the stones,
  so their consumption remains unverified.
- **Babel.** From the earned Dark Castoth return, linked controller replays
  went through the original stairs and light elevators, defeated Dark Viper,
  both Dark Vampires, Dark Sand Fanger and the Dark Mummy Queen and verified
  their returns. The final summit fight and second lift ran on v27. The
  original dialogue with the travel spirit then returned the player to Dao.
  These runs retained earlier checkpoint stats and used no further outcome writes.
- **Solid Arm.** From that Dao arrival, controller input walked to Gem and
  handed in one Red Jewel. The fixture staged 49 previously given jewels
  and their completed reward tiers. The hand-in reached 50 and opened the
  Jeweler's Mansion. A player-position assist shortened the mansion approach,
  then controller input took the actual door and advanced the original
  introduction to active combat. A separate assisted v27 combat replay
  defeated Solid Arm and returned to Babel through the stock script.

The linked routes use virtual controller input and a 598×336 square-pixel
1.5× output. The stock map fallback passed on the v27 production build.

## Solid Arm through the ending

Batch 024 continued on the same Original v27 build and 757-entry dialogue
pack. From the linked active Solid Arm save, D-pad movement positioned Will
at the west side of the arena and face-button attacks took the boss from
40 HP to zero. The original farewell and return script sent Will from the
Jeweler's Mansion (`EA`) back to Babel (`E3`). The replay then verified
movement on both axes in Babel. The save retained its earlier Strength and
Defense boosts. This fight and return used controller input without new
memory writes.

The same earned return save also linked through Babel's upper stairs, the
father's final Mystic Statue sequence and the court on the rooftop (`E4`).
The rooftop checks exercised the spirit conversations, Kara's fusion, the
flight (`E7`) and the original entrance to Dark Gaia's arena (`E8`). On
that same chain, controller movement and attacks defeated both Dark Gaia
forms (20 and 40 HP) as Shadow and earned the original epilogue transition
(`E8` → `E5`). The post-Queen branch repeated the summit and both fights
from batch 023's rematch route and supplied the earned epilogue checkpoint
for the ending replay. Both branches retained boosted player stats.

From that earned epilogue, the game progressed through the Changed World
map (`90`), the return to the epilogue (`E5`), New Babel (`89`), the full
credits (`F7`) and the final school scene (`F0`). The credits ran unskipped.
The replay held on the final school cast and visible END card after the
school actor reached its last scripted step. These runs used virtual SDL
controller input through the game's normal input path.

The active arenas, projectiles, room transitions and authored story framing
were reviewed at square-pixel 1.5× on a 598×336 widescreen canvas. The
rooftop, comet flight and final encounter kept their authored boundaries.
All 14 sampled views on the Babel-to-Dark-Gaia branch matched the original
picture in the source field after masking the Companion HUD. At live
Solid Arm and Dark Gaia checkpoints and an ending classroom checkpoint, the
default, forced-interpreter and reference-pixel paths produced the same scene
history, complete widescreen picture and all seven compared guest state fields.

## Great Wall approach and Mode 7 destination menu

- **Mode 1, Great Wall (`82`, `83`).** The upper approach now keeps the
  mountain layer aligned with the captured game raster. Two controller samples
  in the upper route went from 11,285 and 7,047 differing gameplay pixels to
  zero in the original field. The fix applies to the observed upper-floor
  layout. After a source-verified entry setup, the controller walked through
  the west door and returned through the east door. The staircase, both door
  views and the picture through fallback kept square-pixel 1.5×. The
  reference-pixel replay matched the full captured picture and all seven
  compared guest-state fields.
- **Mode 7, stock destination menu (`FE`).** When the map opens its Mode 1
  dialogue band, the Mode 7 portion now retains the top 56 rows on the 1.5×
  view. The new extension requires every captured map-row transform to match
  the original camera formula. On the verified opening frame, 23,912 nonblack
  pixels were restored above the original field and all 167,440 lower pixels
  stayed exact. The same SDL virtual controller route exited Itory, chose
  South Cape and moved in town through both the extended renderer and the
  explicit split fallback. The guest state matched.
- **Other phases.** Cold prologue and storybook skips, Sky Garden's flight,
  ocean crash and descent, and the Dao-to-Babel flight were compared on v27
  and v28. The sampled pictures and recorded transitions matched. The tiny
  Mu twins bottom-edge difference reproduced in one active pose on v28.

The combined Original v28 build uses the 757-entry dialogue pack. Checks used
headless SDL virtual gamepads and inspected the 598×336 square-pixel 1.5×
picture. The production launcher profile also booted with MSU-1 enabled.

## Bottom edges, lower Great Wall and map dismissal

- **Mu twins (`67`) and western Sky Garden underside (`54`).** The original
  object writer culls actor sprite parts that start on the last displayed
  row. The renderer now applies that boundary inside the original picture
  in these two scenes, with the parts still drawn in the expanded area.
  Pixel differences on the original bottom row dropped from 13 to zero in
  Mu and 28 to zero in Sky Garden. The tested Sky Garden route returned
  to `53`, and the east route also passed (`4E` to `4D`). Seaside Palace's
  `5D`–`5C` door round trip served as a control.
- **Lower Great Wall gallery (`82`).** The existing captured mountain phase
  now covers the measured lower-gallery camera bounds. At the west and east
  Necklace Stone approaches, the original field's differing pixels fell
  from 139 and 328 to zero. The neighboring exit and an `8B`–`8A` door round
  trip kept the same scale across the transition.
- **Stock Mode 7 destination menu (`FE`).** At dismissal, the PPU begins with
  Mode 1 register state, then the stock HDMA producer selects full-height
  Mode 7 before drawing. V29 captures that verified transition. The formerly
  narrowed frame restored 118,935 nonblack pixels around an identical
  original 256×224 image. The four adjacent frames and the earlier menu
  opening capture matched v28. Controller input reached South Cape with the
  renderer enhancement and with the explicit map fallback. Sky Garden's
  flight, ocean crash and descent and the Dao-to-Babel flight also matched
  v28 in the sampled pictures and recorded guest state.

All checks used the Original-based build and virtual SDL controller input.
The sampled 598×336 output was inspected at square-pixel 1.5×. Seven guest
state fields matched in the tested comparisons. The renderer reference and
interpreter remained available and were replayed across the western Sky
Garden transition. The production launcher profile booted with MSU-1 and
the 757-entry dialogue pack.

## Prison, Babel victory waves and Angkor vision

Original v30 recognizes the stock two-layer horizontal wave in the South
Cape prison arrival (`0B`), the Babel entrance after the final Mystic Statue
(`DE`), and the Dark Vampires victory in Babel (`F4`). These effects could
previously fall back to the centered original field. The renderer validates
the original HDMA producer and each captured row. It continues the wave
outside the original field only when the captured source repeats. It keeps
the authentic foreground, stars and room boundaries.

On v30, the other rematch wave layouts kept their original fallback. Test builds that
accepted them intermittently alternated between the expanded and original
field. These layouts need consistent frame-to-frame validation.

The linked Dark Vampires replay kept all 124 victory-wave frames expanded
and returned to the Babel middle floor (`E0`). The sampled original field,
full pixel-reference picture and seven guest state fields matched.

The Spirit Guide's Angkor Wat transition (`BF` → `C0` → `BF`) also keeps
the temple at the correct extent during the measured mosaic phases. The
widened tile chunks align to the original mosaic grid and preserve the
Mode 7 vision's existing renderer. Unknown raster layouts still use fallback.

The prison ripple and the Babel entrance ripple match the captured original
gameplay field at 1.5× after masking the separately placed HUD. Virtual
controller input continued through the prison into the Aqueduct and from
the Babel entrance to the rooftop. The Angkor route used an assisted stock
arrival followed by controller dialogue input. Seventy outgoing mosaic
frames kept the wider picture, and the sampled Mode 7 vision and temple
return matched v29. The tested reference-pixel pictures and seven guest
state fields matched. A forced interpreter replay also passed for the
Babel entrance route.

The headless checks used SDL virtual controllers and 598×336 square-pixel
output. The isolated launcher profile booted with the 757-entry dialogue
pack and MSU-1 enabled.

## Babel victory waves, Ship Dream and Sky Garden flight

Original v31 keeps the original HDMA victory wave in all four Babel
rematches that use it (`F2`–`F5`). The alternate stock scroll buffer moves
some scanlines farther than the prison and Babel arrival effects. The
renderer now verifies the full rematch raster against the actual table
without applying the arrival displacement limit. Dark Sand Fanger's
last two BG2 lines keep their separately verified original values.
Each linked controller replay kept all 124 wave frames wide and returned
to the Babel middle floor (`E0`). Each still has a single setup frame before
the wave that uses the centered fallback. The sampled Castoth setup frame
is visible and uses a different HDMA table from the victory wave.

The Dark Mummy Queen (`F6`) uses a mosaic fade. Its original grid stays
aligned through all 56 frames, including the stars, and the replay returns
to the upper floor (`E3`). The Ship Dream (`2A`) uses the same grid
alignment with its own verified room and iris settings. Both the 75-frame
Dream arrival mosaic and the 75-frame return mosaic in the Wrecked Ship
cabin (`2D`) now stay at 1.5×. The return retains the cabin's per-line
color effect and exposes its real side scenery.

The approach to the Sky Garden Mode 7 crash (`58` → `59` → `58`) retains the
current hardware actors when an OAM upload arrives without a paired actor
composition. The extended area uses the verified cloud layers. The HUD uses
the same placement and size as the surrounding frames. Four alternating
fallback frames are restored. The sampled Mode 7 crash and return images
match v30.

Headless SDL virtual-controller replays checked all five Babel exits, the
ship-to-Dream-to-cabin route and the flight through the crash and return.
The flight and ship routes used assisted checkpoints. The sampled 598×336
square-pixel pictures matched their renderer references. Guest state fields
matched across the tested checkpoints. The forced interpreter and renderer
reference also matched the v30 Dark Space return to the Aqueduct. The stock
Mode 7 map selection replay still reached South Cape with the same picture
and guest state.

## Babel victory setup, Dao and Solid Arm

Original v32 keeps the opening frame of the Babel victory effect wide in
all four rematches (`F2`–`F5`). The renderer verifies the outgoing scroll
table, then preserves the incoming BG2 raster and stationary foreground.
Dark Viper uses its separately verified held scroll value. Each linked
controller replay stayed wide through the setup and all 124 wave frames,
then returned to the middle Babel floor (`E0`) through the stock fade.
The expanded stars and actors were inspected at 598×336. The four setup
captures matched the original PPU field outside the scaled HUD.

Two more Mode 1 mosaics keep the same scale as their neighboring rooms.
The Spirit Guide's arrival in Dao (`E3` → `C3`) preserves the heat window
through all 75 reveal frames. Solid Arm's defeat (`EA` → `E3`) preserves
the purple color math and narrow arena through all 70 exit mosaic frames.
Both controller runs used linked checkpoints. Sampled guest state and
interpreter pictures agreed, and the shipping path matched the original
PPU field outside the scaled HUD except at Dao's active window edge, where
the v32 optimized and scalar pixel samplers differed.

The Mode 7 controller checks covered map-to-Mountain Temple, map-to-Dao
and back, and the stock destination selection into South Cape. The sampled
598×336 pictures and guest state matched v31. The stock split fallback
still reaches South Cape, and unsupported intervals such as fully black
loading between rooms can still use fallback. Six earlier frames in the
v32 Dark Castoth fight used the visual-object fallback.

## Dark Castoth defeat and neighboring mosaics

Dark Castoth's six defeat frames keep their starfield, actors and square-pixel
1.5× framing. The stock OAM writer fills the end of the sprite table with
overlapping copies of one tile during the defeat animation. The renderer
checks the exact Castoth actor state and published OAM before drawing one
copy of that tile. Unverified actor layouts still use fallback. The linked
controller replay covers the defeat, the complete victory wave, and the
return to the Babel landing. The six recovered frames match the stock PPU
field outside the scaled HUD. The three other wave rematches were replayed
with their existing coverage intact.

Three more Mode 1 mosaics stay wide. The Jeweler's Mansion reveal retains
its original fog for all 75 frames. The ship lower deck retains its color
math for all 70 frames before the Dream. The return from Solid Arm to the
upper Babel landing keeps the side hall visible through all 75 reveal frames.
Linked controller replays covered both sides of the transitions. The
black loading phases can still use fallback.

Dao's window edge now samples the original leftmost pixel of a mosaic block
even when the window clips that pixel. Both optimized tile depths involved
in Mode 1 received the correction. The default and scalar Dao captures match
byte for byte after the fix. The local SNESRecomp delta leaves the SDK pin at
`22c01ef1` and is tracked in [SNESRecomp #292](https://github.com/RetroPortingToolKit/snesrecomp/issues/292).

An exact v33 replay with the expanded GaiaLabs pack followed the linked
New Babel checkpoint through the credits and visible END screen. The
38,000-frame controller replay reached the same scene boundaries as
the prior ending receipt. Separate controls rechecked the Dark Mummy Queen,
Ship Dream, Sky Garden flight and stock map route into South Cape at 1.5×.
These runs started from checkpoints.

## Prison letter, Crystal Ring, Diamond Mine and South Cape house

Original v34 keeps four previously centered intervals at square-pixel 1.5×.
The prison letter scene stays wide for 41 recovered frames, the Crystal Ring
fanfare for 35, and the Diamond Mine prisoner conversation for 49.
These scripts upload objects outside the ordinary actor capture. The
renderer retains the live PPU actors in the original field and extends
the verified room scenery after checking the current layout and camera
against the preceding paired picture. South Cape's ground-floor reveal
keeps its original mosaic and framing for all 75 frames. Other unverified
actor and raster layouts retain fallback.

The four stock-text A/B replays preserved the original visible field
outside the scaled HUD and matched 140 checkpoint payloads across the
pairings. The translated final build also reached South Cape from a fresh
boot without a checkpoint or game-state edits. Its classroom-to-town
transition, final 598×336 picture and sampled guest state matched v33.
Separate linked replays checked Mu, the Dark Space return to the Aqueduct,
the Spirit Guide's route into Dao, and Neil's Cottage.

Fresh saves produced by the repaired scenes continued through the prison
gate into the Aqueduct and through the Crystal Ring equip sequence and a
Babel middle-floor door round trip.

## Save-resume framing and connected route regression

Original v35 keeps the first visible frame wide after loading in six
verified Mode 1 layouts. The ordinary sprite publication arrives one
frame later. The renderer checks the observed room and camera against
the incoming composition, extends the verified scenery, and uses the
live PPU actors and HUD. Unsupported layouts and modal restores can
still use fallback.

The exact build passed a controller route from cold boot to the
classroom, out to South Cape, and back through the classroom door with
no save-state or story-flag setup. The full sampled 598×336 picture,
scene timing, and music transitions matched v34. Further linked
replays covered the Mu approach, Dao to the Jeweler's Mansion, and the
walkable and stock world maps. The Mu replay gained the first loaded
frame and matched the recorded gameplay and later picture.

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
