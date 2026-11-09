# November 8 framework integration

SNESRecomp main was inspected and integrated at
[`e98dc63b474d5469ad984490e04eb0b0496ec62e`](https://github.com/RetroPortingToolKit/snesrecomp/commit/e98dc63b474d5469ad984490e04eb0b0496ec62e),
following the earlier `f6912cd74e06eb21329aeb5c929d7f374479db80` pin.
The revision is frozen for this batch; this is not a perpetual latest-version
claim. This note covers source integration and ROM-free checks. Game build,
generated-cohort execution and owner-data checks have separate receipts.

## Preservation and source changes

The update inventories **1,378 paths before vendor mutation**, including
**403 local differences and 282 local-only files**, with explicit nested
repository identities. Both upstream trees and tracked local vendor files
were compared; text line endings were normalized for hashes, binary files
were kept exact. Changed files were staged as base/ours/upstream and merged
individually rather than replacing the vendor directory.

The actual Git comparison contains **80 changed paths across 29 commits**.
Four files had nine conflicting blocks. Resolutions retain Babel's hires
buffers and live-composite blend guard, GLES and presentation filters, and
HD sprite references, while incorporating upstream's wider buffer/clip
contract and exact nearest presentation. Executed JSL controls use the
upstream expanded test. All 1,295 nonoverlapping preserved paths remain
hash-identical; the only intentional additional nonoverlapping change adds
a region-emission regression test. Nested dependency pins are unchanged.

The merged work includes suspended-JSL/folded-branch fixes (#248), complete
beam-driver state (#249), first-visible-line HDMA (#252), mosaic bounds
(#253), HD Mode 7/presentation (#254/#255/#260), mode 2/3 sprite priority
(#256), five-bit brightness rounding (#257), due APU writes at the guest
boundary (#258), and world-provider/view-anchor rendering (#218).
Current upstream license and permission notices are retained alongside
Babel's existing notices; attribution is not replaced by this integration.

One **local carryover** needed semantic removal: our older paced-only
folded-branch workaround duplicated #248's now-shared cycle charge.
An executed interpreter comparison first failed by one CPU cycle and six
master clocks on a taken branch. Removing only that obsolete extra charge
restores parity. New taken/fallthrough, zero-offset and width controls execute
the actual generated code against interp816 with fast and slow code clocks.
The maintainer-rebased #250/#251 already have the correct shared behavior;
this was not a new upstream defect or a reason to overwrite those branches.

## Checks and retained failures

| Check | Result and boundary |
|---|---|
| Full framework Python attempt | **897 passed, 27 failed, 8 skipped.** This was the initial integrated source, before removing the duplicated local fold charge. It is not a passing full-suite gate. |
| Relevant recompiler/timing/beam/world-provider suite after the repair | **644 passed, 1 failed, 2 skipped.** The remaining failure was a Windows atomic rename denied during cache emission. That exact case and the earlier full-suite rename failure both pass in a fresh, shorter scratch directory. Retain the failed runs; do not call this one uninterrupted full-suite pass. |
| Folded branch/paced execution checks | **12 passed**, including the new eight-case matrix with both clock speeds. This overlaps the relevant-suite checks. |
| Rust | **108 library and 12 analyzer checks passed.** |
| Actual bridge contracts | **432 checks passed in each fused-read mode**, 27 interrupt checks passed, and cartridge CPU bus/latch checks passed. |
| PPU | **10 upstream harnesses passed** using Babel's required pthread linkage; the first missing-link attempts remain failed. An additional actual extra-OBJ harness passed. |
| APU guest boundary | The production due-port-write harness passed. This does not establish per-access SPC/DSP hardware timing. |
| GLSL | All three shared HD shader programs compile/link with Khronos glslang. Both desktop and GLES versions of the combined exact-nearest presentation fragment compile. No new physical-GPU gameplay claim. |

Of the 27 initial Python failures, 20 arise from POSIX scaffolder invocation
on Windows, one from a hardcoded absent compiler, one from upstream keyboard
enum positions that differ in Babel, three from fixture pthread linkage,
one from a Windows atomic rename and one from the actual duplicated folded
cycle charge. They were not hidden with skipped assertions or changed
production behavior. The extra-OBJ fixture passes when linked correctly.
The two MSU fixtures, once linked with pthread, reach runtime assertions
and **remain failed**. Their synchronous upstream expectations need separate
review against Babel's inherited asynchronous reader. `msu1.c` is hash-identical
to the before inventory; no music repair was attempted. These results do not
diagnose the owner's separately deferred clubhouse report.

The existing ROM-free legacy-prefill partial-tile witness still reports
seven failed overlap cases at the shared lookup API. This is the previously
[reported #218 witness](https://github.com/RetroPortingToolKit/snesrecomp/pull/218#issuecomment-6615383804),
not a newly discovered game regression. Keep caller-side native-pixel
authority and qualify the complete Gaia output before changing that guard.

## State and generation compatibility

The local instruction-block/region-pacing and native APU hooks remain
preservation deltas: #250/#251 are not merged into this main revision.
Existing generated C still uses those preserved APIs. Regeneration must use
the repaired emitter, not the transient double-charge integration candidate.
Interpreter/reference paths and conservative pre-effect refusal remain.

The ordinary guest state version remains **10** because #241 is unmerged.
Complete execution/rollback residue advances from **7 to 8**, adding PPU
hardware port/latch context and read-only validation. Beam-driver state and
raster APIs are additive. No mandatory title API edit was identified by
source inspection; old owner checkpoints still require copied-state testing.
Do not infer cross-build execution-residue or canonical audio restoration
from successful compilation or same-build native/interpreter parity.

## Upstream follow-up

- [#248](https://github.com/RetroPortingToolKit/snesrecomp/pull/248) merged.
  The maintainer refreshed [#250](https://github.com/RetroPortingToolKit/snesrecomp/pull/250)
  to `7ff96d580ace99d8b5957d2c16466a2a9d3a9a46` and
  [#251](https://github.com/RetroPortingToolKit/snesrecomp/pull/251)
  to `0d65b8d8a0a3983ed98e0a0ff936be7fff18524c`, based on `fb8cf15d`.
  Both remain drafts; all their executed CI jobs pass, with publishing skipped.
  Preserve these remote heads; the old exported patch set is historical.
- New [#205 timing leads](https://github.com/RetroPortingToolKit/snesrecomp/issues/205#issuecomment-6642246313)
  need individual disposition: indirect table-byte charges, (dp),Y crossing,
  H/V IRQ deadlines inside native spans, per-byte move refresh, unresolved
  indirect jump double charge, nested-gap deadlines and HDMA CPU stalls.
  The APU queued-write overrun is already fixed by merged #258.
- The [second-consumer #251 report](https://github.com/RetroPortingToolKit/snesrecomp/pull/251#issuecomment-6644942847)
  independently identifies native-span IRQ timing and frame-end beam/joypad
  synchronization, plus low-bit `apuCatchupCycles` differences. Its reported
  current-build restore and indicative cost results belong to that consumer
  and its explicitly modified binary; they do not replace Gaia qualification.
- Official main's [Linux C gate](https://github.com/RetroPortingToolKit/snesrecomp/actions/runs/42531706189/job/128887112562)
  fails linking `ppu_view_anchor_test`: its shell command omits `hd_jobs.c`,
  leaving `SnesHdFrame*` symbols unresolved. The Windows PPU runner includes
  that source and our correctly linked harness passes. The upstream failure
  log is retained. A separate `git archive` export of the exact official
  revision, without Babel files, also fails linking under Windows Clang;
  adding only `hd_jobs.c` links and the view-anchor executable passes.
  Searches for the fixture and unresolved symbol names found no existing
  report. Root reported [#263](https://github.com/RetroPortingToolKit/snesrecomp/issues/263)
  with the failed link and passing added-source control, and added that one
  missing source to the local shell harness. This changes test linking only.

Private inventories, staging/resolution decisions, exported hashes, compiler
commands, successful and failed logs are retained under the single ignored
`.local/batch-001/native-006/framework-update/` evidence folder. No ROM,
generated game code, music, save, gameplay capture or private receipt belongs
in the public source change.

## Batch 008 local additions

[Batch 008](NATIVE-BATCH-008.md) keeps the same inventoried main revision and
adds explicitly opt-in timed live data-immediate reads. Function/bank/program
emission, SDK CLI/recipe forwarding and both cache layers bind the new mode;
the old conservative mode remains available. No guest runtime ABI/state version
or vendor runtime tree is replaced. New ROM-free execution tests and fresh game
pairs qualify the stated bounded routes, not all hardware timing.

The scoped profile-boundary lookup optimization preserves exact validation
outcomes and is reported as [#265](https://github.com/RetroPortingToolKit/snesrecomp/issues/265).
An independently reproduced pre-existing first-entry-hook bus observation is
reported as [#266](https://github.com/RetroPortingToolKit/snesrecomp/issues/266);
it remains unfixed in this batch and is separate from the live operand result.
All new private source/cache/build/control identities are retained under
`native-008/`; published files contain no ROM-derived generated game code.
