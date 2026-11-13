# Native batch 019 — finite interrupt calls and the original classroom

Source baseline `12bbdd94913fdf2e3dcffd982eb11961422a17bf`, November 12, 2026.
Private candidate SHA-256:
`5f83844b6910f9e2bd6927f061841669ccfa2f4113c294d924711d7952486dc2`.
This is a development source update; the installed owner executable is unchanged.

## Targeting measured interpreter work

The preceding final 105 native captures contain 216,941,428 interpreted guest
cycles out of 9,675,266,024 CPU cycles. About 139 million overlap existing hard
timing/policy guards; those guards are unchanged. The new GaiaLabs actor, wait,
input and audio annotations informed the source review, while actual stock
instruction bytes, recorded owner context and execution determine admission.

The selection preserves all old 9,699 canonical contexts and adds nine measured,
unguarded enable/disable-NMI helper contexts: **9,708 contexts / 38,832 aliases**.
They use existing opcode effects; the fixed body count remains 144. RomAtlas
independently checks all nine additions. Re-emitting the old selection is byte
identical, all 38,896 old functions remain exact, and old descriptors are retained.
An additional RDNMI-acknowledgement candidate was excluded from this batch rather
than treating a static cost estimate as runtime permission.

Finite NMI admission adds **101 already-selected stack/direct-call contexts**
whose actual owner was recorded in earlier unchanged diagnostic executions.
Together with the prior 430, there are 531 grants / 2,124 aliases. These fixed
effects retain the real stack reads/writes and the same owning retirement loop.
The exact NMI entry, owner depth, original frame, mapper, live bytes, mode,
pending-event and policy checks remain. IRQs and nested bridges do not inherit
the grant. COP/RTI, stack-pointer writes, block moves, emulation changes and
indirect control remain outside this finite NMI protocol.

All 101 added grants execute in three same-binary NMI off/on pairs, contributing
940,936 causally isolated cycles in that limited corpus. The three pairs total
25,200 frames; full CPU/devices/APU match, including raw APU event files. Per-PC
native increases equal interpreter decreases and the NMI subset. NMI counters
are subsets of continuation work, never added a second time to guest CPU totals.

The natural opening/town route reaches 98.3623% native guest cycles, compared
with 98.0860% previously. This is a guest-work measure, not host speed or game
completion.

All **105 reference/native pairs pass**: 210 captures, 522,200 frames and 1,480
snapshot sets. The exact previous corpus moves from 216,941,428 to 188,032,136
interpreted cycles, a **13.32585% reduction** in remaining interpreted work;
native guest cycles rise from 97.757773% to 98.056569%. The matched earlier
83-route subset moves from 97.775222% to 98.074265%, reducing interpreted work
by 13.44145%. Total CPU/master cycles, polling and generated AOT work are unchanged.
The 28,909,292 added native cycles split exactly into 9,635,749 from the nine
new helpers and 19,273,543 additional NMI cycles. All nine helpers execute;
8,282 selected canonical contexts execute overall, leaving 1,426 unobserved.

These are matched counters across two SDK builds. The separate same-binary
NMI off/on pairs above isolate that mechanism. Full CPU/device comparison and
canonical APU comparison pass; 740 raw APU files retain diagnostic instruction/
timestamp differences, which are recorded rather than claimed byte-equal.
Dark Gaia's compiled initialization-store attribution remains narrow and
source-bound, with raw IPC0 records and negative controls retained.

## Original classroom, wider presentation

Scene 08 now uses its original 512×256 room, including the original east wing
and town stairs. The secondary 512×512 layer's extra storage does not become
another floor. Walls, stools, actors, dialogue, collision and warp destinations
are unchanged. No added pupils, expanded architecture or private movement hooks
are included. The nightclub prank and its private music copy have been removed.

Confirmed uniform gray void cells become black; authentic front-wall faces stay
unchanged. The original nonvoid pixels have their own equality checks. Intentional
gray-to-black pixels, projected HUD pixels and HUD-only unobserved terrain are
reported separately. Unknown classroom layouts/definitions retain fallback.
The world presenter keeps square-pixel widescreen and its 1.5x view extent.

Classroom unit checks pass 1,938,911 renderer assertions and 21 actual decoder/
source checks. Five fresh reference/span pairs pass 65,000 frames: natural lesson
and dismissal, 16:9/21:9 presentation, both original exits, and town reentry.
Across the five selected pictures, 254,029 original nonvoid pixels and 3,525
projected HUD pixels match; 19,623 confirmed void pixels intentionally become
black, while 9,543 HUD-only terrain pixels remain unobserved. These categories
sum to all five original 256×224 fields; they are not a blanket unchanged-pixel
claim. Full CPU/devices/raw APU, source packets and whole-world reference/span
pixels match. All **82 existing renderer pairs / 164 captures / 337,600 frames /
1,256 snapshot sets** also pass. Their source packets, whole-world pixels,
full CPU/devices and raw APU files are equal between pixel/full-copy reference
and span drawing. The deliberately malformed Castoth phase retains fallback;
both native-width shake controls match all 57,344 original pixels.
The earlier private expanded-classroom experiments are not
used as proof of the original layout.

The final NVIDIA 1920×1080 xBR capture uses the same binary and a fresh,
naturally replayed original-classroom checkpoint. Its 598×336 world view and
MSU-1 town track 3 startup/audio consumption pass a 240-frame check. This uses
a dummy audio device; it does not prove physical listening or sustained FPS.

## Framework and verification

[SNESRecomp 80a4124 and local delta](FRAMEWORK-NOV12.md) records the targeted
13-file upstream merge and preserved Babel/Companion changes. Runtime fixes are
compiled into this candidate. Generator-only fixes are available for future
generation; the immutable, previously qualified batch-016 graph was not regenerated
or silently rewritten. New continuation effects are independently emitted.

The SDK v2/timing/DSP gate passes **877 tests, two skipped, no warnings**. Another
29 upstream screenshot-response tests pass. Strict C fixtures cover the bank-wrap
bridge, long/Unicode mod paths and expression-safe PPU accessor. The strengthened
NMI core fixture passes 14 cases with real CPU/SPC/DSP/DMA, status widths, nested
calls, NMI-enable writes, deadlines and fallback. Those 14 are already inside the
877-test gate. Initial destructive fault fixtures timed out; their failed records
remain, followed by bounded saved-stack-data and call-cycle mutants that reach
the comparison oracle. No timeout was relabeled as a passing fault check.

The original interpreter, native-off controls and pixel reference remain available.
No whole-game campaign, native SPC replacement, new GPU backend or physical-input
latency claim follows from these tests.

## Storage and source publication

The prank and its music copies, ten superseded executables, 5,261 source-bound
obsolete compiler objects and 34,308 reviewed old raw files are retired directly.
Total: **39,674 files / 12,268,759,786 logical bytes**. Reported last-link file-data
allocation removed is **7,876,538,315 bytes**; this is distinct from exact physical
volume reclamation. Normal soundtrack hardlinks, current/prior master builds,
owner files, all states/seeds, current 018 golden proof, immutable 016 graph and
019 proof remain. No archival copy was created for this retirement. Old 015/017
raw comparisons are historical records, not immediately available goldens.

`Clean Disposable Files.cmd` retries only the reviewed allowlists; raw retirement
requires the exact local plan and completed-proof authorization marker. Fifteen
ROM-free cleanup guard tests pass. See [cleanup policy](PROJECT-CLEANUP.md).
Publication contains reviewed source, tests and documentation only; no ROM,
generated game code, executable, soundtrack, save, screenshot or private receipt.
