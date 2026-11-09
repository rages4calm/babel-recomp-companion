# Native batch 013 — status, data stack and current-core gameplay

Original USA edition, November 9, 2026. Based on Babel Recomp by mr0ta / mrOt4;
all original credits and license notices are preserved. Source baseline `4499fce`.

## Native effects

The emitter adds REP/SEP and 16 ordinary data-stack forms: PHP/PLP, PHA/PLA,
PHX/PLX, PHY/PLY, PHD/PLD, PHB/PLB, PHK, PEA, PER and PEI. Status helpers keep
live M/X changes and index truncation. Other helpers remain specialized to
their admitted entry width. The next opcode is looked up using its actual
post-instruction width. The original owning opcode loop still retires events,
interrupts and deadlines, with each real ordered bus access preserved.

Data pushes and pulls do not create host call roots. Guest calls/returns,
interrupt frames, direct stack-pointer/emulation changes, indirect transfers,
halts and block moves retain fallback. The title's original PEA operand `C2AE`
Y-clear behavior is preserved from its actual interpreter source, with a
separate `C2AF` control. This is source parity, not a claim that the title-specific
behavior is an unmodified hardware PEA rule. No interpreter decoder is emitted
or relabeled as native execution.

The finite selection retains all 1,240 prior source contexts verbatim and adds
750: 44 status, 117 data-stack, 467 ordinary and 122 static-control contexts.
It has 1,990 source contexts / 7,960 physical-alias descriptors / 109 fixed opcode
bodies. The existing 8,192 descriptor capacity is unchanged. Independent checks
cover 711 fresh RomAtlas decodes and 39 exact previously bound decodes.
Historical batch 012 rankings are selection ceilings; current execution is measured
separately. Existing owner, live-PC/mode, source-byte, mapper, overlay, policy
and interrupt guards remain. Both direct and legacy lookup remain available.

## Current framework and fresh starts

The [current framework integration](FRAMEWORK-NOV09.md) brings official main
d8116fac, including the merged timing contribution and SPC/DSP work. Hardware
states are version 11/minimum 11. Fresh boot, original loaders, actual forms and
earned-power writers supply the new test states. No old hardware blobs are
converted and no DSP phase is fabricated. The old 161 cohort remains historical
evidence on its original core. New-core base/expanded controls use identical
current hardware code and generated graph.

Source captures from the interpreter-only reference genuinely have no generated
program digest; their empty fields and actual executable SHA stay unchanged.
They are not rebound to an AOT identity. Full AOT qualification captures bind
their actual final program/build/generation identities.

## Execution proof

The focused new-effect proof runs 426,240 paired scenarios / 1,289,824 checks.
The production-emitter/actual-bridge fixture runs 1,293 positive pairs and 75,593
checks in each direct/legacy lookup mode. Six coupled counter/clock/width/stack/
bus corruptions and three effect mutations are detected. Width changes, stack
wrap/order, IRQ/NMI/deadlines and owner-frame boundaries retain their tested
contracts. Fixture integration failures are retained as failures, separately
from gameplay and engine defects.

The initial same-current-core probe passes six reference/native pairs across
two builds, plus six actual same-tier base/expanded controls: 12 complete captures,
49,600 frames / 112 snapshot sets. Full saved state, devices, APU/scheduler, output,
journals and exact cost/site partitions pass. All extra native work exactly
substitutes interpreted work; other generated and poll costs stay unchanged.
The natural 6,000-frame route moves from 89.4516% to 90.3353% native guest cycles
in 4:3 and 89.4741% to 90.3575% in 16:9. These compare the same updated core;
older batch 012 hardware timing is a separate baseline. Native shares measure bounded
execution, not content coverage, speed or project completion.

Narrow extra native cycles are 1,953,735: 1,430,012 stack, 330,990 status and 192,733
ordinary/control work. Wide adds 1,953,721 cycles; the 400-frame Freedan walk/attack
probe adds 294,821. That probe is not a claim of a hit or enemy defeat. The 56 raw
host-clock stamp differences remain retained alongside canonical comparisons.

The final graph has **410 roots / 1,330 contexts / 1,246 eligible / 84 LLE**.
All **1,244 earlier native bodies remain byte-identical**. Two are added:
`bank_83_E7D6_M0X0` and `bank_85_FE9A_M0X0`; all 31 new generated instruction
contexts pass independent RomAtlas decoding. The newly observed `8A8743:M0X0`
stays interpreted because of BRK at `8A8751` and structural poison. No fallback
guard is removed to turn that result into native coverage.

All 87 cached outputs and every input/journal are checked. The source collection
retains 759 earlier observations plus two same-current-core probe profiles as
761 historical inputs, with 62 fresh interpreter-only source profiles. Costs
from different binaries are never aggregated as one current measurement.
Prepared CFG/effective policy and the four NMI floors remain unchanged.

| Final private artifact | SHA-256 |
|---|---|
| Executable | `299dff5133d5b916fb26d811907c6614242c77d177cd4294204454742fb3c2e4` |
| Program manifest | `f35571b22682fd33ee5cb5d34402075cb97ccc72b6f2528961d8460bc66c6d25` |
| Native effects C | `2e04081c2c278c39359b21d7bd7c4c5e3a58fcc5b832b85c4b9d7281ea237051` |

The frozen plan contains 64 cases: 25 source primers/new consequences, 37
selected current-core regressions and two natural aspect routes. The 25 include
the original six power grants, Mine wall/switch/key branches, Mu Hope Statue
pickup/full-inventory/no-contact branches, and Great Wall predicate/pushback/
form branches. The Great Wall checks do not prove physical ramp traversal.
The regression source set includes 25 ordinary damage/death cases, three boss
cases, six power activations and three inventory roundtrips; nine also prove
room-clear rewards. Assisted setup and failed/unselected probes remain explicit.

The clean final qualification passes **64 reference/native pairs / 128 captures /
366,400 frames / 1,144 snapshot sets**. The independent cohort audit binds all
CPU/WRAM traces, saved-state/device artifacts, final output, loss-free coverage
and exact instruction/cycle partitions. Native per-site totals reconcile with
the global counters; forced-reference native counters stay zero. The 25 new
cases, 37 regressions and two natural aspect routes all pass their source-to-
reference, reference-to-native and source-to-native comparisons.

The new-case custom review independently carries **21 positive store groups,
12 negative groups and six inventory-overflow branch checks in each tier**,
including the six original `88EABE` power grants. The regression review verifies
ordinary damage/death, three boss cases, six earned-power activations, inventory
roundtrips and nine room-clear rewards in both tiers. The two natural routes
also pass the complete same-core counter and state audit. Player positioning,
original pending-map tuples, survival/stat assistance and explicit negative
prerequisites remain disclosed; enemy HP/count/death/clear/reward fields are
not fabricated.

WRAM logs preserve store-operation order and repeated writes. A native single
word record may match only two adjacent source byte records with the same
frame, bank and original IPC and exact addresses/values. This handles a
high-byte-first RMW representation without sorting separate operations or
dropping repeats. Eight controls check accepted word forms and rejected value,
frame, IPC, interleaving and repeat changes. A word record does not encode its
physical intraword bus order, so this log comparison does not prove that order.
Original IPC remains mandatory in the reference; native IPC/function labels
are diagnostic. Negative controls separately require uncapped ordered logs,
loss-free captures, complete store streams and unchanged outcomes.

All **572 raw SPC host-stamp clock-file differences** remain retained. Canonical
comparisons match SPC event order, port/value, DSP sample and executed APU
port-clock values, plus full APU state, PCM ring and scheduler snapshots. Raw
host frame/scanline/hclock stamps are not claimed identical. This is bounded
same-core parity, not independent hardware, speaker/controller or campaign
proof.

An initial shared-executable parallel replay exposed a test-launch problem:
Babel's default executable-relative log file mixed different processes' stdout.
Some `all_requested_dumps` receipts failed even though the captured states
matched. Its receipts and failure logs remain retained and excluded from
qualification; redundant raw captures were later retired as described below.
Fresh validation uses the existing `SNESRECOMP_LOG_FILE=0` switch after environment
sanitization, keeping each process's inherited output pipe isolated. An actual
400-frame reference/native smoke pair passes first. No engine code, assertions,
source inputs, saves or expected outcomes are changed for this correction.

The full v2 SDK, timing-generation identity and DSP snapshot gate passes
**810 tests, two skipped**. All **167 title/maintenance script tests** pass.
The focused production bridge and effect results above overlap the SDK gate.

## Host CPU cost

The same-current-core baseline and final build pass a quiet, sequential host
comparison and independent post-audit: **28 native processes / 168,000 frames**,
comprising four warmups and 24 measured runs. Six balanced pairs run per aspect.
Both builds use the updated hardware core; the baseline uses the prior graph
and 1,240 effect contexts, while the final build uses this batch's graph and
1,990 effect contexts. Each run matches its qualified guest counters, final
fingerprint and complete per-site diagnostic totals.

| Aspect | Baseline median frame-service CPU (s) | Final median frame-service CPU (s) | Median paired cost change | Observed paired range |
|---|---:|---:|---:|---|
| 4:3 | 9.1953125 | 9.2265625 | +0.25466893% | -8.4063% to +14.4509% |
| 16:9 | 9.796875 | 9.796875 | -0.31923892% | -0.7899% to +1.5848% |

These are process frame-service CPU seconds for the fixed 6,000-frame routes,
excluding startup/exit. The setup uses dummy SDL, software presentation,
disabled audio/VSync and no per-frame dumps. Reference correctness witnesses
are retained separately; this is not a native-versus-interpreter timing cohort.
The final wide median is **6.1812%** above the narrow median. That is a
descriptive comparison of two complete aspect routes, not an isolated renderer
cost, physical FPS measurement or demonstrated speedup. Six pairs per aspect
and the observed sample spread do not establish statistical significance.

## Cleanup and publication

Private fixtures reuse shared executable/resources with separate per-case
configuration, saves and captures. No per-case executable/font trees are cloned.
Current source plans, receipts, hashes and failure logs remain under ignored `.local/`.
ROMs, generated game C, binaries, saves, music and private captures are excluded
from the source update. Interpreter fallback remains available.

Reviewed direct retirement removes **54,947 receipted raw files /
11,002,481,718 bytes (10.24686 GiB)** from batch 012 and the contaminated batch
013 attempt. The measured after-cleanup inventory is **26,723,023,612 logical
bytes (24.888 GiB) / 224,053 files**. The 35.134615 GiB before figure is derived
from that inventory plus removed-file sizes, not a separate before measurement.

All 39 protected owner files retain their exact hashes and sizes, including the
installed batch 005 game. Latest batch 013 source and clean final raw captures,
metadata, failure logs, profiles, seeds, saves, ROM/MSU resources and master
builds remain. The existing 2,714,636,637-byte cold archive remains unchanged;
no archive is created, deleted or rehashed in this pass. Cleanup receipt
`2b45330f752446dd742520b7cad7c74f19f2d6ad143c161d1a8a4f875672e096`
records the final inventory and protection checks.

This is a source-only update; final remote verification is recorded privately.
No public release is created.
