# Babel baseline audit

Source inspection: 2026-11-02. Starting fork/upstream commit:
`2fa71604222e34ee10d925cc14ebbcfe13a49ad1` (Babel 1.0 plus documentation/CI fixes).
This document records the inherited implementation, before Companion changes.
Runtime receipts and subsequent work belong in the handoff; this audit itself
does not certify boot, image/audio parity, controller behavior or a campaign.

## Execution and supported input

| Path | Actual source behavior | Evidence |
|---|---|---|
| Stock, default build | Every guest 65816 instruction is interpreted. The executable is native host software; the stock game logic is not statically compiled in this configuration. | `CMakeLists.txt:43`; `snesrecomp/runner/runner.cmake`, `snesrecomp_target_generated_code`; `runner/src/setup_host_dispatch.c:33` has zero AOT entries. |
| Stock, local generated build | `SNESRECOMP_INTERPRETER_ONLY=OFF` links locally generated C. Reset still enters the interpreter; eligible JSR/JSL calls can bounce into compiled bodies and missing entries stay interpreted. Native instruction coverage has not been measured. | `src/game_rtl.c:110`; `snesrecomp/runner/src/snes/interp_bridge.c:2178`; `tools/regen.sh`. |
| Apocalypse Gaia | A supplied IPS patch is validated before in-memory changes, then all interpreter-to-AOT bounces are disabled. Original ROM file is not modified. | `src/iog_ips.c`, `ApplyIps` and `ActivateApocalypse`; `interp_bridge_set_interpret_all(1)`. |
| IoGR randomizer | A supplied 2/4 MiB HiROM seed replaces the cartridge image after basic header/reset checks, then interpretation is forced and RetroAchievements blocked. The catalog requests separate saves. | `src/iog_randomizer.c:88`; `mods/preloaded/packages/iog.randomizer/1.0.0/manifest.toml`. |

`recomp/symbols.toml` currently names RESET and NMI with `emit = false` for both.
The larger `bank00.cfg` also contains function seeds; counts of those seeds or
generated C files are not runtime coverage. Default builds do not link them.

The supported base image is the unmodified USA 2,097,152-byte HiROM; an optional
512-byte copier header is stripped. Identity is centralized in `rom_identity.txt`:
SHA-256 `32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd`,
CRC32 `1c3848c0`. European ROMs supply optional language text/fonts, not a
replacement base game. Randomizer acceptance is weaker than stock digest checking;
it must remain a separately labeled mode.

The hardware is still modeled: SNES CPU/bus/register behavior, PPU scanline
rendering, DMA/HDMA, S-SMP/SPC driver and DSP, cartridge/SRAM, input and audio
timing. C host features such as inventory overlays, localization, QoL and MSU-1
integration do not establish native execution of original game routines.

### Demonstrated source constraints

- `src/game_rtl.c:126` deliberately avoids direct AOT reset dispatch: its comment
  records an unbounded compiled poll at `$82:8051` waiting on `$4210`. Do not
  remove the interpreter guard to manufacture a native claim. Reproduce with a
  bounded differential fixture before attempting promotion.
- Frame simulation uses 357,368 master clocks and at most 64 slices, with NMI
  gated by the guest's NMITIMEN (`src/game_rtl.c:61`, `:148`). Rendering applies
  HDMA and a vertical-comparator IRQ before each visible line. This is a
  game-specific frame driver, not proof of full cycle accuracy.
- Save states explicitly preserve guest PC and CPU registers in addition to the
  modeled machine (`src/game_rtl.c`, `GameStateSave`/`GameStateLoad`). Keep these
  extensions when integrating shared host changes.
- Interpreter/reference controls exist: `SNESRECOMP_INTERPRET_ALL`,
  `SNESRECOMP_LLE_BOUNCE` and target exclusions in `interp_bridge.c`. Preserve
  them. Dispatch-hit counts are call counts, not instruction coverage or speed.

## Widescreen and presentation

This is genuine wider rendering. `IogPrepareFrame` in `src/main.c:54` expands the
256-column field to 342 centered columns through `display_aspect.h`; with the
default CRT pixel aspect it presents approximately 16:9. The width is fixed,
independent of the drawable size. There is no adaptive 21:9/32:9 implementation.
Pixel aspect, render width, output size and gameplay zoom are separate choices.

`src/iog_widescreen.c` provides:

- Camera/map-width clipping from WRAM `$068A`/`$0692`, with scroll-phase recovery
  from PPU BG1. Beyond authored horizontal bounds, margins stay black.
- Full margins in Mode 7, independent of those room bounds.
- HUD identification from its BG3 ornament, edge anchoring and reset when the HUD
  disappears. Title/file select/inventory keep their authentic BG3 composition.
- Clearing unavailable margins so old pixels do not survive from a prior frame.
- Checked in-memory actor/player OAM-culling operand patches. Unknown operands
  stop patching; 4:3 restores original operands; randomizer disables these patches.

Known limits matter before extending the width:

1. The extra sprite list at `$03:C797` only expands to the right. The source
   explicitly says the left margin needs additional code (`:129`). General actor
   culling improvements do not cover every sprite path.
2. Gaia installs no `WsShadow` terrain-streaming integration. The shared renderer
   has shadow APIs, but that alone does not prove offscreen columns have current
   tiles. Verify scrolling, building edges, scene transitions and map boundaries
   before claiming complete terrain expansion.
3. Actor operand patches target routines currently executed by the interpreter.
   Any future AOT promotion must reproduce their widescreen behavior; changing
   ROM bytes cannot change already compiled immediates.
4. Scene-by-scene camera, dialogue, menus, cutscenes, layer parallax and transition
   composition remain unqualified by this source audit.

Sharp pixels are the default enabled graphics mod. xBR smoothing, shader support,
HD packs and Mode 7 enhancements exist; those are implemented capabilities, not
visual qualification for every scene or any third-party replacement art.

## Existing usability, audio and progression

Keep the implemented systems rather than replacing them blindly:

| System | Inherited implementation and integration constraint |
|---|---|
| Controls/settings | Shared desktop host owns input/remapping and the in-game settings overlay. `src/iog_settings.c` persists title options through the mod runtime so the next launcher session agrees. Validate remaps and displayed chords on real pads. |
| Companion screen | Items, Status, Saves and Config pages; pad/touch navigation; Dual and rotated Flip Grip layouts (`src/iog_companion.c`). It is not a scenery map or story journal. |
| Running | Optional frame callback invokes the game's dash by setting its motion state, gated on player/movement locks (`src/iog_mods.c:56`). Preserve form/puzzle restrictions; no speed multiplier is justified by this audit. |
| Item switching | Optional modifier plus L/R rotates equipped inventory entries and queues the game's confirm sound (`src/iog_mods.c:96`). |
| Stacking | Red Jewels, Herbs and Crystals use per-save spare bytes `$0B55-$0B57`; overlay digits come from the loaded game (`src/iog_inventory.c`). Retain save compatibility and test equipped-item consumption. |
| New Game+ | Marks completed saves, resets story/dungeon/inventory state while retaining progression and changing damage; blocks RetroAchievements when starting NG+ (`src/iog_ngplus.c`). It is an explicit optional balance mode. |
| Completion | Existing percentage combines reward-room flags, held/delivered jewels and NG+ completion state (`src/iog_ngplus.c:92`). This aggregate is not reliable standalone story-completion evidence for achievements. |
| Audio | `src/iog_msu.c` swaps only songs with usable pack tracks. Missing tracks retain original S-SMP music. Script-waited one-shots deliberately remain original to preserve completion signals. Preserve this offline fallback and test partial/missing packs. |
| RetroAchievements | Shared host/rcheevos integration exists; cheats, NG+ and randomizer have explicit blocking paths. Local CompanionAchievements is a separate pending integration, not a renamed RA service. |

### Game-specific QoL research

[GaiaLabs](https://github.com/Azarem/GaiaLabs) supplies established analysis,
symbols, map structures and reference patches for dash, stacking, item switching,
music and NG+. Its current toolkit is GPL-3.0; use its factual research with
attribution and review licensing before copying implementation code. Existing
Babel source identifies GaiaLabs references inline.

[IoGR's mechanics documentation](https://github.com/DontBaguMe/IoGR/blob/master/README.md)
distinguishes the original room-clear stat rewards from the randomizer's selected
reward rooms, and documents substantial seed-specific travel, item, ability and
form changes. Seed logic must not become stock-game guidance. Its area-item map
and optional hints demonstrate useful assistance concepts without requiring a
combat or movement rebalance. IoGR is Unlicense; that does not cover game data.

Highest-value next research: identify per-location jewel flags and irreversible
travel boundaries, reward-room state and story flags from GaiaLabs plus matched
runtime observations. Default assistance should show discovered facts; explicit
hints can reveal more. Do not infer a specific jewel's location from a total,
or a journal objective from the current room alone. A scenery map should read
terrain/state without advancing guest simulation.

## Dependencies, attribution and distribution

The inherited baseline used these pins:

| Component | Inherited pin |
|---|---|
| SNESRecomp | `b04d8fa00cbb554f868449bd9038bca90c4d312c` |
| recomp-ui | `e0ae4bc2249f4b219f67486de14c2e15bf0b49ab` |
| recomp-net | `859ba28b93f7374f2ac1eb70d2171594c5cd4f4b` |
| retcomm-rbengine | `a7b98507a62fe00e5aec3b90c52a4134f3c174bc` |

Live GitHub comparison on the audit date found
[SNESRecomp main](https://github.com/RetroPortingToolKit/snesrecomp/commit/66eebe6ae415b4fb2607a22e5b12352f612e1bdf)
454 commits ahead of the pin. Changes span HiROM analysis/code generation,
CPU/interrupt and timing contracts, audio, host services and Mode 7 reconstruction.
The newest commits concern the rebuilt Mode 7 pipeline. The owner's subsequent
instruction requires the latest framework, superseding the initial recommendation
to retain the baseline pin. The current `framework_pins.txt` now records:

| Component | Current integration pin |
|---|---|
| SNESRecomp | `66eebe6ae415b4fb2607a22e5b12352f612e1bdf` |
| recomp-ui | `e0ae4bc2249f4b219f67486de14c2e15bf0b49ab` (Babel adapter retained) |
| recomp-net | `7a4d330ecf995b881d167234da3c0b01675fd512` |
| retcomm-rbengine | `2a03e73693acee0fb78076ea058642c931bef12e` |

### Latest-framework integration, 2026-11-02

The update used a three-way merge against the exact original SNESRecomp pin.
Inventory found 41 modified and 91 added Babel files, plus 28 intentionally
omitted upstream files. Fifty-one overlapping text blocks were reconciled;
upstream CI, triage scripts, screenshots and bulky validation artifacts stay
outside the compact vendor tree. Required nested libraries match the new
framework's own gitlinks; neither nested library had local source changes.

Preserved behavior includes Gaia's nested COP/RTI interrupt-return guard,
forced interpretation for patched code, runtime ROM overlays/replacement,
input filters and persistent title options, the inherited RetroAchievements
source (service disabled in this edition; see its policy note), in-game settings,
companion capture/navigation/layout hooks, HD replacement-art/effects APIs,
asynchronous MSU streaming, logs/safe boot and handheld platform adapters.
The new MSU playback bookmark path was reconciled with asynchronous opening by
restoring tracks synchronously under the reader lock during state restoration.
Partial-pack title fallback has since passed a bounded runtime check;
save-state soundtrack restoration and other transitions still need title coverage.

Generic Babel read-cache and quiescence/coverage optimizations were replaced by
the current upstream CPU bus, idle detector and mapper-aware capture mechanisms.
The old cache bypassed newly required idle/volatile-read bookkeeping. During
focused testing, an inherited optimization also left newly added quiescence
fields uninitialized; restoring upstream's initialization corrected six failed
bridge checks. The failed receipts remain in the private scratch batch.

Current shared Mode 7 reconstruction is available; Babel's older 4x/HD-pack
compatibility path remains separately available and defaults off. The title
settings-row migration to the new `Mode7Enabled` pipeline is tracked separately
with the launcher integration; the inherited `EnhancedMode7` setting only
addresses the legacy path.

Focused ROM-free verification passed: 26 Python tests; 89 interpreter-core
checks; 432 bridge checks with fused reads off and another 432 with them on;
27 interrupt-tail checks; the real CPU plain-ROM bus contract; HD Mode 7
analytic scenes including 512 composition cases; and Mode 7 perspective
reconstruction. Two Python registrations skipped because they hardcode an absent
MinGW path; their C bridge/bus harnesses were compiled and executed directly
with the installed toolchain. This is bounded core/analytic evidence, not a
Gaia campaign or reference-emulator qualification. Product builds and fresh
runtime traces are recorded separately in the handoff.

The final public interpreter-only and private generated-code builds produced
identical CPU/WRAM traces over the same 3,600-frame cold-boot/input route:
SHA-256 `a5573d387c5a744337f72410902330e4d2c2388abf310559feafc763a599bd64`.
Both receipts report 40,511,368 interpreted instructions, 151,374,741 interpreted
CPU cycles, 100% interpreter cycles and 0% AOT cycles on that route. Therefore
this comparison exercises the interpreter in both binaries; it does not qualify
native game execution. Final images show the Mode 7 sea/intro text in 342x224
widescreen and visible output in 256x224 original framing. Dummy audio/video and
unpaced execution do not measure real-device audio, input latency, frame pacing
or campaign correctness. No speedup over an emulator is established.

[ROMAtlas main](https://github.com/weisserw/romatlas/commit/3d0d1393149491777626f5a8e4461f7c49b2d6df)
and release `v0.4.4-alpha` (2026-11-01 UTC) were checked. Its SNES debugger exposes
screen, memory, CPU and input control; disassembly/archive tools distinguish
code/data and retain derived analysis separately from the ROM. Use it for a
specific unresolved routine or state hypothesis after consulting GaiaLabs.
No ROMAtlas dependency or whole-game Rust rewrite is needed for this baseline.

The root PolyForm Noncommercial license requires notices for mr0ta (Babel) and
Matthew Stanley (scaffold/framework). Preserve both, all original README thanks,
the upstream support link and framework third-party notices. `recomp-ui` is MIT;
SNESRecomp retains separate notices for incorporated software in
`snesrecomp/THIRD_PARTY_ATTRIBUTION.md`, with additional library/font/art notices.
License files must accompany distributed binaries; a README credit alone does
not replace them. Game rights remain with their owners.

Inherited `scripts/package_release.sh` excludes loose ROM/save/PCM/IPS files but
does not independently establish that the executable was built interpreter-only,
and stages only the root license. Packaging needs an explicit build-mode guard
and complete applicable notices before a Companion release. Never package local
generated C or a binary containing it under the project's distribution policy.

## Qualification boundary and regression routes

Upstream [v1.0 release notes](https://github.com/mrOt4/babel-recomp/releases/tag/v1.0)
report Linux testing and a Switch hardware campaign, Windows build-only,
3DS/Vita emulator runs and untested Android hardware. Those are upstream reports,
not fresh Companion evidence. Keep source audit, successful compilation, bounded
boot, assisted route coverage, reference parity and natural campaign completion
as separate evidence levels. No new platform qualification is claimed here.

The first reproducible routes should cover:

1. Clean boot, title, new file, school and South Cape using original offline
   audio; log ROM/build/config identity and deterministic input timing.
2. Town scrolling and one indoor/dungeon transition in 4:3 and 16:9; capture both
   terrain margins, player/actors, HUD, dialogue, inventory and scene fade.
3. One room-clear reward, item use/switching, save/reload and return to title;
   exercise settings persistence and keyboard/controller shortcuts.
4. Missing and partial MSU-1 packs, then a scripted melody/one-shot boundary.
5. Optional generated AOT versus forced interpreter with identical ROM, starting
   RAM/save and input; stop at first CPU/RAM/frame/I/O divergence. Keep watchdogs
   around the known boot poll and retain failed receipts.
6. Separately assisted Apocalypse/randomizer boot and mod gating when owner
   inputs are available. These do not qualify stock native coverage.

Measure simulation, render and audio cost plus frame-time distributions before
optimizing. Frame rate alone does not establish input latency or correct pacing.
Store private states, images, audio and traces in one ignored bounded scratch
batch; public receipts should contain reproducible commands, hashes and results.
