# Assisted engine testing

The owner authorized cheats, game-flag changes and teleports to fill coverage
gaps. This batch uses isolated fixture data and records every scripted write.
Assisted coverage remains separate from natural progression and campaign proof.
No owner installation, save, mod selection, soundtrack or source ROM was changed.

## Inputs and scope

The original retained PB executable was copied before testing:
`3e2d4cc30267147b2c5d2cdb4caf7de31a760b803f19c9bf36f12df2a2960953`.
A 6,040-frame continuation of the existing natural classroom-to-South-Cape input
route created **fixture-owned slot 0**. It starts with the original stats and
does not fabricate story flags. Its checkpoint SHA-256 is
`d0a7c68a508a3ccf34105f28a7610d96598bc7d3ea2541ee3f83843936be8eb0`.

After the final selected build became available, it was separately copied and
verified before three new runs:
`f8f7f82ff37336ac24b1053ae89151668dd377cd2507ae09680d04c90a034680`.
Those results are **final-F8 execution linked to a PB-origin checkpoint**. They
are not a new cold-start qualification of all later areas or a natural combat
route. Original PB receipts remain distinct.

`scripts/check_assisted_routes.py` uses new output directories under `.local/`,
an explicit immutable executable, the verified read-only USA ROM and optional
private slot-0 input. It stages source-reviewed mod packages, writes fixture
settings, and enables only the requested reward-rate feature. It rejects owner
checkpoints outside the private tree, duplicate output directories, unsupported
ROMs and unbounded frame/timeout requests. It records script writes with inline
reasons, source hashes, dumps and trace evidence. The public script includes no
ROM, generated game code, checkpoint, extracted terrain or game assembly.

## Actual engine reward-rate results

The 120-frame fixture runs the real executable and its actual registered
`RoomRewardFrame` callback with real ROM source fingerprints. It temporarily
selects three known reward-table entries, sets the matching room-clear flag and
applies the original one-point stat delta in source order. It does **not** load
those maps, defeat an enemy or execute an original reward actor. The actual
terrain remains South Cape throughout; the real scene identity is restored
before the final visible capture.

| Script address | Explicit change and reason |
|---|---|
| `$0644` | Temporarily select table entries `$0C`, `$0D`, `$0E` for HP/strength/defense observations; restore `$01` afterwards. These are synthetic selector changes, not visits to those rooms. |
| `$0A61` | Set `$10`, then `$30`, then `$70`: add each selected room's clear bit while preserving preceding bits. This simulates the common helper's flag-before-stat ordering. |
| `$0ACA` | Simulate original maximum-HP award 8 → 9. |
| `$0ADE` | Simulate original strength award 1 → 2. |
| `$0ADC` | Simulate original defense award 0 → 1. |

The fixture writes no movement value, player coordinate, inventory, save-memory
flag, enemy-death event or healing queue. In particular, it does not synthesize
the original HP actor's queued healing. This keeps the observed extra current HP
separate from natural reward-animation/healing behavior.

| Observed value after the injected original award | 1x control | 8x |
|---|---:|---:|
| Maximum HP | 9 | 16 |
| Current HP | 8 | 15 |
| Strength | 2 | 9 |
| Defense | 1 | 8 |

The final-F8 8x run and the same binary forced through the interpreter passed
the full matched comparison: identical CPU/WRAM trace, CPU/master cycles, memory
and PPU snapshots, complete APU/scheduler state, selected APU port-event semantics
and full final PPM output. Inputs include the same ROM, script, checkpoint,
multiplier and assisted status. The bounded mixed-mode run reports **9.442% AOT
cycles**; that fraction applies only to this checkpoint-linked fixture.

A separate eight-check effect receipt verifies the expected 8x versus 1x values
and identical starting observations. Different multipliers deliberately change
state, so that effect check is not reported as a tier-parity comparison.
The earlier 136 helper checks and 656 ROM-free host-integration assertions remain
separate evidence. Natural room-clear timing, combat, reward animation, healing
queue behavior and balance across a campaign remain unqualified.

Private final evidence is under `.local/batch-001/native-002/assisted/`:

- `selected-rewards-8x-native/`, `selected-rewards-8x-reference/` and
  `selected-rewards-1x-control/` contain isolated runs.
- `selected-rewards-8x-parity.json` is the complete matched comparison.
- `selected-reward-effect-receipt.json` records the eight explicit effect checks.
- `reward-component.txt` retains every poke and its reason.

## Warp contract findings and retained failures

GaiaLabs' COP-26 definition and the actual original handler establish pending
scene `$0642`, spawn parameters `$064C/$064E`, flags `$0650` and extra parameters
`$0652`. The previously executed church-start tuple and existing GaiaLabs warp
definitions provide real source values. That data alone does not establish the
complete active-game transition request contract.

The following church probes remain **failed**:

| Probe | Explicit writes | Observed result |
|---|---|---|
| Pending/spawn request from the private South Cape checkpoint; 360 frames, mixed and forced interpreter | `$064C..0653` set to the source-backed church tuple; `$0642 = $0008` | Scene stayed `$01`, pending `$08`; both traces matched. Identical failure does not qualify a warp. |
| Request plus source-backed fade parameters; 400 mixed frames | Same fields plus `$064A = $0303`, `$0648 = $0002` from the original transition actor | Scene stayed `$01`; no church terrain loaded. |
| Same request after a cold natural-route continuation; 6,500 mixed frames | Same fields; no checkpoint load | Remained in South Cape after the request, ruling out a checkpoint-only explanation for this failed request. |

No guessed additional flags were tried and no broad room-ID sweep ran. Source
inspection identifies a transition state machine and caller-entry prerequisite
that remains unproven. A later focused investigation should capture actual
pending/fade writers around the already-working natural church exit, then trace
the caller rather than treating a pending scene word as a teleport API.
`warp-contract-failure-summary.json` preserves the negative result's scope.

One additional 260-frame checkpoint-assisted natural-input probe confirmed
horizontal South Cape movement: X 200 → 248. Downward input remained blocked at
the tested position. It changed no coordinates or flags and establishes neither
a house/cave entry nor a new area. No additional area's gameplay is claimed.
