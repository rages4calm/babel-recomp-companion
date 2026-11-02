# Native batch 003 planning and profile validation

This records the source and profiling basis for the next private native batch.
It does not qualify a new generated build. The selected batch 002 remains the
[natural-route-qualified mixed build](NATIVE-BATCH.md), with 6.2645% native CPU
cycles in 4:3 and 6.3244% in 16:9. New assisted areas have their own
[provenance and limits](NATIVE-BATCH-003.md).

## Selected-build residual

A fresh 6,000-frame capture uses selected executable
`f8f7f82ff37336ac24b1053ae89151668dd377cd2507ae09680d04c90a034680`,
program digest
`83f75543527addc1afb0a24e8598aca140ec818c408ef7263711954ab0ec0178`
and generation digest
`26903b94371c078f131e187a59900c3bc752c61b8058706f1a13660d9e9acc80`.
The checkpoint is complete and all four actual v2 loss counters are zero.
It contains 6,764 interpreted instruction contexts and 146 transfer records.

The same route has 255,149,254 total CPU cycles and 15,983,849 native cycles.
The new capture's 239,165,405 interpreted cycles account for the difference.
This is consistent accounting; matched guest/device state and rendered output
remain separate execution evidence in the batch 002 receipt.

| Selected generated classification | Residual contexts | Interpreted CPU cycles | Share of total CPU cycles |
|---|---:|---:|---:|
| Explicit source/timing policy guards | 596 | 184,774,597 | 72.4182% |
| Already generated paced instruction labels | 2,091 | 36,763,920 | 14.4088% |
| No exact generated entry or label | 3,968 | 12,834,278 | 5.0301% |
| Generated unconditional pacing fallback | 71 | 4,584,277 | 1.7967% |
| Exact manifest LLE variant | 38 | 208,333 | 0.0817% |

These categories describe actual interpreted hits against the selected emitted
tree. A generated label does not prove that a hit executed natively or that the
label is a callable host entry. The analysis reuses the existing structural
receipt and its completed 4,096 independent original-ROM boundary checks;
it does not repeat that decoding or claim campaign coverage.

## Expansion priority

The largest useful limit is indirect data-access timing within existing
generated bodies. An unsupported instruction currently tails into the
interpreter with the original return context, leaving subsequent generated
labels unused for that invocation. More roots or width hypotheses alone do not
remove this barrier.

The first cohort, in the `$80:BBxx` region, has 12,520,970 residual cycles at
already paced labels. Two indirect stores account for another 1,886,500 explicit
fallback cycles. The `$82:91xx` and `$82:82xx` regions contribute another
7,288,917 and 5,395,088 paced residual cycles, with indirect loads/stores among
their blockers. These are source-derived opportunity weights, not projected
native gains: MMIO-effective addresses, earlier fallbacks, branches, deadlines
and nested return contexts can prevent conversion.

The intended mechanism is opt-in pointer-access timing with one architectural
pointer fetch, exact effective-address/bank/wrap semantics, preserved E/M/X
state, and CPU/APU credit recorded at its origin. Eligibility guards must not
perform extra architectural pointer reads or probe MMIO. Unsupported cases
retain interpreter fallback. Internal labels must not be promoted into callable
entries merely to bypass ownership rules. Pointer timing changes require their
own focused differential tests before generation or route qualification.

The source policy continues to exclude vector trampolines, boot/vblank polling,
NMI/COP/RTI ownership and mutable actor/OAM patch ranges. Missing-label costs
also include APU MMIO polling and the mutable WRAM block-move stub; those costs
are not wholly promotable. Frame-scoped WRAM snapshots do not bind historical
instruction costs to immutable source bytes.

## Retaining historical roots honestly

The helper accepts repeatable `--historical-profile` alongside current
`--profile` arguments. Each historical checkpoint is validated independently
and recorded with its original identity, file hash, counts and cost summary.
Its costs are never combined with current-build costs. The SDK receives
`--historical-profile-manifest`, unions eligible analysis seeds and conservative
exclusions, and still performs its own promotion checks.

The three original checkpoints retain executable identity
`e53829c1cd01d5904b4b735d12976e970b9f315b7157d36cb67a979e39a03dc1`.
Their missing older `program_digest` metadata is explicitly recorded as
`legacy_metadata_missing_program_digest`; no file is relabeled or rebound to
the current program. These are v2 records with original ROM/build identity,
not a request to bind unverified v1 profiles. Current natural and assisted
profiles may share one current cost group only when their exact
ROM/module/mapper/program/build/generation identities agree. Overlapping
capture costs remain planning weights, not distinct gameplay coverage.

A real prepare-only smoke using the fresh mixed residual and all three original
historical checkpoints retained all 214 roots discovered from the historical
inputs by the current SDK. The fresh residual alone discovers only 37 roots;
native calls no longer appear as interpreter gaps. These are raw roots before
the source policy, not eligible or executed function counts. The selected older
graph contained 201 roots; eight additional raw roots are policy guarded and
five unguarded exact variants require current analysis. Their discovery is not
permission to loosen NMI guards or infer callee-return modes.

Indexed indirect goto landings still require a declared function boundary or a
separately proven dispatcher-tail/resume contract. Observed execution and
opcode/length agreement alone do not supply that contract.

## Bounded preparation and later qualification

The following prepares a new immutable private work directory. It does not
generate or build anything:

```powershell
python scripts/native_batch.py --prepare `
  --work .local/batch-001/native-003/candidate `
  --profile-only --instruction-blocks --region-paced `
  --max-insns 1024 --max-nodes 12000 `
  --profile .local/batch-001/native-003/planning/mixed-residual/tier2-manifest.json `
  --historical-profile .local/batch-001/native-002/profile-boot/capture.json `
  --historical-profile .local/batch-001/native-002/routes/school-capture/tier2-manifest.json `
  --historical-profile .local/batch-001/native-002/routes/southcape-v4/tier2-manifest.json
```

Add each completed current area checkpoint with another `--profile` only after
checking its exact current identity and source/assisted-test provenance. Keep
historical arguments independent. The default no-history command and receipt
shape remain unchanged. Adding, removing, reordering or changing historical
inputs invalidates reuse of an existing work directory.

Use exact observed widths and profile roots first, with all existing guards.
The selected graph used 888 nodes, a largest analyzed routine of 249
instructions, 143,265,792 bytes peak committed generation memory and 6.81 seconds
of generation time. Neither the 1,024-instruction limit nor the 12,000-node limit
was exhausted. Keep the initial generation process budget at 4,096 MiB and
300 seconds. Increase nodes to 24,000 only after a current-profile closure
actually reaches the node cap. A measured resource need may justify a new
immutable attempt with at most 8,192 MiB and 600 seconds. Unproven call exits
and truncated call continuations are not solved merely by raising decode limits.

Bulk enumeration of all 8,987 CFG declarations across four width hypotheses
would begin with 35,948 hypotheses before closure and would not address the
observed pointer-timing barrier. Candidate count is not the objective. Measure
actual native cycles and compare the first CPU/WRAM/frame/device divergence.
Retain the exact natural 4:3 and 16:9 comparison, then qualify each assisted
area under separately matched reference conditions. No new full-game native
or campaign claim follows from this planning work.

## Validation

The helper now refuses incomplete checkpoints and nonzero or malformed actual
v2 loss fields: `overflowed_tuples`, `dropped_cost_samples`,
`ram_routines_overflow` and `journal_write_failures`. It rejects duplicate JSON
keys, nonfinite constants and exponent overflow, negative/noninteger cost
counters, malformed arrays and cross-build cost aggregation. Historical
inputs pass those same checks independently. The official SDK still owns the
complete root eligibility and source analysis contract.

`python -m unittest discover -s scripts -p test_native_batch.py -v` passes
**17 tests**, including historical identity/cost separation, immutable receipt
reuse/refusals, preservation of the default receipt shape, malformed profile
refusals and the existing child-tree resource guards. All three original real
profiles retain exactly the same recorded counts, highest costs, identities
and hashes as their saved prepare receipt. The real historical smoke reused
its preparation receipt exactly and left all input files unchanged. No engine
or generator was run for these preparation checks.

Private planning, hash bindings and receipts are under
`.local/batch-001/native-003/planning/`; they remain excluded from public source
and packages with all ROMs, generated game code and gameplay captures.
