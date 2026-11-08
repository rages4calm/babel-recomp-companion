# RomAtlas research: transferred Lagoon method

Inspected November 2, 2026. Lagoon was read-only throughout; its existing
qualification scope remains separate from this project.

## What Lagoon actually used

The retained local research tool is
`C:/Users/crono/Desktop/Projects/Lagoon/validation/tools/romatlas/romatlas.exe`:

- CLI version `0.1.0`, revision `0e58894598c67a60e344092fed1d3545873b4749`.
- Executable SHA-256
  `376109639e9a2a539f2d47ba8b32898433942869e34b43bc964c06c28d0fdfa6`;
  verified against the actual executable during this task.
- Its adjacent `provenance.json` records Rust 1.90.0 and a locked build. The
  retained Windows analysis patch refuses external assembler execution on
  Windows; it does not pretend Unix process-group handling works there.
- `LICENSES.md` identifies the combined CLI/SNES adapter as GPLv3 because of
  jgenesis; independent runtime crates retain their own licenses. Gaia does not
  link or redistribute this research executable or emulator implementation.

The concrete retained Lagoon workflow is documented in:

| Lagoon path | Purpose |
|---|---|
| `validation/native69/ROMATLAS-CLOSURE.md` | Scope, evidence limits, reset/mode transitions, code/data conflicts and continuation requirements |
| `validation/native69/analyze_romatlas_closure69.py` | Hash-bind original ROM/tool/generated program and eight retained routes; join observed PC/MX/E costs to exact manifest entries and generated labels; independently decode the highest-cost original-byte candidates |
| `validation/native69/check_static_closure69.py` | Validate export integrity and sample new, unobserved boundaries across represented banks with explicit width/emulation context |
| `validation/native69/romatlas-closure-index.json` | Compact planning index, separating callable entries, internal labels, missing entries and emulation contexts |

The existing research note records 3,333 observed PC/MX/E tuples, 758 legacy
manifest nodes, 508 roots and 9,465 internal labels across eight overlapping
routes. Its structural sample receipt records 65 independent boundary checks.
These are **retained historical research results**, not fresh execution of those
routes. Their counts are not native percentages or campaign proof.

Crucially, Lagoon's analysis distinguished original cartridge data from approved
live camera overlays, rejected assumed WRAM routines, and kept indirect targets
unresolved without evidence. RomAtlas provided an independent decoder and
structural cross-check; the SNESRecomp backend and matched execution supplied
the native implementation and timing proof. No whole-game Rust rewrite was used.

## Tool version decision

The latest [RomAtlas commit inspected](https://github.com/weisserw/romatlas/commit/3d0d1393149491777626f5a8e4461f7c49b2d6df)
is `3d0d1393149491777626f5a8e4461f7c49b2d6df`. GitHub's compare against the local
revision reports one commit and 170 changed files, all under `atlas/`; there
are no CLI, SNES adapter or decoder source changes in that range. Reusing the
verified existing analysis binary therefore avoids an unnecessary download or
build while keeping the actual analysis implementation current to that inspected
head. Future version decisions must repeat that check if upstream changes.

SNESRecomp is a separate dependency: its latest-framework integration and
qualification are recorded by the baseline audit/handoff. This research note
does not select, replace or modify the game runtime dependency.

## Gaia already has substantial research input

November 6 follow-up: the developer supplied the newer
[`Azarem/gaia-iog-baserom` documentation and patch tree](GAIALABS-DEVELOPER-NOTES.md).
Use that note for the pinned revision and pending comparison with the older
GaiaLabs inputs below. The following records the inputs actually used in the
earlier batches; it is not a claim that they cover the current baserom patches.

Do not rediscover the game from an empty map. Babel already includes
`tools/extract_gaialabs_symbols.py`, which extracts code-prefixed symbols from
GaiaLabs assembly and writes `recomp/bankNN.cfg`; the current twelve configs
contain 8,987 `func` declarations. These are analysis roots, **not** 8,987 proven
native functions or execution coverage. `recomp/symbols.toml` separately preserves
the two scaffold reset/NMI symbols as non-emitted seeds. Do not overwrite the
larger configs based on that small TOML alone.

[GaiaLabs](https://github.com/Azarem/GaiaLabs) uses branch `master`, with inspected
head `f7649eb735aaf19b2cd8f693fdaa6669b3e42711`. Existing useful inputs include
`GaiaLib/db/us/{blocks,files,labels,parts,scenes,copdef}.json`, the CPU/database
definitions, and `GaiaPacker`'s documented unpack workflow. The inspected US
metadata includes 806 block definitions and 405 label annotations; these counts
only describe those JSON lists. They are not whole-game code coverage. GaiaLabs
is GPL-3.0 licensed; preserve its attribution and review copied-source licensing
before importing any implementation. Reading its metadata does not license
distribution of the game or extracted assembly/assets.

The first native work should join these existing definitions to actual
SNESRecomp runtime observations, rather than launch RomAtlas's generic porting
scaffold. The generic `scripts/port.py` workflow creates a separate Rust port;
it is outside this project's chosen architecture.

## Actual Gaia probe completed

Used the existing binary directly against the owner's local ROM, without copying
the ROM, modifying Lagoon, changing a save, running an assembler or executing a
game. Private outputs are bounded inside `.local/batch-001/romatlas/` and excluded
from public source.

- `inspect` independently confirms the expected USA SHA-256
  `32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd`, a valid
  checksum, HiROM layout, 2 MiB payload, 8 KiB SRAM and reset vector `$00:8000`.
- Three bounded structural probes decode 18 instructions in total: the reset
  entry, its actual long-jump continuation and the `$82:804D..8051` NMI polling
  loop. All returned empty diagnostic lists. Cold reset establishes carry before
  exchanging emulation mode; the continuation changes register widths. These
  findings support exact mode-aware investigation, not a native execution claim.
- The wait-loop probe confirms the source-documented polling control flow around
  the NMI status register. It does not demonstrate that generated code handles
  deadlines correctly. The input M/X mode for that structural probe was explicitly
  supplied, not obtained from a fresh execution witness.
- `summary.json` binds probe files by hash and records both physical ROM offsets
  and logical CPU addresses. Decode output remains private; public documentation
  does not reproduce a generated game disassembly.

This CLI accepts **decimal** numeric arguments and needs both `--offset` and
`--cpu-address`. The latter labels the logical decode address; it does not select
the ROM bytes. Gaia is HiROM, so Lagoon's LoROM offset formula must not be copied.
For these verified cartridge windows the physical offset is the CPU address
masked with `$3FFFFF`; do not extend that rule to WRAM, SRAM or arbitrary bus
windows. Always check the mapper/source first.

For example, with paths supplied by the developer:

```powershell
& $RomAtlas inspect $RomPath
& $RomAtlas decode $RomPath --offset 32768 --cpu-address 32768 --count 4 --e true --m true --x true
& $RomAtlas decode $RomPath --offset 32788 --cpu-address 8421396 --count 12 --e false --m true --x true
& $RomAtlas decode $RomPath --offset 163917 --cpu-address 8552525 --count 2 --e false --m true --x false
```

## Next bounded native investigation

1. Freeze the current latest-framework baseline identity and obtain a short
   stock cold-boot route plus one in-play transition, recording actual PC, M, X,
   E, DB, direct page, stack, ROM/profile hash and interpreted instruction costs.
2. Join the first meaningful residuals to existing GaiaLabs/codegen definitions.
   Distinguish exact native entries, generated internal labels, unsupported
   context and missing decode. An enclosing min/max interval is only a candidate.
3. Use RomAtlas to independently decode only selected original-byte boundaries
   with their witnessed modes. For patched modes or WRAM code, capture the actual
   bytes and source generation; never substitute original-ROM bytes.
4. Fix demonstrated backend/entry/deadline gaps while retaining the interpreter
   safety net. Do not convert a polling loop into an unconditional native spin
   or disable fallback to hide the residual.
5. Replay identical ROM/profile, initial RAM/save state and inputs against the
   interpreter/reference. Compare the first architectural, RAM, frame or device
   divergence before expanding scope. Record hardware-service modeling separately
   from main-CPU execution.
6. Compact passed evidence and retain one small scratch batch. Publish source
   changes and ROM-free receipts only after focused regression checks; no ROM,
   generated game C, extracted assembly, saves or private captures enter GitHub.
