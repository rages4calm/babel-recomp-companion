# More room coverage, received world-map rendering and map controls

November 19, 2026. Continues [batch003](VISUAL-FULLGAME-003.md). This is a
bounded presentation/integration batch, not whole-game approval or completion
of the GaiaLabs main-content import.

## Neighboring Great Wall rooms

The calibrated raster model now covers rooms `82/83/87/88/8A/8B`, including the
type1F two-band scenery in `8A`. Dimensions and descriptor types are read from
the supplied ROM and checked against actual raster samples. Room82's expanded
green/missing-background strip is fixed. The other rooms retain their correct
band-specific phase, finite vertical artwork and authored bounds at1.5x.

Source/ROM-verified entrance recipes avoid the earlier camera22 survey problem.
Room82's intro is cleared through normal input; no flag write dismisses it.
Movement and settled natural `83↔85`, `87↔88`, `8B↔8A` transitions are tested,
alongside extended room87 movement/return toward86. Six full room pictures,
32 transition presents and two actual NVIDIA1080p smooth-xBR/1.5x captures are
reviewed. All tested route frames retain598x336; transition fallback remains.

The comparisons cover7,150 CPU boundaries and287 sampled guest/PPU/native-field
results. They match retained003. Changed host-picture pixels are recorded
separately; matching guest framebuffers do not imply host-picture parity.
The69 admitted scene formats are structural capability, not69 approved zones.
Room8A's boss phases/victory and later branches remain unqualified.

## GaiaLabs world travel at1.5x

The received reference previously centered its384x224 world-map field inside
the larger host frame. A new read-only adapter reconstructs the surrounding
Mode7 plane, using the actual225 captured register/palette rows and supplied
VRAM. The center384 field stays at the same pixel scale, preserving its exact
OBJ, labels and color composition. No BSO camera code or game artwork is embedded.

The adapter verifies the exact received content identity. Its perspective
producer uses that build's source/ROM-verified divisor, increment, angle and
trig-table locations; all224 generated matrix words and the terminal hold must
match captured hardware state before vertical extension is enabled. Unknown
nonuniform producers retain the native-height band/padding. Unsupported windows,
subscreens, raster layout changes, incomplete capture and unverified content
retain fallback. Disabled window-selection bits are distinguished from active
clipping, and the ignored Mode7 BG3 enable bit is allowed.

Actual walking/turning passes165/165 ready frames with matching traces and36
sampled guest/PPU/APU state fields. Two actual NVIDIA1920x1080/1.5x world-map views
are inspected,150/150 ready frames each. Ground, finite black horizon, expanded
margins, label and player scale look coherent. This retains the existing art;
it does not claim new world-map artwork or manually tested physical buttons.

## South Cape arrival fixed in the integration preview

Normal world-map confirmation enters South Cape through the guest's own
QueueMapChange path. An850-frame comparison matches the retained reference,
but natural return is blocked: the received widened town uses expanded scene
coordinates while the walkable-world-map module retains the stock arrival.

The current public source reproduces the mismatch. All3072 stock South Cape
cells appear in the expanded map at a256px horizontal offset; its world entry
still uses X=`0178` rather than the expanded layout's `0278`. This is a content
coordinate problem, not an affine renderer defect. It is reported with public
source links in [IOGRetranslation issue37](https://github.com/Azarem/IOGRetranslation/issues/37),
without private ROM, ZIP, BSO, states or screenshots.

Companion's opt-in `IOG_RECEIVED_MAIN_CONTENT` profile now resolves the South
Cape destination to X=`0278` before the original scene loader uses it. The
adapter requires the exact received image and verifies the original handler,
call site, actor context and destination. The base ROM remains byte-identical.
Original and the strict received reference exclude the correction.

The corrected preview passed an 850-frame route from the retained world-map
checkpoint. Confirming South Cape arrived at (632, 64), and walking north
returned to the world map through the town's normal exit. Nine fields before
entry matched the strict reference and the route applied exactly one correction.
The two earlier candidates refused the correction because their actor context
was wrong. Their failed receipts are retained. The final guard passed 169 checks.

Three NVIDIA OpenGL captures confirm arrival, movement on both axes and return.
South Cape still uses the same-scale fallback: its 384×224 field sits inside
the 598×336 canvas and leaves black borders. The AREA panel is Companion's
exploration radar. The preview captures use nearest filtering. The Edward
Castle route matches the strict reference across 930 frames and 27 sampled
fields with zero South Cape corrections. The tested return from Edward Castle
remains blocked in both builds.

Full main-content integration still needs coherent Retranslation, expanded maps,
actors and destination data. Changes to another map require that map's own
coordinates. The corrected received preview is private and the Original remains
the default test build.

## One local map and controller configuration

Our local scenery map/radar remains the primary design; GaiaLabs world travel
and Retranslation remain the main-content goal. The received build now routes
its verified local-map Start command to our Map when a qualified map is ready.
The exact input-handler/music-helper hashes bind the RAM meanings. Pause/debug,
world travel, dialogue, game-over, music transitions, unsupported geometry and
unknown content retain original input/fallback. No guest instructions or flags
are patched. Held Start is consumed until release.

On our Map, **Select** opens Controls. Use directions to choose a row, Left/Right
or A to change, and B to return to the map. Conflicting assignments swap; Back
stays available. The footer reflects the current SNES logical buttons. Keyboard
Tab opens the pane; Esc returns to Map before leaving Companion.

Original keeps shared mod/settings persistence. The mods-off received reference
now uses a24-byte versioned CRC preference record under guarded `saves/maps`.
Writes are atomic, invalid records are refused and save failures are shown as
session-only settings. The record contains only radar preference/button IDs,
with no guest save data. Guest save/state files and quest flags are untouched.

Actual SDL virtual-device tests exercise the physical mapping path, Controls,
remapping, return and guest resume in both builds. Original's78 and received's29
modal events retain guest cycles/WRAM, and seven sampled guest fields match
their references. The received preference survives a new process: the reloaded
Map footer shows L/A zoom after remapping zoom-in to logical A. These are virtual
controller events, not a new manual physical-controller playthrough.

## Checks and evidence limits

Private receipts remain under `.local/batch-001/visual-fullgame-004`.

| Check | Result |
| --- | --- |
| Final Original retained comparisons |56 pairs /10080 boundaries pass |
| Wall raster / object / world harnesses |81238 /107085 /12112004 assertions pass |
| Wall fault test |Removing the new cluster profiles is detected |
| Received Mode7 module |261150 assertions with actual detached PPU color rendering |
| Controls / UI |792 /2431229 assertions pass |
| Preferences |32 corruption cases, Windows junction refusal and atomic cleanup pass |
| Pinned received input |70 hash/context/persistence checks pass; synthetic ready-state seam disclosed |
| Reference isolation |Actual configure, preprocessor and observer phase guards pass |
| Shared host input-source reader |Fresh targeted test passes |

The SDK pin remains22c01ef1; unchanged compiled core tests reuse batch003 rather
than repeating its full suite. Graph016/effects025/WRAM021 are unchanged, with
no new native guest CPU coverage claim. Final renderer hashes link to the
actual GPU-tested earlier candidates; this is not a fresh final-build GPU pass.

Final Original v3:
`b66de5e3d2546d18b8a4d1bbc26ec74d2abd16ee43a500487fb0a5290cee2f0e`.
Final received reference v4:
`d07059a08de024a835b56a11b3ea7c3eea91e967f59428a941045335dc9f0cc2`.
Corrected integration preview v3:
`2fdca4ef5dc459577b4424520837b7d5ce5a14683e93b017ce51bfaaa0fdab94`.
The received guest CPU remains interpreted; stock plugins/native hooks remain
excluded. Original and received source identities, saves and evidence stay
separate internally. No edition picker or new public release is introduced.

Remaining work includes coherent main-content import, more rooms and boss
phases, marker state and campaign transitions.
Fallback, earlier runnable builds, all Babel/GaiaLabs/collaborator credits and
licenses remain. Private/game-derived inputs and validation media stay untracked.
