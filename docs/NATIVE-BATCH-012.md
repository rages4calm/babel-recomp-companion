# Native batch 012 — broader game logic and indexed continuation lookup

November 9, 2026. Original USA edition. Based on Babel Recomp by mr0ta / mrOt4;
all inherited credits and license notices remain intact.

## Implementation

The fixed-instruction emitter now supports the eight conditional branches,
BRA/BRL and direct absolute/long jumps. Indirect transfers, stack/call/return
frames and width changes remain outside its emitted subset. The existing
bridge already supports static effects; this does not remove its scheduler,
interrupt, mapper, source-byte, live-PC/mode or policy guards. Each compiled
effect still retires through the original per-opcode event loop and performs
the actual ordered bus fetches. It never calls or relabels the opcode decoder.

The finite selection retains all 240 prior source contexts and adds **1,000
observed contexts**: 756 ordinary operations and 244 static control operations.
Combat, actors, player processing and camera logic supply the largest groups.
This changes execution tier, not movement speed, controls or game balance.
The plan has **1,240 source contexts / 4,960 physical-alias descriptors / 93
fixed opcode bodies**. RomAtlas independently checks 913 new contexts and
87 exact previously verified contexts; no unobserved ROM sweep is substituted
for runtime observations.

A direct PC/MX index replaces per-page binary search when continuations are
registered. The legacy path remains available with
`SNESRECOMP_NATIVE_INSTRUCTION_INDEX=0`; the launch selection is cached.
Both representations are constructed before atomic registration commits.
Allocation failure, conflicts, capacity overflow and active-owner mutation
refuse without changing the old registry, indices, counters or launch setting.
The final exact-key and full-byte checks remain. This is a metadata lookup,
not a code-validation cache or an event/clock shortcut.

At this cohort's 292 pages the two indices total **991,232 bytes**, excluding
the descriptor array. Capacity and allocation tests also exercise 8,192 sparse
pages. Their fresh capacity allocation and observed first idempotent rebuild
peak are distinct from the larger retained-allocation upper bounds; see the
private index receipt rather than treating an initial allocation as a universal
peak. Clearing frees the indices; no guest state is serialized differently.

The title's optional exit-only site diagnostic identifies `direct` or `legacy`.
`IOG_NATIVE_CONTINUATIONS=1` and the separate `IOG_NATIVE_RDNMI_POLL=1` remain
private experimental opt-ins. Default source builds, forced interpretation and
unsupported contexts retain fallback. No launcher feature switch is added.

## Source and build identity

Official SNESRecomp remains inventoried `e98dc63`; its current source and the
GaiaLabs public heads were checked without replacing the vendor tree.
The current managed toolchain and qualified same-branch Python are retained;
newer standalone Python/LLVM major versions are not silently substituted for
the tested toolchain. `interp816.c/h`, guest layouts and all four NMI fallback
floors remain unchanged. [Framework inventory](FRAMEWORK-NOV08.md).

The new graph has **374 roots / 1,327 contexts / 1,244 eligible / 83 LLE**.
All **1,233 previous emitted bodies are byte-identical**; 11 are added and all
65 new instruction contexts pass independent RomAtlas decoding. All 437 older
source observations are retained with 161 current inputs. Cache/source review
recomputes all 598 capture hashes and validates 87 generated outputs. Public
CFG/policy and the 2,124 effective guarded addresses are preserved.

| Private artifact | SHA-256 |
|---|---|
| `native-012/build-final/babel-recomp.exe` | `8a0634d39b8ccdb85ea3035974770c5e6082e74c8556aadd7a3f6f800bd1887b` |
| `native-012/graph-final/generated/program_manifest.json` | `8323a2febc32322842e0f8010ef408e2258d548d3612ec03e70a4285bdf24add` |
| `native-012/effects-final/native_continuations.c` | `40ebbcf27f56f31733001fde494d0d2e8cb37ff9b20df3ae59bc3a78c39808d5` |

Generated game code, ROMs, binaries, music, saves and private captures are not
published. The owner installation remains batch005. This is a source update,
not a new release or installed-game replacement.

## Execution proof

**791 v2 tests pass, two skipped; all 24 focused effect tests pass.** The title
and cleanup script suite also passes all 167 tests. The emitter
proof executes 1,383,168 paired scenarios / 4,185,560 checks, including 55,824
claimed hardware word paths. The focused tests are part of the SDK gate, not
24 additional tests to add to its total.
All missing-fetch, duplicate-fetch, stale-immediate and stale-target mutations
are detected. All 217 admitted opcode forms retain actual-core comparison.

Both lookup modes pass **11,583 actual-bridge branch pairs / 363,092 checks**,
covering flags, aliases, forward/backward/page/bank wrap, self-loops, every
deadline 1..160, IRQ/NMI/nested frames and hook/mode/source refusal cases.
The decoder-relabel, clock, target, duplicate-fetch and stack corruptions fail
as intended. Atomic/index tests pass 65,660 checks in each mode, including
allocation failure at all stages, live statistics, idempotent capacity, exact
miss keys, sparse pages and clear/active-owner refusal.

**161 fresh pairs / 322 complete loss-free captures / 576,680 frames / 2,834
snapshot sets** pass canonical CPU/WRAM/devices/full APU+scheduler/output.
The official loader validates complete journals and identities. Independent
saved binary/frame/trace and exact cost partitions also pass. All **272 actual
same-tier011 controls** pass. Source-semantic and normalized writer facts for
the old50, previous29 and new25 groups are independently reviewed.

Continuations retire **240,893,674 instructions / 866,551,101 cycles** across
the cohort. Site sums exactly match global totals; reference native totals are
zero. **1,211 actual alias/mode contexts** execute in banks80/82/83/85/88/8A/8B;
compiled descriptors elsewhere are not claimed as executed. For all136 older
cases, lost interpreted work equals new continuation work after subtracting
the old native counters: **343,826,781 additional native cycles**. Every other
per-PC cost and poll counter stays unchanged; there is no extra old-case gain
silently attributed to the 11 added generated bodies.

The natural 6,000-frame route reaches **89.3792% narrow / 89.4043% wide**,
versus86.5089%/86.5343% in011. Narrow cycle partition:

| Execution path | Guest CPU cycles |
|---|---:|
| Generated bodies | 89,016,872 |
| Compiled polling effects | 94,378,505 |
| Compiled continuations | 14,118,359 |
| Interpreter | 23,470,246 |
| Total | 220,983,982 |

These shares measure bounded guest execution. They are not campaign coverage,
development completion percentages, a 60-FPS guarantee or a native-only
qualification. Polling is a large part of the count. Protected interrupt/core
paths and other unsupported operations remain interpreted.

## Additional original-game mechanics

The new25 routes cover six original ability grants and their six known-orb
revisits, five chest item/fanfare branches, four opened-chest reloads,
full-inventory and empty-chest controls, and Moon Tribe trial success/timeout.
They have 83,500 source-reference frames, 142 source snapshot sets, 11 wide
cases and 21 strict original writer events per fresh tier. Acquisitions execute
the original grant, conversion, dialogue, walking and authored return paths;
learned-ability/form/control bytes are not used to manufacture those grants.
The full-inventory negative fixture explicitly prepares 16 Herb slots; this is
private test setup, not an earned inventory. Full-inventory, empty-chest and
Mushroom Drop fixtures use explicit **255 DEF** to bound enemy interference.
The Mushroom fixture's earlier grant followed by a respawn still fails its
scene contract and remains excluded.

Trial success uses explicit **255 STR / 40 DEF / infinite HP** and assisted
player positioning. Actual melee reduces the enemy count from 6 to 0; original
code opens the gate and grants statue item04. The matched no-attack control
uses the same assistance, times
out with six enemies at 6 HP and no reward, and starts with all 15 initial
artifacts byte-identical. The broad six-actor death watch reached its
100,000-line cap and remains excluded. A separate loss-free two-byte first-enemy
forced-reference watch matches the reward-watch run's canonical state/output
and qualifies that one original strict death store. It does not establish six
loss-free strict death-store
captures. The fresh trial pair separately preserves the complete initial/final
actor states and strict original gate/item reward stores.

GaiaLabs' newer assembly input masks differ from stock. Final grant witnesses
use verified stock input behavior and actual ROM/writer checks; the earlier
patched-source explanation is superseded. Garden crossings, failed setup
attempts, capped diagnostics and source/decoder calibration failures remain
recorded. These are assisted test paths, not naturally earned campaign proof.
New25 native shares77.5897–93.6919% establish execution on those cases; their
old011 witnesses are forced-reference only, so no old-native gain is claimed.

The cohort retains **1,415 raw APU clock-file differences**. Historical004
strict mechanics remain17/28; all28 fresh pairs pass. Existing logical reload
checks do not establish raw fresh SAVE/RESTORE core/APU/scheduler identity.
Vampire bomb rescue and the deferred clubhouse/Erik music report are untouched.
GaiaLabs dev-build/module identity remains pending, separately from Original.

## Supplemental controls and performance

Passive copied-owner load passes300frames per tier without changing original
inputs. The aspect transition pair matches67 same-binary and134 cross011 full
presented frames; its19 raw strict failures remain retained. Continuation-off
controls restore82.9903%/83.0169%, with zero continuation counters and exact011
off-path counters/state. Three legacy lookup pairs match all4,960 site counts
and all six direct-tier full-state controls, including zero raw clock differences
between lookup modes. No owner story/music probe is implied.

The lookup microbenchmark is deliberately separate: 48 alternating passes over
four synthetic orderings derived from actual probe histograms, with559,984
parity queries and identical checksums. Its lookup-only CPU reductions do not
establish game speed. Renderer stage diagnostics identify wider raster capture
as the main elapsed-time increase in two old011 routes, with nearly unchanged
guest time; they measure wall time and were not an exclusive CPU benchmark.

The final game benchmark uses the frozen011 build, final012 direct lookup and
the **same012 binary** with legacy lookup:42 sequential processes /252,000frames,
six warmups and36 measured runs. Each aspect has six balanced A/B/C orders.
Full forced-reference correctness gates precede timing; this batch times only
the native tier. Every stripped run matches its exact-build/tier final witness,
all guest counters and the actual requested lookup mode. Exit-only diagnostics
stay outside frame-service timing. Resources, compiler and build flags match.
011 imports SDL while012 builds it locally; the discovery paths differ, but
the linked static library bytes, all public headers and generated revision match.

| Paired median frame-service process CPU change | 4:3 | 16:9 |
|---|---:|---:|
| Final012 direct versus011 | +0.3671% | +0.2955% |
| Final012 direct versus same-binary legacy | -0.8147% | -0.5826% |
| Final012 legacy versus011 | +0.7912% | +1.1803% |

Overall CPU cost is roughly flat; this batch does **not** demonstrate a game
speedup. Narrow old/new paired results range from-4.19% to+14.44%; wide results
range from-0.19% to+1.81%. Keep the dispersion, rather than selecting an outlier
or dividing unpaired medians to replace the paired statistic. Direct lookup is
modestly cheaper in this measurement, without a significance claim.

The final direct wide/narrow service medians differ by-0.78%, but these are
separate sequential cohorts with overlapping variation. This is not an isolated
widescreen renderer CPU measurement or evidence that widening is free/faster.
The earlier stage diagnostics distinguish raster-capture overhead from guest
execution; stage wall time remains separate from exclusive CPU. Tests use dummy
SDL/software output, no audio/VSync/per-frame dumps, and exclude startup/exit.
No physical FPS, GPU/audio, campaign or general renderer-speed claim follows.
All42 saved run/log bindings pass the independent post-audit.

## Project cleanup

The owner requested cleanup after the folder reached61.67GiB logical. The bulk
was private validation output and copied runtime assets.495 old runtime copies
were fully hash/receipt checked and compacted into11 payloads, reclaiming
6,363,353,316 net bytes. Unknown/master candidates remain intact; no prior
archive is recreated.

The first cleaner had a real scale problem: repeated receipt/ancestor validation
left a166,156-file plan busy without creating an archive. The owner stopped it;
no originals had been removed. Transaction-scoped caches and live phase progress
are tested against the real plan, preserving mutation-time containment/reparse,
owner/pin protections and archive roundtrip checks. [Cleanup/restore usage](PROJECT-CLEANUP.md).

After all 272 old011 same-tier comparisons completed, the enumerated redundant
011 raw outputs were **retired directly, not archived**: the completed receipt
records 44,898 files / 6,661,494,933 bytes. Their receipts, metadata, scripts,
source profiles, saves and build masters remain; the removed raw snapshots and
traces are not recoverable through an archive restore index. Earlier archived
cold-output cleanup is a separate operation.

Current 012 raw qualification evidence is retained. Disposable runtime copies
use a verified master restore map; the map restores matching binaries/fonts,
not retired raw captures. Owner saves/settings, installed005, ROM/music and
protected masters remain outside the retirement. The final full inventory is
**22.583 GiB logical (24,247,954,336 bytes)**, down from61.670 GiB, before the
small host-timing run folder. All39 protected owner file hashes still match.
Obsolete wider-render/upstream raw outputs and rebuildable Rust intermediates
were also directly retired;76 upstream test executable copies matched a retained
master and have their own restore map. Logical totals do not measure allocated
physical space where hardlinks are involved. No further raw archive is needed.

## Private receipts

All relative paths below are under ignored `.local/batch-001/`:

- `native-012/candidate-final-identity.json` — compiled source/build bindings.
- `native-012/structural/CLOSEOUT.json` — preservation, decodes/cache and old50 controls.
- `native-012/discovery/effects-proof/FINAL-RECEIPT.json` — fixed-effect execution/mutations.
- `native-012/protocol-design/INDEX-FINAL-RECEIPT.json` — actual-core/atomic/index proof.
- `native-012/counter-audit/fresh161-capture-audit.json` — complete fresh capture/counter proof.
- `native-012/counter-audit/cross011-root86/summary.json` —172 old-tier controls.
- `native-012/new-mechanics-final/independent-review.json` — new25 original events/limits.
- `native-012/previous29-final/independent-review.json` — previous29 custom original facts.
- `native-012/cleanup/TOOL-CACHE-FINAL-RECEIPT.json` — scale/safety/progress checks.
- `native-012/cleanup/previous011-raw-retirement.json` — direct retirement inventory.
- `native-012/cleanup/runtime-master-restore-map.json` — matching disposable runtime masters.
- `native-012/cleanup/FINAL-RECEIPT.json` — final folder inventory and protected-file checks.
- `native-012/host-cost/post-audit.json` —42 timing processes, counters, modes and paired ranges.

For earlier archived cold outputs, restore the exact indexed prefixes before a
raw comparison. Directly retired011 raw outputs have no such restore path;
future execution requires a new qualification from retained inputs and masters.
Historical receipts remain historical evidence, not a new execution or a claim
that every old raw artifact is still available.
