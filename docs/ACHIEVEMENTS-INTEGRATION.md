# CompanionAchievements integration

The Original build can audit achievement signals after completed frames.
Set `IOG_ACHIEVEMENT_AUDIT=1` to log events from the verified USA ROM during
development. State loads and resets start a new observation generation.
The audit writes to stderr only. The v40 browser opens from **Companion → Status**
with SNES A or Enter. The list and detail pane expose progress and mask the
ending until earned. B or Escape returns to Status with game input still paused.
The desktop progress writer is on by default; `IOG_ACHIEVEMENT_PROGRESS=0` turns it off.
Only committed unlocks queue an in-game toast and optional synthesized chime.
The Companion Launcher reads the selected executable's profile and catalog.

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

The signal guards use the verified stock USA ROM and
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

## Progress storage

The desktop worker owns a bounded event queue and an exclusive profile lock.
It validates schema 1 and preserves unknown IDs and newer catalog versions.
Each changed snapshot passes through a temporary file, flush, and atomic
replacement before progress and notices become visible to the main thread.
Corrupt or unrecognized profiles remain on disk for recovery. Clean exit
drains accepted events. The executable-relative profile is stored at
`UserData/Achievements/illusion-of-gaia/stock-companion/unseeded/progress.json`.

Read-only audit takes precedence over progress. Builds with a debug server and
sessions launched for scripted routes, input diagnostics, or state relaunch
cannot use the writer. Standard cheat, alternate game and New Game Plus guards
also apply. Battery continuation, rewind and profile changes need additional
end-to-end verification before enabling progress by default.

The chime uses a separate playback stream and the current master volume.
`IOG_ACHIEVEMENT_CHIME=0` silences it. Physical-controller behavior, a live
persisted unlock with sound, and full campaign qualification remain open.

## Verification

The v40 browser was opened by an SDL virtual controller. The replay entered
from Status, selected another row and page, held Back through the return to
Status, then closed the Companion and resumed gameplay. The 640×360 logical
panels matched at 1280×720, 2560×1080 and 1080×2340 window settings.

The Original v37 host emitted one jewel event after a controlled inventory
write. Loading the earlier state and then the later state emitted no duplicate.
The same diagnostic route with its cheat settings enabled emitted no event.
A 75,000-frame controller replay from an earned final-form Dark Gaia checkpoint
defeated the boss, passed through Changed World and New Babel, and let the full
credits run. It emitted exactly one ending event on the first END scene frame.
The checkpoint retained prior player stat boosts. There were no further state
loads, live cheats or memory writes during the replay. In v39, a controller
interaction at a position-assisted South Cape Red Jewel fired once as the
original item and event flag changed. An Aqueduct replay from a prepared
checkpoint earned the original room reward and emitted one clear event across
the reward and revisit. These assisted replays exercised read-only observation.
They created no achievement profile.

Standalone foundation build (no ROM or game build required):

```powershell
cmake -S src/companion_achievements -B build-achievements-foundation -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-achievements-foundation
./build-achievements-foundation/gaia_achievement_observer_test.exe
./build-achievements-foundation/gaia_achievement_progress_test.exe
```

Windows Clang 22.1.8 Release build passed **100 checks**. The fixture exercises
the actual shared core/presentation: silent baseline/restoration, no duplicate
milestones, stacked/given jewels, unchanged RAM, epilogue/END ordering, generation
changes, unsupported modes, bad snapshots, failed commits and queued notices.
It does not certify game playback, persistence, real-controller handling, audio,
the renderer or a campaign. The installed toolchain has no `ctest` command; the
built test executables were run directly. The progress test checks writer lock
contention, forward-compatible rows, shutdown drain, restore without duplicate
notices, corrupt-profile protection and commit failure.

The catalog was validated and its header generated by the pinned shared
`tools/catalog.py` with prefix `gaia`. If it changes, regenerate from the shared
toolkit and repeat validation. Do not hand-edit `catalog.generated.h`.
