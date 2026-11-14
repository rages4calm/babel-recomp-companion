# Native batch 025 — NMI acknowledgements and boss scripts

Source baseline `672b153689d97fdfd238956c853817f971cff8b2`, November 13, 2026.
Private candidate SHA-256:
`194d65974e55cdc90e56e3b0780885e7bc1f0986d255ad1e40ec2eb8d4b097ee`.
Development source update; owner installation remains 005. Interpreter/reference
and the old lookup remain available; native activation switches default off.
SPC700 remains interpreted. No CPU benchmarks ran.

## What changed

The previous 185-route profile contained 13,767,490 interpreted guest cycles.
This batch selects **887 exact physical PC/mode contexts**: 884 supported boss/
script contexts (2,672,069 previous interpreted cycles) and three RDNMI-register
acknowledgements (9,679,040 cycles). That 12,351,109-cycle sum is a selection
ceiling on the old corpus, not runtime credit or a host-speed measurement.

The 884 include Solid Arm's child/vector loops, actor flag operations, Great Wall
archers, world-map exits and Sky Garden platform code. Independent RomAtlas
checks cover 875 fresh decodes plus nine exact identity/byte/mode-bound reused
decodes; all three acknowledgements receive fresh independent decoding. Source
annotations use actual containing GaiaLabs blocks, rather than unrelated nearby
labels. Neither labels nor decoder success grant ownership.

Old 78,449 ROM and twelve WRAM descriptors remain literal, giving **79,348 total**
within the unchanged 131,072 capacity. New contexts have scheduler-only scopes;
396 COP/RTI frame permissions are added, with zero new NMI permissions. All old
4,084 ROM/four WRAM NMI permissions remain. Original interpreter, bridge, emitter,
poll island, owner/event/mapper/live-byte/hook checks, save layouts and ABI are
unchanged. All 524 compiled production-source files match batch 024. The immutable
batch 016 graph and single batch 018 build tree are reused.

The generated effect file has 4,721 shared bodies and 79,336 ROM wrappers.
Independent preservation checks compare all old 78,449 wrappers/descriptors,
4,690 body groups and 156 helper definitions, plus old grants/scopes and the
registration tail. Only numeric shared-body names are normalized. Generated
ROM-derived C and validation inputs remain private.

## The three acknowledgement permissions

The five protected RDNMI PC entries remain in the policy. A new explicit
exception permits only physical **828049 / 828053 / 828195, M1X0/E0**, exact
`AF 10 42 80` LDA bytes, scheduler scope 1 and no NMI grant. These are the original
pre-poll/post-poll and NMI-enable acknowledgements. Other aliases, modes, shapes
and owners remain protected. The original 82804D/828051 poll island is untouched;
no iteration, fetch, register read, guest frame or retirement event is skipped.
The four whole-function AOT barriers and twenty live culling operand bytes stay.

Eight fresh focused tests exercise real modeled Snes/APU/SPC/DSP/DMA devices,
full CPU/WRAM/low-memory state, ordered bus accesses and original retirement.
Four positive flat/outlined/lookup variants execute **9,576 reference/native
pairs / 443,764 checks**, including 9,408 accepted single-read pairs and 168
refusal pairs. Twenty-four refusal pairs use real pushed ordinary/native-NMI
handlers through RTI. Four activated skip-read faults are each rejected with
8,691 failures. Deadline 1..48/2200, fast/slow ROM, pending/host/beam latches,
code/mode/mapper/owner/exclusion and pre-opcode hook controls are covered.

The first new fixture had an incorrect terminal-latch expectation: a later beam
edge can relatch RDNMI after the read. Its failure remains retained. The corrected
fixture observes the actual immediate read-clear and preserves full final-state
comparison, including later edges; no production behavior or guest comparison is
waived. This is real-device fixture proof, not the entire production AOT/cart bus
or independent silicon-latency proof.

Thirteen title-policy, eight alias and five actor-policy tests also pass. The
prior 972-pass/two-skip/zero-warning SDK result and prior eight Mode 7 tests are
**reused, not fresh**. All 786 earlier SDK sources and the Mode 7 test are byte-
exact. The new test makes 788 source files; collection reports 990 tests, not a
fresh full-suite execution. No unnecessary full-suite or benchmark loop ran.

## Matched execution

Independent fresh qualification passes **185 pairs / 370 captures /
1,356,600 frames / 3,114 checkpoint sets**. Every old 78,449 ROM/twelve WRAM per-site
count is exact; each new site's native work exactly replaces its former
interpreted work. Old CPU/master/poll/NMI/WRAM totals are preserved. **All 887
additions execute** 2,452,003 instructions / 12,337,381 cycles: the 884 script
contexts execute 518,939 instructions / 2,672,061 cycles, and the three
acknowledgements execute 1,933,064 instructions / 9,665,320 cycles.

On the **same 185 routes**, interpreted cycles fall **89.612420%**, from 13,767,490
to 1,430,109, reaching 99.994153% native guest CPU. The original 105/129/148/171
subsets separately reach 99.997673% / 99.997316% / 99.996443% / 99.994562%; only the
acknowledgements add native work on those earlier 171 routes. The 884 script
additions execute in the last fourteen inherited scenarios. All 887 are observed,
but other instances can still be refused by the unchanged runtime guards.

Adding NEW 10 gives **195 pairs / 390 captures / 1,415,200 frames / 3,200 sets**,
99.989589% native guest CPU, and 2,574,822 instructions / 12,982,249 cycles at the
887 additions. NEW 10 separately reaches 99.891208%; denominators are not rewritten.
Its harder scenarios expose new interpreter work. The union only aggregates
sealed independent results, without repeating raw CPU/APU comparisons.

The retained 185 has 1,554 raw SPC host-stamp file differences and 18 cached-beam
info differences; combined 195 has 1,597 and 18. Raw values remain unmodified.
Retained info differences were verified to contain only the existing cached
hpos/vpos fields. NEW 10 adds 43 host-stamp differences and zero info differences.
All inherited 80 semantic scenarios are freshly reviewed on this candidate.

These percentages concern measured 65816 guest execution, not project completion,
host speed, native SPC or a complete campaign. Existing full CPU/device/executed-
APU/CPU-port-order/state/PCM/queue criteria remain; raw host-stamp and cached-beam
metadata differences stay explicit and unnormalized. No new masks or global
beam/hardware-waveform claim is introduced.

## New areas and boss phases

All **ten new assisted pairs / 20 captures / 58,600 frames / 86 sets** pass
independently. All 43 original-256 fields match, totaling 2,465,792 exact pixels.
Their separate native guest CPU share is 99.891208%. Of the 887 additions, 138
execute 122,819 instructions / 644,868 cycles in NEW 10; their subset is not added
again to the combined totals.

- Solid Arm's upper-claw phase and distinct left/right child follow/vector
  phases, with a living player, published moving children and original damage
  writers. Boss HP is not edited; a generic fan or win does not substitute.
- Mushroom Water's original bridge flag/item consumption and wrong-region
  refusal control.
- The fourth Sky Garden platform from the genuinely earned three-crystal state:
  original fourth writer, crystal consumption, movement and actor reveal.
- Genuinely earned Magic Powder, original chest/fanfare and Kara rescue flags,
  followed by the authored annex handoff. A separate wrong-region control retains
  the earned item. This narrow handoff fixture **does not prove free control in
  the annex**; the original full-return goal remains unresolved.
- Shadow's original Aura terrain 04 descent/landing, versus the wrong-terrain
  abort and restored position/control. Form 2 is genuinely earned; item 0x24 is
  disclosed prerequisite inventory assistance in both cases, not an earned-item
  claim.

Source exploration closes at **20 actual attempts / 63,700 frames**, including all
failures and refinements, below 90,000 allocated/120,000 maximum frames. The
original fourteen goals have nine passes and five unresolved goals: two Aura
orbital-damage/control setups, two Mine NPC-interaction setups and the strict
Kara free-control return. The distinct narrow handoff is the tenth fresh candidate
fixture, not a relabeled pass for the failed original goal. No further source
loops ran. Earlier castle/Euro exit approaches remain unqualified as well.
All failed inputs/receipts and actual integer-coordinate readbacks remain;
source-baseline attempts are not fresh candidate frames.

Private source attempts and assistance remain separate from fresh candidate
execution. No enemy HP/death/count, victory/quest-counter, actor-PC or NPC-position
outcome pokes are used. Original game writers produce the tested results;
prerequisite inventory, teleports and player-stat assistance are disclosed.

An evaluator import collision stopped the first producer after four fresh pairs
had passed guest parity. The failed producer remains failed. Absolute imports
and a versioned lineage recover only the intended pure predicate, then run the
remaining two pairs without replaying the first four or repeating their raw
parity comparisons. The independent auditor checks actual project-function
provenance before reading raw payloads; substitution of the wrong historical
quest function is rejected. Completed groups receive one independent raw audit,
and the final union aggregates their sealed results.

## Display, music and fallback

The unchanged renderer passes a fresh **22-capture / 71,500-frame** critical set:
original lesson, both doors and town return, combat/boss, seven ready pairs across
six positive scene IDs, one Castoth object refusal and unsupported-scene controls.
Source packets/OAM/ROI/CPU/devices retain the established checks. A further
**three captures / 12,000 frames** verify the actual Mode 7 original field and
padded-wide fallback: all 57,344 original pixels and the stock matrix match.
During that route the three new acknowledgements execute 10,656 instructions /
53,280 cycles; the 252 existing perspective contexts are retained coverage.
There are no new renderer admissions. Earlier 61-format/110-pair proof remains
historical, and the entire old 021 renderer 44 raw suite stays.

Cold MSU opening 4,400 frames and actual NVIDIA 1080p xBR/1.5x output 240 frames
pass. Seed and image are byte-exact to 024; all old 78,449 ROM/twelve WRAM cold
per-site counts remain exact. The three acknowledgements execute 12,148 native
instructions / 60,740 cycles in the opening; none of the other 884 additions run
there. MSU consumption uses a dummy audio device, not physical listening or a
sustained-FPS test. Original classroom geometry stays. The ignored
`native-025/Play Original Classroom.cmd` pins this executable with MSU, 1080p xBR
and 1.5x extent; the owner installation is unchanged.

## Remaining work, tools and retention

The new primary input is the sealed combined 195 ranking, with **2,664,242
interpreted cycles**. Keep the matched 185 ranking (1,430,109 cycles) and earlier
105/129/148/171 rankings separately.

| Remaining category | Guest cycles |
| --- | ---: |
| Old registered sites interpreted; instance cause not captured | 1,460,737 |
| Unregistered ROM/mode contexts | 1,059,735 |
| Mutable actor operands excluded | 127,504 |
| New acknowledgement sites interpreted; instance cause not captured | 15,715 |
| Unsupported stack-pointer operations | 316 |
| Actor stack-pointer operations | 194 |
| Reset/IRQ policy | 30 |
| Other new registered sites interpreted; cause not captured | 8 |
| Unknown actor source span | 3 |

The largest new unregistered sites are 8B9C7F/8B9C8C/8B9CBA, M0X0, with 205,872 /
123,612 / 123,252 cycles. Their opcode/source/owner are not inferred or admitted.
Registered interpreted totals identify sites, not captured refusal causes.
Original 185 now has zero unguarded unregistered-ROM cycles on its own corpus;
the new scenarios expose the next families. Investigate actual source and passive
causal evidence while keeping fallback and owner/event/live-byte checks. Native
SPC, campaign coverage and further renderer/remake work remain.

Official SNESRecomp 80a41241e39bfffd384506fbe7ca65b386e03050, Gaia baserom
e825dddde466c73cb9900c2c04a7d2bfa37ed165 and RomAtlas b9ae425dd6546741f2ec41e36bda9543910287de
remain unchanged at the final November 13 readback. Issues 265/285 remain open with
zero comments. The qualified RomAtlas decoder is reused against the already
documented data-only source delta; no new-main binary build is claimed. Qualified
Python 3.14.10, Clang 22.1.8, CMake 4.4.5 and Ninja 1.13.2 remain; no installs or vendor
replacement occurred. Babel/mr0ta/mrOt4, GaiaLabs and all original upstream
credits/license notices are preserved.

Private disk-limit and import/fixture failures are retained with versioned
corrections; they are not reported as upstream engine bugs. The disk ledger's
initial namespace copy also changed 1024 to 1025; producers were held before more
captures and the original files/tests/receipts were preserved as failed. The only
prior source capture stayed below the intended limit. Ten independent literal
boundary tests now enforce the original 9 GiB hard limit. A first-pair allocation
gate also stopped before a second main launch; immutable payloads passed all
checks, and comparable later allocation reports satisfied the same planning
threshold. A versioned resume ran only the other 184 pairs. No guest criteria,
inputs, storage hard limit or failed receipt were rewritten.

Completed cleanup removes **45,121 obsolete passed raw files /
13,564,669,962 logical bytes / 4,432,448,528 reported last-link file-data bytes**,
with zero locks or errors. This replaces old 024 native 185 and renderer 25 payloads,
after exact plans/identity guards, preview, current replacement proofs and every
reader release. All 17,547 protected files retain their hashes, IDs, sizes
and modification times. All 3,402 historical info JSONs, source, receipts, profiles,
journals, logs, states/seeds, scouts, failures, owner 39/normal 28 PCM tracks,
compact 15 inputs, graph and current/prior runnable masters remain. Entire 021
renderer 44 and all current 025 raw remain. Retirement markers identify unavailable
old goldens without rewriting original passed receipts. No archive, move, broad
rescan or retry CMD is needed. Reported file-data allocation is not whole-volume
free-space change. Current 025 closes with zero pending capture reservations below
the unchanged 9 GiB hard limit.
