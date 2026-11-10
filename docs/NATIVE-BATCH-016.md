# Native batch 016: independent world view

November 9, 2026; source baseline `23090cc`. This work separates the visible
world rectangle from the original gameplay view. It does not claim complete
native game/audio coverage, a campaign playthrough or a replacement GPU engine.

## Implementation

The opt-in development adapter uses `IOG_WORLD_RENDERER=1`, with
`IOG_WORLD_VIEW_EXTENT=1`, `1.25` or `1.5` (default). It keeps simulation at
256×224, restores the ten stock culling operands, and leaves visibility flags,
the guest candidate list and the game camera under original game control.
The legacy/reference renderer remains available when this environment option
is absent. The previous expanded-culling implementation remains experimental;
its batch-015 failures are retained rather than retroactively reclassified.

A separate read-only visual decoder retains full coordinates and original
depth order. Composition observers run at `$83:C714` before the original
producer and `$83:C789` after it. The latter is the common PLP/RTL return,
not `$C76C`, which starts the actor loop. Both compiled and interpreted paths
use the same observational instruction boundaries. The host pairs the saved
producer inputs with an actual NMI OAM upload only when all 544 bytes match.
Loads/resets and unpaired uploads invalidate the visual publication.

The host now distinguishes the original raster size from presentation size.
The additive, optional `presentation_geometry` callback accepts a bounded
2048×512 output while raw captures, rewind and speculative buffers retain the
actual raster dimensions. A missing callback preserves the previous behavior.
For square pixels at 16:9, the three world canvases are 398×224, 498×280 and
598×336. Additional rows and columns are reconstructed from real map data;
increasing the extent does not stretch the original field.

The picture adapter captures each real line's registers and bounded changed
memory epochs after that line's HDMA/IRQ. Detached picture drawing reuses the
pixel algorithms on owned state without executing another CPU/HDMA/IRQ pass.
Terrain uses uploaded native entries in the original view and decoded map
entries outside it. BG3 is captured from actual scanout and composed at a
separate HUD scale. Character artwork remains original; this is a CPU picture
adapter presented through the existing host, not a Vulkan/DirectX world renderer.

Support is deliberately finite: verified stock-USA town 1 and Aqueduct 0C,
ordinary three-form player graphics and validated actor/manual formats.
Unsupported rooms, active world windows, mosaics, interlace, mid-raster character
uploads, capacity exhaustion and missing camera/OAM publication use the
authentic field. Fallback is not counted as successful expanded-world rendering.
No unimplemented zoom control is added to the launcher.

## Source and protocol checks

SNESRecomp main `e9c207322c148eccc8a679b72d8b005d0d95d31c` includes merged
PR 269's finite-interpreter-owner correction after non-local guest returns.
Its two-file delta was inventoried and selectively integrated, preserving
Babel changes and the local paired-call bank-wrap correction. That separate
upstream issue 267 / PR 268 remains open at this check.

The two bridge configurations each pass 447 checks. The complete SDK gate
passes 839 tests, two skipped, with source hashes unchanged. Focused guarded
host tests cover a page-protected 256×224 input, output through 2048×512,
invalid capacities, raw captures/rewind/speculation, and the absent-callback
path. Three intentional bad source-size/pitch variants are rejected.

The regenerated graph has the same structural manifest as 014/015: 415 roots,
1,333 contexts, 1,248 eligible bodies and 85 LLE variants. All 48 bank outputs
were emitted with the new observation hooks; this is not an unchanged-source
or cache-hit claim. The 6,757 native continuation contexts / 27,028 aliases /
140 opcode bodies reproduce the prior effects source byte-for-byte. No new
guest native-coverage percentage is inferred from this rendering work.

ROM-free checks execute the actual visual decoder and world/host glue, covering
malformed chains, coordinate/order/pixel rules, exact upload pairing, read-only
guest state, camera/epoch refusal, repeated presentation and fallback capacity.
They complement actual game captures; they do not replace them.

## Initial actual execution

Candidate `52b8c87d0d5706f03d22ec9b0707ba3dd062bd6aa32609fe181be4f00a332b80`
passes the initial 800-frame original-width / 800-frame Aqueduct world pair.
All recorded guest/device/full-APU bytes, traces and ordered watched writes
match. The per-frame authoritative resume PC, CPU registers/flags, guest and
master clocks, real HDMA/IRQ counts and ten culling operands also match exactly.
The final world output is genuinely active; 567 frames render the world and
233 use fallback during setup. At final frame 800, all 57,344 original central
texels match the narrow field. Independent host and title picture writes match.

The first candidate's gameplay checks passed but its world-positive gate
failed: it rejected window-participation bits even when no window was enabled.
The corrected gate checks actual participating window enables. That failure
and a first screenshot-frame mismatch are retained. Comparing equal actual
frames resolves the latter; no image normalization or visual waiver is used.

The broader frozen plan passes 73 fresh captures / 142,400 frames / 502 snapshot
sets: 42 view comparisons over 32 assisted routes. One exact reused 800-frame
baseline brings the referenced cohort to 74 captures / 143,200 frames; it is
not counted as fresh execution. All strict guest/APU/CPU/
clock/policy/output checks pass. Fourteen final views actually use world
rendering, with 9,978 ready frames; 28 unsupported views remain classified as
fallback. Both town/Aqueduct grids cover 16:9 and 21:9 at all three extents.
Moving town is ready 599/600 frames per view. Sixteen retained original-width
015 controls match byte-for-byte; previous expanded-view captures are not used
as original-width references. Earlier original-writer receipts retain their
historical source identity; this is not a fresh campaign/writer qualification.

An independent official-capture-loader review binds all 74 referenced captures
and 517 compiled-source hashes. Loss counters are zero; all 42 pairs retain
exact per-PC interpreted costs, native-site counts and CPU/master totals.
5,458 of the existing 6,757 canonical continuation sites are actually observed
in this finite cohort. This is not a new selection, completion percentage or
whole-campaign claim. The raw APU comparison receipts remain bound separately.

Six actual NVIDIA 1280×720 captures / 3,260 frames pass transport and geometry,
including camera movement and separate SharpPixels/xBR looks. Nearest pixels
match actual GPU readback at every source texel. A one-pixel viewport bar at
598×336 is preserved, not stretched away. The inherited generic viewport
oracle's first failure is retained; its corrected check follows the explicit
new viewport contract against the same original image bytes. The single
offscreen 4K attempt falls back to software, so its GPU gate remains failed.
No extra large visible-window retry was made.

An independent finite oracle checks 66,192 predetermined South Cape pixels
across three extents, including above/below/both-side scenery and the pier.
58,128 are background-only; 8,064 use an explicit background-plus-one-source-
actor proposition. A failed background-only assumption hitting 27 opaque actor
pixels remains recorded; the pixels were not masked. Independent palette,
brightness, origin and corrupted-pixel controls reject. This establishes the
selected pixels, not every actor/frame/room or interpolation.

Unpaced town host raster/capture means are approximately 6.0/10.7/12.8ms at
1/1.25/1.5 extents; this stage includes CPU world composition. Guest processing
is around1.3ms in these runs. These concurrent QA counters are descriptive,
not a balanced benchmark, sustained FPS, GPU hardware time or physical latency.
CPU row reconstruction is the next performance target; evaluate the optimized
span path and GPU tile/actor batching against the retained pixel reference.
HD2D/HdFx effects are disabled when output differs from raster geometry;
only the stated SharpPixels/xBR looks are checked in this new mode.

This is a source update, with no owner-install replacement or release. Game
images, generated game code and private inputs remain outside public source.

## Content direction

The owner now wants the retranslation and approved expanded maps built into
the eventual main game, without mod toggles for either. This supersedes the
earlier two-edition UI plan. Stock USA remains an internal native reference;
this batch does not import the private developer ROM/maps or qualify patched
native code. Minimap/world-map and Black Glasses jewel-shimmer guidance is in
[developer notes](GAIALABS-DEVELOPER-NOTES.md). The existing author, upstream
and contributor credits and license notices remain intact.
