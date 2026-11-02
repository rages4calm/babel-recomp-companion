# Batch 004: assisted encounters and room rewards

This batch exercises original attacks, damage, enemy deaths and room-clear
rewards from private prepared checkpoints. It does not establish natural
progression, campaign completion or achievement eligibility. Every run uses the
owner's verified original USA ROM; no game data or validation captures are
distributed.

## Source contracts

GaiaLabs metadata is pinned at
[`f7649eb`](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/parts.json).
The private decoder cross-checks those boundaries against the owner's unchanged
ROM and skips COP inline arguments using the pinned
[COP definitions](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/copdef.json).
Addresses below describe observed data contracts, not copied game code.

| Observation | Original source contract |
|---|---|
| Enemy identity and initial HP | Constructor `$83:CF1B..D00E` reads the enemy record's stat ID, resolves four-byte entries at `$81:ABF0`, stores the table pointer at `$7F:(actor + $20)` and initial HP at `$7F:(actor + $26)`. |
| Actual damage | `$83:BE42` and `$83:BFF0` store reduced, zero-clamped enemy HP. The latter includes strength, enemy defense and form in the damage calculation. An animation or changed script PC alone is insufficient. |
| Counted enemy death | Generic death `$80:DB8A..DBB2` decrements binary `$0AEC` and packed-BCD `$0AEE`, with exclusions for actors not counted in that roster. Boss children need separate observations. |
| Room reward | `$80:DD87` checks the existing room-clear flag and `$81:AADE` reward selector. Original HP, strength and defense actors call common `$80:E110`; `$80:E14C` marks the room before their original stat store. |
| Boss completion | `$80:C2BE..C308` selects the boss context by scene and calls the original completion setter. `$80:B05E` tests and `$80:B069` sets the corresponding bit in `$0AA0`. |

The enemy actor base must be identified from a matching live actor and source
stat pointer. A fixed address from another scene, or stale HP after an actor
slot is reused, is not an enemy-health observation.

## Qualified reward cases

The immutable corrected-input executable is SHA-256
`87b5d6a1e6bb06f20ed89160c09dfd7bec5da1f667e59b7c88c7e426eab63750`.
Each rate has a same-binary mixed-native/forced-interpreter pair. Both actual-SPC
cycle comparison and the earlier sample comparison pass, including CPU/WRAM
traces, CPU/master totals, memory/PPU snapshots, complete APU/DSP/PCM/queue state,
device events and full final output.

| Original encounter | Assistance and measured deaths | 1x | 8x |
|---|---|---|---|
| Aqueduct entrance `$0C`, Will | 20 strength, HP regeneration and documented player positions. Three bats start at 3 HP; their HP reaches zero and remaining count is `3 → 2 → 1 → 0`. | Maximum/current HP `8 → 9` | Maximum/current HP `8 → 16` |
| Pyramid main `$CC`, Shadow | 40 strength/defense, HP regeneration and documented player positions. Two 20-HP mystic balls die; count is `2 → 1 → 0`. | Defense `40 → 41` | Defense `40 → 48` |
| Pyramid dangerslide C `$DB`, Shadow | Same 40-point preparation and source-pinned scene entry. Two 25-HP blasters and two 20-HP mystic balls die; count is `4 → 2 → 1 → 0`. | Strength `40 → 41` | Strength `40 → 48` |

The initial clear bit is unset. It changes through the original award sequence
after the counted deaths. Scripts never write enemy HP, death selectors,
remaining counts, clear flags or reward stores. Stats Boost remains disabled;
explicit preparation leaves sufficient headroom below the optional rate caps.
Current HP includes enabled per-frame regeneration, so these values do not
independently qualify the original healing queue or timing. Regeneration does
not revive a defeated player or prevent every lethal hit within one frame.
The acquired Shadow form comes from the previously qualified original Dark
Space roundtrip, with that assisted checkpoint dependency retained.

Two continuous 1x/8x Aqueduct cases also dismiss the original reward dialogue
and reload the cleared room through a source-pinned incoming request. The count
remains zero and maximum HP remains 9/16: no respawn or duplicate reward is
observed. These are same-room reload checks, not a campaign revisit.

## Boss coverage and guide expectations

Guide descriptions select test targets; they do not supply flags or prove a
working encounter. The four-part scope remains explicit:

| Guide | Target and required distinction |
|---|---|
| [Part 1](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide.html) | Castoth's hands and exposed head are distinct from simply arriving in scene `$29`. |
| [Part 2](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%202.html) | Viper's flight/range and the Vampires' exposure windows require actual damage and defeat observations. |
| [Part 3](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%203.html) | Sand Fanger's appearance and temporary exposure must be separated from a sandy-room visit. |
| [Part 4](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%204.html) | Mummy Queen's solid and ghost phases, and the original entry portal, require their own source/runtime evidence. |

Castoth and Viper recipes preserve original boss initialization, damage, death
and completion paths. They use explicitly accelerated **255 strength**, 90
defense, 40 HP and documented player positioning. Strength above normal cheat
UI limits can overcome high-defense portions of the encounter; these recipes
must not be described as normal weakness timing, normal boss balance or
unassisted victories. No boss HP, vulnerability selector, defeat flag or script
entry is injected. Qualification receipts and any remaining failed attempts
must govern the claimed runtime scope.

Both continuous 5,000-frame recipes now pass native/interpreter comparisons in
both audio modes. Each begins at the same qualified Freedan area checkpoint,
runs the original lair loader and intro, then performs actual attacks. Narrow
write traces identify the original `$83:BFF0` zero-HP store before completion:

| Boss | Observed original sequence |
|---|---|
| Castoth `$29` | Main actor starts at 40 HP, hands at 10 HP. The actual damage writer sets main HP to zero, the counted roster reaches zero, and original completion bit `$0AA0 & $01` appears. |
| Viper `$55` | The original intro waits for the player to advance into the arena. Its 40-HP body receives the actual zero-HP damage store, the counted roster reaches zero, and original completion bit `$0AA0 & $02` appears before the original outro/return. |

Viper's old actor slot can contain unrelated HP after the outro. Its completion
proof therefore uses the original damage write plus count/completion transitions,
not the final contents of a reused slot. A separate 90-strength positioning
control did not defeat Castoth and remains unqualified.

## Reproduction and retained failures

Private inputs and receipts are under
`.local/batch-001/native-004/encounters/`. `qualified-cases.json` is the replay
catalog: script/seed hashes, exact options, original source contracts, measured
snapshot values and semantic checks. It deliberately separates a passing engine
route from a passing encounter or reward assertion. Replays against a new
candidate must run both modes from those identical inputs again.

The selected expanded build `fa3a2502...` did replay all ten cases, together
with the two [additional bosses](NATIVE-004-BOSSES.md). All 24 fresh runs and
36 witness/reference/native comparisons passed. Castoth/Viper also require
fresh HP-zero writes in both modes; old hit-log metadata alone cannot pass.
[Final selected evidence](NATIVE-BATCH-004.md).

Earlier probes remain failed or unqualified. These include the old actor-PC-only
bat inference, a lethal projectile before HP regeneration could act, reward
reloads attempted while dialogue still held control, and boss positioning that
allowed knockback to move the player out of range. Later receipts supersede
only their stated scenario. Ability acquisition, normal boss-phase mastery,
natural combat rewards and campaign coverage remain separate work.
