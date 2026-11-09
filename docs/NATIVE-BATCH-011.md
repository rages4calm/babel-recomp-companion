# Native batch 011 — actor and decompression continuations

November 9, 2026. Original USA edition only. Based on Babel Recomp by
mr0ta / mrOt4, preserving all inherited credits and license notices.

## What changes

Actor updates and Quintet's LZ decompression return to the interpreter at real
RTL/deadline boundaries. Registering those addresses as guessed call roots
would invent a stack/frame contract. Instead this batch compiles selected
single-instruction effects at their observed PC/M/X/E contexts, inside the
bridge's existing per-opcode event loop. Control flow and unsupported work
continue through the interpreter.

The SDK gains an atomic, copied, bounded descriptor registry and additive
continuation counters. Its page index rejects empty pages cheaply. Each
callback has a fixed opcode and operands; the generation-time helper closure
contains ALU/address operations, not the opcode decoder. No callback calls
`interp816_runOpcode` or `interp816_doOpcode`, skips guest work, or relabels
interpreted instructions as native. Real opcode/operand bus reads remain in
order. The compiled operands require immutable plain-cart code throughout the
instruction; data reads use live interpreter registers and memory.

Admission requires the exact live PC/mode and complete original instruction
bytes, a supported plain LoROM/HiROM mapper without an overlay, emulation off,
the original scheduler owner, and the existing quiescent/interrupt policy.
It declines at unsupported owner/interrupt/RTI contexts. Stack operations,
calls, returns, COP, indirect control transfers, block moves and width changes
are excluded. The live PC is checked after hooks. Writes publish the real
instruction PC for existing title observers. Event service, instruction
retirement and deadline handling stay with the owning bridge.

The title requires a private generated build, the full clean 2 MiB USA ROM
identity and **`IOG_NATIVE_CONTINUATIONS=1`**. Poll effects retain their separate
**`IOG_NATIVE_RDNMI_POLL=1`** switch. Both are experimental and default off.
Forced interpretation, default source builds and unsupported inputs retain
fallback. No launcher option is added for this private engine experiment.

`IOG_NATIVE_CONTINUATION_STATS` optionally names an exit-only JSON diagnostic.
It reports per-PC/mode counts alongside global totals; it performs no file
I/O during frame service. Qualification enables it; CPU timing does not.

## Source, structural and build identities

Official SNESRecomp remains explicitly inventoried main `e98dc63`; the vendor
tree is not replaced. `interp816.c/h`, guest state layouts, public CFG/policy
and all four NMI fallback floors remain unchanged. Babel-specific changes
and the [framework delta inventory](FRAMEWORK-NOV08.md) are retained.

The graph has **366 roots / 1,316 contexts / 1,233 eligible / 83 LLE**.
All **1,219 prior emitted bodies are byte-identical**; 14 bodies are added.
All 301 earlier source observations are retained, with 136 current inputs.
RomAtlas independently decodes all **231 new instruction contexts**. Cache
validation checks 87 outputs and binds the generator, CFG and input corpus.
These are structural checks, not claims that every body executed.

The continuation plan selects **240 source contexts** (131 actor, 109 LZ),
expanded to 960 physical-alias descriptors using 31 fixed opcode bodies.
Prior independent RomAtlas decodes cover these contexts. Descriptor counts
are not executed-site counts; the game receipts record actual execution.

Private identities:

| Artifact | SHA-256 |
|---|---|
| `native-011/build-final/babel-recomp.exe` | `7bb1dc8882b7061a36858c748d5d3fbc55576b67fc26d020a1535250831fc2bb` |
| `native-011/graph-final/generated/program_manifest.json` | `52a2e75e753440e4d2f468dd38c21a4a67b607271c7afde7dbb2aaf60bf3608d` |
| `native-011/effects-final/native_continuations.c` | `2b25ef7b06c673e412929a2e7f76e9f1fe3a00d35319b471b71e9a7ac4109635` |

The generator and build wrapper validate helper/emitter/driver/source hashes.
Generated game code, binaries, ROMs, saves and private captures remain ignored.
The installed owner executable stays batch005; this is source publication,
not an installed-game replacement or a release.

## Executed protocol and effect checks

Actual-core bridge tests pass **3,979 paired scenarios / 98,107 checks**,
including IRQ/NMI/RTI, ownership, deadline, hook, alias, mapper, overlay,
metadata, duplicate/atomic registration and capacity refusal cases.
Decoder-relabel, extra-clock and frame-corruption negative controls each fail
as intended. The earlier poll and MMIO fallback regressions still pass.

The emitter's actual-core proof passes **1,204,992 scenarios / 3,646,376 checks**
across all 205 admitted opcode forms, including 53,200 hardware word paths.
Missing-fetch, double-fetch and stale-constant mutations are detected. These
are ROM-free synthetic execution tests, separate from gameplay evidence.

The full v2 suite passes **774 tests, two skipped**. One Windows subprocess
encoding warning is retained in that broad log; all five affected atomic-output
tests pass again with inherited UTF-8 and warnings treated as errors. Title
tests and final game qualification are recorded in the receipts below.

## Game qualification and limits

The initial 6,000-frame natural-route comparison passes full canonical state
and output checks. Native guest-cycle share rises from **82.9903% to 86.5089%**.
The new effects execute 2,002,405 instructions / 7,775,406 cycles:

| Work removed from the interpreter | Instructions | CPU cycles |
|---|---:|---:|
| LZ | 1,182,998 | 4,530,132 |
| Actors | 819,407 | 3,245,274 |

Every unrelated cost row, the existing compiled-body total and the poll
counters stay unchanged in that controlled probe. Only 100 LZ and 49 actor
contexts execute on that route; other planned contexts remain source-only
there. A native percentage measures guest execution on a bounded route. It
does not measure campaign coverage or demonstrate a host CPU speedup.

**136 fresh pairs / 272 complete loss-free captures / 409,680 frames /
2,550 snapshot sets** pass canonical CPU/WRAM/devices/full APU+scheduler/output.
The official loader, closed journals, exact cost partition, full saved binary
and frame/trace comparisons are independently checked. All **214 actual
same-tier010 controls** pass. The final 146 title tests pass.

Across the mixed-native cohort, continuations retire **73,332,779 instructions /
288,940,458 cycles**, comprising actor 60,192,022/238,592,992 and
LZ 13,140,757/50,347,466. All 960 per-PC diagnostic rows sum exactly to global
counters in every run; forced-reference counts are zero. **222 contexts**
actually execute, using bank82 for LZ and bank83 for actors. Other aliases are
compiled and synthetic-tested, not observed in these game captures. Selected
actor contexts retain26,355 interpreted instructions/98,921cycles under guards;
selected LZ contexts have zero residual in this cohort. Unselected loop/control
work remains interpreted. All 107 old-case reductions equal the new per-PC
native counts; every other cost row and poll count is unchanged. The 14 new
bodies do not add an unreported old-case gain.

Passive300-frame copied-owner-load controls pass. A fresh6065-frame aspect
transition pair matches canonical state and all 67 same-binary/134 cross010
presented frames. Its 19 raw strict differences remain retained. The current136
cohort retains 1,273 raw APU-clock file differences; normalized comparisons
bind executed SPC cycles/order/ports/values and full saved APU/scheduler state.
The old004 mechanics comparison still fails overall at 17/28; all 28 fresh pairs
pass. This does not waive older failures.

All **56 sequential same-binary timing runs / 336,000 frames** pass their
exact state fingerprints and complete execution-counter gates. Polling stays
enabled in both sides; only continuations change. Six alternating paired
measurements per aspect/tier follow eight warmups. Diagnostics/audio/VSync are
disabled and SDL uses the software/dummy path. The primary measure is process
CPU consumed during frame service, excluding startup/shutdown.

| Continuations ON versus OFF | 4:3 | 16:9 |
|---|---:|---:|
| Mixed-native median paired CPU cost | +0.7609% | +0.7126% |
| Forced-interpreter control CPU cost | +1.0657% | +1.0905% |

There is **no measured host speedup**. Keep the experimental opt-in/default-off
policy. The wider route uses **7.0194%** more median mixed-native CPU with
continuations enabled, versus **6.9565%** with them disabled. These descriptive
sequential route cohorts do not isolate raster CPU or establish physical FPS.
They support investigating the renderer separately; the new native percentage
cannot stand in for a widescreen performance fix.

Completed duplicate executables are compacted: **345 copies / 5,003,156,992 bytes**
become **three verified payloads / 15,843,710 bytes** with a restore index.
Source/superseded builds, generated code, saves, failed receipts and all other
outputs remain retained. No older archive is recreated. All 39 owner inputs,
including the installed005 binary, remain unchanged.

The additional source witnesses use recorded assistance and stock-ROM
behavior: 21 more combat rooms, Shadow Aura floor success/no-item controls,
Vampire catch-up reward handling, Solid Arm's authored return and actual walking,
and a bounded logical save/reload/resumed-input sequence. Failed attempts are
retained. The reload case does **not** establish raw fresh SAVE/RESTORE core,
APU or scheduler identity. Vampire bomb rescue remains unqualified. Boss
death and assisted room entry do not establish quest or campaign completion.

Historical004 mechanics failures remain separate. Raw APU timestamp and
word/byte log-grouping differences remain recorded alongside canonical
comparisons; canonical equality never rewrites a failed strict receipt.
The deferred clubhouse/Erik music report is untouched. GaiaLabs' newer dev
build/module identity is still pending and is not covered by these stock tests.

## Private receipts and reproduction

All paths below are under the one ignored `.local/batch-001/` scratch batch:

- `native-011/discovery/candidate-contexts.json` — selected observed contexts.
- `native-011/structural/final/FINAL-RECEIPT.json` — preservation and RomAtlas.
- `native-011/continuation-protocol/FINAL-RECEIPT.json` — owning-core proof.
- `native-011/discovery/effects-proof/FINAL-RECEIPT.json` — effect parity/mutants.
- `native-011/candidate-final-identity.json` — frozen build/source catalog.
- `native-011/counter-audit/probe-capture-audit.json` — controlled actor/LZ attribution.
- `native-011/counter-audit/fresh136-capture-audit.json` — final capture/counter proof.
- `native-011/counter-audit/cross010-root57/summary.json` —114 actual old-tier controls.
- `native-011/structural/cross010-summary.json` —100 further actual old-tier controls.
- `native-011/new-mechanics-final/independent-review.json` — new29 observations/writes.
- `native-011/host-cost/summary.json` and `post-audit.json` — same-binary CPU costs.
- `native-011/runtime-input-binaries-compaction.json` — verified duplicate restore index.

The emitter creates private source and its identity receipt:

```powershell
python scripts/native_effects.py --rom <private-ROM> --contexts <private-plan> --output .local/<fresh-output>
./scripts/build_windows.ps1 -NativeBatch <private-graph-directory> -BuildDirectory <private-build-directory> -NativeEffects <private-effects-directory>
```

The wrapper links effects only into a private AOT build. Omitting
`-NativeEffects` clears a stale CMake selection; ordinary builds retain their
reference behavior.
