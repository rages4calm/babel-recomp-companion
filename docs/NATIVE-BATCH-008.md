# Native batch 008: timed live sprite operands

November 8, 2026. This is a private, opt-in Original-USA mixed-native build.
Interpreter/reference paths remain available. The installed batch-005 game and
owner saves, settings, bindings and soundtrack stay separate. No release was created.

## What changed

Batch 007 stopped native sprite routines before six host-patched immediate
operands. The new optional **`--region-live-immediates`** mode executes those
data-immediate instructions with their current values and counted bus timing.
This lets the existing compiled sprite pipeline continue past those cutoffs.
The complete actor-sort interval `[03C5FF,03C714)` and its two mutable absolute
operands remain interpreted, along with the existing interrupt/vblank guards.

The graph is deliberately unchanged: **331 roots / 1,233 contexts / 1,154
eligible contexts**, with 79 retained LLE contexts. Reviewing all 57 current
captures plus 172 retained historical inputs found no additional unguarded
observed entry points. Adding speculative roots would not establish useful
execution. This batch instead expands actual execution through nine existing
function bodies and 16 live-instruction blocks.

| Fixture | Batch 007 native CPU-cycle share | Batch 008 |
|---|---:|---:|
| Natural 4:3, 6,000 frames | 14.9396% | **31.4331%** |
| Natural 16:9, 6,000 frames | 14.9394% | **31.4404%** |
| Aqueduct inventory fixture | 10.4071% | **21.7139%** |
| Babel inventory fixture | 26.9550% | **32.5694%** |

All 57 current fixtures increase their measured native cycle share. These are
guest CPU-cycle measurements, not percentages of game content, native entry-hit
counts, a general host-speed claim or campaign certification.

## Timing and fallback contract

For supported data immediates, only the immutable opcode fetch and internal
clocks are precharged. Operand bytes are read once, low then high, with paced
bus helpers using the **live PB** and independently wrapped PC16 addresses.
The final live operand byte supplies open bus; a folded fetch value cannot
overwrite it. Separate C statements preserve read order.

Unsupported emitted shapes retain pre-effect interpreter fallback. Partial-bank
low-half fetches are refused before charging or reading operands; full HiROM
bank wrapping is separately tested. REP/SEP, COP signatures and absolute-address
operands are outside this new data-immediate contract. The default mode keeps
batch 007's conservative refusal.

The option is forwarded through the SDK CLI, TOML recipe, whole-output analysis
key, per-bank cache key and function emitter. The game preparation wrapper also
requires `--sprite-prefixes --instruction-blocks --region-paced`. Mode, policies,
source/CFG/analyzer identities and generation inputs are bound to receipts;
conservative output cannot be reused as timed-live output.

## Exact identities

| Artifact | Identity |
|---|---|
| Integrated SNESRecomp main | `e98dc63b474d5469ad984490e04eb0b0496ec62e`, checked unchanged |
| Stock USA ROM SHA-256 | `32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd` |
| Graph SHA-256, unchanged from 007 | `ac3c4cc24cc3e65359f8e4d20878c9230e00c97bb58f9645cd760e929577ed2b` |
| Final candidate executable | `10759ef65bbd734b7f6a8601a060e775cddcfbd0a18a91b7a37cdb38686e2f7e` |
| Reset-only graph-007 control | `d915c2c1d87dfc949e86f58dd8ddce3939f1f0f0d3b1a5875d29e336ec99fd4c` |
| Graph-006 current-engine control | `e934c1018e8b50388b867d66656f37880708b5983c130ff6d2cf696401b58db8` |
| Timed-mode effective policy | `1af3948c30296244190077461d9233cff6cf1388b6e006ce13c622324e4afd78` |
| SDK generator digest | `57c7500bcb30c06044bbade3d76c26ac13c84a1e3a122100f3530dcd5556be3c` |

Candidate: `.local/batch-001/native-008/build-live-v3/babel-recomp.exe`.
The [previously qualified isolated tools](TOOLS-NOV08.md) are reused, including
Python 3.14.10, Rust 1.99.1 analyzer, managed Clang 22.1.8 and private CMake 4.4.5.
No vendor tree was replaced and no runtime ABI or ordinary state version changed.
These new timing/compiler changes are local deltas, not merged-upstream claims.

## Widescreen memory work

The normal capture path was clearing approximately **10 MiB** of shadow-map
valid/guess/cooldown data twice: BeginFrame, then BeforeDraw, with no consumer
or writer between them. A one-use marker now lets that immediate draw consume
the completed reset. Direct/repeated draws still reset normally, and each next
BeginFrame still resets. This removes the duplicate work without retaining
previous-frame shadow data.

An actual shared-C fixture passes 82,272 checks, including direct redraw,
restore, narrow, classroom and randomizer paths. The old adapter fails the
duplicate-reset negative control. The reset-only control uses the identical
graph-007 generated inputs and compiler settings; its only compiled source
change is `src/iog_widescreen.c`. Both-aspect smoke pairs and old-007 controls
match complete canonical state and output. This identifies shared rendering
work; it does not by itself explain the earlier noisy +4.73% whole-build result.

## Verification

| Check | Result and scope |
|---|---|
| Independent instruction execution | **59 tests** cover all 12 allowed data-immediate mnemonics, m/x widths, carry and decimal controls, four aliases, fast/slow ROM, stock/patch/restore values, wrap/refusal and interrupt boundaries. Actual interp816/owning-bridge comparison, not a second model of the proposed implementation. |
| Existing SDK v2 suite | **639 passed, 2 existing skips**, with the new 59-test file run separately. Profile feedback/root materialization and modern CLI/cache forwarding checks also pass. This is not a new passing all-framework/platform suite. |
| Title checks | **136 tests passed** on the final frozen source, including the mode-metadata/cache binding and actual-C widescreen checks. |
| Structural checks | All **16 live blocks** independently inspected; nine function bodies changed and 1,145 are unchanged. The same-ROM/manifest/decoder identities validate reuse of 007's **379 RomAtlas decodes**. These are reused structural evidence, not 379 new executions. |
| Guard preservation | All **3,232** effective-policy byte/alias guards, full Sort interval and four inherited NMI-callee exclusions remain. No WRAM dispatch entry is introduced. Public policy/CFG files are unchanged. |
| Main game regression | **57 current same-binary pairs / 114 fresh processes / 148,240 frames / 912 snapshots** pass CPU/WRAM, CPU/master cycles, memory/device journals, complete APU/scheduler state and full output under the existing executed-cycle contract. All captures are loss-free and binary/graph-bound. |
| Prior-current controls | All **114** separately tier-bound comparisons against batch 007 match. They reuse the above runs rather than adding executions. |
| Copied owner state | Two additional 300-frame runs preserve scene 2, Will, HP 8/8, pending scene 0 and all observed persistent/extended flags in a private RTLS v10 F1 copy. Owner files/configuration are not modified or imported as fixture preferences. |
| Aspect transitions | Two additional 6,065-frame 4:3 → wide → 4:3 runs match canonical state and all **67** presented-frame pairs. All **134** frame comparisons against 007 match too. Native cycle share on this route is 31.4028%. |

Assisted teleports, learned-bit injection, boosted stats and scripted fights
remain assistance. These fixtures do not prove earned story progression,
normal boss difficulty, physical input/audio/GPU behavior or a complete campaign.

## Isolated widescreen CPU results

Four matched builds separate the graph-006/007 change, the reset-only change,
and the final timed-live change. Compiler settings, headers, runtime resources,
input route and private settings are checked. Each build runs both aspects and
both tiers: **16 warmups plus 64 balanced measured processes / 480,000 frames**.
All final-state fingerprints, exact execution shares and 6,000-row phase
inventories pass. No other agent build/test/analysis workload ran during timing.

The primary metric is all-thread **frame-service process CPU time**, sampled
at the existing engine frame-loop boundaries, excluding startup/shutdown and
CSV export. Negative values mean lower CPU cost. These are medians of four
paired changes, not additive percentages or universal FPS measurements.

| Mixed-native comparison | 4:3 CPU change | 16:9 CPU change |
|---|---:|---:|
| Graph 007 versus graph 006, matched current engine | −0.38% | −0.43% |
| Reset-only 007 versus original 007 | +0.19% | **−3.40%** |
| Timed-live 008 versus reset-only 007 | **−9.18%** | **−8.66%** |
| Final 008 versus original 007 | **−9.10%** | **−11.86%** |

The final paired ranges are −9.52% to −8.83% narrow and −12.17% to −11.54%
wide. The earlier noisy +4.73% whole-build result does not reproduce in this
matched frame-service comparison; its original failed/limited attribution is
not retroactively rewritten.

Reset-only wide CPU is 8.96094 → 8.65625 seconds, paired range −3.83% to
−3.14%. Wide forced interpretation also improves about 3.54%, supporting a
shared rendering fix. The phase CSV records **wall time**, not per-stage CPU:
whole-route raster wall falls about 312 ms while guest wall is essentially
flat. In the settled 600-frame South Cape window, raster wall falls about
24.36%. The timed-live comparison saves about 764 ms of guest wall in wide
mode with raster wall nearly flat and approximately zero interpreter CPU drift.

Those stage observations support the two separate changes without treating
preemption/lock waits as CPU measurements. Results remain bounded to this
software-rendered, dummy-SDL, audio-off scripted route; physical device/GPU/audio
and full-campaign performance remain unqualified. All benchmark processes stop
after their bounded runs. Private analysis and completion receipts are under
`native-008/widescreen-cost/`.

## Generator profile validation

Root discovery rebuilt the same canonical declared-boundary set for each
eligible profile row. It now creates a lazy, call-scoped lookup per loaded
profile, retaining the original validation gate. There is no global cache keyed
by mutable collection identity; custom/one-shot iterables keep their old behavior.

One isolated, instrumented old/new pair over **229 immutable profile inputs**
measures **131.234375 → 5.75 process CPU seconds** (wall 131.889 → 5.781).
All 19,332 first-reason decisions, 341 raw roots, loaded identities/metadata,
warnings and corpus force-LLE results match exactly. That corpus's empty
profile-derived force-LLE set does not remove the independent policy/NMI guards.
This is generator-validation performance, not game FPS or an averaged benchmark.
The reproduced official-main problem is reported as
[#265](https://github.com/RetroPortingToolKit/snesrecomp/issues/265).

## Retained limits and failures

Historical strict mechanics replay against batch 004 remains **17/28 passed**.
All eleven historical failures remain failed. The aspect route also retains
the same **19 raw SPC host-beam stamp-file differences**; its canonical
executed-cycle/full APU/scheduler comparisons pass. No ordinary current-build
canonical audio SAVE/RESTORE or full hardware-timing qualification is inferred.
The deferred clubhouse music report was not investigated or fixed.

The first-instruction entry-hook probe exposed an existing native return-frame
peek changing the observed open-bus latch. A separate 40-case official-source
reproducer confirms it in conservative and new modes, with other boundary
fields/final state matching; it is reported as
[#266](https://github.com/RetroPortingToolKit/snesrecomp/issues/266).
The new exact pre-live snapshot matrix uses a preceding NOP; that adjustment
does not claim to fix the entry-hook defect. Controlled hook-time ROM mutation
in a test proves read ordering, not a public mutable-entry-hook API.

The first private generation attempt rejected a missing top-level CLI option;
the SDK forwarding and modern-CLI regression are corrected. That failed attempt
and earlier fixture/setup negatives remain private. Only final v3 is the
qualified game candidate.

Current GaiaLabs content still awaits its exact dev build/recipe and a deliberate
[separate edition adapter](GAME-EDITIONS.md). Preserve mr0ta / mrOt4, GaiaLabs,
retranslation authors and every existing upstream credit/license notice.

Completed copied executables are compacted under the same private batch:
129 copies (1,787,511,296 bytes) map to four verified payloads in a
20,511,733-byte ZIP plus a relative-path/hash restore index. Retained source
builds, states, snapshots, traces, settings and successful/failed receipts stay
in place. No completed archive from an earlier batch was recreated.
