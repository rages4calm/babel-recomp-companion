# Illusion of Gaia Companion — handoff

Updated November 9, 2026. Development version `0.1.0-dev.1`.
Read this first; the completed source audit is [here](docs/BASELINE-AUDIT.md).

## Qualified continuation — native batch 012

[Batch 012](docs/NATIVE-BATCH-012.md) is a source update on the existing fork,
with completed bounded gameplay and source qualification. Its preceding source
baseline is `2166c8f`. Final publication checks record the pushed commit in
`native-012/final-verify-published.json`. No release or installed-game replacement
is implied.

Final private binary `.local/batch-001/native-012/build-final/babel-recomp.exe`:
`8a0634d39b8ccdb85ea3035974770c5e6082e74c8556aadd7a3f6f800bd1887b`.
Graph SHA `8323a2febc32322842e0f8010ef408e2258d548d3612ec03e70a4285bdf24add`:
374 roots / 1,327 contexts / 1,244 eligible / 83 LLE. All 1,233 older bodies
remain byte-identical; 11 are added, with 65 new instruction contexts checked
through RomAtlas. All 437 historical source inputs and 161 current inputs are
identity-bound; no older cost corpus was relabeled or merged.

The fixed-effect selection preserves 240 contexts and adds 1,000 observed
contexts (756 ordinary / 244 static control), giving 4,960 physical-alias
descriptors and 93 fixed opcode bodies. The 1,000 new contexts have 913 new
RomAtlas decodes and 87 exact bound reuse checks. Twelve static branch/direct-
jump forms are added; indirect transfers, frame/stack and width changes remain
outside the subset. Per-opcode retirement and existing code/mode/owner/mapper/
overlay/policy/interrupt guards remain. Registered continuations use direct
PC/MX lookup by default; `SNESRECOMP_NATIVE_INSTRUCTION_INDEX=0` retains legacy
lookup. This does not cache or bypass code validation.

Final SDK: **791 passed, two skipped**, including all 24 focused effect tests.
Final title gate: **167 passed** (`native-012/title-tests-final.log`). Effects
pass 1,383,168 paired scenarios / 4,185,560 checks. Both index modes pass
11,583 actual-bridge branch pairs / 363,092 checks and 65,660 atomic/index
checks each. Negative mutations remain detected; `interp816.c/h`, guest
layouts and all four NMI fallback floors are unchanged.

**161 fresh pairs / 322 complete loss-free captures / 576,680 frames / 2,834
snapshot sets pass**, with all **272 actual old011 same-tier controls** passing.
Canonical CPU/WRAM/clocks/devices/full APU+scheduler/output, complete journals,
identities, exact cost partitions and per-site/global sums are independently
checked. Source gameplay and normalized writer facts pass for old50,
previous29 and new25. Receipts: `native-012/counter-audit/` and each group's
`independent-review.json`. Current narrow/wide natural routes reach
**89.3792% / 89.4043% native guest cycles**; these are bounded execution shares,
not campaign completion or measured game speed. Lookup-only CPU measurements
must not be promoted to a game-speed result.

Host cost:42 sequential native runs /252,000frames, six warmups plus36 balanced
measurements. Paired median service CPU versus011 is +0.3671% narrow /+0.2955%
wide; direct versus same-binary legacy is -0.8147%/-0.5826%. Narrow old/new
pairs range -4.19% to+14.44%, so do not promote the medians to an overall speedup
or a significant regression. Separate wide/narrow cohorts do not isolate renderer
CPU. SDL discovery paths differ, but actual linked static library bytes, all
public headers and generated revision match; compiler/flags/resources match.
All42 runs retain exact guest counters/final witnesses and actual lookup modes.
See `native-012/host-cost/post-audit.json`; no forced-reference timing cohort.

New25 qualifies six original ability grants, six known-orb revisits, five item
chests, four opened-chest reloads, full-inventory/empty controls and Moon Tribe
success/timeout. It has 83,500 source-reference frames / 142 snapshot sets,
11 wide cases and 21 strict original writer events per fresh tier. Grants use
original writers and form/return paths, without learned/form/control pokes.
Trial setup explicitly uses **255 STR / 40 DEF / infinite HP** and positioning;
actual melee reduces the original six enemies to zero before the countdown
ends, and original gate/statue/item writers execute. Its no-attack control has
15 identical initial artifacts and times out with six enemies at 6 HP, no
reward. Full-inventory, empty-chest and Mushroom fixtures use **255 DEF**;
full-inventory setup supplies 16 private Herb slots, not earned items.

Only the loss-free first-enemy strict trial death store is qualified in source
support. The broad six-actor watch capped and remains excluded; do not claim
six loss-free strict death-store captures. Fresh pairs separately qualify actor
states and original quest reward stores. New25's older011 witnesses are forced
reference only, so no old-native percentage gain is claimed for those routes.
See `native-012/new-routes/completion.json`, `source-semantic-audit.json` and
`retained-attempts.json`. Newer GaiaLabs input masks differ from stock; final
grant witnesses bind verified stock instructions and actual observations.

Retain the 1,415 raw APU clock-file differences, 19 aspect raw strict failures,
normalized word/byte grouping limits and historical004 strict17/28 result.
Passive copied-owner load, aspect full-frame comparisons, continuation-off and
legacy lookup controls pass. Raw fresh SAVE/RESTORE core/APU identity and
Vampire bomb rescue remain unqualified. Garden crossings, failed prerequisites
and source/decoder calibration attempts stay excluded. GaiaLabs dev-build/
module identity is still pending; the clubhouse/Erik music report is deferred.
All **39 owner input hashes are unchanged**, and installed005 is untouched.
Both native feature switches remain explicit private opt-ins with interpreter
fallback; no launcher option for unsupported functionality is added.

Cleanup started from 61.67 GiB logical. Old cold outputs through010 use the
verified archive `9cf7c5a723eaaf414fb0f6515b572fe8eacf37cd489121485f3aa21b41c5550a.zip`;
its restore/index receipts remain private. Redundant **011 raw outputs were
retired directly, not archived**, after all old011 comparisons completed.
Their metadata, scripts, source profiles, saves and build masters remain, but
the retired raw files have no archive restore path. All current012 raw evidence
is retained; disposable runtime copies have matching protected masters and
`native-012/cleanup/runtime-master-restore-map.json`. Earlier copied executables
were separately compacted with SHA/CRC/receipt checks; do not add operation
counts together as a final size or recreate an existing archive.

Final full inventory: **22.583 GiB logical (24,247,954,336 bytes)**, down from
**61.670 GiB**. All 39 owner file hashes remain unchanged, and all current012
raw qualification evidence is preserved. Preserve current012 consumers, build
masters, ROM/MSU/music, saves, owner inputs and retained metadata. Future
comparison of directly retired raw011 data requires a new qualification from retained inputs, not a
claim that an archive can restore it. See [cleanup usage](docs/PROJECT-CLEANUP.md).

## Completed continuation — native batch 011

[Batch 011](docs/NATIVE-BATCH-011.md) compiles selected actor/LZ instruction
effects at actual continuation PCs inside the existing owning interpreter
event loop. It does not manufacture call roots/stack frames, call the decoder
and relabel it, skip bus fetches, or remove boot/MMIO/NMI fallback guards.
The generation-time helper closure specializes fixed opcodes and operands;
data/address state remains live. Complete byte/mode/live-PC, plain-mapper,
owner/interrupt and policy guards precede execution. Interpreter/state layouts
are unchanged. All unsupported work retains interpretation.

Requires private AOT + full clean stock identity +
`IOG_NATIVE_CONTINUATIONS=1`; the separate poll switch remains
`IOG_NATIVE_RDNMI_POLL=1`. Both default off. No public launcher option or
installed-game replacement. Optional `IOG_NATIVE_CONTINUATION_STATS` writes
per-PC/mode totals only at exit; timing runs omit it.

Final candidate `native-011/build-final/babel-recomp.exe`, SHA-256
`7bb1dc8882b7061a36858c748d5d3fbc55576b67fc26d020a1535250831fc2bb`;
graph `native-011/graph-final/generated/program_manifest.json`, SHA-256
`52a2e75e753440e4d2f468dd38c21a4a67b607271c7afde7dbb2aaf60bf3608d`.
Graph:366 roots/1,316 contexts/1,233 eligible/83 LLE. All1,219 previous bodies
are byte-identical;14 added,231 new instruction contexts independently decoded
through RomAtlas. All301 historical source observations retained with136
current inputs. Continuation plan:240 source contexts/960 physical aliases/
31 fixed opcode bodies; compiled/planned sites are distinct from executed ones.

136 fresh pairs pass, including29 new cases. Natural6,000-frame shares:
**86.5089% narrow /86.5343% wide**, up from82.9903%/83.0169% in010.
Narrow continuation work:2,002,405 instructions/7,775,406cycles. Controlled
probe attribution: LZ1,182,998insns/4,530,132cycles and actors819,407insns/
3,245,274cycles; unrelated costs/poll/generated-body totals unchanged.
Guest execution shares are not content coverage or host-speed evidence.

Independent final136 audit:272 complete loss-free captures/409,680frames/
2,550snapshot sets, all960 site counters exact, zero reference native counts.
222 actually observed contexts: bank82LZ/bank83actors. Generic continuation
73,332,779insns/288,940,458cycles; actors60,192,022/238,592,992 and
LZ13,140,757/50,347,466. All107 old cases have exact per-PC substitution,
unrelated costs/poll totals unchanged. Selected actor residual26,355insns/
98,921cycles remains guarded; no universal selected-site execution claim.
See `native-011/counter-audit/fresh136-capture-audit.json`.

New29:21 additional combat rooms, two Aura successes/two no-item controls,
Vampire catch-up rewards+guarded8x, Solid Arm authored return/walking and a
bounded logical reload/resumed-input case. All29+independent source observation/
store contracts pass. Fresh SAVE/RESTORE raw core/APU/scheduler identity and
Vampire bomb rescue remain unqualified; failed probes retained. Source witnesses
are interpreted010 only; no earlier native-gain claim for new29.

Retain1,273 raw APU-clock file differences,19 aspect raw failures, log-grouping
limits and strictold00417/28. Passive copied-owner300frames passes; aspect
67same-binary/134cross010 fullframes pass. Continuation-off controls (poll fixed on)
preserve the exact010 counters/path. All214 actual same-tier010 controls pass.

Same-binary continuationOFF/ON hostcost:56 sequential runs/336,000frames,
all fingerprints and exact counters pass. Mixed-native frame-service CPU
**+0.7609% narrow /+0.7126% wide**; forced-reference controls+1.0657%/+1.0905%.
Wider/narrower native median cost is+7.0194% withcontinuations/+6.9565% without;
descriptive headless/software cohorts, not isolated raster CPU or physicalFPS.
Keep explicitopt-in/defaultoff; no speedup claim. Receipts `native-011/host-cost/`.
345 completed executable copies/5,003,156,992bytes compacted tothree verified
payloads/15,843,710bytes with restore index; all builds/other evidence retained.
No release or installed-game replacement.

Protocol proof:3,979pairs/98,107checks; emitter proof:1,204,992scenarios/
3,646,376checks across205 opcode forms,53,200 hardware word paths.
Decoder-relabel, clock/frame and missing/double/stale-fetch mutations fail as
intended. Final frozen SDK suite774pass/two skips; its one Windows child-output
encoding warning remains recorded, and affected5 tests pass inheritedUTF8
with warnings-as-errors. Final title146pass. No production edits after the
qualified final candidate.

Official main remains inventoried e98dc63 at the November9 closeout refresh.
263–266 have no new replies;250/251 remain open/unmerged, maintainer heads
preserved. No new confirmed upstream defect. All work remains Original stock;
GaiaLabs dev-build identity/module selection is still pending. The clubhouse/
Erik music report remains deferred. Installed005/all39 owner inputs protected.

Next work should start from the actual final residual/cost and host timing
receipts. Profile the wider renderer separately before choosing a speed fix.
Broader/compound continuation execution needs new ownership and
per-instruction event proof; do not invent call roots or relax the four NMI
floors. Do not rebuild old validation archives or repeat completed audits.

## Previous continuation — native batch 010

[Batch010](docs/NATIVE-BATCH-010.md) enables compiled effects for the two RDNMI
poll instructions inside the existing bridge's exact per-opcode event loop.
It does not skip iterations, fake a latch, call the opcode interpreter and
relabel it, or remove the generated MMIO/boot/NMI guards. `interp816` and guest
state layouts are unchanged; separate native-poll counters identify the work.
Private AOT build + clean stock identity + `IOG_NATIVE_RDNMI_POLL=1` are required.
Forced interpretation, unsupported modes/mappings/context and default builds
keep fallback. See the actual-core production-callback proof and negative
interpreter-relabel control in `native-010/poll-protocol/FINAL-RECEIPT.json`.

Final candidate `.local/batch-001/native-010/build-poll-final/babel-recomp.exe`
SHA-256 `52cb4078f679f9dad90fbfd256bef41753bca188398c3888bc1ad955c09dc7e8`;
graph `native-010/poll-v2/generated/program_manifest.json`, SHA-256
`8b0dbafbba97053c61b3775b3874d6fbc1d09054e0e1ff68d489ca8816b5bc82`.
Graph:358 roots/1,300 contexts/1,219 eligible/81 LLE. All1,163 old bodies are
byte-identical;56 added bodies/486 new contexts independently decoded.
107 current +194 historical inputs preserve all prior source-root lineage.
V1 omitted22 older observations/eight native bodies; retain its superseded
5be918... build/receipts, and do not call it the qualified final graph.

Natural native share is **82.9903% narrow /83.0169% wide**; poll disabled gives
40.2820%/40.3216% in the same binary. Natural narrow poll attribution is
23,596,023 instructions/94,378,505 cycles; generated-native89,016,872 cycles
and other per-PC costs remain unchanged. This is guest-cycle execution on
bounded routes, not campaign/content coverage or a host-speed guarantee.

107 fresh pairs/214 complete loss-free captures/314,040 frames/1,924 snapshot
sets pass canonical CPU/WRAM/devices/full APU+scheduler/output. Independent
official-loader, cost-partition and saved-binary/frame/trace proof is in
`native-010/counter-audit/fresh107-capture-audit.json`. Groups:
`qualification-final-v2`29, `mechanics-final-v2`28, `previous20-final-v2`20,
`new-mechanics-final-v2`30. All154 same-tier009 controls pass; all prior77 gain
native share. Owner-copy and aspect checks pass, including67 same-binary and
134 cross009 presented frames. Feature-off controls preserve fallback.

New30 spans27 new rooms, allthree forms,16 widescreen cases,28 original HP/death
contracts,3 no-A controls, Solid Arm death, both Vampire deaths and a settled
Great Wall DEF40→41 reward. Partial fights stay partial; boss death is not
quest/ending completion. New30 source witnesses are interpreted009 only, so
their68.4582–84.8273% native shares do not establish an old-native gain.

Preserve961 raw APU-clock differences in the current107 cohort,19 raw aspect
failures, word/byte log-grouping distinctions and old004 strict17/28. Canonical
equality does not waive them. The deferred clubhouse/Erik music report remains
untouched. GaiaLabs dev-build identity/module selection is still pending;
separate Original/GaiaLabs edition constraints and credits remain.

Protocol proof:2,633 paired scenarios/52,709 checks pass, with every deadline
1..160 acrossaliases/FastROM/Xwidth and realIRQ/NMI/RTI/ownership/refusal cases.
The decoder-relabel negative correctly fails3,374 counter checks;009 guard
regression still passes70. 753 existing v2 tests pass(two skips), plus both
frozen new protocol tests and145 title tests. Initial broad collection captured
a changing test fixture and retained two fixture failures; final focused source
passes. No production source changed after the frozen candidate/proof.

Next targets: actual RTL/deadline continuation ownership for actor and Quintet
LZ loops, not more fake roots. `native-010/discovery/CONTINUATION-DESIGN.md`
binds actual009 diagnostic routes and required inherited guest/host watermarks.
Official main remains e98dc63; no vendor replacement or new upstream defect.

Same-binary poll OFF/ON host cohort passes all56 runs/336,000 frames and exact
counter/fingerprint gates. Enabled mixed-native CPU cost is **+2.22% narrow /
+1.97% wide**; forced-reference controls are +1.45%/+1.28%. This is compiled
execution progress with a measured host-cost penalty, so keep the explicit
opt-in/default-off decision. Do not promote it as a speed fix. Receipts:
`native-010/host-cost/summary.json` and `post-audit.json`.
294 completed executable copies/4,151,687,680bytes are compacted to four verified
payloads/20,793,797bytes with restore index. Retain source/superseded builds and
all other evidence; do not recreate old archives. All39 owner inputs and005
remain protected, no new release or installed-game replacement.

## Previous continuation — native batch 009

[Batch 009](docs/NATIVE-BATCH-009.md) qualifies explicit private `--sprite-sorting`
and guarded live WRAM-address reads. Main remains inventoried `e98dc63b`.
Graph: **339 roots / 1,242 contexts / 1,163 eligible / 79 LLE**, SHA-256
`921769c084482ba9c2362338f29cf99bfc1dfa0a91edb4dae01fe05b0d18f28f`.
All 1,154 old emitted bodies are byte-identical; nine bodies are added.
Public CFG/policy and the other interrupt/boot guards remain unchanged.

Private candidate: `.local/batch-001/native-009/build-sort-v2/babel-recomp.exe`,
SHA-256 `8c584f0d841f31c406fbf59265137ba61270cd25ef834e01bbf62d0d5523e7fe`.
Natural native CPU-cycle share: **40.2820% narrow / 40.3216% wide**. Sort's
19,554,714-cycle interpreter reduction accounts for the entire natural gain;
all other per-PC costs are unchanged. Sort retains 1,299 interpreted cycles /
325 instructions under guards/resume boundaries. Do not claim universal AOT.

**77 fresh pairs / 154 complete loss-free captures / 211,440 frames / 1,294
snapshot sets pass** the executed-cycle CPU/WRAM/device/full APU+scheduler/output
contract. New20 covers 16 melee/death rooms, three no-attack controls, one real
player-contact damage case and nine original room-clear rewards. Assistance is
explicit; enemy HP/count/death/clear/rewards were not fabricated. Those new
witnesses are interpreted008 only: no measured008-native gain is claimed there.
All 114 tier-specific controls against008 match; all 57 existing cases gain
native coverage. Private receipt groups are `native-009/qualification-sort-v1`
(29 pairs using the final v2 executable despite the folder name),
`mechanics-sort-v2` (28), `new-mechanics-v2` (20), and
`current-008-comparison/summary.json`. Independent capture/Sort review is in
`native-009/sort-execution-audit/`; do not recreate its completed audits.

Preserve old004 strict failures (17/28 pass). All 191 new native raw APU-clock
files differ from the source witness while canonical full APU/scheduler/state
passes. Broad no-attack actor logs require byte normalization for generated word
versus interpreted byte stores; raw log identity is not claimed. Required fresh
HP/death write contracts are unchanged and pass. The aspect test retains its
19 raw strict differences; all 67 same-binary and 134 cross008 presented frames
match. Copied owner RTLSv10 load passes. No ordinary fresh SAVE/RESTORE,
music/hardware or campaign qualification follows.

49 new live-address tests pass all 12 operations/four M/X combinations, with
27,648 accepted scenarios, 2,304 guarded refusals, 18,432 negative controls,
32 relocated-stack scans and 32 deadline/interrupt continuations. Purity,
cache/CLI, actual-core polling and integration checks pass; 698 existing v2
tests pass (two existing skips), plus all 144 title tests. Invalid fixture/
reviewer attempts and the Windows command-limit failure remain retained.

The largest RDNMI loop **stays LLE**: guard removal fails cooperative quiescence
and real comparator-IRQ retirement. A future native island needs shared exact
per-opcode ring/step, IRQ/deadline/hook/retirement bookkeeping and guest-frame
ownership; private proposal:
`.local/batch-001/native-009/poll-feasibility/PROPOSAL.md`.
Do not fake the latch or skip the wait. Actor script/RTL ownership and Quintet
LZ are separate remaining targets; SPC upload is a hardware audio handshake.

Await Kass's matching dev build, commit, dependencies and selected modules
before GaiaLabs runtime qualification. Keep the two game editions distinct.
The deferred clubhouse/Erik music report remains untouched. No desktop control
is active; installed005 and owner settings/soundtrack remain protected.

Quiet host-cost cohort: all 56 runs / 336,000 frames match exact-build guest
counters and witness fingerprints. Median paired009-vs008 native frame-service
CPU cost is **−5.01% narrow / −3.81% wide**; forced-interpreter controls drift
+2.04% / +0.93%. This is six-pair dummy-SDL software-rendered route evidence,
not general FPS or isolated raster CPU. Private `native-009/host-cost/` retains
all timing, preflight failure and independent post-audit receipts.
209 completed runtime executables (2,906,378,240 bytes) are compacted to two
verified payloads in a 10,315,461-byte archive plus restore index. Source builds
and all other successful/failed evidence remain; no old archive was recreated.

## Previous continuation — native batch 008

[Batch 008](docs/NATIVE-BATCH-008.md) extends execution through the existing
sprite pipeline using opt-in timed live immediate reads. The graph remains
331 roots / 1,233 contexts / 1,154 eligible contexts, manifest SHA-256
`ac3c4cc24cc3e65359f8e4d20878c9230e00c97bb58f9645cd760e929577ed2b`.
Nine function bodies/16 live blocks change; all 1,145 other bodies are unchanged.
The 3,232 effective guard/alias bytes, full Sort interval, mutable ABS refusal,
four NMI-callee exclusions and WRAM restrictions remain. Public policy/CFG unchanged.

Private candidate: `.local/batch-001/native-008/build-live-v3/babel-recomp.exe`,
SHA-256 `10759ef65bbd734b7f6a8601a060e775cddcfbd0a18a91b7a37cdb38686e2f7e`.
Natural native CPU-cycle share rises **14.9396% → 31.4331%** in 4:3 and
**14.9394% → 31.4404%** in wide mode. All 57 current fixtures gain native
cycle share. This is measured execution, not new graph eligibility or campaign proof.

57 current same-binary pairs / 114 processes / 148,240 frames / 912 snapshots
pass the executed-cycle CPU/WRAM/device/full APU/scheduler/output contract.
All 114 separately tier-bound controls against 007 match. A copied-owner pair
and aspect-transition pair add 12,730 frames; 67 same-binary plus 134 cross-007
presented-frame comparisons match. RTLS v10 owner scene/form/HP/flags remain
intact. Raw strict SPC-stamp files retain the same 19 differences; old004 strict
mechanics remains 17/28. Do not waive those failed contracts or infer ordinary
canonical audio SAVE/RESTORE/hardware/campaign qualification.

Independent proof: 59 new execution tests pass across all 12 data-immediate
mnemonics, widths, aliases, decimal/carry, patch/restore and interrupt/wrap
boundaries; 639 other SDK v2 tests pass with 2 existing skips. Title checks and
current policy/option tests pass. Reuse of 007's 379 RomAtlas decodes is bound
to unchanged ROM/manifest/decoder identities; 16 new live bus plans are inspected.

Widescreen candidate removes only the duplicate ~10 MiB reset between adjacent
BeginFrame/BeforeDraw calls. Direct/repeated draws still reset. Reset-only007
control is `d915c2c1...`, identical-current-engine006 control `e934c101...`;
their settings/flags/resources and the final008 build are independently bound.
Keep the interpreter-only default and conservative sprite-prefix option;
`--region-live-immediates` is an additional explicit generation opt-in.

The isolated four-build CPU cohort passes all 64 measured +16 warmup runs
(480,000 frames). Final008 versus original007 median frame-service CPU cost
is **−9.10% narrow / −11.86% wide**, ranges −9.52..−8.83 / −12.17..−11.54.
Reset-only wide improves −3.40%; timed-live versus reset-only improves
−9.18% narrow / −8.66% wide. Same-engine graph007/006 is −0.38% / −0.43%,
so the earlier +4.73% whole-build result does not reproduce in this controlled
frame-window test. Stage CSVs are WALL measurements; frame-service CPU excludes
startup/shutdown/export. Limits and full ranges remain in batch008's report.

Profile validation is also improved: an isolated 229-input pair uses
131.234375 → 5.75 CPU seconds with identical 19,332 decisions/341 raw roots and
all identities/metadata. This is generator cost, not game speed. Reported
official-source bugs: [#265](https://github.com/RetroPortingToolKit/snesrecomp/issues/265)
(repeated boundary canonicalization) and
[#266](https://github.com/RetroPortingToolKit/snesrecomp/issues/266)
(existing first-entry-hook open-bus observation; no demonstrated final-state
corruption). New exact pre-live snapshots use a preceding NOP and do not fix266.

Receipts: `native-008/current-007-comparison/summary.json`, `structural/`,
`live-immediate-proof/FINAL-RECEIPT.json`, `profile-validation/actual-profile-parity.json`,
`aspect-transition/completion.json`, `owner-load/attempt-001/summary.json`, and
`widescreen-cost/`. Installed005 and owner settings/saves/music stay separate;
the deferred clubhouse report remains untouched. No GaiaLabs dev build has
arrived; its edition adapter still awaits the exact recipe/identity. No release.

All 136 title tests pass on final source; SDK v2 is 639 passing +59 separately
executed new cases, with 2 existing skips. Independent source review found no
new actionable bug. Keep the known first-hook/raw-stamp/audio gates explicit.
Completed executable copies are compacted:129copies/1,787,511,296bytes into
four payloads/20,511,733bytes in `native-008/completed-runtime-input-binaries.zip`,
with `runtime-input-binaries-compaction.json` restore map. Builds and all other
evidence remain; no old archive was recreated.

## Previous checkpoint — native batch 007

[Batch 007](docs/NATIVE-BATCH-007.md) qualifies a conservative sprite-prefix
candidate against unchanged integrated SNESRecomp main `e98dc63`.
Its graph has 331 roots / 1,233 variants / 1,154 eligible contexts, retaining
all previous 1,120 eligible contexts. RomAtlas matches all 379 new instruction
contexts; all 3,232 retained guard/alias addresses and four NMI exclusions pass.
The full Sort interval `[03C5FF,03C714)` remains interpreted. Six later mutable
immediates tail to the interpreter before effects; no mutable ABS promotion.

Private gameplay binary: `.local/batch-001/native-007/build-sprite-prefix-v2/babel-recomp.exe`,
SHA-256 `4ccb4637e80307c6f4a6a29a4df4da7f4d8968b84b807fec44896fa6840110f6`;
graph `native-007/sprite-prefix-v2/generated/program_manifest.json`,
SHA-256 `ac3c4cc24cc3e65359f8e4d20878c9230e00c97bb58f9645cd760e929577ed2b`.
57 fresh same-binary pairs / 114 processes / 148,240 frames / 912 snapshots
pass the existing executed-cycle comparison contract; all 114 separately
bound batch-006/007 tier controls match. Natural native CPU-cycle coverage
rises from 12.8307% to 14.9396% in 4:3 and 12.8268% to 14.9394% in 16:9.
Coverage is not host speed, per-entry execution proof or campaign completion.

The separate five-fixture whole-build CPU benchmark completes 120 measured
processes plus 20 warmups with every final-state/tier control passing. Median
new/old native process-CPU changes: natural 4:3 −1.63%, wide +4.73%, inventory
−2.20%, Shadow Aura −1.50%, Viper −2.82%. Wide has observed higher median cost;
pair spread/interpreter drift prevent a general speedup claim. Startup/layout
and diagnostic support are included, so this is not isolated graph attribution.
All owned workloads are stopped. `native-007/host-cost/completion.json` and
`control-analysis.json` retain full pairs/control ranges; contended warmups
are excluded. Keep the preset opt-in; profile/isolate widescreen cost next.

An additional copied-owner F1 pair preserves observed state/flags. Two
6,065-frame in-session 4:3/wide/4:3 runs match, including all 67 presented
frames. Separate TRACE diagnostic `aa71ee49...` checks all ten live cartridge
words at seven stable checkpoints and confirms the existing one-frame latch.
Its identity is separate from the TRACE-disabled gameplay binary.
Raw strict aspect comparison remains failed on 19 SPC host-beam logs;
canonical executed-cycle/full APU/scheduler comparison passes. Historical
mechanics replay remains 17/28 passed. Retain every failure and its scope.
Ordinary audio SAVE/RESTORE and physical hardware gates remain open.

The public `--sprite-prefixes` preset is opt-in and leaves default/public
policy/CFG guards intact. 133 title tests and 44 focused SDK tests pass with
the [updated isolated tools](docs/TOOLS-NOV08.md). The installed 005 game,
owner settings/saves/music remain separate; no release was created and the
deferred clubhouse music report was not investigated. New confirmed Windows
TCP screenshot JSON escaping bug is reported upstream as
[#264](https://github.com/RetroPortingToolKit/snesrecomp/issues/264).

[Edition identity contract](docs/GAME-EDITIONS.md): at least Original and
GaiaLabs, with separate future save/settings/native namespaces. No edition
picker/import adapter is enabled. Kassiven says his work is in development
and may take a month to clean up; a rough current snapshot with source/module
recipe is sufficient to start compatibility work. The owner has a suggested
DM reply, but no agent sent a DM and no dev build has arrived.

Private receipts: `native-007/current-006-comparison/summary.json`,
`native-007/structural/`, `native-007/refusal-proof/`,
`native-007/aspect-transition-runtime/FINAL-RECEIPT.json`,
`native-007/owner-load-check/attempt-001/summary.json`, and
`native-007/public-preset/`. Keep all evidence beneath the single ignored
`.local/batch-001`. Do not recreate the completed batch-006 archives below.
Final fixed-driver reproduction receipt is
`native-007/public-preset/fixed-driver-cache-hit-receipt-attempt-003.json`:
48 banks reused, zero emitted, all 88 outputs plus `funcs.h` exactly match
the executed graph's inputs. Earlier short timeouts and different-analyzer
metadata remain separate failed/nonmatching evidence.

Completed batch-007 run binaries are deduplicated separately: 121 copies
(1,670,158,848 bytes) map to two verified payloads in the 10,547,919-byte
`native-007/completed-runtime-input-binaries.zip`. The adjacent
`runtime-input-binaries-compaction.json` maps original relative paths and
receipt hashes to archive members. Build executables, all receipts, scripts,
states/captures and failed evidence remain; no old archive was recreated.

## Previous checkpoint — native batch 006

[Batch 006](docs/NATIVE-BATCH-006.md) integrates checked SNESRecomp main
`e98dc63b474d5469ad984490e04eb0b0496ec62e` with full preservation inventory.
The expanded private graph has 328 roots / 1,199 variants / 1,120 eligible
candidates; 19 new node contexts include 16 eligible candidates and three
retained LLE contexts. All previous guards and four NMI-callee exclusions remain.
RomAtlas independently matched 274 new instruction contexts.

Private candidate: `.local/batch-001/native-006/build-expanded-v2/babel-recomp.exe`,
SHA-256 `c028093dee06ba4ebcfbce97659ff37fe41ee87b0a98cc70edd3c31c9002dfda`;
graph `.local/batch-001/native-006/expanded-v2/generated/program_manifest.json`,
SHA-256 `a5acf97ce11e900aded284ef3357a3cdbb690b64b22b8607532f5ab6cf5513ba`.
57 current same-binary pairs / 114 fresh processes pass CPU/WRAM, cycles,
device logs, full APU/scheduler and final output. Two inventory fixtures show
small native-cycle gains; the natural route remains 12.8307% / 12.8268%.
An independently copied current owner RTLS v10 state also loads correctly;
owner scene/form/HP and story flags remain intact, with strict new-tier parity.

Do not overwrite the installed 005 binary automatically. Strict historical
mechanics replay remains 17/28 passed; failed cross-version witnesses remain
failed. A private A/B reversing only upstream #258 attributes the full natural
route's changed CPU/WRAM/APU timing to its corrected no-overshoot scheduler.
A 353-pixel frame-1500 presentation difference remains unisolated. Ordinary
audio SAVE/RESTORE, physical audio/controller/GPU and current host-cost gates
remain separate and unqualified. No release was created.

The offline GaiaLabs module inspector has 17 synthetic checks and a passing
real pinned-source preflight. The actual raw-map override/rebuild path is now
traced; see [module integration](docs/GAIALABS-MODULE-INTEGRATION.md).
Mesen2 MCP 0.6.0 has a private headless readiness check (81 tools, 15 checks),
with owned process stopped; it is not external parity proof.
[Reference operation](docs/MESEN2-REFERENCE.md).

All 100 title Python tests pass. [Framework results](docs/FRAMEWORK-NOV08.md)
retain platform/setup failures and two inherited MSU fixture failures explicitly.
The stale local folded-branch workaround was removed; maintainer #250/#251
heads already contain the correct shared cost handling and were not overwritten.
The verified official Linux C-test link bug is reported as
[#263](https://github.com/RetroPortingToolKit/snesrecomp/issues/263), with the
one-line local test-link repair. No deferred music fix was attempted.

Completed per-run executable duplicates are compacted: 184 copies (2.51 GB)
map to four checksum-verified payloads in the 20.3 MB private
`native-006/completed-runtime-input-binaries.zip`, indexed by
`native-006/runtime-input-binaries-compaction.json`. Retained build binaries,
all receipts, scripts, states, traces and output evidence remain in place.
Restore a copied run executable from the indexed payload if needed; do not
recreate these completed archives.

Next stock-ROM native lead: `native-006/discovery/culling-feasibility.json`
records eight mutable immediate sites versus two mutable absolute-address
sites. Existing `live_operand` refuses the latter. Keep the complete
`SortActorsByDepth` range `$03C5FF..$03C714` interpreted in any experiment;
six remaining immediate-only sprite sites could use conservative refusal.
Paired-owner unwind and current source/cache/alias identity still need focused
execution proof before any public guard narrowing. The current guard is intact.

## New GaiaLabs developer references

**Pending owner DM:** on November 8 the owner was told this is the point to
request the offered current dev patch/build, exact source commits, ordered
module selection, dependency lock, output ROM hash and `.bso` if needed.
Public branches are unchanged; package Git heads differ from current source,
and the public development script selects Apocalypse Gaia while leaving the
new minimap-v2/widescreen commented out. Do not invent the intended profile.
No developer build has been received and no DM was sent by the agent.

The owner relayed the developer's current baserom docs and patch tree on
November 6. [Developer notes and integration queue](docs/GAIALABS-DEVELOPER-NOTES.md)
record both links, inspected revision, the older-library warning, options menu,
key-item auto-use, full world-map movement, new minimap and widescreen-room
reports. Options/auto-use source was located. The later `IOGRetranslation` dev
module link locates the new minimap, walkable-world-map and bsnes-hd widescreen
code/maps, including `sc08`; see the notes for exact identities and dependencies.
Its inspected rebuild script leaves minimap-v2/widescreen commented out. Native
compatibility remains untested. Consult this before the next native batch.
The same note also records the developer's Gaia Mapper (`maps.gaia.studio`)
and Gaia Spriter (`sprites.gaia.studio`) links; initial page HTML was inspected,
but editor operation and native import/export compatibility remain untested.
Screenshot follow-up records raw editor-map import during rebuild, the request
to work directly with current code, and `Azarem/mesen2-mcp` 0.6.0 as a reference
testing lead. Its docs were inspected; no MCP installation or connection was made.
No game code or owner data changed during the November 6 reference collection.
The November 8 work is recorded above. Older checkpoint details below retain
their original dates and are not claims about the newer candidate.

## Deferred owner report — clubhouse music

November 3, 2026: music stopped in the clubhouse when Erik entered with the
message about the missing princess. Leaving the clubhouse did not restore
music. Loading the clubhouse save with F1 restarted it. Owner explicitly asked
to record this only and defer investigation/fixing because weekly usage is
nearly exhausted. User-reported; not independently reproduced or diagnosed.
No game code, save, or settings changes were made for this report.

Installed local build (unchanged): [widescreen/mod batch 005](docs/WIDESCREEN-MODS-005.md),
SHA-256 `00429989aabf5cf2d0d0ee9846fa7a2fd490185237863c5aa587c078b280e8bd`.
South Cape margins now use live decoded map data; the classroom uses an explicit
authentic-width terrain fallback. The run option was disabled in the owner's
settings and is now exposed under Convenience. Inventory/dialogue dash leakage,
live cheat option loading and immediate-load MSU track startup are corrected.
Owner saves/settings/bindings/music were not changed. Earlier 16:9 tier parity
did not establish correct offscreen content; retain that distinction.

## November 3 framework contribution checkpoint (historical)

The maintainer requested three focused timing PRs. Their reviewable source
patches and current qualification limits are in
[contributions/snesrecomp/205](contributions/snesrecomp/205/README.md).
They were [delivered upstream](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6614160563)
with 640 passing source tests, two existing skips and 56 matched cost runs.
The prerequisite fixes merged during batch-005 verification: upstream main is
now `f6912cd74e06eb21329aeb5c929d7f374479db80`. The changed-file preservation
inventory and three-way integration are complete, with 644 Python tests and
12 Rust tests passing. The verified 5ed0138 checkpoint remains private and
separate from the freshly checked current merged-head executable. The refreshed
three-patch timing series now applies to f691 and passes 643 source checks with
two existing skips. The owner separately authorized the new public framework
fork and PR submission: [#248](https://github.com/RetroPortingToolKit/snesrecomp/pull/248)
is ready for review; [#250](https://github.com/RetroPortingToolKit/snesrecomp/pull/250)
and [#251](https://github.com/RetroPortingToolKit/snesrecomp/pull/251) are stacked
drafts with focused diff links and explicit dependency/qualification limits.
Initial upstream fork CI reports `action_required`; local passing tests are
separate from upstream workflow approval/results.
The [rebased source and integrated results were delivered upstream](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6615719490).
Do not duplicate the merged repairs or present the old preparation base as the
requested merged base. Extracted-stack source
checks pass, but fresh ordinary current-build save/load revealed a canonical
audio-continuation difference shared by both tiers. The strict failed check is
recorded in the [consumer report](contributions/snesrecomp/205/QUALIFICATION.md).
The game/vendor source and selected executable remain unchanged by this
upstream contribution preparation. The separately authorized
`rages4calm/snesrecomp` fork hosts the engine series. No game release exists.

Batch 004 established a **route-qualified private mixed-native baseline**, with a fixed
combat input/vblank ownership bug and **61 matched cases / 122 fresh runs**.
The natural
6,000-frame classroom-to-South-Cape route matches retained interpretation in
4:3 and 16:9. Native CPU-cycle shares are **12.8307% / 12.8268%** respectively;
this is partial native execution, not a fully native game or campaign proof.
[Current evidence, failures and reproduction](docs/NATIVE-BATCH-004.md).
The corrected input model changes the workload; earlier percentages are not
direct performance baselines. Actual assisted kills/rewards at 1x/8x, seven
ability effects with nine controls, four boss defeats and four 16:9 stress
cases now pass. Boosted boss stats do not qualify normal weakness timing.
Also verified: 23 assisted area visits across all four guide parts, two inventory
open/return cases, and original Freedan/Shadow transformation roundtrips.
The teleport prerequisite was an undismissed scene-title input loop. Source
request context and real Dark Space prerequisites are now recorded; assistance
does not count as earned story progression.

Tested batch-004 source is published at
[`1ea3ab4`](https://github.com/rages4calm/babel-recomp-companion/commit/1ea3ab4a46af8a5d39f8ab991990c88b36fd31d5).
The combat input/vblank ownership bug is reported as
[upstream #242](https://github.com/RetroPortingToolKit/snesrecomp/issues/242),
with the ROM-free actual-core reproducer. Earlier batch-003 source is published
at `bf826a377ff608fd4c524ba0e67b315c9c4fe4ee`.
Default v2 indirect bank-carry mismatch is reported as
[upstream #240](https://github.com/RetroPortingToolKit/snesrecomp/issues/240),
with a ROM-free reproducer; this is separate from the tested opt-in pointer
recipe. Current timing results extend the existing
[#205 discussion](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6589796017).
No release was created.

## Current source and decisions

- Fork: `rages4calm/babel-recomp-companion`; original Babel author **mr0ta /
  mrOt4**, support link, full credits and licenses preserved. Lagoon, EarthBound
  and shared Companion projects were read-only references.
- Latest checked/integrated SNESRecomp source: `e98dc63b474d5469ad984490e04eb0b0496ec62e`.
  Batch 006 above records current source and candidate identities. The installed
  005 executable retains `f6912cd74e06eb21329aeb5c929d7f374479db80`.
  A three-way preservation audit retained Babel's game-specific changes;
  `framework_pins.txt` also records the matching nested-library versions.
  [Current changed-file integration and fresh checks](docs/FRAMEWORK-F691.md).
  Newly opened upstream [PR #241](https://github.com/RetroPortingToolKit/snesrecomp/pull/241)
  changes APU/DSP/DMA timing but is unmerged and was not adopted in this batch;
  integration needs a delta inventory and fresh qualification after review.
  The pinned Babel UI has two appended seed-compatibility fields; Gaia uses
  its existing in-game settings overlay, with the new Mode 7 control migrated.
- CompanionLauncher 0.2.0 packages are pinned; the game adapter preserves native
  INI/bindings, rejects stale writes and avoids creating partial first-run configs.
  Mode7Enabled and Off/On/Adaptive VSync reflect the updated engine. Full remapping
  and mod management remain available through Babel tools.
- RetroAchievements service/account support is compiled out, including its
  rcheevos/HTTP backend. Original sources and attribution remain. Official policy,
  the standalone/client distinction and verification are [documented](docs/RETROACHIEVEMENTS.md).
- CompanionAchievements 0.3.0 core/presentation and a guarded observation adapter
  are present, **not yet connected to live unlock/storage/UI/audio**. Follow the
  [integration worklist](docs/ACHIEVEMENTS-INTEGRATION.md); never infer unlocks
  from a loaded save or copy the RA set.
- Dedicated launcher **Cheats and Mods** shares native settings with the in-game
  menu. Source-guarded room-clear rewards support 1x–8x; no movement multipliers.
  Cheat eligibility is sticky for the process session, ready for future live
  achievements. [Controls](docs/CHEATS-AND-MODS.md), [engine guards](docs/CHEAT-RATES.md).
- New transparent game/launcher icons are embedded at nine Windows sizes.
  [Artwork, provenance and converter](res/branding/README.md). Computer-control
  runtime was released after visual checks; previews are closed.

## Retained batch-004/005 evidence

| Check | Result and boundary |
|---|---|
| Windows source builds | Interpreter-only and private generated-code builds linked with Clang/Ninja. Final development package is interpreter-only. |
| Stock cold boot/input | 3,600-frame CPU/WRAM traces matched between the two configurations; final interpreter build reproduced hash `a5573d387c5a744337f72410902330e4d2c2388abf310559feafc763a599bd64`. Visible sea/intro text checked; 342x224 and 256x224 framing captured. |
| Native execution | Batch 004: 312 roots, 1,180 variants / 1,104 eligible candidates; all earlier roots/eligible variants retained. Actual corrected-route native share **12.8307% in 4:3, 12.8268% in 16:9**. A source-verified separate math leaf was removed from the polling range; 6,224 explicit PC/alias guards and inherited function exclusions remain. Counts are not executed/qualified-function coverage. |
| Natural gameplay comparison | 6,000 frames from cold boot through classroom dialogue, directional movement and the South Cape transition. Exact CPU/WRAM trace, CPU/master totals, 13 memory/PPU/APU/DSP/PCM-ring/port-scheduler snapshots, DMA/PPU journals, and full final output including widescreen margins. CPU audio-event stamps match; batched SPC beam tags are explicitly separated from matching event/sample/state evidence. |
| Framework regressions | Current merged framework: 644 Python tests pass with 2 existing skips; 75 title generation/comparator/replay tests and 243 subtests pass separately. Twelve Rust checks pass. Actual scoped-read/RDNMI/IRQ/snapshot and parser/ticker checks pass, as do 432 bridge checks per bus mode, CPU bus/latch and 27 interrupt-tail checks. |
| Assisted areas/mechanics | 23 area entries, inventory and corrected form roundtrips; six actual room-clear reward cases, two no-repeat reloads, seven original ability effects plus nine controls, and four continuous boss fights pass on one final binary. Fresh Castoth/Viper HP-zero writes are required. Four additional full-width 16:9 stress cases pass. Exact SPC cycles, full audio/PCM/queue state and output match. Explicit stats/positions/learned bits/item assistance; no earned story or normal boss difficulty claim. |
| Launcher/mods/icons | 30 adapter +47 importer +7 activation +21 native-mod tests. Room-reward helpers/source: 136 assertions; actual callbacks with host stubs: 656 assertions. Final-engine assisted 8x/native versus 8x/interpreter comparison passed; separate 1x control passed 8 reward-effect assertions. Native launcher UI/draft/Revert and its title-bar icon reviewed. Both rebuilt PE icon groups match all nine source ICO frames. |
| Achievements foundation | 100 synthetic checks through the actual shared core/presentation. No live unlock claim. |
| Music import | 47 importer checks plus 7 native activation checks. The owner's JUD6MENT ZIP imported once, all 28 track hashes verified, original credits DOCX retained and original ZIP hash unchanged. |
| Music runtime | Four paced 900-frame cases: full JUD6MENT pack, absent selected folder, partial synthetic pack missing title track, and original audio. All booted/captured output and delivered samples to SDL's dummy device. Full pack started title track 1; absent/partial selections retained original audio. |
| RomAtlas | Current 8,192 mechanic/route contexts passed: 3,122 new decodes, 5,070 identity/byte-matched reused checks, zero mismatches. All 248 cartridge transfer targets checked; three WRAM targets remain unverified/interpreted. Separate 72-context math-leaf audit. Structural evidence only. [Method/provenance](docs/ROMATLAS-PLAN.md). |

No physical controller, speaker output, campaign, natural combat reward,
save-state music restoration or non-Windows gameplay has been qualified here.
Assisted/teleported/flag-edited checks have separate receipts and do not extend
the natural route's cold-play scope.
[Assisted testing](docs/ASSISTED-TESTING.md) records every injected field, the
checkpoint dependency and failed probes. Current assisted proof covers
actual assisted combat/rewards, seven ability effects, four bosses, 23 area
entries, inventory and form roundtrips. It does not establish earned campaign
progression, unboosted boss timing, every puzzle or original healing timing.
Early failed receipts remain failed: the inherited AOT build differed at frame 1;
an initial bridge merge missed initialization; early harness runs used invalid
button/aspect spellings or accepted black captures; a missing optional-pack path
blocked boot before the fallback fix. Later checks supersede only their stated
scope. Batch 002's failed aggregate, instruction-only, first pacing and
pre-credit/pre-PB candidates remain failed; see its detailed note.

## Working local artifacts and reproduction

```powershell
./scripts/build_windows.ps1
./companion/build.ps1 -Test
./companion/bin/Release/net8.0-windows/illusion-of-gaia.Companion.exe
python scripts/test_package_release.py
python scripts/package_release.py build windows-x86_64 --companion companion/bin/Release/net8.0-windows
```

The shared launcher package feed is the sibling CompanionLauncher checkout.
The compiled engine is `build/babel-recomp.exe`, currently the selected private
mixed-native build (SHA-256
`00429989aabf5cf2d0d0ee9846fa7a2fd490185237863c5aa587c078b280e8bd`).
Its unchanged graph/source lives only under `.local/batch-001/native-004/expanded-v2/`;
`inputs/` there retains the earlier immutable `fa3a2502…` baseline. The current
frozen executable is `.local/batch-001/wide-005/build/upstream-f691/babel-recomp.exe`.
The earlier `5ed0138b…` checkpoint stays in `wide-005/build/selected/`.
Fresh visual/control/music evidence is under `wide-005/`. The older proof index is
`native-004/selected-proof-index.json`; replay plans/reports are under `replay/`.
`./scripts/build_windows.ps1` still builds an interpreter-only package candidate;
use `-NativeBatch .local/batch-001/native-004/expanded-v2 -Jobs 2` to restore
this private native build. Set `SNESRECOMP_INTERPRET_ALL=1` for retained fallback
in the same mixed executable; clear that environment variable for native play.
The one verified local music
copy is under `build/msu1/companion-packs/`; native selection is enabled in
`build/mods/preloaded/state.toml`. Use **Soundtrack → Use original audio** to
disable it without deleting music. Download opens the credited provider in the
browser; ZIP/folder import is local. [Instructions and musician credits](docs/MSU1.md).

`scripts/check_baseline.py` creates a fresh isolated runtime fixture and validates
CPU/WRAM trace and nonblack PPM evidence. `scripts/check_msu_runtime.py` creates
isolated full/partial/missing/off fixtures that reference the one private pack.
Detailed logs, failed receipts, captures, original upstream release and dependency
preservation records remain in the single ignored `.local/batch-001/` scratch batch.
Completed batch-003 v2/v3 raw run blobs are compacted in
`native-003/failed-expanded-v2-v3-raw.zip`, with a per-file verified SHA-256 index
in `failed-expanded-v2-v3-archive.json` there. Their failed receipts, manifests,
journals and seeds remain in place. Selected v4 evidence remains unpacked.
Batch 004 consolidates 1,586 duplicate runtime input files (about 2.1 GB) into
the immutable `native-004/expanded-v2/inputs/` copy, with per-file hashes in
`native-004/duplicate-runtime-inputs-compaction.json`. All 122 run receipts,
traces, snapshots, outputs, captures, settings and seeds remain in place.
Automatic approval review blocked deleting its downloaded framework checkout
(`blocked by policy`); it remains isolated there. Do not retry through a bypass.

Packaging checks both CMake mode and a retained binary execution identity,
rejects private/player data, stages source-reviewed mods rather than runtime
preferences, and includes applicable dependency notices. Music, ROMs, generated
game code, tokens, saves and gameplay captures are excluded. No public release
is authorized or published. Tag builds no longer publish automatically.

## Next bounded work

0. Obtain the developer's current profile identity via the pending owner DM.
   Use `scripts/inspect_gaia_modules.py` with clean exact commits and dependency
   metadata, then build/import that precise external profile privately. Preserve
   module order, raw-map companion actor/warp changes and all credits/licenses.
   The public 22-module script is not assumed to be the intended build.
   Continue from batch-006 receipts, not the obsolete pre-rebase patch branches.

1. Extend the qualified cohort from the current natural route and the 23
   source-backed area/form contexts, using
   [guide milestones](docs/GUIDE-RESEARCH.md) and explicitly recorded assisted
   teleports/flags/cheats. Attack/remap, assisted kills/rewards, all seven ability
   effects and four boosted boss completions are verified. Next pursue earned
   abilities/story, unboosted boss phases, broader form-dependent puzzles and
   missing transfer boundaries. Preserve the four inherited NMI-callee CFG
   exclusions until their original mode/DMA issue has its own verified repair.
2. Expand 16:9 actor/terrain/camera/dialogue coverage beyond the qualified
   classroom/South Cape route before extending to 21:9/32:9. Existing raw SPC
   beam-tag differences are diagnostic batching metadata; preserve the strict
   failed receipts and require raw-bound event-time SPC cycles plus matching
   APU state/PCM/queue in `--apu-clock cycles` mode. Batch 003 v2/v3 remain failed;
   v4 corrects extended absolute scheduling markers and boundary flushing.
3. Wire durable local achievements with verified event hooks and explicit restore/
   rewind/profile generations, then shared browser/toasts/chime and launcher view.
4. Build scenery map, story-flag journal and spoiler-controlled jewel assistance
   from actual game state; preserve Gaia's form-dependent puzzle requirements.
5. Add music transitions/one-shot/save-state coverage and physical device checks;
   qualify release packages/platforms separately before requesting publication.
