# Illusion of Gaia Companion — handoff

Updated November 2, 2026. Development version `0.1.0-dev.1`.
Read this first; the completed source audit is [here](docs/BASELINE-AUDIT.md).

Batch 003 now has a **route-qualified private mixed-native build**. The natural
6,000-frame classroom-to-South-Cape route matches retained interpretation in
4:3 and 16:9. Native CPU-cycle shares are **13.4210% / 14.0185%** respectively;
this is partial native execution, not a fully native game or campaign proof.
[Current evidence, failures and reproduction](docs/NATIVE-BATCH-003.md).
Also verified: 23 assisted area visits across all four guide parts, two inventory
open/return cases, and original Freedan/Shadow transformation roundtrips.
The teleport prerequisite was an undismissed scene-title input loop. Source
request context and real Dark Space prerequisites are now recorded; assistance
does not count as earned story progression.

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
| Native execution | Batch 003: 231 profile roots, 952 variants / 877 eligible candidates; actual natural-route native share **13.4210% in 4:3, 14.0185% in 16:9**. All 6,460 explicit PC/alias guards retained. Candidate counts are not executed/qualified-function counts. Batch 002 was 6.2645% / 6.3244%; earlier baseline 0% AOT. |
| Natural gameplay comparison | 6,000 frames from cold boot through classroom dialogue, directional movement and the South Cape transition. Exact CPU/WRAM trace, CPU/master totals, 13 memory/PPU/APU/DSP/PCM-ring/port-scheduler snapshots, DMA/PPU journals, and full final output including widescreen margins. CPU audio-event stamps match; batched SPC beam tags are explicitly separated from matching event/sample/state evidence. |
| Framework regressions | Current 665 Python tests passed, 2 existing skips, 163 subtests; 864 executed pointer cases against actual interpreter. Current 432 bridge checks in each bus mode, CPU bus/latch and 27 interrupt-tail checks pass. Earlier 12 Rust analyzer tests and 89 interpreter/bus/Mode 7 checks remain scoped to their receipts. |
| Assisted areas/mechanics | 23 visits at 600 frames each, two inventory cases, two 2,000-frame transformations, and two continuous 3,000-frame form roundtrips pass matched native/interpreter checks. Freedan returns to Ankor and Shadow to Pyramid retaining the form. Actual event-time SPC cycles, complete audio state/PCM/queue and full output match. Explicit HP, spatial positioning and Shadow unlock assistance; no attack/hit/kill/earned-ability claim. |
| Launcher/mods/icons | 30 adapter +47 importer +7 activation +21 native-mod tests. Room-reward helpers/source: 136 assertions; actual callbacks with host stubs: 656 assertions. Final-engine assisted 8x/native versus 8x/interpreter comparison passed; separate 1x control passed 8 reward-effect assertions. Native launcher UI/draft/Revert and its title-bar icon reviewed. Both rebuilt PE icon groups match all nine source ICO frames. |
| Achievements foundation | 100 synthetic checks through the actual shared core/presentation. No live unlock claim. |
| Music import | 47 importer checks plus 7 native activation checks. The owner's JUD6MENT ZIP imported once, all 28 track hashes verified, original credits DOCX retained and original ZIP hash unchanged. |
| Music runtime | Four paced 900-frame cases: full JUD6MENT pack, absent selected folder, partial synthetic pack missing title track, and original audio. All booted/captured output and delivered samples to SDL's dummy device. Full pack started title track 1; absent/partial selections retained original audio. |
| RomAtlas | Current 8,192 area boundaries passed with zero mismatches: 4,888 new decodes and 3,304 identity/byte-matched reused checks; 151/154 transfer targets checked, three changing WRAM targets remain unverified/interpreted. Structural evidence only. [Method/provenance](docs/ROMATLAS-PLAN.md). |

No physical controller, speaker output, campaign, natural combat reward,
save-state music restoration or non-Windows gameplay has been qualified here.
Assisted/teleported/flag-edited checks have separate receipts and do not extend
the natural route's cold-play scope.
[Assisted testing](docs/ASSISTED-TESTING.md) records every injected field, the
checkpoint dependency and failed probes. Current assisted proof covers
reward-backend wiring, 23 area entries, inventory, and form roundtrips;
it does not establish campaign progression or natural combat/rewards.
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
`6e3abd83b0fa57ec3708ab893e5e60a502d0fcd3c42ea988b47cc804c405fc7a`).
Its graph/source lives only under `.local/batch-001/native-003/expanded-v3/`;
`expanded-v4/` contains the final immutable runtime copy and receipts.
`./scripts/build_windows.ps1` still builds an interpreter-only package candidate;
use `-NativeBatch .local/batch-001/native-003/expanded-v3 -Jobs 2` to restore
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
   teleports/flags/cheats. First resolve the ambiguous repeated controller-remap
   attack stimulus, then verify real hits/kills/rewards, earned abilities,
   form-dependent puzzles, bosses and missing transfer boundaries.
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
