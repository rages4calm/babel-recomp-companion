# Native batch 004 planning

Expand observed combat, ability, puzzle and encounter contexts from the
corrected controller-input host. Retain batch 003 roots as historical analysis
inputs. This plan does not qualify a new build or inherit campaign coverage
from overlapping captures.

## Upstream check — November 2, 2026

Official GitHub API heads are unchanged; no vendor replacement or head-delta
merge is needed. Babel adaptations and tested local overlays remain intact.

| Source | Inspected head |
|---|---|
| [SNESRecomp](https://github.com/RetroPortingToolKit/snesrecomp/commit/66eebe6ae415b4fb2607a22e5b12352f612e1bdf) | `66eebe6ae415b4fb2607a22e5b12352f612e1bdf` |
| [RomAtlas](https://github.com/weisserw/romatlas/commit/3d0d1393149491777626f5a8e4461f7c49b2d6df) | `3d0d1393149491777626f5a8e4461f7c49b2d6df` |
| [GaiaLabs](https://github.com/Azarem/GaiaLabs/commit/f7649eb735aaf19b2cd8f693fdaa6669b3e42711) | `f7649eb735aaf19b2cd8f693fdaa6669b3e42711` |

[Default indirect bank-carry issue #240](https://github.com/RetroPortingToolKit/snesrecomp/issues/240)
is open with no comments; [timing issue #205](https://github.com/RetroPortingToolKit/snesrecomp/issues/205)
is open with three comments. The opt-in region-paced pointer path is separate
from the reported default-path failure; no official resolution is assumed.

## Independently checked V4 residuals

The 27 captures are two natural aspect-ratio runs, 23 assisted area visits and
two assisted original transformation roundtrips. All are complete and loss-free,
with passing executed-APU-cycle comparisons. Each individual instruction-cost
sum equals its own receipt's interpreted CPU cycles. Their identities are:

- Build: `6e3abd83b0fa57ec3708ab893e5e60a502d0fcd3c42ea988b47cc804c405fc7a`.
- Program: `858c125d1b895005462324eb5e3a54a92722e42680ce3ef2c71e529847b4bc5f`.
- Generation: `dbc6d0b10da5d80c293bf499a5fb5c3b4e9f35d8d4226a01b8e53d7f8da9e8ce`.

These predate the RDNMI input-owner correction and remain historical. The
11,933 unique residual PC/M/X/E contexts are a planning union, not distinct
gameplay, callable entries or executed native functions. Overlapping costs
must not be added into campaign totals.

| Residual category | Natural 4:3 CPU cycles | Natural 16:9 CPU cycles |
|---|---:|---:|
| Explicit source/timing policy guards | 184,774,597 | 195,177,519 |
| Generated paced labels hit while interpreted | 23,087,805 | 23,403,869 |
| No exact generated label | 12,642,299 | 13,444,078 |
| Exact LLE-only variant | 210,763 | 237,848 |
| Mutable/unwitnessed bus source | 189,549 | 193,373 |
| Generated unconditional pacing fallback | 712 | 712 |

Only five generated unconditional unsupported contexts appear after pointer
support. Below are maxima in a single route, not added weights or projected gains.

| Context | Instruction | Largest individual route cost |
|---|---|---:|
| `$83:8119 M0X0` | `MVN` | 9,856 cycles, Inca hallway |
| `$83:EA76 M0X0` | Indexed indirect `JSR` | 656 cycles, natural route |
| `$83:D416 M0X0` | Indexed indirect `JMP` | 84 cycles, Freedan roundtrip |
| `$83:DFAE M0X0` | `COP $50` | 56 cycles, natural route |
| `$83:8243 M0X0` | `COP $BD` | 8 cycles, Inca hallway |

Other unguarded unsupported source includes COP dispatcher `$80:8482` and
handler `RTI`s outside explicit policy ranges. That does not prove their
return/interrupt contracts safe. Mutable WRAM block moves, architectural
interrupts and live actor/OAM patches retain interpretation.

Already paced labels are the larger residual opportunity, but label presence
does not identify runtime fallback cause. The largest natural cost is the
APU protocol loop around `$82:9138/$82:913B`, including authoritative MMIO.
Resuming native execution after one interpreted instruction would need a
proven current-owner continuation ABI, deadlines/interrupts, stack, open bus
and APU timing. No existing public single-step interface was established here.
That mechanism is deferred; internal labels will not become invented callable
entries. No source/timing guard relaxation is proposed.

Another analysis-only lead is forced-LLE callee exit propagation. For example,
observed `$80:ED0B M0X0` and `$80:BB63 M0X0` stay LLE because calls to guarded
`$82:8000` have unproven exits. An independently proven return contract could
permit callers while leaving that callee interpreted, but no such contract is
asserted here. The private call-candidate index preserves existing LLE reasons.

The independent follow-up supports refining only the overbroad polling guard
start to `02803B`. Pinned [GaiaLabs block metadata](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/parts.json)
separates the preceding 59-byte arithmetic leaf from both polling routines.
RomAtlas agrees with the framework on its 35 instructions across all four E0
M/X entry variants, covering 72 unique instruction contexts. It has a straight
path to `RTL`, exits M0 with X unchanged, and balances its byte push/pop.
System-bank math-register access still falls back at the first guarded store;
no native MMIO model is enabled. Known culling patches do not touch the leaf;
arbitrary image patches still force interpretation. This source/contract audit
supports new analysis eligibility only. New graph, guard and matched-runtime
evidence must establish any resulting promotion or actual gain.

## Input owner and next action cohort

The host's manual vblank and independent beam RDNMI latch can produce two
readable `$4210.7` edges before the next raw-pad refresh. The opt-in ownership
API retains the core's default beam behavior; Gaia selects its manual owner.
Read-clear, manual `inNmi`, IRQs, beam progression and PPU field events remain.
Policy stays outside serialized guest state.

Three focused tests passed against full actual SNES/DMA/interpreter source:
default NMI-enabled/disabled beam behavior, manual/stale latches, IRQ/field
progression, existing snapshot/reset contracts and a synthetic guest wait/remap
witness. These contract checks do not replace matched real-action fixtures.

The next complete captures should establish actions rather than arrival alone:

- Corrected natural 4:3/16:9 controls, including dialogue, movement and transition.
- Enemy rooms with actual attack-handler execution, damage, deaths and room reward.
- Will/Freedan/Shadow actions with verified original form/capability prerequisites.
- Puzzle/traversal and boss contexts across all four guide parts, using the
  encounter/ability owners' source-backed prerequisites and checkpoints.

Retain setup writes, sticky assistance and failed probes. Rendering a room,
pressing an input or loading a boss scene does not establish its mechanic.

## Historical seeds and bounded preparation

Private `planning/historical-profile-index.json` indexes 54 files independently:
24 F8 selected-graph inputs, three original interpreter seeds and 27 qualified
V4 residuals. Original hashes and three build identity groups remain separate.
The oldest absent program/generation fields remain absent. V4 alone omits calls
already native; ancestor inputs retain those roots.

Pass every indexed path as repeated `--historical-profile`; new complete
corrected-build captures use `--profile`. Current cost groups must match all
ROM/module/mapper/program/build/generation identities. Start a new immutable
work directory with profile roots, `--instruction-blocks --region-paced`,
`--max-insns 1024 --max-nodes 12000`, 4,096 MiB process-tree commit and 300 seconds.
Preserve guards and fallback; retain failed resource attempts. The 8,987 CFG
boundaries remain metadata, not blanket roots or native coverage.

After generation, independently decode new observed boundaries with RomAtlas,
reusing identity/byte-matched checks from the 8,192-context structural receipt.
Then compile and compare CPU/WRAM, memory/PPU, executed APU cycles, PCM/queue and
full rendered output. Native CPU shares stay route-specific; host speedup and
campaign qualification require separate evidence.

Private batch 004 receipts: `research/dependency-status.json`,
`planning/v4-residuals.json`, `planning/historical-profile-index.json` and
`research/rdnmi-ownership-tests-final.log`. No game bytes or assets are published.

## Final expanded-graph structural check

The completed `expanded-v2` graph, manifest
`5322a4e3f86935b45184bad90fb01026338680287f76bf1ed84d011e9aa6af7f`,
was independently checked against the 19 selected semantic-case profiles and
both fixed-input natural reference aspects. These 21 inputs contain 18,622
observed PC/M/X/E contexts. The 8,192-context sample had zero opcode/length
mismatches: 5,070 prior decodes were reused only after tool/decoder/ROM identity
and original-byte checks, and 3,122 contexts received new RomAtlas decodes.

All 248 observed cartridge transfer-target contexts were checked. Three other
transfer targets are mutable WRAM mirrors of `$0402`; 12 WRAM instruction
contexts remain without historical byte witnesses and are not promoted by this
analysis. The graph classifies 621 exact eligible AOT entries, 47 exact LLE
entries, 6,251 internal labels only and 11,700 missing exact entries/labels.
Three E1 contexts are not represented by the legacy manifest's entry keys.
These classifications do not establish callable contracts or actual native
execution. Input and generated-manifest hashes remained stable during the check.

Private receipt/log: `research/structural-final.json` and
`research/structural-final.log`. The separate 72-context math-leaf audit retains
matching tool, ROM and decoder identities. Structural samples, repeated route
hits and generated counts are not campaign coverage or matched-runtime proof.
