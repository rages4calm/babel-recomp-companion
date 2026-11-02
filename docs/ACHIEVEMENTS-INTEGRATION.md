# CompanionAchievements foundation

This batch adds a **tested observation foundation, not enabled gameplay
achievement tracking**. Babel's RetroAchievements integration remains intact.
No current game frame calls this observer, no achievement profile is written,
and no browser, toast or sound has been wired into Gaia yet.

The unchanged MIT-licensed shared core and presentation module are pinned from
[CompanionAchievements](https://github.com/rages4calm/companion-achievements)
commit `6617dc00e4af43035b08fdb6ef0e4fbd67246514` (toolkit 0.3.0, core 0.1.0).
`src/companion_achievements/toolkit/provenance.json` records exact hashes; the
original copyright and license are included. No existing EarthBound or Lagoon
code, profiles or assets were modified or copied. The game's original upstream
credits continue to apply.

## Implemented boundary

`observer.c` takes const RAM/ROM snapshots and a caller-owned generation. It
emits bounded, allocation-free milestone facts through a callback, allowing a
later host adapter to enqueue work without disk I/O in the game frame. It never
changes game state, calls a clock or infers CPU/native coverage. A failed enqueue
latches tracking failure until initialization; hosts must expose that status.

The original six-entry draft catalog covers room-clear rewards, Red Jewel
milestones and the ending. It uses the shared launcher-readable JSON schema.
It contains no copied RetroAchievements definitions or game assets. More story,
boss, exploration and challenge goals need verified action hooks before being
added. These definitions are not yet a shipped, stable achievement edition.

| Observation | Source evidence | Guard |
|---|---|---|
| Reward-bearing rooms | Babel `IogCompletionPercent`, `src/iog_ngplus.c`: ROM reward table `$01:AADE`, RAM flags `$0A60..$0A7F` | Only a newly observed increase during consecutive in-play observations emits a milestone |
| Red Jewels | Same function; `src/iog_inventory.c` stack stores: BCD `$0AB0`, item `$01` in `$0AB4..$0AC3`, stacked extras `$0B56` | Invalid BCD or total above 50 rejects the snapshot; handing jewels to Gem does not count twice |
| Ending | Babel NG+ route: epilogue scene `$E5`, terminal END scene `$F0`, current scene `$0644` | Requires observing transition into epilogue and then END in the same generation; no normal gameplay-ready requirement at END |

This is source-derived evidence, **not a naturally completed route or independent
GaiaLabs verification**. The host must require a verified stock USA ROM and
exclude Apocalypse Gaia, IoGR, New Game+, diagnostics, assisted validation and
any session in which cheats were used. A current cheat toggle is insufficient;
the host must retain sticky session eligibility. Unsupported editions must not
share the stock profile.

First observations, generation changes and explicit invalidations seed a silent
baseline. Decreasing jewel counts or reset clear flags also seed silently as a
secondary safeguard. Explicit generation changes are still mandatory: a loaded
save can move forwards, which cannot be reliably distinguished from gameplay by
RAM comparison. Invalidate on battery-save continuation, state loading, rewind,
reset, ROM replacement and profile changes. Loading an epilogue or END snapshot
does not award completion.

## Required next wiring

1. Qualify the source-derived signals on controlled real-game routes against
   GaiaLabs symbols and a matched reference. Distinguish fixtures from natural
   progression and keep assisted sessions read-only.
2. Add host lifecycle hooks to `game_rtl.c` and all save/load/rewind paths, with a
   reliable generation and sticky eligibility flag. Observe after completed game
   frames, outside guest simulation and outside achievement-worker threads.
3. Add the serialized storage worker, bounded immutable event queue, single-writer
   profile lock, strict JSON validation and unknown-ID preservation. The worker
   calls `ca_event`; its commit callback must durably replace a temporary file
   before returning success. Commit failures must leave progress and notices
   unchanged. Never overwrite corrupt progress.
4. Persist outside game saves, using schema 1 and the catalog namespace:
   `UserData/Achievements/illusion-of-gaia/stock-companion/unseeded/progress.json`.
   The executable-relative user-data root must match the launcher provider.
5. Publish only committed snapshots/notices to the UI thread. Add controller and
   keyboard browser access, held-opener/dismissal guards and small queued toasts
   through the shared presentation API. Mask the ending entry while locked.
6. Prepare the shared synthesized chime once at startup, submit through a
   separate audio voice, and respect master volume, sound setting and device
   loss. Original SPC audio and optional MSU-1 behavior stay independent.
7. Give CompanionLauncher a read-only catalog/progress provider. It must never
   write progress or turn a save's already-set flags into unlocks.

## Verification

Standalone foundation build (no ROM or game build required):

```powershell
cmake -S src/companion_achievements -B build-achievements-foundation -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-achievements-foundation
./build-achievements-foundation/gaia_achievement_observer_test.exe
```

Windows Clang 22.1.8 Release build passed **100 checks**. The fixture exercises
the actual shared core/presentation: silent baseline/restoration, no duplicate
milestones, stacked/given jewels, unchanged RAM, epilogue/END ordering, generation
changes, unsupported modes, bad snapshots, failed commits and queued notices.
It does not certify game playback, persistence, real-controller handling, audio,
the renderer or a campaign. The installed toolchain has no `ctest` command; the
built test executable was run directly and passed.

The catalog was validated and its header generated by the pinned shared
`tools/catalog.py` with prefix `gaia`. If it changes, regenerate from the shared
toolkit and repeat validation. Do not hand-edit `catalog.generated.h`.
