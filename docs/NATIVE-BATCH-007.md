# Native batch 007: conservative sprite prefixes

November 8, 2026. This is an opt-in private Original-USA mixed-native candidate.
Interpreter/reference paths remain available. The installed batch-005 game,
owner saves/settings and soundtrack remain separate. No release was created.

## Identity and scope

| Artifact | SHA-256 / source |
|---|---|
| SNESRecomp main | `e98dc63b474d5469ad984490e04eb0b0496ec62e`, unchanged since inventoried batch 006 integration |
| Stock USA image, read-only | `32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd` |
| Candidate graph | `ac3c4cc24cc3e65359f8e4d20878c9230e00c97bb58f9645cd760e929577ed2b` |
| Gameplay executable | `4ccb4637e80307c6f4a6a29a4df4da7f4d8968b84b807fec44896fa6840110f6` |
| Separate TRACE diagnostic | `aa71ee490a0522933ef0e809dc63f89bd3f425bb7dc2b5e19ccefceeac060f4c` |

The gameplay binary is retained at
`.local/batch-001/native-007/build-sprite-prefix-v2/babel-recomp.exe`.
The graph has **331 roots / 1,233 variants / 1,154 eligible contexts** and 79
retained LLE contexts. All 1,120 previously eligible contexts remain. The 34
additional eligible contexts are structural candidates; there is no claim
that every newly emitted entry executed or that the game is fully native.

## Why the mutable sprite code can be approached safely

The existing widescreen host changes ten operand words in the sprite pipeline.
Two are absolute-address operands; the other eight are immediate operands.
Existing region pacing cannot safely handle a live absolute operand. The
complete `SortActorsByDepth` interval **[`$03C5FF`, `$03C714`)** therefore stays
interpreted, including both absolute sites and its two immediate comparisons.

The six later immediate sites receive `live_operand` contracts in the private
CFG only. A generated prefix stops before executing the mutable instruction,
charging its clocks or changing open bus. The real interpreter owns that
instruction and continuation; later genuine subroutine calls can bounce back
into eligible native bodies. This deliberately does not invent arbitrary
native re-entry points or use an HLE exclusion to skip the original body.

ROM-free executed bridge tests cover CMP/SBC, fast/slow ROM, width controls,
stock → patched → restored operands and aliases 03/43/83/C3. The focused
refusal matrix executes 256 bridge runs with 1,792 C assertions, plus stale
operand and premature-clock negative controls. These are bounded bridge
contracts, separate from the actual game's route evidence.

RomAtlas independently matches **379/379 instruction contexts**, covering all
34 new entries and their emitted instructions. All 3,232 protected byte/alias
addresses and four inherited NMI-callee exclusions remain. Six live sites in
16 emitted bank83 blocks tail before effects. Bank03 can reuse bank83 bodies
through the existing mirror lookup while retaining live PB; bank43/C3 retain
interpreter paths. No generated WRAM dispatch entry was introduced; eight
bank/width rejection controls pass.

## Fresh execution and comparison

| Qualification | Result |
|---|---|
| Area/inventory/form routes | **29/29** fresh same-binary interpreter/native pairs pass. Transition, inventory and form observations are independently rechecked. |
| Combat, rewards, abilities and bosses | **28/28** current same-binary pairs pass, with 19 positive cases and nine controls. Fresh required Castoth/Viper HP-zero store events pass. Assistance and boosted stats remain explicit. |
| Prior current-framework controls | **114/114** comparisons of batch-006 versus batch-007, separately for both tiers, match under the executed-cycle contract. These reuse the above runs, not additional executions. |
| Capture integrity | All **114** captures are complete, loss-free, bound to the exact executable/graph, and their exclusive interpreted instruction-cycle sums match runtime totals. |
| Current owner checkpoint | Two additional 300-frame runs load a private copy of the existing RTLS v10 F1 state, preserve observed scene/form/HP and persistent flags, and match between tiers. No owner preferences or new saves are imported. |
| In-session aspect changes | Two additional 6,065-frame runs match CPU/WRAM, clocks, memory/device snapshots and complete APU/scheduler state under the executed-cycle contract. All **67/67** captured full presented frames match, including 32 at 342×224. |
| Actual mutable-word transitions | The separate TRACE diagnostic checks all ten cartridge words at seven stable checkpoints: **70 checks pass**, with widths 256 → 342 → 256, scratch camera 23 and the existing one-frame culling latch confirmed in both directions. |

The principal 57 pairs execute **114 fresh processes / 148,240 frames / 912
snapshots**. The copied-state, aspect-transition and preliminary smoke runs
are separate evidence. All runtime evidence uses isolated dummy video/audio;
it does not establish physical controller/GPU/audio behavior, naturally earned
progression, visual correctness outside the tested routes or campaign completion.

| Natural 6,000-frame route | Batch 006 native CPU-cycle share | Batch 007 |
|---|---:|---:|
| 4:3 | 12.8307% | **14.9396%** |
| 16:9 | 12.8268% | **14.9394%** |

All 57 current cases increase their measured native CPU-cycle share. These
percentages describe guest execution coverage, not host speed or per-entry hits.

## Whole-build host CPU comparison

A separate sequential benchmark compares batch-006 `c028...` with batch-007
`4ccb...`: five fixtures, each build in mixed-native and forced-interpreter
mode, one warmup per build/tier/case and six balanced pairs (three AB, three BA).
All **120 measured processes plus 20 warmups** pass final CPU/sampled-WRAM,
frame and guest-cycle controls against their exact-build/tier witnesses. All
20 execution-share groups exactly match the witnesses; interpretation reports
zero native share. These reduced diagnostic runs supplement the complete state
comparisons above rather than replacing them.

Primary cost is Windows `GetProcessTimes` kernel plus user CPU time for all
threads in the complete process. Dumps/captures/profile output are disabled;
inputs/waits and private mod settings remain identical, with dummy SDL,
audio off, VSync off and no frame delay. Startup/shutdown, binary layout,
unused script-command support and newer CMake qualification are included.
This does not isolate the sprite graph's cost or measure physical GPU/audio FPS.

Negative percentages below mean lower process CPU cost. Values are medians of
six paired new/old ratios; they are not ratios of separately computed medians.

| Fixture | Mixed-native cost change | Observed pair range | Forced-interpreter control change |
|---|---:|---:|---:|
| Natural 4:3 | −1.63% | −17.57% to +7.94% | +0.13% |
| Natural 16:9 | +4.73% | −5.03% to +11.85% | −0.05% |
| Inventory | −2.20% | −14.00% to +12.20% | −1.82% |
| Shadow Aura | −1.50% | −12.62% to +2.04% | 0.00% |
| Viper | −2.82% | −7.56% to −0.48% | +0.92% |

The widescreen fixture has observed higher median whole-build cost. Most
effects are small relative to pair spread/control drift. Viper's six raw
native pairs are all lower, but its interpreter-normalized range still crosses
zero. Short inventory runs also make startup cost and accounting quantization
material. **No general speedup is qualified.** The preset remains opt-in;
isolating/profile-guiding widescreen cost is the next performance task.
The interrupted contended setup contains warmups only and is excluded.
Private receipts: `host-cost/completion.json`, `summary.json` and
`control-analysis.json`; all owned benchmark processes are stopped.

## Retained limits and failed checks

Strict replay against old batch-004 mechanics witnesses remains **17/28**
passed. Eleven old cross-version comparisons remain failed; no historical
semantic conditions are carried through those failed witnesses. Current tier
parity and the current-framework controls do not waive them.

The aspect test's raw strict comparison also remains failed on **19 SPC
host-beam event logs**. The passing executed-cycle comparison preserves bound
cycle/order/port/value/sample information and full APU/scheduler state; it does
not assert identical raw host scanline/hclock stamps. Both comparison files
remain private. Ordinary current-build canonical audio SAVE/RESTORE, broader
IRQ timing and physical audio qualification remain open. The owner's deferred
clubhouse music report was not investigated or fixed.

Three aspect-probe setup failures are retained: TRACE-disabled gameplay builds
have no TCP server; the first Windows screenshot response has invalid JSON;
and `run_to_frame` rejects the current frame as its target. The final diagnostic
uses a separate TRACE build, relative capture paths and supported adjacent-frame
stepping. All owned diagnostic processes were stopped.

The screenshot issue was independently reproduced with the exact official
format call and synthetic inputs, then reported as
[#264](https://github.com/RetroPortingToolKit/snesrecomp/issues/264).
No game data or private screenshot was published. Relative paths work around
it; production code was not changed for this diagnostic API defect.

## Reviewable source and reproduction

`scripts/native_batch.py --sprite-prefixes` is an explicit private preparation
preset requiring both `--instruction-blocks` and `--region-paced`. It validates
all ten stock opcode/operand and host patch contracts, preserves the public
policy/CFG byte-for-byte, and derives an effective policy beneath the private
work directory. Only the six immediate sites acquire live directives; the SDK
loader's four-alias expansion is exercised. Default behavior is unchanged.

Receipts bind effective/public policies, source/CFG hashes, profiles, framework
pins, generation command, analyzer/source stamp, emit environment and SDK cache
identities. Explicit analyzer overrides pin their exact binary/stamp; the SDK's
default analyzer can bootstrap/rebuild from its bound sources, with actual
binary observations recorded separately before/after generation. Cold build
and later cache-reuse tests cover that distinction. Changed bound inputs are
refused before generation. The new preset's
prepared CFGs exactly match the successfully executed candidate; its effective
policy is semantically identical (canonical LF serialization changes its byte
hash). Detailed reproduction inputs stay private rather than publishing ROM
bytes, extracted code or validation captures.

The fixed public driver also passes an actual bound SDK cache run using the
qualified Python/analyzer: **48 banks reused, zero emitted**, with all **88
outputs plus `funcs.h` byte-identical** to the executed candidate's inputs.
Generator/config/analysis-input identities match. This verifies input/cache
reuse, not a second compilation or new gameplay execution. Earlier 10/30-second
caps expired during profile validation; the passing normal-bound attempt takes
155.8 seconds. A separate first reproduction selected a different matching-source
analyzer and changed cache/module metadata; that evidence remains separate from
the final exact-tool/output match.

Prepare with an exact current profile and any individually identified historical
profiles, a fresh private `--work` directory, `--profile-only`, the two pacing
flags and `--sprite-prefixes`. Repeat the same arguments with `--generate` to
generate; compilation and matched runtime qualification remain separate steps.
`build_windows.ps1 -NativeBatch <work> -BuildDirectory <private-build> -CMake
<qualified-exe>` builds without replacing the installed game.

All **133 title Python tests** and **44 focused SDK tests** pass on the updated
private Python/pytest tools. Rust debug/release each pass 108 library plus 12
analyzer tests. This is not a new all-framework-suite pass; the failures in
[batch 006's framework report](FRAMEWORK-NOV08.md) remain documented.
[Tool identities and selection](TOOLS-NOV08.md).

The new script command `widescreen 0|1` exercises the existing per-title setter
at a frame boundary and persists the active configuration. Test runs always use
private configs. No new launcher feature or renderer default is introduced.

Original and GaiaLabs remain [separate planned editions](GAME-EDITIONS.md).
Kassiven's rough current build/recipe is pending; these stock-ROM results do
not qualify current GaiaLabs content. Preserve mr0ta / mrOt4, GaiaLabs,
retranslation authors and every existing upstream credit/license notice.

Completed per-run executable copies are compacted privately: 121 copies
(1.67 GB) map to two checksum-verified payloads in a 10.55 MB ZIP, with a
relative-path/hash/receipt restore index. Retained source builds, evidence,
states and logs stay in place. The completed batch-006 archive was untouched.
