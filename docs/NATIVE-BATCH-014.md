# Native batch 014 — system routines and wider gameplay checks

Original USA edition, November 9, 2026. Source baseline `b5feec7`, based on
Babel Recomp by mr0ta / mrOt4, with all existing credits and licenses retained.

## Goal and selection

The goal is fully native Original game execution, followed by a separate
GaiaLabs edition. The owner wants the finish of a faithful modern PC remake,
preserving Quintet's art direction and atmosphere. Native instruction coverage
is one part of that work; presentation, controls, audio and QoL need their own
qualification. The current SPC700 sound driver is still interpreted. Keeping a
development reference does not make required interpreter fallback a finished
product requirement.

Batch 013's actual mixed-native captures identify the next costs. Its broad
source-module filter was our conservative selection choice, not a rule imposed
by Babel's author. It excluded useful SPC upload, camera, initialization,
hardware-math and DMA-related routines even outside the hard policy ranges.
Simply filling the old filter's remaining pool would address very little of
the actually interpreted work.

This batch retains all **1,990 earlier context rows verbatim** and selects
**2,500 additional exact observed contexts**: 2,000 ranked from actual native
residual costs, plus 500 nonduplicate current-core source contexts for broader
gameplay paths. The result is **4,490 canonical contexts / 17,960 physical-alias
descriptors / 127 fixed opcode bodies**. Independent checks cover **2,308 fresh
RomAtlas decodes and 192 exact bound reuse decodes**.

Only the selected PC/width/mode/source bytes are admitted. This does not promote
whole modules or relax the runtime interrupt, mapper, live-byte, owner, hook or
policy checks. All 2,124 guarded addresses, four NMI floors, CFGs and nested
pins remain. Calls, returns, indirect transfers, interrupt frames, direct
SP/emulation changes and block moves still need further work. Known timing
guards are work to resolve and verify, rather than permanent completion rules.

The source/native rankings stay separate. The selected actual-native residual
ceiling is 277,838,729 guest cycles across the old bounded cohort; it is not an
execution claim. Some source-reserve DMA sites are NMI-only, and the unchanged
interrupt guard still refuses that context. Actual gains below come from new
execution and exact per-PC counters.

## Registry and generation

The registry and emitter cap rise from 8,192 to **32,768** descriptors without
widening the existing 16-bit direct/legacy indexes. Registration remains atomic:
allocation failure, invalid metadata, conflicting callbacks and capacity
overflow preserve the old registry, statistics and launch mode.

Both lookup modes actually execute descriptor 32,768. Sparse tests exercise
32,768 PC/MX entries across 8,192 valid pages and fail each allocation in a
populated registry. Seven focused continuation/index tests pass. Their measured
fixture peak is 37,748,736 bytes; that is not a universal registration-memory
bound. No runtime bus-validation cache or interpreter counter relabeling is
introduced.

Generation now extracts each source opcode body once per emission. Regenerating
the complete old 7,960-descriptor set produces all 4,843,883 C bytes exactly as
before, SHA-256
`2e04081c2c278c39359b21d7bd7c4c5e3a58fcc5b832b85c4b9d7281ea237051`.
The emitted game-specific source remains private.

## Bus and timing checks

SDK qualification covers **811 passing tests, two skipped**, followed by the
six new MMIO tests below in a separate gate. The 811-test collection includes
the focused capacity/index checks. An
initial private pytest-directory bootstrap failure is retained separately;
its setup errors are not production assertion failures.

Six additional ROM-free MMIO tests use production-generated effects under the
real owning bridge, with the actual SPC/APU/DSP and DMA implementations. The
SPC echo program receives scheduled future input; a native CMP/BNE loop must
observe the acknowledgement at the same bus phase. A native DMA-register store
must perform the real transfer to WMDATA, including its zero-channel control.
Both lookup modes pass 728 owner pairs each across short deadlines and complete
transfers, comparing full APU state/scheduler, CPU/bus phase, payload, clocks
and counters. Skipping the port read or mapped DMA write is detected in each
mode. These fixtures cover the master-clock timeline and M8 operations; they
do not claim CPU-to-APU writes, word-atomicity or physical audio-thread coverage.
Fixture composition/calibration failures remain retained; no engine change was
made to satisfy them.

## Initial same-core execution

Capacity-only controls preserve all old guest counters, per-site totals, full
state, output and APU behavior. The expanded selection uses the same hardware
core and batch 013 graph to isolate its effect from new graph roots.

| Bounded route | Prior selection native guest cycles | Expanded selection |
|---|---:|---:|
| 6,000-frame classroom/South Cape, 4:3 | 90.3353% | 94.6280% |
| Same route, 16:9 | 90.3575% | 94.6488% |
| 4,000-frame assisted Viper fight | 87.7513% | 91.9404% |

The added native cycles are exactly 9,490,366 / 9,490,471 / 6,317,727
respectively. Per-PC instruction/cycle changes exactly replace interpreted
work; other generated and poll costs stay unchanged. Six base/expanded pairs
and six same-tier controls pass. A separate independent audit includes two old
batch-013 pairs for the capacity comparison: eight unique pairs / 16 captures /
88,000 frames, without double-counting reused natural-route pairs.

These percentages measure guest execution on those inputs, not game content,
completion or host speed. Source-only ceilings do not substitute for actual
owner admission. Interpreter fallback remains available throughout development.

## Final graph and gameplay

The frozen final graph has **415 roots / 1,333 contexts / 1,248 eligible /
85 LLE**. All 1,246 earlier native bodies are byte-identical, and earlier node
dispositions are unchanged. The two new bodies are `bank_83_F0B3_M0X0` and
`bank_8B_8B05_M0X0`; all 21 new generated instruction contexts pass independent
RomAtlas checks. `8B856E:M0X0` remains interpreted because of BRK at `8B8573`
and structural poison. All 87 cached outputs and the source/config/input hashes
pass. Inputs are 825 historical profiles and 81 current-core profiles: 62 exact
reuses from batch 013 and 19 new source observations.

The 19 new reference cases span 34,800 frames and 75 snapshot sets. They cover
Castoth's original hand/face/death sequence, Sand Fanger's authored descent and
fight prerequisites, Mummy Queen's damage-driven phase thresholds and death,
statue ceremonies/catch-up/returns, and both Mummy teleport pads with an outside
control. Assistance is explicit, including positioning, strong stats and
survival settings. Enemy HP/count, phase progression and rewards are written
by the game. Six superseded or unpaired diagnostic passes and eight failed
source attempts remain excluded. Unresolved Mu wall and original portal-choice
attempts do not become qualified traversal claims.

Fifteen positive and four negative source-writer groups, 27 stock instruction
facts, 11 source RomAtlas decodes and eight v11 seed lineages bind the new source
contracts. These carry into the final candidate only through actual matched
execution and fresh custom writer/outcome checks.

| Final private artifact | SHA-256 |
|---|---|
| Executable | `d8cc01020aadeff92012d5498aa0c172dc7097171300db32271526f913b9530a` |
| Program manifest | `0e8b5c3deb57023e93f539607bc7fd871a559a6ea821d1bb65f6dee4b464c021` |
| Native effects C | `6cd666982dbe93d2118539ee937f3c4ea0e4aefeaf9f8fba4a97283479ce3041` |

All **83 final reference/native pairs pass: 166 captures / 436,000 frames /
1,294 snapshot sets**, with source/reference/native comparisons and independent
counter, artifact and original-writer reviews. This includes all 64 prior cases
on the new executable and the 19 new cases above. The old cohort preserves its
25 ordinary damage/death cases, three earlier bosses, six power activations,
three inventory roundtrips and nine full-room-clear rewards. The new cohort
adds the Castoth, Sand Fanger and Mummy Queen consequences and controls.

Actual execution reaches **3,686 descriptor sites**, including **1,983 of the
new 2,500**: 1,428 ordinary data/register, 283 static control, 93 status-width
and 179 data-stack contexts. The remaining 517 were not observed executing;
no refusal reason is inferred from that absence. Every per-site instruction
and cycle count reconciles with the global totals. Forced-reference native
counters remain zero. The final town-route shares remain 94.6280% / 94.6488%.

All **647 raw SPC host-stamp-only file differences** remain retained. Canonical
executed-cycle events, CPU rows, full APU state/scheduler, saved devices and
output pass their stated comparisons. Store-operation reviews preserve order,
repeated writes and mandatory original reference IPC. An atomic native word
record may match only its exact adjacent source-byte pair; this does not prove
physical intraword bus order. The new M8 MMIO fixture provides separate ordered
bus/phase evidence for its explicit scenarios.

An initial private input binder assumed every historical manifest still had a
journal peer. That attempt stopped before generation, and its log/receipt are
retained. The corrected binder records absent historical peers explicitly as
null, matching the previous batch's convention; current source journals remain
hashed. The actual guarded SDK generation succeeds on its first attempt. No
source input, expected gameplay outcome or engine assertion was changed.

## Host CPU cost

The independent timing audit passes **42 sequential processes / 224,000
frames**: six warmups and 36 measured runs, with six balanced A/B pairs for
each route. Both builds use the same updated hardware core and registry code;
the baseline has the prior graph/1,990 effects, and the final build has this
batch's graph/4,490 effects. Each run matches its qualified guest counters,
final fingerprint and complete per-site totals, with isolated file logging.

| Route | Baseline median CPU (s) | Final median CPU (s) | Median paired cost change | Pair range |
|---|---:|---:|---:|---:|
| 4:3 town, 6,000 frames | 10.0390625 | 10.0390625 | -0.1420% | -5.2870% to +4.3339% |
| 16:9 town, 6,000 frames | 9.078125 | 8.9921875 | -0.4793% | -3.9216% to +4.2202% |
| Viper, 4,000 frames | 7.703125 | 7.8125 | +2.5511% | -17.0175% to +5.3942% |

These are process frame-service CPU seconds, excluding startup/exit, with
dummy SDL, software presentation, disabled audio/VSync and no diagnostic frame
dumps. They do not establish an overall host-speed improvement or physical FPS.
The Viper paired median is higher, with substantial sample variation.

The final wide/narrow block medians differ by -10.4280%. The separate route
blocks and observed variation make that ratio unsuitable as a claim that wide
rendering is cheaper, or as an isolated renderer-cost estimate. Future renderer
work needs interleaved aspect comparisons and real CPU/GPU/presentation phase
measurements. This cohort does not measure NVIDIA hardware rendering or input
latency. See the [renderer/performance direction](RENDERER-DIRECTION.md).

## Cleanup and source publication

One reusable private build tree serves the baseline, expanded and final builds.
Named master executables share resources; per-case EXE/font trees are not
cloned. Private inputs and raw validation outputs stay under ignored `.local/`.
Original and GaiaLabs identities remain separate; this batch does not use the
private developer archive or include its ROM/override/audio contents.

Direct retirement removes **19,659 superseded raw files / 6,725,563,249 bytes
(6.263669 GiB)** from batch 013, with zero skipped deletions. The after-cleanup
inventory measures **27,777,053,244 logical bytes (25.869 GiB) / 237,937 files**.
The 32.133066 GiB before figure is derived from that inventory plus removed
sizes, not a separate before measurement.

All 39 protected owner files and the installed batch 005 executable are
unchanged. The 64 exact batch-013 source witnesses still used by batch 014 are
pinned: all 7,684 artifacts plus their receipts match the frozen inventories.
Latest batch-014 source/final/probe/timing evidence, all metadata/failure logs,
seeds/saves, ROM/music/private developer inputs and master builds remain.
No archive is created or modified. Cleanup receipt
`5e24435668f21718e1f1d5713a3985c25d7410b9547b8f7731504b7cfdcaff38`
binds the measured inventory, protected files and source-pin verification.

This is a source-only update to the existing fork. Final staged and remote
tree verification are recorded privately. No release or owner installation is
created. All original credit/license notices remain; no ROM, generated game C,
binary, save, soundtrack, screenshot or private validation artifact is included.
