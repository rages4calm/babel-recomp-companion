# Native batch 020 — script frames, scoped interrupt work and room boundaries

Source baseline `6b7c40d103c948ea9d24a7d254790710a3148804`, November 12, 2026.
Private final candidate SHA-256:
`984919e11911a69a658cd769cbc9d52e83f1f94a22e324733016aa2117ee9d30`.
This is a development source update; the installed owner executable is unchanged.

## Targeting the remaining interpreter cost

Batch 019's matched 105 native captures contain 188,032,136 interpreted guest
cycles. About 139 million overlap whole-function timing/policy barriers.
GaiaLabs' annotated engine and flag references guide the investigation; stock
USA bytes, actual owner observations, RomAtlas checks and matched execution
establish this batch's permission. No developer ROM or widescreen map content
is redistributed or installed into the stock baseline.

All old 9,708 canonical contexts and 531 NMI grants remain literal subsets.
The new selection adds 5,163 canonical contexts: 171 protected fixed effects,
4,988 COP/RTI script-frame contexts and four vector mode contexts. Total:
**14,871 contexts / 59,484 physical aliases**, with **1,021 finite NMI grants**
and **4,988 explicit frame grants**. Six new opcode bodies bring the fixed
body count to 150. All 38,932 previous emitted functions remain byte-identical.
RomAtlas independently validates the new selection's stock bytes and entry modes;
4,678 fresh CLI checks, 481 exact earlier byte/mode proofs and four current
vector checks are distinguished in the private receipt. This is structural
proof, not execution coverage.

The new bridge mechanism grants exact descriptors the existing scheduler and/or
finite NMI owner, without admitting another interrupt owner. All 5,163 additions
have restrictive scope metadata: 4,993 scheduler-only, 73 NMI-only and 97 both.
Seven unchanged-admission diagnostic routes (27,400 frames) record actual owners
and reproduce the previous full CPU/device/APU state and counters. At proposal time, frame contexts unobserved in those diagnostics
received only existing scheduler eligibility; broader executed coverage is
reported below. Indexed-indirect control remains outside NMI scope.

COP/RTI callbacks perform the original stack/frame bus effects under the same
retirement loop. Registration alone never executes them. A separate exact frame
grant and `IOG_NATIVE_FRAME_CONTINUATIONS=1` are required, and finite NMI still
requires its own exact owner grant and enable. The launch switch defaults off.
Atomic permission updates, duplicate registration, immutable restrictions,
invalid modes, live bytes, mapper, pending events, exclusions, owner depth and
RTI exits have actual C bridge tests. No frame is repaired or synthesized.
Reset/IRQ vectors, SP/emulation changes, block moves and RDNMI acknowledgements
remain excluded. Whole-function AOT barrier bounds and the existing RDNMI poll
source are unchanged; this batch qualifies finite instruction exceptions rather
than removing those barriers.

## Matched execution

All **105 reference/native pairs pass** independent closure: 210 captures,
522,200 frames and 1,480 snapshot sets, with the exact final build/ROM/graph
identity in every capture. Matched native guest CPU work rises from
**98.056569% to 99.816657%**. Interpreted cycles fall from 188,032,136 to
17,738,898: **170,293,238 fewer cycles, or 90.566% of the previous remainder**.
The matched earlier 83 routes reach 99.821833%; the natural opening/town route
reaches 99.8539%. These figures describe this corpus, not campaign completion.

All **5,163 added contexts execute natively** in the full corpus. Overall,
13,459 of 14,871 selected contexts execute; 1,412 old contexts remain unobserved.
The new fixed/protected cohort contributes 125,389,458 cycles, COP contributes
16,924,824, RTI 12,575,038 and vector jumps 9,427,024. The remaining 5,976,894
added native cycles occur in old contexts under the newly qualified execution
permissions. Total CPU/master cycles, original polling and generated AOT work
are unchanged; native increases equal interpreter decreases exactly.

Full CPU/devices and canonical complete APU state pass. The 740 raw diagnostic
APU files differ only in SPC host-observer stamps under the retained cycles-mode
comparison. Port values, event order, DSP samples, executed `Apu.portClock`,
complete APU/PCM/queue state and all seven CPU-row fields match strictly. Raw
files remain preserved and are not claimed byte-identical. The existing narrow
Dark Gaia initialization attribution and original raw records/negative controls
remain in force. No comparison rule was broadened for this batch.

Two independent same-binary feature switches are tested in six logical off/on
pairs: NMI and frame effects over natural opening, Dark Friar grant and Dark
Gaia controls. There are **nine unique captures / 53,400 freshly executed
frames**, with three hash-bound all-features-on captures reused between the two
comparisons (71,200 logical comparison frames). Full CPU/devices/raw APU match
exactly; per-PC native increases equal interpreted decreases, with ordinary
native/polling/AOT work unchanged. Of the 490 added NMI grants, 470 are causally
seen in these controls, contributing 4,979,297 cycles; 20 remain outside that
causal subset. All 490 grant sites execute across the broad corpus, but their
all-owner per-PC counters are not a per-PC NMI attribution. NMI work is already
included in native continuation totals and is never counted twice.

## Next measured gaps

The final audited captures still contain 17,738,898 interpreted cycles.
Dynamic WRAM/mirrored-memory or unmapped sites account for 11,428,773;
explicit protected RDNMI sites account for 3,674,705. These are source/policy
categories, not causal runtime-refusal counts. The largest recorded contexts
are 830403/M0X0E0 (7,449,596 cycles), 820403/M0X0E0 (3,077,536), then the
protected 828049, 828053 and 828195 M1X0E0 sites. A profile PC alone does not
establish immutable instruction bytes. Executed encoded-byte/source identity
and live-byte/owner proof are prerequisites for a dynamic-code extension;
current WRAM must not be substituted for an older capture. RDNMI timing guards
remain until matched first-divergence proof supports a replacement.

A source/stock-byte review identifies the 0402–0407 hotspot as the game's own
self-modifying copy helper, installed by the 829E6F/829E7A initialization loop.
Palette and scene callers rewrite its bank operands. Absolute calls preserve
the caller's program bank, explaining the 80/82/83 low-WRAM mirrors. Existing
journals record 321 such call-target metadata rows but no encoded routine bodies;
the recorder currently restricts that capture to dedicated 7E/7F banks. The
narrow provenance review uses an older GaiaLabs source snapshot with independent
stock checks, not an assumption that transformed annotations are identical.
A future native contract must preserve live operands, one-byte/seven-cycle MVN
retirement, bus/event timing and real call/return ownership. Upper-ROM's four-way
alias rule and an atomic whole-transfer copy are unsuitable for this code.
No dynamic-WRAM permission is added in this batch.

## Room composition without invented scenery

Ten additional stock scenes are selected: coastal cave (02), Lance's house (03),
Erik's house (04), Seth's house (05), Will's house (06), Oakton interior (31),
ending (E5), Dark Space (E6), flight (E7) and Dark Gaia (E8). House envelopes use
the game's live authored camera bounds; another storage page does not become an
extra floor or reveal a different story version. The original classroom remains
unchanged, with square-pixel widescreen/1.5x and black outside its actual walls.

The four E5–E8 scenes present their original 256×224 source field with black
outside; no unverified background layer or animation storage becomes scenery.
A first candidate caught a flight readiness bug: its independently animated
background scroll disagreed with the RAM camera, causing periodic fallback.
Full CPU/device/APU and source comparisons passed, but readiness failed and
that failure remains recorded. The final candidate permits independent scroll
only for these source-plate scenes, keeping primary shape, scene/epoch and
source checks. The formerly failing flight frame now has stable 1.5x framing
and exact original sprite parts. World/peripheral scenes retain the strict
camera-publication check. Unsupported menu and malformed phase formats retain
fallback.

Production renderer seam tests compile under Clang 22 with `-Wall -Wextra
-Werror`: **14,524,016 assertions and 51 actual decoder/source checks pass**.
These include inherited controls and are separate from actual pixel/OAM replay
qualification. Dark Space variants 0, 1 and 2 have observed source records;
variant 3 remains unobserved. Unused EB–EF records are not teleported into.

## Verification and limits

[Framework pin and preserved local delta](FRAMEWORK-NOV12.md) remain based on
SNESRecomp `80a41241e39bfffd384506fbe7ca65b386e03050`; GaiaLabs reference main
is `e825dddde466c73cb9900c2c04a7d2bfa37ed165`. Qualified tools remain Clang
22.1.8, Python 3.14.10, CMake 4.4.5 and Ninja 1.13.2. The existing batch-018
build tree and immutable batch-016 generated graph are reused. Generator-only
fixes are not retroactively claimed in retained generated C.

The exact core source gate passes **903 tests, two skipped, no warnings**, with
780 source files unchanged during execution. Focused frame/scope/vector tests
are included in that total, not counted again. Nine separate ROM-free title
policy tests pass. Initial test-preparation/old-contract expectation failures
remain distinct from the final pass. Credits and license notices are preserved.

## Final rendering and play checks

All **110 reference/span pairs pass** independent closure: 220 unique captures,
555,000 frames and 1,710 snapshot sets. The corpus includes 23 new pairs,
82 retained renderer pairs and five cold classroom pairs. All 61 source-admitted
scene IDs are observed in selected formats: 109 positive source pictures and
one deliberately malformed Castoth refusal. Four original-width controls match
all 57,344 pixels. Full CPU/devices/raw APU, per-PC counters, source packets,
whole-world pixels and original published OAM match between drawing paths.
Native-visible parts, order, texels and native-field/HUD partitions have separate
checks; offscreen artwork has no independent original-field oracle.

The lesson's dismissal flag changes through the original script. Both original
classroom doors, east exit to town, native town return and roof exit are observed.
The original room stays intact with black outside. During a reviewed storage
budget transition, 37 closed same-V2 pairs were hash-verified and retained;
73 unstarted pairs then executed using unchanged imported test functions.
There is no V1 substitution or repeated capture counted as new. The initial
6 GiB ceiling was revised explicitly to 9 GiB from measured full-suite storage;
the old bound ledger/producer source remains unchanged.

A fresh 4,400-frame original opening creates the MSU-enabled postclass checkpoint.
The final 240-frame RTX 5070 / NVIDIA 616.64 OpenGL readback uses 1920×1080,
xBR, square pixels and 1.5x extent. Its classroom image and checkpoint hashes
match batch 019 exactly. MSU-1 track 3 starts and consumes audio through a dummy
device; this is not a physical-listening or sustained-FPS test. The private
`native-020/Play Original Classroom.cmd` launches this exact candidate with native
poll/NMI/frame continuations and the existing MSU pack. Owner installation stays
unchanged.

## Widescreen CPU cost

The selected benchmark passes **26 fresh processes / 18,200 frames**, with
unchanged source, inputs, guest state and warmup pictures. Windows
`GetProcessTimes` kernel+user CPU includes startup, diagnostics and shutdown.
The same 700-frame assisted South Cape pose/route, SDL software/dummy devices,
audio-off settings and drawing backend are used throughout.

| Comparison | 1x extent | 1.5x extent |
|---|---:|---:|
| Same final build: SPAN/reference median CPU ratio | 0.407862 | 0.296689 |
| Existing SPAN CPU saving versus reference | 59.2% | 70.3% |
| Batch 020/019 default-SPAN median CPU ratio | 1.043940 | 1.017624 |

The renderer comparison has three order-swapped measured pairs per extent;
the cross-build comparison has two. The latter measures **4.39% and 1.76% higher
whole-process CPU cost**, respectively. Native coverage has improved while this
bounded host benchmark has no measured speedup. Profiling dispatch/guards,
registry startup, callback locality and diagnostic cost remains work; no cause
has been isolated. Neither comparison establishes GPU performance, sustained FPS
or physical input latency. The old build remains runnable.

An earlier single warmup failed only its strict input-hash check: the native mod
writer removed an extra terminal blank line, with identical parsed TOML and all
gameplay checks passing. Its source, plan, output and failed receipt remain.
The corrected test prepares canonical single-newline settings in a fresh sibling
attempt and retains the exact unchanged-input requirement. The 26 successful
processes above exclude that failed warmup.

## Storage closeout

Three exact, source/proof-bound retirements remove **86,557 obsolete files**:
26,226,189,611 logical bytes / 8,548,063,889 reported last-link file-data storage
bytes, with zero locked or failed files. No archives or whole-project scan were
used. Superseded V1 passed outputs and selected passed 018/019 raw captures are
retired; their original JSON/source/profiles/journals/logs remain historical.
Four adjacent retirement markers make the unavailable-golden status explicit.

Current full V2 raw proof, runnable masters, the immutable 016 graph, all
states/seeds, six historical Dark Gaia failure captures, complete 019 classroom
failure lineage, normal soundtrack and owner files remain. Ten exact old019 unit
inputs (1,245,184 bytes) stay in place, together with the compact old018 classroom
input. The E7 failure and required refusal inputs remain. No old passed receipt
was rewritten as new proof. Final capture accounting is 8,408,921,397 bytes
including the 512 MiB noncapture allowance, with no reservations, below the
reviewed 8.5/9 GiB soft/hard bounds. Reported file-data allocation is separate
from exact whole-volume free-space change.


These are bounded, disclosed assisted routes and controls, not a completed
natural campaign or 100% native game. SPC700 remains interpreted. Native guest
work is not a host-speed, FPS or physical input-latency percentage. The existing
world picture adapter is not a new GPU backend, interpolation implementation or
finished remake renderer. Fallback and previous qualified inputs remain available.
