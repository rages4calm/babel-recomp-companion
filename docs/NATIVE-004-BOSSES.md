# Batch 004 assisted boss fixtures

Two continuous checkpoint-linked boss cases pass matched interpreter/native
comparison on immutable fixed-input build
`87b5d6a1e6bb06f20ed89160c09dfd7bec5da1f667e59b7c88c7e426eab63750`.
Both use original scene initialization, boss AI, player attacks, damage and
defeat handling. Player stats, position and infinite HP are assisted. This is
bounded encounter evidence, not earned progression, stock difficulty or campaign
qualification. The discovery metrics below retain their original build identity.
Both exact cases also passed fresh same-binary native/reference and frozen-witness
comparisons on selected expanded build `fa3a2502...`; see the
[final batch record](NATIVE-BATCH-004.md).

| Case | Frames | Observed original defeat | Native CPU-cycle share |
|---|---:|---|---:|
| Sand Fanger | 2,200 | HP 40 to 0; boss bit `$08`; live/BCD counts 1 to 0 | 8.4726% |
| Mummy Queen | 2,460 | HP 40, 30, 20, 10, 0; boss bit `$10`; live/BCD counts 1 to 0 | 8.5778% |

The percentages describe each whole fixture. They do not prove that the boss
controller itself executed natively or measure host speedup.

## Source and setup

Pinned [GaiaLabs scene metadata](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/scenes.json)
identifies scenes `$8A` and `$DD`. The original actor tables and named
[source blocks](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/parts.json)
identify `h_gw8A_sand_fanger` and `h_pyDD_mummy_queen`. The owner's original USA
ROM identity, incoming record hashes and bounded source-range hashes are retained
privately; no game assembly or bytes are published here.

Sand Fanger starts from the previously witnessed Freedan checkpoint, then
requests the original ordinary warp record at physical `019C8E`, from scene
`8B` to `8A`. Explicit player placement enters the original two `COP 45`
intro rectangles. The controller then runs its original segmented head/body
movement before an ordinary directional input and attack. Further player
placement uses the independently observed head trajectory; it does not move
the boss or select a boss phase. Assisted stats are 40 maximum/current HP,
90 DEF and 255 STR at the strike, with infinite HP enabled.

Mummy Queen starts from the previously witnessed Shadow checkpoint. Scene `DD`
has no ordinary incoming warp row in the inspected table. Its fixture instead
requests the exact original normal `COP 26` payload at physical `08CDCD`.
The real loader initializes the lair and actors. This bypasses the Pyramid
portal/puzzle progression; that progression is not claimed. The fixture lets
original AI run before placing the player below the observed queen position.
Ordinary repeated attacks, with assisted 135 STR, produce multiple real damage
steps. Maximum/current HP is 40, DEF is 90 and infinite HP is enabled.

Neither case writes a form selector, enemy HP/DEF, boss script, phase selector,
death state, enemy count or defeat/clear flag. The original form checkpoints
remain explicitly assisted evidence. The actual script-write lists are checked
against a narrow allowlist of player stats/coordinates and verified incoming
request fields.

## Mechanic evidence and comparison

Enemy HP comes from the original `7F:actor+26` field. The Sand Fanger head is
actor `1090`; its original death callback executes in `$8B:8582..8619`. The
Mummy Queen is actor `1150`; its callback executes in `$8B:A9C2..AA2C`.
Actual instruction captures witness both AI and death-handler execution.
The common original handlers set the corresponding boss bit and retire the
live and BCD counts; those fields are observed rather than injected.

Mummy Queen's original HP-controlled phase word at `7F:actor+10` changes from
0 to 1 to 2 during the continuous fight. This establishes those transitions,
not every randomized attack pattern. The final fixture stops after defeat and
count retirement; it does not claim post-boss statue, item or story completion.

Both comparisons require identical source inputs, CPU/WRAM traces, CPU/master
totals, memory/PPU snapshots, full output, APU/SPC/DSP state, PCM ring and port
scheduler/queue state. Executed-cycle mode binds every eight-column APU sidecar
to the same run's raw log, compares ordered SPC event/port/value/sample/executed
cycle fields, and retains exact CPU event stamps. Only SPC host-observation
frame/beam stamps are normalized. Raw differences remain recorded; executed
emulator cycles are not a hardware timestamp.

## Retained attempts and reproduction

The first Pyramid portal probe treated `D2 D1 01` as a word flag. Pinned
[COP definitions](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/copdef.json)
and the actual handler establish byte flag `D1` plus byte condition `1`:
`0A1A` bit `$02`, rather than `0A3A` bit `$02`. Correcting it releases the
portal's wait, but the bounded interaction probe did not finish its dialogue/
transition. Both failed arrival attempts remain retained. The qualified direct
entry writes neither prerequisite flag.

A shorter Mummy combat attempt demonstrated damage but stopped at HP 10.
A longer discovery defeated it and followed the original post-boss transition,
so it failed that attempt's expected-final-scene gate. Neither result was
rewritten as the final qualification. The final shorter continuous case was
rerun with its own matched reference and receipts.

Private `.local/batch-001/native-004/bosses/qualified-cases.json` contains both
case scripts, original checkpoint hashes, frame/config/mod settings, source
contracts, native/reference output and profile paths, semantic checks and
cycle-comparison hashes. The immutable scripts can be replayed through the
unchanged `check_assisted_routes.run` helper; `export_cases.py` verifies the
recorded semantics without running the engine. All attempts and source notes
remain private. No engine, generator or helper was edited for these fixtures.

## Final-candidate widescreen stress

The exact qualified Mummy Queen script, checkpoint and assistance settings were
replayed in 16:9 on final candidate
`fa3a25028b72443f7998bc6da6a31c845f03adc4444e95ca51525f607db7ea7f`.
Both same-binary native and interpreted runs passed for 2,460 frames. They match
99,865,176 CPU cycles, 797,631,484 master clocks, CPU/WRAM and device evidence,
executed SPC-cycle events, complete APU/DSP/PCM/queue state and full 342×224
output. The candidate's whole-fixture native CPU-cycle share is **9.7532%**.

Direct source-field checks in both runs reproduce boss HP 40, 30, 20, 10, 0;
the original phase word 0, 1, 2; boss bit `$10`; and live/BCD counts 1 to 0.
This compares the relevant mechanic fields against their source-backed
expectations, not whole memory across aspect ratios. It remains a checkpoint-
assisted widescreen stress case, not campaign coverage, stock difficulty,
hardware timing or proof of native execution of the boss controller itself.

Private receipts are under `native-004/wide-boss/`: `inputs.json`,
`parity-cycles.json`, `semantics.json`, and the two complete run directories.
