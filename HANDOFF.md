# Illusion of Gaia Companion — handoff

Updated November 3, 2026. Development version `0.1.0-dev.1`.
Read this first; the completed source audit is [here](docs/BASELINE-AUDIT.md).

Current local build: [widescreen/mod batch 005](docs/WIDESCREEN-MODS-005.md),
SHA-256 `5ed0138bc855c626a2752080d4c1639d74c14e30750d1068afeb38e954dee5b8`.
South Cape margins now use live decoded map data; the classroom uses an explicit
authentic-width terrain fallback. The run option was disabled in the owner's
settings and is now exposed under Convenience. Inventory/dialogue dash leakage,
live cheat option loading and immediate-load MSU track startup are corrected.
Owner saves/settings/bindings/music were not changed. Earlier 16:9 tier parity
did not establish correct offscreen content; retain that distinction.

The maintainer requested three focused timing PRs. Their reviewable source
patches and current qualification limits are in
[contributions/snesrecomp/205](contributions/snesrecomp/205/README.md).
They were [delivered upstream](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6614160563)
with 640 passing source tests, two existing skips and 56 matched cost runs.
The prerequisite fixes merged during batch-005 verification: upstream main is
now `f6912cd74e06eb21329aeb5c929d7f374479db80`. Their preservation inventory,
integration and timing-series rebase are the next checked step; the verified
5ed0138 checkpoint below still uses main66 plus preserved local changes.
Do not duplicate the merged repairs or present the old preparation base as the
requested merged base. Extracted-stack source
checks pass, but fresh ordinary current-build save/load revealed a canonical
audio-continuation difference shared by both tiers. The strict failed check is
recorded in the [consumer report](contributions/snesrecomp/205/QUALIFICATION.md).
The game/vendor source and selected executable remain unchanged by this
upstream contribution preparation. No new public repository or release exists.

Batch 004 established a **route-qualified private mixed-native baseline**, with a fixed
combat input/vblank ownership bug and **61 matched cases / 122 fresh runs**.
The natural
6,000-frame classroom-to-South-Cape route matches retained interpretation in
4:3 and 16:9. Native CPU-cycle shares are **12.8307% / 12.8268%** respectively;
this is partial native execution, not a fully native game or campaign proof.
[Current evidence, failures and reproduction](docs/NATIVE-BATCH-004.md).
The corrected input model changes the workload; earlier percentages are not
direct performance baselines. Actual assisted kills/rewards at 1x/8x, seven
ability effects with nine controls, four boss defeats and four 16:9 stress
cases now pass. Boosted boss stats do not qualify normal weakness timing.
Also verified: 23 assisted area visits across all four guide parts, two inventory
open/return cases, and original Freedan/Shadow transformation roundtrips.
The teleport prerequisite was an undismissed scene-title input loop. Source
request context and real Dark Space prerequisites are now recorded; assistance
does not count as earned story progression.

Tested batch-004 source is published at
[`1ea3ab4`](https://github.com/rages4calm/babel-recomp-companion/commit/1ea3ab4a46af8a5d39f8ab991990c88b36fd31d5).
The combat input/vblank ownership bug is reported as
[upstream #242](https://github.com/RetroPortingToolKit/snesrecomp/issues/242),
with the ROM-free actual-core reproducer. Earlier batch-003 source is published
at `bf826a377ff608fd4c524ba0e67b315c9c4fe4ee`.
Default v2 indirect bank-carry mismatch is reported as
[upstream #240](https://github.com/RetroPortingToolKit/snesrecomp/issues/240),
with a ROM-free reproducer; this is separate from the tested opt-in pointer
recipe. Current timing results extend the existing
[#205 discussion](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6589796017).
No release was created.

## Current source and decisions

- Fork: `rages4calm/babel-recomp-companion`; original Babel author **mr0ta /
  mrOt4**, support link, full credits and licenses preserved. Lagoon, EarthBound
  and shared Companion projects were read-only references.
- Latest SNESRecomp main checked and integrated: `66eebe6ae415b4fb2607a22e5b12352f612e1bdf`.
  A three-way preservation audit retained Babel's game-specific changes;
  `framework_pins.txt` also records the matching nested-library versions.
  Newly opened upstream [PR #241](https://github.com/RetroPortingToolKit/snesrecomp/pull/241)
  changes APU/DSP/DMA timing but is unmerged and was not adopted in this batch;
  integration needs a delta inventory and fresh qualification after review.
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
- Dedicated launcher **Cheats and Mods** shares native settings with the in-game
  menu. Source-guarded room-clear rewards support 1x–8x; no movement multipliers.
  Cheat eligibility is sticky for the process session, ready for future live
  achievements. [Controls](docs/CHEATS-AND-MODS.md), [engine guards](docs/CHEAT-RATES.md).
- New transparent game/launcher icons are embedded at nine Windows sizes.
  [Artwork, provenance and converter](res/branding/README.md). Computer-control
  runtime was released after visual checks; previews are closed.

## Verified behavior

| Check | Result and boundary |
|---|---|
| Windows source builds | Interpreter-only and private generated-code builds linked with Clang/Ninja. Final development package is interpreter-only. |
| Stock cold boot/input | 3,600-frame CPU/WRAM traces matched between the two configurations; final interpreter build reproduced hash `a5573d387c5a744337f72410902330e4d2c2388abf310559feafc763a599bd64`. Visible sea/intro text checked; 342x224 and 256x224 framing captured. |
| Native execution | Batch 004: 312 roots, 1,180 variants / 1,104 eligible candidates; all earlier roots/eligible variants retained. Actual corrected-route native share **12.8307% in 4:3, 12.8268% in 16:9**. A source-verified separate math leaf was removed from the polling range; 6,224 explicit PC/alias guards and inherited function exclusions remain. Counts are not executed/qualified-function coverage. |
| Natural gameplay comparison | 6,000 frames from cold boot through classroom dialogue, directional movement and the South Cape transition. Exact CPU/WRAM trace, CPU/master totals, 13 memory/PPU/APU/DSP/PCM-ring/port-scheduler snapshots, DMA/PPU journals, and full final output including widescreen margins. CPU audio-event stamps match; batched SPC beam tags are explicitly separated from matching event/sample/state evidence. |
| Framework regressions | Current 694 Python tests passed, 2 existing skips, 243 subtests; actual RDNMI core/IRQ/snapshot tests and parser/ticker/replay checks pass. Current 432 bridge checks in each bus mode, CPU bus/latch and 27 interrupt-tail checks pass. Earlier 864 executed pointer cases and 12 Rust tests retain their original scope. |
| Assisted areas/mechanics | 23 area entries, inventory and corrected form roundtrips; six actual room-clear reward cases, two no-repeat reloads, seven original ability effects plus nine controls, and four continuous boss fights pass on one final binary. Fresh Castoth/Viper HP-zero writes are required. Four additional full-width 16:9 stress cases pass. Exact SPC cycles, full audio/PCM/queue state and output match. Explicit stats/positions/learned bits/item assistance; no earned story or normal boss difficulty claim. |
| Launcher/mods/icons | 30 adapter +47 importer +7 activation +21 native-mod tests. Room-reward helpers/source: 136 assertions; actual callbacks with host stubs: 656 assertions. Final-engine assisted 8x/native versus 8x/interpreter comparison passed; separate 1x control passed 8 reward-effect assertions. Native launcher UI/draft/Revert and its title-bar icon reviewed. Both rebuilt PE icon groups match all nine source ICO frames. |
| Achievements foundation | 100 synthetic checks through the actual shared core/presentation. No live unlock claim. |
| Music import | 47 importer checks plus 7 native activation checks. The owner's JUD6MENT ZIP imported once, all 28 track hashes verified, original credits DOCX retained and original ZIP hash unchanged. |
| Music runtime | Four paced 900-frame cases: full JUD6MENT pack, absent selected folder, partial synthetic pack missing title track, and original audio. All booted/captured output and delivered samples to SDL's dummy device. Full pack started title track 1; absent/partial selections retained original audio. |
| RomAtlas | Current 8,192 mechanic/route contexts passed: 3,122 new decodes, 5,070 identity/byte-matched reused checks, zero mismatches. All 248 cartridge transfer targets checked; three WRAM targets remain unverified/interpreted. Separate 72-context math-leaf audit. Structural evidence only. [Method/provenance](docs/ROMATLAS-PLAN.md). |

No physical controller, speaker output, campaign, natural combat reward,
save-state music restoration or non-Windows gameplay has been qualified here.
Assisted/teleported/flag-edited checks have separate receipts and do not extend
the natural route's cold-play scope.
[Assisted testing](docs/ASSISTED-TESTING.md) records every injected field, the
checkpoint dependency and failed probes. Current assisted proof covers
actual assisted combat/rewards, seven ability effects, four bosses, 23 area
entries, inventory and form roundtrips. It does not establish earned campaign
progression, unboosted boss timing, every puzzle or original healing timing.
Early failed receipts remain failed: the inherited AOT build differed at frame 1;
an initial bridge merge missed initialization; early harness runs used invalid
button/aspect spellings or accepted black captures; a missing optional-pack path
blocked boot before the fallback fix. Later checks supersede only their stated
scope. Batch 002's failed aggregate, instruction-only, first pacing and
pre-credit/pre-PB candidates remain failed; see its detailed note.

## Working local artifacts and reproduction

```powershell
./scripts/build_windows.ps1
./companion/build.ps1 -Test
./companion/bin/Release/net8.0-windows/illusion-of-gaia.Companion.exe
python scripts/test_package_release.py
python scripts/package_release.py build windows-x86_64 --companion companion/bin/Release/net8.0-windows
```

The shared launcher package feed is the sibling CompanionLauncher checkout.
The compiled engine is `build/babel-recomp.exe`, currently the selected private
mixed-native build (SHA-256
`5ed0138bc855c626a2752080d4c1639d74c14e30750d1068afeb38e954dee5b8`).
Its unchanged graph/source lives only under `.local/batch-001/native-004/expanded-v2/`;
`inputs/` there retains the earlier immutable `fa3a2502…` baseline. The current
frozen executable is `.local/batch-001/wide-005/build/selected/babel-recomp.exe`.
Fresh visual/control/music evidence is under `wide-005/`. The older proof index is
`native-004/selected-proof-index.json`; replay plans/reports are under `replay/`.
`./scripts/build_windows.ps1` still builds an interpreter-only package candidate;
use `-NativeBatch .local/batch-001/native-004/expanded-v2 -Jobs 2` to restore
this private native build. Set `SNESRECOMP_INTERPRET_ALL=1` for retained fallback
in the same mixed executable; clear that environment variable for native play.
The one verified local music
copy is under `build/msu1/companion-packs/`; native selection is enabled in
`build/mods/preloaded/state.toml`. Use **Soundtrack → Use original audio** to
disable it without deleting music. Download opens the credited provider in the
browser; ZIP/folder import is local. [Instructions and musician credits](docs/MSU1.md).

`scripts/check_baseline.py` creates a fresh isolated runtime fixture and validates
CPU/WRAM trace and nonblack PPM evidence. `scripts/check_msu_runtime.py` creates
isolated full/partial/missing/off fixtures that reference the one private pack.
Detailed logs, failed receipts, captures, original upstream release and dependency
preservation records remain in the single ignored `.local/batch-001/` scratch batch.
Completed batch-003 v2/v3 raw run blobs are compacted in
`native-003/failed-expanded-v2-v3-raw.zip`, with a per-file verified SHA-256 index
in `failed-expanded-v2-v3-archive.json` there. Their failed receipts, manifests,
journals and seeds remain in place. Selected v4 evidence remains unpacked.
Batch 004 consolidates 1,586 duplicate runtime input files (about 2.1 GB) into
the immutable `native-004/expanded-v2/inputs/` copy, with per-file hashes in
`native-004/duplicate-runtime-inputs-compaction.json`. All 122 run receipts,
traces, snapshots, outputs, captures, settings and seeds remain in place.
Automatic approval review blocked deleting its downloaded framework checkout
(`blocked by policy`); it remains isolated there. Do not retry through a bypass.

Packaging checks both CMake mode and a retained binary execution identity,
rejects private/player data, stages source-reviewed mods rather than runtime
preferences, and includes applicable dependency notices. Music, ROMs, generated
game code, tokens, saves and gameplay captures are excluded. No public release
is authorized or published. Tag builds no longer publish automatically.

## Next bounded work

1. Extend the qualified cohort from the current natural route and the 23
   source-backed area/form contexts, using
   [guide milestones](docs/GUIDE-RESEARCH.md) and explicitly recorded assisted
   teleports/flags/cheats. Attack/remap, assisted kills/rewards, all seven ability
   effects and four boosted boss completions are verified. Next pursue earned
   abilities/story, unboosted boss phases, broader form-dependent puzzles and
   missing transfer boundaries. Preserve the four inherited NMI-callee CFG
   exclusions until their original mode/DMA issue has its own verified repair.
2. Expand 16:9 actor/terrain/camera/dialogue coverage beyond the qualified
   classroom/South Cape route before extending to 21:9/32:9. Existing raw SPC
   beam-tag differences are diagnostic batching metadata; preserve the strict
   failed receipts and require raw-bound event-time SPC cycles plus matching
   APU state/PCM/queue in `--apu-clock cycles` mode. Batch 003 v2/v3 remain failed;
   v4 corrects extended absolute scheduling markers and boundary flushing.
3. Wire durable local achievements with verified event hooks and explicit restore/
   rewind/profile generations, then shared browser/toasts/chime and launcher view.
4. Build scenery map, story-flag journal and spoiler-controlled jewel assistance
   from actual game state; preserve Gaia's form-dependent puzzle requirements.
5. Add music transitions/one-shot/save-state coverage and physical device checks;
   qualify release packages/platforms separately before requesting publication.
