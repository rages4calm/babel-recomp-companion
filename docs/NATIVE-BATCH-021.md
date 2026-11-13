# Native batch 021 — live WRAM copies and smaller native effects

Source baseline `596a38ef1f67c7efd6e9f6c743f4fe0360a80036`, November 13, 2026.
Private candidate SHA-256:
`50cdd0644e8f29cc58856d8466b43d566241cdfcb7b5b686e90b20eb9a8cbd47`.
Development source update; owner installation unchanged.

## Mutable code without cached operands

Batch 020's largest remaining interpreter cost is the game's six-byte bank-copy
helper. Stock initialization copies it into low WRAM; callers rewrite its source
and destination banks. Historical call targets did not establish executed bytes.
The new private diagnostic records actual opcode/operand fetches, with no extra
bus reads, guest writes or inferred snapshots. Four matched captures preserve
recorded CPU/device snapshots, raw APU and previous counters exactly.

The new contract admits twelve observed physical PC/mode entries in banks 80/82/83
at 0402/0403/0406/0407, all E0/M0/X0. It preserves all 59,484 ROM descriptors and
adds twelve physical WRAM descriptors, totaling 59,496. It does not expand RAM
using upper-ROM's four-alias rule. Only the four 83 entries additionally grant
the existing finite NMI owner 00800B; IRQ, nested and foreign owners retain fallback.

Each callback executes one real PHB, MVN, PLB or RTS instruction. MVN transfers
one byte, costs its original seven cycles and fetches both live bank operands on
every iteration. The runtime checks the entire source opcode shape after hooks;
changed shapes, modes, mappers, exclusions and pending events decline normally.
Original stack/bus/event/deadline retirement remains. Default activation is off;
`IOG_NATIVE_WRAM_COPY_CONTINUATIONS=1` enables the separately compiled private
effects alongside the existing native/poll/NMI/frame switches.

The public `native_wram_effects.py` driver requires the bare stock USA image,
hash-bound private actual-fetch witnesses and a fresh private output directory.
Generated C and those witnesses are never distributed. SDK dedicated-bank capture
has a deliberately narrower contract; its lack of mirror entries was not reported
as an upstream bug.

## Repeated native bodies

Optional `--outline-effects` groups identical byte/mode effects into 2,474 shared
bodies. All 59,484 physical/mode wrappers keep their literal PCs and full guards;
descriptor, owner-scope, frame and NMI tables are unchanged. The emitter's default
output remains byte-identical to 020. Generated ROM effect source shrinks from
43,477,053 to 19,297,240 bytes. The combined executable is 23,542,272 bytes versus
020's 37,864,448; executable size alone is not a speed measurement.

## Mechanism checks

The full SDK suite passes 915 tests, with two skips and no warnings; all 784 source
files remain unchanged during execution. Nine title-policy tests pass. The actual
WRAM core fixture passes 1,066 differential pairs over both lookup representations,
including live self-modification, register/index/stack wrapping, real APU/DMA,
NMI/IRQ/owner and event retirement. Whole-transfer and cached-operand mutants fail
causally. Only the first opcode-fetch IPC diagnostic is normalized; operand,
data, stack and write IPC, bus order and devices remain strict.

Outlining's actual opcode oracle covers 1,354,752 synthetic scenarios and 29,003,692
checks, plus 3,264 indirect-jump scenarios and 9,881 checks. A wrong physical-base
mutant is detected; actual bridge branch/call/COP/RTI/NMI/device fixtures pass.

Four same-binary WRAM-off/on controls pass: eight captures, 43,600 frames, 80 exact
raw APU files. Exactly 176,511 instructions / 1,178,033 cycles move from interpretation
to the new callbacks, with every old ROM site's native counts unchanged. The
797 instructions / 5,011 cycles executed inside NMI are a subset of that work, never
extra CPU cycles. Actual fetched-byte source evidence and same-binary callback
qualification are separate receipts.

## Broader execution

The independent suite passes **129 reference/native pairs: 258 captures,
683,400 frames and 1,988 snapshot sets**. The original 105 inputs are unchanged;
14 new area pairs and ten rematch attack/idle pairs are separate additions.
All twelve physical WRAM contexts execute. Fifty previously registered ROM
contexts are additionally observed, giving 13,509 observed ROM contexts.

| Same original 105 routes | Batch 020 | Batch 021 |
|---|---:|---:|
| Interpreted guest cycles | 17,738,898 | 6,310,125 |
| Native guest cycles | 99.816657% | 99.934781% |

The decrease is exactly **11,428,773 cycles / 64.43%** of the previous residual,
with every old ROM site's native counts unchanged. All measured dynamic WRAM
cost in that matched cohort is accounted for by the new helper. The expanded
129-route cohort reaches **99.831025%**, with 21,661,924 interpreted cycles and
17,661,262 WRAM native cycles; its harder denominator is kept separate.
These percentages describe executed guest CPU work, not project completion.

New area tests cover castle/prison, Moon Tribe, Seaside, Ishtar, Watermia, Euro,
Native Village and Dao routes. All five stock Neo rematches now show sampled
nonzero damage, original completion flags, restoration to Will and return to
their hub. Matched idle controls retain living, undamaged bosses and clear win
flags. Teleports, player strength/defense assistance and checkpoint-linked
starting states are disclosed. The Vampire setup additionally sets only the
two source-verified intro flags 86/87 and crosses the original entry trigger;
no enemy HP, actor program counter, death or victory flag is written by the test.
The original 256-by-224 fields match at all 254 new snapshot pairs (14,565,376
pixels). These are assisted fights and area checks, not natural campaign proof.

The existing APU comparison policy is unchanged. The 993 raw APU diagnostic-file
differences concern SPC host observer tags; ordered ports, values, samples,
executed Apu.portClock, full saved APU/PCM/queue state and all CPU-event fields
remain strict. Raw diagnostics are retained.

There are also 17 unmodified metadata differences in cached beam coordinates:
one already exists in the old 105-route cohort, and sixteen occur in the new
cases. CPU frame/master clocks and the selected device/memory dumps match.
A separate passive three-capture, 12,000-frame diagnostic proves that all 31
sampled Castoth latch projections agree after using the actual beam anchor;
WRAM copy off/on also retains identical raw anchors. It does not establish
universal hardware/internal beam equality. Thirteen other unequal new cached
positions have no captured anchor projection. The exporter omits that clock
context; this is reported as a diagnostic issue in
[SNESRecomp #285](https://github.com/RetroPortingToolKit/snesrecomp/issues/285),
without attributing a new game-timing defect or silently synchronizing the beam.

Remaining matched-105 interpreter work is explicitly ranked: 3,674,705 protected
RDNMI cycles, 2,183,192 unregistered opcode/mode cycles, 244,715 actor/OAM policy
cycles and 207,513 selected-but-interpreted cycles whose refusal cause was not
recorded. The expanded tests expose further code to tackle. No additional
permission is inferred from a profile row or a nearby symbol.
## Widescreen regression

**Twenty REF/SPAN comparisons plus four original-field controls pass:**
44 unique captures, 169,800 frames and 432 snapshot sets. Sixteen comparisons
revisit critical old scenes, including the natural classroom lesson, both doors,
town re-entry, town at 16:9/21:9 with 1.5x extent, combat, room bounds and boss
phases. Fifteen publish a supported picture; one retains the Castoth object
refusal. Four new unsupported-scene comparisons (0A,75,F2,F6) retain fallback,
with uniform original-field scaling and black padding checked against the extra
256-by-224 controls. Their missing source packets are not treated as admissions.

The fresh positive subset contains nine scene IDs. Renderer source is unchanged,
and no new scene format is admitted. The previous 61-format/110-pair result
remains historical; it is not relabeled as a fresh full-coverage result. Source,
OAM, ROI, world pixels, CPU/register/device dumps, raw APU and per-PC counters
remain checked under the existing drawing-path contract. Original classroom
geometry, actors and authored decoration remain; the prank is gone.
## CPU cost

The selected benchmark passes **26 fresh processes / 18,200 frames**, with eight
warmups and eighteen measured runs. Seven complete comparison blocks all pass
on their first attempt; no previous failed cohort or partial timing is reused.
Compiler/game activity is monitored, and the other project provided a short
quiet window. All game and monitor children join normally.

The same 700-frame South Cape route uses SDL software/dummy devices and audio-off
settings. Windows GetProcessTimes includes startup, diagnostics and shutdown;
frame-service CPU is recorded separately. Primary comparisons have two reciprocal
pairs per extent; the copy switch has three at 1x and two at 1.5x.

| Whole-process CPU ratio | 1x extent | 1.5x extent |
|---|---:|---:|
| Selected copy-on candidate / batch 020 | 0.997009 | 1.013333 |
| Paired range for that comparison | 0.981595–1.012422 | 1.000000–1.026667 |
| Selected candidate / batch 019 | 1.018908 | 1.008931 |
| Same binary: copy on / off | 1.000000 | 1.008811 |
| Copy-off candidate / batch 020 | 0.987692 | 1.004444 |

**No CPU speedup is demonstrated.** The selected path is roughly flat at 1x
and costs about 1.3% more process CPU at 1.5x in this small test. Its matching
frame-service ratios versus 020 are 1.000023 / 1.014286. The copy-off comparison
includes the new disabled WRAM infrastructure as well as outlining; it does not
isolate outlining causality. Do not multiply medians to manufacture a direct
comparison. Guest native coverage and executable size improved, while
[performance issue 4](https://github.com/rages4calm/babel-recomp-companion/issues/4)
remains open. GPU performance, sustained FPS and physical input latency are not
measured here.

Earlier benchmark preflight/contended/monitor attempts remain failed and separate.
The final monitor uses positive owned-child creation/parent/launch identity for
teardown rows, preserving the external-process guards. Periodic process sampling
cannot rule out every transient shorter than its polling interval.
## Cleanup

The reviewed cleanup removes **43,918 files: 13,273,408,436 logical bytes /
4,353,804,196 reported last-link file-data bytes**, with zero locks or failures.
This combines 268 obsolete compiled test artifacts and 43,650 superseded020 passed
native/renderer raw payloads. No archive, relocation or whole-project scan is used.
The large operation independently verifies 19,258 retained files, 39 owner files,
28 normal soundtrack tracks and all 15 required old unit/refusal inputs.

All source, states/seeds, metadata, profiles, counters, original receipts, failures,
current 021 captures and current/prior runnable binaries remain. Two explicit
RAW-RETIRED-20261113 markers bind the old 020 native and renderer selections.
Their old full 110-pair/61-format proof is historical and no longer an available
raw golden; the fresh 44-capture critical subset is identified separately.
No retry CMD is needed because there are no locked leftovers.

## Opening, source identities and limits

A fresh 4,400-frame original opening and 240-frame NVIDIA 1080p xBR/1.5x presentation
check pass with MSU-1 selected. The resulting checkpoint and image bytes match 020.
Track 3 starts and consumes dummy-device audio. Physical listening and sustained
FPS are not established by this smoke test.

Official SNESRecomp main still matches pin `80a41241`; GaiaLabs main remains `e825dddde`.
Fresh checks find all four authored PRs merged. Eleven of the original twelve
reported issues are closed; profile-import issue 265 remains open. New diagnostic
issue 285 is separate. No vendor replacement or graph regeneration occurs.
Babel author mr0ta / mrOt4, upstream credits and license notices remain unchanged.
The private developer ZIP/BSO, ROMs, generated game output, music and validation
data are not published.

These are assisted bounded execution tests. Campaign qualification, native SPC,
remaining interpreted paths and the larger remake/GPU goals remain work. Guest
native-cycle percentages are not project-completion, FPS or input-latency figures.
