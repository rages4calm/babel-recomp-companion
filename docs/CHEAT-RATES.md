# Optional room-clear reward rates

The `iog.cheats/room_rewards` feature offers **1x through 8x newly earned
room-clear stat rewards**. It is disabled by default; selecting 1x preserves the
original game. It changes no movement, speed, form ability, puzzle requirement or
XP system. Gaia does not use Lagoon's level/XP model, so no XP knob was copied.

Both the native menu and CompanionLauncher use feature `room_rewards`, integer
option `multiplier`, default 1, range 1..8. Selecting 1x stores the feature as
disabled and the multiplier as 1; other values enable it. Settings share the
native mod-state file rather than separate launcher-only preferences.

## Traced source and limits

GaiaLabs US `parts.json` identifies the original reward actors
`e_hp_increase`, `e_str_increase`, `e_def_increase` and their common helper
`func_00E110`. Its COP definitions distinguish embedded script arguments from
CPU instructions. The source was inspected locally from the owner's USA ROM;
no generated game assembly or instruction implementation is included here.

The common helper marks the current room's clear flag through the original
flag setter before returning to the actor's +1 maximum-HP, strength or defense
store. The room reward table at `$01:AADE` contains 87 nonzero entries: 29 HP,
27 strength and 31 defense. Each entry is 1, 2 or 3, matching those three actor
types. Source fingerprints guard the known award-store ranges, common flag
setter and table; a changed or unknown source leaves rewards original.

This is not a generic positive-stat-delta multiplier. In particular, the
inspected `$80:D697` Dark Point store belongs to spending 100 DP after death;
using arbitrary DP changes as a gain signal would confuse spending, restoration
and genuine pickups. That mechanism was not implemented.

The host adapter requires all of the following:

- The current room changes from uncleared to cleared, with no other room bits
  newly set and none moving backwards.
- A live, nonzero-HP player stays in the same room and state generation.
- The table-selected stat increases by exactly the original one point while
  the other two stats remain unchanged.
- The award appears on the flag frame or within two following real frames;
  unrelated stat changes, expiry, loading, scene changes or invalid state cancel
  the pending observation.
- The stock source fingerprints still match, and Stats Boost, New Game+,
  randomizer and Apocalypse Gaia are inactive.

Matching awards add only the extra `multiplier - 1` points. The optional cheat
caps maximum HP at 40 and strength/defense at 99; it never reduces existing higher
stats. Extra maximum HP adds the same extra amount to current HP, preserving
damage and the original reward's remaining healing sequence. It never revives a
zero-HP player. These are explicit cheat limits, not claims about every original
overflow or display boundary.

The small continuation window is deliberately conservative. This batch proves
the source ordering and fixture behavior; a natural combat/room-clear route must
still establish which frame boundaries real reward actors use and that the
feature appears consistently during ordinary play. Missing a reward under an
unqualified timing context is preferable to multiplying an unrelated change.

## Restore safety and local achievements

The callback runs through the framework's existing real-frame mod boundary;
speculative run-ahead frames do not advance this observer. State generation
changes seed a silent baseline. `IogCheatRatesInvalidate()` is also available to
the host at real load/reset boundaries. A run-ahead rollback must not erase the
real observer state; extra load hooks must skip speculative restoration.

`IogCheatsSessionTainted()` is sticky after any supported cheat is activated or
enabled, including existing HP/DP/stat cheats, a reward rate above 1x and the
successful all-jewels action. Turning a cheat off, loading or resetting does not
restore that process session's eligibility. Future local achievement wiring must
consult this flag. This does not claim that CompanionAchievements live tracking
has already been connected; its storage/UI work remains separate.

## Verification

```powershell
clang -std=c11 -Wall -Wextra -Werror -I src scripts/test_iog_cheat_rates.c src/iog_cheat_rates.c -o .local/batch-001/native-002/cheat-rates/test_rates.exe
./.local/batch-001/native-002/cheat-rates/test_rates.exe 'Illusion of Gaia (USA).sfc'
```

The focused helper/source check passed **136 assertions**: every reward kind
and multiplier, silent baselines/restores, generation changes, same-frame and
bounded delayed rewards, expiry, wrong-room/multiple/backward flags, unrelated
stat changes, invalid modes/player/death, caps, original source acceptance and
modified-source refusal. These are bounded fixtures and read-only source checks,
not a naturally completed reward, a combat campaign or a balance qualification.

`python scripts/test_iog_mods_runtime.py` separately compiles the actual
`iog_mods.c` callbacks and reward tracker with ROM-free host stubs. **656
assertions across seven fresh processes** passed: actual reward writes, all
multiplier/type combinations, default no-op, activation/persistence, restore
guards, blocked modes and sticky cheat eligibility. The source-acceptance
decision is injected in this harness; the read-only 136-check suite covers the
real fingerprint separately. Neither substitutes for a natural combat reward or
the framework's run-ahead/restore lifecycle.

The final selected engine also passed a 120-frame, checkpoint-linked assisted
fixture with explicit room-selector, clear-bit and original +1 stat writes.
Native 8x versus forced-interpreter 8x matched all comparison gates; a separate
1x control confirmed eight effect assertions for HP/max HP, strength and defense.
These are actual engine effects under synthetic events. The loaded terrain
remains South Cape; no dungeon visit or natural enemy-clear reward is claimed.
[Complete inputs, values and limitations](ASSISTED-TESTING.md).
