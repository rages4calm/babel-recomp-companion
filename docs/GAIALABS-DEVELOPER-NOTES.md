# GaiaLabs developer references and follow-up

Recorded November 6, 2026 from developer messages relayed by the owner.
This is a research and integration queue, not a record of implemented Companion
features or newly qualified gameplay.

November 8 follow-up: [module/source preflight](GAIALABS-MODULE-INTEGRATION.md)
and [Mesen2 runtime readiness](MESEN2-REFERENCE.md) now have actual private
checks. [Batch 006](NATIVE-BATCH-006.md) records native/framework work separately.
The reference-collection observations below retain their November 6 scope;
the current developer build/profile is still pending the owner's DM.

November 9 fixture calibration: newer baserom assembly uses logical button
masks that differ from the verified stock USA instructions. Its comments are
useful research, but are not a stock input oracle. Distinguish script button
names, configured controller bindings and the game's logical input words;
bind stock tests to actual ROM instructions and observed writes. This is a
source-version difference, not a demonstrated GaiaLabs or SNESRecomp defect.
Successful original ability/chest observations retain their execution evidence;
earlier failed setup attempts and superseded input explanations remain recorded.

## References supplied by the developer

- [Current baserom documentation](https://github.com/Azarem/gaia-iog-baserom/tree/main/docs)
- [Current baserom patches and assets](https://github.com/Azarem/gaia-iog-baserom/tree/main/baserom)
- [Gaia Mapper](https://maps.gaia.studio/) — browser map tool supplied by the developer.
- [Gaia Spriter](https://sprites.gaia.studio/) — browser sprite tool supplied by the developer.
- [Mesen2 MCP](https://github.com/Azarem/mesen2-mcp) — Kassiven supplied this in the follow-up chat.
- [Retranslation rebuild modules, branch `dev`](https://github.com/Azarem/IOGRetranslation/tree/dev/modules) — developer-supplied location for the module structure.

The developer says Babel was written using core-library and patch files more
than a year old. That age claim is developer-reported; it has not been
independently traced to the exact inherited source revisions. Updating
SNESRecomp does not by itself update these game-specific dependencies.

Inspected baserom `main` at
`0dcd500c5142ca4fd8639d6cd41a53442a0b62f6` (commit dated November 1, 2026).
The older GaiaLabs reference used by our native batches was
`Azarem/GaiaLabs@f7649eb735aaf19b2cd8f693fdaa6669b3e42711`.
These are different repositories and identities; keep both with their receipts.
Prior stock-ROM test results do not qualify a newer patched baserom.

## Features the developer wants us to know about

| Feature | Evidence checked here | Follow-up |
|---|---|---|
| In-game options menu | `baserom/options-menu/` exists. `options_menu_core.asm` describes an inventory Options tab with button assignments, registered settings, confirm and cancel. | Compare its input/settings/save behavior with Babel and Companion before adapting it. |
| Key-item auto-use | `baserom/auto-use-items/` contains separate patches for keys, statues and other quest items. A cell-key patch was inspected and reads key-item flags. | Inventory the supported items and verify prerequisites, consumption and story flags against source and execution. |
| Full world-map movement | Follow-up source located in `IOGRetranslation` dev: `modules/walkable-world-map/`. The patch describes free roaming on the Mode 7 map. | Source located; build/runtime/native compatibility remain untested. See module notes below. |
| New minimap | Follow-up source located in `IOGRetranslation` dev: `modules/minimap-v2/`, alongside a separate `dungeon-map` module. | Source located; distinguish the variants and verify the selected module profile. |
| Widescreen rooms for the emulator | Follow-up source located in `IOGRetranslation` dev: `modules/widescreen/`, with map files, camera and sprite patches. Its source explicitly targets bsnes-hd. | Adapt the authored content and renderer contract deliberately; source presence is not native compatibility. |

Source presence is not a build, runtime or compatibility check. No patches were
applied, no new features were exposed, and no game assets were copied locally.

## Gaia Studio browser tools

Both additional URLs returned HTTP 200 on November 6, 2026. Page HTML identifies
them as **Gaia Mapper** and **Gaia Spriter**. The web reader could not open them;
their HTML was inspected through a direct read-only HTTP request instead.

- Mapper's initial page exposes layer selection, a grid, map width/height and
  resize anchoring, shift/wrap controls, undo/redo, tileset/VRAM/palette panels,
  and tile flip/priority/block properties. It is a useful lead for inspecting
  authored rooms and understanding map edits needed by wider rendering.
- Spriter's initial page exposes bundle selection, playback and page controls.
  It is a useful lead for inspecting sprite composition and animation while
  checking actor rendering.

These are observations of the initial HTML controls, not exercised editor
features. Both pages initially contain a loading-payload placeholder. No ROM,
save, asset pack or file was uploaded, no browser editing/export operation was
tested, and no game media was downloaded. Identify the input/output formats,
source revision and applicable licenses before integrating either tool with
the native workflow. A map editor link alone does not locate or qualify the
developer's new widescreen room content.

## Follow-up chat: rebuild pipeline and direct code use

The owner's November 6 screenshot records two further points:

- Kassiven says maps are imported directly during rebuild using raw files from
  the editor. This is developer-reported pipeline behavior; our HTML inspection
  did not test exports or trace the rebuild importer. Prefer locating that
  actual format/import path over inventing a parallel map conversion pipeline.
- ViewtifulSlayer welcomes questions and would prefer a recomp to work directly
  with their code, given the fine-tuning already done, rather than only use it
  as inspiration. Treat faithful integration of current code and patches as
  the preferred direction to investigate. This is a collaboration preference,
  not a replacement for the source licenses or completed compatibility work.

Kassiven linked `Azarem/mesen2-mcp`. Inspected `master` at
`0c7d9d76ef5680521538378853d2516447e30a8f`; `mcp-version.txt` is `0.6.0`.
Its migration guide describes an in-process C# MCP host using stdio, and the
tool contract documents ROM identity, input, breakpoints, CPU/memory inspection,
bounded stepping, scripts and ROM-bound save states. These could support
matched original-versus-native tests and investigation of the first divergence.
Recompilation still needs its own integration and execution checks.

At the November 6 inspection, no Mesen tools were exposed in the chat inventory. That turn
only inspected repository documentation: nothing was installed, registered,
started or tested locally. Review the runtime/tool contract before relying on
it; do not claim an active bridge or confuse it with the map/sprite editors.

## Retranslation rebuild module structure

The next developer link resolves the previously missing module locations:
[`Azarem/IOGRetranslation`, branch `dev`, `modules/`](https://github.com/Azarem/IOGRetranslation/tree/dev/modules).
Inspected revision `754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc`
(commit dated October 28, 2026). Keep this identity separate from the baserom
repository and any currently published retranslation package.

- `scripts/index.ts` delegates extraction/rebuild to `@gaialabs/iog-baserom`,
  with an ordered array of module directory paths passed to `rebuildInternal`.
  The inspected `package.json` declares `@gaialabs/core` 1.0.5 and
  `@gaialabs/iog-baserom` 0.2.7. These declarations alone do not establish the
  installed package hashes or their correspondence to baserom `main`.
- `modules/manifest.json` describes grouped player-facing choices, defaults,
  descriptions and module names. It also carries English retranslation credits
  to LThammy and ViewtifulSlayer, and Portuguese credits to Igor Chagas.
  A null module value is not evidence that a feature is absent: some listed
  features belong to the base content.
- The inspected rebuild selection includes `base`, `dungeon-map`,
  `walkable-world-map`, `debug-menu` and other modules. The `minimap-v2` and
  `widescreen` entries are commented out. Do not describe every directory as
  active in the default script or equate the manifest with actual selection.
- `modules/minimap-v2/MinimapV2.patch.asm` replaces `GlobalInputHandler` and
  includes the minimap core. Its source describes viewport scrolling, actor
  markers, blinking and border animation. `dungeon-map` is a separate module
  with its own VRAM-layout document; inspect their compatibility before mixing.
- `modules/walkable-world-map/WalkableWorldMap.patch.asm` replaces
  `WorldMapController` and arrival/travel setup for free-roaming Mode 7 movement.
  Its directory includes a core, collision data and an asset generator.
- `modules/widescreen/Widescreen.patch.asm` explicitly targets **bsnes-hd**
  384x224 output at 1:1 pixel aspect, 64 additional pixels per side, and a
  matching `.bso` configuration. It changes camera bounds, tilemap management
  and sprite behavior; `WidescreenBG3.patch.asm` is also present. The source
  credits VitorVilela7/wide-snes as its approach. Preserve that credit too.
- The widescreen tree contains raw `.map` files for `sc01`, `sc08`, `ec0A`,
  `ec0D`, `ec0F`, `ir29` and `mu_vampires`, including several effect layers,
  plus `scene_actors.asm` and `scene_warps.asm`. `sc08` is particularly relevant
  to our classroom terrain fallback. Do not claim all game rooms are widened.

This is a source inspection only: no build script, asset generator, patch or
ROM was executed and no assets were imported. Babel's current 342-column
widescreen presentation and pixel-aspect policy differ from the module's
384-column contract. Reconcile that before treating these maps/patches as
drop-in fixes. Record selected modules, order, package identities and resulting
ROM identity for future native generation and matched reference tests.

## Documentation useful for native conversion

The current docs index points to per-bank engine and actor documentation,
the canonical `docs/cop/` family references, WRAM and actor structures,
and Mesen2 runtime findings. The monolithic
`docs/cop-commands-reference.md` explicitly marks itself archived; use the
family references for current work.

The docs describe metadata inputs under `us/blocks.json`, `us/overrides.json`
and `db-us/names/`. Compare these with our older GaiaLib JSON inputs rather
than treating their formats or boundaries as interchangeable.

`docs/mesen2-d-series-summary.md` contains runtime-tested corrections to
music identifiers, queue/port handling, fade and stop behavior. In particular,
it cautions against treating WRAM `$06F2` as simply the currently playing song.
These findings are leads for an audit, not proof of a bug in our current code.

Also located `baserom/patches/MusicTransitions.patch.asm` and
`baserom/patches/APUWaitFixes.patch.asm`; their source includes scene/music
mapping and SPC/MSU synchronization paths. They have not been integrated or
tested in Companion. The owner's clubhouse music report remains deferred;
this reference collection does not diagnose or fix it.

## Next integration work

### Developer build offer and resume checkpoint

The final November 6 developer message offers a dev build with new content by
DM and says the generator is behind. The owner plans to resume in two days
(November 8) and asks us to say when they should DM him for it. Keep this as a
resume checkpoint, not an automatic outreach or scheduled reminder.

Before selecting or testing current new content, determine whether the
inspected public branches/packages reproduce the intended build. If they do
not, or its identity cannot be established, ask the owner to request the dev
build and the matching source revision, dependency versions and selected
modules/build configuration. Prefer a patch or build instructions usable with
the owner's ROM. Keep received game-derived files private. Do not infer
current dev-build contents from the lagging generator or older public files.
No message has been sent and no build has been received through this offer.

### Integration queue

November 8 follow-up: Kassiven asked whether the request is specifically for
widescreen or other features, and warned that the in-development work could
take a month to clean up. The useful request is an available rough snapshot,
with its actual build recipe and known issues, rather than a polished release.
The integration interests also include the current retranslation, options,
key-item auto-use, world-map movement and minimap. None is assumed enabled
until the supplied build/module selection identifies it. Original Gaia and
GaiaLabs remain separate editions; see [their identity contract](GAME-EDITIONS.md).
No new build has been received, and the agent has sent no DM.

1. Read the current core/build configuration and map the inherited Babel
   patches against this pinned baserom revision. Preserve existing deltas.
2. Use the newer game documentation to review native entry boundaries,
   COP control flow, actor state, map loading and audio assumptions alongside
   RomAtlas checks and matched execution.
3. Establish the exact retranslation/baserom profile to support. Adapt code
   changes and data deliberately; arbitrary patched ROM compatibility is not
   established by a stock-ROM native build.
4. Use the located retranslation modules to trace raw-map rebuild import,
   select the intended minimap/world-map/widescreen profile and reconcile its
   renderer contract. Authored content and renderer support remain separate.
5. Preserve mr0ta / mrOt4, GaiaLabs, the retranslation authors and all existing
   upstream credits. The inspected baserom repository carries GPLv3; review
   applicable terms before importing implementation into the existing fork.

Keep interpreter/reference paths and owner saves/settings intact. This note
does not reopen paused game fixes or authorize a release.
