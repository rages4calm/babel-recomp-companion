# GaiaLabs module build-profile preflight

November 8, 2026. This adds an offline source-inspection tool, not a new game
mode or evidence that the current retranslation runs natively. The existing
stock-ROM native/interpreter baseline remains separate.

## Current sources and the missing dev-build identity

Live API reads still identify these public branches with the same revisions
recorded in the developer notes:

| Source | Inspected revision |
|---|---|
| [gaia-iog-baserom main](https://github.com/Azarem/gaia-iog-baserom/tree/0dcd500c5142ca4fd8639d6cd41a53442a0b62f6) | `0dcd500c5142ca4fd8639d6cd41a53442a0b62f6` |
| [IOGRetranslation dev](https://github.com/Azarem/IOGRetranslation/tree/754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc) | `754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc` |
| [gaia-core main](https://github.com/Azarem/gaia-core/tree/d90d2b2864de69960fb6d9e1c4334546a532da5b) | `d90d2b2864de69960fb6d9e1c4334546a532da5b` |

The latest public retranslation release inspected is `iog_rxlt_143`, published
October 17, 2025; no public dev-build release was found. The developer explicitly
said the generator is behind and offered a current dev build by DM. These
branches therefore do not identify that offered build.

This is the point to ask the owner to request a current patch/build recipe,
the exact source commits, selected modules in order, package lock/dependency
identities, expected resulting ROM hash and any required `.bso` configuration.
No agent outreach is implied. A historical generator output or release should
not be relabeled as the developer's current build.

## How the actual rebuild consumes maps and modules

Source tracing, without running upstream scripts, establishes:

1. Retranslation `scripts/index.ts` calls `rebuildInternal` from
   `@gaialabs/iog-baserom` with an explicit ordered module-path array.
2. Baserom `src/index.ts`, function `rebuild`, calls
   `DbRootUtils.rebuildAllContent` with `[inPath, baseRomPath, ...modulePaths]`.
3. Core `src/database/root.ts`, `rebuildAllContent` and `applyFolder`, walks
   each directory recursively. Files with the same basename and file type
   replace previously loaded content; later modules can override earlier ones.
4. Baserom `db-us/fileTypes.json` defines `.map` as `Tilemap`, a binary input
   with a two-byte header and `compressed: true`. `applyFolder` reads it as
   binary; assembly/patch/structured files take the text path. Core's rebuild
   processor handles compression according to the build configuration.

Thus the developer's raw-editor-file workflow has a concrete import path.
There is no need to invent a second map format or reproduce their assembly
patches in the host just to stage an external build. The current modules include
both `.map` assets and associated actor/warp/camera changes; copying only a map
would not establish equivalent behavior.

`scripts/generate-package.ts` is another path: it collects baserom files,
all module files and the player-facing manifest into static package JSON.
That is not the same as the ordered selection in `scripts/index.ts`.
`modules/manifest.json` options/defaults are not proof of active build choices.

The inspected development rebuild selects `dungeon-map` and
`walkable-world-map`, while `minimap-v2` and `widescreen` are commented out.
The widescreen module targets bsnes-hd's 384-column contract and a matching
`.bso`. Babel currently uses 342 columns with a different pixel-aspect policy.
Native renderer compatibility must be established separately.

## Dependency identities are not just version strings

Retranslation's committed lockfile and live npm metadata agree on:

| Dependency | Locked version | npm `gitHead` |
|---|---|---|
| `@gaialabs/core` | `1.0.5` | `131f130681da914070d48d5c8f1c0cbbf39b1782` |
| `@gaialabs/iog-baserom` | `0.2.7` | `3191832956c6a3e778a073f0432fe281440f5d73` |

The registry SHA-512 integrity strings match the committed lockfile. This was
a metadata comparison, not a download/build or verification of package bytes.
Neither npm source identity is the current source branch above: core main
declares version `1.0.7`, while baserom main still declares `0.2.7` despite
having a different commit. Do not silently replace dependencies or assume a
source checkout and the published package are identical.

The repository `LICENSE` files carry GPLv3 while their package manifests/locked
npm metadata declare MIT. Retain the actual notices and resolve which terms
apply to any implementation proposed for import. This task copies no upstream
implementation and makes no license change. Continue preserving Babel author
mr0ta / mrOt4, GaiaLabs, LThammy, ViewtifulSlayer, Igor Chagas, all existing
credits, and the widescreen module's VitorVilela7/wide-snes attribution.

## Offline inspector

`scripts/inspect_gaia_modules.py` accepts supplied clean external checkouts.
It never fetches source/packages, installs dependencies, runs Node/upstream
code, builds a ROM, edits the checkouts or copies their source/assets into this
repository. Each checkout must be at the supplied full 40-character commit.
Dirty worktrees, ignored additions inside inventoried module/baserom inputs,
symlinks/junctions, escaping paths, unpinned/mismatched dependencies and dynamic
module selection are refused.

Example, using already prepared private checkouts:

```powershell
python scripts/inspect_gaia_modules.py `
  --retranslation .local/batch-001/native-006/gaia-sources/retranslation `
  --retranslation-commit 754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc `
  --baserom .local/batch-001/native-006/gaia-sources/baserom `
  --baserom-commit 0dcd500c5142ca4fd8639d6cd41a53442a0b62f6 `
  --output .local/batch-001/native-006/gaia-sources/module-preflight-new.json
```

Use a new receipt filename for each run; existing receipts are not overwritten.
All detailed output is restricted to the project's ignored `.local/batch-001/`
tree. The JSON contains source/tree identities, source-file hashes, module asset
hashes, active order, commented modules, manifest choices and exact dependency
lock fields. It contains no source text or asset bytes.

Optional `--npm-metadata <local.json>` accepts an object keyed by the two
package names. Each value is the package version's registry JSON (`name`,
`version`, `dist.integrity`, `dist.tarball`, optional `gitHead`/`license`). It
must match the lockfile. This option reads a supplied file and makes no network
request; it does not authenticate package bytes or verify the installed
`node_modules` tree.

The parser intentionally supports the current literal one-entry-per-line
`const modules` array forwarded once to `rebuildInternal`. Changed/dynamic
scripts require review rather than inferred execution. Module-directory
hashes describe current inputs; they are not full extraction/build receipts.
The two-byte map-header check verifies the declared type contract, not the
contents or correctness of each copyrighted map. No profile is certified for
native execution by this inspection.

## Validation and the next profile boundary

The real pinned checkouts were fetched into
`.local/batch-001/native-006/gaia-sources/{baserom,retranslation}` and inspected
successfully with matching local npm metadata. The private receipt
`module-preflight.json` has SHA-256
`6743839c36f10142f43c6550e151691734fbba479139d001c203ecc0eddd3293`.
It hashes **32 module directories / 261 module files and 96 baserom files**,
with **22 active modules** and four commented modules. The active selection
includes `apocalypse-gaia`; it must not be assumed to be the desired ordinary
retranslation profile. Raw map inventory is separately summarized in
`profile-summary.json`. Both source worktrees remained clean. No upstream
script, assembler, generator or game was run during this preflight.

Run the synthetic safety tests with:

```powershell
python -m unittest discover -s scripts -p test_inspect_gaia_modules.py -v
```

They cover active/commented/manifest disagreement, dynamic or ambiguous arrays,
commit mismatches, dirty and ignored inputs, symlink/path escape, dependency
lock/registry mismatch, changed map contracts, strict JSON and private output
boundaries. No ROM, soundtrack, owner state or upstream executable is needed.
All **17 tests passed**, with no skips; the symlink refusal was exercised on
this machine. These checks qualify the inspector's stated safety boundaries,
not a native or emulator gameplay profile.

After receiving the intended dev-build identity, use the upstream build system
in the private scratch tree to produce and hash that exact profile from the
owner's ROM. Preserve original inputs and module order. Only then qualify its
boot, maps, flags, menus and audio in isolation. Stock-ROM native entries and
stock-address mod hooks must not run against relocated code/data by assumption.
The existing IoGR/Apocalypse interpreter guards are reference patterns, not
automatic support for a retranslation profile. New native generation must be
bound to the resulting ROM and validated against matched reference execution.
