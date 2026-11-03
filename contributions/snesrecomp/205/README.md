# SNESRecomp timing contribution

Prepared November 3, 2026 in response to [the maintainer's requested split](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6613478058).
These are three reviewable source patches, not submitted or accepted PRs.
They apply in order to upstream main `66eebe6ae415b4fb2607a22e5b12352f612e1bdf`.
The serialized patches were independently replayed with `git am`; their final
Git tree exactly matches the tested stack: `8762c81aa0123ae663e387c980c8e37cf502d062`.

The requested prerequisites [#243](https://github.com/RetroPortingToolKit/snesrecomp/pull/243),
[#245](https://github.com/RetroPortingToolKit/snesrecomp/pull/245),
[#247](https://github.com/RetroPortingToolKit/snesrecomp/pull/247) and
[#246](https://github.com/RetroPortingToolKit/snesrecomp/pull/246) are still open.
The maintainer requested eventual merged bases. Rebase and rerun combined
qualification after those merges before submitting these as PRs. Their repairs
are not included in this series. [PR #241](https://github.com/RetroPortingToolKit/snesrecomp/pull/241)
also remains unmerged; its per-clock APU/DSP, DMA and version-11 state changes
are not incorporated or qualified here.

## Source split

| Patch | Changes |
|---|---|
| [01: Default correctness](01-default-correctness.patch) | Preserve the live program bank through nested JSL yield/deadline unwinds, with the production query API and executed tests. Charge the extra taken-branch cycle after constant-Z folding in the shared static-cost calculation. Explicit taken metadata distinguishes zero-offset taken and not-taken cases. This does not replace default aggregate master-clock accounting. |
| [02: Explicit emission and identity](02-region-paced-emission.patch) | Add default-false instruction blocks and region pacing through the emitter, public SDK/CLI and recipe. Include both modes in effective recipe, output and per-bank cache identities. Refuse unsupported instructions, MMIO and pointer/stack/word boundaries before instruction charging or guest mutation. Keep owning-interpreter fallback. Add neutral clock-origin/boundary extension points, without the bridge's APU policy. |
| [03: Native APU integration](03-native-apu-integration.patch) | Queue actual native clock increments in the existing rollback-owned bridge accumulator, under the interpreter's scheduling predicate. Flush only at completed instruction boundaries. Final paired returns finalize refresh/boundary work only when a scheduling marker is pending. Add no inferred elapsed-call credit or new serialized counter. |

Patch 02 also adapts pointer access matching to both current codegen and the
pending #243 codegen. Its existing low-WRAM preview, MMIO/bank-boundary refusal
and single architectural pointer fetch remain required. The adaptation passed
all 864 synthetic pointer cases with both code generators. The pending #247
clocked-read scopes must be preserved when rebasing paced helpers; replace only
the clock increment, not their hardware-read wrapper.

Babel-specific presentation, mods, interrupt-stop policy, generated game code,
game assets, source-analysis expansion and private captures are excluded.
The interpreter-only build and the consumer's forced-interpreter path remain
available. Region timing stays an explicit generation-time choice.

## Executed source checks

- First group: 46 focused JSL/API checks and 23 focused branch/cycle checks.
  The branch fixture executes 12 synthetic programs against the actual
  interpreter, including taken/not-taken zero-offset controls. Earlier red
  witnesses are retained privately.
- Second group alone: 45 tests pass, including actual emitted/interpreter bus
  comparisons, exactly-once pointer reads, refusal side effects, deadline
  suspension and public SDK/output/bank-cache toggles. The folded-branch
  fixture also executes through instruction-block emission.
- Complete stack: **640 Python tests pass, two existing compiler-path skips**.
  The real bridge C fixture passes **432 checks in each fused-read mode**;
  the interrupt-tail fixture passes 27 checks, and CPU bus/latch checks pass.
- Predictive pointer compatibility: 19 tests pass with current codegen and
  20 with pending #243 codegen, including its separate executed bank-carry
  regression. This is not a claim that the prerequisite has merged.

The isolated source suite first encountered an uninitialized nested dependency,
then a Windows file-replace error on another run. After materializing the pinned
dependency and using a fresh shorter scratch path, the full matrix passed.
Those failed receipts remain retained; no production retry or timing behavior
was changed to make tests pass.

To replay the preparation base in an isolated upstream checkout:

```sh
git checkout -b timing-205-preparation 66eebe6ae415b4fb2607a22e5b12352f612e1bdf
git submodule update --init --recursive
git am /path/to/01-default-correctness.patch /path/to/02-region-paced-emission.patch /path/to/03-native-apu-integration.patch
python -m pytest tests/v2 tests/test_generation_recipe.py tests/test_timing_generation_identity.py tests/test_snes_cycles.py tests/test_beam_events.py tests/test_rdnmi.py -q
```

## Consumer qualification

The separate [consumer report](QUALIFICATION.md) records fresh gameplay,
current-build restoration and matched host cost. It includes a **failed canonical
audio-continuation check after ordinary save/load** shared by native and
interpreted runs. That failure is not waived by their mutual parity. The source
patch tests do not qualify the future merged prerequisite combination or PR
#241's version-11 state layout.

Original SNESRecomp author and license notices remain in place. This work comes
from the noncommercial Illusion of Gaia Companion fork of Babel by **mr0ta /
mrOt4**, maintained by **Carl Prewitt Jr. / rages4calm**. The earlier timing
investigation in #205, including pogoflow's report, informed this work. ROMs,
generated game code, saves, soundtrack data and raw private validation artifacts
are not part of these patches.
