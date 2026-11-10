# Native batch 018 — interrupt work, Dark Gaia and wider scene coverage

Source baseline `4990326`, November 2026. The tested private build is
`7a850990d1c72ad6e33c1947a3070f388056b20228831e1353a0c7359f1a86e2`.
This is a development source update. The installed owner build is unchanged.

The native and renderer comparisons below are complete on that final binary.
Their scope remains bounded, with development reference/fallback paths intact.

## Native selection and ownership

The previous 8,128 contexts remain literal. This batch adds 1,571 contexts:
the union of the highest-cost 1,000 additional room contexts and 1,000 boss
contexts contains 1,566 unique entries; five indexed-indirect JMP contexts
complete the selection. Total: **9,699 canonical contexts / 38,796 aliases**.
RomAtlas independently checks 1,563 new decodes and eight exact bound reuses.
There are 144 fixed opcode bodies: the old 140 remain unchanged, with indexed
JMP and three already-supported instruction forms newly selected.

The old 8,128-context C output remains byte-identical under the current
emitter. All 32,512 old descriptors and 32,610 effect/helper functions remain
identical in the expanded output. Generated game C and the selection/profile
payloads stay private. The immutable batch-016 graph is reused without adding
speculative roots or regenerating its original functions.

The registry limit rises to 65,535 descriptors while retaining 16-bit IDs and
zero as the miss sentinel. Both lookup implementations execute the last valid
ID. Capacity, allocation, conflicting metadata and active-owner failures leave
the existing registry intact.

Indexed-indirect JMP retains real pointer reads, PB/X wrapping and the owning
opcode loop's resolved landing, interrupt and deadline handling. Other indirect
jumps/calls, COP/RTI and unsupported effects remain interpreted.

Profiling also found already-selected data routines being refused in a finite
host interrupt owner. A private diagnostic preserved the guards and compared
three routes with the previous build. It identified the actual NMI entry as
`00800B`, correcting the initial `008003` assumption. The three diagnostic
runs preserve full CPU, clocks, devices and canonical APU state.

The new opt-in NMI API grants only 430 already-selected canonical contexts
(1,720 aliases) observed in that owner. It requires the explicit actual NMI
delivery edge, the exact entry, bridge depth and stack watermark. Nested
bridges and IRQs cannot inherit it; acknowledging RDNMI inside the handler
does not erase an already established owner. Ordinary `run_interrupt` retains
its default refusal. Stack/frame changes, calls, returns, indirect control,
COP/RTI, power and block-move effects are excluded from these grants.

`IOG_NATIVE_NMI_CONTINUATIONS=1` enables the qualified title path alongside
native continuations. `native_nmi_insns` and `native_nmi_cycles` are explicit
subsets of existing native-continuation counters. They are never added again
to the CPU partition. All prior policy, pending-event, mapper, live-byte and
mode checks remain.

The focused gate passes 34 tests and three subtests. Actual-core NMI and
indexed-JMP fixtures exercise real SPC/DSP, DMA, hardware math, ordered bus
accesses, deadlines and nested ownership. Six NMI and ten indexed-JMP causal
fault processes are rejected. Fixture setup mistakes and the first capacity
fixture's accidental sign-mask edit remain recorded separately; they were not
reported as production engine defects.

Three final-binary NMI off/on pairs pass **six captures / 25,200 frames**.
Full CPU, WRAM, devices, APU and raw APU event files match. At each site, the
interpreted decrease equals the native increase and the NMI subset. Other
native work, poll work and unregistered costs remain unchanged. The town route
changes from 97.1250% to 98.0860% native guest cycles solely through this toggle;
this is a finite execution result, not completion or host speed.

## More rooms and the final boss

Nineteen additional assisted room routes reach their expected scenes through
verified original incoming warp tuples. A shipwreck probe reaches scene 43 but
its subsequent controller input leaves for 45; its stationary-final-scene
expectation remains failed and is not silently relabeled as a passing source.

Dark Gaia's new routes use verified caller-chain graphics context, then the
original space-flight transition. The game itself creates the special boss
entry. No enemy HP, phase, PC, clear or reward fields are edited.

Controller attacks produce the original first-form 20→0 HP writes, the game's
second-form initialization to 40, then 40→0 and the ending transition to E5.
The idle control stays at first-form HP20. A directional attack control reaches
the second form and stays at HP40. Survival assistance and source-derived
loader prerequisites are disclosed; these are not natural campaign runs.

The first native boss review stopped at HP initialization: the interpreter logs
two byte writes with IPC `83D009`, while the compiled function logs one word
write with raw interpreter IPC zero. The original records and failed review
are retained. A separate read-only review binds the compiled function hash,
its unique matching store, full logged CPU/actor context, address, width,
value, frame and byte order before deriving that one source-site attribution.
Damage and second-form writers retain their exact PCs. Wrong mappings and a
missing initialization are rejected. No general IPC substitution is applied.

All **105 fresh reference/native pairs pass: 210 captures, 522,200 frames and
1,480 snapshot sets**. The final binary preserves original-width simulation,
full CPU/resume/master clocks, IRQ/HDMA, device state, ordered writes and the
complete canonical APU checks. All forced-reference native counters are zero.
The original failed boss review remains failed; its separately bound read-only
replacement completes the same three captured pairs without rerunning games.

| Route corpus | Pairs | Actual native guest-cycle share |
|---|---:|---:|
| Matched previous routes | 83 | 97.7752% |
| Additional room visits | 19 | 97.9738% |
| Dark Gaia routes | 3 | 97.2174% |

The matched 83 routes previously reached 96.5202%. Interpreted cycles fall from
281,948,133 to 180,262,079: **101,686,054 fewer cycles, a 36.0655% reduction in
that corpus's remaining interpreter work**. The entire 105-route corpus reaches
97.7578%; its different mix is kept separate from the matched comparison.
These are guest-cycle measures, not completion percentages, host speed or
independent physical hardware proof.

Of the 1,571 additions, 707 execute: 702 ordinary contexts and all five indexed
JMP contexts. They contribute 10,196,834 and 12,703,470 actual guest cycles,
respectively. The remaining 864 additions are unobserved; no refusal reason or
execution coverage is assigned to them. In total 8,225 continuation contexts
are observed. The NMI subset contributes 108,212,898 cycles already included in
the old-context native totals, never additional work in the CPU partition.

All 740 raw APU file differences retain their unnormalized hashes and first
differences. The established canonical comparison preserves access order,
ports/values, executed APU port clocks, DSP samples and CPU-event fields while
excluding host frame/scanline/hclock labels. Complete APU/SPC/DSP/PCM/scheduler
snapshots pass. The comparison policy is unchanged. Three additional read-only
old-build/new-build forced-reference controls also preserve CPU, devices and
APU state. All 1,260 actual mod manifests in the 210 native captures open, and
the resolved feature states match the requested HP/rate settings.

## World renderer

The finite world-format set grows from 15 to **50**. The 35 additional formats
include Inca, Mine, Garden, Mu, Angel, Wall, Angkor, Pyramid ceremony and Babel
rooms. This does not admit the spare storage in the classroom, houses or cave.
The older expanded-culling preview retains its original two-scene contract.

The host camera now handles bounded signed excursions of up to 16 pixels.
Containing the entire original 256×224 field takes priority over clamping the
larger view to the map. A camera value of −1 therefore stays −1, with an
explicit edge, rather than wrapping an unsigned offset or dropping the wide
view. Original uploaded edge cells remain authoritative inside the native
rectangle; expanded pixels outside authored map bounds stay blank. The normal
town boundary fix and square-pixel geometry remain unchanged.

All **82 fresh reference/span pairs pass: 164 captures, 337,600 frames and
1,256 snapshot sets**. Both sides run the same final native/poll/NMI tier;
only pixel drawing and full-copy versus touched-word restoration differ.
Full guest memory/devices, raw APU events/state, full CPU/IRQ/HDMA/policies,
per-PC costs, complete new-world pixels and source packets match exactly.
This gate uses raw APU equality and does not apply the separate native-versus-
interpreter host-stamp comparison policy.

The selected pictures contain 81 positive world views across all 50 formats
and one expected Castoth source refusal. Per implementation, stock C714
reproduces all published OAM, 1,481 native-visible parts, 644 player parts and
280,640 raw object texels, with matching attributes and order. The original
rectangle partitions into 4,351,535 non-HUD exact pixels, 102,836 projected BG3
exact pixels and 190,493 original-HUD-only terrain pixels that remain
independently unobserved. These total 81×57,344. Both 256×224 shake controls
match every original pixel with no HUD mask or unobserved remainder.

Every endpoint passes actual catalog file opens, SHA/resolver and requested
HP/rate activation checks. Resolved states remain identical before and after
the game; the longest current catalog path is 195 UTF-16 characters.

Castoth's nine malformed sprite-source frames remain explicit fallback. Their
paired source contains an unmapped metadata read also refused by the bounded
original composer. No guessed dead-actor skip, bank substitution or metadata
waiver was introduced. Spatially varying color windows, unobserved phases and
all offscreen overlap cases still need further qualification.

Two actual final-binary NVIDIA 1280×720 captures pass nearest transport and the
requested xBR geometry/effect checks. NMI execution is active in both. Nearest
transport checks all 200,928 source texels; xBR is an intentional filter, without
an independent filtered-color oracle. No fresh 4K, HD2D, GPU-world-engine,
sustained-FPS or physical input-latency claim is made.

The first full renderer matrix stopped after 44 passing pairs when one Inca
comparison lost HP parity. The underlying difference was Windows package
loading: a 264-character manifest path was skipped, while the corresponding
259-character path opened and activated infinite HP. A read-only C++ probe and
the runtime's resolved state confirm the difference. The raw failed comparison
remains failed. Fresh bounded directory names preserve the logical cases,
routes and events while allowing package paths/loading to be checked before
each run. [SNESRecomp issue 271](https://github.com/RetroPortingToolKit/snesrecomp/issues/271)
reports the shared runtime limitation; no guest comparison is normalized to
hide it. Windows users should keep mod paths short pending a dependency fix.

## Patched-ROM fallback

[Issue 3](https://github.com/rages4calm/babel-recomp-companion/issues/3) records
a separate startup-order defect: stock identity was cached before plugin
activation, while a later successful IPS patch changed the in-memory image.
Forcing CPU interpretation did not invalidate that world-renderer approval.

Successful IPS activation now calls the existing world initialization routine
to recheck the image and discard pending pictures. Rejected IPS input preserves
the original bytes and valid stock pairing. A ROM-free regression links the
actual IPS activation/parser and world module with the production SHA-256
implementation over a synthetic 2 MiB image. The world fixture passes 871,391
assertions; removing only the refresh call reproduces stale approval. This
does not qualify real Apocalypse or GaiaLabs rendering compatibility.

## CPU cost, tools and storage

A quiet final-binary NMI off/on benchmark runs six balanced AB/BA pairs plus
warmups at each extent: **42 processes / 29,400 frames**. Both modes use the
same 9,699-context selection and optimized renderer. All 671 service-window
frames per run are genuinely world-ready. ROM, copied seed, route, config and
all mod resources match; CPU/WRAM/policy streams match, and the native-work
delta equals the measured NMI subset. Each timed run also matches its own
mode's complete exit-site counts.

| Extent | Median process-CPU ratio, NMI on/off | Observed paired range |
|---|---:|---:|
| 1× | 1.0000 | 0.9808–1.0327 |
| 1.25× | 1.0000 | 0.9842–1.0160 |
| 1.5× | 1.0071 | 0.9720–1.0240 |

Process CPU is essentially flat within the observed variation; no consistent
host speed gain is established. GetProcessTimes covers the target process's
startup, input reads, engine, diagnostics and exit. Parent preparation/hashing
is excluded. No concurrent test, build or compression workload ran during
measurement. Batch 017's 60.0–71.8% renderer CPU reduction is a separate result;
these NMI measurements do not replace it or establish FPS/input latency.

The SDK gate passes **872 tests, two skipped**, with inherited UTF-8 child
output and strict thread-warning handling. The source catalog remains frozen.
Official SNESRecomp main remains `e9c207322c148eccc8a679b72d8b005d0d95d31c`;
the earlier encoding report in issue 270 is still open. No vendor tree,
compiler bundle or unrelated project was replaced.

The batch reuses the existing graph/resources and one build tree. All final
105/82 raw comparisons, current source/profile inputs and the entire earlier
failing Inca pair remain. After successor validation, 13,472 superseded
preliminary/raw files totaling 3,726,274,127 logical bytes were retired with a
scoped hash inventory. Their JSON receipts remain historical; no archive was
created and no final proof is reclassified as fresh evidence by that cleanup.

In-place compression preserves paths and bytes, saving another 1,046,548,214
reported storage bytes on existing files. Capture directories also inherited
compression from creation. The batch's regular files now total about 15.7 GB
logical / 5.2 GB reported file storage. This exceeds the initial 4 GiB target;
retaining the complete final evidence was reviewed within a 5 GiB limit.
File-storage totals exclude volume/MFT overhead. All 39 protected owner files,
source inputs, masters, saves and soundtrack data remain unchanged.

The interpreter/reference paths and guarded unsupported-mode fallbacks remain
available. SPC700 sound-driver interpretation, remaining CPU guards, campaign
coverage and additional renderer formats/phases are unfinished. The eventual
built-in retranslation and approved expanded maps are separate integration
work; this batch still uses the verified stock-USA foundation. Original Babel
and upstream credits/licenses remain intact. Public source excludes ROMs,
generated game code, saves, screenshots, soundtrack packs and private evidence.
