# Full-game presentation work, first batch

November 13, 2026. This work supersedes the eight-save-only follow-up. The goal
is correct widescreen and 1.5x presentation across every room and transition,
with GaiaLabs Retranslation and approved maps built into the main content.
This first batch does **not** qualify every zone or finish map integration.

## Original renderer

- Read the live, publication-paired camera producer instead of guessing a
  background's movement from its allocation size. Track, Vertical, Accumulate
  and WrappedDrift retain their actual ratios and raster offsets. A global
  camera model is deliberately deferred when per-band HDMA needs separate work.
- Use valid live authored camera windows to avoid exposing other floors stored
  in the same allocation. Great Wall85 has three 256-high courses in a 768-high
  allocation. A continuous assisted sprint through the upper course reaches86;
  later86 and the complete obstacle sequence remain unqualified.
- Keep the authentic field at the same pixel scale in unsupported rooms and
  transitions, rather than magnifying it to fill the taller presentation.
- Render Mode7 from captured per-line registers, VRAM and palette epochs. The
  stock perspective producer can extend vertically only after **all224 rows**
  and its terminal-row hold match. Otherwise retain the original-height band
  with explicit padding. Invalid/horizon depths never mirror invented ground.
- Viper55's declared cloud background now continues beyond terrain bounds in
  a separate background-only pass. Terrain and objects remain bounded; the
  original field is preserved. This policy is not applied to unrelated rooms.
- Source admissions0D/4C/83 bring the structural scene count to64. Admission,
  diagnostic room entry and an attractive still are not whole-scene approval.

Final Original candidate v7 SHA-256:
`21b4e1174be8ee93ee4533ad1999498b56b77dbd2b3bb84aaf680e03d8db0241`.
The older qualified graph016/effects025/WRAM021 inputs remain selected; no
regeneration, CPU promotion or benchmark campaign is part of this batch.

## GaiaLabs received-content reference

A separate, default-off build admits the exact privately supplied image. It
forbids stock generated/native inputs, stock address hooks and plugins, and
executes the received game **entirely interpreted**. It is a compatibility
reference, not a native GaiaLabs qualification or distributable game package.

The actual received classroom uses a768-wide primary map and384-column native
raster. Its new opt-in picture adapter presents598x336 at1.5x with square pixels,
retains actual dialogue/UI, and keeps fallback for unsupported scenes/forms.
Exact map identity, composition/OAM publication, player layout and raster guards
must pass. Boundary-connected solid filler cells become black through a
source-backed exterior mask; walls, collision, actors and doors are unchanged.
The earlier gray-void/green-bottom prototype remains a recorded failure.

Free control, dialogue and directional classroom tests have matching retained
CPU/WRAM traces. At the diagnostic native extent, the final GPU overlap differs
only in verified exterior filler cells changed to black. This establishes a
bounded classroom prototype, not correct presentation throughout GaiaLabs.

The received world map has also run with walking and turning. Its parchment
artwork should **not** be described as new or visually upgraded. The inspected
walkable-world-map module changes movement behavior. Destination entry/return,
natural campaign access and final custom rendering remain unfinished. The
provided original-game video is a comparison reference, not validation of our
renderer. Its media download was unavailable in this environment.

The received ZIP, patched ROM and BSO remain private. Matching public source
files do not establish an exact reproducible recipe for the complete dev ROM.

## Enhanced map foundations

The product direction is in [MAP-SYSTEM-DIRECTION.md](MAP-SYSTEM-DIRECTION.md).
New pure native helpers provide:

- `iog_map_scenery`: actual packed map/metatile/4bpp/palette decoding for the
  large map, without HUD, actors or a miniature screenshot of the game window.
  Integer sampling preserves proportions; no game assets are bundled.
- `iog_map_discovery`: bounded exploration with a required caller-provided
  visibility mask, content/layout/floor identity, and a checked portable format.
  Unknown geometry and markers remain hidden. Incorrect/corrupt state is refused.
- `iog_map_view`: scenery overview and clean radar compositors sharing discovery,
  with rational pan/zoom and discovered-only markers.

These helpers are independently compiled and tested; they are **not yet wired
into the game's map controls or persistent gameplay observations**. A collision
nibble is not an optical-occlusion rule: water, slopes, ledges and NPC occupancy
need explicit treatment. Do not feed an unrestricted visibility mask to claim
fog-of-war is finished. Floor/layout changes must not inherit another area's
exploration, and save/load/rewind need deliberate host-state integration.

`scripts/render_iog_map_preview.py` exercises the three native helpers together
against a private source packet. It produces an actual primary-scenery overview,
radar and checked discovery state using explicit caller-provided masks. Its
optional camera-rectangle/collision-zero modes are clearly labelled diagnostics,
not automatically earned exploration. South Cape's test exposes210 camera-
contained cells on a48x64-cell grid; unknown areas stay opaque in both views.
The full atlas is private and must not be published as a bundled game asset.

For an already captured local packet and explicit qualified cell masks:

```powershell
python scripts/render_iog_map_preview.py --compiler clang `
  --packet .local/capture/world.ppm --out .local/map-preview `
  --explored-mask .local/capture/explored-mask.bin `
  --walkable-mask .local/capture/radar-mask.bin --step 2
```

Masks are one byte per16x16 world cell in the selected authored crop. The
preview refuses outputs outside `.local/`; it does not authenticate an arbitrary
packet as the original game or turn supplied masks into earned exploration.

## Evidence and remaining work

Private receipts remain under `.local/batch-001/visual-fullgame-001/`:

| Check | Result and limit |
|---|---|
| Final Original v7 regression |56 pairs,10,080 candidate frame boundaries; sampled CPU/RAM/PPU/original-field equality with retained reference inputs. |
| Actual Original GPU views |Eight NVIDIA1920x1080 smooth/1.5x views captured and inspected. Not campaign or every-zone proof. |
| Mode7 actual v7 GPU |1500-frame bounded travel capture at NVIDIA1080p/1.5x;225 available original snapshot files match. Perspective rows validate at the capture. |
| Mode7 travel v6 |4000 frames,189 retained original snapshot fields match; full perspective extension validated at the captured travel pose. |
| World module harness |7,533,146 assertions; publication, safe fallback, windows, camera models, perspective refusal and background-only cloud bounds. Pixel transport is stubbed here. |
| Mode7 sampler |768 actual SDK PPU cases /420,100 checks; separate perspective arithmetic/phase checks. |
| Original visual decoder |107,085 ROM-free assertions. |
| Received adapter |40 paired classroom packets /1400 visible parts; no geometry/order/attribute/pixel/palette mismatches. Separate reference guard/configuration tests pass. |
| Scenery decoder |26,658,429 assertions /24 actual SDK PPU fixtures, including flips, pages, palettes, transparent pixels and VRAM wrap. |
| Discovery / map view |618 /1748 assertions: state roundtrip/refusals, fog, marker privacy, pan/zoom, buffer guards. |

The first32-room diagnostic survey exposed additional outdoor/per-band issues.
Its early probe metadata could predate map loading; the updated survey now
classifies visuals from capture-bound metadata and freezes its producer before
launch. Keep invalid teleport poses and failed room entries visible. No survey
entry counts as a visual approval.

A second frozen32-room v7 survey finishes all entry checks;31 have matching
capture-bound scene data and living in-bounds players. Only18 have an
unobstructed collision anchor, which still does not qualify playable quest
state. Scene49 refuses the expanded adapter and stays unverified. All four
contact sheets were reviewed: thin interior edge strips and apparent spare room
pages prompted a fixture audit. It found the survey's uniform incoming camera
override22 incorrectly forcing512x512 windows even into256-wide rooms. Those
captures cannot establish production renderer defects. Authentic inbound warp
windows must replace that test setup before qualifying those rooms.
Verified lossless compaction keeps this survey below100MiB.

The corrected producer now requires explicit inbound recipes, checking both
their extracted-source provenance and literal records in the exact Original
ROM. Four targeted retests use authentic33/2D/2E/39 entrances: the thin wrapped
edge in33 disappears, the ship rooms show the correct top floor, and39 is
framed on its correct lower floor. All four paired captures match the requested
scenes. These bounded stills do not qualify their movement, stairs or quest state.

Remaining work includes per-band HDMA background phase, finite-height horizon
plates, further room/transition/combat phases, GaiaLabs content and map controls,
and reliable exploration/marker observations. [Issue6](https://github.com/rages4calm/babel-recomp-companion/issues/6)
stays open. Preserve interpreter/original-view and the previous runnable build.

SNESRecomp main was rechecked at
`80a41241e39bfffd384506fbe7ca65b386e03050`, matching `framework_pins.txt`.
No vendor replacement was needed. All Babel/GaiaLabs and existing contributor
credits and license notices remain in place.
