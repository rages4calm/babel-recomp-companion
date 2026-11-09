# Native batch 009: actor sorting and wider combat coverage

November 8, 2026. Private, opt-in Original-USA development build. The installed
batch-005 game, owner data and original interpreter remain available. The
GaiaLabs dev build is still pending; this does not qualify its modules or content.

## Target selection

All 57 current batch-008 captures were ranked separately from 172 historical
inputs. Complete actor sorting accounts for 11.04% of total guest CPU cycles
across that cohort. The main RDNMI wait accounts for 43.43%; its two hot loop
instructions alone account for 42.71% on the natural 4:3 route. These are guest
costs, not measured host CPU time by instruction.

889 new RomAtlas instruction contexts and 14 JSL caller decodes were inspected
against the verified stock image and GaiaLabs source labels. This includes all
277 bytes of the sorting interval in 135 observed width contexts. Earlier
decode receipts retain their original identities and scope. Decoding establishes
structure, not execution or full-game correctness.

The private sorting option removes the remaining `[03C5FF,03C714)` guard only
after checking the complete existing host patch contract. All ten live patch
sites are marked: eight immediate operands and two absolute data addresses.
The public policy, ordinary CFG and other fallback guards remain unchanged.
The graph uses two natural batch-008 captures and 20 new reference captures,
plus all 172 historical inputs: **339 roots / 1,242 contexts / 1,163 eligible
contexts / 79 retained LLE contexts**. The eight additional roots were observed;
no arbitrary instruction samples were converted into call entry points.
All 1,154 previous emitted function bodies are byte-identical; nine bodies are
added. On the natural 4:3 route, Sort's interpreted cost falls from 19,556,013
cycles / 5,199,050 instructions to 1,299 / 325. That exact 19,554,714-cycle
reduction explains the whole native gain; all non-Sort per-PC costs are unchanged.
Sorting is not universally AOT: conditional memory, mode/stack and resume
fallbacks remain, including 52 labels with conditional MMIO refusal.

## Live addresses and fallback

The new SDK `--region-live-wram-addresses` option supports explicitly marked,
unindexed ABS data reads for LDA, LDX, LDY, ADC, SBC, AND, ORA, EOR, CMP,
CPX, CPY and BIT. It requires instruction blocks and region pacing.

A pure plain-ROM preview checks the current operand before instruction clocks,
bus reads or register effects. Only complete accesses within WRAM or its low
mirrors are accepted. MMIO, ROM/SRAM data targets, bank-wrapped word accesses,
unsupported cartridge mappings and overlays retain interpreter fallback.
Accepted instructions fetch their two address bytes once, low then high,
through timed live-PB bus reads, followed by the timed data read through live DB.
Opcode identity is fixed; host operand edits belong between instructions.
This is not general self-modifying-code or asynchronous ROM-edit support.

The title wrapper additionally requires the existing sprite-prefix/live-immediate
chain and explicit `--sprite-sorting`. Enabling the WRAM capability alone does
not remove the sorting guard. Disabled/absent options retain conservative
receipt shapes and cache identities; enabled modes bind both cache layers,
CLI/recipe forwarding, CFG/policy/source identities and reuse checks.

Windows generation now handles an overlong Python-file argument vector inside
the same gated resource-limited child. This preserves every profile argument,
the exact command receipt, exit status and process ownership. Other overlong
command forms are refused. The initial command-limit failure remains retained.

## Why the larger wait loop remains interpreted

A ROM-free test links the actual core, interpreter and owning bridge. Merely
removing the MMIO guard changes cooperative yields and interrupt timing:

| Condition | Interpreter/current fallback | Guard-only native hypothesis |
|---|---:|---:|
| Quiet wait | 1,620 master clocks / 33 RDNMI reads | 10,020 / 208 |
| Actual comparator IRQ | 84 master clocks / 1 read | 10,020 / 208 |

The regression also checks deferred manual NMI ownership, real interrupt frames
and RTI with NMI enabled and disabled. The existing fallback matches the
reference. A native polling island needs shared per-opcode quiescence,
retirement, IRQ and scheduler ownership; a deadline check alone is insufficient.
No latch response, skipped wait or generic MMIO whitelist was introduced.
This unsupported optimization hypothesis is not a new upstream bug report.

## Frozen identities and first execution results

| Artifact | SHA-256 / revision |
|---|---|
| Integrated SNESRecomp main, checked unchanged | `e98dc63b474d5469ad984490e04eb0b0496ec62e` |
| Candidate executable | `8c584f0d841f31c406fbf59265137ba61270cd25ef834e01bbf62d0d5523e7fe` |
| Graph manifest | `921769c084482ba9c2362338f29cf99bfc1dfa0a91edb4dae01fe05b0d18f28f` |
| Private effective policy | `6a9e7dc47bd01cdaa065a7b4c62eab37e705168734b1d17a2c2ce0a1f14445a4` |
| Generator digest | `c46190d02e8468853e51f6e3fe99913cc5dc7f6760ae254f62c6a28e117917c7` |

Candidate: `.local/batch-001/native-009/build-sort-v2/babel-recomp.exe`.
Generation completed in 8.32 seconds with a 186.8 MB peak job commit and no
fallback-range violations. The qualified Python 3.14.10, Rust 1.99.1 analyzer,
Clang 22.1.8 and CMake 4.4.5 are reused. No vendor tree or guest state ABI was
replaced. [Framework delta inventory](FRAMEWORK-NOV08.md).

| Fixture | Batch 008 native CPU-cycle share | Batch 009 |
|---|---:|---:|
| Natural 4:3, 6,000 frames | 31.4331% | **40.2820%** |
| Natural 16:9, 6,000 frames | 31.4404% | **40.3216%** |
| Aqueduct inventory | 21.7139% | **31.7274%** |
| Babel inventory | 32.5694% | **40.4380%** |

These measure executed guest cycles, not percentages of game content or host
speed.

## Host CPU cost

A quiet sequential cohort compares008 and009 with identical runtime resources,
compiler binaries/options and exact-build correctness witnesses. Six balanced
AB/BA repetitions cover both tiers and both natural aspect routes: **48 measured
runs plus eight warmups / 336,000 frames**. All 56 runs match their witness's
final CPU/WRAM fingerprint and every native/interpreter execution counter.

| Route | Median paired native frame-service CPU change | Forced-interpreter control |
|---|---:|---:|
| Natural 4:3 | **−5.01%** | +2.04% |
| Natural 16:9 | **−3.81%** | +0.93% |

The metric is all-thread process CPU accumulated across frame service;
whole-process Windows GetProcessTimes results are separately retained. Dumps,
coverage capture and screenshots are disabled during timing. This measures the
combined009 batch, including additional roots and binary layout, rather than
an isolated per-instruction effect. Individual pairs vary, including positive
native-cost outliers. These are six-pair descriptive measurements under dummy
SDL/software rendering, audio off and no VSync, not general gameplay FPS.

Narrow and wide cohorts run sequentially. Their absolute cross-cohort medians
cannot isolate widescreen's extra raster cost; no negative widescreen overhead
is inferred. The paired wide009-versus-wide008 improvement is the supported
comparison here. The earlier renderer reset investigation remains documented
in [batch008](NATIVE-BATCH-008.md). An initial preflight rejected equivalent
compiler paths with different slash spelling; path normalization plus matching
compiler-file hashes resolved it before timing, and the failed preflight stays
retained.

## Execution qualification

**77 fresh pairs / 154 processes / 211,440 frames / 1,294 snapshot sets pass**
the preselected executed-cycle CPU/WRAM/device/full APU+scheduler/output
comparison. Independent official-loader manifest/journal validation confirms
all 154 captures are complete, loss-free and bound to the exact binary, graph
and generation. Exclusive interpreted instruction costs match the final
interpreter counters. Across the cohort, both tiers execute exactly
3,802,933,160 guest CPU cycles and 29,980,583,368 master clocks.

The previous 57 cases also pass all **114 tier-specific batch-008 controls**.
Every existing case gains native CPU-cycle coverage. This includes the earlier
area/form/inventory, ability and boss fixtures; their assistance and original
qualification limits remain intact.

The 20 new cases use ordinary room-entry checkpoints and the guide/GaiaLabs
map metadata across Inca, Diamond Mine, Sky Garden, Mu, Angel Caverns, Kress,
Angkor and the Pyramid. They establish 16 new melee/death situations, three
matched no-attack controls, one actual player-contact damage sequence
(90 → 81 → 72 HP), and nine complete original room-clear/reward paths.
Teleports, positioning and infinite player HP are explicit where used. Enemy
HP, live counts, death/clear flags and rewards were not fabricated. Partial
clears stay partial. The river no-hit attempt remains unqualified; failed entry
prerequisites and later ordinary-input successes remain recorded.

All 20 replay cases pass three-way canonical comparisons against the source
witness, the new forced interpreter and the new native run. An independent
review verifies WRAM observations, the supplied original HP/death write events,
active no-attack watches, source hashes and all 40 capture identities. Their
native shares span 32.4745%–44.4037%. The new source witnesses are interpreted
008 only; this is not a measured native008-to009 gain for those new cases.

A passive copied-owner RTLS v10 load pair passes without changing owner data.
A separate 12,130-frame narrow/wide/narrow pair passes canonical state, all
67 presented-frame comparisons and 134 tier-specific cross008 frame controls.
Pixel equality is bounded regression evidence, not proof of visual correctness
throughout the game.

## Engine and orchestration proof

49 new live-address tests execute all twelve supported operations in all four
M/X combinations through the real interpreter/owning bridge and production
paced helpers. They cover **27,648 accepted scenarios, 2,304 pre-effect
refusals, 18,432 stale-address/double-clock negative controls, 32 relocated-stack
scans and 32 deadline/interrupt-frame continuations**: 236,000 checks, zero
failures. Operand order is explicitly low byte then high byte. Code previews
in these synthetic fixtures are pure stable-ROM fakes; the production helper
has a separate purity/patch-restore test with a counted mapper dependency.

698 existing v2 tests pass with two existing skips. The pure preview, new
cache/CLI forwarding, actual-core polling and recipe/SDK integration checks
also pass. All **144 title tests**, including 42 focused native-batch tests,
pass. Enabled/disabled/stale receipt paths, every host patch mutation, manifest
guard violations and actual >32 KiB Windows argument vectors are exercised.
Independent production source review finds no material defect. This does not
establish arbitrary cartridge support or hardware IRQ latency in native spans.

## Retained limits and failed evidence

Old004 strict mechanics remains **17/28**, unchanged. New current-tier parity
does not turn those cross-version failures into passes. The aspect test still
fails raw strict comparison in 19 SPC host-beam timestamp files. All **191 new
native raw APU-clock files** differ from their interpreted008 witnesses; all
new forced-reference files match. The preselected executed-cycle/full
APU+scheduler comparisons pass. Raw timestamp identity is not claimed.

Broad no-attack actor watch logs group generated word writes differently from
interpreted byte writes. Per-frame byte multiplicity matches, while raw width
and ordering identity is not claimed. The required original HP/death write
contracts are unchanged and pass. An initial extra reviewer incorrectly
compared exclusive interpreted costs with total mixed CPU cycles and demanded
raw log grouping; that failed review is retained alongside the corrected audit.
Invalid synthetic fixture attempts also remain retained rather than relabeled
as core defects.

The existing first-entry-hook open-bus observation
[#266](https://github.com/RetroPortingToolKit/snesrecomp/issues/266) remains
unfixed. Exact pre-live synthetic snapshots use a preceding NOP, as in008;
that does not qualify an arbitrary mutable entry-hook API.

No naturally earned progression, campaign completion, physical controller/GPU,
audible music, ordinary current-build SAVE/RESTORE, GaiaLabs dev content or
fully native game qualification follows. The deferred clubhouse/Erik music
report remains untouched. Credits and licenses remain with Babel and every
existing contributor; [developer references](GAIALABS-DEVELOPER-NOTES.md) and
[guide research](GUIDE-RESEARCH.md) retain their source attribution.

Completed runtime copies are compacted within the same ignored batch:
**209 executables / 2,906,378,240 bytes** map to two verified payloads in a
**10,315,461-byte ZIP** and a relative-path/hash restore index. All 209 duplicate
copies are removed after verification; both source builds, saves, settings,
snapshots, traces and successful/failed receipts remain. No earlier archive was
recreated. The installed game and all 39 protected owner inputs remain separate.
