# Native batch 004: combat and mechanics

Updated November 2, 2026. This batch fixes the combat input problem and qualifies
a larger private mixed-native cohort through **61 matched cases**. All 122 fresh
runs use the same frozen executable and generated program, with complete,
zero-loss captures. The 157,560 frames are separate, partly overlapping fixtures,
not a continuous campaign. Interpreter fallback remains available.

## Selected source and build

- Executable SHA-256: `fa3a25028b72443f7998bc6da6a31c845f03adc4444e95ca51525f607db7ea7f`.
- Private graph: `.local/batch-001/native-004/expanded-v2/`; manifest SHA-256
  `5322a4e3f86935b45184bad90fb01026338680287f76bf1ed84d011e9aa6af7f`.
- **312 roots, 1,180 variants: 1,104 eligible candidates and 76 LLE variants.**
  All 231 earlier roots and all 877 earlier eligible variants remain present;
  81 roots and 227 eligible variants were added. These are structural counts,
  not counts of executed or independently qualified functions.
- SNESRecomp `66eebe6ae415b4fb2607a22e5b12352f612e1bdf`, RomAtlas
  `3d0d1393149491777626f5a8e4461f7c49b2d6df` and GaiaLabs
  `f7649eb735aaf19b2cd8f693fdaa6669b3e42711` remain the latest inspected heads.
  Rechecked before publication; no vendor replacement was necessary.

Generation used current residual evidence and independently validated historical
analysis seeds. Each older executable/program identity and its costs remain
separate. No profile was relabeled or overlapping costs treated as campaign
coverage. The owned Windows Job Object retained its 4 GiB/300-second limits;
generation finished in 89.78 seconds with about 164 MiB peak commit and zero
guarded-range violations. The default source build remains interpreter-only;
generated game code stays private and public packaging rejects this executable.

## Combat input correction

The original input normalizer waits on `$4210` and then rewrites raw controller
input into logical actions. Gaia's frame host already supplies a manual vblank
latch once per frame. The shared beam model could supply a second RDNMI edge
during the same host iteration, allowing the normalizer to run again before
NMI refreshed the raw input. The observed attack input became an item action.

The new `snes_set_rdnmi_beam_enabled(bool)` makes ownership explicit, like the
existing raster-IRQ ownership policy. Core beam behavior remains the default.
Gaia selects manual ownership during initialization; beam/IRQ/joypad timing and
PPU field observers continue running. Reading `$4210` still reports and clears
the manual latch, and suppresses stale beam-pending state from older snapshots.
The setting is host policy outside serialized guest state; save layout is
unchanged. No game input table or movement behavior was patched.

A ROM-free fixture executes the actual core and a synthetic non-idempotent
wait/remap loop. It reproduces the duplicate edge with both owners and the
single action with manual ownership. Default beam behavior, disabled NMITIMEN,
stale pending state, read-clear, IRQ preemption and field observers are checked.
The actual game now attacks, damages enemies, clears rooms and awards rewards
through its original routines. In the tested button configuration physical A
is attack and B is the equipped-item action.

Some ability gestures need a held attack while adding shoulder inputs. The
script runner now offers bounded continuous segments:

```text
hold a 180
dump charged
hold a+l+r 40
hold none 1
```

Existing `press` scripts retain their release frame. `hold` preserves shared
buttons between adjacent segments, supports explicit release and accepts only
1–10,000 frames. Actual parser/ticker tests check both timelines and malformed
input. This is a diagnostic script extension, not a movement feature or a
claim that an external oracle understands the new command.

## Native policy refinement

The former polling guard also covered the separate math leaf at physical
`028000..02803A`. Pinned GaiaLabs boundaries and 72 independent RomAtlas M/X
contexts establish a 35-instruction branchless leaf, ending in RTL with M0,
unchanged X width and balanced byte push/pop. Its exclusion also prevented
analysis from proving several hot callers' exit contracts.

Only that 59-byte leaf was separated. The polling guard now starts at `02803B`;
all actual vblank routines, reset/NMI delivery and mutable actor/OAM regions
remain guarded. Its first system-bank hardware store still falls back before
access, so this does not promote math-device timing. The policy now lists
**6,224 explicit PC/alias guards**, plus inherited CFG function exclusions.
In particular, the four Babel NMI-callee `force_lle` entries remain unchanged;
their absence from the manifest is intentional, not lost historical evidence.
Changing WRAM code remains interpreted. [Planning and independent checks](NATIVE-004-PLANNING.md).

## Matched execution

| Case group | Cases | Observed scope |
|---|---:|---|
| Cold natural route, 4:3 and 16:9 | 2 | 6,000 frames each: boot, classroom dialogue/movement and South Cape. |
| Earlier source-backed area entries | 23 | 600 frames each across all four guide parts; original request protocol and changed terrain. |
| Original form returns and inventory | 4 | Freedan/Shadow transformation-and-return sequences, plus Aqueduct/Babel inventory open/close. |
| Actual combat and rewards | 8 | HP, strength and defense at 1x/8x; cleared-room reloads without duplicate awards. |
| Original ability effects | 7 | Dash, slider, spin, projectile, barrier, Earthquaker and Aura terrain descent. |
| Missing-prerequisite controls | 9 | Effects absent with the relevant bit/item absent; two controls retain the base charge capability. |
| Continuous boss encounters | 4 | Castoth, Viper, Sand Fanger and Mummy Queen: actual damage, death and original completion handling. |
| Focused 16:9 stress cases | 4 | Will room clear, Freedan projectile, Shadow Aura traversal and Mummy Queen. |

All cases require matching CPU/WRAM traces, CPU/master totals, memory/PPU/frame
snapshots, DMA/PPU events, complete SPC/RAM/DSP/PCM-ring and scheduler/port-queue
state, executed SPC-event cycles and full final rendered output. SPC host
frame/beam stamps are observer metadata under the explicit `cycles` contract;
CPU event stamps, SPC event order/port/value/sample/executed cycle stay exact.
Strict raw-byte comparison remains available. This is emulator-cycle evidence,
not a hardware or bus-phase oracle.

The cold route reports **12.8307% native CPU cycles in 4:3** and **12.8268% in
16:9**. Its totals are 220,983,983 CPU / 1,492,544,604 master clocks and
221,051,422 CPU / 1,493,019,964 master clocks respectively. The corrected-input
pre-expansion 4:3 baseline was 12.4398%. Batch 003's 13.4210% / 14.0185% came
from the older input/vblank workload and is not a comparable performance
baseline. Native share is partial execution, not host speedup or campaign
coverage. The seven effects and nine controls report 5.2182%–14.8916% by case;
the 12 encounter/reward cases report 5.1689%–15.7383%.

## What the mechanics establish

The original three-bat clear sets its clear flag and raises maximum/current HP
8→9 at 1x and 8→16 at 8x. Shadow clears two other original enemy groups and
receives defense 40→41/48 and strength 40→41/48. Scripts do not write enemy HP,
death selectors, counts, clear bits or reward stores. The original clear and
reward paths produce these changes. [Encounter contracts and assistance](NATIVE-004-ENCOUNTERS.md).
Current HP includes the enabled per-frame refill; this does not independently
qualify the original healing queue or its timing.

Ability fixtures supply explicit learned bits or Aura in an empty inventory
slot, then exercise original actions. Controls distinguish their absence.
Aura actually descends through original Pyramid terrain; Earthquaker uses an
original ledge jump and landing effect. No movement rate, velocity, jump script
or form selector is written. [Effects, controls and limits](NATIVE-004-ABILITIES.md).

Boss fixtures use source-pinned normal incoming requests, actual AI and player
attacks. Player stats/positions and HP regeneration are assisted. Castoth,
Viper and Sand Fanger use 255 strength; Mummy Queen uses 135. These boosts can
overpower high-defense phases, so normal weakness timing, difficulty and
balance are not qualified. Mummy entry uses the original COP-26 payload and
does not establish completion of the Pyramid portal puzzle.
[Sand/Mummy details](NATIVE-004-BOSSES.md).

Actor slots can be reused after an outro. Castoth/Viper replays therefore also
require fresh HP-zero writes in both modes at the witnessed frame, bank,
address, value and width. The interpreted event must match its original source
PC; the native event is not identified through a stale interpreter-PC label.
Defeat bits/counts and the complete state/output comparisons remain required.

The reusable [mechanics replay runner](../scripts/replay_gaia_mechanics.py)
preflights every private script, seed and witness artifact by SHA-256 before
execution. It runs a new same-binary interpreter/native pair and checks all
three comparisons with the frozen witness. Semantic observations carry only
through matching inputs, traces, states and output; a recorded boolean is
insufficient. Watched hit events must occur in the fresh logs. Widescreen
stress cases assert their source outcomes anew instead of inheriting a 4:3
image comparison. All four full outputs are 342×224.

## Checks, failures and continuation

- 694 Python tests passed, two existing compiler-path skips, 243 subtests.
  This includes 24 replay-policy tests and actual script parser/ticker tests.
- Current-source standalone contracts pass: 432/432 bridge checks in each bus
  mode, 27 interrupt-tail checks and CPU bus/latch checks.
- RomAtlas: 8,192 contexts, zero mismatches; 5,070 identity/byte-matched reused
  checks and 3,122 new decodes. All 248 cartridge transfer targets were checked;
  three mutable WRAM targets remain unverified. The math leaf also passes a
  separate 72-context check. Structural counts are not runtime proof.
- Seven packaging-policy tests pass. No release or game-data package was made.

Failed discovery probes remain failed, including an overly weak defense
setup, a wrong byte/word interpretation in a portal prerequisite, missed
boss geometry, cancelled early charge gestures and an initially incorrect
ability-disabled fixture. The original 3,000-frame Freedan regression exited
before its transformation committed under corrected input timing. Its revised
fixture waits for actual form/control state before exiting; the complete
sequence and return now pass. No failed receipt was rewritten as a success.

```powershell
./scripts/build_windows.ps1 -NativeBatch .local/batch-001/native-004/expanded-v2 -Jobs 2
# Force retained interpretation in that private executable:
$env:SNESRECOMP_INTERPRET_ALL = '1'
# Permit native execution again:
Remove-Item Env:SNESRECOMP_INTERPRET_ALL
```

Replay with immutable copied inputs and a fresh private output directory:

```text
python scripts/replay_gaia_mechanics.py --binary .local/batch-001/native-004/expanded-v2/inputs/babel-recomp.exe --rom "Illusion of Gaia (USA).sfc" --plan .local/batch-001/native-004/replay/abilities-plan.json --output .local/batch-001/native-004/replay/another-ability-check
```

The binary, plans, seeds and output must resolve under this project's ignored
`.local` tree; the verified owner ROM is read-only. Current proof index:
`.local/batch-001/native-004/selected-proof-index.json`. The replay reports,
`final-regression-summary.json`, wide receipts, source receipts and retained
failures are under that same bounded scratch batch. Original Babel author
mr0ta / mrOt4, existing credits and license notices are preserved.

Remaining work includes naturally earned abilities and story progression,
unboosted boss weakness/timing, more puzzles/areas and aspect ratios, physical
input/audio, external-reference accuracy and campaign completion. The seven
ability effects do not establish every associated hit, guardian stun or puzzle.
No achievement unlock or full-native claim follows from these assisted tests.
