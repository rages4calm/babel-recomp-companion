# Native batch 002

The selected private build now passes the natural 6,000-frame classroom/South
Cape route in both 4:3 and 16:9, with **6.2645% / 6.3244% native CPU cycles**.
The earlier structural and failed-candidate sections below retain their original
scope. [Selected-build qualification](#selected-build-qualification) records the
actual executed evidence; candidate counts alone are not coverage.

## RomAtlas and GaiaLabs structural evidence

This section records **structural research**, independently from build, native
execution, matched-reference and gameplay qualification elsewhere in this note.
The existing pinned RomAtlas tool, decoder provenance and GaiaLabs metadata are
documented in [ROMATLAS-PLAN.md](ROMATLAS-PLAN.md); they were reused without
downloading another tool or repeating the earlier reset/wait audit.

`scripts/check_gaia_native_boundaries.py` consumes completed tier2 coverage v2
checkpoints. It validates stock ROM identity and HiROM mapping, rejects lost or
overflowed observations, preserves exact PC/M/X/E keys, and classifies each
observed instruction against exact generated manifest entries, internal labels,
existing CFG seeds and physical aliases. A seed or mirror alias never becomes
a callable native entry merely because it names the same cartridge bytes.
GaiaLabs block names and asset ranges provide structural context, not execution
or callable-stack proof. COP instructions retain an explicit dispatcher-context
requirement; data is never promoted by linear disassembly.

The initial stock 4:3 cold-boot profile is
`.local/batch-001/native-002/profile-boot/capture.json`, with executable identity
`e53829c1cd01d5904b4b735d12976e970b9f315b7157d36cb67a979e39a03dc1`.
The capture contains 5,485 exact interpreted PC/M/X/E contexts and 246 transfer
discoveries, with no dropped costs, tuple overflow or journal-write failures.
The caller declared stock mode with no widescreen code patch or MSU-1 source
changes. The file's original-ROM hash by itself would not establish that live
cartridge bytes were unmodified; that source-profile assertion remains explicit.

The first independent check classified all contexts and compared **1,024**
selected boundaries between RomAtlas and the framework's single-instruction
decoder. Opcode and instruction-length agreement passed for every selection.
The sample includes all **159 cartridge-backed contexts** among 162 unique
observed transfer targets. These boundaries account for 38,380,357 of 40,626,623
interpreted instruction hits (94.47% of this profile's planning weight). This
fraction is **not native coverage, timing accuracy or campaign progress**.
Transfer discovery does not independently prove a resumable host-call context.

The three remaining transfer targets are WRAM-mirrored `$80:0402`, `$82:0402`
and `$83:0402`. Together their observed bodies contribute twelve PC/M/X/E
contexts at offsets `$0402`, `$0403`, `$0406` and `$0407`, all M0/X0/E0.
The profile contains no RAM-routine byte captures. The checker therefore refuses
to decode cartridge bytes as these routines. They need actual runtime bytes,
mapping and source generation before any native promotion; existing interpreter
fallback must remain available.

The observed cohort also includes **321** contexts inside the known dynamic
actor/OAM patch range. The script flags the original byte window
`$03:C5FF..C9FF` across its observed HiROM aliases, regardless of whether this
particular route enabled widescreen. Any later widescreen execution needs a
source-profile guard or the witnessed patched bytes; original-ROM decode is
insufficient. Language patches, optional IPS content, randomizer replacement and
MSU-1 source modifications likewise cannot borrow stock qualification.

Initial generated-output classification found no exact executed entries or
labels among the current eight generated variants; three E1 contexts also have
an emulation-mode identity absent from legacy PC/M/X manifest keys. The large
candidate generation and its later execution checks are separate work. Do not
reinterpret the initial no-AOT result as successful native execution.

The private report `structural-boundaries-initial.json` binds the profile,
original ROM, tool, framework decoder, generated files, CFG seeds and GaiaLabs
metadata by SHA-256. It retains disassembly privately under the one ignored
scratch batch. Public source contains the generic checker and this ROM-free
summary, without game assembly, generated game C, owner saves or captures.

The checker additionally passed 18 focused mapping/schema/refusal checks:
HiROM versus WRAM windows, physical offset versus logical PC, duplicate JSON
keys, non-finite numeric input, incomplete checkpoints and nonzero loss counters.
These checks validate the research tool's boundaries; they do not execute Gaia.

Example reproduction, with a developer-supplied tool path:

```powershell
python scripts/check_gaia_native_boundaries.py --rom 'Illusion of Gaia (USA).sfc' --coverage .local/batch-001/native-002/profile-boot/capture.json --romatlas $RomAtlas --source-profile stock --max-boundaries 1024 --out .local/batch-001/native-002/structural-boundaries-initial.json
```

The tool requires an output under `.local/`, a matching pinned research binary,
and the verified bare USA ROM. `--source-profile stock` is an explicit caller
assertion, not a result inferred from server identity or a function count.
`--live-rom` can bind a witnessed cartridge-image snapshot for byte comparison;
it cannot substitute for missing WRAM execution bytes. Unknown profiles remain
explicitly marked original-only. The tool never changes engine code, generates
native functions or launches the game.

### School route extension and WRAM source variation

The later natural-input school route contributes 7,351 instruction contexts and
363 transfer discoveries, with scene `$08` and player actor `$1000` observed
from frame 2,000. Combining its completed checkpoint with the earlier boot
profile gives **8,224 unique PC/M/X/E contexts**, 609 overlapping transfer
records and 225 unique transfer-target contexts. A **2,048-boundary** independent
RomAtlas/framework decoder comparison passed without opcode/length mismatches,
including all 222 cartridge-backed transfer-target contexts. Selected boundaries
account for 93,758,914 of 95,344,167 overlapping instruction hits (98.34% planning
weight); the three remaining targets are still the WRAM mirrors described above.
The two profiles overlap, so their aggregate hits are not distinct campaign work.
The combined cohort contains 435 actor/OAM patch-range contexts.

Nine paired WRAM/info snapshots from the school route supplied **108 bounded
byte observations** across the twelve WRAM contexts. Each record retains its
exact snapshot frame and file hash; no record claims those bytes persisted
throughout earlier cost hits or that the CPU was executing the stub when dumped.
The local decoder identifies a block-move stub, and its move-bank operand changes
between captured frames. Consequently a single static stock-ROM body cannot
stand in for this WRAM code; native execution would need exact runtime-byte and
source-generation guards. Original cartridge bytes are not a substitute.

The existing RomAtlas CLI refuses raw WRAM files because they lack a supported
cartridge header. These 108 snapshot observations therefore use the framework's
single-instruction decoder **only**, not an independent RomAtlas comparison.
No fabricated cartridge mapping was used. Both limitations are explicit in
`structural-boundaries-school.json`; this is source investigation, not runtime
or timing qualification.

The checker can reuse identity- and byte-matched independent decode results with
`--reuse-decodes` when classifying a later generated manifest. It binds that prior
receipt by hash, preserving completed research without re-running unchanged
original-byte decoding. Generated entries, internal labels and forced fallback
must still be reported separately after candidate generation.

### South Cape active-route extension

The subsequent natural-input route reaches South Cape through the classroom,
church dialogue and door, with directional movement and a visible town/player
capture. This supplies actual movement/transition scope absent from an idle or
paused school snapshot; the earlier school scene/player fields alone did not
prove that player control was active. Its completed checkpoint contributes 9,004
instruction contexts and 470 transfer records.

Across the three overlapping profiles, the checker classified **9,921 unique
PC/M/X/E contexts** and 1,079 transfer records, representing 284 unique target
contexts. It checked **4,096 original cartridge boundaries** without opcode or
length mismatch, including all 281 cartridge-backed transfer-target contexts.
The other three targets remain the WRAM stub. It reused the completed 2,048
independent decodes from the preceding receipt and decoded 2,048 newly selected
contexts; it did not repeat the earlier independent checks.

This selection accounts for 163,449,690 of 163,627,364 overlapping instruction
hits (99.89% of planning weight), with 440 observed dynamic actor/OAM contexts
explicitly guarded. None of these statistics measures native execution. Thirteen
South Cape route snapshots add 156 frame-scoped WRAM byte observations, again
using only the framework decoder and never substituting them for historical
source bytes. Private report: `structural-boundaries-southcape.json`.

A separate narrow structural check also confirmed that `$83:EA76` is an indexed
indirect **call**, whose ordinary return continues at `$83:EA79` before looping
back through the explicit width setup. Its bounded selector admits eighteen
word-pointer entries. This is relevant to analyzer caller-continuation behavior;
it is not permission to treat the call as a terminal jump or to infer every
callee's return mode from the caller's entry mode. The alternative writer path
arrives with its own 8-bit accumulator context. Details remain in private
`decoder-83ea62.json` and `romatlas-83ea76.json`; no game assembly is reproduced
in public documentation.

### Candidate graph classification before pacing

Reclassified the same three completed profiles against the new private
`native-instruction/generated/` graph. The graph's manifest SHA-256 is
`83f75543527addc1afb0a24e8598aca140ec818c408ef7263711954ab0ec0178`:
201 roots, 888 PC/M/X variants, 816 eligible exported candidates and 72 LLE-only
variants. The emitted dispatch table contains exactly 816 non-null variant
slots, consistent with the manifest. This is generated entry structure, not
proof that every entry has a valid observed call/stack context or has executed.

| Relation of observed exact PC/M/X/E context to candidate graph | Contexts |
|---|---:|
| Exact eligible manifest entry with matching non-null dispatch export | 386 |
| Generated internal label without an exact exported entry | 4,229 |
| Exact LLE-only manifest variant | 38 |
| No exact generated entry or internal label | 5,265 |
| E1 context not represented by legacy manifest's PC/M/X key | 3 |
| Total observed contexts | 9,921 |

Among 284 unique observed transfer-target contexts, 177 match eligible exports,
24 match LLE-only variants and 83 have no exact generated entry/label. Eight of
those missing targets are explicitly policy-guarded; 75 are unguarded targets
without matching emitted boundaries, primarily observed goto transfers. This
classification does not establish native closure for that cohort. Internal
labels do not supply independently callable entries; neither a physical ROM
alias nor an enclosing function interval resolves missing stack/mode context.

The explicit interpreted policy covers 664 observed contexts: seven vector
trampoline contexts, 70 NMI-body contexts, 147 boot/polling contexts and 440
dynamic actor/OAM contexts. None has an exported eligible candidate. The three
WRAM-mirrored transfer entries also remain LLE-only because their changing
runtime bytes were not historically captured with those instruction costs.
Other LLE reasons include unproven callee exits, truncated continuations and
structural decode hazards; they remain explicitly recorded. Surrounding
generated C is not evidence of native execution at an LLE-only variant.

The public checker now recognizes both `bankXX_v2.c` and split
`bankXX_partNN_v2.c` files. A focused synthetic fixture was added to the existing
mapping/schema/refusal checks; `--self-test` passes **24 ROM-free checks**.
Fresh execution of that public parser reproduced the candidate classifications
above. It reused all **4,096** already-completed independent boundary checks,
made **zero new RomAtlas decode calls**, and retained zero decoder mismatches.
The private report binds the complete generated bank files, dispatch table,
manifest, cache and policy alongside original evidence identities:
`structural-boundaries-candidate.json`.

That pre-pacing candidate remains **unqualified**: matched execution found a master
cycle parity failure. A structural match cannot supersede that failed receipt
or establish CPU/device timing. The explicit pacing investigation is separate;
this section makes no fresh execution, timing, campaign or native-percentage
claim. No standalone serialized program graph was emitted in this directory;
the authoritative manifest, generation cache and actual dispatch source were
the available structure inputs, rather than an invented missing program file.

## Selected build qualification

The selected source includes explicit instruction blocks, opt-in region pacing,
origin-based native APU clock credit, owner-safe fallback and live program-bank
preservation during nested JSL unwinds. The conservative mode also interprets
`XCE` before it can change emulation mode mid-body. Its detailed framework
contract and ROM-free fixtures are in
[REGION_PACED_TIMING.md](../snesrecomp/docs/REGION_PACED_TIMING.md).

Base SNESRecomp main remains
`66eebe6ae415b4fb2607a22e5b12352f612e1bdf`, rechecked November 2, 2026.
The local source changes build on that revision; the vendor tree was not
replaced. [Issue 239](https://github.com/RetroPortingToolKit/snesrecomp/issues/239)
contains the nine-byte synthetic recursive-analysis failure and
[its isolated fix](https://github.com/rages4calm/babel-recomp-companion/commit/5f38a99edbce843bdca01cbadf7f9bf0a88eec1d).
Matching runtime timing findings were contributed to
[existing issue 205](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6586173267).
The earlier timing report by pogoflow informed this investigation.

The private recipe is `.local/batch-001/native-002/native-selected/`. It uses all
three retained captures, 201 profile roots and the existing GaiaLabs seed
inventory without promoting all 8,987 declarations to roots. The graph retains
888 PC/M/X variants, 816 eligible candidates and 72 LLE-only variants. All 6,460
explicit byte/alias guards remain in place, with zero eligible-body guard
violations. Generation completed under the owned 4 GiB / 300-second process-tree
limits; original resource-heavy and nonconverging attempts remain failed.

The selected Windows executable SHA-256 is
`f8f7f82ff37336ac24b1053ae89151668dd377cd2507ae09680d04c90a034680`.
It includes the new game icon. The same binary ran both native and forced
interpreter cases in fresh fixtures with the same clean ROM, input route,
settings and initial state. No teleports, RAM writes or loaded states occur in
this natural route. The route reaches the classroom, completes dialogue,
moves around the pews and exits through the doorway into South Cape.

| Final 6,000-frame case | 4:3 | 16:9 |
|---|---:|---:|
| Total CPU cycles, identical between tiers | 255,149,254 | 270,357,536 |
| Total master clocks, identical between tiers | 1,725,672,422 | 1,828,113,010 |
| Native CPU cycles | 15,983,849 | 17,098,513 |
| Native share | 6.2645% | 6.3244% |
| Guest instructions absent from the matched interpreter count | 4,560,776 | 4,857,769 |
| Full final output | 256 x 224 | 342 x 224 |

The instruction-count differences are derived from matched interpreter totals;
they are not an assertion that every eligible candidate function executed.
This is **partial native execution on a bounded route**, not full native
coverage, a performance measurement, hardware accuracy or campaign proof.

### Matched state and audio evidence

Both selected comparisons pass every CPU/WRAM trace row, all thirteen saved
WRAM/SRAM/VRAM/CGRAM/OAM/framebuffer/PPU-register snapshots, CPU/master totals,
DMA/PPU write journals and the full nonempty final PPM output. The full 342-wide
output includes margins omitted from the state dumper's authentic 256 columns.
Forced interpretation also reproduces the prior interpreter-only baseline.

The observer now saves the existing pointer-free APU/SPC/DSP regions, including
the native PCM ring, and the complete audio-port scheduler/queue under the
existing audio lock. All thirteen APU-state and scheduler snapshots match
byte-for-byte in both aspects. This reads state without advancing the audio
processor or modifying player data.

Raw APU event files are **not byte-identical**. Their circular history windows
retain some SPC read/write beam tags at the CPU beam position where a batch was
flushed. The exact event order, frame, port, value and DSP-produced sample index
match; all CPU event rows, including beam positions, match exactly. The sample
index is not an exact SPC-cycle timestamp. Accordingly the comparator keeps
byte-strict device comparison as its default and preserves the raw failure.
The explicit `--apu-clock samples` mode requires `--devices --apu-state`, complete
matching state/PCM/queue files for every tag, exact CPU rows and all other SPC
fields. It ignores only the two SPC beam-tag fields and still reports every raw
difference. It is not a general timestamp-ignore mode.

Private receipts: `selected-comparison.json`, `selected-wide-comparison.json`,
`selected-fallback-comparison.json`, and `selected-routes-summary.json` under the
same scratch batch. Twenty-two ROM-free comparator tests include missing states,
changed event/sample/frame/CPU timestamps and full-output mismatches.

### Failed candidates retained

- The all-seed generation grew to about 7.3 GiB RSS and was stopped by verified
  owned PID before the later process-tree limiter was introduced. It did not
  qualify or complete generation.
- The first profile-only graph oscillated for 128 analyzer rounds. The validated
  no-return dependency fix resolved this without increasing that cap.
- Aggregate native emission reached South Cape at 14.6781% AOT but diverged from
  frame 1. Instruction blocks alone moved the first failure to frame 3.
- The initial region fallback bypassed the owning interpreter and produced a
  black run. Existing owner-safe tail transfer corrected this local mistake.
- The next candidate matched CPU clocks for the first 2,076 instructions but
  diverged at an interpreted audio-handshake poll: native instruction time had
  not joined the bridge's relative APU credit. Exact-origin credit fixed it.
- The pre-PB candidate then matched all memory/graphics and final clocks, but a
  nested JSL envelope restored an ancestor's PB during a pending yield. A
  ROM-free executed before/after fixture proves the live-bank fix, including
  unchanged ordinary return behavior.

These failures remain failures. The selected receipts supersede only their
stated route/build/aspect, and the raw SPC beam-tag difference remains visible.
No natural dungeon combat/reward, boss, later form or full playthrough is implied.
[Guide research](GUIDE-RESEARCH.md) provides upcoming scenarios; assisted tests
have separate provenance.

The final selected binary additionally passed the explicitly checkpoint-linked
[assisted reward component fixture](ASSISTED-TESTING.md): 8x native/interpreter
parity and a separate eight-assertion 1x control. Its 9.442% AOT share belongs to
that synthetic 120-frame fixture only. Failed warp requests remain failed;
changing a scene selector for a component test did not visit that area.

### Reproduction and fallback

Use a completed private tier2 checkpoint captured from the supported stock ROM.
Captures, input scripts, generated game C, saves and screenshots stay private.

```powershell
python scripts/native_batch.py --generate --profile-only --instruction-blocks --region-paced --profile .local/your-capture.json --work .local/batch-001/native-002/your-native-batch
./scripts/build_windows.ps1 -NativeBatch .local/batch-001/native-002/your-native-batch -Jobs 2
python scripts/compare_native_runs.py .local/your-reference .local/your-native --devices --apu-state --apu-clock samples --output .local/your-comparison.json
```

Keep only one active scratch batch; reuse completed immutable research receipts.
`-NativeBatch` requires a successful generation receipt, matching manifest hash
and no guard violations. `SNESRECOMP_INTERPRET_ALL=1` retains the same executable's
reference path. A normal `./scripts/build_windows.ps1` builds interpreter-only;
private native builds contain ROM-derived code and are rejected by public
packaging. Actual selected-build packaging refusal was verified. No release or
ROM-derived generated source/binary was published.
