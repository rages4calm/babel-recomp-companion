# Native batch 010: compiled polling with shared event retirement

November 9, 2026. Private, explicitly enabled Original-USA development path.
The installed game and owner data remain separate. Interpreter fallback and
the ordinary source-build defaults remain available. No release was created;
the matching GaiaLabs developer build is still pending.

## The largest remaining CPU interpreter hotspot

Batch009's 77 captures put the RDNMI wait family at 44.69% of guest CPU cycles.
Removing its generated MMIO guard was already disproven: a deadline alone does
not preserve cooperative quiescence or real comparator IRQ timing. That guard
and its regression test remain unchanged.

The new path compiles the effects of exactly two stock instructions: the byte
load from RDNMI and its backward conditional branch. It performs every real
opcode/operand/device read, in order, and every guest iteration. It does not
skip the wait, synthesize an NMI response, or invoke the interpreter's opcode
decoder and relabel its work.

Instead, the existing active bridge frame still owns each instruction's event
protocol: pre-opcode hooks/redirects, quiescent ring and logical steps,
IRQ/deadline decisions, bus/master clocks, refresh, beam and APU retirement.
The compiled callback operates directly on the live registers. No guest return
frame is invented, and no per-instruction CpuState conversion is needed.

Admission requires an active supported scheduler frame, E0/M1, no pending
interpreter interrupt or power state, no host interrupt scope, plain HiROM,
and the exact live six-byte shape in a contiguous cartridge-backed window.
Code is rechecked after hooks at every instruction; active overlays are refused
before mapper probes can alter diagnostics. Unsupported modes, mappings,
observers/co-simulation, contexts and explicit interpreter policies retain the
reference path. A callback declining must do so without effects.

The title registers only four physical mirrors after checking the complete
clean stock image identity, and only in a private AOT build with
`IOG_NATIVE_RDNMI_POLL=1`. The default interpreter build never enables it.
Apocalypse/randomizer forced-interpretation policies still take precedence.
The public boot/NMI/generated-code guards were not removed.

`native_poll_insns` and `native_poll_cycles` now expose direct attribution.
The existing `aot_cycle_pct` complement includes generated functions **and**
these compiled effects; it is described here as native CPU-cycle share.
Bridge steps remain logical retired operations, while interpreter instruction
and cost counters exclude the compiled callbacks. No guest save/state layout
or `Interp816` implementation changed; host diagnostic APIs/JSON are extended.

## Generation and structural preservation

The final graph has **358 observed roots / 1,300 contexts / 1,219 eligible
contexts / 81 retained LLE contexts**. All **1,163 prior emitted bodies remain
byte-identical**; 56 bodies are added. All 486 new emitted instruction contexts
pass independent RomAtlas decoding with bound stock-ROM/tool identities.
This is structural proof, not a claim that every additional body ran.

107 current captures and 194 separately retained historical captures supply
the input corpus. The first attempt used only the prior native observations
and omitted 22 older source captures that had seeded eight already-native
bodies. The structural gate caught their absence. Those 22 inputs are now
retained as historical evidence with their original identities, rather than
merged into current costs. The superseded graph/build and passing bounded
probes remain recorded; only the replacement graph qualifies this batch.

All effective guards, four NMI floors, ordinary CFG/policy and WRAM dispatch
restrictions remain. Generator, analyzer, source/config and all 301 profile
inputs are independently bound to the final cache identity. Official
SNESRecomp main remains inventoried `e98dc63b474d5469ad984490e04eb0b0496ec62e`,
checked unchanged November 9; no vendor tree was replaced.

| Artifact | SHA-256 |
|---|---|
| Final executable | `52cb4078f679f9dad90fbfd256bef41753bca188398c3888bc1ad955c09dc7e8` |
| Final graph | `8b0dbafbba97053c61b3775b3874d6fbc1d09054e0e1ff68d489ca8816b5bc82` |
| Native-poll compiled protocol proof | `4e41b9cfdcca3e2bd7520f9da5ab21f6f8ef936b109d38a42a0546d37e872ae8` |
| Independent 107-pair audit | `f13cdf2f8251dd155b93f3f241c37e6e346eff60c1b743537f996b588b764110` |

Candidate: `.local/batch-001/native-010/build-poll-final/babel-recomp.exe`.
Its poll effects require the explicit environment setting; disabling it restores
the previous generated-native/reference combination in the same executable.

## Executed results

| Natural route, 6,000 frames | Poll disabled | Poll enabled |
|---|---:|---:|
| 4:3 native CPU-cycle share | 40.2820% | **82.9903%** |
| 16:9 native CPU-cycle share | 40.3216% | **83.0169%** |

The narrow route executes **23,596,023 compiled poll instructions /
94,378,505 cycles**. Those counts equal the exact reference-minus-native
instruction costs at the two sites. Generated-native cycles stay 89,016,872,
and other per-PC costs are unchanged on this route. The forced interpreter
reports zero poll execution. Neither figure is game-content coverage or FPS.

**107 fresh same-binary pairs / 214 complete, loss-free captures / 314,040
frames / 1,924 snapshot sets pass** the executed-cycle CPU/WRAM/device/full
APU+scheduler/output contract. The official manifest/journal loader verifies
identities and exclusive interpreted costs. Independently compared saved
evidence includes 7,696 binary pairs, 107 final frames and 107 CPU traces.

Both tiers execute exactly **5,846,076,538 guest CPU cycles /
46,426,125,344 master clocks**. Native work partitions into 2,474,103,097 direct
poll cycles, 2,215,880,917 generated-native cycles and 1,156,092,524 remaining
interpreted cycles. Every pair independently checks its poll attribution;
all forced-reference poll counters are zero.

All **154 tier-specific controls against009** pass. All 77 existing cases gain
native cycle share. The 30 additional cases cover 27 new rooms, Will/Freedan/
Shadow, and 16 widescreen cases. They verify 28 supplied original HP/death
stores in each mode, three active no-attack controls, Solid Arm's HP40→0 and
count1→0, both Vampire deaths, and an actual settled Great Wall clear with
DEF40→41. Boss death is not an ending or quest-completion claim. Other partial
fights remain partial; enemy HP/count/death/clear/rewards were not fabricated.
Assistance and prerequisites are recorded, and failed attempts stay failed.

The new30 witnesses are interpreted009 only. Their 68.4582%–84.8273% native
shares prove current execution, not a measured009-native gain in those new
cases. The previous77 have actual native009 controls. Source references remain
in [guide research](GUIDE-RESEARCH.md) and
[GaiaLabs developer notes](GAIALABS-DEVELOPER-NOTES.md).

The copied-owner RTLSv10 load pair passes. The 12,130-frame aspect-transition
pair passes canonical state, all 67 same-binary presented frames and 134
cross009 frame controls. Separate feature-disabled natural pairs preserve
40.28%/40.32% coverage, zero poll counts and full canonical equality with the
enabled path. Existing settings, saves, bindings and soundtrack remain protected.

## Protocol and regression evidence

The ROM-free actual-core fixture extracts the production callback and uses
the real interpreter/owning bridge, comparator and interrupt-frame/RTI paths.
**2,633 paired scenarios / 52,709 checks pass**. Every deadline1..160 is tested
across four aliases, FastROM settings and both X widths, with ordered bus
read/value hashes, complete synthetic memory, registers, clocks, quiescent and
interrupt continuations, hooks/redirects/mutations, unsupported contexts and
overlay refusal. Deferred manual NMI enabled/disabled cases restore the real
guest stack and consume one edge without duplication.

A deliberate decoder-based callback relabeled as native fails 3,374 counter
partition assertions, as intended. The unchanged009 guard regression still
passes its 70 checks. Separate title tests compile the real wrapper in private
and default configurations and verify effects, exact opt-in/ROM admission and
registration-failure cleanup.

753 existing v2 tests pass with two existing skips; both new protocol tests
pass separately on their frozen final source. An initial broad collection
imported the new fixture while it was being edited and retained two fixture
failures; the final source-bound focused run resolves those without changing
the production core. All 145 title tests pass. Independent source review
found and resolved overlay-admission diagnostic purity and step-counter
wording issues before the frozen build.

## Host cost: keep this experimental

A quiet sequential same-binary comparison holds the executable, generated
graph, resources, compiler and inputs fixed. A disables the poll feature; B
explicitly enables it. Six balanced AB/BA repetitions cover both interpreter
and mixed-native modes in both aspects: **48 measured runs plus eight warmups /
336,000 frames**. All 56 runs pass their exact-build state fingerprints and
every execution counter, including native poll attribution.

| Route | Median paired mixed-native frame-service CPU change | Forced-interpreter control |
|---|---:|---:|
| Natural 4:3 | **+2.22%** | +1.45% |
| Natural 16:9 | **+1.97%** | +1.28% |

This is a measured host-cost increase, so the feature stays explicitly opt-in
and is not presented as a speed fix. Safety admission and shared retirement
still have costs; the forced-reference control also measures registration/
policy-check overhead. The new path establishes compiled execution and correct
event ownership while keeping the previous path available.

The primary metric is all-thread process CPU accumulated over frame service;
whole-process GetProcessTimes data is retained separately. Timing uses dummy
SDL/software rendering, audio off, no VSync and no captures/dumps/screenshots.
Narrow/wide cohorts are sequential: their absolute medians do not isolate
renderer overhead or general gameplay FPS. Further guard/dispatch optimization
must retain the same protocol proof and be measured again.

## Limits and next work

Canonical APU/scheduler/state equality does not establish raw host-beam stamp
identity: **961 raw APU-clock snapshot files** differ in the current107 pair
cohort. The aspect check retains its 19 raw strict differences. New30 raw
native clocks differ in314/315 files from their source witness; all forced
references match. Generated word-store versus interpreted byte-store log
grouping also remains explicitly distinct; required original HP/death contracts
and per-frame byte inventories pass. Old004 strict mechanics is still **17/28**.
Those failures are preserved separately, not waived by current-tier parity.

Remaining actor/RTL and Quintet LZ costs are continuation ownership problems.
Two source-bound diagnostics reproduce the exact009 route and show LZ resuming
after a real deadline and actor scripts returning through interpreted RTL
continuations. Adding already-known roots would not fix those paths. Future
native continuations must inherit the actual owner watermark and guest frame;
no fake call entry or return frame was introduced here.

No full campaign, naturally earned progression, audible music, physical
controller/GPU timing, ordinary current-build SAVE/RESTORE, or GaiaLabs dev-build
qualification follows. The deferred clubhouse/Erik music report is untouched.
Babel/mr0ta/mrOt4 and every existing contributor/license retain their credits.

294 completed runtime executable copies (4,151,687,680 bytes) are compacted
to four verified payloads in a 20,793,797-byte archive plus relative-path/hash
restore index. Source builds, superseded/probe binaries, saves, settings,
snapshots, traces and successful/failed receipts remain. No earlier archive was
recreated. All 39 protected owner inputs and the installed005 binary remain
unchanged; all owned game/compile processes stop after their bounded runs.
