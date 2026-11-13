# Project cleanup

Routine maintenance removes obsolete generated test output and duplicate runtime
copies after their consumers finish. Keep the current qualification batch, source,
receipts, required generation inputs, master builds and owner data. Do not grow a
new full fixture tree for each small check; reuse one bounded scratch batch.

For the explicitly retired classroom prank and old private preview executables,
use `Clean Disposable Files.cmd` (or pass `-Preview` first). Its PowerShell script
has a fixed allowlist: the `native-018/classroom-preview/nightclub` tree, its two
nightclub executables, and normal preview executables v1 through v17 in the
private 018 build directory. It also removes the explicitly retired
`babel-renderer-prelim-v1.exe` and `babel-owner-diagnostic-v1.exe` there; their
hashes match retained build receipts. The classroom worker confirmed the old
classroom executables are unused. It preserves normal v18, classroom
source/seeds/receipts, complete 018 final105 native and82 renderer proof,
current019 work, owner files, normal soundtrack,
SDKs and toolchains. It does not run the archival workflow described below.

The script rejects paths outside this project and reparse points, skips targets
referenced by running processes, and unlinks files individually without changing
permissions or forcing locks closed. Receipts under
`.local/project-cleanup/disposable-20261112/` list every result. If files are
locked, close their consumers and rerun the same CMD; absent targets are harmless.
Music hardlinks are unlinked without modifying the surviving original tracks.
Logical bytes removed, reported file-data allocation removed at the last link,
and observed volume free-space change are separate figures. Concurrent activity
and filesystem metadata prevent claiming the last figure as exact reclamation.

The CMD also runs `scripts/cleanup_obsolete_objects.ps1`. This second script
only accepts the SHA-bound reviewed plan at
`.local/project-cleanup/disposable-20261112/obsolete-objects-proposal.json`.
It retires 5,261 exact source-bound objects from 19 obsolete CMake build roots
in batches 006–015; 88 unmapped objects are retained. It checks each build's
project source home, source-file existence, object file identity/size, reparse
ancestors and running consumers. It keeps the build recipes, source and master
executables. Both scripts share the project cleanup lease and support `-Preview`.
A missing object plan is skipped; a changed plan is refused. Neither script
retries the blocked 016 SDK target or selects any 018/019 raw proof.

The third helper, `scripts/retire_old_raw.ps1`, skips immediately unless the
private completed019 coordinator GO marker exists. It accepts only the reviewed
SHA-bound 34,308-file plan for the old015 and017 `qualification-final` raw
outputs. Seven hash-bound closedproof gates require the new105 native pairs,
82 renderer pairs and independent closeout, five classroom pairs and independent
closeout, SDK877 checks and core proof. It also rebinds the reviewed input-consumer
JSON/scripts and verifies the selected replacement binary. Each unlink checks
project containment, reparse ancestors, file identity, size and modification
time, while denying writers. Running consumers and locked/changed files are
retained with a receipt; rerun the same CMD after closing their consumers.
After all34,308 files are verified absent, a small hash-bound completion marker
makes later runs an immediate no-op. Recreated historical data is not silently
deleted again under that completed operation.

November12 retirement completed after these new019 checks passed: 34,308 old raw
files /10,953,226,876 logical bytes /7,272,078,861 reported last-link file-storage
bytes removed, with no locks or failures. Together with the prank, old private
executables and compiler objects, this cleanup removed39,674 files /
12,268,759,786 logical bytes /7,876,538,315 reported last-link storage bytes.
The27 prank soundtrack hardlinks contribute zero storage savings. These are
reported file-data figures, not a claim of exact total physical volume recovery.

Old015/017 JSON summaries, profiles, journals, source, saved states and input
seeds remain. Their selected raw comparisons are **retired without an archive**
and are no longer available golden captures. Adjacent `RAW-RETIRED-20261112.json`
markers and the cleanup closeout bind that status; historical passed receipts
are not rewritten as new proof. The failed017 renderer matrix remains intact.
All current018 golden raw proof and complete019 proof remain. No owner ROM,
save, normal soundtrack, source baserom, master graph, SDK or toolchain is retired.

ROM-free guard checks: `python -m unittest discover -s scripts -p test_cleanup_disposable.py -v`.
The raw helper has nine additional checks:
`python -m unittest discover -s scripts -p test_retire_old_raw.py -v`.

At the November9 cleanup, complete012 raw qualification was retained. Older011
raw captures and selected obsolete widescreen/upstream test outputs were directly
retired at the owner's request; those files are **not archived**. Their receipts,
metadata, scripts and seeds remain as historical records. Do not claim those old
raw comparisons are immediately rerunnable. Current012 supplies the fresh proof.
Duplicate runtime copies have private restore maps to retained master binaries.
ROMs, soundtrack, owner saves/settings, source and master builds were preserved.

## Optional lossless archive tool

`Clean Project.cmd` is the slower archival option when old raw evidence needs to
remain recoverable. It is not required for routine removal of disposable build
output. Already archived cold fixtures can be restored with the commands below.

Run `Clean Project.cmd --preview` to list the cold selection and write a plan.
Double-click `Clean Project.cmd` to preview, archive, verify and then remove the
selected originals. Close runners and other consumers first. Compression can take
time and needs temporary free space for the archive while originals still exist.
Python 3.10 or newer is required (`py -3`, with `python` as a fallback).

All CLI modes, including preview and verification, hold an OS-backed project
lease at `.local/project-cleanup/run.lock`. A second operation refuses before
scanning; wait for the first operation to finish. The OS releases the lease when
its holder exits, including an interrupted process. Do not delete the lock file.
Timing wrappers may import `cleanup_lease` from `scripts/project_cleanup.py` and
hold `with cleanup_lease(project_root, "native timing"):` around their measurement.
Do not launch another guarded cleanup CLI inside an already held lease.

The tool only handles private files under this project's `.local`. It requires
`.local/cleanup-active.json` with schema `gaia active cleanup pins v1`, a nonempty
`active_batches` list and `protected_owner_inventory` pointing to the owner's
`protected_files` inventory. Missing or changed policy/inventory stops an old plan.
The project coordinator releases a previous batch only after its comparisons and
timing consumers finish; the current batch remains pinned. Do not remove pins to
work around a refusal.

Selection is limited to receipted native-route fixtures: raw TSV outputs, named
memory snapshots, PPM/BGRX/BMP/TGA raster captures and copied TTF/OTF fonts. The receipt schema is
`iog-native-route-v1`; failed runs are preserved in exactly the same reversible
way. All JSON, JSONL, CSV, `.log` files, source, profiles, receipts and configuration remain
direct files. ROMs, saves/states, MSU/music, owner folders, tools, existing archives,
active batches, executables and CMake build trees are excluded. The root `build`
directory and every source file outside `.local` are outside the mutation scope.
Other fixture formats and rebuildable caches are deliberately outside this tool's
initial selection.

The console prints the current phase, file count, logical bytes and elapsed time
as files are processed, throttled to one update per second. Preview still hashes every
selected original; a large cold cohort takes time. Receipt and directory
classification caches last for one operation and check receipt timestamps/sizes
for changes. Policy and owner inventory are fully rebound at operation boundaries;
their stamps are checked during mutations. Fresh ancestor/reparse and containment
checks remain mandatory before every removal or restored write. Existing identical
plans are reused; an interrupted/conflicting plan gets a new name and is preserved.

Every plan lists exact paths, lengths and SHA-256 identities and binds the project,
pins and owner inventory. A fresh ZIP stores one payload per unique SHA-256, with
an adjacent JSON index mapping every original path to its payload. Full streamed
decompression must reproduce every payload's length and SHA before an original
can be unlinked. Archive construction hashes each unique payload while writing
it; each duplicate source copy is checked separately at apply time. Apply rechecks
source contents and protections immediately before each removal. This is a
per-file fail-stop operation, not a transaction over the whole selection: if a
later file has changed, cleanup stops and leaves it in place. Earlier verified
removals remain recoverable from the complete verified archive. Archives and
indexes are never replaced or rebuilt; partial/failed archives stop the operation
and leave originals intact. Keep the entire `.local/project-cleanup` directory.

Windows sharing/lock violations (32/33) during unlink retain that verified file
and allow other verified files to be processed. The result lists every locked
path, its size and the pending totals; CLI exit code 3 means files remain locked.
Close the process using them, then resume `apply` with the **same plan**, without
rebuilding the archive. Access denied (5), changed contents, protection changes
and archive failures still stop the operation. Cleanup never changes permissions
or forces a lock closed.

For a smaller explicit cohort, use PowerShell from the project root:

```powershell
py -3 scripts/project_cleanup.py preview --prefix .local/batch-001/native-004
py -3 scripts/project_cleanup.py archive --plan .local/project-cleanup/plans/PLAN_ID.json
py -3 scripts/project_cleanup.py apply --plan .local/project-cleanup/plans/PLAN_ID.json
py -3 scripts/project_cleanup.py verify --index .local/project-cleanup/archives/PLAN_ID.json
py -3 scripts/project_cleanup.py restore --index .local/project-cleanup/archives/PLAN_ID.json --prefix .local/batch-001/native-004
```

Use the actual plan/index names printed by the tool. `clean --prefix ...` combines
preview, archive and apply. `apply` requires an already completed verified archive;
it can resume safely if some selected originals have already been removed. Restore
accepts a complete batch, run or narrower prefix, recreates original paths and
timestamps, and accepts existing files only when their bytes match. Conflicting
files, owner/pin protections, missing archives, corruption and reparse points cause
visible failures. Restore the full required fixture prefix **before** rerunning an
old comparison, coverage input or replay consumer; consumers have no automatic
archive reader. Preserve older standalone compactor archives and their own restore
instructions as well.

The scanner skips reparse points. Every mutation rechecks ancestor paths and
project containment; there is no recursive deletion. Run against a quiescent
workspace: filesystem checks cannot make a concurrent administrator or process
changing junctions/files safe. On an interrupted restore, inspect any partial file
that conflicts rather than overwriting it. Cleanup reports logical bytes removed
and archive size; hardlinks mean these are **not** a measurement of physical disk
space reclaimed.

The ROM-free tests use temporary fake workspaces:

```powershell
py -3 -m unittest discover -s scripts -p test_project_cleanup.py -v
```
