# Illusion of Gaia Companion — handoff

Updated November 2, 2026. Development version `0.1.0-dev.1`.
Read this first; the completed source audit is [here](docs/BASELINE-AUDIT.md).

## Current source and decisions

- Fork: `rages4calm/babel-recomp-companion`; original Babel author **mr0ta /
  mrOt4**, support link, full credits and licenses preserved. Lagoon, EarthBound
  and shared Companion projects were read-only references.
- Latest SNESRecomp main checked and integrated: `66eebe6ae415b4fb2607a22e5b12352f612e1bdf`.
  A three-way preservation audit retained Babel's game-specific changes;
  `framework_pins.txt` also records the matching nested-library versions.
  The pinned Babel UI has two appended seed-compatibility fields; Gaia uses
  its existing in-game settings overlay, with the new Mode 7 control migrated.
- CompanionLauncher 0.2.0 packages are pinned; the game adapter preserves native
  INI/bindings, rejects stale writes and avoids creating partial first-run configs.
  Mode7Enabled and Off/On/Adaptive VSync reflect the updated engine. Full remapping
  and mod management remain available through Babel tools.
- RetroAchievements service/account support is compiled out, including its
  rcheevos/HTTP backend. Original sources and attribution remain. Official policy,
  the standalone/client distinction and verification are [documented](docs/RETROACHIEVEMENTS.md).
- CompanionAchievements 0.3.0 core/presentation and a guarded observation adapter
  are present, **not yet connected to live unlock/storage/UI/audio**. Follow the
  [integration worklist](docs/ACHIEVEMENTS-INTEGRATION.md); never infer unlocks
  from a loaded save or copy the RA set.

## Verified behavior

| Check | Result and boundary |
|---|---|
| Windows source builds | Interpreter-only and private generated-code builds linked with Clang/Ninja. Final development package is interpreter-only. |
| Stock cold boot/input | 3,600-frame CPU/WRAM traces matched between the two configurations; final interpreter build reproduced hash `a5573d387c5a744337f72410902330e4d2c2388abf310559feafc763a599bd64`. Visible sea/intro text checked; 342x224 and 256x224 framing captured. |
| Native execution | **100% interpreted CPU cycles, 0% AOT cycles** on that route, including the generated-code build. This is not native-game qualification or a campaign. |
| Framework regressions | 26 Python checks; 89 interpreter checks; 432 bridge checks in each of two bus modes; 27 interrupt-tail checks; CPU bus and Mode 7 analytic fixtures. Two hardcoded-toolchain Python skips were covered by directly running their C harnesses. |
| Launcher | 30 synthetic adapter checks, 35 including read-only owner-ROM/launch-plan checks; shared pages and new soundtrack window rendered/reviewed. Actual adapter-to-engine bounded process handoff passed separately. |
| Achievements foundation | 100 synthetic checks through the actual shared core/presentation. No live unlock claim. |
| Music import | 47 importer checks plus 7 native activation checks. The owner's JUD6MENT ZIP imported once, all 28 track hashes verified, original credits DOCX retained and original ZIP hash unchanged. |
| Music runtime | Four paced 900-frame cases: full JUD6MENT pack, absent selected folder, partial synthetic pack missing title track, and original audio. All booted/captured output and delivered samples to SDL's dummy device. Full pack started title track 1; absent/partial selections retained original audio. |
| RomAtlas | Existing verified Lagoon research tool is current in decoder implementation to the inspected latest commit; 18 bounded Gaia structural decodes passed. Structural evidence only. [Method/provenance](docs/ROMATLAS-PLAN.md). |

No physical controller, speaker output, campaign, combat/puzzle route, save-state
music restoration or non-Windows gameplay has been qualified in this batch.
Early failed receipts remain failed: the inherited AOT build differed at frame 1;
an initial bridge merge missed initialization; early harness runs used invalid
button/aspect spellings or accepted black captures; a missing optional-pack path
blocked boot before the fallback fix. Later checks supersede only their stated
scope. Do not turn the 0% AOT comparison into a native-coverage claim.

## Working local artifacts and reproduction

```powershell
./scripts/build_windows.ps1
./companion/build.ps1 -Test
./companion/bin/Release/net8.0-windows/illusion-of-gaia.Companion.exe
python scripts/test_package_release.py
python scripts/package_release.py build windows-x86_64 --companion companion/bin/Release/net8.0-windows
```

The shared launcher package feed is the sibling CompanionLauncher checkout.
The compiled engine is `build/babel-recomp.exe`. The one verified local music
copy is under `build/msu1/companion-packs/`; native selection is enabled in
`build/mods/preloaded/state.toml`. Use **Soundtrack → Use original audio** to
disable it without deleting music. Download opens the credited provider in the
browser; ZIP/folder import is local. [Instructions and musician credits](docs/MSU1.md).

`scripts/check_baseline.py` creates a fresh isolated runtime fixture and validates
CPU/WRAM trace and nonblack PPM evidence. `scripts/check_msu_runtime.py` creates
isolated full/partial/missing/off fixtures that reference the one private pack.
Detailed logs, failed receipts, captures, original upstream release and dependency
preservation records remain in the single ignored `.local/batch-001/` scratch batch.
Automatic approval review blocked deleting its downloaded framework checkout
(`blocked by policy`); it remains isolated there. Do not retry through a bypass.

Packaging checks both CMake mode and a retained binary execution identity,
rejects private/player data, stages source-reviewed mods rather than runtime
preferences, and includes applicable dependency notices. Music, ROMs, generated
game code, tokens, saves and gameplay captures are excluded. No public release
is authorized or published. Tag builds no longer publish automatically.

## Next bounded work

1. Capture an actual in-play stock route and exact PC/M/X/E execution residuals;
   use existing GaiaLabs definitions plus the transferred RomAtlas method to
   promote a small meaningful native batch. Keep deadline guards and interpreter
   fallback. Current optional generation produced 8 exact variants with no AOT
   execution in the measured route; bulk source generation is not the endpoint.
2. Qualify actor visibility, terrain streaming, transitions, dialogue/HUD and
   camera boundaries in existing 16:9 before extending to 21:9/32:9.
3. Wire durable local achievements with verified event hooks and explicit restore/
   rewind/profile generations, then shared browser/toasts/chime and launcher view.
4. Build scenery map, story-flag journal and spoiler-controlled jewel assistance
   from actual game state; preserve Gaia's form-dependent puzzle requirements.
5. Add music transitions/one-shot/save-state coverage and physical device checks;
   qualify release packages/platforms separately before requesting publication.
