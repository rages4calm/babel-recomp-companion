# In-game scenery map, exploration and Itory horizons

November 13, 2026. This continues the [first full-game visual batch](VISUAL-FULLGAME-001.md).
The whole-game room/transition pass remains unfinished. No new native CPU
coverage or benchmark claim is made in this presentation batch.

## What works in game

The existing paused Companion has a fifth **Map** page. It shows actual room
artwork with unexplored areas hidden, a player position, zoom and pan. The clean
radar follows the player separately from the game's upper HUD. Both share a
content-bound persistent discovery journal and observe actual game frames;
neither writes guest flags, changes collision nor wakes offscreen actors.

- Keyboard: I opens Companion; M selects Map inside Companion. Arrows pan,
  +/- zoom, Home or C centers; Esc/M returns. Q/E cycle Companion pages.
- Mouse: drag the map; Center, minus, plus and Back are clickable.
- Gamepad: use the existing Companion gesture and page navigation. On Map,
  shoulders zoom, directions pan, Y centers and B returns to Items.
- Ctrl+M toggles the radar. Ctrl+R retains the SDK's reset meaning.

The host map canvas is currently598x336. It uses the SDK font and title-owned
stone/gold controls, without bundled game artwork. Scenery is decoded locally
from the supplied game's map, characters and palette. Original classroom08
combines two layers only after their alignment and publication are verified;
other qualified rooms currently use their primary scenery plane. This is not a
complete multilayer atlas for every room.

Unsupported geometry, fades, pending transitions and dialogue/menus suppress
the radar. The paused page does not run game frames while navigating. Inventory
art captures are speculative and explicitly suspended from exploration updates.

## Exploration policy

Discovery uses a camera-contained radius-eight static-geometry flood. It reveals
adjacent blocking cells without spreading through them; slopes, partial and
special collision classes are conservative. Dynamic actor occupancy does not
turn a static wall into walkable floor. This is not optical line of sight or
complete gameplay material classification. Source-exact secondary collision
replacement is supported where qualified.

The bounded journal lives under `saves/maps`, separately from game SRAM/states.
It remembers exploration across save reloads and rewind. Identity includes
content, room, authored crop/floor, dimensions and relevant source layout.
Qualified Original profiles use stable source-cache identities so a normal
scripted door change does not discard exploration. Received/unqualified profiles
retain strict content fingerprints. Writes are periodic/transition/exit based,
CRC checked and atomic; corrupted journals and unsafe path boundaries are refused.
One current atlas and eight discovery states bound memory use.

Player/scenery/radar work now. Enemy, chest, exit and Dark Space state bindings,
marker filters and discovery for unsupported rooms remain future work. Their
presence in GaiaLabs source does not establish them in this UI or every received
build. Retranslation and approved maps remain intended built-in main content;
the separate private received build is an integration reference, not a second
public edition.

## Additional widescreen fixes

Itory15/1A/1C now use a source-backed raster camera model, calibrated against all
225 captured BG2 scroll samples. Current/previous producer phases and fractional
drift are retained. The background uses its own row coordinates, repeats only
horizontally and stays finite vertically. A flat terminal color extends only
after all512 final-row pixels are proven opaque and identical. No repeated
mountain, invented floor or foreground-object leakage is used to fill margins.

Scenes1A/1C join the structural admission list:66 admitted formats still do not
mean66 visually approved zones. Every room, transition and phase remains the
owner's requested coverage target.

## Verification and exact scope

Private receipts live under ignored `.local/batch-001/visual-fullgame-002`.
They contain private inputs/captures and are not distributed with source.

| Check | Result |
| --- | --- |
| Original v8 retained-reference comparisons |56 pairs,10,080 candidate frame boundaries pass |
| Current Original v9 town smoke |110 supported frames; retained game/native snapshots match |
| Current v9 movement, rewind and process restart |11 player cells; discovery97→107, retains107 after rewind and restart |
| Current v9 paused Map controls |6 events retain identical guest cycles and full WRAM hash |
| Current v9 Itory1A/1C movement |Map ready throughout tested windows;10 guest/native snapshot sets match |
| Received reference v5 radar/full map |400 frames each,399 ready;77 explored; CPU/WRAM match retained v11 |
| Received v5 paused Map |5 events retain frame, cycles and WRAM; aligned classroom floor reviewed |
| Runtime unit checks |898 assertions plus12 corruption checks |
| UI/pointer checks with SDK font |2,421,775 assertions |
| World renderer checks |11,977,927 assertions, including causal rejection and flat-tail cases |
| Raster camera checks |999 assertions plus actual1A/1C captured packets |

Live mouse dragging was confirmed manually by the owner. Automated desktop drag
attempts were interrupted by concurrent input and are not counted as a separate
automated pass. Computer control was stopped after the preview.

Actual NVIDIA1080p smooth/1.5x Itory views were inspected on v6, with2600 matched
CPU boundaries across authentic entrance/movement routes. Later map-only edits
retain those renderer sources; this is linked historical visual evidence rather
than a new full GPU/campaign qualification. Current v9 adds conservative actor-
occupancy handling and a Companion key-repeat guard over the v8 comparison build.

Original v9 SHA-256:
`5b290e854742cb216f08c808e8693547b846cc7d6ccd99b31542dcae386b3f44`.
Received reference v5:
`672a1d1955858edbc4cc983487639ac2a9c8e2117658e6522cff91195bc88ddc`.
The received guest CPU remains interpreted, with stock plugins/native hooks
excluded. Original fallback/reference paths remain available.

Official SNESRecomp main checked at
`80a41241e39bfffd384506fbe7ca65b386e03050`, matching the pin. A reproducible
Windows `FORCEINLINE`/WinNT header collision is reported in
[upstream issue287](https://github.com/RetroPortingToolKit/snesrecomp/issues/287).
The local include boundary restores the macro without replacing vendor code;
the public ROM-free two-translation-unit test covers failure and protection.

Remaining work includes other layered scenery, later GreatWall86/course phases,
additional HDMA backgrounds, world-map natural entry/return, marker state and
all-room transitions. Prior malformed-entry surveys remain diagnostics. No
campaign-complete or fully native GaiaLabs claim follows from this batch.

Original Babel, GaiaLabs and existing collaborator credits/licenses remain.
No ROM, extracted game code/assets, private ZIP/BSO, states, soundtrack or game
screenshots are part of this source update.
