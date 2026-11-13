# Native batch 022 — boss logic, inventory copies and indexed calls

Source baseline `a1441342aceab647dd63f01e8682d507041082c7`, November 13, 2026.
Private candidate SHA-256:
`e9d538170d0a39c8ee14d863a28935a5e8af04d3f79bed91bd10fd190ca7d4fb`.
Development source update; owner installation unchanged.

## What changed

The remaining interpreter profile exposed boss AI, ordinary game scripts,
inventory copies and the original text renderer. This batch selects 6,039
additional instruction/PC/mode contexts, including fourteen ROM MVN sites and
one indexed JSR. Each new context retains its observed physical program bank;
the old four-bank alias recipe remains unchanged for every previous context.

All 59,484 previous ROM descriptors and twelve WRAM descriptors remain, making
65,535 total entries. This fits the existing registry capacity without an ABI
or index change. Every new entry is scheduler-only. There are 359 additional
explicit frame-effect permissions and no new NMI permissions. The old 4,084 ROM
and four WRAM finite-owner NMI permissions remain unchanged. All previous
mapper, live-byte/mode, hook, exclusion, owner and pending-event guards remain.

The new ordinary ROM MVN callback transfers one byte and retires one original
instruction at a time. Indexed JSR reads the live pointer from the current
program bank and performs the original return-address pushes. Neither grants
these instructions to NMI execution. Other unsupported indirect forms, SP
writes and emulation-mode contexts keep the interpreter path.

The optional outlining recipe shares 3,317 effect bodies behind 65,523 ROM
wrappers. Independent preservation checks compare all 59,484 old wrappers,
2,474 old body groups and 100 old helper definitions. Only numeric body-group
names are normalized; executable semantics and guards are compared literally.
Regenerating the old selection with the new emitter reproduces its previous
source SHA-256 exactly. ROM-derived output remains private.

The immutable 016 graph and single 018 build tree are reused. Interpreter,
reference, old lookup and default-off activation switches remain available.
This is native CPU coverage within the tested routes, not native SPC audio,
full-campaign proof or a promise of a CPU speedup. No performance benchmark
campaign was run for this batch.

## Matched execution results

The independent matched 129-route suite passes 258 captures / 683,400 frames /
1,988 snapshot sets. The same guest CPU, master-clock, poll and NMI work remains.
Every previous ROM and WRAM site's instruction/cycle counts are unchanged. For
each new site, its previous interpreted instruction/cycle decrease equals its
new native count exactly, with no attribution exceptions.

| Same-route cohort | Previous interpreted cycles | Current interpreted cycles | Reduction | Current native guest CPU |
| --- | ---: | ---: | ---: | ---: |
| Original 105 | 6,310,125 | 4,232,373 | 32.9273% | 99.956256% |
| Retained 129 | 21,661,924 | 9,519,673 | 56.0534% | 99.925741% |

These are executed 65816 guest-cycle figures, not host speed or project-completion
percentages. The denominator does not include SPC700 audio. Of 6,039 additions,
6,029 execute: 2,883,199 instructions / 12,142,251 cycles. Ten remain unobserved
under their restrictions; their refusal causes are not instrumented or guessed.
All fourteen ROM MVN sites execute 58,386 instructions / 408,702 cycles. The
indexed JSR executes 17,165 instructions / 137,320 cycles. These are subsets of
the new work, not additional cycles to sum on top.

Remaining 129-route interpreter work is 4,785,310 protected RDNMI cycles,
4,380,197 actor/OAM-policy cycles, 207,603 previously selected but refused cycles,
3,538 newly selected but refused cycles, and 143,025 unregistered cycles. New
native execution removes 98.8073% of the previously unregistered cycle cost.
Owner/source qualification is required before addressing the retained guards.
The larger148 corpus exposes 13,424,794 remaining cycles: protected RDNMI
6,121,885; actor/OAM4,429,899; previously selected/refused346,018; newly selected/
refused57,476; and unregistered ROM/mode2,469,516. That broader ranking is the next
input, derived from closed129 costs plus only the nineteen hash-bound checkpoint
profiles. Existing rankings/receipts are unchanged; no raw, APU or game was rerun
for the ranking supplement.

The 993 raw SPC observer-tag differences and seventeen raw cached-beam info
files are exactly the same counts as 021; they remain available and unnormalized.
The existing executed-APU cycle/event-order/CPU-port/full-state/PCM/queue contract
still passes. No new mask or global hardware beam-phase equivalence is asserted.
The original NEW24 damage, flags, Will restoration, hub-return and idle semantics
are freshly checked on this exact candidate; all 254 original-field pairs match.

## Current tools and developer sources

Fresh upstream verification keeps SNESRecomp at `80a41241e39bfffd384506fbe7ca65b386e03050`
and GaiaLabs at `e825dddde466c73cb9900c2c04a7d2bfa37ed165`; no vendor tree
replacement was necessary. Qualified Python 3.14.10, Clang 22.1.8, CMake 4.4.5
and Ninja 1.13.2 were used. GaiaLabs flag and extracted-engine sources guide
original-game prerequisites; the private developer ROM/BSO are not distributed.
Babel author mr0ta / mrOt4 and all existing upstream credits remain intact.

## Executed qualification

The new ROM-free core fixture passes 53 tests: 13,764 positive differential
pairs / 325,348 checks, four extra boundary executions and forty activated
negative controls. Both lookup modes and flat/outlined emission are exercised.
The 628-pair peripheral matrix per style/lookup uses the actual CPU, APU, SPC,
DSP, DMA, ordered bus and event retirement. The 2,813-pair advanced owner/AOT/
stack/inline-return matrix per style/lookup uses its inherited APU stubs; it
is not a second full-APU claim. Sixty-four runtime finite-NMI/IRQ pairs and
nested-interrupt checks retain zero native execution for the new effects.
Only the first opcode-fetch IPC observer uses the pre-existing normalization;
operand/data/stack writes, device clocks and retirement stay strict.

A bounded unchanged-renderer check independently passes ten reference/span
pairs plus two additional native256 controls: 22 captures / 71,500 frames.
Seven ready pairs cover six positive scene IDs (01,03,08,0E,B6,E8), plus one
Castoth object refusal and two unsupported-scene controls. Original lesson,
both doors, town return, aqueduct combat and boss pictures are checked. Full
CPU/devices/raw APU, per-site counts, source packets, published OAM, stock OBJ
texels, original visible-region partitions and world pictures retain their
existing checks. Unsupported scenes keep exact original-field/black-padding
controls. No new renderer admission or 61-format refresh is claimed.

The actual original opening runs 4,400 frames with MSU tracks 1/2/3, followed
by a 240-frame NVIDIA1080p xBR/1.5x check. The checkpoint and displayed image
are byte-identical to 021. This opening executes 1,329 new contexts / 9,711
instructions / 33,474 cycles, alongside the unchanged 15,434 WRAM-copy
instructions / 106,646 cycles. It verifies dummy-device audio consumption,
not physical listening or sustained frame rate.

Freshness review also checks RomAtlas main `23521a5743b1cf8ce36c818b482f683068380acd`.
The previously qualified binary comes from `0e58894598c67a60e344092fed1d3545873b4749`
with its recorded Windows assembler-refusal patch. All thirteen crate trees,
vendor trees, Cargo.toml and Cargo.lock are identical to current main; the
eight intervening commits change root documentation, atlases and scripts.
It is a reused qualified decoder, not a newly built main binary. Independent
selection checks use 5,556 fresh decodes and 483 exact byte/mode-bound prior
checks; returned post-REP/SEP/PLP/RTI context is kept distinct from CLI entry
context. Initial assessor failures remain private rather than relabeled.

## New stock quests, puzzles and abilities

Nineteen new assisted fixtures pass fresh same-candidate reference/native
comparisons: Prison Key gates; Mu Hope placement/drain and Rama's original
ceremony; Ishtar's ordered doors/four answers and refusals; actual Moon trial
clear/timeout; real jewel deposits at 30 versus 29; earned Dark Friar remote
burst/manual input; and armor combat/pull/pressure plate. Original game writers
produce the outcomes. No enemy HP/death/count, victory/quest counter, NPC-position
or actor-PC edits establish the result. Disclosed prerequisite flags, starting
inventory, player stats and teleports remain assistance, not campaign progress.

These nineteen add 38 unique captures / 186,000 frames / 426 snapshot sets.
All 213 captured original256 fields match exactly: 12,214,272 pixels. There are
zero new raw.info differences. Combined with the retained129, the current larger
cohort is 148 pairs / 296 captures / 869,400 frames / 2,414 snapshot sets; it has
a different denominator from both historical tables above. Its native guest CPU
share is 99.915671%; the new nineteen alone are 99.874029%. These additional
routes have no historical same-route percentage delta. Across148, 6,029 new
contexts execute 3,485,853 instructions / 15,595,378 cycles; the fourteen MVN
sites contribute 253,006 / 1,771,042 and the indexed call 19,400 / 155,200.
The retained twelve WRAM sites contribute 2,884,353 / 19,377,119. Again, these
crosscuts overlap the native totals.

The new nineteen retain 213 raw SPC observer-tag file differences with zero
raw.info differences; combined148 retains 1,206 and seventeen respectively.
The independent combined audit reuses the immutable129 closure and checks only
the additional19 raw devices/APU/counters/semantic bindings, avoiding a duplicate
129 analysis. No game was rerun by either independent counter auditor.

Source-baseline exploration (38 baseline executions / 184,155 frames)
and failed/refined attempts are separate evidence. In the last-nine reviewer,
a missing pure word-decoder import was corrected before continuing: the already
closed fresh Ishtar pair was independently rechecked from its immutable raw data,
then only eight unstarted pairs ran. No passing capture was rewritten or rerun.
The twelve-thousand-frame Ishtar inputs use a private 14,000-frame capacity cap;
all comparison, admission and original outcome rules remain unchanged.

## Core, build and retention

The full SDK v2/timing/DSP gate passes **968 tests, two skipped, zero warnings**;
all 785 relevant source files remain unchanged during the successful run. There
are also nine title-policy and eight alias-recipe tests. Two earlier SDK attempts
remain failed/interrupted: one synthetic negative control initially selected the
wrong physical bank, and an old broad-SAFE outlining fixture incorrectly tried
to grant newly supported MVN to NMI. Those test expectations were corrected;
production guards correctly refused the grant. Focused core and the final full
SDK pass on the frozen source. No engine failure is hidden as a fixture pass.

The 24,646,656-byte candidate retains interpreter/reference and the old lookup.
Current emitted effects still need private verified-ROM inputs and opt-in NI,
poll, NMI, frame and WRAM switches. Default source builds do not silently acquire
this private native corpus. No install, release, graph regeneration or CPU
benchmark campaign took place. Source and ROM-free tests are the public output;
ROM-derived code, assets, captures, states and music stay ignored.

Current 022 raw evidence, all seeds/states/failures, owner39/normal28PCM, masters,
the immutable016 graph and fifteen compact unit inputs remain protected.
Superseded passed 021 native payloads are retired only after the replacement
129, inherited/new semantics and explicit reader releases; all old metadata,
profiles, logs and 1,988 info files remain. The entire earlier 44-capture renderer
raw set stays because the new22 subset does not replace it in full. See
[cleanup](PROJECT-CLEANUP.md) and the current [handoff](../HANDOFF.md).

Primary private receipts: `FROZEN-ENGINE-PROOF.json`,
`counter-audit-v1/FINAL-COHORT-AUDIT.json`,
`counter-audit-148-v1/FINAL-COMBINED-AUDIT.json`, `native-gap/FROZEN-EFFECTS-RECEIPT.json`,
`core-tests-flow/FINAL-MECHANISM-RECEIPT.json`, `area-boss/COMPLETE-RECEIPT.json`,
`area-boss/INDEPENDENT-SEMANTICS-19-v1.json`, `renderer/COMPLETE-RECEIPT.json`,
`play-proof/READBACK-REVIEW.json` and the storage retirement receipt. Immutable
hash-bound receipts distinguish structural selection, builds, bounded execution,
original outcomes and campaign work. Native SPC and campaign completion remain
unfinished.

## Historical payload retirement by batch 023

After fresh independent replacement of all 148 pairs and inherited 43 semantic
reviews, all consumers released the exact passed native payloads in the three
qualified roots. Batch 023 retired 31,974 raw files in place; every historical
info JSON, receipt, profile, journal, log, state, seed, failure and required unit
input remains. Three retirement markers bind the operation. These passed
receipts remain historical; the retired raw must not be used as available
goldens. **All batch-022 renderer22 and older batch-021 renderer44 raw remain.**
See [cleanup](PROJECT-CLEANUP.md) and [replacement qualification](NATIVE-BATCH-023.md).
