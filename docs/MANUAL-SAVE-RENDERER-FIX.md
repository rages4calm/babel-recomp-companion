# Manual-save background correction — November 13, 2026

Owner playtesting exposed incorrect expanded scenery in the eight manual test
saves, despite earlier native-viewport and CPU comparisons passing. Tracked in
[issue 5](https://github.com/rages4calm/babel-recomp-companion/issues/5).
These are Mode 1 background problems, not an established Mode 7 or SNESRecomp bug.

## Changes and scope

Only the five affected Original-USA scene models are changed:

| Test slot | Scene | Secondary scenery |
| --- | --- | --- |
| F4, Great Wall | `85` | Repeating scenery; fixed horizontal phase, 1:1 vertical camera |
| F5, Sky Garden | `4F` | Repeating scenery; quarter-rate camera on both axes |
| F6, Viper | `55` | Independent sky; retain actual raster scroll and repeat its map |
| F7, Solid Arm | `EA` | Camera-following drift; retain the uploaded, animated VRAM ring in position-bypass mode |
| F8, Pyramid | `CC` | Fixed secondary plate with repeating coverage |

The host view now projects each secondary plane at its own camera rate. A
clamped enlarged camera no longer drags a background at the foreground rate.
Sample normalization fills the small background allocations beyond the old
viewport; it does not wrap foreground terrain or change guest camera arithmetic.
Uploaded cells and decoded cells now use the same projected source row, fixing
the additional Viper cloud seam at the original 256-pixel boundary.

The Original camera, collision, CPU/native contexts, guest RAM, foreground bounds,
classroom layout, object placement, music settings and saved game data are not
changed. Other scenes retain their prior rendering policy. This does not qualify
all rooms, all boss phases, GaiaLabs content or a complete playthrough.

The camera models were checked against GaiaLabs' extracted `camera_scroll.asm`,
`camera_tilemap.asm`, `layer1_scroll_actors.asm`, `system_core.asm`, scene actor
lists and scene clearing. Their coefficients come from the original camera
producers, not the ratio of map allocation sizes. Live per-line scroll, palettes
and effects remain inputs to the picture.

## Validation

Private build `713f96f3071ce481361e4ab3ec6bc1e9092d64a0f14b6973504df6e0e7631cf4`
reuses the qualified native025 generated inputs and existing build tree. Only
`src/iog_world_renderer.c` changes among its compiled production sources; no
generation, interpreter promotion, vendor update or performance benchmark ran.

- 48 paired save replays: each of F1–F8 at rest, moving in four directions, and
  opening the menu or attacking. Final candidate captures are fresh; their
  unchanged baseline captures are reused from the first diagnostic pass.
- Eight additional paired runs cover settled transitions, a player-position
  assisted Viper arena attack, Solid Arm attacks and Aura use. No enemy stats or
  outcome flags are written. Adjacent unsupported scenes use the original view;
  this is not a qualification of those areas' expanded scenery or boss victories.
- All 56 pairs match the sampled WRAM, SRAM, VRAM, CGRAM, OAM, PPU registers and
  original-field framebuffer. All 10,080 paired frame boundaries match guest CPU
  registers, guest/master cycles and HDMA/IRQ service counts. This is bounded
  comparison, not instruction-stream or campaign proof.
- Eight actual NVIDIA OpenGL captures at 1920×1080, smooth/xBR filtering and
  1.5× extent were visually inspected, together with movement and settled-scene
  sheets. Structural readiness alone was not accepted as visual approval.
- ROM-free actual-module tests pass 4,008,421 assertions, with scene/OBJ/pixel
  stubs disclosed by the harness. Removing repetition or restoring the wrong
  source-row calculation causes the respective targeted regression to fail.
  Existing late-IPS identity checks remain passing.

Corrected background projection intentionally changes the expanded picture,
including background pixels within the old viewport's host placement. It is not
claimed to be byte-identical to the old expanded image. Guest scanout and the
foreground/object geometry are separate checks.

The intermediate first fix retained a cloud seam; its results are historical,
not the selected build. Local receipts and captures remain private under
`.local/manual-test-slots-025/renderer-fix/`. No game images, states, ROM-derived
inputs or generated executable are published.

## Local testing

`.local/manual-test-slots-025/Play Test Saves.cmd` now selects the corrected
executable. F1–F8, the eight states, infinite health, boosted stats and MSU-1
selection are unchanged. `Play Original View.cmd` selects the original-view
renderer; `Play Previous Build.cmd` retains the prior native025 candidate.
The owner installation and qualified batch025 folder remain intact.

Future native area work must visually check the whole output at player settings:
movement, expanded edges, parallax, transitions, menus and relevant fights.
The durable requirement is in `AGENTS.md`; CPU or central-field parity alone is
not visual approval.
