# Batch 004: original ability fixtures

Seven assisted ability cases executed their original game logic and passed
matched mixed-native/reference comparisons. Five cases run for 600 frames each;
Aura and Earthquaker run for 900 frames each. This is 4,800 frames per execution
mode across seven independent checkpoint fixtures, not one continuous route.
The private reusable index is
`.local/batch-001/native-004/abilities/qualified-cases.json`.

| Form / action | Observed original effect | Control with prerequisite absent |
|---|---|---|
| Will: Psycho Dash | Original dash state; x770 to808 before the original collision/bounce returns him. | No dash state or corresponding displacement. |
| Will: Psycho Slider | Stock double-tap produces speed−3; slide state moves x760 to728. | Stock double-tap remains, but no slide state. |
| Will: Spin Dash | Charged, alternating shoulder presses enter the original spin/rush state; x770 to808. | No spin/rush state. |
| Freedan: Dark Friar | Original projectile actor spawns at1098,810 and moves to1108,810. | No projectile actor. |
| Freedan: Aura Barrier | Original controller spawns two original orbiting actors; their coordinates change around Freedan. | No barrier controller or orbiting actors. |
| Freedan: Earthquaker | Original ledge jump, quake descent, landing controller and temporary quake flag, which subsequently clears. | Same original ledge jump and landing, without the quake controller/flag. |
| Shadow: Aura | Equipped item triggers the original melt and floor-drop path; y480 to896 through original Pyramid terrain, then idle/control restored. | Without the item, Shadow remains at y480. |

The comparisons require identical ROM, route, seed, frame count, aspect ratio
and fixture mod state. They passed CPU/WRAM traces, saved WRAM/VRAM/CGRAM/OAM
and framebuffer snapshots, final full output, device events, complete APU
state/PCM and executed APU-cycle sidecars. As described by
`compare_native_runs.py --apu-clock cycles`, SPC host frame/scanline/hclock
stamps may differ; executed APU cycles and event order must match. This is not
a claim of byte-identical raw host-stamped APU logs or physical hardware timing.

## Assistance and source boundaries

The stock USA ROM was read without modification; its SHA-256 is
`32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd`.
Checkpoint form startup came from the previously qualified
[original transformation/return fixtures](NATIVE-003-FORMS.md). These tests do
not write the current form selector or install a replacement player script.
Learned bits are explicitly supplied into an observed-zero ability word.
Aura is explicitly supplied/equipped in an observed-empty inventory slot.
Earthquaker and Aura additionally place the real player at a location derived
from the existing scene's collision map. Terrain, velocities and jump scripts
are never written. Each runner receipt enumerates every assisted write.

The cases use private copied saves/settings, room reward rate1×, infinite HP
and 4:3. This isolates effects from enemy damage; it does not test damage
blocking or reward balance. No owner save/settings/music files were changed.
The stock run, double-tap and ability movement logic is unchanged; no movement
multiplier or holding-Y change was introduced.

Source interpretation joins exact stock ROM bytes with pinned
[Azarem/GaiaLabs](https://github.com/Azarem/GaiaLabs/tree/f7649eb735aaf19b2cd8f693fdaa6669b3e42711)
metadata and its COP argument definitions. Credit remains with the original
game authors, Babel contributors and GaiaLabs contributors. The bounded
framework decoder records REP/SEP and exact inline COP sizes. It is source
research, not another independent RomAtlas qualification. Private excerpts and
receipts remain under the private ability directory and are not distributed.

## Input and prerequisite contracts

In these fixed input builds, physical A maps once to the game's logical attack
bit `$8000`; physical B maps to the equipped-item action. The original charge
actor requires free controls and a non-Shadow form. Will needs learned Dash or
Spin; Freedan needs Dark Friar or Earthquaker to keep the charge controller.
Barrier's own learned bit alone does not satisfy that charge prerequisite.

| Action | Explicit ability mask at `$0AA2` | Reusable input after setup |
|---|---:|---|
| Psycho Dash | `$0001` | Attack held220 frames, then release. |
| Psycho Slider | `$0002` | Left2, idle1, left2; then left+attack8. |
| Spin Dash | `$0005` | Attack200; alternate attack+L4 / attack+R4 twelve times; attack+right60. |
| Dark Friar | `$0010` | Attack held220 frames, then release. |
| Aura Barrier | `$0030` | Attack200; continue attack while adding L+R4; then release. |
| Earthquaker | `$0040` | From the original Ankor ledge, down12, then attack110 across the original fall. |
| Aura | Item `$24`, not an ability bit | Equipped-item button2 over the verified Pyramid floor. |

These are bounded fixture timings, not universal charge times. Continuous
`hold` segments preserve the attack button between combinations and zero-time
snapshot commands. `press` retains its original release-gap behavior. Holding
both shoulder buttons throughout charging does not replace Spin's alternating
new presses. The game's original controller consumes those edges. The
[Great Wall guide](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%203.html)
also describes alternating shoulder inputs after charging.

Two additional controls isolate the advanced bit: Barrier absent while
retaining Dark Friar (`$0010`), and Spin absent while retaining Psycho Dash
(`$0001`). Both reach the real ready charge actor with its completed counter;
the same shoulder combinations produce no advanced action. With the advanced
bit absent, those combinations follow the original guard/cancel behavior, so
these controls do not claim a projectile or dash from that exact combination.
The independent positive cases above separately execute those base actions.

## Earthquaker: actual jump and landing

The original downward collision path at `$82D376` recognizes collision class8
and reaches `$82D425`, which installs the original player jump `$82C61E`.
The existing Ankor scene B6 contains this class at the ledge around1048,80.
Only the player's position is assisted to that location. Down input produces
the jump; no airborne state is supplied.

The runtime observations are jump `$82C633` at1052,78, then the learned
Earthquaker descent `$82C6F4` at1052,116. Landing at1052,128 spawns the
original `$82C73F` controller, observed at `$82C749`, and sets the original
`$09AE & $0010` effect flag. By frame663 the controller is gone, the flag is
clear and the player is idle. The no-ability control takes the ordinary jump
path and never creates that effect.

This qualifies the original landing effect. It does not establish a Rock
Guardian stun, damage or the naturally earned Ankor ability event.

## Aura: actual original floor traversal

The pinned [GaiaLabs item dictionary](https://raw.githubusercontent.com/Azarem/GaiaLabs/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaPacker/Patches/ItemDictionary.asm)
identifies Aura as item24. The stock item dispatch reaches `$839CAF`, which
requires Shadow, stationary movement and available controls, then installs the
original `$80C557` melt script. Its floor test requires collision class4 below
the scan stop. The
[Pyramid guide](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%204.html)
describes using equipped Aura at the marked floors to reach lower levels.

The private candidate finder translates the original collision-address
calculation against the already populated Pyramid CC checkpoint. It finds the
original class4 tile below y496 at x424. The player is placed at424,480;
the short facing input leaves x428 within the same tile column. Equipped-item
input enters `$80C56D`, then the real floor-drop path `$80C5CF`. Observed y
coordinates are480,559,659,859 and finally896. By frame645 and again845,
the player has returned to `$82C4C8` with controls zero. The missing-item
control stays at428,480. Original terrain is unchanged.

This qualifies one Aura floor traversal. It does not claim the entire Pyramid
puzzle, hieroglyph acquisition, naturally earned item or campaign completion.

## Immutable identities and retained failures

Dark Friar and Psycho Dash were captured with fixed-input binary SHA-256
`87b5d6a1e6bb06f20ed89160c09dfd7bec5da1f667e59b7c88c7e426eab63750`.
The other five use continuous-input binary
`be19975da2e7f50dfda63f8d543fa7b9b63b024c3edcbd930d2d836b40cd8236`.
Each index entry includes exact script/seed/binary/profile hashes, the capture,
parity receipt, absent-prerequisite control and semantic snapshot expectations.
Every control also records its exact script, seed, frames, options and hashes.
The private `verify_qualified.py` checked all seven existing receipt pairs and
nine prerequisite controls against raw WRAM snapshots and immutable hashes;
`semantic-verification.json` records the result and bound index hash. This
verification reads existing evidence and does not run or qualify a new binary.
Different program/build identities remain separate or explicitly historical;
their cost samples must not be silently aggregated or relabeled.

Earlier simultaneous-shoulder, insufficient-momentum and non-drop Aura
attempts remain discovery evidence. The initial unset01 controls that
accidentally retained their grant are preserved and superseded by explicit
unset02 controls. Only the seven indexed cases carry qualification. The
current batch's expanded build separately replayed these exact scripts and
seeds: all seven effects and nine controls passed on selected `fa3a2502...`,
with 32 fresh runs and all 48 witness/reference/native comparisons passing.
Source observations carry through matching input, trace/state and output
evidence. [Selected batch and reproduction](NATIVE-BATCH-004.md).

## Fresh widescreen checks across all three forms

The final private candidate
`fa3a25028b72443f7998bc6da6a31c845f03adc4444e95ca51525f607db7ea7f`
also passed three fresh 16:9 native/reference cases. They reuse the exact
qualified scripts, checkpoints, frame caps and cheat settings, changing only
the aspect option. This is six fresh runs and 4,400 frames in total across
three independent assisted fixtures.

| Case | Frames per mode | Native CPU-cycle share | Newly checked outcome in both modes |
|---|---:|---:|---|
| Will, Aqueduct clear at 8× | 700 | 5.1652% | Three live bats become three deaths; counts 3→2→1→0; the original room flag sets after the kills; current/max HP become 16. |
| Freedan, Dark Friar | 600 | 14.3200% | Original cast and projectile PCs; projectile moves 1098,810→1108,810. |
| Shadow, Aura floor | 900 | 9.6848% | Original drop path from y480; settled y896, idle script and controls zero, with original collision grid unchanged. |

Each case passed fresh CPU/WRAM, snapshot, device-event, complete APU-state,
executed APU-cycle and full-render parity. The source outcomes above were
asserted anew from each widescreen run's raw WRAM. They were not copied from
the earlier qualification booleans. All final full outputs were **342×224**,
byte-identical between native/reference, nonblack and visually reviewed at
their full width. The normal debug framebuffer snapshots remain 256×224;
the separate full `final.ppm` output supplies the widescreen render check.

The private per-case `wide-receipt.json`, `parity-cycles.json`, fresh
`source-outcomes.json` and aggregate `summary.json` are under
`.local/batch-001/native-004/wide/`. Lossless format conversions used for visual
review have a private conversion receipt and do not alter source pixels.
No 4:3 framebuffer was compared with a widescreen framebuffer. These results
extend the bounded assisted checks across three forms; they do not establish
earned abilities, natural progression, stock difficulty or campaign completion.
