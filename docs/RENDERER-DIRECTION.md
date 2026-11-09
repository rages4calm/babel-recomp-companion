# Renderer and modern PC quality direction

Owner direction, November 9, 2026. This is a design contract and work queue,
not a claim that the renderer or listed features are implemented.

## Product standard

Keep Gaia's art, character and atmosphere while making the enhanced edition
feel like a polished contemporary PC game. Fully native Original game code
and sound remain the foundation; GaiaLabs has a separate integration profile.
Original hardware constraints and inherited defects are not product goals.

Sluggish menus, unnecessary transition stalls, camera/character stepping,
inconsistent frame pacing and avoidable input delay need deliberate fixes.
Preserve correct combat, story, music and cutscene timing while improving those
systems. Do not use a global game-speed multiplier as their implementation.

The enhanced experience should be the finished product's default. Optional
retro presentation can preserve a pixel grid, original aspect and CRT effects.
Both finished presentations should use native game code. The interpreter is a
development reference while native coverage is completed.

## Current limitations

Gaia is not currently qualified as fully widescreen or remake quality. South
Cape has targeted terrain-margin fixes; the classroom still uses an explicit
authentic-width fallback. Other rooms, actor paths, cameras, transitions and
ultrawide composition need scene-specific work. The existing fixed wide field
does not establish adaptive 21:9/32:9 support. See
[current presentation evidence](WIDESCREEN-MODS-005.md).

Inherited filtering/shader facilities need an implementation inventory before
designing replacements. A modern GPU backend alone cannot supply missing map
content, correct offscreen actor behavior or appropriate camera framing.

## Architecture to investigate

Separate the reusable graphics foundation from each game's scene logic:

1. A game adapter supplies world layers, actors, effects, camera state, UI and
   the timing/raster behavior the scene actually needs.
2. A reusable renderer composes those inputs, manages resources and runs
   bounded optional shader/effect passes.
3. A presentation layer handles the display, scaling, color, frame pacing and
   GPU synchronization.

Gaia needs its own tilemap/room/actor adapter. StarFox's geometry and camera work
is a reference to inspect, not evidence that its renderer can be dropped into
this game. Other owner projects remain read-only during this investigation.

Target 4:3, 16:9, 21:9 and 32:9 composition with correct proportions and readable
HUD/menu placement. Check window resizing, resolution/DPI changes, full-screen
transitions and moving between displays with different refresh rates. Multiple
simultaneous game views or monitor spanning need separate design and evidence.

World expansion must draw valid authored scenery and correct actors. Define
room bounds, camera policies and how insufficient content is handled. Do not
stretch the image, repeat stale edge tiles or expose unloaded scenery to claim
widescreen coverage. Maps supplied by GaiaLabs can inform its separate profile;
private game-derived inputs remain private.

## GPU and shader direction

Evaluate a shared modern GPU interface with Vulkan and Direct3D 12 paths,
alongside the compatibility backend the game actually needs. SDL3's GPU API is
one candidate: it supports graphics/compute pipelines and backend-specific
shader formats. This is a candidate, not a backend selection or implementation.
[SDL GPU documentation](https://wiki.libsdl.org/SDL3/CategoryGPU).

Choose backends from measured compatibility, correctness, frame time and
latency on actual hardware. Do not infer a speedup from an API's name. The
owner's NVIDIA system is an important target; inspect its actual adapter and
capabilities before selecting vendor-specific features.

Keep sharp, readable pixel art as a complete presentation. Offer deliberate
optional CRT, scanline, color and enhancement profiles with individual cost
budgets. Extra effects should preserve sprite edges, text, layer ordering and
scene readability. Additional texture work is optional; a complete texture
redraw is not a prerequisite for modern controls, motion or presentation.

Compile/prewarm shader pipelines outside active gameplay where practical.
Capability-check optional color/presentation features and report actual support.
Do not expose settings for unimplemented engine features.

## Responsiveness and timing

Measure CPU simulation, scene extraction, rendering, GPU work and presentation
separately. Record frame-time distributions and worst cases, not just average
FPS or native guest-cycle share. A headless software benchmark does not measure
the NVIDIA renderer, physical display latency or controller latency.

Keep gameplay's intended time progression while investigating higher-refresh
rendering and smooth camera/actor interpolation. Test fractional positioning,
pixel-grid snapping and layer alignment together so smoothing does not introduce
stepping, shimmering or collision changes. Faster native execution alone does
not remove a simulated SNES CPU ceiling, built-in waits or delayed input use.
Those need explicit, independently tested enhanced scheduling/input changes.

Sample input at appropriate simulation/presentation boundaries, avoid unnecessary
frame queues and preserve stable audio timing. Select a present mode and frame
queue depth from supported capabilities and latency/throughput measurements.
SDL documents the frame-queue tradeoff and device checks; Windows also provides
waitable presentation facilities. These are investigation inputs, not a promise
of zero latency.
[SDL queue control](https://wiki.libsdl.org/SDL3/SDL_SetGPUAllowedFramesInFlight),
[SDL presentation capabilities](https://wiki.libsdl.org/SDL3/SDL_SetGPUSwapchainParameters),
[Windows waitable swap chains](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_3/nf-dxgi1_3-idxgiswapchain2-getframelatencywaitableobject),
[Vulkan presentation modes](https://docs.vulkan.org/refpages/latest/refpages/source/VkPresentModeKHR.html).

Use target-refresh budgets explicitly: 16.67 ms at 60 Hz, 8.33 ms at 120 Hz,
6.94 ms at 144 Hz and 4.17 ms at 240 Hz. Qualification needs measured CPU/GPU
headroom, consistent pacing and an input-to-display method; these targets are
not current performance results. Test effect presets and resolutions separately.

## Acceptance and rollout

Original-behavior parity establishes the baseline and catches unintended
regressions. It does not define the finished enhanced edition. Intentional
improvements get explicit acceptance contracts: for example, a faster menu or
transition must preserve its selected item/destination, story flags, music,
control handoff and save behavior while meeting a responsiveness target.
Do not make an approved improvement fail merely because its timing differs
from the original. Do not loosen unrelated correctness assertions to accept it.

First complete the current native batch and its source publication. Then
inventory Gaia and the StarFox reference, measure the actual presentation path,
and prototype a bounded renderer slice covering South Cape, the classroom,
scrolling edges, a busy fight, menus and transitions. Keep the current/reference
path available during development. Expand scene/aspect/backend coverage from
those receipts; full widescreen is earned across the game rather than inferred
from one attractive room. Preserve all author credits and report confirmed tool
bugs upstream, checking existing issues first.

## Source inventory and first implementation boundary

Inspected Gaia at `b5feec7` plus the frozen native-014 changes. Its
[frame setup](../src/main.c) fixes the wide field at 342 columns and does not
install the existing title-owned draw/interpolation/presentation-rate hooks.
[Host extension hooks](../snesrecomp/runner/src/desktop/host_main.h) already
provide useful seams for a game-owned renderer, reset invalidation and viewport
policies. Add an efficient resident texture/packet handoff; the existing CPU
pixel callback should not force GPU readback each frame.

Accelerated presentation and shaders already exist. The ordinary SDL path
uploads CPU-rendered pixels; OpenGL supports GLSL presets and a separate
[resident HD frame-job path](../snesrecomp/runner/src/desktop/hd_gpu.h).
The current build enables HD_GPU, which does not establish its use, speed or
compatibility for every Gaia scene. Shader presets are currently OpenGL-only.
Existing HOST_PROFILE/FRAME_TIMING stages and GPU timestamp/upload diagnostics
can inform the next measurements. RunAhead and image blending also already
exist; neither establishes physical latency or stable object interpolation.

The [Gaia widescreen adapter](../src/iog_widescreen.c) reconstructs two live map
layers, honors scanline scroll/effect changes, moves recognizable HUD groups
and patches ten checked culling operands. It also writes a scratch culling
camera word. It suppresses the classroom and unsupported layouts, and has a
documented extra-sprite-list left-margin limitation. Its stale comments are
tracked in [issue 1](https://github.com/rages4calm/babel-recomp-companion/issues/1);
that is a documentation defect, not a newly reproduced core/rendering fault.

The former local StarFox checkout was not available at the recorded path.
The read-only official reference was instead pinned to
[`kandowontu2/starfox-enhanced@77a5ee84`](https://github.com/kandowontu2/starfox-enhanced/tree/77a5ee84a3d87eb2abfbbf03afb5992557b660bb).
Its [GPU model path](https://github.com/kandowontu2/starfox-enhanced/blob/77a5ee84a3d87eb2abfbbf03afb5992557b660bb/src/render/gpu_model.cpp)
keeps projection, visibility, BSP, clipping and span work resident;
its [portable effects layer](https://github.com/kandowontu2/starfox-enhanced/blob/77a5ee84a3d87eb2abfbbf03afb5992557b660bb/src/render/sdl_gpu_effects.cpp)
supports backend shader payloads. Its simulation/presentation split is a useful
reference for interpolation, not proof of Gaia support or of the owner's former
StarFox executable. Component credits and licenses need preservation before
extracting implementation.

The proposed boundary is a shared SDL3 GPU device/presenter/resource/shader/timing
layer, exposed through a narrow C ABI, plus a Gaia-specific immutable 2D scene
adapter. Capture real layer/tile/palette versions, room envelopes, stable
actors/parts, priorities, windows/color math, raster effects, camera and HUD.
Keep object/history identity stable and invalidate interpolation on cuts,
teleports, load/reset, palette/layout changes and object reuse. Prototype this
boundary locally before choosing a default API or extracting a shared package.
No other project was changed, and no new backend, UI option, NVIDIA effect or
real-GPU performance/latency result is implemented or qualified in batch 014.
