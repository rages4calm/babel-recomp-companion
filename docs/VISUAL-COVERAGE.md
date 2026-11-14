# Full-game visual coverage

The owner has expanded the presentation task beyond the eight manual test saves.
Every playable zone and its transitions needs correct widescreen, 1.5× framing,
background scrolling and Mode 1/7 effects. Native-gap work is secondary to this
visual pass. Approved GaiaLabs content integration is a separate content-identity
boundary; a stock renderer receipt does not qualify a modified ROM or new maps.

## Inventory, not a pass percentage

`scripts/inspect_visual_coverage.py` enumerates all 256 scene IDs without reading
a ROM, executing a game or changing renderer eligibility. It reads the actual
source admission, authored-window and secondary-camera predicates. An admitted
scene format can still render incorrectly; the manual-save bugs demonstrated
that directly. There are currently no complete scene/phase approvals in this
inventory. A known unused/default-record alias is not counted as a tested zone.

An optional external GaiaLabs scene index identifies shared default-record
aliases without copying extracted source or assets into this repository. Their
classification is source evidence, not proof that no runtime path can reach them.
Mode 7 is inventoried separately. The uniform-plane sampler has layout/raster
gates. The calibrated perspective path extends rows only when its parameters
match the captured original transforms. Other supported nonuniform rasters can
retain the captured original-height band with padding outside it. These are
separate structural capabilities, not proof of every Mode 7 scene or phase.
The generic widescreen Mode 7 margin path remains separate. Scene modes are not
guessed from IDs.
Likewise, five explicit legacy scene camera models are counted separately from
the new live producer reader for Track, Vertical, Accumulate and Drift behavior;
neither count is a full-game pass figure.
The generic authored-window reader conditionally frames live room bounds; it
does not establish that secondary scenery should stop at the floor boundary.
Per-line HDMA camera derivatives also cannot be inferred from a global actor
ratio. Deferred raster-camera paths remain explicit review work.

The optional manual visual receipt binds the eight historical samples to their
actual build and dependency hashes. A later source edit changes those samples
to historical evidence. Neither current nor historical samples are silently
promoted to a whole-scene approval.

```powershell
python scripts/inspect_visual_coverage.py `
  --scene-index .local/batch-001/native-006/gaia-sources/baserom/extracted/tables/scene_actors.asm `
  --visual-receipt .local/manual-test-slots-025/renderer-fix/COMPLETE-v2.json `
  --output .local/batch-001/visual-fullgame-001/inventory-initial.json
```

Detailed output remains ignored/private. Existing output files are refused;
produce a new receipt when policy changes. Do not commit private indexes,
captures, states, ROM-derived generated code or asset data.

## Bounded entry survey

`scripts/survey_iog_scenes.py` stages isolated copies of a private fixture's
settings/mod metadata and seed. `--plan` records the intended commands without
launching the game or reading a ROM. Execution requires the exact bare Original
USA image and a frozen private executable; it is not a GaiaLabs-ROM runner.

```powershell
python scripts/survey_iog_scenes.py `
  --binary .local/batch-001/visual-fullgame-001/babel-visual-v7.exe `
  --seed .local/manual-test-slots-025/play/saves/save1.sav `
  --fixture .local/manual-test-slots-025/play `
  --rom "Illusion of Gaia (USA).sfc" --scenes 33,2D,2E,39 `
  --incoming-catalog .local/batch-001/visual-fullgame-001/authentic-incoming-camera-repair-v1.json `
  --output .local/batch-001/visual-fullgame-001/entry-plan-example `
  --frames 600 --jobs 2 --plan
```

Remove `--plan` and select a new output directory only after the candidate is
ready. Each run accepts at most 32 explicit unique IDs below `F0`, 400–1000
frames per case and two workers. It requests scene entry through the original
pending request/return-context path, with source-validated destination X/Y,
facing and camera window from an actual Original inbound warp. Execution
refuses missing recipes; a plan without a catalog labels its scripts missing
and cannot execute. Catalogs bind the private source file hash, record line,
source scene and exact incoming tuple. Executed recipes must also match a
literal warp record in the verified Original ROM. This does not establish
story prerequisites or natural progression. It does not set every story flag
or overwrite enemy/reward outcomes. Captured player position, health,
allocation bounds, PPU mode and renderer refusal reasons must be reviewed.

Cases retain failures/timeouts, capped logs, source picture packets and command,
environment and input hashes. Entry checks are distinct from renderer readiness
and visual approval. A loaded room, a nonblack image or an opted-in survey scene
is not a shipping admission or completed visual test. Survey instrumentation
retains the stock identity, layout, object and publication guards.

The first 32-scene survey remains diagnostic evidence: its producer changed
during preparation and its early `settled` snapshots could retain old scene
dimensions. Do not rerun it merely to rewrite that status. Future plans freeze
the producer hash before launching, refuse later launches after a producer edit,
and record any end-of-run producer/input drift. The new delayed probe snapshot
is still not the picture's state: visual classification uses the composition-
paired active RAM exported with the actual source picture. Where that association
is absent (including packet formats without scene RAM), classification is marked
unavailable instead of silently substituting probe metadata. An off-map player
or a story-specific departure phase remains a fixture problem to investigate.

Both initial 32-scene surveys forced an invalid `$2200` camera window through
the last incoming byte. That selects a 512×512 window even for a 256-pixel room.
It can preserve wrapped edge strips or expose separate floors, so those images
cannot establish renderer defects without correcting the fixture. The original
surveys remain diagnostic, with their invalid setup disclosed. Targeted repeats
of `33`, `2D`, `2E` and `39` correct this identified fixture bug; they do not
rewrite the earlier results or qualify other rooms. There is no silent `$2200`
or allocation-window fallback in the current execution tool.

## Work groups

1. Preserve the eight bounded samples: Classroom `08`, South Cape `01`, Aqueduct
   `0E`, Great Wall `85`, Sky Garden `4F`, Viper `55`, Solid Arm `EA`, Pyramid `CC`.
2. Fix immediate exits that fell back in the manual-save build: Aqueduct `0D`,
   Sky Garden hub `4C`, Great Wall adjoining room `83`. A newly added source
   admission is still unqualified until exercised. Check both directions after fades settle;
   a correct source-sized fallback is not completed widescreen support.
3. Review all other admitted formats for their actual secondary-camera producer,
   repeating versus bounded layers, live VRAM animation, raster effects and
   authored camera window. Do not apply one parallax coefficient to every room.
4. Implement remaining scene formats, including cutscenes, Dark Space, flight,
   world map, inventory and Mode 7 compositions. Keep an explicit original-view
   reference until each replacement is visually qualified.
5. Re-run the same acceptance against the selected GaiaLabs content identity,
   including approved expanded maps and their actor, warp and collision changes.

## Acceptance per zone and phase

Use actual 1920×1080, widescreen, 1.5× extent and the player's selected filter;
retain an original-view comparison. Check movement in both axes and directions,
all expanded edges and camera clamps, secondary-plane phase, animated/raster
effects, actor placement and occlusion. Traverse entrances, exits, stairs and
story/ability transitions in both directions. Check menus, cutscenes and relevant
combat/boss phases. Teleports and prerequisite flags may set up fixtures, with
assistance disclosed; they do not establish natural progression.

Record each defect even if structural readiness, native CPU parity or the old
256-pixel field passes. Keep guest-state and foreground/object checks separate
from the intentionally reframed background. Visual review needs actual pictures
and motion evidence, not only screenshot existence, a list of admitted IDs or an
aggregate native coverage figure. Scope failures and untested phases explicitly.
