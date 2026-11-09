# Native batch 015 — guarded calls and finite scene preview

November 9, 2026. This is a source-only development update, not an installed
build or release. Source baseline: `0e58f018ee17cb54e62835d2f7cc50400f6cc034`.
Private inputs, ROM-derived code, captures and images remain under ignored
`.local/batch-001/native-015`; none belongs in the public repository.

## Frozen candidate and selection

Candidate SHA-256:
`9e9f6a221b4e8a397403a16cd5a063d6daf3143145f5c9f557ee5398444154c0`.
The batch reuses the native-014 graph and all 1,248 emitted bodies unchanged.
Graph SHA-256:
`0e8b5c3deb57023e93f539607bc7fd871a559a6ea821d1bb65f6dee4b464c021`.
Its 415 roots / 1,333 contexts / 1,248 eligible bodies / 85 LLE entries retain
their original identities.

The continuation selection grows from 4,490 to **6,757 canonical contexts /
27,028 aliases**, using 140 fixed opcode bodies. All old contexts remain;
the 2,267 additions are 1,267 guarded direct call/return contexts and 1,000
selected non-frame COP contexts. This is a finite selection, not blanket
promotion of every call or COP. Existing mapper, owner, timing, stack and
runtime-operand guards remain authoritative.

The public default source build remains interpreter-only. The private path
requires `IOG_NATIVE_CONTINUATIONS=1`; compiled poll effects separately require
`IOG_NATIVE_RDNMI_POLL=1`. Both default off. Interpreter/reference execution and
the same-binary legacy lookup (`SNESRECOMP_NATIVE_INSTRUCTION_INDEX=0`) remain
available. The SPC700 audio driver is still interpreted. Fully native Original
game code and sound remain the goal.

## Fresh execution and original writers

**83 fresh reference/native pairs / 166 captures / 436,000 frames / 1,294
snapshot sets pass** on the final binary. These reuse the 014 cohort: 64 prior
v11 source cases and 19 added boss, reward, phase, ceremony and physical
teleport consequences. All four independent original-writer review groups
pass with their original assertions. This is assisted, bounded coverage, not
an earned campaign playthrough or new content coverage.

The comparisons include CPU/WRAM, devices, full saved APU state, scheduler,
executed-cycle events and output. All **647 raw SPC host frame/scanline/clock
stamp differences** remain recorded; those raw logs are not identical. The
canonical checks pass. Native word-store versus adjacent source byte-store
grouping retains inter-operation order and repeated writes; it does not prove
physical intraword bus order. Source witnesses and failed attempts retain
their original identities, without hardware-state conversion.

Cross-014 counter controls bind eight reviewed changed compiled paths. They
are explicitly different-source controls; the fresh same-binary 015 pairs
provide the strict correctness result. Pure comparison memoization retains
full immutable byte keys and unchanged artifact hashes; three fresh uncached
public-comparator controls also pass.

Actual execution reaches **5,921 native PC/MXE sites**: the previous 3,686 plus
2,235 additions (1,235 calls and all 1,000 selected COP contexts). The remaining
32 selected call contexts were not observed; no refusal reason is inferred.
Across the cohort, **385,345,440 guest cycles / 92,397,681 instructions** move
out of the interpreter, while the old 4,490 sites retain their counts.

| Bounded native guest-cycle share | Batch 014 | Batch 015 |
| --- | ---: | ---: |
| 6,000-frame town route, 4:3 | 94.6280% | 96.3806% |
| Same route, 16:9 | 94.6488% | 96.4008% |
| All 83 routes, weighted | 90.110845% | 94.853866% |

The weighted gain is **4.743021 percentage points**. These figures measure
observed guest execution, not project completion, content coverage or host
speed.

## Protocol and upstream gates

The full SDK suite passes **839 tests, two skipped**. Its 23 focused
protocol checks also pass and overlap that suite; they are not additional
unique tests. Fourteen deliberately faulted child processes reject as
required, with their negative receipts retained. These tests exercise the
owning CPU/bus/master-clock/math model, not independent silicon latency or
physical input-to-display latency. The standalone public bank-wrap repro uses
an artificial callee clock charge only to force its bounded stop; actual
coupled-core protocol tests provide separate timing evidence.

The paired JSR/JSL continuation correction preserves caller PB and wraps the
continuation within its low 16 bits, including configured inline arguments.
It is reported in [issue 267](https://github.com/RetroPortingToolKit/snesrecomp/issues/267)
and [PR 268](https://github.com/RetroPortingToolKit/snesrecomp/pull/268).
Both remain open at the November 9, 22:51 UTC check; official main remains
`d8116fac4470ed1c9df70ae56869c7a9cb44935f`.

## Scene preview: transport passes, combat acceptance fails

The new [scene adapter](../src/iog_scene_view.c) is explicitly experimental:
`IOG_SCENE_VIEW_PREVIEW=1` plus the existing widescreen option. Without that
token, the legacy presentation path remains unchanged. It validates live
two-layer scene descriptors and uses actual drawable proportions with the
selected pixel-aspect policy. Only South Cape (`01`) and Aqueduct (`0C`) are
enabled by the finite descriptor gate. The measured CRT-shaped (`4:3`, PAR 7:6)
matrix uses 256 columns at 4:3, 342 at 16:9 and at most 448 at 21:9 or wider.
A 32:9 window remains capped and
letterboxed; full live 32:9 composition is not implemented. Classroom,
inventory and unsupported layouts use the authentic 256-column fallback.

The compact snapshot/reset seam and existing draw callback are connected.
HUD remains centered. The code does not install a new GPU world renderer,
frame interpolation, a higher presentation rate or a per-frame HD RGB copy.
ROM-free C tests cover geometry, validation, reset and source gating; private
captured-PPU replay covers 24 scene/aspect samples with exact original centers.
No ROM-derived art or private classroom filler is shipped.

On the actual RTX 5070 / NVIDIA 616.64 OpenGL path, **16 serial processes /
10,600 frames** cover South Cape, classroom, Aqueduct combat and inventory at
four window aspects. **1,128,064 native texel-center GPU transport comparisons
pass**. This proves the sampled CPU-field-to-GPU mapping, not every scaled
output pixel, renderer speed or combat equivalence.

Overall preview acceptance **FAILS**: nine cross-aspect original-center
controls pass and three expanded Aqueduct combat controls fail. The failures
are retained. Legacy 014/015 wide controls reproduce the same AI/RNG change;
the preview does not introduce it. Original sorting writes actor flag `4000`
and the guest `$0C00` list; AI's COP 27 waits on that flag, while combat and
interaction also consume the list. Enlarging that sort couples gameplay
activation to display width. The latter collision dependency is a source-led
risk, not an additional reproduced damage bug. See
[own-fork issue 2](https://github.com/rages4calm/babel-recomp-companion/issues/2).

The next fix keeps original gameplay visibility authoritative and extracts a
separate host visual actor list at real composition time. Arbitrary late flag
restoration or removal of a failing scene gate would not resolve this cause.
[Renderer direction](RENDERER-DIRECTION.md) records the packet, framing and
acceptance requirements. The normal-path 83-pair result does not qualify this
opt-in preview.

A private 3,840 × 2,160 South Cape image records actual GPU output and bounded
moving-edge checks. This first image uses CRT-shaped pixels and a 342 × 224
field; it is superseded for fair pixel-shape comparison with the square-pixel
reference. Eight fresh Square captures (four looks at 1,280 × 720 and
3,840 × 2,160) pass with identical **398 × 224 source fields and pose/device
states**. `DisplayAspect = 8:7` means genuine square pixels; `1:1` is a
different square-frame mode. The clean variant passes exact native-texel
mapping; SharpPixels, xBR and the separate `sharp.glslp` preset produce distinct
GPU outputs, with no observed fallback or shader error. The 640-column xBR
fallback threshold concerns source width, not display resolution. An external
shader preset bypasses the built-in filter branch; no stacked xBR/sharp claim
is made. SharpPixels is the recommended faithful look, xBR an optional smooth
showcase. The separate contrast-sharpening preset is not preferred. These are
implemented presentation effects, not a new texture pack or reference-pixel
equivalence for filtered output. Output resolution alone is not zoom-out.
The private GaiaLabs reference has a different map width
(1,280 versus stock 768), a 256-world-pixel landmark offset and a 384-column
field (versus the square native field's 398). It is not a byte-equivalent map,
identical framing or native GaiaLabs qualification. No game screenshot is
published with this source update.

## Host CPU, preservation and publication

The host CPU benchmark and independent post-audit pass **42 sequential
processes / 224,000 frames**: six warmups and 36 measurements, six balanced
pairs per route. Both binaries use the same current hardware core and graph;
the comparison isolates the prior versus expanded finite selection on that
core. Frame-service process CPU excludes startup/exit. Dummy SDL/software,
disabled audio/VSync and no per-frame dumps distinguish this from GPU tests.

| Route | Median paired CPU cost change | Pair range |
| --- | ---: | ---: |
| Narrow town | +0.249865% | −0.770713% to +10.160428% |
| Wide town | −2.427484% | −5.555556% to +4.778761% |
| Viper lair | +4.262536% | −5.384615% to +18.055556% |

The results are mixed and noisy. No overall host-speed gain, FPS, isolated
renderer cost or physical latency improvement is established. These costs
remain separate from guest-cycle native share and GPU transport correctness.

Cleanup retires **22,643 superseded native-014 raw/object/test-temporary files /
6,190,536,108 logical bytes (5.765 GiB)** in 11.08 seconds. All 39 protected
owner files and installed build 005 remain unchanged. The 64 exact native-013
source pins, native-014 graph/master/effects and 19 source witnesses, and all
current native-015 inputs/evidence remain. No archive is created or removed;
existing archives are untouched. The actual 23:17 UTC inventory records
29,629,452,173 logical bytes / 27.595 GiB / 251,354 files, before the later
private website export. No installed build, owner settings or saves are updated.

Source-only update; final remote verification is recorded privately after
publication. No release, installer or public game-derived asset is created.
All Babel author credits, upstream acknowledgments and licenses remain.
