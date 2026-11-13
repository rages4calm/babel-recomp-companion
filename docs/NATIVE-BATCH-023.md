# Native batch 023 — immutable actor code and broader script coverage

Source baseline `58411f46ec4a6eeca66baf8fda93ed3eb1860b68`, November 13, 2026.
Private candidate SHA-256:
`fff8e726b3dff92ec5b04a34b32334c36808e95e1ed96fc50f4bb582660c01b8`.
Development source update; owner installation remains 005. Interpreter/reference
paths and the old lookup remain available. All native activation switches default
off. SPC700 remains interpreted.

## Selection and boundaries

The retained 148-route results exposed 13,424,794 interpreted cycles. This batch
selects **9,576 new exact physical PC/M/X/E contexts**: immutable actor/OAM code
and ordinary scripts, including Layer1DriftUnbounded and Nitropede's
WaitWhileOffscreen COP. Independent RomAtlas validation covers 9,577 proposed
contexts: 9,079 fresh decodes and 498 exact byte/mode/address-bound batch-004
reuses. Unchanged title policy rejects one reset trampoline before emission;
its twelve historical cycles stay interpreted. Source labels and static decoding
do not grant execution ownership.

All previous 65,523 ROM descriptors and twelve WRAM descriptors remain literal.
The new total is **75,111**: 75,099 ROM plus twelve WRAM. New contexts are
scheduler-only, with 1,322 explicit frame permissions and zero new NMI grants.
The old 4,084 ROM and four WRAM finite-owner NMI grants remain. Six passive probes
using the old admission policy (36,800 frames) preserve full CPU, devices, raw
APU/info and every old native count. Of 2,727 proposed contexts seen there, six
were NMI-only and deliberately left unpromoted. The separate metadata readback
is structural/ownership evidence, not native execution proof.

Actor instructions require explicit owner scopes. Any instruction whose byte
span intersects one of the ten live culling operand words is excluded from
immutable selection in all four aliases. Those twenty bytes need a separately
qualified live-operand contract. The four whole-function AOT guard ranges, five
RDNMI exclusions and existing runtime exclusions remain unchanged. This batch
adds no owner class, opcode, dynamic-code exemption or whole-function promotion.
Live-byte, mode, mapper, hook, pending-event and retirement checks remain.

## Registry and core proof

The old 65,535-entry registry was full. Host descriptor slot IDs and legacy page
starts become 32-bit, with a bounded **131,072-entry** capacity. Page IDs/counts
stay 16-bit: current eligibility allows at most 36,640 pages and 1,024 E0 PC/MX
slots per page. These tables are not saved CPU data; public ABI and save layouts
remain unchanged. Both lookup representations are constructed before commit.
Allocation failures retain the old descriptors, statistics, permissions and cache.

Four focused tests execute fourteen actual reference/native pairs across both
lookups, including IDs 65,535, 65,536, 65,537 and 131,072, plus a legacy range
start of 65,538. All 264 assertions pass; two activated 16-bit truncation faults
are rejected. Mixed ROM/WRAM/frame/NMI/scope data and used counters survive merges
and idempotence. Three allocation-failure stages, over-capacity 131,073 and
conflicting/late-E1 inputs refuse atomically. Seven migrated boundary checks
also pass. An earlier synthetic fixture lacked its new opcode byte and correctly
failed live-byte validation; that attempt remains failed and separate.

The full SDK gate passes **972 tests, two skipped, zero warnings**, with all 786
source files unchanged; 974 tests are collected. Separate title-policy nine,
immutable-actor five and alias-recipe eight tests pass. The entire bridge
executable matches the previous source except the exact internal capacity
migration. Metadata validators, dispatch, owners, event/bus retirement, headers,
snapshots, interpreter, poll and title activation remain unchanged.

The immutable batch-016 graph and single batch-018 build tree are reused, with
no graph regeneration, installation, release or CPU benchmark campaign. Every
previous ROM wrapper, 3,317 shared body groups, 100 helper definitions and old
grant/scope row remains identical, normalizing only numeric shared-body names.
Re-emitting the old selection reproduces source SHA-256 `91c5d768…` exactly.
The new 4,298 shared bodies and all ROM-derived generated C remain private.

## Presentation regression and live culling controls

The unchanged modern renderer passes 22 captures / 71,500 frames across original
classroom doors, town, combat, boss and unsupported-scene controls. Seven ready
pairs cover six positive scene IDs; one Castoth object refusal and two additional
native-256 controls remain explicit. Original source-packet, OAM, ROI, device and
CPU checks pass. There are no new admissions or full 61-format refresh claims.

Two additional legacy widescreen pairs use genuinely earned Dark Friar and
armor-plate inputs: four captures / 14,800 frames, actual culling margin 43 and
20,979 new immutable actor instructions. Full CPU, actual patched operand values,
devices and executed-APU/full-state/PCM/queue comparisons pass. Twenty raw SPC
observer differences and zero info differences remain. Both tiers share the
legacy widened gameplay mode; this does not establish original-256 culling/RNG
equivalence. The initial Town control passed CPU/devices but executed no new
actor code, so its positive-coverage assertion stays failed. Known positive
inputs were used without replaying Town. Modern stock-culling checks are unchanged.

The original 4,400-frame MSU opening and 240-frame NVIDIA 1080p xBR/1.5x check
pass. Checkpoint and displayed image are byte-identical to batch 022. The opening
executes 396 new contexts / 1,017 instructions / 3,681 cycles; old WRAM counts
remain 15,434 instructions / 106,646 cycles. This verifies audio consumption by
a dummy device, not physical listening or sustained FPS.

## Matched gameplay and expanded outcomes

The independent matched 148-route suite passes 296 captures / 869,400 frames /
2,414 snapshot sets. It rehashes 44,186 input/output files and binds the unchanged
SDK sources, full CPU/device checks and fresh inherited 43 semantic reviews.
Every old ROM/WRAM per-site count, NMI/poll count and CPU/master-clock total
remains exact. Each new site's previous interpreted instruction/cycle decrease
matches its new native count; zero attribution exceptions.

| Same-route cohort | Previous interpreted cycles | Current interpreted cycles | Reduction | Current native guest CPU |
| --- | ---: | ---: | ---: | ---: |
| Original 105 | 4,232,373 | 3,893,264 | 8.0123% | 99.959761% |
| Retained 129 | 9,519,673 | 5,122,822 | 46.186996% | 99.960039% |
| Full 148 | 13,424,794 | 6,681,281 | 50.231780% | 99.958031% |

Of the 9,576 added contexts, 9,570 execute 1,762,752 instructions / 6,743,513
cycles; six remain unobserved and receive no execution credit. All 371 immutable
actor contexts execute 1,259,719 instructions / 4,302,945 cycles. These are subsets
of the new-context totals, not additional work. All twelve old WRAM and fourteen
old ROM MVN contexts still execute, with unchanged per-site counts.

The 1,206 raw SPC host-observer file differences and 17 cached-beam info
differences remain recorded under the existing comparison scope. Captured APU
executed-cycle/CPU-port order/full-state/PCM/queue checks remain unchanged. There
are no new masks, waivers or claims of continuously synchronized hardware beams,
continuous SPC state or hardware waveform equivalence.

**23 new assisted positive/control pairs** pass independently on this candidate:
46 captures / 351,200 frames / 342 snapshot sets, with 171 exact original-256
field comparisons totaling 9,805,824 pixels. They cover:

- Inca statue placement and its missing-statue refusal; genuinely earned Wind
  Melody, the uninterrupted 600-tick floor puzzle and its interrupted reset.
- Six real lithograph pickups and full-inventory refusal; Jackal/Lola's flame
  sequence and its no-melody control; correct/wrong hieroglyph arrangements.
- Angkor's vision and Flower gift, full-inventory Herb exchange, Gorgon's three
  petals/girls/jewel outcome and a two-petal control.
- Actual jewel deposits reaching fifty, stock secret-mansion door/intro, and
  forty-nine refusing entry.
- Red/blue wire choices and the original timeout-dud dialogue from an earned
  post-Vampire-kill checkpoint.
- Earned Earth Quaker freezing an on-camera, nonimmune enemy, actual HP 8→0 and
  room count 39→38. The control retains live HP8 and movement; the original quake
  timer thaws normally.

Both tiers must produce the actual stock item, flag, inventory, interaction,
damage and transition writes specified by each scenario, alongside full CPU,
devices/APU and exact original-256 field checks. Disclosed teleports, prerequisite
flags/inventory and player stats are assistance. There are no enemy HP/death/count,
victory/quest-counter, actor-PC or NPC-position outcome edits. Actual writes and
dumps are authoritative; a test comment saying DEF255 while the actual input is
DEF0 is disclosed without rewriting the frozen input. Earlier deaths, missed
interaction radii and premature snapshots remain failed/unqualified attempts.

The Vampire checkpoint follows a genuine kill with an observed active countdown.
One enemy had already died before the timer started, so it does not prove both
started at full HP at that instant or a clean first-hit sequence. Wire follow-ons
are not counted as another boss victory. Stock timeout with zero enemies follows
the dud-dialogue branch, not player death.

The two planned Aura scenarios remain **unresolved and unqualified**: no required
orbs/arrows were observed, enemies were off-camera and a control retained dialogue.
The ability was already present; the exact failure cause is not established.
There is no inferred guard-success or confirmed engine-bug claim. The final source
exploration is closed: 43 engine attempts / 301,928 frames including failures,
refinements and the 9,750-frame Vampire primer, below the 320,000-frame ceiling.
Those source-baseline runs are separate from fresh candidate qualification.

The expanded qualification is **171 pairs / 342 captures / 1,220,600 frames /
2,756 snapshot sets**. The added 23-route cohort reaches 99.513670% native
guest CPU; the combined 171 reaches 99.836466%. The retained 148 remains
99.958031% on its unchanged denominator. The first eleven harder additions
separately reached 98.989863%; their original receipt remains unchanged.
Across the expanded cohort, 9,570 new contexts execute 1,908,408
instructions / 7,492,836 cycles. Separate per-group, 105/129/148, added-23 and
expanded-171 receipts remain. These percentages describe their particular routes,
not campaign or project completion.

The new cases retain 171 raw SPC observer-file
differences and 0 raw info differences;
the combined totals are 1,377 and
17, respectively. Existing exact
CPU/device/executed-APU/port/full-state/PCM/queue criteria are unchanged.

## Remaining native work

Use the expanded `counter-audit-additions/combined171-v1/remaining-union-v1.json`
as the primary next-batch input. Its 35,838,335 interpreted cycles include
26,006,938 unregistered ROM/mode cycles and
8,702,595 guarded RDNMI cycles. The largest unregistered
site is `83AA6A` / M0X0 / E0 (1,038,016 cycles).
Its opcode, source identity and owner are unqualified, not inferred from the
address. Broader source/owner/byte/mode evidence is the next priority. This
expanded corpus exposes additional work; the matched 148 results stay unchanged.

The same 148 routes separately retain 6,681,281 interpreted cycles:

| Category | Interpreted cycles |
| --- | ---: |
| Existing RDNMI acknowledgement/poll exclusions | 6,121,885 |
| Previously registered ROM contexts refused at runtime | 403,494 |
| Instructions overlapping live actor culling operands | 126,780 |
| Newly registered contexts refused at runtime | 28,666 |
| Other ROM/mode, unsupported actor SP writes and reset/IRQ policy | 456 |

Registered refusal categories identify sites, not their exact instance-level
causes. The next batch needs passive causal evidence and a separately qualified
live-operand contract; do not remove owner/event/mode/byte guards to inflate
coverage. The five RDNMI sites remain outside this immutable registry. Separate
105/129/148 and added-outcome denominators are retained. These are guest CPU
coverage figures, not project-completion, host speed, native SPC or campaign proof.

## Tools, preservation and cleanup

Official SNESRecomp main remains `80a41241e39bfffd384506fbe7ca65b386e03050` and
Gaia baserom remains `e825dddde466c73cb9900c2c04a7d2bfa37ed165` at the final
November 13 readback. No vendor replacement was needed. Issues 265 and 285 remain
open with zero comments. No new confirmed repository bug arose in this batch;
initial selection, synthetic-fixture and snapshot-timing failures remain
explicit failures rather than upstream defects.

Qualified Python 3.14.10, Clang 22.1.8, CMake 4.4.5 and Ninja 1.13.2 are reused.
RomAtlas main `23521a5743b1cf8ce36c818b482f683068380acd` has the same thirteen
crate/vendor/lock trees as the qualified decoder plus its recorded Windows
assembler-refusal patch. This is reuse of the qualified binary, not a fresh build
of main. GaiaLabs source/flag evidence informs tests; private developer ROM,
patch, widescreen and audio inputs remain private. Existing author credits and
licenses are preserved.

Cleanup complete: 32,205 obsolete files removed in place, 9,407,344,680 logical
bytes / 3,127,474,696 reported last-link file-data bytes, zero locks or errors.
This combines 231 old SDK EXE/OBJ files and 31,974 old batch-022 native capture
payloads, after independent replacement qualification and all reader releases.
All 12,619 protected files in the native cleanup stay byte/identity/time-exact,
including 2,414 info JSONs, owner39, normal28PCM, fifteen compact dependencies,
the Gem30 scout seed and current/prior runnable masters. All states, seeds,
metadata, logs, source, failures and both old renderer suites remain. Three
retirement markers preserve historical proof status; retired raw is unavailable
as a golden. No archive, move, whole-project rescan or retry CMD was needed.
Logical size and reported file-data allocation are not whole-volume recovery.
