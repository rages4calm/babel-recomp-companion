# Widescreen margins and mod controls

Verified November 3, 2026. This follows the reported classroom/South Cape edge
artifacts and problems using enabled mods. It is a presentation and usability
repair, not an expansion of native CPU coverage.

The selected local mixed-native executable is `build/babel-recomp.exe`, SHA-256
`5ed0138bc855c626a2752080d4c1639d74c14e30750d1068afeb38e954dee5b8`.
The generated cohort remains batch 004's manifest
`5322a4e3f86935b45184bad90fb01026338680287f76bf1ed84d011e9aa6af7f`.
Its roots, interpreter guards and default interpreter-only public build are
unchanged. `SNESRECOMP_INTERPRET_ALL=1` retains interpretation in this executable.
Generated game code and binaries remain private.

## Terrain repair

The game streams tilemap strips for its original screen. Widening that ring
buffer alone exposed columns left over from earlier camera positions. The
owner's copied F1 state reproduced the problem: at the same South Cape camera
position after walking left and right, **2,238 of 2,752 static building pixels
in the left margin changed**, while the central roof remained identical.

Gaia retains the decoded map arrangement and tile definitions in WRAM. The
new adapter resolves those live cells into the existing shared `WsShadow`
renderer. It follows the physical BG1/BG2 assignment, each rendered line's
scroll after HDMA/IRQ, map bounds and partial tile phases. This changes host
presentation data, not guest maps, VRAM, registers or gameplay. The original
256 pixels retain native VRAM ownership, including partially visible edge
tiles. Cache registration is rebuilt for every presentation, so an F1 load or
scene change cannot reuse another scene's terrain.

The resolver is based on source-backed GaiaLabs layout research and the
original map-strip routines. It matched all 8,960 native-view cells across
five retained classroom/town snapshots before implementation. No GaiaLabs
implementation or generated game code was copied into the adapter.

The shared partial-native-tile issue overlaps the pending
[SNESRecomp PR #218](https://github.com/RetroPortingToolKit/snesrecomp/pull/218).
The [ROM-free shared-helper witness](../scripts/repro_ws_shadow_partial_tile.c)
reproduces seven failing fine-scroll phases and one passing aligned control
on main `66eebe6`. It intentionally exits 1 on that baseline. The pending PR
has not been adopted or tested here; the adapter preserves native edge tiles
until the shared change is integrated and qualified. No duplicate issue is
needed for work already covered by that PR.

On the final executable, the same static margin has **zero changing pixels**
at the matched camera pair. An independent decode of CPU map entries, tile
graphics, palette and color math matches **2,752/2,752 pixels in both frames**.
The original first frame matched only 514. The repaired margin contains real
nonblack terrain; it is not a black cover or stretched edge.

The classroom has a separate, explicit scene-08 interior policy. Its 512-pixel
map storage did not establish that the extra room strip belonged in the visible
interior. This room now uses authentic-width terrain margins, removing that
strip while preserving its original view. This is an interior fallback, not
newly authored wide classroom geometry. Earlier `4e360ca1…` captures left the
classroom unchanged; they were regression evidence, not a classroom repair.

Exact moving sequences cover walking, the existing hold-to-run feature and the
natural classroom route. Their captured central 256-pixel images and CPU
traces match the earlier executable at the same presentation points. Direct
4:3 classroom/town comparisons retain the entire original image and strict
CPU/device/APU comparisons. Four fresh 16:9 native/interpreter pairs cover an
8x room clear, Freedan projectile, Shadow Aura and Mummy. All their central
snapshots and final central images match the earlier executable; complete
native/interpreter state, cycle-bound audio and full-width output agree.

Unsupported map layouts, allocation failure and special scenes use the
authentic-width terrain fallback. Mode 7 retains its existing plane behavior.
Full-campaign camera/layer effects, every actor-culling path, every puzzle and
larger aspect ratios remain unqualified. The inherited extra-sprite left-edge
limitation has not been replaced by a new actor engine.

## Enabled mods and controls

The owner state and settings were copied before testing. The originals, ROM,
SRAM, controller bindings and soundtrack selection remain byte-identical.

- **Hold to run was disabled in the saved settings.** Its original dash works
  when enabled. The launcher now exposes that existing switch under
  **Convenience**, preserving the selected button. No movement multiplier or
  automatic enabling of unrelated features was added.
- A real run-control bug also allowed a remapped run button to queue a dash
  while inventory or dialogue was open. The callback now respects the verified
  inventory/message contexts. Holding the button in those contexts leaves no
  dash to leak into world movement. Higher-numbered gameplay scenes are not
  excluded by an invented scene range.
- Live-enabling minimum DP or stats now loads the same configured values as
  startup activation. A disabled-at-start feature previously retained stale
  or zero limits when switched on during play.
- **Refill HP** describes the existing effect accurately: it refills positive
  HP between frames, cannot prevent a single lethal hit and does not revive
  death. The old “Infinite HP” label was misleading. Both launcher and in-game
  names now match the implementation.
- Minimum DP really maintains its configured amount. The selected 99 does not
  pay the game's 100-DP continue cost; the launcher help now explains that.
  Minimum stats needs at least one nonzero configured limit. No owner value
  was silently raised or changed.
- Actual room clears award HP 8→16 at 8x and 8→9 in a separate parsed-1x
  control. HP refill, minimum DP and the enabled fast dialogue setting also
  pass private owner-state checks with disabled controls.

The **Cheats** and **Convenience** tabs now have separate 200×48 selection
targets, visible spacing, contrasting active/inactive fills and keyboard focus
indication. Native tab navigation remains. The actual WinForms dialog was
rendered and inspected on both pages at normal and minimum window sizes.
Settings still use the native catalog and atomic merge/conflict checks.

## Music on an immediate F1 load

With the selected local MSU pack, loading F1 on the first simulated frame could
skip the music resynchronization. The old callback sampled its initial state
generation after that load had already happened. Activation now records the
generation before the host can restore a state. Immediate and delayed loads
both start the restored South Cape track, while cold boot retains the original
music-upload protocol. Missing-pack cold boot retains original audio.

This qualifies track restart/selection in the tested cases, not sample-position
restoration, speaker output or the separate canonical SPC/DSP continuation
failure reported in [timing qualification](../contributions/snesrecomp/205/QUALIFICATION.md).

## Checks and retained failures

The actual adapter/shared-shadow fixture covers map layout, layer swaps, all
eight horizontal fine phases, partial native tiles, scene/restore replacement,
bounds, allocation failure, menus, Mode 7 and 4:3. Actual callback fixtures cover
run buttons/locks, live options, rewards and cheat eligibility. The MSU fixture
executes the real activation/upload/frame state machine with synthetic metadata.
The launcher passes 30 adapter, 47 importer, seven activation and 25 native-mod
settings checks. Seven packaging-policy checks pass; no release was created.

```powershell
python scripts/test_iog_widescreen.py
python scripts/test_iog_mods_runtime.py
python scripts/test_iog_msu_runtime.py
./companion/build.ps1 -Test
python scripts/test_package_release.py
```

Provisional `f78da098…` remains distinct from the selected executable. Its three
changed Mummy edge pixels and queued inventory/dialogue dash are retained as
failed semantic checks, even where interpreter/native parity passed. An initial
1x fixture accidentally retained the 8x TOML value; its failed reward result
remains retained. The corrected control verifies its parsed rate before running.
No failed receipt was relabeled. Raw states, captures, screenshots, soundtrack
data, runtime logs and detailed private evidence stay under the ignored scratch
batch and are not published.
