# November 9 framework integration

Official main is pinned to
[`d8116fac4470ed1c9df70ae56869c7a9cb44935f`](https://github.com/RetroPortingToolKit/snesrecomp/commit/d8116fac4470ed1c9df70ae56869c7a9cb44935f).
This advances the earlier `e98dc63` integration. The maintainer merged our
[#250](https://github.com/RetroPortingToolKit/snesrecomp/pull/250) and
[#251](https://github.com/RetroPortingToolKit/snesrecomp/pull/251), along with
[#241](https://github.com/RetroPortingToolKit/snesrecomp/pull/241),
[#261](https://github.com/RetroPortingToolKit/snesrecomp/pull/261) and
[#262](https://github.com/RetroPortingToolKit/snesrecomp/pull/262).

## Source preservation

Before vendor mutation, the private inventory records all 1,337 tracked local
vendor files and the complete 60-path official delta. Base, local and upstream
copies were compared individually. Babel's overlay/replacement map epochs,
asynchronous music observation, Android/handheld GL presenter and fallback,
mods and title-specific changes remain. No vendor directory was replaced.
All 2,124 existing guarded addresses, four NMI fallback floors and nested pins
are preserved. Native batch 013's emitter and test changes are separately inventoried.
Original attribution and license notices remain intact.

The merged instruction/region pacing behavior was already present in our
local emitter. Its live operand/address, sorting, profile, limit and cache
extensions remain additive. The upstream boundary test/docs, folded-deadline
test and timing identity tests are integrated without duplicating the existing
folded-taken cycle charge. The final maintainer branches are recorded in the
[contribution history](../contributions/snesrecomp/205/README.md).

The bridge now uses the upstream pending marker around native APU finalization.
Access-time SPC synchronization keeps Babel's port-observation marker. ROM
mapping adopts the upstream mask/mirroring and full-bank low-ROM fused-read
changes while retaining overlays and replacement. SDL2/GLES2 remains optional;
the default Windows build still uses SDL3. Presenter availability checks retain
Babel's Android/handheld behavior when the optional backend is disabled.

## State boundary

The SPC/DSP work introduces per-clock DSP phases and snapshot version 11 with
minimum 11. Older hardware state blobs are rejected. The owner explicitly
accepts fresh starts; this integration does not infer missing DSP phases or
weaken that version check. Private test states are rebuilt through real boot,
the original map loader, forms and power-grant code. Teleports and gameplay
cheats are disclosed. Old batch 012 state/output receipts remain old-version history,
not current-core audio comparisons.

## Checks

The Windows interpreter-only reference and mixed-AOT probes build with the
qualified Clang 22.1.8 toolchain. Recompiler integration passes 152 focused
pacing/deadline/APU/pointer/live-operand checks and 16 recipe/cache checks.
These overlap the later complete SDK gate.

Twenty-one private C build/runtime commands pass, including both per-clock DSP
snapshot modes, scalar/native DSP mix, guest-time APU ports, cart/fused ROM
reads, the interpreter core, 435 bridge checks in each fused mode, 27 interrupt
checks in each fused mode, and production snapshot transactions. No engine
behavior was changed to satisfy a fixture. The continuation fixtures explicitly
exclude an HDMA-only stub when linking the real bridge and supply their fake
PPU's new null latch hook.

The complete v2 SDK plus timing-generation identity and DSP snapshot gate passes
**810 tests, two skipped**. The title and maintenance script suite passes all
**167 tests**. These are separate gates; focused checks above overlap the SDK
gate and are not added to its total. Both native lookup modes pass the new
status/data-stack protocol tests. No fresh all-platform or complete campaign
qualification is implied.

Game qualification and measured CPU costs belong to
[native batch 013](NATIVE-BATCH-013.md). Same-core native/reference parity does
not independently establish hardware accuracy, speaker/controller behavior or
campaign completion. Windows is the executed target for this integration;
optional SDL2/GLES2 and other platform builds are not newly qualified here.

## Upstream follow-up

At the final November 9 refresh, issues
[#263](https://github.com/RetroPortingToolKit/snesrecomp/issues/263),
[#264](https://github.com/RetroPortingToolKit/snesrecomp/issues/264),
[#265](https://github.com/RetroPortingToolKit/snesrecomp/issues/265) and
[#266](https://github.com/RetroPortingToolKit/snesrecomp/issues/266) remain open
with zero comments. The three submitted timing PRs, #248/#250/#251, are merged.
The older [November 8 integration record](FRAMEWORK-NOV08.md) retains its
original failure and state-compatibility limits.

## Final batch 013 qualification

The clean current-core cohort passes **64 reference/native pairs / 128 captures /
366,400 frames / 1,144 snapshot sets**: 25 fresh-start/form/earned-power and new
consequence cases, 37 selected regressions and two natural aspect routes.
Separate custom reviews preserve the original grant, damage/death, pickup,
negative-control and room-clear reward contracts. The complete cohort audit
binds saved state, output, devices, APU/scheduler, loss-free coverage and exact
native/interpreted cost partitions. Old version-10 captures remain historical.

All 572 raw SPC host-stamp clock-file differences are retained alongside passing
canonical executed-cycle and complete APU-state comparisons. WRAM store logs
can group an actual native word record only with two adjacent same-frame,
same-bank, same-original-IPC source byte records having exact addresses/values;
all inter-operation order and repeats remain. This is store-operation parity,
not physical intraword bus-order proof. Native IPC labels are diagnostic;
reference original writers and uncapped negative-control logs remain required.

The final host CPU comparison and post-audit pass 28 sequential processes /
168,000 frames, with 24 measured runs and four warmups. Median paired CPU-cost
changes are +0.25466893% in 4:3 and -0.31923892% in 16:9. The final wide/narrow
median difference is descriptive and does not isolate renderer cost or establish
physical FPS or a speedup. Exact medians, sample scope, retained launch failures
and cleanup/publication records are in [native batch 013](NATIVE-BATCH-013.md).
