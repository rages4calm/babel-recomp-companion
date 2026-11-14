# Native batch 024 — Mode 7 perspective and world-map coverage

> Historical receipt. [Batch 025](NATIVE-BATCH-025.md) retires this batch's passed
> native185 and renderer25 raw after fresh replacement proof and reader releases.
> Source, metadata, failures, scouts, states/seeds and runnable masters remain.
> Original retention statements below describe the earlier closeout. Retired raw
> is unavailable as a golden; entire 021 renderer44 remains.


Source baseline `cc984267df0d98ba5a8c68e678e4434520a23535`, November 13, 2026.
Private candidate SHA-256:
`172ff8743f08c0edc02abf54bc2c5fefefa09385b65251d75201d50765dea1aa`.
Development source update, not a release or installation. Interpreter/reference
and the old lookup remain available; native activation switches default off.
SPC700 remains interpreted. No CPU benchmarks ran.

## The native batch

The expanded 171-route baseline exposed 35,838,335 interpreted guest cycles,
including 26,006,938 in 2,436 unregistered PC/mode contexts. Existing fixed-effect
support covers 2,434 of them: a 26,006,680-cycle ceiling, not execution credit.
Two unsupported stack-pointer operations stay interpreted: TXS at `82A328` and TCS
at `80801E`, totaling 258 cycles on that particular corpus.

Successful new world-map travel/Quit source runs expose another 916 supported
contexts, including 87 more in the perspective block. Their 12,048,456 source-case
cycles are a separate denominator. The selected batch is **3,350 exact physical
contexts**. Independent RomAtlas decoding covers all 2,434 original additions
and all 916 source additions, with zero mismatches. Source annotations identify
Mode 7 perspective/scanline work; annotations do not grant ownership.

All old 75,099 ROM and twelve WRAM descriptors remain literal. New totals are
78,449 ROM + 12 WRAM = **78,461**, within the existing 131,072-entry capacity.
There are 892 new explicit frame permissions and zero new NMI grants. All new
contexts have scheduler-only scopes; old 4,084 ROM/four WRAM NMI grants stay.
The four whole-function barriers, five RDNMI exclusions, twenty mutable culling
operand bytes, live-byte/mode/mapper/hook checks and runtime event/owner guards
are unchanged. No opcode, permission class, ABI, save layout or engine mechanism
was added.

The immutable batch 016 graph and single batch 018 build tree are reused. Public
production code, generator, policy and all 524 compiled-source files match the
qualified previous build byte-for-byte. Outlining shares 4,690 bodies behind
78,449 wrappers. Preservation checks compare every old 75,099 descriptor/wrapper,
4,298 body groups and 156 helper definitions, plus all old grant/scope rows and
registration code. Only numeric shared-body names are normalized. Generated
ROM-derived C and validation inputs remain private.

## Word-I/O proof and diagnostic limits

The dominant work uses sixteen-bit hardware-divider accesses, including STY at
4206 also writing 4207 (H-IRQ timer low). Existing real-peripheral tests covered
byte APU/DMA accesses; earlier word-claim tests used a synthetic bus. New
`test_native_mode7_mmio.py` closes that specific gap with **eight focused tests**:
flat/outlined emission and both lookups, claimed-word and scalar-refusal paths,
normal/zero divisors, H-timer bit 8 controls and 111 deadline boundaries per case.
Four positive variants execute 3,552 reference/native pairs and 167,044 checks.
One generated fault masking the high write byte is activated in four variants;
all reject it while scalar controls remain unchanged.

The fixture counts the six actual 4204/05/06/07/4214/15 byte accesses independently
of byte hooks and checks full CPU/Snes divider/comparator/pending state,
APU/SPC/DSP/DMA/WRAM, bus order/values, master/access-lead clocks, retirement and
counter conservation. This extends the established real-Snes-device fixture;
it is not the entire production AOT/cart bus, IRQ-handler delivery or a silicon
latency claim. All twelve compiled production C files remain unchanged.

The prior full SDK result—972 passed, two skipped, zero warnings—is **reused,
not fresh**. All 786 existing source files remain byte-exact. The only added
public code is the new test file. Collection confirms 982 tests (the previous 974
plus eight new tests); the full suite was not needlessly rerun. The fresh focused
test execution and current game qualification are separate evidence.

A private ownership/fetch observer made two 14,000-frame captures with unchanged
admission. Both matched the old executable's full guest CPU/devices/rawAPU/info
and old per-PC counts, but their byte-collection guards failed: first on adrImm
reads, then on a duplicated BIT immediate classification. Claimed-word MMIO
also bypassed its scalar taps. The failed guards remain failed; zero tap counts
do not mean absent MMIO. Only 607 owner keys were observed (597 scheduler, ten
finite-NMI); no complete three-case, byte-fetch or MMIO proof is claimed. There
were no further probe loops. Conservative unchanged runtime guards, the focused
word-device tests and fresh game execution qualify actual accepted work.

## Matched game execution

Independent fresh qualification of the retained **171 pairs / 342 captures /
1,220,600 frames / 2,756 checkpoint sets** passes. Of the 3,350 new contexts,
2,408 execute 6,846,413 instructions / 25,956,056 cycles on these routes. Every
old 75,099 ROM/twelve WRAM per-site count is preserved; each new site's native
work exactly replaces its previous interpreted work, with zero exceptions.

On the same 171 routes, interpreted cycles fall **72.425396%**, from 35,838,335
to 9,882,279. Native guest CPU reaches **99.954906%**. The earlier 105/129/148
subsets stay unchanged this batch at 99.959761% / 99.960039% / 99.958031%; the new
selection targets the broader 171 frontier rather than repeating their gains.

Adding the fourteen new scenarios gives **185 pairs / 370 captures / 1,356,600
frames / 3,114 sets** and 99.943708% native guest CPU. Across that union, **3,324
of 3,350 additions execute** 19,237,441 instructions / 70,700,566 cycles; the 26
unobserved contexts get no execution credit. All 916 source additions execute.
The NEW 14 cohort separately reaches 99.847186%. The final union aggregates sealed
independent results; it does not repeat full 171 raw/APU comparisons.

These guest-cycle figures are not host speed, project completion, full-campaign
or native-SPC percentages. Existing device/executed-APU/CPU-port-order/full-state/
PCM/queue criteria remain. The retained 171 has 1,377 raw SPC host-stamp file
differences and 17 cached-beam
info differences; the combined 185 has 1,554 and 18. Actual raw values remain
unmodified. All 17 retained info differences were independently verified to
contain only cached hpos/vpos fields; NEW 14 retains its separately reviewed
single info difference. These metadata observations do not waive guest checks.
No new comparison masks or global beam/hardware waveform claims are introduced.

## Fourteen new functional scenarios

All fourteen new assisted pairs pass independently: **28 captures / 136,000 frames /
358 snapshot sets**, with 179 exact original-256 field comparisons totaling
10,264,576 pixels. Their separate weighted native guest CPU figure is 99.847186%.
All 916 new source-derived contexts execute in the first two travel/Quit cases:
3,378,219 instructions / 12,048,456 cycles. Across NEW 14,1,325 of all 3,350 additions
execute 12,391,028 instructions / 44,744,510 cycles. The other twelve quest/phase
cases add functional coverage and execute zero of the new contexts; they receive
no new-native-coverage credit. These are separate from the retained 171 corpus.

- An original Itory→South Cape world-map trip traverses all four rotation
  quadrants, publishes the stock matrix/HDMA tables and reaches the real
  destination. A separate original Quit control returns to Itory.
- Crystal Ring 0x27 pickup and full-inventory refusal; Purification Stone stock
  cutscene/flag 70 and wrong-region control; Teapot parent-reveal/flagA8 and
  departure with its wrong-region control.
- Viper's distinct left/right hit-callback paths and real boss/player damage;
  Solid Arm's lower projectile-fan phase with a living player and original
  player-damage writer. These are distinct phase checks, not repeated wins.
- A genuine three-crystal platform state with the fourth flag still clear and
  duplicate crystal retained.
- Narrow Aura activation/orbital lifecycle versus the no-LR control. This is
  neither earned-unlock, orbital-damage nor projectile-guard proof; those
  original combat goals remain unresolved.

The other unresolved scenarios are Solid Arm's upper-claw setup (player died
before a late boost), the fourth crystal platform, and the castle/Euro exit
approaches. They are not promoted into passes. Source exploration closes at
27 engine attempts / 106,798 frames, including failures and single refinements,
below the 180,000-frame ceiling. Those source-baseline runs are not fresh candidate
frames. Input-stat comments and a hexadecimal item-label typo were corrected in
versioned metadata; actual writes/dumps remain authoritative. Failed receipts,
scripts and raw inputs are retained. No enemy HP/death/count, victory/quest-counter,
actor-PC or NPC-position outcome pokes are used; prerequisite flags/inventory,
teleports and player stats remain disclosed assistance.

## Display, audio and fallback

The unchanged renderer passes a fresh critical 22-capture / 71,500-frame subset:
original lesson, both classroom doors and town return, combat/boss, seven ready
pairs across six positive scene IDs, one Castoth object refusal, and two
unsupported-scene pairs with extra native-256 controls. Source packets, OAM,
ROI, CPU and devices retain their existing checks. A private prelaunch path
guard initially refused the new batch before any game ran; its zero-frame
failure and original helper remain, and only batch/output paths were corrected.

A new three-capture / 12,000-frame original Mode 7 control compares reference,
world full-copy/span and original-width fallback. At the actual travel picture,
all 57,344 original pixels and padded wide-field composition match. The stock
matrix and Mode 7 scene remain intact. During the route 1,323 new contexts execute
10,449,105 instructions / 37,766,871 cycles; this is not per-picture MMIO proof.
This adds **25 fresh presentation captures / 83,500 frames** in total, without
admitting a new renderer format. Mode 7 retains original-field fallback. The
entire old 021 renderer 44 stays as historical evidence; the new subset does not
replace it in full. Earlier 61-format/110-pair evidence remains historical.

Cold original MSU opening 4,400 frames and an actual NVIDIA 1080p xBR/1.5x check
of 240 frames pass. Their seed and image are byte-exact to 023. Zero new contexts
execute in the opening, so it supplies regression evidence only. Dummy-device
MSU consumption is not physical listening or sustained-FPS proof. Original
classroom geometry stays; this batch makes no scene redesign. The ignored
`native-024/Play Original Classroom.cmd` pins the new executable with MSU,
1080p xBR and 1.5x extent; the owner installation is unchanged.

## Remaining work, tools and cleanup

The new primary input is the sealed combined 185 ranking, with **13,767,490
interpreted cycles**. Keep earlier 105/129/148/171 rankings as separate cohorts.

| Remaining category | Guest cycles |
| --- | ---: |
| Protected RDNMI accesses | 9,679,040 |
| Unregistered ROM/mode contexts | 2,672,069 |
| Old registered sites refused; instance cause not captured | 1,178,672 |
| Mutable actor operands excluded | 127,488 |
| New registered sites refused; instance cause not captured | 109,752 |
| Unsupported stack-pointer operations | 258 |
| Actor stack-pointer operations | 178 |
| Reset/IRQ policy | 30 |
| Unknown actor source span | 3 |

The largest unregistered frontier starts at 88F9DC/88F9C0/88F9C2/88F9CA. Its
opcode/source identity and ownership remain unqualified. Registered-refusal
totals identify sites, not proven refusal causes. Investigate source and passive
causal evidence before expanding admission; keep RDNMI/live-operand/owner/event
guards. Native SPC, remaining gameplay/campaign proof and broader renderer work
remain. No benchmark or graph regeneration is required to continue.

Official SNESRecomp main 80a41241e39bfffd384506fbe7ca65b386e03050 and Gaia baserom
e825dddde466c73cb9900c2c04a7d2bfa37ed165 remain current at this batch's readback.
RomAtlas main advances to `b9ae425dd6546741f2ec41e36bda9543910287de` through data
for six games only; all other 18 root trees/files, including decoder/crates/vendor/
Cargo inputs, match. The qualified decoder with its recorded Windows refusal
patch is reused; this is not a claim of a freshly built main binary. Qualified
Python 3.14.10, Clang 22.1.8, CMake 4.4.5 and Ninja 1.13.2 remain. Babel/mr0ta/mrOt4,
GaiaLabs and all upstream credits/license notices are preserved.

Cleanup removes **42,421 obsolete passed files / 12,443,866,688 logical bytes /
5,425,289,728 reported last-link file-data bytes**, with zero locks or errors.
This combines 235 old SDK EXE/OBJ files and 42,186 old raw payloads: old 023
native 171 plus old 023/022 renderer 22 each. Exact plans, SHA/file identities,
guard checks, full preview, replacement proof and every reader release precede
removal. All 514 named dependencies were checked against the target set. No
archive, move, broad rescan or retry CMD is needed. These are file-data reports,
not a whole-volume free-space claim.

All 3,170 historical info JSONs and all source/receipts/profiles/journals/logs,
failures, states/seeds, owner 39/normal 28 PCM tracks, fifteen compact dependencies,
immutable graph and current/prior runnable masters remain. Current 024 raw stays;
the entire 021 renderer 44 remains. Retirement markers identify removed payloads
without rewriting original passed receipts; retired raw is unavailable as a
future golden. No old 022 native raw was read or retargeted. Current 024 capture
storage closes with zero reservations below the unchanged 9 GiB hard cap; no
further captures are scheduled.
