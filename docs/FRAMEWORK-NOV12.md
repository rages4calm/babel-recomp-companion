# SNESRecomp integration — November 12, 2026

Previous official pin: `e9c207322c148eccc8a679b72d8b005d0d95d31c`.
Current official pin: `80a41241e39bfffd384506fbe7ca65b386e03050`.
The [upstream comparison](https://github.com/RetroPortingToolKit/snesrecomp/compare/e9c207322c148eccc8a679b72d8b005d0d95d31c...80a41241e39bfffd384506fbe7ca65b386e03050)
contains 13 commits affecting 13 files. The vendor directory was not replaced.

An explicit base/local/upstream inventory preceded the merge. Eleven file patches
applied directly, preserving unrelated local edits. The bridge's bank-preserving
return-PC calculation was already locally equivalent; upstream comments/format
were merged around it. The C test runner already linked the required HD job code;
that local fix was retained while adding upstream's new fixture sections.
Private patch texts, identities and applied/reverse checks are retained in
`native-019/triage/upstream-delta/`.

| Upstream change | Consumer status |
|---|---|
| Keep paired return PCs inside the caller's 16-bit program bank | Runtime bridge merged; equivalent local fix preserved. New upstream bridge checks pass in both fused modes. |
| Windows long and Unicode mod paths | Runtime path helper/catalog changes compiled. Actual resolver, activation, state and binary reads pass short, 259-, 264-, 380-character and Unicode-path fixtures. |
| Parenthesized PPU tile-address macro | Header fix compiled; expression/one-evaluation fixture passes strict Clang. |
| Screenshot JSON path escaping | Debug-server fix compiled; 29 ROM-free production-command tests pass. |
| Host metadata sampling preserves open bus | Emitter template adopted and its new test passes. The immutable old AOT graph is retained, so this template change is not retroactively claimed in existing generated game C. |
| UTF-8 generation and test-fixture linking | Tool/test source merged. Existing generated graph identity is not presented as new generation. |

Upstream issues [267](https://github.com/RetroPortingToolKit/snesrecomp/issues/267),
[270](https://github.com/RetroPortingToolKit/snesrecomp/issues/270),
[271](https://github.com/RetroPortingToolKit/snesrecomp/issues/271) and
[273](https://github.com/RetroPortingToolKit/snesrecomp/issues/273) were checked
closed; PRs 268, 274, 275 and 282 were checked merged on November 11.

A final November 12 account-wide check finds 11 of the owner's 12 reported issues
closed, and all four authored PRs (248, 250, 251 and 268) merged. Only
[profile-import performance issue 265](https://github.com/RetroPortingToolKit/snesrecomp/issues/265)
remains open. Official main is still the pin above. These are issue/merge states,
not a claim that every historical generated graph has been regenerated.

The new upstream PPU fixture initially failed strict Clang on a signed/unsigned
comparison in its expected-value array. The local fixture uses `int` expectations,
matching the accessor's promoted result type; all values fit. The initial failure
is retained and the strict rerun passes. This is a fixture warning fix, not a
recurrence of the macro defect. It was reported in the existing
[issue 273 discussion](https://github.com/RetroPortingToolKit/snesrecomp/issues/273#issuecomment-6840707823).

Local native continuation/ownership, pacing, bus/APU timing, dispatcher, renderer,
logging and content-identity changes remain local deltas with their own tests.
Batch 019's finite NMI stack/direct-call extension is not described as an upstream
feature. See [the batch evidence](NATIVE-BATCH-019.md) for execution scope and limits.
The SDK v2/timing/DSP gate reports 877 passed, two skipped and no warnings; no
source catalog changed during that gate. Credits and license notices are retained.


## Batch 020 local extension

Official main was checked again on November 12 and remains the same pin.
This batch adds a local, opt-in fixed-instruction frame permission and restrictive
owner-scope API; it is not described as an upstream feature. Ordinary registration
does not enable COP/RTI. Exact frame grants, a separate launch switch and the
existing finite NMI protocol are required. Whole-function AOT barrier bounds,
RDNMI poll code and runtime interpreter exclusions remain unchanged.

The updated SDK v2/timing/DSP source gate passes **903 tests, two skipped, no
warnings**, with 780 files unchanged during execution. New actual C bridge tests
cover frame and vector retirement, default-off behavior, atomic permissions,
restrictive scope combinations and duplicate registration. Nine separate title
policy tests cover the allowed fixed-instruction boundaries. The earlier 877-test
receipt remains historical; its test count is not added to 903. The immutable
batch-016 graph is reused, so generator-only changes still do not imply new
generated game code. [Batch 020](NATIVE-BATCH-020.md) records the actual execution
and renderer scope, failures and limits. All existing credits and license notices
remain intact.

## Batch 023 local registry extension

Official main was checked again on November 13 and remains the pin above.
The local descriptor registry now supports 131,072 entries using 32-bit slot IDs
and legacy range starts. Page IDs/counts remain 16-bit within their proven bounds;
public headers, saved CPU layouts, dispatch, interpreter, exclusions, owner/event
checks and retirement remain unchanged. This is a local extension, not an
upstream merge. The old lookup remains available.

Four new capacity tests exercise both lookups across the 65,535 boundary and at
131,072, with real reference/native effects, atomic failure checks and two
activated truncation faults. The full SDK gate passes **972 tests, two skipped,
zero warnings**, with all 786 source files unchanged during execution.
[Batch 023](NATIVE-BATCH-023.md) records the exact native gameplay proof and limits.

## Batch 024 word-MMIO coverage

Official main remains the pin above at the November 13 readback. Public engine,
bridge, interpreter, emitter, policy, ABI, save layouts and compiled sources are
unchanged. A source-backed context expansion targets the game's Mode7 perspective
and world-map code; it adds no opcode or permission class.

Eight new focused tests cover M0 claimed-word and scalar-refusal access to the
runtime's divider and H-IRQ registers, with flat/outlined effects and both lookups.
They execute 3,552 positive reference/native pairs and 167,044 checks. One
high-write-byte fault is activated and rejected in four variants. Real modeled
Snes/APU/SPC/DSP/DMA state, bus order and masked IRQ pending state are checked;
this is not the entire production AOT/cart bus, IRQ handler delivery or silicon
latency proof.

The previous 972-pass/two-skip SDK result is explicitly reused against 786
unchanged source files. The eight new tests ran separately; collection reports
982 tests, and no fresh full-suite run is claimed. Current game execution is
qualified independently. [Batch 024](NATIVE-BATCH-024.md) records the exact scope.


## Batch 025 exact acknowledgement qualification

Official main remains 80a41241 at the final November 13 check; no vendor/runtime
replacement or new engine mechanism is introduced. Three exact physical
M1X0/E0 RDNMI acknowledgements now have explicit title-policy permission for the
existing fixed-effect path, scheduler scope only, no NMI/frame grants or alias
expansion. The five protected-PC list and two original poll sites stay; all other
modes/bytes/owners remain excluded. Original bridge/interpreter/emitter/ABI/save/
retirement/event/live-byte behavior and 524 compiled-source files are unchanged.

Eight fresh real-device tests execute 9,576 REF/native pairs/443,764 checks,
including actual read-clear/beam edges, ordinary/native-NMI refusals and four
activated skip-read fault rejections. Thirteen title-policy, eight alias and five
actor-policy tests pass. Prior SDK972/two skipped and prior Mode7 eight are reused,
not fresh; old 786 sources plus the Mode7 test are byte-exact. The 990-test
collection is not a fresh full-suite run. [Batch 025](NATIVE-BATCH-025.md) records
the fresh185/expanded195 execution, partial source goals and observation limits.
