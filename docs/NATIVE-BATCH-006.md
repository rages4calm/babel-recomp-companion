# Native batch 006: current framework and inventory cohort

November 8, 2026. This is a private experimental stock-USA candidate, not a
release, fully native game, current retranslation build or campaign certificate.
The owner's installed batch-005 executable and personal data remain separate.

## Source and executable identity

SNESRecomp main `e98dc63b474d5469ad984490e04eb0b0496ec62e` was integrated
through an inventoried three-way merge, preserving Babel's changes and the local
opt-in instruction/region pacing and native APU work. These local mechanisms
remain distinct from accepted upstream main. [Integration and source checks](FRAMEWORK-NOV08.md).

| Artifact | Identity |
|---|---|
| Stock USA ROM SHA-256, read-only | `32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd` |
| Previous graph SHA-256 | `5322a4e3f86935b45184bad90fb01026338680287f76bf1ed84d011e9aa6af7f` |
| Expanded graph SHA-256 | `a5acf97ce11e900aded284ef3357a3cdbb690b64b22b8607532f5ab6cf5513ba` |
| New framework, previous graph executable | `a5ae4392f20a579a371c2310038d14600681d816f6340238c8744d73ef635b47` |
| Expanded candidate executable | `c028093dee06ba4ebcfbce97659ff37fe41ee87b0a98cc70edd3c31c9002dfda` |

The candidate is retained privately at
`.local/batch-001/native-006/build-expanded-v2/babel-recomp.exe`.
The interpreter-only default and same-binary `SNESRECOMP_INTERPRET_ALL=1`
reference remain available. No owner save, settings, music or controller data
is replaced by a candidate build.

## What the expansion adds

The input index preserves all earlier graph seeds plus selected qualified-route
captures, as **172 separately identified historical profiles**. Their costs
were not combined into a current-build or campaign measurement. Current
GaiaLabs baserom labels identify the additional inventory/menu helpers.

The graph grows from 312 to **328 roots**, 1,180 to **1,199 variants**, and
1,104 to **1,120 eligible candidates**. There are 19 new node contexts,
including 16 eligible contexts. Three new contexts retain LLE dispositions:
`82EC58 M0X0`, `82ED02 M0X0` and `82EED2 M1X0`, because of structural poison,
COP/data boundaries or unproven callee continuation. No earlier eligible node,
policy guard or inherited NMI-callee exclusion was removed.

The new cohort includes slot positioning/display, equipment cursor, tab cursor,
inventory snapshot helpers and scene-script setup. Eligibility and generated
labels are not per-entry execution counts. Existing captures record interpreted
instruction costs rather than direct native function-hit counts, so no claim
that every new body executed follows from the graph.

RomAtlas independently checked **274 instruction contexts**, covering every
new entry and the emitted instruction contexts within the new eligible bodies:
zero opcode/length mismatches and zero guard overlaps. The tool, original
bytes, local decoder, current Gaia names and generated graph hashes are bound
in private receipts. This remains structural evidence, not execution proof.

## Fresh execution

| Check | Result and scope |
|---|---|
| Current framework with previous graph | 29/29 fresh reference/native pairs pass: 58 processes, 76,920 frames and 304 snapshots. |
| Expanded graph | 29/29 fresh reference/native pairs pass, with the same bounded routes and independently reasserted transition, inventory and form conditions. |
| Graph-only comparison | All 29 previous-graph/expanded-graph native comparisons match exactly under the same current framework. These reuse the fresh runs above; they are not extra executions. |
| Expanded combat/ability/reward replay | 28/28 current reference/native pairs pass, including 19 positive cases and nine controls. Both Castoth/Viper fresh HP-zero event checks pass. |
| Copied owner checkpoint | Existing RTLS v10 state loads on the installed 005 and expanded candidate. Three separate 300-frame runs preserve observed scene/form/HP and story flags; the new reference/native pair matches strictly. Fixture mods/audio were off; no owner preferences were copied. |

The expanded candidate therefore passes **57 current same-binary pairs / 114
fresh processes**, totaling **148,240 frames**, plus the separate owner-load
compatibility check. Comparisons include CPU/WRAM
traces, CPU/master totals, device journals, executed-cycle-bound APU events,
complete APU/scheduler state and full final output. Assistance stays explicitly
recorded; teleports, boosted stats and learned-bit injection do not establish
earned progression or normal boss difficulty.

The 6,000-frame natural classroom/South Cape route remains **12.8307% native
CPU cycles in 4:3 and 12.8268% in 16:9**. The two inventory fixtures increase
from **8.5266% to 8.5427%** and **26.1150% to 26.1329%**, respectively, under
the same integrated framework. This is a small measured coverage gain, not a
host-performance benchmark. The large guarded vblank wait and mutable culling
loops remain interpreted; removing their guards would inflate coverage without
establishing correctness.

## Historical comparisons remain separate

Strict mechanics replay against old batch-004 witnesses remains **17/28
passed**, including 11/19 positives and 6/9 controls. Eleven fail historical
output, audio or timing equality; their historical semantic conditions were
not carried. All failures and first divergences remain recorded. Current tier
parity does not turn these failed cross-version comparisons into passes.

A fresh comparison with the actual installed batch-005 binary also differs.
An isolated source A/B reverses **only merged upstream #258** in a private
vendor copy: it restores exact CPU/WRAM trace, CPU/master totals, APU/scheduler
and bound audio-event agreement across the complete 6,000-frame route. This
attributes that route's timing changes to the upstream queue-boundary fix:
the old scheduler ran one SPC cycle past the requested target, while current
main stops at it. The reverse-258 binary is a diagnostic control, not a fix
or recommended executable. Production retains the upstream correction.

One historical frame-1500 framebuffer difference of 353 pixels remains in that
control. New clipped-color half-math is a source lead, not independently isolated
attribution. The complete final 4:3 output matches. Historical comparisons
remain failed wherever equality is not established. Ordinary current-build
canonical audio save/restore and representative host-cost gates from the timing
contribution remain open; none is waived by these route checks.

## New GaiaLabs input and external reference

[The developer's newer baserom and modules](GAIALABS-MODULE-INTEGRATION.md)
were checked through a new offline preflight against clean pinned checkouts.
It hashes 261 files across 32 modules plus 96 baserom files, and distinguishes
22 selected modules from four commented entries. The public development script
includes Apocalypse Gaia and leaves minimap-v2/widescreen commented out; it is
not automatically the ordinary retranslation profile we want to support.
Published package commits also differ from current source branches.

The exact raw-map rebuild path and override order are documented without
copying upstream implementation/assets into the host. The current dev build
offered by DM is still needed, with its source/dependency/module identity,
before qualifying that content. Existing 342-column rendering and bsnes-hd's
384-column authored-map contract require deliberate integration.

[Mesen2 MCP readiness](MESEN2-REFERENCE.md) now has an actual private headless
check: official checksum-verified 0.6.0, 81 tools, ROM/CPU/memory reads, three
bounded frames, 15 independent checks and clean shutdown. It is not an external
parity result; future comparisons need synchronized guest points and inputs.

## Tooling, source tests and reproduction

Larger profile sets exposed a Windows launcher bug: JSON-encoding the entire
child command on another command line doubled path backslashes past the OS
limit. The resource-gated launcher now transfers that command through its
stdin pipe after applying job limits. An executed regression reproduces the
old failure and passes after repair; timeout and memory-limit checks still pass.
All **100 title Python tests** pass, including the 17 module-inspector tests.
Framework passing and failing checks are itemized in the integration report.

`build_windows.ps1 -BuildDirectory` can build candidates below ignored `.local`
without replacing the owner's installed binary or build cache. For retained
private generation inputs:

```powershell
./scripts/build_windows.ps1 -NativeBatch .local/batch-001/native-006/expanded-v2 -BuildDirectory .local/batch-001/native-006/another-build -Jobs 2
```

The public source contains no generated game C, ROM, soundtrack, saves,
screenshots or private receipts. Detailed evidence is bounded beneath
`.local/batch-001/native-006/`. The verified upstream CI link issue is reported
as [#263](https://github.com/RetroPortingToolKit/snesrecomp/issues/263).
Original Babel, GaiaLabs, retranslation and all prior credits remain intact.
