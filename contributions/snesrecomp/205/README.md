# SNESRecomp timing contribution

November 9 update: [#250](https://github.com/RetroPortingToolKit/snesrecomp/pull/250)
and [#251](https://github.com/RetroPortingToolKit/snesrecomp/pull/251) are now
merged into official main `d8116fac4470ed1c9df70ae56869c7a9cb44935f`.
Their final maintainer heads are `075c8323993ba15fbaab539d408255cb334f716b`
and `31b23c976c54e8f426354a6effe003293cf7f7f0`. The older status and patches
below are historical preparation records. #241 has also merged, bringing the
SPC/DSP timing and version11 snapshot changes; current-core game qualification
is tracked separately from the original consumer restore limitations.

Updated November 8, 2026: [#248](https://github.com/RetroPortingToolKit/snesrecomp/pull/248)
is merged. The maintainer refreshed the still-draft [#250](https://github.com/RetroPortingToolKit/snesrecomp/pull/250)
and [#251](https://github.com/RetroPortingToolKit/snesrecomp/pull/251) to
`7ff96d580ace99d8b5957d2c16466a2a9d3a9a46` and
`0d65b8d8a0a3983ed98e0a0ff936be7fff18524c`; their executed CI jobs pass.
Preserve those remote heads. The exported patches and preparation evidence
below remain the historical November 3 series, not a replacement for the
maintainer's newer branches. [Current framework integration and outstanding timing leads](../../../docs/FRAMEWORK-NOV08.md).
The recorded consumer restore/cost limitations remain open.

## November 3 preparation record

Prepared November 3, 2026 in response to [the maintainer's requested split](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6613478058).
The three source groups are now submitted from the separately authorized
[framework fork](https://github.com/rages4calm/snesrecomp):

- [#248: default correctness](https://github.com/RetroPortingToolKit/snesrecomp/pull/248), ready for review when submitted (now merged).
- [#250: explicit pacing and cache identity](https://github.com/RetroPortingToolKit/snesrecomp/pull/250), stacked draft depending on #248.
- [#251: native APU integration](https://github.com/RetroPortingToolKit/snesrecomp/pull/251), stacked draft depending on both predecessors.

The drafts provide focused predecessor-to-head diff links; their branches also
include the dependencies so the series builds. Rebase after predecessor merges
before promotion. They are not accepted/merged changes, and the documented
consumer restore/cost limits remain explicit.
The [submitted series index](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6615843553)
records all three PRs. Initial fork workflow runs report `action_required`;
upstream CI has not passed or been represented as passing.
The source series, passing checks, measured costs and failed restore gate were
[delivered in the existing #205 discussion](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6614160563).
The current refreshed patches apply in order to merged upstream main
`f6912cd74e06eb21329aeb5c929d7f374479db80`.
The [rebased series and new integration results were delivered upstream](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6615719490).
The serialized patches were independently replayed with `git am`; their final
Git tree exactly matches the tested stack: `e09c0ddcfa4208dc9a2464bd1f3bb00f0029ed59`.

The requested prerequisites [#243](https://github.com/RetroPortingToolKit/snesrecomp/pull/243),
[#245](https://github.com/RetroPortingToolKit/snesrecomp/pull/245),
[#247](https://github.com/RetroPortingToolKit/snesrecomp/pull/247) and
[#246](https://github.com/RetroPortingToolKit/snesrecomp/pull/246) were open when
these patches were prepared. They have now merged into main
`f6912cd74e06eb21329aeb5c929d7f374479db80`. The series is now rebased and retested
on that merged head, with its clocked-read wrappers preserved. Those repairs
are inherited from the base and are not duplicated in this series. The initial
main66 series remains available at [its original source checkpoint](https://github.com/rages4calm/babel-recomp-companion/tree/66e442618616b7086d6adf61a10f03a0adc40f98/contributions/snesrecomp/205).
[PR #241](https://github.com/RetroPortingToolKit/snesrecomp/pull/241)
also remains unmerged; its per-clock APU/DSP, DMA and version-11 state changes
are not incorporated or qualified here.

## Source split

| Patch | Changes |
|---|---|
| [01: Default correctness](01-default-correctness.patch) | Preserve the live program bank through nested JSL yield/deadline unwinds, with the production query API and executed tests. Charge the extra taken-branch cycle after constant-Z folding in the shared static-cost calculation. Explicit taken metadata distinguishes zero-offset taken and not-taken cases. This does not replace default aggregate master-clock accounting. |
| [02: Explicit emission and identity](02-region-paced-emission.patch) | Add default-false instruction blocks and region pacing through the emitter, public SDK/CLI and recipe. Include both modes in effective recipe, output and per-bank cache identities. Refuse unsupported instructions, MMIO and pointer/stack/word boundaries before instruction charging or guest mutation. Keep owning-interpreter fallback. Add neutral clock-origin/boundary extension points, without the bridge's APU policy. |
| [03: Native APU integration](03-native-apu-integration.patch) | Queue actual native clock increments in the existing rollback-owned bridge accumulator, under the interpreter's scheduling predicate. Flush only at completed instruction boundaries. Final paired returns finalize refresh/boundary work only when a scheduling marker is pending. Add no inferred elapsed-call credit or new serialized counter. |

Patch 02 also adapts pointer access matching to the merged #243 codegen and
retains compatibility with the earlier generator. Its existing low-WRAM preview, MMIO/bank-boundary refusal
and single architectural pointer fetch remain required. The adaptation passed
all 864 synthetic pointer cases with both code generators. Merged #247
clocked-read scopes remain intact: only the clock increment changes to the
neutral origin API, preserving the hardware-read wrapper.

Babel-specific presentation, mods, interrupt-stop policy, generated game code,
game assets, source-analysis expansion and private captures are excluded.
The interpreter-only build and the consumer's forced-interpreter path remain
available. Region timing stays an explicit generation-time choice.

## Executed source checks

- Initial preparation of the first group: 46 focused JSL/API checks and 23 focused branch/cycle checks.
  The branch fixture executes 12 synthetic programs against the actual
  interpreter, including taken/not-taken zero-offset controls. Earlier red
  witnesses are retained privately.
- Rebased second group alone: **37 focused tests pass**, including actual emitted/interpreter bus
  comparisons, exactly-once pointer reads, refusal side effects, deadline
  suspension and public SDK/output/bank-cache toggles. The folded-branch
  fixture also executes through instruction-block emission.
- Complete rebased stack: **643 Python tests pass, two existing compiler-path skips**.
  The separate current merged vendor integration also passes 644 Python checks.
  Its real bridge C fixture passes **432 checks in each fused-read mode**;
  the interrupt-tail fixture passes 27 checks, and CPU bus/latch checks pass.
- Earlier dual-codegen compatibility checks: 19 tests passed with main66 codegen
  and 20 with then-pending #243 codegen, including its separate bank-carry
  regression. The current rebased matrix exercises the now-merged implementation.

The isolated source suite first encountered an uninitialized nested dependency,
then a Windows file-replace error on another run. After materializing the pinned
dependency and using a fresh shorter scratch path, the full matrix passed.
Those failed receipts remain retained. The rebase additionally updates the
extracted test fixture for #247's real scoped-read helpers and explicit UTF-8
source reads. No production wrapper or timing behavior was removed to pass.

To replay the preparation base in an isolated upstream checkout:

```sh
git checkout -b timing-205-preparation f6912cd74e06eb21329aeb5c929d7f374479db80
git submodule update --init --recursive
git am /path/to/01-default-correctness.patch /path/to/02-region-paced-emission.patch /path/to/03-native-apu-integration.patch
python -m pytest tests/v2 tests/test_generation_recipe.py tests/test_timing_generation_identity.py tests/test_snes_cycles.py tests/test_beam_events.py tests/test_rdnmi.py -q
```

## Consumer qualification

The separate [consumer report](QUALIFICATION.md) records fresh gameplay,
current-build restoration and matched host cost. It includes a **failed canonical
audio-continuation check after ordinary save/load** shared by native and
interpreted runs. That failure is not waived by their mutual parity. The source
patch tests do not waive that restore failure or qualify PR #241's version-11
state layout. New [merged-head consumer checks](../../../docs/FRAMEWORK-F691.md)
are recorded separately from the original main66 cost/restore measurements.

Original SNESRecomp author and license notices remain in place. This work comes
from the noncommercial Illusion of Gaia Companion fork of Babel by **mr0ta /
mrOt4**, maintained by **Carl Prewitt Jr. / rages4calm**. The earlier timing
investigation in #205, including pogoflow's report, informed this work. ROMs,
generated game code, saves, soundtrack data and raw private validation artifacts
are not part of these patches.
