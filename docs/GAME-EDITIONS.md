# Original and GaiaLabs editions

The owner's November 8 direction is to retain **at least two editions**:
**Original Gaia** and **GaiaLabs**. GaiaLabs work must not replace or silently
change the normal game. No edition picker or new runtime option is enabled by
this contract; the GaiaLabs dev-build identity and engine integration are pending.

| Edition | Current contract |
|---|---|
| Original | Fixed clean USA image, 2,097,152 bytes, SHA-256 `32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd`; retains the existing stock-ROM workflow. |
| GaiaLabs | Requires its exact resulting bare-ROM hash/size, separate full core/baserom/retranslation source commits, ordered modules, dependency-lock hash and module-preflight receipt hash. Provenance validation alone does not enable it in the engine. |

`scripts/gaia_editions.py` supplies the offline contract for future setup/build
integration. `original_profile()` accepts no caller overrides. Calling
`gaialabs_profile()` without all required identities fails; even a complete
profile is refused by `require_runtime_support()` until an actual GaiaLabs
runtime adapter is implemented and reviewed. No current public generator output
is assumed to be Kassiven's offered dev build.

## Isolation

Each profile has a deterministic SHA-256 over its edition and build identity.
Dictionary key ordering is canonicalized; **module ordering is preserved**.
Changing a source commit, selected module order, lock/preflight hash or ROM
identity creates a different profile. A missing or edited fingerprint is refused.

Future provisioned data paths are derived, never taken from a manifest:

```text
editions/original/<profile-id>/saves
editions/original/<profile-id>/settings
editions/original/<profile-id>/native/<graph-id>

editions/gaialabs/<profile-id>/saves
editions/gaialabs/<profile-id>/settings
editions/gaialabs/<profile-id>/native/<graph-id>
```

Save/settings and native-graph binding functions reject another edition,
another profile, path aliases or injected namespaces. Native bindings also
carry the exact ROM, framework, program-manifest and generation identities;
an Original graph cannot be rebound to GaiaLabs merely because symbols or
addresses happen to look similar. These descriptors are not save files and
are not proof that a generated graph is qualified.
The generation identity must bind the complete input/options recipe, not only
the generator's source hash: conservative and timed-live emission can share
the same ROM and structural manifest while producing different executable code.
`graph-id` is one full SHA-256 over those binding fields, avoiding three nested
hash directories in a normal Windows workspace.

The existing `build/saves`, owner settings, F1 states and installed 005 game
remain untouched. This utility does **not** create these future edition folders,
copy/migrate saves, edit settings, install patches, run upstream code or import
assets. Any later migration needs explicit compatibility handling; changing
an edition/profile must not silently adopt another profile's checkpoints.

## GaiaLabs input and existing fallback

Use the [module preflight](GAIALABS-MODULE-INTEGRATION.md) to bind the exact
clean source trees, file hashes and actual ordered module selection. The
GaiaLabs contract's `module_preflight_sha256` is the SHA-256 of that receipt;
its dependency lock hash is the exact lockfile used by the build. These fields
do not authenticate a developer, prove package bytes or establish that a ROM
was reproduced from the recipe. Retain the actual dev patch/build recipe and
result independently, then qualify execution.

`verify_gaialabs_inputs()` also reads the actual receipt and lockfile, checking
their bytes, selected module order and source commits against the profile.
The inspected npm package Git heads must match the declared core/baserom
source identities; current-branch files and an older published package cannot
silently be combined. This intentionally refuses the currently documented
branch/package mismatch. A deliberately different dependency/build mechanism
requires an explicit contract review, not guessing that it is equivalent.

The current engine's `src/iog_randomizer.c` swaps an IoGR image and forces
interpretation; stock-address features stand down while that seed is active.
`src/iog_ips.c` also forces interpretation when a code-changing Apocalypse
patch is active. Those guards illustrate why stock-generated functions must
not run on changed code. They are **not** existing GaiaLabs support, and the
current IPS loader cannot grow the cartridge image. GaiaLabs still needs a
deliberate import/profile adapter, guarded hooks and separately qualified native
generation. Interpreter/reference paths must remain available in both editions.

## Read-only preflight

For the owner's existing Original ROM, write a fresh private identity receipt:

```powershell
python scripts/gaia_editions.py --edition original --rom "Illusion of Gaia (USA).sfc" --output .local/batch-001/native-007/editions/original-preflight.json
```

The CLI verifies the bare-image hash, optionally stripping a 512-byte copier
header for hashing, and writes only metadata beneath ignored `.local/batch-001`.
It refuses existing outputs and symlink/junction input paths. A GaiaLabs
`--gaialabs-build` JSON must contain exactly the six documented build fields,
and the CLI also requires `--module-preflight` and `--dependency-lock` paths:

```text
rom_sha256, rom_size, source_commits,
modules_in_order, dependency_lock_sha256, module_preflight_sha256
```

`source_commits` contains `core`, `baserom` and `retranslation`, each a full
lowercase 40-character commit. `modules_in_order` is a nonempty list of distinct
plain module names. Hashes are lowercase SHA-256. No real GaiaLabs identity
example is supplied while the intended dev build is pending.

Synthetic checks:

```powershell
python -m unittest discover -s scripts -p test_gaia_editions.py -v
```

Preserve Babel author mr0ta / mrOt4 and every existing credit and notice.
GaiaLabs, retranslation authors and referenced modules retain their authorship
and applicable terms; this contract imports none of their implementation/assets.
