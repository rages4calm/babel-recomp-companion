# Consumer checks for timing issue 205

Checked November 3, 2026. These are fresh, bounded Illusion of Gaia consumer
checks, separate from the ROM-free extracted-patch tests. They do not qualify
the future merged prerequisite stack, PR #241's per-clock model, hardware timing
or a completed campaign.

## Fixed consumer identity

- Tested engine source: [`1ea3ab4`](https://github.com/rages4calm/babel-recomp-companion/commit/1ea3ab4a46af8a5d39f8ab991990c88b36fd31d5).
- Release executable SHA-256:
  `fa3a25028b72443f7998bc6da6a31c845f03adc4444e95ca51525f607db7ea7f`.
- Generated program manifest SHA-256:
  `5322a4e3f86935b45184bad90fb01026338680287f76bf1ed84d011e9aa6af7f`.
- Upstream main baseline: `66eebe6ae415b4fb2607a22e5b12352f612e1bdf`, with
  preserved Babel integration and the existing opt-in consumer timing work.
- Stock USA ROM identity:
  `32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd`.

One frozen executable runs both modes in fresh isolated processes. Native mode
uses the selected generated cohort; `SNESRECOMP_INTERPRET_ALL=1` retains the
consumer's canonical interpretation. The default public source/package build
remains interpreter-only. No owner save or installation is modified.

The extracted patches also refine default folded-branch metadata, preserve
compatibility with pending #243 codegen and restrict final-return refresh to
nonempty scheduling markers. Those refinements have executed synthetic/core
tests; this frozen consumer was not rebuilt from the extracted upstream tree.
The eventual merged base needs a new consumer build and fresh qualification.

## Fresh gameplay comparisons

| Workload | Frames per mode | Gameplay evidence | Result |
|---|---:|---|---|
| Natural 4:3 classroom to South Cape | 6,000 | Cold boot, dialogue, movement and original scene transition; no state load or injected flags | Pass |
| Aqueduct 8x room clear | 700 | Original attacks kill three bats; original room-clear reward applies the selected multiplier | Pass |
| Castoth fight | 5,000 | Continuous assisted fight through original defeat/outro; boosted stats, not stock-difficulty qualification | Pass |
| Freedan projectile | 600 | Original projectile effect occurs before a later lethal enemy hit; the matched workload includes that death segment | Pass |

All four fresh native/interpreter pairs match CPU/WRAM traces and CPU/master
totals, complete memory/PPU/APU/SPC/DSP/PCM-ring and scheduler state, device
journals, cycle-bound APU events and the full final image. The stronger executed
APU-cycle comparison and the older sample-index contract both pass. No physical
controller, speaker, natural acquisition or unboosted boss claim follows from
these assisted fixtures. Native execution was observed, not inferred from the
generated program's size.

## Current-build save/load: audio gate fails

Both modes produce a fresh ordinary runtime state from the current executable,
then new processes load each current state and continue with real input.
The native/interpreted save files are identical: 305,627 bytes, runtime format
version 10, with Gaia's register/resume-PC extension. Both restored modes match
each other through movement, scene entry, inventory open and return.

Aligned original-versus-restored CPU registers, WRAM, SRAM, VRAM, CGRAM, OAM and
framebuffer match. **Canonical audio continuation does not.** A separate
forced-interpreter-only no-input save/load check reproduces SPC RAM, APU timer,
DSP and SPC-register differences at four aligned continuation points. The
differences persist at 2, 3, 9 and 29 frames. They are not just discarded PCM
history or an interpreter/native timing disagreement.

The first restore probe also had a wrong scene expectation; the input naturally
reentered the church. Corrected probes preserve that original transition and
inventory return. The initial failed receipts remain retained. Neither that
fixture correction nor matching restored tiers changes the failed original
audio-continuation result.

Read-only source inspection found that ordinary snapshots and the separate
execution/rollback API preserve different clock/port-scheduler residue. Gaia's
ordinary extension stores registers and resume PC. PR #241 adds canonical
APU/DSP/SPC timing fields and version 11, but does not make all ordinary host
clock/port residue equivalent to the separate execution-state API. These are
investigation candidates, **not a proven cause or a proposed blind serializer
fix**. A first-divergence trace and combined-current-build restore check remain
required. No legacy/version-11 compatibility or audible continuation is claimed.

## Matched runtime cost

Cost measurements use the same four workloads, the same Release executable,
ROM, scripts, initial states and settings. High-volume trace, coverage and
snapshot exports are disabled. A single final image, guest CPU/master totals
and actual native execution are checked against the fresh diagnostic workloads.
Audio-device output is disabled; this is uncapped simulation cost, not a
physical audio/presentation benchmark.

Each workload has a warmup pair followed by six measured pairs arranged in
three order-balanced ABBA/BAAB blocks. Route/block orientation is randomized
with a fixed seed. Whole-process CPU time comes from Windows `GetProcessTimes`;
whole-process and frame-loop wall time and frame-loop CPU time are retained
separately. Compiler/test work is paused during the measured runs. This is
bounded workload cost, not whole-campaign performance.

All **56 runs** completed: eight warmups and 48 measured runs. Every run passed
the identity, execution-mode, CPU/master-total and final-image checks. The host
was Windows on an Intel Core Ultra 7 265F. Ratios below are native/interpreted;
lower means less host cost. Absolute times are medians for each mode; the ratios
are medians of the six matched pair ratios, not ratios of independent medians.

| Workload | Native process CPU, seconds | Interpreted process CPU, seconds | Paired CPU ratio, median [min, max] | Paired process-wall ratio, median |
|---|---:|---:|---|---:|
| Natural route | 10.015625 | 10.492188 | 0.950934 [0.945022, 0.959641] | 0.953608 |
| Aqueduct 8x clear | 1.062500 | 1.085938 | 0.978468 [0.916667, 1.014286] | 0.985116 |
| Castoth | 8.179688 | 8.679688 | 0.942238 [0.935943, 0.949275] | 0.944929 |
| Freedan projectile | 1.140625 | 1.218750 | 0.935897 [0.911392, 0.973684] | 0.937889 |

These samples show about 4.9%, 5.8% and 6.4% lower median process CPU cost for
the natural, Castoth and projectile workloads respectively. The short Aqueduct
case crosses a ratio of 1 and is **inconclusive**, despite its favorable median.
The projectile sample is also short and variable. No confidence interval,
universal speedup or lower-power platform qualification is asserted. These
measurements cannot waive the restore failure or qualify an unbuilt upstream
combination.

Raw traces, current saves, generated game code, images, per-run receipts and
private timing records remain excluded from the public source. This report
publishes the method, identities and summarized results only.
