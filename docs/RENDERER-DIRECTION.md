# Renderer and modern PC quality direction

Owner direction, November 9, 2026. Implemented evidence is identified below;
the remaining quality goals are a design contract and work queue.

## Product standard

Keep Gaia's art, character and atmosphere while making the enhanced edition
feel like a polished contemporary PC game. Fully native Original game code
and sound remain the foundation. The eventual main game includes GaiaLabs'
retranslation and approved expanded maps as built-in content, without toggles
for either. Stock USA remains an internal verification baseline. Distinct
content/build identities still prevent incompatible generated code from mixing.
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

Gaia is not qualified as fully widescreen or remake quality. Batch 018 has an
independent world adapter for 50 stock scene formats, corrected host-camera
boundaries and bounded signed shake handling. Its original gameplay view remains 256×224;
82 reference/span pairs and final NVIDIA captures pass. The older expanded-
culling preview's Aqueduct failure remains historical and unresolved on that
legacy path. Classroom/unsupported formats retain authentic-field fallback;
other rooms, actor phases, varying windows, smooth motion and ultrawide
composition still need work. See [batch 018 evidence and limits](NATIVE-BATCH-018.md).

The 1.5× Town view's left strip is fixed by clamping the presentation camera
inside available map data. During bounded shakes, containing the entire
original field takes priority; its uploaded edge cells remain authoritative.
Both native-width shake controls match all 57,344 original pixels. Small maps can still require balanced
padding; a larger storage plane does not establish an authored wider room.
The existing Mode1 span renderer and bounded tilemap restoration reduce
measured whole-process CPU cost by about72% at 1.5× in batch 017's paired test.
This is not a replacement GPU world renderer or a latency/FPS measurement.

A modern GPU backend alone cannot supply missing map content, correct
offscreen actor behavior or appropriate camera framing. Existing accelerated
presentation, shaders and HD frame jobs remain useful foundations.

## World framing, independently of resolution

The first measured 342 × 224 wide field uses CRT-shaped pixels (PAR 7:6) and
adds scenery at the sides while keeping the same vertical world extent.
Increasing output resolution to 4K produces more display pixels; it does not
reveal more world. That private town photo records a baseline, not implemented
zoom-out. For the enhanced baseline, prefer genuine square pixels:
`DisplayAspect = 8:7` (PAR 1:1), not the separately named `1:1` square-frame
mode (PAR 7:8). Eight fresh square-pixel runs now record four looks at 720p
and 4K, all sharing the exact 398 × 224 source field and pose/device state.
The first CRT photo remains historical; owner settings are unchanged.

The implemented faithful recommendation is SquarePixels plus SharpPixels.
Optional xBR gives a visibly smoother showcase; it changes art edges and is
an aesthetic choice. The existing `sharp.glslp` contrast preset is a separate
alternative and bypasses built-in SharpPixels/xBR, so those effects are not
stacked. All four have actual NVIDIA readbacks and distinct outputs; only
clean nearest is source-pixel equivalence. No new texture pack is involved.

The finished custom renderer should support a larger world rectangle in both
directions, including scenery above and below the current view. Investigate
1.25×, 1.5× and 2× view extents as concrete prototype targets; exact room,
camera, cutscene and gameplay policies require acceptance tests. Prefer a
larger world view as the finished default once it meets those contracts.
Preserve pixel proportions and stable integer-grid policies. HUD/text scale
and readability must be controlled separately from world extent.

This requires real world layers and full-coordinate visual actors, without
changing guest AI visibility, the guest camera or global game speed merely
to enlarge the view. Shrinking the existing image inside borders does not
qualify. No launcher or in-game zoom setting should appear before an engine
implementation works. GaiaLabs' expanded maps belong with Retranslation content;
the supplied town has different dimensions and landmark coordinates from
stock, so matching scenery does not establish identical maps or raw positions.

## Architecture boundary

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
widescreen coverage. Maps supplied by GaiaLabs can inform the Retranslation build;
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

Keep the current/reference path available while developing the independent
world adapter. The first finite preview now covers South Cape, the classroom,
scrolling edges, a busy fight and inventory; its failed combat contract is the
next implementation gate. Expand scene/aspect/backend coverage from receipts;
full widescreen is earned across the game rather than inferred from one
attractive room. Preserve all author credits and report confirmed tool bugs
upstream, checking existing issues first.

## Source inventory and first implementation boundary

The native-014 inventory established Gaia's existing rendering paths. Batch
015's [frame setup](../src/main.c) now installs a title-owned draw callback
and [scene snapshot adapter](../src/iog_scene_view.c) for its explicit preview.
The default path retains its existing 342/256-column policy; no interpolation
or presentation-rate callback is enabled.
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
and patches ten checked in-memory ROM culling operands. It also writes a
scratch WRAM camera word; qualified native paths read the runtime operands.
The stale comments tracked in
[issue 1](https://github.com/rages4calm/babel-recomp-companion/issues/1) are
corrected in batch 015. The existing extra-sprite-list left-margin limitation
remains a reason to capture full coordinates before packed OAM loses them.

With `IOG_SCENE_VIEW_PREVIEW=1` and widescreen enabled, live validated South
Cape (`01`) and Aqueduct (`0C`) descriptors use actual drawable proportions
and the selected pixel shape. The measured PAR 7:6 matrix uses 256 columns at
4:3, 342 at 16:9 and a finite cap of 448 at 21:9 or wider.
A 32:9 window is capped and letterboxed, not a full live 32:9 world view.
Classroom, menus and unsupported scenes remain 256 columns. The HUD stays
centered, snapshot/reset invalidation is explicit, and original PPU algorithms
remain the oracle. Private decorative classroom filler is not shipped.

Sixteen actual RTX 5070 / NVIDIA 616.64 OpenGL runs cover four scene types and
four window aspects over 10,600 frames. All 1,128,064 native texel-center
transport comparisons pass. Nine original-center controls pass, but three
expanded Aqueduct combat controls fail; overall preview acceptance remains
failed. These unpaced checks do not measure FPS, GPU speedup or physical input
latency. The default path separately passes all 83 native/reference pairs.

## Next implementation: visual actors without aspect-dependent gameplay

[Issue 2](https://github.com/rages4calm/babel-recomp-companion/issues/2)
records a reproduced inherited coupling: widened sorting changes actor flag
`4000`, AI's COP 27 wait behavior and RNG. Exact legacy-wide controls reproduce
the result on both 014 and 015. The guest `$0C00` sorted list also feeds combat
and interaction; this is an additional source-led correctness risk, not a
separately reproduced collision-damage defect.

The original loop runs AI, sorting, combat/interaction/death/dodge, camera and
HDMA before sprite composition. Other sort callers exist during dialogue and
render-only paths. Preserve original gameplay visibility and its list, then
extract a separate host visual list at actual composition time. Do not repair
this with arbitrary late flag restoration, a second simulation/draw call,
scene removal or blanket widening of independent camera queries.

Use real metasprite parts, full X/Y before 9-bit OAM packing, stable slot and
lifetime identity, ordering, priorities, windows and color math. Existing
`PpuExtraObject` coordinates and original composition provide a CPU oracle.
Keep a true original-width simulation raster and compose expanded world/HUD
from an immutable packet. Retire the ten culling patches from that new path
only after its own acceptance passes. Tests must cover idle and fighting
actors crossing both edges, collision/interaction, rewards, dialogue, room
transitions, load/reset and aspect changes. A deliberately enhanced AI policy
can come later under its own contract; display width must not choose it.

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

The proposed reusable boundary is a shared SDL3 GPU device/presenter/resource/shader/timing
layer, exposed through a narrow C ABI, plus a Gaia-specific immutable 2D scene
adapter. Capture real layer/tile/palette versions, room envelopes, stable
actors/parts, priorities, windows/color math, raster effects, camera and HUD.
Keep object/history identity stable and invalidate interpolation on cuts,
teleports, load/reset, palette/layout changes and object reuse. Prototype this
boundary before choosing a default API or extracting a shared package. No
other project was changed. Batch 015 qualifies existing NVIDIA pixel transport,
not a new backend, GPU world renderer, NVIDIA effect, smooth object history or
real-GPU performance/latency improvement. The resident packet must be proved
before adding those features or exposing settings for them.
