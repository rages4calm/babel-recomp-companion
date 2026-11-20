# Updated SDK, controller maps and Great Wall scenery

November 19, 2026. Continues [the in-game map batch](VISUAL-FULLGAME-002.md).
Full-game visual coverage and GaiaLabs main-content integration remain unfinished.

## Controller operation

The shared host's default physical gestures are L2+L3 for Companion and L2+R3
for Settings. These commands and physical-to-SNES mapping are configurable
through the shared controller bindings. In Companion, shoulders cycle pages;
the Map page uses directions/left stick to pan, L/R to zoom, Y to center, X to
toggle radar and B to return. These are **SNES logical labels**: for the default
Xbox layout, south is SNES B, west is Y and north is X.

Settings now includes Map zoom in/out, center, radar toggle and Back assignments,
plus the radar preference. Changes persist through the existing mod selection
contract. Choosing an occupied button swaps actions, so Back cannot become
unreachable. The Map footer reflects the assignments. Disabling custom controls
restores defaults on launch; it does not disable the built-in map. Keyboard and
mouse remain supported.

Original's Start command previously offered another local radar. The title now
routes it to the enhanced map only when actual quiet/available state and the
source input handler establish the radar context (`09AE` bit3 clear). The held
button is consumed until release. Original pause contexts, unavailable geometry
and world travel retain their input. `IOG_ORIGINAL_AREA_MAP=1` restores the old
command as a development fallback. The optional shared `companion_input` hook
operates only on local human input, before script/debug input is combined;
netplay and speculative execution do not invoke it.

The owner clarified the content direction: preserve GaiaLabs' **world travel
map and Retranslation**, while using our scenery/exploration map within areas.
The private received reference still retains its guest minimap; this update
does not pretend an undocumented patch removed it. Main-content integration
must resolve that duplication without removing world travel.

## SDK integration

Official source advanced from `80a41241e39bfffd384506fbe7ca65b386e03050` to
[`22c01ef12cc94767451d0b218e4fc341bc19043e`](https://github.com/RetroPortingToolKit/snesrecomp/commit/22c01ef12cc94767451d0b218e4fc341bc19043e):
19 commits and32 changed paths. A before/base/upstream inventory covers all1365
previously tracked vendor files. Unrelated Babel/local deltas were retained;
the vendor tree was not replaced.

Three-way merges preserve Android/handheld presentation restrictions, Babel's
storage default with the SDK override, local touch controls, native continuation
guards and dual APU diagnostic exports. The upstream canonical-boundaries keyword
is supported while retaining lazy profile caching, one-shot iterable behavior,
early rejection order and raw execution-PC qualification.

SPC700 DIV/ADDW, extended Windows paths, diagnostic beam-clock metadata, HD Mode7
shader portability and shared native IRQ-deadline APIs are integrated. The new
IRQ callback is default-off and **Gaia's own frame driver does not arm it**.
No automatic Gaia IRQ qualification or new native coverage is inferred. The old
immutable graph016/effects025/WRAM021 sources are reused, not regenerated.

The namespaced SDK inline helper fixes the reported Windows header conflict;
the title's old include workaround is removed. Its regression verifies the
current SDK links directly and an injected legacy macro still reproduces failure.

## Great Wall85/86

The background uses several horizontal-scroll bands. The renderer now decodes
the supplied ROM's type21/1E producers and calibrates against all225 actual row
samples. Expanded rows choose their own world-height band and producer phase,
with horizontal repetition, finite vertical artwork and existing room masks.
No extracted game constants or artwork are bundled.

Actual1080p smooth-xBR/1.5x views show the expanded-right green missing-floor
patch replaced by continuous checker floor and correctly phased facade/windows.
The pit, ladder and finite walls remain. The corrected host parallax deliberately
changes136 decorative pixels inside the native overlap, plus10026 expanded
pixels in the inspected lower view. Matching guest framebuffers are therefore
not described as whole-picture pixel parity. Structural admissions remain66.

## Verification

Private receipts are in ignored `.local/batch-001/visual-fullgame-003`.

| Check | Result |
| --- | --- |
| SDK v2/timing/DSP suite |1014 pass,2 skipped, zero warnings |
| Strict Clang bridge |Interpreter89/89; bridge516/516 in each fused mode |
| Strict SPC arithmetic |823991 cases, zero failures |
| State dump |New clock metadata and existing failure paths pass |
| Controller host |765 assertions, including remapping/persistence and Start guards |
| UI |2421775 assertions |
| SDL trigger regression |21 ROM-free checks using actual SDL3 and SDK mapping |
| Final actual SDL virtual-pad route |Start, pan, zoom, center, radar and Back/resume;78 modal events retain cycles/WRAM;7 guest snapshot fields match |
| Final Original retained comparisons |56 pairs,10080 candidate boundaries pass |
| Received reference v2 |400 frames each radar/full,399 supported;77 explored; CPU/WRAM and7 final fields match;7 modal events frozen |
| Received isolation |Current configure/preprocessing/observer guards pass |
| Persistent discovery |97 to107 cells;107 retained after rewind and fresh process |
| Wall raster / world harness |20386 /12112004 assertions; removing wall support fails targeted check |
| Authentic wall route |1050 frames,598x336 throughout;1018 ready,32 transition fallback |
| Natural return |86 to85 to86; guest snapshots match retained reference |
| Actual GPU |Two NVIDIA1920x1080 smooth-xBR/1.5x views inspected |

The broad SDK suite receipt remains **failed** because `host_main.c` changed
during the run. Its supplemental qualification verifies the other793 catalog
entries stayed unchanged and links a fresh final host-source-reader check. The
compiled core tests passed; no full-suite repeat or false broad-freeze pass is
claimed. Two hardcoded-GCC fixtures skipped on this Clang installation; the
bridge fixture was separately executed with Clang.

Actual SDL attachment correctly releases virtual triggers. A local inherited
self-test helper instead wrote raw0, meaning half-pressed after gamepad mapping.
The corrected helper uses raw-32768. The independent regression distinguishes
this local test defect from upstream behavior; no false upstream issue was filed.

The connected physical device enumerates as Xbox360 Controller. Automated event
tests use SDL's virtual device; they are not a new manual physical-button test.
GPU CLI captures exited normally without desktop input/control. GPU evidence
from candidate v1 links to final v5 through unchanged renderer-source hashes;
later changes are map persistence/build-mode guards and controller test helpers.

Final Original v5 SHA-256:
`bf693e1b9a583e512ddc6ceaed836c04689c50b351a7bfda33373ea1e3d59378`.
Separate received reference v2:
`182e0ac7d5b1a770dad17b2b566b386806c2af3325653181c3d23e25dc811ee3`.
Its guest CPU remains interpreted, stock plugins/native hooks excluded. Its
mod-free Map uses default controls and session-only radar preference; Original
has the persistent configurable controls. Runtime/guard receipts record the
received qualification separately from Original.

Later GreatWall86 branches, additional rooms/layers/HDMA, relevant boss phases,
natural world-map access, marker binding and full-game transitions remain work.
Fallback and prior runnable builds remain. No speedup or campaign-complete claim
is made. All Babel/GaiaLabs/collaborator credits and licenses remain, and no game
assets, generated game code, private builds, states or soundtracks are published.
