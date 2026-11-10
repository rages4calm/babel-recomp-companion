# Native batch 017: script coverage and a faster world view

November 9, 2026. Source baseline `522b078`. The tested private candidate is
`782833d274f28d884f53b6e5e305d2bb0c4924ab817715c4fa233e4602a19769`.
This remains a development source update, not a release or a claim of complete
native execution, full widescreen coverage or an earned campaign playthrough.

## Native execution

The selection retains all 6,757 previous contexts and adds 1,371 observed
contexts: 371 COP-dispatcher/saved-register/frame-data contexts and 1,000
further contexts using the existing effects contract. Total: **8,128 canonical
contexts / 32,512 aliases**, within the existing 32,768 capacity. The old
27,028 descriptors and their emitted effect/helper functions remain identical;
all 140 existing opcode bodies are conserved. The immutable batch-016 graph
is reused without copying/regenerating it or adding speculative function roots.

These effects already existed in production. The new work establishes the
additional frame-ownership proof and selection; no production emitter, bridge
or timing guard is relaxed. COP/RTI control and indirect jumps remain decoded.
The optional five indirect-jump sites were deferred rather than included
without their own capability proof. Development interpreter/reference paths
remain available.

The new ROM-free actual-core tests cover both lookup implementations, all 16
data-stack forms, COP PB/PC reads, saved return-PC edits, nested COP/NMI, finite
deadline expiry, real comparator IRQ and host delivery/acknowledgment, and
frame-discard-to-RTL behavior. Each lookup executes 2,912 paired cases / 442,656
checks. Eight causal mutants are rejected. Failed fixture assumptions about
automatic IRQ delivery and two initially noncausal mutants remain recorded;
they were not reported as engine defects.

All **83 fresh same-binary reference/native pairs pass: 166 captures, 436,000
frames and 1,294 snapshot sets**. Original-width simulation, authoritative
resume PC, full CPU flags/registers, guest/master clocks, IRQ/HDMA counts,
watched stores, device state and the established complete APU checks pass.
All forced-reference native counters are zero. The official capture loader
reports no loss and conserves the counter partitions.

Actual native guest-cycle share is **96.5202%** across this finite corpus;
the classroom/town routes reach 97.0578%. The new cohort actually executes
1,369 of the 1,371 contexts: 31,903,484 instructions / 135,552,332 guest cycles.
The two unobserved additions are not assigned an inferred refusal reason.
7,280 total continuation contexts are observed. These are execution measures,
not completion percentages or host speed. The remaining interpreted guest
cycles total 281,948,133; the SPC700 sound driver is still interpreted.

Exactly **647 raw APU TSV files differ** between reference/native captures.
Both unnormalized hashes and first differing rows are retained. The established
comparison preserves SPC access order, ports/values, executed APU port clock,
DSP sample counts and all seven CPU-event fields. Only host frame/scanline/
hclock labels are excluded from its canonical event comparison. Complete
APU/SPC/DSP/PCM/scheduler snapshots pass. This is not raw-byte identity or
independent physical intraword-bus/hardware proof; no new blanket normalization
or fresh memo-control claim is introduced.

## Framing and drawing

The reported town pose previously requested worldX−19 at 1.5× extent, leaving
a black left strip. The pure host-camera policy now starts at **worldX0**,
placing the original field at nativeX152 within the larger canvas. Larger
maps clamp at their edges; maps smaller than the entire requested canvas
retain explicit balanced padding. Pixels are neither stretched nor filled
with invented scenery, and the guest camera/visibility/candidate list remain
unchanged. All ten gameplay-culling operands stay stock in the world adapter.

The existing Mode1 span algorithm is now the default for detached world
pictures. `IOG_WORLD_REFERENCE_PIXELS=1` selects the old pixel reference and
full VRAM-copy path. Explicit zero/invalid `IOG_WORLD_SPAN_PIXELS` also selects
the reference; unsupported picture modes retain it. The helper rejects the
live PPU and restores caller flags. Rendering changes only owned picture data.

Between chunks the host restores at most 58 touched tilemap words instead of
copying all 64 KB of VRAM each time. The existing identical-VRAM epoch check
is retained. Per-line palette/register input, brightness and actual scanout
ownership remain explicit; drawing never executes another CPU/HDMA/IRQ pass.

The independent world adapter now admits these **15 verified stock formats**:
`01, 0C, 0E, 0F, 12, 29, 3F, 55, 67, 85, 8A, B6, CC, DD, EA`.
The older legacy preview still admits only its original two scenes. Classroom
08 remains excluded: spare storage is not proof of an authored wider room.
The nine-row player graphics format is bounded; actual forms 0/1/2 and active
override rows 4/5/6 are observed. Rows 7/8 have format/synthetic proof only.

All **42 fresh reference/span pairs / 84 captures / 150,200 frames pass** on
the final binary. Full guest/APU/CPU/policy state, per-PC/native-site counts,
complete new-world pixels and exact source-packet bytes match across modes.
Every selected picture is genuinely world-rendered. Of 75,100 optimized-mode
frames, 61,602 are ready; intermediate setup/effect fallbacks are retained.
Six-view grids cover both 16:9 and 21:9 at 1×, 1.25× and 1.5× extents.

An explicit source packet binds published precomposition RAM, all 544 actual
OAM bytes, original field, HUD, 225 register/epoch records and epoch picture
memory at the requested output frame. It removes the earlier ambiguity from
joining end-of-logic RAM to the previous published sprite table. These optional
diagnostic files remain private. A valid captured source may still be refused
by the visual adapter; ready/reason and packet-I/O completeness are separate.

Independent replay of the original stock composer matches **16 selected
published sprite tables / 8,704 OAM bytes** across all 15 scenes plus Dash.
350 native-visible parts, including 124 player parts / 66,368 raw sprite
texels, match source attributes, coordinates, palette indices and relative
native-slot order. Two old unpaired late Castoth source failures remain failed;
the valid selected struck phase does not qualify every death/cutscene phase.

A separate fixed Town proposition checks all 25,728 predetermined pixels
above/below/both sides: 25,559 independent terrain pixels, 156 captured-HUD
pixels and 13 actual offscreen-actor pixels. Earlier background-only and
background-plus-HUD assumptions remain failed. No pixels were masked or
regions reselected to obtain the composite result. Original-frame ROI checks
also retain a separate source-HUD-only terrain category that cannot be
independently observed beneath the original UI; no full-57,344-pixel
independent claim is made for those scaled-HUD views.

All 18,900 captured line records have no spatially varying color-window effect.
Vampire has 450 nominally mode-sensitive records, but its empty inverted
window is spatially constant. Broader varying-window and offscreen-overlap
composition remain unverified domains. Matching the stock depth clamp does
not establish every expanded-world overlap's aesthetic correctness.

Two final-binary NVIDIA 1280×720 captures pass, including default-span nearest
transport of every 200,928 source texels and the requested xBR look at the
same pose. The corrected 1.5× image has no left map-edge strip. Filtered xBR
colors intentionally differ; no independent filtered-color identity claim is
made. The previous failed offscreen 4K GPU attempt remains failed; no new 4K
claim is introduced. HD2D/HdFx and the new GPU-world engine remain future work.

## Measured CPU cost

An isolated real-PPU component test first found span/reference process-CPU
ratios around 0.125–0.129 with identical pixels. The final whole-process test
then runs six balanced AB/BA pairs plus warmups per extent, **42 processes /
29,400 frames**, on the same final executable with unchanged controls.

| View extent | Reference CPU median, 700 frames | Optimized CPU median | Paired median reduction |
|---|---:|---:|---:|
| 1× | 6.227 s | 2.492 s | 60.0% |
| 1.25× | 10.438 s | 3.031 s | 70.8% |
| 1.5× | 12.336 s | 3.500 s | 71.8% |

GetProcessTimes user+kernel time is primary. These totals include startup,
exit and matched diagnostic overhead. All per-frame CPU/policy streams,
sampled WRAM and 32,512 exit-site counts remain equal. Host raster/capture
elapsed-stage medians separately change 6.796→1.663 ms, 12.711→2.416 ms and
15.407→2.946 ms. This is a bounded CPU cost result, not sustained GPU FPS,
physical input latency or a measured improvement to intentional game waits.

## Tools and publication

Completed private test data was compressed in place with NTFS compression.
All 20,128 selected files retain their original paths, sizes and SHA-256
hashes; allocated storage fell by 6,071,073,461 bytes (about 6.1 GB).
No archives were created and no owner files were changed or deleted.

Official SNESRecomp main remains `e9c207322c148eccc8a679b72d8b005d0d95d31c`;
the local Babel deltas and all hard timing guards remain. The SDK suite passes
849 tests, two skipped. One Windows child-output encoding warning is retained;
the affected official test additionally passes with inherited UTF-8 and strict
thread-warning handling. The unmodified upstream red/green reproduction is
reported in [issue 270](https://github.com/RetroPortingToolKit/snesrecomp/issues/270).
No production SDK patch or redundant full-suite rerun was used to hide it.

Original author and upstream credits/licenses remain. This work uses the
stock-USA baseline; the eventual main game's built-in retranslation/approved
maps follow separately. No private GaiaLabs build, soundtrack, screenshot,
save/state, generated game C or validation payload is published with source.
